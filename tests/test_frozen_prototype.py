"""Opt-in test against an explicitly supplied disposable worker bundle."""
import json
import os
import queue
import shutil
import sqlite3
import subprocess
import sys
import threading
import time
import urllib.error
import urllib.request
from pathlib import Path

import pytest


@pytest.mark.skipif(not os.environ.get("SMARTFLOW_FROZEN_WORKER"), reason="Disposable frozen worker not supplied")
def test_frozen_recovery_follows_active_root_and_preserves_wal(tmp_path):
    from tests.test_desktop_recover import make_root, value
    from desktop.migration_snapshot import snapshot_before_start
    worker = str(Path(os.environ["SMARTFLOW_FROZEN_WORKER"]).resolve())
    control = tmp_path / "SmartFlow"
    active = control / "desktop-restored" / "restore-synthetic"
    active.mkdir(parents=True)
    control_data = make_root(control, "inactive")
    data = make_root(active, "snapshot")
    snapshot_before_start(data / "smartflow.db", data)
    (control / "config").mkdir()
    (control / "config" / "active-data-root.json").write_text(json.dumps({"version": 1, "root": str(active)}))
    code = "import sqlite3,sys,os; c=sqlite3.connect(sys.argv[1]); c.execute('PRAGMA journal_mode=WAL'); c.execute(\"UPDATE t SET v='committed'\"); c.commit(); os._exit(0)"
    subprocess.run([sys.executable, "-c", code, str(data / "smartflow.db")], check=True)
    env = {k: v for k, v in os.environ.items() if not k.startswith("SMARTFLOW_")}
    env["LOCALAPPDATA"] = str(tmp_path)
    result = subprocess.run([worker, "recover", "--yes"], env=env, text=True, capture_output=True, timeout=45)
    assert result.returncode == 0, result.stdout + result.stderr
    assert value(data / "smartflow.db") == "snapshot"
    kept = [p for p in data.glob("smartflow.db.replaced-*") if not p.name.endswith(("-wal", "-shm"))]
    assert len(kept) == 1 and value(kept[0]) == "committed"
    assert value(control_data / "smartflow.db") == "inactive"


@pytest.mark.skipif(not os.environ.get("SMARTFLOW_FROZEN_WORKER"), reason="Disposable frozen worker not supplied")
def test_frozen_bootstrap_and_backend_lifecycle(tmp_path):
    worker = Path(os.environ["SMARTFLOW_FROZEN_WORKER"]).resolve()
    resources = worker.parent / "_internal"
    frontend = resources / "dist" if (resources / "dist" / "index.html").is_file() else Path(__file__).resolve().parents[1] / "dist"
    assert (frontend / "index.html").is_file()
    root = tmp_path / "fresh desktop"
    env = {k: v for k, v in os.environ.items() if not k.startswith("SMARTFLOW_")}
    weak = subprocess.run([str(worker), "bootstrap"], input=json.dumps({"resources": str(resources), "data_root": str(root), "password": "weak"}),
                          text=True, capture_output=True, env=env, timeout=90)
    assert weak.returncode != 0 and json.loads(weak.stdout)["code"] == "weak_password"
    assert not (root / "data" / "smartflow.db").exists()
    secret = (root / "config" / "installation-secret").read_text(encoding="ascii")
    setup = subprocess.run([str(worker), "bootstrap"], input=json.dumps({"resources": str(resources), "data_root": str(root), "password": "StrongPass123"}),
                           text=True, capture_output=True, env=env, timeout=90)
    assert setup.returncode == 0, setup.stdout + setup.stderr
    assert json.loads(setup.stdout)["ok"]
    assert (root / "config" / "installation-secret").read_text(encoding="ascii") == secret
    edited_site = root / "data" / "networks" / "tagum_site_a.json"
    site_payload = json.loads(edited_site.read_text(encoding="utf-8"))
    site_payload["name"] = "Synthetic user-data site"
    edited_site.write_text(json.dumps(site_payload), encoding="utf-8")
    process = subprocess.Popen([str(worker), "serve"], stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, env=env)
    try:
        nonce = "frozen-synthetic-readiness-12345"
        process.stdin.write(json.dumps({"resources": str(resources), "data_root": str(root), "frontend": str(frontend), "nonce": nonce}) + "\n")
        process.stdin.flush()
        lines = queue.Queue()
        threading.Thread(target=lambda: lines.put(process.stdout.readline()), daemon=True).start()
        ready = json.loads(lines.get(timeout=60))
        assert ready.get("ready") and ready.get("nonce") == nonce, ready
        assert list((root / "data" / "pre-start-snapshots").glob("pre-start-*.db"))
        with sqlite3.connect(root / "data" / "smartflow.db") as connection:
            from desktop.schema_guard import DESKTOP_SCHEMA_VERSION
            assert connection.execute("PRAGMA user_version").fetchone() == (DESKTOP_SCHEMA_VERSION,)
        with urllib.request.urlopen(ready["origin"] + "/api/health", timeout=10) as response:
            assert json.load(response)["status"] == "healthy"
        login = urllib.request.Request(ready["origin"] + "/api/auth/login", data=json.dumps({"username": "admin", "password": "StrongPass123"}).encode(),
                                       headers={"Content-Type": "application/json", "Origin": ready["origin"]})
        with urllib.request.urlopen(login, timeout=20) as response:
            cookie = response.headers["Set-Cookie"].split(";", 1)[0]
        with urllib.request.urlopen(urllib.request.Request(ready["origin"] + "/api/networks", headers={"Cookie": cookie}), timeout=20) as response:
            assert next(site for site in json.load(response) if site["id"] == "tagum_site_a")["name"] == "Synthetic user-data site"
        for site, counted, assumed in (("tagum_site_a", 1052, 0), ("tagum_site_b", 650, 50)):
            counts = urllib.request.Request(
                ready["origin"] + "/api/scenarios/peak-counts",
                data=json.dumps({"network_id": site, "engine_config": {}}).encode(),
                headers={"Content-Type": "application/json", "Origin": ready["origin"], "Cookie": cookie},
            )
            try:
                with urllib.request.urlopen(counts, timeout=20) as response:
                    result = json.load(response)
            except urllib.error.HTTPError as exc:
                pytest.fail(f"Peak counts for {site} returned {exc.code}: {exc.read().decode()}")
            assert result["engine_config"]["demand_windows"]
            assert result["summary"]["counted_vehicles"] == counted
            assert result["summary"]["assumed_vehicles"] == assumed
        process.stdin.write('{"command":"shutdown_if_idle"}\n')
        process.stdin.flush()
        assert json.loads(process.stdout.readline())["accepted"] is True
        process.stdin.close()
        assert process.wait(timeout=30) == 0
    finally:
        if process.poll() is None:
            process.kill()
            process.wait(timeout=10)
        if not process.stdin.closed:
            process.stdin.close()
        process.stdout.close()
        process.stderr.close()


