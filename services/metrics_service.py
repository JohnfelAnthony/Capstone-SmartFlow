"""Metrics service — saves engine run data to SQLite at stop/reset."""

import json
from typing import Optional
import database

try:
    from flask import session
except ImportError:  # pragma: no cover - exercised in dependency-light unit environments
    session = {}


def save_run(scenario_id: int, control_mode: str, engine) -> int:
    """Persist a completed simulation run and its metrics to the DB.
    Returns the run_id."""
    user_id = session.get("user_id") or None
    run_notes = None if user_id else "system-run"

    run_id = database.create_run(
        scenario_id=scenario_id,
        user_id=user_id,
        control_mode=control_mode,
        status=engine.status,
        duration_seconds=int(engine.simulation_time),
        notes=run_notes,
    )

    m = engine.metrics
    database.save_run_metrics(
        run_id=run_id,
        avg_waiting_time=m.avg_wait,
        avg_queue_length=m.avg_queue,
        max_queue_length=m.max_queue,
        throughput=m.throughput,
        avg_pedestrian_delay=m.avg_ped_delay,
        raw_metrics_json=json.dumps(m.to_dict()),
    )
    return run_id


def get_recent(limit: int = 5) -> list:
    return database.get_runs(limit=limit)


def metrics_payload(engine) -> dict:
    """Return a KPI-friendly dict for dashboard callbacks."""
    m = engine.metrics
    state = engine.to_dict()
    return {
        "avg_wait": m.avg_wait,
        "avg_queue": m.avg_queue,
        "max_queue": m.max_queue,
        "throughput": m.throughput,
        "avg_ped_delay": m.avg_ped_delay,
        "total_vehicles": state.get("vehicle_count", 0),
        "total_pedestrians": state.get("pedestrian_count", 0),
        "status": state.get("status", "stopped"),
        "time": state.get("time", 0.0),
        "phase": state.get("phase", "NS_GREEN"),
        "phase_remaining": state.get("phase_remaining", 0),
        "events": state.get("events", []),
    }
