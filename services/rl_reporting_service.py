from __future__ import annotations

import json
import math
import statistics
from pathlib import Path
from services.metric_definitions import METRIC_DEFINITIONS


RL_CONTROLLERS = {"ql", "dql", "ppo"}


def _safe_float(value) -> float | None:
    try:
        if value is None:
            return None
        if isinstance(value, bool):
            return None
        number = float(value)
        return number if math.isfinite(number) else None
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
    wait_summary = controller_summary.get("avg_wait") or {}
    if wait_summary.get("available_count", 0) < wait_summary.get("run_count", 0):
        return None
    avg_wait = _summary_mean(controller_summary, "avg_wait")
    if avg_wait is None:
        return None
    return round(-avg_wait, 6)


RANKING_CRITERION = "Lowest mean stopped vehicle wait; completed trips break ties. Not an overall traffic-performance recommendation."
RANKING_VERSION = "waiting-time-order-1"
TRADEOFF_METRICS = ("avg_wait", "avg_queue", "max_queue", "throughput", "avg_travel_time",
                    "avg_ped_delay", "requested_vehicles", "total_vehicles_spawned", "pending_demand",
                    "dropped_vehicles", "unfinished_vehicles", "boundary_wait_seconds",
                    "avg_admitted_boundary_wait",
                    "measurement_start", "measurement_seconds")


def _summary_mean(summary: dict | None, key: str) -> float | None:
    summary = summary or {}
    item = summary.get(key)
    if not isinstance(item, dict) or item.get("available_count") == 0:
        return None
    value = _safe_float(item.get("mean"))
    population_keys = (METRIC_DEFINITIONS.get(key) or {}).get("population_keys", [])
    if population_keys:
        values = [_safe_float(summary[name].get("mean")) if isinstance(summary.get(name), dict) else None
                  for name in population_keys]
        if all(count is not None for count in values):
            if sum(values) <= 0:
                return None
        elif value == 0 and not (_safe_float(item.get("available_count")) or 0) > 0:
            return None
    return value


def _comparison(value, reference, baseline: bool) -> dict:
    difference = value-reference if value is not None and reference is not None else None
    return {"value": value, "fixed_time_value": reference,
            "difference": _round_or_none(difference),
            "percent_change": _round_or_none(difference/abs(reference)*100) if difference is not None and reference != 0 else None,
            "percent_change_note": "Undefined for a zero reference." if reference == 0 else None,
            "relation": "unavailable" if difference is None else "baseline" if baseline else
                        "tie" if difference == 0 else "lower" if difference < 0 else "higher"}


def build_combined_ranking(summary: dict, model_learning: dict | None = None) -> list[dict]:
    model_learning = model_learning or {}
    fixed_summary = summary.get("fixed-time") or {}
    fixed_wait = _summary_mean(fixed_summary, "avg_wait")
    fixed_queue = _summary_mean(fixed_summary, "avg_queue")
    fixed_throughput = _summary_mean(fixed_summary, "throughput")
    reference_summary = summary.get("no-signal")
    reference_wait = _summary_mean(reference_summary or {}, "avg_wait")
    reference_queue = _summary_mean(reference_summary or {}, "avg_queue")
    reference_throughput = _summary_mean(reference_summary or {}, "throughput")

    rows = []
    for controller, controller_summary in summary.items():
        avg_wait = _summary_mean(controller_summary, "avg_wait")
        avg_queue = _summary_mean(controller_summary, "avg_queue")
        throughput = _summary_mean(controller_summary, "throughput")
        learning = model_learning.get(controller) or {}
        row = (
            {
                "controller": controller,
                "ranking_version": RANKING_VERSION,
                "ranking_criterion": RANKING_CRITERION,
                "overall_recommendation": None,
                "interpretation": "No overall recommendation criteria have been established. Review completion, unfinished demand, pedestrians and other tradeoffs. Legacy summaries may lack population evidence.",
                "comparison_to_fixed_time": {key: _comparison(_summary_mean(controller_summary, key),
                    _summary_mean(fixed_summary, key), controller == "fixed-time") for key in TRADEOFF_METRICS},
                "avg_wait_mean": _round_or_none(avg_wait),
                "ranking_eligible": primary_evaluation_score(controller_summary) is not None,
                "avg_wait_coverage": {key: _safe_float((controller_summary.get("avg_wait") or {}).get(key))
                                      for key in ("available_count", "run_count")},
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
                        None if avg_wait is None or fixed_wait is None else
                        controller != "fixed-time"
                        and avg_wait is not None
                        and fixed_wait is not None
                        and avg_wait < fixed_wait
                    ),
                    "avg_queue": (
                        None if avg_queue is None or fixed_queue is None else
                        controller != "fixed-time"
                        and avg_queue is not None
                        and fixed_queue is not None
                        and avg_queue < fixed_queue
                    ),
                    "throughput": (
                        None if throughput is None or fixed_throughput is None else
                        controller != "fixed-time"
                        and throughput is not None
                        and fixed_throughput is not None
                        and throughput > fixed_throughput
                    ),
                },
            }
        )
        if reference_summary:  # the no-signal condition is a second reference beside fixed-time
            row["comparison_to_no_signal"] = {key: _comparison(_summary_mean(controller_summary, key), _summary_mean(reference_summary, key), controller == "no-signal")
                                                for key in TRADEOFF_METRICS}
            row["beats_no_signal"] = {
                "avg_wait": None if avg_wait is None or reference_wait is None else controller != "no-signal" and avg_wait < reference_wait,
                "avg_queue": None if avg_queue is None or reference_queue is None else controller != "no-signal" and avg_queue < reference_queue,
                "throughput": None if throughput is None or reference_throughput is None else controller != "no-signal" and throughput > reference_throughput,
            }
        rows.append(row)

    rows.sort(
        key=lambda row: (
            float("inf") if not row["ranking_eligible"] else row["avg_wait_mean"],
            float("inf") if row["throughput_mean"] is None else -row["throughput_mean"],
            row["controller"],
        )
    )
    previous = None
    rank = None
    for index, row in enumerate(rows, start=1):
        criterion = (row["avg_wait_mean"], row["throughput_mean"])
        if not row["ranking_eligible"]:
            rank = None
        elif criterion != previous:
            rank = index
        row["waiting_time_rank"] = rank
        # Retain the old key for consumers; explicitly qualify its narrow semantics.
        row["traffic_performance_rank"] = rank
        row["traffic_performance_rank_semantics"] = "Legacy alias of waiting_time_rank; not overall performance."
        previous = criterion
    return rows
