import json
import os
import queue
import shutil
import sqlite3
import subprocess
import sys
import threading
import urllib.error
import urllib.request
from pathlib import Path

import pytest

from desktop.lifecycle import DesktopBackend
from desktop.paths import DesktopPaths


ROOT = Path(__file__).resolve().parents[1]


def test_source_backend_readiness_and_authentication(tmp_path):
    resources = tmp_path / "resources"
    networks = resources / "data" / "networks"
    networks.mkdir(parents=True)
    for name in ("registry.json", "tagum_network.json", "tagum_site_a.json", "tagum_site_b.json"):
        shutil.copyfile(ROOT / "data" / "networks" / name, networks / name)
    frontend = resources / "dist"
    frontend.mkdir()
    (frontend / "index.html").write_text("desktop test", encoding="utf-8")
    root = tmp_path / "user data"
    clean_env = {k: v for k, v in os.environ.items() if not k.startswith("SMARTFLOW_")}
    setup = subprocess.run([sys.executable, "-m", "desktop.bootstrap"], cwd=ROOT, env=clean_env,
                           input=json.dumps({"data_root": str(root), "resources": str(resources), "password": "StrongPass123"}),
                           text=True, capture_output=True, timeout=45)
    assert setup.returncode == 0, setup.stdout + setup.stderr
    edited_site = root / "data" / "networks" / "tagum_site_a.json"
    site_payload = json.loads(edited_site.read_text(encoding="utf-8"))
    site_payload["name"] = "Synthetic user-data site"
    edited_site.write_text(json.dumps(site_payload), encoding="utf-8")
    process = subprocess.Popen([sys.executable, "-m", "desktop.serve"], cwd=ROOT, env=clean_env,
                               stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    try:
        nonce = "private-test-identity-1234567890"
        process.stdin.write(json.dumps({"data_root": str(root), "resources": str(resources), "frontend": str(frontend), "nonce": nonce}) + "\n")
        process.stdin.flush()
        output = queue.Queue()
        threading.Thread(target=lambda: output.put(process.stdout.readline()), daemon=True).start()
        try:
            line = output.get(timeout=45)
        except queue.Empty:
            pytest.fail("Desktop backend did not return a readiness response")
        response = json.loads(line)
        assert response.get("ready"), response
        snapshots = list((root / "data" / "pre-start-snapshots").glob("pre-start-*.db"))
        assert len(snapshots) == 1
        # Bootstrap produced an unversioned database; startup snapshots it
        # before setting the desktop marker or running application migrations.
        with sqlite3.connect(snapshots[0]) as snapshot:
            assert snapshot.execute("PRAGMA user_version").fetchone() == (0,)
            assert snapshot.execute("SELECT username FROM users WHERE username='admin'").fetchone() == ("admin",)
        with sqlite3.connect(root / "data" / "smartflow.db") as live:
            from desktop.schema_guard import DESKTOP_SCHEMA_VERSION
            assert live.execute("PRAGMA user_version").fetchone() == (DESKTOP_SCHEMA_VERSION,)
        assert response["nonce"] == nonce
        origin = response["origin"]
        assert origin.startswith("http://127.0.0.1:")
        with urllib.request.urlopen(origin + "/api/health", timeout=5) as result:
            assert json.load(result)["status"] == "healthy"
        duplicate = DesktopBackend(DesktopPaths.discover(data_root=root, resources=resources), frontend)
        with pytest.raises(RuntimeError, match="Another SmartFlow desktop instance"):
            duplicate.start(timeout=20)
        with urllib.request.urlopen(origin + "/api/health", timeout=5) as result:
            assert json.load(result)["status"] == "healthy"
        with urllib.request.urlopen(origin + "/dashboard", timeout=5) as result:
            assert result.read().decode() == "desktop test"
        preference = urllib.request.Request(origin + "/api/desktop/preferences", data=json.dumps({"key": "smartflow-theme", "value": "light"}).encode(), headers={"Content-Type": "application/json", "Origin": origin})
        with urllib.request.urlopen(preference, timeout=5) as result:
            assert json.load(result)["ok"]
        body = json.dumps({"username": "admin", "password": "StrongPass123"}).encode()
        denied = urllib.request.Request(origin + "/api/auth/login", data=body, headers={"Content-Type": "application/json", "Origin": "http://evil.example"})
        with pytest.raises(urllib.error.HTTPError) as error:
            urllib.request.urlopen(denied, timeout=5)
        assert error.value.code == 403
        allowed = urllib.request.Request(origin + "/api/auth/login", data=body, headers={"Content-Type": "application/json", "Origin": origin})
        with urllib.request.urlopen(allowed, timeout=5) as result:
            assert result.status == 200
            assert "smartflow_api_session=" in result.headers["Set-Cookie"]
            cookie = result.headers["Set-Cookie"].split(";", 1)[0]
        with urllib.request.urlopen(urllib.request.Request(origin + "/api/networks", headers={"Cookie": cookie}), timeout=10) as result:
            assert next(site for site in json.load(result) if site["id"] == "tagum_site_a")["name"] == "Synthetic user-data site"
    finally:
        process.terminate()
        try:
            process.wait(timeout=10)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait(timeout=10)
        process.stdout.close()
        process.stderr.close()
        process.stdin.close()
    backend = DesktopBackend(DesktopPaths.discover(data_root=root, resources=resources), frontend)
    try:
        origin = backend.start()
        owned = backend.process
        with urllib.request.urlopen(origin + "/api/health", timeout=5) as result:
            assert json.load(result)["status"] == "healthy"
        with urllib.request.urlopen(origin + "/api/desktop/preferences", timeout=5) as result:
            assert json.load(result)["smartflow-theme"] == "light"
        login = urllib.request.Request(origin + "/api/auth/login", data=body, headers={"Content-Type": "application/json", "Origin": origin})
        with urllib.request.urlopen(login, timeout=5) as result:
            cookie = result.headers["Set-Cookie"].split(";", 1)[0]
        headers = {"Content-Type": "application/json", "Origin": origin, "Cookie": cookie}
        start = urllib.request.Request(origin + "/api/simulation/start", data=json.dumps({"scenario_id": 1, "duration_seconds": 3600}).encode(), headers=headers)
        with urllib.request.urlopen(start, timeout=10) as result:
            assert json.load(result)["simulation"]["status"] == "running"
        paused = urllib.request.Request(origin + "/api/simulation/pause", data=b"{}", headers=headers)
        with urllib.request.urlopen(paused, timeout=10) as result:
            assert json.load(result)["simulation"]["status"] == "paused"
        accepted, reason = backend.request_shutdown()
        assert not accepted and "live simulation" in reason
        stopped = urllib.request.Request(origin + "/api/simulation/stop", data=b"{}", headers=headers)
        with urllib.request.urlopen(stopped, timeout=10) as result:
            assert json.load(result)["simulation"]["status"] == "stopped"
        assert backend.request_shutdown() == (True, None)
    finally:
        backend.stop()
    assert owned.poll() is not None
    assert backend.process is None
    try:
        assert backend.start().startswith("http://127.0.0.1:")
    finally:
        backend.stop()


def test_supervisor_reports_failed_start_without_a_setup(tmp_path):
    resources = tmp_path / "resources"
    frontend = resources / "dist"
    frontend.mkdir(parents=True)
    (frontend / "index.html").write_text("desktop test", encoding="utf-8")
    backend = DesktopBackend(DesktopPaths.discover(data_root=tmp_path / "data", resources=resources), frontend)
    with pytest.raises(RuntimeError, match="setup must complete"):
        backend.start(timeout=15)
    assert backend.process is None


def test_snapshot_failure_stops_startup_before_database_migration(tmp_path):
    resources = tmp_path / "resources"
    frontend = resources / "dist"
    frontend.mkdir(parents=True)
    (frontend / "index.html").write_text("desktop test", encoding="utf-8")
    root = tmp_path / "user data"
    (root / "config").mkdir(parents=True)
    (root / "config" / "installation-secret").write_text("s" * 48, encoding="ascii")
    data = root / "data"
    data.mkdir()
    (data / "pre-start-snapshots").write_text("not a directory", encoding="utf-8")
    database = data / "smartflow.db"
    with sqlite3.connect(database) as connection:
        connection.execute("CREATE TABLE original_evidence (value TEXT)")
        connection.execute("INSERT INTO original_evidence VALUES ('kept')")
    backend = DesktopBackend(DesktopPaths.discover(data_root=root, resources=resources), frontend)
    with pytest.raises(RuntimeError, match="Could not create the pre-start database snapshot.*not migrated"):
        backend.start(timeout=15)
    with sqlite3.connect(database) as connection:
        assert connection.execute("SELECT value FROM original_evidence").fetchone() == ("kept",)
        tables = connection.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
        assert tables == [("original_evidence",)]
    assert backend.process is None


def test_backend_refuses_newer_database_before_migration(tmp_path):
    from desktop.schema_guard import DESKTOP_SCHEMA_VERSION

    resources = tmp_path / "resources"
    frontend = resources / "dist"
    frontend.mkdir(parents=True)
    (frontend / "index.html").write_text("desktop test", encoding="utf-8")
    root = tmp_path / "user data"
    (root / "config").mkdir(parents=True)
    (root / "config" / "installation-secret").write_text("s" * 48, encoding="ascii")
    data = root / "data"
    data.mkdir()
    database = data / "smartflow.db"
    with sqlite3.connect(database) as connection:
        connection.execute(f"PRAGMA user_version = {DESKTOP_SCHEMA_VERSION + 1}")
        connection.execute("CREATE TABLE newer_evidence (value TEXT)")
        connection.execute("INSERT INTO newer_evidence VALUES ('kept')")
    backend = DesktopBackend(DesktopPaths.discover(data_root=root, resources=resources), frontend)
    with pytest.raises(RuntimeError, match="requires desktop schema version"):
        backend.start(timeout=15)
    with sqlite3.connect(database) as connection:
        assert connection.execute("PRAGMA user_version").fetchone() == (DESKTOP_SCHEMA_VERSION + 1,)
        assert connection.execute("SELECT value FROM newer_evidence").fetchone() == ("kept",)
        assert connection.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall() == [("newer_evidence",)]
