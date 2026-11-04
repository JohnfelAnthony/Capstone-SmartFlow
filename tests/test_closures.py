"""User-chosen road closures: validation, the divert rule, held vehicles and signals (engine native-9).

Lane ids on the test cross: `wf` is w -> j (an entry), `wr` is j -> w (an exit); likewise for e, n, s.
"""
import pytest

from simulation.scenario_config import DEFAULTS, validate_config
from simulation.traffic_engine import ENGINE_VERSION, TrafficEngine
from tests.mixed_traffic_helpers import junction_network

EXITS = ["er", "nr", "sr", "wr"]
ENTRIES = ["ef", "nf", "sf", "wf"]


def run_trips(trips, seconds=200, **config):
    engine = TrafficEngine(seed=7, network=junction_network())
    engine.configure(traffic_density="none", pedestrian_density="none", trips=trips, **config)
    engine.driver_variation_scale = 0
    engine.start(seconds)
    engine.step(int(seconds*10))
    return engine


def west_to_east(time=0.0):
    return {"time": time, "source": "w", "destination": "e"}


def test_engine_label_is_native_9():
    assert ENGINE_VERSION == "native-9"


@pytest.mark.parametrize("closed", [ENTRIES + EXITS, EXITS, ENTRIES])
def test_closures_leaving_no_legal_movement_are_refused(closed):
    with pytest.raises(ValueError, match="no legal movement"):
        validate_config(DEFAULTS, {"closed_lanes": closed}, junction_network())


def test_three_closed_roads_leave_no_movement_because_u_turns_are_not_allowed():
    three_roads = ["wf", "wr", "ef", "er", "nf", "nr"]
    with pytest.raises(ValueError, match="no legal movement"):
        validate_config(DEFAULTS, {"closed_lanes": three_roads}, junction_network())


def test_a_timed_closure_that_later_leaves_no_movement_is_refused():
    events = [{"time": 100, "lane_id": lane, "closed": True} for lane in EXITS]
    with pytest.raises(ValueError, match="no legal movement"):
        validate_config(DEFAULTS, {"events": events}, junction_network())


def test_two_closed_roads_and_one_direction_are_allowed():
    validated = validate_config(DEFAULTS, {"closed_lanes": ["wf", "wr", "ef", "er"]}, junction_network())
    assert validated["closed_lanes"] == ["ef", "er", "wf", "wr"]
    validate_config(DEFAULTS, {"closed_lanes": ["wf"]}, junction_network())


def test_route_accepts_several_destinations_and_returns_the_cheapest():
    network = junction_network()
    route = network.route("w", {"n", "s"})
    assert network.lanes[route[-1]].target in {"n", "s"}
    assert network.route("w", "e") == ["wf", "er"]


def test_unreachable_destination_at_spawn_diverts_to_an_open_exit():
    engine = run_trips([west_to_east()], closed_lanes=["er"])
    metrics = engine._last_metrics
    assert (metrics["throughput"], metrics["diverted_vehicles"]) == (1, 1)
    assert metrics["lanes"]["er"]["exits"] == 0 and metrics["unfinished_vehicles"] == 0


def test_vehicle_at_its_last_junction_diverts_when_its_exit_closes_mid_trip():
    engine = run_trips([west_to_east()], events=[{"time": 3, "lane_id": "er", "closed": True}])
    metrics = engine._last_metrics
    assert (metrics["throughput"], metrics["diverted_vehicles"], metrics["reroutes"]) == (1, 1, 1)
    assert metrics["lanes"]["er"]["exits"] == 0


def test_a_vehicle_is_counted_as_diverted_once():
    engine = run_trips([west_to_east()], events=[{"time": 3, "lane_id": "er", "closed": True},
                                                 {"time": 6, "lane_id": "nr", "closed": True}])
    assert engine._last_metrics["diverted_vehicles"] == 1


def test_runs_with_a_reachable_destination_count_no_diversion():
    engine = run_trips([west_to_east()], closed_lanes=["nr"])
    assert engine._last_metrics["diverted_vehicles"] == 0 and engine._last_metrics["throughput"] == 1


