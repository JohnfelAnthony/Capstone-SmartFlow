import json
import math
import unittest

from simulation.road_network import load_network
from simulation.traffic_engine import CAR_LENGTH, MIN_GAP, TrafficEngine


class NativeEngineTests(unittest.TestCase):
    def test_real_connected_geometry_has_five_junctions_and_alternate_routes(self):
        network = load_network()
        self.assertEqual(len(network.intersections), 5)
        self.assertEqual(network.payload["source"]["provider"], "OpenStreetMap")
        self.assertTrue(any(len(road["shape"]) > 2 for road in network.payload["roads"]))
        alternatives = 0
        for source in network.boundaries:
            for target in network.boundaries:
                route = network.route(source, target)
                if len(route) > 2:
                    alternative = network.route(source, target, closed={route[1]})
                    alternatives += bool(alternative and alternative != route)
        self.assertGreater(alternatives, 0)

    def test_same_seed_has_identical_trajectories_and_metrics(self):
        first, second = TrafficEngine(seed=19), TrafficEngine(seed=19)
        for engine in (first, second):
            engine.configure(traffic_density="medium", pedestrian_density="medium")
            engine.start(80)
            engine.step(800)
        self.assertEqual(first.to_dict(), second.to_dict())
        json.dumps(first.to_dict(), allow_nan=False)

    def test_pause_resume_reset_and_exact_duration(self):
        engine = TrafficEngine()
        engine.start(12)
        engine.step(20)
        engine.pause()
        before = engine.to_dict()
        engine.step(20)
        self.assertEqual(before, engine.to_dict())
        engine.resume()
        engine.step(200)
        self.assertEqual((engine.status, engine.simulation_time), ("completed", 12))
        engine.reset()
        self.assertEqual(engine.simulation_time, 0)
        self.assertEqual(len(engine.vehicles), 0)

    def test_single_car_traverses_connected_junctions_and_completes(self):
        engine = TrafficEngine()
        engine.start(600)
        visited = set()
        for _ in range(6000):
            engine.step()
            self.assertEqual(len(engine.vehicles), 1)
            visited.update(car.reserved_junction for car in engine.vehicles.values() if car.reserved_junction)
        self.assertGreaterEqual(len(visited), 3)
        self.assertGreater(engine.completed, 0)

    def test_heavy_traffic_preserves_gaps_and_junction_exclusivity(self):
        engine = TrafficEngine(seed=27)
        engine.configure(traffic_density="high", pedestrian_density="high")
        engine.start(300)
        for _ in range(3000):
            engine.step()
            for lane in engine.network.lanes:
                cars = sorted((car for car in engine.vehicles.values() if car.lane_id == lane and car.connector is None), key=lambda car: car.position)
                for rear, front in zip(cars, cars[1:]):
                    self.assertGreaterEqual(front.position-rear.position, CAR_LENGTH+MIN_GAP-0.001)
            crossing_nodes = [car.reserved_junction for car in engine.vehicles.values() if car.connector]
            self.assertEqual(len(crossing_nodes), len(set(crossing_nodes)))
            for node in crossing_nodes:
                self.assertFalse(engine._crossing_occupied(node))
            self.assertTrue(all(math.isfinite(car.speed) and car.speed >= 0 for car in engine.vehicles.values()))
        self.assertGreater(engine.completed, 0)
        self.assertGreater(engine.completed_pedestrians, 0)
        self.assertGreater(engine._last_metrics["avg_ped_delay"], 0)

    def test_closed_lane_is_avoided_and_reopens(self):
        engine = TrafficEngine()
        engine.configure(traffic_density="none")
        engine.start(300)
        chosen = None
        for source in engine.network.boundaries:
            for target in engine.network.boundaries:
                route = engine.network.route(source, target)
                if len(route) > 2 and engine.network.route(source, target, closed={route[1]}):
                    chosen = route
                    break
            if chosen:
                break
        self.assertIsNotNone(chosen)
        car = engine.add_vehicle(chosen)
        engine.close_lane(chosen[1])
        engine.step(10)
        self.assertNotIn(chosen[1], car.route[1:])
        self.assertEqual(engine.reroutes, 1)
        engine.close_lane(chosen[1], False)
        self.assertNotIn(chosen[1], engine.closed_lanes)

    def test_signal_requests_use_minimum_green_yellow_and_all_red(self):
        engine = TrafficEngine()
        engine.configure_rl_control()
        engine.start(30)
        signal = engine.signals[engine.controlled_junction]
        target = next(approach for approach in signal.approaches if approach not in {signal.family, "pedestrian"})
        original = signal.family
        engine.apply_rl_action("SERVE_"+target.upper())
        engine.step(90)
        self.assertEqual((signal.family, signal.stage), (original, "green"))
        phases = []
        for _ in range(70):
            engine.step()
            if not phases or signal.stage != phases[-1]:
                phases.append(signal.stage)
        self.assertEqual(phases, ["green", "yellow", "red", "green"])
        self.assertEqual(signal.family, target)


if __name__ == "__main__":
    unittest.main()
