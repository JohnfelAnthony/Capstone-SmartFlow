"""A reviewed Field Observer export becomes the scenario's demand (D38): counts per class, approach and turn, as one steady hourly rate each.

The scenario is "scenario-based, demand from field counts, not calibrated or validated". The counts are read at the counting
lines and used as boundary entry rates: no lead time between the line and the boundary is modelled. A blank reviewed bin, a
coverage gap, an unknown approach name, a vehicle with no reviewed exit or a changed file stops the import with the reason;
nothing is ever filled with zero.
"""
from __future__ import annotations

import csv
import hashlib
import io
import json
from collections import Counter

from services.field_observer_import import ACCEPTED_REVIEW, REVISION_FILES, _require_reviewed, _seconds
from services.movement_counts import approach_boundaries
from simulation.network_registry import load_registered_network
from simulation.scenario_config import DEFAULTS, validate_config

MAX_FILE_BYTES = 5_000_000
RUN_END_SECONDS = 86400.0  # a demand window's end: beyond the longest run, so the counted rate applies for the whole run
TAIL_SECONDS = 60.0  # a vehicle seen arriving this close to the end of the footage may simply not have left it yet
# Field Observer class (class/subtype) to the five engine classes. `pending` marks the two choices the team has not decided.
CLASS_MAP = {"car": "car", "motorcycle": "motorcycle", "tricycle": "tricycle", "tricycle/bao_bao": "tricycle", "bus": "bus", "truck": "truck",
             "tricycle/pedicab": "tricycle", "jeepney": "bus"}
PENDING = {"tricycle/pedicab": "A pedal pedicab is simulated as a tricycle. Pending the team's decision.",
           "jeepney": "A jeepney is simulated as a bus (nearest size). Pending the team's decision."}
LIMITS = ("16 minutes of one day, midday, are one observation of the site. Simulation settings (speeds, gaps, junction behaviour) are not tuned "
          "to the site, and counts at the lines are used as boundary entry rates. Not calibrated or validated.")


def _class_key(row: dict) -> str:
    return row["reviewed_class"] if not row["vehicle_subtype"] else f"{row['reviewed_class']}/{row['vehicle_subtype']}"


def _table(text: str) -> list[dict]:
    return list(csv.DictReader(io.StringIO(text, newline="")))


def _verified_files(files: dict) -> tuple[dict, dict[str, str]]:
    """The manifest and the four files it hashes. Files the manifest lists but that were not given are not checked."""
    for name in ("manifest.json", *REVISION_FILES):
        text = files.get(name)
        if not isinstance(text, str) or not text.strip():
            raise ValueError(f"Choose all five files of the revision; {name} is missing")
        if len(text.encode("utf-8")) > MAX_FILE_BYTES:
            raise ValueError(f"{name} is larger than {MAX_FILE_BYTES // 1_000_000} MB")
    try:
        manifest = json.loads(files["manifest.json"])
    except ValueError as exc:
        raise ValueError("manifest.json is not valid JSON") from exc
    hashes = manifest.get("artifact_sha256") if isinstance(manifest, dict) else None
    if not isinstance(hashes, dict):
        raise ValueError("manifest.json has no artifact_sha256 list; this is not a Field Observer revision")
    for name in REVISION_FILES:
        if name not in hashes:
            raise ValueError(f"The revision is missing {name}")
        if hashlib.sha256(files[name].encode("utf-8")).hexdigest() != hashes[name]:
            raise ValueError(f"{name} changed since this revision was exported")
    return manifest, {name: files[name] for name in REVISION_FILES}


def _lines(text: str, manifest: dict, approaches: dict) -> tuple[dict, dict]:
    """Arrival lines and exit lines as location -> approach name; every name must be one of the site's approaches."""
    lines = json.loads(text)
    if lines.get("take_id") != manifest.get("take_id"):
        raise ValueError("lines.json belongs to a different take than manifest.json")
    arrivals, exits = {}, {}
    for line in lines.get("lines", []):
        if line.get("event_type") == "vehicle_arrival":
            target = arrivals
        elif line.get("role") == "exit":
            target = exits
        else:
            continue
        approach = line.get("approach_id")
        if approach not in approaches:
            raise ValueError(f"Line {line.get('location_id')} names approach '{approach}'; at this site it must be one of {', '.join(sorted(approaches))}")
        target[line["location_id"]] = approach
    if not arrivals or not exits:
        raise ValueError("lines.json needs at least one vehicle arrival line and one line with role \"exit\"")
    return arrivals, exits


