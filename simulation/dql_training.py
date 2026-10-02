from __future__ import annotations

from .model_contract import native_contract, validate_neural_artifact

import json
import statistics
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Callable

try:
    from stable_baselines3 import DQN
    from stable_baselines3.common.callbacks import BaseCallback
except ImportError:  # pragma: no cover - exercised when the local venv lacks the RL stack
    DQN = None
    BaseCallback = None


OBSERVATION_VERSION = "obs_v1"
REWARD_VERSION = "reward_v1"
ACTION_SPACE_VERSION = "action_v1"


@dataclass(frozen=True)
class DQLTrainingConfig:
    total_timesteps: int
    learning_rate: float = 1e-4
    buffer_size: int = 50_000
    learning_starts: int = 100
    batch_size: int = 32
    gamma: float = 0.99
    train_freq: int = 1
    gradient_steps: int = 1
    target_update_interval: int = 250
    exploration_fraction: float = 0.2
    exploration_initial_eps: float = 1.0
    exploration_final_eps: float = 0.05
    seed: int = 42


@dataclass(frozen=True)
class DQLProgressEvent:
    episodes_finished: int
    timesteps_finished: int
    total_timesteps: int
    last_episode_reward: float
    last_episode_length: int


@dataclass(frozen=True)
class DQLCheckpointEvent:
    episodes_finished: int
    reward: float
    epsilon: float
    model_path: Path
    metadata_path: Path


class DQLTrainingInterrupted(Exception):
    def __init__(self, saved_path: Path, metadata_path: Path):
        super().__init__("DQL training interrupted after saving partial artifact.")
        self.saved_path = saved_path
        self.metadata_path = metadata_path


def calculate_dql_timesteps(
    *,
    episodes: int,
    evaluation_seconds: float,
    decision_interval_seconds: float,
    max_steps_per_episode: int | None = None,
) -> int:
    if episodes <= 0:
        raise ValueError("episodes must be greater than 0.")
    if max_steps_per_episode is not None:
        steps_per_episode = max(int(max_steps_per_episode), 1)
    else:
        steps_per_episode = max(
            int(round(float(evaluation_seconds) / max(float(decision_interval_seconds), 0.1))) + 1,
            1,
        )
    return int(episodes) * steps_per_episode


def require_dql_dependencies():
    if DQN is None or BaseCallback is None:
        raise RuntimeError(
            "DQL training requires stable-baselines3, gymnasium, and torch. "
            "Install the locked requirements first: .venv\\Scripts\\python.exe -m pip install -r requirements.txt"
        )


class DQLProgressCallback(BaseCallback if BaseCallback is not None else object):
    def __init__(self, on_episode_complete: Callable[[DQLProgressEvent], None] | None = None, *, starting_timesteps: int = 0):
        if BaseCallback is not None:
            super().__init__()
        self.on_episode_complete = on_episode_complete
        self.starting_timesteps = starting_timesteps
        self.episodes_finished = 0
        self._episode_reward = 0.0
        self._episode_length = 0

    def _on_step(self) -> bool:
        rewards = self.locals.get("rewards", []) if hasattr(self, "locals") else []
        dones = self.locals.get("dones", []) if hasattr(self, "locals") else []
        if rewards:
            self._episode_reward += float(rewards[0])
            self._episode_length += 1
        if dones and bool(dones[0]):
            self.episodes_finished += 1
            if self.on_episode_complete:
                self.on_episode_complete(
                    DQLProgressEvent(
                        episodes_finished=self.episodes_finished,
                        timesteps_finished=max(0, int(getattr(self, "num_timesteps", 0) or 0) - self.starting_timesteps),
                        total_timesteps=max(0, int(getattr(self.model, "_total_timesteps", 0) or 0) - self.starting_timesteps),
                        last_episode_reward=round(self._episode_reward, 6),
                        last_episode_length=self._episode_length,
                    )
                )
            self._episode_reward = 0.0
            self._episode_length = 0
        return True


def build_dql_model(env, config: DQLTrainingConfig):
    require_dql_dependencies()
    return DQN(
        "MlpPolicy",
        env,
        learning_rate=config.learning_rate,
        buffer_size=config.buffer_size,
        learning_starts=config.learning_starts,
        batch_size=config.batch_size,
        gamma=config.gamma,
        train_freq=config.train_freq,
        gradient_steps=config.gradient_steps,
        target_update_interval=config.target_update_interval,
        exploration_fraction=config.exploration_fraction,
        exploration_initial_eps=config.exploration_initial_eps,
        exploration_final_eps=config.exploration_final_eps,
        policy_kwargs={"net_arch": [128, 128]},
        seed=config.seed,
        verbose=0,
    )


