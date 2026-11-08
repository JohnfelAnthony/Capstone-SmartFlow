"""Network-derived choices for native scenario controls; no hard-coded study IDs."""
import copy
import math

from simulation.scenario_config import VEHICLE_MIX_PRESETS, is_study_site
from simulation.traffic_engine import TrafficEngine


def network_display_labels(network):
    """Share existing road/junction names without constructing an engine."""
    road_names = {road["id"]: road.get("name") or road["id"] for road in network.payload["roads"]}
    node_labels = {}
    for index, node in enumerate(network.intersections, 1):
        streets = sorted({road_names[lane[:-1]] for lane in network.incoming[node]})
        node_labels[node] = f"J{index}: {' / '.join(streets)}"
    for index, node in enumerate(network.boundaries, 1):
        node_labels[node] = f"Boundary {index}"
    return road_names, node_labels


def lane_direction(lane) -> str:
    """Compass direction of travel along the lane, from its overall start to end."""
    (x1, y1), (x2, y2) = lane.shape[0], lane.shape[-1]
    return ("eastbound", "northbound", "westbound", "southbound")[round(math.atan2(y2-y1, x2-x1)/(math.pi/2)) % 4]


def road_whereabouts(network, road: dict) -> str:
    """Where a road piece lies relative to the study junction, e.g. "west, 0–226 m out", so same-name pieces can be told apart."""
    centre = network.nodes[network.intersections[0]]
    offsets = [(x-centre["x"], y-centre["y"]) for x, y in road["shape"]]
    far = max(offsets, key=lambda point: math.hypot(*point))
    compass = ("east", "north-east", "north", "north-west", "west", "south-west", "south", "south-east")[round(math.atan2(far[1], far[0])/(math.pi/4)) % 8]
    distances = [math.hypot(*point) for point in offsets]
    return f"{compass}, {round(min(distances))}–{round(max(distances))} m out"


def configuration_options(network_id: str | None = None):
    from simulation.network_registry import load_registered_network
    engine = TrafficEngine(network=load_registered_network(network_id))
    network = engine.network
    road_names, node_labels = network_display_labels(network)
    roads = {road["id"]: road for road in network.payload["roads"]}
    junctions = []
    for node, signal in engine.signals.items():
        junctions.append({
            "id": node, "label": node_labels[node], "approaches": signal.approaches,
            "default_plan": {
                "mode": signal.mode, "phase_order": list(signal.approaches),
                "green_seconds": signal.green_seconds, "minimum_green": signal.minimum_green,
                "maximum_green": signal.maximum_green, "yellow_seconds": signal.yellow_seconds,
                "all_red_seconds": signal.all_red_seconds, "offset_seconds": 0,
            },
        })
    return {
        "network_id": network.id, "network_name": network.payload.get("name", network.id),
        "network_sha256": network.fingerprint, "defaults": copy.deepcopy(engine.config),
        "routing_follows_closure_choice": is_study_site(network.id),
        "junctions": junctions,
        "boundaries": [{"id": node, "label": node_labels[node]} for node in network.boundaries],
        "lanes": [{"id": lane.id, "source": lane.source, "target": lane.target, "road_id": lane.id[:-1], "direction": lane_direction(lane), "where": road_whereabouts(network, roads[lane.id[:-1]]),
                   "kind": "entry" if lane.source in network.boundaries else "exit" if lane.target in network.boundaries else "link",
                   "road_name": road_names[lane.id[:-1]], "speed_mps": lane.speed,
                   "label": f"{road_names[lane.id[:-1]]}: {node_labels[lane.source]} to {node_labels[lane.target]}"}
                  for lane in network.lanes.values()],
        "vehicle_mix_presets": copy.deepcopy(VEHICLE_MIX_PRESETS),
    }
