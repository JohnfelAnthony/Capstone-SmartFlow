"""Unsignalized first-come traffic behaviour on synthetic junctions."""
import os
import unittest

import pytest

from simulation.footprints import state_digest
from tests.mixed_traffic_helpers import assert_never_overlap, busy_engine, junction_network, place, started_engine

FIRST_COME = {"signal_plans": {"j": {"mode": "first_come"}}}


def test_lone_car_can_reserve_without_a_stop():
    engine = started_engine(junction_network(), **FIRST_COME)
    vehicle = place(engine, ["wf", "er"], "car", from_stop_line=12, lateral=0, speed=3)
    for _ in range(200):
        engine.step()
        if vehicle.reserved_junction:
            assert vehicle.stop_arrival is None
            return
    raise AssertionError("The lone car never entered")


def test_nonconflicting_opposite_movements_can_share_junction():
    engine = started_engine(junction_network(), **FIRST_COME)
    first = place(engine, ["wf", "er"], "car", from_stop_line=5, lateral=0, speed=3)
    second = place(engine, ["ef", "wr"], "car", from_stop_line=5, lateral=0, speed=3)
    for _ in range(200):
        engine.step()
        if first.reserved_junction == "j" and second.reserved_junction == "j":
            return
    raise AssertionError("Opposite through traffic never shared the junction")


def test_oncoming_through_cars_pass_each_other_inside_the_junction():
    engine = started_engine(junction_network(), **FIRST_COME)
    first = place(engine, ["wf", "er"], "car", from_stop_line=5, lateral=-0.65, speed=3)
    second = place(engine, ["ef", "wr"], "car", from_stop_line=5, lateral=-0.65, speed=3)
    for _ in range(300):
        engine.step()
        if first.route[0] == "er" and second.route[0] == "wr":
            return
    raise AssertionError("Oncoming through cars stopped face to face inside the junction")


def test_blocked_earlier_exit_does_not_hold_conflicting_car():
    engine = started_engine(junction_network(), routing_mode="static", **FIRST_COME)
    first = place(engine, ["nf", "er"], "car", from_stop_line=12, lateral=0, speed=3)
    second = place(engine, ["sf", "nr"], "car", from_stop_line=20, lateral=0, speed=3)
    engine.close_lane("er", True)
    for _ in range(300):
        engine.step()
        if second.reserved_junction == "j":
            assert first.reserved_junction is None
            return
    raise AssertionError("Blocked exit stranded the other approach")


def test_side_road_is_served_in_arrival_order_under_constant_main_road_flow():
    main = [{"time": t, "source": s, "destination": d, "vehicle_type": "car"}
            for t in range(0, 121, 2) for s, d in (("w", "e"), ("e", "w"))]
    side = {"time": 30, "source": "n", "destination": "s", "vehicle_type": "car"}
    engine = started_engine(junction_network(), trips=main + [side], routing_mode="static", **FIRST_COME)
    arrivals, entered = {}, {}
    for _ in range(1800):
        engine.step()
        for vehicle in engine.vehicles.values():
            if vehicle.approach_arrival is not None:
                arrivals.setdefault(vehicle.id, (vehicle.approach_arrival, vehicle.route[0]))
            if vehicle.reserved_junction == "j":
                entered.setdefault(vehicle.id, engine.simulation_time)
    north = next(vid for vid, (_, lane) in arrivals.items() if lane == "nf")
    north_arrival = arrivals[north][0]
    assert north in entered and entered[north] - north_arrival <= 15
    overtakers = [vid for vid, (arrival, lane) in arrivals.items()
                  if lane != "nf" and arrival > north_arrival + 2.0 and entered.get(vid, 1e9) < entered[north]]
    assert overtakers == []


def test_no_overlap_at_any_tick_at_high_demand():
    assert_never_overlap(unittest.TestCase(), busy_engine(junction_network(), **FIRST_COME), 6000)


# Hours of runtime: the oversaturated 1800 s run is opt-in so the normal suite stays near 20 minutes.
@pytest.mark.skipif(os.environ.get("SMARTFLOW_SLOW_TESTS") != "1", reason="set SMARTFLOW_SLOW_TESTS=1 to run")
def test_no_stuck_gridlock_or_lost_vehicles_over_1800_s():
    engine = busy_engine(junction_network(), **FIRST_COME)
    stuck = gridlock = 0
    for _ in range(1800):
        engine.step(10)
        stuck = max(stuck, engine._last_metrics["stuck_junction_vehicles"])
        gridlock = max(gridlock, engine._last_metrics["gridlock_seconds"])
    assert (stuck, gridlock) == (0, 0)
    assert engine._last_metrics["vehicle_conservation_error"] == 0


def test_same_seed_same_result():
    def digest():
        return state_digest(busy_engine(junction_network(), seed=101, density="medium", **FIRST_COME), 300)
    assert digest() == digest()
