"""Resource and user-data paths for the desktop prototype.

This module does not initialize the application or create credentials. Its
environment must be applied before importing SmartFlow's config or network modules.
"""
from __future__ import annotations

import hashlib
import json
import os
import sys
import uuid
from dataclasses import dataclass
from pathlib import Path


STUDY_SITE_RESOURCE_NAMES = (
    "tagum_site_a_mapping.json",
    "tagum_site_b_mapping.json",
    "tagum_site_a_peak_counts.json",
    "tagum_site_b_peak_counts.json",
)


def network_resource_names(source: Path) -> tuple[str, ...]:
    entries = json.loads((source / "registry.json").read_text(encoding="utf-8"))["networks"]
    names = ["tagum_network.json"]
    for entry in entries:
        names.append(entry["file"])
        names.extend(revision["file"] for revision in entry.get("revision_history", []))
    if any(Path(name).name != name or not name.endswith(".json") for name in names):
        raise ValueError("Invalid bundled network filename")
    return (*dict.fromkeys(names), "registry.json")


def _write_network(path: Path, content: bytes, *, replace: bool = False) -> None:
    temporary = path.with_name(".seed-" + uuid.uuid4().hex)
    try:
        with temporary.open("xb") as output:
            output.write(content)
            output.flush()
            os.fsync(output.fileno())
        if replace:
            os.replace(temporary, path)
        elif os.name == "nt":
            os.rename(temporary, path)
        else:
            os.link(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


# The registry and exact default geometry shipped in desktop builds through 0.1.2.
_LEGACY_STOCK_HASHES = {
    "tagum_site_a": "67932f463538ffc944cd3e6584326071d605558bf7ff7eddf64dcf24778a9785",
    "tagum_site_b": "4676bf9d3439e9b56a45439ac209fdeb730b8836373561568c43c5a1dc3e2e37",
}


def _source_hash(content: bytes) -> str:
    return hashlib.sha256(content.replace(b"\r\n", b"\n")).hexdigest()


def extended_path(path: Path) -> Path:
    """Use an extended Windows path without importing application configuration."""
    value = str(path)
    if os.name != "nt" or value.startswith("\\\\?\\"):
        return path
    return Path("\\\\?\\UNC\\" + value[2:] if value.startswith("\\\\") else "\\\\?\\" + value)


@dataclass(frozen=True)
class DesktopPaths:
    resources: Path
    root: Path

    @classmethod
    def discover(cls, *, data_root: Path | None = None, resources: Path | None = None):
        resource_root = resources or Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parents[1]))
        if data_root is None:
            local = os.environ.get("LOCALAPPDATA")
            if not local:
                raise RuntimeError("LOCALAPPDATA is required unless an explicit desktop data root is supplied")
            data_root = Path(local) / "SmartFlow"
        return cls(Path(resource_root).resolve(), Path(data_root).resolve())

    def environment(self) -> dict[str, str]:
        data = self.root / "data"
        return {"SMARTFLOW_DATA_DIR": str(data),
                "SMARTFLOW_DB_PATH": str(data / "smartflow.db"),
                "SMARTFLOW_NETWORK_PATH": str(data / "networks" / "tagum_network.json"),
                # Immutable revision filenames add a SHA-256 suffix; the parent
                # must support them even when the registry itself is short.
                "SMARTFLOW_NETWORK_REGISTRY_PATH": str(extended_path(data / "networks" / "registry.json")),
                "SMARTFLOW_IMPORT_DIR": str(data / "imports"),
                "SMARTFLOW_STUDY_ROOT": str(self.root)}

    def seed_networks(self) -> None:
        """Copy an explicit allowlist once; never overwrite user-edited resources."""
        if self.root == self.resources or self.resources in self.root.parents:
            raise ValueError("Desktop data must be outside the installation resources")
        source = self.resources / "data" / "networks"
        if not (source / "registry.json").is_file():
            raise FileNotFoundError("Desktop network resources are incomplete")
        names = network_resource_names(source)
        if any(not (source / name).is_file() for name in names):
            raise FileNotFoundError("Desktop network resources are incomplete")
        target = extended_path(self.root / "data" / "networks")
        target.mkdir(parents=True, exist_ok=True)
        for name in names:
            if (target / name).exists():
                continue
            try:
                _write_network(target / name, (source / name).read_bytes())
            except FileExistsError:
                continue

    def upgrade_stock_networks(self) -> None:
        """Move unchanged prior defaults to the bundled revisions while retaining their history."""
        target = extended_path(self.root / "data" / "networks")
        registry = target / "registry.json"
        if not registry.is_file() or registry.is_symlink():
            return
        previous = json.loads(registry.read_text(encoding="utf-8"))
        expected = {"networks": [{"id": site, "file": site + ".json"} for site in _LEGACY_STOCK_HASHES]}
        if previous != expected:
            return
        old_contents = {}
        for entry in previous["networks"]:
            path = target / entry["file"]
            if path.is_symlink() or not path.is_file():
                return
            content = path.read_bytes()
            if _source_hash(content) != _LEGACY_STOCK_HASHES[entry["id"]]:
                return
            old_contents[entry["id"]] = content

        from simulation.road_network import RoadNetwork

        source = self.resources / "data" / "networks"
        current = json.loads((source / "registry.json").read_text(encoding="utf-8"))
        for entry in current["networks"]:
            content = (source / entry["file"]).read_bytes()
            previous_file = entry["file"]
            entry["file"] = f'{entry["id"]}-{_source_hash(content)[:16]}.json'
            self._copy_upgrade_network(target / entry["file"], content)
            history = entry.setdefault("revision_history", [])
            for revision in history:
                self._copy_upgrade_network(target / revision["file"], (source / revision["file"]).read_bytes())
            fingerprint = RoadNetwork(json.loads(old_contents[entry["id"]])).fingerprint
            if all(revision["sha256"] != fingerprint for revision in history):
                history.append({"file": previous_file, "sha256": fingerprint})
        _write_network(registry, (json.dumps(current, indent=2) + "\n").encode("utf-8"), replace=True)

    @staticmethod
    def _copy_upgrade_network(path: Path, content: bytes) -> None:
        if path.is_symlink():
            raise ValueError(f"Cannot update the bundled networks because {path.name} is a symbolic link")
        try:
            _write_network(path, content)
        except FileExistsError:
            if _source_hash(path.read_bytes()) != _source_hash(content):
                raise ValueError(f"Cannot update the bundled networks because {path.name} already differs")
