"""Experimental Site B frontage graph; never install without clearance and traffic acceptance.

The provisional offsets are from the owner's image-based layout, not surveyed
dimensions. RoadNetwork may reject the candidate's short junction spacing.
"""
from __future__ import annotations

import copy
import math

from simulation.road_network import JUNCTION_CLEARANCE_M, STOP_LINE_SETBACK_M, length, width_per_direction

FRONTAGE_CENTER_M = 14.55


def _crossing(shape, origin, normal, offset):
    """First polyline crossing of a signed lateral offset; returns split data."""
    travelled = 0.0
    for index, (a, b) in enumerate(zip(shape, shape[1:])):
        left = (a[0]-origin[0])*normal[0] + (a[1]-origin[1])*normal[1]
        right = (b[0]-origin[0])*normal[0] + (b[1]-origin[1])*normal[1]
        segment = math.dist(a, b)
        if segment and min(left, right) <= offset <= max(left, right) and abs(right-left) > 1e-9:
            ratio = (offset-left)/(right-left)
            point = [a[i]+ratio*(b[i]-a[i]) for i in (0, 1)]
            if ratio < 1e-8 or ratio > 1-1e-8:
                raise ValueError("A frontage crossing lands on a road vertex; explicit topology review is required")
            return index, point, travelled + segment*ratio
        travelled += segment
    raise ValueError(f"Road does not reach provisional frontage offset {offset:g} m")


