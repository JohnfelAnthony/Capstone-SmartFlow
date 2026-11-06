"""Site A's West -> North side-street loop on the real installed network: detours, closures and the one-junction assumptions.

Lane ids: road2 is the study junction -> west loop junction piece (`road2r` runs towards the study junction), road4 is the
boundary stub beyond it, road1 is study junction -> north loop junction, road5 the north stub, road6 the loop street
(`road6f` runs from the west loop junction to the north one). boundary_2 is the west entry, boundary_1 the north, boundary_3 the east.
"""
import pytest

from services.movement_counts import approach_boundaries
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


def test_every_engine_at_the_study_site_uses_static_routing():
    scenario = {"network_id": SITE, "engine_config": {"routing_mode": "adaptive"}}
    assert engine_for_scenario(scenario, seed=101).config["routing_mode"] == "static"


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


def test_opposing_bodies_never_overlap_anywhere_on_the_loop_street_bend():
    """Straight bodies on a curved lane swing their ends sideways; at every stagger and every sideways position the engine allows, two opposing bodies must still be apart."""
    import math
    from simulation.footprints import rectangle, rectangles_overlap
    from simulation.road_network import sample
    from simulation.traffic_engine import VEHICLE_TYPES

    engine = TrafficEngine(network=load_registered_network(SITE))
    forward, backward = engine.network.lanes["road6f"], engine.network.lanes["road6r"]
    across = [(q, *sample(backward.shape, q)[:2]) for q in (index*0.25 for index in range(int(backward.length/0.25)+1))]

    def body(lane, position, spec, lateral):
        x, y, heading = sample(lane.shape, position)
        return rectangle(x+math.sin(heading)*lateral, y-math.cos(heading)*lateral, heading, spec["length"], spec["width"])

    overlaps = []
    kinds = sorted(VEHICLE_TYPES)
    for index, first in enumerate(kinds):
        for second in kinds[index:]:
            a_spec, b_spec = VEHICLE_TYPES[first], VEHICLE_TYPES[second]
            a_low = engine.lateral_limits("road6f", a_spec["width"])[0]
            b_low = engine.lateral_limits("road6r", b_spec["width"])[0]
            for a_lateral, b_lateral in ((a_low, b_low), (0.0, 0.0), (a_low, 0.0), (0.0, b_low)):
                for position in range(3, int(forward.length), 3):
                    x, y, _ = sample(forward.shape, position)
                    opposite = min(across, key=lambda row: (row[1]-x)**2+(row[2]-y)**2)[0]
                    for stagger in range(-12, 13):
                        if 0 <= opposite+stagger <= backward.length and rectangles_overlap(
                                body(forward, position, a_spec, a_lateral), body(backward, opposite+stagger, b_spec, b_lateral)):
                            overlaps.append((first, second, a_lateral, b_lateral, position, stagger))
    assert overlaps == [], f"{len(overlaps)} overlapping placements, first {overlaps[:3]}"


def test_only_a_bent_lane_gives_up_sideways_room():
    from simulation.road_network import body_swing
    assert body_swing([(0, 0), (50, 0), (100, 0)], 10.0) == 0.0
    import math
    arc = [(25*math.sin(angle/200*1.5), 25-25*math.cos(angle/200*1.5)) for angle in range(201)]
    assert body_swing(arc, 10.0) == pytest.approx(10.0**2/(8*25), rel=0.1)
    for site in ("tagum_site_b", "tagum_network"):
        engine = TrafficEngine(network=load_registered_network(site))
        assert all(engine._room_width[lane_id] == lane.width for lane_id, lane in engine.network.lanes.items())
    engine = TrafficEngine(network=load_registered_network(SITE))
    assert engine._room_width["road6f"] < engine.network.lanes["road6f"].width and engine._room_width["road2r"] == engine.network.lanes["road2r"].width


def test_a_bus_entering_the_short_west_stub_waits_for_a_bus_still_leaving_it_through_the_junction():
    """road4r is 15 m long, so the entry spot is within one body length of the junction: a vehicle in the connector with its rear still on the lane blocks the entry."""
    from tests.mixed_traffic_helpers import started_engine
    engine = started_engine(load_registered_network(SITE), routing_mode="static")
    leader = engine.add_vehicle(["road4r", "road6f", "road5f"], vehicle_type="bus", speed=3.0)
    leader.position = engine.network.lanes["road4r"].length-8
    for _ in range(300):
        engine.step(1)
        if leader.connector is not None and leader.connector_position > 0.3:
            break
    assert leader.connector is not None and leader.connector_position-leader.length/2 < 0
    lateral = engine._entry_lateral("road4r", "bus")
    assert lateral is None or abs(lateral-leader.lateral) >= 2.5+0.3  # never in the leader's band


