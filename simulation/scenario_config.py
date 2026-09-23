"""Validated native experiment inputs. No GUI or ML dependency."""
from __future__ import annotations

import copy
import csv
import json
import math
from pathlib import Path

VEHICLE_TYPES = {
    "car": {"length": 4.5, "width": 1.8, "speed_factor": 1.0},
    "motorcycle": {"length": 2.0, "width": 0.8, "speed_factor": 1.0},
    "tricycle": {"length": 3.0, "width": 1.4, "speed_factor": 0.75},
    "bus": {"length": 10.0, "width": 2.5, "speed_factor": 0.85},
    "truck": {"length": 8.0, "width": 2.5, "speed_factor": 0.8},
    "emergency": {"length": 5.0, "width": 2.0, "speed_factor": 1.0},
}
DEFAULTS = {
    "traffic_density": "single", "pedestrian_density": "none", "emergency_mode": "disabled",
    "road_constraint": "None", "green_seconds": 14.0, "closed_lanes": [], "slow_lanes": {},
    "events": [], "signal_plans": {}, "demand_windows": [], "trips": [],
    "demand_source": {"kind": "synthetic", "description": "Seeded study assumptions"},
    "vehicle_mix": {"car": 1.0}, "routing_mode": "adaptive", "reroute_interval": 15.0,
    "reroute_improvement": 0.15, "pedestrian_speed": 1.4, "crossing_length": 18.0,
    "pedestrian_max_wait": 90.0, "max_active_vehicles": 300, "max_pending_vehicles": 2000,
}


def number(value, label, minimum=0.0, maximum=86400.0):
    if isinstance(value, bool):
        raise ValueError(f"{label} must be a number")
    try:
        result = float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{label} must be a finite number") from exc
    if not math.isfinite(result) or not minimum <= result <= maximum:
        raise ValueError(f"{label} must be between {minimum} and {maximum}")
    return result


def object_config(value, label):
    """Decode persisted JSON without treating null/false/arrays as empty settings."""
    if isinstance(value, str):
        try:
            value = json.loads(value)
        except (TypeError, ValueError) as exc:
            raise ValueError(f"{label} must be a JSON object") from exc
    if not isinstance(value, dict):
        raise ValueError(f"{label} must be an object")
    return copy.deepcopy(value)


