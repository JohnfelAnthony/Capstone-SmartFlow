"""Vehicle agent — rule-based car-following with signal response."""

import math
from typing import Optional

from .agents import Agent
from .constants import (
    VEHICLE_LENGTH, MIN_GAP, TIME_HEADWAY,
    COMFORT_ACCEL, COMFORT_DECEL, MAX_DECEL,
    SPEED_LIMIT,
)
from .network import Network


class Vehicle(Agent):
    """A single vehicle that follows waypoints and responds to its environment."""

    _counter: int = 0

    @classmethod
    def next_id(cls) -> str:
        cls._counter += 1
        return f"V_{cls._counter}"

    def __init__(
        self,
        vehicle_id: str,
        approach: str,
        lane: int,
        turn: str,
        route: list,
        network: Network,
        vehicle_type: str = "car",
        emergency: bool = False,
    ):
        spawn = route[0]
        super().__init__(
            id=vehicle_id, type="vehicle",
            x=spawn[0], y=spawn[1],
            speed=0.0, heading=0.0,
            state="active", active=True,
        )
        self.approach = approach
        self.lane = lane
        self.turn = turn
        self.route = route
        self.network = network
        self.vehicle_type = vehicle_type
        self.target_speed = SPEED_LIMIT
        self.emergency = emergency
        self.length = VEHICLE_LENGTH
        self.waypoint_idx = 0
        self.wait_time = 0.0
        self.signal_state: str = "green"
        self.lead_vehicle: Optional["Vehicle"] = None

        if len(route) > 1:
            self._update_heading(route[1])

    def _current_waypoint(self):
        return self.route[self.waypoint_idx]

    def _next_waypoint(self):
        idx = min(self.waypoint_idx + 1, len(self.route) - 1)
        return self.route[idx]

    def _distance_to_waypoint(self) -> float:
        wx, wy = self._current_waypoint()
        return math.hypot(wx - self.x, wy - self.y)

    def _distance_to_stop_line(self) -> float:
        """Signed distance to stop line (waypoint 1). Negative if already past."""
        if self.waypoint_idx > 1 or len(self.route) < 2:
            return -1.0
        sl = self.route[1]
        dx = sl[0] - self.x
        dy = sl[1] - self.y
        return math.copysign(math.hypot(dx, dy), dx * math.cos(self.heading) + dy * math.sin(self.heading))

    def _update_heading(self, target):
        self.heading = math.atan2(target[1] - self.y, target[0] - self.x)

    def update(self, dt: float):
        if not self.active or self.state != "active":
            return

        desired = self._compute_desired_speed(dt)

        diff = desired - self.speed
        if diff > 0:
            self.speed = min(self.speed + COMFORT_ACCEL * dt, desired)
        else:
            self.speed = max(self.speed + COMFORT_DECEL * dt, desired)
        self.speed = max(0.0, self.speed)

        if self.speed < 0.1:
            self.wait_time += dt

        remaining = self.speed * dt
        while remaining > 0 and self.active:
            wx, wy = self._current_waypoint()
            dx = wx - self.x
            dy = wy - self.y
            dist = math.hypot(dx, dy)

            if dist <= remaining:
                if self.waypoint_idx == 1 and self.signal_state in ("red", "yellow"):
                    self.x, self.y = wx, wy
                    self.speed = 0.0
                    break
                self.x, self.y = wx, wy
                remaining -= dist
                self.waypoint_idx += 1
                if self.waypoint_idx >= len(self.route):
                    self.active = False
                    self.state = "done"
                    break
                self._update_heading(self._next_waypoint())
            else:
                frac = remaining / dist if dist > 0 else 0
                self.x += dx * frac
                self.y += dy * frac
                remaining = 0.0

    def _compute_desired_speed(self, dt: float) -> float:
        desired = self.target_speed

        # ── Stop-line braking (signal response) ────────────
        dist_sl = self._distance_to_stop_line()
        if dist_sl > 0 and self.signal_state in ("red", "yellow"):
            stop_dist = max(dist_sl - MIN_GAP, 0.0)
            safe = math.sqrt(max(2 * -COMFORT_DECEL * stop_dist, 0.0))
            desired = min(desired, safe)

        # ── Car-following ──────────────────────────────────
        if self.lead_vehicle is not None and self.lead_vehicle.active:
            gap = self.distance_to(self.lead_vehicle)
            gap -= self.length / 2 + self.lead_vehicle.length / 2
            gap = max(gap, 0.0)
            desired_gap = MIN_GAP + self.speed * TIME_HEADWAY
            if gap < desired_gap:
                ratio = gap / max(desired_gap, 0.01)
                desired = min(desired, self.lead_vehicle.speed * max(ratio, 0.3))
            elif gap > desired_gap * 2 and self.speed < self.target_speed:
                desired = min(desired, self.target_speed)

        # ── Tight turn slowing ─────────────────────────────
        seg = self._next_waypoint() if self.waypoint_idx < len(self.route) - 1 else None
        if seg:
            wx, wy = self._current_waypoint()
            seg_len = math.hypot(seg[0] - wx, seg[1] - wy)
            if seg_len < 6.0 and self._distance_to_waypoint() < 10.0:
                desired = min(desired, 5.0)

        return max(desired, 0.0)

    @staticmethod
    def create(approach: str, lane: int, turn: str,
               network: Network,
               vehicle_type: str = "car",
               emergency: bool = False) -> "Vehicle":
        route = network.get_route(approach, lane, turn)
        return Vehicle(
            vehicle_id=Vehicle.next_id(),
            approach=approach, lane=lane, turn=turn,
            route=route, network=network,
            vehicle_type=vehicle_type, emergency=emergency,
        )

    def to_dict(self) -> dict:
        base = super().to_dict()
        base.update({
            "approach": self.approach,
            "lane": self.lane,
            "turn": self.turn,
            "vehicle_type": self.vehicle_type,
            "emergency": self.emergency,
            "wait_time": round(self.wait_time, 1),
        })
        return base
