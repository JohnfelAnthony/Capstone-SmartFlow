from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Protocol

from .ql_agent import TabularQLearningAgent
from .sumo_engine import RL_SERVICE_ACTIONS

try:
    from stable_baselines3 import DQN, PPO
except ImportError:  # pragma: no cover - optional until the neural stack is installed
    DQN = None
    PPO = None


@dataclass(frozen=True)
class PolicyPrediction:
    action: int
    action_name: str
    controller_provenance: str
    q_values: tuple[float, ...] = ()
    state_known: bool = False


class RuntimePolicy(Protocol):
    controller_provenance: str

    def predict(self, observation=None, info: dict | None = None) -> PolicyPrediction:
        ...


def _coerce_state(raw_state: Iterable[int] | None) -> tuple[int, ...]:
    if raw_state is None:
        raise KeyError("QL runtime policy requires info['ql_state'].")
    return tuple(int(part) for part in raw_state)


def _coerce_valid_action_mask(raw_mask: Iterable[int] | None) -> tuple[int, ...] | None:
    if raw_mask is None:
        return None
    return tuple(int(part) for part in raw_mask)


class QLRuntimePolicy:
    controller_provenance = "ql"

    def __init__(self, agent: TabularQLearningAgent):
        if agent.action_count != len(RL_SERVICE_ACTIONS):
            raise ValueError(
                f"QL policy action_count={agent.action_count}; expected {len(RL_SERVICE_ACTIONS)}."
            )
        self.agent = agent
        self.agent.epsilon = 0.0

    @classmethod
    def load(cls, model_path: str | Path) -> "QLRuntimePolicy":
        return cls(TabularQLearningAgent.load(model_path))

    def predict(self, observation=None, info: dict | None = None) -> PolicyPrediction:
        info = info or {}
        state = _coerce_state(info.get("ql_state"))
        valid_action_mask = _coerce_valid_action_mask(info.get("valid_action_mask"))
        state_known = state in self.agent.q_table
        action = self.agent.choose_action(
            state,
            valid_action_mask=valid_action_mask,
            training=False,
        )
        q_values = tuple(round(value, 8) for value in self.agent.get_q_values(state))
        return PolicyPrediction(
            action=action,
            action_name=RL_SERVICE_ACTIONS[action],
            controller_provenance=self.controller_provenance,
            q_values=q_values,
            state_known=state_known,
        )


def _first_valid_action(valid_action_mask: tuple[int, ...] | None) -> int:
    if not valid_action_mask:
        return 0
    for index, is_valid in enumerate(valid_action_mask):
        if int(is_valid):
            return index
    return 0


def _masked_argmax(values: Iterable[float], valid_action_mask: tuple[int, ...] | None = None) -> int:
    q_values = tuple(float(value) for value in values)
    if not q_values:
        return _first_valid_action(valid_action_mask)

    best_action = None
    best_value = None
    for index, value in enumerate(q_values):
        if valid_action_mask is not None and (index >= len(valid_action_mask) or not valid_action_mask[index]):
            continue
        if best_value is None or value > best_value:
            best_action = index
            best_value = value
    if best_action is None:
        return _first_valid_action(valid_action_mask)
    return int(best_action)


def _extract_dql_q_values(model, observation) -> tuple[float, ...]:
    if hasattr(model, "predict_q_values"):
        return tuple(float(value) for value in model.predict_q_values(observation))

    try:
        import numpy as np
        import torch
    except ImportError:
        return ()

    if observation is None or not hasattr(model, "q_net"):
        return ()

    try:
        observation_array = np.asarray(observation, dtype=np.float32)
        if observation_array.ndim == 1:
            observation_array = observation_array.reshape(1, -1)
        observation_tensor = torch.as_tensor(observation_array, device=model.device)
        with torch.no_grad():
            q_values = model.q_net(observation_tensor)
        return tuple(float(value) for value in q_values.detach().cpu().numpy()[0])
    except Exception:
        return ()


