"""Atomic registry storage for reviewed networks; not an authorization or safety gate.

The caller must hold the application workload/runtime exclusion, repeat all
validation, and audit the operation. This module is not exposed as an API.
"""
from __future__ import annotations

import json
import os
import uuid
from pathlib import Path

from simulation.network_registry import _entries, load_registered_network
from simulation.road_network import RoadNetwork


class RevisionConflict(ValueError):
    pass


def store_revision(registry_path: Path, network_id: str, expected_sha256: str, payload: dict) -> dict:
    """Install a revision in a trusted registry directory under caller-held exclusion.

    A stale expected fingerprint fails before the registry changes. Revision
    files are never overwritten; a failed commit can leave an unused immutable
    file but the previous registry stays readable.
    """
    registry_path = Path(registry_path).resolve()
    if network_id not in {"tagum_site_a", "tagum_site_b"} or not isinstance(payload, dict) or payload.get("id") != network_id:
        raise ValueError("The candidate must match a registered study site")
    old = load_registered_network(network_id, registry_path=registry_path)
    if old.fingerprint != expected_sha256:
        raise RevisionConflict("The installed network changed; review the draft again")
    candidate = RoadNetwork(payload)
    registry = json.loads(registry_path.read_text(encoding="utf-8"))
    _entries(registry_path)
    entry = next((item for item in registry["networks"] if item["id"] == network_id), None)
    if entry is None:
        raise ValueError("The study site is not present in the registry")
    if candidate.fingerprint == old.fingerprint:
        return {"old_sha256": old.fingerprint, "new_sha256": old.fingerprint, "file": entry["file"], "changed": False}
    history = entry.get("revision_history", [])
    if not isinstance(history, list) or any(not isinstance(item, dict) or not isinstance(item.get("file"), str) or
                                            not isinstance(item.get("sha256"), str) for item in history):
        raise ValueError("The network revision history is malformed")
    history = list(history)
    previous = {"file": entry["file"], "sha256": old.fingerprint}
    if previous not in history:
        history.append(previous)
    name = f"{network_id}-{candidate.fingerprint}.json"
    path = registry_path.parent / name
    content = json.dumps(payload, indent=2, ensure_ascii=False, allow_nan=False) + "\n"
    staging = registry_path.with_name(f".revision.{uuid.uuid4().hex}.tmp")
    try:
        with staging.open("x", encoding="utf-8") as stream:
            stream.write(content)
            stream.flush()
            os.fsync(stream.fileno())
        try:
            # Windows rename refuses an existing destination. On POSIX use a
            # hard link because rename would silently replace that revision.
            if os.name == "nt":
                os.rename(staging, path)
            else:
                os.link(staging, path)
        except FileExistsError:
            existing = RoadNetwork(json.loads(path.read_text(encoding="utf-8")))
            if existing.fingerprint != candidate.fingerprint:
                raise RevisionConflict("An existing immutable revision has unexpected contents") from None
    finally:
        staging.unlink(missing_ok=True)
    entry["file"] = name
    entry["revision_history"] = history
    temporary = registry_path.with_name(f".{registry_path.name}.{uuid.uuid4().hex}.tmp")
    try:
        with temporary.open("x", encoding="utf-8") as stream:
            json.dump(registry, stream, indent=2, ensure_ascii=False, allow_nan=False)
            stream.write("\n")
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, registry_path)
    finally:
        temporary.unlink(missing_ok=True)
    return {"old_sha256": old.fingerprint, "new_sha256": candidate.fingerprint, "file": name, "changed": True}
