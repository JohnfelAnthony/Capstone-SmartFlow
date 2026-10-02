"""Shared live ownership and atomic, traceable CSV import through the API."""
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

os.environ.setdefault("SMARTFLOW_SECRET_KEY", "shared-session-tests-only")
os.environ.setdefault("SMARTFLOW_BOOTSTRAP_ADMIN_PASSWORD", "SharedSessionAdmin42!")

from fastapi.testclient import TestClient

import auth
import config
import database
from backend.main import app
from backend.simulation_runtime import simulation_runtime
from services import observed_data_import, render_frame_service
from simulation.road_network import load_network
from simulation.traffic_engine import TrafficEngine


class SharedSessionAndImportTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory(prefix="shared-test-", dir=Path(__file__).resolve().parent)
        self.root = Path(self.directory.name)
        self.db_patch = patch.object(config, "DB_PATH", str(self.root / "test.db"))
        self.import_patch = patch.object(observed_data_import, "IMPORT_DIRECTORY", self.root / "imports")
        self.db_patch.start()
        self.import_patch.start()
        self.a = TestClient(app)
        self.a.__enter__()
        self.b = TestClient(app)
        self.b.__enter__()
        simulation_runtime.reset()
        for username in ("operator_a", "operator_b"):
            database.create_user(username, username, None, auth.hash_password("SharedSessionUser42!"), role_id=1)
        for client, username in ((self.a, "operator_a"), (self.b, "operator_b")):
            response = client.post("/api/auth/login", json={"username": username, "password": "SharedSessionUser42!"})
            self.assertEqual(response.status_code, 200, response.text)
        self.scenario = next(row for row in database.get_scenarios() if row["traffic_density"] == "Single")

    def tearDown(self):
        simulation_runtime.reset()
        self.b.__exit__(None, None, None)
        self.a.__exit__(None, None, None)
        self.import_patch.stop()
        self.db_patch.stop()
        self.assertTrue(self.root.resolve().is_relative_to(Path(__file__).resolve().parent))
        self.directory.cleanup()

    def test_owner_blocks_conflicting_mutations_and_releases_on_reset(self):
        initial_speed = self.a.post("/api/simulation/speed", json={"speed_multiplier": 0.5})
        self.assertEqual(initial_speed.json()["simulation"]["owner_name"], "operator_a")
        self.assertEqual(self.b.post("/api/simulation/speed", json={"speed_multiplier": 2}).status_code, 409)
        configured = self.a.post("/api/simulation/configure", json={"scenario_id": self.scenario["id"]})
        self.assertEqual(configured.status_code, 200, configured.text)
        self.assertEqual(configured.json()["simulation"]["owner_name"], "operator_a")
        for endpoint, payload in (("configure", {"scenario_id": self.scenario["id"]}),
                                  ("start", {}), ("reset", None), ("speed", {"speed_multiplier": 2})):
            response = self.b.post(f"/api/simulation/{endpoint}", json=payload)
            self.assertEqual(response.status_code, 409, (endpoint, response.text))
        with patch.object(simulation_runtime, "_start_background_runner_locked"):
            started = self.a.post("/api/simulation/start", json={})
        self.assertEqual(started.status_code, 200, started.text)
        active_run_id = started.json()["simulation"]["active_run_id"]
        self.assertIsNotNone(active_run_id)
        self.assertEqual(self.b.post("/api/simulation/stop").status_code, 409)
        self.assertEqual(self.b.post("/api/simulation/pause").status_code, 409)
        self.assertEqual(self.a.post("/api/simulation/speed", json={"speed_multiplier": 2}).json()["simulation"]["speed_multiplier"], 2)
        self.assertEqual(self.a.post("/api/simulation/pause").status_code, 200)
        self.assertEqual(self.a.post("/api/simulation/resume").status_code, 200)
        self.assertEqual(self.a.post("/api/simulation/stop").status_code, 200)
        self.assertEqual(database.get_run_by_id(active_run_id)["status"], "stopped")
        released = self.a.post("/api/simulation/reset")
        self.assertIsNone(released.json()["simulation"]["owner_user_id"])
        self.assertEqual(released.json()["simulation"]["speed_multiplier"], 1)
        self.assertEqual(self.b.post("/api/simulation/configure", json={"scenario_id": self.scenario["id"]}).status_code, 200)
        takeover = self.a.post("/api/simulation/reset?force=true")
        self.assertEqual(takeover.status_code, 200, takeover.text)
        self.assertIsNone(takeover.json()["simulation"]["owner_user_id"])

    def test_csv_schemas_validate_rows_and_preserve_source(self):
        network = load_network()
        source, destination = next((a, b) for a in network.boundaries for b in network.boundaries
                                   if a != b and network.route(a, b))
        metadata = {"source_kind": "synthetic", "source_description": "Reproducible sample counts", "collected_on": "2026-01-01"}
        trip_csv = f"time_s,source,destination,vehicle_type\n0.5,{source},{destination},bus\n"
        imported = self.a.post("/api/scenarios/observations/import", json={"kind": "trips", "csv_text": trip_csv, **metadata})
        self.assertEqual(imported.status_code, 200, imported.text)
        config = imported.json()["engine_config"]
        self.assertEqual(config["trips"][0]["vehicle_type"], "bus")
        source_path = Path(imported.json()["summary"]["source_path"])
        self.assertEqual(source_path.read_bytes(), trip_csv.encode("utf-8"))
        self.assertEqual(source_path.read_text(encoding="utf-8"), trip_csv)
        bad = self.a.post("/api/scenarios/observations/import", json={"kind": "trips",
            "csv_text": f"time_s,source,destination,vehicle_type\n0.5,{source},invalid,bus\n", **metadata})
        self.assertEqual(bad.status_code, 422, bad.text)
        self.assertIn("Row 2", bad.json()["detail"])
        self.assertEqual(len(list((self.root / "imports").glob("*.csv"))), 1)
        count_csv = f"start_s,end_s,source,destination,count\n0,10,{source},{destination},3\n"
        counts = self.a.post("/api/scenarios/observations/import", json={"kind": "od_counts", "csv_text": count_csv, **metadata,
            "engine_config": config})
        self.assertEqual(counts.status_code, 200, counts.text)
        count_config = counts.json()["engine_config"]
        self.assertEqual([trip["time"] for trip in count_config["trips"]], [1.666667, 5.0, 8.333333])
        self.assertIn("evenly", counts.json()["summary"]["conversion"])
        route = network.route(source, destination)
        turning_pair = next(((a, b) for a, b in zip(route, route[1:])
                             if network.lanes[a].target in network.intersections), None)
        self.assertIsNotNone(turning_pair)
        from_lane, to_lane = turning_pair
        junction = network.lanes[from_lane].target
        turn_header = "start_s,end_s,source,destination,junction,from_lane,to_lane,count\n"
        turn_row = f"0,10,{source},{destination},{junction},{from_lane},{to_lane},2\n"
        turns = self.a.post("/api/scenarios/observations/import", json={"kind": "turn_counts",
            "csv_text": turn_header + turn_row, **metadata, "engine_config": count_config})
        self.assertEqual(turns.status_code, 200, turns.text)
        self.assertEqual(len(turns.json()["engine_config"]["trips"]), 2)
        self.assertIn("routing may later change", turns.json()["summary"]["conversion"])
        invalid_turn = self.a.post("/api/scenarios/observations/import", json={"kind": "turn_counts",
            "csv_text": turn_header + turn_row.replace(from_lane, "invalid-lane"), **metadata})
        self.assertEqual(invalid_turn.status_code, 422)
        self.assertIn("Row 2", invalid_turn.json()["detail"])
        ped_csv = f"start_s,end_s,junction,count\n0,10,{network.intersections[0]},2\n"
        pedestrians = self.a.post("/api/scenarios/observations/import", json={"kind": "pedestrian_counts", "csv_text": ped_csv,
            **metadata, "engine_config": count_config})
        self.assertEqual(pedestrians.status_code, 200, pedestrians.text)
        full_config = pedestrians.json()["engine_config"]
        self.assertEqual(len(full_config["pedestrian_trips"]), 2)
        self.assertEqual(len(full_config["trips"]), 3)
        created = self.a.post("/api/scenarios", json={"name": "Imported synthetic counts", "traffic_density": "none",
            "pedestrian_density": "none", "engine_config": full_config})
        self.assertEqual(created.status_code, 200, created.text)
        engine = TrafficEngine(seed=11)
        engine.configure_from_scenario(created.json())
        engine.start(10)
        engine.step(100)
        self.assertEqual(engine.pedestrian_serial, 2)
        self.assertEqual(engine.requested_vehicles, 3)
        self.assertEqual(engine.experiment_metadata()["config"]["demand_source"]["kind"], "synthetic")

    def test_300_arrival_import_can_save_reload_edit_and_restore(self):
        from services import backup_bundle
        network = load_network()
        source, destination = next((a, b) for a in network.boundaries for b in network.boundaries
                                   if a != b and network.route(a, b))
        csv_text = f"start_s,end_s,source,destination,count\n0,600,{source},{destination},300\n"
        imported = self.a.post("/api/scenarios/observations/import", json={
            "kind": "od_counts", "csv_text": csv_text, "source_kind": "synthetic",
            "source_description": "300-arrival persistence regression", "collected_on": "2026-01-01"})
        self.assertEqual(imported.status_code, 200, imported.text)
        engine_config = imported.json()["engine_config"]
        self.assertEqual(len(engine_config["trips"]), 300)
        self.assertGreater(len(json.dumps(engine_config).encode("utf-8")), 16384)
        saved = self.a.post("/api/scenarios", json={"name": "Imported 300 arrivals", "engine_config": engine_config})
        self.assertEqual(saved.status_code, 200, saved.text)
        scenario_id = saved.json()["id"]
        reopened = self.a.get(f"/api/scenarios/{scenario_id}")
        self.assertEqual(reopened.json()["engine_config"], engine_config)
        edited = self.a.put(f"/api/scenarios/{scenario_id}", json={"name": "Renamed 300 arrivals"})
        self.assertEqual(edited.status_code, 200, edited.text)
        self.assertEqual(edited.json()["engine_config"], engine_config)
        configured = self.a.post("/api/simulation/configure", json={"scenario_id": scenario_id, "seed": 11})
        self.assertEqual(configured.status_code, 200, configured.text)
        filename = backup_bundle.create_bundle(1)
        backup_id = next(row["id"] for row in database.list_backups() if row["filename"] == filename)
        stage = backup_bundle.restore_bundle_to_stage(backup_id)
        with patch.object(config, "DB_PATH", str(stage / "smartflow.db")):
            restored = database.get_scenario_by_id(scenario_id)
            restored_config = json.loads(restored["engine_config"])
            self.assertEqual(restored_config["trips"], engine_config["trips"])
            retained_csv = Path(restored_config["demand_source"]["datasets"][0]["source_path"])
            self.assertTrue(retained_csv.is_relative_to(stage))
            self.assertEqual(retained_csv.read_text(encoding="utf-8"), csv_text)

    def test_import_retains_exact_utf8_bytes_for_lf_and_crlf_sources(self):
        import hashlib
        network = load_network()
        source, destination = next((a, b) for a in network.boundaries for b in network.boundaries
                                   if a != b and network.route(a, b))
        for newline in ("\n", "\r\n"):
            with self.subTest(newline=repr(newline)):
                csv_text = newline.join(["time_s,source,destination,vehicle_type", f"1,{source},{destination},car", ""])
                response = self.a.post("/api/scenarios/observations/import", json={
                    "kind": "trips", "csv_text": csv_text, "source_kind": "synthetic",
                    "source_description": "Exact source bytes — synthetic fixture", "collected_on": "2026-01-01"})
                self.assertEqual(response.status_code, 200, response.text)
                summary = response.json()["summary"]
                contents = Path(summary["source_path"]).read_bytes()
                self.assertEqual(contents, csv_text.encode("utf-8"))
                self.assertEqual(hashlib.sha256(contents).hexdigest(), summary["sha256"])

    def test_oversized_import_is_rejected_before_source_retention(self):
        network = load_network()
        source, destination = next((a, b) for a in network.boundaries for b in network.boundaries
                                   if a != b and network.route(a, b))
        csv_text = f"start_s,end_s,source,destination,count\n0,600,{source},{destination},300\n"
        payload = {"kind": "od_counts", "csv_text": csv_text, "source_kind": "synthetic",
                   "source_description": "Bounded import regression", "collected_on": "2026-01-01"}
        existing_scenarios = database.get_scenarios()
        with patch.object(config, "SCENARIO_CONFIG_MAX_BYTES", 16384):
            rejected = self.a.post("/api/scenarios/observations/import", json=payload)
        self.assertEqual(rejected.status_code, 422, rejected.text)
        self.assertIn("16384-byte limit", rejected.json()["detail"])
        self.assertIn("expanded size", rejected.json()["detail"])
        self.assertEqual(list((self.root / "imports").glob("*")), [])
        self.assertEqual(database.get_scenarios(), existing_scenarios)

    def test_zero_count_bins_retain_provenance_and_validate_ids(self):
        network = load_network()
        source, destination = next((a, b) for a in network.boundaries for b in network.boundaries
                                   if a != b and network.route(a, b))
        metadata = {"source_kind": "observed", "source_description": "Zero-count survey bin", "collected_on": "2026-01-01"}
        for kind, csv_text in (
            ("od_counts", f"start_s,end_s,source,destination,count\n0,15,{source},{destination},0\n"),
            ("pedestrian_counts", f"start_s,end_s,junction,count\n0,15,{network.intersections[0]},0\n"),
        ):
            response = self.a.post("/api/scenarios/observations/import", json={
                "kind": kind, "csv_text": csv_text, "engine_config": {"traffic_density": "none"}, **metadata})
            self.assertEqual(response.status_code, 200, response.text)
            self.assertEqual(response.json()["summary"]["arrival_count"], 0)
            self.assertEqual(response.json()["engine_config"]["demand_source"]["kind"], "observed")
            self.assertEqual(Path(response.json()["summary"]["source_path"]).read_text(encoding="utf-8"), csv_text)
        invalid = self.a.post("/api/scenarios/observations/import", json={"kind": "od_counts",
            "csv_text": f"start_s,end_s,source,destination,count\n0,15,invalid,{destination},0\n", **metadata})
        self.assertEqual(invalid.status_code, 422)
        self.assertIn("Row 2", invalid.json()["detail"])

    def test_renderer_count_is_separate_from_visual_cap(self):
        state = {"status": "running", "flow": {"state": "LIVE_RUNNING"}, "scenario": {"intersection_id": "tagum_network"},
                 "vehicles": [{"id": f"v{i}", "x": i, "y": 0, "length": 8, "width": 2.5} for i in range(90)],
                 "pedestrians": [{"id": f"p{i}", "x": i, "y": 0} for i in range(40)],
                 "vehicle_count": 90, "pedestrian_count": 40}
        frame = render_frame_service.build_render_frame(state)
        self.assertEqual((frame["vehicle_count"], len(frame["vehicles"])), (90, 80))
        self.assertEqual((frame["pedestrian_count"], len(frame["pedestrians"])), (40, 32))
        self.assertEqual(frame["vehicles"][0]["length"], 8)
        network = load_network()
        visual = network.visual()
        expected_turns = sum(network.turn_allowed(incoming, outgoing)
                             for junction in network.intersections
                             for incoming in network.incoming[junction]
                             for outgoing in network.outgoing[junction])
        self.assertEqual(len(visual["internal_lanes"]), expected_turns)
        self.assertGreater(expected_turns, 0)

    def test_comparison_and_csv_export_trace_saved_values(self):
        engine = TrafficEngine(seed=42)
        engine.configure(traffic_density="single", pedestrian_density="none")
        engine.start(1)
        frames = [engine.to_dict()]
        while engine.status == "running":
            engine.step(1)
            frames.append(engine.to_dict())
        run_ids = []
        for label in ("left", "right"):
            timeline = self.root / f"{label}.jsonl"
            timeline.write_text("".join(json.dumps(frame) + "\n" for frame in frames), encoding="utf-8")
            manifest = {"experiment": engine.experiment_metadata(),
                        "controller": {"provenance_label": "Fixed-Time"},
                        "scenario": {"intersection_id": engine.intersection_id},
                        "timeline": {"requested_duration_seconds": 1, "actual_duration_seconds": 1,
                                     "step_length_seconds": 0.1, "frame_count": len(frames)}}
            timeline.with_suffix(".manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
            run_id = database.create_run(self.scenario["id"], None, run_mode="pre-record", status="completed",
                                         control_mode="fixed-time", seed=42, duration_seconds=1, timeline_path=str(timeline))
            metrics = {**engine.to_dict()["metrics"], "experiment": engine.experiment_metadata()}
            database.save_run_metrics(run_id=run_id, avg_waiting_time=metrics["avg_wait"],
                avg_queue_length=metrics["avg_queue"], max_queue_length=metrics["max_queue"],
                throughput=metrics["throughput"], avg_pedestrian_delay=metrics["avg_ped_delay"],
                raw_metrics_json=json.dumps(metrics))
            run_ids.append(run_id)
        pair = self.a.get("/api/compare/pair", params={"left_run_id": run_ids[0], "right_run_id": run_ids[1]})
        self.assertEqual(pair.status_code, 200, pair.text)
        data = pair.json()
        self.assertEqual(data["frame_count"], len(frames))
        self.assertEqual(data["left"]["frames"][-1]["throughput"], metrics["throughput"])
        self.assertEqual(data["left"]["option"]["provenance"]["demand_sha256"], engine.demand_fingerprint)
        self.assertTrue(any("synthetic" in warning for warning in data["warnings"]))
        with patch("backend.main.report_export_directory", return_value=self.root):
            exported = self.a.post("/api/reports/export", json={"run_ids": run_ids, "format": "csv"})
        self.assertEqual(exported.status_code, 200, exported.text)
        self.assertIn("Demand SHA256", exported.text)
        self.assertIn(engine.demand_fingerprint, exported.text)
        self.assertIn("Unfinished Vehicles", exported.text)
        self.assertEqual(exported.text.count(engine.demand_fingerprint), 4)
        missing = self.a.post("/api/reports/export", json={"run_ids": [run_ids[0], 999999], "format": "csv"})
        self.assertEqual(missing.status_code, 404)

    def test_static_and_adaptive_routing_pair_keeps_controller_fixed(self):
        run_ids = []
        demand_hashes = []
        for routing_mode in ("static", "adaptive"):
            engine = TrafficEngine(seed=42)
            engine.configure(traffic_density="single", pedestrian_density="none", routing_mode=routing_mode)
            engine.start(1)
            frames = [engine.to_dict()]
            while engine.status == "running":
                engine.step(1)
                frames.append(engine.to_dict())
            experiment = engine.experiment_metadata()
            demand_hashes.append(experiment["demand_sha256"])
            timeline = self.root / f"{routing_mode}.jsonl"
            timeline.write_text("".join(json.dumps(frame) + "\n" for frame in frames), encoding="utf-8")
            timeline.with_suffix(".manifest.json").write_text(json.dumps({
                "experiment": experiment, "controller": {"provenance_label": "Fixed-Time"},
                "scenario": {"intersection_id": engine.intersection_id},
                "timeline": {"requested_duration_seconds": 1, "actual_duration_seconds": 1,
                             "step_length_seconds": 0.1, "frame_count": len(frames)},
            }), encoding="utf-8")
            run_ids.append(database.create_run(
                self.scenario["id"], None, run_mode="pre-record", status="completed",
                control_mode="fixed-time", seed=42, duration_seconds=1, timeline_path=str(timeline)))
        self.assertEqual(demand_hashes[0], demand_hashes[1])
        compatible = self.a.get("/api/compare/compatible-runs", params={"left_run_id": run_ids[0]})
        self.assertEqual(compatible.status_code, 200, compatible.text)
        self.assertIn(run_ids[1], [option["run"]["id"] for option in compatible.json()["runs"]])
        pair = self.a.get("/api/compare/pair", params={"left_run_id": run_ids[0], "right_run_id": run_ids[1]})
        self.assertEqual(pair.status_code, 200, pair.text)
        self.assertEqual(pair.json()["comparison_type"], "routing")
        database.update_run(run_ids[1], control_mode="ql")
        rejected = self.a.get("/api/compare/pair", params={"left_run_id": run_ids[0], "right_run_id": run_ids[1]})
        self.assertEqual(rejected.status_code, 422)


if __name__ == "__main__":
    unittest.main()