@pytest.mark.skipif(not os.environ.get("SMARTFLOW_FROZEN_WORKER"), reason="Disposable frozen worker not supplied")
def test_frozen_backend_refuses_newer_database(tmp_path):
    from desktop.schema_guard import DESKTOP_SCHEMA_VERSION

    worker = Path(os.environ["SMARTFLOW_FROZEN_WORKER"]).resolve()
    resources = worker.parent / "_internal"
    frontend = resources / "dist"
    root = tmp_path / "newer synthetic desktop"
    (root / "data").mkdir(parents=True)
    (root / "config").mkdir()
    (root / "config" / "installation-secret").write_text("s" * 48, encoding="ascii")
    database = root / "data" / "smartflow.db"
    with sqlite3.connect(database) as connection:
        connection.execute(f"PRAGMA user_version = {DESKTOP_SCHEMA_VERSION + 1}")
        connection.execute("CREATE TABLE evidence(value TEXT)")
        connection.execute("INSERT INTO evidence VALUES ('kept')")
    env = {k: v for k, v in os.environ.items() if not k.startswith("SMARTFLOW_")}
    request = {"resources": str(resources), "data_root": str(root), "frontend": str(frontend), "nonce": "frozen-synthetic-readiness-12345"}
    process = subprocess.run([str(worker), "serve"], input=json.dumps(request) + "\n", text=True, capture_output=True, env=env, timeout=90)
    assert process.returncode != 0
    response = json.loads(process.stdout)
    assert not response["ready"] and "requires desktop schema version" in response["error"]
    with sqlite3.connect(database) as connection:
        assert connection.execute("PRAGMA user_version").fetchone() == (DESKTOP_SCHEMA_VERSION + 1,)
        assert connection.execute("SELECT value FROM evidence").fetchone() == ("kept",)
        assert connection.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall() == [("evidence",)]


@pytest.mark.skipif(not os.environ.get("SMARTFLOW_FROZEN_WORKER"), reason="Disposable frozen worker not supplied")
def test_frozen_worker_rejects_tampered_engine_inventory(tmp_path):
    from services.reviewed_revision_store import _long_path

    source = Path(os.environ["SMARTFLOW_FROZEN_WORKER"]).resolve()
    clone = tmp_path / "worker copy"
    # Torch includes nested paths that can exceed Windows' traditional path limit.
    shutil.copytree(_long_path(source.parent), _long_path(clone.resolve()))
    worker = clone / source.name
    command = [str(worker), "train-ql", "--help"]
    healthy = subprocess.run(command, text=True, capture_output=True, timeout=45)
    assert healthy.returncode == 0, healthy.stdout + healthy.stderr
    (clone / "_internal" / "simulation" / "traffic_engine.py").unlink()
    tampered = subprocess.run(command, text=True, capture_output=True, timeout=45)
    assert tampered.returncode != 0
    assert "Packaged engine identity cannot be verified" in tampered.stderr


