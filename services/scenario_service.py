"""Scenario service — loads DB scenario presets into the simulation engine."""

from typing import Optional
import database


def load_into_engine(scenario_id: int, engine) -> str:
    """Load a scenario from the DB and apply it to the engine.
    Returns the scenario name."""
    row = database.get_scenario_by_id(scenario_id)
    if not row:
        raise ValueError(f"Scenario {scenario_id} not found")
    engine.configure_from_scenario(row)
    return row.get("name", "Unknown")


def get_presets() -> list:
    """Return available official scenarios for dropdown."""
    return database.get_scenarios(official_only=True)


def get_available_scenarios() -> list:
    """Return active scenarios that can be selected in the dashboard."""
    return database.get_scenarios(include_archived=False)


def get_scenario(scenario_id: int) -> Optional[dict]:
    return database.get_scenario_by_id(scenario_id)


def summary(scenario_id: int) -> Optional[dict]:
    row = database.get_scenario_by_id(scenario_id)
    if not row:
        return None
    return {
        "name": row.get("name"),
        "traffic_density": row.get("traffic_density"),
        "pedestrian_density": row.get("pedestrian_density"),
        "emergency_mode": row.get("emergency_mode"),
        "road_constraint": row.get("road_constraint"),
        "control_mode": row.get("control_mode", "fixed-time"),
    }
