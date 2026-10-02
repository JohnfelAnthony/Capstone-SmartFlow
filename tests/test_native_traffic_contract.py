"""Synthetic traffic contracts independent of the eventual study intersections."""
import copy
import unittest
from unittest.mock import patch

from simulation.road_network import RoadNetwork, length
from simulation.traffic_engine import MIN_GAP, Pedestrian, Signal, TrafficEngine


def cross_network():
    nodes = [{"id": "j", "x": 0, "y": 0}]
    nodes.extend({"id": name, "x": x, "y": y, "boundary": True}
                 for name, x, y in (("w", -100, 0), ("e", 100, 0),
                                    ("n", 0, 100), ("s", 0, -100)))
    roads = [{"id": node["id"], "source": node["id"], "target": "j",
              "shape": [[node["x"], node["y"]], [0, 0]], "speed_mps": 8}
             for node in nodes[1:]]
    return RoadNetwork({"id": "synthetic-cross", "nodes": nodes, "roads": roads,
                        "source": {"kind": "synthetic"}})


def diamond_network():
    coordinates = {"w": (-100, 0), "a": (0, 0), "b": (100, 80),
                   "c": (100, -80), "d": (200, 0), "e": (300, 0)}
    nodes = [{"id": name, "x": x, "y": y, "boundary": name in {"w", "e"}}
             for name, (x, y) in coordinates.items()]
    roads = [{"id": name, "source": start, "target": end,
              "shape": [coordinates[start], coordinates[end]], "oneway": True, "speed_mps": 8}
             for name, start, end in (("in", "w", "a"), ("upper1", "a", "b"),
                                      ("upper2", "b", "d"), ("lower1", "a", "c"),
                                      ("lower2", "c", "d"), ("out", "d", "e"))]
    return RoadNetwork({"id": "synthetic-diamond", "nodes": nodes, "roads": roads,
                        "source": {"kind": "synthetic"}})


