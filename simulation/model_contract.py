"""Prevent legacy or differently shaped network models from running silently."""
import hashlib
import json
from pathlib import Path

from .road_network import load_network


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
