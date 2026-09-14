"""Signal controllers — fixed-time and RL interface for traffic light control."""

from typing import Optional
from .traffic_light import TrafficLight
from .constants import DT


class FixedTimeController:
    """Cycles through a pre-defined signal phase sequence at fixed durations."""

    def __init__(self, initial_idx: int = 0):
        self.light = TrafficLight(initial_idx=initial_idx)
        self.transitioned = False

    @property
    def phase(self) -> str:
        return self.light.phase

    def step(self, _state: dict, dt: float = DT) -> bool:
        self.transitioned = self.light.update(dt)
        return self.transitioned

    def signal_for_approach(self, approach: str) -> str:
        return self.light.signal_for_approach(approach)

    def reset(self):
        self.light.reset()
        self.transitioned = False

    def to_dict(self) -> dict:
        return {
            "type": "fixed_time",
            "light": self.light.to_dict(),
        }


class RLController:
    """Adapter that allows an RL policy to drive the traffic light.

    For now this acts as a passthrough to FixedTimeController.
    Replace `choose_action` with a trained model later.
    """

    def __init__(self, initial_idx: int = 0):
        self.light = TrafficLight(initial_idx=initial_idx)
        self.transitioned = False
        self.last_action = None

    @property
    def phase(self) -> str:
        return self.light.phase

    def step(self, state: dict, dt: float = DT) -> bool:
        # Override: choose action based on state (placeholder)
        action = self.choose_action(state)
        self.last_action = action
        self.transitioned = self.light.update(dt)
        return self.transitioned

    def choose_action(self, state: dict):
        """Override this with a trained policy."""
        # Default: let the fixed cycle run (dummy RL)
        return None

    def signal_for_approach(self, approach: str) -> str:
        return self.light.signal_for_approach(approach)

    def reset(self):
        self.light.reset()
        self.transitioned = False
        self.last_action = None

    def to_dict(self) -> dict:
        return {
            "type": "rl",
            "light": self.light.to_dict(),
            "last_action": self.last_action,
        }


def create_controller(mode: str = "fixed_time", **kwargs):
    """Factory: returns the appropriate controller instance."""
    if mode == "fixed_time":
        return FixedTimeController(**kwargs)
    elif mode == "rl":
        return RLController(**kwargs)
    else:
        raise ValueError(f"Unknown controller mode: {mode!r}")
