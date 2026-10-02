"""Load immutable job inputs, or a saved scenario for direct CLI use."""
import json
from pathlib import Path
from services.scenario_identity import validate_resume_snapshot


def cumulative_training_seeds(seeds: tuple[int, ...], resume_model: Path | None, algorithm: str, scenario: dict) -> tuple[int, ...]:
    if resume_model is None:
        return seeds
    metadata_path = resume_model if algorithm == "ql" else resume_model.with_suffix(".metadata.json")
    payload = json.loads(metadata_path.read_text(encoding="utf-8"))
    metadata = payload.get("metadata", {}) if algorithm == "ql" else payload
    previous_seeds = metadata.get("seed_set")
    if not isinstance(previous_seeds, list) or not previous_seeds:
        raise ValueError("Resume artifact lacks its training seed history.")
    validate_resume_snapshot(metadata.get("scenario"), scenario)
    return tuple(sorted(set(seeds) | {int(seed) for seed in previous_seeds}))


def load_training_scenario(args, fallback: dict) -> dict:
    if args.scenario_file is not None:
        scenario = json.loads(args.scenario_file.read_text(encoding="utf-8"))
        if not isinstance(scenario, dict):
            raise ValueError("Scenario snapshot must be an object")
        return scenario
    if args.scenario_id is not None:
        import database
        database.init_db()
        scenario = database.get_scenario_by_id(args.scenario_id)
        if not scenario or scenario.get("is_archived"):
            raise ValueError("Saved scenario missing or archived")
        return scenario
    return fallback
