from __future__ import annotations

import argparse
import json
import sys
from datetime import UTC, datetime
from pathlib import Path
from time import perf_counter

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools.training_inputs import cumulative_training_seeds, load_training_scenario

from simulation.dql_training import (
    ACTION_SPACE_VERSION,
    OBSERVATION_VERSION,
    REWARD_VERSION,
    DQLCheckpointEvent,
    DQLProgressEvent,
    DQLTrainingConfig,
    DQLTrainingInterrupted,
    calculate_dql_timesteps,
    train_deep_q_learning,
)
from simulation.rl_env import SmartFlowRLEnv
from simulation.traffic_engine import RL_SERVICE_ACTIONS


def _parse_seed_set(raw_seed_set: str) -> tuple[int, ...]:
    seeds = tuple(
        int(seed.strip())
        for seed in str(raw_seed_set or "").split(",")
        if seed.strip()
    )
    if not seeds:
        raise argparse.ArgumentTypeError("seed set must contain at least one integer.")
    return seeds


def _default_output_path() -> Path:
    timestamp = datetime.now(UTC).strftime("%Y%m%d_%H%M%S")
    return ROOT / "data" / "models" / "dql" / f"dql_{timestamp}.zip"


def _format_duration(seconds: float) -> str:
    seconds = max(float(seconds or 0), 0.0)
    minutes, remaining_seconds = divmod(int(round(seconds)), 60)
    hours, minutes = divmod(minutes, 60)
    if hours:
        return f"{hours}h {minutes:02d}m {remaining_seconds:02d}s"
    if minutes:
        return f"{minutes}m {remaining_seconds:02d}s"
    return f"{remaining_seconds}s"


class SeedCyclingSmartFlowRLEnv(SmartFlowRLEnv):
    def __init__(self, *, seed_set: tuple[int, ...], **kwargs):
        super().__init__(seed=seed_set[0], **kwargs)
        self.seed_set = tuple(int(seed) for seed in seed_set)
        self._reset_count = 0

    def reset(self, *, seed: int | None = None, options: dict | None = None):
        if seed is None:
            seed = self.seed_set[self._reset_count % len(self.seed_set)]
            self._reset_count += 1
        return super().reset(seed=seed, options=options)


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Train the SMARTFLOW Deep Q-Learning baseline offline using Stable-Baselines3 DQN."
    )
    parser.add_argument("--episodes", type=int, default=10)
    parser.add_argument("--seeds", type=_parse_seed_set, default=_parse_seed_set("11,22,33,44,55"))
    parser.add_argument("--warmup-seconds", type=float, default=20.0)
    parser.add_argument("--evaluation-seconds", type=float, default=300.0)
    parser.add_argument("--decision-interval-seconds", type=float, default=5.0)
    parser.add_argument("--minimum-green-hold-seconds", type=float, default=10.0)
    parser.add_argument("--max-steps-per-episode", type=int, default=None)
    parser.add_argument("--intersection-id", default="tagum_network")
    parser.add_argument("--scenario-id", type=int, help="Use the complete saved scenario, including native engine_config")
    parser.add_argument("--scenario-file", type=Path, help="Immutable scenario snapshot for this job")
    parser.add_argument("--scenario-name", default="SMARTFLOW DQL Training Scenario")
    parser.add_argument("--traffic-density", default="medium")
    parser.add_argument("--pedestrian-density", default="medium")
    parser.add_argument("--emergency-mode", default="disabled")
    parser.add_argument("--road-constraint", default="None")
    parser.add_argument("--learning-rate", type=float, default=1e-4)
    parser.add_argument("--buffer-size", type=int, default=50_000)
    parser.add_argument("--learning-starts", type=int, default=100)
    parser.add_argument("--batch-size", type=int, default=32)
    parser.add_argument("--gamma", type=float, default=0.99)
    parser.add_argument("--target-update-interval", type=int, default=250)
    parser.add_argument("--exploration-fraction", type=float, default=0.2)
    parser.add_argument("--exploration-initial-eps", type=float, default=1.0)
    parser.add_argument("--exploration-final-eps", type=float, default=0.05)
    parser.add_argument("--agent-seed", type=int, default=42)
    parser.add_argument("--output", type=Path, default=None)
    parser.add_argument("--checkpoint-every", type=int, default=25)
    parser.add_argument("--resume-model", type=Path, default=None)
    parser.add_argument("--skip-db", action="store_true")
    return parser


