import sqlite3
import json
import subprocess
import sys
from contextlib import closing

from desktop.instance_lock import InstanceLock
from desktop.migration_snapshot import KEEP_SNAPSHOTS, snapshot_before_start
from desktop.recover import list_snapshots, main, recover


def test_recovery_preserves_committed_wal_after_crash(tmp_path):
    data = make_root(tmp_path, "snapshot")
    snapshot = snapshot_before_start(data / "smartflow.db", data)
    code = "import sqlite3,sys,os; c=sqlite3.connect(sys.argv[1]); c.execute('PRAGMA journal_mode=WAL'); c.execute('PRAGMA wal_autocheckpoint=0'); c.execute(\"UPDATE t SET v='committed after snapshot'\"); c.commit(); os._exit(0)"
    subprocess.run([sys.executable, "-c", code, str(data / "smartflow.db")], check=True)
    assert (data / "smartflow.db-wal").is_file()
    kept = recover(tmp_path, snapshot)
    assert value(kept) == "committed after snapshot"
    assert value(data / "smartflow.db") == "snapshot"


def test_default_recovery_follows_active_selection(tmp_path, monkeypatch):
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))
    control = tmp_path / "SmartFlow"
    control.mkdir()
    make_root(control, "inactive")
    active = control / "desktop-restored" / "restore-test"
    active.mkdir(parents=True)
    data = make_root(active, "good")
    snapshot_before_start(data / "smartflow.db", data)
    make_root(active, "bad")
    (control / "config").mkdir()
    (control / "config" / "active-data-root.json").write_text(json.dumps({"version": 1, "root": str(active)}))
    assert main(["--yes"]) == 0
    assert value(data / "smartflow.db") == "good"
    assert value(control / "data" / "smartflow.db") == "inactive"
    with InstanceLock(control / "config" / "supervisor"):
        assert main(["--yes"]) == 1


def test_recovery_staging_failure_keeps_live_database(tmp_path, monkeypatch):
    import desktop.recover as module
    data = make_root(tmp_path, "old")
    snapshot = snapshot_before_start(data / "smartflow.db", data)
    make_root(tmp_path, "current")
    original = module.sqlite3.connect
    def fail_stage(path, *args, **kwargs):
        if ".recovery-" in str(path):
            raise OSError("disk full")
        return original(path, *args, **kwargs)
    monkeypatch.setattr(module.sqlite3, "connect", fail_stage)
    import pytest
    with pytest.raises(OSError, match="disk full"):
        recover(tmp_path, snapshot)
    assert value(data / "smartflow.db") == "current"


def test_recovery_switch_failure_restores_original_files(tmp_path, monkeypatch):
    import desktop.recover as module
    import pytest
    data = make_root(tmp_path, "snapshot")
    snapshot = snapshot_before_start(data / "smartflow.db", data)
    make_root(tmp_path, "current")
    def fail_switch(*_args):
        raise OSError("replacement denied")
    monkeypatch.setattr(module.os, "replace", fail_switch)
    with pytest.raises(OSError, match="replacement denied"):
        recover(tmp_path, snapshot)
    assert value(data / "smartflow.db") == "current"
    assert not list(data.glob(".recovery-*"))


def make_root(tmp_path, value):
    data = tmp_path / "data"
    data.mkdir(exist_ok=True)
    with closing(sqlite3.connect(data / "smartflow.db")) as db:
        db.execute("CREATE TABLE IF NOT EXISTS t(v TEXT)")
        db.execute("DELETE FROM t")
        db.execute("INSERT INTO t VALUES (?)", (value,))
        db.commit()
    return data


def value(path):
    with closing(sqlite3.connect(path)) as db:
        return db.execute("SELECT v FROM t").fetchone()[0]


def test_snapshots_are_pruned_to_the_newest(tmp_path):
    data = make_root(tmp_path, "x")
    for _ in range(KEEP_SNAPSHOTS + 3):
        snapshot_before_start(data / "smartflow.db", data)
    assert len(list_snapshots(data)) == KEEP_SNAPSHOTS


def test_recover_restores_snapshot_and_keeps_replaced_database(tmp_path):
    data = make_root(tmp_path, "good")
    snapshot = snapshot_before_start(data / "smartflow.db", data)
    make_root(tmp_path, "damaged")
    kept = recover(tmp_path, snapshot)
    assert value(data / "smartflow.db") == "good"
    assert value(kept) == "damaged"


def test_recover_refuses_while_running_and_foreign_files(tmp_path, capsys):
    data = make_root(tmp_path, "good")
    snapshot = snapshot_before_start(data / "smartflow.db", data)
    with InstanceLock(tmp_path):
        assert main(["--data-root", str(tmp_path), "--snapshot", snapshot.name]) == 1
    assert "running" in capsys.readouterr().err
    outside = tmp_path / "other.db"
    outside.write_bytes(snapshot.read_bytes())
    try:
        recover(tmp_path, outside)
        raise AssertionError("foreign snapshot accepted")
    except ValueError:
        pass
    assert value(data / "smartflow.db") == "good"


def test_recovery_restores_into_selected_root_whose_database_is_missing(tmp_path, monkeypatch):
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))
    control = tmp_path / "SmartFlow"
    control.mkdir()
    make_root(control, "inactive")
    active = control / "desktop-restored" / "restore-test"
    active.mkdir(parents=True)
    data = make_root(active, "good")
    snapshot_before_start(data / "smartflow.db", data)
    (data / "smartflow.db").unlink()
    (control / "config").mkdir()
    (control / "config" / "active-data-root.json").write_text(json.dumps({"version": 1, "root": str(active)}))
    assert main(["--yes"]) == 0
    assert value(data / "smartflow.db") == "good"


def test_recovery_still_validates_the_selected_root(tmp_path, monkeypatch):
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))
    control = tmp_path / "SmartFlow"
    (control / "config").mkdir(parents=True)
    outside = tmp_path / "elsewhere"
    outside.mkdir()
    make_root(outside, "x")
    (control / "config" / "active-data-root.json").write_text(json.dumps({"version": 1, "root": str(outside)}))
    assert main(["--yes"]) == 1


def test_rerun_after_crash_between_renames_keeps_the_set_together(tmp_path):
    data = make_root(tmp_path, "snapshot")
    snapshot = snapshot_before_start(data / "smartflow.db", data)
    code = "import sqlite3,sys,os; c=sqlite3.connect(sys.argv[1]); c.execute('PRAGMA journal_mode=WAL'); c.execute('PRAGMA wal_autocheckpoint=0'); c.execute(\"UPDATE t SET v='committed'\"); c.commit(); os._exit(0)"
    subprocess.run([sys.executable, "-c", code, str(data / "smartflow.db")], check=True)
    first = data / "smartflow.db.replaced-20260101T000000Z-aaaa"
    (data / "smartflow.db").rename(first)  # simulated crash: the WAL is still at the live name
    kept = recover(tmp_path, snapshot)
    assert kept == first
    assert (data / (first.name + "-wal")).is_file()
    assert value(first) == "committed"
    assert all("aaaa" in p.name for p in data.glob("smartflow.db.replaced-*"))  # no second, split kept set
    assert value(data / "smartflow.db") == "snapshot"
