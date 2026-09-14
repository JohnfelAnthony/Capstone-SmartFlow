"""Base agent class for all simulation entities."""

import math
from dataclasses import dataclass
from typing import Dict, Any


@dataclass
class Agent:
    """Shared base for vehicles and pedestrians."""

    id: str
    type: str
    x: float
    y: float
    speed: float
    heading: float
    state: str
    active: bool = True

    def distance_to(self, other: "Agent") -> float:
        dx = self.x - other.x
        dy = self.y - other.y
        return math.hypot(dx, dy)

    def bearing_to(self, other: "Agent") -> float:
        return math.atan2(other.y - self.y, other.x - self.x)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "type": self.type,
            "x": round(self.x, 2),
            "y": round(self.y, 2),
            "speed": round(self.speed, 2),
            "heading_deg": round(math.degrees(self.heading), 1),
            "state": self.state,
        }
