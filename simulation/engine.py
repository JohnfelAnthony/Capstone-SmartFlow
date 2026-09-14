"""Main simulation engine — orchestrates agents, signals, and metrics."""

import random
from typing import Optional, List, Dict, Any

from .network import Network
from .vehicles import Vehicle
from .pedestrians import Pedestrian
from .controllers import FixedTimeController, create_controller
from .metrics import MetricsCollector
from .constants import (
    DT, SPAWN_RATES, PED_SPAWN_RATES,
)


# ── Default turn distribution ────────────────────────────────
TURN_WEIGHTS = {"straight": 0.50, "left": 0.25, "right": 0.25}
APPROACHES = ("north", "south", "east", "west")
CROSSWALK_SIDES = ("north", "south", "east", "west")

# Normalize friendly density names to SPAWN_RATES keys
_DENSITY_MAP = {
    "low": "low", "medium": "medium", "high": "heavy", "heavy": "heavy",
    "none": "low",
}


def _norm_density(val: str) -> str:
    return _DENSITY_MAP.get(str(val).lower(), "medium")


def _spawn_probability(rate_per_hour: float) -> float:
    """Probability of spawning one vehicle per tick at the given hourly rate."""
    return rate_per_hour * DT / 3600.0


def _pick_turn(lane_def, weights: dict = None) -> str:
    """Pick a turn from the lane's allowed turns using the weight distribution."""
    allowed = list(lane_def.allowed_turns)
    if len(allowed) == 1:
        return allowed[0]
    w = weights or TURN_WEIGHTS
    # Normalize weights to only allowed turns
    total = sum(w.get(t, 1) for t in allowed)
    r = random.random() * total
    cumulative = 0.0
    for t in allowed:
        cumulative += w.get(t, 1)
        if r <= cumulative:
            return t
    return allowed[-1]


