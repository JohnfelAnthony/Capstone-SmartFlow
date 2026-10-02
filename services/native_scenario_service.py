"""Network-derived choices for native scenario controls; no hard-coded study IDs."""
import copy

from simulation.traffic_engine import TrafficEngine


def configuration_options():
    engine = TrafficEngine()
    network = engine.network
    road_names = {road["id"]: road.get("name") or road["id"] for road in network.payload["roads"]}
    node_labels = {}
    for index, node in enumerate(network.intersections, 1):
        streets = sorted({road_names[lane[:-1]] for lane in network.incoming[node]})
        node_labels[node] = f"J{index}: {' / '.join(streets)}"
    for index, node in enumerate(network.boundaries, 1):
        node_labels[node] = f"Boundary {index}"
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
        "junctions": junctions,
        "boundaries": [{"id": node, "label": node_labels[node]} for node in network.boundaries],
        "lanes": [{"id": lane.id, "source": lane.source, "target": lane.target,
                   "road_name": road_names[lane.id[:-1]], "speed_mps": lane.speed,
                   "label": f"{road_names[lane.id[:-1]]}: {node_labels[lane.source]} to {node_labels[lane.target]} ({lane.id})"}
                  for lane in network.lanes.values()],
    }
