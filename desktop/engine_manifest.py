"""Build and verify the frozen package's engine-source inventory."""
from __future__ import annotations

import hashlib
import json
import re
import subprocess
from pathlib import Path

REQUIRED = frozenset({"__init__.py", "traffic_engine.py", "road_network.py", "scenario_config.py"})
HEX = re.compile(r"^[0-9a-f]{64}$")


def _inventory(root: Path):
    paths = sorted((root / "simulation").glob("*.py"))
    if not REQUIRED.issubset({p.name for p in paths}):
        raise ValueError("Engine source inventory is incomplete")
    aggregate = hashlib.sha256()
    files = {}
    for path in paths:
        content = path.read_bytes()
        aggregate.update(path.name.encode("utf-8"))
        aggregate.update(content)
        files[path.name] = hashlib.sha256(content).hexdigest()
    return files, aggregate.hexdigest()


def create_manifest(root: Path) -> dict:
    files, aggregate = _inventory(root)
    try:
        revision = subprocess.run(["git", "rev-parse", "HEAD"], cwd=root, text=True, capture_output=True, timeout=10, check=True).stdout.strip()
        dirty = bool(subprocess.run(["git", "status", "--porcelain", "--untracked-files=no"], cwd=root, text=True, capture_output=True, timeout=10, check=True).stdout.strip())
    except (OSError, subprocess.SubprocessError):
        revision, dirty = None, None
    return {"format": 1, "files": files, "engine_content_sha256": aggregate, "source_revision": revision, "tracked_changes": dirty}


def verify_manifest(root: Path) -> dict:
    try:
        payload = json.loads((root / "engine-manifest.json").read_text(encoding="utf-8"))
        if not isinstance(payload, dict) or payload.get("format") != 1 or not isinstance(payload.get("files"), dict):
            raise ValueError("invalid manifest format")
        expected = payload["files"]
        if not REQUIRED.issubset(expected) or any(not isinstance(k, str) or Path(k).name != k or not k.endswith(".py") or not isinstance(v, str) or not HEX.fullmatch(v) for k, v in expected.items()):
            raise ValueError("invalid manifest inventory")
        files, aggregate = _inventory(root)
        if files != expected or aggregate != payload.get("engine_content_sha256"):
            raise ValueError("engine files do not match their build manifest")
        return payload
    except (OSError, ValueError, TypeError) as exc:
        raise ValueError(f"Packaged engine identity cannot be verified: {exc}") from exc
