"""Permission-aware search and durable baseline-fit records."""
from __future__ import annotations

import csv
import io
import json
import math
from datetime import datetime
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import Response
from pydantic import BaseModel, ConfigDict, Field

import database
from backend.security import require_current_user, require_permission
from simulation.traffic_engine import ENGINE_VERSION

router = APIRouter()

METRICS = [
    {"key": "throughput", "label": "Completed network trips", "unit": "vehicles", "definition": "Trips completed at network boundaries during the measurement window; not local stop-line discharge."},
    {"key": "avg_wait", "label": "Mean stopped vehicle wait", "unit": "seconds", "definition": "Stopped wait of completed and active admitted vehicles divided by their count; pending arrivals are excluded."},
    {"key": "avg_queue", "label": "Mean incoming-lane queue", "unit": "vehicles", "definition": "Time average per incoming signal lane, speed ≤0.1 m/s; excludes connectors. Not a local snapshot or total network queue."},
    {"key": "avg_travel_time", "label": "Completed-trip travel time", "unit": "seconds", "definition": "Mean full travel time of trips completing in the measurement window; unfinished trips are excluded."},
    {"key": "avg_ped_delay", "label": "Mean pedestrian wait", "unit": "seconds", "definition": "Wait of completed and active pedestrians divided by their count; not crossing duration."},
    {"key": "local_reference", "label": "Local observation / custom measure", "unit": "researcher-defined", "definition": "Enter a simulated measurement extracted at the same location, times and definition as the field reference. Cite the extraction method; no automatic local metric is inferred."},
]


def may(user: dict, page: str, action: str = "view") -> bool:
    try:
        require_permission(user, page, action)
        return True
    except HTTPException:
        return False


def research_access(user: dict, write: bool = False, export: bool = False):
    require_permission(user, "scenarios", "view")
    require_permission(user, "runs-reports", "view")
    if write:
        require_permission(user, "scenarios", "edit")
    if export:
        require_permission(user, "runs-reports", "export")


@router.get("/api/search")
def search(q: str = Query(min_length=1, max_length=160), user: dict = Depends(require_current_user)):
    query = q.strip().lower()
    if not query:
        return {"results": [], "has_more": False}
    results = []
    pages = [("Dashboard", "dashboard"), ("Scenarios", "scenarios"), ("RL Training", "rl-training"),
             ("Runs & Reports", "runs-reports"), ("Compare Runs", "compare"), ("Settings", "profile"), ("Help", "help")]
    if may(user, "scenarios") and may(user, "runs-reports"):
        pages.append(("Calibration & Validation", "scenarios"))
    for title, permission in pages:
        if query in title.lower() and may(user, permission):
            results.append({"kind": "Page", "id": None, "title": title, "description": "Open workspace", "page": title})
    # Literal substring search: '%' and '_' are text, not SQL wildcard operators.
    pattern = "%" + query.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_") + "%"
    sources = [
        ("scenarios", "scenarios", "Scenario", "Scenarios", "name", "COALESCE(description,'')"),
        ("simulation_runs", "runs-reports", "Run", "Runs & Reports", "CAST(id AS TEXT)", "COALESCE(notes,'') || ' ' || control_mode || ' ' || status"),
        ("rl_models", "rl-training", "Model", "RL Training", "COALESCE(name, algorithm)", "algorithm"),
    ]
    if may(user, "scenarios") and may(user, "runs-reports"):
        sources.append(("calibration_records", "scenarios", "Fit record", "Calibration & Validation", "name", "site_id || ' ' || purpose"))
    has_more = False
    with database.get_db() as conn:
        for table, permission, kind, page, title, description in sources:
            if not may(user, permission):
                continue
            rows = conn.execute(f"SELECT id, {title} AS title, {description} AS description FROM {table} WHERE lower({title} || ' ' || {description}) LIKE ? ESCAPE '\\' ORDER BY id DESC LIMIT 26", (pattern,)).fetchall()
            has_more = has_more or len(rows) > 25
            results.extend({"kind": kind, "id": row["id"], "title": f"Run #{row['id']}" if kind == "Run" else row["title"],
                            "description": row["description"] or "", "page": page} for row in rows[:25])
    return {"results": results, "has_more": has_more}


