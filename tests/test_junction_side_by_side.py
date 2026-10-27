"""Side-by-side vehicles pass through a junction without overlapping or waiting on each other."""
import unittest

from simulation.mixed_traffic import lateral_bounds
from simulation.road_network import length
from tests.mixed_traffic_helpers import assert_never_overlap, hold_green, junction_network, place, started_engine

THROUGH, LEFT = ["wf", "er"], ["wf", "nr"]


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
        engine.step(20)
        self.assertTrue(car.connector is not None and motorcycle.connector is not None)
        assert_never_overlap(self, engine, 280)
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


if __name__ == "__main__":
    unittest.main()
