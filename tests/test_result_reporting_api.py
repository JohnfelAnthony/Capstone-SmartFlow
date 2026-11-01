"""Exercise real API/CSV/JSON interpretation using isolated synthetic runs."""
import csv
import io
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

os.environ.setdefault("SMARTFLOW_SECRET_KEY", "result-reporting-test-only")
from fastapi.testclient import TestClient
import config
import database
from backend.main import app
from backend.simulation_runtime import simulation_runtime
from services.metric_definitions import METRIC_CATALOG
from tools.evaluate_controllers import _run_controller_once, main


class ResultReportingApiTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory(prefix="result-reporting-", dir=Path(__file__).resolve().parent)
        self.root = Path(self.directory.name)
        self.patches = [patch.object(config, "DB_PATH", str(self.root / "synthetic.db")),
                        patch.object(config, "BOOTSTRAP_ADMIN_PASSWORD", "ReportAdmin42!"),
                        patch("backend.main.report_export_directory", return_value=self.root)]
        for item in self.patches:
            item.start()
        self.client = TestClient(app)
        self.client.__enter__()
        simulation_runtime.reset(force=True)
        self.assertEqual(self.client.post("/api/auth/login", json={"username": "admin", "password": "ReportAdmin42!"}).status_code, 200)
        self.scenario_id = database.create_scenario("Empty synthetic interpretation fixture",
            engine_config=json.dumps({"traffic_density": "none", "pedestrian_density": "none"}))
        self.result = _run_controller_once(controller="fixed-time", seed=0,
            scenario=database.get_scenario_by_id(self.scenario_id), scenario_id=self.scenario_id,
            duration_seconds=2, warmup_seconds=1, decision_interval_seconds=1,
            minimum_green_hold_seconds=5, policies={}, model_ids={}, record_timeline=False)
        self.run_id = self.result["run_id"]

    def tearDown(self):
        simulation_runtime.reset(force=True)
        self.client.__exit__(None, None, None)
        for item in reversed(self.patches):
            item.stop()
        self.directory.cleanup()

    def test_catalog_and_saved_run_preserve_raw_zero_but_explain_empty_average(self):
        self.assertEqual(self.client.get("/api/metrics/definitions").json(), METRIC_CATALOG)
        run = self.client.get(f"/api/runs/{self.run_id}").json()
        self.assertEqual(run["metrics"]["raw_metrics"]["avg_wait"], 0)
        reading = run["metrics"]["metric_interpretation"]["values"]["avg_wait"]
        self.assertFalse(reading["available"])
        self.assertIsNone(reading["value"])
        self.client.cookies.clear()
        self.assertEqual(self.client.get("/api/metrics/definitions").status_code, 401)

    def test_current_reports_and_scenario_inputs_exclude_emergency_support(self):
        for settings in ({"emergency_mode": "enabled"}, {"vehicle_mix": {"emergency": 1}}):
            response = self.client.post("/api/scenarios", json={"name": "Rejected scope", "engine_config": settings})
            self.assertEqual(response.status_code, 422, response.text)
        template = self.client.get("/api/scenarios/observations/template", params={"kind": "trips", "example": True}).json()
        csv_text = template["csv_text"].replace(",car", ",emergency")
        self.assertNotEqual(csv_text, template["csv_text"])
        response = self.client.post("/api/scenarios/observations/import", json={"kind": "trips",
            "csv_text": csv_text, "source_description": "Synthetic removed-class rejection",
            "source_kind": "synthetic", "collected_on": "2026-01-01"})
        self.assertEqual(response.status_code, 422, response.text)
        for format in ("csv", "json"):
            response = self.client.post("/api/reports/export", json={"run_ids": [self.run_id], "format": format})
            self.assertEqual(response.status_code, 200, response.text)
            self.assertNotIn("emergency", response.text.lower())
        for suffix in ("", "/metrics"):
            response = self.client.get(f"/api/runs/{self.run_id}{suffix}")
            self.assertEqual(response.status_code, 200, response.text)
            self.assertNotIn("emergency", response.text.lower())

    def test_actual_csv_and_json_exports_include_definitions_windows_and_unavailability(self):
        response = self.client.post("/api/reports/export", json={"run_ids": [self.run_id], "format": "csv"})
        self.assertEqual(response.status_code, 200, response.text)
        row = next(csv.DictReader(io.StringIO(response.text)))
        self.assertEqual(row["Average Wait Seconds"], "")
        self.assertEqual(float(row["Throughput"]), 0)
        self.assertEqual(float(row["Measurement Start Seconds"]), 1)
        self.assertAlmostEqual(float(row["Measurement Duration Seconds"]), 2)
        self.assertEqual(json.loads(row["Metric Definitions JSON"]), METRIC_CATALOG)
        self.assertFalse(json.loads(row["Metric Availability JSON"])["avg_travel_time"]["available"])
        response = self.client.post("/api/reports/export", json={"run_ids": [self.run_id], "format": "json"})
        self.assertEqual(response.status_code, 200, response.text)
        payload = response.json()[0]
        self.assertEqual(payload["metric_definitions"], METRIC_CATALOG)
        self.assertEqual(payload["metrics"]["raw_metrics"]["avg_wait"], 0)
        self.assertIsNone(payload["metrics"]["metric_interpretation"]["values"]["avg_wait"]["value"])

    def test_export_names_the_condition(self):
        no_signal = _run_controller_once(controller="no-signal", seed=0, scenario=database.get_scenario_by_id(self.scenario_id), scenario_id=self.scenario_id,
            duration_seconds=2, warmup_seconds=1, decision_interval_seconds=1, minimum_green_hold_seconds=5, policies={}, model_ids={}, record_timeline=False)["run_id"]
        expected = {no_signal: "No signal (first come, first served)", self.run_id: "Traditional signal (fixed-time)"}
        csv_response = self.client.post("/api/reports/export", json={"run_ids": [no_signal, self.run_id], "format": "csv"})
        self.assertEqual(csv_response.status_code, 200, csv_response.text)
        rows = {int(row["Run ID"]): row["Condition"] for row in csv.DictReader(io.StringIO(csv_response.text))}
        self.assertEqual(rows, expected)
        json_response = self.client.post("/api/reports/export", json={"run_ids": [no_signal, self.run_id], "format": "json"})
        self.assertEqual({item["id"]: item["condition"] for item in json_response.json()}, expected)

    def test_a_comparison_label_names_the_condition(self):
        from backend.main import compare_run_label
        from backend.schemas import SimulationRunRecord
        record = SimulationRunRecord(**{**self.client.get(f"/api/runs/{self.run_id}").json(), "control_mode": "no-signal"})
        self.assertIn("No signal (first come, first served)", compare_run_label(record, {"controller": {"provenance_label": "No signal"}, "experiment": {}}))

    def test_cli_evaluation_retains_repetitions_and_qualifies_empty_results(self):
        output = self.root / "evaluation.json"
        with patch.object(sys, "argv", ["evaluate_controllers", "--scenario-id", str(self.scenario_id),
                "--controllers", "fixed-time", "--seeds", "11,22", "--duration-seconds", "2",
                "--warmup-seconds", "1", "--output", str(output)]):
            self.assertEqual(main(), 0)
        payload = json.loads(output.read_text())
        self.assertEqual(len(payload["results"]), 2)
        self.assertIsNone(payload["overall_recommendation"])
        self.assertIn("not an overall", payload["ranking_criterion"].lower())
        self.assertIsNone(payload["combined_ranking"][0]["waiting_time_rank"])
        self.assertEqual(payload["summary"]["fixed-time"]["avg_wait"]["available_count"], 0)
        self.assertEqual(payload["metric_definitions"], METRIC_CATALOG)
        self.assertIn("not a confidence interval", payload["aggregation"])


if __name__ == "__main__":
    unittest.main()