def validate_config(current: dict, settings: dict, network) -> dict:
    """Build a candidate before committing anything to a running engine."""
    result = copy.deepcopy(current)
    if not isinstance(settings, dict) or any(not isinstance(key, str) for key in settings):
        raise ValueError("Engine settings must be an object with named fields")
    unknown = settings.keys() - (DEFAULTS.keys() | {"controlled_junction", "intersection_id"})
    if unknown:
        raise ValueError(f"Unknown engine settings: {', '.join(sorted(unknown))}")
    result.update(copy.deepcopy(settings))
    for key in ("slow_lanes", "signal_plans", "vehicle_mix", "demand_source"):
        if not isinstance(result[key], dict):
            raise ValueError(f"{key} must be an object")
    for key in ("closed_lanes", "events", "demand_windows", "trips"):
        if not isinstance(result[key], list):
            raise ValueError(f"{key} must be a list")
    for key in ("events", "demand_windows", "trips"):
        if any(not isinstance(item, dict) for item in result[key]):
            raise ValueError(f"{key} entries must be objects")
    if any(not isinstance(item, dict) for item in result["signal_plans"].values()):
        raise ValueError("Signal plans must be objects")
    if any(not isinstance(lane, str) for lane in result["closed_lanes"]):
        raise ValueError("Closed lanes must contain lane IDs")
    requested = result.pop("intersection_id", network.id)
    if not isinstance(requested, str) or requested not in {network.id, "tagum_1", "tagum_2", "tagum_3"}:
        raise ValueError("Unknown road network")
    result.setdefault("controlled_junction", network.intersections[0])
    if result["controlled_junction"] not in network.intersections:
        raise ValueError("Unknown controlled junction")
    for key, allowed in (("traffic_density", {"none", "single", "low", "medium", "high", "very high"}),
                         ("pedestrian_density", {"none", "low", "medium", "high"})):
        result[key] = str(result[key]).lower()
        if result[key] not in allowed:
            raise ValueError(f"Unsupported {key}")
    emergency = str(result["emergency_mode"]).lower()
    if emergency not in {"disabled", "enabled", "enabled (1 vehicle)", "enabled (1 ambulance)", "enabled (2 vehicles)"}:
        raise ValueError("Unsupported emergency mode")
    result["emergency_mode"] = emergency
    if not isinstance(result["routing_mode"], str) or result["routing_mode"] not in {"adaptive", "static"}:
        raise ValueError("routing_mode must be adaptive or static")
    for key, low, high in (("green_seconds", 5, 180), ("reroute_interval", 1, 300),
                           ("reroute_improvement", 0, .9), ("pedestrian_speed", .3, 3),
                           ("crossing_length", 2, 50), ("pedestrian_max_wait", 10, 600),
                           ("max_active_vehicles", 1, 2000), ("max_pending_vehicles", 1, 100000)):
        result[key] = number(result[key], key, low, high)
    for key in ("max_active_vehicles", "max_pending_vehicles"):
        if result[key] != int(result[key]):
            raise ValueError(f"{key} must be an integer")
        result[key] = int(result[key])
    if "road_constraint" in settings:
        result["closed_lanes"], result["slow_lanes"] = [], {}
        constraint = str(result["road_constraint"]).lower()
        if constraint not in {"none", "", "no constraints"}:
            candidate = next((lane.id for lane in network.lanes.values() if lane.source in network.intersections and lane.target in network.intersections), None)
            if candidate is None:
                raise ValueError("This network has no internal lane for a disruption preset")
            if "flood" in constraint or "construct" in constraint:
                result["slow_lanes"][candidate] = .35
            elif "clos" in constraint or "accident" in constraint:
                result["closed_lanes"] = [candidate]
            else:
                raise ValueError("Unknown disruption preset; use explicit lane events")
        for key in ("closed_lanes", "slow_lanes"):
            if key in settings:
                result[key] = copy.deepcopy(settings[key])
    if set(result["closed_lanes"]) - network.lanes.keys() or result["slow_lanes"].keys() - network.lanes.keys():
        raise ValueError("Unknown constrained lane")
    result["closed_lanes"] = sorted(set(result["closed_lanes"]))
    result["slow_lanes"] = {lane: number(factor, "speed factor", .05, 1) for lane, factor in result["slow_lanes"].items()}
    for event in result["events"]:
        if event.keys() - {"time", "lane_id", "closed", "speed_factor", "label"}:
            raise ValueError("Unknown lane event field")
        event["time"] = number(event.get("time"), "event time")
        if not isinstance(event.get("lane_id"), str) or event["lane_id"] not in network.lanes:
            raise ValueError("Unknown event lane")
        if "closed" not in event and "speed_factor" not in event:
            raise ValueError("An event needs closed or speed_factor")
        if "closed" in event and not isinstance(event["closed"], bool):
            raise ValueError("closed must be true or false")
        if "speed_factor" in event:
            event["speed_factor"] = number(event["speed_factor"], "speed factor", .05, 1)
    result["events"].sort(key=lambda event: event["time"])
    for node, plan in result["signal_plans"].items():
        if node not in network.intersections:
            raise ValueError("Unknown signal junction")
        if plan.keys() - {"mode", "green_seconds", "minimum_green", "maximum_green", "yellow_seconds", "all_red_seconds", "phase_order", "offset_seconds"}:
            raise ValueError("Unknown signal plan field")
        if not isinstance(plan.get("mode", "signalized"), str) or plan.get("mode", "signalized") not in {"signalized", "all_way_stop"}:
            raise ValueError("Signal mode must be signalized or all_way_stop")
        available = {network.lanes[lane].approach for lane in network.incoming[node]} | {"pedestrian"}
        order = plan.get("phase_order", [a for a in ("north", "east", "south", "west", "pedestrian") if a in available])
        if not isinstance(order, list) or any(not isinstance(item, str) for item in order) or len(order) != len(set(order)) or set(order) != available:
            raise ValueError("phase_order must contain every available approach and pedestrian exactly once")
        plan["phase_order"] = order
        for key, default, low, high in (("minimum_green", 10, 5, 60), ("maximum_green", 60, 10, 180),
                                       ("green_seconds", result["green_seconds"], 5, 180),
                                       ("yellow_seconds", 3, 2, 6), ("all_red_seconds", 1, 1, 10),
                                       ("offset_seconds", 0, 0, 3600)):
            plan[key] = number(plan.get(key, default), key, low, high)
        if not plan["minimum_green"] <= plan["green_seconds"] <= plan["maximum_green"]:
            raise ValueError("Signal timing requires minimum_green <= green_seconds <= maximum_green")
    mix = result["vehicle_mix"]
    if not mix or mix.keys() - VEHICLE_TYPES.keys():
        raise ValueError("Unknown or empty vehicle mix")
    result["vehicle_mix"] = {kind: number(weight, "vehicle weight", 0, 1e6) for kind, weight in mix.items()}
    if sum(result["vehicle_mix"].values()) <= 0:
        raise ValueError("Vehicle mix needs a positive weight")
    source_kind = result["demand_source"].get("kind")
    if not isinstance(source_kind, str) or source_kind not in {"synthetic", "observed"}:
        raise ValueError("Demand source kind must be synthetic or observed")
    if result["demand_source"]["kind"] == "observed" and not result["demand_source"].get("description"):
        raise ValueError("Observed demand needs its survey/source description")
    def validate_od(item):
        source, target = item.get("source"), item.get("destination")
        if source not in network.boundaries or target not in network.boundaries or not network.route(source, target):
            raise ValueError("Demand needs distinct, connected boundary source/destination IDs")
    for window in result["demand_windows"]:
        if window.keys() - {"start", "end", "vehicles_per_hour", "od", "label"}:
            raise ValueError("Unknown demand window field")
        window["start"] = number(window.get("start"), "window start")
        window["end"] = number(window.get("end"), "window end")
        if window["end"] <= window["start"]:
            raise ValueError("Demand window end must follow start")
        window["vehicles_per_hour"] = number(window.get("vehicles_per_hour"), "vehicles/hour", 0, 36000)
        if not isinstance(window.get("od", []), list) or any(not isinstance(item, dict) for item in window.get("od", [])):
            raise ValueError("OD must be a list of objects")
        for od in window.get("od", []):
            if od.keys() - {"source", "destination", "weight"}:
                raise ValueError("Unknown OD field")
            validate_od(od)
            od["weight"] = number(od.get("weight", 1), "OD weight", .00001, 1e6)
    for trip in result["trips"]:
        if trip.keys() - {"time", "source", "destination", "vehicle_type"}:
            raise ValueError("Unknown trip field")
        trip["time"] = number(trip.get("time"), "trip time")
        validate_od(trip)
        trip.setdefault("vehicle_type", "car")
        if not isinstance(trip["vehicle_type"], str) or trip["vehicle_type"] not in VEHICLE_TYPES:
            raise ValueError("Unknown trip vehicle type")
    return result


def read_trip_csv(path: str | Path) -> list[dict]:
    """CSV columns: time,source,destination,vehicle_type (optional). Validated on configure."""
    with Path(path).open(encoding="utf-8-sig", newline="") as stream:
        rows = list(csv.DictReader(stream))
    return [{**row, "time": number(row.get("time"), "trip time"),
             "vehicle_type": row.get("vehicle_type") or "car"} for row in rows]
