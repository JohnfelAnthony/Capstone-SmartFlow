"""Permission, restart, and portable artifact backup workflows."""
import json
import os
import subprocess
import sys
import tempfile
import threading
import unittest
import zipfile
from datetime import UTC, datetime, timedelta
from pathlib import Path
from unittest.mock import patch

os.environ.setdefault("SMARTFLOW_SECRET_KEY", "operations-tests-only")
os.environ.setdefault("SMARTFLOW_BOOTSTRAP_ADMIN_PASSWORD", "OperationsAdmin42!")

from fastapi.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

import auth
import config
import database
from backend.main import app, resolve_artifact_path
from backend.simulation_runtime import simulation_runtime
from services import timeline_generator
from simulation import road_network
from simulation.ql_agent import TabularQLearningAgent
from simulation.timeline_engine import TimelinePlaybackEngine
from simulation.traffic_engine import TrafficEngine


class OperationsTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory(prefix="operations-", dir=Path(__file__).resolve().parent)
        self.root = Path(self.directory.name)
        self.db_patch = patch.object(config, "DB_PATH", str(self.root / "live.db"))
        self.password_patch = patch.object(config, "BOOTSTRAP_ADMIN_PASSWORD", "OperationsAdmin42!")
        self.db_patch.start()
        self.password_patch.start()
        self.client = TestClient(app)
        self.client.__enter__()
        self.assertEqual(self.client.post("/api/auth/login", json={
            "username": "admin", "password": "OperationsAdmin42!"}).status_code, 200)
        simulation_runtime.reset()
        self.scenario = next(row for row in database.get_scenarios() if row["traffic_density"] == "Single")

    def tearDown(self):
        simulation_runtime.reset()
        self.client.__exit__(None, None, None)
        self.db_patch.stop()
        self.password_patch.stop()
        self.assertTrue(self.root.resolve().is_relative_to(Path(__file__).resolve().parent))
        self.directory.cleanup()

    def test_recording_paths_are_isolated_by_database(self):
        from services import rl_training_service
        first_jobs = rl_training_service._job_root()
        first_raw, first_gzip, first_manifest = timeline_generator._artifact_paths(1)
        first_raw.write_text("first database recording\n", encoding="utf-8")
        with patch.object(config, "DB_PATH", str(self.root / "live.sqlite")):
            second_jobs = rl_training_service._job_root()
            second_raw, second_gzip, second_manifest = timeline_generator._artifact_paths(1)
            self.assertNotEqual((first_raw, first_gzip, first_manifest),
                                (second_raw, second_gzip, second_manifest))
            second_raw.write_text("second database recording\n", encoding="utf-8")
            timeline_generator._prune_old_raw_timelines()
        self.assertEqual(first_raw.read_text(encoding="utf-8"), "first database recording\n")
        self.assertEqual(second_raw.read_text(encoding="utf-8"), "second database recording\n")
        self.assertNotEqual(first_jobs, second_jobs)

    def test_recording_admission_limits_duration_space_and_concurrency(self):
        request = {"scenario_id": self.scenario["id"], "duration_seconds": 10, "seed": 7}
        too_long = self.client.post("/api/simulation/timelines", json={**request, "duration_seconds": 3601})
        self.assertEqual(too_long.status_code, 422)
        with patch("backend.main.shutil.disk_usage") as disk_usage:
            disk_usage.return_value.free = 0
            no_space = self.client.post("/api/simulation/timelines", json=request)
        self.assertEqual(no_space.status_code, 507)
        with patch.object(timeline_generator, "generate_timeline") as generator:
            admitted = self.client.post("/api/simulation/timelines", json=request)
            self.assertEqual(admitted.status_code, 200, admitted.text)
            concurrent = self.client.post("/api/simulation/timelines", json=request)
        self.assertEqual(concurrent.status_code, 409)
        database.update_run(admitted.json()["run"]["id"], status="completed")
        from services.workload_admission import workload_admission
        workload_admission.release(generator.call_args.kwargs["workload_lease"])
        missing = self.root / "missing-run.jsonl"
        self.assertEqual(resolve_artifact_path(str(missing)), missing)
        self.assertEqual(TimelinePlaybackEngine._resolve_timeline_path(1, str(missing)), missing)

    def test_backup_keeps_configured_replacement_network(self):
        replacement = self.root / "replacement-network.json"
        payload = json.loads(road_network.NETWORK_PATH.read_text(encoding="utf-8"))
        payload["id"] = "replacement_network"
        replacement.write_text(json.dumps(payload), encoding="utf-8")
        with patch.object(road_network, "NETWORK_PATH", replacement):
            response = self.client.post("/api/admin/backups")
            self.assertEqual(response.status_code, 200, response.text)
            backup_id = response.json()["backup"]["id"]
            restored = self.client.post(f"/api/admin/backups/{backup_id}/restore")
        self.assertEqual(restored.status_code, 200, restored.text)
        stage = Path(restored.json()["restore_path"])
        environment = json.loads((stage / "restore_environment.json").read_text(encoding="utf-8"))
        restored_network = Path(environment["SMARTFLOW_NETWORK_PATH"])
        self.assertEqual(restored_network.read_bytes(), replacement.read_bytes())
        self.assertEqual(road_network.load_network(restored_network).id, "replacement_network")

    def test_replacement_network_starts_through_api(self):
        replacement = self.root / "replacement-api-network.json"
        payload = json.loads(road_network.NETWORK_PATH.read_text(encoding="utf-8"))
        payload.update(id="replacement_network", name="Replacement Study Network")
        replacement.write_text(json.dumps(payload), encoding="utf-8")
        script = "\n".join([
            "from fastapi.testclient import TestClient",
            "from backend.main import app",
            "with TestClient(app) as client:",
            "    assert client.post('/api/auth/login', json={'username':'admin','password':'OperationsAdmin42!'}).status_code == 200",
            "    options = client.get('/api/simulation/options')",
            "    assert options.status_code == 200 and options.json()['network_id'] == 'replacement_network', options.text",
            "    visual = client.get('/api/visual-network', params={'intersection_id':'replacement_network'})",
            "    assert visual.status_code == 200 and visual.json()['network_id'] == 'replacement_network', visual.text",
            "    scenario = client.post('/api/scenarios', json={'name':'Replacement scenario','intersection_id':'replacement_network','traffic_density':'Single','pedestrian_density':'None'})",
            "    assert scenario.status_code == 200 and scenario.json()['intersection_id'] == 'replacement_network', scenario.text",
            "    scenario_id = scenario.json()['id']",
            "    assert client.get(f'/api/scenarios/{scenario_id}/native-config').status_code == 200",
            "    assert client.post('/api/simulation/configure', json={'scenario_id':scenario_id}).status_code == 200",
            "    assert client.post('/api/simulation/start', json={}).status_code == 200",
            "    assert client.post('/api/simulation/stop', json={}).status_code == 200",
        ])
        result = subprocess.run([sys.executable, "-c", script], cwd=Path(__file__).resolve().parents[1],
            env={**os.environ, "SMARTFLOW_DB_PATH": str(self.root / "replacement-api.db"),
                 "SMARTFLOW_NETWORK_PATH": str(replacement), "SMARTFLOW_SECRET_KEY": "replacement-test-secret",
                 "SMARTFLOW_BOOTSTRAP_ADMIN_PASSWORD": "OperationsAdmin42!"},
            capture_output=True, text=True, timeout=45)
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_view_only_user_cannot_run_training_or_simulation(self):
        database.create_user("Viewer", "viewer", None, auth.hash_password("ViewerPassword42!"), role_id=2)
        database.update_role_permission(2, "rl-training", "run", False)
        database.update_role_permission(2, "simulation", "run", False)
        with TestClient(app) as viewer:
            login = viewer.post("/api/auth/login", json={"username": "viewer", "password": "ViewerPassword42!"})
            self.assertEqual(login.status_code, 200, login.text)
            self.assertEqual(viewer.get("/api/rl/jobs").status_code, 200)
            self.assertEqual(viewer.post("/api/rl/jobs", json={"algorithms": ["ql"]}).status_code, 403)
            self.assertEqual(viewer.post("/api/rl/jobs/1/stop").status_code, 403)
            self.assertEqual(viewer.post("/api/rl/evaluate", json={"model_id": 1}).status_code, 403)
            self.assertEqual(viewer.post("/api/simulation/configure", json={"scenario_id": self.scenario["id"]}).status_code, 403)
            self.assertEqual(viewer.get("/api/admin/backups").status_code, 403)
            self.assertEqual(viewer.post("/api/auth/logout").status_code, 200)
            self.assertEqual(viewer.get("/api/auth/me").status_code, 401)
        rejected = self.client.put("/api/admin/roles/2/permissions", json={"updates": [
            {"page": "admin-backup", "action": "view", "enabled": True}]})
        self.assertEqual(rejected.status_code, 422, rejected.text)

    def test_expired_session_and_restart_reconciliation(self):
        user_id = database.create_user("Operator", "operator", None, auth.hash_password("OperatorPassword42!"), role_id=2)
        with TestClient(app) as operator:
            self.assertEqual(operator.post("/api/auth/login", json={"username": "operator", "password": "OperatorPassword42!"}).status_code, 200)
            self.assertEqual(operator.get("/api/auth/me").status_code, 200)
            with database.get_db() as conn:
                conn.execute("UPDATE user_sessions SET expires_at = ? WHERE user_id = ?",
                             ((datetime.now(UTC) - timedelta(minutes=1)).isoformat(), user_id))
            self.assertEqual(operator.get("/api/auth/me").status_code, 401)
        partial = self.root / "partial.jsonl"
        partial.write_text('{"time": 0}\n', encoding="utf-8")
        run_id = database.create_run(self.scenario["id"], user_id, timeline_path=str(partial))
        log = self.root / "training.log"
        log.write_text("partial evidence\n", encoding="utf-8")
        job_id = database.create_rl_training_job(user_id=user_id, selected_algorithms=["ql"], log_path=str(log))
        item_id = database.create_rl_training_job_item(job_id=job_id, algorithm="ql", sequence_index=0)
        database.update_rl_training_job(job_id, status="running")
        database.update_rl_training_job_item(item_id, status="running")
        self.assertEqual(database.reconcile_incomplete_runs(), 1)
        self.assertEqual(database.reconcile_incomplete_rl_training_jobs(), 1)
        self.assertEqual(database.get_run_by_id(run_id)["status"], "stopped")
        self.assertEqual(database.get_rl_training_job(job_id)["status"], "interrupted")
        self.assertEqual(database.get_rl_training_job_items(job_id)[0]["status"], "interrupted")
        self.assertTrue(partial.exists())
        self.assertEqual(log.read_text(encoding="utf-8"), "partial evidence\n")
        self.assertEqual(self.client.post("/api/simulation/configure", json={"scenario_id": self.scenario["id"]}).status_code, 200)

    def test_logout_revokes_open_simulation_stream(self):
        with self.client.websocket_connect("/ws/simulation") as stream:
            self.assertEqual(stream.receive_json()["sequence"], 0)
            self.assertEqual(self.client.post("/api/auth/logout").status_code, 200)
            with self.assertRaises(WebSocketDisconnect) as closed:
                while True:
                    stream.receive_json()
            self.assertEqual(closed.exception.code, 1008)

    def test_simulation_stream_rejects_foreign_browser_origin(self):
        with self.assertRaises(WebSocketDisconnect) as closed:
            with self.client.websocket_connect("/ws/simulation", headers={"origin": "https://untrusted.example"}) as stream:
                stream.receive_json()
        self.assertEqual(closed.exception.code, 1008)

    def test_legacy_sqlite_restore_is_staged_without_replacing_live_data(self):
        filename = database.create_backup(1)
        backup_id = next(row["id"] for row in database.list_backups() if row["filename"] == filename)
        with database.get_db() as conn:
            conn.execute("UPDATE scenarios SET name = 'Live newer scenario' WHERE id = ?", (self.scenario["id"],))
        restored = self.client.post(f"/api/admin/backups/{backup_id}/restore")
        self.assertEqual(restored.status_code, 200, restored.text)
        self.assertIn("separate directory", restored.json()["message"])
        stage = Path(restored.json()["restore_path"])
        with patch.object(config, "DB_PATH", str(stage / "smartflow.db")):
            self.assertEqual(database.get_scenario_by_id(self.scenario["id"])["name"], self.scenario["name"])
            with database.get_db() as conn:
                self.assertEqual(conn.execute("SELECT count(*) FROM user_sessions").fetchone()[0], 0)
        self.assertEqual(database.get_scenario_by_id(self.scenario["id"])["name"], "Live newer scenario")

    def test_backup_restores_scenario_model_and_recording_in_isolation(self):
        source = self.root / "observed.csv"
        source.write_text("time_s,source,destination\n", encoding="utf-8")
        with database.get_db() as conn:
            config_data = json.loads(conn.execute("SELECT engine_config FROM scenarios WHERE id = ?", (self.scenario["id"],)).fetchone()[0])
            config_data["demand_source"] = {"kind": "synthetic", "datasets": [{"source_path": str(source)}]}
            conn.execute("UPDATE scenarios SET engine_config = ? WHERE id = ?", (json.dumps(config_data), self.scenario["id"]))
        model_path = self.root / "model.json"
        TabularQLearningAgent(action_count=5).save(model_path)
        model_id = database.create_rl_model(name="Restore QL", checkpoint_path=str(model_path))
        engine = TrafficEngine(seed=42)
        engine.configure(traffic_density="single", pedestrian_density="none")
        engine.start(1)
        frames = [engine.to_dict()]
        while engine.status == "running":
            engine.step(1)
            frames.append(engine.to_dict())
        timeline = self.root / "known.jsonl"
        timeline.write_text("".join(json.dumps(frame) + "\n" for frame in frames), encoding="utf-8")
        timeline.with_suffix(".manifest.json").write_text(json.dumps({
            "experiment": engine.experiment_metadata(), "controller": {"provenance": "fixed-time"},
            "timeline": {"actual_duration_seconds": 1, "frame_count": len(frames)}}), encoding="utf-8")
        run_id = database.create_run(self.scenario["id"], None, status="completed", run_mode="pre-record",
                                     duration_seconds=1, timeline_path=str(timeline))
        response = self.client.post("/api/admin/backups")
        self.assertEqual(response.status_code, 200, response.text)
        backup_id = response.json()["backup"]["id"]
        self.assertEqual(self.client.get(f"/api/admin/backups/{backup_id}/download").status_code, 200)
        with database.get_db() as conn:
            conn.execute("UPDATE scenarios SET name = 'Changed after backup' WHERE id = ?", (self.scenario["id"],))
        restored = self.client.post(f"/api/admin/backups/{backup_id}/restore")
        self.assertEqual(restored.status_code, 200, restored.text)
        stage = Path(restored.json()["restore_path"])
        self.assertTrue(stage.is_relative_to(self.root))
        with patch.object(config, "DB_PATH", str(stage / "smartflow.db")):
            scenario = database.get_scenario_by_id(self.scenario["id"])
            self.assertEqual(scenario["name"], self.scenario["name"])
            restored_config = json.loads(scenario["engine_config"])
            restored_source = Path(restored_config["demand_source"]["datasets"][0]["source_path"])
            self.assertEqual(restored_source.read_text(encoding="utf-8"), source.read_text(encoding="utf-8"))
            restored_model = Path(database.get_rl_model_by_id(model_id)["checkpoint_path"])
            self.assertEqual(TabularQLearningAgent.load(restored_model).action_count, 5)
            restored_timeline = database.get_run_by_id(run_id)["timeline_path"]
            playback = TimelinePlaybackEngine(run_id, restored_timeline)
            self.assertNotEqual(playback.status, "error", playback.last_error)
            with database.get_db() as conn:
                self.assertEqual(conn.execute("SELECT count(*) FROM user_sessions").fetchone()[0], 0)
            simulation_runtime.reset()
            with TestClient(app) as restored_app:
                self.assertEqual(restored_app.get("/api/scenarios").status_code, 401)
                login = restored_app.post("/api/auth/login", json={"username": "admin", "password": "OperationsAdmin42!"})
                self.assertEqual(login.status_code, 200, login.text)
                self.assertEqual(restored_app.get("/api/scenarios").status_code, 200)
                self.assertEqual(restored_app.get("/api/rl/models").status_code, 200)
                loaded = restored_app.post("/api/simulation/playback/load", json={"run_id": run_id})
                self.assertEqual(loaded.status_code, 200, loaded.text)
        self.assertEqual(database.get_scenario_by_id(self.scenario["id"])["name"], "Changed after backup")
        restore_environment = json.loads((stage / "restore_environment.json").read_text(encoding="utf-8"))
        restored_process = subprocess.run([sys.executable, "-c", "\n".join([
            "import database, sys",
            "from simulation.ql_agent import TabularQLearningAgent",
            "from simulation.timeline_engine import TimelinePlaybackEngine",
            "from simulation.road_network import load_network",
            "assert load_network().fingerprint",
            "model = database.get_rl_model_by_id(int(sys.argv[1]))",
            "assert TabularQLearningAgent.load(model['checkpoint_path']).action_count == 5",
            "run = database.get_run_by_id(int(sys.argv[2]))",
            "playback = TimelinePlaybackEngine(int(sys.argv[2]), run['timeline_path'])",
            "assert playback.status != 'error', playback.last_error",
        ]), str(model_id), str(run_id)], cwd=Path(__file__).resolve().parents[1],
            env={**os.environ, **{key: value for key, value in restore_environment.items() if key.startswith("SMARTFLOW_")},
                 "SMARTFLOW_SECRET_KEY": "restored-process-test-secret"}, capture_output=True, text=True, timeout=30)
        self.assertEqual(restored_process.returncode, 0, restored_process.stderr)
        archive = database._resolve_backup_path(response.json()["backup"]["filename"])
        tampered = self.root / "tampered.zip"
        with zipfile.ZipFile(archive) as source_bundle, zipfile.ZipFile(tampered, "w") as modified_bundle:
            for member in source_bundle.namelist():
                content = source_bundle.read(member)
                modified_bundle.writestr(member, content + b"corrupt" if member == "smartflow.db" else content)
        os.replace(tampered, archive)
        rejected = self.client.post(f"/api/admin/backups/{backup_id}/restore")
        self.assertEqual(rejected.status_code, 422, rejected.text)

    def test_engine_and_recording_failure_keep_evidence_and_allow_next_run(self):
        configured = self.client.post("/api/simulation/configure", json={"scenario_id": self.scenario["id"]})
        self.assertEqual(configured.status_code, 200, configured.text)
        with patch.object(simulation_runtime, "_start_background_runner_locked"):
            started = self.client.post("/api/simulation/start", json={})
        self.assertEqual(started.status_code, 200, started.text)
        run_id = started.json()["simulation"]["active_run_id"]
        with patch.object(TrafficEngine, "step", side_effect=RuntimeError("injected tick failure")):
            failed = self.client.post("/api/simulation/step", json={"num_ticks": 1})
        self.assertEqual(failed.status_code, 409, failed.text)
        self.assertEqual(database.get_run_by_id(run_id)["status"], "error")
        self.assertIn("injected tick failure", database.get_run_by_id(run_id)["notes"])
        self.assertEqual(self.client.post("/api/simulation/reset").status_code, 200)
        self.assertEqual(self.client.post("/api/simulation/configure", json={"scenario_id": self.scenario["id"]}).status_code, 200)
        with patch.object(simulation_runtime, "_start_background_runner_locked"):
            restarted = self.client.post("/api/simulation/start", json={})
        self.assertEqual(restarted.status_code, 200, restarted.text)
        self.assertNotEqual(restarted.json()["simulation"]["active_run_id"], run_id)
        self.assertEqual(self.client.post("/api/simulation/stop").status_code, 200)

        recording_id = database.create_run(self.scenario["id"], None, status="running", run_mode="pre-record")
        raw = self.root / "failed-recording.jsonl"
        artifacts = (raw, self.root / "failed-recording.jsonl.gz", self.root / "failed-recording.manifest.json")
        completed = threading.Event()
        result = []

        def on_complete(status, payload):
            result.append((status, payload))
            completed.set()

        with patch.object(timeline_generator, "_artifact_paths", return_value=artifacts), \
                patch.object(TrafficEngine, "step", side_effect=RuntimeError("injected recording failure")):
            worker = timeline_generator.generate_timeline(self.scenario["id"], 1, recording_id, on_complete=on_complete)
            self.assertTrue(completed.wait(10))
            worker.join(timeout=5)
        self.assertEqual(result[0][0], "error")
        self.assertEqual(database.get_run_by_id(recording_id)["status"], "error")
        self.assertTrue(raw.exists())
        self.assertEqual(len(raw.read_text(encoding="utf-8").splitlines()), 1)
        next_id = database.create_run(self.scenario["id"], None, status="running", run_mode="pre-record")
        next_raw = self.root / "next-recording.jsonl"
        next_artifacts = (next_raw, self.root / "next-recording.jsonl.gz", self.root / "next-recording.manifest.json")
        completed.clear()
        result.clear()
        with patch.object(timeline_generator, "_artifact_paths", return_value=next_artifacts), \
                patch.object(timeline_generator, "_prune_old_raw_timelines"):
            worker = timeline_generator.generate_timeline(self.scenario["id"], 1, next_id, on_complete=on_complete)
            self.assertTrue(completed.wait(10))
            worker.join(timeout=5)
        self.assertEqual(result[0][0], "completed")
        self.assertEqual(database.get_run_by_id(next_id)["status"], "completed")


if __name__ == "__main__":
    unittest.main()
