"""CLI recording isolation and conservative resume identity checks."""
import copy
import hashlib
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

os.environ.setdefault("SMARTFLOW_SECRET_KEY", "portable-input-tests-only")

import config
import database
from services import backup_bundle, timeline_generator
from services.scenario_identity import validate_resume_snapshot
from simulation.timeline_engine import TimelinePlaybackEngine
from tools import evaluate_controllers
from tools.training_inputs import cumulative_training_seeds


class PortableInputTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory(prefix="portable-inputs-", dir=Path(__file__).resolve().parent)
        self.root = Path(self.directory.name).resolve()
        self.addCleanup(self.directory.cleanup)

    def test_cli_recordings_in_two_databases_preserve_bytes_and_restore(self):
        for gzip_enabled in (True, False):
            with self.subTest(gzip_enabled=gzip_enabled), patch.object(config, "TIMELINE_GZIP_ENABLED", gzip_enabled):
                first_path = None
                first_bytes = None
                for index, seed in enumerate((11, 22)):
                    db_path = self.root / f"{gzip_enabled}-{index}.db"
                    with patch.object(config, "DB_PATH", str(db_path)):
                        database.init_db()
                        database.seed_data()
                        scenario_id = database.create_scenario("CLI recording fixture", traffic_density="single",
                                                               pedestrian_density="none")
                        scenario = database.get_scenario_by_id(scenario_id)
                        result = evaluate_controllers._run_controller_once(
                            controller="fixed-time", seed=seed, scenario=scenario, scenario_id=scenario["id"],
                            duration_seconds=.2, warmup_seconds=0, decision_interval_seconds=1,
                            minimum_green_hold_seconds=5, policies={}, model_ids={}, record_timeline=True,
                        )
                        self.assertEqual(result["run_id"], 1)
                        path = Path(result["timeline_path"])
                        api_paths = timeline_generator._artifact_paths(1)
                        self.assertEqual(path, api_paths[1] if gzip_enabled else api_paths[0])
                        self.assertTrue(path.is_absolute())
                        manifest = json.loads(api_paths[2].read_text(encoding="utf-8"))
                        self.assertEqual(Path(manifest["artifacts"]["timeline_path_canonical"]), path)
                        playback = TimelinePlaybackEngine(1, str(path))
                        self.assertNotEqual(playback.status, "error", playback.last_error)
                        self.assertEqual(playback.seed, seed)
                        if first_path is None:
                            first_path, first_bytes = path, path.read_bytes()
                        else:
                            self.assertNotEqual(first_path, path)
                            self.assertEqual(first_path.read_bytes(), first_bytes)

                        filename = backup_bundle.create_bundle(1)
                        backup_id = next(row["id"] for row in database.list_backups() if row["filename"] == filename)
                        stage = backup_bundle.restore_bundle_to_stage(backup_id)
                    with patch.object(config, "DB_PATH", str(stage / "smartflow.db")):
                        restored_path = Path(database.get_run_by_id(1)["timeline_path"])
                        self.assertTrue(restored_path.is_relative_to(stage))
                        self.assertEqual(restored_path.read_bytes(), path.read_bytes())
                        replay = TimelinePlaybackEngine(1, str(restored_path))
                        self.assertNotEqual(replay.status, "error", replay.last_error)
                        self.assertEqual(replay.seed, seed)

    def snapshots(self):
        contents = b"time_s,source,destination,vehicle_type\n1,a,b,car\n"
        digest = hashlib.sha256(contents).hexdigest()
        original = self.root / "original.csv"
        relocated = self.root / "restored.csv"
        original.write_bytes(contents)
        relocated.write_bytes(contents)
        trained = {"id": 3, "name": "Frozen training inputs", "intersection_id": "tagum_network",
                   "engine_config": {"controlled_junction": "junction-a", "trips": [{"time": 1}],
                                     "signal_plans": {"junction-a": {"minimum_green": 10}},
                                     "demand_source": {"kind": "observed", "datasets": [{
                                         "schema": "trips", "sha256": digest, "network_sha256": "network-v1",
                                         "collected_on": "2026-01-01", "source_path": str(original)}]}}}
        current = copy.deepcopy(trained)
        current["engine_config"]["demand_source"]["datasets"][0]["source_path"] = str(relocated)
        original.unlink()
        return trained, current, relocated

    def test_resume_allows_verified_relocation_for_api_and_cli_metadata(self):
        trained, current, _ = self.snapshots()
        original_metadata = copy.deepcopy(trained)
        validate_resume_snapshot(trained, current)
        self.assertEqual(trained, original_metadata)
        for algorithm in ("ql", "dql", "ppo"):
            with self.subTest(algorithm=algorithm):
                artifact = self.root / ("ql.json" if algorithm == "ql" else f"{algorithm}.zip")
                metadata = {"scenario": trained, "seed_set": [11]}
                target = artifact if algorithm == "ql" else artifact.with_suffix(".metadata.json")
                target.write_text(json.dumps({"metadata": metadata} if algorithm == "ql" else metadata), encoding="utf-8")
                self.assertEqual(cumulative_training_seeds((22,), artifact, algorithm, current), (11, 22))
        serialized = copy.deepcopy(current)
        serialized["engine_config"] = json.dumps(current["engine_config"])
        validate_resume_snapshot(trained, serialized)

    def test_resume_rejects_changed_inputs_despite_identical_source_hash(self):
        trained, current, _ = self.snapshots()
        mutations = [
            lambda item: item["engine_config"]["trips"][0].update(time=2),
            lambda item: item["engine_config"].update(controlled_junction="junction-b"),
            lambda item: item["engine_config"]["signal_plans"]["junction-a"].update(minimum_green=20),
            lambda item: item["engine_config"]["demand_source"]["datasets"][0].update(network_sha256="other-network"),
            lambda item: item["engine_config"]["demand_source"].update(kind="synthetic"),
        ]
        for index, mutate in enumerate(mutations):
            with self.subTest(mutation=index):
                changed = copy.deepcopy(current)
                mutate(changed)
                with self.assertRaisesRegex(ValueError, "original training scenario snapshot"):
                    validate_resume_snapshot(trained, changed)

    def test_resume_accepts_legacy_windows_source_bytes_without_rewriting_them(self):
        trained, current, relocated = self.snapshots()
        windows_bytes = relocated.read_bytes().replace(b"\n", b"\r\n")
        relocated.write_bytes(windows_bytes)
        validate_resume_snapshot(trained, current)
        self.assertEqual(relocated.read_bytes(), windows_bytes)

    def test_resume_rejects_missing_corrupt_or_unidentified_relocated_source(self):
        trained, current, relocated = self.snapshots()
        relocated.write_bytes(b"changed source bytes")
        with self.assertRaisesRegex(ValueError, "checksum differs"):
            validate_resume_snapshot(trained, current)
        relocated.unlink()
        with self.assertRaisesRegex(ValueError, "missing or unreadable"):
            validate_resume_snapshot(trained, current)
        for snapshot in (trained, current):
            del snapshot["engine_config"]["demand_source"]["datasets"][0]["sha256"]
        with self.assertRaisesRegex(ValueError, "original training scenario snapshot"):
            validate_resume_snapshot(trained, current)


if __name__ == "__main__":
    unittest.main()