class Measurement(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)
    metric: str
    location: str = Field(min_length=1, max_length=180)
    definition: str = Field(min_length=1, max_length=1200)
    unit: str = Field(min_length=1, max_length=60)
    observed: float = Field(ge=0)
    tolerance: float = Field(ge=0)
    tolerance_mode: Literal["absolute", "percent"] = "absolute"
    simulated: float | None = Field(default=None, ge=0)
    simulation_method: str = Field(default="", max_length=1200)


class FitRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)
    name: str = Field(min_length=1, max_length=160)
    site_id: str = Field(min_length=1, max_length=160)
    purpose: Literal["calibration", "validation"]
    source_kind: Literal["observed", "synthetic"]
    source_reference: str = Field(min_length=1, max_length=1200)
    source_sha256: str = Field(default="", pattern=r"^([a-fA-F0-9]{64})?$")
    collection_start: str
    collection_end: str
    run_id: int = Field(ge=1)
    calibration_id: int | None = Field(default=None, ge=1)
    measurement_start: float = Field(ge=0)
    measurement_seconds: float = Field(gt=0)
    definitions_confirmed: bool
    measurements: list[Measurement] = Field(min_length=1, max_length=50)
    parameter_changes: str = Field(default="", max_length=6000)
    notes: str = Field(default="", max_length=6000)


def period(start: str, end: str):
    try:
        first, last = datetime.fromisoformat(start), datetime.fromisoformat(end)
    except ValueError as exc:
        raise ValueError("Collection times must be ISO 8601 timestamps with UTC offsets.") from exc
    if first.utcoffset() is None or last.utcoffset() is None or last <= first:
        raise ValueError("Collection end must follow start; both need UTC offsets.")
    return first, last


def unpack(row):
    return {"id": row["id"], "created_at": row["created_at"], "created_by": row["created_by"], **json.loads(row["payload_json"])}


def get_record(record_id: int):
    with database.get_db() as conn:
        row = conn.execute("SELECT * FROM calibration_records WHERE id = ?", (record_id,)).fetchone()
    if not row:
        raise HTTPException(404, "Fit record not found.")
    return unpack(row)


@router.get("/api/calibration")
def list_records(user: dict = Depends(require_current_user)):
    research_access(user)
    with database.get_db() as conn:
        rows = conn.execute("SELECT * FROM calibration_records ORDER BY id DESC LIMIT 200").fetchall()
    return {"records": [unpack(row) for row in rows], "metrics": METRICS}


@router.get("/api/calibration/{record_id}")
def read_record(record_id: int, user: dict = Depends(require_current_user)):
    research_access(user)
    return get_record(record_id)


def baseline_snapshot(run_id: int):
    run = database.get_run_by_id(run_id)
    if not run:
        raise ValueError("Selected run does not exist.")
    if run["status"] != "completed" or run["control_mode"] != "fixed-time":
        raise ValueError("Choose a completed fixed-time baseline run.")
    saved = database.get_run_metrics(run_id)
    try:
        metrics = json.loads((saved or {}).get("raw_metrics_json") or "{}")
    except ValueError as exc:
        raise ValueError("Run metrics are unreadable.") from exc
    experiment = metrics.get("experiment", {})
    if experiment.get("engine_version") != ENGINE_VERSION or not experiment.get("network_sha256") or not experiment.get("config"):
        raise ValueError("Run lacks current native engine/network provenance; record a new baseline.")
    if not all(math.isfinite(float(metrics.get(key, -1))) and float(metrics.get(key, -1)) >= 0 for key in ("measurement_start", "measurement_seconds")):
        raise ValueError("Run lacks a valid measurement window.")
    if metrics.get("vehicle_conservation_error", 0) or metrics.get("pedestrian_conservation_error", 0):
        raise ValueError("Conservation errors prevent using this run as a baseline.")
    return {"run_id": run_id, "scenario_id": run["scenario_id"], "scenario_name": run.get("scenario_name"),
            "seed": run["seed"], "controller": run["control_mode"], "experiment": experiment, "metrics": metrics}


