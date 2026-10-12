"""Real HTTP/media checks against isolated GUI workspaces and labeled synthetic input."""

import copy
import json
import re
import tempfile
import threading
import unittest
from pathlib import Path
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

    def test_gui_demo_boxes_counts_playback_review_and_export_roundtrip(self):
        import av
        self.assertIn('type="file"', self.html)
        self.assertIn('id="player" controls', self.html)
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
        for row in rows:
            pedestrian = row["event_type"].startswith("pedestrian_")
            self.post("/api/review", {"event_id": row["event_id"], "time_s": float(row["time_s"]),
                      "reviewed_class": "person" if pedestrian else "tricycle", "vehicle_subtype": "" if pedestrian else "tagum_passenger_tricycle",
                      "review_status": "corrected", "reviewer": "Synthetic reviewer", "note": "Invented correction for software test"})
        self.post("/api/review", {"line_id": "VEHICLES_IN", "time_s": .4, "reviewed_class": "car",
                  "review_status": "accepted", "reviewer": "Synthetic reviewer", "note": "Invented missed event"})
        for line in self.service.config["lines"]:
            self.post("/api/coverage", {"line_id": line["id"], "start_s": 0,
                      "end_s": self.service.manifest["media"]["decoded_duration_s"], "visibility": "complete",
                      "full_pass": True, "reviewer": "Synthetic reviewer"})
        self.post("/api/export", {"reviewer": "Synthetic reviewer", "note": "Software test only"})
        self.wait_job("complete")
        self.assertTrue(self.service.revision)
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

    def test_cross_site_and_missing_token_requests_cannot_mutate(self):
        for headers in ({"X-Observer-Token": "bad"}, {"Origin": "https://example.com"}):
            with self.assertRaises(HTTPError) as error:
                self.post("/api/demo", {}, headers)
            self.assertEqual(error.exception.code, 400)
        self.assertIsNone(self.service.project)

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