@pytest.mark.skipif(not os.environ.get("SMARTFLOW_FROZEN_ML") or not os.environ.get("SMARTFLOW_FROZEN_WORKER"), reason="CPU ML prototype not supplied")
def test_frozen_dql_ppo_train_load_and_evaluate_synthetic(tmp_path):
    worker = str(Path(os.environ["SMARTFLOW_FROZEN_WORKER"]).resolve())
    env = {k: v for k, v in os.environ.items() if not k.startswith("SMARTFLOW_")}
    env.update({"SMARTFLOW_SECRET_KEY": "synthetic-ml-test", "SMARTFLOW_DB_PATH": str(tmp_path / "evaluation.db"),
                "SMARTFLOW_DATA_DIR": str(tmp_path / "data"), "OMP_NUM_THREADS": "1", "MKL_NUM_THREADS": "1"})
    models = {}
    for algorithm in ("dql", "ppo"):
        model = tmp_path / f"{algorithm}.zip"
        command = [worker, f"train-{algorithm}", "--episodes", "1", "--seeds", "11", "--warmup-seconds", "0",
                   "--evaluation-seconds", "10", "--max-steps-per-episode", "2", "--skip-db", "--output", str(model)]
        if algorithm == "dql":
            command += ["--learning-starts", "2", "--buffer-size", "100", "--batch-size", "4"]
        else:
            command += ["--n-steps", "8", "--batch-size", "4", "--n-epochs", "1"]
        result = subprocess.run(command, cwd=tmp_path, env=env, capture_output=True, text=True, timeout=180)
        assert result.returncode == 0, result.stdout + result.stderr
        assert model.is_file() and model.with_suffix(".metadata.json").is_file()
        models[algorithm] = model
    result = subprocess.run([worker, "evaluate", "--controllers", "fixed-time,dql,ppo", "--seeds", "101",
                             "--duration-seconds", "10", "--warmup-seconds", "0", "--record-timeline-seed", "-1",
                             "--dql-model", str(models["dql"]), "--ppo-model", str(models["ppo"]),
                             "--output", str(tmp_path / "evaluation.json")], cwd=tmp_path, env=env,
                            capture_output=True, text=True, timeout=180)
    assert result.returncode == 0, result.stdout + result.stderr
    assert (tmp_path / "evaluation.json").is_file()


@pytest.mark.skipif(not os.environ.get("SMARTFLOW_FROZEN_WORKER"), reason="Disposable frozen worker not supplied")
def test_frozen_ql_train_resume_evaluate_and_study_site(tmp_path):
    worker = str(Path(os.environ["SMARTFLOW_FROZEN_WORKER"]).resolve())
    env = {k: v for k, v in os.environ.items() if not k.startswith("SMARTFLOW_")}
    env.update({"SMARTFLOW_SECRET_KEY": "synthetic-ql-test", "SMARTFLOW_DB_PATH": str(tmp_path / "evaluation.db"),
                "SMARTFLOW_DATA_DIR": str(tmp_path / "data"), "SMARTFLOW_STUDY_ROOT": str(tmp_path / "empty-study")})
    first, resumed = tmp_path / "first.json", tmp_path / "resumed.json"
    common = ["--episodes", "1", "--seeds", "11", "--warmup-seconds", "0", "--evaluation-seconds", "10",
              "--max-steps-per-episode", "2", "--skip-db"]
    trained = subprocess.run([worker, "train-ql", *common, "--output", str(first)], cwd=tmp_path, env=env, capture_output=True, text=True, timeout=180)
    assert trained.returncode == 0, trained.stdout + trained.stderr
    assert first.is_file()
    continued = subprocess.run([worker, "train-ql", *common, "--resume-model", str(first), "--output", str(resumed)],
                               cwd=tmp_path, env=env, capture_output=True, text=True, timeout=180)
    assert continued.returncode == 0, continued.stdout + continued.stderr
    assert resumed.is_file()
    evaluated = subprocess.run([worker, "evaluate", "--controllers", "fixed-time,ql", "--seeds", "101", "--duration-seconds", "10",
                                "--warmup-seconds", "0", "--record-timeline-seed", "-1", "--ql-model", str(resumed),
                                "--output", str(tmp_path / "evaluation.json")], cwd=tmp_path, env=env, capture_output=True, text=True, timeout=180)
    assert evaluated.returncode == 0, evaluated.stdout + evaluated.stderr
    assert (tmp_path / "evaluation.json").is_file()
    study = tmp_path / "study.json"
    study.write_text(json.dumps({"network_id": "tagum_site_a", "name": "Synthetic fixture", "engine_config": {}}), encoding="utf-8")
    result = subprocess.run([worker, "train-ql", "--scenario-file", str(study), *common, "--output", str(tmp_path / "site-a.json")],
                            cwd=tmp_path, env=env, capture_output=True, text=True, timeout=90)
    assert result.returncode == 0, result.stdout + result.stderr
    assert (tmp_path / "site-a.json").is_file()
