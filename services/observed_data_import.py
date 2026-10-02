"""Validated CSV observations converted to explicit, reproducible native demand."""
from __future__ import annotations

import csv
import hashlib
import io
import json
import os
from datetime import date
from pathlib import Path

import config
from services.scenario_storage import validate_scenario_json_size
from services.observation_identity import collection_period, normalized_observation_identity
from simulation.road_network import load_network
from simulation.scenario_config import DEFAULTS, VEHICLE_TYPES, number, validate_config

IMPORT_DIRECTORY = Path(os.environ.get("SMARTFLOW_IMPORT_DIR", str(Path(config.BASE_DIR) / "data" / "imports")))
MAX_CSV_BYTES = 1_000_000
MAX_ROWS = 5000
MAX_ARRIVALS = 100000
SCHEMAS = {
    "trips": ("time_s", "source", "destination", "vehicle_type"),
    "od_counts": ("start_s", "end_s", "source", "destination", "count"),
    "turn_counts": ("start_s", "end_s", "source", "destination", "junction", "from_lane", "to_lane", "count"),
    "pedestrian_counts": ("start_s", "end_s", "junction", "count"),
}


def _rows(csv_text: str, kind: str) -> list[dict[str, str]]:
    if kind not in SCHEMAS:
        raise ValueError("Schema must be trips, od_counts, turn_counts, or pedestrian_counts")
    if not isinstance(csv_text, str) or not csv_text.strip() or len(csv_text.encode("utf-8")) > MAX_CSV_BYTES:
        raise ValueError("CSV must contain data and be at most 1 MB")
    reader = csv.DictReader(io.StringIO(csv_text.lstrip("\ufeff"), newline=""))
    headers = reader.fieldnames or []
    if set(headers) != set(SCHEMAS[kind]) or len(headers) != len(SCHEMAS[kind]):
        raise ValueError(f"CSV columns for {kind} must be: {', '.join(sorted(SCHEMAS[kind]))}")
    rows = list(reader)
    if not rows or len(rows) > MAX_ROWS:
        raise ValueError(f"CSV must contain 1–{MAX_ROWS} data rows")
    for index, row in enumerate(rows, start=2):
        if None in row or any(value is None or not value.strip() for value in row.values()):
            raise ValueError(f"Row {index}: every field is required; extra columns are not supported")
    return rows


def _count(value: str, row_number: int) -> int:
    parsed = number(value, f"row {row_number} count", 0, MAX_ARRIVALS)
    if parsed != int(parsed):
        raise ValueError(f"Row {row_number}: count must be a whole number")
    return int(parsed)


def _bin(row: dict, row_number: int) -> tuple[float, float]:
    start = number(row["start_s"], f"row {row_number} start_s")
    end = number(row["end_s"], f"row {row_number} end_s")
    if end <= start:
        raise ValueError(f"Row {row_number}: end_s must follow start_s")
    return start, end


