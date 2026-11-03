import sqlite3
import os
import subprocess
import sys
from contextlib import closing

import pytest

from desktop.migration_snapshot import snapshot_before_start


def test_snapshot_modules_do_not_import_network_or_config_before_desktop_setup():
    script = ("import sys; import desktop.migration_snapshot, desktop.schema_guard; "
              "assert 'simulation.road_network' not in sys.modules; "
              "assert 'simulation.network_registry' not in sys.modules; "
              "assert 'config' not in sys.modules")
    result = subprocess.run([sys.executable, "-c", script], capture_output=True, text=True, timeout=30)
    assert result.returncode == 0, result.stdout + result.stderr


def test_snapshot_contains_committed_wal_data_and_remains_independent(tmp_path):
    data = tmp_path / "data"
    data.mkdir()
    database = data / "smartflow.db"
    with closing(sqlite3.connect(database)) as live:
        live.execute("PRAGMA journal_mode=WAL")
        live.execute("CREATE TABLE evidence(value TEXT)")
        live.execute("INSERT INTO evidence VALUES ('before')")
        live.commit()
        snapshot = snapshot_before_start(database, data)
        live.execute("UPDATE evidence SET value='after'")
        live.commit()
        with closing(sqlite3.connect(snapshot)) as saved:
            assert saved.execute("SELECT value FROM evidence").fetchone() == ("before",)
            assert saved.execute("PRAGMA integrity_check").fetchone() == ("ok",)


def test_snapshot_refuses_missing_or_outside_database(tmp_path):
    data = tmp_path / "data"
    data.mkdir()
    with pytest.raises(ValueError, match="must exist"):
        snapshot_before_start(data / "missing.db", data)
    outside = tmp_path / "outside.db"
    outside.touch()
    with pytest.raises(ValueError, match="inside"):
        snapshot_before_start(outside, data)


def test_snapshot_failure_leaves_original_untouched(tmp_path):
    data = tmp_path / "data"
    data.mkdir()
    database = data / "smartflow.db"
    database.write_bytes(b"not sqlite")
    with pytest.raises(sqlite3.DatabaseError):
        snapshot_before_start(database, data)
    assert database.read_bytes() == b"not sqlite"
    assert not list((data / "pre-start-snapshots").iterdir())


@pytest.mark.skipif(os.name != "nt", reason="Windows extended-length path handling")
def test_snapshot_supports_a_long_restored_data_root(tmp_path):
    from desktop.schema_guard import DESKTOP_SCHEMA_VERSION, claim_schema_version
    from services.reviewed_revision_store import _long_path

    data = tmp_path / ("deep-" + "a" * 70) / ("nested-" + "b" * 70) / "data"
    _long_path(data).mkdir(parents=True)
    database = data / "smartflow.db"
    with closing(sqlite3.connect(_long_path(database))) as connection:
        connection.execute("CREATE TABLE evidence(value TEXT)")
        connection.execute("INSERT INTO evidence VALUES ('preserved')")
        connection.commit()
    snapshot = snapshot_before_start(database, data)
    with closing(sqlite3.connect(_long_path(snapshot))) as connection:
        assert connection.execute("SELECT value FROM evidence").fetchone() == ("preserved",)
        assert connection.execute("PRAGMA user_version").fetchone() == (0,)
    claim_schema_version(database)
    with closing(sqlite3.connect(_long_path(database))) as connection:
        assert connection.execute("PRAGMA user_version").fetchone() == (DESKTOP_SCHEMA_VERSION,)
        assert connection.execute("SELECT value FROM evidence").fetchone() == ("preserved",)