def test_vehicles_side_by_side_at_the_stub_line_for_the_narrower_loop_all_get_through():
    """Seed 108, medium, no signal, side street closed 500-800 s: three vehicles stood at the west stub's line for 958 s. The earliest
    (stopped at the line first) was held by the last one standing in its path, the last waited for the middle one's earlier place, and the
    middle one waited for the earliest: a cycle through one hop of 'stands in its path'. Rebuilt from the traced positions."""
    engine = TrafficEngine(seed=7, network=load_registered_network(SITE))
    engine.configure(traffic_density="none", pedestrian_density="none", routing_mode="static")
    engine.enable_no_signal_control()
    engine.driver_variation_scale = 0
    engine.start(300)
    for kind, position, lateral, arrival in (("motorcycle", 13.9, 1.9, 10.0), ("tricycle", 13.4, -1.62, 11.0), ("tricycle", 13.4, 0.75, 12.0)):
        vehicle = engine.add_vehicle(["road4r", "road6f", "road5f"], vehicle_type=kind, speed=0.0)
        vehicle.position, vehicle.lateral, vehicle.lateral_target = position, lateral, lateral
        vehicle.approach_arrival = vehicle.stop_arrival = arrival
    engine.step(1200)
    assert engine._last_metrics["throughput"] == 3


def test_a_bus_does_not_start_its_turn_beside_a_committed_motorcycle_that_is_then_held_in_the_bus_path():
    """Seed 101, medium, fixed-time, west and side street closed, 1035.0 s. The motorcycle (in the band beside the bus: its lateral 0.2 against the
    bus's -1.89) had committed and was still moving when the bus committed, so the commit test excused it as 'about to drive off'. Sweeps ahead of
    it then held it 3.6 m past its stop line, inside the swing of the bus's rear, and the bodies overlapped for one tick."""
    from simulation.footprints import overlapping_pairs
    engine = TrafficEngine(seed=7, network=load_registered_network(SITE))
    engine.configure(traffic_density="none", pedestrian_density="none", routing_mode="static")
    engine.driver_variation_scale = 0
    engine.start(300)
    signal = engine.signals["tagum_site_a_j"]
    signal.index, signal.stage, signal.elapsed = signal.approaches.index("north"), "green", 0
    signal.external, signal.maximum_green = True, 180
    lane = engine.network.lanes["road1r"]
    motorcycle = engine.add_vehicle(["road1r", "road3f"], vehicle_type="motorcycle", speed=1.0)
    motorcycle.position, motorcycle.lateral, motorcycle.lateral_target = 46.0, 0.2, 0.2
    engine._reserve(motorcycle, lane.target, lane.approach)
    engine._sweeps[motorcycle.id] = engine._sweep_for(motorcycle, motorcycle.lateral, engine._exit_lateral(motorcycle))
    bus = engine.add_vehicle(["road1r", "road3f"], vehicle_type="bus", speed=3.9)
    bus.position, bus.lateral, bus.lateral_target = 38.0, -1.89, -1.89
    original = engine._sweep_clear_travel
    # the motorcycle moves until the bus has committed, then sweeps ahead of it (other approaches' turns) hold it where it stands
    engine._sweep_clear_travel = lambda vehicle, lane_, travel: 0.0 if vehicle is motorcycle and bus.reserved_junction else original(vehicle, lane_, travel)
    for _ in range(150):
        engine.step(1)
        assert not overlapping_pairs(engine.vehicle_records()), f"overlap at {engine.simulation_time}s"


@pytest.mark.xfail(strict=True, reason="Known and unfixed: two vehicles side by side at the line can each stand in the other's turning path by a few centimetres. Neither can start, and a stopped vehicle cannot move sideways (the engine moves a body sideways only while it moves forward, a motorcycle's shuffle aside), so no sideways move frees them. The stalled_vehicles alarm reports it.")
def test_a_bus_and_a_motorcycle_whose_turning_paths_barely_touch_do_not_freeze_the_line():
    """Seed 105, medium, no signal, road2 closed, 1150 s: a bus and a motorcycle stood at the north loop junction's line for 440 s, both bound for
    the loop street, each standing in the other's path by about 5 cm (the bus's nose against the motorcycle's drift toward the exit). Neither could
    commit, and no sideways move was ever tried. Positions and arrival order are from the traced state."""
    engine = TrafficEngine(seed=7, network=load_registered_network(SITE))
    engine.configure(traffic_density="none", pedestrian_density="none", routing_mode="static")
    engine.enable_no_signal_control()
    engine.driver_variation_scale = 0
    engine.start(300)
    for kind, position, lateral, arrival in (("bus", 44.47, 1.1, 8.0), ("motorcycle", 48.47, 2.8, 9.0)):
        vehicle = engine.add_vehicle(["road1f", "road6r", "road4f"], vehicle_type=kind, speed=0.0)
        vehicle.position, vehicle.lateral, vehicle.lateral_target = position, lateral, lateral
        vehicle.approach_arrival = vehicle.stop_arrival = arrival
    engine.step(1500)
    assert engine._last_metrics["throughput"] == 2 and engine._last_metrics["stalled_vehicles"] == 0
