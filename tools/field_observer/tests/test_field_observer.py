"""Synthetic evidence tests; no real traffic or detector accuracy claims."""

import copy
import csv
import importlib.util
import json
import subprocess
import sys
import tempfile
import unittest
from fractions import Fraction
from pathlib import Path
from unittest.mock import patch

from field_observer.core import (COMMON, TABLES, create_take, export_revision, make_bins,
                                 nearest_frame, sha256, validate, write_csv)
from field_observer.media import probe_video

MEDIA = {"decoder": "synthetic test metadata", "width": 32, "height": 32,
         "stream_metadata": {}, "first_pts": 1000, "first_pts_seconds": 1.0,
         "last_frame_time_s": .3, "decoded_duration_s": .4,
         "reported_stream_duration_s": .4, "timestamp_issues": [],
         "frames": [{"frame_index": i, "frame_pts": pts, "time_base": "1/1000", "time_s": seconds}
                    for i, (pts, seconds) in enumerate(((1000, 0), (1050, .05), (1150, .15), (1300, .3)))]}


class EvidenceTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="field-observer-test-")
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.video = self.root / "synthetic fixture.mp4"
        self.video.write_bytes(b"Synthetic bytes; decoder is mocked only in table tests.")
        self.take = self.root / "take"
        with patch("field_observer.core.probe_video", return_value=copy.deepcopy(MEDIA)):
            self.manifest = create_take(self.video, self.take, survey_id="synthetic",
                intersection_id="J_TEST", take_id="TAKE_TEST", start="2026-10-03T08:00:00+08:00",
                collector="test", clock_note="invented test clock", source_kind="synthetic")

    def row(self, filename, **values):
        row = {key: "" for key in TABLES[filename]}
        row.update({key: self.manifest[key] for key in COMMON})
        row.update(values)
        return row

    def save(self, filename, rows):
        write_csv(self.take / "draft" / filename, TABLES[filename], rows)

    def coverage(self, kind="vehicle_discharge", location="N_STOP", end=.4, visibility="complete"):
        return self.row("coverage.csv", event_type=kind, location_id=location,
                        start_s=0, end_s=end, visibility=visibility,
                        review_method="manual_count", reviewer="reviewer")

    def event(self, **changes):
        row = self.row("events.csv", event_id="E1", episode_id="V1", event_type="vehicle_discharge",
                       location_id="N_STOP", time_s=.05, frame_pts=1050, approach_id="N",
                       reviewed_class="tricycle", vehicle_subtype="pedicab",
                       review_status="accepted", review_method="manual_count", reviewer="reviewer")
        row.update(changes)
        return row

    def seed(self):
        self.save("coverage.csv", [self.coverage()])
        self.save("events.csv", [self.event()])

    def test_removed_response_category_is_not_exported_or_reclassified(self):
        self.save("coverage.csv", [self.coverage()])
        self.save("events.csv", [self.event(reviewed_class="emergency_confirmed", vehicle_subtype="")])
        original = (self.take / "draft/events.csv").read_bytes()
        with self.assertRaisesRegex(ValueError, "invalid vehicle/person category"):
            export_revision(self.take, "reviewer", "Historical category requires a scope review")
        self.assertEqual((self.take / "draft/events.csv").read_bytes(), original)
        self.assertFalse(list((self.take / "revisions").glob("revision*")))

    def test_readme_uses_current_tricycle_subtypes(self):
        readme = (Path(__file__).parents[1] / "README.md").read_text(encoding="utf-8").lower()
        self.assertNotIn("tagum_passenger_tricycle", readme)
        self.assertNotIn("tagum passenger tricycle", readme)

    def test_registration_preserves_source_and_refuses_overwrite(self):
        self.assertEqual(sha256(self.video), self.manifest["source_sha256"])
        self.assertEqual(self.manifest["camera_id"], "PHONE_01")
        with self.assertRaisesRegex(ValueError, "already exists"):
            create_take(self.video, self.take, survey_id="x", intersection_id="x", take_id="x",
                        start="2026-10-03T08:00:00+08:00", collector="x", clock_note="x", source_kind="synthetic")

    def test_time_comes_from_pts_and_tampered_source_blocks_export(self):
        self.assertEqual(nearest_frame(self.take, .16)["frame_pts"], 1150)
        self.seed()
        self.video.write_bytes(b"changed")
        with self.assertRaisesRegex(ValueError, "recording changed"):
            export_revision(self.take, "reviewer", "check")
        self.assertEqual(list((self.take / "revisions").iterdir()), [])

    def test_unknown_collection_clock_is_preserved_and_naive_clock_rejected(self):
        options = dict(survey_id="synthetic", intersection_id="J_TEST", take_id="TAKE_2",
                       collector="test", clock_note="unknown clock", source_kind="synthetic")
        with patch("field_observer.core.probe_video", return_value=copy.deepcopy(MEDIA)):
            manifest = create_take(self.video, self.root / "unknown-clock", start=None, **options)
        self.assertIsNone(manifest["collection_start"])
        self.assertEqual(manifest["collection_clock_status"], "unknown")
        signal = {key: "" for key in TABLES["signal_changes.csv"]}
        signal.update({key: manifest[key] for key in COMMON})
        signal.update(signal_event_id="S1", time_s=.05, signal_head_id="HEAD_N", movement_group="N",
                      indication="green", source="observer_log", review_status="accepted",
                      reviewer="test", note="Synthetic paper log without known alignment")
        write_csv(self.root / "unknown-clock" / "draft" / "signal_changes.csv",
                  TABLES["signal_changes.csv"], [signal])
        with self.assertRaisesRegex(ValueError, "resolve the collection clock"):
            validate(self.root / "unknown-clock")
        with self.assertRaisesRegex(ValueError, "UTC offset"):
            create_take(self.video, self.root / "naive-clock", start="2026-10-03T08:00:00", **options)

    def test_count_bins_keep_class_subtype_and_distinguish_unknown_from_zero(self):
        self.save("coverage.csv", [self.coverage(end=.2)])
        self.save("events.csv", [self.event()])
        manifest, tables, _ = validate(self.take)
        rows = make_bins(manifest, tables, 1)
        self.assertTrue(all(row["count"] == "" for row in rows))
        self.assertEqual(sum(row["observed_count"] for row in rows), 1)
        self.seed()
        manifest, tables, _ = validate(self.take)
        rows = make_bins(manifest, tables, 1)
        self.assertEqual(sum(row["count"] for row in rows), 1)
        tricycle = next(row for row in rows if row["vehicle_subtype"] == "pedicab")
        self.assertEqual(tricycle["count"], 1)
        self.assertEqual(next(row["count"] for row in rows if row["reviewed_class"] == "car"), 0)
        self.assertEqual(tricycle["end_s"], .4)  # No extrapolation to one second or 15 minutes.

    def test_count_bins_keep_bao_bao_and_pedicab_apart(self):
        self.save("coverage.csv", [self.coverage()])
        self.save("events.csv", [self.event(), self.event(event_id="E2", episode_id="V2", time_s=.15, frame_pts=1150,
                                                          vehicle_subtype="bao_bao")])
        manifest, tables, _ = validate(self.take)
        counts = {row["vehicle_subtype"]: row["count"] for row in make_bins(manifest, tables, 1) if row["reviewed_class"] == "tricycle"}
        self.assertEqual(counts, {"": 0, "bao_bao": 1, "pedicab": 1})

    def test_retired_or_unknown_tricycle_subtype_is_rejected(self):
        self.save("coverage.csv", [self.coverage()])
        for subtype in ("tagum_passenger_tricycle", "Pedicab"):
            self.save("events.csv", [self.event(vehicle_subtype=subtype)])
            with self.assertRaisesRegex(ValueError, "tricycle subtype must be bao_bao or pedicab"):
                validate(self.take)

    def test_duplicate_episode_or_wrong_frame_is_rejected(self):
        self.seed()
        self.save("events.csv", [self.event(), self.event(event_id="E2")])
        with self.assertRaisesRegex(ValueError, "duplicate accepted"):
            validate(self.take)
        self.save("events.csv", [self.event(time_s=.1)])
        with self.assertRaisesRegex(ValueError, "must match frames"):
            validate(self.take)

    def test_automatic_acceptance_cannot_be_claimed(self):
        self.seed()
        self.save("events.csv", [self.event(review_method="sample_audited_auto")])
        with self.assertRaisesRegex(ValueError, "not implemented"):
            validate(self.take)

    def test_unresolved_events_do_not_produce_verified_zero(self):
        self.seed()
        self.save("events.csv", [self.event(review_status="uncertain")])
        manifest, tables, _ = validate(self.take)
        rows = make_bins(manifest, tables, 1)
        self.assertTrue(all(row["count"] == "" and row["review_state"] == "unresolved" for row in rows))

    def test_bad_coverage_or_wrong_take_fails(self):
        self.seed()
        self.save("coverage.csv", [self.coverage(), self.coverage()])
        with self.assertRaisesRegex(ValueError, "overlapping coverage"):
            validate(self.take)
        self.save("coverage.csv", [self.coverage()])
        self.save("events.csv", [self.event(take_id="ANOTHER_TAKE")])
        with self.assertRaisesRegex(ValueError, "does not match"):
            validate(self.take)

    def test_pedestrian_stages_cannot_run_backwards(self):
        kinds = ("pedestrian_arrival", "pedestrian_start")
        self.save("coverage.csv", [self.coverage(kind, "CROSS_N") for kind in kinds])
        base = dict(location_id="CROSS_N", crossing_id="CROSS_N", approach_id="", reviewed_class="person", vehicle_subtype="")
        self.save("events.csv", [self.event(**base, event_type=kinds[0], time_s=.15, frame_pts=1150),
                                 self.event(**base, event_id="E2", event_type=kinds[1])])
        with self.assertRaisesRegex(ValueError, "out of time order"):
            validate(self.take)

    def test_unknown_queue_is_blank_not_zero(self):
        row = self.row("queue_samples.csv", sample_id="Q1", time_s=.05, frame_pts=1050,
                       approach_id="N", queue_count="0", visibility="unknown",
                       review_status="accepted", reviewer="reviewer")
        self.save("queue_samples.csv", [row])
        with self.assertRaisesRegex(ValueError, "blank, not zero"):
            validate(self.take)
        row["queue_count"] = ""
        self.save("queue_samples.csv", [row])
        validate(self.take)

    def test_revisions_preserve_previous_records_and_detect_changes(self):
        self.seed()
        first = export_revision(self.take, "reviewer", "Initial manual count", 900)
        before = (first / "events.csv").read_bytes()
        self.save("events.csv", [self.event(reviewed_class="motorcycle", vehicle_subtype="",
                                            review_status="corrected", note="synthetic correction")])
        second = export_revision(self.take, "reviewer", "Correct classification", 900)
        self.assertEqual(before, (first / "events.csv").read_bytes())
        self.assertEqual(json.loads((second / "review_record.json").read_text())["previous_revision"], first.name)
        report = json.loads((second / "quality_report.json").read_text())
        self.assertFalse(report["field_accuracy_verified"])
        self.assertEqual(report["publication_status"], "provisional")
        (second / "events.csv").write_text("changed")
        with self.assertRaisesRegex(ValueError, "Previous revision changed"):
            export_revision(self.take, "reviewer", "Should fail")

    def test_cli_check_and_actionable_failure(self):
        self.seed()
        tool = Path(__file__).resolve().parents[1]
        result = subprocess.run([sys.executable, "-m", "field_observer", "check", str(self.take)],
                                cwd=tool, capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout)["accepted_event_count"], 1)
        result = subprocess.run([sys.executable, "-m", "field_observer", "frame", str(self.take), "--time", "99"],
                                cwd=tool, capture_output=True, text=True)
        self.assertEqual(result.returncode, 2)
        self.assertIn("outside recorded", result.stderr)


