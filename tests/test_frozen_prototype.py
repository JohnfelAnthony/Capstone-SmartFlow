"""Opt-in test against an explicitly supplied disposable worker bundle."""
import json
import os
import queue
import shutil
import sqlite3
import subprocess
import threading
import time
import urllib.request
from datetime import date
from pathlib import Path

import pytest


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
def test_frozen_reviewed_conversion_and_synthetic_calibration(tmp_path):
    from tests.test_field_observer_import import build, mapping, vehicle
    from tests.test_reviewed_revision_store import archive
    from tests.test_study_gate import CRITERIA
    from services.field_observer_import import site_mapping_template
    from simulation.network_registry import load_registered_network

    worker = Path(os.environ["SMARTFLOW_FROZEN_WORKER"]).resolve()
    resources, root = worker.parent / "_internal", tmp_path / "synthetic-desktop"
    frontend = resources / "dist"
    env = {k: v for k, v in os.environ.items() if not k.startswith("SMARTFLOW_")}
    setup = subprocess.run([str(worker), "bootstrap"], input=json.dumps({"resources": str(resources), "data_root": str(root), "password": "StrongPass123"}),
                           text=True, capture_output=True, env=env, timeout=90)
    assert setup.returncode == 0, setup.stdout + setup.stderr
    source = build(tmp_path, vehicle("e1", 12.4, 20.0) + vehicle("e2", 30.0, 60.0, cls="bus"))
    process = subprocess.Popen([str(worker), "serve"], stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, env=env)
    try:
        process.stdin.write(json.dumps({"resources": str(resources), "data_root": str(root), "frontend": str(frontend), "nonce": "frozen-synthetic-readiness-12345"}) + "\n")
        process.stdin.flush()
        lines = queue.Queue()
        threading.Thread(target=lambda: lines.put(process.stdout.readline()), daemon=True).start()
        ready = json.loads(lines.get(timeout=90))
        assert ready.get("ready"), ready
        origin = ready["origin"]
        login = urllib.request.Request(origin + "/api/auth/login", data=json.dumps({"username": "admin", "password": "StrongPass123"}).encode(),
                                       headers={"Content-Type": "application/json", "Origin": origin})
        with urllib.request.urlopen(login, timeout=20) as response:
            cookie = response.headers["Set-Cookie"].split(";", 1)[0]
        headers = {"Origin": origin, "Cookie": cookie, "Content-Type": "application/json"}
        def call(path, payload=None, *, body=None, content_type="application/json"):
            request = urllib.request.Request(origin + path, data=(json.dumps(payload).encode() if payload is not None else body),
                                             headers={**headers, "Content-Type": content_type})
            with urllib.request.urlopen(request, timeout=45) as response:
                return json.load(response)
        revision = call("/api/desktop/reviewed-revisions", body=archive(source), content_type="application/zip")["id"]
        template = site_mapping_template(load_registered_network("tagum_site_a"))
        west, east = [item for item in template["boundaries"] if item["road_name"] == "Capitol Circumferential Road"][:2]
        site_mapping = {**template, "lead_out_s": 120, "initialization": mapping()["initialization"],
                        "locations": {"arrival_west": {"role": "arrival", "boundary": west["boundary"], "approach_id": "west", "distance_from_junction_m": west["length_m"]},
                                      "exit_east": {"role": "exit", "boundary": east["boundary"], "approach_id": "east", "distance_from_junction_m": east["length_m"]}}}
        input_url = "/api/desktop/study-inputs/tagum_site_a"
        current = call(input_url)["inputs"]
        criteria = {**CRITERIA, "approaches": [west["boundary"]]}
        for kind, document in (("mapping", site_mapping), ("criteria", {"sites": {"tagum_site_a": criteria}})):
            assert call(input_url + "/" + kind, {"document": document, "expected_sha256": current[kind]["sha256"]})["changed"]
        conversion = {"mapping": site_mapping, "origin_s": 0, "start_s": 0, "end_s": 900}
        prefix = f"/api/desktop/reviewed-revisions/{revision}"
        preview = call(prefix + "/conversion-preview", conversion)
        created = call(prefix + "/create-scenario", {**conversion, "name": "Frozen synthetic calibration", "collected_on": date.today().isoformat(),
                       "source_kind": "synthetic", "expected_network_sha256": preview["network_sha256"],
                       "expected_mapping_sha256": preview["provenance"]["mapping_sha256"], "expected_manifest_sha256": preview["provenance"]["manifest_sha256"]})
        job = call("/api/desktop/site-validation-jobs", {"scenario_id": created["scenario_id"], "revision_id": revision,
                   "purpose": "calibration", "origin_s": 0, "start_s": 0, "end_s": 15})
        deadline = time.monotonic() + 120
        while time.monotonic() < deadline:
            result = call("/api/desktop/site-validation-jobs/" + job["id"])
            if result["status"] != "running":
                break
            time.sleep(.2)
        assert result["status"] == "completed", result
        assert result["result"]["gate"]["open"] is False
        assert (root / "docs" / "reports" / result["result"]["report_file"]).is_file()
        process.stdin.write('{"command":"shutdown_if_idle"}\n')
        process.stdin.flush()
        assert json.loads(process.stdout.readline())["accepted"]
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
def test_frozen_study_gate_rejects_tampered_engine_inventory(tmp_path):
    from services.reviewed_revision_store import _long_path

    source = Path(os.environ["SMARTFLOW_FROZEN_WORKER"]).resolve()
    clone = tmp_path / "worker copy"
    # Torch includes nested paths that can exceed Windows' traditional path limit.
    shutil.copytree(_long_path(source.parent), _long_path(clone.resolve()))
    worker = clone / source.name
    root = tmp_path / "synthetic study"
    sites = root / "data" / "sites"
    reports = root / "docs" / "reports"
    sites.mkdir(parents=True)
    reports.mkdir(parents=True)
    criteria = {"development_seeds": [101, 102, 103, 104, 105],
                "tolerances": {"queue": {"abs": 2.0}, "discharge": {"rel": .2}, "travel_time": {"rel": .25}, "arrival_order_share": {"abs": .15}},
                "arrival_order_share_min": .8, "pair_window_s": 10, "tie_tolerance_s": .5, "min_order_pairs": 3,
                "min_samples": {"queue": 4, "discharge": 1, "travel_time": 5}, "queue_sample_interval_s": 30,
                "stopped_speed_mps": .5, "discharge_bin_s": 900, "max_unfinished_share": .2, "approaches": ["boundary_0"]}
    (sites / "tagum_site_a_mapping.json").write_text(json.dumps({"network_id": "tagum_site_a", "lead_out_s": 120, "initialization": {}}), encoding="utf-8")
    (sites / "validation_criteria.json").write_text(json.dumps({"sites": {"tagum_site_a": criteria}}), encoding="utf-8")
    (sites / "tagum_site_a_ledger.json").write_text("{}", encoding="utf-8")
    (reports / "site-validation-tagum_site_a-validation-fixture.json").write_text("{}", encoding="utf-8")
    scenario = tmp_path / "scenario.json"
    scenario.write_text(json.dumps({"network_id": "tagum_site_a", "name": "Synthetic fixture", "engine_config": {}}), encoding="utf-8")
    env = {k: v for k, v in os.environ.items() if not k.startswith("SMARTFLOW_")}
    env.update({"SMARTFLOW_SECRET_KEY": "synthetic-test-only", "SMARTFLOW_STUDY_ROOT": str(root)})
    command = [str(worker), "train-ql", "--scenario-file", str(scenario), "--episodes", "1", "--skip-db", "--output", str(tmp_path / "blocked.json")]
    healthy = subprocess.run(command, env=env, text=True, capture_output=True, timeout=45)
    assert healthy.returncode != 0
    assert "requires an open independent validation gate" in healthy.stderr
    assert "Packaged engine identity cannot be verified" not in healthy.stderr
    (clone / "_internal" / "simulation" / "traffic_engine.py").unlink()
    tampered = subprocess.run(command, env=env, text=True, capture_output=True, timeout=45)
    assert tampered.returncode != 0
    assert "Packaged engine identity cannot be verified" in tampered.stderr
    assert not (tmp_path / "blocked.json").exists()


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
    scenario = tmp_path / "study-fixture.json"
    scenario.write_text(json.dumps({"network_id": "tagum_site_a", "name": "Unvalidated synthetic fixture", "engine_config": {}}), encoding="utf-8")
    env["SMARTFLOW_STUDY_ROOT"] = str(tmp_path / "empty-study")
    for algorithm in ("dql", "ppo"):
        blocked = subprocess.run([worker, f"train-{algorithm}", "--scenario-file", str(scenario), "--episodes", "1",
                                  "--skip-db", "--output", str(tmp_path / f"blocked-{algorithm}.zip")],
                                 cwd=tmp_path, env=env, capture_output=True, text=True, timeout=90)
        assert blocked.returncode != 0
        assert "requires an open independent validation gate" in blocked.stderr
        assert not (tmp_path / f"blocked-{algorithm}.zip").exists()


@pytest.mark.skipif(not os.environ.get("SMARTFLOW_FROZEN_WORKER"), reason="Disposable frozen worker not supplied")
def test_frozen_ql_train_resume_evaluate_and_study_gate(tmp_path):
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
    study.write_text(json.dumps({"network_id": "tagum_site_a", "name": "Unvalidated synthetic fixture", "engine_config": {}}), encoding="utf-8")
    blocked = subprocess.run([worker, "train-ql", "--scenario-file", str(study), *common, "--output", str(tmp_path / "blocked.json")],
                             cwd=tmp_path, env=env, capture_output=True, text=True, timeout=90)
    assert blocked.returncode != 0 and "requires an open independent validation gate" in blocked.stderr
    assert not (tmp_path / "blocked.json").exists()
