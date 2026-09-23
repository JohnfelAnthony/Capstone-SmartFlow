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

from simulation.ql_agent import QLearningConfig, TabularQLearningAgent
from simulation.ql_training import QLEpisodeResult, train_tabular_q_learning
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
    return ROOT / "data" / "models" / "ql" / f"ql_{timestamp}.json"


def _checkpoint_path(output_path: Path, episode: int) -> Path:
    return output_path.parent / "checkpoints" / f"{output_path.stem}_ep{int(episode):04d}.json"


def _format_duration(seconds: float) -> str:
    seconds = max(float(seconds or 0), 0.0)
    minutes, remaining_seconds = divmod(int(round(seconds)), 60)
    hours, minutes = divmod(minutes, 60)
    if hours:
        return f"{hours}h {minutes:02d}m {remaining_seconds:02d}s"
    if minutes:
        return f"{minutes}m {remaining_seconds:02d}s"
    return f"{remaining_seconds}s"


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Train the SMARTFLOW tabular Q-learning baseline offline."
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
    parser.add_argument("--scenario-name", default="SMARTFLOW QL Training Scenario")
    parser.add_argument("--traffic-density", default="medium")
    parser.add_argument("--pedestrian-density", default="medium")
    parser.add_argument("--emergency-mode", default="disabled")
    parser.add_argument("--road-constraint", default="None")
    parser.add_argument("--alpha", type=float, default=0.1)
    parser.add_argument("--gamma", type=float, default=0.9)
    parser.add_argument("--epsilon", type=float, default=0.2)
    parser.add_argument("--min-epsilon", type=float, default=0.05)
    parser.add_argument("--epsilon-decay", type=float, default=0.995)
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
    best_score: float | None = None,
) -> int | None:
    try:
        import database

        database.init_db()
        model_id = database.create_rl_model(
            name=model_name,
            algorithm="ql",
            version="1.0",
            checkpoint_path=str(output_path),
            intersection_support=[scenario["intersection_id"]],
            training_scenarios=[scenario],
            observation_version="obs_v1",
            reward_version="reward_v1",
            action_space_version="action_v1",
            seed_set=list(seed_set),
            training_date=datetime.now(UTC).isoformat(),
            best_evaluation_score=best_score,
        )
        return int(model_id)
    except Exception as exc:
        print(f"Warning: QL DB model registration failed: {exc}")
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
        print(f"Warning: QL DB checkpoint failed: {exc}")


def _load_resume_artifact(path: Path) -> tuple[TabularQLearningAgent, list[dict]]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    agent = TabularQLearningAgent.from_artifact(payload)
    metadata = payload.get("metadata", {}) if isinstance(payload, dict) else {}
    previous_episodes = list(metadata.get("episodes", []) or [])
    return agent, previous_episodes