@unittest.skipUnless(importlib.util.find_spec("av"), "PyAV is installed only in the tool environment")
class MediaTests(unittest.TestCase):
    def test_invalid_recording_is_rejected_without_a_take(self):
        with tempfile.TemporaryDirectory(prefix="field-observer-invalid-") as temporary:
            source = Path(temporary) / "invalid.mp4"
            source.write_bytes(b"This is not a recording.")
            destination = Path(temporary) / "take"
            with self.assertRaisesRegex(ValueError, "Cannot decode"):
                create_take(source, destination, survey_id="TEST", intersection_id="TEST", take_id="TEST",
                            start=None, collector="test", clock_note="unknown", source_kind="synthetic")
            self.assertFalse(destination.exists())

    def test_real_decoder_uses_variable_pts_and_nonzero_origin(self):
        import av
        with tempfile.TemporaryDirectory(prefix="field-observer-media-") as temporary:
            path = Path(temporary) / "synthetic-vfr.mkv"
            with av.open(str(path), "w") as container:
                stream = container.add_stream("ffv1", rate=25)
                stream.width, stream.height, stream.pix_fmt = 32, 32, "gray"
                stream.time_base = Fraction(1, 1000)
                stream.codec_context.time_base = Fraction(1, 1000)
                for pts in (1000, 1040, 1120, 1280):
                    frame = av.VideoFrame(32, 32, "gray")
                    frame.planes[0].update(bytes(frame.planes[0].buffer_size))
                    frame.pts, frame.time_base = pts, Fraction(1, 1000)
                    for packet in stream.encode(frame):
                        container.mux(packet)
                for packet in stream.encode():
                    container.mux(packet)
            before = sha256(path)
            result = probe_video(path)
            self.assertEqual([row["time_s"] for row in result["frames"]], [0, .04, .12, .28])
            self.assertEqual(result["first_pts_seconds"], 1)
            self.assertEqual(result["timestamp_issues"], [])
            self.assertEqual(sha256(path), before)
            # Exercise the real command chain, not just the mocked table layer.
            take = Path(temporary) / "registered"
            tool = Path(__file__).resolve().parents[1]
            registered = subprocess.run([sys.executable, "-m", "field_observer", "register", str(path), str(take),
                "--survey-id", "SYNTHETIC", "--intersection-id", "J_TEST", "--take-id", "TAKE_TEST",
                "--source-kind", "synthetic", "--collector", "test", "--clock-note", "unknown synthetic clock"],
                cwd=tool, capture_output=True, text=True)
            self.assertEqual(registered.returncode, 0, registered.stderr)
            manifest = json.loads(registered.stdout)
            context = {key: manifest[key] for key in COMMON}
            coverage = {key: "" for key in TABLES["coverage.csv"]}
            coverage.update(context, event_type="vehicle_discharge", location_id="N_STOP", start_s=0,
                            end_s=manifest["media"]["decoded_duration_s"], visibility="complete",
                            review_method="manual_count", reviewer="test")
            event = {key: "" for key in TABLES["events.csv"]}
            event.update(context, event_id="E1", episode_id="V1", event_type="vehicle_discharge",
                         location_id="N_STOP", time_s=.04, frame_pts=1040, approach_id="N",
                         reviewed_class="tricycle", vehicle_subtype="pedicab",
                         review_status="accepted", review_method="manual_count", reviewer="test",
                         note="Invented event on a synthetic blank timing fixture; no traffic detection claim.")
            write_csv(take / "draft" / "coverage.csv", TABLES["coverage.csv"], [coverage])
            write_csv(take / "draft" / "events.csv", TABLES["events.csv"], [event])
            exported = subprocess.run([sys.executable, "-m", "field_observer", "export", str(take),
                "--reviewer", "test", "--note", "Synthetic CLI smoke"], cwd=tool, capture_output=True, text=True)
            self.assertEqual(exported.returncode, 0, exported.stderr)
            revision = Path(json.loads(exported.stdout)["revision_path"])
            with (revision / "reviewed_bins.csv").open(newline="", encoding="utf-8") as stream:
                rows = list(csv.DictReader(stream))
            self.assertEqual(sum(int(row["count"]) for row in rows), 1)
            self.assertEqual(manifest["source_kind"], "synthetic")
            self.assertEqual(sha256(path), before)


if __name__ == "__main__":
    unittest.main()