def _create_model_record(
    *,
    model_name: str,
    output_path: Path,
    scenario: dict,
    seed_set: tuple[int, ...],
    best_score: float | None,
) -> int | None:
    try:
        import database

        database.init_db()
        model_id = database.create_rl_model(
            name=model_name,
            algorithm="dql",
            version="1.0",
            checkpoint_path=str(output_path),
            intersection_support=[scenario["intersection_id"]],
            training_scenarios=[scenario],
            observation_version=OBSERVATION_VERSION,
            reward_version=REWARD_VERSION,
            action_space_version=ACTION_SPACE_VERSION,
            seed_set=list(seed_set),
            training_date=datetime.now(UTC).isoformat(),
            best_evaluation_score=best_score,
        )
        return int(model_id)
    except Exception as exc:
        print(f"Warning: DQL DB model registration failed: {exc}")
        return None


def _save_db_checkpoint(
    *,
    model_id: int | None,
    episode: int,
    reward: float,
    epsilon: float,
    path: Path,
):
    if model_id is None:
        return
    try:
        import database

        database.create_rl_checkpoint(
            model_id=model_id,
            episode=episode,
            reward=reward,
            epsilon=epsilon,
            path=str(path),
        )
    except Exception as exc:
        print(f"Warning: DQL DB checkpoint failed: {exc}")


