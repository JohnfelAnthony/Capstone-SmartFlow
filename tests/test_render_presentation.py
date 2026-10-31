"""Synthetic presentation contracts; these checks do not validate field traffic."""
import copy
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from services.render_frame_service import (
    MAX_RENDER_STATE_BYTES,
    RenderFrameBudgetError,
    build_render_frame,
    encode_render_frame,
)
from simulation.timeline_engine import TimelinePlaybackEngine
from simulation.traffic_engine import Pedestrian, TrafficEngine


def population_state(vehicles=300, pedestrians=128):
    return {
        "status": "running", "time": 12.5, "step_length": .1,
        "scenario": {"intersection_id": "tagum_network"},
        "vehicles": [{"id": f"vehicle-{i:04d}", "lane_id": f"lane-{i % 4}", "x": i,
                      "y": 0, "speed": 2, "wait_time": i / 10, "visual_type": "tricycle",
                      "length": 3, "width": 1.4} for i in range(vehicles)],
        "pedestrians": [{"id": f"person-{i:04d}", "lane_id": f"J{i % 4}", "x": i,
                         "y": 6, "wait_time": i / 2, "stopped": True} for i in range(pedestrians)],
        "vehicle_count": vehicles, "pedestrian_count": pedestrians,
        "metrics": {"lanes": {f"lane-{i}": {"vehicles": vehicles // 4, "queue": i + 10,
                     "mean_speed_mps": 2, "density_vehicles_per_km": 25, "exits": 3,
                     "closed": False, "speed_factor": 1} for i in range(4)},
                    "junctions": {"J0": {"queue": 42, "vehicle_passages": 12, "waiting_pedestrians": 32}}},
        "experiment": {"last_policy_decision": {"time": 11, "junction_id": "J0", "action": "SERVE_EAST",
                                                  "applied": True, "reason": "queued_safely"},
                       "last_safety_override": {"time": 9, "junction_id": "J0", "reason": "pedestrian_wait"}},
    }


