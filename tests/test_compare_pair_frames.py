"""Pair validation and render-frame windows for the two-map Compare Runs view."""
import gzip
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
from simulation.road_network import RoadNetwork
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

    def get_frames(self, left: int, right: int, start: float, end: float):
        return self.client.get("/api/compare/pair/frames", params={"left_run_id": left, "right_run_id": right, "start": start, "end": end})

    def test_active_session_renews_cookie_and_expired_session_is_not_revived(self):
        from datetime import timedelta
        from backend import security
        now = security._utc_now()
        with patch.object(security, "_utc_now", return_value=now + timedelta(seconds=100)):
            response = self.client.get("/api/auth/me")
        self.assertEqual(response.status_code, 200)
        cookie = response.headers.get("set-cookie", "")
        self.assertIn(f"Max-Age={config.SESSION_TIMEOUT}", cookie)
        self.assertIn("HttpOnly", cookie)
        with patch.object(security, "_utc_now", return_value=now + timedelta(seconds=config.SESSION_TIMEOUT + 101)):
            response = self.client.get("/api/auth/me")
        self.assertEqual(response.status_code, 401)
        self.assertNotIn("set-cookie", response.headers)

    def test_pdf_download_and_signal_evidence_share_pair_validation_and_auth(self):
        left, right = self.record_pair()
        params = {"left_run_id": left, "right_run_id": right}
        signals = self.client.get("/api/compare/pair/signals", params=params)
        self.assertEqual(signals.status_code, 200, signals.text)
        self.assertEqual(signals.json()["start"], 0)
        report = self.client.get("/api/compare/pair/report", params=params)
        self.assertEqual(report.status_code, 200, report.text[:100] if report.status_code != 200 else "")
        self.assertTrue(report.content.startswith(b"%PDF-"))
        self.assertEqual(report.headers["content-type"], "application/pdf")
        self.assertIn(f"{left}-{right}.pdf", report.headers["content-disposition"])
        for endpoint in ("report", "signals"):
            self.assertEqual(self.client.get(f"/api/compare/pair/{endpoint}", params={"left_run_id":left,"right_run_id":left}).status_code, 422)
        self.client.cookies.clear()
        self.assertEqual(self.client.get("/api/compare/pair/report", params=params).status_code, 401)

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

    def test_interactive_pair_opens_maps_without_decoding_chart_history(self):
        left, right = self.record_pair(extra_left_frames=5)
        params = {"left_run_id": left, "right_run_id": right}
        with patch.object(backend_main, "condense_compare_frame", side_effect=AssertionError("chart decoding on the opening path")):
            response = self.client.get("/api/compare/pair", params={**params, "interactive": True})
        self.assertEqual(response.status_code, 200, response.text[:500])
        pair = response.json()
        self.assertEqual(pair["playback_times"], self.shared_times)
        self.assertEqual(pair["left"]["frames"], [])
        self.assertEqual(pair["right"]["frames"], [])
        opening = pair["opening_frames"]
        self.assertEqual(opening["times"], self.shared_times[:1])
        window = self.get_frames(left, right, 0, 1).json()
        for side in ("left", "right"):
            for key in ("time", "vehicles", "queues", "junction_controls"):
                self.assertEqual(opening[side][0][key], window[side][0][key])

        # Chart sampling keeps both sides aligned, including the first and last shared frame.
        with patch.object(backend_main, "COMPARE_CHART_FRAME_LIMIT", 3):
            history = self.client.get("/api/compare/pair/history", params=params)
        self.assertEqual(history.status_code, 200, history.text[:500])
        for side in ("left", "right"):
            self.assertEqual([frame["time"] for frame in history.json()[side]],
                             [self.shared_times[0], self.shared_times[5], self.shared_times[-1]])

    def test_frames_cover_only_shared_times_in_the_window(self):
        first, second = self.record_pair(extra_left_frames=5)
        response = self.get_frames(first, second, 0, 1)
        self.assertEqual(response.status_code, 200, response.text)
        data = response.json()
        self.assertEqual(len(data["times"]), len(data["left"]))
        self.assertEqual(len(data["times"]), len(data["right"]))
        self.assertGreater(len(data["times"]), 0)
        for index, shared_time in enumerate(data["times"]):
            self.assertEqual(data["left"][index]["time"], shared_time)
            self.assertEqual(data["right"][index]["time"], shared_time)
        self.assertEqual(data["times"], [time for time in self.shared_times if time <= 1])
        self.assertEqual(data["duration"], self.shared_times[-1])
        self.assertLess(data["duration"], self.shared_times[-1] + 10)
        later = self.get_frames(first, second, 0.5, 1).json()
        self.assertEqual(later["times"], [time for time in self.shared_times if 0.5 <= time <= 1])
        self.assertLess(len(later["times"]), len(data["times"]))
        self.assertEqual(later["duration"], data["duration"])

    def test_pair_uses_the_embedded_revision_and_refuses_unverified_geometry(self):
        first, second = self.record_pair()
        payload = dict(TrafficEngine().base_network.payload, name="Recorded layout")
        fingerprint = RoadNetwork(payload).fingerprint
        for label in ("left", "right"):
            path = self.root / f"{label}.manifest.json"
            manifest = json.loads(path.read_text(encoding="utf-8"))
            manifest["experiment"]["network_sha256"] = fingerprint
            manifest["network"] = payload
            path.write_text(json.dumps(manifest), encoding="utf-8")

        params = {"left_run_id": first, "right_run_id": second}
        with patch("services.visual_network_service.load_registered_network_revision", side_effect=AssertionError):
            response = self.client.get("/api/compare/pair", params=params)
        self.assertEqual(response.status_code, 200, response.text)
        self.assertIsNotNone(response.json()["geometry"])
        self.assertEqual(response.json()["playback_times"], self.shared_times)

        manifest["experiment"]["network_sha256"] = "0" * 64
        for label in ("left", "right"):
            (self.root / f"{label}.manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
        response = self.client.get("/api/compare/pair", params=params)
        self.assertEqual(response.status_code, 200, response.text)
        self.assertIsNone(response.json()["geometry"])
        self.assertTrue(any("could not be verified" in warning for warning in response.json()["warnings"]))

    def test_gzip_index_reads_shared_frames_after_a_gap(self):
        first, second = self.record_pair()
        for run_id, label in ((first, "left"), (second, "right")):
            raw = self.root / f"{label}.jsonl"
            compressed = raw.with_suffix(".jsonl.gz")
            lines = raw.read_bytes()
            last = json.loads(lines.splitlines()[-1])
            later = json.dumps({**last, "time": 30.1}, ensure_ascii=False).encode("utf-8")
            with gzip.open(compressed, "wb") as stream:
                stream.write(lines + b"\n" + later + b"\n")
            database.update_run(run_id, timeline_path=str(compressed))

        empty = self.get_frames(first, second, 10, 20).json()
        self.assertEqual(empty["times"], [])
        self.assertEqual(empty["duration"], 30.1)
        late = self.get_frames(first, second, 30, 40).json()
        self.assertEqual(late["times"], [30.1])
        self.assertEqual(late["left"][0]["time"], 30.1)
        self.assertEqual(late["right"][0]["sequence"], len(self.shared_times))

    def test_frames_refuse_a_window_longer_than_the_limit(self):
        first, second = self.record_pair()
        self.assertEqual(self.get_frames(first, second, 0, 61).status_code, 422)
        self.assertEqual(self.get_frames(first, second, 5, 1).status_code, 422)
        self.assertEqual(self.get_frames(first, second, 0, 60).status_code, 200)

    def test_frames_refuse_the_same_run_twice(self):
        first, _ = self.record_pair()
        self.assertEqual(self.get_frames(first, first, 0, 1).status_code, 422)

    def test_frame_time_is_read_from_the_line_start_or_by_parsing(self):
        self.assertEqual(backend_main.compare_line_time('{"engine_version": "x", "time": 12.5, "vehicles": [{"time": 99}]}'), 12.5)
        self.assertEqual(backend_main.compare_line_time('{"vehicles": [], "time": 3.25}'), 3.25)
        self.assertEqual(backend_main.compare_line_time('{"status": "x"}'), 0.0)


if __name__ == "__main__":
    unittest.main()
