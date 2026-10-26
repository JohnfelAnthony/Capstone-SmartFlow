"""Synthetic mechanics checks; these do not measure roadside detector accuracy."""

import csv
import tempfile
import unittest
from fractions import Fraction
from pathlib import Path

from field_observer.analysis import analyze, use_proposals
from field_observer.core import (COMMON, TABLES, create_take, export_revision, load_tables,
                                 read_json, sha256, validate, write_csv, write_json)
from field_observer.lines import LineCounter, validate_config
from field_observer.setup import create_setup


def line(event="vehicle_arrival", **values):
    return {"id": "N_IN", "a": [5, 24], "b": [55, 24], "event_type": event,
            "location_id": "N_IN", "approach_id": "N", "crossing_id": "C_N",
            "direction": "negative_to_positive", **values}


def config(**values):
    return {"schema_version": 1, "take_id": "T1", "source_sha256": "test",
            "coordinate_space": "display_pixels", "rotation_clockwise": 0,
            "width": 64, "height": 48, "deadband_px": 1, "max_gap_s": .5,
            "lines": [line()], **values}


def track(y, x=20, identity="V1", category="car"):
    return {"track_id": identity, "detected_class_id": 3 if category == "car" else 1,
            "detected_class": category, "confidence": .8, "x1": x - 4, "y1": y - 8, "x2": x + 4, "y2": y}


class CrossingTests(unittest.TestCase):
    def test_deadband_and_recrossing_do_not_duplicate(self):
        counter = LineCounter(config())
        events = [counter.update(track(y), i * .04) for i, y in enumerate((20, 23.5, 24.5, 26, 20, 26))]
        self.assertEqual([len(rows) for rows in events], [0, 0, 0, 1, 0, 0])

    def test_finite_segment_gap_direction_and_families(self):
        for x, interval in ((60, .1), (20, .6)):
            counter = LineCounter(config())
            counter.update(track(20, x=x), 0)
            self.assertEqual(counter.update(track(28, x=x), interval), [])
        counter = LineCounter(config())
        counter.update(track(28), 0)
        self.assertEqual(counter.update(track(20), .1), [])
        counter = LineCounter(config())
        counter.update(track(20, category="person"), 0)
        self.assertEqual(counter.update(track(28, category="person"), .1), [])
        counter = LineCounter(config(lines=[line(event="pedestrian_start")]))
        counter.update(track(20, category="person"), 0)
        self.assertEqual(len(counter.update(track(28, category="person"), .1)), 1)

    def test_pending_border_does_not_bridge_long_unobserved_crossing(self):
        counter = LineCounter(config())
        counter.update(track(20), 0)
        counter.update(track(24), .4)
        self.assertEqual(counter.update(track(28), .6), [])

    def test_config_refuses_wrong_source_invalid_geometry_and_unsupported_turns(self):
        manifest = {"source_sha256": "test", "take_id": "T1", "media": {"width": 64, "height": 48}}
        validate_config(config(), manifest)
        for update in ({"source_sha256": "wrong"}, {"width": 48}, {"max_gap_s": float("nan")},
                       {"lines": [line(a=[-1, 4])]}, {"lines": [line(event="vehicle_movement")]},
                       {"lines": [line(), line()]}, {"lines": [line(b=[6, 24])]}):
            with self.assertRaises(ValueError):
                validate_config(config(**update), manifest)


class SyntheticDetector:
    provenance = {"model": "synthetic scripted boxes", "field_accuracy_verified": False}

    def __init__(self, *_):
        self.index = 0

    def update(self, image, seconds):
        y = (12, 20, 28, 32)[self.index]
        self.index += 1
        return [track(y)]


