"""Prevent legacy or differently shaped network models from running silently."""
import hashlib
import json
from pathlib import Path

from .road_network import load_network
from functools import lru_cache


def native_contract() -> dict:
    from .traffic_engine import ENGINE_VERSION
    return {"engine": ENGINE_VERSION, "observation": "native-local-30-v1", "actions": "protected-service-5-v1", "network_sha256": load_network().fingerprint}


def validate_metadata(metadata: dict) -> None:
    if metadata.get("native_contract") != native_contract():
        raise ValueError("This model was not trained for the current Python engine and road network. Train a new model; legacy SUMO artifacts cannot be reused.")


def validate_neural_artifact(path: str | Path) -> None:
    metadata_path = Path(path).with_suffix(".metadata.json")
    if not metadata_path.exists():
        raise ValueError("Native model metadata is missing. Train a new model for this engine.")
    validate_metadata(json.loads(metadata_path.read_text(encoding="utf-8")))


@lru_cache(maxsize=128)
def _read_metadata(path: str, modified_ns: int, size: int, algorithm: str) -> dict:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    metadata = payload.get("metadata", {}) if algorithm == "ql" else payload
    validate_metadata(metadata)
    return metadata


def artifact_metadata(algorithm: str, path: str | Path) -> dict:
    artifact = Path(path)
    if not artifact.is_file():
        raise ValueError("Model artifact is missing or has not been saved yet.")
    metadata_path = artifact if algorithm == "ql" else artifact.with_suffix(".metadata.json")
    try:
        stat = metadata_path.stat()
        return _read_metadata(str(metadata_path.resolve()), stat.st_mtime_ns, stat.st_size, algorithm)
    except (OSError, TypeError, json.JSONDecodeError) as exc:
        raise ValueError("Model metadata is missing or unreadable; train a new model.") from exc


def training_junction(metadata: dict) -> str:
    scenario = metadata.get("scenario", {})
    settings = scenario.get("engine_config", {})
    if isinstance(settings, str):
        settings = json.loads(settings)
    return settings.get("controlled_junction") or scenario.get("controlled_junction") or load_network().intersections[0]
