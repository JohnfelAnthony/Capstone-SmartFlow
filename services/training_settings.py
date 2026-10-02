"""Validate job inputs before persistence or subprocess launch."""
import hashlib
import json
import math

import database
from services.scenario_identity import validate_resume_snapshot
from services.observation_identity import validate_observed_holdout
from simulation.model_contract import artifact_metadata, training_junction
from simulation.traffic_engine import TrafficEngine


def numeric(value, label, lower, upper, *, integer=False):
    try:
        result = float(value)
    except (TypeError, ValueError):
        raise ValueError(f"{label} must be a number") from None
    if isinstance(value, bool) or not math.isfinite(result) or not lower <= result <= upper:
        raise ValueError(f"{label} must be between {lower} and {upper}")
    if integer and result != int(result):
        raise ValueError(f"{label} must be a whole number")
    return int(result) if integer else result


def prepare_settings(settings: dict) -> dict:
    scenario_id = numeric(settings.get("scenario_id"), "Saved scenario ID", 1, 2**31-1, integer=True)
    scenario = database.get_scenario_by_id(scenario_id)
    if not scenario or scenario.get("is_archived"):
        raise ValueError("Select an available saved scenario before starting training.")
    engine = TrafficEngine()
    engine.configure_from_scenario(scenario)
    normalized = {"scenario_id": scenario_id}
    evaluation_scenario_id = numeric(settings.get("evaluation_scenario_id"), "Held-out scenario ID", 1, 2**31-1, integer=True)
    if evaluation_scenario_id == scenario_id:
        raise ValueError("Held-out evaluation must use a different saved scenario.")
    evaluation_scenario = database.get_scenario_by_id(evaluation_scenario_id)
    if not evaluation_scenario or evaluation_scenario.get("is_archived"):
        raise ValueError("Select an available held-out evaluation scenario.")
    evaluation_engine = TrafficEngine()
    evaluation_engine.configure_from_scenario(evaluation_scenario)
    validate_observed_holdout({"engine_config": engine.config}, {"engine_config": evaluation_engine.config})
    if evaluation_engine.controlled_junction != engine.controlled_junction:
        raise ValueError("Training and held-out scenarios must use the same controlled junction.")
    normalized["evaluation_scenario_id"] = evaluation_scenario_id
    for key, default, lower, upper, integer in (
        ("episodes", 10, 1, 100000, True), ("checkpoint_every", 25, 0, 100000, True),
        ("warmup_seconds", 20, 0, 86400, False), ("evaluation_seconds", 300, .1, 86400, False),
        ("decision_interval_seconds", 5, .1, 60, False), ("minimum_green_hold_seconds", 10, 5, 60, False),
    ):
        normalized[key] = numeric(settings.get(key, default), key.replace("_", " "), lower, upper, integer=integer)
    for key in ("warmup_seconds", "evaluation_seconds", "decision_interval_seconds"):
        value = normalized[key]
        if abs(value*10-round(value*10)) > 1e-7:
            raise ValueError(f"{key} must use 0.1-second increments")
    if normalized["warmup_seconds"] + normalized["evaluation_seconds"] > 86400:
        raise ValueError("Warmup and evaluation together must not exceed 86400 seconds")
    if normalized["decision_interval_seconds"] > normalized["evaluation_seconds"]:
        raise ValueError("Decision interval must not exceed the evaluation duration")
    for key, default in (("seeds", "11,22,33,44,55"), ("evaluation_seeds", "101,102,103,104,105")):
        seeds = [value.strip() for value in str(settings.get(key, default)).split(",")]
        if not 1 <= len(seeds) <= 100 or any(not value.isdecimal() for value in seeds):
            raise ValueError(f"{key} must be 1–100 comma-separated non-negative integers")
        normalized[key] = ",".join(str(numeric(value, key, 0, 2**32-1, integer=True)) for value in seeds)
    if set(normalized["seeds"].split(",")) & set(normalized["evaluation_seeds"].split(",")):
        raise ValueError("Training and held-out evaluation seeds must not overlap.")
    engine.configure_rl_control(decision_interval=normalized["decision_interval_seconds"],
                                minimum_green_hold=normalized["minimum_green_hold_seconds"])
    snapshot = {"id": scenario_id, "name": scenario["name"], "intersection_id": engine.intersection_id,
                "engine_config": engine.config}
    normalized["scenario_snapshot"] = snapshot
    normalized["scenario_sha256"] = hashlib.sha256(json.dumps(snapshot, sort_keys=True).encode()).hexdigest()
    evaluation_snapshot = {"id": evaluation_scenario_id, "name": evaluation_scenario["name"],
                           "intersection_id": evaluation_engine.intersection_id,
                           "engine_config": evaluation_engine.config}
    normalized["evaluation_scenario_snapshot"] = evaluation_snapshot
    normalized["evaluation_scenario_sha256"] = hashlib.sha256(json.dumps(evaluation_snapshot, sort_keys=True).encode()).hexdigest()
    normalized["controlled_junction"] = engine.controlled_junction
    if settings.get("resume_model"):
        raise ValueError("Choose a registered model or checkpoint; arbitrary resume paths are not accepted.")
    if settings.get("resume_model_id") is not None:
        model_id = numeric(settings["resume_model_id"], "Resume model ID", 1, 2**31-1, integer=True)
        model = database.get_rl_model_by_id(model_id)
        if not model:
            raise ValueError("Resume model no longer exists")
        resume_path = model.get("checkpoint_path")
        checkpoint_id = settings.get("resume_checkpoint_id")
        if checkpoint_id is not None:
            checkpoint_id = numeric(checkpoint_id, "Checkpoint ID", 1, 2**31-1, integer=True)
            checkpoint = database.get_rl_checkpoint_by_id(checkpoint_id)
            if not checkpoint or checkpoint["model_id"] != model_id:
                raise ValueError("Checkpoint does not belong to the selected model")
            resume_path = checkpoint["path"]
        metadata = validate_model_for_settings(model, normalized, path=resume_path)
        trained_scenario = metadata.get("scenario")
        validate_resume_snapshot(trained_scenario, snapshot)
        if isinstance(trained_scenario, dict) and trained_scenario.get("id") == evaluation_scenario_id:
            raise ValueError("Held-out evaluation must use a scenario different from the resumed model's training scenario.")
        if set(str(seed) for seed in metadata.get("seed_set", [])) & set(normalized["evaluation_seeds"].split(",")):
            raise ValueError("Held-out evaluation seeds overlap the resumed model's training seeds.")
        normalized.update(resume_model=resume_path, resume_model_id=model_id,
                          resume_checkpoint_id=checkpoint_id, resume_algorithm=str(model["algorithm"]).lower())
        normalized["resume_training_status"] = metadata.get("training_status")
        if str(model["algorithm"]).lower() == "ql":
            with open(resume_path, encoding="utf-8") as stream:
                saved_parameters = json.load(stream).get("config", {})
        else:
            saved_parameters = metadata.get("config", {})
        if not isinstance(saved_parameters, dict) or not saved_parameters:
            raise ValueError("Resume artifact does not describe its saved learning parameters")
        normalized["resume_advanced"] = saved_parameters
    elif settings.get("resume_checkpoint_id") is not None:
        raise ValueError("Choose a model before choosing a checkpoint")
    return normalized