def import_field_counts(*, files: dict, network_id: str, engine_config: dict) -> dict:
    """Replace the draft's vehicle demand by the export's counts; pedestrians and every other setting are untouched."""
    network = load_registered_network(network_id)
    approaches = approach_boundaries(network)  # refuses a network that is not a study site
    manifest, texts = _verified_files(files)
    arrival_lines, exit_lines = _lines(texts["lines.json"], manifest, approaches)
    tables = {"events.csv": _table(texts["events.csv"]), "coverage.csv": _table(texts["coverage.csv"]), "reviewed_bins.csv": _table(texts["reviewed_bins.csv"])}

    # Complete bins only: a blank count is a bin nobody finished reviewing, not a bin with no vehicles.
    vehicle_bins = [row for row in tables["reviewed_bins.csv"] if row["location_id"] in {*arrival_lines, *exit_lines}]
    for row in vehicle_bins:
        if row["count"] == "":
            raise ValueError(f"{row['location_id']} {_seconds(row['start_s'])}–{_seconds(row['end_s'])} s has no reviewed count "
                             f"(incomplete coverage or unresolved events); finish the review in Field Observer and export again. Nothing is filled with zero")
    edges = {location: sorted({(float(row["start_s"]), float(row["end_s"])) for row in vehicle_bins if row["location_id"] == location}) for location in arrival_lines}
    grid = next(iter(edges.values()))
    if not grid or any(other != grid for other in edges.values()):
        raise ValueError("The arrival lines do not share one time-bin grid; export the revision again with one bin size")
    first, last = grid[0][0], grid[-1][1]
    for location in arrival_lines:
        _require_reviewed(tables, location, ("vehicle_arrival",), first, last, "the counts")
    for location in exit_lines:
        _require_reviewed(tables, location, ("vehicle_discharge", "vehicle_movement"), first, last, "the turn counts")

    accepted = [row for row in tables["events.csv"] if row["review_status"] in ACCEPTED_REVIEW]
    exits: dict[str, tuple[float, str]] = {}
    for row in accepted:
        if row["event_type"] not in {"vehicle_discharge", "vehicle_movement"} or not row["episode_id"]:
            continue
        place = row["exit_id"] or row["location_id"]
        if place in exit_lines and (row["episode_id"] not in exits or float(row["time_s"]) < exits[row["episode_id"]][0]):
            exits[row["episode_id"]] = (float(row["time_s"]), place)

    counts: Counter = Counter()          # (bin index, from, to, engine class) -> vehicles
    by_class: Counter = Counter()        # field class key -> vehicles seen
    not_simulated: Counter = Counter()
    missing_exit: list[str] = []
    not_counted_at_the_end = 0
    for row in sorted((item for item in accepted if item["event_type"] == "vehicle_arrival" and item["location_id"] in arrival_lines),
                      key=lambda item: (float(item["time_s"]), item["event_id"])):
        moment = float(row["time_s"])
        if not first <= moment < last:
            continue
        index = next(position for position, (left, right) in enumerate(grid) if left <= moment < right)
        key = _class_key(row)
        exit_ = exits.get(row["episode_id"]) if row["episode_id"] else None
        if exit_ is None:
            if moment >= last - TAIL_SECONDS:
                not_counted_at_the_end += 1
            else:
                missing_exit.append(row["event_id"])
            continue
        by_class[key] += 1
        origin, destination = arrival_lines[row["location_id"]], exit_lines[exit_[1]]
        if origin == destination:
            raise ValueError(f"Vehicle {row['event_id']} goes {origin} to {destination}; a vehicle cannot leave by the leg it arrived on. Correct it in the review")
        engine_class = CLASS_MAP.get(key)
        if engine_class is None:
            not_simulated[key] += 1
            continue
        counts[(index, origin, destination, engine_class)] += 1
    if missing_exit:
        raise ValueError(f"{len(missing_exit)} vehicle(s) have no reviewed exit and arrived more than {TAIL_SECONDS:g} s before the footage ended "
                         f"(first: {', '.join(missing_exit[:3])}); their turn is unknown. Review the exit lines for them in Field Observer")
    if not counts:
        raise ValueError("The export has no countable vehicle movements")

    # What the reviewed bins say must equal what the accepted events say, or the export is not what it claims to be.
    reviewed: Counter = Counter()
    for row in tables["reviewed_bins.csv"]:
        if row["location_id"] in arrival_lines and row["event_type"] == "vehicle_arrival":
            reviewed[(row["location_id"], float(row["start_s"]), _class_key(row))] += int(float(row["count"]))
    seen: Counter = Counter()
    for row in accepted:
        if row["event_type"] == "vehicle_arrival" and row["location_id"] in arrival_lines and first <= float(row["time_s"]) < last:
            left = next(left for left, right in grid if left <= float(row["time_s"]) < right)
            seen[(row["location_id"], left, _class_key(row))] += 1
    for key in reviewed.keys() | seen.keys():
        if reviewed[key] != seen[key]:
            raise ValueError(f"{key[0]} from {_seconds(key[1])} s, {key[2]}: the reviewed bin says {reviewed[key]} and the accepted events say {seen[key]}; export the revision again")

    # The owner's choice (D38): the bins were checked above, not replayed. Each movement and class is one steady rate over the whole count,
    # in force from the start to beyond any run, so a run longer than the footage keeps receiving vehicles.
    span = last - first
    rate_note = f"steady hourly rates from a {_seconds(span)} s count; within-period variation not modelled"
    movements: Counter = Counter()
    for (_, origin, destination, engine_class), count in counts.items():
        movements[(origin, destination, engine_class)] += count
    windows = []
    for (origin, destination, engine_class), count in sorted(movements.items()):
        windows.append({"start": 0.0, "end": RUN_END_SECONDS, "vehicles_per_hour": count*3600.0/span, "vehicle_type": engine_class,
                        "label": f"{origin} to {destination} {engine_class}", "od": [{"source": approaches[origin][0], "destination": approaches[destination][1], "weight": 1}]})
    take, revision = manifest.get("take_id"), manifest.get("revision")
    manifest_sha = hashlib.sha256(files["manifest.json"].encode("utf-8")).hexdigest()
    description = (f"Field Observer counts (take {take}, revision {revision}): {rate_note}, "
                   f"per class, approach and turn. Scenario demand from field counts; not calibrated or validated.")
    candidate = {**engine_config, "traffic_density": "none", "trips": [], "demand_windows": windows,
                 "demand_source": {"kind": "field_counts", "description": description,
                                   "datasets": [{"kind": "field_counts", "description": description, "schema": "field_observer_counts", "sha256": manifest_sha}]}}
    total = sum(counts.values())
    summary = {
        "vehicles": total, "bins": len(grid), "bin_seconds": grid[0][1]-grid[0][0], "span_seconds": span,
        "vehicles_per_hour": round(total*3600.0/span, 1),
        "by_approach_class": {approach: {engine_class: sum(count for (_, origin, _, kind), count in counts.items() if origin == approach and kind == engine_class)
                                         for engine_class in sorted({kind for (_, origin, _, kind) in counts if origin == approach})}
                              for approach in sorted({origin for (_, origin, _, _) in counts})},
        "turns": {f"{origin} to {destination}": sum(count for (_, o, d, _), count in counts.items() if (o, d) == (origin, destination))
                  for origin, destination in sorted({(o, d) for (_, o, d, _) in counts})},
        "class_mapping": [{"field_class": key, "engine_class": CLASS_MAP[key], "vehicles": by_class[key], "pending_team_decision": key in PENDING,
                           "note": PENDING.get(key, "")} for key in sorted(by_class) if key in CLASS_MAP],
        "not_simulated": dict(not_simulated), "not_counted_at_the_end": not_counted_at_the_end, "limits": LIMITS, "rate_note": rate_note,
        "source": {"take_id": take, "revision": revision, "manifest_sha256": manifest_sha},
    }
    return {"engine_config": validate_config(DEFAULTS, candidate, network), "summary": summary}
