from __future__ import annotations

import json
import random
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Iterable


StateKey = tuple[int, ...]


@dataclass(frozen=True)
class QLearningConfig:
    alpha: float = 0.1
    gamma: float = 0.9
    epsilon: float = 0.2
    min_epsilon: float = 0.05
    epsilon_decay: float = 0.995
    seed: int = 42


@dataclass(frozen=True)
class QLearningUpdate:
    old_value: float
    new_value: float
    target: float
    td_error: float


class TabularQLearningAgent:
    def __init__(
        self,
        *,
        action_count: int,
        config: QLearningConfig | None = None,
        q_table: dict[StateKey, list[float]] | None = None,
    ):
        if action_count <= 0:
            raise ValueError("action_count must be positive.")

        self.action_count = int(action_count)
        self.config = config or QLearningConfig()
        self.epsilon = float(self.config.epsilon)
        self._rng = random.Random(self.config.seed)
        self.q_table: dict[StateKey, list[float]] = {}
        if q_table:
            for state, values in q_table.items():
                self.q_table[tuple(int(part) for part in state)] = self._normalized_values(values)

    def _normalized_values(self, values: Iterable[float]) -> list[float]:
        normalized = [float(value) for value in values]
        if len(normalized) != self.action_count:
            raise ValueError(
                f"Q-value row has {len(normalized)} actions; expected {self.action_count}."
            )
        return normalized

    def _state_key(self, state: Iterable[int]) -> StateKey:
        return tuple(int(part) for part in state)

    def _valid_action_indices(self, valid_action_mask: Iterable[int] | None = None) -> list[int]:
        if valid_action_mask is None:
            return list(range(self.action_count))

        valid_actions = [
            index
            for index, is_valid in enumerate(valid_action_mask)
            if index < self.action_count and int(is_valid) == 1
        ]
        return valid_actions or list(range(self.action_count))

    def get_q_values(self, state: Iterable[int]) -> list[float]:
        state_key = self._state_key(state)
        if state_key not in self.q_table:
            self.q_table[state_key] = [0.0 for _ in range(self.action_count)]
        return self.q_table[state_key]

    def choose_action(
        self,
        state: Iterable[int],
        *,
        valid_action_mask: Iterable[int] | None = None,
        training: bool = True,
    ) -> int:
        valid_actions = self._valid_action_indices(valid_action_mask)
        if training and self._rng.random() < self.epsilon:
            return int(self._rng.choice(valid_actions))

        q_values = self.get_q_values(state)
        best_action = max(valid_actions, key=lambda action_index: q_values[action_index])
        return int(best_action)

    def update(
        self,
        state: Iterable[int],
        action: int,
        reward: float,
        next_state: Iterable[int],
        *,
        next_valid_action_mask: Iterable[int] | None = None,
        terminated: bool = False,
    ) -> QLearningUpdate:
        action_index = int(action)
        if action_index < 0 or action_index >= self.action_count:
            raise ValueError(f"Action index out of range: {action_index}")

        q_values = self.get_q_values(state)
        next_q_values = self.get_q_values(next_state)
        next_valid_actions = self._valid_action_indices(next_valid_action_mask)
        best_future_q = 0.0 if terminated else max(next_q_values[next_action] for next_action in next_valid_actions)

        old_value = q_values[action_index]
        target = float(reward) + self.config.gamma * best_future_q
        td_error = target - old_value
        new_value = old_value + self.config.alpha * td_error
        q_values[action_index] = new_value

        return QLearningUpdate(
            old_value=round(old_value, 6),
            new_value=round(new_value, 6),
            target=round(target, 6),
            td_error=round(td_error, 6),
        )

    def decay_epsilon(self) -> float:
        self.epsilon = max(self.config.min_epsilon, self.epsilon * self.config.epsilon_decay)
        return self.epsilon

    def to_artifact(self, *, metadata: dict | None = None) -> dict:
        from .model_contract import native_contract
        return {
            "algorithm": "ql",
            "artifact_type": "tabular_q_table",
            "action_count": self.action_count,
            "config": asdict(self.config),
            "epsilon": round(float(self.epsilon), 8),
            "metadata": {**(metadata or {}), "native_contract": native_contract()},
            "q_table": [
                {
                    "state": list(state),
                    "values": [round(value, 8) for value in values],
                }
                for state, values in sorted(self.q_table.items())
            ],
        }

    @classmethod
    def from_artifact(cls, payload: dict) -> "TabularQLearningAgent":
        q_table = {
            tuple(int(part) for part in row["state"]): [float(value) for value in row["values"]]
            for row in payload.get("q_table", [])
        }
        config_payload = payload.get("config") or {}
        agent = cls(
            action_count=int(payload["action_count"]),
            config=QLearningConfig(**config_payload),
            q_table=q_table,
        )
        agent.epsilon = float(payload.get("epsilon", agent.config.epsilon))
        return agent

    def save(self, path: str | Path, *, metadata: dict | None = None) -> Path:
        output_path = Path(path)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(
            json.dumps(self.to_artifact(metadata=metadata), indent=2, sort_keys=True),
            encoding="utf-8",
        )
        return output_path

    @classmethod
    def load(cls, path: str | Path) -> "TabularQLearningAgent":
        payload = json.loads(Path(path).read_text(encoding="utf-8"))
        from .model_contract import validate_metadata
        validate_metadata(payload.get("metadata", {}))
        return cls.from_artifact(payload)

    @property
    def state_count(self) -> int:
        return len(self.q_table)
