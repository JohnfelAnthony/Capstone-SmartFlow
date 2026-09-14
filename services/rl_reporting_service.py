from __future__ import annotations

import json
import statistics
from pathlib import Path


RL_CONTROLLERS = {"ql", "dql", "ppo"}


def _safe_float(value) -> float | None:
    try:
        if value is None:
            return None
        return float(value)
    except (TypeError, ValueError):
        return None


def _round_or_none(value, digits: int = 6) -> float | None:
    numeric_value = _safe_float(value)
    if numeric_value is None:
        return None
    return round(numeric_value, digits)


def _read_json(path: Path) -> dict:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _sidecar_metadata_path(model_path: Path) -> Path:
    return model_path.with_suffix(".metadata.json")


def _training_rewards(events: list[dict], reward_key: str) -> list[float]:
    rewards = []
    for event in events:
        reward = _safe_float(event.get(reward_key))
        if reward is not None:
            rewards.append(reward)
    return rewards


def _reward_rollup(rewards: list[float]) -> dict:
    if not rewards:
        return {
            "best_training_reward": None,
            "final_training_reward": None,
            "last_10_avg_training_reward": None,
        }
    return {
        "best_training_reward": _round_or_none(max(rewards)),
        "final_training_reward": _round_or_none(rewards[-1]),
        "last_10_avg_training_reward": _round_or_none(statistics.fmean(rewards[-10:])),
    }


def load_model_learning_summary(
    controller: str,
    model_path: str | Path | None,
    *,
    model_id: int | None = None,
    model_record: dict | None = None,
) -> dict:
    controller = str(controller or "").lower().replace("_", "-")
    if controller not in RL_CONTROLLERS:
        return {
            "available": False,
            "controller": controller or "unknown",
            "model_id": model_id,
            "message": "No learning model",
        }
    if not model_path:
        return {
            "available": False,
            "controller": controller,
            "model_id": model_id,
            "message": "No model artifact path recorded",
        }

    path = Path(model_path)
    if not path.exists():
        return {
            "available": False,
            "controller": controller,
            "model_id": model_id,
            "model_path": str(path),
            "message": "Model artifact not found",
        }

    if controller == "ql":
        payload = _read_json(path)
        metadata = payload.get("metadata", {}) if isinstance(payload, dict) else {}
        episodes = metadata.get("episodes", []) if isinstance(metadata, dict) else []
        rewards = _training_rewards(episodes, "total_reward")
        rollup = _reward_rollup(rewards)
        best_reward = _safe_float(metadata.get("best_training_reward"))
        if best_reward is not None:
            rollup["best_training_reward"] = _round_or_none(best_reward)
        final_episode = episodes[-1] if episodes else {}
        return {
            "available": True,
            "controller": "ql",
            "algorithm": "ql",
            "implementation": "tabular_q_learning",
            "model_id": model_id,
            "model_path": str(path),
            "training_scenario": metadata.get("scenario") or _model_record_scenarios(model_record),
            "seed_set": metadata.get("seed_set") or _model_record_seed_set(model_record),
            "total_training_episodes": len(episodes),
            "total_timesteps": None,
            "final_epsilon": _round_or_none(final_episode.get("epsilon")),
            "learned_state_count": len(payload.get("q_table", []) or []),
            "observation_version": metadata.get("observation_version") or _model_record_value(model_record, "observation_version"),
            "reward_version": metadata.get("reward_version") or _model_record_value(model_record, "reward_version"),
            "action_space_version": metadata.get("action_space_version") or _model_record_value(model_record, "action_space_version"),
            **rollup,
        }

    if controller in {"dql", "ppo"}:
        metadata_path = _sidecar_metadata_path(path)
        metadata = _read_json(metadata_path) if metadata_path.exists() else {}
        config = metadata.get("config", {}) if isinstance(metadata, dict) else {}
        events = metadata.get("progress_events", []) if isinstance(metadata, dict) else []
        rewards = _training_rewards(events, "last_episode_reward")
        rollup = _reward_rollup(rewards)
        for key in (
            "best_training_reward",
            "final_training_reward",
            "last_10_avg_training_reward",
        ):
            if _safe_float(metadata.get(key)) is not None:
                rollup[key] = _round_or_none(metadata.get(key))
        final_event = events[-1] if events else {}
        return {
            "available": True,
            "controller": controller,
            "algorithm": controller,
            "implementation": metadata.get("implementation") or (
                "stable_baselines3.PPO" if controller == "ppo" else "stable_baselines3.DQN"
            ),
            "model_id": model_id,
            "model_path": str(path),
            "metadata_path": str(metadata_path) if metadata_path.exists() else None,
            "training_scenario": metadata.get("scenario") or _model_record_scenarios(model_record),
            "seed_set": metadata.get("seed_set") or _model_record_seed_set(model_record),
            "total_training_episodes": metadata.get("episodes_requested") or len(events),
            "total_timesteps": config.get("total_timesteps") or final_event.get("timesteps_finished"),
            "final_epsilon": config.get("exploration_final_eps") if controller == "dql" else None,
            "learned_state_count": None,
            "observation_version": metadata.get("observation_version") or _model_record_value(model_record, "observation_version"),
            "reward_version": metadata.get("reward_version") or _model_record_value(model_record, "reward_version"),
            "action_space_version": metadata.get("action_space_version") or _model_record_value(model_record, "action_space_version"),
            **rollup,
        }

    return {
        "available": False,
        "controller": controller,
        "model_id": model_id,
        "model_path": str(path),
        "message": "Learning summary not implemented for this controller",
    }


