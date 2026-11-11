"""Manual lane-by-lane counting: four passes merge into one revision that the tool's own validation accepts. All data is synthetic."""

import csv
import json
import re
import tempfile
import threading
import unittest
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from field_observer import manual_count
from field_observer.core import COMMON, TABLES, read_json, sha256, validate, write_csv, write_json
from field_observer.gui import make_server

FPS, FRAMES = 10, 600   # a 60 s synthetic recording
DURATION = FRAMES / FPS
SITE = "tagum_site_a"


def fabricated_take(root: Path) -> Path:
    """A registered take without decoding a video: manifest, frame index, a stand-in source file and an empty draft."""
    take = root / "take"
    (take / "draft").mkdir(parents=True)
    (take / "revisions").mkdir()
    source = root / "source.mp4"
    source.write_bytes(b"synthetic stand-in, never decoded")
    write_csv(take / "frames.csv", ("frame_index", "frame_pts", "time_base", "time_s"),
              [{"frame_index": i, "frame_pts": i * 100, "time_base": "1/1000", "time_s": i / FPS} for i in range(FRAMES)])
    manifest = {"schema_version": 1, "tool_version": "test", "survey_id": "S1", "intersection_id": "site_a", "camera_id": "PHONE_01",
                "take_id": "T1", "view_segment_id": "T1", "collection_start": None, "collection_clock_status": "unknown",
                "collector": "T", "clock_note": "test", "source_kind": "synthetic", "source_path": str(source),
                "source_sha256": sha256(source), "source_bytes": source.stat().st_size, "frames_sha256": sha256(take / "frames.csv"),
                "media": {"width": 640, "height": 360, "decoded_duration_s": DURATION, "last_frame_time_s": (FRAMES - 1) / FPS}}
    write_json(take / "manifest.json", manifest)
    for name, columns in TABLES.items():
        write_csv(take / "draft" / name, columns, [])
    return take


def watch_all(directory: Path, approach: str, duration: float = DURATION):
    manual_count.add_watched(directory, approach, duration, 0, 20)
    manual_count.add_watched(directory, approach, duration, 20.4, duration)   # a 0.4 s playback hiccup is not a gap


def count_four_passes(directory: Path, duration: float = DURATION):
    """south: 2 cars to north + 1 motorcycle to east; west: 1 truck to east; north: 1 bus to south; east: 1 tricycle to west."""
    manual_count.set_site(directory, SITE)
    plan = {"south": [(3.04, "north", "car"), (10.0, "north", "car"), (30.5, "east", "motorcycle")],
            "west": [(12.0, "east", "truck")], "north": [(40.0, "south", "bus")], "east": [(55.5, "west", "tricycle")]}
    for approach, clicks in plan.items():
        for moment, exit_, vehicle in clicks:
            manual_count.add_click(directory, SITE, duration, {"approach": approach, "exit": exit_, "class": vehicle, "time_s": moment})
        watch_all(directory, approach, duration)
        manual_count.set_complete(directory, approach, duration, True, "Counter " + approach)


class ManualCountTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="manual-count-")
        self.root = Path(self.temporary.name)
        self.take = fabricated_take(self.root)
        self.directory = self.root / "manual_count"

    def tearDown(self):
        self.temporary.cleanup()

    def test_four_complete_passes_export_a_revision_the_tool_validates(self):
        count_four_passes(self.directory)
        revision = manual_count.export_manual(self.take, self.directory, "Reviewer", "Hand count, synthetic test", bin_seconds=30)
        manifest = read_json(revision / "manifest.json")
        for name in ("events.csv", "coverage.csv", "reviewed_bins.csv", "lines.json"):
            self.assertEqual(sha256(revision / name), manifest["artifact_sha256"][name])
        validate(self.take)   # the tool's own checks pass on the merged draft
        with (revision / "events.csv").open(newline="", encoding="utf-8") as stream:
            events = list(csv.DictReader(stream))
        arrivals = [row for row in events if row["event_type"] == "vehicle_arrival"]
        exits = [row for row in events if row["event_type"] == "vehicle_discharge"]
        self.assertEqual((len(arrivals), len(exits)), (6, 6))
        self.assertTrue(all(row["review_status"] == "accepted" and row["review_method"] == "manual_count" for row in events))
        # Each arrival has a matching exit sharing its episode, and the exit is on the street the counter chose.
        by_episode = {row["episode_id"]: row for row in exits}
        first = next(row for row in arrivals if row["approach_id"] == "south" and float(row["time_s"]) == 3.0)  # 3.04 snaps to the frame at 3.0
        self.assertEqual((first["reviewed_class"], by_episode[first["episode_id"]]["location_id"]), ("car", "north_exit"))
        lines = read_json(revision / "lines.json")["lines"]
        self.assertEqual({line["approach_id"] for line in lines if line["role"] == "arrival"}, {"north", "south", "east", "west"})
        self.assertEqual({line["location_id"] for line in lines if line["role"] == "exit"}, {"north_exit", "south_exit", "east_exit", "west_exit"})
        with (revision / "reviewed_bins.csv").open(newline="", encoding="utf-8") as stream:
            bins = list(csv.DictReader(stream))
        self.assertEqual({(float(row["start_s"]), float(row["end_s"])) for row in bins}, {(0.0, 30.0), (30.0, 60.0)})   # one shared grid
        self.assertTrue(all(row["count"] != "" for row in bins))   # complete bins only
        total = sum(int(row["count"]) for row in bins if row["event_type"] == "vehicle_arrival")
        self.assertEqual(total, 6)

    def test_an_incomplete_pass_blocks_export_and_is_named(self):
        manual_count.set_site(self.directory, SITE)
        for approach in ("south", "west", "north"):
            watch_all(self.directory, approach)
            manual_count.set_complete(self.directory, approach, DURATION, True, "T")
        with self.assertRaisesRegex(ValueError, "Not complete: east"):
            manual_count.export_manual(self.take, self.directory, "R", "n")
        self.assertEqual(list((self.take / "revisions").iterdir()), [])   # nothing exported, nothing guessed

    def test_a_pass_cannot_be_completed_over_a_skipped_stretch(self):
        manual_count.set_site(self.directory, SITE)
        manual_count.add_watched(self.directory, "south", DURATION, 0, 25)
        manual_count.add_watched(self.directory, "south", DURATION, 35, DURATION)   # 10 s never played
        with self.assertRaisesRegex(ValueError, "played through"):
            manual_count.set_complete(self.directory, "south", DURATION, True, "T")
        manual_count.add_watched(self.directory, "south", DURATION, 25, 35)
        manual_count.set_complete(self.directory, "south", DURATION, True, "T")

    def test_clicks_are_validated_undone_and_survive_a_restart(self):
        manual_count.set_site(self.directory, SITE)
        bad = [{"exit": "south", "class": "car"},            # cannot leave by the leg it came in on
               {"exit": "north", "class": "jeepney"},         # only the five engine classes
               {"exit": "north", "class": "car", "time_s": DURATION + 1}]
        for extra in bad:
            with self.assertRaises(ValueError):
                manual_count.add_click(self.directory, SITE, DURATION, {"approach": "south", "time_s": 1, **extra})
        manual_count.add_click(self.directory, SITE, DURATION, {"approach": "south", "exit": "north", "class": "car", "time_s": 1.5})
        manual_count.add_click(self.directory, SITE, DURATION, {"approach": "south", "exit": "east", "class": "bus", "time_s": 2.5})
        saved = manual_count.load_pass(self.directory, "south")   # what a fresh process would read
        self.assertEqual([click["class"] for click in saved["clicks"]], ["car", "bus"])
        manual_count.undo_click(self.directory, "south")
        self.assertEqual([click["class"] for click in manual_count.load_pass(self.directory, "south")["clicks"]], ["car"])
        manual_count.undo_click(self.directory, "south")
        with self.assertRaises(ValueError):
            manual_count.undo_click(self.directory, "south")

    def test_a_detector_review_draft_is_not_overwritten(self):
        count_four_passes(self.directory)
        row = {key: "" for key in TABLES["events.csv"]}
        write_csv(self.take / "draft" / "events.csv", TABLES["events.csv"], [{**row, **{key: "x" for key in COMMON}, "event_id": "D1"}])
        with self.assertRaisesRegex(ValueError, "detector review draft"):
            manual_count.export_manual(self.take, self.directory, "R", "n")

    def test_the_site_cannot_change_under_existing_clicks(self):
        manual_count.set_site(self.directory, SITE)
        manual_count.add_click(self.directory, SITE, DURATION, {"approach": "south", "exit": "north", "class": "car", "time_s": 1})
        with self.assertRaises(ValueError):
            manual_count.set_site(self.directory, "tagum_site_b")


class ManualCountPageTests(unittest.TestCase):
    """The page's HTTP API on the scripted demo recording (a real, decodable 4 s video)."""

    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="manual-count-gui-")
        self.server = make_server(Path(self.temporary.name))
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.url = f"http://127.0.0.1:{self.server.server_port}"
        with urlopen(self.url) as response:
            html = response.read().decode()
        self.token = re.search(r"const token='([^']+)'", html)[1]
        self.service = self.server.observer
        self.assertIn('id="mcMap"', html)

    def tearDown(self):
        self.service.cancel.set()
        if self.service.thread:
            self.service.thread.join(20)
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(5)
        self.temporary.cleanup()

    def post(self, route, body):
        request = Request(self.url + route, json.dumps(body).encode(), {"Content-Type": "application/json", "X-Observer-Token": self.token})
        with urlopen(request, timeout=30) as response:
            return json.load(response)

    def wait_job(self, expected):
        self.service.thread.join(25)
        self.assertFalse(self.service.thread.is_alive())
        self.assertEqual(self.service.status, expected, self.service.message)

    def test_four_passes_over_http_export_a_downloadable_revision(self):
        self.post("/api/demo", {})
        self.wait_job("ready")
        duration = self.service.manifest["media"]["decoded_duration_s"]
        self.assertTrue(self.post("/api/manual/site", {"site": SITE})["manual"]["site"]["id"] == SITE)
        moments = {"south": 0.5, "north": 1.0, "west": 1.5, "east": 2.0}
        exits = {"south": "north", "north": "south", "west": "east", "east": "west"}
        for approach in moments:
            state = self.post("/api/manual/click", {"approach": approach, "exit": exits[approach], "class": "car", "time_s": moments[approach]})["manual"]
            self.assertFalse(state["can_export"])
            self.post("/api/manual/watched", {"approach": approach, "start": 0, "end": duration})
            state = self.post("/api/manual/complete", {"approach": approach, "complete": True, "reviewer": "Demo reviewer"})["manual"]
        self.assertTrue(state["can_export"])
        self.post("/api/manual/export", {"reviewer": "Demo reviewer", "note": "Synthetic demo, 4 s"})
        self.wait_job("ready")
        self.assertIsNotNone(self.service.revision, self.service.message)
        with urlopen(self.url + "/api/export.zip") as response:
            self.assertEqual(response.headers["Content-Type"], "application/zip")
            self.assertGreater(len(response.read()), 100)
        with self.assertRaises(HTTPError) as caught:   # no token, no change
            urlopen(Request(self.url + "/api/manual/undo", b"{}", {"Content-Type": "application/json"}))
        self.assertEqual(caught.exception.code, 400)


if __name__ == "__main__":
    unittest.main()
