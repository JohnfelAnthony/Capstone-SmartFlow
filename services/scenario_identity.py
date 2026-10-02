"""Resume compatibility preserves inputs while allowing verified source relocation."""
import copy
import hashlib
import json
from pathlib import Path

import config


def _snapshot_identity(snapshot: dict) -> tuple[dict, list[dict]]:
    identity = copy.deepcopy(snapshot)
    settings = identity.get("engine_config", {})
    if isinstance(settings, str):
        settings = json.loads(settings)
        identity["engine_config"] = settings
    if not isinstance(settings, dict):
        raise ValueError("Resume requires the original training scenario snapshot.")
    source = settings.get("demand_source", {})
    datasets = source.get("datasets", []) if isinstance(source, dict) else []
    if not isinstance(datasets, list):
        datasets = []
    locations = []
    for dataset in datasets:
        if not isinstance(dataset, dict):
            continue
        digest = dataset.get("sha256")
        path = dataset.get("source_path")
        has_content_identity = (isinstance(digest, str) and len(digest) == 64
                                and all(character in "0123456789abcdef" for character in digest.lower()))
        if has_content_identity and isinstance(path, str) and path:
            locations.append({"source_path": path, "sha256": digest})
            del dataset["source_path"]
    return identity, locations


def validate_resume_snapshot(trained: dict, current: dict) -> None:
    if not isinstance(trained, dict) or not isinstance(current, dict):
        raise ValueError("Resume requires the original training scenario snapshot.")
    if trained == current:
        return
    trained_identity, trained_locations = _snapshot_identity(trained)
    current_identity, current_locations = _snapshot_identity(current)
    if trained_identity != current_identity:
        raise ValueError("Resume requires the original training scenario snapshot.")
    for previous, relocated in zip(trained_locations, current_locations):
        if previous["source_path"] == relocated["source_path"]:
            continue
        path = Path(relocated["source_path"])
        if not path.is_absolute():
            path = Path(config.BASE_DIR) / path
        hasher = hashlib.sha256()
        legacy_hasher = hashlib.sha256()
        trailing_cr = b""
        try:
            with path.open("rb") as stream:
                for chunk in iter(lambda: stream.read(1024 * 1024), b""):
                    hasher.update(chunk)
                    # Older Windows imports wrote text with LF -> CRLF conversion.
                    # Undo exactly that conversion, including CRLF split across chunks.
                    legacy_chunk = trailing_cr + chunk
                    trailing_cr = b"\r" if legacy_chunk.endswith(b"\r") else b""
                    if trailing_cr:
                        legacy_chunk = legacy_chunk[:-1]
                    legacy_hasher.update(legacy_chunk.replace(b"\r\n", b"\n"))
                legacy_hasher.update(trailing_cr)
        except OSError as exc:
            raise ValueError("Relocated demand source is missing or unreadable; resume was refused.") from exc
        if relocated["sha256"].lower() not in {hasher.hexdigest(), legacy_hasher.hexdigest()}:
            raise ValueError("Relocated demand source checksum differs from the training snapshot; resume was refused.")
