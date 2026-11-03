"""Store a reviewed Field Observer ZIP without changing its evidence files."""
from __future__ import annotations

import io
import json
import os
import re
import stat
import tempfile
import uuid
import zipfile
from pathlib import Path

from services.field_observer_import import _load_revision

MAX_ARCHIVE_BYTES = 32 * 1024 * 1024
MAX_EXPANDED_BYTES = 64 * 1024 * 1024
MAX_FILES = 40
SAFE_NAME = re.compile(r"[A-Za-z0-9_][A-Za-z0-9_.-]{0,127}\.(?:json|csv)\Z")
REVISION_ID = re.compile(r"[0-9a-f]{32}\Z")


def _long_path(path: Path) -> Path:
    value = str(path)
    if os.name != "nt" or value.startswith("\\\\?\\"):
        return path
    return Path("\\\\?\\UNC\\" + value[2:] if value.startswith("\\\\") else "\\\\?\\" + value)


def import_reviewed_zip(content: bytes, study_root: Path) -> dict:
    if not content or len(content) > MAX_ARCHIVE_BYTES:
        raise ValueError("Reviewed ZIP is empty or exceeds the 32 MB limit")
    parent = _long_path(Path(study_root).resolve() / "data" / "reviewed-revisions")
    parent.mkdir(parents=True, exist_ok=True)
    try:
        with zipfile.ZipFile(io.BytesIO(content)) as archive:
            entries = archive.infolist()
            names = [item.filename for item in entries]
            if (not entries or len(entries) > MAX_FILES or len({name.casefold() for name in names}) != len(names)
                    or any(not SAFE_NAME.fullmatch(name) for name in names)
                    or sum(item.file_size for item in entries) > MAX_EXPANDED_BYTES
                    or any(item.is_dir() or item.flag_bits & 1 or stat.S_ISLNK(item.external_attr >> 16) for item in entries)):
                raise ValueError("Reviewed ZIP contains unsafe, duplicate or oversized entries")
            if "manifest.json" not in names:
                raise ValueError("Reviewed ZIP is missing manifest.json")
            with tempfile.TemporaryDirectory(prefix=".reviewed-", dir=parent) as temp:
                stage = Path(temp) / "revision"
                stage.mkdir()
                for item in entries:
                    (stage / item.filename).write_bytes(archive.read(item))
                manifest, _ = _load_revision(stage)
                hashes = manifest.get("artifact_sha256")
                if not isinstance(hashes, dict) or set(names) != {"manifest.json", *hashes}:
                    raise ValueError("Reviewed ZIP files must match the revision manifest")
                revision_id = uuid.uuid4().hex
                destination = parent / revision_id
                os.rename(stage, destination)
    except (zipfile.BadZipFile, KeyError, TypeError, json.JSONDecodeError) as exc:
        raise ValueError(f"Invalid reviewed ZIP: {exc}") from exc
    return {"id": revision_id, "revision": manifest.get("revision"), "survey_id": manifest.get("survey_id"),
            "take_id": manifest.get("take_id"), "publication_status": manifest.get("publication_status"),
            "message": "Reviewed files retained. This does not establish field validation."}


def revision_path(study_root: Path, revision_id: str) -> Path:
    if not isinstance(revision_id, str) or not REVISION_ID.fullmatch(revision_id):
        raise ValueError("Invalid reviewed revision ID")
    parent = _long_path(Path(study_root).resolve() / "data" / "reviewed-revisions").resolve()
    path = (parent / revision_id).resolve(strict=True)
    if path.parent != parent or not path.is_dir():
        raise ValueError("Reviewed revision is outside the study data directory")
    _load_revision(path)
    return path


def list_revisions(study_root: Path) -> list[dict]:
    parent = _long_path(Path(study_root).resolve() / "data" / "reviewed-revisions")
    if not parent.exists():
        return []
    result = []
    for item in sorted(parent.iterdir(), key=lambda entry: entry.name):
        if not REVISION_ID.fullmatch(item.name):
            continue
        try:
            path = revision_path(study_root, item.name)
            manifest = json.loads((path / "manifest.json").read_text(encoding="utf-8"))
            result.append({"id": item.name, "revision": manifest.get("revision"), "survey_id": manifest.get("survey_id"),
                           "take_id": manifest.get("take_id"), "publication_status": manifest.get("publication_status"), "error": None})
        except (ValueError, OSError, TypeError) as exc:
            result.append({"id": item.name, "error": str(exc)})
    return result