def _build_metadata(
    *,
    scenario: dict,
    seed_set: tuple[int, ...],
    episodes: list[dict],
    status: str,
    resume_model: Path | None = None,
) -> dict:
    rewards = [
        float(episode["total_reward"])
        for episode in episodes
        if episode.get("total_reward") is not None
    ]
    metadata = {
        "created_at": datetime.now(UTC).isoformat(),
        "scenario": scenario,
        "seed_set": list(seed_set),
        "action_labels": list(RL_SERVICE_ACTIONS),
        "observation_version": "obs_v1",
        "reward_version": "reward_v1",
        "action_space_version": "action_v1",
        "episodes": episodes,
        "best_training_reward": max(rewards) if rewards else None,
        "final_training_reward": rewards[-1] if rewards else None,
        "last_10_avg_training_reward": (
            round(sum(rewards[-10:]) / len(rewards[-10:]), 6)
            if rewards
            else None
        ),
        "training_status": status,
    }
    if resume_model is not None:
        metadata["resumed_from"] = str(resume_model)
    return metadata


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

    config = QLearningConfig(
        alpha=args.alpha,
        gamma=args.gamma,
        epsilon=args.epsilon,
        min_epsilon=args.min_epsilon,
        epsilon_decay=args.epsilon_decay,
        seed=args.agent_seed,
    )
    previous_episodes: list[dict] = []
    if args.resume_model:
        agent, previous_episodes = _load_resume_artifact(args.resume_model)
        if agent.action_count != len(RL_SERVICE_ACTIONS):
            raise SystemExit(
                f"Resume model action count {agent.action_count} does not match current action count {len(RL_SERVICE_ACTIONS)}."
            )
    else:
        agent = TabularQLearningAgent(
            action_count=len(RL_SERVICE_ACTIONS),
            config=config,
        )

    def env_factory():
        return SmartFlowRLEnv(
            scenario=scenario,
            seed=args.seeds[0],
            warmup_seconds=args.warmup_seconds,
            evaluation_seconds=args.evaluation_seconds,
            decision_interval_seconds=args.decision_interval_seconds,
            minimum_green_hold_seconds=args.minimum_green_hold_seconds,
            controller_provenance="ql",
        )

    print("Starting SMARTFLOW QL offline training")
    print(f"Scenario: {json.dumps(scenario, sort_keys=True)}")
    output_path = args.output or _default_output_path()
    completed_before_resume = len(previous_episodes)
    target_episode_total = completed_before_resume + args.episodes
    print(f"Episodes: {args.episodes}, seeds: {args.seeds}")
    if args.resume_model:
        print(
            f"Resuming from {args.resume_model} with {completed_before_resume} completed episodes; "
            f"new target is episode {target_episode_total}."
        )
    if args.checkpoint_every > 0:
        print(f"Checkpoint every {args.checkpoint_every} completed episode(s).")
    print("Progress: waiting for episode 1 to finish...")

    training_started_at = perf_counter()
    completed_results: list[QLEpisodeResult] = []
    model_id = None
    if not args.skip_db:
        model_id = _create_model_record(
            model_name=f"QL {scenario['intersection_id']} {output_path.stem}",
            output_path=output_path,
            scenario=scenario,
            seed_set=args.seeds,
        )

    def save_training_artifact(*, status: str, path: Path | None = None) -> Path:
        artifact_path = path or output_path
        all_episode_dicts = previous_episodes + [result.to_dict() for result in completed_results]
        metadata = _build_metadata(
            scenario=scenario,
            seed_set=args.seeds,
            episodes=all_episode_dicts,
            status=status,
            resume_model=args.resume_model,
        )
        return agent.save(artifact_path, metadata=metadata)

    def print_progress(result: QLEpisodeResult):
        completed_results.append(result)
        elapsed_seconds = perf_counter() - training_started_at
        progress_ratio = (result.episode - completed_before_resume) / max(args.episodes, 1)
        estimated_total_seconds = elapsed_seconds / progress_ratio if progress_ratio > 0 else 0.0
        remaining_seconds = max(estimated_total_seconds - elapsed_seconds, 0.0)
        print(
            "[{episode}/{total} | {percent:5.1f}%] seed={seed} steps={steps} "
            "reward={reward:.6f} epsilon={epsilon:.6f} states={states} "
            "elapsed={elapsed} eta={eta}".format(
                episode=result.episode,
                total=target_episode_total,
                percent=progress_ratio * 100,
                seed=result.seed,
                steps=result.steps,
                reward=result.total_reward,
                epsilon=result.epsilon,
                states=result.q_table_size,
                elapsed=_format_duration(elapsed_seconds),
                eta=_format_duration(remaining_seconds),
            ),
            flush=True,
        )
        if args.checkpoint_every > 0 and result.episode % int(args.checkpoint_every) == 0:
            checkpoint_path = save_training_artifact(
                status="checkpoint",
                path=_checkpoint_path(output_path, result.episode),
            )
            _save_db_checkpoint(
                model_id=model_id,
                episode=result.episode,
                reward=result.total_reward,
                epsilon=result.epsilon,
                path=checkpoint_path,
            )
            print(f"Saved QL checkpoint: {checkpoint_path}", flush=True)

    try:
        train_tabular_q_learning(
            env_factory=env_factory,
            agent=agent,
            episodes=args.episodes,
            seed_set=args.seeds,
            max_steps_per_episode=args.max_steps_per_episode,
            starting_episode=completed_before_resume,
            on_episode_complete=print_progress,
        )
    except KeyboardInterrupt:
        print("Interrupt signal received. Saving partial QL training artifact.")
        saved_path = save_training_artifact(status="interrupted")
        if completed_results:
            final_result = completed_results[-1]
            _save_db_checkpoint(
                model_id=model_id,
                episode=final_result.episode,
                reward=final_result.total_reward,
                epsilon=final_result.epsilon,
                path=saved_path,
            )
        print(f"Saved partial QL model artifact: {saved_path}")
        if model_id is not None:
            print(f"Registered rl_models.id: {model_id}")
        return 130

    saved_path = save_training_artifact(status="completed")
    if completed_results:
        final_result = completed_results[-1]
        _save_db_checkpoint(
            model_id=model_id,
            episode=final_result.episode,
            reward=final_result.total_reward,
            epsilon=final_result.epsilon,
            path=saved_path,
        )

    print(f"Saved QL model artifact: {saved_path}")
    if model_id is not None:
        print(f"Registered rl_models.id: {model_id}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
