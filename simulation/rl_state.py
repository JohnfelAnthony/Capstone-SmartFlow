from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

from .traffic_engine import RL_SERVICE_ACTIONS, TrafficEngine, phase_family_from_name

APPROACH_ORDER = ("north", "east", "south", "west")
PHASE_FAMILY_ORDER = ("NORTH", "EAST", "SOUTH", "WEST", "PEDESTRIAN")
INTERSECTION_ORDER = ("tagum_network", "custom_network")

MAX_QUEUE_COUNT = 30.0
MAX_WAIT_SECONDS = 120.0
MAX_ACTIVE_VEHICLES = 30.0
MAX_PEDESTRIAN_WAITING = 20.0

QUEUE_BIN_EDGES = (0.0, 3.0, 8.0, MAX_QUEUE_COUNT)
WAIT_BIN_EDGES = (0.0, 15.0, 45.0, MAX_WAIT_SECONDS)
ACTIVE_BIN_EDGES = (0.0, 3.0, 8.0, MAX_ACTIVE_VEHICLES)
PEDESTRIAN_BIN_EDGES = (0.0, 4.0, MAX_PEDESTRIAN_WAITING)
EMERGENCY_PROXIMITY_BIN_EDGES = (0.25, 0.65, 1.0)


@dataclass(frozen=True)
class RLSnapshot:
    observation: list[float]
    phase_family: str
    elapsed_phase_seconds: float
    remaining_switch_seconds: float
    queue_by_approach: dict[str, int]
    wait_by_approach: dict[str, float]
    active_vehicles_by_approach: dict[str, int]
    pedestrian_waiting_count: int
    emergency_presence_by_approach: dict[str, int]
    emergency_proximity_by_approach: dict[str, float]
    valid_action_mask: tuple[int, ...]
    throughput: int
    avg_wait: float
    avg_queue: float
    max_queue: int
    avg_ped_delay: float
    total_phase_switches: int
    simulation_time: float
    intersection_id: str

    @property
    def ql_state(self) -> tuple[int, ...]:
        phase_index = PHASE_FAMILY_ORDER.index(self.phase_family) if self.phase_family in PHASE_FAMILY_ORDER else len(PHASE_FAMILY_ORDER)
        encoded: list[int] = [phase_index]
        encoded.extend(_discretize_value(self.queue_by_approach[approach], QUEUE_BIN_EDGES) for approach in APPROACH_ORDER)
        encoded.extend(_discretize_value(self.wait_by_approach[approach], WAIT_BIN_EDGES) for approach in APPROACH_ORDER)
        encoded.extend(_discretize_value(self.active_vehicles_by_approach[approach], ACTIVE_BIN_EDGES) for approach in APPROACH_ORDER)
        encoded.append(_discretize_value(self.pedestrian_waiting_count, PEDESTRIAN_BIN_EDGES))
        encoded.extend(int(bool(self.emergency_presence_by_approach[approach])) for approach in APPROACH_ORDER)
        encoded.extend(
            _discretize_value(self.emergency_proximity_by_approach[approach], EMERGENCY_PROXIMITY_BIN_EDGES)
            for approach in APPROACH_ORDER
        )
        encoded.append(INTERSECTION_ORDER.index(self.intersection_id) if self.intersection_id in INTERSECTION_ORDER else len(INTERSECTION_ORDER))
        return tuple(encoded)


def _clamp(value: float, minimum: float, maximum: float) -> float:
    return max(minimum, min(maximum, value))


def _normalize(value: float, maximum: float) -> float:
    if maximum <= 0:
        return 0.0
    return round(_clamp(float(value), 0.0, maximum) / maximum, 6)


def _discretize_value(value: float, edges: Iterable[float]) -> int:
    numeric_value = float(value)
    for index, edge in enumerate(edges):
        if numeric_value <= edge:
            return index
    return len(tuple(edges))


def _phase_one_hot(phase_family: str) -> list[float]:
    return [1.0 if phase_family == family else 0.0 for family in PHASE_FAMILY_ORDER]


def _intersection_one_hot(intersection_id: str) -> list[float]:
    return [1.0 if intersection_id == family else 0.0 for family in INTERSECTION_ORDER]


