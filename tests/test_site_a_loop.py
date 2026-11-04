"""Site A's West -> North side-street loop on the real installed network: detours, closures and the one-junction assumptions.

Lane ids: road2 is the study junction -> west loop junction piece (`road2r` runs towards the study junction), road4 is the
boundary stub beyond it, road1 is study junction -> north loop junction, road5 the north stub, road6 the loop street
(`road6f` runs from the west loop junction to the north one). boundary_2 is the west entry, boundary_1 the north, boundary_3 the east.
"""
import pytest

from services.movement_counts import approach_boundaries
from services.study_gate import study_routing_mode
from simulation.network_registry import engine_for_scenario, load_registered_network
from simulation.scenario_config import DEFAULTS, validate_config
from simulation.traffic_engine import TrafficEngine

WEST, NORTH, SOUTH, EAST = "boundary_2", "boundary_1", "boundary_0", "boundary_3"
SITE = "tagum_site_a"


def run_site_a(trips, seconds=400, **config):
    engine = TrafficEngine(seed=7, network=load_registered_network(SITE))
    engine.configure(traffic_density="none", pedestrian_density="none", trips=trips, routing_mode="static", **config)
    engine.driver_variation_scale = 0
    engine.start(seconds)
    engine.step(int(seconds*10))
    return engine


def trip(time, source, destination):
    return {"time": time, "source": source, "destination": destination, "vehicle_type": "car"}


def test_site_a_keeps_the_study_junction_first_and_the_loop_junctions_unsignalled():
    network = load_registered_network(SITE)
    assert network.intersections[0] == "tagum_site_a_j" and len(network.intersections) == 3
    engine = TrafficEngine(network=network)
    modes = {node: signal.mode for node, signal in engine.signals.items()}
    assert modes == {"tagum_site_a_j": "signalized", "tagum_site_a_j2": "first_come", "tagum_site_a_j3": "first_come"}
    assert engine.controlled_junction == "tagum_site_a_j"


def test_route_west_to_north_is_normally_through_the_study_junction():
    assert "road2r" in load_registered_network(SITE).route(WEST, NORTH)


def test_closed_from_the_start_traffic_takes_the_loop_and_finishes():
    trips = [trip(second, WEST, NORTH) for second in (1, 8, 15)]
    engine = run_site_a(trips, closed_lanes=["road2r"])
    metrics = engine._last_metrics
    assert (metrics["throughput"], metrics["unfinished_vehicles"], metrics["diverted_vehicles"]) == (3, 0, 0)
    assert metrics["lanes"]["road6f"]["exits"] == 3 and metrics["lanes"]["road2r"]["exits"] == 0


def test_closed_mid_run_a_vehicle_already_underway_reroutes_onto_the_loop():
    engine = run_site_a([trip(0, WEST, EAST)], events=[{"time": 2, "lane_id": "road2r", "closed": True}])
    metrics = engine._last_metrics
    assert (metrics["throughput"], metrics["reroutes"], metrics["diverted_vehicles"]) == (1, 1, 0)
    assert metrics["lanes"]["road6f"]["exits"] == 1 and metrics["lanes"]["road2r"]["exits"] == 0


def test_opposite_direction_closure_also_uses_the_loop():
    engine = run_site_a([trip(1, NORTH, WEST), trip(10, EAST, WEST)], closed_lanes=["road2f"])
    metrics = engine._last_metrics
    assert metrics["throughput"] == 2 and metrics["lanes"]["road6r"]["exits"] == 2 and metrics["diverted_vehicles"] == 0


def test_a_closure_outside_the_loop_diverts_to_an_open_exit():
    engine = run_site_a([trip(1, WEST, EAST), trip(8, NORTH, EAST)], closed_lanes=["road3f"])
    metrics = engine._last_metrics
    assert (metrics["throughput"], metrics["diverted_vehicles"]) == (2, 2)
    assert metrics["lanes"]["road3f"]["exits"] == 0 and metrics["unfinished_vehicles"] == 0


def test_closing_every_lane_is_refused_with_a_plain_message():
    network = load_registered_network(SITE)
    with pytest.raises(ValueError, match="no legal movement"):
        validate_config(DEFAULTS, {"closed_lanes": list(network.lanes)}, network)


def test_closing_the_loop_itself_and_its_ends_leaves_the_four_legs_working():
    network = load_registered_network(SITE)
    validate_config(DEFAULTS, {"closed_lanes": ["road6f", "road6r"]}, network)


def test_every_leg_is_still_matched_to_its_boundary_through_the_loop_junctions():
    network = load_registered_network(SITE)
    legs = approach_boundaries(network)
    assert legs == {"south": (SOUTH, SOUTH), "north": (NORTH, NORTH), "west": (WEST, WEST), "east": (EAST, EAST)}


def test_the_loop_has_a_detour_for_each_piece_it_bypasses():
    from services.closure_check import closure_report
    pieces = closure_report(load_registered_network(SITE), [])["pieces"]
    assert pieces["road2r"]["has_detour"] and pieces["road2f"]["has_detour"] and pieces["road1r"]["has_detour"]
    assert not pieces["road3f"]["has_detour"] and not pieces["road4r"]["has_detour"]


def test_study_site_validation_and_reference_runs_use_static_routing():
    assert study_routing_mode(SITE) == "static" and study_routing_mode("tagum_network") is None
    scenario = {"network_id": SITE, "engine_config": {"routing_mode": "adaptive"}}
    assert engine_for_scenario(scenario, seed=101).config["routing_mode"] == "adaptive"
    assert engine_for_scenario(scenario, seed=101, routing_mode="static").config["routing_mode"] == "static"


def test_site_validation_builds_its_engines_with_static_routing():
    from services.site_simulation import validation_engine
    scenario = {"network_id": SITE, "engine_config": {"routing_mode": "adaptive"}}
    assert validation_engine(scenario, 101).config["routing_mode"] == "static"


def test_static_routing_never_sends_open_road_traffic_onto_the_loop():
    from tests.mixed_traffic_helpers import busy_engine
    engine = busy_engine(load_registered_network(SITE), seed=101, density="medium", routing_mode="static")
    engine.step(6000)
    assert engine._last_metrics["reroutes"] == 0
    assert engine._last_metrics["lanes"]["road6f"]["exits"] == 0 and engine._last_metrics["lanes"]["road6r"]["exits"] == 0
