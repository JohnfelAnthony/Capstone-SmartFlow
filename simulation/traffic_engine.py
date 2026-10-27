"""Deterministic, headless microscopic traffic simulator in metres and seconds.

IDM car following, approach-scoped junction occupancy, protected crossings,
seeded demand and travel-time routing. Rendering never advances this engine.
"""
from __future__ import annotations

import bisect
import copy
import math
import random
from dataclasses import dataclass
from functools import lru_cache

from .scenario_config import DEFAULT_PEDESTRIAN_PHASE, DEFAULTS, VEHICLE_TYPES, effective_maximum_red, fixed_red_seconds, number, object_config, validate_config
from .demand import Arrival, build_schedule, schedule_hash
from .footprints import rectangle, rectangles_overlap
from .mixed_traffic import (CLASS_DRIVING, DRIVER_STREAM_SALT, KEEPING_WEIGHT_PER_M, LANE_KEEPING_CLASSES, LATERAL_DECISION_TICKS,
                            MAX_YAW_DEGREES, MOTORCYCLE_SHUFFLE_MPS, MOVE_COOLDOWN_SECONDS, MOVE_COST_PER_M, MOVE_GAIN_THRESHOLD_M,
                            ROOM_HORIZON_M, SIDE_CLEARANCE_M, TURN_SIDE_DISTANCE_M, TURN_SIDE_WEIGHT_PER_M, bands_overlap, body_box,
                            candidate_laterals, keeping_position, lateral_bounds, sample_driver, sub_lane_of)
from .road_network import NETWORK_ID, RoadNetwork, length, load_network, sample

STEP_LENGTH = 0.1
# A turning body sweeps across the centre line beside the opposite stop line; vehicles this close to their stop line
# yield to committed sweeps, and a vehicle may not commit while its sweep would hit one of them.
SWEEP_ZONE_M = 15.0
SWEEP_SAMPLE_M = 0.2
# A stop line sits far enough back that no class turning from another approach sweeps over a body waiting at it;
# bodies up to this deep are kept clear, and a line never moves back more than half its lane.
STOP_SETBACK_DEPTH_M = 12.0
STOP_SETBACK_STEP_M = 0.1
# (network fingerprint, lane) -> setback in metres; pure geometry, shared by every engine on that network.
_STOP_SETBACKS: dict[tuple[str, str], float] = {}
_JUNCTION_TURN_BODIES: dict[tuple[str, str], list] = {}
ENGINE_VERSION = "native-5"
RL_SERVICE_ACTIONS = ("SERVE_NORTH", "SERVE_EAST", "SERVE_SOUTH", "SERVE_WEST", "SERVE_PEDESTRIAN")
APPROACHES = ("north", "east", "south", "west")
CAR_LENGTH = 4.5
MIN_GAP = 2.0
# Car following creeps towards its standstill gap without reaching it, so entry keeps this slack past release.
EXIT_SPACE_MARGIN = 1.0
STUCK_IN_JUNCTION_SECONDS = 30.0
GRIDLOCK_SECONDS = 60.0
# Turning speed through a junction and the straight-ahead tolerance; both are calibration parameters.
# shortcut: fixed constants until field discharge headways exist, then move them into the scenario config.
TURN_SPEED_MPS = 5.0
THROUGH_ANGLE_DEGREES = 30.0
COMFORTABLE_DECELERATION = 2.0
TIME_HEADWAY = 1.2


def phase_family_from_name(phase: str) -> str:
    if phase.startswith("PED_"):
        return "PEDESTRIAN"
    return phase.split("_")[0] if phase != "ALL_RED" else "ALL_RED"


@dataclass
class Signal:
    approaches: list[str]
    index: int = 0
    stage: str = "green"
    elapsed: float = 0.0
    green_seconds: float = 14.0
    minimum_green: float = 10.0
    pending: str | None = None
    external: bool = False
    switches: int = 0
    maximum_green: float = 60.0
    yellow_seconds: float = 3.0
    all_red_seconds: float = 1.0
    mode: str = "signalized"
    # Longest a demanded approach may wait for green before the engine requests it (any controller).
    maximum_red: float = 120.0
    # Walk-phase rule; engine plans default to on_call (see scenario_config.DEFAULT_PEDESTRIAN_PHASE).
    pedestrian_phase: str = "every_cycle"
    # Under every_cycle, the longest RL may leave the walk phase unserved: the plan's own fixed-time red.
    walk_interval: float = math.inf

    @property
    def family(self):
        return self.approaches[self.index]

    @property
    def phase(self):
        return "ALL_RED" if self.stage == "red" else f"{'PED' if self.family == 'pedestrian' else self.family.upper()}_{self.stage.upper()}"

    @property
    def remaining(self):
        duration = self.minimum_green if self.external and self.stage == "green" else self.green_seconds if self.stage == "green" else self.yellow_seconds if self.stage == "yellow" else self.all_red_seconds
        return max(0.0, duration-self.elapsed)

    def request(self, family: str):
        if family not in self.approaches:
            return {"applied": False, "reason": "unavailable_approach"}
        if self.stage != "green":
            return {"applied": False, "reason": "clearance_in_progress"}
        self.pending = family if family != self.family else None
        return {"applied": bool(self.pending), "reason": "queued_safely" if self.pending else "already_serving"}

    def step(self, dt: float, crossing_occupied: bool, pedestrians_waiting: bool = False):
        self.elapsed = round(self.elapsed + dt, 6)
        if self.mode == "all_way_stop":
            return
        if self.stage == "green":
            can_switch = self.elapsed >= self.minimum_green and self.pending is not None
            timed_switch = (not self.external and self.elapsed >= self.green_seconds) or self.elapsed >= self.maximum_green
            if (can_switch or timed_switch) and not (self.family == "pedestrian" and crossing_occupied):
                self.stage = "red" if self.family == "pedestrian" else "yellow"
                self.elapsed = 0
        elif self.stage == "yellow" and self.elapsed >= self.yellow_seconds:
            self.stage, self.elapsed = "red", 0
        elif self.stage == "red" and self.elapsed >= self.all_red_seconds and not crossing_occupied:
            next_index = self.approaches.index(self.pending) if self.pending else (self.index+1) % len(self.approaches)
            skip_walk = self.approaches[next_index] == "pedestrian" and self.pedestrian_phase == "on_call" and not pedestrians_waiting
            self.index = (next_index+1) % len(self.approaches) if skip_walk else next_index
            self.stage, self.elapsed, self.pending = "green", 0, None
            self.switches += 1


@dataclass
class Vehicle:
    id: str
    route: list[str]
    destination: str
    born: float
    position: float = CAR_LENGTH / 2
    speed: float = 0.0
    wait: float = 0.0
    connector: list[tuple[float, float]] | None = None
    connector_position: float = 0.0
    reserved_junction: str | None = None
    reroute_at: float = 0.0
    vehicle_type: str = "car"
    length: float = CAR_LENGTH
    width: float = 1.8
    speed_factor: float = 1.0
    requested_at: float = 0.0
    stop_arrival: float | None = None
    stopped_for: float = 0.0
    # Per-driver values drawn at entry (simulation/mixed_traffic.py); defaults are the car class.
    time_headway: float = 1.2
    minimum_gap: float = 2.0
    max_acceleration: float = 1.5
    max_lateral_speed: float = 0.5
    # Body centre's offset from the lane centre line, positive toward the right-hand kerb (metres).
    lateral: float = 0.0
    lateral_speed: float = 0.0
    # Body angle from the lane direction (radians, positive toward the kerb); 0 unless moving sideways, always 0 on connectors.
    yaw: float = 0.0
    lateral_target: float = 0.0
    lateral_cooldown_until: float = 0.0
    # Sideways positions where the vehicle entered its connector and will join the exit lane; it blends between them.
    connector_entry_lateral: float = 0.0
    connector_exit_lateral: float = 0.0

    @property
    def lane_id(self):
        return self.route[0]


@dataclass
class Pedestrian:
    id: str
    junction: str
    wait: float = 0.0
    progress: float = 0.0
    crossing: bool = False


SPAWN_OCCUPANCY_PENDING = object()
TAN_MAX_YAW = math.tan(math.radians(MAX_YAW_DEGREES))


@lru_cache(maxsize=8192)
def vehicle_serial(identity: str) -> int:
    return int(identity.rsplit("-", 1)[-1])