def build_frontage_candidate(network: dict, frontage_center_m: float = FRONTAGE_CENTER_M) -> tuple[dict, dict]:
    """Return a draft graph and diagnostics without touching the registered site."""
    if isinstance(frontage_center_m, bool) or not isinstance(frontage_center_m, (int, float)) or not math.isfinite(frontage_center_m) or not 10 <= frontage_center_m <= 50:
        raise ValueError("Frontage centre offset must be between 10 and 50 metres")
    payload = copy.deepcopy(network)
    restrictions = payload.get("prohibited_turns", [])
    if not isinstance(restrictions, list) or any(not isinstance(pair, list) or len(pair) != 2 or any(not isinstance(lane, str) for lane in pair) for pair in restrictions):
        raise ValueError("Turn restrictions need review before splitting frontage roads")
    nodes = {node["id"]: node for node in payload["nodes"]}
    roads = {road["id"]: road for road in payload["roads"]}
    main, neighbor = nodes["tagum_site_b_j"], nodes["1115349256"]
    dx, dy = neighbor["x"]-main["x"], neighbor["y"]-main["y"]
    span = math.hypot(dx, dy)
    if span < 1:
        raise ValueError("Study and neighboring junctions need distinct positions")
    axis, normal = (dx/span, dy/span), (-dy/span, dx/span)
    anchors: dict[tuple[str, int], dict] = {}
    side_roads = (("study", "road0"), ("study", "road1"), ("neighbor", "road6"), ("neighbor", "road7"))
    for group, road_id in side_roads:
        road = roads[road_id]
        junction = main if group == "study" else neighbor
        if road["source"] != junction["id"]:
            raise ValueError(f"{road_id} does not start at the expected junction")
        a, b = road["shape"][:2]
        lateral = (b[0]-a[0])*normal[0] + (b[1]-a[1])*normal[1]
        if abs(lateral) < 1e-8:
            raise ValueError(f"{road_id} has no identifiable frontage side")
        side = 1 if lateral > 0 else -1
        if (group, side) in anchors:
            raise ValueError(f"Multiple side streets mapped to {group} side {side}")
        index, point, along = _crossing(road["shape"], [junction["x"], junction["y"]], normal, side*frontage_center_m)
        node_id, tail_id = f"frontage_{group}_{'left' if side > 0 else 'right'}", f"{road_id}_outer"
        if node_id in nodes or tail_id in roads:
            raise ValueError("Candidate IDs already exist")
        old_target, old_shape = road["target"], road["shape"]
        tail = {**copy.deepcopy(road), "id": tail_id, "source": node_id, "target": old_target,
                "shape": [point, *old_shape[index+1:]]}
        road["target"], road["shape"] = node_id, [*old_shape[:index+1], point]
        payload["roads"].append(tail)
        # Restrictions at the old target move to the outer segment; those at
        # the original source remain attached to the inner segment.
        restrictions = [[tail_id + "f" if incoming == road_id + "f" else incoming,
                         tail_id + "r" if outgoing == road_id + "r" else outgoing]
                        for incoming, outgoing in restrictions]
        if "prohibited_turns" in payload:
            payload["prohibited_turns"] = restrictions
        node = {"id": node_id, "x": point[0], "y": point[1], "boundary": False,
                "default_control_mode": "first_come", "label": f"Provisional {group} frontage access"}
        payload["nodes"].append(node)
        nodes[node_id] = node
        anchors[group, side] = {"id": node_id, "point": point, "side_road": road_id, "distance_m": along}
    if set(anchors) != {(group, side) for group in ("study", "neighbor") for side in (-1, 1)}:
        raise ValueError("Both frontage sides need a side-street crossing at each junction")

    for side in (-1, 1):
        study, other = anchors["study", side], anchors["neighbor", side]
        # Extend parallel to the cached highway; these two boundary positions are estimates.
        near = [study["point"][i]-axis[i]*200 for i in (0, 1)]
        far = [other["point"][i]+axis[i]*150 for i in (0, 1)]
        suffix = "left" if side > 0 else "right"
        near_id, far_id = f"frontage_{suffix}_south", f"frontage_{suffix}_north"
        for name, point in ((near_id, near), (far_id, far)):
            if name in nodes:
                raise ValueError("Candidate boundary ID already exists")
            payload["nodes"].append({"id": name, "x": point[0], "y": point[1], "boundary": True})
        # Determine direction from the adjacent original highway carriageway south of the study node.
        choices = []
        for road_id in ("road4", "road5"):
            road = roads[road_id]
            mid = road["shape"][len(road["shape"])//2]
            cross = (mid[0]-main["x"])*normal[0] + (mid[1]-main["y"])*normal[1]
            choices.append((abs(cross-side*frontage_center_m), road))
        adjacent = min(choices, key=lambda item: item[0])[1]
        direction = ((adjacent["shape"][-1][0]-adjacent["shape"][0][0])*axis[0]
                     + (adjacent["shape"][-1][1]-adjacent["shape"][0][1])*axis[1])
        if abs(direction) < 1e-6:
            raise ValueError("Adjacent highway direction is ambiguous")
        chain = [(near_id, near), (study["id"], study["point"]), (other["id"], other["point"]), (far_id, far)]
        if direction < 0:
            chain.reverse()
        for index, ((source, a), (target, b)) in enumerate(zip(chain, chain[1:])):
            payload["roads"].append({"id": f"frontage_{suffix}_{index}", "name": f"Provisional {suffix} frontage",
                                     "source": source, "target": target, "oneway": True, "shape": [a, b],
                                     "width_per_direction_m": 3.3, "speed_mps": 30/3.6, "osm_tags": {"lanes": "1"}})
        anchors["direction", side] = {"adjacent_highway": adjacent["id"], "axis_sign": 1 if direction > 0 else -1}

    payload["source"]["assumptions"] = [*payload["source"].get("assumptions", []),
        "EXPERIMENTAL FRONTAGE CANDIDATE: not validated or approved for simulation",
        "Frontage offsets, boundary extensions and new side-street turns are provisional"]
    def clearance(node_id):
        widths = [width_per_direction(road) * (1 if road.get("oneway") else 2)
                  for road in payload["roads"] if node_id in (road["source"], road["target"])]
        return max(nodes[node_id].get("junction_clearance_m", JUNCTION_CLEARANCE_M), max(widths)/2 + STOP_LINE_SETBACK_M)
    crossings = []
    for group in ("study", "neighbor"):
        for side in (-1, 1):
            item = anchors[group, side]
            inner = roads[item["side_road"]]
            required = clearance(inner["source"]) + clearance(inner["target"]) + 8.0
            actual = length([tuple(point) for point in inner["shape"]])
            crossings.append({"junction": group, "side": side, **item, "inner_length_m": actual,
                              "required_length_m": required, "shortfall_m": max(0.0, required-actual)})
    report = {"status": "unvalidated candidate; do not install", "frontage_center_offset_m": frontage_center_m,
              "crossings": crossings,
              "directions": [{"side": side, **anchors["direction", side]} for side in (-1, 1)],
              "limitations": ["Island geometry and vehicle clearance are not enforced", "New movements are provisional",
                              "Field measurement and traffic acceptance remain outstanding"]}
    return payload, report


if __name__ == "__main__":
    import argparse
    import json
    from pathlib import Path
    from simulation.road_network import RoadNetwork

    parser = argparse.ArgumentParser(description="Write an uninstalled, provisional Site B frontage candidate and diagnostics")
    parser.add_argument("--network", type=Path, required=True)
    parser.add_argument("--candidate", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    args = parser.parse_args()
    if args.candidate.resolve() == args.network.resolve() or args.report.resolve() in (args.network.resolve(), args.candidate.resolve()):
        parser.error("Input, candidate and report must be distinct files")
    if args.candidate.exists() or args.report.exists():
        parser.error("Choose new output paths; existing files are preserved")
    candidate, report = build_frontage_candidate(json.loads(args.network.read_text(encoding="utf-8")))
    try:
        RoadNetwork(candidate)
        report["native_structure"] = {"accepted": True, "reason": "Structure only; clearance and traffic remain unverified"}
    except ValueError as exc:
        report["native_structure"] = {"accepted": False, "reason": str(exc)}
    with args.candidate.open("x", encoding="utf-8") as output:
        json.dump(candidate, output, indent=2)
    try:
        with args.report.open("x", encoding="utf-8") as output:
            json.dump(report, output, indent=2)
    except Exception:
        args.candidate.unlink(missing_ok=True)
        raise