class SimulationEngine:
    """Top-level simulation controller.

    Manages the network, agents, signal controller, metrics pipeline,
    event log, and the main update loop.
    """

    def __init__(
        self,
        network: Optional[Network] = None,
        controller_mode: str = "fixed_time",
        seed: Optional[int] = None,
    ):
        self.network = network or Network()
        self.controller = create_controller(controller_mode)
        self.metrics = MetricsCollector()

        self.clock: float = 0.0
        self.status: str = "stopped"  # running | paused | stopped
        self.simulation_time: float = 0.0

        # Agent collections
        self.vehicles: List[Vehicle] = []
        self.pedestrians: List[Pedestrian] = []

        # Scenario configuration
        self.traffic_density: str = "medium"
        self.pedestrian_density: str = "medium"
        self.emergency_mode: str = "disabled"
        self.road_constraint: str = "None"
        self.lane_closure: bool = False
        self.accident: bool = False
        self.flooding: bool = False
        self.construction: bool = False
        self.temp_blockage: bool = False

        # Events log
        self.events: List[Dict[str, Any]] = []

        # Random seed
        if seed is not None:
            random.seed(seed)
        self._event_counter = 0

        # Internal spawn accumulators
        self._spawn_timer: float = 0.0

        # Track last emit time for periodic events
        self._last_event_time: float = 0.0

    # ── Configuration ─────────────────────────────────────────

    def configure(self, **kwargs):
        """Apply scenario configuration."""
        density_fields = ("traffic_density", "pedestrian_density")
        for key, value in kwargs.items():
            if hasattr(self, key):
                if key in density_fields and isinstance(value, str):
                    value = value.lower()
                setattr(self, key, value)

    def configure_from_scenario(self, scenario: dict):
        """Apply a scenario dictionary from the database."""
        mapping = {
            "traffic_density": "traffic_density",
            "pedestrian_density": "pedestrian_density",
            "emergency_mode": "emergency_mode",
            "road_constraint": "road_constraint",
            "lane_closure": "lane_closure",
            "construction": "construction",
            "accident": "accident",
            "flooding": "flooding",
            "temp_blockage": "temp_blockage",
        }
        density_fields = ("traffic_density", "pedestrian_density")
        for db_key, attr in mapping.items():
            if db_key in scenario and scenario[db_key] is not None:
                value = scenario[db_key]
                if attr in density_fields and isinstance(value, str):
                    value = value.lower()
                setattr(self, attr, value)

    # ── Lifecycle ─────────────────────────────────────────────

    def start(self):
        if self.status == "stopped":
            self._reset()
        self.status = "running"
        self._add_event("info", "Simulation started")

    def pause(self):
        if self.status == "running":
            self.status = "paused"
            self._add_event("info", "Simulation paused")

    def resume(self):
        if self.status == "paused":
            self.status = "running"
            self._add_event("info", "Simulation resumed")

    def stop(self):
        if self.status in ("running", "paused"):
            self.status = "stopped"
            self._add_event("info", "Simulation stopped")

    def reset(self):
        self._reset()
        self.status = "stopped"
        self._add_event("info", "Simulation reset")

    def _reset(self):
        self.clock = 0.0
        self.simulation_time = 0.0
        self.vehicles.clear()
        self.pedestrians.clear()
        self.events.clear()
        self.metrics.reset()
        self.controller.reset()
        self._spawn_timer = 0.0
        self._last_event_time = 0.0
        self._event_counter = 0

    # ── Main Step ─────────────────────────────────────────────

    def step(self, num_ticks: int = 1):
        """Advance the simulation by *num_ticks* ticks."""
        if self.status != "running":
            return

        for _ in range(num_ticks):
            self._tick()

    def _tick(self):
        dt = DT
        self.clock += dt
        self.simulation_time += dt

        # 1. Spawn new agents
        self._spawn_vehicles()
        self._spawn_pedestrians()

        # 2. Update signal controller
        phase_changed = self.controller.step(self._build_state(), dt)

        if phase_changed:
            self._add_event(
                "signal",
                f"Phase changed: {self.controller.phase}"
            )

        # 3. Update vehicles
        self._assign_lead_vehicles()
        for v in self.vehicles:
            if not v.active:
                continue
            approach = v.approach
            v.signal_state = self.controller.signal_for_approach(approach)
            v.update(dt)

        # 4. Remove completed vehicles
        completed = [v for v in self.vehicles if not v.active]
        self.vehicles = [v for v in self.vehicles if v.active]
        if completed:
            self.metrics.record_completion(count=len(completed))

        # 5. Update pedestrians
        for p in self.pedestrians:
            p.update(dt)

        # 6. Remove completed pedestrians
        finished = [p for p in self.pedestrians if not p.active]
        self.pedestrians = [p for p in self.pedestrians if p.active]
        if finished:
            self.metrics.record_completion(peds=len(finished))

        # 7. Compute metrics
        self.metrics.update(self.vehicles, self.pedestrians)

        # 8. Periodic event emission
        self._emit_periodic_events()

    # ── Spawning ──────────────────────────────────────────────

    def _spawn_vehicles(self):
        rate_key = _norm_density(self.traffic_density)
        rate = SPAWN_RATES.get(rate_key, 600)

        spawned = 0
        for approach in APPROACHES:
            if random.random() > _spawn_probability(rate):
                continue
            # Pick lane
            lane_idx = random.choice((0, 1))
            lane_def = self.network.get_approach(approach).lanes[lane_idx]
            turn = _pick_turn(lane_def)

            vehicle_type = "car"
            emergency = False

            # Emergency vehicle spawning
            if self.emergency_mode != "disabled":
                ev_chance = 0.02 if self.emergency_mode == "enabled" else 0.05
                if random.random() < ev_chance:
                    vehicle_type = "emergency"
                    emergency = True
                    self._add_event(
                        "priority",
                        f"Emergency vehicle spawned on {approach} approach"
                    )

            v = Vehicle.create(
                approach=approach,
                lane=lane_idx,
                turn=turn,
                network=self.network,
                vehicle_type=vehicle_type,
                emergency=emergency,
            )
            self.vehicles.append(v)
            spawned += 1

        if spawned:
            self.metrics.record_spawn(count=spawned)

    def _spawn_pedestrians(self):
        rate_key = _norm_density(self.pedestrian_density)
        rate = PED_SPAWN_RATES.get(rate_key, 180)

        spawned = 0
        for side in CROSSWALK_SIDES:
            if random.random() > _spawn_probability(rate):
                continue
            # Some non-compliant pedestrians for realism
            compliance = "compliant" if random.random() > 0.15 else "non-compliant"
            p = Pedestrian.create(
                side=side,
                network=self.network,
                compliance=compliance,
            )
            self.pedestrians.append(p)
            spawned += 1

        if spawned:
            self.metrics.record_spawn(peds=spawned)

    # ── Car-following assignment ──────────────────────────────

    def _assign_lead_vehicles(self):
        """Assign each vehicle's lead_vehicle (the one immediately ahead in the same lane)."""
        # Group active vehicles by (approach, lane)
        groups: Dict[tuple, List[Vehicle]] = {}
        for v in self.vehicles:
            if not v.active:
                continue
            key = (v.approach, v.lane)
            groups.setdefault(key, []).append(v)

        for key, group in groups.items():
            approach, lane = key
            # Sort by distance-to-end of route
            # For north: higher waypoint_idx + smaller y = further along
            group.sort(key=lambda v: (
                v.waypoint_idx,
                -v.y if v.approach in ("north",) else v.y if v.approach == "south" else -v.x if v.approach == "east" else v.x
            ), reverse=True)

            for i, v in enumerate(group):
                if i == 0:
                    v.lead_vehicle = None
                else:
                    v.lead_vehicle = group[i - 1]

    # ── Events ────────────────────────────────────────────────

    def _add_event(self, kind: str, message: str):
        self._event_counter += 1
        self.events.append({
            "id": self._event_counter,
            "time": round(self.simulation_time, 1),
            "kind": kind,
            "message": message,
        })
        # Keep last 100 events
        if len(self.events) > 100:
            self.events = self.events[-100:]

    def _emit_periodic_events(self):
        """Emit congestion-warning events periodically."""
        interval = 30.0  # every 30 seconds of sim time
        if self.simulation_time - self._last_event_time < interval:
            return
        self._last_event_time = self.simulation_time

        # Check for congestion on each approach
        for approach in APPROACHES:
            active_on_approach = [
                v for v in self.vehicles
                if v.active and v.approach == approach
            ]
            if len(active_on_approach) >= 8:
                self._add_event(
                    "warning",
                    f"High congestion on {approach} approach — "
                    f"{len(active_on_approach)} vehicles"
                )

        # Pedestrian activity
        waiting_peds = [p for p in self.pedestrians if p.state == "waiting"]
        if len(waiting_peds) >= 5:
            self._add_event(
                "info",
                f"{len(waiting_peds)} pedestrians waiting at crosswalks"
            )

    # ── State helpers ─────────────────────────────────────────

    def _build_state(self) -> dict:
        """Return a lightweight state dict for the controller."""
        queue_by_approach = {}
        for approach in APPROACHES:
            q = len([
                v for v in self.vehicles
                if v.active and v.approach == approach and v.speed < 0.1
            ])
            queue_by_approach[approach] = q

        return {
            "clock": self.clock,
            "vehicles": len([v for v in self.vehicles if v.active]),
            "pedestrians": len([p for p in self.pedestrians if p.active]),
            "queues": queue_by_approach,
            "phase": self.controller.phase,
        }

    # ── Serialization ─────────────────────────────────────────

    def to_dict(self) -> dict:
        """Full serialization for dashboard consumption."""
        return {
            "time": round(self.simulation_time, 1),
            "status": self.status,
            "phase": self.controller.phase,
            "phase_remaining": self.controller.light.remaining,
            "cycle_count": self.controller.light.cycle_count,
            "controller_type": "fixed_time" if isinstance(self.controller, FixedTimeController) else "rl",
            "vehicles": [v.to_dict() for v in self.vehicles if v.active][:50],
            "vehicle_count": len([v for v in self.vehicles if v.active]),
            "pedestrians": [p.to_dict() for p in self.pedestrians if p.active][:20],
            "pedestrian_count": len([p for p in self.pedestrians if p.active]),
            "metrics": self.metrics.to_dict(),
            "events": self.events[-20:] if self.events else [],
            "scenario": {
                "traffic_density": self.traffic_density,
                "pedestrian_density": self.pedestrian_density,
                "emergency_mode": self.emergency_mode,
                "road_constraint": self.road_constraint,
            },
        }
