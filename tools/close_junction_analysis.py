"""Analyze short physical links before proposing a coordinated-junction model.

This does not alter simulation behavior or certify the proposed network.
"""
from __future__ import annotations

from simulation.mixed_traffic import CLASS_DRIVING
import math

from simulation.road_network import JUNCTION_CLEARANCE_M, MAX_JUNCTION_CLEARANCE_M, STOP_LINE_SETBACK_M, length, width_per_direction
from simulation.scenario_config import VEHICLE_TYPES
from simulation.traffic_engine import EXIT_SPACE_MARGIN


def analyze(payload: dict) -> dict:
    nodes = {node["id"]: node for node in payload["nodes"]}
    junctions = {name for name, node in nodes.items() if not node.get("boundary")}
    clearance = {}
    for node_id in junctions:
        widths = [width_per_direction(road) * (1 if road.get("oneway") else 2)
                  for road in payload["roads"] if node_id in (road["source"], road["target"])]
        if not widths:
            raise ValueError(f"Junction {node_id} has no connected roads")
        explicit = nodes[node_id].get("junction_clearance_m", JUNCTION_CLEARANCE_M)
        if (isinstance(explicit, bool) or not isinstance(explicit, (int, float)) or not math.isfinite(explicit)
                or not JUNCTION_CLEARANCE_M <= explicit <= MAX_JUNCTION_CLEARANCE_M):
            raise ValueError(f"Invalid junction clearance for {node_id}")
        clearance[node_id] = max(explicit, max(widths)/2 + STOP_LINE_SETBACK_M)
    parents = {name: name for name in junctions}

    def root(name):
        while parents[name] != name:
            name = parents[name]
        return name

    def join(a, b):
        left, right = root(a), root(b)
        if left != right:
            parents[max(left, right)] = min(left, right)

    short_links = []
    for road in payload["roads"]:
        source, target = road["source"], road["target"]
        if source not in junctions or target not in junctions:
            continue
        physical = length([tuple(point) for point in road["shape"]])
        usable = physical - clearance[source] - clearance[target]
        # This is an optimistic upper bound: stop-line setbacks and other
        # vehicles can only reduce the actual storage available.
        storage = {name: spec["length"] + CLASS_DRIVING[name].minimum_gap + EXIT_SPACE_MARGIN
                   for name, spec in VEHICLE_TYPES.items()}
        excluded = [name for name, required in storage.items() if required > usable]
        if usable < 8 or excluded:
            join(source, target)
            short_links.append({"road_id": road["id"], "source": source, "target": target,
                                "physical_length_m": physical, "current_usable_upper_bound_m": usable,
                                "parser_accepts_length": usable >= 8,
                                "classes_that_cannot_fit_even_if_empty": excluded})
    clusters = {}
    for name in sorted(junctions):
        clusters.setdefault(root(name), []).append(name)
    return {"status": "design analysis only; no simulation behavior changed",
            "short_links": short_links,
            "candidate_groups": [members for members in clusters.values() if len(members) > 1],
            "limitations": ["Groups use link storage only and do not identify every geometric conflict",
                            "An empty-lane upper bound is not a safety or liveness guarantee",
                            "Signals, pedestrians, turns and neighboring vehicle bodies need coordinated handling"]}


if __name__ == "__main__":
    import argparse
    import json
    from pathlib import Path
    parser = argparse.ArgumentParser(description="Analyze candidate networks with close physical junctions")
    parser.add_argument("network", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    if args.network.resolve() == args.output.resolve():
        parser.error("Output must differ from input")
    result = analyze(json.loads(args.network.read_text(encoding="utf-8")))
    with args.output.open("x", encoding="utf-8") as stream:
        json.dump(result, stream, indent=2)
