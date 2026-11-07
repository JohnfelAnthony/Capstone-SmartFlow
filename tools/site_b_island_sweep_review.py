"""Review connector-body/island conflicts; diagnostic only, never an acceptance test."""
from __future__ import annotations

import argparse
import json
import math
from pathlib import Path

from simulation.mixed_traffic import lateral_bounds
from simulation.road_network import RoadNetwork, length, sample
from simulation.footprints import rectangle
from simulation.scenario_config import VEHICLE_TYPES
from simulation.traffic_engine import SWEEP_SAMPLE_M, TrafficEngine
from tools.road_editor.geometry_checks import polygons_touch_or_overlap


def review(network: RoadNetwork) -> dict:
    """Inspect centre and lane-edge connector sweeps at engine resolution.

    These are conservative envelopes, not necessarily reachable vehicle poses.
    The finite lateral samples and absence of lane dynamics preclude a safety proof.
    """
    engine = TrafficEngine(network=network)
    islands = []
    for island in network.islands:
        shape = island["shape"]
        islands.append((island["id"], shape, (min(p[0] for p in shape), min(p[1] for p in shape),
                                             max(p[0] for p in shape), max(p[1] for p in shape))))
    conflicts, checked = [], 0
    for junction in network.intersections:
        for incoming in network.incoming[junction]:
            for outgoing in network.outgoing[junction]:
                if not network.turn_allowed(incoming, outgoing):
                    continue
                for name, spec in VEHICLE_TYPES.items():
                    if not network.turn_allowed(incoming, outgoing, vehicle_type=name):
                        continue
                    low, high = lateral_bounds(network.lanes[incoming].width, spec["width"])
                    exit_low, exit_high = lateral_bounds(network.lanes[outgoing].width, spec["width"])
                    kerb = engine._entry_kerb_position(network.lanes[incoming], name, spec["width"])
                    for lateral in sorted({low, (low + high) / 2, high}) if kerb is None else (kerb,):
                        exit_lateral = max(exit_low, min(exit_high, lateral))
                        sweep = engine._build_sweep(incoming, outgoing, lateral, exit_lateral, spec["length"], spec["width"])
                        connector = network.connector(incoming, outgoing)
                        connector_length = length(connector)
                        checked += 1
                        found = {}
                        body_contacts = {}
                        for distance, body, (left, bottom, right, top) in sweep:
                            for island_id, shape, (il, ib, ir, it) in islands:
                                if left > ir or il > right or bottom > it or ib > top:
                                    continue
                                if island_id not in found and polygons_touch_or_overlap(body, shape):
                                    found[island_id] = round(distance, 3)
                                if island_id in found and island_id not in body_contacts:
                                    x, y, heading = sample(connector, distance)
                                    offset = lateral + (exit_lateral-lateral)*distance/connector_length
                                    exact_body = rectangle(x+math.sin(heading)*offset, y-math.cos(heading)*offset,
                                                           heading, spec["length"], spec["width"])
                                    if polygons_touch_or_overlap(exact_body, shape):
                                        body_contacts[island_id] = round(distance, 3)
                        for island_id, distance in found.items():
                            conflicts.append({"junction": junction, "incoming": incoming, "outgoing": outgoing,
                                              "vehicle_class": name, "entry_lateral_m": lateral,
                                              "exit_lateral_m": exit_lateral, "island": island_id,
                                              "first_sample_m": distance,
                                              "actual_size_body_first_sample_m": body_contacts.get(island_id)})
    return {"network_id": network.id, "fingerprint": network.fingerprint,
            "status": "diagnostic only; no clearance or field-validation claim",
            "sample_spacing_m": SWEEP_SAMPLE_M, "sampled_sweeps": checked,
            "limitations": ["Entry lateral positions sampled at centre and lane limits, or the configured kerb position",
                            "Conservative expanded footprints can yield false positives",
                            "Actual-size contacts are sampled poses, not a continuous trajectory proof",
                            "Lane travel, actual vehicle paths, traffic interactions and dynamics are not checked"],
            "conflicts": conflicts}


def review_lanes(network: RoadNetwork, *, spacing_m: float = 0.5) -> dict:
    """Sample actual-sized vehicle bodies on lane center and lateral limits.

    A sampled contact is evidence to inspect; absence of contacts is not a
    continuous swept-clearance proof or a simulation of actual trajectories.
    """
    if isinstance(spacing_m, bool) or not isinstance(spacing_m, (int, float)) or not math.isfinite(spacing_m) or not 0.1 <= spacing_m <= 5:
        raise ValueError("Lane sample spacing must be between 0.1 and 5 metres")
    islands = [(item["id"], item["shape"],
                (min(p[0] for p in item["shape"]), min(p[1] for p in item["shape"]),
                 max(p[0] for p in item["shape"]), max(p[1] for p in item["shape"]))) for item in network.islands]
    conflicts, sampled = [], 0
    for lane in network.lanes.values():
        steps = max(1, math.ceil(lane.length / spacing_m))
        for vehicle_class, spec in VEHICLE_TYPES.items():
            if not network.lane_allows(lane.id, vehicle_class):
                continue
            low, high = lateral_bounds(lane.width, spec["width"])
            for lateral in sorted({low, (low + high) / 2, high}):
                found = set()
                for index in range(steps + 1):
                    distance = lane.length * index / steps
                    x, y, heading = sample(lane.shape, distance)
                    body = rectangle(x + math.sin(heading)*lateral, y - math.cos(heading)*lateral,
                                     heading, spec["length"], spec["width"])
                    left, bottom = min(p[0] for p in body), min(p[1] for p in body)
                    right, top = max(p[0] for p in body), max(p[1] for p in body)
                    sampled += 1
                    for island_id, polygon, (il, ib, ir, it) in islands:
                        if island_id in found or left > ir or il > right or bottom > it or ib > top:
                            continue
                        if polygons_touch_or_overlap(body, polygon):
                            found.add(island_id)
                            conflicts.append({"lane": lane.id, "vehicle_class": vehicle_class, "lateral_m": lateral,
                                              "island": island_id, "first_sample_m": round(distance, 3)})
    return {"network_id": network.id, "fingerprint": network.fingerprint,
            "status": "sampled lane-body diagnostic only; no clearance or field-validation claim",
            "sample_spacing_m": spacing_m, "sampled_positions": sampled, "conflicts": conflicts,
            "limitations": ["Only centre and lane-edge lateral positions are sampled",
                            "Finite samples do not establish continuous clearance",
                            "Bodies are aligned with the lane heading; additional dynamic yaw is not checked",
                            "Lateral motion, traffic interactions and junction behavior are not simulated"]}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("network", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--lanes", action="store_true", help="Sample vehicle bodies along lanes instead of connectors")
    args = parser.parse_args()
    if args.output.resolve() == args.network.resolve() or args.output.exists():
        parser.error("Choose a new output path distinct from the input network")
    network = RoadNetwork(json.loads(args.network.read_text(encoding="utf-8")))
    result = review_lanes(network) if args.lanes else review(network)
    with args.output.open("x", encoding="utf-8") as target:
        json.dump(result, target, indent=2)
    count = result["sampled_positions"] if args.lanes else result["sampled_sweeps"]
    print(f"Reviewed {count} {'positions' if args.lanes else 'sweeps'}; {len(result['conflicts'])} possible island contacts")


if __name__ == "__main__":
    main()
