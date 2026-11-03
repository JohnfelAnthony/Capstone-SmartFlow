"""Operating-system lock scoped to one desktop data directory."""
from __future__ import annotations

import os
from pathlib import Path


class InstanceInUse(RuntimeError):
    pass


class InstanceLock:
    def __init__(self, root: Path):
        self.root = Path(root).resolve()
        self.handle = None

    def __enter__(self):
        self.root.mkdir(parents=True, exist_ok=True)
        handle = (self.root / ".desktop-instance.lock").open("a+b")
        try:
            handle.seek(0)
            if os.name == "nt":
                import msvcrt
                msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                import fcntl
                fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError:
            handle.close()
            raise InstanceInUse("Another SmartFlow desktop instance is using this data directory.") from None
        self.handle = handle
        return self

    def __exit__(self, *_):
        if self.handle is None:
            return
        try:
            self.handle.seek(0)
            if os.name == "nt":
                import msvcrt
                msvcrt.locking(self.handle.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                import fcntl
                fcntl.flock(self.handle.fileno(), fcntl.LOCK_UN)
        finally:
            self.handle.close()
            self.handle = None