class NativeTrafficContractTests(unittest.TestCase):
    def engine(self, network=None, **config):
        engine = TrafficEngine(seed=7, network=network or cross_network())
        engine.configure(traffic_density="none", pedestrian_density="none", **config)
        engine.start(300)
        return engine

    def hold_phase(self, engine, family):
        signal = engine.signals["j"]
        signal.index = signal.approaches.index(family)
        signal.external = True
        signal.maximum_green = 180
        signal.elapsed = 0
        return signal

    def assert_bumper_gaps(self, engine):
        for lane in engine.network.lanes:
            vehicles = sorted((v for v in engine.vehicles.values() if not v.connector and v.lane_id == lane),
                              key=lambda vehicle: vehicle.position)
            for rear, front in zip(vehicles, vehicles[1:]):
                gap = front.position-rear.position-(front.length+rear.length)/2
                self.assertGreaterEqual(gap, MIN_GAP-1e-6)

    def test_mixed_followers_form_a_red_queue_and_discharge_on_green(self):
        engine = self.engine()
        self.hold_phase(engine, "north")
        route = engine.network.route("w", "e")
        cars = []
        for kind, position in (("truck", 70), ("bus", 48), ("car", 29), ("motorcycle", 10)):
            vehicle = engine.add_vehicle(route, vehicle_type=kind, speed=8)
            self.assertIsNotNone(vehicle)
            vehicle.position = position
            cars.append(vehicle)
        for _ in range(350):
            engine.step()
            self.assert_bumper_gaps(engine)
            self.assertFalse(engine.reservations)
            self.assertLessEqual(cars[0].position+cars[0].length/2, engine.network.lanes[route[0]].length+1e-6)
        self.assertEqual(engine._lane_queues()[route[0]], 4)
        self.hold_phase(engine, "west")
        for _ in range(600):
            engine.step()
            self.assert_bumper_gaps(engine)
        self.assertGreater(engine.completed, 0)
        self.assertEqual(engine._last_metrics["vehicle_conservation_error"], 0)

    def test_blocked_downstream_storage_prevents_junction_entry(self):
        engine = self.engine()
        self.hold_phase(engine, "west")
        vehicle = engine.add_vehicle(["wf", "er"], vehicle_type="bus")
        vehicle.position = engine.network.lanes["wf"].length-vehicle.length/2
        blocker = engine.add_vehicle(["er"], vehicle_type="truck")
        for _ in range(5):
            engine.step()
            self.assertIsNone(vehicle.reserved_junction)
            self.assertIsNone(vehicle.connector)
        blocker.position = 50
        engine.step()
        self.assertEqual(vehicle.reserved_junction, "j")
        for _ in range(500):
            engine.step()
            self.assert_bumper_gaps(engine)
        self.assertEqual(engine.completed, 2)

    def test_straight_left_and_right_turns_traverse_connected_geometry(self):
        for destination in ("e", "n", "s"):
            with self.subTest(destination=destination):
                engine = self.engine()
                self.hold_phase(engine, "west")
                route = engine.network.route("w", destination)
                connector = engine.network.connector(*route)
                self.assertEqual(connector[0], engine.network.lanes[route[0]].shape[-1])
                self.assertEqual(connector[-1], engine.network.lanes[route[1]].shape[0])
                self.assertGreater(length(connector), 0)
                vehicle = engine.add_vehicle(route)
                seen_connector = False
                for _ in range(600):
                    engine.step()
                    seen_connector |= bool(vehicle.connector)
                    if vehicle.id not in engine.vehicles:
                        break
                self.assertTrue(seen_connector)
                self.assertEqual(engine.completed, 1)
                self.assertFalse(engine.reservations)
        with self.assertRaisesRegex(ValueError, "prohibited"):
            cross_network().connector("wf", "wr")

    def test_vehicle_waits_through_full_yellow_and_all_red(self):
        engine = self.engine()
        signal = self.hold_phase(engine, "north")
        signal.stage, signal.pending = "yellow", "west"
        vehicle = engine.add_vehicle(["wf", "er"])
        vehicle.position = engine.network.lanes["wf"].length-vehicle.length/2
        for tick in range(39):
            engine.step()
            self.assertIsNone(vehicle.reserved_junction)
            self.assertEqual(signal.stage, "yellow" if tick < 29 else "red")
        engine.step()
        self.assertEqual((signal.family, signal.stage), ("west", "green"))
        self.assertEqual(vehicle.reserved_junction, "j")

    def test_slow_pedestrian_holds_clearance_against_emergency_request(self):
        engine = self.engine(crossing_length=30, pedestrian_speed=.5)
        signal = self.hold_phase(engine, "pedestrian")
        signal.green_seconds = signal.maximum_green = 10
        pedestrian = Pedestrian("ped-test", "j")
        engine.pedestrians[pedestrian.id] = pedestrian
        engine.pedestrian_serial = 1
        vehicle = engine.add_vehicle(["wf", "er"], vehicle_type="emergency")
        vehicle.position = engine.network.lanes["wf"].length-vehicle.length/2
        engine.step()
        self.assertTrue(pedestrian.crossing)
        for _ in range(590):
            engine.step()
            self.assertTrue(engine._crossing_occupied("j"))
            self.assertIsNone(vehicle.reserved_junction)
            self.assertEqual(signal.family, "pedestrian")
        engine.step(1000)
        self.assertEqual(engine.completed_pedestrians, 1)
        self.assertEqual(engine.emergency_completed, 1, "Emergency vehicle must eventually cross after pedestrian clearance")
        self.assertNotIn(vehicle.id, engine.vehicles)
        self.assertEqual(engine._last_metrics["pedestrian_conservation_error"], 0)

    def test_in_network_vehicle_waits_when_no_detour_then_recovers(self):
        engine = self.engine()
        self.hold_phase(engine, "west")
        vehicle = engine.add_vehicle(["wf", "er"])
        vehicle.position = engine.network.lanes["wf"].length-vehicle.length/2
        engine.close_lane("er")
        engine.step(100)
        self.assertEqual(vehicle.route, ["wf", "er"])
        self.assertIsNone(vehicle.reserved_junction)
        self.assertEqual(engine._last_metrics["unfinished_vehicles"], 1)
        engine.close_lane("er", False)
        engine.step(500)
        self.assertEqual(engine.completed, 1)
        self.assertEqual(engine._last_metrics["vehicle_conservation_error"], 0)

    def test_adaptive_routing_requires_benefit_and_respects_cooldown(self):
        engine = self.engine(diamond_network(), reroute_improvement=.15, reroute_interval=15)
        route = ["inf", "upper1f", "upper2f", "outf"]
        vehicle = engine.add_vehicle(route)
        costs = {lane: 1.0 for lane in engine.network.lanes}
        costs.update(upper1f=10, upper2f=10, lower1f=9, lower2f=9)
        with patch.object(engine, "_travel_costs", return_value=costs):
            engine._reroute(vehicle)
            self.assertEqual(vehicle.route, route, "A small improvement must not trigger rerouting")
            costs.update(lower1f=5, lower2f=5)
            engine._reroute(vehicle)
            self.assertEqual(vehicle.route, route, "Cost changes must not bypass the cooldown")
            engine.simulation_time = 15
            engine._reroute(vehicle)
            self.assertEqual(vehicle.route, ["inf", "lower1f", "lower2f", "outf"])
            costs.update(upper1f=1, upper2f=1)
            engine._reroute(vehicle)
            self.assertEqual(engine.reroutes, 1)
            engine.simulation_time = 30
            engine._reroute(vehicle)
            self.assertEqual(vehicle.route, route)
            self.assertEqual(engine.reroutes, 2)

    def test_actual_queued_vehicles_make_adaptive_detour_beneficial(self):
        engine = self.engine(diamond_network(), reroute_improvement=.15)
        route = ["inf", "upper1f", "upper2f", "outf"]
        traveler = engine.add_vehicle(route)
        for position in (90, 75, 60, 45, 30, 15):
            blocker = engine.add_vehicle(["upper1f", "upper2f", "outf"])
            self.assertIsNotNone(blocker)
            blocker.position = position
            blocker.speed = 0
        self.assertEqual(engine._lane_queues()["upper1f"], 6)
        self.assertGreater(engine._travel_costs()["upper1f"], engine._travel_costs()["lower1f"])
        engine._reroute(traveler)
        self.assertEqual(traveler.route, ["inf", "lower1f", "lower2f", "outf"])
        self.assertEqual(engine.reroutes, 1)

    def test_closure_forces_static_detour_and_restoration_does_not_churn(self):
        engine = self.engine(diamond_network(), routing_mode="static")
        vehicle = engine.add_vehicle(["inf", "upper1f", "upper2f", "outf"])
        engine.close_lane("upper1f")
        engine.step()
        self.assertNotIn("upper1f", vehicle.route)
        detour = list(vehicle.route)
        engine.close_lane("upper1f", False)
        engine.step(20)
        self.assertEqual(vehicle.route, detour)
        self.assertEqual(engine.reroutes, 1)

    def test_scheduled_slowdown_and_restore_are_visible_and_repeatable(self):
        engine = self.engine(events=[{"time": 1, "lane_id": "wf", "speed_factor": .25},
                                     {"time": 4, "lane_id": "wf", "speed_factor": 1}])
        self.hold_phase(engine, "west")
        vehicle = engine.add_vehicle(["wf", "er"], speed=8)
        engine.step(10)
        self.assertEqual(engine.to_dict()["visual"]["slow_lanes"], {"wf": .25})
        engine.step(20)
        self.assertLessEqual(vehicle.speed, 2)
        engine.step(10)
        self.assertEqual(engine.to_dict()["visual"]["slow_lanes"], {})

    def test_initial_unrestricted_speed_does_not_appear_as_disruption(self):
        engine = self.engine(slow_lanes={"wf": 1})
        self.assertEqual(engine.to_dict()["visual"]["slow_lanes"], {})

    def test_fixed_time_plan_sequence_and_configured_offsets_repeat(self):
        signal = Signal(["west", "east", "pedestrian"], green_seconds=7, minimum_green=5,
                        maximum_green=20, yellow_seconds=2, all_red_seconds=1)
        for count, expected in ((70, ("west", "yellow")), (20, ("west", "red")),
                                (10, ("east", "green")), (70, ("east", "yellow")),
                                (30, ("pedestrian", "green")), (70, ("pedestrian", "red")),
                                (10, ("west", "green"))):
            for _ in range(count):
                signal.step(.1, False)
            self.assertEqual((signal.family, signal.stage), expected)
        engine = self.engine(signal_plans={"j": {"green_seconds": 7, "minimum_green": 5,
                                                 "maximum_green": 20, "offset_seconds": 8}})
        engine.stop()
        engine.configure(traffic_density="low")
        engine.start(300)
        self.assertEqual(engine.signals["j"].stage, "yellow")
        engine.step(3000)
        first = copy.deepcopy(engine.to_dict())
        self.assertEqual(first["status"], "completed")
        first_fingerprint = engine.demand_fingerprint
        engine.start(300)
        engine.step(3000)
        self.assertEqual(engine.to_dict(), first)
        self.assertEqual(engine.demand_fingerprint, first_fingerprint)
        self.assertEqual(engine.controller_provenance, "fixed-time")
        self.assertFalse(any(signal.external for signal in engine.signals.values()))


if __name__ == "__main__":
    unittest.main()
