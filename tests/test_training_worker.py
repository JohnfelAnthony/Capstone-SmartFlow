"""Real subprocess lifecycle checks with an isolated database and artifact root."""
import os
import json
import tempfile
import shutil
import time
import unittest
from pathlib import Path
from unittest.mock import patch

os.environ.setdefault("SMARTFLOW_SECRET_KEY", "native-worker-tests-only")

import config
import database
from services import rl_training_service as worker


class TrainingWorkerTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory(prefix="worker-test-", dir=Path(__file__).resolve().parent)
        self.root = Path(self.directory.name)
        self.patches = [
            patch.object(config, "DB_PATH", str(self.root / "test.db")),
            patch.object(worker, "LOG_DIR", self.root / "jobs"),
        ]
        for active_patch in self.patches:
            active_patch.start()
        database.init_db()
        self.scenario_id = database.create_scenario("Synthetic worker check", engine_config='{"demand_source":{"kind":"synthetic"}}')
        self.evaluation_scenario_id = database.create_scenario(
            "Held-out synthetic worker check", engine_config='{"traffic_density":"low","demand_source":{"kind":"synthetic"}}')
        self.settings = {
            "scenario_id": self.scenario_id, "evaluation_scenario_id": self.evaluation_scenario_id,
            "episodes": 2, "seeds": "11", "evaluation_seeds": "101",
            "warmup_seconds": 0, "evaluation_seconds": 10,
            "decision_interval_seconds": 1, "minimum_green_hold_seconds": 5,
            "checkpoint_every": 1,
        }

    def tearDown(self):
        if worker._active_job_id is not None:
            worker.stop_training_job(worker._active_job_id)
            self.wait_for_job(worker._active_job_id)
        for active_patch in reversed(self.patches):
            active_patch.stop()
        for attempt in range(20):
            try:
                self.directory.cleanup()
                break
            except PermissionError:
                if attempt == 19:
                    raise
                time.sleep(0.25)

    @staticmethod
    def wait_for_job(job_id, timeout=120):
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            job = database.get_rl_training_job(job_id)
            if job and job["status"] in {"completed", "interrupted", "error"} and worker._active_job_id is None:
                return job
            time.sleep(0.1)
        raise AssertionError(f"Job #{job_id} did not reach a terminal state")

    def test_invalid_request_does_not_queue_and_failed_launch_releases_worker(self):
        with self.assertRaisesRegex(ValueError, "Saved scenario"):
            worker.enqueue_training_job(algorithms=["ql"], settings={**self.settings, "scenario_id": -1})
        self.assertEqual(database.list_rl_training_jobs(), [])
        with self.assertRaisesRegex(ValueError, "different saved scenario"):
            worker.enqueue_training_job(algorithms=["ql"], settings={**self.settings, "evaluation_scenario_id": self.scenario_id})
        with self.assertRaisesRegex(ValueError, "must not overlap"):
            worker.enqueue_training_job(algorithms=["ql"], settings={**self.settings, "evaluation_seeds": "11"})
        with patch.object(worker, "_start_process", side_effect=OSError("launch unavailable")):
            failed_id = worker.enqueue_training_job(algorithms=["ql"], settings=self.settings)
            failed = self.wait_for_job(failed_id)
        self.assertEqual(failed["status"], "error")
        self.assertIn("launch unavailable", failed["message"])
        self.assertIsNone(worker._active_job_id)

    def test_ql_job_saves_evaluates_and_registered_checkpoint_resumes(self):
        first_id = worker.enqueue_training_job(algorithms=["ql"], settings=self.settings)
        first = self.wait_for_job(first_id)
        self.assertEqual(first["status"], "completed", first["message"])
        first_item = database.get_rl_training_job_items(first_id)[0]
        self.assertEqual(first_item["status"], "completed")
        self.assertTrue(Path(first_item["artifact_path"]).is_file())
        self.assertTrue(Path(first_item["evaluation_path"]).is_file())
        first_settings = json.loads(database.get_rl_training_job(first_id)["settings_json"])
        self.assertEqual(first_settings["scenario_snapshot"]["id"], self.scenario_id)
        self.assertEqual(first_settings["evaluation_scenario_snapshot"]["id"], self.evaluation_scenario_id)
        self.assertEqual(first_settings["seeds"], "11")
        self.assertEqual(first_settings["evaluation_seeds"], "101")
        self.assertIn('"id": %d' % self.evaluation_scenario_id, Path(first_settings["evaluation_scenario_file"]).read_text(encoding="utf-8"))
        model_id = first_item["rl_model_id"]
        with self.assertRaisesRegex(ValueError, "selected model's training seeds"):
            worker.enqueue_model_evaluation(model_id=model_id, settings={**self.settings, "seeds": "22", "evaluation_seeds": "11"})
        with self.assertRaisesRegex(ValueError, "model's training scenario"):
            worker.enqueue_model_evaluation(model_id=model_id, settings={**self.settings,
                "scenario_id": self.evaluation_scenario_id, "evaluation_scenario_id": self.scenario_id})
        manual_id = worker.enqueue_model_evaluation(model_id=model_id, settings=self.settings)
        manual = self.wait_for_job(manual_id)
        self.assertEqual(manual["status"], "completed", manual["message"])
        manual_item = database.get_rl_training_job_items(manual_id)[0]
        self.assertTrue(Path(manual_item["evaluation_path"]).is_file())
        checkpoints = database.list_rl_checkpoints(model_id)
        self.assertTrue(checkpoints)
        resumed_id = worker.enqueue_training_job(algorithms=["ql"], settings={
            **self.settings, "episodes": 1, "seeds": "22", "resume_model_id": model_id,
            "resume_checkpoint_id": checkpoints[0]["id"],
        })
        resumed = self.wait_for_job(resumed_id)
        self.assertEqual(resumed["status"], "completed", resumed["message"])
        from simulation.model_contract import artifact_metadata
        resumed_item = database.get_rl_training_job_items(resumed_id)[0]
        self.assertEqual(artifact_metadata("ql", resumed_item["artifact_path"])["seed_set"], [11, 22])

    def test_imported_checkpoints_resume_after_restore_without_original_files(self):
        from services import backup_bundle, observed_data_import
        from services.training_settings import prepare_settings
        from simulation.model_contract import artifact_metadata
        from simulation.road_network import load_network

        network = load_network()
        source, destination = next((a, b) for a in network.boundaries for b in network.boundaries
                                   if a != b and network.route(a, b))
        csv_text = f"start_s,end_s,source,destination,count\n0,600,{source},{destination},300\n"
        with patch.object(observed_data_import, "IMPORT_DIRECTORY", self.root / "imports"):
            imported = observed_data_import.import_observations(
                kind="od_counts", csv_text=csv_text, source_description="Portable synthetic training fixture",
                source_kind="synthetic", collected_on="2026-01-01")
        database.update_scenario(self.scenario_id, engine_config=json.dumps(imported["engine_config"]))
        settings = {**self.settings, "episodes": 1, "evaluation_seconds": 2}
        initial_id = worker.enqueue_training_job(
            algorithms=["ql", "dql", "ppo"], settings=settings,
            advanced={"dql": {"learning_starts": 1, "buffer_size": 10, "batch_size": 2},
                      "ppo": {"n_steps": 2, "batch_size": 2, "n_epochs": 1}},
        )
        initial = self.wait_for_job(initial_id, timeout=240)
        self.assertEqual(initial["status"], "completed", initial["message"])
        model_choices = []
        for item in database.get_rl_training_job_items(initial_id):
            checkpoints = database.list_rl_checkpoints(item["rl_model_id"])
            self.assertTrue(checkpoints, item["algorithm"])
            model_choices.append((item["algorithm"], item["rl_model_id"], checkpoints[0]["id"]))
            prepare_settings({**settings, "resume_model_id": item["rl_model_id"],
                              "resume_checkpoint_id": checkpoints[0]["id"]})

        # Rehearse existing Windows imports as well as newly byte-preserving imports.
        original_csv = Path(imported["summary"]["source_path"])
        original_csv.write_bytes(csv_text.encode("utf-8").replace(b"\n", b"\r\n"))
        database.seed_data()
        filename = backup_bundle.create_bundle(1)
        backup_id = next(row["id"] for row in database.list_backups() if row["filename"] == filename)
        stage = backup_bundle.restore_bundle_to_stage(backup_id)
        for disposable in (self.root / "imports", self.root / "jobs"):
            self.assertTrue(disposable.resolve().is_relative_to(self.root.resolve()))
            shutil.rmtree(disposable)

        with patch.object(config, "DB_PATH", str(stage / "smartflow.db")), \
                patch.object(worker, "LOG_DIR", stage / "resumed-jobs"):
            restored = database.get_scenario_by_id(self.scenario_id)
            restored_config = json.loads(restored["engine_config"])
            restored_source = Path(restored_config["demand_source"]["datasets"][0]["source_path"])
            self.assertTrue(restored_source.is_relative_to(stage))
            self.assertEqual(restored_source.read_text(encoding="utf-8"), csv_text)
            for algorithm, model_id, checkpoint_id in model_choices:
                with self.subTest(algorithm=algorithm):
                    checkpoint = database.get_rl_checkpoint_by_id(checkpoint_id)
                    artifact = Path(checkpoint["path"])
                    metadata_path = artifact if algorithm == "ql" else artifact.with_suffix(".metadata.json")
                    bytes_before = (artifact.read_bytes(), metadata_path.read_bytes())
                    prior_metadata = artifact_metadata(algorithm, artifact)
                    resumed_id = worker.enqueue_training_job(algorithms=[algorithm], settings={
                        **settings, "seeds": "22", "resume_model_id": model_id,
                        "resume_checkpoint_id": checkpoint_id,
                    })
                    resumed = self.wait_for_job(resumed_id, timeout=180)
                    self.assertEqual(resumed["status"], "completed", resumed["message"])
                    self.assertEqual((artifact.read_bytes(), metadata_path.read_bytes()), bytes_before)
                    resumed_item = database.get_rl_training_job_items(resumed_id)[0]
                    resumed_metadata = artifact_metadata(algorithm, resumed_item["artifact_path"])
                    self.assertEqual(resumed_metadata["seed_set"], [11, 22])
                    if algorithm == "ql":
                        self.assertGreater(len(resumed_metadata["episodes"]), len(prior_metadata["episodes"]))
                    else:
                        from stable_baselines3 import DQN, PPO
                        model_class = DQN if algorithm == "dql" else PPO
                        prior_steps = model_class.load(str(artifact)).num_timesteps
                        resumed_steps = model_class.load(resumed_item["artifact_path"]).num_timesteps
                        self.assertGreater(resumed_steps, prior_steps)

            restored_config["trips"][0]["time"] += .1
            database.update_scenario(self.scenario_id, engine_config=json.dumps(restored_config))
            for algorithm, model_id, checkpoint_id in model_choices:
                with self.subTest(changed_inputs=algorithm), self.assertRaisesRegex(ValueError, "original training scenario snapshot"):
                    prepare_settings({**settings, "resume_model_id": model_id, "resume_checkpoint_id": checkpoint_id})

    def test_dql_and_ppo_jobs_train_and_evaluate_from_saved_scenario(self):
        job_id = worker.enqueue_training_job(
            algorithms=["dql", "ppo"],
            settings={**self.settings, "episodes": 1},
            advanced={
                "dql": {"learning_starts": 4, "buffer_size": 100, "batch_size": 4},
                "ppo": {"n_steps": 8, "batch_size": 4, "n_epochs": 1},
            },
        )
        job = self.wait_for_job(job_id, timeout=180)
        self.assertEqual(job["status"], "completed", job["message"])
        items = database.get_rl_training_job_items(job_id)
        self.assertEqual([item["status"] for item in items], ["completed", "completed"])
        self.assertTrue(all(Path(item["evaluation_path"]).is_file() for item in items))
        from simulation.rl_policy_runtime import load_runtime_policy
        from simulation.traffic_engine import TrafficEngine
        for item in items:
            policy = load_runtime_policy(item["algorithm"], item["artifact_path"])
            engine = TrafficEngine()
            engine.set_runtime_policy(policy, decision_interval=1, minimum_green_hold=5)
            engine.start(10)
            engine.step(100)
            self.assertEqual(engine.status, "completed")
            self.assertGreater(engine.policy_decisions, 0)


if __name__ == "__main__":
    unittest.main()
