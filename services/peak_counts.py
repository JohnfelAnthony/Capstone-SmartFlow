"""Peak-traffic video counts as scenario demand (design: docs/superpowers/specs/2026-11-13-peak-video-counts-in-scenarios-design.md).

The counted side is kept exactly; the unmeasured side is shared equally among legal routes (owner, 2026-11-13). Site A counted vehicles
leaving by each road, so each exit's count is shared among the roads it can come from; Site B counted vehicles arriving, so each road's
count is shared among the roads it can go to. A legal route goes through the study junction for that vehicle type, never back the way it came.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

from services.movement_counts import approach_boundaries
from simulation.network_registry import load_registered_network
from simulation.scenario_config import DEFAULTS, STEADY_DEMAND_END_SECONDS, validate_config

SITES = Path(__file__).resolve().parents[1] / "data" / "sites"
LABEL = "Demand based on video counts with assumed routes"
MINUTES = (5, 10, 15)
PLURALS = {"bus": "buses", "truck": "trucks"}


def _counts_path(network_id: str) -> Path:
    path = SITES / f"{network_id}_peak_counts.json"
    if not path.is_file():
        raise ValueError(f"No peak-traffic video count for {network_id}; only the two study sites have one")
    return path


def load_peak_counts(network_id: str) -> dict:
    return json.loads(_counts_path(network_id).read_text(encoding="utf-8"))


def peak_counts_sha256(network_id: str) -> str:
    """Identity of the count file over its text; read_text turns CRLF into LF, so a Windows checkout gives the same value."""
    return hashlib.sha256(_counts_path(network_id).read_text(encoding="utf-8").encode("utf-8")).hexdigest()


def _legal(network, source: str, destination: str, vehicle_type: str) -> bool:
    route = network.route(source, destination, vehicle_type=vehicle_type)
    return bool(route) and network.intersections[0] in {network.lanes[lane].target for lane in route}


def _notes(counts: dict) -> list[str]:
    notes = []
    if counts["count_direction"] == "leaving":
        notes.append("Vehicles were counted leaving by each road. Where they came from is assumed: each exit's vehicles come equally from every road that can legally reach it.")
    else:
        notes.append("Vehicles were counted arriving on each road. Where they go is assumed: each road's vehicles go equally to every road they can legally reach.")
    if counts["method"] == "automatic_detector" and not counts["reviewed"]:
        notes.append("Vehicle types are automatic detector guesses that nobody has reviewed; the detector has no tricycle class.")
    for item in counts.get("relabelled", []):
        notes.append(f"{item['vehicles']} detected {' and '.join(PLURALS.get(kind, kind) for kind in item['from'])} on {counts['road_names'][item['road']]} count as {item['to']}s: "
                     "buses and trucks are banned there, so they were most likely tricycles.")
    for road in counts.get("assumed", {}):
        notes.append(f"{counts['road_names'][road]} was not counted; it is given the rate and mix of "
                     f"{counts['road_names'][_twin(counts, road)]} (assumed).")
    if counts.get("pedestrians") is None:
        notes.append("Pedestrians were not counted at this site; choose a pedestrian level.")
    notes.append("Each count is a steady rate for the whole run; variation within the video is not modelled. Not calibrated or validated.")
    return notes


def _twin(counts: dict, road: str) -> str:
    """The counted road whose numbers an assumed road copies."""
    return next(name for name, classes in counts["counts"].items() if classes == counts["assumed"][road])


def peak_counts_demand(*, network_id: str, engine_config: dict) -> dict:
    """Replace the draft's vehicle demand with the site's peak-traffic count; Site A also sets its counted pedestrian rate."""
    path = _counts_path(network_id)
    counts = load_peak_counts(network_id)
    network = load_registered_network(network_id)
    legs = approach_boundaries(network)
    seconds = counts["video"]["seconds"]
    known = {**counts["counts"], **counts.get("assumed", {})}
    leaving = counts["count_direction"] == "leaving"

    windows = []
    flows: dict[tuple[str, str], float] = {}  # (origin, exit) -> vehicles in the video
    for road, classes in sorted(known.items()):
        for kind, vehicles in classes.items():
            if not vehicles:
                continue
            # Counted leaving: the road is the exit and the others are origins. Counted arriving: the reverse.
            pairs = [(other, road) if leaving else (road, other) for other in sorted(legs) if other != road]
            pairs = [(origin, exit_) for origin, exit_ in pairs if _legal(network, legs[origin][0], legs[exit_][1], kind)]
            if not pairs:
                raise ValueError(f"{vehicles} {kind} on {road} have no legal route through the study junction")
            share = vehicles/len(pairs)
            for origin, exit_ in pairs:
                flows[(origin, exit_)] = flows.get((origin, exit_), 0.0) + share
                windows.append({"start": 0.0, "end": STEADY_DEMAND_END_SECONDS, "vehicles_per_hour": share*3600/seconds, "vehicle_type": kind,
                                "label": f"{origin} to {exit_} {kind}", "od": [{"source": legs[origin][0], "destination": legs[exit_][1], "weight": 1}]})

    method = "manual count" if counts["method"] == "manual" else "automatic detector count, not reviewed"
    description = (f"{LABEL}: {counts['label'].lower()}, {network_id}, {method} of {counts['video']['file']} ({seconds:g} s); "
                   "steady rates, routes shared equally among legal routes. Scenario-based, not calibrated or validated.")
    sha = peak_counts_sha256(network_id)
    candidate = {**engine_config, "traffic_density": "none", "trips": [], "demand_windows": windows,
                 "demand_source": {"kind": "field_counts", "description": description,
                                   "datasets": [{"kind": "field_counts", "description": description, "schema": "smartflow_peak_counts", "sha256": sha}]}}
    pedestrians = counts.get("pedestrians")
    if pedestrians is not None:
        candidate.update(pedestrian_density="counted", pedestrian_rate_per_hour=pedestrians*3600/seconds)
    elif candidate.get("pedestrian_density") == "counted":
        candidate["pedestrian_density"] = DEFAULTS["pedestrian_density"]

    counted = sum(sum(classes.values()) for classes in counts["counts"].values())
    assumed = sum(sum(classes.values()) for classes in counts.get("assumed", {}).values())
    per_hour = (counted+assumed)*3600/seconds
    by_type = {kind: sum(classes.get(kind, 0) for classes in known.values()) for kind in ("car", "motorcycle", "tricycle", "bus", "truck")}
    roads = []
    for road in ("north", "south", "east", "west"):
        if road not in legs:
            continue
        arriving = round(sum(value for (origin, _), value in flows.items() if origin == road))
        leaving_total = round(sum(value for (_, exit_), value in flows.items() if exit_ == road))
        roads.append({"approach": road, "name": counts["road_names"][road], "arriving": arriving, "leaving": leaving_total,
                      "arriving_assumed": leaving or road in counts.get("assumed", {}), "leaving_assumed": not leaving})
    summary = {
        "label": LABEL, "traffic_label": counts["label"], "video": counts["video"], "method": counts["method"], "reviewed": counts["reviewed"],
        "count_direction": counts["count_direction"], "counted_vehicles": counted, "assumed_vehicles": assumed,
        "vehicles_per_hour": round(per_hour, 1), "entering": {str(minutes): round(per_hour*minutes/60) for minutes in MINUTES},
        "by_type": by_type, "roads": roads,
        "pedestrians": None if pedestrians is None else {"counted": pedestrians, "per_hour": round(pedestrians*3600/seconds, 1)},
        "notes": _notes(counts), "dataset_sha256": sha,
    }
    return {"engine_config": validate_config(DEFAULTS, candidate, network), "summary": summary}
