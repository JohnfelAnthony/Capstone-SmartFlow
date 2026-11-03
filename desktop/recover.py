"""Operator recovery: put a pre-start snapshot back as the live database.

Run with SmartFlow closed:  SmartFlowWorker.exe recover [--data-root DIR] [--snapshot FILE]
Without --snapshot the newest snapshot is listed and used only with --yes.
"""
from __future__ import annotations

import argparse
import os
import sqlite3
import sys
import uuid
from contextlib import closing
from datetime import datetime, timezone
from pathlib import Path

from desktop.instance_lock import InstanceInUse, InstanceLock
from desktop.paths import DesktopPaths
from desktop.restore_switch import RestoreSwitch


def list_snapshots(data_root: Path) -> list[Path]:
    return sorted((data_root / "pre-start-snapshots").glob("pre-start-*.db"), reverse=True)


def recover(root: Path, snapshot: Path) -> Path:
    """Replace the live database with a verified snapshot; the old one is kept beside it."""
    data = root / "data"
    snapshot = data / "pre-start-snapshots" / snapshot.name  # only our own folder, by name
    if not (snapshot.name.startswith("pre-start-") and snapshot.suffix == ".db" and snapshot.is_file()):
        raise ValueError("Choose a snapshot file from the pre-start-snapshots folder")
    with closing(sqlite3.connect(snapshot.resolve().as_uri() + "?mode=ro", uri=True)) as check:
        if check.execute("PRAGMA integrity_check").fetchone() != ("ok",):
            raise ValueError("That snapshot failed its integrity check; try an older one")
    with InstanceLock(root):  # refuses while SmartFlow is running on this data root
        live = data / "smartflow.db"
        token = uuid.uuid4().hex
        kept = data / f"smartflow.db.replaced-{datetime.now(timezone.utc):%Y%m%dT%H%M%SZ}-{token}"
        if not live.exists() and (Path(str(live) + "-wal").exists() or Path(str(live) + "-shm").exists()):
            # An interrupted run already moved the database; put its WAL/SHM beside that copy.
            earlier = sorted(p for p in data.glob("smartflow.db.replaced-*") if not p.name.endswith(("-wal", "-shm")))
            kept = earlier[-1] if earlier else kept
        staged = data / f".recovery-{token}.db"
        moved = []
        try:
            # Finish and verify the replacement before touching the only live copy.
            with closing(sqlite3.connect(snapshot.resolve().as_uri() + "?mode=ro", uri=True)) as source, \
                    closing(sqlite3.connect(staged)) as target:
                source.backup(target)
                if target.execute("PRAGMA integrity_check").fetchone() != ("ok",):
                    raise ValueError("Staged recovery database failed integrity verification")
            with staged.open("r+b") as stream:
                os.fsync(stream.fileno())
            # Preserve the raw set even if the live database is corrupt. SQLite
            # recovers committed WAL pages when the kept database is opened.
            for suffix in ("", "-wal", "-shm"):
                original = Path(str(live) + suffix)
                preserved = Path(str(kept) + suffix)
                if original.exists():
                    original.rename(preserved)
                    moved.append((original, preserved))
            os.replace(staged, live)
        except BaseException:
            for original, preserved in reversed(moved):
                preserved.rename(original)
            raise
        finally:
            staged.unlink(missing_ok=True)
    return kept


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="recover", description=__doc__)
    parser.add_argument("--data-root", type=Path)
    parser.add_argument("--snapshot", type=Path, help="snapshot file name or path")
    parser.add_argument("--yes", action="store_true", help="use the newest snapshot")
    args = parser.parse_args(argv)
    paths = DesktopPaths.discover(data_root=args.data_root)
    try:
        # Match the launcher's lock and selection, including after restore.
        with InstanceLock(paths.root / "config" / "supervisor"):
            switch = RestoreSwitch(paths.root, paths.resources, paths.resources / "dist")
            # The launcher still refuses a missing database; recovery is how it comes back.
            return _recover_selected(switch.active_root(require_database=False), args)
    except InstanceInUse:
        print("SmartFlow is running on this data folder. Close it and try again.", file=sys.stderr)
        return 1
    except (ValueError, OSError, sqlite3.Error) as exc:
        print(f"Recovery failed: {exc}", file=sys.stderr)
        return 1


def _recover_selected(root: Path, args) -> int:
    snapshots = list_snapshots(root / "data")
    if not snapshots:
        print("No pre-start snapshots exist for this data folder.", file=sys.stderr)
        return 1
    chosen = args.snapshot
    if chosen is not None and not chosen.is_absolute():
        chosen = root / "data" / "pre-start-snapshots" / chosen.name
    if chosen is None:
        print("Snapshots, newest first:\n  " + "\n  ".join(p.name for p in snapshots))
        if not args.yes:
            print("Re-run with --snapshot NAME, or --yes for the newest.")
            return 2
        chosen = snapshots[0]
    try:
        kept = recover(root, chosen)
    except InstanceInUse:
        print("SmartFlow is running on this data folder. Close it and try again.", file=sys.stderr)
        return 1
    except (ValueError, OSError, sqlite3.Error) as exc:
        print(f"Recovery failed; nothing was replaced unless stated: {exc}", file=sys.stderr)
        return 1
    print(f"Restored {chosen.name} in {root}. The previous database and any WAL/SHM files were kept as {kept.name}.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
