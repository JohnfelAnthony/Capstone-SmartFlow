"""One versioned definition catalog for Python reports and the browser.

Interpret stored engine values without rewriting artifacts or changing traffic math.
"""
from __future__ import annotations

import json
import math
from pathlib import Path

METRIC_CATALOG = json.loads((Path(__file__).resolve().parents[1] /
                            "simulation/metric_definitions.json").read_text(encoding="utf-8"))
METRIC_VERSION = METRIC_CATALOG["version"]
METRIC_DEFINITIONS = {item["key"]: item for item in METRIC_CATALOG["metrics"]}
ALIASES = {alias: item["key"] for item in METRIC_CATALOG["metrics"] for alias in item["aliases"]}


def finite_number(value) -> float | None:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    return float(value) if math.isfinite(value) else None


def metric_sources(metrics: dict | None) -> tuple[dict, dict]:
    saved = metrics if isinstance(metrics, dict) else {}
    raw = saved.get("raw_metrics")
    return (raw, saved) if isinstance(raw, dict) else (saved, {})


def metric_reading(metrics: dict | None, key: str) -> dict:
    key = ALIASES.get(key, key)
    definition = METRIC_DEFINITIONS.get(key)
    sources = metric_sources(metrics)
    experiment = sources[0].get("experiment")
    engine_version = experiment.get("engine_version") if isinstance(experiment, dict) else None
    if engine_version is not None and engine_version != METRIC_CATALOG["engine_version"]:
        return {"value": None, "available": False,
                "reason": "Historical engine differs; current native metric definitions do not establish this stored metric's meaning."}
    keys = [key, *(definition["aliases"] if definition else [])]

    def lookup(names):
        for source in sources:
            for name in names:
                if name in source:
                    return finite_number(source[name])
        return None

    value = lookup(keys)
    reason = None
    if value is None:
        reason = "Metric not recorded as a finite number."
    elif definition:
        counts = [lookup([name]) for name in definition["population_keys"]]
        if counts and any(count is None for count in counts):
            reason = "Population counts not recorded; this average cannot be verified."
        elif counts and sum(counts) <= 0:
            reason = "This average has no measured population; the engine's numeric zero is not an observed average."
        elif definition["requires_ticks"]:
            ticks = lookup(["step_count"])
            if ticks is None or ticks <= 0:
                reason = "No recorded metric ticks; queue sampling is unavailable."
        if reason is None and definition.get("requires_elapsed") and (lookup(["measurement_seconds"]) or 0) <= 0:
            reason = "No positive measured duration; a completed-trip rate is unavailable."
    return {"value": value if reason is None else None, "available": reason is None, "reason": reason}


def metric_value(metrics: dict | None, key: str) -> float | None:
    return metric_reading(metrics, key)["value"]


def interpreted_metrics(metrics: dict | None) -> dict:
    return {key: metric_reading(metrics, key) for key in METRIC_DEFINITIONS if key != "local_reference"}


def metric_report_metadata(metrics: dict | None) -> dict:
    return {"version": METRIC_VERSION, "definitions": METRIC_CATALOG,
            "values": interpreted_metrics(metrics),
            "historical_note": "Stored values/artifacts are unchanged. Unavailable averages are not zero. "
                               f"Definitions describe {METRIC_CATALOG['engine_version']}; historical artifacts need their engine provenance checked."}
