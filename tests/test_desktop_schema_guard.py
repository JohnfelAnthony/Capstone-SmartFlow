import sqlite3
from contextlib import closing

import pytest

from desktop.schema_guard import DESKTOP_SCHEMA_VERSION, claim_schema_version


def test_unversioned_database_is_marked_without_changing_content(tmp_path):
    database = tmp_path / "db.sqlite"
    with closing(sqlite3.connect(database)) as connection:
        connection.execute("CREATE TABLE evidence(value TEXT)")
        connection.execute("INSERT INTO evidence VALUES ('kept')")
        connection.commit()
    claim_schema_version(database)
    claim_schema_version(database)
    with closing(sqlite3.connect(database)) as connection:
        assert connection.execute("PRAGMA user_version").fetchone() == (DESKTOP_SCHEMA_VERSION,)
        assert connection.execute("SELECT value FROM evidence").fetchone() == ("kept",)


def test_newer_database_is_refused_unchanged(tmp_path):
    database = tmp_path / "db.sqlite"
    future = DESKTOP_SCHEMA_VERSION + 1
    with closing(sqlite3.connect(database)) as connection:
        connection.execute(f"PRAGMA user_version = {future}")
        connection.execute("CREATE TABLE evidence(value TEXT)")
        connection.commit()
    with pytest.raises(ValueError, match="requires desktop schema version"):
        claim_schema_version(database)
    with closing(sqlite3.connect(database)) as connection:
        assert connection.execute("PRAGMA user_version").fetchone() == (future,)
        assert connection.execute("SELECT name FROM sqlite_master WHERE name='evidence'").fetchone()
