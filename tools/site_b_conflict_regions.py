"""Review-only conservative lane conflict ranges; no engine control is changed."""
from __future__ import annotations

import argparse
import itertools
import json
import math
from pathlib import Path

from simulation.road_network import RoadNetwork
from simulation.scenario_config import VEHICLE_TYPES
from tools.road_editor.geometry_checks import lane_overlap_ranges


def analyze(payload):
    network = RoadNetwork(payload)
    radius = max(math.hypot(spec["length"], spec["width"]) / 2 for spec in VEHICLE_TYPES.values())
    conflicts = []
    for first, second in itertools.combinations(network.lanes.values(), 2):
        # The full lane width bounds centre positions; a body radius on each
        # side includes any orientation. This is intentionally conservative.
        ranges = lane_overlap_ranges(first.shape, first.width + 2 * radius, second.shape, second.width + 2 * radius)
        if ranges:
            conflicts.append({"first_lane": first.id, "second_lane": second.id, "first_range_m": ranges["first"], "second_range_m": ranges["second"]})
    return {"status": "review only; no reservation or safety certification", "network_id": network.id,
            "network_fingerprint": network.fingerprint, "body_radius_m": radius, "conflicts": conflicts,
            "limitations": ["Whole intersecting segments are included, so ranges may be substantially too large.",
                            "Connector paths and dynamic trajectories require additional conflict checks.",
                            "Do not use these ranges as accepted geometry or field measurements."]}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("network", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    if args.network.resolve() == args.output.resolve():
        parser.error("Choose a new output file")
    result = analyze(json.loads(args.network.read_text(encoding="utf-8")))
    with args.output.open("x", encoding="utf-8") as stream:
        json.dump(result, stream, indent=2)
        stream.write("\n")


if __name__ == "__main__":
    main()