class PipelineTests(unittest.TestCase):
    def setUp(self):
        import av
        self.temporary = tempfile.TemporaryDirectory(prefix="field-analysis-")
        self.root = Path(self.temporary.name)
        self.video = self.root / "synthetic.mkv"
        with av.open(str(self.video), "w") as container:
            stream = container.add_stream("ffv1", rate=25)
            stream.width, stream.height, stream.pix_fmt = 64, 48, "gray"
            stream.time_base = stream.codec_context.time_base = Fraction(1, 1000)
            for pts in (1000, 1040, 1120, 1280):
                frame = av.VideoFrame(64, 48, "gray")
                frame.planes[0].update(bytes(frame.planes[0].buffer_size))
                frame.pts, frame.time_base = pts, Fraction(1, 1000)
                for packet in stream.encode(frame):
                    container.mux(packet)
            for packet in stream.encode():
                container.mux(packet)
        self.take = self.root / "take"
        self.manifest = create_take(self.video, self.take, survey_id="SYNTHETIC", intersection_id="J_TEST",
                                    take_id="T1", start=None, collector="test", clock_note="synthetic", source_kind="synthetic")
        self.lines = self.root / "lines.json"
        write_json(self.lines, config(source_sha256=self.manifest["source_sha256"]))
        self.run = self.root / "analysis"

    def tearDown(self):
        self.temporary.cleanup()

    def analyze(self, factory=SyntheticDetector):
        return analyze(self.take, self.lines, self.run, Path("unused"), detector_factory=factory)

    def test_real_pts_pipeline_separates_raw_proposals_from_manual_tricycle_review(self):
        result = self.analyze()
        self.assertEqual(result["status"], "complete")
        self.assertEqual(result["proposal_count"], 1)
        self.assertEqual(result["source_kind"], "synthetic")
        self.assertFalse(load_tables(self.take)["events.csv"])
        use_proposals(self.take, self.run)
        manifest, tables, report = validate(self.take)
        self.assertEqual(report["accepted_event_count"], 0)
        event = tables["events.csv"][0]
        self.assertEqual(event["frame_pts"], "1120")
        self.assertEqual(float(event["time_s"]), .12)
        self.assertEqual(event["reviewed_class"], "unknown")
        with self.assertRaisesRegex(ValueError, "not empty"):
            use_proposals(self.take, self.run)
        event.update(review_status="accepted", reviewer="tester")
        write_csv(self.take / "draft/events.csv", TABLES["events.csv"], [event])
        with self.assertRaisesRegex(ValueError, "automatic/sample"):
            validate(self.take)
        event.update(reviewed_class="tricycle", vehicle_subtype="pedicab",
                     review_status="corrected", review_method="individual_review", note="Synthetic manual reclassification")
        write_csv(self.take / "draft/events.csv", TABLES["events.csv"], [event])
        coverage = {key: "" for key in TABLES["coverage.csv"]}
        coverage.update({key: manifest[key] for key in COMMON}, event_type="vehicle_arrival", location_id="N_IN",
                        start_s=0, end_s=manifest["media"]["decoded_duration_s"], visibility="complete",
                        review_method="manual_count", reviewer="tester")
        write_csv(self.take / "draft/coverage.csv", TABLES["coverage.csv"], [coverage])
        revision = export_revision(self.take, "tester", "Synthetic reviewed test")
        self.assertEqual(read_json(revision / "quality_report.json")["accepted_event_count"], 1)
        with (self.run / "proposals.csv").open(newline="", encoding="utf-8") as stream:
            raw = list(csv.DictReader(stream))[0]
        self.assertEqual(raw["detected_class"], "car")
        self.assertEqual(raw["review_status"], "proposed")
        self.assertEqual(sha256(self.video), self.manifest["source_sha256"])

    def test_failed_analysis_cannot_seed_draft_and_existing_run_is_preserved(self):
        class FailingDetector(SyntheticDetector):
            def update(self, *_):
                raise RuntimeError("injected inference failure")
        with self.assertRaisesRegex(RuntimeError, "injected"):
            self.analyze(FailingDetector)
        self.assertEqual(read_json(self.run / "run.json")["status"], "failed")
        with self.assertRaisesRegex(ValueError, "complete analysis"):
            use_proposals(self.take, self.run)
        with self.assertRaisesRegex(ValueError, "already exists"):
            self.analyze()

    def test_modified_raw_artifact_and_wrong_take_refused(self):
        self.analyze()
        other = self.root / "other-take"
        create_take(self.video, other, survey_id="SYNTHETIC", intersection_id="J_TEST", take_id="OTHER",
                    start=None, collector="test", clock_note="synthetic", source_kind="synthetic")
        with self.assertRaisesRegex(ValueError, "different take"):
            use_proposals(other, self.run)
        with (self.run / "tracks.csv").open("a") as stream:
            stream.write("tampered")
        with self.assertRaisesRegex(ValueError, "artifact changed"):
            use_proposals(self.take, self.run)

    def test_index_changed_during_inference_leaves_failed_run(self):
        take = self.take
        class MutatingDetector(SyntheticDetector):
            def update(self, *args):
                with (take / "frames.csv").open("a") as stream:
                    stream.write("changed\n")
                return super().update(*args)
        with self.assertRaisesRegex(ValueError, "Frame index changed"):
            self.analyze(MutatingDetector)
        self.assertEqual(read_json(self.run / "run.json")["status"], "failed")

    def test_setup_rotation_coordinates_and_no_overwrite(self):
        destination = self.root / "setup.html"
        create_setup(self.take, destination, .1, 90)
        html = destination.read_text(encoding="utf-8")
        self.assertIn('"width": 48, "height": 64', html)
        self.assertIn('"reference_frame_pts": 1120', html)
        self.assertIn("data:image/png;base64,", html)
        self.assertNotIn("__CONFIG__", html)
        with self.assertRaisesRegex(ValueError, "already exists"):
            create_setup(self.take, destination, 0, 0)


