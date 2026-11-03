"""Desktop data-root selection and reversible backend switch.

The caller must hold a supervisor-wide lock, prepare the candidate from a
verified backup, and reload the window after a successful switch.
"""
from __future__ import annotations

import json
import os
import uuid
from pathlib import Path

from desktop.lifecycle import DesktopBackend
from desktop.paths import DesktopPaths


class RestoreSwitchError(RuntimeError):
    pass


class RestoreSwitch:
    def __init__(self, control_root: Path, resources: Path, frontend: Path, *, backend_factory=DesktopBackend):
        self.control_root = Path(control_root).resolve()
        self.resources = Path(resources).resolve()
        self.frontend = Path(frontend).resolve()
        self.backend_factory = backend_factory
        self.pointer = self.control_root / "config" / "active-data-root.json"
        self.candidates = self.control_root / "desktop-restored"

    def _validate_root(self, root: Path) -> Path:
        root = Path(root).resolve()
        if root != self.control_root and root.parent != self.candidates.resolve():
            raise ValueError("The selected desktop data root is outside restore storage")
        return root

    def active_root(self, *, require_database: bool = True) -> Path:
        if not self.pointer.exists():
            return self.control_root
        raw = json.loads(self.pointer.read_text(encoding="utf-8"))
        if not isinstance(raw, dict) or raw.get("version") != 1 or not isinstance(raw.get("root"), str):
            raise ValueError("Invalid desktop data-root selection")
        root = self._validate_root(Path(raw["root"]))
        if require_database and not (root / "data" / "smartflow.db").is_file():
            raise ValueError("The selected desktop database is missing; the previous data has not been removed")
        return root

    def candidate_path(self) -> Path:
        return self.candidates / ("restore-" + uuid.uuid4().hex)

    def _commit(self, root: Path) -> None:
        root = self._validate_root(root)
        self.pointer.parent.mkdir(parents=True, exist_ok=True)
        temporary = self.pointer.with_name(".active-" + uuid.uuid4().hex + ".json")
        try:
            with temporary.open("x", encoding="utf-8") as stream:
                json.dump({"version": 1, "root": str(root)}, stream)
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(temporary, self.pointer)
        finally:
            temporary.unlink(missing_ok=True)

    def activate(self, current: DesktopBackend, candidate: Path) -> tuple[DesktopBackend, str]:
        """Stop an idle backend, start the candidate, then persist the switch.

        Failure restarts the old backend and leaves the selection unchanged. The
        caller retains ownership of whichever backend is returned in the error.
        """
        old_root = self._validate_root(current.paths.root)
        candidate = self._validate_root(candidate)
        if candidate == old_root or candidate == self.control_root:
            raise ValueError("Choose a different restored data root")
        if self.active_root() != old_root:
            raise RestoreSwitchError("The active desktop data root changed; restart before restoring")
        if not (candidate / "data" / "smartflow.db").is_file():
            raise RestoreSwitchError("The restored candidate database is missing")
        accepted, reason = current.request_shutdown()
        if not accepted:
            raise RestoreSwitchError(reason or "Stop active work before restoring")
        current.stop()
        replacement = self.backend_factory(DesktopPaths(self.resources, candidate), self.frontend)
        replacement.control_root = self.control_root
        try:
            origin = replacement.start()
            self._commit(candidate)
            return replacement, origin
        except Exception as exc:
            replacement.stop()
            try:
                old_origin = current.start()
            except Exception as recovery:
                raise RestoreSwitchError(f"Restore failed and the previous backend could not restart: {recovery}") from exc
            error = RestoreSwitchError(f"Restore failed; the previous data is active again: {exc}")
            error.backend = current
            error.origin = old_origin
            raise error from exc
