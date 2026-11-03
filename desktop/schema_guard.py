"""Desktop schema compatibility marker for future cooperating builds.

Increment this version when a desktop build makes an incompatible database
change. Historical builds that predate this guard cannot enforce it.
"""
import sqlite3
from contextlib import closing
from pathlib import Path

from desktop.paths import extended_path

DESKTOP_SCHEMA_VERSION = 1


def claim_schema_version(database: Path) -> None:
    database = extended_path(Path(database).absolute()).resolve()
    if not database.is_file():
        raise ValueError("Desktop database is missing")
    with closing(sqlite3.connect(database)) as connection:
        connection.execute("BEGIN IMMEDIATE")
        current = connection.execute("PRAGMA user_version").fetchone()[0]
        if current > DESKTOP_SCHEMA_VERSION:
            connection.rollback()
            raise ValueError(
                f"This database requires desktop schema version {current}, but this application supports "
                f"version {DESKTOP_SCHEMA_VERSION}. Reinstall the newer application or restore a compatible backup."
            )
        if current < DESKTOP_SCHEMA_VERSION:
            connection.execute(f"PRAGMA user_version = {DESKTOP_SCHEMA_VERSION}")
        connection.commit()
