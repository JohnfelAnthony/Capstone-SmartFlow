from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Callable

from .ql_agent import TabularQLearningAgent


@dataclass(frozen=True)
class QLEpisodeResult:
    episode: int
    seed: int
    total_reward: float
    steps: int
    epsilon: float
    q_table_size: int
    terminated: bool
    truncated: bool

    def to_dict(self) -> dict:
        return asdict(self)


def _require_ql_state(info: dict, source: str) -> tuple[int, ...]:
    if "ql_state" not in info:
        raise KeyError(f"{source} info payload must include 'ql_state'.")
    return tuple(int(part) for part in info["ql_state"])


def train_tabular_q_learning(
    *,
    env_factory: Callable[[], object],
    agent: TabularQLearningAgent,
    episodes: int,
    seed_set: tuple[int, ...],
    max_steps_per_episode: int | None = None,
    starting_episode: int = 0,
    on_episode_complete: Callable[[QLEpisodeResult], None] | None = None,
) -> list[QLEpisodeResult]:
    if episodes <= 0:
        raise ValueError("episodes must be positive.")
    if not seed_set:
        raise ValueError("seed_set must not be empty.")

    results: list[QLEpisodeResult] = []

    for local_episode_index in range(episodes):
        episode_index = int(starting_episode) + local_episode_index
        seed = int(seed_set[episode_index % len(seed_set)])
        env = env_factory()
        total_reward = 0.0
        steps = 0
        terminated = False
        truncated = False

        try:
            _observation, reset_info = env.reset(seed=seed)
            state = _require_ql_state(reset_info, "reset")
            valid_action_mask = tuple(reset_info.get("valid_action_mask", ()))

            while True:
                action = agent.choose_action(
                    state,
                    valid_action_mask=valid_action_mask,
                    training=True,
                )
                _next_observation, reward, terminated, truncated, step_info = env.step(action)
                next_state = _require_ql_state(step_info, "step")
                next_valid_action_mask = tuple(step_info.get("valid_action_mask", ()))

                agent.update(
                    state,
                    action,
                    float(reward),
                    next_state,
                    next_valid_action_mask=next_valid_action_mask,
                    terminated=terminated,
                )

                total_reward += float(reward)
                steps += 1
                state = next_state
                valid_action_mask = next_valid_action_mask

                reached_step_limit = (
                    max_steps_per_episode is not None
                    and steps >= int(max_steps_per_episode)
                )
                if terminated or truncated or reached_step_limit:
                    break
        finally:
            close = getattr(env, "close", None)
            if callable(close):
                close()

        epsilon = agent.decay_epsilon()
        result = QLEpisodeResult(
            episode=episode_index + 1,
            seed=seed,
            total_reward=round(total_reward, 6),
            steps=steps,
            epsilon=round(epsilon, 8),
            q_table_size=agent.state_count,
            terminated=bool(terminated),
            truncated=bool(truncated),
        )
        results.append(result)
        if on_episode_complete is not None:
            on_episode_complete(result)

    return results
