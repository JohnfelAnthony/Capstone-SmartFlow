"""Known provisional Site B geometry must eventually satisfy the overlap invariant."""
import pytest

from simulation.footprints import overlapping_pairs
from tools.mixed_traffic_report import build_engine, case_options


def to_boundary(network, route):
    """The route continued by the cheapest way on to a boundary, for tests that place a vehicle on a turn at a junction that no longer ends at one."""
    return route + network.route(network.lanes[route[-1]].target, set(network.boundaries), previous=route[-1])


# The measured layout separates the carriageways and sets stop lines back, which removes these overlaps at medium traffic.
@pytest.mark.parametrize("seed,duration", [(101, 60), (102, 60), (101, 120), (102, 120)])
def test_site_b_no_signal_has_no_overlapping_vehicles(seed, duration):
    network, density, mix, options = case_options("siteB-medium-nosignal")
    engine = build_engine(network, density, mix, duration, seed, **options)
    while engine.status == "running":
        engine.step(1)
        assert not overlapping_pairs(engine.vehicle_records()), f"overlap at {engine.simulation_time}s"


# The engine limits below were found on the OSM corridor and stay pinned to that history. Seed 102 used to overlap at 45.4 s (same-lane
# motorcycles on a curved approach); a lane with a bend now keeps its bodies further from the lane edges (TrafficEngine.lateral_limits), which
# removed that run's overlap. The isolated two-motorcycle case below still fails, so the same-lane bend limit itself is not closed.
@pytest.mark.parametrize("seed,duration", [(101, 60), (102, 60)])
def test_osm_corridor_overlaps_remain_documented(seed, duration):
    _, density, mix, options = case_options("siteB-medium-nosignal")
    engine = build_engine("siteB-osm-corridor", density, mix, duration, seed, **options)
    while engine.status == "running":
        engine.step(1)
        assert not overlapping_pairs(engine.vehicle_records()), f"overlap at {engine.simulation_time}s"


def test_two_motorcycles_on_a_bend_keep_their_world_footprints_separate():
    _, _, mix, options = case_options("siteB-medium-nosignal")
    engine = build_engine("siteB-osm-corridor", "none", mix, 60, 102, **options)
    engine._decide_lateral = lambda *args: None
    engine._step_lateral = lambda *args: None
    leader = engine.add_vehicle(["road6r", "road2f", "road4f"], vehicle_type="motorcycle")
    leader.position, leader.lateral, leader.lateral_target, leader.speed = 231.928143, -.15, -.15, 0
    follower = engine.add_vehicle(["road6r", "road7f"], vehicle_type="motorcycle")  # added once the leader has left the lane start
    follower.position, follower.lateral, follower.lateral_target, follower.speed = 230.716, 1.1, 1.1, 1.68
    assert not overlapping_pairs(engine.vehicle_records())
    engine._move_vehicle(follower)
    assert not overlapping_pairs(engine.vehicle_records())


def test_experimental_guard_blocks_the_isolated_bend_overlap():
    from tools.mixed_traffic_report import load_network
    from tools.site_b_guard_prototype import PrototypeCurvedLaneGuard

    engine = PrototypeCurvedLaneGuard(network=load_network("siteB-osm-corridor"), seed=102)
    engine.configure(traffic_density="none", pedestrian_density="none")
    engine.enable_no_signal_control()
    engine.start(60)
    engine._decide_lateral = lambda *args: None
    engine._step_lateral = lambda *args: None
    leader = engine.add_vehicle(["road6r", "road2f", "road4f"], vehicle_type="motorcycle")
    leader.position, leader.lateral, leader.lateral_target, leader.speed = 231.928143, -.15, -.15, 0
    follower = engine.add_vehicle(["road6r", "road7f"], vehicle_type="motorcycle")  # added once the leader has left the lane start
    follower.position, follower.lateral, follower.lateral_target, follower.speed = 230.716, 1.1, 1.1, 1.68
    assert not overlapping_pairs(engine.vehicle_records())
    engine._move_vehicle(follower)
    assert not overlapping_pairs(engine.vehicle_records())


@pytest.mark.xfail(strict=True, reason="The experimental guard holds opposing cars on intersecting lane geometry, so both wait forever")
def test_experimental_guard_opposing_lanes_can_make_progress():
    from tools.mixed_traffic_report import load_network
    from tools.site_b_guard_prototype import PrototypeCurvedLaneGuard

    engine = PrototypeCurvedLaneGuard(network=load_network("siteB-osm-corridor"), seed=101)
    engine.configure(traffic_density="none", pedestrian_density="none")
    engine.enable_no_signal_control()
    engine.start(60)
    first = engine.add_vehicle(["road3f", "road8f"], vehicle_type="car")
    second = engine.add_vehicle(["road2f", "road4f"], vehicle_type="car")
    first.position, first.lateral, first.lateral_target, first.speed = 145.08473813626634, -3.95, -3.95, 0
    second.position, second.lateral, second.lateral_target, second.speed = 4.314513959871041, -.65, -.65, 0
    assert not overlapping_pairs(engine.vehicle_records())
    first_step = engine._sweep_clear_travel(first, engine.network.lanes[first.lane_id], .1)
    second_step = engine._sweep_clear_travel(second, engine.network.lanes[second.lane_id], .1)
    assert first_step > 0 or second_step > 0


def test_a_motorcycle_does_not_drift_into_the_path_of_a_truck_already_committed_beside_it():
    """Seed 102, high traffic, fixed-time, 333.9 s: a truck committed to its left turn from a lane band away, then a motorcycle
    standing at the line (its front ahead of the truck's) edged sideways into the swing of the truck's rear. Reproduced from the traced state."""
    from simulation.network_registry import load_registered_network
    from simulation.traffic_engine import TrafficEngine
    engine = TrafficEngine(seed=7, network=load_registered_network("tagum_site_b"))
    engine.configure(traffic_density="none", pedestrian_density="none", routing_mode="static")
    engine.enable_no_signal_control()
    engine.driver_variation_scale = 0
    engine.start(120)
    motorcycle = engine.add_vehicle(to_boundary(engine.network, ["road2f", "road1f"]), vehicle_type="motorcycle", speed=0.27)
    truck = engine.add_vehicle(to_boundary(engine.network, ["road2f", "road0f"]), vehicle_type="truck", speed=1.9)
    truck.position, truck.lateral, truck.lateral_target = 115.3, -3.25, -3.25
    motorcycle.position, motorcycle.lateral, motorcycle.lateral_target, motorcycle.yaw = 119.93, -1.02, -1.85, -0.175
    lane = engine.network.lanes["road2f"]
    engine._reserve(truck, lane.target, lane.approach)  # what the truck's commit does
    truck.lateral_target, truck.yaw, truck.lateral_speed = truck.lateral, 0.0, 0.0
    engine._sweeps[truck.id] = engine._sweep_for(truck, truck.lateral, engine._exit_lateral(truck))
    for _ in range(300):
        engine.step(1)
        assert not overlapping_pairs(engine.vehicle_records()), f"overlap at {engine.simulation_time}s"