@router.post("/api/calibration", status_code=201)
def save_record(body: FitRequest, user: dict = Depends(require_current_user)):
    research_access(user, write=True)
    try:
        if body.purpose == "calibration" and body.calibration_id is not None:
            raise ValueError("Calibration records do not reference a validation parent.")
        for name in ("name", "site_id", "source_reference"):
            if not getattr(body, name).strip():
                raise ValueError(f"{name.replace('_', ' ').title()} is required.")
        if not body.definitions_confirmed:
            raise ValueError("Confirm matching measurement locations, population, definitions and windows.")
        first, last = period(body.collection_start, body.collection_end)
        if (last-first).total_seconds() + .001 < body.measurement_start + body.measurement_seconds:
            raise ValueError("The recording period must cover warmup and the full measurement window.")
        snapshot = baseline_snapshot(body.run_id)
        metrics = snapshot["metrics"]
        if any(abs(float(metrics[key])-getattr(body, key)) > .001 for key in ("measurement_start", "measurement_seconds")):
            raise ValueError("Measurement start/duration must match the selected baseline's saved metrics.")
        comparisons = []
        catalog = {item["key"]: item for item in METRICS}
        for measurement in body.measurements:
            if measurement.metric not in catalog:
                raise ValueError("Unknown comparison metric.")
            if not all(getattr(measurement, field).strip() for field in ("location", "definition", "unit")):
                raise ValueError("Each measurement needs a location, unit and definition.")
            is_local = measurement.metric == "local_reference"
            if is_local:
                if measurement.simulated is None or not measurement.simulation_method.strip():
                    raise ValueError("Local comparisons need the simulated value and its extraction method/source.")
                simulated = measurement.simulated
            else:
                if measurement.unit != catalog[measurement.metric]["unit"]:
                    raise ValueError("Metric units must match the saved native metric.")
                if measurement.simulated is not None:
                    raise ValueError("Whole-network simulated values come from saved metrics; manual overrides are not allowed.")
                simulated = metrics.get(measurement.metric)
                if simulated is None or not isinstance(simulated, (float, int)) or not math.isfinite(simulated):
                    raise ValueError("The selected run is missing this metric.")
                populations = {
                    "avg_travel_time": metrics.get("total_vehicles_completed", 0),
                    "avg_wait": metrics.get("total_vehicles_completed", 0) + metrics.get("active_vehicle_count", 0),
                    "avg_ped_delay": metrics.get("total_pedestrians_completed", 0) + metrics.get("active_pedestrian_count", 0),
                }
                if measurement.metric in populations and populations[measurement.metric] <= 0:
                    raise ValueError("This average has no measured population. Choose a run with measured trips/pedestrians or a matched local measure.")
            difference = simulated - measurement.observed
            percent_error = abs(difference) / measurement.observed * 100 if measurement.observed else None
            allowed = measurement.tolerance if measurement.tolerance_mode == "absolute" else measurement.observed * measurement.tolerance / 100
            comparisons.append({**measurement.model_dump(), "simulated": simulated, "difference": difference,
                                "absolute_error": abs(difference), "percent_error": percent_error,
                                "within_tolerance": abs(difference) <= allowed + 1e-9})
        payload = {**body.model_dump(), "schema_version": 1, "reviewer": user["username"], "name": body.name.strip(), "site_id": body.site_id.strip(), "snapshot": snapshot,
                   "comparisons": comparisons, "within_tolerance": all(item["within_tolerance"] for item in comparisons),
                   "assessment": "Numerical fit check only; field truth, reference quality and study validity require independent review."}
        # A single transaction also prevents a concurrent calibration from bypassing the held-out check.
        with database.get_db() as conn:
            conn.execute("BEGIN IMMEDIATE")
            if body.purpose == "validation":
                parent_row = conn.execute("SELECT * FROM calibration_records WHERE id = ?", (body.calibration_id,)).fetchone()
                if not parent_row:
                    raise ValueError("Choose a saved calibration record before independent validation.")
                parent = unpack(parent_row)
                if parent["purpose"] != "calibration" or parent["site_id"] != payload["site_id"] or parent["source_kind"] != body.source_kind:
                    raise ValueError("Validation must reference calibration for the same site and source kind.")
                def structure(record):
                    experiment = record["snapshot"]["experiment"]
                    demand_keys = {"traffic_density", "pedestrian_density", "trips", "pedestrian_trips", "demand_windows", "demand_source", "vehicle_mix", "emergency_mode"}
                    return {"engine": experiment["engine_version"], "network": experiment["network_sha256"],
                            "config": {key: value for key, value in experiment.get("config", {}).items() if key not in demand_keys}}
                if structure(parent) != structure(payload):
                    raise ValueError("Validation must use the frozen calibrated network/control/behavior settings. Recalibrate changed settings first.")
                definitions = lambda record: [(row["metric"], row["location"], row["definition"], row["unit"], row["tolerance_mode"], row["tolerance"]) for row in record["measurements"]]
                if definitions(parent) != definitions(payload):
                    raise ValueError("Keep the calibrated measurement definitions and tolerances unchanged for validation.")
                if any(abs(parent[key] - payload[key]) > .001 for key in ("measurement_start", "measurement_seconds")):
                    raise ValueError("Keep the calibrated warmup and measurement duration unchanged for validation.")
                for row in conn.execute("SELECT * FROM calibration_records WHERE purpose = 'calibration' AND site_id = ?", (payload["site_id"],)):
                    previous = unpack(row)
                    if previous["source_kind"] != body.source_kind or previous["snapshot"]["experiment"]["network_sha256"] != snapshot["experiment"]["network_sha256"]:
                        continue
                    earlier_start, earlier_end = period(previous["collection_start"], previous["collection_end"])
                    same_hash = bool(body.source_sha256 and previous["source_sha256"].lower() == body.source_sha256.lower())
                    periods_overlap = first < earlier_end and earlier_start < last
                    same_reference = previous["source_reference"].strip().casefold() == body.source_reference.strip().casefold()
                    if periods_overlap or same_hash or same_reference:
                        raise ValueError("Validation needs an independent source and nonoverlapping collection period, separate from calibration.")
            encoded = json.dumps(payload, allow_nan=False)
            if len(encoded.encode("utf-8")) > 2_097_152:
                raise ValueError("Fit record exceeds the 2 MiB storage limit.")
            cursor = conn.execute("INSERT INTO calibration_records (name, site_id, purpose, created_by, payload_json) VALUES (?, ?, ?, ?, ?)",
                                  (payload["name"], payload["site_id"], body.purpose, user["id"], encoded))
            record_id = cursor.lastrowid
        database.log_audit_event(user_id=user["id"], action="save_fit_record", target=f"calibration:{record_id}", details=payload["name"])
        return get_record(record_id)
    except (ValueError, TypeError, KeyError) as exc:
        raise HTTPException(422, str(exc)) from exc