class TrackerApiTests(unittest.TestCase):
    def test_detector_adapter_preserves_classes_and_separates_person_vehicle_ids(self):
        import numpy as np
        import supervision as sv
        from trackers import ByteTrackTracker
        from field_observer.detector import TrafficDetector
        class Predictions:
            def predict(self, image, **kwargs):
                return sv.Detections(xyxy=np.array([[10., 10., 30., 30.], [40., 10., 60., 30.], [70., 10., 90., 30.]]),
                                     confidence=np.array([.9, .85, .8]), class_id=np.array([1, 8, 4]))
        detector = TrafficDetector.__new__(TrafficDetector)
        detector.np, detector.model, detector.confidence = np, Predictions(), .35
        detector.trackers = {key: ByteTrackTracker(track_activation_threshold=.35, high_conf_det_threshold=.35,
                                                   minimum_consecutive_frames=1) for key in ("P", "V")}
        rows = detector.update(None, 0.)
        rows = detector.update(None, .04)
        self.assertEqual([row["detected_class"] for row in rows], ["person", "truck", "motorcycle"])
        self.assertEqual([row["detected_class_id"] for row in rows], [1, 8, 4])
        self.assertTrue(rows[0]["track_id"].startswith("P"))
        self.assertTrue(all(row["track_id"].startswith("V") for row in rows[1:]))
        self.assertEqual(len({row["track_id"] for row in rows}), 3)

    def test_installed_bytetrack_preserves_categories_with_actual_timestamps(self):
        import numpy as np
        import supervision as sv
        from trackers import ByteTrackTracker
        tracker = ByteTrackTracker(track_activation_threshold=.35, high_conf_det_threshold=.35,
                                   minimum_consecutive_frames=2)
        ids = []
        for i, timestamp in enumerate((0., .04, .12, .28)):
            detection = sv.Detections(xyxy=np.array([[10., 10.+i, 30., 30.+i]]),
                                      confidence=np.array([.9]), class_id=np.array([8]))
            output = tracker.update(detection, timestamp=timestamp)
            self.assertEqual(output.class_id.tolist(), [8])
            ids.append(int(output.tracker_id[0]))
        self.assertGreaterEqual(ids[-1], 0)
        self.assertEqual(ids[-1], ids[-2])


if __name__ == "__main__":
    unittest.main()