class DQLRuntimePolicy:
    controller_provenance = "dql"

    def __init__(self, model):
        self.model = model

    @classmethod
    def load(cls, model_path: str | Path) -> "DQLRuntimePolicy":
        if DQN is None:
            raise RuntimeError(
                "DQL runtime requires stable-baselines3 and torch. "
                "Install the locked requirements first: .venv\\Scripts\\python.exe -m pip install -r requirements.txt"
            )
        return cls(DQN.load(str(model_path)))

    def predict(self, observation=None, info: dict | None = None) -> PolicyPrediction:
        info = info or {}
        valid_action_mask = _coerce_valid_action_mask(info.get("valid_action_mask"))
        q_values = tuple(round(value, 8) for value in _extract_dql_q_values(self.model, observation))
        if q_values:
            action = _masked_argmax(q_values, valid_action_mask)
        else:
            raw_action, _ = self.model.predict(observation, deterministic=True)
            if hasattr(raw_action, "item"):
                action = int(raw_action.item())
            elif isinstance(raw_action, (list, tuple)):
                action = int(raw_action[0])
            else:
                action = int(raw_action)
            if valid_action_mask is not None and (
                action >= len(valid_action_mask) or not valid_action_mask[action]
            ):
                action = _first_valid_action(valid_action_mask)

        if action < 0 or action >= len(RL_SERVICE_ACTIONS):
            action = _first_valid_action(valid_action_mask)

        return PolicyPrediction(
            action=action,
            action_name=RL_SERVICE_ACTIONS[action],
            controller_provenance=self.controller_provenance,
            q_values=q_values,
            state_known=True,
        )


class PPORuntimePolicy:
    controller_provenance = "ppo"

    def __init__(self, model):
        self.model = model

    @classmethod
    def load(cls, model_path: str | Path) -> "PPORuntimePolicy":
        if PPO is None:
            raise RuntimeError(
                "PPO runtime requires stable-baselines3 and torch. "
                "Install the locked requirements first: .venv\\Scripts\\python.exe -m pip install -r requirements.txt"
            )
        return cls(PPO.load(str(model_path)))

    def predict(self, observation=None, info: dict | None = None) -> PolicyPrediction:
        info = info or {}
        valid_action_mask = _coerce_valid_action_mask(info.get("valid_action_mask"))
        raw_action, _ = self.model.predict(observation, deterministic=True)
        if hasattr(raw_action, "item"):
            action = int(raw_action.item())
        elif isinstance(raw_action, (list, tuple)):
            action = int(raw_action[0])
        else:
            action = int(raw_action)

        if action < 0 or action >= len(RL_SERVICE_ACTIONS):
            action = _first_valid_action(valid_action_mask)
        if valid_action_mask is not None and (
            action >= len(valid_action_mask) or not valid_action_mask[action]
        ):
            action = _first_valid_action(valid_action_mask)

        return PolicyPrediction(
            action=action,
            action_name=RL_SERVICE_ACTIONS[action],
            controller_provenance=self.controller_provenance,
            q_values=(),
            state_known=True,
        )


def load_runtime_policy(controller_provenance: str, model_path: str | Path | None = None) -> RuntimePolicy:
    normalized_provenance = str(controller_provenance or "").strip().lower().replace("_", "-")
    if normalized_provenance == "ql":
        if model_path is None:
            raise ValueError("model_path is required for QL runtime policy.")
        return QLRuntimePolicy.load(model_path)
    if normalized_provenance == "dql":
        if model_path is None:
            raise ValueError("model_path is required for DQL runtime policy.")
        return DQLRuntimePolicy.load(model_path)
    if normalized_provenance == "ppo":
        if model_path is None:
            raise ValueError("model_path is required for PPO runtime policy.")
        return PPORuntimePolicy.load(model_path)
    raise ValueError(f"Unsupported runtime policy: {controller_provenance}")
