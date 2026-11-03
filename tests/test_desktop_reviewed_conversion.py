import json
import os
import time
from datetime import date
from types import SimpleNamespace

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

os.environ.setdefault("SMARTFLOW_SECRET_KEY", "desktop-conversion-tests-only")
os.environ.setdefault("SMARTFLOW_BOOTSTRAP_ADMIN_PASSWORD", "DesktopConversion123!")

from backend.security import require_current_user
from desktop.reviewed_conversion import create_scenario_from_review, preview_conversion
from desktop.server import desktop_app
from services.field_observer_import import site_mapping_template
from services.reviewed_revision_store import import_reviewed_zip
from simulation.network_registry import load_registered_network
from tests.test_field_observer_import import build, event, mapping, vehicle
from tests.test_reviewed_revision_store import archive


@pytest.fixture
def reviewed(tmp_path):
    revision = build(tmp_path, vehicle("e1", 12.4, 20.0) + vehicle("e2", 30.0, 60.0, cls="bus"))
    retained = import_reviewed_zip(archive(revision), tmp_path)
    site = load_registered_network("tagum_site_a")
    template = site_mapping_template(site)
    west, east = [item for item in template["boundaries"] if item["road_name"] == "Capitol Circumferential Road"][:2]
    site_mapping = {**template, "lead_out_s": 120, "initialization": mapping()["initialization"],
                    "locations": {"arrival_west": {"role": "arrival", "boundary": west["boundary"], "approach_id": "west", "distance_from_junction_m": west["length_m"]},
                                  "exit_east": {"role": "exit", "boundary": east["boundary"], "approach_id": "east", "distance_from_junction_m": east["length_m"]}}}
    return retained["id"], site_mapping


def test_preview_converts_without_writing_scenario_or_evidence(tmp_path, reviewed):
    revision_id, site_mapping = reviewed
    before = sorted(str(path.relative_to(tmp_path)) for path in tmp_path.rglob("*") if path.is_file())
    result = preview_conversion(study_root=tmp_path, revision_id=revision_id, mapping=site_mapping, origin_s=0, start_s=0, end_s=900)
    assert result["summary"]["by_class"] == {"car": 1, "bus": 1}
    assert result["provenance"]["mapping_sha256"] and "No scenario was created" in result["message"]
    assert before == sorted(str(path.relative_to(tmp_path)) for path in tmp_path.rglob("*") if path.is_file())
    site_mapping["network_sha256"] = "0" * 64
    with pytest.raises(ValueError, match="another network"):
        preview_conversion(study_root=tmp_path, revision_id=revision_id, mapping=site_mapping, origin_s=0, start_s=0, end_s=900)


def test_desktop_conversion_api_checks_permission_and_mapping(tmp_path, reviewed, monkeypatch):
    import config
    import database
    from services import observed_data_import
    monkeypatch.setattr(config, "DB_PATH", str(tmp_path / "isolated.sqlite"))
    monkeypatch.setattr(observed_data_import, "IMPORT_DIRECTORY", tmp_path / "data" / "imports")
    database.init_db()
    database.seed_data()
    revision_id, site_mapping = reviewed
    frontend = tmp_path / "frontend"
    frontend.mkdir()
    (frontend / "index.html").write_text("test", encoding="utf-8")
    app = FastAPI()
    origin = "http://127.0.0.1:8123"
    wrapped = desktop_app(app, frontend, origin, restore_requests=SimpleNamespace(paths=SimpleNamespace(root=tmp_path)))
    client = TestClient(wrapped, base_url=origin, headers={"Origin": origin})
    url = f"/api/desktop/reviewed-revisions/{revision_id}/conversion-preview"
    payload = {"mapping": site_mapping, "origin_s": 0, "start_s": 0, "end_s": 900}
    assert client.post(url, json=payload).status_code == 401
    app.dependency_overrides[require_current_user] = lambda: {"id": 2, "role_name": "viewer"}
    assert client.post(url, json=payload).status_code == 403
    app.dependency_overrides[require_current_user] = lambda: {"id": 1, "role_name": "admin"}
    result = client.post(url, json=payload)
    assert result.status_code == 200, result.text
    assert result.json()["summary"]["trips"] == 2
    review = result.json()
    create = {**payload, "name": "Synthetic API scenario", "collected_on": date.today().isoformat(), "source_kind": "synthetic",
              "expected_network_sha256": review["network_sha256"], "expected_mapping_sha256": review["provenance"]["mapping_sha256"],
              "expected_manifest_sha256": review["provenance"]["manifest_sha256"]}
    create_url = f"/api/desktop/reviewed-revisions/{revision_id}/create-scenario"
    app.dependency_overrides[require_current_user] = lambda: {"id": 2, "role_name": "viewer"}
    assert client.post(create_url, json=create).status_code == 403
    app.dependency_overrides[require_current_user] = lambda: {"id": 1, "role_name": "admin"}
    assert client.post(create_url, json={**create, "expected_mapping_sha256": "0" * 64}).status_code == 422
    created = client.post(create_url, json=create)
    assert created.status_code == 200, created.text
    assert database.get_scenario_by_id(created.json()["scenario_id"])["name"] == "Synthetic API scenario"
    invalid = client.post(url, json={**payload, "end_s": -1})
    assert invalid.status_code == 422
    assert client.post("/api/desktop/reviewed-revisions/not-a-revision/conversion-preview", json=payload).status_code == 422


