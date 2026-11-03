"""Resource and user-data paths for the desktop prototype.

This module does not initialize the application or create credentials. Its
environment must be applied before importing SmartFlow's config or network modules.
"""
from __future__ import annotations

import os
import shutil
import sys
import uuid
from dataclasses import dataclass
from pathlib import Path


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
        names = ("registry.json", "tagum_network.json", "tagum_site_a.json", "tagum_site_b.json")
        source = self.resources / "data" / "networks"
        if any(not (source / name).is_file() for name in names):
            raise FileNotFoundError("Desktop network resources are incomplete")
        target = self.root / "data" / "networks"
        target.mkdir(parents=True, exist_ok=True)
        for name in names:
            temporary = target / (".seed-" + uuid.uuid4().hex)
            try:
                with temporary.open("xb") as output, (source / name).open("rb") as input_file:
                    shutil.copyfileobj(input_file, output)
                    output.flush()
                    os.fsync(output.fileno())
                if os.name == "nt":
                    # Windows rename fails if the destination already exists.
                    os.rename(temporary, target / name)
                else:
                    os.link(temporary, target / name)
            except FileExistsError:
                continue
            finally:
                temporary.unlink(missing_ok=True)
