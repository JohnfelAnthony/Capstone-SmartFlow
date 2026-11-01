"""One measurement definition for observed and simulated data (design 0.15 and plan Task 26).

Queue: stopped vehicles per approach at the same video-relative sample instants.
Discharge: crossings of the mapped stop line per approach per fixed bin.
Travel time: arrival-line to exit-line duration for the arrival-window cohort, with unfinished vehicles reported.
Arrival order: unique conflicting pairs from different approaches, judged by priority-zone and stop-line entry times.

Approaches are keyed by their boundary node id on both sides. Nothing is dropped silently: unusable samples and bins are
counted, and a measure with no usable evidence reports `None`, never zero.
"""
from __future__ import annotations

import math
import statistics
from pathlib import Path

from services.field_observer_import import ACCEPTED_REVIEW, _load_revision, _read_csv

QUEUE_MATCH_S = 0.5  # a reviewed queue sample counts at a sample instant when its frame time is within this many seconds
REVIEW_FILES = ("queue_samples.csv", "priority_review.csv")


def _finite(value) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)


def classify_pairs(pairs: list[dict], mapping: dict, criteria: dict) -> dict:
    """Eligible conflicting pairs and why the others are excluded (design 0.15 'Arrival-order share').

    Each pair carries movement_a/movement_b ("<origin boundary>-><destination boundary>"), the priority-zone entry times
    priority_a/priority_b, the stop-line entry times entry_a/entry_b, `readiness` of the vehicle that reached the zone first
    at the first entrant's entry ("ready", "blocked" or anything else for unknown) and `visible`. A later vehicle entering
    first is a violation only when the earlier one was ready; nothing is inferred from who entered first alone.
    """
    conflicts = {frozenset(pair) for pair in (mapping.get("movement_conflicts") or {}).get("pairs", [])}
    tie, window = criteria["tie_tolerance_s"], criteria["pair_window_s"]
    excluded: dict[str, int] = {}
    respected = violations = 0

    def skip(reason):
        excluded[reason] = excluded.get(reason, 0) + 1

    for item in pairs:
        movements = (item["movement_a"], item["movement_b"])
        if not item.get("visible", True):
            skip("unobservable")
        elif movements[0].split("->")[0] == movements[1].split("->")[0] or frozenset(movements) not in conflicts:
            skip("nonconflicting")
        elif not all(_finite(item.get(key)) for key in ("priority_a", "priority_b")):
            skip("unobservable")
        elif abs(item["priority_a"] - item["priority_b"]) <= tie:
            skip("tied")
        elif abs(item["priority_a"] - item["priority_b"]) > window:
            skip("noncompeting")
        elif not all(_finite(item.get(key)) for key in ("entry_a", "entry_b")):
            skip("unobservable")
        elif abs(item["entry_a"] - item["entry_b"]) < 1e-6:
            skip("tied")
        elif max(item["priority_a"], item["priority_b"]) > min(item["entry_a"], item["entry_b"]):
            skip("noncompeting")
        else:
            earlier_is_a = item["priority_a"] < item["priority_b"]
            entered_first_is_a = item["entry_a"] < item["entry_b"]
            if earlier_is_a == entered_first_is_a:
                respected += 1
            elif item.get("readiness") == "ready":
                violations += 1
            elif item.get("readiness") == "blocked":
                skip("blocked_earlier")
            else:
                skip("unknown_readiness")
    eligible = respected + violations
    return {"eligible": eligible, "respected": respected, "share": respected / eligible if eligible else None, "excluded": excluded}


def approach_boundaries(mapping: dict) -> dict[str, str]:
    return {item["approach_id"]: item["boundary"] for item in mapping["locations"].values() if item.get("approach_id") and item.get("boundary")}


def locations_with_role(mapping: dict, role: str) -> dict[str, dict]:
    return {name: item for name, item in mapping["locations"].items() if item.get("role") == role}


def _covered(tables: dict, location: str, kinds: tuple, first: float, last: float) -> bool:
    """Complete coverage spans [first, last) and no reviewed bin there lacks a count."""
    for row in tables["reviewed_bins.csv"]:
        if row["location_id"] == location and row["event_type"] in kinds and float(row["start_s"]) < last and float(row["end_s"]) > first and row["count"] == "":
            return False
    reached = first
    for start, end in sorted((float(row["start_s"]), float(row["end_s"])) for row in tables["coverage.csv"]
                             if row["location_id"] == location and row["event_type"] in kinds and row["visibility"] == "complete"):
        if start <= reached + 1e-9:
            reached = max(reached, end)
    return reached >= last - 1e-9


def _number_or_none(value):
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


def summarize_queue(samples: dict[str, dict[int, float]], approaches: list[str]) -> dict:
    """Mean queue per approach over the sample instants that were usable."""
    return {boundary: {"value": statistics.fmean(samples[boundary].values()) if samples.get(boundary) else None,
                       "samples": len(samples.get(boundary, {}))} for boundary in approaches}


