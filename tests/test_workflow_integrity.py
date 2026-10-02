"""Playback identity, observed hold-outs and cross-workload admission."""
import copy
import json
import os
import tempfile
import threading
import time
import unittest
from concurrent.futures import ThreadPoolExecutor
from types import SimpleNamespace
from pathlib import Path
from unittest.mock import patch

os.environ.setdefault("SMARTFLOW_SECRET_KEY", "workflow-integrity-test-only")

from fastapi.testclient import TestClient
import config
import database
from backend.main import app
from backend.simulation_runtime import simulation_runtime
from services import observed_data_import as importer, rl_training_service as worker
from services.observation_identity import validate_observed_holdout
from services.training_settings import prepare_settings
from services.workload_admission import WorkloadAdmission, WorkloadConflict, workload_admission
from simulation.road_network import load_network
from simulation.traffic_engine import TrafficEngine
from tools import evaluate_controllers


class WorkflowIntegrityTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory(prefix="workflow-", dir=Path(__file__).resolve().parent)
        self.root = Path(self.directory.name)
        self.patches = [patch.object(config, "DB_PATH", str(self.root / "isolated.db")),
                        patch.object(config, "BOOTSTRAP_ADMIN_PASSWORD", "WorkflowAdmin42!"),
                        patch.object(worker, "LOG_DIR", self.root / "jobs"),
                        patch.object(importer, "IMPORT_DIRECTORY", self.root / "imports")]
        for item in self.patches:
            item.start()
        self.client = TestClient(app)
        self.client.__enter__()
        response = self.client.post("/api/auth/login", json={"username": "admin", "password": "WorkflowAdmin42!"})
        self.assertEqual(response.status_code, 200, response.text)
        simulation_runtime.reset(force=True)
        self.train_id = database.create_scenario("Synthetic training", traffic_density="single", pedestrian_density="none")
        self.eval_id = database.create_scenario("Synthetic evaluation", traffic_density="low", pedestrian_density="none")
        self.settings = {"scenario_id": self.train_id, "evaluation_scenario_id": self.eval_id,
                         "episodes": 1, "seeds": "11", "evaluation_seeds": "101", "warmup_seconds": 0,
                         "evaluation_seconds": 1, "decision_interval_seconds": 1, "minimum_green_hold_seconds": 5}
        network = load_network()
        self.source, self.destination = next((a, b) for a in network.boundaries for b in network.boundaries
                                             if a != b and network.route(a, b))

    def tearDown(self):
        simulation_runtime.reset(force=True)
        if worker._active_job_id is not None:
            worker.stop_training_job(worker._active_job_id)
            self.wait_for_job(worker._active_job_id)
        self.client.__exit__(None, None, None)
        for item in reversed(self.patches):
            item.stop()
        self.directory.cleanup()

    def observed(self, *, time_s=0, date="2026-01-01", formatted=False, **kwargs):
        csv_text = (f"\ufeffvehicle_type,destination,time_s,source\r\nCAR,{self.destination},{time_s:.3f},{self.source}\r\n" if formatted else
                    f"time_s,source,destination,vehicle_type\n{time_s},{self.source},{self.destination},car\n")
        return importer.import_observations(kind="trips", csv_text=csv_text, source_description="Artificial regression fixture",
            source_kind="observed", collected_on=date, engine_config={"traffic_density": "none", "pedestrian_density": "none"}, **kwargs)

    def save_pair(self, first, second):
        database.update_scenario(self.train_id, engine_config=json.dumps(first["engine_config"]))
        database.update_scenario(self.eval_id, engine_config=json.dumps(second["engine_config"]))

    @staticmethod
    def wait_for_job(job_id, timeout=20):
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            job = database.get_rl_training_job(job_id)
            if job["status"] in {"completed", "error", "interrupted"} and worker._active_job_id is None:
                return job
            time.sleep(.02)
        raise AssertionError("Worker failed to terminate")

    def test_playback_switch_uses_manifest_seed_and_controller_without_rewriting_frames(self):
        recordings = []
        for seed in (0, 11):
            scenario = database.get_scenario_by_id(self.train_id)
            run = evaluate_controllers._run_controller_once(controller="fixed-time", seed=seed, scenario=scenario,
                scenario_id=self.train_id, duration_seconds=.2, warmup_seconds=0, decision_interval_seconds=1,
                minimum_green_hold_seconds=5, policies={}, model_ids={}, record_timeline=True)
            path = Path(run["timeline_path"])
            recordings.append((run["run_id"], seed, path, path.read_bytes()))
        self.client.post("/api/simulation/configure", json={"scenario_id": self.train_id, "seed": 42})
        for run_id, seed, path, contents in recordings:
            response = self.client.post("/api/simulation/playback/load", json={"run_id": run_id})
            self.assertEqual(response.status_code, 200, response.text)
            state = response.json()["simulation"]
            self.assertEqual(state["seed"], seed)
            self.assertIn("Fixed", state["state"]["playback"]["source_controller_label"])
            self.assertEqual(path.read_bytes(), contents)
        failed = self.client.post("/api/simulation/playback/load", json={"run_id": 99999})
        self.assertEqual(failed.status_code, 409)
        self.assertEqual(self.client.get("/api/simulation/state").json()["seed"], 11)

    def test_reformatted_duplicate_rejected_for_every_training_algorithm_without_rows(self):
        self.save_pair(self.observed(), self.observed(formatted=True, date="2026-01-02"))
        for algorithm in ("ql", "dql", "ppo"):
            response = self.client.post("/api/rl/jobs", json={"algorithms": [algorithm], "settings": self.settings})
            self.assertEqual(response.status_code, 422, response.text)
            self.assertIn("duplicates", response.text)
        self.assertEqual(database.list_rl_training_jobs(), [])

    def test_collection_overlap_rejects_different_arrivals_and_disjoint_periods_allow(self):
        first = self.observed(collection_start="2026-01-01T07:00:00+08:00", collection_end="2026-01-01T08:00:00+08:00")
        second = self.observed(time_s=1, collection_start="2026-01-01T07:30:00+08:00", collection_end="2026-01-01T08:30:00+08:00")
        self.save_pair(first, second)
        with self.assertRaisesRegex(ValueError, "overlap"):
            prepare_settings(self.settings)
        second = self.observed(time_s=1, collection_start="2026-01-01T08:00:00+08:00", collection_end="2026-01-01T09:00:00+08:00")
        self.save_pair(first, second)
        self.assertEqual(prepare_settings(self.settings)["scenario_id"], self.train_id)
        self.save_pair(first, self.observed(time_s=1, date="2026-01-02"))
        prepare_settings(self.settings)

    def test_date_only_and_mixed_synthetic_provenance_cannot_hide_overlap(self):
        first, second = self.observed(), self.observed(time_s=1)
        for value in (first, second):
            value["engine_config"]["demand_source"]["kind"] = "synthetic"
        self.save_pair(first, second)
        with self.assertRaisesRegex(ValueError, "overlap"):
            prepare_settings(self.settings)
        self.save_pair(first, copy.deepcopy(first))
        with self.assertRaisesRegex(ValueError, "duplicates"):
            prepare_settings(self.settings)

    def test_legacy_relocated_paths_and_equivalent_arrivals_reject_duplicates(self):
        first, second = self.observed(), self.observed(formatted=True, date="2026-01-02")
        for value in (first, second):
            source = value["engine_config"]["demand_source"]["datasets"][0]
            source.pop("normalized_sha256")
            source.pop("observation_rows_sha256")
            source["source_path"] = str(self.root / "old-unavailable-path.csv")
        with self.assertRaisesRegex(ValueError, "duplicates"):
            validate_observed_holdout(first, second)

    def test_invalid_collection_metadata_fails_before_source_retention(self):
        for fields in ({"collection_start": "2026-01-01T07:00:00+08:00"},
                       {"collection_start": "2026-01-01T07:00:00", "collection_end": "2026-01-01T08:00:00"},
                       {"collection_start": "2026-01-01T07:00:00+08:00", "collection_end": "2026-01-01T07:00:01+08:00"}):
            with self.assertRaises(ValueError):
                self.observed(time_s=2, **fields)
        self.assertFalse((self.root / "imports").exists())

    def test_manual_evaluation_checks_actual_model_snapshot_and_cli_all_algorithms(self):
        trained, duplicate = self.observed(), self.observed(formatted=True, date="2026-01-02")
        database.update_scenario(self.eval_id, engine_config=json.dumps(duplicate["engine_config"]))
        actual = {"id": 77, "engine_config": trained["engine_config"]}
        model = {"id": 1, "algorithm": "ql"}
        with patch.object(database, "get_rl_model_by_id", return_value=model), patch.object(worker, "validate_model_for_settings", return_value={"scenario": actual, "seed_set": [11]}):
            with self.assertRaisesRegex(ValueError, "duplicates"):
                worker.enqueue_model_evaluation(model_id=1, settings=self.settings)
        path = self.root / "evaluation.json"
        path.write_text(json.dumps({"id": self.eval_id, "engine_config": duplicate["engine_config"]}), encoding="utf-8")
        for algorithm in ("ql", "dql", "ppo"):
            args = ["evaluate_controllers.py", "--controllers", algorithm, "--scenario-file", str(path), f"--{algorithm}-model", str(self.root / "model")]
            with patch("sys.argv", args), patch.object(evaluate_controllers, "artifact_metadata", return_value={"scenario": actual}), patch.object(evaluate_controllers, "load_runtime_policy") as load:
                with self.assertRaisesRegex(ValueError, "duplicates"):
                    evaluate_controllers.main()
                load.assert_not_called()
        self.assertEqual(database.get_runs(), [])
        self.assertEqual(database.list_rl_training_jobs(), [])

    def test_live_and_paused_execution_block_jobs_and_recordings_before_allocation(self):
        with patch.object(simulation_runtime, "_start_background_runner_locked"):
            live = self.client.post("/api/simulation/start", json={"scenario_id": self.train_id, "duration_seconds": 10})
        self.assertEqual(live.status_code, 200, live.text)
        for paused in (False, True):
            if paused:
                self.client.post("/api/simulation/pause")
            job = self.client.post("/api/rl/jobs", json={"algorithms": ["ql"], "settings": self.settings})
            recording = self.client.post("/api/simulation/timelines", json={"scenario_id": self.train_id, "duration_seconds": 1})
            self.assertEqual(job.status_code, 409, job.text)
            self.assertEqual(recording.status_code, 409, recording.text)
            self.assertIn("live simulation", job.text)
        self.assertEqual(len(database.get_runs()), 1)
        self.assertEqual(database.list_rl_training_jobs(), [])
        self.client.post("/api/simulation/stop")
        token = workload_admission.acquire("verification")
        workload_admission.release(token)

    def test_training_failure_and_cancellation_hold_admission_until_worker_exits(self):
        entered, release = threading.Event(), threading.Event()
        def blocked_launch(*args, **kwargs):
            entered.set()
            if not release.wait(10):
                raise AssertionError("test worker release timed out")
            raise OSError("injected launch failure")
        with patch.object(worker, "_start_process", side_effect=blocked_launch):
            job_id = worker.enqueue_training_job(algorithms=["ql"], settings=self.settings)
            try:
                self.assertTrue(entered.wait(5))
                worker.stop_training_job(job_id)
                live = self.client.post("/api/simulation/start", json={"scenario_id": self.train_id})
                record = self.client.post("/api/simulation/timelines", json={"scenario_id": self.train_id, "duration_seconds": 1})
                self.assertEqual(live.status_code, 409, live.text)
                self.assertEqual(record.status_code, 409, record.text)
                self.assertEqual(database.get_runs(), [])
            finally:
                release.set()
                job = self.wait_for_job(job_id)
        self.assertEqual(job["status"], "interrupted")
        token = workload_admission.acquire("verification")
        workload_admission.release(token)

    def test_recording_failure_blocks_live_and_training_then_releases(self):
        entered, release = threading.Event(), threading.Event()
        def blocked_step(*args, **kwargs):
            entered.set()
            release.wait(10)
            raise RuntimeError("injected recording failure")
        with patch.object(TrafficEngine, "step", side_effect=blocked_step):
            recording = self.client.post("/api/simulation/timelines", json={"scenario_id": self.train_id, "duration_seconds": 1})
            self.assertEqual(recording.status_code, 200, recording.text)
            run_id = recording.json()["run"]["id"]
            try:
                self.assertTrue(entered.wait(5))
                live = self.client.post("/api/simulation/start", json={"scenario_id": self.train_id})
                job = self.client.post("/api/rl/jobs", json={"algorithms": ["ql"], "settings": self.settings})
                self.assertEqual(live.status_code, 409, live.text)
                self.assertEqual(job.status_code, 409, job.text)
                self.assertEqual(database.list_rl_training_jobs(), [])
            finally:
                release.set()
                deadline = time.monotonic() + 5
                while time.monotonic() < deadline:
                    try:
                        token = workload_admission.acquire("verification")
                        workload_admission.release(token)
                        break
                    except WorkloadConflict:
                        time.sleep(.02)
                else:
                    self.fail("Recording did not release admission")
        self.assertEqual(database.get_run_by_id(run_id)["status"], "error")

    def test_atomic_admission_and_stale_release_cannot_unblock_current_work(self):
        admission = WorkloadAdmission()
        barrier = threading.Barrier(3)
        admitted, rejected = [], []
        def acquire(kind):
            barrier.wait()
            try:
                admitted.append(admission.acquire(kind))
            except WorkloadConflict:
                rejected.append(kind)
        threads = [threading.Thread(target=acquire, args=(kind,)) for kind in ("live", "recording")]
        for thread in threads:
            thread.start()
        barrier.wait()
        for thread in threads:
            thread.join(5)
        self.assertEqual((len(admitted), len(rejected)), (1, 1))
        stale = admitted[0]
        admission.release(stale)
        current = admission.acquire("training")
        admission.release(stale)
        with self.assertRaises(WorkloadConflict):
            admission.acquire("recording")
        admission.release(current)

    def test_pedestrian_overlap_and_vehicle_replacement_keep_active_provenance(self):
        junction = next(iter(load_network().intersections))
        def pedestrians(count):
            return importer.import_observations(kind="pedestrian_counts", csv_text=f"start_s,end_s,junction,count\n0,60,{junction},{count}\n",
                source_description="Artificial pedestrian fixture", source_kind="observed", collected_on="2026-01-01",
                engine_config={"traffic_density": "none", "pedestrian_density": "none"})
        first, second = pedestrians(1), pedestrians(2)
        with self.assertRaisesRegex(ValueError, "overlap"):
            validate_observed_holdout(first, second)
        first_vehicle = self.observed()
        native = first_vehicle["engine_config"]
        native["demand_source"]["datasets"].extend(first["engine_config"]["demand_source"]["datasets"])
        replaced = importer.import_observations(kind="od_counts", csv_text=f"start_s,end_s,source,destination,count\n0,60,{self.source},{self.destination},2\n",
            source_description="Artificial replacement fixture", source_kind="observed", collected_on="2026-01-02", engine_config=native)
        self.assertEqual([item["schema"] for item in replaced["engine_config"]["demand_source"]["datasets"]], ["pedestrian_counts", "od_counts"])

    def test_simultaneous_live_and_training_api_admit_exactly_one_workload(self):
        barrier, release = threading.Barrier(2), threading.Event()
        def blocked_launch(*args, **kwargs):
            release.wait(10)
            raise OSError("bounded race fixture")
        def start_live():
            barrier.wait()
            return self.client.post("/api/simulation/start", json={"scenario_id": self.train_id})
        def start_training():
            barrier.wait()
            return self.client.post("/api/rl/jobs", json={"algorithms": ["ql"], "settings": self.settings})
        with patch.object(simulation_runtime, "_start_background_runner_locked"), patch.object(worker, "_start_process", side_effect=blocked_launch):
            try:
                with ThreadPoolExecutor(max_workers=2) as pool:
                    live_future, train_future = pool.submit(start_live), pool.submit(start_training)
                    live, train = live_future.result(timeout=10), train_future.result(timeout=10)
                self.assertEqual(sorted([live.status_code, train.status_code]), [200, 409], (live.text, train.text))
                self.assertEqual(len(database.get_runs()) + len(database.list_rl_training_jobs()), 1)
            finally:
                release.set()
                if worker._active_job_id is not None:
                    self.wait_for_job(worker._active_job_id)
                self.client.post("/api/simulation/stop")

    def test_thread_launch_failures_release_admission_and_terminalize_allocated_jobs(self):
        from unittest.mock import Mock
        failed_thread = SimpleNamespace(Thread=Mock(side_effect=RuntimeError("thread unavailable")))
        with patch.object(worker, "threading", failed_thread):
            with self.assertRaisesRegex(RuntimeError, "thread unavailable"):
                worker.enqueue_training_job(algorithms=["ql"], settings=self.settings)
        self.assertEqual(database.list_rl_training_jobs()[0]["status"], "error")
        from services import timeline_generator
        with patch.object(timeline_generator, "threading", failed_thread):
            response = self.client.post("/api/simulation/timelines", json={"scenario_id": self.train_id, "duration_seconds": 1})
        self.assertEqual(response.status_code, 503, response.text)
        self.assertEqual(database.get_runs()[0]["status"], "error")
        token = workload_admission.acquire("verification")
        workload_admission.release(token)


if __name__ == "__main__":
    unittest.main()
