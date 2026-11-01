from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

from .traffic_engine import RL_SERVICE_ACTIONS, TrafficEngine, phase_family_from_name, phase_slots  # noqa: F401  (re-exported)

APPROACH_ORDER = ("north", "east", "south", "west")
OBSERVATION_VERSION = "obs_v4"  # 20 values; the phase one-hot is by plan slot and the network flags are gone (the contract binds the site)

# Above the largest per-approach p95 in docs/reports/mixed-traffic-acceptance.json (Tagum mix).
MAX_QUEUE_COUNT = 70.0
MAX_WAIT_SECONDS = 120.0
MAX_ACTIVE_VEHICLES = 70.0
MAX_PEDESTRIAN_WAITING = 20.0

QUEUE_BIN_EDGES = (0.0, 3.0, 8.0, MAX_QUEUE_COUNT)
WAIT_BIN_EDGES = (0.0, 15.0, 45.0, MAX_WAIT_SECONDS)
ACTIVE_BIN_EDGES = (0.0, 3.0, 8.0, MAX_ACTIVE_VEHICLES)
PEDESTRIAN_BIN_EDGES = (0.0, 4.0, MAX_PEDESTRIAN_WAITING)


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
    valid_action_mask: tuple[int, ...]
    junction_stopped_seconds: float
    junction_passages: int
    total_phase_switches: int
    simulation_time: float
    intersection_id: str
    phase_slot: int = 5  # 0-4 for the slot being served, 5 during clearance

    @property
    def ql_state(self) -> tuple[int, ...]:
        encoded: list[int] = [self.phase_slot]
        encoded.extend(_discretize_value(self.queue_by_approach[approach], QUEUE_BIN_EDGES) for approach in APPROACH_ORDER)
        encoded.extend(_discretize_value(self.wait_by_approach[approach], WAIT_BIN_EDGES) for approach in APPROACH_ORDER)
        encoded.extend(_discretize_value(self.active_vehicles_by_approach[approach], ACTIVE_BIN_EDGES) for approach in APPROACH_ORDER)
        encoded.append(_discretize_value(self.pedestrian_waiting_count, PEDESTRIAN_BIN_EDGES))
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


def _phase_one_hot(current_slot: int, slot_count: int = 5) -> list[float]:
    return [1.0 if slot == current_slot else 0.0 for slot in range(slot_count)]


def _is_action_valid_for_snapshot(snapshot_state: dict, target_phase_family: str) -> bool:
    current_phase_family = snapshot_state["phase_family"]
    remaining_switch_seconds = snapshot_state["remaining_switch_seconds"]
    if current_phase_family == target_phase_family:
        return True
    return remaining_switch_seconds <= 0.0


def _phase_elapsed_seconds(engine: TrafficEngine) -> float:
    return engine.signals[engine.controlled_junction].elapsed


def extract_rl_snapshot(engine: TrafficEngine) -> RLSnapshot:
    runtime_state = engine.build_rl_runtime_state()
    metrics = runtime_state.get("metrics", {})
    vehicles = list(runtime_state.get("vehicles", []))
    pedestrians = [ped for ped in runtime_state.get("pedestrians", []) if ped.get("lane_id") == engine.controlled_junction]
    approach_lanes = runtime_state.get("approach_lanes", {})

    queue_by_approach = {
        approach: int(metrics.get("queue_by_approach", {}).get(approach, 0) or 0)
        for approach in APPROACH_ORDER
    }
    wait_by_approach = {approach: 0.0 for approach in APPROACH_ORDER}
    active_vehicles_by_approach = {approach: 0 for approach in APPROACH_ORDER}

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


    for approach in APPROACH_ORDER:
        vehicle_count = active_vehicles_by_approach[approach]
        if vehicle_count > 0:
            wait_by_approach[approach] = round(wait_by_approach[approach] / vehicle_count, 4)

    pedestrian_waiting_count = sum(1 for pedestrian in pedestrians if bool(pedestrian.get("stopped")))

    phase_family = runtime_state.get("phase_family") or phase_family_from_name(engine.phase)
    remaining_switch_seconds = max(float(runtime_state.get("phase_remaining", 0.0) or 0.0), 0.0)
    elapsed_phase_seconds = _phase_elapsed_seconds(engine)

    junction_metrics = metrics.get("junctions", {}).get(engine.controlled_junction, {})
    snapshot_state = {
        "phase_family": phase_family,
        "remaining_switch_seconds": remaining_switch_seconds,
    }
    signal = engine.signals[engine.controlled_junction]
    slots = phase_slots(signal)
    current_slot = slots.index(signal.family) if signal.stage != "red" and signal.family in slots else len(slots)
    valid_action_mask = tuple(
        int(key is not None and (key == signal.family or (signal.stage == "green" and signal.elapsed >= signal.minimum_green)))
        for key in slots
    )

    observation = [
        *_phase_one_hot(current_slot),
        _normalize(elapsed_phase_seconds, float(engine.rl_minimum_green_hold)),
        _normalize(remaining_switch_seconds, float(engine.rl_minimum_green_hold)),
        *(_normalize(queue_by_approach[approach], MAX_QUEUE_COUNT) for approach in APPROACH_ORDER),
        *(_normalize(wait_by_approach[approach], MAX_WAIT_SECONDS) for approach in APPROACH_ORDER),
        *(_normalize(active_vehicles_by_approach[approach], MAX_ACTIVE_VEHICLES) for approach in APPROACH_ORDER),
        _normalize(float(pedestrian_waiting_count), MAX_PEDESTRIAN_WAITING),
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
        valid_action_mask=valid_action_mask,
        junction_stopped_seconds=float(junction_metrics.get("stopped_seconds", 0.0) or 0.0),
        junction_passages=int(junction_metrics.get("vehicle_passages", 0) or 0),
        total_phase_switches=int(runtime_state.get("rl_total_phase_switches", 0) or 0),
        simulation_time=float(runtime_state.get("simulation_time", 0.0) or 0.0),
        intersection_id=str(runtime_state.get("intersection_id") or engine.network.id),
        phase_slot=current_slot,
    )
