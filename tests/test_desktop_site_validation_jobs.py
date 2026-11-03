import hashlib
import json
import os
import subprocess
import sys
import threading
import time
from types import SimpleNamespace

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

os.environ.setdefault("SMARTFLOW_SECRET_KEY", "desktop-validation-test-secret")
os.environ.setdefault("SMARTFLOW_BOOTSTRAP_ADMIN_PASSWORD", "DesktopValidation123!")

from backend.security import require_current_user
from desktop.server import desktop_app
from desktop.site_validation_jobs import DesktopValidationJobs
from services.site_validation import criteria_sha256
from services.workload_admission import WorkloadConflict, workload_admission
from tests.test_study_gate import CRITERIA, LEDGER, MAPPING, SITE


@pytest.fixture
def files(tmp_path, monkeypatch):
    sites = tmp_path / "data" / "sites"
    sites.mkdir(parents=True)
    (sites / f"{SITE}_mapping.json").write_text(json.dumps(MAPPING), encoding="utf-8")
    (sites / "validation_criteria.json").write_text(json.dumps({"sites": {SITE: CRITERIA}}), encoding="utf-8")
    revision = tmp_path / "fixture-revision"
    revision.mkdir()
    (revision / "manifest.json").write_text('{"synthetic":true}', encoding="utf-8")
    manifest = hashlib.sha256((revision / "manifest.json").read_bytes()).hexdigest()
    ledger = {**LEDGER, "criteria_sha256": criteria_sha256(CRITERIA), "held_out": {**LEDGER["held_out"], "manifest_sha256": manifest}}
    (sites / f"{SITE}_ledger.json").write_text(json.dumps(ledger), encoding="utf-8")
    monkeypatch.setattr("desktop.site_validation_jobs.revision_path", lambda root, revision_id: revision)
    monkeypatch.setattr("desktop.site_validation_jobs.load_registered_network", lambda site: None)
    monkeypatch.setattr("desktop.site_validation_jobs.convert_revision", lambda *args, **kwargs: {"trips_csv": "time_s,source,destination,vehicle_type\n", "pedestrian_counts_csv": None})
    mapping_hash = hashlib.sha256(json.dumps(MAPPING, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
    provenance = {"manifest_sha256": manifest, "mapping_sha256": mapping_hash, "window": [0, 900], "origin_s": 0}
    scenario = {"network_id": SITE, "engine_config": json.dumps({"traffic_density": "none", "pedestrian_density": "none",
                "demand_source": {"kind": "observed", "datasets": [{"kind": "observed", "provenance": provenance}]}})}
    monkeypatch.setattr("desktop.site_validation_jobs.database.get_scenario_by_id", lambda _id: scenario)
    return tmp_path, scenario


def test_validation_refuses_synthetic_or_wrong_held_out_inputs(files):
    root, scenario = files
    jobs = DesktopValidationJobs(root)
    settings = json.loads(scenario["engine_config"])
    settings["demand_source"]["kind"] = "synthetic"
    scenario["engine_config"] = json.dumps(settings)
    with pytest.raises(ValueError, match="synthetic"):
        jobs.start(scenario_id=1, revision_id="a" * 32, purpose="validation", origin_s=0, start_s=0, end_s=900)
    settings["demand_source"]["kind"] = "observed"
    settings["demand_source"]["datasets"][0]["provenance"]["window"] = [0, 800]
    scenario["engine_config"] = json.dumps(settings)
    with pytest.raises(ValueError, match="video window"):
        jobs.start(scenario_id=1, revision_id="a" * 32, purpose="validation", origin_s=0, start_s=0, end_s=900)
    settings["demand_source"]["datasets"][0]["provenance"]["window"] = [0, 900]
    settings["trips"] = [{"time": 3, "source": "w", "destination": "e", "vehicle_type": "car"}]
    scenario["engine_config"] = json.dumps(settings)
    with pytest.raises(ValueError, match="differs"):
        jobs.start(scenario_id=1, revision_id="a" * 32, purpose="validation", origin_s=0, start_s=0, end_s=900)


def test_job_holds_workload_until_real_validator_returns(files, monkeypatch):
    root, _ = files
    started, release = threading.Event(), threading.Event()
    def fake_validator(**kwargs):
        started.set()
        assert release.wait(5)
        return {"report_id": "test", "status": "INCONCLUSIVE", "gate": {"open": False, "reasons": ["synthetic fixture"]},
                "decision": {"reasons": ["insufficient"]}}, root / "report.json"
    monkeypatch.setattr("desktop.site_validation_jobs.run_validation", fake_validator)
    jobs = DesktopValidationJobs(root)
    job = jobs.start(scenario_id=1, revision_id="a" * 32, purpose="validation", origin_s=0, start_s=0, end_s=900)
    try:
        assert started.wait(2)
        with pytest.raises(WorkloadConflict):
            workload_admission.acquire("recording")
    finally:
        release.set()
    for _ in range(100):
        result = jobs.get(job["id"])
        if result["status"] != "running":
            break
        time.sleep(.02)
    assert result["status"] == "completed" and not result["result"]["gate"]["open"]
    restored = DesktopValidationJobs(root).get(job["id"])
    assert restored["status"] == "completed" and restored["result"]["status"] == "INCONCLUSIVE"
    lease = workload_admission.acquire("recording")
    workload_admission.release(lease)


def test_abrupt_backend_exit_marks_job_interrupted_and_preserves_reports(tmp_path):
    report_dir = tmp_path / "docs" / "reports"
    report_dir.mkdir(parents=True)
    report = report_dir / "site-validation-synthetic.json"
    report.write_text('{"synthetic":true}', encoding="utf-8")
    script = "\n".join([
        "import os, sys",
        "from desktop.site_validation_jobs import DesktopValidationJobs",
        "jobs = DesktopValidationJobs(sys.argv[1])",
        "jobs._save({'id':'a'*32,'status':'running','site':'tagum_site_a','purpose':'validation','result':None,'error':None})",
        "os._exit(91)",
    ])
    process = subprocess.run([sys.executable, "-c", script, str(tmp_path)], capture_output=True, text=True, timeout=30)
    assert process.returncode == 91, process.stdout + process.stderr
    jobs = DesktopValidationJobs(tmp_path)
    restored = jobs.get("a" * 32)
    assert restored["status"] == "interrupted" and restored["result"] is None
    assert "Check saved reports" in restored["error"]
    assert json.loads((tmp_path / "data" / "validation-jobs" / ("a" * 32 + ".json")).read_text(encoding="utf-8"))["status"] == "interrupted"
    assert report.read_text(encoding="utf-8") == '{"synthetic":true}'


def test_validation_endpoints_require_admin(tmp_path, monkeypatch):
    frontend = tmp_path / "frontend"
    frontend.mkdir()
    (frontend / "index.html").write_text("test", encoding="utf-8")
    app = FastAPI()
    origin = "http://127.0.0.1:8123"
    wrapped = desktop_app(app, frontend, origin, restore_requests=SimpleNamespace(paths=SimpleNamespace(root=tmp_path)))
    client = TestClient(wrapped, base_url=origin, headers={"Origin": origin})
    payload = {"scenario_id": 1, "revision_id": "a" * 32, "purpose": "validation", "origin_s": 0, "start_s": 0, "end_s": 900}
    assert client.post("/api/desktop/site-validation-jobs", json=payload).status_code == 401
    app.dependency_overrides[require_current_user] = lambda: {"id": 2, "role_name": "viewer"}
    assert client.post("/api/desktop/site-validation-jobs", json=payload).status_code == 403
    app.dependency_overrides[require_current_user] = lambda: {"id": 1, "role_name": "admin"}
    monkeypatch.setattr(DesktopValidationJobs, "start", lambda self, **kwargs: {"id": "test", "status": "running"})
    assert client.post("/api/desktop/site-validation-jobs", json=payload).json()["id"] == "test"
    assert client.get("/api/desktop/site-validation-jobs/missing").status_code == 404
