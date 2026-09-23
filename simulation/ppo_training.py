from __future__ import annotations

from .model_contract import native_contract, validate_neural_artifact

import json
import statistics
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Callable

try:
    from stable_baselines3 import PPO
    from stable_baselines3.common.callbacks import BaseCallback
except ImportError:  # pragma: no cover - exercised when the local venv lacks the RL stack
    PPO = None
    BaseCallback = None


OBSERVATION_VERSION = "obs_v1"
REWARD_VERSION = "reward_v1"
ACTION_SPACE_VERSION = "action_v1"


@dataclass(frozen=True)
class PPOTrainingConfig:
    total_timesteps: int
    learning_rate: float = 3e-4
    n_steps: int = 128
    batch_size: int = 64
    n_epochs: int = 10
    gamma: float = 0.99
    gae_lambda: float = 0.95
    clip_range: float = 0.2
    ent_coef: float = 0.0
    vf_coef: float = 0.5
    max_grad_norm: float = 0.5
    seed: int = 42


@dataclass(frozen=True)
class PPOProgressEvent:
    episodes_finished: int
    timesteps_finished: int
    total_timesteps: int
    last_episode_reward: float
    last_episode_length: int


@dataclass(frozen=True)
class PPOCheckpointEvent:
    episodes_finished: int
    reward: float
    model_path: Path
    metadata_path: Path


class PPOTrainingInterrupted(Exception):
    def __init__(self, saved_path: Path, metadata_path: Path):
        super().__init__("PPO training interrupted after saving partial artifact.")
        self.saved_path = saved_path
        self.metadata_path = metadata_path


def calculate_ppo_timesteps(
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


def require_ppo_dependencies():
    if PPO is None or BaseCallback is None:
        raise RuntimeError(
            "PPO training requires stable-baselines3, gymnasium, and torch. "
            "Install the locked requirements first: .venv\\Scripts\\python.exe -m pip install -r requirements.txt"
        )


class PPOProgressCallback(BaseCallback if BaseCallback is not None else object):
    def __init__(self, on_episode_complete: Callable[[PPOProgressEvent], None] | None = None):
        if BaseCallback is not None:
            super().__init__()
        self.on_episode_complete = on_episode_complete
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
                    PPOProgressEvent(
                        episodes_finished=self.episodes_finished,
                        timesteps_finished=int(getattr(self, "num_timesteps", 0) or 0),
                        total_timesteps=int(getattr(self.model, "_total_timesteps", 0) or 0),
                        last_episode_reward=round(self._episode_reward, 6),
                        last_episode_length=self._episode_length,
                    )
                )
            self._episode_reward = 0.0
            self._episode_length = 0
        return True


def build_ppo_model(env, config: PPOTrainingConfig):
    require_ppo_dependencies()
    return PPO(
        "MlpPolicy",
        env,
        learning_rate=config.learning_rate,
        n_steps=config.n_steps,
        batch_size=config.batch_size,
        n_epochs=config.n_epochs,
        gamma=config.gamma,
        gae_lambda=config.gae_lambda,
        clip_range=config.clip_range,
        ent_coef=config.ent_coef,
        vf_coef=config.vf_coef,
        max_grad_norm=config.max_grad_norm,
        policy_kwargs={"net_arch": [128, 128]},
        seed=config.seed,
        verbose=0,
    )


def train_ppo(
    *,
    env_factory,
    config: PPOTrainingConfig,
    output_path: str | Path,
    metadata: dict | None = None,
    resume_model_path: str | Path | None = None,
    checkpoint_every_episodes: int = 0,
    checkpoint_dir: str | Path | None = None,
    on_checkpoint: Callable[[PPOCheckpointEvent], None] | None = None,
    on_episode_complete: Callable[[PPOProgressEvent], None] | None = None,
) -> tuple[Path, Path]:
    require_ppo_dependencies()
    env = env_factory()
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    progress_events: list[PPOProgressEvent] = []
    checkpoint_dir_path = Path(checkpoint_dir) if checkpoint_dir else output_path.parent / "checkpoints"
    checkpoint_every_episodes = max(int(checkpoint_every_episodes or 0), 0)

    def build_metadata_payload(*, status: str) -> dict:
        episode_rewards = [event.last_episode_reward for event in progress_events]
        return {
            "created_at": datetime.now(UTC).isoformat(),
            "algorithm": "ppo",
            "implementation": "stable-baselines3.PPO",
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

    def record_progress(event: PPOProgressEvent):
        progress_events.append(event)
        if on_episode_complete:
            on_episode_complete(event)
        if checkpoint_every_episodes and event.episodes_finished % checkpoint_every_episodes == 0:
            checkpoint_path = checkpoint_dir_path / f"{output_path.stem}_ep{event.episodes_finished:04d}.zip"
            saved_checkpoint_path, saved_metadata_path = save_artifact(model, checkpoint_path, status="checkpoint")
            if on_checkpoint:
                on_checkpoint(
                    PPOCheckpointEvent(
                        episodes_finished=event.episodes_finished,
                        reward=event.last_episode_reward,
                        model_path=saved_checkpoint_path,
                        metadata_path=saved_metadata_path,
                    )
                )

    try:
        if resume_model_path:
            validate_neural_artifact(resume_model_path)
            model = PPO.load(str(resume_model_path), env=env)
        else:
            model = build_ppo_model(env, config)
        try:
            model.learn(
                total_timesteps=config.total_timesteps,
                callback=PPOProgressCallback(record_progress),
                progress_bar=False,
                reset_num_timesteps=not bool(resume_model_path),
            )
        except KeyboardInterrupt as exc:
            saved_path, saved_metadata_path = save_artifact(model, output_path, status="interrupted")
            raise PPOTrainingInterrupted(saved_path, saved_metadata_path) from exc
        return save_artifact(model, output_path, status="completed")
    finally:
        close = getattr(env, "close", None)
        if callable(close):
            close()