def main() -> int:
    parser = _build_parser()
    args = parser.parse_args()

    scenario = {
        "name": args.scenario_name,
        "intersection_id": args.intersection_id,
        "traffic_density": args.traffic_density,
        "pedestrian_density": args.pedestrian_density,
        "emergency_mode": args.emergency_mode,
        "road_constraint": args.road_constraint,
    }
    scenario = load_training_scenario(args, scenario)
    seed_history = cumulative_training_seeds(args.seeds, args.resume_model, "dql", scenario)

    total_timesteps = calculate_dql_timesteps(
        episodes=args.episodes,
        evaluation_seconds=args.evaluation_seconds,
        decision_interval_seconds=args.decision_interval_seconds,
        max_steps_per_episode=args.max_steps_per_episode,
    )
    config = DQLTrainingConfig(
        total_timesteps=total_timesteps,
        learning_rate=args.learning_rate,
        buffer_size=args.buffer_size,
        learning_starts=args.learning_starts,
        batch_size=args.batch_size,
        gamma=args.gamma,
        target_update_interval=args.target_update_interval,
        exploration_fraction=args.exploration_fraction,
        exploration_initial_eps=args.exploration_initial_eps,
        exploration_final_eps=args.exploration_final_eps,
        seed=args.agent_seed,
    )

    def env_factory():
        return SeedCyclingSmartFlowRLEnv(
            seed_set=args.seeds,
            scenario=scenario,
            warmup_seconds=args.warmup_seconds,
            evaluation_seconds=args.evaluation_seconds,
            decision_interval_seconds=args.decision_interval_seconds,
            minimum_green_hold_seconds=args.minimum_green_hold_seconds,
            controller_provenance="dql",
        )

    print("Starting SMARTFLOW DQL offline training")
    print(f"Scenario: {json.dumps(scenario, sort_keys=True)}")
    print(f"Episodes: {args.episodes}, seeds: {args.seeds}")
    print(f"Timesteps: {total_timesteps}")
    if args.resume_model:
        print(f"Resuming DQL model from: {args.resume_model}")
    if args.checkpoint_every > 0:
        print(f"Checkpoint every {args.checkpoint_every} completed episode(s).")
    print("Progress: waiting for episode 1 to finish...")

    progress_events: list[DQLProgressEvent] = []
    training_started_at = perf_counter()
    output_path = args.output or _default_output_path()
    model_id = None
    if not args.skip_db:
        model_id = _create_model_record(
            model_name=f"DQL {scenario['intersection_id']} {output_path.stem}",
            output_path=output_path,
            scenario=scenario,
            seed_set=seed_history,
            best_score=None,
        )

    def print_progress(event: DQLProgressEvent):
        progress_events.append(event)
        elapsed_seconds = perf_counter() - training_started_at
        progress_ratio = min(event.timesteps_finished / max(total_timesteps, 1), 1)
        estimated_total_seconds = elapsed_seconds / progress_ratio if progress_ratio > 0 else 0.0
        remaining_seconds = max(estimated_total_seconds - elapsed_seconds, 0.0)
        print(
            "[{episode}/{total_episodes} | {percent:5.1f}%] timesteps={steps}/{total_steps} "
            "reward={reward:.6f} length={length} elapsed={elapsed} eta={eta}".format(
                episode=event.episodes_finished,
                total_episodes=args.episodes,
                percent=progress_ratio * 100,
                steps=event.timesteps_finished,
                total_steps=total_timesteps,
                reward=event.last_episode_reward,
                length=event.last_episode_length,
                elapsed=_format_duration(elapsed_seconds),
                eta=_format_duration(remaining_seconds),
            ),
            flush=True,
        )

    def record_checkpoint(event: DQLCheckpointEvent):
        _save_db_checkpoint(
            model_id=model_id,
            episode=event.episodes_finished,
            reward=event.reward,
            epsilon=event.epsilon,
            path=event.model_path,
        )
        print(f"Saved DQL checkpoint: {event.model_path}", flush=True)

    try:
        saved_path, metadata_path = train_deep_q_learning(
            env_factory=env_factory,
            config=config,
            output_path=output_path,
            metadata={
                "scenario": scenario,
                "seed_set": list(seed_history),
                "action_labels": list(RL_SERVICE_ACTIONS),
                "episodes_requested": args.episodes,
                "warmup_seconds": args.warmup_seconds,
                "evaluation_seconds": args.evaluation_seconds,
                "decision_interval_seconds": args.decision_interval_seconds,
                "minimum_green_hold_seconds": args.minimum_green_hold_seconds,
            },
            resume_model_path=args.resume_model,
            checkpoint_every_episodes=args.checkpoint_every,
            checkpoint_dir=output_path.parent / "checkpoints",
            on_checkpoint=record_checkpoint,
            on_episode_complete=print_progress,
        )
    except RuntimeError as exc:
        raise SystemExit(str(exc)) from exc
    except DQLTrainingInterrupted as exc:
        print("Interrupt signal received. Saved partial DQL training artifact.")
        saved_path = exc.saved_path
        metadata_path = exc.metadata_path
        final_event = progress_events[-1] if progress_events else None
        if final_event is not None:
            _save_db_checkpoint(
                model_id=model_id,
                episode=final_event.episodes_finished,
                reward=final_event.last_episode_reward,
                epsilon=args.exploration_final_eps,
                path=saved_path,
            )
        print(f"Saved partial DQL model artifact: {saved_path}")
        print(f"Saved partial DQL metadata: {metadata_path}")
        if model_id is not None:
            print(f"Registered rl_models.id: {model_id}")
        return 130

    best_score = max((event.last_episode_reward for event in progress_events), default=None)
    final_event = progress_events[-1] if progress_events else None
    if final_event is not None:
        _save_db_checkpoint(
            model_id=model_id,
            episode=final_event.episodes_finished,
            reward=final_event.last_episode_reward,
            epsilon=args.exploration_final_eps,
            path=saved_path,
        )

    print(f"Saved DQL model artifact: {saved_path}")
    print(f"Saved DQL metadata: {metadata_path}")
    if model_id is not None:
        print(f"Registered rl_models.id: {model_id}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
