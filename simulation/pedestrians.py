"""Pedestrian agent — crossing behavior at crosswalks."""

import math
from .agents import Agent
from .constants import PED_SPEED
from .network import Network


class Pedestrian(Agent):
    """A pedestrian that spawns, waits, crosses, and finishes."""

    _counter: int = 0

    @classmethod
    def next_id(cls) -> str:
        cls._counter += 1
        return f"P_{cls._counter}"

    # Crossing directions mapped from approach
    CROSSWALK_AXIS = {
        "north": ("y", +1),    # walk north → south (crossing the north crosswalk)
        "south": ("y", -1),
        "east":  ("x", -1),
        "west":  ("x", +1),
    }

    def __init__(
        self,
        ped_id: str,
        crosswalk_side: str,
        network: Network,
        compliance: str = "compliant",
        speed: float = PED_SPEED,
    ):
        cw = network.crosswalks[crosswalk_side]
        # Start position depends on crosswalk
        if crosswalk_side in ("north", "south"):
            sx = cw["x1"]
            sy = cw["y"]
            target_x = cw["x2"]
            target_y = cw["y"]
        else:
            sx = cw["x"]
            sy = cw["y1"]
            target_x = cw["x"]
            target_y = cw["y2"]

        super().__init__(
            id=ped_id, type="pedestrian",
            x=sx, y=sy,
            speed=0.0, heading=math.atan2(target_y - sy, target_x - sx),
            state="waiting", active=True,
        )
        self.crosswalk_side = crosswalk_side
        self.compliance = compliance
        self.target_x = target_x
        self.target_y = target_y
        self.walk_speed = speed
        self.delay = 0.0
        self.compliant = compliance == "compliant"
        self._wait_timer = 0.0
        self._start_delay = 3.0  # seconds before starting to cross

    def update(self, dt: float):
        if not self.active:
            return

        if self.state == "waiting":
            self.delay += dt
            self._wait_timer += dt
            # Non-compliant pedestrians may cross early or whenever
            if self.compliant:
                if self._wait_timer >= self._start_delay:
                    self.state = "crossing"
            else:
                # Non-compliant cross after a shorter wait
                if self._wait_timer >= 1.0:
                    self.state = "crossing"
            return

        if self.state == "crossing":
            self.speed = self.walk_speed
            dx = self.target_x - self.x
            dy = self.target_y - self.y
            dist = math.hypot(dx, dy)

            if dist < 0.3:
                self.state = "done"
                self.active = False
                return

            step = min(self.speed * dt, dist)
            self.x += (dx / dist) * step
            self.y += (dy / dist) * step

    def to_dict(self) -> dict:
        base = super().to_dict()
        base.update({
            "crosswalk_side": self.crosswalk_side,
            "compliance": self.compliance,
            "delay": round(self.delay, 1),
        })
        return base

    @staticmethod
    def create(side: str, network: Network,
               compliance: str = "compliant") -> "Pedestrian":
        return Pedestrian(
            ped_id=Pedestrian.next_id(),
            crosswalk_side=side,
            network=network,
            compliance=compliance,
        )