def _model_record_value(model_record: dict | None, key: str):
    return model_record.get(key) if isinstance(model_record, dict) else None


def _model_record_seed_set(model_record: dict | None):
    raw_seed_set = _model_record_value(model_record, "seed_set_json")
    if not raw_seed_set:
        return None
    try:
        return json.loads(raw_seed_set)
    except Exception:
        return None


def _model_record_scenarios(model_record: dict | None):
    raw_scenarios = _model_record_value(model_record, "training_scenarios_json")
    if not raw_scenarios:
        return None
    try:
        scenarios = json.loads(raw_scenarios)
    except Exception:
        return None
    if isinstance(scenarios, list) and len(scenarios) == 1:
        return scenarios[0]
    return scenarios or None


def primary_evaluation_score(controller_summary: dict | None) -> float | None:
    if not controller_summary:
        return None
    avg_wait = _safe_float((controller_summary.get("avg_wait") or {}).get("mean"))
    if avg_wait is None:
        return None
    return round(-avg_wait, 6)


def build_combined_ranking(summary: dict, model_learning: dict | None = None) -> list[dict]:
    model_learning = model_learning or {}
    fixed_summary = summary.get("fixed-time") or {}
    fixed_wait = _safe_float((fixed_summary.get("avg_wait") or {}).get("mean"))
    fixed_queue = _safe_float((fixed_summary.get("avg_queue") or {}).get("mean"))
    fixed_throughput = _safe_float((fixed_summary.get("throughput") or {}).get("mean"))

    rows = []
    for controller, controller_summary in summary.items():
        avg_wait = _safe_float((controller_summary.get("avg_wait") or {}).get("mean"))
        avg_queue = _safe_float((controller_summary.get("avg_queue") or {}).get("mean"))
        throughput = _safe_float((controller_summary.get("throughput") or {}).get("mean"))
        learning = model_learning.get(controller) or {}
        rows.append(
            {
                "controller": controller,
                "avg_wait_mean": _round_or_none(avg_wait),
                "avg_queue_mean": _round_or_none(avg_queue),
                "throughput_mean": _round_or_none(throughput),
                "primary_evaluation_score": primary_evaluation_score(controller_summary),
                "training": {
                    "total_training_episodes": learning.get("total_training_episodes"),
                    "total_timesteps": learning.get("total_timesteps"),
                    "best_training_reward": learning.get("best_training_reward"),
                    "final_training_reward": learning.get("final_training_reward"),
                    "last_10_avg_training_reward": learning.get("last_10_avg_training_reward"),
                },
                "beats_fixed_time": {
                    "avg_wait": (
                        controller != "fixed-time"
                        and avg_wait is not None
                        and fixed_wait is not None
                        and avg_wait < fixed_wait
                    ),
                    "avg_queue": (
                        controller != "fixed-time"
                        and avg_queue is not None
                        and fixed_queue is not None
                        and avg_queue < fixed_queue
                    ),
                    "throughput": (
                        controller != "fixed-time"
                        and throughput is not None
                        and fixed_throughput is not None
                        and throughput > fixed_throughput
                    ),
                },
            }
        )

    rows.sort(
        key=lambda row: (
            float("inf") if row["avg_wait_mean"] is None else row["avg_wait_mean"],
            -(row["throughput_mean"] or 0),
            row["controller"],
        )
    )
    for index, row in enumerate(rows, start=1):
        row["traffic_performance_rank"] = index
    return rows
