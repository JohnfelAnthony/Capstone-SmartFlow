"""Real HTTP/media checks against isolated GUI workspaces and labeled synthetic input."""

import copy
import json
import re
import tempfile
import threading
import unittest
from pathlib import Path
from unittest.mock import patch
from urllib.error import HTTPError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from field_observer.core import load_tables, read_json, sha256
from field_observer.gui import ObserverGUI, make_server


class GUITests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="observer-gui-")
        self.root = Path(self.temporary.name)
        self.server = make_server(self.root)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.url = f"http://127.0.0.1:{self.server.server_port}"
        with urlopen(self.url) as response:
            self.html = response.read().decode()
        self.token = re.search(r"const token='([^']+)'", self.html)[1]
        self.service = self.server.observer

    def tearDown(self):
        self.service.cancel.set()
        if self.service.thread:
            self.service.thread.join(20)
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(5)
        self.temporary.cleanup()

    def post(self, route, body, headers=None):
        request = Request(self.url + route, json.dumps(body).encode(),
                          {"Content-Type": "application/json", "X-Observer-Token": self.token, **(headers or {})})
        with urlopen(request, timeout=30) as response:
            return json.load(response)

    def wait_job(self, expected):
        self.service.thread.join(25)
        self.assertFalse(self.service.thread.is_alive(), "Background operation did not finish.")
        self.assertEqual(self.service.status, expected, self.service.message)

    def demo(self):
        self.post("/api/demo", {})
        self.wait_job("ready")

    def run_demo(self):
        self.demo()
        self.post("/api/analyze", {"config": self.service.config, "confidence": .35})
        self.wait_job("complete")

    def test_queue_samples_capture_visibility_and_frame(self):
        self.run_demo()
        self.post("/api/queue", {"time_s": 1.0, "approach_id": "N", "queue_count": 7,
                                 "visibility": "complete", "reviewer": "Tester"})
        self.post("/api/queue", {"time_s": 1.5, "approach_id": "N", "queue_count": None,
                                 "visibility": "unknown", "reviewer": "Tester"})
        rows = load_tables(self.service.take)["queue_samples.csv"]
        self.assertEqual([(r["queue_count"], r["visibility"]) for r in rows], [("7", "complete"), ("", "unknown")])
        self.assertTrue(all(r["frame_pts"] and r["review_status"] == "accepted" for r in rows))
        with self.assertRaises(HTTPError):
            self.post("/api/queue", {"time_s": 1, "approach_id": "N", "queue_count": -1,
                                     "visibility": "complete", "reviewer": "Tester"})

    def test_review_records_a_configured_exit(self):
        self.demo()
        config = copy.deepcopy(self.service.config)
        exit_line = copy.deepcopy(config["lines"][0])
        exit_line.update(id="EXIT_EAST", event_type="vehicle_discharge", location_id="E_EXIT", approach_id="E")
        config["lines"].append(exit_line)
        self.post("/api/analyze", {"config": config, "confidence": .35})
        self.wait_job("complete")
        event = next(row for row in self.service.events()["events"] if row["event_type"] == "vehicle_arrival")
        review = {"event_id": event["event_id"], "reviewed_class": "car", "review_status": "accepted",
                  "reviewer": "Tester", "exit_id": "EXIT_EAST"}
        self.post("/api/review", review)
        saved = next(row for row in self.service.events()["events"] if row["event_id"] == event["event_id"])
        self.assertEqual(saved["exit_id"], "EXIT_EAST")
        with self.assertRaises(HTTPError):
            self.post("/api/review", {**review, "exit_id": "INVALID"})

    def test_gui_demo_boxes_counts_playback_review_and_export_roundtrip(self):
        import av
        self.assertIn('type="file"', self.html)
        self.assertIn('id="player" controls', self.html)
        for subtype in ("bao_bao", "pedicab"):
            self.assertIn(f'<option value="{subtype}">', self.html)
        self.assertNotIn("tagum_passenger_tricycle", self.html)
        self.run_demo()
        run = self.service.run
        frozen = sha256(run / "proposals.csv")
        self.assertEqual(read_json(run / "run.json")["proposal_count"], 3)
        self.assertIn("SCRIPTED", read_json(run / "run.json")["detector"]["model"])
        self.assertEqual(sum(row["count"] for row in self.service.state()["counts"]), 3)
        with av.open(str(run / "preview.mp4")) as container:
            times = [float(frame.pts * frame.time_base) for frame in container.decode(video=0)]
        self.assertEqual(len(times), 100)
        self.assertAlmostEqual(times[1], .04)
        self.assertAlmostEqual(times[-1], 3.96)
        with urlopen(Request(self.url + "/api/replay", headers={"Range": "bytes=0-31"})) as response:
            self.assertEqual(response.status, 206)
            self.assertEqual(len(response.read()), 32)
            self.assertTrue(response.headers["Content-Range"].startswith("bytes 0-31/"))
        with self.assertRaises(HTTPError) as invalid:
            urlopen(Request(self.url + "/api/replay", headers={"Range": "bytes=999999999-"}))
        self.assertEqual(invalid.exception.code, 416)
        rows = self.service.events()["events"]
        vehicle = next(row for row in rows if row["event_type"].startswith("vehicle_"))
        with self.assertRaises(HTTPError) as retired:
            self.post("/api/review", {"event_id": vehicle["event_id"], "time_s": float(vehicle["time_s"]),
                      "reviewed_class": "tricycle", "vehicle_subtype": "tagum_passenger_tricycle",
                      "review_status": "corrected", "reviewer": "Synthetic reviewer", "note": "Retired subtype name"})
        self.assertEqual(retired.exception.code, 400)
        self.assertEqual(json.loads(retired.exception.read())["error"], "Unknown tricycle subtype.")
        with self.assertRaises(HTTPError) as mismatch:
            self.post("/api/review", {"event_id": vehicle["event_id"], "time_s": float(vehicle["time_s"]),
                      "reviewed_class": "unknown", "vehicle_subtype": "pedicab",
                      "review_status": "accepted", "reviewer": "Synthetic reviewer"})
        self.assertEqual(mismatch.exception.code, 400)
        self.assertEqual(json.loads(mismatch.exception.read())["error"], "A tricycle subtype requires the tricycle class.")
        self.assertIn(vehicle, self.service.events()["events"])  # rejected save leaves the event unchanged
        subtypes = iter(("pedicab", "bao_bao"))  # the demo's two vehicle events
        for row in rows:
            pedestrian = row["event_type"].startswith("pedestrian_")
            self.post("/api/review", {"event_id": row["event_id"], "time_s": float(row["time_s"]),
                      "reviewed_class": "person" if pedestrian else "tricycle", "vehicle_subtype": "" if pedestrian else next(subtypes),
                      "review_status": "corrected", "reviewer": "Synthetic reviewer", "note": "Invented correction for software test"})
        reviewed = {row["vehicle_subtype"] for row in self.service.events()["events"] if row["reviewed_class"] == "tricycle"}
        self.assertEqual(reviewed, {"pedicab", "bao_bao"})
        self.post("/api/review", {"line_id": "VEHICLES_IN", "time_s": .4, "reviewed_class": "car",
                  "review_status": "accepted", "reviewer": "Synthetic reviewer", "note": "Invented missed event"})
        for line in self.service.config["lines"]:
            self.post("/api/coverage", {"line_id": line["id"], "start_s": 0,
                      "end_s": self.service.manifest["media"]["decoded_duration_s"], "visibility": "complete",
                      "full_pass": True, "reviewer": "Synthetic reviewer"})
        self.post("/api/export", {"reviewer": "Synthetic reviewer", "note": "Software test only"})
        self.wait_job("complete")
        self.assertTrue(self.service.revision)
        self.assertEqual(read_json(self.service.revision / "lines.json"), self.service.config)
        revision_manifest = read_json(self.service.revision / "manifest.json")
        self.assertEqual(revision_manifest["artifact_sha256"]["lines.json"], sha256(self.service.revision / "lines.json"))
        quality = read_json(self.service.revision / "quality_report.json")
        self.assertEqual(quality["accepted_event_count"], 4)
        self.assertEqual(quality["source_kind"], "synthetic")
        self.assertFalse(quality["field_accuracy_verified"])
        self.assertEqual(sha256(run / "proposals.csv"), frozen)
        with urlopen(self.url + "/api/export.zip") as response:
            self.assertTrue(response.read().startswith(b"PK"))
        reopened = ObserverGUI(self.root)
        reopened.open_project(self.service.project.name)
        self.assertEqual(reopened.status, "complete")
        self.assertEqual(len(reopened.events()["events"]), 4)
        from contextlib import redirect_stdout
        from io import StringIO
        from field_observer.__main__ import main
        with redirect_stdout(StringIO()):
            result = main(["export", str(self.service.take), "--reviewer", "Tester", "--note", "CLI test",
                           "--analysis", str(run)])
        self.assertEqual(result, 0)
        cli_revision = self.service.take / "revisions" / "r000002"
        self.assertEqual(read_json(cli_revision / "lines.json"), self.service.config)

    def test_cross_site_and_missing_token_requests_cannot_mutate(self):
        for headers in ({"X-Observer-Token": "bad"}, {"Origin": "https://example.com"}):
            with self.assertRaises(HTTPError) as error:
                self.post("/api/demo", {}, headers)
            self.assertEqual(error.exception.code, 400)
        self.assertIsNone(self.service.project)

    def test_browser_cancelled_response_is_ignored_quietly(self):
        # Windows raises ConnectionAbortedError when a video seek cancels a download.
        handler = self.server.RequestHandlerClass
        errors = []
        with patch.object(handler, "json_response", side_effect=ConnectionAbortedError(10053, "aborted")), \
             patch.object(self.server, "handle_error", side_effect=lambda *args: errors.append(args)):
            with self.assertRaises(OSError):
                urlopen(self.url + "/api/state", timeout=10)
            with self.assertRaises(OSError):
                self.post("/api/demo", {})
        self.assertEqual(errors, [])

    def test_uploaded_invalid_media_has_clear_error_and_never_becomes_observed_counts(self):
        metadata = dict(name="broken.mp4", survey_id="S1", intersection_id="J1", collector="Tester", source_kind="synthetic")
        request = Request(self.url + "/api/upload?" + urlencode(metadata), b"not a video",
                          {"X-Observer-Token": self.token, "Content-Type": "application/octet-stream"})
        with urlopen(request) as response:
            self.assertTrue(json.load(response)["ok"])
        self.wait_job("error")
        self.assertIn("Cannot decode", self.service.message)
        self.assertIsNone(self.service.manifest)
        self.assertFalse(self.service.state()["counts"])

    def test_cancel_preserves_interrupted_run_and_blocks_other_work(self):
        self.demo()
        self.post("/api/analyze", {"config": self.service.config, "confidence": .35})
        with self.assertRaises(HTTPError):
            self.post("/api/demo", {})
        self.post("/api/stop", {})
        self.wait_job("cancelled")
        self.assertEqual(read_json(self.service.run / "run.json")["status"], "interrupted")
        self.assertFalse(load_tables(self.service.take)["events.csv"])
        with self.assertRaises(HTTPError):
            self.post("/api/export", {"reviewer": "test", "note": "should fail"})

    def test_wrong_config_and_false_complete_coverage_are_rejected(self):
        self.demo()
        config = copy.deepcopy(self.service.config)
        config["source_sha256"] = "wrong"
        with self.assertRaises(HTTPError):
            self.post("/api/analyze", {"config": config})
        self.assertEqual(self.service.status, "ready")
        with self.assertRaises(HTTPError):
            self.post("/api/coverage", {"line_id": "VEHICLES_IN", "start_s": 0, "end_s": 1,
                      "visibility": "complete", "reviewer": "test", "full_pass": False})
        self.assertFalse(load_tables(self.service.take)["coverage.csv"])


if __name__ == "__main__":
    unittest.main()