def validate_model_for_settings(model, settings, *, path=None):
    algorithm = str(model["algorithm"]).lower()
    metadata = artifact_metadata(algorithm, path or model.get("checkpoint_path") or "")
    if training_junction(metadata) != settings["controlled_junction"]:
        raise ValueError("This model was trained for a different controlled junction. Choose the matching scenario or train a new model.")
    for key, default in (("decision_interval_seconds", 5), ("minimum_green_hold_seconds", 10)):
        if settings[key] != metadata.get(key, default):
            raise ValueError(f"Model requires {key.replace('_', ' ')} = {metadata.get(key, default)}")
    return metadata


def validate_advanced(advanced: dict, algorithms: list[str]) -> dict:
    limits = {
        "ql": {"alpha": (.000001, 1), "gamma": (0, 1), "epsilon": (0, 1), "min_epsilon": (0, 1), "epsilon_decay": (.000001, 1)},
        "dql": {"learning_rate": (1e-8, 1), "learning_starts": (0, 1000000), "buffer_size": (2, 1000000), "batch_size": (1, 65536), "gamma": (0, 1), "target_update_interval": (1, 1000000)},
        "ppo": {"learning_rate": (1e-8, 1), "n_steps": (2, 65536), "batch_size": (2, 65536), "n_epochs": (1, 100), "gamma": (0, 1), "gae_lambda": (0, 1), "clip_range": (.000001, 1)},
    }
    integer_keys = {"learning_starts", "buffer_size", "batch_size", "target_update_interval", "n_steps", "n_epochs"}
    result = {}
    for algorithm in algorithms:
        values = advanced.get(algorithm, {})
        if not isinstance(values, dict):
            raise ValueError(f"{algorithm.upper()} settings must be an object")
        unknown = set(values)-set(limits[algorithm])
        if unknown:
            raise ValueError(f"Unknown {algorithm.upper()} setting: {sorted(unknown)[0]}")
        result[algorithm] = {key: numeric(value, f"{algorithm.upper()} {key}", *limits[algorithm][key], integer=key in integer_keys) for key, value in values.items()}
    ppo = result.get("ppo", {})
    if "ppo" in result and (ppo.get("batch_size", 64) > ppo.get("n_steps", 128) or ppo.get("n_steps", 128) % ppo.get("batch_size", 64)):
        raise ValueError("PPO batch size must divide rollout steps and must not exceed them")
    dql = result.get("dql", {})
    if "dql" in result and dql.get("batch_size", 32) > dql.get("buffer_size", 50000):
        raise ValueError("DQL batch size must not exceed replay buffer size")
    return result
