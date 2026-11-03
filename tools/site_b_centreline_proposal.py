"""Generate an uninstalled Site B carriageway-separation experiment.

This is image-informed geometry exploration, not surveyed geometry, a completed
frontage network, or a traffic-safe design. It must not replace the active site.
"""
from __future__ import annotations

import argparse
import copy
import json
from pathlib import Path

from simulation.road_network import RoadNetwork, clip, length, offset

HIGHWAY_ROADS = ("road2", "road3", "road4", "road5", "road8", "road9")
SHIFT_M = 2.0
END_TRANSITION_M = 2.0


def build_candidate(payload):
    candidate = copy.deepcopy(payload)
    if candidate.get("islands") or candidate.get("site_features"):
        raise ValueError("This historical corridor experiment cannot be applied to a network with existing islands or site features")
    roads = {road["id"]: road for road in candidate["roads"]}
    if candidate.get("id") != "tagum_site_b" or any(name not in roads for name in HIGHWAY_ROADS):
        raise ValueError("Expected the expanded Site B network with all six highway segments")
    changes = []
    for road_id in HIGHWAY_ROADS:
        road = roads[road_id]
        if not road.get("oneway") or "Highway" not in road.get("name", ""):
            raise ValueError(f"{road_id} is not a one-way highway segment")
        original = [tuple(point) for point in road["shape"]]
        shifted = offset(original, SHIFT_M)
        total = length(shifted)
        if total <= 2 * END_TRANSITION_M:
            raise ValueError(f"{road_id} is too short for the proposed endpoint transition")
        # The shared junction coordinates remain connected; the transition is
        # clipped out at junctions by the current native network parser.
        interior = clip(shifted, END_TRANSITION_M, total-END_TRANSITION_M)
        road["shape"] = [list(original[0]), *[list(point) for point in interior], list(original[-1])]
        changes.append({"road_id": road_id, "right_shift_m": SHIFT_M, "endpoint_transition_m": END_TRANSITION_M})
    candidate["source"].setdefault("assumptions", []).append(
        "Unvalidated visual experiment: six one-way highway centrelines shifted right by 2 m; shared endpoint transitions are provisional and require field review."
    )
    network = RoadNetwork(candidate)
    report = {"status": "unvalidated experiment; do not install or use for research", "network_fingerprint": network.fingerprint,
              "changes": changes, "limits": ["Shift is an image-based assumption, not a measurement.",
              "Frontage roads, island obstacles and full vehicle clearance are not included.",
              "Endpoint transitions and connector paths need review and traffic acceptance."]}
    return candidate, report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("network", type=Path)
    parser.add_argument("candidate", type=Path)
    parser.add_argument("report", type=Path)
    args = parser.parse_args()
    paths = [args.network.resolve(), args.candidate.resolve(), args.report.resolve()]
    if len(set(paths)) != 3 or args.candidate.exists() or args.report.exists():
        parser.error("Choose distinct new output paths; existing files are preserved")
    candidate, report = build_candidate(json.loads(args.network.read_text(encoding="utf-8")))
    with args.candidate.open("x", encoding="utf-8") as output:
        json.dump(candidate, output, indent=2)
        output.write("\n")
    try:
        with args.report.open("x", encoding="utf-8") as output:
            json.dump(report, output, indent=2)
            output.write("\n")
    except Exception:
        args.candidate.unlink(missing_ok=True)
        raise


if __name__ == "__main__":
    main()
