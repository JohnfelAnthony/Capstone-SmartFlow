from copy import deepcopy

from simulation.network_registry import load_registered_network
from simulation.road_network import RoadNetwork
from simulation.traffic_engine import TrafficEngine


SITE_A = "tagum_site_a"
SITE_B = "tagum_site_b"
EAST, NORTH, WEST, SOUTH = "boundary_3", "boundary_1", "boundary_2", "boundary_0"


def site_engine(site=SITE_A, **settings):
    engine = TrafficEngine(network=load_registered_network(site))
    if settings:
        engine.configure(**settings)
    return engine


def test_arrival_keeps_main_route_when_reachable():
    engine = site_engine()
    route, diverting = engine.arrival_route(EAST, NORTH, vehicle_type="car", costs=None)
    assert route == ["road24r", "road3r", "road1f", "road5f", "road8f", "road12f"]
    assert not diverting


def test_arrival_nearest_exit_overrides_available_detour():
    engine = site_engine(closed_lanes=["road1f"], closure_responses={"road1f": "nearest_exit"})
    assert engine.network.route(EAST, NORTH, closed=engine.closed_lanes, vehicle_type="car") == [
        "road24r", "road21r", "road13r", "road12f",
    ]
    route, diverting = engine.arrival_route(EAST, NORTH, vehicle_type="car", costs=None)
    assert route == ["road24r", "road3r", "road0f", "road10f"]
    assert diverting and engine.network.lanes[route[-1]].target == SOUTH


def test_unreachable_destination_uses_non_generating_exit():
    engine = site_engine(closed_lanes=["road0f"])
    assert not engine.network.route(WEST, SOUTH, closed=engine.closed_lanes, vehicle_type="car")
    route, diverting = engine.arrival_route(WEST, SOUTH, vehicle_type="car", costs=None)
    assert route == ["road4r", "road6f", "road16f"]
    exit_id = engine.network.lanes[route[-1]].target
    assert diverting and exit_id in engine.network.boundaries and exit_id not in engine.network.demand_boundaries


def test_vehicle_class_and_turn_rules_are_respected():
    engine = site_engine(SITE_B)
    for vehicle_type in ("bus", "truck"):
        assert engine.arrival_route("boundary_9", "boundary_1", vehicle_type=vehicle_type, costs=None) == ([], False)
    car_route, diverting = engine.arrival_route("boundary_9", "boundary_1", vehicle_type="car", costs=None)
    assert car_route and not diverting

    payload = deepcopy(load_registered_network(SITE_A).payload)
    payload.setdefault("prohibited_turns", []).append(["road3r", "road1f"])
    engine = TrafficEngine(network=RoadNetwork(payload))
    route, diverting = engine.arrival_route(EAST, NORTH, vehicle_type="car", costs=None)
    assert route == ["road24r", "road21r", "road13r", "road12f"]
    assert not diverting


def test_arrival_does_not_mutate_network_or_inputs():
    engine = site_engine(closed_lanes=["road2r"], closure_responses={"road2r": "side_street_adaptive"})
    costs = engine._travel_costs()
    before = deepcopy((engine.network.payload, engine.config, engine.closed_lanes, costs))
    state = engine.random.getstate()
    route, diverting = engine.arrival_route(WEST, NORTH, vehicle_type="car", costs=costs)
    assert route and "road2r" not in route and not diverting
    assert (engine.network.payload, engine.config, engine.closed_lanes, costs) == before
    assert engine.random.getstate() == state
    assert not engine.vehicles and not engine.pending_demand and engine.ticks == 0
