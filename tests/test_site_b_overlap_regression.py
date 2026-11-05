"""Known provisional Site B geometry must eventually satisfy the overlap invariant."""
import pytest

from simulation.footprints import overlapping_pairs
from tools.mixed_traffic_report import build_engine, case_options


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


@pytest.mark.xfail(strict=True, reason="Same-lane spacing compares lateral bands in local lane coordinates, which is insufficient across a bend")
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