@router.get("/api/calibration/{record_id}/export")
def export_record(record_id: int, format: Literal["json", "csv"] = "json", user: dict = Depends(require_current_user)):
    research_access(user, export=True)
    record = get_record(record_id)
    if format == "json":
        content, media = json.dumps(record, indent=2, allow_nan=False), "application/json"
    else:
        output = io.StringIO(newline="")
        columns = ["metric", "location", "definition", "unit", "observed", "simulated", "difference", "absolute_error", "percent_error", "tolerance_mode", "tolerance", "within_tolerance", "simulation_method"]
        writer = csv.writer(output)
        writer.writerow(["Record ID", "Name", "Purpose", "Source Kind", "Source Reference", "Collection Start", "Collection End", "Measurement Start", "Measurement Seconds", "Run ID", "Seed", "Network SHA256", *columns, "Assessment", "Frozen Record JSON"])
        for comparison in record["comparisons"]:
            values = [record["id"], record["name"], record["purpose"], record["source_kind"], record["source_reference"], record["collection_start"], record["collection_end"], record["measurement_start"], record["measurement_seconds"], record["run_id"], record["snapshot"]["seed"], record["snapshot"]["experiment"]["network_sha256"], *[comparison.get(key) for key in columns], record["assessment"], json.dumps(record)]
            writer.writerow(["'" + value if isinstance(value, str) and value.startswith(("=", "+", "-", "@")) else value for value in values])
        content, media = output.getvalue(), "text/csv"
    return Response(content, media_type=media, headers={"Content-Disposition": f'attachment; filename="smartflow-fit-{record_id}.{format}"'})
