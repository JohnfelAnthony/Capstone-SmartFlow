import sqlite3
from contextlib import closing

from desktop.instance_lock import InstanceLock
from desktop.migration_snapshot import KEEP_SNAPSHOTS, snapshot_before_start
from desktop.recover import list_snapshots, main, recover


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