def _is_action_valid_for_snapshot(snapshot_state: dict, target_phase_family: str) -> bool:
    current_phase_family = snapshot_state["phase_family"]
    remaining_switch_seconds = snapshot_state["remaining_switch_seconds"]
    if current_phase_family == target_phase_family:
        return True
    return remaining_switch_seconds <= 0.0


def _phase_elapsed_seconds(engine: TrafficEngine) -> float:
    return engine.signals[engine.controlled_junction].elapsed


def _runtime_vehicle_records(
    engine: TrafficEngine,
    fallback_vehicles: list[dict],
    emergency_vehicle_ids: set[str],
) -> list[dict]:
    connection = engine.connection
    if connection is None:
        return list(fallback_vehicles)

    records: list[dict] = []
    try:
        vehicle_ids = list(connection.vehicle.getIDList())
    except Exception:
        return list(fallback_vehicles)

    for vehicle_id in vehicle_ids:
        try:
            lane_id = connection.vehicle.getLaneID(vehicle_id)
            speed = float(connection.vehicle.getSpeed(vehicle_id))
            record = {
                "id": vehicle_id,
                "lane_id": lane_id,
                "lane_position": float(connection.vehicle.getLanePosition(vehicle_id)),
                "wait_time": float(connection.vehicle.getAccumulatedWaitingTime(vehicle_id)),
                "stopped": speed <= 0.1,
                "emergency": vehicle_id in emergency_vehicle_ids or engine._is_declared_emergency_vehicle(vehicle_id),
            }
        except Exception:
            continue
        records.append(record)
    return records


def _runtime_pedestrian_waiting_count(engine: TrafficEngine, fallback_pedestrians: list[dict]) -> int:
    connection = engine.connection
    if connection is None:
        return sum(1 for pedestrian in fallback_pedestrians if bool(pedestrian.get("stopped")))

    try:
        person_ids = list(connection.person.getIDList())
    except Exception:
        return sum(1 for pedestrian in fallback_pedestrians if bool(pedestrian.get("stopped")))

    waiting_count = 0
    for person_id in person_ids:
        try:
            if float(connection.person.getSpeed(person_id)) <= 0.05:
                waiting_count += 1
        except Exception:
            continue
    return waiting_count


