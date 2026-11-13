"""Negotiated no-signal at the study junction (docs/superpowers/specs/2026-11-12-negotiated-no-signal-design.md).

Only the controlled junction, only under the No signal controller: crossing movements share the middle, a newcomer
needs a big enough gap to vehicles still approaching (smaller for motorcycles, shrinking while it waits), at most
NEGOTIATED_MAX_INSIDE vehicles are inside, and a pedestrian steps out after NEGOTIATED_PEDESTRIAN_PATIENCE_S.
"""
import math

import pytest

from services.native_controller import apply_controller
from simulation.footprints import overlapping_pairs
from simulation.traffic_engine import (NEGOTIATED_MAX_INSIDE, NEGOTIATED_PEDESTRIAN_PATIENCE_S, NO_SIGNAL_BEHAVIOUR,
                                       Pedestrian, TrafficEngine)
from tests.mixed_traffic_helpers import junction_network, place


def no_signal_engine(**config):
    engine = TrafficEngine(seed=7, network=junction_network())
    engine.configure(**{"traffic_density": "none", "pedestrian_density": "none", **config})
    engine.driver_variation_scale = 0
    apply_controller(engine, "no-signal")
    engine.start(600)
    return engine


def inside(engine):
    return [vehicle for vehicle in engine.vehicles.values() if vehicle.reserved_junction == "j"]


def test_a_crossing_vehicle_enters_while_an_earlier_one_has_not_passed_their_crossing_point():
    engine = no_signal_engine()
    west = place(engine, ["wf", "er"], "car", from_stop_line=4, lateral=0, speed=4)
    south = place(engine, ["sf", "nr"], "car", from_stop_line=12, lateral=0, speed=4)
    entered_while_crossing = None
    for _ in range(400):
        engine.step(1)
        assert overlapping_pairs(engine.vehicle_records()) == [], f"overlap at t={engine.simulation_time}"
        if entered_while_crossing is None and south.reserved_junction == "j":
            entered_while_crossing = (west.reserved_junction == "j" and len(west.route) > 1
                                      and engine._sweeps_intersect(south, west, remaining=True))
    assert entered_while_crossing, "the old first-come rule kept it at the line until the crossing path was free"
    assert west.id not in engine.vehicles and south.id not in engine.vehicles


def test_a_vehicle_not_yet_inside_crosses_every_path_and_once_inside_only_those_it_touches():
    """The conservative rule (owner, 2026-11-13): before it is inside, a vehicle counts as crossing every path from that path's start;
    once inside, only paths it really touches count. (Counting only touching paths from the start let the junction lock in 3 of 12 runs.)"""
    exits = {"w": ["er", "nr", "sr"], "s": ["nr", "er", "wr"], "e": ["wr", "nr", "sr"], "n": ["sr", "er", "wr"]}
    movements = [(arm, exit_lane) for arm in exits for exit_lane in exits[arm]]
    apart = 0
    for (arm, exit_lane), (other_arm, other_exit) in ((a, b) for a in movements for b in movements if a[0] != b[0]):
        engine = no_signal_engine()
        first = place(engine, [arm+"f", exit_lane], "car", from_stop_line=20, lateral=0)
        second = place(engine, [other_arm+"f", other_exit], "car", from_stop_line=20, lateral=0)
        if engine._sweeps_intersect(first, second):
            continue
        apart += 1
        own, other = (engine._sweep_for(vehicle, 0, engine._exit_lateral(vehicle)) for vehicle in (first, second))
        assert engine._first_conflict(own, other, -math.inf) == own[0][0] == engine._first_conflict_scan(own, other, -math.inf)
        inside = other[0][0]  # the other vehicle has entered: from here on only bodies that touch count
        assert engine._first_conflict(own, other, inside) is None, (first.route, second.route)
        assert engine._first_conflict_scan(own, other, inside) is None, (first.route, second.route)
    assert apart, "this junction has non-crossing movements from different approaches (for example two right turns)"


