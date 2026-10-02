"""Observed input identity and conservative held-out collection separation."""
import csv
import hashlib
import io
import json
from datetime import UTC, date, datetime, timedelta
from pathlib import Path

import config


def normalized_observation_identity(kind: str, csv_text: str) -> dict:
    numeric_columns = {"time_s", "start_s", "end_s", "count"}
    records = []
    for row in csv.DictReader(io.StringIO(csv_text.lstrip("\ufeff"), newline="")):
        normalized = {key: float(value.strip()) if key in numeric_columns else
                      value.strip().lower() if key == "vehicle_type" else value.strip()
                      for key, value in row.items()}
        records.append(hashlib.sha256(json.dumps(normalized, sort_keys=True).encode()).hexdigest())
    ordered = sorted(records)
    digest = hashlib.sha256(json.dumps([kind, ordered]).encode()).hexdigest()
    return {"normalized_sha256": digest, "observation_rows_sha256": ordered}


def collection_period(start, end, collected_on: str) -> dict:
    if not start and not end:
        return {}
    try:
        first, last = datetime.fromisoformat(start), datetime.fromisoformat(end)
        if first.tzinfo is None or last.tzinfo is None or last <= first or first.date().isoformat() != collected_on:
            raise ValueError()
    except (TypeError, ValueError) as exc:
        raise ValueError("Collection start/end must be ordered ISO 8601 timestamps with UTC offsets; start must match the collection date.") from exc
    return {"collection_start": first.isoformat(), "collection_end": last.isoformat()}


def _configuration(snapshot):
    if not isinstance(snapshot, dict):
        raise ValueError("Held-out evaluation needs a recorded training scenario snapshot.")
    value = snapshot.get("engine_config", {})
    value = json.loads(value) if isinstance(value, str) else value
    if not isinstance(value, dict):
        raise ValueError("Observed input configuration must be an object.")
    return value


def _observed_datasets(settings):
    source = settings.get("demand_source", {})
    if not isinstance(source, dict) or not isinstance(source.get("datasets", []), list):
        raise ValueError("Observed dataset provenance must be an object with a dataset list.")
    observed = [item for item in source.get("datasets", []) if isinstance(item, dict) and item.get("kind") == "observed"]
    if source.get("kind") == "observed" and not observed:
        observed = [source]
    return observed


def _identity(dataset):
    if dataset.get("normalized_sha256") and dataset.get("observation_rows_sha256"):
        return dataset
    source_path = dataset.get("source_path")
    if not source_path or not dataset.get("schema"):
        raise ValueError("Held-out observed inputs need retained CSV content and collection provenance; re-import this legacy dataset.")
    path = Path(source_path)
    if not path.is_absolute():
        path = Path(config.BASE_DIR) / path
    if not path.exists() and dataset.get("sha256"):
        # Frozen older model snapshots retain pre-restore locations. Their raw
        # content hash, realized arrivals and dates still identify the inputs.
        return dataset
    try:
        return {**dataset, **normalized_observation_identity(dataset["schema"], path.read_text(encoding="utf-8"))}
    except (OSError, ValueError, AttributeError, TypeError) as exc:
        raise ValueError("Held-out observed source is missing or unreadable; restore or re-import it before evaluation.") from exc


def _period(dataset):
    try:
        if bool(dataset.get("collection_start")) != bool(dataset.get("collection_end")):
            raise ValueError()
        if dataset.get("collection_start") and dataset.get("collection_end"):
            start = datetime.fromisoformat(dataset["collection_start"])
            end = datetime.fromisoformat(dataset["collection_end"])
            if start.tzinfo is None or end.tzinfo is None or end <= start:
                raise ValueError()
            return start.astimezone(UTC), end.astimezone(UTC)
        date.fromisoformat(dataset["collected_on"])
        return None
    except (KeyError, TypeError, ValueError) as exc:
        raise ValueError("Held-out observed inputs need a collection date or an explicit collection period.") from exc


def _collection_dates(dataset):
    if dataset.get("collection_start") and dataset.get("collection_end"):
        first = datetime.fromisoformat(dataset["collection_start"])
        last = datetime.fromisoformat(dataset["collection_end"]).astimezone(first.tzinfo) - timedelta(microseconds=1)
        return first.date(), last.date()
    day = date.fromisoformat(dataset["collected_on"])
    return day, day


def has_observed_inputs(snapshot):
    return bool(_observed_datasets(_configuration(snapshot)))


def _arrivals(settings, pedestrians=False):
    if pedestrians:
        return sorted((float(item["time"]), item["junction"]) for item in settings.get("pedestrian_trips", []))
    return sorted((float(item["time"]), item["source"], item["destination"], item.get("vehicle_type", "car"))
                  for item in settings.get("trips", []))


def validate_observed_holdout(trained: dict, evaluation: dict) -> None:
    train_settings, eval_settings = _configuration(trained), _configuration(evaluation)
    train_sources, eval_sources = _observed_datasets(train_settings), _observed_datasets(eval_settings)
    if not train_sources or not eval_sources:
        return
    for original in train_sources:
        left = _identity(original)
        for candidate in eval_sources:
            right = _identity(candidate)
            same_raw = bool(left.get("sha256")) and left.get("sha256") == right.get("sha256")
            same_normalized = bool(left.get("normalized_sha256")) and left.get("normalized_sha256") == right.get("normalized_sha256")
            same_vehicle_arrivals = bool(train_settings.get("trips")) and _arrivals(train_settings) == _arrivals(eval_settings)
            same_pedestrian_arrivals = bool(train_settings.get("pedestrian_trips")) and _arrivals(train_settings, True) == _arrivals(eval_settings, True)
            same_stream_arrivals = (same_pedestrian_arrivals if left.get("schema") == right.get("schema") == "pedestrian_counts" else
                                    same_vehicle_arrivals if left.get("schema") != "pedestrian_counts" and right.get("schema") != "pedestrian_counts" else False)
            if same_raw or same_normalized or same_stream_arrivals:
                raise ValueError("Held-out observed data duplicates training observations, even under a different scenario name or CSV formatting.")
            left_period, right_period = _period(left), _period(right)
            if left_period and right_period:
                periods_overlap = left_period[0] < right_period[1] and right_period[0] < left_period[1]
            else:
                left_first, left_last = _collection_dates(left)
                right_first, right_last = _collection_dates(right)
                periods_overlap = left_first <= right_last and right_first <= left_last
            same_network = left.get("network_sha256") == right.get("network_sha256")
            left_mode = "pedestrians" if left.get("schema") == "pedestrian_counts" else "vehicles"
            right_mode = "pedestrians" if right.get("schema") == "pedestrian_counts" else "vehicles"
            if periods_overlap and same_network and left_mode == right_mode:
                raise ValueError("Held-out observed collection periods overlap training. Use disjoint dates or explicit non-overlapping collection start/end times.")