def summarize_travel(durations: list[float], unfinished: int, complete: bool) -> dict:
    return {"mean": statistics.fmean(durations) if durations else None, "median": statistics.median(durations) if durations else None,
            "count": len(durations), "unfinished": unfinished, "complete": complete}


def observed_measures(revision_dir: Path, mapping: dict, *, start_s: float, end_s: float, criteria: dict) -> dict:
    """Queue, discharge, travel time and arrival-order evidence from a reviewed revision."""
    manifest, tables = _load_revision(revision_dir)
    for name in REVIEW_FILES:
        if name in (manifest.get("artifact_sha256") or {}):
            tables[name] = _read_csv(Path(revision_dir) / name)
    boundaries = approach_boundaries(mapping)
    interval, bin_s = criteria["queue_sample_interval_s"], criteria["discharge_bin_s"]
    lead_out_s = float(mapping["lead_out_s"])
    accepted = [row for row in tables["events.csv"] if row["review_status"] in ACCEPTED_REVIEW]

    queue = {boundary: {"value": None, "samples": 0, "excluded": {}} for boundary in criteria["approaches"]}
    taken: dict[str, dict[int, float]] = {}
    instants = math.ceil((end_s - start_s) / interval)
    for row in tables.get("queue_samples.csv", []):
        boundary = boundaries.get(row["approach_id"])
        if boundary is None or row["review_status"] not in ACCEPTED_REVIEW:
            continue
        entry = queue.setdefault(boundary, {"value": None, "samples": 0, "excluded": {}})
        moment, count = _number_or_none(row["time_s"]), _number_or_none(row["queue_count"])
        index = round((moment - start_s) / interval) if moment is not None else None
        if moment is None or not 0 <= index < instants or abs(moment - (start_s + index * interval)) > QUEUE_MATCH_S:
            reason = "off_instant"
        elif row["visibility"] != "complete" or count is None:
            reason = "incomplete_visibility"
        elif index in taken.get(boundary, {}):
            reason = "duplicate_instant"
        else:
            taken.setdefault(boundary, {})[index] = count
            continue
        entry["excluded"][reason] = entry["excluded"].get(reason, 0) + 1
    for boundary, summary in summarize_queue(taken, list(queue)).items():
        queue[boundary].update(summary)

    discharge: dict[str, dict] = {}
    bin_count = int((end_s - start_s) / bin_s + 1e-9)
    for name, line in locations_with_role(mapping, "stopline").items():
        bins = discharge.setdefault(line["boundary"], {})
        for index in range(bin_count):
            left, right = start_s + index * bin_s, start_s + (index + 1) * bin_s
            crossings = sum(1 for row in accepted if row["event_type"] == "vehicle_discharge" and row["location_id"] == name and left <= float(row["time_s"]) < right)
            bins[str(index)] = {"value": crossings, "complete": _covered(tables, name, ("vehicle_discharge",), left, right)}

    exit_lines, arrival_lines = locations_with_role(mapping, "exit"), locations_with_role(mapping, "arrival")
    exits: dict[str, float] = {}
    for row in accepted:
        exit_id = row["exit_id"] or row["location_id"]
        if row["event_type"] in {"vehicle_discharge", "vehicle_movement"} and row["episode_id"] and exit_id in exit_lines and float(row["time_s"]) <= end_s + lead_out_s:
            exits[row["episode_id"]] = min(float(row["time_s"]), exits.get(row["episode_id"], math.inf))
    durations, unfinished = [], 0
    for row in accepted:
        if row["event_type"] == "vehicle_arrival" and row["location_id"] in arrival_lines and start_s <= float(row["time_s"]) < end_s:
            finished = exits.get(row["episode_id"]) if row["episode_id"] else None
            if finished is None or finished < float(row["time_s"]):
                unfinished += 1
            else:
                durations.append(finished - float(row["time_s"]))
    complete = (all(_covered(tables, name, ("vehicle_arrival",), start_s, end_s) for name in arrival_lines)
                and all(_covered(tables, name, ("vehicle_discharge", "vehicle_movement"), start_s, end_s + lead_out_s) for name in exit_lines))

    pairs = [{"movement_a": row["movement_a"], "movement_b": row["movement_b"],
              "priority_a": _number_or_none(row["priority_time_a_s"]), "priority_b": _number_or_none(row["priority_time_b_s"]),
              "entry_a": _number_or_none(row["entry_time_a_s"]), "entry_b": _number_or_none(row["entry_time_b_s"]),
              "readiness": row["readiness_of_earlier"], "visible": row["visibility"] == "complete"}
             for row in tables.get("priority_review.csv", [])]
    return {"queue": queue, "discharge": discharge, "travel_time": summarize_travel(durations, unfinished, complete),
            "arrival_order": classify_pairs(pairs, mapping, criteria)}
