"""Junction reservations must always be released (engine fix plan P0-1)."""
import json
import math
import unittest
from pathlib import Path

from simulation.road_network import RoadNetwork
from simulation.scenario_config import VEHICLE_TYPES
from simulation.mixed_traffic import SIDE_CLEARANCE_M, lateral_bounds
from simulation.traffic_engine import EXIT_SPACE_MARGIN, TrafficEngine
from tests.mixed_traffic_helpers import assert_never_overlap, place
from tests import test_native_traffic_contract as contract

TWO_JUNCTION_NETWORK = Path(__file__).resolve().parents[1] / "data/networks/tagum_network_2j.json"


def two_junction_line(link_length=60, link_width=None):
    """w -> j1 -> j2 -> e, one-way, so a red at j2 can hold a queue on the j1-j2 link."""
    coordinates = {"w": (-150, 0), "j1": (0, 0), "j2": (link_length, 0), "e": (link_length+150, 0),
                   "n1": (0, 150), "n2": (link_length, 150)}
    nodes = [{"id": name, "x": x, "y": y, "boundary": not name.startswith("j")} for name, (x, y) in coordinates.items()]
    roads = [{"id": road, "source": start, "target": end, "shape": [coordinates[start], coordinates[end]], "oneway": True, "speed_mps": 8.33}
             for road, start, end in (("in", "w", "j1"), ("link", "j1", "j2"), ("out", "j2", "e"), ("n1", "n1", "j1"), ("n2", "n2", "j2"))]
    if link_width is not None:
        next(road for road in roads if road["id"] == "link")["width_per_direction_m"] = link_width
    return RoadNetwork({"id": "two-junction-line", "nodes": nodes, "roads": roads, "source": {"kind": "synthetic"}})


def hold(engine, node, family):
    signal = engine.signals[node]
    signal.index, signal.stage, signal.elapsed = signal.approaches.index(family), "green", 0
    signal.external, signal.maximum_green = True, 180


