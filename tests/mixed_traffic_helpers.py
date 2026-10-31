"""Synthetic scenes for the mixed-traffic tests."""
from simulation.footprints import overlapping_pairs
from simulation.mixed_traffic import lateral_bounds
from simulation.road_network import RoadNetwork
from simulation.traffic_engine import TrafficEngine

ARMS = {"w": (-1, 0), "e": (1, 0), "n": (0, 1), "s": (0, -1)}


def junction_network(width_per_direction_m=None, lanes_tag="2", arm_length=150.0, arm_widths: dict[str, float] | None = None,
                     arm_shapes: dict[str, list] | None = None) -> RoadNetwork:
    """A cross: boundary arms w, e, n, s as two-way roads into junction j, at 8.33 m/s (straight unless arm_shapes)."""
    nodes = [{"id": "j", "x": 0.0, "y": 0.0}]
    roads = []
    for arm, (dx, dy) in ARMS.items():
        nodes.append({"id": arm, "x": dx*arm_length, "y": dy*arm_length, "boundary": True})
        road = {"id": arm, "source": arm, "target": "j", "oneway": False, "speed_mps": 8.33,
                "shape": (arm_shapes or {}).get(arm, [[dx*arm_length, dy*arm_length], [0.0, 0.0]]), "osm_tags": {"lanes": lanes_tag}}
        width = (arm_widths or {}).get(arm, width_per_direction_m)
        if width is not None:
            road["width_per_direction_m"] = width
        roads.append(road)
    return RoadNetwork({"id": "test_cross", "source": "synthetic test network", "nodes": nodes, "roads": roads})


def started_engine(network, **config):
    """Seed 7, no background demand or pedestrians, driver variation off, started for 600 s."""
    engine = TrafficEngine(seed=7, network=network)
    engine.configure(traffic_density="none", pedestrian_density="none", **config)
    engine.driver_variation_scale = 0
    engine.start(600)
    return engine


def hold_green(engine, node, family):
    """Hold one approach green (so every other approach waits) for the rest of the test."""
    signal = engine.signals[node]
    signal.index, signal.stage, signal.elapsed = signal.approaches.index(family), "green", 0
    signal.external, signal.maximum_green = True, 180


def place(engine, route, vehicle_type, *, from_stop_line: float, lateral: float, speed: float = 0.0):
    """Add a vehicle and put its front `from_stop_line` metres before the stop line at `lateral`."""
    vehicle = engine.add_vehicle(route, vehicle_type=vehicle_type, speed=speed)
    assert vehicle is not None, "lane start blocked"
    vehicle.position = engine.stop_line(route[0])-vehicle.length/2-from_stop_line
    vehicle.lateral = vehicle.lateral_target = lateral
    return vehicle


def front_to_stop_line(engine, vehicle):
    return engine.stop_line(vehicle.lane_id)-(vehicle.position+vehicle.length/2)


def assert_never_overlap(test, engine, ticks, *, every=1, lanes_only=False):
    """Step `ticks` ticks; at each sample no two drawn bodies overlap and every lane body stays on its road."""
    for tick in range(ticks+1):
        if tick:
            engine.step(1)
        if tick % every:
            continue
        records = [record for record in engine.vehicle_records()
                   if not (lanes_only and engine.vehicles[record["id"]].connector is not None)]
        test.assertEqual(overlapping_pairs(records), [], f"overlap at t={engine.simulation_time}")
        for vehicle in engine.vehicles.values():
            if vehicle.connector is not None:
                continue
            lane = engine.network.lanes[vehicle.lane_id]
            yaw = getattr(vehicle, "yaw", 0.0)
            if yaw == 0:
                low, high = lateral_bounds(lane.width, vehicle.width)
            else:
                low, high = lateral_bounds(lane.width, engine._box(vehicle)[1], edge_clearance=0)
            test.assertTrue(low-1e-9 <= vehicle.lateral <= high+1e-9, f"{vehicle.id} off the road at t={engine.simulation_time}")


def fill_queue(engine, route, vehicle_type, count, ticks=600):
    """Add `count` vehicles at the lane start as soon as each fits, then step `ticks` more ticks."""
    added = []
    while len(added) < count:
        vehicle = engine.add_vehicle(route, vehicle_type=vehicle_type, speed=5.0)
        if vehicle:
            added.append(vehicle)
        engine.step(1)
    engine.step(ticks)
    return added


def busy_engine(network, *, seed=7, density="high", **config):
    """Seeded background demand with the provisional Tagum mix and light pedestrians, started for 1,800 s."""
    from simulation.scenario_config import TAGUM_PROVISIONAL_MIX
    engine = TrafficEngine(seed=seed, network=network)
    engine.configure(traffic_density=density, pedestrian_density="low", vehicle_mix=TAGUM_PROVISIONAL_MIX, **config)
    engine.start(1800)
    return engine
