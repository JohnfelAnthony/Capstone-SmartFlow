"""Make a durable SQLite snapshot before desktop startup can migrate data."""
from __future__ import annotations

import os
import sqlite3
import uuid
from contextlib import closing
from datetime import datetime, timezone
from pathlib import Path

from desktop.paths import extended_path


KEEP_SNAPSHOTS = 10


def prune_snapshots(directory: Path, keep: int = KEEP_SNAPSHOTS) -> None:
    """Delete only our own named snapshots beyond the newest `keep`; names sort by UTC time."""
    old = sorted(directory.glob("pre-start-*.db"))[:-keep]
    for path in old:
        path.unlink(missing_ok=True)


def snapshot_before_start(database: Path, data_root: Path) -> Path:
    database = extended_path(Path(database).absolute()).resolve()
    data_root = extended_path(Path(data_root).absolute()).resolve()
    if not database.is_file() or not database.is_relative_to(data_root):
        raise ValueError("Desktop database must exist inside its data directory")
    directory = data_root / "pre-start-snapshots"
    if directory.is_symlink() or not directory.resolve().is_relative_to(data_root):
        raise ValueError("Snapshot directory must remain inside desktop data")
    directory.mkdir(parents=True, exist_ok=True)
    token = uuid.uuid4().hex
    temporary = directory / f".snapshot-{token}.tmp"
    final = directory / f"pre-start-{datetime.now(timezone.utc):%Y%m%dT%H%M%SZ}-{token}.db"
    try:
        # SQLite backup includes committed WAL pages; a filesystem copy may not.
        with closing(sqlite3.connect(database)) as source:
            source.execute("PRAGMA query_only=ON")
            with closing(sqlite3.connect(temporary)) as target:
                source.backup(target)
                if target.execute("PRAGMA integrity_check").fetchone() != ("ok",):
                    raise ValueError("Desktop database snapshot failed integrity verification")
        with temporary.open("r+b") as stream:
            os.fsync(stream.fileno())
        os.rename(temporary, final)
        prune_snapshots(directory)
        return final
    finally:
        temporary.unlink(missing_ok=True)
