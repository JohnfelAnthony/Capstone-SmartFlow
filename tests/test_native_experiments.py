import copy
import json
import math
import tempfile
import unittest
from pathlib import Path

from simulation.road_network import RoadNetwork, load_network
from simulation.scenario_config import read_trip_csv
from simulation.traffic_engine import TrafficEngine, Pedestrian, STEP_LENGTH
from tools.run_native_experiment import run_experiment


class NativeExperimentTests(unittest.TestCase):
    def setUp(self):
        self.engine = TrafficEngine(seed=71)
        self.network = self.engine.network
        self.pair = next((a, b) for a in self.network.boundaries for b in self.network.boundaries if len(self.network.route(a, b)) >= 3)
        self.route = self.network.route(*self.pair)

    def trip(self, time=0, kind="car"):
        return {"time": time, "source": self.pair[0], "destination": self.pair[1], "vehicle_type": kind}

    def test_invalid_configuration_is_atomic(self):
        original = copy.deepcopy(self.engine.config)
        for settings in ({"traffic_density": "high", "closed_lanes": ["missing"]},
                         {"green_seconds": float("nan")}, {"events": [{"time": 1, "lane_id": self.route[0], "closed": "false"}]},
                         {"trips": [{**self.trip(), "destination": "missing"}]}, {"typo": 3}):
            with self.assertRaises(ValueError):
                self.engine.configure(**settings)
            self.assertEqual(self.engine.config, original)

    def test_reset_restores_baseline_and_replays_events_identically(self):
        self.engine.configure(traffic_density="medium", pedestrian_density="medium", events=[
            {"time": 2, "lane_id": self.route[1], "closed": True},
            {"time": 4, "lane_id": self.route[0], "speed_factor": .3}])
        self.engine.start(20)
        self.engine.step(200)
        first = self.engine.to_dict()
        self.engine.start(20)
        self.assertNotIn(self.route[1], self.engine.closed_lanes)
        self.assertNotIn(self.route[0], self.engine.slow_lanes)
        self.engine.step(200)
        self.assertEqual(first, self.engine.to_dict())

    def test_identical_arrivals_across_closures_and_controller_choices(self):
        other = TrafficEngine(seed=71)
        self.engine.configure(traffic_density="high", pedestrian_density="high")
        other.configure(traffic_density="high", pedestrian_density="high", closed_lanes=[self.route[1]])
        other.configure_rl_control()
        for engine in (self.engine, other):
            engine.start(90)
            engine.step(900)
        self.assertEqual(self.engine.arrivals, other.arrivals)
        self.assertEqual(self.engine.pedestrian_serial, other.pedestrian_serial)
        self.assertEqual(self.engine.demand_fingerprint, other.demand_fingerprint)

    def test_no_route_demand_waits_then_enters_when_reopened(self):
        self.engine.configure(traffic_density="none", trips=[self.trip()], closed_lanes=list(self.network.outgoing[self.pair[0]]))
        self.engine.start(30)
        self.engine.step(40)
        self.assertEqual(len(self.engine.pending_demand), 1)
        self.assertEqual(len(self.engine.vehicles), 0)
        for lane in self.network.outgoing[self.pair[0]]:
            self.engine.close_lane(lane, False)
        self.engine.step()
        self.assertEqual(len(self.engine.vehicles), 1)
        self.assertGreater(next(iter(self.engine.vehicles.values())).born, 0)
        self.assertEqual(self.engine._last_metrics["vehicle_conservation_error"], 0)

    def test_mixed_traffic_conserves_demand_and_bumper_gaps(self):
        self.engine.configure(traffic_density="high", pedestrian_density="high", vehicle_mix={"car": 2, "bus": 1, "motorcycle": 1, "tricycle": 1, "truck": 1})
        self.engine.start(180)
        for _ in range(1800):
            self.engine.step()
            for lane in self.network.lanes:
                cars = sorted((v for v in self.engine.vehicles.values() if v.lane_id == lane and not v.connector), key=lambda v: v.position)
                for rear, front in zip(cars, cars[1:]):
                    self.assertGreaterEqual(front.position-rear.position-(front.length+rear.length)/2, 2-.001)
            self.assertEqual(self.engine._last_metrics["vehicle_conservation_error"], 0)
            self.assertEqual(self.engine._last_metrics["pedestrian_conservation_error"], 0)
        self.assertGreater(self.engine.completed, 0)
        json.dumps(self.engine.to_dict(), allow_nan=False)

    def test_queue_limits_report_dropped_arrivals(self):
        self.engine.configure(traffic_density="none", trips=[self.trip() for _ in range(8)], max_pending_vehicles=2, closed_lanes=self.network.outgoing[self.pair[0]])
        self.engine.start(1)
        self.assertEqual(len(self.engine.pending_demand), 2)
        self.assertEqual(self.engine.deferred_demand, 6)
        self.assertEqual(self.engine._last_metrics["vehicle_conservation_error"], 0)

    def test_signal_plans_and_unsignalized_comparison(self):
        self.engine.configure(traffic_density="low", signal_plans={node: {"mode": "all_way_stop"} for node in self.network.intersections})
        self.engine.start(180)
        self.engine.step(1800)
        self.assertGreater(self.engine.completed, 0)
        self.assertTrue(all(s.mode == "all_way_stop" for s in self.engine.signals.values()))
        with self.assertRaisesRegex(ValueError, "signalized"):
            self.engine.configure_rl_control()

    def test_rl_maximum_hold_releases_phase_and_pedestrian_clearance(self):
        self.engine.configure(traffic_density="none")
        self.engine.configure_rl_control()
        self.engine.start(90)
        signal = self.engine.signals[self.engine.controlled_junction]
        initial = signal.family
        for _ in range(650):
            self.engine.apply_rl_action("SERVE_"+initial.upper())
            self.engine.step()
        self.assertNotEqual(signal.family, initial)
        signal.index = signal.approaches.index("pedestrian")
        signal.stage, signal.elapsed = "green", 0
        ped = Pedestrian("manual-ped", self.engine.controlled_junction)
        self.engine.pedestrians[ped.id] = ped
        self.engine.step()
        self.assertTrue(ped.crossing)
        signal.pending = initial
        self.engine.step(105)
        self.assertEqual(signal.family, "pedestrian")
        self.assertTrue(self.engine._crossing_occupied(ped.junction))

    def test_emergency_priority_respects_yellow_and_all_red(self):
        self.engine.configure(traffic_density="none")
        self.engine.start(60)
        car = self.engine.add_vehicle(self.route, vehicle_type="emergency")
        lane = self.network.lanes[car.lane_id]
        signal = self.engine.signals[lane.target]
        signal.index = next(i for i, a in enumerate(signal.approaches) if a not in {lane.approach, "pedestrian"})
        car.position = lane.length-car.length/2-5
        self.engine.step(50)
        self.assertNotEqual(signal.family, lane.approach)
        seen = set()
        for _ in range(120):
            self.engine.step()
            seen.add(signal.stage)
        self.assertIn("yellow", seen)
        self.assertIn("red", seen)
        self.assertEqual(signal.family, lane.approach)

    def test_network_validation_and_turn_restrictions(self):
        payload = copy.deepcopy(self.network.payload)
        payload["prohibited_turns"] = [[self.route[0], self.route[1]]]
        network = RoadNetwork(payload)
        self.assertFalse(network.turn_allowed(*self.route[:2]))
        self.assertNotEqual(network.route(*self.pair), self.route)
        with self.assertRaises(ValueError):
            network.connector(*self.route[:2])
        payload["roads"][0]["speed_mps"] = 0
        with self.assertRaises(ValueError):
            RoadNetwork(payload)

    def test_warmup_keeps_full_trip_time_and_lifetime_conservation(self):
        self.engine.configure(traffic_density="none", trips=[self.trip()])
        self.engine.start(300)
        self.engine.step(100)
        born = next(iter(self.engine.vehicles.values())).born
        self.engine.reset_metrics()
        self.assertEqual(next(iter(self.engine.vehicles.values())).born, born)
        self.engine.step(2900)
        self.assertEqual(self.engine.completed, 1)
        self.assertGreater(self.engine._last_metrics["avg_travel_time"], 10)
        self.assertEqual(self.engine._last_metrics["vehicle_conservation_error"], 0)

    def test_csv_demand_and_headless_experiment(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)/"trips.csv"
            path.write_text(f"time,source,destination,vehicle_type\n0,{self.pair[0]},{self.pair[1]},bus\n", encoding="utf-8")
            trips = read_trip_csv(path)
        result = run_experiment({"traffic_density": "none", "trips": trips}, duration=10, warmup=2)
        self.assertEqual(result["status"], "completed")
        self.assertEqual(result["metrics"]["measurement_seconds"], 10)
        self.assertEqual(result["metrics"]["total_vehicles_spawned"], 1)
        self.assertEqual(result["experiment"]["config"]["trips"][0]["vehicle_type"], "bus")


if __name__ == "__main__":
    unittest.main()