def train_deep_q_learning(
    *,
    env_factory,
    config: DQLTrainingConfig,
    output_path: str | Path,
    metadata: dict | None = None,
    resume_model_path: str | Path | None = None,
    checkpoint_every_episodes: int = 0,
    checkpoint_dir: str | Path | None = None,
    on_checkpoint: Callable[[DQLCheckpointEvent], None] | None = None,
    on_episode_complete: Callable[[DQLProgressEvent], None] | None = None,
) -> tuple[Path, Path]:
    require_dql_dependencies()
    env = env_factory()
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    metadata_path = output_path.with_suffix(".metadata.json")
    progress_events: list[DQLProgressEvent] = []
    checkpoint_dir_path = Path(checkpoint_dir) if checkpoint_dir else output_path.parent / "checkpoints"
    checkpoint_every_episodes = max(int(checkpoint_every_episodes or 0), 0)

    def build_metadata_payload(*, status: str) -> dict:
        episode_rewards = [event.last_episode_reward for event in progress_events]
        return {
            "created_at": datetime.now(UTC).isoformat(),
            "algorithm": "dql",
            "implementation": "stable-baselines3.DQN",
            "config": asdict(config),
            "resumed_from": str(resume_model_path) if resume_model_path else None,
            "progress_events": [asdict(event) for event in progress_events],
            "best_training_reward": round(max(episode_rewards), 6) if episode_rewards else None,
            "final_training_reward": round(episode_rewards[-1], 6) if episode_rewards else None,
            "last_10_avg_training_reward": (
                round(statistics.fmean(episode_rewards[-10:]), 6)
                if episode_rewards
                else None
            ),
            "training_status": status,
            "observation_version": OBSERVATION_VERSION,
            "reward_version": REWARD_VERSION,
            "action_space_version": ACTION_SPACE_VERSION,
            **(metadata or {}),
            "native_contract": native_contract(),
        }

    def save_artifact(model, path: Path, *, status: str) -> tuple[Path, Path]:
        path.parent.mkdir(parents=True, exist_ok=True)
        model.save(path)
        saved_path = path.with_suffix(".zip")
        saved_metadata_path = saved_path.with_suffix(".metadata.json")
        saved_metadata_path.write_text(
            json.dumps(build_metadata_payload(status=status), indent=2),
            encoding="utf-8",
        )
        return saved_path, saved_metadata_path

    def record_progress(event: DQLProgressEvent):
        progress_events.append(event)
        if on_episode_complete:
            on_episode_complete(event)
        if checkpoint_every_episodes and event.episodes_finished % checkpoint_every_episodes == 0:
            checkpoint_path = checkpoint_dir_path / f"{output_path.stem}_ep{event.episodes_finished:04d}.zip"
            saved_checkpoint_path, saved_metadata_path = save_artifact(model, checkpoint_path, status="checkpoint")
            if on_checkpoint:
                on_checkpoint(
                    DQLCheckpointEvent(
                        episodes_finished=event.episodes_finished,
                        reward=event.last_episode_reward,
                        epsilon=float(getattr(model, "exploration_rate", 0.0) or 0.0),
                        model_path=saved_checkpoint_path,
                        metadata_path=saved_metadata_path,
                    )
                )

    try:
        if resume_model_path:
            validate_neural_artifact(resume_model_path)
            model = DQN.load(str(resume_model_path), env=env)
        else:
            model = build_dql_model(env, config)
        try:
            model.learn(
                total_timesteps=config.total_timesteps,
                callback=DQLProgressCallback(record_progress, starting_timesteps=int(model.num_timesteps)),
                progress_bar=False,
                reset_num_timesteps=not bool(resume_model_path),
            )
        except KeyboardInterrupt as exc:
            saved_path, saved_metadata_path = save_artifact(model, output_path, status="interrupted")
            raise DQLTrainingInterrupted(saved_path, saved_metadata_path) from exc
        return save_artifact(model, output_path, status="completed")
    finally:
        close = getattr(env, "close", None)
        if callable(close):
            close()
