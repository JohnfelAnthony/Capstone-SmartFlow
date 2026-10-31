"""Preparation for a reviewed Field Observer to native-demand conversion.

Templates contain no asserted field observations. Conversion and its coverage,
initialization, timing and provenance safeguards remain to be implemented.
"""
from __future__ import annotations

from simulation.road_network import RoadNetwork, length


DEFAULT_CLASS_MAP = {
    "car": "car", "motorcycle": "motorcycle", "tricycle": "tricycle",
    "tricycle/bao_bao": "tricycle", "bus": "bus", "truck": "truck",
}


def site_mapping_template(network: RoadNetwork) -> dict:
    """List network boundaries while leaving measured study inputs unset."""
    boundaries = []
    for boundary in network.boundaries:
        roads = [road for road in network.payload["roads"] if boundary in (road["source"], road["target"])]
        if len(roads) != 1:
            raise ValueError(f"Boundary {boundary} must connect to exactly one road")
        road = roads[0]
        boundaries.append({"boundary": boundary, "road_name": road.get("name") or road["id"],
                           "road_id": road["id"], "length_m": round(length(road["shape"]), 2)})
    return {"network_id": network.id, "network_sha256": network.fingerprint,
            "boundaries": boundaries, "locations": {}, "lead_out_s": None,
            "upstream_speed_mps_by_class": {}, "movement_conflicts": {},
            "initialization": None, "priority_review": None, "class_map": dict(DEFAULT_CLASS_MAP)}
