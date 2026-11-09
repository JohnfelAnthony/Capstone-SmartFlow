"""Register compatible local SmartFlow models without unpickling uploaded files."""
from __future__ import annotations

import hashlib
import io
import json
import math
from pathlib import Path
from tempfile import TemporaryDirectory
from zipfile import BadZipFile, ZipFile

import database
from desktop.paths import extended_path
from services.data_paths import data_directory
from simulation.model_contract import phase_plan, validate_metadata
from simulation.network_registry import engine_for_scenario
from simulation.ql_agent import TabularQLearningAgent
from simulation.traffic_engine import RL_SERVICE_ACTIONS

MAX_MODEL_BYTES = 32 * 1024 * 1024
MAX_METADATA_BYTES = 2 * 1024 * 1024
MAX_REQUEST_BYTES = ((MAX_MODEL_BYTES + MAX_METADATA_BYTES) * 4 // 3) + 4096


def json_object(raw: bytes) -> dict:
    value = json.loads(raw)
    if not isinstance(value, dict):
        raise ValueError("Expected a SmartFlow JSON object.")
    return value


def inspect_model(filename: str, content: bytes, sidecar: bytes | None) -> tuple[str, dict]:
    if not content or len(content) > MAX_MODEL_BYTES:
        raise ValueError("Select a model up to 32 MB.")
    suffix = Path(filename).suffix.lower()
    if suffix == ".json" and sidecar is None:
        artifact = json_object(content)
        if artifact.get("algorithm") != "ql" or artifact.get("artifact_type") != "tabular_q_table":
            raise ValueError("Select the QL model JSON, or a neural model ZIP with its metadata.")
        metadata = artifact.get("metadata")
        try:
            agent = TabularQLearningAgent.from_artifact(artifact)
            if agent.action_count != len(RL_SERVICE_ACTIONS) or not all(
                len(values) == agent.action_count and all(math.isfinite(value) for value in values)
                for values in agent.q_table.values()
            ):
                raise ValueError
        except (AttributeError, KeyError, TypeError, ValueError, OverflowError) as exc:
            raise ValueError("The QL model has an invalid Q table or configuration.") from exc
        algorithm = "ql"
    elif suffix == ".zip":
        if not sidecar or len(sidecar) > MAX_METADATA_BYTES:
            raise ValueError("Select the ZIP and its matching .metadata.json file (up to 2 MB).")
        metadata = json_object(sidecar)
        algorithm = metadata.get("algorithm")
        implementations = {"dql": "stable-baselines3.DQN", "ppo": "stable-baselines3.PPO"}
        if algorithm not in ("dql", "ppo") or metadata.get("implementation") != implementations[algorithm]:
            raise ValueError("The metadata must identify a SmartFlow DQL or PPO model.")
        try:
            with ZipFile(io.BytesIO(content)) as archive:
                members = archive.infolist()
                if len(members) > 20 or sum(item.file_size for item in members) > 128 * 1024 * 1024:
                    raise ValueError("The expanded model ZIP exceeds the import limit.")
                names = {item.filename for item in members}
                if len(names) != len(members) or not {"data", "policy.pth", "_stable_baselines3_version"} <= names:
                    raise ValueError("The ZIP does not contain a complete neural model.")
                settings_file = archive.getinfo("data")
                if settings_file.file_size > MAX_METADATA_BYTES:
                    raise ValueError("The model settings exceed the import limit.")
                settings = json_object(archive.read(settings_file))
                if ("exploration_initial_eps" in settings) != (algorithm == "dql") or (
                    "clip_range" in settings
                ) != (algorithm == "ppo"):
                    raise ValueError("The model ZIP and metadata identify different algorithms.")
                if archive.testzip() is not None:
                    raise ValueError("The model ZIP contains a damaged file.")
        except (BadZipFile, RuntimeError, NotImplementedError) as exc:
            raise ValueError("The model ZIP is damaged or unsupported.") from exc
    else:
        raise ValueError("Select one QL JSON or one DQL/PPO ZIP and its metadata.")

    if not isinstance(metadata, dict) or not isinstance(metadata.get("scenario"), dict):
        raise ValueError("The model is missing its SmartFlow training scenario.")
    scenario = metadata["scenario"]
    engine = engine_for_scenario(scenario, seed=0)
    validate_metadata(metadata, engine.base_network)
    if metadata.get("phase_plan") != phase_plan(engine):
        raise ValueError("The model's phase order does not match its training scenario.")
    engine.configure_rl_control(
        decision_interval=metadata.get("decision_interval_seconds", 5),
        minimum_green_hold=metadata.get("minimum_green_hold_seconds", 10),
    )
    for key in ("observation_version", "reward_version", "action_space_version", "created_at"):
        if key in metadata and not isinstance(metadata[key], str):
            raise ValueError(f"Invalid model metadata field: {key}.")
    return algorithm, metadata


def write_artifact(path: Path, content: bytes) -> None:
    path = extended_path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with TemporaryDirectory(prefix="write-", dir=path.parent) as temp:
        staged = Path(temp) / path.name
        staged.write_bytes(content)
        staged.replace(path)


def register_model(connection, filename: str, content: bytes, sidecar: bytes | None = None) -> dict:
    """Use the caller's write transaction so seed data and manual imports share one registry."""
    algorithm, metadata = inspect_model(filename, content, sidecar)
    digest = hashlib.sha256(content).hexdigest()
    if sidecar is not None:
        digest = hashlib.sha256(bytes.fromhex(digest) + hashlib.sha256(sidecar).digest()).hexdigest()
    target = data_directory() / "models" / algorithm / "imported" / f"{digest}{Path(filename).suffix.lower()}"
    existing = connection.execute(
        "SELECT id, name FROM rl_models WHERE algorithm = ? AND checkpoint_path = ?", (algorithm, str(target))
    ).fetchone()
    write_artifact(target, content)
    if sidecar is not None:
        write_artifact(target.with_suffix(".metadata.json"), sidecar)
    if existing:
        return {"id": existing["id"], "algorithm": algorithm, "name": existing["name"], "already_imported": True}

    name = f"{algorithm.upper()} {Path(filename).stem[:130]}"
    scenario = metadata["scenario"]
    model_id = connection.execute(
        """INSERT INTO rl_models (
               name, algorithm, checkpoint_path, intersection_support_json, training_scenarios_json,
               observation_version, reward_version, action_space_version, seed_set_json, training_date
           ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (name, algorithm, str(target), json.dumps([scenario.get("network_id") or "tagum_network"]),
         json.dumps([scenario.get("name") or "Imported scenario"]),
         metadata.get("observation_version", "obs_v2"), metadata.get("reward_version", "reward_v3"),
         metadata.get("action_space_version", "action_v1"), json.dumps(metadata.get("seed_set") or []),
         metadata.get("created_at")),
    ).lastrowid
    return {"id": model_id, "algorithm": algorithm, "name": name, "already_imported": False}


def import_model(filename: str, content: bytes, sidecar: bytes | None) -> dict:
    with database.get_db() as connection:
        connection.execute("BEGIN IMMEDIATE")
        return register_model(connection, filename, content, sidecar)
