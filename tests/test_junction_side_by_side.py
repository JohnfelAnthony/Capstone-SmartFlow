"""Side-by-side vehicles pass through a junction without overlapping or waiting on each other."""
import json
import unittest
from pathlib import Path

from simulation.mixed_traffic import lateral_bounds
from simulation.road_network import RoadNetwork, length
from simulation.traffic_engine import TrafficEngine
from tests.mixed_traffic_helpers import assert_never_overlap, hold_green, junction_network, place, started_engine

THROUGH, LEFT = ["wf", "er"], ["wf", "nr"]
NETWORK_2J = Path(__file__).resolve().parents[1]/"data"/"networks"/"tagum_network_2j.json"


def on_exit(vehicle, lane_id):
    return vehicle.connector is None and vehicle.lane_id == lane_id


def rear_past_line(vehicle):
    return vehicle.connector is not None and vehicle.connector_position-vehicle.length/2 >= 0 or len(vehicle.route) == 1 or vehicle.lane_id != "wf"


def front_past_line(engine, vehicle):
    return vehicle.connector is not None or vehicle.lane_id != "wf"


def beside(engine, a, b):
    return abs(engine._progress(a)-engine._progress(b)) < (a.length+b.length)/2+max(a.minimum_gap, b.minimum_gap)


