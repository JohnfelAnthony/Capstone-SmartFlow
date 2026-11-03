"""Uninstalled Site B island-spacing experiment; not surveyed or traffic-safe."""
from __future__ import annotations

import argparse
import json
import math
from pathlib import Path

from simulation.road_network import RoadNetwork, width_per_direction
from tools.road_editor.geometry_checks import lane_touches_island
from tools.site_b_combined_review import build_combined, overview


def build_island_proposal(payload):
    # The larger offset is a nominal spacing experiment, not a measurement.
    candidate, report = build_combined(payload, frontage_center_m=15.25)
    nodes = {node["id"]: node for node in candidate["nodes"]}
    start, end = nodes["tagum_site_b_j"], nodes["1115349256"]
    dx, dy = end["x"]-start["x"], end["y"]-start["y"]
    span = math.hypot(dx, dy)
    if span <= 100:
        raise ValueError("The junctions are too close for the provisional middle island")
    ux, uy = dx/span, dy/span

    def point(along, across):
        return [start["x"] + along*ux - across*uy, start["y"] + along*uy + across*ux]

    intervals = (("south", -180., -40.), ("middle", 40., span-50.), ("north", span+50., span+130.))
    bands = (("central", -1., 1.), ("outer_left", 11.4, 13.4), ("outer_right", -13.4, -11.4))
    proposed = []
    for section, low, high in intervals:
        for name, left, right in bands:
            shape = [point(low, left), point(high, left), point(high, right), point(low, right)]
            conflicts = []
            for road in candidate["roads"]:
                width = width_per_direction(road) * (1 if road.get("oneway") else 2)
                if lane_touches_island(road["shape"], width, shape):
                    conflicts.append(road["id"])
            proposed.append({"id": f"provisional_{section}_{name}", "planted": True, "shape": shape,
                             "review_pavement_conflicts": conflicts})
    candidate["islands"] = proposed
    candidate["source"]["assumptions"].append("Historical OSM corridor experiment: provisional 2 m island rectangles and 15.25 m frontage offset are review estimates, not surveyed dimensions or enforced obstacles.")
    report["source_network_fingerprint"] = RoadNetwork(payload).fingerprint
    report["limits"] = ["Proposed islands are visual only and may overlap roadway pavement.",
                        "Dimensions, frontage turns and endpoint transitions require field review.",
                        "The native engine cannot currently model the short links safely."]
    report["island_review"] = {"frontage_center_offset_m": 15.25, "nominal_island_width_m": 2.0,
                               "island_count": len(proposed),
                               "pavement_conflicts": [{"island": island["id"], "roads": island["review_pavement_conflicts"]} for island in proposed if island["review_pavement_conflicts"]],
                               "limitations": ["Road-shape pavement check only; vehicle bodies and connectors are not checked.",
                                               "Rectangles, openings and widths are visual estimates and require field measurement.",
                                               "Islands are not enforced by the traffic engine."]}
    return candidate, report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("network", type=Path)
    parser.add_argument("candidate", type=Path)
    parser.add_argument("report", type=Path)
    parser.add_argument("svg", type=Path)
    args = parser.parse_args()
    paths = [args.network, args.candidate, args.report, args.svg]
    if len({path.resolve() for path in paths}) != 4 or any(path.exists() for path in paths[1:]):
        parser.error("Choose three distinct new output files")
    candidate, report = build_island_proposal(json.loads(args.network.read_text(encoding="utf-8")))
    outputs = [(args.candidate, json.dumps(candidate, indent=2)+"\n"), (args.report, json.dumps(report, indent=2)+"\n"), (args.svg, overview(candidate))]
    created = []
    try:
        for path, contents in outputs:
            with path.open("x", encoding="utf-8") as stream:
                created.append(path)
                stream.write(contents)
    except Exception:
        for path in created:
            path.unlink(missing_ok=True)
        raise


if __name__ == "__main__":
    main()
