"""Research records use saved native baselines and permission-scoped search."""
import copy
import csv
import io
import json
import os
import sqlite3
import tempfile
import unittest
from contextlib import closing
from pathlib import Path
from unittest.mock import patch

os.environ.setdefault("SMARTFLOW_SECRET_KEY", "research-workspace-test-only")
from fastapi.testclient import TestClient
import auth
import config
import database
from backend.main import app
from backend.research_routes import METRICS
from backend.simulation_runtime import simulation_runtime
from tools.evaluate_controllers import _run_controller_once


class ResearchWorkspaceTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory(prefix="research-", dir=Path(__file__).resolve().parent)
        self.root = Path(self.directory.name)
        self.patches = [patch.object(config, "DB_PATH", str(self.root / "research.db")),
                        patch.object(config, "BOOTSTRAP_ADMIN_PASSWORD", "ResearchAdmin42!")]
        for item in self.patches:
            item.start()
        self.client = TestClient(app)
        self.client.__enter__()
        simulation_runtime.reset(force=True)
        self.assertEqual(self.client.post("/api/auth/login", json={"username": "admin", "password": "ResearchAdmin42!"}).status_code, 200)
        self.scenario_id = database.create_scenario("Research baseline 100%_fixture", description="Literal search fixture",
            engine_config=json.dumps({"traffic_density": "none", "pedestrian_density": "none"}))
        scenario = database.get_scenario_by_id(self.scenario_id)
        result = _run_controller_once(controller="fixed-time", seed=0, scenario=scenario, scenario_id=self.scenario_id,
            duration_seconds=2, warmup_seconds=1, decision_interval_seconds=1, minimum_green_hold_seconds=5,
            policies={}, model_ids={}, record_timeline=False)
        self.run_id = result["run_id"]
        self.draft = {"name": "Synthetic baseline comparison", "site_id": "fixture-site", "purpose": "calibration",
            "source_kind": "synthetic", "source_reference": "Synthetic sheet A", "source_sha256": "",
            "collection_start": "2026-10-01T07:00:00+08:00", "collection_end": "2026-10-01T07:01:00+08:00",
            "run_id": self.run_id, "calibration_id": None, "measurement_start": 1, "measurement_seconds": 2,
            "definitions_confirmed": True, "parameter_changes": "Fixture baseline; no field claim.", "notes": "Test only.",
            "measurements": [{"metric": "throughput", "location": "Whole network", "definition": METRICS[0]["definition"],
                "unit": "vehicles", "observed": 0, "tolerance": 0, "tolerance_mode": "absolute", "simulated": None,
                "simulation_method": ""}, {"metric": "local_reference", "location": "Synthetic stop line", "definition": "Discharge in two seconds",
                "unit": "vehicles", "observed": 8, "simulated": 10, "simulation_method": "Synthetic manually supplied extraction",
                "tolerance": 25, "tolerance_mode": "percent"}]}

    def tearDown(self):
        simulation_runtime.reset(force=True)
        self.client.__exit__(None, None, None)
        for item in reversed(self.patches):
            item.stop()
        self.assertTrue(self.root.resolve().is_relative_to(Path(__file__).resolve().parent))
        self.directory.cleanup()

    def save(self, draft=None):
        response = self.client.post("/api/calibration", json=draft or self.draft)
        self.assertEqual(response.status_code, 201, response.text)
        return response.json()

    def validation(self, parent):
        draft = copy.deepcopy(self.draft)
        draft.update(purpose="validation", calibration_id=parent["id"], source_reference="Synthetic sheet B",
            collection_start="2026-10-02T07:00:00+08:00", collection_end="2026-10-02T07:01:00+08:00")
        return draft

    def test_arithmetic_zero_reference_and_frozen_snapshot_survive_run_deletion(self):
        record = self.save()
        self.assertEqual(record["snapshot"]["seed"], 0)
        self.assertEqual(record["reviewer"], "admin")
        self.assertTrue(record["within_tolerance"])
        self.assertIsNone(record["comparisons"][0]["percent_error"])
        local = record["comparisons"][1]
        self.assertEqual((local["difference"], local["absolute_error"], local["percent_error"]), (2, 2, 25))
        second = copy.deepcopy(self.draft)
        second["measurements"][1]["tolerance"] = 24
        self.assertFalse(self.save(second)["within_tolerance"])
        database.update_scenario(self.scenario_id, engine_config='{"green_seconds":55}')
        database.delete_run(self.run_id)
        self.assertEqual(self.client.get(f"/api/calibration/{record['id']}").json(), record)
        self.assertEqual(len(self.client.get("/api/calibration").json()["records"]), 2)

    def test_validation_uses_independent_period_and_frozen_plan(self):
        parent = self.save()
        draft = self.validation(parent)
        self.assertEqual(self.save(draft)["calibration_id"], parent["id"])
        for patch_values, fragment in [
            ({"collection_start": self.draft["collection_start"], "collection_end": self.draft["collection_end"]}, "independent"),
            ({"source_reference": self.draft["source_reference"]}, "independent"),
            ({"calibration_id": 99999}, "Choose a saved"),
            ({"site_id": "another-site"}, "same site"),
        ]:
            with self.subTest(patch_values=patch_values):
                response = self.client.post("/api/calibration", json={**draft, **patch_values})
                self.assertEqual(response.status_code, 422, response.text)
                self.assertIn(fragment, response.text)
        draft["measurements"][0]["tolerance"] = 100
        self.assertIn("tolerances unchanged", self.client.post("/api/calibration", json=draft).text)
        draft = self.validation(parent)
        with database.get_db() as conn:
            raw = json.loads(database.get_run_metrics(self.run_id)["raw_metrics_json"])
            raw["experiment"]["config"]["green_seconds"] = 60
            conn.execute("UPDATE run_metrics SET raw_metrics_json=? WHERE run_id=?", (json.dumps(raw), self.run_id))
        self.assertIn("frozen calibrated", self.client.post("/api/calibration", json=draft).text)

    def test_validation_checks_all_calibration_sources_and_hashes(self):
        parent_draft = copy.deepcopy(self.draft)
        parent_draft["source_sha256"] = "a" * 64
        parent = self.save(parent_draft)
        validation = self.validation(parent)
        validation["source_sha256"] = "A" * 64
        self.assertEqual(self.client.post("/api/calibration", json=validation).status_code, 422)
        another = self.validation(parent)
        another.update(purpose="calibration", calibration_id=None)
        self.save(another)
        validation["source_sha256"] = "b" * 64
        self.assertEqual(self.client.post("/api/calibration", json=validation).status_code, 422)

    def test_invalid_windows_units_and_manual_metric_overrides_are_rejected(self):
        cases = [{"measurement_seconds": 3}, {"definitions_confirmed": False}, {"name": " "}, {"calibration_id": 123},
                 {"collection_start": "2026-10-01T07:00:00"}, {"collection_end": "2026-10-01T07:00:02+08:00"}]
        for changes in cases:
            with self.subTest(changes=changes):
                self.assertEqual(self.client.post("/api/calibration", json={**self.draft, **changes}).status_code, 422)
        for change in [{"unit": "vph"}, {"metric": "unknown"}, {"simulated": 100}, {"observed": -1}, {"observed": "NaN"}]:
            draft = copy.deepcopy(self.draft)
            draft["measurements"][0].update(change)
            self.assertEqual(self.client.post("/api/calibration", json=draft).status_code, 422)
        draft = copy.deepcopy(self.draft)
        draft["measurements"][1]["simulation_method"] = ""
        self.assertEqual(self.client.post("/api/calibration", json=draft).status_code, 422)
        self.assertEqual(self.client.get("/api/calibration").json()["records"], [])

    def test_independent_demand_changes_are_allowed_but_measurement_protocol_is_frozen(self):
        parent = self.save()
        scenario = database.get_scenario_by_id(self.scenario_id)
        scenario["engine_config"] = json.dumps({"traffic_density": "none", "pedestrian_density": "none",
            "vehicle_mix": {"car": .5, "bus": .5}, "trips": [{"time": 0, "source": "west", "destination": "east", "vehicle_type": "car"}]})
        # Derive actual boundary IDs instead of relying on the default network labels.
        from simulation.road_network import load_network
        network = load_network()
        boundaries = list(network.boundaries)
        route = next((source, destination) for source in boundaries for destination in boundaries
                     if source != destination and network.route(source, destination))
        settings = json.loads(scenario["engine_config"])
        settings["trips"][0].update(source=route[0], destination=route[1])
        scenario["engine_config"] = json.dumps(settings)
        for duration in (2, 3):
            result = _run_controller_once(controller="fixed-time", seed=5, scenario=scenario, scenario_id=self.scenario_id,
                duration_seconds=duration, warmup_seconds=1, decision_interval_seconds=1, minimum_green_hold_seconds=5,
                policies={}, model_ids={}, record_timeline=False)
            draft = self.validation(parent)
            draft.update(run_id=result["run_id"], measurement_seconds=duration)
            response = self.client.post("/api/calibration", json=draft)
            if duration == 2:
                self.assertEqual(response.status_code, 201, response.text)
            else:
                self.assertEqual(response.status_code, 422, response.text)
                self.assertIn("measurement duration unchanged", response.text)

    def test_only_completed_fixed_time_native_baselines_with_population_are_accepted(self):
        for changes in [{"control_mode": "ql"}, {"status": "running"}]:
            database.update_run(self.run_id, **changes)
            self.assertEqual(self.client.post("/api/calibration", json=self.draft).status_code, 422)
            database.update_run(self.run_id, control_mode="fixed-time", status="completed")
        draft = copy.deepcopy(self.draft)
        draft["measurements"][0].update(metric="avg_travel_time", unit="seconds")
        self.assertIn("no measured population", self.client.post("/api/calibration", json=draft).text)
        with database.get_db() as conn:
            raw = json.loads(database.get_run_metrics(self.run_id)["raw_metrics_json"])
            raw["experiment"]["engine_version"] = "legacy"
            conn.execute("UPDATE run_metrics SET raw_metrics_json=? WHERE run_id=?", (json.dumps(raw), self.run_id))
        self.assertEqual(self.client.post("/api/calibration", json=self.draft).status_code, 422)

    def test_exports_and_backup_restore_keep_frozen_record(self):
        draft = {**self.draft, "name": "=Untrusted spreadsheet name"}
        record = self.save(draft)
        self.assertEqual(self.client.get(f"/api/calibration/{record['id']}/export").json(), record)
        exported = self.client.get(f"/api/calibration/{record['id']}/export", params={"format": "csv"})
        rows = list(csv.DictReader(io.StringIO(exported.text)))
        self.assertEqual(rows[0]["Name"], "'=Untrusted spreadsheet name")
        self.assertEqual(rows[0]["Seed"], "0")
        self.assertEqual(json.loads(rows[1]["Frozen Record JSON"]), record)
        backup = self.client.post("/api/admin/backups")
        self.assertEqual(backup.status_code, 200, backup.text)
        restored = self.client.post(f"/api/admin/backups/{backup.json()['backup']['id']}/restore")
        self.assertEqual(restored.status_code, 200, restored.text)
        with closing(sqlite3.connect(Path(restored.json()["restore_path"]) / "smartflow.db")) as conn:
            saved = conn.execute("SELECT payload_json FROM calibration_records WHERE id=?", (record["id"],)).fetchone()
        self.assertEqual(json.loads(saved[0])["snapshot"], record["snapshot"])

    def test_search_literal_substrings_deep_links_and_permissions(self):
        fit = self.save()
        model = database.create_rl_model(name="Research model fixture")
        results = self.client.get("/api/search", params={"q": "research"}).json()["results"]
        self.assertTrue(any(row["kind"] == "Scenario" and row["id"] == self.scenario_id for row in results))
        self.assertTrue(any(row["kind"] == "Model" and row["id"] == model for row in results))
        self.assertTrue(any(row["page"] == "Settings" for row in self.client.get("/api/search", params={"q": "settings"}).json()["results"]))
        self.assertTrue(any(row["id"] == fit["id"] for row in self.client.get("/api/search", params={"q": "fixture-site"}).json()["results"]))
        literal = self.client.get("/api/search", params={"q": "100%_fixture"}).json()["results"]
        self.assertEqual(len(literal), 1)
        self.assertEqual(self.client.get("/api/search", params={"q": "' OR 1=1 --"}).json()["results"], [])
        database.create_user("Research viewer", "research_viewer", None, auth.hash_password("ViewerOnly42!"), role_id=2)
        for page, action in [("scenarios", "edit"), ("runs-reports", "export"), ("rl-training", "view")]:
            database.update_role_permission(2, page, action, False)
        viewer = TestClient(app)  # use the already initialized database; no second startup/permission seeding
        self.assertEqual(viewer.post("/api/auth/login", json={"username": "research_viewer", "password": "ViewerOnly42!"}).status_code, 200)
        self.assertEqual(viewer.get("/api/calibration").status_code, 200)
        self.assertEqual(viewer.post("/api/calibration", json=self.draft).status_code, 403)
        self.assertEqual(viewer.get(f"/api/calibration/{fit['id']}/export").status_code, 403)
        self.assertFalse(any(row["kind"] == "Model" for row in viewer.get("/api/search", params={"q": "research"}).json()["results"]))
        database.update_role_permission(2, "scenarios", "view", False)
        self.assertEqual(viewer.get("/api/calibration").status_code, 403)
        self.assertEqual(viewer.get("/api/search", params={"q": "fixture-site"}).json()["results"], [])
        self.assertEqual(TestClient(app).get("/api/search", params={"q": "research"}).status_code, 401)


if __name__ == "__main__":
    unittest.main()