def test_the_first_committed_vehicle_is_not_held_by_the_path_of_one_holding_for_it():
    """Site A seed 102 froze 8 committed vehicles at the line: the first one's footprint check waited on the path of a later one
    merging into the same exit, while that one held for it (car-53 road3r and car-57 road0r, both to road1f)."""
    from tests.test_site_b_measured_layout import to_boundary
    from tools.mixed_traffic_report import build_engine
    engine = build_engine("siteA", "none", {"car": 1}, 600, 1, no_signal=True)
    engine.driver_variation_scale = 0
    node = engine.controlled_junction
    first = place(engine, to_boundary(engine.network, ["road3r", "road1f"]), "car", from_stop_line=-4.877, lateral=0.98, speed=0)
    later = place(engine, to_boundary(engine.network, ["road0r", "road1f"]), "motorcycle", from_stop_line=-4.3, lateral=2.8, speed=0)
    # Their positions in that run: both past the set-back stop line. Both committed while standing, the first one first (as the engine commits them).
    for vehicle in (first, later):
        engine._reserve(vehicle, node, engine.network.lanes[vehicle.route[0]].approach)
        engine._sweeps[vehicle.id] = engine._sweep_for(vehicle, vehicle.lateral, engine._exit_lateral(vehicle))
    assert engine._hold_for(later, first) is not None
    for _ in range(300):
        engine.step(1)
        assert overlapping_pairs(engine.vehicle_records()) == [], f"overlap at t={engine.simulation_time}"
    assert first.reserved_junction != node and later.reserved_junction != node


def gap_verdict(seconds_away: float, vehicle_type: str, waited: float = 0.0) -> bool:
    """A vehicle stopped at the south line; a car approaches from the west at 4 m/s, still uncommitted, `seconds_away` from where it counts
    as crossing (by the conservative rule, the start of its path through the junction). Does the gap rule let the first one in? Asked of the
    rule directly: stepping would let a close car commit first, and a committed car is handled by holding short instead."""
    engine = no_signal_engine()
    side = place(engine, ["sf", "nr"], vehicle_type, from_stop_line=0.3, lateral=0, speed=0)
    side.stop_arrival = engine.simulation_time-waited
    approaching = place(engine, ["wf", "er"], "car", from_stop_line=0, lateral=0, speed=4)
    lane = engine.network.lanes["wf"]
    crossing = engine._first_conflict_scan(engine._sweep_for(approaching, 0, engine._exit_lateral(approaching)),
                                           engine._sweep_for(side, 0, engine._exit_lateral(side)), -math.inf)
    at_stop_line = lane.length-approaching.position+crossing  # metres to the crossing from the stop line
    approaching.position -= 4*seconds_away-at_stop_line
    assert approaching.position <= lane.length-approaching.length/2, "closer than a car can be while still on its approach lane"
    approaching.approach_arrival = engine.simulation_time
    return engine._negotiated_permission(side, engine.network.lanes["sf"])


def test_a_motorcycle_takes_a_gap_a_car_refuses_and_a_long_wait_shrinks_the_gap():
    distances = [quarters/4 for quarters in range(11, 41)]  # 2.75 .. 10 s at 4 m/s to the crossing; nearer, a car is already past its lane end
    cars = [gap_verdict(seconds, "car") for seconds in distances]
    motorcycles = [gap_verdict(seconds, "motorcycle") for seconds in distances]
    impatient_cars = [gap_verdict(seconds, "car", waited=15.0) for seconds in distances]
    assert not cars[0] and cars[-1], "a close vehicle stops a car; a distant one does not"
    assert all(motorcycle or not car for car, motorcycle in zip(cars, motorcycles)), "a motorcycle never refuses a gap a car takes"
    assert any(motorcycle and not car for car, motorcycle in zip(cars, motorcycles))
    assert any(impatient and not car for car, impatient in zip(cars, impatient_cars))


def test_critical_gap_by_class_and_waiting_time():
    engine = no_signal_engine()
    gaps = {kind: engine._critical_gap(place(engine, [arm+"f", "er" if arm != "e" else "wr"], kind, from_stop_line=1, lateral=0))
            for kind, arm in (("motorcycle", "w"), ("car", "s"), ("bus", "n"))}
    assert gaps == {"motorcycle": 2.0, "car": 3.0, "bus": 3.5}
    car = next(vehicle for vehicle in engine.vehicles.values() if vehicle.vehicle_type == "car")
    car.stop_arrival = engine.simulation_time-10
    assert engine._critical_gap(car) == pytest.approx(2.0)
    car.stop_arrival = engine.simulation_time-100
    assert engine._critical_gap(car) == pytest.approx(1.5)


