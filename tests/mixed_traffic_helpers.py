"""Synthetic scenes for the mixed-traffic tests."""
from simulation.road_network import RoadNetwork
from simulation.traffic_engine import TrafficEngine

ARMS = {"w": (-1, 0), "e": (1, 0), "n": (0, 1), "s": (0, -1)}


def junction_network(width_per_direction_m=None, lanes_tag="2", arm_length=150.0, arm_widths: dict[str, float] | None = None) -> RoadNetwork:
    """A cross: boundary arms w, e, n, s as two-way roads into junction j, at 8.33 m/s."""
    nodes = [{"id": "j", "x": 0.0, "y": 0.0}]
    roads = []
    for arm, (dx, dy) in ARMS.items():
        nodes.append({"id": arm, "x": dx*arm_length, "y": dy*arm_length, "boundary": True})
        road = {"id": arm, "source": arm, "target": "j", "oneway": False, "speed_mps": 8.33,
                "shape": [[dx*arm_length, dy*arm_length], [0.0, 0.0]], "osm_tags": {"lanes": lanes_tag}}
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
