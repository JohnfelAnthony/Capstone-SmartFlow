"""Record and verify an unsigned, disposable desktop bundle inventory."""
from __future__ import annotations

import argparse
import hashlib
import importlib.metadata
import json
import platform
from pathlib import Path


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def inventory(bundle: Path) -> dict:
    bundle = Path(bundle).resolve()
    if not bundle.is_dir() or not (bundle / "SmartFlow.exe").is_file() or not (bundle / "SmartFlowWorker.exe").is_file():
        raise ValueError("Select a complete two-executable desktop prototype folder")
    files = []
    for path in sorted(bundle.rglob("*")):
        if path.is_symlink():
            raise ValueError("Prototype inventories do not follow symbolic links")
        if path.is_file():
            files.append({"path": path.relative_to(bundle).as_posix(), "size": path.stat().st_size, "sha256": _sha256(path)})
    packages = sorted(f"{distribution.metadata['Name']}=={distribution.version}"
                      for distribution in importlib.metadata.distributions() if distribution.metadata.get("Name"))
    return {"schema": 1, "purpose": "unsigned prototype inventory; not a release signature or dependency lock",
            "python": platform.python_version(), "platform": platform.platform(), "packages": packages, "files": files}


def verify(bundle: Path, recorded: dict) -> bool:
    if not isinstance(recorded, dict) or recorded.get("schema") != 1 or not isinstance(recorded.get("files"), list):
        raise ValueError("Invalid prototype inventory")
    return inventory(bundle)["files"] == recorded["files"]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("bundle", type=Path)
    parser.add_argument("record", type=Path)
    parser.add_argument("--verify", action="store_true")
    args = parser.parse_args()
    if args.verify:
        if not verify(args.bundle, json.loads(args.record.read_text(encoding="utf-8"))):
            raise SystemExit("Prototype bundle differs from recorded inventory")
        print("Prototype bundle matches its unsigned inventory")
        return
    if args.record.resolve().is_relative_to(args.bundle.resolve()):
        parser.error("Write the inventory outside the bundle")
    result = inventory(args.bundle)
    with args.record.open("x", encoding="utf-8") as stream:
        json.dump(result, stream, indent=2)
        stream.write("\n")
    print(f"Recorded {len(result['files'])} files; inventory is unsigned")


if __name__ == "__main__":
    main()
