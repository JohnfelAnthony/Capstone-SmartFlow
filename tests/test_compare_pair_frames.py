"""Pair validation and render-frame windows for the two-map Compare Runs view."""
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

os.environ.setdefault("SMARTFLOW_SECRET_KEY", "compare-frames-tests-only")
os.environ.setdefault("SMARTFLOW_BOOTSTRAP_ADMIN_PASSWORD", "CompareFramesAdmin42!")

from fastapi import HTTPException
from fastapi.testclient import TestClient

import auth
import config
import database
from backend import main as backend_main
from backend.main import app
from simulation.traffic_engine import TrafficEngine


class ComparePairFramesTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory(prefix="compare-frames-", dir=Path(__file__).resolve().parent)
        self.root = Path(self.directory.name)
        self.db_patch = patch.object(config, "DB_PATH", str(self.root / "test.db"))
        self.db_patch.start()
        self.client = TestClient(app)
        self.client.__enter__()
        database.create_user("viewer", "viewer", None, auth.hash_password("CompareFramesUser42!"), role_id=1)
        login = self.client.post("/api/auth/login", json={"username": "viewer", "password": "CompareFramesUser42!"})
        self.assertEqual(login.status_code, 200, login.text)
        self.scenario = database.get_scenario_by_id(database.create_scenario("Single car", engine_config={"traffic_density": "single", "pedestrian_density": "none"}))

    def tearDown(self):
        self.client.__exit__(None, None, None)
        self.db_patch.stop()
        self.assertTrue(self.root.resolve().is_relative_to(Path(__file__).resolve().parent))
        self.directory.cleanup()

    def record_pair(self, *, extra_left_frames: int = 0) -> list[int]:
        """Two pre-record runs of one single-car engine run; the left file gets extra frames at later times."""
        engine = TrafficEngine(seed=42)
        engine.configure(traffic_density="single", pedestrian_density="none")
        engine.start(1)
        frames = [engine.to_dict()]
        while engine.status == "running":
            engine.step(1)
            frames.append(engine.to_dict())
        run_ids = []
        for label in ("left", "right"):
            written = list(frames)
            if label == "left":
                last_time = frames[-1]["time"]
                written += [{**frames[-1], "time": last_time + 10 * (index + 1)} for index in range(extra_left_frames)]
            timeline = self.root / f"{label}.jsonl"
            timeline.write_text("".join(json.dumps(frame) + "\n" for frame in written), encoding="utf-8")
            manifest = {"experiment": engine.experiment_metadata(),
                        "controller": {"provenance_label": "Fixed-Time"},
                        "scenario": {"intersection_id": engine.intersection_id},
                        "timeline": {"requested_duration_seconds": 1, "actual_duration_seconds": 1,
                                     "step_length_seconds": 0.1, "frame_count": len(written)}}
            timeline.with_suffix(".manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
            run_ids.append(database.create_run(self.scenario["id"], None, run_mode="pre-record", status="completed",
                                               control_mode="fixed-time", seed=42, duration_seconds=1, timeline_path=str(timeline)))
        self.shared_times = [frame["time"] for frame in frames]
        return run_ids

    def test_the_pair_refuses_the_same_run_and_an_incompatible_run(self):
        first, second = self.record_pair()
        with self.assertRaises(HTTPException) as same:
            backend_main.validated_compare_pair(first, first)
        self.assertEqual(same.exception.status_code, 422)
        # Compatibility reads the recorded experiment, so a different recorded seed is never comparable.
        manifest_path = (self.root / "right.manifest.json")
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        manifest["experiment"]["seed"] = 7
        manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
        with self.assertRaises(HTTPException) as different:
            backend_main.validated_compare_pair(first, second)
        self.assertEqual(different.exception.status_code, 422)


if __name__ == "__main__":
    unittest.main()
