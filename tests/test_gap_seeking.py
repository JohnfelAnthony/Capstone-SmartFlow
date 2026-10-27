"""Gap seeking and motorcycle filtering: sideways moves that are safe, bounded and calm."""
import json
import random
import unittest
from pathlib import Path

from simulation.mixed_traffic import lateral_bounds
from simulation.road_network import RoadNetwork, length
from simulation.scenario_config import TAGUM_PROVISIONAL_MIX
from simulation.traffic_engine import TrafficEngine
from tests.mixed_traffic_helpers import (assert_never_overlap, front_to_stop_line, hold_green, junction_network, place,
                                         started_engine)

NETWORK_2J = Path(__file__).resolve().parents[1]/"data"/"networks"/"tagum_network_2j.json"
THROUGH, LEFT = ["wf", "er"], ["wf", "nr"]


class NoFilteringEngine(TrafficEngine):
    def _decide_lateral(self, vehicle, lane):
        return None


def tagum_2j(**config):
    engine = TrafficEngine(seed=101, network=RoadNetwork(json.loads(NETWORK_2J.read_text(encoding="utf-8"))))
    engine.configure(**{"traffic_density": "medium", "vehicle_mix": dict(TAGUM_PROVISIONAL_MIX), **config})
    return engine


class GapSeekingTests(unittest.TestCase):
    def red_engine(self, engine_class=TrafficEngine, **network_options):
        network = junction_network(**network_options)
        engine = engine_class(seed=7, network=network)
        engine.configure(traffic_density="none", pedestrian_density="none")
        engine.driver_variation_scale = 0
        engine.start(600)
        hold_green(engine, "j", "north")
        return engine

    def queue_three_cars(self, engine, lateral):
        return [place(engine, THROUGH, "car", from_stop_line=distance, lateral=lateral) for distance in (0.0, 6.5, 13.0)]

    def test_motorcycle_moves_aside_and_filters_to_the_stop_line(self):
        engine = self.red_engine()
        self.queue_three_cars(engine, -0.65)
        motorcycle = place(engine, THROUGH, "motorcycle", from_stop_line=40, lateral=0.0, speed=5)
        assert_never_overlap(self, engine, 600, every=5)
        self.assertLessEqual(front_to_stop_line(engine, motorcycle), 1.0)

    def test_motorcycle_stays_behind_when_the_gap_is_too_narrow(self):
        engine = self.red_engine(width_per_direction_m=2.8)
        cars = self.queue_three_cars(engine, lateral_bounds(2.8, 1.8)[0])
        motorcycle = place(engine, THROUGH, "motorcycle", from_stop_line=40, lateral=0.0, speed=5)
        assert_never_overlap(self, engine, 600, every=5)
        last = min(cars, key=lambda car: car.position)
        self.assertLessEqual(motorcycle.position+motorcycle.length/2, last.position-last.length/2)

    def test_motorcycle_starts_a_move_from_the_kerb_edge(self):
        engine = self.red_engine()
        # Two tricycles queued at the kerb: moving aside gains about 5 m of room, past the 2 m threshold (one tricycle
        # would offer 3 m minus a 2.3 m move cost, which the provisional values rightly ignore).
        place(engine, THROUGH, "tricycle", from_stop_line=0, lateral=0.85)
        place(engine, THROUGH, "tricycle", from_stop_line=4.5, lateral=0.85)
        motorcycle = place(engine, THROUGH, "motorcycle", from_stop_line=9.0, lateral=1.15)
        assert_never_overlap(self, engine, 200)
        self.assertLessEqual(front_to_stop_line(engine, motorcycle), 1.0)
        self.assertLess(motorcycle.lateral, 0)

    def lateral_trace(self, engine, ticks):
        """Per tick: (vehicle, lane, lateral, speed, limit) at the tick start, then the lateral after it."""
        for _ in range(ticks):
            before = {vehicle.id: (vehicle.lane_id, vehicle.connector is None, vehicle.lateral, vehicle.speed, engine._lateral_speed_limit(vehicle), vehicle.vehicle_type)
                      for vehicle in engine.vehicles.values()}
            engine.step(1)
            for vehicle in engine.vehicles.values():
                if vehicle.id in before and before[vehicle.id][1] and vehicle.connector is None and before[vehicle.id][0] == vehicle.lane_id:
                    yield vehicle, before[vehicle.id], vehicle.lateral

    def test_lateral_motion_respects_speed_limits_and_does_not_jitter(self):
        engine = tagum_2j()
        engine.start(300)
        reversals: dict[str, list[float]] = {}
        last_sign: dict[str, int] = {}
        for vehicle, (_, _, lateral, _, limit, _), after in self.lateral_trace(engine, 3000):
            self.assertLessEqual(abs(after-lateral), limit*0.1+1e-9, vehicle.id)
            sign = (vehicle.lateral_speed > 0)-(vehicle.lateral_speed < 0)
            if sign:
                if last_sign.get(vehicle.id, sign) != sign:
                    reversals.setdefault(vehicle.id, []).append(engine.simulation_time)
                last_sign[vehicle.id] = sign
        for identity, times in reversals.items():
            for index, time in enumerate(times):
                self.assertLessEqual(sum(1 for other in times[index:] if other < time+10), 2, identity)

    def test_stopped_cars_tricycles_buses_and_trucks_never_move_sideways(self):
        engine = tagum_2j()
        engine.start(300)
        checked = 0
        for vehicle, (_, _, lateral, speed, _, vehicle_type), after in self.lateral_trace(engine, 3000):
            if vehicle_type != "motorcycle" and speed == 0:
                checked += 1
                self.assertEqual(after, lateral, vehicle.id)
        self.assertGreater(checked, 0)

    def test_left_turners_wait_on_the_centre_line_side(self):
        engine = self.red_engine(lanes_tag="4")
        car = place(engine, LEFT, "car", from_stop_line=25, lateral=1.0, speed=5)
        engine.step(200)
        self.assertLess(car.lateral, 0)

    def test_bus_and_truck_moving_beside_stopped_traffic_never_overlap(self):
        for vehicle_type in ("bus", "truck"):
            with self.subTest(vehicle_type=vehicle_type):
                engine = self.red_engine(lanes_tag="4")
                self.queue_three_cars(engine, -2.3)
                place(engine, LEFT, vehicle_type, from_stop_line=60, lateral=1.35, speed=5)
                assert_never_overlap(self, engine, 400)

    def test_vehicle_near_the_lane_start_does_not_move_into_an_arriving_vehicle(self):
        engine = self.red_engine()
        hold_green(engine, "j", "west")
        car = place(engine, THROUGH, "car", from_stop_line=0, lateral=-0.65)
        engine._reserve(car, "j", "west")
        connector = engine.network.connector("wf", "er")
        car.connector, car.connector_position = connector, length(connector)-3
        car.connector_entry_lateral = car.connector_exit_lateral = car.lateral = car.lateral_target = -0.65
        # A stopped tricycle ahead on the kerb side makes the car's exit position the motorcycle's best gap.
        tricycle = engine.add_vehicle(["er"], vehicle_type="tricycle")
        tricycle.position, tricycle.lateral, tricycle.lateral_target = 14.0, 0.85, 0.85
        motorcycle = engine.add_vehicle(["er"], vehicle_type="motorcycle", speed=2)
        motorcycle.position, motorcycle.lateral, motorcycle.lateral_target = 3.0, 1.15, 1.15
        assert_never_overlap(self, engine, 200)

    def test_turning_bus_and_a_motorcycle_at_the_opposite_stop_line_never_touch(self):
        # On the 2-junction network a right-turning bus swings its rear about 1 m across the centre line beside the
        # opposite stop line, where a motorcycle may wait on the centre-line side.
        for motorcycle_first in (True, False):
            with self.subTest(motorcycle_first=motorcycle_first):
                engine = TrafficEngine(seed=7, network=RoadNetwork(json.loads(NETWORK_2J.read_text(encoding="utf-8"))))
                engine.configure(traffic_density="none", pedestrian_density="none")
                engine.driver_variation_scale = 0
                engine.start(600)
                node = engine.network.lanes["road0f"].target
                hold_green(engine, node, engine.network.lanes["road0f"].approach)
                motorcycle = place(engine, ["road5f", "road0r"], "motorcycle", from_stop_line=0 if motorcycle_first else 25,
                                   lateral=-1.15, speed=0 if motorcycle_first else 5)
                bus = place(engine, ["road0f", "road5r"], "bus", from_stop_line=5, lateral=-0.3, speed=4)
                assert_never_overlap(self, engine, 300)
                if motorcycle_first:
                    # The bus waits uncommitted for the motorcycle in its path; once the motorcycle has its green and goes,
                    # the bus turns on its next green.
                    self.assertIsNone(bus.reserved_junction)
                    hold_green(engine, node, engine.network.lanes["road5f"].approach)
                    assert_never_overlap(self, engine, 200)
                    hold_green(engine, node, engine.network.lanes["road0f"].approach)
                    assert_never_overlap(self, engine, 300)
                self.assertTrue(bus.id not in engine.vehicles or bus.lane_id == "road5r")

    def front_row_motorcycle_share(self, engine_class):
        motorcycles = total = 0
        weights = list(TAGUM_PROVISIONAL_MIX.values())
        for seed in range(1, 6):
            engine = self.red_engine(engine_class)
            classes = random.Random(seed)
            for tick in range(900):
                if tick % 20 == 0:
                    engine.add_vehicle(THROUGH, vehicle_type=classes.choices(list(TAGUM_PROVISIONAL_MIX), weights)[0], speed=5)
                engine.step(1)
            front_row = [vehicle for vehicle in engine.vehicles.values() if vehicle.connector is None and vehicle.speed <= 0.1
                         and vehicle.lane_id == "wf" and front_to_stop_line(engine, vehicle) <= 1.0]
            motorcycles += sum(vehicle.vehicle_type == "motorcycle" for vehicle in front_row)
            total += len(front_row)
        return motorcycles/total

    def test_filtering_raises_the_front_row_motorcycle_share(self):
        self.assertGreater(self.front_row_motorcycle_share(TrafficEngine), self.front_row_motorcycle_share(NoFilteringEngine))

    def test_closure_during_filtering_keeps_accounting_and_no_overlap(self):
        network = RoadNetwork(json.loads(NETWORK_2J.read_text(encoding="utf-8")))
        lane = network.incoming[TrafficEngine(seed=1, network=network).controlled_junction][0]
        engine = tagum_2j(events=[{"time": 60, "lane_id": lane, "closed": True}, {"time": 180, "lane_id": lane, "closed": False}])
        engine.start(240)
        assert_never_overlap(self, engine, 2400)
        self.assertEqual(engine._last_metrics["vehicle_conservation_error"], 0)
        self.assertEqual(engine._last_metrics["stuck_junction_vehicles"], 0)

    def test_very_high_demand_at_the_vehicle_cap_never_overlaps(self):
        engine = tagum_2j(traffic_density="very high", max_active_vehicles=120)
        engine.start(240)
        for _ in range(24):
            assert_never_overlap(self, engine, 100)
            self.assertEqual(engine._last_metrics["stuck_junction_vehicles"], 0)
            self.assertEqual(engine._last_metrics["gridlock_seconds"], 0)


if __name__ == "__main__":
    unittest.main()
