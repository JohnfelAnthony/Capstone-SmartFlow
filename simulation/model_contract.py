"""Prevent legacy or differently shaped network models from running silently."""
import hashlib
import json
from pathlib import Path

from .road_network import load_network
from functools import lru_cache


def native_contract(network=None) -> dict:
    from .traffic_engine import ENGINE_VERSION
    return {"engine": ENGINE_VERSION, "observation": "native-local-20-v4", "actions": "phase-service-5-v2", "network_sha256": (network or load_network()).fingerprint}


def phase_plan(engine) -> dict:
    """What an action means: the controlled junction and its phases in slot order. Green times may differ between scenarios."""
    from .traffic_engine import phase_slots
    signal = engine.signals[engine.controlled_junction]
    keys = [key for key in phase_slots(signal)[:4] if key is not None]
    return {"junction": engine.controlled_junction, "phase_keys": [*keys, "pedestrian"] if "pedestrian" in signal.approaches else keys}


def phase_plan_for_scenario(scenario: dict) -> dict:
    """The phase plan of a training scenario snapshot, for the model metadata (a snapshot with no network id uses the default network)."""
    from .network_registry import engine_for_scenario
    from .traffic_engine import TrafficEngine
    settings = scenario.get("engine_config", {})
    settings = json.loads(settings) if isinstance(settings, str) else dict(settings or {})
    if scenario.get("network_id"):
        return phase_plan(engine_for_scenario({"network_id": scenario["network_id"], "engine_config": settings}, seed=0))
    engine = TrafficEngine(seed=0)
    engine.configure(**settings)
    return phase_plan(engine)


def scenario_phase_plan(scenario) -> dict:
    """The phase plan to store with a model; a training scenario that is not a snapshot object means the default network and plan."""
    return phase_plan_for_scenario(scenario if isinstance(scenario, dict) else {})


def validate_metadata(metadata: dict, network=None) -> None:
    if metadata.get("native_contract") != native_contract(network):
        raise ValueError("This model was not trained for the current Python engine and road network. Train a new model; artifacts from earlier engine or observation versions cannot be reused.")


def validate_neural_artifact(path: str | Path, network=None) -> None:
    metadata_path = Path(path).with_suffix(".metadata.json")
    if not metadata_path.exists():
        raise ValueError("Native model metadata is missing. Train a new model for this engine.")
    validate_metadata(json.loads(metadata_path.read_text(encoding="utf-8")), network)


@lru_cache(maxsize=128)
def _read_metadata(path: str, modified_ns: int, size: int, algorithm: str) -> dict:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    metadata = payload.get("metadata", {}) if algorithm == "ql" else payload
    return metadata


def artifact_metadata(algorithm: str, path: str | Path, network=None) -> dict:
    artifact = Path(path)
    if not artifact.is_file():
        raise ValueError("Model artifact is missing or has not been saved yet.")
    metadata_path = artifact if algorithm == "ql" else artifact.with_suffix(".metadata.json")
    try:
        stat = metadata_path.stat()
        metadata = _read_metadata(str(metadata_path.resolve()), stat.st_mtime_ns, stat.st_size, algorithm)
        validate_metadata(metadata, network)
        return metadata
    except (OSError, TypeError, json.JSONDecodeError) as exc:
        raise ValueError("Model metadata is missing or unreadable; train a new model.") from exc


def training_junction(metadata: dict, network=None) -> str:
    scenario = metadata.get("scenario", {})
    settings = scenario.get("engine_config", {})
    if isinstance(settings, str):
        settings = json.loads(settings)
    return settings.get("controlled_junction") or scenario.get("controlled_junction") or (network or load_network()).intersections[0]
