"""Experimental directional conflict ranges, for review and research only.

These static envelopes do not include connectors, pedestrian motion or arbitrary
vehicle positions. They do not control simulation traffic.
"""
from __future__ import annotations

import argparse
import itertools
import json
import math
from pathlib import Path

from simulation.footprints import rectangle, rectangles_overlap
from simulation.road_network import RoadNetwork
from simulation.scenario_config import VEHICLE_TYPES

CELL_M = 4.0
MARGIN_M = .01


def cells(shape, width, radius):
    result, travelled = [], 0.0
    for a, b in zip(shape, shape[1:]):
        distance = math.dist(a, b)
        if distance <= 1e-9:
            continue
        count = math.ceil(distance / CELL_M)
        dx, dy = (b[0] - a[0]) / distance, (b[1] - a[1]) / distance
        heading = math.atan2(dy, dx)
        for index in range(count):
            start, end = distance * index / count, distance * (index + 1) / count
            mid = (start + end) / 2
            body = rectangle(a[0] + dx*mid, a[1] + dy*mid, heading,
                             end-start + 2*radius + 2*MARGIN_M, width + 2*MARGIN_M)
            xs, ys = zip(*body)
            result.append((travelled+start, travelled+end, body, (min(xs), min(ys), max(xs), max(ys))))
        travelled += distance
    return result


def merge_ranges(ranges):
    result = []
    for low, high in sorted(ranges):
        if result and low <= result[-1][1] + 1e-8:
            result[-1][1] = max(result[-1][1], high)
        else:
            result.append([low, high])
    return result


def conflict_ranges(first, second):
    hits = []
    for a0, a1, a, ab in first:
        for b0, b1, b, bb in second:
            if ab[0] >= bb[2] or bb[0] >= ab[2] or ab[1] >= bb[3] or bb[1] >= ab[3]:
                continue
            if rectangles_overlap(a, b):
                hits.append((a0, a1, b0, b1))
    if not hits:
        return None
    return {"first": merge_ranges((hit[0], hit[1]) for hit in hits),
            "second": merge_ranges((hit[2], hit[3]) for hit in hits)}


def analyze(payload):
    network = RoadNetwork(payload)
    radius = max(math.hypot(spec["length"], spec["width"]) / 2 for spec in VEHICLE_TYPES.values())
    prepared = {lane.id: cells(lane.shape, lane.width, radius) for lane in network.lanes.values()}
    conflicts = []
    for first, second in itertools.combinations(network.lanes.values(), 2):
        result = conflict_ranges(prepared[first.id], prepared[second.id])
        if result:
            conflicts.append({"first_lane": first.id, "second_lane": second.id,
                              "first_ranges_m": result["first"], "second_ranges_m": result["second"]})
    return {"status": "experimental review only; not an operational reservation or safety certification",
            "network_id": network.id, "network_fingerprint": network.fingerprint, "cell_max_m": CELL_M,
            "body_radius_m": radius, "conflicts": conflicts,
            "assumptions": ["Vehicle centres remain on the reported lane with their body contained in its lateral width.",
                            "Straight segments use heading-aligned envelopes grown along the path by the maximum body radius.",
                            "Turn connectors, vehicles transitioning between paths, and pedestrians are excluded.",
                            "Ranges need dynamic, liveness, and field validation before use."]}


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