class TrafficEngine:
    step_length = STEP_LENGTH

    def __init__(self, seed: int | None = 42, network: RoadNetwork | None = None):
        validated_seed = 42 if seed is None else number(seed, "seed", 0, 2**32-1)
        if validated_seed != int(validated_seed):
            raise ValueError("Seed must be an integer")
        self.seed = int(validated_seed)
        self.network = network or load_network()
        self.intersection_id = self.network.id
        self.controlled_junction = self.network.intersections[0]
        self.traffic_density = "single"
        self.pedestrian_density = "none"
        self.road_constraint = "None"
        self.closed_lanes: set[str] = set()
        self.slow_lanes: dict[str, float] = {}
        self.scheduled_events: list[dict] = []
        self.green_seconds = 14.0
        self.current_scenario_name = "Tagum five-junction demonstration"
        self.rl_control_enabled = False
        self.rl_decision_interval = 5.0
        self.rl_minimum_green_hold = 10.0
        self.controller_type = "fixed_time"
        self.controller_provenance = "fixed-time"
        self.controller_provenance_label = self.control_mode_label = "Fixed-Time (Python)"
        self.duration_limit = 300
        self.config = validate_config(DEFAULTS, {}, self.network)
        self.runtime_policy = None
        self._turn_angle_cache: dict[tuple[str, str], float] = {}
        # 0 turns per-driver variation off (class values only); kept across configure().
        self.driver_variation_scale = 1.0
        self._reset_state()

    def _reset_state(self, *, arrivals=None):
        # Scheduling can reject excessive demand; fail before changing live state.
        arrivals = build_schedule(self.config, self.network, self.seed, self.duration_limit) if arrivals is None else arrivals
        self.random = random.Random(self.seed)
        self.pedestrian_random = random.Random(self.seed ^ 0x504544)
        # Driver variety has its own stream, so arrivals and pedestrians match native-5 for the same seed.
        self.driver_random = random.Random(self.seed ^ DRIVER_STREAM_SALT)
        self.closed_lanes = set(self.config["closed_lanes"])
        self.slow_lanes = dict(self.config["slow_lanes"])
        self.scheduled_events = copy.deepcopy(self.config["events"])
        self.status, self.simulation_time, self.ticks = "stopped", 0.0, 0
        self.vehicles: dict[str, Vehicle] = {}
        # Search indexes, valid only while a tick moves vehicles or spawns demand; None means scan every vehicle.
        self._tick_index = None
        self._spawn_occupancy = None
        # (tick, {all-way-stop junction: vehicle whose turn it is}), see _stop_priority.
        self._stop_turn: tuple[int, dict] = (-1, {})
        # Committed vehicle -> its remaining path through the junction as drawn bodies [(path position, corners, bbox)].
        self._sweeps: dict[str, list] = {}
        self._sweep_cache: dict[tuple, list] = {}
        self._sweep_bounds_cache: dict[int, tuple[list, tuple[float, float, float, float]]] = {}
        self.pedestrians: dict[str, Pedestrian] = {}
        # Junction occupants and the approach they share; only one approach may be inside a junction at a time.
        self.reservations: dict[str, set[str]] = {}
        self.reservation_approach: dict[str, str] = {}
        self.last_vehicle_movement = 0.0
        self.signals = {}
        for node in self.network.intersections:
            available = [a for a in APPROACHES if any(self.network.lanes[lane].approach == a for lane in self.network.incoming[node])] + ["pedestrian"]
            plan = self.config["signal_plans"].get(node, {})
            order, green = plan.get("phase_order", available), plan.get("green_seconds", self.green_seconds)
            signal = Signal(order,
                            green_seconds=green,
                            minimum_green=(self.rl_minimum_green_hold if self.rl_control_enabled and node == self.controlled_junction
                                           else plan.get("minimum_green", min(self.green_seconds, 10.0))),
                            maximum_green=plan.get("maximum_green", max(60, self.green_seconds)),
                            yellow_seconds=plan.get("yellow_seconds", 3), all_red_seconds=plan.get("all_red_seconds", 1),
                            mode=plan.get("mode", "signalized"), maximum_red=effective_maximum_red(plan, order, green),
                            pedestrian_phase=plan.get("pedestrian_phase", DEFAULT_PEDESTRIAN_PHASE),
                            walk_interval=fixed_red_seconds(order, green, plan.get("yellow_seconds", 3), plan.get("all_red_seconds", 1)))
            # Offset is a phase-clock shift; there are no road users during initialization.
            for _ in range(round(plan.get("offset_seconds", 0)/STEP_LENGTH)):
                signal.step(STEP_LENGTH, False)
            signal.external = self.rl_control_enabled and node == self.controlled_junction
            self.signals[node] = signal
        self.arrivals = arrivals
        self.pedestrian_arrivals = self.config["pedestrian_trips"]
        self.pedestrian_arrival_index = 0
        self.demand_fingerprint = schedule_hash(self.arrivals)
        self.arrival_index = self.requested_vehicles = self.lifetime_completed = 0
        self.lifetime_pedestrians_completed = self.dropped_pedestrians = 0
        self.next_policy_time = 0.0
        self.policy_decisions = 0
        self.last_policy_decision = None
        self.safety_overrides = 0
        self.last_safety_override = None
        self.measurement_start = 0.0
        self.admitted_at_measurement = self.pedestrians_at_measurement = 0
        self.completed_external_wait = 0.0
        self.lane_exits = dict.fromkeys(self.network.lanes, 0)
        self.lane_stopped_seconds = dict.fromkeys(self.network.lanes, 0.0)
        self.last_served = {node: dict.fromkeys(signal.approaches, 0.0) for node, signal in self.signals.items()}
        self.last_action, self.last_error, self.run_id = "Ready", "None", "-"
        self.events = []
        self.next_vehicle_time, self.next_pedestrian_time = 0.0, 6.0
        self.vehicle_serial = self.pedestrian_serial = 0
        self.pending_demand: list[Arrival] = []
        self.completed = self.completed_pedestrians = self.reroutes = self.deferred_demand = 0
        self.completed_wait = self.completed_travel = self.completed_pedestrian_wait = 0.0
        self.queue_integral = self.max_queue = 0.0
        self.metric_ticks = 0
        self.charts = {key: [] for key in ("traffic_flow", "wait_time", "queue_length", "throughput")}
        self.applied_events: set[int] = set()
        self._metrics_pending, self._metrics_snapshot = False, {}
        self._refresh_metrics()

    @property
    def phase(self):
        return self.signals[self.controlled_junction].phase

    @property
    def phase_remaining(self):
        return self.signals[self.controlled_junction].remaining

    @property
    def cycle_count(self):
        signal = self.signals[self.controlled_junction]
        return signal.switches // len(signal.approaches)

    @property
    def rl_total_phase_switches(self):
        return self.signals[self.controlled_junction].switches

    def _add_event(self, kind: str, message: str):
        self.events.append({"time": self.simulation_time, "kind": kind, "message": message})
        self.events = self.events[-40:]
        self.last_action = message

    def configure(self, **settings):
        self._settle_metrics()
        if self.status in {"running", "paused"}:
            raise ValueError("Stop the run before changing scenario settings")
        candidate = validate_config(self.config, settings, self.network)
        arrivals = build_schedule(candidate, self.network, self.seed, self.duration_limit)
        self.config = candidate
        for key in ("traffic_density", "pedestrian_density", "green_seconds", "controlled_junction"):
            setattr(self, key, candidate[key])
        self._reset_state(arrivals=arrivals)
        self._add_event("configuration", "Scenario configured for the Python engine")

    def configure_from_scenario(self, scenario: dict):
        self._settle_metrics()
        if not isinstance(scenario, dict):
            raise ValueError("Scenario must be an object")
        from .scenario_config import normalize_vehicle_scope
        scenario = normalize_vehicle_scope(scenario)
        if 'network_id' in scenario:
            if scenario['network_id'] != self.network.id:
                raise ValueError('Scenario network is unresolved or differs from the configured network; migrate it before execution.')
            native = object_config(scenario.get('engine_config'), 'engine_config')
            if 'intersection_id' in native:
                raise ValueError('Network identity belongs in network_id, not engine_config.')
            self.configure(intersection_id=scenario['network_id'], **native)
            self.current_scenario_name = str(scenario.get('name', self.current_scenario_name))
            return
        if 'road_constraint' in scenario:
            raise ValueError('Legacy road_constraint needs migration to explicit native lane settings.')
        for field in ("lane_closure_config", "construction_config", "accident_config", "flooding_config"):
            if object_config(scenario.get(field, {}), field):
                raise ValueError(f"{field} uses legacy disruption settings; migrate them to engine_config.closed_lanes, slow_lanes or events")
        settings = {key: value for key, value in scenario.items() if key in DEFAULTS or key in {"controlled_junction", "intersection_id", "emergency_mode"}}
        native = object_config(scenario.get("engine_config", {}), "engine_config")
        settings.update(native)
        self.configure(**settings)
        self.current_scenario_name = str(scenario.get("name", self.current_scenario_name))

    def start(self, duration_limit: int = 300):
        if self.status == "paused":
            self.resume()
            return
        if self.status == "running":
            return
        duration = number(duration_limit, "duration", STEP_LENGTH, 86400)
        if abs(duration/STEP_LENGTH-round(duration/STEP_LENGTH)) > 1e-7:
            raise ValueError("Duration must be a multiple of the 0.1 second step")
        arrivals = build_schedule(self.config, self.network, self.seed, duration)
        self.duration_limit = duration
        self._reset_state(arrivals=arrivals)
        self.status, self.run_id = "running", f"native-{self.seed}"
        self._add_event("run", "Python traffic simulation started")
        self._apply_scheduled_events()
        self._spawn_demand()
        self._refresh_metrics()

    def pause(self):
        if self.status == "running":
            self.status = "paused"

    def resume(self):
        if self.status == "paused":
            self.status = "running"

    def stop(self):
        self.status = "stopped"

    def reset(self):
        self._reset_state()

    def close_lane(self, lane_id: str, closed: bool = True):
        self._settle_metrics()
        if lane_id not in self.network.lanes:
            raise ValueError("Unknown lane")
        if not isinstance(closed, bool):
            raise ValueError("closed must be true or false")
        if closed:
            self.closed_lanes.add(lane_id)
        else:
            self.closed_lanes.discard(lane_id)
        for vehicle in self.vehicles.values():
            vehicle.reroute_at = 0
        self._add_event("constraint", f"Lane {lane_id} {'closed to entry' if closed else 'reopened'}")

    def _travel_costs(self):
        queues = self._lane_queues()
        return {lane.id: lane.length/(lane.speed*self.slow_lanes.get(lane.id, 1)) + queues[lane.id]*2.5 for lane in self.network.lanes.values()}

    def _demand_pair(self):
        sources = [node for node in self.network.boundaries if self.network.outgoing[node]]
        destinations = [node for node in self.network.boundaries if self.network.incoming[node]]
        pairs = [(source, target) for source in sources for target in destinations if source != target]
        self.random.shuffle(pairs)
        candidates = []
        for source, target in pairs:
            route = self.network.route(source, target, closed=self.closed_lanes)
            if route:
                if self.traffic_density != "single":
                    return source, target
                candidates.append((len(route), source, target))
        if candidates:
            _, source, target = max(candidates)
            return source, target
        return None

    def add_vehicle(self, route: list[str], *, speed: float = 0.0, vehicle_type: str = "car", requested_at: float | None = None) -> Vehicle | None:
        self._settle_metrics()
        if not route or any(lane not in self.network.lanes for lane in route):
            raise ValueError("Vehicle requires a valid route")
        if any(not self.network.turn_allowed(a, b) for a, b in zip(route, route[1:])):
            raise ValueError("Disconnected or prohibited vehicle turn")
        if self.network.lanes[route[-1]].target not in self.network.boundaries:
            raise ValueError("A vehicle route must finish at a boundary")
        if vehicle_type not in VEHICLE_TYPES:
            raise ValueError("Unknown vehicle type")
        speed = number(speed, "initial speed", 0, 60)
        spec = VEHICLE_TYPES[vehicle_type]
        spawn_position = spec["length"]/2
        lateral = self._entry_lateral(route[0], vehicle_type)
        if route[0] in self.closed_lanes or lateral is None or len(self.vehicles) >= self.config["max_active_vehicles"]:
            return None
        self.vehicle_serial += 1
        vehicle = Vehicle(f"car-{self.vehicle_serial}", list(route), self.network.lanes[route[-1]].target,
                          self.simulation_time, position=spawn_position, speed=speed,
                          vehicle_type=vehicle_type,
                          requested_at=self.simulation_time if requested_at is None else requested_at, **spec)
        profile = sample_driver(vehicle_type, self.driver_random, self.driver_variation_scale)
        vehicle.speed_factor = spec["speed_factor"]*profile.speed_multiplier
        vehicle.time_headway, vehicle.minimum_gap = profile.time_headway, profile.minimum_gap
        vehicle.max_acceleration, vehicle.max_lateral_speed = profile.max_acceleration, profile.max_lateral_speed
        vehicle.lateral = vehicle.lateral_target = lateral
        self.vehicles[vehicle.id] = vehicle
        if isinstance(self._spawn_occupancy, dict):
            self._spawn_occupancy.setdefault(route[0], []).append((vehicle.position-vehicle.length/2, lateral, vehicle.width))
        if requested_at is None:
            self.requested_vehicles += 1
        return vehicle

    def _box(self, vehicle: Vehicle) -> tuple[float, float]:
        """Along-road length and across-road width of the body as drawn (turned by its yaw)."""
        return (vehicle.length, vehicle.width) if vehicle.yaw == 0 else body_box(vehicle.length, vehicle.width, vehicle.yaw)

    def _pose(self, vehicle: Vehicle) -> tuple[float, float, float]:
        """Drawn centre x, y and body heading, including the sideways offset, on a lane or a connector."""
        if vehicle.connector is not None:
            x, y, path_heading = sample(vehicle.connector, vehicle.connector_position)
            body_heading = path_heading
        else:
            x, y, path_heading = sample(self.network.lanes[vehicle.route[0]].shape, vehicle.position)
            body_heading = path_heading-vehicle.yaw
        return x+math.sin(path_heading)*vehicle.lateral, y-math.cos(path_heading)*vehicle.lateral, body_heading

    def _build_spawn_occupancy(self) -> dict[str, list[tuple[float, float, float]]] | None:
        """Lane -> (rear, lateral, width) of vehicles on lanes, so spawn checks skip a scan of every vehicle."""
        occupancy: dict[str, list[tuple[float, float, float]]] = {}
        for other in self.vehicles.values():
            if not other.connector:
                other_length, other_width = self._box(other)
                occupancy.setdefault(other.route[0], []).append((other.position-other_length/2, other.lateral, other_width))
        return occupancy

    def _entry_lateral(self, lane_id: str, vehicle_type: str) -> float | None:
        """Sideways entry position with room at the lane start, or None when every allowed position is blocked."""
        spec, lane = VEHICLE_TYPES[vehicle_type], self.network.lanes[lane_id]
        needed = spec["length"]+CLASS_DRIVING[vehicle_type].minimum_gap
        if self._spawn_occupancy is SPAWN_OCCUPANCY_PENDING:
            self._spawn_occupancy = self._build_spawn_occupancy()
        if self._spawn_occupancy is not None:
            occupancy = self._spawn_occupancy.get(lane_id, [])
        else:
            occupancy = [(other.position-self._box(other)[0]/2, other.lateral, self._box(other)[1])
                         for other in self.vehicles.values() if not other.connector and other.route[0] == lane_id]

        def room(lateral):
            return min((rear for rear, other_lateral, other_width in occupancy
                        if bands_overlap(lateral, spec["width"], other_lateral, other_width)), default=math.inf)
        if vehicle_type in LANE_KEEPING_CLASSES:
            positions = [keeping_position(vehicle_type, spec["width"], lane.width, lane.lane_count, sub_lane) for sub_lane in range(lane.lane_count)]
            candidates = [positions[index] for index in sorted(range(len(positions)), key=lambda index: (-room(positions[index]), index))]
        else:
            # Tricycles and motorcycles take the free position nearest the kerb.
            candidates = list(reversed(candidate_laterals(lane.width, spec["width"])))
        return next((lateral for lateral in candidates if room(lateral) >= needed), None)

    def _spawn_demand(self):
        # Built at the first entry check of this spawn step (most ticks have none); it then includes vehicles added before it.
        self._spawn_occupancy = SPAWN_OCCUPANCY_PENDING
        try:
            self._spawn_vehicles_and_pedestrians()
        finally:
            self._spawn_occupancy = None

    def _spawn_vehicles_and_pedestrians(self):
        single_demo = self.traffic_density == "single" and not self.config["trips"] and not self.config["demand_windows"]
        if single_demo and not self.vehicles and self.simulation_time < self.duration_limit:
            pair = self._demand_pair()
            if pair:
                self.add_vehicle(self.network.route(*pair, closed=self.closed_lanes), vehicle_type="car")
        while self.arrival_index < len(self.arrivals) and self.arrivals[self.arrival_index].time <= self.simulation_time:
            arrival = self.arrivals[self.arrival_index]
            self.arrival_index += 1
            self.requested_vehicles += 1
            if len(self.pending_demand) < self.config["max_pending_vehicles"]:
                self.pending_demand.append(arrival)
            else:
                self.deferred_demand += 1
        costs = None
        for arrival in self.pending_demand[:]:
            if len(self.vehicles) >= self.config["max_active_vehicles"]:
                break
            spec = VEHICLE_TYPES.get(arrival.vehicle_type)
            # Every route starts on one of the source's outgoing lanes; when all are closed or full, entry fails anyway.
            entry_possible = spec is None or any(lane not in self.closed_lanes and self._entry_lateral(lane, arrival.vehicle_type) is not None
                                                 for lane in self.network.outgoing.get(arrival.source, []))
            if not entry_possible:
                continue
            if costs is None and self.config["routing_mode"] == "adaptive":
                costs = self._travel_costs()
            route = self.network.route(arrival.source, arrival.destination, closed=self.closed_lanes, costs=costs if self.config["routing_mode"] == "adaptive" else None)
            if route and self.add_vehicle(route, vehicle_type=arrival.vehicle_type, requested_at=arrival.time):
                self.pending_demand.remove(arrival)
        while self.pedestrian_arrival_index < len(self.pedestrian_arrivals) and self.pedestrian_arrivals[self.pedestrian_arrival_index]["time"] <= self.simulation_time:
            trip = self.pedestrian_arrivals[self.pedestrian_arrival_index]
            self.pedestrian_arrival_index += 1
            if trip["time"] >= self.duration_limit:
                continue
            self.pedestrian_serial += 1
            if len(self.pedestrians) < 1000:
                pedestrian = Pedestrian(f"ped-{self.pedestrian_serial}", trip["junction"])
                self.pedestrians[pedestrian.id] = pedestrian
            else:
                self.dropped_pedestrians += 1
        while self.pedestrian_density != "none" and self.simulation_time >= self.next_pedestrian_time and self.next_pedestrian_time < self.duration_limit:
            self.pedestrian_serial += 1
            junction = self.pedestrian_random.choice(self.network.intersections)
            if len(self.pedestrians) < 1000:
                pedestrian = Pedestrian(f"ped-{self.pedestrian_serial}", junction)
                self.pedestrians[pedestrian.id] = pedestrian
            else:
                self.dropped_pedestrians += 1
            rate = {"low": 0.025, "medium": 0.07, "high": 0.15}[self.pedestrian_density]
            self.next_pedestrian_time += self.pedestrian_random.expovariate(rate)

    def _control_signals(self):
        if self.runtime_policy is not None and self.simulation_time >= self.next_policy_time:
            from .rl_state import extract_rl_snapshot
            snapshot = extract_rl_snapshot(self)
            prediction = self.runtime_policy.predict(snapshot.observation, {"ql_state": snapshot.ql_state, "valid_action_mask": snapshot.valid_action_mask})
            self.apply_rl_action(prediction.action_name)
            self.next_policy_time = self.simulation_time+self.rl_decision_interval
        for node, signal in self.signals.items():
            if signal.mode != "signalized" or signal.stage != "green":
                continue
            self.last_served[node][signal.family] = self.simulation_time
            demanded = {self.network.lanes[v.route[0]].approach for v in self.vehicles.values() if not v.connector and self.network.lanes[v.route[0]].target == node}
            oldest = min(demanded, key=lambda a: (self.last_served[node][a], a), default=None)
            overdue_approach = oldest is not None and self.simulation_time-self.last_served[node][oldest] >= signal.maximum_red
            overdue_pedestrians = any(p.junction == node and not p.crossing and p.wait >= self.config["pedestrian_max_wait"] for p in self.pedestrians.values())
            # Fixed-time serves an every_cycle walk phase by itself; RL is held to the same interval.
            walk_overdue = (signal.external and signal.pedestrian_phase == "every_cycle" and signal.family != "pedestrian"
                            and self.simulation_time-self.last_served[node]["pedestrian"] >= signal.walk_interval)
            # Bound service starvation even when a policy repeatedly asks for the same phase.
            if signal.elapsed >= signal.maximum_green:
                self._request_safety_service(node, signal.approaches[(signal.index+1) % len(signal.approaches)], "maximum_green")
            elif overdue_pedestrians and signal.family != "pedestrian":
                self._request_safety_service(node, "pedestrian", "pedestrian_wait")
            elif walk_overdue:
                self._request_safety_service(node, "pedestrian", "walk_interval")
            elif overdue_approach:
                self._request_safety_service(node, oldest, "approach_starvation")

    def _request_safety_service(self, node, family, reason):
        signal = self.signals[node]
        if family == signal.family or signal.pending == family:
            return
        result = signal.request(family)
        if result["applied"]:
            self.safety_overrides += 1
            self.last_safety_override = {"time": self.simulation_time, "junction_id": node,
                                         "service": family, "reason": reason}
            self._add_event("safety", f"{node}: {reason} requested {family}")

    def set_runtime_policy(self, policy, *, decision_interval=5.0, minimum_green_hold=10.0):
        self._settle_metrics()
        if not callable(getattr(policy, "predict", None)):
            raise ValueError("Policy needs predict(observation, info)")
        from .model_contract import native_contract
        if self.network.fingerprint != native_contract()["network_sha256"]:
            raise ValueError("Saved policies currently support only the versioned default study network")
        training_node = getattr(policy, "artifact_metadata", {}).get("training_junction")
        if training_node and training_node != self.controlled_junction:
            raise ValueError("Selected model was trained for a different controlled junction")
        self.configure_rl_control(decision_interval=decision_interval, minimum_green_hold=minimum_green_hold,
                                  controller_label=policy.controller_provenance.upper(), controller_provenance=policy.controller_provenance)
        self.runtime_policy = policy

    def _pedestrians_waiting(self, node: str):
        return any(pedestrian.junction == node and not pedestrian.crossing for pedestrian in self.pedestrians.values())

    def _crossing_occupied(self, node: str):
        return any(pedestrian.junction == node and pedestrian.crossing for pedestrian in self.pedestrians.values())

    def _step_pedestrians(self):
        for pedestrian in list(self.pedestrians.values()):
            signal = self.signals[pedestrian.junction]
            if not pedestrian.crossing:
                # Do not start a crossing that cannot finish in this pedestrian green.
                if ((signal.family == "pedestrian" and signal.stage == "green" and signal.elapsed <= 0.5) or signal.mode == "all_way_stop") and pedestrian.junction not in self.reservations:
                    pedestrian.crossing = True
                else:
                    pedestrian.wait += STEP_LENGTH
            if pedestrian.crossing:
                pedestrian.progress += self.config["pedestrian_speed"]*STEP_LENGTH
                if pedestrian.progress >= self.config["crossing_length"]:
                    self.completed_pedestrians += 1
                    self.lifetime_pedestrians_completed += 1
                    self.completed_pedestrian_wait += pedestrian.wait
                    del self.pedestrians[pedestrian.id]

    @staticmethod
    def _index_keys(vehicle: Vehicle) -> list[tuple[str, str]]:
        keys = [("on_lane" if vehicle.connector is None else "turning_off", vehicle.route[0])]
        if len(vehicle.route) > 1:
            keys.append(("next_lane", vehicle.route[1]))
        return keys

    def _build_tick_index(self):
        """Index vehicles by lane, by lane they are turning off and by next lane, in self.vehicles order."""
        order, on_lane, turning_off, next_lane = {}, {}, {}, {}
        for position, vehicle in enumerate(self.vehicles.values()):
            order[vehicle.id] = position
            (on_lane if vehicle.connector is None else turning_off).setdefault(vehicle.route[0], []).append(vehicle)
            if len(vehicle.route) > 1:
                next_lane.setdefault(vehicle.route[1], []).append(vehicle)
        self._tick_index = {"order": order, "on_lane": on_lane, "turning_off": turning_off, "next_lane": next_lane}

    def _reindex(self, vehicle: Vehicle, old_keys: list[tuple[str, str]]):
        """Keep the index current after a vehicle moved: it leaves buckets it no longer matches and joins new ones in order."""
        index = self._tick_index
        new_keys = self._index_keys(vehicle) if self.vehicles.get(vehicle.id) is vehicle else []
        for name, key in old_keys:
            if (name, key) not in new_keys:
                bucket = index[name][key]
                del bucket[next(position for position, other in enumerate(bucket) if other is vehicle)]
        order = index["order"]
        for name, key in new_keys:
            if (name, key) not in old_keys:
                bucket = index[name].setdefault(key, [])
                bucket.insert(bisect.bisect_left(bucket, order[vehicle.id], key=lambda other: order[other.id]), vehicle)

    def _candidates(self, *lookups: tuple[str, str]):
        """Every live vehicle whose current lane, connector state or next lane matches the lookups, in self.vehicles
        order. Callers still apply their full condition, so results match a scan of every vehicle exactly. A single
        lookup returns the index bucket itself, which callers only read."""
        index = self._tick_index
        if index is None:
            return list(self.vehicles.values())
        if len(lookups) == 1:
            name, key = lookups[0]
            return index[name].get(key, ())
        pool = {vehicle.id: vehicle for name, key in lookups for vehicle in index[name].get(key, ())}
        return sorted(pool.values(), key=lambda vehicle: index["order"][vehicle.id])

    def _exit_has_space(self, lane_id: str, entering: Vehicle):
        """Storage rule: everything on the exit lane or committed to it, plus the entrant, must fit end to end, each
        counted as its length, its own minimum gap and a margin (which also covers a turned body's extra length).
        Vehicles only stop behind a leader or a stop line, so even if the lane's far end holds them all, each
        committed vehicle can still leave the junction and release it. This holds side by side too: every leader in
        the chain ahead of an entrant is counted, whatever its sideways position. Accepted limitation: a road backed
        up with vehicles side by side counts as full sooner than it really is."""
        occupying = [vehicle for vehicle in self._candidates(("on_lane", lane_id), ("next_lane", lane_id)) if vehicle is not entering and (
            (vehicle.connector is None and vehicle.route[0] == lane_id)
            or (vehicle.reserved_junction and len(vehicle.route) > 1 and vehicle.route[1] == lane_id))]
        required_length = sum(vehicle.length+vehicle.minimum_gap+EXIT_SPACE_MARGIN for vehicle in occupying+[entering])
        return required_length <= self.network.lanes[lane_id].length

    def _reserve(self, vehicle: Vehicle, node: str, approach: str):
        self.reservations.setdefault(node, set()).add(vehicle.id)
        self.reservation_approach[node] = approach
        vehicle.reserved_junction = node
        # Time stuck in the junction counts from commitment, not from the red wait before it.
        vehicle.stopped_for = 0.0

    def _release(self, vehicle: Vehicle):
        node = vehicle.reserved_junction
        occupants = self.reservations.get(node, set())
        occupants.discard(vehicle.id)
        if not occupants:
            self.reservations.pop(node, None)
            self.reservation_approach.pop(node, None)
        vehicle.reserved_junction = None

    def _junction_open_to(self, node: str, approach: str, signal: Signal):
        """Signalized junctions admit more vehicles only from the approach already inside; stop control admits one."""
        if node not in self.reservations:
            return True
        return signal.mode == "signalized" and self.reservation_approach.get(node) == approach

    def _turn_angle(self, incoming: str, outgoing: str) -> float:
        """Signed heading change in degrees, in (-180, 180]; positive for a left (counter-clockwise) turn."""
        key = (incoming, outgoing)
        if key not in self._turn_angle_cache:
            self._turn_angle_cache[key] = self._measure_turn_angle(incoming, outgoing)
        return self._turn_angle_cache[key]

    def _measure_turn_angle(self, incoming: str, outgoing: str) -> float:
        entry, exit_lane = self.network.lanes[incoming], self.network.lanes[outgoing]
        (ax, ay), (bx, by) = entry.shape[-2], entry.shape[-1]
        (cx, cy), (dx, dy) = exit_lane.shape[0], exit_lane.shape[1]
        turn = (math.degrees(math.atan2(dy-cy, dx-cx)-math.atan2(by-ay, bx-ax))+180) % 360-180
        return 180.0 if turn == -180 else turn

    def _movement_speed(self, incoming: str, outgoing: str):
        """Through movements keep road speed; turns slow to the turning speed."""
        entry, exit_lane = self.network.lanes[incoming], self.network.lanes[outgoing]
        turn = abs(self._turn_angle(incoming, outgoing))
        return min(entry.speed, exit_lane.speed) if turn <= THROUGH_ANGLE_DEGREES else TURN_SPEED_MPS

    def _progress(self, vehicle: Vehicle) -> float:
        """Distance past the stop line along the vehicle's path; larger is further along."""
        if vehicle.connector is not None:
            return vehicle.connector_position
        return vehicle.position-self.network.lanes[vehicle.route[0]].length

    def _exit_lateral(self, vehicle: Vehicle) -> float:
        """Where the vehicle joins its exit lane: its own sideways position, limited to that lane's width."""
        if vehicle.connector is not None:
            return vehicle.connector_exit_lateral
        low, high = lateral_bounds(self.network.lanes[vehicle.route[1]].width, vehicle.width)
        return min(high, max(low, vehicle.lateral))

    def _paths_merge(self, a: Vehicle, b: Vehicle) -> bool:
        """Same movement and joining the exit lane too close abreast (clamping never moves two positions apart), or the
        same turning movement: on a tight curve bodies abreast at slightly different headings can touch, so turns go
        single file."""
        if len(a.route) < 2 or a.route[:2] != b.route[:2]:
            return False
        turning = abs(self._turn_angle(a.route[0], a.route[1])) > THROUGH_ANGLE_DEGREES
        return turning or bands_overlap(self._exit_lateral(a), a.width, self._exit_lateral(b), b.width)

    def _paths_cross(self, a: Vehicle, b: Vehicle) -> bool:
        """Different exits, and the vehicle turning more to the left starts further right (or the reverse)."""
        if len(a.route) < 2 or len(b.route) < 2 or a.route[1] == b.route[1]:
            return False
        start_a = a.connector_entry_lateral if a.connector is not None else a.lateral
        start_b = b.connector_entry_lateral if b.connector is not None else b.lateral
        return (self._turn_angle(a.route[0], a.route[1])-self._turn_angle(b.route[0], b.route[1]))*(start_a-start_b) > 0

    def _beside(self, a: Vehicle, b: Vehicle) -> bool:
        return abs(self._progress(a)-self._progress(b)) < (a.length+b.length)/2+max(a.minimum_gap, b.minimum_gap)

    def _crossing_order(self, vehicle: Vehicle) -> tuple:
        return (math.inf if vehicle.stop_arrival is None else vehicle.stop_arrival, -(self._progress(vehicle)+vehicle.length/2), vehicle.id)

    def _must_wait_at_line(self, vehicle: Vehicle) -> bool:
        """Fixed order between vehicles of one approach whose paths merge or cross, so none waits for another in the junction."""
        node = self.network.lanes[vehicle.route[0]].target
        own_order = (math.inf if vehicle.stop_arrival is None else vehicle.stop_arrival, vehicle.id)
        for other in self._candidates(("turning_off", vehicle.route[0]), ("on_lane", vehicle.route[0])):
            if other is vehicle or other.route[0] != vehicle.route[0] or len(other.route) < 2:
                continue
            # A vehicle commits while still moving and then skips the line, so committed counts as already inside.
            inside_or_committed = other.connector is not None or other.reserved_junction == node
            if self._paths_cross(vehicle, other):
                # Crossing paths go through one at a time: once both are inside, each body can stand in the other's next
                # step, so a gap at the line does not keep them apart. Order: first stopped at the line, then front first.
                must_wait = inside_or_committed or self._crossing_order(other) < self._crossing_order(vehicle)
            else:
                ahead_in_order = other.connector is None and other.stop_arrival is not None and (other.stop_arrival, other.id) < own_order
                must_wait = ((inside_or_committed and self._beside(vehicle, other)) or ahead_in_order) and self._paths_merge(vehicle, other)
            # An uncommitted vehicle whose path this one stands in waits for it (_sweep_blocked), so this one goes first.
            if must_wait and (inside_or_committed or not self._stands_in_path(vehicle, other)):
                return True
        return False

    def _connector_lateral(self, vehicle: Vehicle, connector_length: float, connector_position: float | None = None) -> float:
        share = min(1.0, max(0.0, (vehicle.connector_position if connector_position is None else connector_position)/connector_length))
        return vehicle.connector_entry_lateral+(vehicle.connector_exit_lateral-vehicle.connector_entry_lateral)*share

    def _junction_pool(self, vehicle: Vehicle) -> list[Vehicle]:
        node = self.network.lanes[vehicle.route[0]].target
        lookups = [("turning_off", lane) for lane in self.network.incoming[node]]
        if len(vehicle.route) > 1:
            lookups.append(("on_lane", vehicle.route[1]))
        return [other for other in self._candidates(*lookups) if other is not vehicle and (
            other.connector is not None and self.network.lanes[other.route[0]].target == node
            or other.connector is None and len(vehicle.route) > 1 and other.route[0] == vehicle.route[1])]

    @staticmethod
    def _same_movement_behind(a: Vehicle, b: Vehicle) -> bool:
        """True when a and b are on the same movement inside the junction and a is behind b along the path."""
        return (a.connector is not None and b.connector is not None and a.route[:2] == b.route[:2]
                and (a.connector_position, a.id) < (b.connector_position, b.id))

    def _junction_gap(self, vehicle: Vehicle, connector_length: float) -> tuple[float, float]:
        """Gap to the nearest vehicle ahead in the junction or at the start of the exit lane, and its speed."""
        gap, leader_speed = math.inf, vehicle.speed
        x, y, heading = self._pose(vehicle)
        for other in self._junction_pool(vehicle):
            if self._same_movement_behind(other, vehicle):
                continue  # it yields to this vehicle, so this vehicle never waits for it
            if self._same_movement_behind(vehicle, other):
                # Same path, other ahead: follow it along the path when the bands are close; beside it, the footprint
                # check alone keeps the bodies apart on a curve.
                if not (self._paths_merge(vehicle, other) or bands_overlap(vehicle.lateral, vehicle.width, other.lateral, other.width)):
                    continue
                candidate = other.connector_position-(other.length+vehicle.length)/2-vehicle.connector_position
            else:
                # Judged in this vehicle's own frame: ahead along its heading and within its sideways band.
                other_x, other_y, _ = self._pose(other)
                dx, dy = other_x-x, other_y-y
                along, across = dx*math.cos(heading)+dy*math.sin(heading), dx*math.sin(heading)-dy*math.cos(heading)
                other_length, other_width = self._box(other)
                if along <= 0 or abs(across) >= (vehicle.width+other_width)/2+SIDE_CLEARANCE_M:
                    continue
                candidate = along-(vehicle.length+other_length)/2
            if candidate < gap:
                gap, leader_speed = candidate, other.speed
        return gap, leader_speed

    def _clear_travel(self, vehicle: Vehicle, travel: float, connector_length: float) -> float:
        """Last-resort footprint check: the longest of travel, travel/2 ... travel/16 that overlaps nobody, else 0."""
        if travel <= 0:
            return 0.0
        pool = self._junction_pool(vehicle)
        # Bodies farther than any tried position can reach are skipped: the centre moves at most travel along the
        # path plus the change of the sideways offset, which is at most twice the larger offset.
        x, y, _ = self._pose(vehicle)
        reach = travel+2*max(abs(vehicle.connector_entry_lateral), abs(vehicle.connector_exit_lateral))+math.hypot(vehicle.length, vehicle.width)/2+1.0
        bodies = []
        for other in pool:
            other_x, other_y, other_heading = self._pose(other)
            if math.hypot(other_x-x, other_y-y) > reach+math.hypot(other.length, other.width)/2:
                continue
            bodies.append(rectangle(other_x, other_y, other_heading, other.length, other.width))
        for step in (travel, travel/2, travel/4, travel/8, travel/16):
            position = vehicle.connector_position+step
            x, y, heading = sample(vehicle.connector, position)
            lateral = self._connector_lateral(vehicle, connector_length, position)
            body = rectangle(x+math.sin(heading)*lateral, y-math.cos(heading)*lateral, heading, vehicle.length, vehicle.width)
            if not any(rectangles_overlap(body, other) for other in bodies):
                return step
        return 0.0

    def _advance(self, vehicle: Vehicle, gap: float, leader_speed: float, desired_speed: float):
        """IDM step with the driver's own values; travel never closes the gap below its minimum gap. Returns the distance
        to move, which the footprint checks may still shorten before _record_motion counts it."""
        gap = max(0.01, gap)
        desired_gap = vehicle.minimum_gap + max(0.0, vehicle.speed*vehicle.time_headway + vehicle.speed*(vehicle.speed-leader_speed)/(2*math.sqrt(vehicle.max_acceleration*COMFORTABLE_DECELERATION)))
        acceleration = vehicle.max_acceleration*(1-(vehicle.speed/desired_speed)**4-(desired_gap/gap)**2)
        next_speed = max(0.0, min(desired_speed, vehicle.speed+max(-4.5, acceleration)*STEP_LENGTH))
        travel = min(next_speed*STEP_LENGTH, max(0.0, gap-vehicle.minimum_gap))
        vehicle.speed = travel/STEP_LENGTH
        return travel

    def _record_motion(self, vehicle: Vehicle, travel: float) -> None:
        """Movement and stopped-time accounting for the distance the vehicle really moved this tick."""
        vehicle.speed = travel/STEP_LENGTH
        if travel > 0:
            self.last_vehicle_movement = self.simulation_time
        if vehicle.speed <= 0.1:
            vehicle.wait += STEP_LENGTH
            vehicle.stopped_for += STEP_LENGTH
            # On a connector lane_id is still the incoming lane, so junction-internal stops count for that approach.
            self.lane_stopped_seconds[vehicle.route[0]] += STEP_LENGTH
        else:
            vehicle.stopped_for = 0.0

    def _lane_obstacle(self, vehicle: Vehicle, lane) -> tuple[Vehicle | None, float, float]:
        """(leader, obstacle position, leader speed): the nearest vehicle ahead whose sideways band overlaps this one's."""
        length_self, width_self = self._box(vehicle)
        # One pass keeping the overlapping vehicle with the nearest rear (the first such in candidate order on ties): a
        # short vehicle's centre can be nearer than a long one's while its rear is farther. A band is only tested for a
        # vehicle whose rear is nearer than the current leader's.
        leader, obstacle = None, math.inf
        position, lateral = vehicle.position, vehicle.lateral
        # With the tick index every vehicle in the bucket is on this lane, so only the full scan needs the lane test.
        index = self._tick_index
        scanning_all = index is None
        for other in (self._candidates() if scanning_all else index["on_lane"].get(vehicle.route[0], ())):
            if other.position <= position or other is vehicle:
                continue
            other_length, other_width = (other.length, other.width) if other.yaw == 0 else self._box(other)
            candidate = other.position-(other_length+length_self)/2
            if candidate >= obstacle or scanning_all and (other.connector is not None or other.route[0] != vehicle.route[0]):
                continue
            # A vehicle already alongside (lengthways overlap) is only followed if the bodies' bands really overlap: inside
            # the side clearance it is beside this one, not ahead, and holding back for it can lock both for good.
            alongside = candidate < position
            if bands_overlap(lateral, width_self, other.lateral, other_width, 0.0 if alongside else SIDE_CLEARANCE_M):
                leader, obstacle = other, candidate
        leader_speed = leader.speed if leader else vehicle.speed
        # A vehicle that has just turned off this lane is still ahead of followers in its band, or whose path it merges with.
        for other in (self._candidates() if scanning_all else index["turning_off"].get(vehicle.route[0], ())):
            if other.connector is None or other.route[0] != vehicle.route[0]:
                continue
            connector_obstacle = lane.length+other.connector_position-(other.length+length_self)/2
            if connector_obstacle < obstacle and (bands_overlap(vehicle.lateral, width_self, other.lateral, other.width)
                                                  or self._paths_merge(vehicle, other)):
                obstacle, leader_speed = connector_obstacle, other.speed
        return leader, obstacle, leader_speed

    def _turn_side(self, incoming: str, outgoing: str) -> int:
        """-1 for a left turn (prefer the centre-line side), +1 for a right turn (the kerb side), 0 for through."""
        turn = self._turn_angle(incoming, outgoing)
        return -1 if turn > THROUGH_ANGLE_DEGREES else 1 if turn < -THROUGH_ANGLE_DEGREES else 0

    def _lateral_speed_limit(self, vehicle: Vehicle) -> float:
        """Sideways speed allowed now: forward speed x tan 10 degrees, plus a slow motorcycle shuffle, within the class limit."""
        shuffle = MOTORCYCLE_SHUFFLE_MPS if vehicle.vehicle_type == "motorcycle" else 0.0
        return min(vehicle.max_lateral_speed, max(vehicle.speed*TAN_MAX_YAW, shuffle))

    def _lane_neighbours(self, vehicle: Vehicle, lane) -> list[tuple[float, float, float, float]]:
        """(centre position, lateral, along-road length, across-road width) of every other body sharing this lane:
        vehicles on it, vehicles turning off it (ahead of the line) and vehicles arriving on it from the junction."""
        result = []
        # Every use of this list is order-free (sorted or any()), so the index buckets are read one after another.
        if self._tick_index is None:
            others = self._candidates()
        else:
            others = [other for name in ("on_lane", "turning_off", "next_lane") for other in self._tick_index[name].get(lane.id, ())]
        for other in others:
            if other is vehicle:
                continue
            if other.connector is None and other.route[0] == lane.id:
                other_length, other_width = self._box(other)
                result.append((other.position, other.lateral, other_length, other_width))
            elif other.connector is not None and other.route[0] == lane.id:
                result.append((lane.length+other.connector_position, other.lateral, other.length, other.width))
            elif other.connector is not None and len(other.route) > 1 and other.route[1] == lane.id:
                result.append((other.connector_position-length(other.connector), other.connector_exit_lateral, other.length, other.width))
        return result

    def _may_proceed_now(self, vehicle: Vehicle, lane) -> bool:
        if lane.target not in self.signals or len(vehicle.route) < 2 or vehicle.reserved_junction == lane.target:
            return True
        signal = self.signals[lane.target]
        return signal.mode == "signalized" and signal.stage == "green" and signal.family == lane.approach

    def _rears_ahead(self, vehicle: Vehicle, neighbours) -> list[tuple[float, float, float]]:
        """(rear, lateral, width) of neighbours ahead of the vehicle, nearest rear first."""
        return sorted((position-other_length/2, other_lateral, other_width)
                      for position, other_lateral, other_length, other_width in neighbours if position > vehicle.position)

    def _lateral_room(self, vehicle: Vehicle, lane, lateral: float, neighbours=None, rears=None, cap=None) -> float:
        """Free distance ahead of the vehicle's front in the band at `lateral`, up to the room horizon."""
        length_self, width_self = self._box(vehicle)
        front = vehicle.position+length_self/2
        if cap is None:
            cap = ROOM_HORIZON_M if self._may_proceed_now(vehicle, lane) else min(ROOM_HORIZON_M, lane.length-front)
        if rears is None:
            rears = self._rears_ahead(vehicle, self._lane_neighbours(vehicle, lane) if neighbours is None else neighbours)
        # The first overlapping rear in rear order is the nearest obstacle in this band.
        room = next((rear-front for rear, other_lateral, other_width in rears if bands_overlap(lateral, width_self, other_lateral, other_width)), cap)
        return max(0.0, min(cap, room))

    def _side_clear(self, vehicle: Vehicle, lane, start: float, end: float, neighbours=None) -> bool:
        """Planning check with full clearances: nothing alongside in the band swept from start to end."""
        length_self, width_self = self._box(vehicle)
        low, high = min(start, end)-width_self/2, max(start, end)+width_self/2
        for position, other_lateral, other_length, other_width in (self._lane_neighbours(vehicle, lane) if neighbours is None else neighbours):
            alongside = abs(position-vehicle.position) < (length_self+other_length)/2+0.5
            band_low, band_high = other_lateral-other_width/2-SIDE_CLEARANCE_M, other_lateral+other_width/2+SIDE_CLEARANCE_M
            if alongside and band_low < high and low < band_high:
                return False
        return True

    def _decide_lateral(self, vehicle: Vehicle, lane) -> None:
        """Periodically pick the sideways position with the most room to advance, net of moving and keeping costs."""
        serial = vehicle_serial(vehicle.id)
        if ((self.ticks+serial) % LATERAL_DECISION_TICKS or vehicle.lateral != vehicle.lateral_target
                or self.simulation_time < vehicle.lateral_cooldown_until or self._lateral_speed_limit(vehicle) <= 0
                or vehicle.reserved_junction == lane.target):
            return
        neighbours = self._lane_neighbours(vehicle, lane)
        front = vehicle.position+self._box(vehicle)[0]/2
        cap = ROOM_HORIZON_M if self._may_proceed_now(vehicle, lane) else min(ROOM_HORIZON_M, lane.length-front)
        low, high = lateral_bounds(lane.width, vehicle.width)
        turn_side = self._turn_side(lane.id, vehicle.route[1]) if len(vehicle.route) > 1 else 0
        near_line = lane.length-(vehicle.position+vehicle.length/2) <= TURN_SIDE_DISTANCE_M
        # With full room ahead, at its keeping position and no turn-side pull, no candidate can gain the threshold.
        keep_here = keeping_position(vehicle.vehicle_type, vehicle.width, lane.width, lane.lane_count, sub_lane_of(vehicle.lateral, lane.width, lane.lane_count))
        if not (turn_side and near_line) and (keep_here is None or keep_here == vehicle.lateral):
            # Nothing can beat the current position when it already has all the room the line allows, or when its
            # nearest obstacle also blocks the bands at both lane edges (and so every candidate band between them).
            # The smallest overlapping (rear, lateral, width) is the first overlapping one in rear order.
            width_self = self._box(vehicle)[1]
            nearest = min(((position-other_length/2, other_lateral, other_width)
                           for position, other_lateral, other_length, other_width in neighbours
                           if position > vehicle.position and bands_overlap(vehicle.lateral, width_self, other_lateral, other_width)), default=None)
            if nearest is None or nearest[0]-front >= cap:
                return
            if all(bands_overlap(edge, width_self, nearest[1], nearest[2]) for edge in (low, high)):
                return
        rears = self._rears_ahead(vehicle, neighbours)

        def score(lateral):
            value = self._lateral_room(vehicle, lane, lateral, rears=rears, cap=cap)-MOVE_COST_PER_M*abs(lateral-vehicle.lateral)
            keep = keeping_position(vehicle.vehicle_type, vehicle.width, lane.width, lane.lane_count, sub_lane_of(lateral, lane.width, lane.lane_count))
            if keep is not None:
                value -= KEEPING_WEIGHT_PER_M*abs(lateral-keep)
            if turn_side and near_line:
                value -= TURN_SIDE_WEIGHT_PER_M*abs(lateral-(low if turn_side < 0 else high))
            return value
        scores = {lateral: score(lateral) for lateral in candidate_laterals(lane.width, vehicle.width)}
        best = max(scores, key=lambda lateral: (scores[lateral], -abs(lateral-vehicle.lateral)))
        current = scores[vehicle.lateral] if vehicle.lateral in scores else score(vehicle.lateral)
        if best != vehicle.lateral and scores[best] >= current+MOVE_GAIN_THRESHOLD_M and self._side_clear(vehicle, lane, vehicle.lateral, best, neighbours):
            vehicle.lateral_target = best

    def _turned_step_fits(self, vehicle: Vehicle, lane, lateral: float, yaw: float, neighbours, sweeps=()) -> bool:
        """The body turned by yaw at lateral stays on the road, touches no neighbour alongside it and enters no sweep."""
        along, across = body_box(vehicle.length, vehicle.width, yaw)
        low, high = lateral_bounds(lane.width, across, edge_clearance=0)
        if not low-1e-9 <= lateral <= high+1e-9:
            return False
        if any(abs(position-vehicle.position) < (along+other_length)/2 and bands_overlap(lateral, across, other_lateral, other_width, clearance=0)
               for position, other_lateral, other_length, other_width in neighbours):
            return False
        return not sweeps or not self._hits_sweep(self._lane_body(vehicle, lane, vehicle.position, lateral, yaw), sweeps)

    def _sweep_for(self, vehicle: Vehicle, entry_lateral: float, exit_lateral: float) -> list:
        """The vehicle's drawn bodies along its whole connector, sampled every SWEEP_SAMPLE_M (cached: pure geometry)."""
        key = (vehicle.route[0], vehicle.route[1], entry_lateral, exit_lateral, vehicle.length, vehicle.width)
        if key not in self._sweep_cache:
            self._sweep_cache[key] = self._build_sweep(vehicle.route[0], vehicle.route[1], entry_lateral, exit_lateral, vehicle.length, vehicle.width)
        return self._sweep_cache[key]

    def _build_sweep(self, incoming: str, outgoing: str, entry_lateral: float, exit_lateral: float, body_length: float, body_width: float) -> list:
        connector = self.network.connector(incoming, outgoing)
        total = length(connector)
        # Samples every SWEEP_SAMPLE_M plus each vertex once per adjoining heading, so any point on the path lies
        # within half a spacing of a sample with the same heading; growing each body by half a spacing along and by
        # the sideways drift over half a spacing then covers every body in between exactly.
        poses = [(index*SWEEP_SAMPLE_M, sample(connector, index*SWEEP_SAMPLE_M)[2]) for index in range(int(total/SWEEP_SAMPLE_M)+1)]
        poses.append((total, sample(connector, total)[2]))
        travelled, previous_heading = 0.0, None
        for a, b in zip(connector, connector[1:]):
            segment_length = math.dist(a, b)
            if segment_length < 1e-8:
                continue
            heading = math.atan2(b[1]-a[1], b[0]-a[0])
            if previous_heading is not None:
                poses += [(travelled, previous_heading), (travelled, heading)]
            travelled, previous_heading = travelled+segment_length, heading
        drift = abs(exit_lateral-entry_lateral)/total*SWEEP_SAMPLE_M/2
        samples = []
        for point, heading in sorted(poses):
            x, y, _ = sample(connector, point)
            lateral = entry_lateral+(exit_lateral-entry_lateral)*point/total
            corners = rectangle(x+math.sin(heading)*lateral, y-math.cos(heading)*lateral, heading,
                                body_length+SWEEP_SAMPLE_M, body_width+2*drift)
            xs, ys = [corner[0] for corner in corners], [corner[1] for corner in corners]
            samples.append((point, corners, (min(xs), min(ys), max(xs), max(ys))))
        return samples

    def stop_line(self, lane_id: str) -> float:
        """Path position on the lane where its vehicles stop for the junction ahead."""
        key = (self.network.fingerprint, lane_id)
        if key not in _STOP_SETBACKS:
            _STOP_SETBACKS[key] = self._stop_setback(self.network.lanes[lane_id])
        return self.network.lanes[lane_id].length-_STOP_SETBACKS[key]

    def _stop_setback(self, lane) -> float:
        """Smallest distance back from the lane end at which a body across the lane's whole width, up to
        STOP_SETBACK_DEPTH_M deep, clears the path of every class turning from another approach at its
        kerb-side, centre-line-side or central position."""
        node = lane.target
        if node not in self.network.intersections:
            return 0.0
        limit = lane.length/2

        def zone(setback: float, depth: float = STOP_SETBACK_DEPTH_M):
            x, y, heading = sample(lane.shape, max(0.0, lane.length-setback-depth/2))
            return rectangle(x, y, heading, depth, lane.width)

        reach = zone(0.0, limit+STOP_SETBACK_DEPTH_M)
        low_x, high_x = min(corner[0] for corner in reach), max(corner[0] for corner in reach)
        low_y, high_y = min(corner[1] for corner in reach), max(corner[1] for corner in reach)
        # Only bodies still overlapping the zone are tried again one step further back.
        bodies = [corners for incoming, corners, box in self._junction_turn_bodies(node)
                  if incoming != lane.id and box[0] < high_x and low_x < box[2] and box[1] < high_y and low_y < box[3]]
        setback = 0.0
        while setback < limit:
            area = zone(setback)
            bodies = [body for body in bodies if rectangles_overlap(area, body)]
            if not bodies:
                break
            setback += STOP_SETBACK_STEP_M
        return min(setback, limit)

    def _junction_turn_bodies(self, node: str) -> list:
        """[(incoming lane, corners, box)] along every allowed movement through the junction, for every class at its
        kerb-side, centre-line-side and central entry position (cached per network: pure geometry)."""
        key = (self.network.fingerprint, node)
        if key not in _JUNCTION_TURN_BODIES:
            bodies = []
            for incoming in self.network.incoming[node]:
                for outgoing in self.network.outgoing[node]:
                    if not self.network.turn_allowed(incoming, outgoing):
                        continue
                    for spec in VEHICLE_TYPES.values():
                        entry_low, entry_high = lateral_bounds(self.network.lanes[incoming].width, spec["width"])
                        exit_low, exit_high = lateral_bounds(self.network.lanes[outgoing].width, spec["width"])
                        for entry in {entry_low, entry_high, min(entry_high, max(entry_low, 0.0))}:
                            bodies += [(incoming, corners, box) for _, corners, box in self._build_sweep(
                                incoming, outgoing, entry, min(exit_high, max(exit_low, entry)), spec["length"], spec["width"])]
            _JUNCTION_TURN_BODIES[key] = bodies
        return _JUNCTION_TURN_BODIES[key]

    def _lane_body(self, vehicle: Vehicle, lane, position: float, lateral: float, yaw: float):
        x, y, heading = sample(lane.shape, position)
        return rectangle(x+math.sin(heading)*lateral, y-math.cos(heading)*lateral, heading-yaw, vehicle.length, vehicle.width)

    def _sweep_bounds(self, samples: list) -> tuple[float, float, float, float]:
        """Box around every sample of a cached sweep; a body outside it cannot touch any part of that sweep."""
        entry = self._sweep_bounds_cache.get(id(samples))
        if entry is None or entry[0] is not samples:
            boxes = [box for _, _, box in samples]
            entry = (samples, (min(box[0] for box in boxes), min(box[1] for box in boxes), max(box[2] for box in boxes), max(box[3] for box in boxes)))
            self._sweep_bounds_cache[id(samples)] = entry
        return entry[1]

    @staticmethod
    def _hits_sweep(body, sweeps) -> bool:
        """sweeps: (samples, progress, bounds); only samples at or beyond progress count."""
        xs, ys = [corner[0] for corner in body], [corner[1] for corner in body]
        low_x, low_y, high_x, high_y = min(xs), min(ys), max(xs), max(ys)
        return any(bounds[0] < high_x and low_x < bounds[2] and bounds[1] < high_y and low_y < bounds[3]
                   and any(point >= progress and box[0] < high_x and low_x < box[2] and box[1] < high_y and low_y < box[3]
                           and rectangles_overlap(body, corners) for point, corners, box in samples)
                   for samples, progress, bounds in sweeps)

    def _near_line(self, vehicle: Vehicle, lane, position: float) -> bool:
        return lane.target in self.signals and lane.length-(position+vehicle.length/2) <= SWEEP_ZONE_M

    def _committed_sweeps(self, vehicle: Vehicle, lane) -> list:
        """Remaining sweeps of vehicles from other approaches committed to (or inside) the junction ahead."""
        result = []
        for identity, samples in self._sweeps.items():
            other = self.vehicles.get(identity)
            if other is None or other.route[0] == lane.id or self.network.lanes[other.route[0]].target != lane.target:
                continue
            progress = other.connector_position-other.length if other.connector is not None else -math.inf
            result.append((samples, progress, self._sweep_bounds(samples)))
        return result

    def _stands_in_path(self, stander: Vehicle, mover: Vehicle) -> bool:
        """True when stander, on a lane near its stop line, is hit by the path mover would take through the junction."""
        stander_lane = self.network.lanes[stander.route[0]]
        if stander.connector is not None or not self._near_line(stander, stander_lane, stander.position):
            return False
        sweep = self._sweep_for(mover, mover.lateral, self._exit_lateral(mover))
        return self._hits_sweep(self._lane_body(stander, stander_lane, stander.position, stander.lateral, stander.yaw),
                                [(sweep, -math.inf, self._sweep_bounds(sweep))])

    def _sweep_blocked(self, vehicle: Vehicle, node: str) -> bool:
        """True when this vehicle's path through the junction would hit a vehicle standing near a stop line, including
        one beside it on its own approach (where a committed vehicle ahead is about to drive off, so it does not count)."""
        return any(other is not vehicle and other.route[0] == lane_id and self._stands_in_path(other, vehicle)
                   and not (lane_id == vehicle.route[0] and other.reserved_junction == node)
                   for lane_id in self.network.incoming[node] for other in self._candidates(("on_lane", lane_id)))

    def _meets_own_approach_path(self, vehicle: Vehicle) -> bool:
        """True when this vehicle's path through the junction meets the rest of the recorded path of a committed vehicle
        from its own approach bound for another exit: a path drifting sideways towards its exit can cross one that
        started beside it, and once both are inside each body can stand in the other's next step."""
        own = None
        for identity, samples in self._sweeps.items():
            other = self.vehicles.get(identity)
            if other is None or other is vehicle or other.route[0] != vehicle.route[0] or other.route[1] == vehicle.route[1]:
                continue
            if own is None:
                own = self._sweep_for(vehicle, vehicle.lateral, self._exit_lateral(vehicle))
                own_bounds = self._sweep_bounds(own)
            bounds = self._sweep_bounds(samples)
            if not (bounds[0] < own_bounds[2] and own_bounds[0] < bounds[2] and bounds[1] < own_bounds[3] and own_bounds[1] < bounds[3]):
                continue
            progress = other.connector_position-other.length if other.connector is not None else -math.inf
            if any(point >= progress and self._hits_sweep(corners, [(own, -math.inf, own_bounds)]) for point, corners, _ in samples):
                return True
        return False

    def _sweep_clear_travel(self, vehicle: Vehicle, lane, travel: float) -> float:
        """Near the stop line, the longest of travel, travel/2 ... travel/16 that keeps out of committed sweeps, else 0."""
        if travel <= 0 or not self._sweeps or not self._near_line(vehicle, lane, vehicle.position+travel):
            return travel
        sweeps = self._committed_sweeps(vehicle, lane)
        if not sweeps:
            return travel
        for step in (travel, travel/2, travel/4, travel/8, travel/16):
            if not self._hits_sweep(self._lane_body(vehicle, lane, vehicle.position+step, vehicle.lateral, vehicle.yaw), sweeps):
                return step
        return 0.0

    def _step_lateral(self, vehicle: Vehicle, lane) -> None:
        """Move toward the target this tick with the turned body as drawn; shorten a step that touches anyone or leaves the road."""
        if vehicle.lateral == vehicle.lateral_target:
            vehicle.yaw = vehicle.lateral_speed = 0.0
            return
        remaining = vehicle.lateral_target-vehicle.lateral
        full = min(self._lateral_speed_limit(vehicle)*STEP_LENGTH, abs(remaining))
        neighbours = self._lane_neighbours(vehicle, lane)
        sweeps = self._committed_sweeps(vehicle, lane) if self._sweeps and self._near_line(vehicle, lane, vehicle.position) else ()
        for fraction in (1, .5, .25, .125):
            step = math.copysign(full*fraction, remaining)
            if full <= 0:
                break
            lateral = vehicle.lateral+step
            full_yaw = math.copysign(min(math.atan2(abs(step)/STEP_LENGTH, vehicle.speed), math.radians(MAX_YAW_DEGREES)), step)
            # At the road edge the full turn would swing a corner off the road; a smaller turn (drawn as checked) may fit.
            yaw = next((yaw for yaw in (full_yaw, full_yaw/2, full_yaw/4, 0.0) if self._turned_step_fits(vehicle, lane, lateral, yaw, neighbours, sweeps)), None)
            if yaw is None:
                continue
            vehicle.lateral, vehicle.lateral_speed, vehicle.yaw = lateral, step/STEP_LENGTH, yaw
            if abs(vehicle.lateral_target-vehicle.lateral) <= 1e-9:
                vehicle.lateral = vehicle.lateral_target
                vehicle.yaw = vehicle.lateral_speed = 0.0
                vehicle.lateral_cooldown_until = self.simulation_time+MOVE_COOLDOWN_SECONDS
            return
        # No step fits: give up this move where the vehicle stands.
        vehicle.yaw = vehicle.lateral_speed = 0.0
        vehicle.lateral_target = vehicle.lateral
        vehicle.lateral_cooldown_until = self.simulation_time+MOVE_COOLDOWN_SECONDS

    def _stop_priority(self, vehicle: Vehicle, node: str):
        if vehicle.stop_arrival is None:
            return False
        # The turn goes to the first arrival that can go now: one held by a blocked exit or by a vehicle of its own
        # approach must not stop every approach. Settled once per junction and tick.
        if self._stop_turn[0] != self.ticks:
            self._stop_turn = (self.ticks, {})
        turns = self._stop_turn[1]
        if node not in turns:
            waiting = sorted((car for car in self.vehicles.values()
                              if car.stop_arrival is not None and not car.connector
                              and self.network.lanes[car.route[0]].target == node and len(car.route) > 1),
                             key=lambda car: (car.stop_arrival, car.id))
            turns[node] = next((car for car in waiting if car.route[1] not in self.closed_lanes and self._exit_has_space(car.route[1], car)
                                and not self._must_wait_at_line(car) and not self._sweep_blocked(car, node)), None)
        return turns[node] is vehicle and self.simulation_time-vehicle.stop_arrival >= 1.0


    def _reroute(self, vehicle: Vehicle):
        if vehicle.connector or len(vehicle.route) < 2 or vehicle.reserved_junction:
            return
        if self.simulation_time < vehicle.reroute_at:
            return
        route_blocked = any(lane in self.closed_lanes for lane in vehicle.route[1:])
        if not route_blocked and self.config["routing_mode"] == "static":
            return
        vehicle.reroute_at = self.simulation_time+self.config["reroute_interval"]
        current = self.network.lanes[vehicle.route[0]]
        costs = self._travel_costs()
        alternative = self.network.route(current.target, vehicle.destination, closed=self.closed_lanes, costs=costs, previous=current.id)
        if alternative and alternative != vehicle.route[1:]:
            current_cost = sum(costs[lane] for lane in vehicle.route[1:])
            alternative_cost = sum(costs[lane] for lane in alternative)
            if route_blocked or alternative_cost < current_cost*(1-self.config["reroute_improvement"]):
                vehicle.route = [current.id]+alternative
                self.reroutes += 1

    def _move_vehicle(self, vehicle: Vehicle):
        if vehicle.connector:
            connector_length = length(vehicle.connector)
            gap, leader_speed = self._junction_gap(vehicle, connector_length)
            desired_speed = self._movement_speed(vehicle.route[0], vehicle.route[1])*vehicle.speed_factor
            travel = self._advance(vehicle, gap, leader_speed, desired_speed)
            cleared = self._clear_travel(vehicle, travel, connector_length)
            self._record_motion(vehicle, cleared)
            vehicle.connector_position += cleared
            vehicle.lateral = self._connector_lateral(vehicle, connector_length)
            if vehicle.connector_position >= connector_length:
                vehicle.position = vehicle.connector_position-length(vehicle.connector)
                vehicle.connector, vehicle.route = None, vehicle.route[1:]
                vehicle.lateral = vehicle.lateral_target = vehicle.connector_exit_lateral
                self._sweeps.pop(vehicle.id, None)
                vehicle.stop_arrival = None
            return
        lane = self.network.lanes[vehicle.route[0]]
        has_left_junction = vehicle.position-vehicle.length/2 >= 0
        if vehicle.reserved_junction and lane.source == vehicle.reserved_junction and has_left_junction:
            self._release(vehicle)
        self._reroute(vehicle)
        self._decide_lateral(vehicle, lane)
        self._step_lateral(vehicle, lane)
        leader, obstacle, leader_speed = self._lane_obstacle(vehicle, lane)
        if lane.target in self.signals and len(vehicle.route) > 1 and vehicle.reserved_junction != lane.target:
            signal = self.signals[lane.target]
            outgoing = vehicle.route[1]
            stop_position = self.stop_line(lane.id)-vehicle.length/2
            if vehicle.position >= stop_position-1 and vehicle.speed <= .1 and vehicle.stop_arrival is None:
                vehicle.stop_arrival = self.simulation_time
            has_permission = self._stop_priority(vehicle, lane.target) if signal.mode == "all_way_stop" else signal.stage == "green" and signal.family == lane.approach
            may_proceed = (has_permission and self._junction_open_to(lane.target, lane.approach, signal)
                           and not self._crossing_occupied(lane.target) and outgoing not in self.closed_lanes
                           and self._exit_has_space(outgoing, vehicle) and not self._must_wait_at_line(vehicle))
            # Commit at the last point where a comfortable stop is still possible; until then a vehicle that may
            # proceed keeps moving instead of braking for the line, and it brakes gently if permission or space goes.
            commit_distance = vehicle.speed**2/(2*COMFORTABLE_DECELERATION)+vehicle.speed*STEP_LENGTH+EXIT_SPACE_MARGIN
            must_decide = stop_position-vehicle.position <= commit_distance
            # Never commit behind an uncommitted vehicle that could still be held at the line.
            clear_ahead = leader is None or leader.reserved_junction == lane.target
            # The sweep test is the costliest, so it runs only at the moment the vehicle would otherwise commit.
            if may_proceed and must_decide and clear_ahead and (self._sweep_blocked(vehicle, lane.target) or self._meets_own_approach_path(vehicle)):
                may_proceed = False
            if may_proceed and must_decide and clear_ahead:
                self._reserve(vehicle, lane.target, lane.approach)
                # A committed vehicle keeps its sideways position, so its recorded sweep is the path it will take.
                vehicle.lateral_target, vehicle.yaw, vehicle.lateral_speed = vehicle.lateral, 0.0, 0.0
                self._sweeps[vehicle.id] = self._sweep_for(vehicle, vehicle.lateral, self._exit_lateral(vehicle))
            elif not may_proceed and stop_position < obstacle:
                obstacle, leader_speed = stop_position+vehicle.minimum_gap, 0.0
        desired_speed = lane.speed*self.slow_lanes.get(lane.id, 1.0)*vehicle.speed_factor
        if vehicle.reserved_junction == lane.target:
            desired_speed = min(desired_speed, self._movement_speed(lane.id, vehicle.route[1])*vehicle.speed_factor)
        travel = self._advance(vehicle, obstacle-vehicle.position, leader_speed, desired_speed)
        cleared = self._sweep_clear_travel(vehicle, lane, travel)
        self._record_motion(vehicle, cleared)
        vehicle.position += cleared
        if vehicle.position >= lane.length:
            self.lane_exits[lane.id] += 1
            if len(vehicle.route) > 1:
                # Enter at the real sideways position (no jump at the line) and blend to the exit position.
                vehicle.connector_entry_lateral, vehicle.connector_exit_lateral = vehicle.lateral, self._exit_lateral(vehicle)
                vehicle.connector = self.network.connector(vehicle.route[0], vehicle.route[1])
                vehicle.connector_position = vehicle.position-lane.length
                vehicle.lateral = self._connector_lateral(vehicle, length(vehicle.connector))
            else:
                self.completed += 1
                self.lifetime_completed += 1
                self.completed_external_wait += vehicle.born-vehicle.requested_at
                self.completed_wait += vehicle.wait
                self.completed_travel += self.simulation_time+STEP_LENGTH-vehicle.born
                if vehicle.reserved_junction:
                    self._release(vehicle)
                del self.vehicles[vehicle.id]

    def _apply_scheduled_events(self):
        for index, event in enumerate(self.scheduled_events):
            if index in self.applied_events or self.simulation_time < event["time"]:
                continue
            if "closed" in event:
                self.close_lane(event["lane_id"], event["closed"])
            if "speed_factor" in event:
                if event["speed_factor"] == 1:
                    self.slow_lanes.pop(event["lane_id"], None)
                else:
                    self.slow_lanes[event["lane_id"]] = event["speed_factor"]
                self._add_event("constraint", f"Lane {event['lane_id']} speed factor {event['speed_factor']}")
            self.applied_events.add(index)

    def step(self, num_ticks: int = 1):
        if isinstance(num_ticks, bool) or not isinstance(num_ticks, int) or num_ticks < 0:
            raise ValueError("Tick count must be non-negative")
        for _ in range(num_ticks):
            if self.status != "running":
                break
            self._apply_scheduled_events()
            self._control_signals()
            for node, signal in self.signals.items():
                signal.step(STEP_LENGTH, self._crossing_occupied(node), self._pedestrians_waiting(node))
            self._step_pedestrians()
            # Front vehicles move first; followers are capped against the updated leader.
            self._build_tick_index()
            try:
                for vehicle in sorted(list(self.vehicles.values()), key=lambda car: (-car.position, car.id)):
                    on_lane, route = vehicle.connector is None, vehicle.route
                    old_keys = None
                    self._move_vehicle(vehicle)
                    if vehicle.route is not route or (vehicle.connector is None) != on_lane or self.vehicles.get(vehicle.id) is not vehicle:
                        old_keys = [("on_lane" if on_lane else "turning_off", route[0])]+([("next_lane", route[1])] if len(route) > 1 else [])
                        self._reindex(vehicle, old_keys)
            finally:
                self._tick_index = None
            self.ticks += 1
            self.simulation_time = round(self.ticks*STEP_LENGTH, 6)
            self._apply_scheduled_events()
            self._spawn_demand()
            self._refresh_metrics(record=True)
            if self.simulation_time >= self.duration_limit:
                self.status = "completed"
                self._add_event("run", "Simulation duration completed")

    def _lane_queues(self):
        result = dict.fromkeys(self.network.lanes, 0)
        for vehicle in self.vehicles.values():
            if not vehicle.connector and vehicle.speed <= 0.1:
                result[vehicle.route[0]] += 1
        return result

    def _blocked_on_green(self, vehicle: Vehicle):
        """Stopped at its stop line while its own approach may go: it waits only for downstream space."""
        if vehicle.connector or vehicle.stop_arrival is None or len(vehicle.route) < 2:
            return False
        lane = self.network.lanes[vehicle.route[0]]
        signal = self.signals.get(lane.target)
        if signal is None:
            return False
        has_green = signal.mode == "signalized" and signal.stage == "green" and signal.family == lane.approach
        return has_green or signal.mode == "all_way_stop"

    def _gridlock_seconds(self):
        """Time with no vehicle movement while someone holds a green; normal red waits do not count."""
        stalled_seconds = self.simulation_time-self.last_vehicle_movement
        if not self.vehicles or stalled_seconds < GRIDLOCK_SECONDS:
            return 0.0
        return stalled_seconds if any(self._blocked_on_green(vehicle) for vehicle in self.vehicles.values()) else 0.0

    def _queue_reaches(self) -> dict[str, float]:
        """Lane -> distance from its stop line to the rear of the farthest stopped vehicle (0 when none)."""
        reaches = dict.fromkeys(self.network.lanes, 0.0)
        for vehicle in self.vehicles.values():
            if not vehicle.connector and vehicle.speed <= 0.1:
                lane = self.network.lanes[vehicle.route[0]]
                reaches[lane.id] = max(reaches[lane.id], self.stop_line(lane.id)-(vehicle.position-vehicle.length/2))
        return reaches

    def _queue_reach(self, lane_id: str) -> float:
        return self._queue_reaches()[lane_id]

    @property
    def _last_metrics(self) -> dict:
        if self._metrics_pending:
            self._metrics_pending = False
            self._metrics_snapshot = self._build_metrics()
        return self._metrics_snapshot

    @_last_metrics.setter
    def _last_metrics(self, value: dict):
        self._metrics_pending, self._metrics_snapshot = False, value

    def _refresh_metrics(self, record: bool = False):
        """Accumulate the per-tick measures now. The full metrics depend only on the state, so they are built from it
        when first read; public methods that change state between ticks build them first (_settle_metrics)."""
        if record:
            queues = self._lane_queues()
            incoming = [lane for lane in self.network.lanes.values() if lane.target in self.signals]
            self.metric_ticks += 1
            self.queue_integral += sum(queues[lane.id] for lane in incoming)/max(1, len(incoming))
            self.max_queue = max(self.max_queue, max(queues.values(), default=0))
            if self.ticks % 10 == 0:
                average_wait = (self.completed_wait + sum(vehicle.wait for vehicle in self.vehicles.values()))/max(1, self.completed+len(self.vehicles))
                for key, value in (("traffic_flow", len(self.vehicles)), ("wait_time", average_wait), ("queue_length", sum(queues.values())), ("throughput", self.completed)):
                    self.charts[key].append({"time": self.simulation_time, "value": value})
                    self.charts[key] = self.charts[key][-300:]
        self._metrics_pending = True

    def _settle_metrics(self):
        """Build pending metrics from the state they describe, before a public method changes that state."""
        self._last_metrics

    def _build_metrics(self) -> dict:
        queues = self._lane_queues()
        reaches = self._queue_reaches()
        wait = self.completed_wait + sum(vehicle.wait for vehicle in self.vehicles.values())
        ped_wait = self.completed_pedestrian_wait + sum(pedestrian.wait for pedestrian in self.pedestrians.values())
        approaches = {approach: sum(queues[lane] for lane in self.network.incoming[self.controlled_junction] if self.network.lanes[lane].approach == approach) for approach in APPROACHES}
        metrics = {"avg_wait": wait/max(1, self.completed+len(self.vehicles)), "avg_queue": self.queue_integral/max(1, self.metric_ticks), "max_queue": self.max_queue, "throughput": self.completed, "avg_ped_delay": ped_wait/max(1, self.completed_pedestrians+len(self.pedestrians)), "avg_travel_time": self.completed_travel/max(1, self.completed), "total_vehicles_spawned": self.vehicle_serial, "total_vehicles_completed": self.completed, "total_pedestrians_spawned": self.pedestrian_serial, "total_pedestrians_completed": self.completed_pedestrians, "active_vehicle_count": len(self.vehicles), "active_pedestrian_count": len(self.pedestrians), "queue_by_approach": approaches, "queue_by_lane": queues, "pending_demand": len(self.pending_demand), "deferred_demand": self.deferred_demand, "reroutes": self.reroutes, "step_count": self.metric_ticks}
        lane_counts = dict.fromkeys(self.network.lanes, 0)
        lane_speeds = dict.fromkeys(self.network.lanes, 0.0)
        for vehicle in self.vehicles.values():
            if not vehicle.connector:
                lane_counts[vehicle.route[0]] += 1
                lane_speeds[vehicle.route[0]] += vehicle.speed
        elapsed = self.simulation_time-self.measurement_start
        external_wait = self.completed_external_wait + sum(v.born-v.requested_at for v in self.vehicles.values())
        metrics.update({
            "policy_decisions": self.policy_decisions, "safety_overrides": self.safety_overrides,
            "measurement_start": self.measurement_start, "measurement_seconds": elapsed,
            "lifetime_completed": self.lifetime_completed,
            "requested_vehicles": self.requested_vehicles, "scheduled_vehicles": len(self.arrivals),
            "dropped_vehicles": self.deferred_demand, "unfinished_vehicles": len(self.vehicles)+len(self.pending_demand),
            "vehicle_conservation_error": self.requested_vehicles-self.lifetime_completed-len(self.vehicles)-len(self.pending_demand)-self.deferred_demand,
            "pedestrian_conservation_error": self.pedestrian_serial-self.lifetime_pedestrians_completed-len(self.pedestrians)-self.dropped_pedestrians,
            "dropped_pedestrians": self.dropped_pedestrians,
            "stuck_junction_vehicles": sum(1 for vehicle in self.vehicles.values() if vehicle.reserved_junction and vehicle.stopped_for > STUCK_IN_JUNCTION_SECONDS),
            "gridlock_seconds": self._gridlock_seconds(),
            "boundary_wait_seconds": sum(self.simulation_time-item.time for item in self.pending_demand),
            "avg_admitted_boundary_wait": external_wait/max(1, self.completed+len(self.vehicles)),
            "total_stopped_seconds": wait, "total_pedestrian_wait_seconds": ped_wait,
            "mean_speed_mps": sum(v.speed for v in self.vehicles.values())/max(1, len(self.vehicles)),
            "density_vehicles_per_km": len(self.vehicles)/(sum(l.length for l in self.network.lanes.values())/1000),
            "throughput_per_hour": self.completed*3600/elapsed if elapsed else 0,
            "lanes": {lane.id: {"vehicles": lane_counts[lane.id], "queue": queues[lane.id],
                                "density_vehicles_per_km": lane_counts[lane.id]*1000/lane.length,
                                "mean_speed_mps": lane_speeds[lane.id]/max(1, lane_counts[lane.id]),
                                "exits": self.lane_exits[lane.id], "closed": lane.id in self.closed_lanes,
                                "speed_factor": self.slow_lanes.get(lane.id, 1)} for lane in self.network.lanes.values()},
            "max_queue_reach_m": max((reaches[lane] for node in self.signals for lane in self.network.incoming[node]), default=0.0),
            "junctions": {node: {"queue": sum(queues[lane] for lane in self.network.incoming[node]),
                                  "vehicle_passages": sum(self.lane_exits[lane] for lane in self.network.incoming[node]),
                                  "stopped_seconds": sum(self.lane_stopped_seconds[lane] for lane in self.network.incoming[node]),
                                  "stopped_seconds_by_approach": {approach: sum(self.lane_stopped_seconds[lane] for lane in self.network.incoming[node] if self.network.lanes[lane].approach == approach) for approach in APPROACHES},
                                  "queue_reach_m": {approach: max((reaches[lane] for lane in self.network.incoming[node] if self.network.lanes[lane].approach == approach), default=0.0) for approach in APPROACHES},
                                  "phase": signal.phase, "mode": signal.mode,
                                  "waiting_pedestrians": sum(p.junction == node and not p.crossing for p in self.pedestrians.values())} for node, signal in self.signals.items()},
        })
        return metrics

    def vehicle_records(self):
        records = []
        for vehicle in self.vehicles.values():
            x, y, heading = self._pose(vehicle)
            records.append({"id": vehicle.id, "x": x, "y": y, "angle": (90-math.degrees(heading)) % 360, "lateral": vehicle.lateral, "speed": vehicle.speed, "lane_id": vehicle.route[0], "lane_position": vehicle.position, "length": vehicle.length, "width": vehicle.width, "stopped": vehicle.speed <= 0.1, "visual_type": vehicle.vehicle_type, "wait_time": vehicle.wait})
        return records

    def _pedestrian_path_origin(self, junction):
        """Presentation coordinates shared with the existing simplified crossing."""
        node = self.network.nodes[junction]
        return node["x"]-9, node["y"]+6

    def pedestrian_paths(self):
        paths = []
        for junction in self.signals:
            x, y = self._pedestrian_path_origin(junction)
            paths.append({"id": f"pedestrian-path:{junction}", "junction_id": junction,
                          "shape": [{"x": x, "y": y}, {"x": x+self.config["crossing_length"], "y": y}],
                          "provenance": "illustrative"})
        return paths

    def pedestrian_records(self):
        records = []
        for pedestrian in self.pedestrians.values():
            x, y = self._pedestrian_path_origin(pedestrian.junction)
            records.append({"id": pedestrian.id, "x": x+pedestrian.progress, "y": y,
                            "speed": self.config["pedestrian_speed"] if pedestrian.crossing else 0,
                            "lane_id": pedestrian.junction, "stopped": not pedestrian.crossing,
                            "wait_time": pedestrian.wait})
        return records

    def to_dict(self):
        lights = {}
        for lane in self.network.lanes.values():
            if lane.target in self.signals:
                signal = self.signals[lane.target]
                lights[lane.id] = {"state": "o" if signal.mode == "all_way_stop" else "G" if signal.stage == "green" and signal.family == lane.approach else "y" if signal.stage == "yellow" and signal.family == lane.approach else "r", "phase": signal.phase}
        return copy.deepcopy({"engine_version": ENGINE_VERSION, "time": self.simulation_time, "step_length": STEP_LENGTH, "status": self.status, "phase": self.phase, "phase_remaining": self.phase_remaining, "cycle_count": self.cycle_count, "controller_type": self.controller_type, "vehicles": self.vehicle_records(), "vehicle_count": len(self.vehicles), "pedestrians": self.pedestrian_records(), "pedestrian_count": len(self.pedestrians), "queues": self._last_metrics["queue_by_approach"], "metrics": self._last_metrics, "events": self.events, "scenario": {"intersection_id": self.intersection_id, "traffic_density": self.traffic_density, "pedestrian_density": self.pedestrian_density, "road_constraint": self.road_constraint}, "dashboard": {"current_scenario_name": self.current_scenario_name, "control_mode_label": self.control_mode_label, "controller_provenance": self.controller_provenance, "controller_provenance_label": self.controller_provenance_label, "last_action": self.last_action, "last_error": self.last_error, "run_id": self.run_id}, "charts": self.charts, "visual": {"constraint_marker": {"active": bool(self.closed_lanes or self.slow_lanes), "x": 0, "y": 0}, "closed_lanes": sorted(self.closed_lanes), "slow_lanes": {lane: factor for lane, factor in self.slow_lanes.items() if factor < 1}, "pedestrian_paths": self.pedestrian_paths()}, "junction_controls": self.junction_controls(), "traffic_lights": lights, "experiment": self.experiment_metadata()})

    get_state = to_dict

    def configure_rl_control(self, *, decision_interval=5.0, minimum_green_hold=10.0, controller_label="RL Controller", controller_provenance="rl"):
        self._settle_metrics()
        decision_interval = number(decision_interval, "decision interval", .1, 60)
        minimum_green_hold = number(minimum_green_hold, "minimum green hold", 5, 60)
        if self.config["signal_plans"].get(self.controlled_junction, {}).get("mode") == "all_way_stop":
            raise ValueError("RL signal control requires a signalized controlled junction")
        plan = self.config["signal_plans"].get(self.controlled_junction, {})
        effective_minimum = max(plan.get("minimum_green", 0), minimum_green_hold)
        maximum_green = plan.get("maximum_green", max(60, self.green_seconds))
        if effective_minimum > maximum_green:
            raise ValueError("RL minimum green cannot exceed the junction maximum green")
        self.rl_control_enabled = True
        self.rl_decision_interval, self.rl_minimum_green_hold = decision_interval, effective_minimum
        self.controller_type, self.controller_provenance = "rl", controller_provenance
        self.control_mode_label = self.controller_provenance_label = controller_label
        for node, signal in self.signals.items():
            signal.external = node == self.controlled_junction
            if signal.external:
                signal.minimum_green = self.rl_minimum_green_hold

    def disable_rl_control(self):
        self._settle_metrics()
        self.rl_control_enabled = False
        self.runtime_policy = None
        self.controller_type, self.controller_provenance = "fixed_time", "fixed-time"
        self.control_mode_label = self.controller_provenance_label = "Fixed-Time (Python)"
        for signal in self.signals.values():
            signal.external = False
        for node, signal in self.signals.items():
            signal.minimum_green = self.config["signal_plans"].get(node, {}).get("minimum_green", min(self.green_seconds, 10.0))

    def get_green_phase_for_action(self, action_name):
        return action_name.replace("SERVE_", "").replace("PEDESTRIAN", "PED")+"_GREEN" if action_name in RL_SERVICE_ACTIONS else None

    def apply_rl_action(self, action_name: str, junction_id: str | None = None):
        self._settle_metrics()
        if not self.rl_control_enabled or self.status != "running":
            return {"applied": False, "reason": "rl_control_disabled"}
        if action_name not in RL_SERVICE_ACTIONS:
            return {"applied": False, "reason": "unknown_action"}
        node = junction_id or self.controlled_junction
        if node not in self.signals:
            return {"applied": False, "reason": "unknown_junction"}
        if node != self.controlled_junction:
            return {"applied": False, "reason": "uncontrolled_junction"}
        signal = self.signals[node]
        if signal.mode != "signalized":
            return {"applied": False, "reason": "unsignalized_junction"}
        signal.external = True
        result = signal.request(action_name.removeprefix("SERVE_").lower())
        self.policy_decisions += 1
        self.last_policy_decision = {"time": self.simulation_time, "junction_id": node,
                                     "action": action_name, **result}
        return result

    def current_approach_lanes(self):
        return {approach: tuple(lane_id for lane_id in self.network.incoming[self.controlled_junction] if self.network.lanes[lane_id].approach == approach) for approach in APPROACHES}

    def current_phase_family(self):
        return phase_family_from_name(self.phase)

    def build_rl_runtime_state(self):
        return {"intersection_id": self.intersection_id, "phase": self.phase, "phase_family": self.current_phase_family(), "phase_remaining": self.phase_remaining, "simulation_time": self.simulation_time, "metrics": self._last_metrics, "vehicles": self.vehicle_records(), "pedestrians": self.pedestrian_records(), "approach_lanes": self.current_approach_lanes(), "rl_total_phase_switches": self.rl_total_phase_switches}

    def reset_metrics(self):
        self.policy_decisions = self.safety_overrides = 0
        self.last_policy_decision = self.last_safety_override = None
        self.completed = self.completed_pedestrians = 0
        self.completed_wait = self.completed_travel = self.completed_pedestrian_wait = self.queue_integral = self.max_queue = 0.0
        self.metric_ticks = 0
        self.measurement_start = self.simulation_time
        self.admitted_at_measurement = self.vehicle_serial-len(self.vehicles)
        self.pedestrians_at_measurement = self.pedestrian_serial-len(self.pedestrians)-self.dropped_pedestrians
        self.completed_external_wait = 0.0
        self.lane_exits = dict.fromkeys(self.network.lanes, 0)
        self.lane_stopped_seconds = dict.fromkeys(self.network.lanes, 0.0)
        self.charts = {key: [] for key in self.charts}
        for vehicle in self.vehicles.values():
            vehicle.wait = 0.0
        for pedestrian in self.pedestrians.values():
            pedestrian.wait = 0.0
        self._refresh_metrics()

    def junction_controls(self):
        return {node: {"mode": signal.mode,
                       "controller": self.controller_provenance if signal.external else
                       "all-way-stop" if signal.mode == "all_way_stop" else "fixed-time",
                       "selected_for_rl": node == self.controlled_junction,
                       "phase": signal.phase, "remaining": signal.remaining,
                       "stage": signal.stage, "elapsed_seconds": signal.elapsed,
                       "remaining_seconds": None if signal.mode == "all_way_stop" else signal.remaining,
                       "timing_kind": "none" if signal.mode == "all_way_stop" else
                       "minimum_hold" if signal.stage == "green" and signal.external else
                       "fixed_stage" if signal.stage == "green" else "clearance",
                       "pending_service": signal.pending, "external_control": signal.external,
                       "phase_order": list(signal.approaches),
                       "green_seconds": signal.green_seconds,
                       "minimum_green": signal.minimum_green,
                       "maximum_green": signal.maximum_green,
                       "yellow_seconds": signal.yellow_seconds,
                       "all_red_seconds": signal.all_red_seconds}
                for node, signal in self.signals.items()}

    def experiment_metadata(self):
        return {"engine_version": ENGINE_VERSION, "network_id": self.network.id,
                "network_sha256": self.network.fingerprint, "seed": self.seed,
                "duration_seconds": self.duration_limit, "step_length": STEP_LENGTH,
                "measurement_start": self.measurement_start, "controller": self.controller_provenance,
                "demand_sha256": self.demand_fingerprint, "config": copy.deepcopy(self.config),
                "policy": copy.deepcopy(getattr(self.runtime_policy, "artifact_metadata", None)),
                "control": {"decision_interval": self.rl_decision_interval if self.rl_control_enabled else None,
                            "minimum_green_hold": self.rl_minimum_green_hold if self.rl_control_enabled else None},
                "last_policy_decision": copy.deepcopy(self.last_policy_decision),
                "last_safety_override": copy.deepcopy(self.last_safety_override)}