def import_observations(*, kind: str, csv_text: str, source_description: str, source_kind: str = "synthetic",
                        collected_on: str, engine_config: dict | None = None,
                        collection_start: str | None = None, collection_end: str | None = None) -> dict:
    """Validate every row and the complete scenario before retaining source bytes."""
    description = source_description.strip() if isinstance(source_description, str) else ""
    if not description or len(description) > 500:
        raise ValueError("Source description is required (1–500 characters)")
    if source_kind not in {"synthetic", "observed"}:
        raise ValueError("Source kind must be synthetic or observed")
    try:
        observed_date = date.fromisoformat(collected_on)
    except (TypeError, ValueError) as exc:
        raise ValueError("Collection date must be YYYY-MM-DD") from exc
    if observed_date > date.today():
        raise ValueError("Collection date cannot be in the future")
    period = collection_period(collection_start, collection_end, collected_on)
    network = load_network()
    rows = _rows(csv_text, kind)
    if period:
        from datetime import datetime
        period_seconds = (datetime.fromisoformat(period["collection_end"]) - datetime.fromisoformat(period["collection_start"])).total_seconds()
        last_column = "time_s" if kind == "trips" else "end_s"
        if any(number(row[last_column], last_column) > period_seconds for row in rows):
            raise ValueError("CSV times exceed the declared collection period; times must start at the collection start.")
    trips: list[dict] = []
    pedestrian_trips: list[dict] = []
    for row_number, row in enumerate(rows, start=2):
        try:
            if kind == "trips":
                vehicle_type = row["vehicle_type"].strip().lower()
                if vehicle_type not in VEHICLE_TYPES:
                    raise ValueError("vehicle_type is not supported")
                trips.append({"time": number(row["time_s"], "time_s"), "source": row["source"].strip(),
                              "destination": row["destination"].strip(), "vehicle_type": vehicle_type})
            else:
                start, end = _bin(row, row_number)
                count = _count(row["count"], row_number)
                if kind == "turn_counts":
                    source, destination = row["source"].strip(), row["destination"].strip()
                    junction = row["junction"].strip()
                    from_lane, to_lane = row["from_lane"].strip(), row["to_lane"].strip()
                    if junction not in network.intersections:
                        raise ValueError("junction is not a network intersection ID")
                    if from_lane not in network.lanes or to_lane not in network.lanes:
                        raise ValueError("from_lane and to_lane must be network lane IDs")
                    if network.lanes[from_lane].target != junction or network.lanes[to_lane].source != junction:
                        raise ValueError("from_lane and to_lane must meet at junction")
                    if not network.turn_allowed(from_lane, to_lane):
                        raise ValueError("from_lane to to_lane is prohibited or disconnected")
                    route = network.route(source, destination)
                    if (from_lane, to_lane) not in zip(route, route[1:]):
                        raise ValueError("source/destination route does not use the recorded turn")
                for index in range(count):
                    arrival_time = round(start + (index + 0.5) * (end - start) / count, 6)
                    if kind == "pedestrian_counts":
                        pedestrian_trips.append({"time": arrival_time, "junction": row["junction"].strip()})
                    else:
                        trips.append({"time": arrival_time, "source": row["source"].strip(),
                                      "destination": row["destination"].strip(), "vehicle_type": "car"})
            if len(trips) + len(pedestrian_trips) > MAX_ARRIVALS:
                raise ValueError(f"import exceeds {MAX_ARRIVALS} arrivals")
            # Include the CSV row in connectivity and ID errors.
            if kind == "trips":
                probe_trips = trips[-1:]
                probe_pedestrians = []
            elif kind == "pedestrian_counts":
                probe_trips = []
                probe_pedestrians = [{"time": start, "junction": row["junction"].strip()}]
            else:
                probe_trips = [{"time": start, "source": row["source"].strip(),
                                "destination": row["destination"].strip(), "vehicle_type": "car"}]
                probe_pedestrians = []
            candidate_row = {"traffic_density": "none", "pedestrian_density": "none",
                             "trips": probe_trips, "pedestrian_trips": probe_pedestrians}
            validate_config(DEFAULTS, candidate_row, network)
        except ValueError as exc:
            raise ValueError(f"Row {row_number}: {exc}") from exc

    digest = hashlib.sha256(csv_text.encode("utf-8")).hexdigest()
    source = {
        "kind": source_kind, "description": description, "collected_on": collected_on,
        "schema": kind, "sha256": digest, "network_sha256": network.fingerprint,
        "conversion": "Explicit trip times" if kind == "trips" else
        ("Turn counts assigned to the supplied boundary OD route and distributed evenly within each time bin; "
         "routing may later change under congestion or closures" if kind == "turn_counts" else
         "Count bins distributed evenly within each time bin; actual arrival times are unknown"),
        "row_count": len(rows), "arrival_count": len(trips) + len(pedestrian_trips),
        "source_path": str(IMPORT_DIRECTORY / f"{digest}.csv"),
        **normalized_observation_identity(kind, csv_text), **period,
    }
    candidate = dict(engine_config or {})
    if kind == "pedestrian_counts":
        candidate.update(pedestrian_density="none", pedestrian_trips=pedestrian_trips)
    else:
        candidate.update(traffic_density="none", trips=trips, demand_windows=[])
    previous = candidate.get("demand_source", {})
    replaced_schemas = {"pedestrian_counts"} if kind == "pedestrian_counts" else {"trips", "od_counts", "turn_counts"}
    datasets = [item for item in previous.get("datasets", []) if item.get("schema") not in replaced_schemas] if isinstance(previous, dict) else []
    all_datasets = [*datasets, source]
    has_synthetic_demand = (candidate.get("traffic_density", DEFAULTS["traffic_density"]) != "none" or
                            candidate.get("pedestrian_density", DEFAULTS["pedestrian_density"]) != "none")
    overall_kind = "observed" if not has_synthetic_demand and all(item["kind"] == "observed" for item in all_datasets) else "synthetic"
    candidate["demand_source"] = {"kind": overall_kind, "description": description,
                                   "datasets": all_datasets}
    validated = validate_config(DEFAULTS, candidate, network)
    # Match scenario_write_values serialization before retaining the source CSV.
    validate_scenario_json_size("engine_config", json.dumps(validated))
    IMPORT_DIRECTORY.mkdir(parents=True, exist_ok=True)
    source_path = IMPORT_DIRECTORY / f"{digest}.csv"
    if not source_path.exists():
        temporary = IMPORT_DIRECTORY / f"{digest}.{os.getpid()}.tmp"
        temporary.write_bytes(csv_text.encode("utf-8"))
        os.replace(temporary, source_path)
    return {"engine_config": validated, "summary": source}
