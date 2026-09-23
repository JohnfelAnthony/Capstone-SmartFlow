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

from simulation.ppo_training import (
    ACTION_SPACE_VERSION,
    OBSERVATION_VERSION,
    REWARD_VERSION,
    PPOCheckpointEvent,
    PPOProgressEvent,
    PPOTrainingConfig,
    PPOTrainingInterrupted,
    calculate_ppo_timesteps,
    train_ppo,
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
    return ROOT / "data" / "models" / "ppo" / f"ppo_{timestamp}.zip"


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
        description="Train the SMARTFLOW PPO baseline offline using Stable-Baselines3 PPO."
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
    parser.add_argument("--scenario-name", default="SMARTFLOW PPO Training Scenario")
    parser.add_argument("--traffic-density", default="medium")
    parser.add_argument("--pedestrian-density", default="medium")
    parser.add_argument("--emergency-mode", default="disabled")
    parser.add_argument("--road-constraint", default="None")
    parser.add_argument("--learning-rate", type=float, default=3e-4)
    parser.add_argument("--n-steps", type=int, default=128)
    parser.add_argument("--batch-size", type=int, default=64)
    parser.add_argument("--n-epochs", type=int, default=10)
    parser.add_argument("--gamma", type=float, default=0.99)
    parser.add_argument("--gae-lambda", type=float, default=0.95)
    parser.add_argument("--clip-range", type=float, default=0.2)
    parser.add_argument("--ent-coef", type=float, default=0.0)
    parser.add_argument("--vf-coef", type=float, default=0.5)
    parser.add_argument("--max-grad-norm", type=float, default=0.5)
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
            algorithm="ppo",
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
        print(f"Warning: PPO DB model registration failed: {exc}")
        return None


def _save_db_checkpoint(
    *,
    model_id: int | None,
    episode: int,
    reward: float,
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
            epsilon=0.0,
            path=str(path),
        )
    except Exception as exc:
        print(f"Warning: PPO DB checkpoint failed: {exc}")


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
    if args.scenario_id is not None:
        database.init_db()
        saved = database.get_scenario_by_id(args.scenario_id)
        if not saved or saved.get("is_archived"):
            raise SystemExit("Saved scenario missing or archived")
        scenario = saved

    total_timesteps = calculate_ppo_timesteps(
        episodes=args.episodes,
        evaluation_seconds=args.evaluation_seconds,
        decision_interval_seconds=args.decision_interval_seconds,
        max_steps_per_episode=args.max_steps_per_episode,
    )
    config = PPOTrainingConfig(
        total_timesteps=total_timesteps,
        learning_rate=args.learning_rate,
        n_steps=args.n_steps,
        batch_size=args.batch_size,
        n_epochs=args.n_epochs,
        gamma=args.gamma,
        gae_lambda=args.gae_lambda,
        clip_range=args.clip_range,
        ent_coef=args.ent_coef,
        vf_coef=args.vf_coef,
        max_grad_norm=args.max_grad_norm,
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
            controller_provenance="ppo",
        )

    print("Starting SMARTFLOW PPO offline training")
    print(f"Scenario: {json.dumps(scenario, sort_keys=True)}")
    print(f"Episodes: {args.episodes}, seeds: {args.seeds}")
    print(f"Timesteps: {total_timesteps}")
    if args.resume_model:
        print(f"Resuming PPO model from: {args.resume_model}")
    if args.checkpoint_every > 0:
        print(f"Checkpoint every {args.checkpoint_every} completed episode(s).")
    print("Progress: waiting for episode 1 to finish...")

    progress_events: list[PPOProgressEvent] = []
    training_started_at = perf_counter()
    output_path = args.output or _default_output_path()
    model_id = None
    if not args.skip_db:
        model_id = _create_model_record(
            model_name=f"PPO {scenario['intersection_id']} {output_path.stem}",
            output_path=output_path,
            scenario=scenario,
            seed_set=args.seeds,
            best_score=None,
        )

    def print_progress(event: PPOProgressEvent):
        progress_events.append(event)
        elapsed_seconds = perf_counter() - training_started_at
        progress_ratio = event.timesteps_finished / max(total_timesteps, 1)
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

    def record_checkpoint(event: PPOCheckpointEvent):
        _save_db_checkpoint(
            model_id=model_id,
            episode=event.episodes_finished,
            reward=event.reward,
            path=event.model_path,
        )
        print(f"Saved PPO checkpoint: {event.model_path}", flush=True)

    try:
        saved_path, metadata_path = train_ppo(
            env_factory=env_factory,
            config=config,
            output_path=output_path,
            metadata={
                "scenario": scenario,
                "seed_set": list(args.seeds),
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
    except PPOTrainingInterrupted as exc:
        print("Interrupt signal received. Saved partial PPO training artifact.")
        saved_path = exc.saved_path
        metadata_path = exc.metadata_path
        final_event = progress_events[-1] if progress_events else None
        if final_event is not None:
            _save_db_checkpoint(
                model_id=model_id,
                episode=final_event.episodes_finished,
                reward=final_event.last_episode_reward,
                path=saved_path,
            )
        print(f"Saved partial PPO model artifact: {saved_path}")
        print(f"Saved partial PPO metadata: {metadata_path}")
        if model_id is not None:
            print(f"Registered rl_models.id: {model_id}")
        return 130

    final_event = progress_events[-1] if progress_events else None
    if final_event is not None:
        _save_db_checkpoint(
            model_id=model_id,
            episode=final_event.episodes_finished,
            reward=final_event.last_episode_reward,
            path=saved_path,
        )

    print(f"Saved PPO model artifact: {saved_path}")
    print(f"Saved PPO metadata: {metadata_path}")
    if model_id is not None:
        print(f"Registered rl_models.id: {model_id}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