def test_demand_whose_entry_road_is_closed_is_reported_as_blocked():
    engine = run_trips([west_to_east(), west_to_east(5.0), {"time": 0, "source": "n", "destination": "s"}], closed_lanes=["wf"])
    metrics = engine._last_metrics
    assert metrics["closure_blocked_vehicles"] == 2 and metrics["throughput"] == 1
    assert metrics["pending_demand"] == 2 and metrics["vehicle_conservation_error"] == 0


def test_blocked_demand_clears_when_a_timed_closure_ends():
    engine = run_trips([west_to_east()], seconds=120, events=[{"time": 0, "lane_id": "wf", "closed": True},
                                                              {"time": 30, "lane_id": "wf", "closed": False}])
    assert engine._last_metrics["closure_blocked_vehicles"] == 0 and engine._last_metrics["throughput"] == 1


def test_a_source_with_no_open_exit_is_blocked_even_when_its_entry_is_open():
    engine = run_trips([west_to_east()], closed_lanes=["er", "nr", "sr"])
    assert engine._last_metrics["closure_blocked_vehicles"] == 1


def test_vehicle_with_no_open_exit_is_reported_as_held_and_then_stuck():
    engine = run_trips([west_to_east()], seconds=100, events=[{"time": 3, "lane_id": lane, "closed": True} for lane in ("er", "nr", "sr")])
    metrics = engine._last_metrics
    assert metrics["closure_held_vehicles"] == 1
    assert metrics["stuck_junction_vehicles"] == 1


def test_an_ordinary_red_wait_is_not_reported_as_held():
    engine = run_trips([west_to_east()], seconds=100)
    assert engine._last_metrics["closure_held_vehicles"] == 0


def test_signal_skips_a_phase_whose_approaches_are_all_closed():
    engine = TrafficEngine(seed=7, network=junction_network())
    engine.configure(traffic_density="none", pedestrian_density="none", closed_lanes=["wf"])
    engine.start(300)
    served = set()
    for _ in range(3000):
        engine.step(1)
        served.add(engine.signals["j"].family)
    assert "west" not in served and {"north", "east", "south"} <= served


def test_signal_leaves_a_green_whose_approach_closes():
    engine = TrafficEngine(seed=7, network=junction_network())
    engine.configure(traffic_density="none", pedestrian_density="none", signal_plans={"j": {"phase_order": ["west", "north", "east", "south", "pedestrian"], "green_seconds": 40, "maximum_green": 60}},
                     events=[{"time": 15, "lane_id": "wf", "closed": True}])
    engine.start(200)
    engine.step(int(14/0.1))
    signal = engine.signals["j"]
    assert signal.family == "west"
    engine.step(int(12/0.1))
    assert signal.family != "west"


def test_group_phase_is_dead_only_when_every_member_is_closed():
    engine = TrafficEngine(seed=7, network=junction_network())
    plan = {"j": {"phase_order": [["north", "south"], "east", "west", "pedestrian"]}}
    engine.configure(traffic_density="none", pedestrian_density="none", signal_plans=plan, closed_lanes=["nf"])
    assert engine.signals["j"].dead == frozenset()
    engine.configure(closed_lanes=["nf", "sf"])
    assert engine.signals["j"].dead == {"north+south"}


def test_rl_request_for_a_closed_phase_is_refused_and_recorded_as_an_override():
    engine = TrafficEngine(seed=7, network=junction_network())
    engine.configure(traffic_density="none", pedestrian_density="none", closed_lanes=["ef"])
    engine.configure_rl_control()
    engine.start(60)
    slot = list(engine.signals["j"].approaches).index("east")
    result = engine.apply_rl_action(f"SERVE_PHASE_{slot+1}")
    assert result == {"applied": False, "reason": "closed_approach"}
    assert engine.safety_overrides == 1
    assert engine.last_safety_override["reason"] == "closed_approach" and engine.last_safety_override["service"] == "east"
    assert engine.signals["j"].pending is None


def test_closing_and_reopening_a_lane_by_hand_updates_the_dead_phases():
    engine = TrafficEngine(seed=7, network=junction_network())
    engine.configure(traffic_density="none", pedestrian_density="none")
    engine.start(60)
    engine.close_lane("wf")
    assert engine.signals["j"].dead == {"west"}
    engine.close_lane("wf", False)
    assert engine.signals["j"].dead == frozenset()
