"""Downloadable templates and exported experiment provenance."""
import copy
import csv
import io
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

os.environ.setdefault("SMARTFLOW_SECRET_KEY", "delivery-workflows-test-only")
from fastapi.testclient import TestClient
import auth
import config
import database
from backend.main import app
from backend.simulation_runtime import simulation_runtime
from services import observed_data_import as importer
from services.observation_templates import observation_template
from simulation.ql_agent import TabularQLearningAgent
from simulation.road_network import RoadNetwork, load_network
from simulation.rl_policy_runtime import load_runtime_policy
from tools.evaluate_controllers import _run_controller_once


class DeliveryWorkflowTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory(prefix="delivery-test-", dir=Path(__file__).resolve().parent)
        self.root = Path(self.directory.name)
        self.patches = [patch.object(config, "DB_PATH", str(self.root / "delivery.db")),
                        patch.object(config, "BOOTSTRAP_ADMIN_PASSWORD", "DeliveryAdmin42!"),
                        patch.object(importer, "IMPORT_DIRECTORY", self.root / "imports")]
        for item in self.patches:
            item.start()
        self.client = TestClient(app)
        self.client.__enter__()
        simulation_runtime.reset(force=True)
        response = self.client.post("/api/auth/login", json={"username":"admin", "password":"DeliveryAdmin42!"})
        self.assertEqual(response.status_code, 200, response.text)

    def tearDown(self):
        simulation_runtime.reset(force=True)
        self.client.__exit__(None, None, None)
        for item in reversed(self.patches):
            item.stop()
        self.directory.cleanup()

    def test_all_downloaded_examples_import_and_blank_templates_need_rows(self):
        for kind, columns in importer.SCHEMAS.items():
            with self.subTest(kind=kind):
                result = self.client.get("/api/scenarios/observations/template", params={"kind":kind,"example":True})
                self.assertEqual(result.status_code, 200, result.text)
                template = result.json()
                self.assertIn("synthetic_example", template["filename"])
                for example in (False, True):
                    attachment = self.client.get("/api/scenarios/observations/template",
                        params={"kind":kind,"example":example,"format":"csv"})
                    metadata = self.client.get("/api/scenarios/observations/template", params={"kind":kind,"example":example}).json()
                    self.assertEqual(attachment.status_code, 200, attachment.text)
                    self.assertEqual(attachment.text, metadata["csv_text"])
                    self.assertTrue(attachment.headers["content-type"].startswith("text/csv"))
                    self.assertEqual(attachment.headers["content-disposition"], f'attachment; filename="{metadata["filename"]}"')
                imported = self.client.post("/api/scenarios/observations/import", json={
                    "kind":kind, "csv_text":template["csv_text"], "source_description":"Synthetic downloaded example",
                    "source_kind":"synthetic", "collected_on":"2026-01-01"})
                self.assertEqual(imported.status_code, 200, imported.text)
                self.assertEqual(imported.json()["summary"]["row_count"], 1)
                blank = self.client.get("/api/scenarios/observations/template", params={"kind":kind}).json()
                self.assertEqual(next(csv.reader(io.StringIO(blank["csv_text"]))), list(columns))
                with self.assertRaisesRegex(ValueError, "data rows"):
                    importer.import_observations(kind=kind, csv_text=blank["csv_text"], source_description="Blank",
                                                source_kind="synthetic", collected_on="2026-01-01")
        self.assertEqual(database.get_runs(), [])

    def test_template_endpoint_requires_scenario_authority_and_valid_schema(self):
        anonymous = TestClient(app)
        self.assertEqual(anonymous.get("/api/scenarios/observations/template", params={"kind":"trips"}).status_code, 401)
        database.create_user("Viewer", "template_viewer", None, auth.hash_password("ViewerOnly42!"), role_id=2)
        for action in ("create", "edit"):
            database.update_role_permission(2, "scenarios", action, False)
        with TestClient(app) as viewer:
            login = viewer.post("/api/auth/login", json={"username":"template_viewer", "password":"ViewerOnly42!"})
            self.assertEqual(login.status_code, 200, login.text)
            self.assertEqual(viewer.get("/api/scenarios/observations/template", params={"kind":"trips"}).status_code, 403)
        response = self.client.get("/api/scenarios/observations/template", params={"kind":"unexpected"})
        self.assertEqual(response.status_code, 422)
        self.assertEqual(self.client.get("/api/scenarios/observations/template", params={"kind":"trips","format":"bad"}).status_code, 422)
        self.assertFalse((self.root / "imports").exists())

    def test_examples_follow_replacement_network_ids(self):
        payload = copy.deepcopy(load_network().payload)
        payload["id"] = "replacement-template-network"
        for node in payload["nodes"]:
            old_id = node["id"]
            node["id"] = f"fixture-{old_id}"
            for road in payload["roads"]:
                for end in ("source", "target"):
                    if road[end] == old_id:
                        road[end] = node["id"]
        network = RoadNetwork(payload)
        with patch.object(importer, "load_network", return_value=network):
            for kind in importer.SCHEMAS:
                template = observation_template(kind, example=True, network=network)
                self.assertEqual(template["network_sha256"], network.fingerprint)
                self.assertIn("fixture-", template["csv_text"])
                importer.import_observations(kind=kind, csv_text=template["csv_text"], source_description="Replacement fixture",
                    source_kind="synthetic", collected_on="2026-01-01")

    def test_csv_and_json_retain_observation_period_model_and_measurement_window(self):
        template = observation_template("trips", example=True)
        imported = importer.import_observations(kind="trips", csv_text=template["csv_text"], source_description="Artificial observed-format export fixture",
            source_kind="observed", collected_on="2026-01-01", collection_start="2026-01-01T07:00:00+08:00",
            collection_end="2026-01-01T08:00:00+08:00", engine_config={"traffic_density":"none","pedestrian_density":"none"})
        scenario_id = database.create_scenario("Export traceability", engine_config=json.dumps(imported["engine_config"]))
        scenario = database.get_scenario_by_id(scenario_id)
        path = TabularQLearningAgent(action_count=5).save(self.root / "ql.json", metadata={"scenario":scenario})
        model_id = database.create_rl_model(name="Export fixture", checkpoint_path=str(path))
        policy = load_runtime_policy("ql", path)
        result = _run_controller_once(controller="ql", seed=0, scenario=scenario, scenario_id=scenario_id,
            duration_seconds=2, warmup_seconds=1, decision_interval_seconds=1, minimum_green_hold_seconds=5,
            policies={"ql":policy}, model_ids={"ql":model_id}, record_timeline=False)
        database.update_scenario(scenario_id, engine_config='{"demand_source":{"kind":"synthetic"}}')
        with patch("backend.main.report_export_directory", return_value=self.root):
            csv_result = self.client.post("/api/reports/export", json={"run_ids":[result["run_id"]],"format":"csv"})
            json_result = self.client.post("/api/reports/export", json={"run_ids":[result["run_id"]],"format":"json"})
        self.assertEqual(csv_result.status_code, 200, csv_result.text)
        self.assertEqual(json_result.status_code, 200, json_result.text)
        row = next(csv.DictReader(io.StringIO(csv_result.text)))
        self.assertEqual(row["Seed"], "0")
        self.assertEqual(row["Model ID"], str(model_id))
        self.assertEqual(row["Model SHA256"], policy.artifact_metadata["sha256"])
        self.assertEqual(float(row["Measurement Start Seconds"]), 1)
        self.assertEqual(float(row["Measurement Duration Seconds"]), 2)
        self.assertEqual(row["Demand Source"], "observed")
        provenance = json.loads(row["Dataset Provenance JSON"])
        self.assertEqual(provenance[0]["collection_start"], "2026-01-01T07:00:00+08:00")
        self.assertEqual(provenance[0]["sha256"], imported["summary"]["sha256"])
        saved = json_result.json()[0]["metrics"]["raw_metrics"]
        self.assertEqual(float(row["Unfinished Vehicles"]), saved["unfinished_vehicles"])
        self.assertEqual(provenance, saved["experiment"]["config"]["demand_source"]["datasets"])
