"""Import named study inputs without manufacturing or certifying evidence."""
from __future__ import annotations

import hashlib
import json
import os
import uuid
from pathlib import Path

from services.field_observer_import import _validate_mapping
from services.site_validation import validate_criteria
from services.workload_admission import workload_admission
from simulation.network_registry import load_registered_network

SITES = {"tagum_site_a", "tagum_site_b"}
KINDS = {"mapping", "criteria", "ledger"}


class StaleStudyInput(ValueError):
    pass


def _directory(root: Path) -> Path:
    root = Path(root).resolve()
    sites = root / "data" / "sites"
    if sites.is_symlink() or not sites.resolve().is_relative_to(root):
        raise ValueError("Study input directory must remain inside desktop data")
    return sites


def _path(root: Path, site: str, kind: str) -> Path:
    if site not in SITES or kind not in KINDS:
        raise ValueError("Choose Site A or Site B and a supported evidence type")
    name = "validation_criteria.json" if kind == "criteria" else f"{site}_{kind}.json"
    path = _directory(root) / name
    if path.is_symlink():
        raise ValueError("Study input cannot be a symbolic link")
    return path


def _sha(content: bytes | None) -> str | None:
    return hashlib.sha256(content).hexdigest() if content is not None else None


def status(root: Path, site: str) -> dict:
    result = {}
    for kind in KINDS:
        path = _path(root, site, kind)
        data = path.read_bytes() if path.exists() else None
        result[kind] = {"filename": path.name, "sha256": _sha(data)}
    return {"site": site, "inputs": result}


def import_input(*, root: Path, site: str, kind: str, document: dict, expected_sha256: str | None,
                 user_id: int, audit) -> dict:
    path = _path(root, site, kind)
    if not isinstance(document, dict):
        raise ValueError("The selected file must contain a JSON object")
    lease = workload_admission.acquire("study evidence import")
    try:
        old = path.read_bytes() if path.exists() else None
        if _sha(old) != expected_sha256:
            raise StaleStudyInput("Study input changed; refresh and review it again")
        if kind == "mapping":
            network = load_registered_network(site)
            _validate_mapping(document, network)
            result = document
        elif kind == "criteria":
            incoming = document.get("sites")
            if not isinstance(incoming, dict) or site not in incoming:
                raise ValueError("Criteria file must contain the selected site under sites")
            validate_criteria(incoming[site])
            result = json.loads(old) if old is not None else {"schema_version": document.get("schema_version", 1), "sites": {}}
            if not isinstance(result, dict) or not isinstance(result.get("sites"), dict):
                raise ValueError("Existing validation criteria are malformed; preserve and repair them first")
            result["sites"][site] = incoming[site]
        else:
            if document.get("network_id", site) != site:
                raise ValueError("Ledger identifies another site")
            if not isinstance(document.get("held_out", {}), dict) or any(not isinstance(document.get(key, []), list) for key in ("accesses", "development_recordings", "informed_by")):
                raise ValueError("Ledger held_out must be an object and access histories must be lists")
            if any(not isinstance(item, dict) for item in document.get("accesses", [])):
                raise ValueError("Each ledger access must be an object")
            result = document
        content = (json.dumps(result, sort_keys=True, indent=2, ensure_ascii=False, allow_nan=False) + "\n").encode("utf-8")
        new_hash = _sha(content)
        if old == content:
            return {"changed": False, "sha256": new_hash, "message": "The same input is already present; field validity was not assessed."}
        details = json.dumps({"site": site, "kind": kind, "old_sha256": _sha(old), "new_sha256": new_hash}, sort_keys=True)
        audit(user_id=user_id, action="desktop_study_input_import_requested", target=site, details=details)
        path.parent.mkdir(parents=True, exist_ok=True)
        if old is not None:
            archive = path.parent / f"history-{kind}-{site[-1]}-{_sha(old)[:16]}.json"
            try:
                with archive.open("xb") as stream:
                    stream.write(old)
                    stream.flush()
                    os.fsync(stream.fileno())
            except FileExistsError:
                if archive.read_bytes() != old:
                    raise ValueError("A preserved study input has conflicting contents") from None
        temporary = path.with_name(f".study-input-{uuid.uuid4().hex}.tmp")
        try:
            with temporary.open("xb") as stream:
                stream.write(content)
                stream.flush()
                os.fsync(stream.fileno())
            if _sha(path.read_bytes() if path.exists() else None) != expected_sha256:
                raise StaleStudyInput("Study input changed during import; refresh and review it again")
            os.replace(temporary, path)
        finally:
            temporary.unlink(missing_ok=True)
        response = {"changed": True, "sha256": new_hash,
                    "message": "Input imported. Its accuracy and independence have not been verified; existing validation results may become stale."}
        try:
            audit(user_id=user_id, action="desktop_study_input_imported", target=site, details=details)
        except Exception:
            response["audit_warning"] = "Input was imported, but the completion audit entry could not be written."
        return response
    finally:
        workload_admission.release(lease)