class JunctionReleaseTests(unittest.TestCase):
    # Reuse the synthetic-cross helpers without collecting that test class twice.
    engine = contract.NativeTrafficContractTests.engine
    hold_phase = contract.NativeTrafficContractTests.hold_phase

    def held_queue_cases(self, engine_class=TrafficEngine):
        """Every class pair, queue length, link width and queue side, with the link held by a red at j2 like
        spillback towards j1. Yields (engine, entering vehicle, route, entered j1) after 400 ticks."""
        for link_width in (None, 6.6):
            for queued_side in ("left", "kerb"):
                for entering_type in VEHICLE_TYPES:
                    for queued_type in VEHICLE_TYPES:
                        for queued_count in range(0, 12):
                            engine = engine_class(seed=7, network=two_junction_line(link_width=link_width))
                            engine.configure(traffic_density="none", pedestrian_density="none")
                            engine.driver_variation_scale = 0
                            engine.start(300)
                            hold(engine, "j1", "west")
                            hold(engine, "j2", "north")
                            route = engine.network.route("w", "e")
                            link = engine.network.lanes[route[1]]
                            front = link.length
                            for _ in range(queued_count):
                                queued = engine.add_vehicle(route[1:], vehicle_type=queued_type)
                                if queued is None:
                                    break  # the link is already full back to j1
                                queued.position = front-queued.length/2
                                queued.lateral = queued.lateral_target = lateral_bounds(link.width, queued.width)[0 if queued_side == "left" else 1]
                                front -= queued.length+queued.minimum_gap
                            entering = engine.add_vehicle(route, vehicle_type=entering_type)
                            entering.position = engine.network.lanes[route[0]].length-entering.length/2
                            entered = False
                            for _ in range(400):
                                engine.step()
                                entered = entered or entering.reserved_junction == "j1"
                            yield (link_width, queued_side, entering_type, queued_type, queued_count), engine, entering, route, entered

    def test_any_admitted_vehicle_clears_and_releases_behind_a_held_queue(self):
        """For every case: the vehicle never enters, or it enters and releases."""
        outcomes = set()
        for case, engine, entering, route, entered in self.held_queue_cases():
            with self.subTest(case=case):
                outcomes.add(entered)
                if entered:
                    self.assertEqual(entering.lane_id, route[1])
                    self.assertNotEqual(entering.reserved_junction, "j1")
                    self.assertNotIn("j1", engine.reservations)
                else:
                    self.assertEqual(entering.lane_id, route[0])
        self.assertEqual(outcomes, {True, False}, "both admitted and refused cases must be exercised")

    def test_area_only_rule_would_strand_a_vehicle(self):
        class AreaOnlyEngine(TrafficEngine):
            def _exit_has_space(self, lane_id, entering):
                # Footprint area only, no end-to-end check: the same occupying vehicles as the real rule, plus the entrant.
                occupying = [vehicle for vehicle in self.vehicles.values() if vehicle is not entering and (
                    (vehicle.connector is None and vehicle.lane_id == lane_id)
                    or (vehicle.reserved_junction and len(vehicle.route) > 1 and vehicle.route[1] == lane_id))]
                lane = self.network.lanes[lane_id]
                area = sum((vehicle.length+vehicle.minimum_gap)*(vehicle.width+SIDE_CLEARANCE_M) for vehicle in occupying+[entering])
                return area <= 0.8*lane.length*lane.width
        stranded = [entered and entering.reserved_junction == "j1"
                    for _, engine, entering, route, entered in self.held_queue_cases(AreaOnlyEngine)]
        self.assertTrue(any(stranded), "the end-to-end rule must be what prevents stranding")

    def test_motorcycles_count_with_their_own_minimum_gap(self):
        engine = TrafficEngine(seed=7, network=two_junction_line())
        engine.configure(traffic_density="none", pedestrian_density="none")
        engine.driver_variation_scale = 0
        engine.start(300)
        hold(engine, "j1", "west")
        hold(engine, "j2", "north")
        route = engine.network.route("w", "e")
        link = engine.network.lanes[route[1]]
        most = 0
        for tick in range(1200):
            if tick % 20 == 0:
                engine.add_vehicle(route, vehicle_type="motorcycle", speed=5)
            assert_never_overlap(self, engine, 1)
            on_or_committed = sum(1 for vehicle in engine.vehicles.values() if (vehicle.connector is None and vehicle.lane_id == link.id)
                                  or (vehicle.reserved_junction == "j1" and len(vehicle.route) > 1 and vehicle.route[1] == link.id))
            most = max(most, on_or_committed)
        self.assertEqual(most, math.floor(link.length/(2.0+1.0+EXIT_SPACE_MARGIN)))

    def test_watchdog_metrics_flag_blocked_green_but_not_red_waits(self):
        engine = self.engine(network=contract.cross_network())
        signal = self.hold_phase(engine, "west")
        waiting = engine.add_vehicle(["wf", "er"])
        waiting.position = engine.network.lanes["wf"].length-waiting.length/2
        waiting.stop_arrival = engine.simulation_time
        engine.last_vehicle_movement = engine.simulation_time-61
        self.assertGreater(engine._gridlock_seconds(), 60)
        signal.index = signal.approaches.index("north")
        self.assertEqual(engine._gridlock_seconds(), 0)
        waiting.reserved_junction, waiting.stopped_for = "j", 31.0
        engine._refresh_metrics()
        self.assertEqual(engine._last_metrics["stuck_junction_vehicles"], 1)

    def test_a_slow_starter_committing_after_a_long_red_is_not_counted_stuck(self):
        # A truck needs two ticks to pass 0.1 m/s; its red wait must not count as time stuck in the junction.
        engine = self.engine(network=contract.cross_network())
        engine.driver_variation_scale = 0
        hold(engine, "j", "north")
        truck = engine.add_vehicle(["wf", "er"], vehicle_type="truck", speed=5)
        engine.step(600)
        self.assertGreater(truck.stopped_for, 30)
        hold(engine, "j", "west")
        committed = False
        for _ in range(100):
            engine.step()
            committed = committed or truck.reserved_junction == "j"
            self.assertEqual(engine._last_metrics["stuck_junction_vehicles"], 0)
        self.assertTrue(committed)

    def test_a_vehicle_whose_step_the_footprint_check_cancels_counts_as_stopped(self):
        # The footprint check, not the car-following model, can be what holds a vehicle in the junction.
        class BlockedEngine(TrafficEngine):
            blocked = False

            def _clear_travel(self, vehicle, travel, connector_length):
                return 0.0 if self.blocked else super()._clear_travel(vehicle, travel, connector_length)

        engine = BlockedEngine(seed=7, network=contract.cross_network())
        engine.configure(traffic_density="none", pedestrian_density="none")
        engine.driver_variation_scale = 0
        engine.start(300)
        hold(engine, "j", "west")
        car = engine.add_vehicle(["wf", "er"], speed=5)
        while car.connector is None:
            engine.step()
        engine.blocked, blocked_at = True, engine.simulation_time
        engine.step(40)
        self.assertGreaterEqual(car.stopped_for, 3.9)
        self.assertLessEqual(engine.last_vehicle_movement, blocked_at)

    def test_crossing_paths_from_one_approach_never_lock_inside_the_junction(self):
        # Tagum 5j: a right turner on the kerb side and a left turner a few metres behind on the centre-line side
        # used to enter together and block each other's next step for good.
        network = RoadNetwork(json.loads((Path(__file__).resolve().parents[1]/"data/networks/tagum_network.json").read_text(encoding="utf-8")))
        node = network.lanes["road2r"].target
        for gap, speeds in ((3, (2, 5)), (6, (0, 4))):
            with self.subTest(gap=gap, speeds=speeds):
                engine = TrafficEngine(seed=7, network=network)
                engine.configure(traffic_density="none", pedestrian_density="none")
                engine.driver_variation_scale = 0
                engine._decide_lateral = lambda vehicle, lane: None  # keep the crossing order
                engine.start(600)
                hold(engine, node, network.lanes["road2r"].approach)
                right = place(engine, ["road2r", "road0f", "road10f", "road4r"], "motorcycle", from_stop_line=2, lateral=2.7, speed=speeds[0])
                left = place(engine, ["road2r", "road1f"], "motorcycle", from_stop_line=2+gap, lateral=-2.05, speed=speeds[1])
                assert_never_overlap(self, engine, 400)
                self.assertTrue(all(vehicle.id not in engine.vehicles or engine.vehicles[vehicle.id].connector is None
                                    for vehicle in (right, left)))
                self.assertNotIn(left.id, engine.vehicles)

    def test_two_junction_network_keeps_completing_trips_at_medium_demand(self):
        network = RoadNetwork(json.loads(TWO_JUNCTION_NETWORK.read_text(encoding="utf-8")))
        engine = TrafficEngine(seed=101, network=network)
        engine.configure(traffic_density="medium")
        engine.start(duration_limit=900)
        completed_at = {}
        while engine.status == "running":
            engine.step(100)
            completed_at[round(engine.simulation_time)] = engine.completed
            self.assertEqual(engine._last_metrics["stuck_junction_vehicles"], 0)
            self.assertEqual(engine._last_metrics["gridlock_seconds"], 0)
        # Before the fix both junctions locked each other from about t=600 s with 52 completed trips.
        self.assertGreater(completed_at[900], completed_at[600])
        self.assertEqual(engine._last_metrics["vehicle_conservation_error"], 0)


if __name__ == "__main__":
    unittest.main()
