"""Exercise actual API authentication, streaming, persistence and recording paths."""
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

os.environ.setdefault("SMARTFLOW_SECRET_KEY", "native-integration-tests-only")
os.environ.setdefault("SMARTFLOW_BOOTSTRAP_ADMIN_PASSWORD", "NativeTestAdmin42!")

from fastapi.testclient import TestClient

import auth
import config
import database
from backend.main import app
from backend.simulation_runtime import simulation_runtime
from services import timeline_generator
from simulation.model_contract import native_contract
from simulation.ql_agent import TabularQLearningAgent
from simulation.rl_env import SmartFlowRLEnv
from simulation.rl_policy_runtime import load_runtime_policy


class NativeIntegrationTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory(prefix="native-test-", dir=Path(__file__).resolve().parent)
        self.root = Path(self.directory.name)
        self.db_patch = patch.object(config, "DB_PATH", str(self.root / "test.db"))
        self.db_patch.start()
        self.client = TestClient(app)
        self.client.__enter__()
        simulation_runtime.reset()
        database.create_user("Verification", "native_test", None, auth.hash_password("NativeTestUser42!"), role_id=1)
        response = self.client.post("/api/auth/login", json={"username": "native_test", "password": "NativeTestUser42!"})
        self.assertEqual(response.status_code, 200, response.text)
        self.scenario = next(row for row in database.get_scenarios() if row["traffic_density"] == "Single")

    def tearDown(self):
        simulation_runtime.reset()
        self.client.__exit__(None, None, None)
        self.db_patch.stop()
        self.assertTrue(self.root.resolve().is_relative_to(Path(__file__).resolve().parent))
        self.directory.cleanup()

    def test_configured_values_survive_start_stream_pause_resume_and_save(self):
        response = self.client.post("/api/simulation/configure", json={"scenario_id": self.scenario["id"], "traffic_density": "low", "pedestrian_density": "none", "duration_seconds": 60})
        self.assertEqual(response.status_code, 200, response.text)
        response = self.client.post("/api/simulation/start", json={})
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(response.json()["simulation"]["state"]["scenario"]["traffic_density"], "low")
        with self.client.websocket_connect("/ws/simulation") as socket:
            first = socket.receive_json()
            second = socket.receive_json()
            self.assertEqual(first["intersection_id"], "tagum_network")
            self.assertGreater(second["sequence"], first["sequence"])
            self.assertIn("road0f", first["traffic_lights"])
        paused = self.client.post("/api/simulation/pause").json()["simulation"]
        self.assertEqual(paused["status"], "paused")
        advanced = self.client.post("/api/simulation/step", json={"num_ticks": 10}).json()["simulation"]
        self.assertEqual(advanced["state"]["time"], paused["state"]["time"])
        self.assertEqual(self.client.post("/api/simulation/resume").json()["simulation"]["status"], "running")
        self.client.post("/api/simulation/stop")
        run = database.get_runs(limit=1)[0]
        self.assertEqual(run["status"], "stopped")
        self.assertIsNotNone(database.get_run_metrics(run["id"]))

    def test_recording_and_playback_preserve_car_positions_and_metrics(self):
        run_id = database.create_run(self.scenario["id"], None, run_mode="pre-record", status="running", seed=11)
        paths = (self.root / "recording.jsonl", self.root / "recording.jsonl.gz", self.root / "recording.manifest.json")
        with patch.object(timeline_generator, "_artifact_paths", return_value=paths), patch.object(timeline_generator, "_prune_old_raw_timelines"):
            worker = timeline_generator.generate_timeline(self.scenario["id"], 5, run_id, seed=11)
            worker.join(timeout=10)
            self.assertFalse(worker.is_alive(), "Timeline worker did not finish")
        run = database.get_run_by_id(run_id)
        self.assertEqual(run["status"], "completed", run.get("notes"))
        response = self.client.post("/api/simulation/playback/load", json={"run_id": run_id})
        self.assertEqual(response.status_code, 200, response.text)
        response = self.client.post("/api/simulation/playback/seek", json={"frame_index": 50})
        state = response.json()["simulation"]["state"]
        self.assertEqual(state["time"], 5)
        self.assertEqual(state["vehicle_count"], 1)
        self.assertEqual(state["scenario"]["intersection_id"], "tagum_network")
        self.assertEqual(state["metrics"]["throughput"], 0)

    def test_rl_observation_masks_and_native_model_round_trip(self):
        env = SmartFlowRLEnv(warmup_seconds=0, evaluation_seconds=20, scenario={"traffic_density": "low"})
        try:
            observation, info = env.reset(seed=9)
            self.assertEqual(len(observation), 30)
            self.assertGreater(sum(info["valid_action_mask"]), 0)
            agent = TabularQLearningAgent(action_count=5)
            model_path = agent.save(self.root / "model.json")
            payload = json.loads(model_path.read_text())
            self.assertEqual(payload["metadata"]["native_contract"], native_contract())
            policy = load_runtime_policy("ql", model_path)
            prediction = policy.predict(observation, info)
            self.assertTrue(info["valid_action_mask"][prediction.action])
            env.step(prediction.action)
            payload["metadata"] = {}
            model_path.write_text(json.dumps(payload))
            with self.assertRaisesRegex(ValueError, "not trained"):
                load_runtime_policy("ql", model_path)
        finally:
            env.close()

    def test_native_scenario_persistence_and_atomic_config_validation(self):
        native = {"vehicle_mix": {"bus": 1, "car": 2}, "green_seconds": 20}
        response = self.client.post("/api/scenarios", json={"name": "Native configuration", "traffic_density": "high", "engine_config": native})
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(response.json()["engine_config"], native)
        scenario_id = response.json()["id"]
        response = self.client.post("/api/simulation/configure", json={"scenario_id": scenario_id})
        self.assertEqual(response.status_code, 200, response.text)
        original = response.json()["simulation"]["state"]["experiment"]["config"]
        response = self.client.post("/api/simulation/configure", json={"engine_config": {"events": None}, "traffic_density": "none"})
        self.assertEqual(response.status_code, 409, response.text)
        self.assertEqual(simulation_runtime.get_state().state["experiment"]["config"], original)

    def test_registered_native_policy_controls_run_and_unbound_rl_is_rejected(self):
        path = TabularQLearningAgent(action_count=5).save(self.root/"ql.json")
        model_id = database.create_rl_model(name="Native test policy", algorithm="ql", checkpoint_path=str(path))
        response = self.client.post("/api/simulation/configure", json={"scenario_id": self.scenario["id"], "control_mode": f"ql:{model_id}"})
        self.assertEqual(response.status_code, 200, response.text)
        response = self.client.post("/api/simulation/start", json={})
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(response.json()["simulation"]["state"]["dashboard"]["controller_provenance"], "ql")
        self.client.post("/api/simulation/stop")
        response = self.client.post("/api/simulation/configure", json={"control_mode": "rl"})
        self.assertEqual(response.status_code, 409, response.text)

    def test_legacy_recording_rejected_and_invalid_generation_marks_error(self):
        from simulation.timeline_engine import TimelinePlaybackEngine
        path = self.root/"legacy.jsonl"
        path.write_text('{"time": 0}\n')
        engine = TimelinePlaybackEngine(1, str(path))
        self.assertEqual(engine.status, "error")
        self.assertIn("incompatible", engine.last_error)
        run_id = database.create_run(self.scenario["id"], None, run_mode="pre-record", status="running")
        paths = (self.root/"bad.jsonl", self.root/"bad.jsonl.gz", self.root/"bad.manifest.json")
        with patch.object(timeline_generator, "_artifact_paths", return_value=paths), patch.object(timeline_generator, "_prune_old_raw_timelines"):
            worker = timeline_generator.generate_timeline(self.scenario["id"], 5, run_id, control_mode="rl")
            worker.join(timeout=10)
        self.assertFalse(worker.is_alive())
        self.assertEqual(database.get_run_by_id(run_id)["status"], "error")

    def test_scenario_edit_preserves_omitted_native_settings_and_can_clear_explicitly(self):
        native = {"vehicle_mix": {"bus": 1}, "green_seconds": 20}
        created = self.client.post("/api/scenarios", json={"name": "Preserve settings", "engine_config": native, "traffic_density": "high"})
        self.assertEqual(created.status_code, 200, created.text)
        scenario_id = created.json()["id"]
        changed = self.client.put(f"/api/scenarios/{scenario_id}", json={"name": "Renamed"})
        self.assertEqual(changed.status_code, 200, changed.text)
        self.assertEqual(changed.json()["engine_config"], native)
        self.assertEqual(changed.json()["traffic_density"], "high")
        invalid = self.client.put(f"/api/scenarios/{scenario_id}", json={"name": "Invalid", "engine_config": {"routing_mode": []}})
        self.assertEqual(invalid.status_code, 422, invalid.text)
        self.assertEqual(self.client.get(f"/api/scenarios/{scenario_id}").json()["name"], "Renamed")
        cleared = self.client.put(f"/api/scenarios/{scenario_id}", json={"name": "Cleared", "engine_config": {}})
        self.assertEqual(cleared.json()["engine_config"], {})

    def test_bad_playback_does_not_interrupt_an_active_run(self):
        self.client.post("/api/simulation/configure", json={"scenario_id": self.scenario["id"]})
        with patch.object(simulation_runtime, "_start_background_runner_locked"):
            self.client.post("/api/simulation/start", json={})
        original = simulation_runtime.get_state().model_dump()
        live_id = simulation_runtime._active_run_id
        path = self.root/"bad-recording.jsonl"
        path.write_text('{"time": 0}\n')
        run_id = database.create_run(self.scenario["id"], None, run_mode="pre-record", status="completed", timeline_path=str(path))
        response = self.client.post("/api/simulation/playback/load", json={"run_id": run_id})
        self.assertEqual(response.status_code, 409, response.text)
        self.assertEqual(simulation_runtime.get_state().model_dump(), original)
        self.assertEqual(database.get_run_by_id(live_id)["status"], "running")

    def test_start_failure_does_not_leave_a_running_database_record(self):
        self.client.post("/api/simulation/configure", json={"scenario_id": self.scenario["id"]})
        with patch("simulation.traffic_engine.build_schedule", side_effect=ValueError("excess demand")):
            response = self.client.post("/api/simulation/start", json={})
        self.assertEqual(response.status_code, 409, response.text)
        self.assertEqual(database.get_runs(), [])

    def test_manual_completion_saves_metrics_and_exported_provenance(self):
        self.client.post("/api/simulation/configure", json={"scenario_id": self.scenario["id"], "duration_seconds": 1})
        with patch.object(simulation_runtime, "_start_background_runner_locked"):
            response = self.client.post("/api/simulation/start", json={})
        self.assertEqual(response.status_code, 200, response.text)
        change = self.client.post("/api/simulation/start", json={"duration_seconds": 10})
        self.assertEqual(change.status_code, 409, change.text)
        final = self.client.post("/api/simulation/step", json={"num_ticks": 10}).json()["simulation"]
        self.assertEqual(final["status"], "completed")
        run = database.get_runs()[0]
        self.assertEqual(run["status"], "completed")
        self.assertEqual(run["duration_seconds"], 1)
        saved = json.loads(database.get_run_metrics(run["id"])["raw_metrics_json"])
        self.assertEqual(saved["experiment"], final["state"]["experiment"])
        for key, value in final["state"]["metrics"].items():
            self.assertEqual(saved[key], value)
        with patch("backend.main.report_export_directory", return_value=self.root):
            exported = self.client.post("/api/reports/export", json={"run_ids": [run["id"]], "format": "json"})
        self.assertEqual(exported.status_code, 200, exported.text)
        self.assertIn(final["state"]["experiment"]["demand_sha256"], exported.text)

    def test_recording_initialization_failure_is_persisted(self):
        run_id = database.create_run(self.scenario["id"], None, run_mode="pre-record", status="running")
        with patch.object(timeline_generator, "_artifact_paths", side_effect=OSError("test disk unavailable")):
            with self.assertLogs("services.timeline_generator", level="ERROR"):
                worker = timeline_generator.generate_timeline(self.scenario["id"], 1, run_id)
                worker.join(timeout=10)
        self.assertFalse(worker.is_alive())
        run = database.get_run_by_id(run_id)
        self.assertEqual(run["status"], "error")
        self.assertIn("test disk unavailable", run["notes"])

    def test_offline_evaluation_matches_headless_policy_metrics(self):
        from tools.evaluate_controllers import _run_controller_once
        from tools.run_native_experiment import run_experiment
        path = TabularQLearningAgent(action_count=5).save(self.root/"eval-model.json")
        scenario = {"name": "Matched inputs", "traffic_density": "low", "pedestrian_density": "low"}
        expected = run_experiment(scenario, seed=31, duration=6, warmup=2, policy=load_runtime_policy("ql", path))
        result = _run_controller_once(controller="ql", seed=31, scenario=scenario,
            scenario_id=self.scenario["id"], duration_seconds=6, warmup_seconds=2,
            decision_interval_seconds=5, minimum_green_hold_seconds=10,
            policies={"ql": load_runtime_policy("ql", path)}, model_ids={}, record_timeline=False)
        for key, value in expected["metrics"].items():
            self.assertEqual(result["metrics"][key], value, key)
        self.assertEqual(result["experiment"], expected["experiment"])
        self.assertEqual(len(result["experiment"]["policy"]["sha256"]), 64)


if __name__ == "__main__":
    unittest.main()
