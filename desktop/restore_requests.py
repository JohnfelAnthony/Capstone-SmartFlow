"""Queue a single administrator-requested, fully prepared desktop restore."""
from __future__ import annotations

import threading
from pathlib import Path

from desktop.restore_switch import RestoreSwitch


class RestoreRequests:
    def __init__(self, paths, control_root: Path, frontend: Path):
        self.paths = paths
        self.switch = RestoreSwitch(control_root, paths.resources, frontend)
        self.lock = threading.Lock()
        self.pending = None
        self.claimed = False

    def prepare(self, backup_id: int) -> None:
        from services.backup_bundle import prepare_desktop_restore, restore_bundle_to_stage
        with self.lock:
            if self.pending is not None or self.claimed:
                raise ValueError("A desktop restore is already waiting to be activated")
            stage = restore_bundle_to_stage(backup_id)
            candidate = self.switch.candidate_path()
            prepare_desktop_restore(stage, candidate, self.paths.root / "config" / "installation-secret")
            self.pending = candidate

    def claim(self) -> str | None:
        if not self.lock.acquire(blocking=False):
            return None
        try:
            if self.pending is None:
                return None
            result = str(self.pending)
            self.pending = None
            self.claimed = True
            return result
        finally:
            self.lock.release()

    def release(self) -> None:
        with self.lock:
            self.claimed = False
