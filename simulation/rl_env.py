from __future__ import annotations

from dataclasses import dataclass
from typing import Any

try:
    import numpy as np
except ImportError:  # pragma: no cover - numpy is provided by the training stack
    np = None

try:
    import gymnasium as gym
    from gymnasium import spaces
except ImportError:  # pragma: no cover - optional dependency during initial scaffold
    gym = None
    spaces = None

from .rl_reward import calculate_reward
from .rl_state import RLSnapshot, extract_rl_snapshot
from .sumo_config import SUMO_STEP_LENGTH
from .sumo_engine import RL_SERVICE_ACTIONS, SumoSimulationEngine

RL_CONTROLLER_LABELS = {
    "ql": "Q-Learning",
    "dql": "Deep Q-Learning",
    "ppo": "PPO",
}


@dataclass(frozen=True)
class _SimpleDiscrete:
    n: int


@dataclass(frozen=True)
class _SimpleBox:
    low: float
    high: float
    shape: tuple[int, ...]
    dtype: str


BaseEnv = gym.Env if gym is not None else object


class SmartFlowRLEnv(BaseEnv):
    metadata = {"render_modes": []}

    def __init__(
        self,
        *,
        scenario: dict | None = None,
        seed: int = 42,
        warmup_seconds: float = 20.0,
        evaluation_seconds: float = 300.0,
        decision_interval_seconds: float = 5.0,
        minimum_green_hold_seconds: float = 10.0,
        controller_provenance: str = "ql",
        controller_label: str | None = None,
    ):
        super().__init__()
        normalized_provenance = str(controller_provenance or "").strip().lower().replace("_", "-")
        if normalized_provenance not in RL_CONTROLLER_LABELS:
            allowed_labels = ", ".join(sorted(RL_CONTROLLER_LABELS))
            raise ValueError(f"Unsupported RL controller provenance '{controller_provenance}'. Expected one of: {allowed_labels}.")

        self.base_seed = int(seed)
        self.scenario = dict(scenario or {})
        self.warmup_seconds = max(float(warmup_seconds), 0.0)
        self.evaluation_seconds = max(float(evaluation_seconds), SUMO_STEP_LENGTH)
        self.decision_interval_seconds = max(float(decision_interval_seconds), SUMO_STEP_LENGTH)
        self.minimum_green_hold_seconds = max(float(minimum_green_hold_seconds), SUMO_STEP_LENGTH)
        self.controller_provenance = normalized_provenance
        self.controller_label = str(controller_label or RL_CONTROLLER_LABELS[normalized_provenance])
        self.total_episode_seconds = self.warmup_seconds + self.evaluation_seconds
        self.engine: SumoSimulationEngine | None = None
        self._last_snapshot: RLSnapshot | None = None
        self._step_index = 0

        observation_size = 30
        if spaces is not None:
            self.action_space = spaces.Discrete(len(RL_SERVICE_ACTIONS))
            self.observation_space = spaces.Box(
                low=0.0,
                high=1.0,
                shape=(observation_size,),
                dtype=np.float32 if np is not None else float,
            )
        else:
            self.action_space = _SimpleDiscrete(len(RL_SERVICE_ACTIONS))
            self.observation_space = _SimpleBox(low=0.0, high=1.0, shape=(observation_size,), dtype="float32")

    def _format_observation(self, snapshot: RLSnapshot):
        if np is not None:
            return np.asarray(snapshot.observation, dtype=np.float32)
        return list(snapshot.observation)

    def _build_engine(self, seed: int) -> SumoSimulationEngine:
        engine = SumoSimulationEngine(seed=seed)
        if self.scenario:
            engine.configure_from_scenario(self.scenario)
        engine.start(duration_limit=int(round(self.total_episode_seconds)))
        if engine.status == "error":
            raise RuntimeError(engine.last_error or "SUMO engine failed to start for RL environment.")
        engine.configure_rl_control(
            decision_interval=self.decision_interval_seconds,
            minimum_green_hold=self.minimum_green_hold_seconds,
            controller_label=self.controller_label,
            controller_provenance=self.controller_provenance,
        )
        return engine

    def reset(self, *, seed: int | None = None, options: dict[str, Any] | None = None):
        if self.engine is not None:
            self.engine.stop()

        runtime_seed = int(seed if seed is not None else self.base_seed)
        merged_scenario = dict(self.scenario)
        if options and isinstance(options.get("scenario"), dict):
            merged_scenario.update(options["scenario"])
        if options:
            for field_name in (
                "intersection_id",
                "traffic_density",
                "pedestrian_density",
                "emergency_mode",
                "road_constraint",
                "name",
            ):
                if field_name in options and options[field_name] is not None:
                    merged_scenario[field_name] = options[field_name]
        if merged_scenario != self.scenario:
            self.scenario = merged_scenario

        self.engine = self._build_engine(runtime_seed)
        warmup_ticks = int(round(self.warmup_seconds / SUMO_STEP_LENGTH))
        if warmup_ticks > 0:
            self.engine.step(num_ticks=warmup_ticks)

        self._last_snapshot = extract_rl_snapshot(self.engine)
        self._step_index = 0
        reset_info = {
            "seed": runtime_seed,
            "scenario": dict(self.scenario),
            "phase_family": self._last_snapshot.phase_family,
            "valid_action_mask": self._last_snapshot.valid_action_mask,
            "ql_state": self._last_snapshot.ql_state,
        }
        return self._format_observation(self._last_snapshot), reset_info

    def step(self, action: int):
        if self.engine is None or self._last_snapshot is None:
            raise RuntimeError("Call reset() before step() in SmartFlowRLEnv.")

        action_index = int(action)
        if action_index < 0 or action_index >= len(RL_SERVICE_ACTIONS):
            raise ValueError(f"Action index out of range: {action_index}")

        action_name = RL_SERVICE_ACTIONS[action_index]
        action_result = self.engine.apply_rl_action(action_name)
        decision_ticks = max(1, int(round(self.decision_interval_seconds / SUMO_STEP_LENGTH)))
        self.engine.step(num_ticks=decision_ticks)

        current_snapshot = extract_rl_snapshot(self.engine)
        reward_breakdown = calculate_reward(self._last_snapshot, current_snapshot)
        self._last_snapshot = current_snapshot
        self._step_index += 1

        terminated = self.engine.status in {"completed", "stopped"}
        truncated = self.engine.status == "error"
        info = {
            "action_name": action_name,
            "action_result": action_result,
            "reward_breakdown": reward_breakdown.to_dict(),
            "phase_family": current_snapshot.phase_family,
            "valid_action_mask": current_snapshot.valid_action_mask,
            "ql_state": current_snapshot.ql_state,
            "simulation_time": current_snapshot.simulation_time,
        }
        return self._format_observation(current_snapshot), reward_breakdown.total, terminated, truncated, info

    def close(self):
        if self.engine is not None:
            self.engine.stop()
            self.engine = None
        self._last_snapshot = None

    def render(self):
        return None

    @property
    def action_labels(self) -> tuple[str, ...]:
        return RL_SERVICE_ACTIONS