def extract_rl_snapshot(engine: TrafficEngine) -> RLSnapshot:
    runtime_state = engine.build_rl_runtime_state()
    metrics = runtime_state.get("metrics", {})
    vehicles = _runtime_vehicle_records(
        engine,
        list(runtime_state.get("vehicles", [])),
        set(runtime_state.get("emergency_vehicle_ids", [])),
    )
    pedestrians = [ped for ped in runtime_state.get("pedestrians", []) if ped.get("lane_id") == engine.controlled_junction]
    approach_lanes = runtime_state.get("approach_lanes", {})
    connection = engine.connection

    queue_by_approach = {
        approach: int(metrics.get("queue_by_approach", {}).get(approach, 0) or 0)
        for approach in APPROACH_ORDER
    }
    wait_by_approach = {approach: 0.0 for approach in APPROACH_ORDER}
    active_vehicles_by_approach = {approach: 0 for approach in APPROACH_ORDER}
    emergency_presence_by_approach = {approach: 0 for approach in APPROACH_ORDER}
    emergency_proximity_by_approach = {approach: 0.0 for approach in APPROACH_ORDER}

    lane_length_cache: dict[str, float] = {}
    lane_to_approach: dict[str, str] = {}
    for approach, lane_ids in approach_lanes.items():
        for lane_id in lane_ids:
            lane_to_approach[str(lane_id)] = approach

    for vehicle in vehicles:
        lane_id = str(vehicle.get("lane_id") or "")
        approach = lane_to_approach.get(lane_id)
        if not approach:
            continue

        active_vehicles_by_approach[approach] += 1
        wait_by_approach[approach] += float(vehicle.get("wait_time", 0.0) or 0.0)

        if not bool(vehicle.get("emergency")):
            continue

        emergency_presence_by_approach[approach] = 1
        if connection is None and lane_id in engine.network.lanes:
            emergency_proximity_by_approach[approach] = max(emergency_proximity_by_approach[approach], _normalize(float(vehicle.get("lane_position", 0)), engine.network.lanes[lane_id].length))
        if connection is not None and lane_id:
            if lane_id not in lane_length_cache:
                try:
                    lane_length_cache[lane_id] = float(connection.lane.getLength(lane_id))
                except Exception:
                    lane_length_cache[lane_id] = 0.0
            lane_length = lane_length_cache[lane_id]
            lane_position = float(vehicle.get("lane_position", 0.0) or 0.0)
            if lane_length > 0:
                emergency_proximity_by_approach[approach] = max(
                    emergency_proximity_by_approach[approach],
                    _normalize(lane_position, lane_length),
                )

    for approach in APPROACH_ORDER:
        vehicle_count = active_vehicles_by_approach[approach]
        if vehicle_count > 0:
            wait_by_approach[approach] = round(wait_by_approach[approach] / vehicle_count, 4)

    pedestrian_waiting_count = _runtime_pedestrian_waiting_count(engine, pedestrians)

    phase_family = runtime_state.get("phase_family") or phase_family_from_name(engine.phase)
    remaining_switch_seconds = max(float(runtime_state.get("phase_remaining", 0.0) or 0.0), 0.0)
    elapsed_phase_seconds = _phase_elapsed_seconds(engine)

    snapshot_state = {
        "phase_family": phase_family,
        "remaining_switch_seconds": remaining_switch_seconds,
    }
    signal = engine.signals[engine.controlled_junction]
    valid_action_mask = tuple(
        int(action.removeprefix("SERVE_").lower() in signal.approaches and
            (action.removeprefix("SERVE_").lower() == signal.family or
             (signal.stage == "green" and signal.elapsed >= signal.minimum_green)))
        for action in RL_SERVICE_ACTIONS
    )

    observation = [
        *_phase_one_hot(phase_family),
        _normalize(elapsed_phase_seconds, float(engine.rl_minimum_green_hold)),
        _normalize(remaining_switch_seconds, float(engine.rl_minimum_green_hold)),
        *(_normalize(queue_by_approach[approach], MAX_QUEUE_COUNT) for approach in APPROACH_ORDER),
        *(_normalize(wait_by_approach[approach], MAX_WAIT_SECONDS) for approach in APPROACH_ORDER),
        *(_normalize(active_vehicles_by_approach[approach], MAX_ACTIVE_VEHICLES) for approach in APPROACH_ORDER),
        _normalize(float(pedestrian_waiting_count), MAX_PEDESTRIAN_WAITING),
        *(float(emergency_presence_by_approach[approach]) for approach in APPROACH_ORDER),
        *(_clamp(emergency_proximity_by_approach[approach], 0.0, 1.0) for approach in APPROACH_ORDER),
        *_intersection_one_hot(runtime_state["intersection_id"]),
    ]

    return RLSnapshot(
        observation=observation,
        phase_family=phase_family,
        elapsed_phase_seconds=round(elapsed_phase_seconds, 4),
        remaining_switch_seconds=round(remaining_switch_seconds, 4),
        queue_by_approach=queue_by_approach,
        wait_by_approach={approach: round(wait_by_approach[approach], 4) for approach in APPROACH_ORDER},
        active_vehicles_by_approach=active_vehicles_by_approach,
        pedestrian_waiting_count=pedestrian_waiting_count,
        emergency_presence_by_approach=emergency_presence_by_approach,
        emergency_proximity_by_approach={approach: round(emergency_proximity_by_approach[approach], 6) for approach in APPROACH_ORDER},
        valid_action_mask=valid_action_mask,
        throughput=int(metrics.get("throughput", 0) or 0),
        avg_wait=float(metrics.get("avg_wait", 0.0) or 0.0),
        avg_queue=float(metrics.get("avg_queue", 0.0) or 0.0),
        max_queue=int(metrics.get("max_queue", 0) or 0),
        avg_ped_delay=float(metrics.get("avg_ped_delay", 0.0) or 0.0),
        total_phase_switches=int(runtime_state.get("rl_total_phase_switches", 0) or 0),
        simulation_time=float(runtime_state.get("simulation_time", 0.0) or 0.0),
        intersection_id=str(runtime_state.get("intersection_id") or "tagum_1"),
    )
