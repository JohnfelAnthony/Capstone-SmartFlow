"""Exercise desktop backups through a real isolated backend and data root."""
import json
import os
import shutil
import sqlite3
import subprocess
import sys
import urllib.error
import urllib.request
from contextlib import closing
from datetime import date
from pathlib import Path

import pytest
from werkzeug.security import generate_password_hash

from desktop.lifecycle import DesktopBackend
from desktop.paths import DesktopPaths
from desktop.restore_switch import RestoreSwitch, RestoreSwitchError
from services.reviewed_revision_store import revision_path
from tests.test_reviewed_revision_store import archive
from tests.test_field_observer_import import build, vehicle
from tests.test_field_observer_import import mapping as synthetic_mapping
from tests.test_study_gate import CRITERIA, LEDGER
from services.field_observer_import import site_mapping_template
from simulation.road_network import RoadNetwork


ROOT = Path(__file__).resolve().parents[1]


def test_desktop_api_backup_and_staging_keep_networks_and_evidence(tmp_path, monkeypatch):
    frozen_worker = os.environ.get("SMARTFLOW_FROZEN_WORKER")
    if frozen_worker:
        worker = Path(frozen_worker).resolve()
        resources = worker.parent / "_internal"
        frontend = resources / "dist"
        assert worker.is_file() and (frontend / "index.html").is_file()
        monkeypatch.setattr("desktop.lifecycle.service_prefix", lambda mode: [str(worker), mode])
        bootstrap_command = [str(worker), "bootstrap"]
    else:
        resources = tmp_path / "resources"
        networks = resources / "data" / "networks"
        networks.mkdir(parents=True)
        for name in ("registry.json", "tagum_network.json", "tagum_site_a.json", "tagum_site_b.json"):
            shutil.copyfile(ROOT / "data" / "networks" / name, networks / name)
        frontend = resources / "dist"
        frontend.mkdir()
        (frontend / "index.html").write_text("test", encoding="utf-8")
        bootstrap_command = [sys.executable, "-m", "desktop.bootstrap"]
    root = tmp_path / "user data"
    env = {k: v for k, v in os.environ.items() if not k.startswith("SMARTFLOW_")}
    setup = subprocess.run(bootstrap_command, cwd=ROOT, env=env,
                           input=json.dumps({"data_root": str(root), "resources": str(resources), "password": "StrongPass123"}),
                           text=True, capture_output=True, timeout=45)
    assert setup.returncode == 0, setup.stdout + setup.stderr
    edited_site = root / "data" / "networks" / "tagum_site_a.json"
    edited_payload = json.loads(edited_site.read_text(encoding="utf-8"))
    edited_payload["name"] = "Synthetic user-edited site"
    edited_site.write_text(json.dumps(edited_payload), encoding="utf-8")
    # Two trusted synthetic revisions exercise both original and hashed history files.
    from services.network_revision_storage import store_revision
    registry_path = edited_site.parent / "registry.json"
    for _ in range(2):
        previous = RoadNetwork(edited_payload)
        edited_payload = json.loads(json.dumps(edited_payload))
        edited_payload["roads"][0]["width"] = float(edited_payload["roads"][0].get("width", 7)) + 0.1
        store_revision(registry_path, "tagum_site_a", previous.fingerprint, edited_payload)
    evidence = root / "data" / "sites" / "tagum_site_a_mapping.json"
    evidence.parent.mkdir(parents=True)
    evidence.write_text('{"note":"synthetic evidence"}', encoding="utf-8")
    source_revision = build(tmp_path, vehicle("e1", 12.4, 20.0))
    recording = root / "data" / "recordings" / "synthetic.jsonl"
    recording.parent.mkdir()
    recording.write_text('{"fixture":true}\n', encoding="utf-8")
    model = root / "data" / "models" / "synthetic.zip"
    model.parent.mkdir()
    model.write_bytes(b"synthetic model bytes")
    with closing(sqlite3.connect(root / "data" / "smartflow.db")) as connection, connection:
        connection.execute("INSERT INTO simulation_runs (timeline_path) VALUES (?)", (str(recording),))
        connection.execute("INSERT INTO rl_models (name, checkpoint_path) VALUES (?, ?)", ("synthetic", str(model)))
        connection.execute("INSERT INTO users (full_name, username, password_hash, role_id) VALUES (?, ?, ?, 2)",
                           ("Viewer", "viewer", generate_password_hash("ViewerPass123")))
    backend = DesktopBackend(DesktopPaths.discover(data_root=root, resources=resources), frontend)
    try:
        origin = backend.start()
        login = urllib.request.Request(origin + "/api/auth/login", data=json.dumps({"username": "admin", "password": "StrongPass123"}).encode(),
                                       headers={"Content-Type": "application/json", "Origin": origin})
        with urllib.request.urlopen(login, timeout=10) as response:
            cookie = response.headers["Set-Cookie"].split(";", 1)[0]
        headers = {"Content-Type": "application/json", "Origin": origin, "Cookie": cookie}
        upload_url = origin + "/api/desktop/reviewed-revisions"
        unauth_upload = urllib.request.Request(upload_url, data=archive(source_revision), headers={"Origin": origin, "Content-Type": "application/zip"})
        with pytest.raises(urllib.error.HTTPError) as error:
            urllib.request.urlopen(unauth_upload, timeout=10)
        assert error.value.code == 401
        upload = urllib.request.Request(upload_url, data=archive(source_revision), headers={"Origin": origin, "Cookie": cookie, "Content-Type": "application/zip"})
        with urllib.request.urlopen(upload, timeout=10) as response:
            reviewed_id = json.load(response)["id"]
        list_request = urllib.request.Request(upload_url, headers={"Cookie": cookie})
        with urllib.request.urlopen(list_request, timeout=10) as response:
            assert json.load(response)["revisions"][0]["id"] == reviewed_id
        template = site_mapping_template(RoadNetwork(edited_payload))
        west, east = [item for item in template["boundaries"] if item["road_name"] == "Capitol Circumferential Road"][:2]
        site_mapping = {**template, "lead_out_s": 120, "initialization": synthetic_mapping()["initialization"],
                        "locations": {"arrival_west": {"role": "arrival", "boundary": west["boundary"], "approach_id": "west", "distance_from_junction_m": west["length_m"]},
                                      "exit_east": {"role": "exit", "boundary": east["boundary"], "approach_id": "east", "distance_from_junction_m": east["length_m"]}}}
        inputs_url = origin + "/api/desktop/study-inputs/tagum_site_a"
        with urllib.request.urlopen(urllib.request.Request(inputs_url, headers={"Cookie": cookie}), timeout=10) as response:
            current_inputs = json.load(response)["inputs"]
        for kind, document in (("mapping", site_mapping), ("criteria", {"sites": {"tagum_site_a": CRITERIA}}), ("ledger", LEDGER)):
            data = json.dumps({"document": document, "expected_sha256": current_inputs[kind]["sha256"]}).encode()
            request = urllib.request.Request(inputs_url + "/" + kind, data=data, headers=headers)
            with urllib.request.urlopen(request, timeout=30) as response:
                assert json.load(response)["changed"]
        convert_payload = {"mapping": site_mapping, "origin_s": 0, "start_s": 0, "end_s": 900}
        preview_request = urllib.request.Request(upload_url + f"/{reviewed_id}/conversion-preview", data=json.dumps(convert_payload).encode(), headers=headers)
        with urllib.request.urlopen(preview_request, timeout=30) as response:
            preview = json.load(response)
        create_payload = {**convert_payload, "name": "Synthetic reviewed backup", "collected_on": date.today().isoformat(), "source_kind": "synthetic",
                          "expected_network_sha256": preview["network_sha256"], "expected_mapping_sha256": preview["provenance"]["mapping_sha256"],
                          "expected_manifest_sha256": preview["provenance"]["manifest_sha256"]}
        create_request = urllib.request.Request(upload_url + f"/{reviewed_id}/create-scenario", data=json.dumps(create_payload).encode(), headers=headers)
        with urllib.request.urlopen(create_request, timeout=30) as response:
            scenario_id = json.load(response)["scenario_id"]
        job_id = "a" * 32
        job_file = root / "data" / "validation-jobs" / (job_id + ".json")
        job_file.write_text(json.dumps({"id": job_id, "status": "running", "site": "tagum_site_a", "purpose": "calibration", "result": None, "error": None}), encoding="utf-8")
        request = urllib.request.Request(origin + "/api/admin/backups", data=b"{}", headers=headers)
        try:
            with urllib.request.urlopen(request, timeout=30) as response:
                backup_id = json.load(response)["backup"]["id"]
        except urllib.error.HTTPError as exc:
            pytest.fail(f"Backup returned {exc.code}: {exc.read().decode()}")
        request = urllib.request.Request(origin + f"/api/admin/backups/{backup_id}/restore", data=b"{}", headers=headers)
        with urllib.request.urlopen(request, timeout=30) as response:
            stage = Path(json.load(response)["restore_path"])
        restored = json.loads((stage / "restore_environment.json").read_text(encoding="utf-8"))
        registry = Path(restored["SMARTFLOW_NETWORK_REGISTRY_PATH"])
        assert Path(restored["SMARTFLOW_DB_PATH"]).is_file()
        assert Path(restored["SMARTFLOW_NETWORK_PATH"]).is_file()
        for entry in json.loads(registry.read_text(encoding="utf-8"))["networks"]:
            assert (registry.parent / entry["file"]).is_file()
        assert (Path(restored["SMARTFLOW_STUDY_ROOT"]) / "data/sites/tagum_site_a_mapping.json").read_text(encoding="utf-8") == evidence.read_text(encoding="utf-8")
        assert (revision_path(Path(restored["SMARTFLOW_STUDY_ROOT"]), reviewed_id) / "events.csv").read_bytes() == (source_revision / "events.csv").read_bytes()
        assert backend.request_shutdown() == (True, None)
    finally:
        backend.stop()
    from services.backup_bundle import _windows_long_path, _write_restore_seal, prepare_desktop_restore
    staged_db = Path(restored["SMARTFLOW_DB_PATH"])
    with closing(sqlite3.connect(staged_db)) as connection, connection:
        original_path = connection.execute("SELECT timeline_path FROM simulation_runs WHERE timeline_path IS NOT NULL").fetchone()[0]
        connection.execute("UPDATE simulation_runs SET timeline_path = ? WHERE timeline_path = ?", (str(tmp_path / "outside.jsonl"), original_path))
    rejected = tmp_path / "rejected candidate"
    with pytest.raises(ValueError, match="stage changed"):
        prepare_desktop_restore(stage, rejected, root / "config" / "installation-secret")
    assert not rejected.exists()
    # Exercise reference containment independently of the stage checksum.
    _write_restore_seal(stage)
    with pytest.raises(ValueError, match="not contained"):
        prepare_desktop_restore(stage, rejected, root / "config" / "installation-secret")
    assert not rejected.exists()
    with closing(sqlite3.connect(staged_db)) as connection, connection:
        connection.execute("UPDATE simulation_runs SET timeline_path = ? WHERE timeline_path = ?", (original_path, str(tmp_path / "outside.jsonl")))
    _write_restore_seal(stage)
    switch = RestoreSwitch(root, resources, frontend)
    candidate = switch.candidate_path()
    prepare_desktop_restore(stage, candidate, root / "config" / "installation-secret")
    restored_registry = candidate / "data" / "networks" / "registry.json"
    for entry in json.loads(restored_registry.read_text())["networks"]:
        for revision in entry.get("revision_history", []):
            historical_path = Path(_windows_long_path(restored_registry.parent / revision["file"]))
            historical = RoadNetwork(json.loads(historical_path.read_text(encoding="utf-8")))
            assert historical.fingerprint == revision["sha256"]
    shutil.rmtree(stage)
    with closing(sqlite3.connect(candidate / "data" / "smartflow.db")) as connection:
        restored_recording = Path(connection.execute("SELECT timeline_path FROM simulation_runs WHERE timeline_path IS NOT NULL").fetchone()[0])
        restored_model = Path(connection.execute("SELECT checkpoint_path FROM rl_models WHERE name = 'synthetic'").fetchone()[0])
    assert Path(_windows_long_path(restored_recording)).is_relative_to(Path(_windows_long_path(candidate))) and restored_recording.read_bytes() == recording.read_bytes()
    assert Path(_windows_long_path(restored_model)).is_relative_to(Path(_windows_long_path(candidate))) and restored_model.read_bytes() == model.read_bytes()
    current = DesktopBackend(DesktopPaths.discover(data_root=root, resources=resources), frontend)
    current_origin = current.start()
    restored_backend = None
    try:
        activation_url = current_origin + f"/api/desktop/backups/{backup_id}/activate"
        unauthorized = urllib.request.Request(activation_url, data=b"{}", headers={"Content-Type": "application/json", "Origin": current_origin})
        with pytest.raises(urllib.error.HTTPError) as error:
            urllib.request.urlopen(unauthorized, timeout=10)
        assert error.value.code == 401
        viewer_login = urllib.request.Request(current_origin + "/api/auth/login", data=json.dumps({"username": "viewer", "password": "ViewerPass123"}).encode(),
                                              headers={"Content-Type": "application/json", "Origin": current_origin})
        with urllib.request.urlopen(viewer_login, timeout=10) as response:
            viewer_cookie = response.headers["Set-Cookie"].split(";", 1)[0]
        viewer_request = urllib.request.Request(activation_url, data=b"{}", headers={"Content-Type": "application/json", "Origin": current_origin, "Cookie": viewer_cookie})
        with pytest.raises(urllib.error.HTTPError) as error:
            urllib.request.urlopen(viewer_request, timeout=10)
        assert error.value.code == 403 and current.poll_restore() is None
        login = urllib.request.Request(current_origin + "/api/auth/login", data=json.dumps({"username": "admin", "password": "StrongPass123"}).encode(),
                                       headers={"Content-Type": "application/json", "Origin": current_origin})
        with urllib.request.urlopen(login, timeout=10) as response:
            cookie = response.headers["Set-Cookie"].split(";", 1)[0]
        request = urllib.request.Request(activation_url, data=b"{}", headers={"Content-Type": "application/json", "Origin": current_origin, "Cookie": cookie})
        start = urllib.request.Request(current_origin + "/api/simulation/start", data=json.dumps({"scenario_id": 1, "duration_seconds": 3600}).encode(),
                                       headers={"Content-Type": "application/json", "Origin": current_origin, "Cookie": cookie})
        with urllib.request.urlopen(start, timeout=10):
            pass
        with urllib.request.urlopen(request, timeout=30):
            pass
        blocked_candidate = Path(current.poll_restore())
        with pytest.raises(RestoreSwitchError, match="active|simulation"):
            switch.activate(current, blocked_candidate)
        current.release_restore()
        stop = urllib.request.Request(current_origin + "/api/simulation/stop", data=b"{}", headers={"Content-Type": "application/json", "Origin": current_origin, "Cookie": cookie})
        with urllib.request.urlopen(stop, timeout=10):
            pass
        with urllib.request.urlopen(request, timeout=30) as response:
            assert "verified" in json.load(response)["message"]
        requested_candidate = Path(current.poll_restore())
        assert current.poll_restore() is None
        restored_backend, restored_origin = switch.activate(current, requested_candidate)
        assert switch.active_root() == requested_candidate.resolve()
        restored_site = requested_candidate / "data" / "networks" / "tagum_site_a.json"
        assert json.loads(restored_site.read_text(encoding="utf-8"))["name"] == "Synthetic user-edited site"
        login = urllib.request.Request(restored_origin + "/api/auth/login", data=json.dumps({"username": "admin", "password": "StrongPass123"}).encode(),
                                       headers={"Content-Type": "application/json", "Origin": restored_origin})
        with urllib.request.urlopen(login, timeout=10) as response:
            assert response.status == 200
            restored_cookie = response.headers["Set-Cookie"].split(";", 1)[0]
        with urllib.request.urlopen(urllib.request.Request(restored_origin + "/api/networks", headers={"Cookie": restored_cookie}), timeout=20) as response:
            assert next(site for site in json.load(response) if site["id"] == "tagum_site_a")["name"] == "Synthetic user-edited site"
        with closing(sqlite3.connect(requested_candidate / "data" / "smartflow.db")) as connection:
            model_path = Path(connection.execute("SELECT checkpoint_path FROM rl_models WHERE name = 'synthetic'").fetchone()[0])
            assert Path(_windows_long_path(model_path)).is_relative_to(Path(_windows_long_path(requested_candidate))) and model_path.read_bytes() == model.read_bytes()
            saved = json.loads(connection.execute("SELECT engine_config FROM scenarios WHERE id = ?", (scenario_id,)).fetchone()[0])
            assert saved["trips"][0]["vehicle_type"] == "car"
            dataset = saved["demand_source"]["datasets"][0]
            restored_csv = Path(dataset["source_path"])
            extended_candidate = Path(_windows_long_path(requested_candidate))
            assert Path(_windows_long_path(restored_csv)).is_relative_to(extended_candidate) and restored_csv.is_file()
            assert dataset["provenance"]["manifest_sha256"] == preview["provenance"]["manifest_sha256"]
        mapping_path = requested_candidate / "data/sites" / f"mapping-{preview['provenance']['mapping_sha256']}.json"
        assert json.loads(Path(_windows_long_path(mapping_path)).read_text(encoding="utf-8")) == site_mapping
        assert (requested_candidate / "data/sites/tagum_site_a_mapping.json").read_text(encoding="utf-8") == evidence.read_text(encoding="utf-8")
        history = list((requested_candidate / "data" / "sites").glob("history-mapping-a-*.json"))
        assert len(history) == 1 and Path(_windows_long_path(history[0])).read_text(encoding="utf-8") == '{"note":"synthetic evidence"}'
        assert json.loads((requested_candidate / "data/sites/validation_criteria.json").read_text(encoding="utf-8"))["sites"]["tagum_site_a"] == CRITERIA
        assert json.loads((requested_candidate / "data/sites/tagum_site_a_ledger.json").read_text(encoding="utf-8")) == LEDGER
        assert (revision_path(requested_candidate, reviewed_id) / "events.csv").read_bytes() == (source_revision / "events.csv").read_bytes()
        restored_job = requested_candidate / "data" / "validation-jobs" / (job_id + ".json")
        assert json.loads(Path(_windows_long_path(restored_job)).read_text(encoding="utf-8"))["status"] == "interrupted"
        new_backup = urllib.request.Request(restored_origin + "/api/admin/backups", data=b"{}", headers={"Content-Type": "application/json", "Origin": restored_origin, "Cookie": restored_cookie})
        try:
            with urllib.request.urlopen(new_backup, timeout=30) as response:
                second_backup = json.load(response)["backup"]
                assert second_backup["filename"].endswith(".zip")
        except urllib.error.HTTPError as exc:
            pytest.fail(f"Restored backup returned {exc.code}: {exc.read().decode()}")
        verify_again = urllib.request.Request(restored_origin + f"/api/admin/backups/{second_backup['id']}/restore", data=b"{}", headers={"Content-Type": "application/json", "Origin": restored_origin, "Cookie": restored_cookie})
        try:
            with urllib.request.urlopen(verify_again, timeout=30) as response:
                assert json.load(response)["restore_path"]
        except urllib.error.HTTPError as exc:
            pytest.fail(f"Second verification returned {exc.code}: {exc.read().decode()}")
        assert restored_backend.request_shutdown() == (True, None)
    finally:
        if restored_backend is not None:
            restored_backend.stop()
        current.stop()