class RenderPresentationTests(unittest.TestCase):
    def test_visual_junction_labels_match_existing_options_without_geometry_changes(self):
        from services.native_scenario_service import configuration_options
        from services.visual_network_service import load_client_visual_network
        from simulation.road_network import load_network
        network = load_network()
        baseline = copy.deepcopy(network.visual())
        labels = {junction["id"]: junction["label"] for junction in configuration_options()["junctions"]}
        # Labeling reuses the loaded network; it does not initialize an engine.
        with patch("services.visual_network_service.load_registered_network", return_value=network), \
                patch("services.native_scenario_service.TrafficEngine", side_effect=AssertionError("engine should not be constructed")):
            visual = load_client_visual_network(network.id)
        self.assertEqual(visual["network_id"], network.id)
        for junction in visual["junctions"]:
            self.assertEqual(junction.pop("label"), labels[junction["id"]])
        self.assertEqual(visual, baseline)
        self.assertEqual(network.visual(), baseline)

    def test_full_population_at_below_and_above_uniform_limits(self):
        for vehicle_count, pedestrian_count in ((0, 0), (90, 40), (300, 128), (400, 160)):
            for flow in ({}, {"state": "LIVE_RUNNING"}, {"state": "PLAYBACK_RUNNING"}):
                with self.subTest(vehicles=vehicle_count, pedestrians=pedestrian_count, flow=flow):
                    state = population_state(vehicle_count, pedestrian_count)
                    state["flow"] = flow
                    frame = build_render_frame(state, render_ts=0)
                    self.assertEqual(len(frame["vehicles"]), min(vehicle_count, 300))
                    self.assertEqual(len(frame["pedestrians"]), min(pedestrian_count, 128))
                    self.assertEqual(frame["vehicle_count"], vehicle_count)
                    self.assertEqual(frame["pedestrian_count"], pedestrian_count)
                    coverage = frame["render_coverage"]
                    limited = vehicle_count > 300 or pedestrian_count > 128
                    self.assertEqual(coverage["limited"], limited)
                    self.assertEqual(coverage["reason"], "entity_limit" if limited else None)
                    self.assertEqual(coverage["vehicles"]["shown"], min(vehicle_count, 300))
                    self.assertEqual(coverage["pedestrians"]["total"], pedestrian_count)
                    self.assertEqual(frame["lane_metrics"], state["metrics"]["lanes"])
                    self.assertLessEqual(len(encode_render_frame(frame).encode("utf-8")), MAX_RENDER_STATE_BYTES)

    def test_allocation_is_distributed_stable_and_independent_of_array_order(self):
        state = population_state(400, 160)
        frame = build_render_frame(state, render_ts=0)
        reverse = copy.deepcopy(state)
        reverse["vehicles"].reverse()
        reverse["pedestrians"].reverse()
        self.assertEqual(frame, build_render_frame(reverse, render_ts=0))
        for lane in range(4):
            self.assertEqual(sum(entity["lane_id"] == f"lane-{lane}" for entity in frame["vehicles"]), 75)
            self.assertEqual(sum(entity["lane_id"] == f"J{lane}" for entity in frame["pedestrians"]), 32)

    def test_byte_budget_trims_entities_only_and_measures_encoded_utf8(self):
        state = population_state()
        # Multibyte metadata distinguishes UTF-8 bytes from string length.
        state["junction_controls"] = {"J0": {"controller": "測" * 70000, "phase": "NORTH_GREEN"}}
        frame = build_render_frame(state, render_ts=0, sequence=7)
        encoded = encode_render_frame(frame)
        self.assertGreater(len(encoded.encode("utf-8")), len(encoded))
        self.assertLessEqual(len(encoded.encode("utf-8")), MAX_RENDER_STATE_BYTES)
        self.assertEqual(frame["render_coverage"]["reason"], "byte_limit")
        self.assertLess(len(frame["vehicles"]), 300)
        self.assertLess(len(frame["pedestrians"]), 128)
        self.assertGreater(len(frame["vehicles"]), 0)
        self.assertGreater(len(frame["pedestrians"]), 0)
        self.assertEqual(frame["junction_controls"], state["junction_controls"])
        self.assertEqual(frame["lane_metrics"], state["metrics"]["lanes"])
        self.assertEqual(frame["junction_metrics"], state["metrics"]["junctions"])
        self.assertEqual(frame["controller_events"], state["experiment"])
        self.assertEqual(frame, build_render_frame(state, render_ts=0, sequence=7))

    def test_metadata_overflow_is_an_error_not_silent_telemetry_loss(self):
        state = population_state()
        state["junction_controls"] = {"J0": {"controller": "測" * 90000}}
        with self.assertRaisesRegex(RenderFrameBudgetError, "metadata exceeds 262144"):
            build_render_frame(state, render_ts=0)

    def test_wait_metrics_events_are_snapshot_values_without_source_mutation(self):
        state = population_state(4, 2)
        before = copy.deepcopy(state)
        frame = build_render_frame(state, render_ts=0)
        self.assertEqual(state, before)
        self.assertEqual(frame["vehicles"][1]["wait_time"], .1)
        self.assertEqual(frame["pedestrians"][1]["wait_time"], .5)
        self.assertEqual(frame["controller_events"]["last_policy_decision"]["reason"], "queued_safely")
        frame["lane_metrics"]["lane-0"]["queue"] = -99
        self.assertEqual(state, before)

    def test_missing_historical_telemetry_remains_absent(self):
        state = {"status": "running", "vehicles": [{"id": "old"}], "pedestrians": [{"id": "old-person"}],
                 "junction_controls": {"J0": {"mode": "signalized", "controller": "fixed-time", "phase": "NORTH_GREEN"}}}
        frame = build_render_frame(state, render_ts=0)
        for key in ("lane_metrics", "junction_metrics", "controller_events"):
            self.assertNotIn(key, frame)
        self.assertNotIn("wait_time", frame["vehicles"][0])
        self.assertNotIn("wait_time", frame["pedestrians"][0])
        self.assertNotIn("pedestrian_paths", frame["visual"])
        self.assertNotIn("timing_kind", frame["junction_controls"]["J0"])

    def test_timing_semantics_and_queued_request_preserve_actual_signal(self):
        engine = TrafficEngine(seed=17)
        engine.start(30)
        junction = engine.controlled_junction
        signal = engine.signals[junction]
        fixed = engine.junction_controls()[junction]
        self.assertEqual(fixed["timing_kind"], "fixed_stage")
        self.assertEqual(fixed["remaining_seconds"], signal.remaining)
        self.assertFalse(fixed["external_control"])
        engine.configure_rl_control(controller_provenance="synthetic-policy")
        before_phase = signal.phase
        request = engine.apply_rl_action("SERVE_EAST")
        control = engine.junction_controls()[junction]
        self.assertEqual(request, {"applied": True, "reason": "queued_safely"})
        self.assertEqual(control["timing_kind"], "minimum_hold")
        self.assertEqual(control["pending_service"], "east")
        self.assertEqual(control["phase"], before_phase)
        self.assertTrue(control["external_control"])
        signal.elapsed = signal.minimum_green + 1
        self.assertEqual(engine.junction_controls()[junction]["remaining_seconds"], 0)
        for stage in ("yellow", "red"):
            signal.stage = stage
            self.assertEqual(engine.junction_controls()[junction]["timing_kind"], "clearance")

    def test_all_way_stop_has_unlit_signals_and_no_countdown(self):
        engine = TrafficEngine(seed=17)
        junction = engine.controlled_junction
        engine.configure(signal_plans={junction: {"mode": "all_way_stop"}})
        engine.start(30)
        frame = build_render_frame(engine.to_dict(), render_ts=0)
        control = frame["junction_controls"][junction]
        self.assertEqual(control["controller"], "all-way-stop")
        self.assertEqual(control["timing_kind"], "none")
        self.assertIsNone(control["remaining_seconds"])
        for lane in engine.network.incoming[junction]:
            self.assertEqual(frame["traffic_lights"][lane]["state"], "o")

    def test_illustrative_paths_match_actual_position_derivation_and_length(self):
        engine = TrafficEngine(seed=17)
        engine.configure(crossing_length=27)
        engine.start(30)
        junction = engine.controlled_junction
        pedestrian = Pedestrian("synthetic-person", junction, progress=7, crossing=True)
        engine.pedestrians[pedestrian.id] = pedestrian
        before = copy.deepcopy(vars(pedestrian))
        state = engine.to_dict()
        path = next(path for path in state["visual"]["pedestrian_paths"] if path["junction_id"] == junction)
        record = state["pedestrians"][0]
        self.assertEqual(path["provenance"], "illustrative")
        self.assertEqual(path["shape"][1]["x"]-path["shape"][0]["x"], 27)
        self.assertEqual(record["x"], path["shape"][0]["x"] + 7)
        self.assertEqual(record["y"], path["shape"][0]["y"])
        self.assertEqual(vars(pedestrian), before)

    def test_new_and_old_native_recordings_preserve_optional_snapshot_contracts(self):
        engine = TrafficEngine(seed=17)
        engine.start(1)
        frames = [engine.to_dict()]
        while engine.status == "running":
            engine.step()
            frames.append(engine.to_dict())
        with tempfile.TemporaryDirectory(prefix="presentation-replay-") as directory:
            root = Path(directory)
            for old in (False, True):
                snapshots = copy.deepcopy(frames)
                if old:
                    for snapshot in snapshots:
                        snapshot["visual"].pop("pedestrian_paths", None)
                        snapshot["metrics"].pop("lanes", None)
                        snapshot["metrics"].pop("junctions", None)
                        snapshot["experiment"].pop("last_policy_decision", None)
                        snapshot["experiment"].pop("last_safety_override", None)
                        for control in snapshot["junction_controls"].values():
                            for key in ("stage", "elapsed_seconds", "remaining_seconds", "timing_kind", "pending_service", "external_control"):
                                control.pop(key, None)
                timeline = root / ("old.jsonl" if old else "new.jsonl")
                timeline.write_text("".join(json.dumps(frame) + "\n" for frame in snapshots), encoding="utf-8")
                timeline.with_suffix(".manifest.json").write_text(json.dumps({
                    "experiment": engine.experiment_metadata(), "timeline": {"frame_count": len(frames), "actual_duration_seconds": 1}}), encoding="utf-8")
                playback = TimelinePlaybackEngine(1, str(timeline))
                self.assertNotEqual(playback.status, "error", playback.last_error)
                playback.start(1)
                playback.seek(7)
                replay = build_render_frame(playback.get_state(), render_ts=0)
                expected = build_render_frame(snapshots[7], render_ts=0)
                for key in ("vehicles", "pedestrians", "visual", "junction_controls", "traffic_lights", "render_coverage"):
                    self.assertEqual(replay[key], expected[key])
                for key in ("lane_metrics", "junction_metrics", "controller_events"):
                    self.assertEqual(replay.get(key), expected.get(key))
                    self.assertEqual(key in replay, not old)
                playback.seek(2)
                self.assertEqual(build_render_frame(playback.get_state(), render_ts=0)["time"], .2)

    def test_paired_frontend_fixture_uses_exact_python_serializer(self):
        fixture = Path(__file__).with_name("fixtures") / "render-presentation.json"
        for case in json.loads(fixture.read_text(encoding="utf-8")):
            with self.subTest(case=case["name"]):
                self.assertEqual(build_render_frame(case["state"], render_ts=0), case["expected"])

    def test_websocket_uses_guarded_encoding_and_surfaces_metadata_overflow(self):
        import os
        os.environ.setdefault("SMARTFLOW_SECRET_KEY", "presentation-tests-only")
        os.environ.setdefault("SMARTFLOW_BOOTSTRAP_ADMIN_PASSWORD", "PresentationAdmin42!")
        from fastapi.testclient import TestClient
        import config
        from backend.main import app
        from backend.schemas import SimulationStateResponse
        from backend.simulation_runtime import simulation_runtime
        with tempfile.TemporaryDirectory(prefix="presentation-stream-") as directory, patch.object(config, "DB_PATH", str(Path(directory) / "test.db")):
            with TestClient(app) as client:
                response = client.post("/api/auth/login", json={"username": "admin", "password": os.environ["SMARTFLOW_BOOTSTRAP_ADMIN_PASSWORD"]})
                self.assertEqual(response.status_code, 200, response.text)
                state = population_state()
                snapshot = SimulationStateResponse(state=state, status="running", duration_seconds=30, seed=17, control_mode="fixed-time")
                with patch.object(simulation_runtime, "get_state", return_value=snapshot):
                    http = client.get("/api/simulation/state")
                    self.assertEqual(http.status_code, 200, http.text)
                    delivered = http.json()["render_frame"]
                    self.assertEqual(delivered, build_render_frame(state, render_ts=delivered["render_ts"]))
                    self.assertIsNone(http.json()["render_frame_error"])
                    self.assertEqual(http.json()["state"], state)
                    with client.websocket_connect("/ws/simulation") as socket:
                        raw = socket.receive_text()
                        frame = json.loads(raw)
                        self.assertLessEqual(len(raw.encode("utf-8")), MAX_RENDER_STATE_BYTES)
                        self.assertEqual(raw, encode_render_frame(frame))
                        self.assertEqual(frame["render_coverage"]["vehicles"]["shown"], 300)
                state["junction_controls"] = {"J0": {"controller": "測" * 90000}}
                snapshot = SimulationStateResponse(state=state, status="running", duration_seconds=30, seed=17, control_mode="fixed-time")
                with patch.object(simulation_runtime, "get_state", return_value=snapshot):
                    http = client.get("/api/simulation/state")
                    self.assertEqual(http.status_code, 200, http.text)
                    self.assertIsNone(http.json()["render_frame"])
                    self.assertIn("metadata exceeds", http.json()["render_frame_error"])
                    self.assertEqual(http.json()["state"], state)
                    with client.websocket_connect("/ws/simulation") as socket:
                        error = socket.receive_json()
                        self.assertEqual(error["type"], "stream_error")
                        self.assertEqual(error["code"], "render_metadata_budget")
                        self.assertEqual(socket.receive()["code"], 1009)

    def test_action_response_adds_exact_server_frame_without_changing_snapshot(self):
        import os
        os.environ.setdefault("SMARTFLOW_SECRET_KEY", "presentation-tests-only")
        from backend.main import simulation_action_response
        from backend.schemas import SimulationStateResponse
        state = population_state(400, 160)
        original = copy.deepcopy(state)
        snapshot = SimulationStateResponse(state=state, status="running", duration_seconds=30, seed=17, control_mode="fixed-time")
        response = simulation_action_response("Synthetic presentation fixture", snapshot)
        frame = response.simulation.render_frame
        self.assertEqual(frame, build_render_frame(state, render_ts=frame["render_ts"]))
        self.assertEqual(response.simulation.state, original)
        self.assertIsNone(snapshot.render_frame)
        self.assertIsNone(response.simulation.render_frame_error)


if __name__ == "__main__":
    unittest.main()
