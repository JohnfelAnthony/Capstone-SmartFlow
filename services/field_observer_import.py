"""Reviewed Field Observer revisions to native scenario demand (design 0.11 of the two-site plan).

Templates contain no asserted field observations. A conversion stops, naming the line and interval, whenever
coverage, review status, mapping, class decisions or the initial state do not support the demand it would create;
it never fills a gap with zero demand.
"""
from __future__ import annotations

import csv
import hashlib
import io
import json
import math
from collections import Counter
from pathlib import Path

from simulation.road_network import RoadNetwork, length
from simulation.scenario_config import VEHICLE_TYPES


DEFAULT_CLASS_MAP = {
    "car": "car", "motorcycle": "motorcycle", "tricycle": "tricycle",
    "tricycle/bao_bao": "tricycle", "bus": "bus", "truck": "truck",
}
MIN_LEAD_OUT_S = 120.0
AT_BOUNDARY_TOLERANCE_M = 0.01  # the site template rounds road lengths to 0.01 m
PEDESTRIAN_BIN_S = 60
ACCEPTED_REVIEW = {"accepted", "corrected"}
REVISION_FILES = ("events.csv", "coverage.csv", "reviewed_bins.csv", "lines.json")
ROLES = {"arrival", "priority", "stopline", "exit", "crossing"}
ROLE_EVENT_TYPES = {"arrival": ("vehicle_arrival",), "exit": ("vehicle_discharge", "vehicle_movement"), "crossing": ("pedestrian_start",)}
INSUFFICIENT_INITIAL_STATE = "INSUFFICIENT_INITIAL_STATE"


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


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _read_csv(path: Path) -> list[dict]:
    with open(path, newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def _seconds(value) -> str:
    return f"{float(value):g}"


def _number(value, label: str, minimum: float = 0.0) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or value < minimum:
        raise ValueError(f"{label} must be a number of at least {minimum:g}")
    return float(value)


def _csv_text(header: tuple, rows) -> str:
    out = io.StringIO()
    writer = csv.writer(out, lineterminator="\n")
    writer.writerow(header)
    writer.writerows(rows)
    return out.getvalue()


def _boundary_road_length(network: RoadNetwork, boundary: str) -> float:
    roads = [road for road in network.payload["roads"] if boundary in (road["source"], road["target"])]
    if len(roads) != 1:
        raise ValueError(f"Boundary {boundary} must connect to exactly one road")
    return length(roads[0]["shape"])


def _class_key(row: dict) -> str:
    return row["reviewed_class"] if not row["vehicle_subtype"] else f"{row['reviewed_class']}/{row['vehicle_subtype']}"


def _validate_mapping(mapping: dict, network: RoadNetwork) -> dict:
    """Return the effective class map after checking the mapping belongs to this network and is usable."""
    if mapping.get("network_id") != network.id or mapping.get("network_sha256") != network.fingerprint:
        raise ValueError(f"The mapping was made for another network than '{network.id}'; regenerate it for this network")
    locations = mapping.get("locations")
    if not isinstance(locations, dict) or not locations:
        raise ValueError("The mapping has no locations; map each counting line to a boundary first")
    for location_id, item in locations.items():
        role = item.get("role") if isinstance(item, dict) else None
        if role not in ROLES:
            raise ValueError(f"{location_id} needs a role of {', '.join(sorted(ROLES))}")
        if role in {"arrival", "exit"} and item.get("boundary") not in network.boundaries:
            raise ValueError(f"{location_id} must name a boundary of network '{network.id}'")
        if role == "arrival":
            _number(item.get("distance_from_junction_m"), f"{location_id} distance_from_junction_m")
    lead_out = mapping.get("lead_out_s")
    if isinstance(lead_out, bool) or not isinstance(lead_out, (int, float)) or lead_out < MIN_LEAD_OUT_S:
        raise ValueError(f"lead_out_s must be at least {MIN_LEAD_OUT_S:g} s of reviewed footage after the window")
    class_map = {**DEFAULT_CLASS_MAP, **(mapping.get("class_map") or {})}
    for key, value in class_map.items():
        if value != "exclude" and value not in VEHICLE_TYPES:
            raise ValueError(f"class_map '{key}' must be one of {', '.join(VEHICLE_TYPES)} or \"exclude\"")
    return class_map


def _load_revision(revision_dir: Path) -> tuple[dict, dict[str, list[dict]]]:
    manifest_path = Path(revision_dir) / "manifest.json"
    if not manifest_path.exists():
        raise ValueError("The revision has no manifest.json")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    hashes = manifest.get("artifact_sha256") or {}
    for name in REVISION_FILES:
        if name not in hashes or not (Path(revision_dir) / name).exists():
            raise ValueError(f"The revision is missing {name}")
    for name, expected in hashes.items():
        path = Path(revision_dir) / name
        if Path(name).name != name or not path.exists() or _sha256(path) != expected:
            raise ValueError(f"{name} changed since this revision was exported")
    return manifest, {name: _read_csv(Path(revision_dir) / name) for name in ("events.csv", "coverage.csv", "reviewed_bins.csv")}


def _require_reviewed(tables: dict, location: str, kinds: tuple, first: float, last: float, purpose: str) -> None:
    """Every reviewed bin overlapping [first, last) must have a count, and complete coverage must span it."""
    for row in tables["reviewed_bins.csv"]:
        overlaps = float(row["start_s"]) < last and float(row["end_s"]) > first
        if row["location_id"] == location and row["event_type"] in kinds and overlaps and row["count"] == "":
            raise ValueError(f"{location} {_seconds(row['start_s'])}–{_seconds(row['end_s'])} s is incomplete: "
                             f"the reviewed bin has no count (incomplete coverage or unresolved events)")
    intervals = sorted((float(row["start_s"]), float(row["end_s"])) for row in tables["coverage.csv"]
                       if row["location_id"] == location and row["event_type"] in kinds and row["visibility"] == "complete")
    reached = first
    for start, end in intervals:
        if start <= reached + 1e-9:
            reached = max(reached, end)
    if reached < last - 1e-9:
        raise ValueError(f"{location} coverage ends at {_seconds(reached)} s; {purpose} needs it until {_seconds(last)} s")


def convert_revision(revision_dir: Path, mapping: dict, network: RoadNetwork, *, origin_s: float, start_s: float, end_s: float) -> dict:
    """Turn a reviewed revision into `trips` and `pedestrian_counts` CSV text plus timing and provenance.

    `origin_s` is the simulation origin in video seconds and `[start_s, end_s)` the measurement window. A vehicle
    enters its boundary `(approach length - line distance) / upstream speed` before it crosses the counting line,
    so demand before `start_s` is lead-in that stays in the engine across measurement start.
    """
    origin_s, start_s, end_s = (_number(value, name) for value, name in ((origin_s, "origin_s"), (start_s, "start_s"), (end_s, "end_s")))
    if not origin_s <= start_s < end_s:
        raise ValueError("Require 0 <= origin_s <= start_s < end_s")
    class_map = _validate_mapping(mapping, network)
    manifest, tables = _load_revision(revision_dir)
    locations, lead_out_s = mapping["locations"], float(mapping["lead_out_s"])
    speeds = mapping.get("upstream_speed_mps_by_class") or {}
    initialization = mapping.get("initialization")
    horizon = end_s + lead_out_s
    has_empty_start_evidence = (isinstance(initialization, dict) and initialization.get("state") == "empty"
                                and str(initialization.get("verified_by", "")).strip() and str(initialization.get("evidence", "")).strip())
    if not has_empty_start_evidence:
        raise ValueError(f"{INSUFFICIENT_INITIAL_STATE}: the mapping has no reviewed evidence that the approaches were empty at "
                         f"origin {_seconds(origin_s)} s; choose an earlier origin or document an observed empty start")

    arrival_lines, shifts = {}, {}
    for location_id, item in locations.items():
        if item["role"] != "arrival":
            continue
        road_length = _boundary_road_length(network, item["boundary"])
        distance = float(item["distance_from_junction_m"])
        if distance > road_length + 1e-9:
            raise ValueError(f"{location_id} is {_seconds(distance)} m from the junction; the modelled approach is {_seconds(road_length)} m")
        gap = max(0.0, road_length - distance)
        arrival_lines[location_id] = (item, road_length, gap)
        approach_speeds = speeds.get(item.get("approach_id"), {})
        shifts[location_id] = max((gap / float(entry["speed_mps"]) for entry in approach_speeds.values()), default=0.0) if gap > AT_BOUNDARY_TOLERANCE_M else 0.0
    if lead_out_s < max(shifts.values(), default=0.0):
        raise ValueError(f"lead_out_s ({_seconds(lead_out_s)} s) is shorter than the largest boundary-to-line shift ({_seconds(max(shifts.values()))} s)")
    for location_id, item in locations.items():
        kinds = ROLE_EVENT_TYPES.get(item["role"])
        if kinds is None:
            continue
        if item["role"] == "arrival":
            _require_reviewed(tables, location_id, kinds, origin_s, end_s + shifts[location_id], "the demand")
        elif item["role"] == "exit":
            _require_reviewed(tables, location_id, kinds, origin_s, horizon, "the lead-out")
        else:
            _require_reviewed(tables, location_id, kinds, origin_s, end_s, "the pedestrian demand")

    accepted = [row for row in tables["events.csv"] if row["review_status"] in ACCEPTED_REVIEW]
    arrivals = [row for row in accepted if row["event_type"] == "vehicle_arrival"]
    for row in arrivals:
        if locations.get(row["location_id"], {}).get("role") != "arrival":
            raise ValueError(f"Arrival event {row['event_id']} is at {row['location_id']}, which the mapping does not list as an arrival line")
    unmapped = Counter(_class_key(row) for row in arrivals if float(row["time_s"]) >= origin_s and _class_key(row) not in class_map)
    if unmapped:
        listing = ", ".join(f"{name}: {count} vehicle(s)" for name, count in sorted(unmapped.items()))
        raise ValueError(f"{listing} have no class_map entry; choose one of {', '.join(VEHICLE_TYPES)} or \"exclude\" for each class")

    exits: dict[str, tuple[float, str]] = {}
    for row in accepted:
        if row["event_type"] not in {"vehicle_discharge", "vehicle_movement"} or not row["episode_id"]:
            continue
        exit_id = row["exit_id"] or (row["location_id"] if locations.get(row["location_id"], {}).get("role") == "exit" else "")
        if not exit_id:
            continue
        if locations.get(exit_id, {}).get("role") != "exit":
            raise ValueError(f"exit_id {exit_id} (event {row['event_id']}) is not an exit line in the mapping")
        moment, boundary = float(row["time_s"]), locations[exit_id]["boundary"]
        if moment > horizon:
            continue
        known = exits.get(row["episode_id"])
        if known and known[1] != boundary:
            raise ValueError(f"Episode {row['episode_id']} has exits at both {known[1]} and {boundary}; resolve it in review")
        if not known or moment < known[0]:
            exits[row["episode_id"]] = (moment, boundary)

    trips, excluded = [], Counter()
    periods = Counter(lead_in=0, measurement=0, follow_up=0)
    in_system = missing_exit = follow_up_missing = before_origin = 0
    used_speeds: dict[str, dict] = {}
    episodes_seen = set()
    for row in sorted(arrivals, key=lambda item: (float(item["time_s"]), item["event_id"])):
        observed, item = float(row["time_s"]), locations[row["location_id"]]
        if row["episode_id"]:
            if row["episode_id"] in episodes_seen:
                raise ValueError(f"Episode {row['episode_id']} has more than one arrival event; resolve it in review")
            episodes_seen.add(row["episode_id"])
        vehicle_class = class_map[_class_key(row)] if _class_key(row) in class_map else None
        if vehicle_class == "exclude":
            if origin_s <= observed < end_s:
                excluded[_class_key(row)] += 1
            continue
        if vehicle_class is None:
            continue  # observed before the origin, so it has no class decision to make
        _, _, gap = arrival_lines[row["location_id"]]
        shift = 0.0
        if gap > AT_BOUNDARY_TOLERANCE_M:
            entry = speeds.get(item.get("approach_id"), {}).get(vehicle_class)
            if not entry or not float(entry.get("speed_mps", 0)) > 0:
                raise ValueError(f"No upstream speed estimate for approach {item.get('approach_id')} class {vehicle_class}; "
                                 f"add a positive speed_mps and source to upstream_speed_mps_by_class")
            shift = gap / float(entry["speed_mps"])
            used_speeds.setdefault(row["location_id"], {})[vehicle_class] = {"speed_mps": float(entry["speed_mps"]), "source": entry.get("source", "")}
        boundary_time = observed - shift
        exit_ = exits.get(row["episode_id"]) if row["episode_id"] else None
        if boundary_time >= horizon:
            continue
        if boundary_time < origin_s:
            if observed >= origin_s or (exit_ is not None and exit_[0] >= origin_s):
                in_system += 1
            else:
                before_origin += 1
            continue
        period = "lead_in" if boundary_time < start_s else "measurement" if boundary_time < end_s else "follow_up"
        if exit_ is None:
            if period == "follow_up":
                follow_up_missing += 1
            else:
                missing_exit += 1
            continue
        if exit_[0] < observed - 1e-9:
            raise ValueError(f"Episode {row['episode_id']} exits at {_seconds(exit_[0])} s before it arrives at {_seconds(observed)} s")
        periods[period] += 1
        trips.append((round(boundary_time - origin_s, 1), item["boundary"], exit_[1], vehicle_class))
    if in_system:
        raise ValueError(f"{INSUFFICIENT_INITIAL_STATE}: {in_system} vehicle(s) were already on the approaches at origin {_seconds(origin_s)} s "
                         f"(boundary entry before the origin); choose an earlier origin whose start is observed empty. Nothing was dropped or moved to zero.")
    if missing_exit:
        raise ValueError(f"{missing_exit} arrivals have no exit within {_seconds(horizon)} s; review the exit lines or extend the lead-out")

    trips.sort()
    pedestrian_bins = Counter()
    for row in accepted:
        item = locations.get(row["location_id"])
        if row["event_type"] == "pedestrian_start" and item and item["role"] == "crossing" and origin_s <= float(row["time_s"]) < end_s:
            junction = item.get("junction") or (network.intersections[0] if len(network.intersections) == 1 else None)
            if junction not in network.intersections:
                raise ValueError(f"{row['location_id']} needs a junction; the network has several")
            pedestrian_bins[(int((float(row["time_s"]) - origin_s) // PEDESTRIAN_BIN_S), junction)] += 1
    pedestrian_csv = _csv_text(("start_s", "end_s", "junction", "count"),
                               ((index * PEDESTRIAN_BIN_S, (index + 1) * PEDESTRIAN_BIN_S, junction, count)
                                for (index, junction), count in sorted(pedestrian_bins.items()))) if pedestrian_bins else None

    timing = {"origin_s": origin_s, "measurement_start_s": start_s - origin_s, "measurement_duration_s": end_s - start_s,
              "demand_end_s": horizon - origin_s}
    assumptions = {location_id: {"distance_from_junction_m": float(arrival_lines[location_id][0]["distance_from_junction_m"]),
                                 "approach_length_m": arrival_lines[location_id][1], "speeds": classes}
                   for location_id, classes in used_speeds.items()}
    return {
        "trips_csv": _csv_text(("time_s", "source", "destination", "vehicle_type"),
                               ((f"{moment:.1f}", source, destination, vehicle_class) for moment, source, destination, vehicle_class in trips)),
        "pedestrian_counts_csv": pedestrian_csv,
        "summary": {"trips": len(trips), "by_class": dict(Counter(trip[3] for trip in trips)),
                    "by_movement": dict(Counter(f"{trip[1]}->{trip[2]}" for trip in trips)), "excluded_by_class": dict(excluded),
                    "demand_by_period": dict(periods), "before_origin_arrivals": before_origin,
                    "follow_up_arrivals_without_exit": follow_up_missing,
                    "travel_time_follow_up": "insufficient" if follow_up_missing else "sufficient",
                    "pedestrian_starts": sum(pedestrian_bins.values())},
        "timing": timing,
        "provenance": {"survey_id": manifest.get("survey_id"), "take_id": manifest.get("take_id"), "revision": manifest.get("revision"),
                       "manifest_sha256": _sha256(Path(revision_dir) / "manifest.json"),
                       "reviewed_bins_sha256": _sha256(Path(revision_dir) / "reviewed_bins.csv"),
                       "origin_s": origin_s, "window": [start_s, end_s], "measurement_start_s": timing["measurement_start_s"],
                       "demand_end_s": timing["demand_end_s"], "lead_out_s": lead_out_s, "initialization": initialization,
                       "upstream_time_assumptions": assumptions,
                       "mapping_sha256": hashlib.sha256(json.dumps(mapping, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()},
    }