def test_reviewed_conversion_creates_provisional_scenario_and_retains_mapping(tmp_path, reviewed, monkeypatch):
    import config
    import database
    from services import observed_data_import
    monkeypatch.setattr(config, "DB_PATH", str(tmp_path / "isolated.sqlite"))
    monkeypatch.setattr(observed_data_import, "IMPORT_DIRECTORY", tmp_path / "data" / "imports")
    database.init_db()
    database.seed_data()
    revision_id, site_mapping = reviewed
    preview = preview_conversion(study_root=tmp_path, revision_id=revision_id, mapping=site_mapping, origin_s=0, start_s=0, end_s=900)
    params = {"study_root": tmp_path, "revision_id": revision_id, "mapping": site_mapping, "origin_s": 0, "start_s": 0, "end_s": 900,
              "expected_network_sha256": preview["network_sha256"], "expected_mapping_sha256": preview["provenance"]["mapping_sha256"],
              "expected_manifest_sha256": preview["provenance"]["manifest_sha256"], "name": "Synthetic reviewed demand",
              "collected_on": date.today().isoformat(), "source_kind": "synthetic", "user_id": 1}
    with pytest.raises(ValueError, match="preview"):
        create_scenario_from_review(**{**params, "expected_mapping_sha256": "0" * 64})
    assert not list((tmp_path / "data" / "imports").glob("*"))
    result = create_scenario_from_review(**params)
    scenario = database.get_scenario_by_id(result["scenario_id"])
    settings = json.loads(scenario["engine_config"])
    assert scenario["network_sha256"] == preview["network_sha256"]
    assert sorted(trip["vehicle_type"] for trip in settings["trips"]) == ["bus", "car"]
    assert settings["demand_source"]["kind"] == "synthetic"
    assert settings["demand_source"]["datasets"][0]["provenance"]["manifest_sha256"] == preview["provenance"]["manifest_sha256"]
    mapping_file = tmp_path / "data" / "sites" / f"mapping-{preview['provenance']['mapping_sha256']}.json"
    assert json.loads(mapping_file.read_text(encoding="utf-8")) == site_mapping
    assert "Independent site validation" in result["message"]