class JunctionSideBySideTests(unittest.TestCase):
    def green_engine(self, **network_options):
        engine = started_engine(junction_network(**network_options))
        hold_green(engine, "j", "west")
        return engine

    def test_front_row_enters_the_junction_together(self):
        engine = self.green_engine()
        car = place(engine, THROUGH, "car", from_stop_line=0, lateral=-0.65)
        motorcycle = place(engine, THROUGH, "motorcycle", from_stop_line=0, lateral=1.15)
        engine.step(30)  # the stop line sits 4.1 m before the junction here
        self.assertTrue(car.connector is not None and motorcycle.connector is not None)
        assert_never_overlap(self, engine, 270)
        self.assertTrue(on_exit(car, "er") and on_exit(motorcycle, "er"))

    def test_crossing_movements_from_one_approach_never_overlap(self):
        engine = self.green_engine()
        car = place(engine, LEFT, "car", from_stop_line=0, lateral=0.65)
        motorcycle = place(engine, THROUGH, "motorcycle", from_stop_line=0, lateral=-1.15)
        car.stop_arrival, motorcycle.stop_arrival = engine.simulation_time-2, engine.simulation_time-1
        motorcycle_entered = False
        for _ in range(400):
            assert_never_overlap(self, engine, 1)
            if motorcycle.connector is not None and not motorcycle_entered:
                motorcycle_entered = True
                self.assertFalse(beside(engine, car, motorcycle))
        self.assertTrue(on_exit(car, "nr") and on_exit(motorcycle, "er"))

    def test_offset_stays_inside_the_connector(self):
        engine = self.green_engine(arm_widths={"w": 6.6})
        car = place(engine, THROUGH, "car", from_stop_line=0, lateral=2.3)
        wide, narrow = lateral_bounds(6.6, car.width)[1], lateral_bounds(3.3, car.width)[1]
        travelled = False
        for _ in range(300):
            engine.step(1)
            if car.connector is not None:
                travelled = True
                share = min(1.0, car.connector_position/length(car.connector))
                self.assertLessEqual(abs(car.lateral), (1-share)*wide+share*narrow+1e-9)
        self.assertTrue(travelled and on_exit(car, "er"))

    def test_no_sideways_jump_entering_a_narrower_exit(self):
        engine = self.green_engine(arm_widths={"w": 6.6})
        car = place(engine, THROUGH, "car", from_stop_line=0, lateral=1.0)
        previous = car.lateral
        for _ in range(300):
            engine.step(1)
            self.assertLessEqual(abs(car.lateral-previous), 0.05)
            previous = car.lateral
            if on_exit(car, "er"):
                break
        self.assertTrue(on_exit(car, "er"))

    def test_abreast_cars_merge_into_a_narrower_exit_one_after_the_other(self):
        engine = self.green_engine(arm_widths={"w": 6.6})
        first = place(engine, THROUGH, "car", from_stop_line=0, lateral=-2.3)
        second = place(engine, THROUGH, "car", from_stop_line=0, lateral=1.0)
        first.stop_arrival, second.stop_arrival = engine.simulation_time-2, engine.simulation_time-1
        for _ in range(300):
            assert_never_overlap(self, engine, 1)
            if front_past_line(engine, second):
                self.assertTrue(rear_past_line(first))
        self.assertTrue(on_exit(first, "er") and on_exit(second, "er"))

    def test_abreast_vehicles_arriving_on_green_at_speed_keep_the_fixed_order(self):
        cases = (({}, (LEFT, "car", 0.65), (THROUGH, "motorcycle", -1.15)),
                 ({"arm_widths": {"w": 6.6}}, (THROUGH, "car", -2.3), (THROUGH, "car", 1.0)))
        for options, (route_a, type_a, lateral_a), (route_b, type_b, lateral_b) in cases:
            with self.subTest(options=options):
                engine = self.green_engine(**options)
                a = place(engine, route_a, type_a, from_stop_line=40, lateral=lateral_a, speed=8)
                b = place(engine, route_b, type_b, from_stop_line=40, lateral=lateral_b, speed=8)
                for _ in range(300):
                    assert_never_overlap(self, engine, 1)
                    both_committed = a.reserved_junction == "j" and b.reserved_junction == "j"
                    self.assertFalse(both_committed and beside(engine, a, b), f"both committed abreast at t={engine.simulation_time}")
                self.assertTrue(on_exit(a, route_a[1]) and on_exit(b, route_b[1]))

    def test_abreast_vehicles_on_one_turning_movement_go_single_file(self):
        # Abreast inside a tight turn (about 8 m radius), bodies at different headings blocked each other for good.
        network = RoadNetwork(json.loads(NETWORK_2J.read_text(encoding="utf-8")))
        route, node = ["road3f", "road4r"], network.lanes["road3f"].target
        for gap in (0.0, 0.5, 2.0):
            with self.subTest(motorcycle_behind=gap):
                engine = started_engine(network)
                hold_green(engine, node, network.lanes["road3f"].approach)
                tricycle = place(engine, route, "tricycle", from_stop_line=0, lateral=0.85)
                motorcycle = place(engine, route, "motorcycle", from_stop_line=gap, lateral=-0.65)
                for _ in range(300):
                    assert_never_overlap(self, engine, 1)
                    both_inside = tricycle.connector is not None and motorcycle.connector is not None
                    self.assertFalse(both_inside and engine._beside(tricycle, motorcycle), f"abreast in the turn at t={engine.simulation_time}")
                self.assertTrue(on_exit(tricycle, "road4r") and on_exit(motorcycle, "road4r"))

    def test_all_way_stop_admits_one_vehicle_at_a_time_from_an_abreast_front_row(self):
        engine = started_engine(junction_network(), signal_plans={"j": {"mode": "all_way_stop"}})
        vehicles = [place(engine, THROUGH, "car", from_stop_line=0, lateral=-0.65),
                    place(engine, THROUGH, "motorcycle", from_stop_line=0, lateral=1.15),
                    place(engine, ["nf", "sr"], "car", from_stop_line=0, lateral=-0.65)]
        for _ in range(600):
            assert_never_overlap(self, engine, 1)
            self.assertLessEqual(len(engine.reservations.get("j", ())), 1)
        self.assertTrue(all(vehicle.id not in engine.vehicles or vehicle.connector is None and len(vehicle.route) == 1 for vehicle in vehicles))
        self.assertTrue(all(vehicle.lane_id in {"er", "sr"} or vehicle.id not in engine.vehicles for vehicle in vehicles))

    def test_all_way_stop_turn_passes_over_a_first_arrival_held_by_its_own_approach(self):
        # Tagum 5j: a truck that stopped first waits for the motorcycle standing in its turning path, which used to
        # never get the turn, so the junction stopped for good.
        network = RoadNetwork(json.loads((Path(__file__).resolve().parents[1]/"data/networks/tagum_network.json").read_text(encoding="utf-8")))
        node = network.lanes["road2r"].target
        engine = started_engine(network, signal_plans={node: {"mode": "all_way_stop"}})
        engine._decide_lateral = lambda vehicle, lane: None
        route = ["road2r", "road0f", "road10f", "road4r"]
        truck = place(engine, route, "truck", from_stop_line=0, lateral=-1.95)
        motorcycle = place(engine, route, "motorcycle", from_stop_line=0, lateral=0.2)
        truck.stop_arrival, motorcycle.stop_arrival = engine.simulation_time-2, engine.simulation_time-1
        assert_never_overlap(self, engine, 600)
        self.assertTrue(all(vehicle.id not in engine.vehicles or vehicle.route[0] != "road2r" for vehicle in (truck, motorcycle)))

    def test_all_way_stop_turn_skips_a_vehicle_queued_behind_one_without_exit_space(self):
        class FullExitEngine(TrafficEngine):
            def _exit_has_space(self, lane_id, entering):
                return entering is not blocked and super()._exit_has_space(lane_id, entering)

        engine = FullExitEngine(seed=7, network=junction_network(arm_widths={"w": 6.6}))
        engine.configure(traffic_density="none", pedestrian_density="none", signal_plans={"j": {"mode": "all_way_stop"}})
        engine.driver_variation_scale = 0
        engine.start(300)
        # Abreast into a narrower exit, so the second waits for the first, which has no exit space.
        blocked = place(engine, THROUGH, "car", from_stop_line=0, lateral=-2.3)
        follower = place(engine, THROUGH, "car", from_stop_line=0, lateral=1.0)
        crossing = place(engine, ["nf", "sr"], "car", from_stop_line=0, lateral=-0.65)
        blocked.stop_arrival, follower.stop_arrival, crossing.stop_arrival = (engine.simulation_time-3, engine.simulation_time-2,
                                                                                engine.simulation_time-1)
        engine.step(100)
        self.assertTrue(crossing.id not in engine.vehicles or crossing.lane_id == "sr")


if __name__ == "__main__":
    unittest.main()