def test_busy_no_signal_junction_shares_the_middle_within_the_limit_and_keeps_moving():
    engine = no_signal_engine(traffic_density="high")
    most_inside, crossing_inside = 0, False
    for tick in range(3000):
        engine.step(1)
        occupants = inside(engine)
        most_inside = max(most_inside, len(occupants))
        approaches = {engine.network.lanes[vehicle.route[0]].approach for vehicle in occupants}
        crossing_inside |= len(approaches) >= 2
        if tick % 10 == 0:
            assert overlapping_pairs(engine.vehicle_records()) == [], f"overlap at t={engine.simulation_time}"
    assert most_inside <= NEGOTIATED_MAX_INSIDE
    assert crossing_inside
    assert engine.completed > 100
    assert engine._stalled_vehicle_count() == 0


def test_a_pedestrian_steps_out_after_waiting_even_while_vehicles_hold_the_junction():
    engine = no_signal_engine()
    engine.reservations["j"] = {"held-by-traffic"}  # vehicles always inside
    pedestrian = engine.pedestrians["p"] = Pedestrian("p", "j")
    engine.step(int((NEGOTIATED_PEDESTRIAN_PATIENCE_S-0.5)/0.1))
    assert not pedestrian.crossing
    engine.step(10)
    assert pedestrian.crossing


def test_only_the_controlled_junction_under_no_signal_negotiates_and_recordings_say_so():
    engine = TrafficEngine(seed=7, network=junction_network())
    engine.configure(traffic_density="none", pedestrian_density="none", signal_plans={"j": {"mode": "first_come"}})
    engine.start(60)
    assert engine._negotiated_junction() is None, "an explicit first-come plan (a neighbour) keeps the orderly rule"
    assert "no_signal_behaviour" not in engine.experiment_metadata()["control"]
    engine = no_signal_engine()
    assert engine._negotiated_junction() == "j"
    behaviour = engine.experiment_metadata()["control"]["no_signal_behaviour"]
    assert behaviour["version"] == NO_SIGNAL_BEHAVIOUR == "negotiated-v1"
    assert (behaviour["junction"], behaviour["max_inside"], behaviour["critical_gap_s"]["motorcycle"]) == ("j", 8, 2.0)


def test_a_crowded_sharp_turn_does_not_starve_the_driver_who_waited_longest():
    """Site B's sharp right turn takes one vehicle at a time; under a dense stream the one that stopped first must not wait while later ones go."""
    from tests.test_site_b_measured_layout import NETWORK, build_engine, to_boundary
    engine = build_engine("siteB", "none", {"car": 1}, 600, 1, no_signal=True)
    classes = ["motorcycle", "motorcycle", "tricycle", "car", "motorcycle", "motorcycle", "tricycle", "motorcycle"]
    added, longest_line_wait = 0, 0.0
    while engine.simulation_time < 600 and (added < 32 or engine.vehicles):
        if added < 32 and engine.simulation_time >= added*1.2 and engine.add_vehicle(to_boundary(NETWORK, ["road2f", "road1f"]), vehicle_type=classes[added % len(classes)]):
            added += 1
        engine.step(1)
        longest_line_wait = max([longest_line_wait, *[engine.simulation_time-vehicle.stop_arrival for vehicle in engine.vehicles.values()
                                                      if vehicle.stop_arrival is not None and vehicle.reserved_junction is None]])
    assert added == 32 and not engine.vehicles
    assert longest_line_wait < 150  # the rule this replaced left one driver 171 s at the line; with it, 116 s


def test_the_junction_does_not_lock_where_counting_only_touching_paths_did():
    """Site B medium, seed 101: counting only paths a waiting vehicle really touches (tried 2026-11-13) let car-20 follow car-33, car-33 hold
    for car-11 and car-11 hold for car-20, so 5 vehicles stood inside from about t=167 s. The conservative rule must keep this run moving."""
    from tools.mixed_traffic_report import build_engine, case_options
    network, density, mix, options = case_options("siteB-medium-nosignal")
    engine = build_engine(network, density, mix, 600, 101, **options)
    node, standing = engine.controlled_junction, 0.0
    while engine.simulation_time < 300:
        engine.step(1)
        inside = [engine.vehicles[identity] for identity in engine.reservations.get(node, ()) if identity in engine.vehicles]
        standing = standing+0.1 if inside and all(vehicle.speed < 0.05 for vehicle in inside) else 0.0
        assert standing < 20, f"everyone inside the junction has stood for 20 s at t={engine.simulation_time:.1f}"