def test_vehicle_and_pedestrian_conversion_keeps_both_inputs(tmp_path, reviewed, monkeypatch):
    import config
    import database
    from services import observed_data_import
    monkeypatch.setattr(config, "DB_PATH", str(tmp_path / "pedestrian.sqlite"))
    monkeypatch.setattr(observed_data_import, "IMPORT_DIRECTORY", tmp_path / "data" / "imports")
    database.init_db()
    database.seed_data()
    _, site_mapping = reviewed
    source_dir = tmp_path / "pedestrian-source"
    source_dir.mkdir()
    revision = build(source_dir, vehicle("v1", 200, 230) + [event("p1", "pedestrian_start", "crossing_main", 100, cls="person")])
    revision_id = import_reviewed_zip(archive(revision), tmp_path)["id"]
    site_mapping["locations"]["crossing_main"] = {"role": "crossing", "junction": load_registered_network("tagum_site_a").intersections[0]}
    preview = preview_conversion(study_root=tmp_path, revision_id=revision_id, mapping=site_mapping, origin_s=0, start_s=0, end_s=900)
    result = create_scenario_from_review(study_root=tmp_path, revision_id=revision_id, mapping=site_mapping, origin_s=0, start_s=0, end_s=900,
        expected_network_sha256=preview["network_sha256"], expected_mapping_sha256=preview["provenance"]["mapping_sha256"],
        expected_manifest_sha256=preview["provenance"]["manifest_sha256"], name="Synthetic mixed demand", collected_on=date.today().isoformat(), source_kind="synthetic", user_id=1)
    settings = json.loads(database.get_scenario_by_id(result["scenario_id"])["engine_config"])
    assert len(settings["trips"]) == 1 and len(settings["pedestrian_trips"]) == 1
    assert settings["pedestrian_trips"][0]["time"] == 90
    assert {entry["schema"] for entry in settings["demand_source"]["datasets"]} == {"trips", "pedestrian_counts"}


def test_synthetic_desktop_calibration_runs_real_validator(tmp_path, reviewed, monkeypatch):
    """Exercise the real engine and report writer without claiming field validation."""
    import config
    import database
    from desktop.site_validation_jobs import DesktopValidationJobs
    from services import observed_data_import
    from tests.test_study_gate import CRITERIA

    monkeypatch.setattr(config, "DB_PATH", str(tmp_path / "calibration.sqlite"))
    monkeypatch.setattr(observed_data_import, "IMPORT_DIRECTORY", tmp_path / "data" / "imports")
    database.init_db()
    database.seed_data()
    revision_id, site_mapping = reviewed
    preview = preview_conversion(study_root=tmp_path, revision_id=revision_id, mapping=site_mapping, origin_s=0, start_s=0, end_s=900)
    created = create_scenario_from_review(
        study_root=tmp_path, revision_id=revision_id, mapping=site_mapping, origin_s=0, start_s=0, end_s=900,
        expected_network_sha256=preview["network_sha256"], expected_mapping_sha256=preview["provenance"]["mapping_sha256"],
        expected_manifest_sha256=preview["provenance"]["manifest_sha256"], name="Synthetic calibration",
        collected_on=date.today().isoformat(), source_kind="synthetic", user_id=1,
    )
    sites = tmp_path / "data" / "sites"
    (sites / "tagum_site_a_mapping.json").write_text(json.dumps(site_mapping), encoding="utf-8")
    criteria = {**CRITERIA, "approaches": [site_mapping["locations"]["arrival_west"]["boundary"]]}
    (sites / "validation_criteria.json").write_text(json.dumps({"sites": {"tagum_site_a": criteria}}), encoding="utf-8")
    jobs = DesktopValidationJobs(tmp_path)
    job = jobs.start(scenario_id=created["scenario_id"], revision_id=revision_id, purpose="calibration", origin_s=0, start_s=0, end_s=15)
    deadline = time.monotonic() + 120
    while time.monotonic() < deadline:
        result = jobs.get(job["id"])
        if result["status"] != "running":
            break
        time.sleep(.1)
    assert result["status"] == "completed", result
    assert result["result"]["status"] in {"FAIL", "INCONCLUSIVE"}
    assert result["result"]["gate"]["open"] is False
    report_path = tmp_path / "docs" / "reports" / result["result"]["report_file"]
    report = json.loads(report_path.read_text(encoding="utf-8"))
    assert report["purpose"] == "calibration" and report["gate"]["open"] is False
    assert DesktopValidationJobs(tmp_path).get(job["id"])["status"] == "completed"
