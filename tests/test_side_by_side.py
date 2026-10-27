"""Vehicles travel and queue side by side within a lane's real width."""
import json
import unittest
from pathlib import Path

from simulation.road_network import RoadNetwork
from simulation.scenario_config import TAGUM_PROVISIONAL_MIX
from simulation.traffic_engine import TrafficEngine
from tests.mixed_traffic_helpers import (assert_never_overlap, front_to_stop_line, hold_green, junction_network, place,
                                         started_engine)

NETWORK_2J = Path(__file__).resolve().parents[1]/"data"/"networks"/"tagum_network_2j.json"
ROUTE = ["wf", "er"]


class SideBySideTests(unittest.TestCase):
    def red_engine(self, **network_options):
        engine = started_engine(junction_network(**network_options))
        hold_green(engine, "j", "north")
        return engine

    def test_two_cars_stay_single_file_on_a_3_3_m_lane(self):
        engine = self.red_engine()
        first = engine.add_vehicle(ROUTE, speed=5)
        engine.step(30)
        second = engine.add_vehicle(ROUTE, speed=5)
        engine.step(300)
        self.assertLessEqual(second.position+second.length/2, first.position-first.length/2)

    def test_two_cars_queue_abreast_on_a_6_6_m_carriageway(self):
        engine = self.red_engine(lanes_tag="4")
        cars = [place(engine, ROUTE, "car", from_stop_line=20, lateral=lateral) for lateral in (-2.3, 1.0)]
        assert_never_overlap(self, engine, 300, every=10)
        self.assertTrue(all(front_to_stop_line(engine, car) <= 1.0 for car in cars), [front_to_stop_line(engine, car) for car in cars])

    def test_motorcycle_on_the_kerb_side_reaches_the_stop_line_past_queued_cars(self):
        engine = self.red_engine()
        for distance in (0.0, 6.5, 13.0):
            place(engine, ROUTE, "car", from_stop_line=distance, lateral=-0.65)
        motorcycle = place(engine, ROUTE, "motorcycle", from_stop_line=40, lateral=1.15, speed=5)
        assert_never_overlap(self, engine, 300, every=10)
        self.assertLessEqual(front_to_stop_line(engine, motorcycle), 1.0)

    def test_tricycle_holds_cars_behind_but_lets_motorcycles_pass(self):
        engine = self.red_engine()
        tricycle = place(engine, ROUTE, "tricycle", from_stop_line=0, lateral=0.85)
        motorcycle = place(engine, ROUTE, "motorcycle", from_stop_line=20, lateral=-1.15, speed=5)
        car = place(engine, ROUTE, "car", from_stop_line=40, lateral=-0.65, speed=5)
        assert_never_overlap(self, engine, 300, every=10)
        self.assertLessEqual(front_to_stop_line(engine, motorcycle), 1.0)
        self.assertLessEqual(car.position+car.length/2, tricycle.position-tricycle.length/2)

    def test_spawn_places_vehicles_abreast_when_the_lane_start_is_partly_occupied(self):
        engine = self.red_engine()
        car = engine.add_vehicle(ROUTE, vehicle_type="car")
        motorcycle = engine.add_vehicle(ROUTE, vehicle_type="motorcycle")
        self.assertIsNotNone(motorcycle)
        self.assertAlmostEqual(car.lateral, -0.65)
        self.assertAlmostEqual(motorcycle.lateral, 1.15)
        self.assertIsNone(engine.add_vehicle(ROUTE, vehicle_type="car"))

    def test_mixed_traffic_never_overlaps(self):
        engine = TrafficEngine(seed=101, network=RoadNetwork(json.loads(NETWORK_2J.read_text(encoding="utf-8"))))
        engine.configure(traffic_density="medium", vehicle_mix=dict(TAGUM_PROVISIONAL_MIX))
        engine.start(300)
        assert_never_overlap(self, engine, 3000, every=1)
        self.assertGreater(engine.completed, 0)


if __name__ == "__main__":
    unittest.main()
