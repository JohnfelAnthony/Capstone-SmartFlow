import uuid
from dataclasses import dataclass

import traci

from .sumo_config import (
    CHART_HISTORY_LIMIT,
    DEFAULT_INTERSECTION_ID,
    DENSITY_SCALE,
    EVENT_LIMIT,
    PEDESTRIAN_SAMPLE_LIMIT,
    PEDESTRIAN_SPAWN_INTERVALS,
    SUMO_STEP_LENGTH,
    VEHICLE_SAMPLE_LIMIT,
    get_intersection_assets,
    get_sumo_binary,
)
from .sumo_state import build_state_payload, pedestrian_snapshot, vehicle_snapshot

RL_SERVICE_ACTIONS = (
    "SERVE_NORTH",
    "SERVE_EAST",
    "SERVE_SOUTH",
    "SERVE_WEST",
    "SERVE_PEDESTRIAN",
)

RL_ACTION_TO_GREEN_PHASE = {
    "SERVE_NORTH": "NORTH_GREEN",
    "SERVE_EAST": "EAST_GREEN",
    "SERVE_SOUTH": "SOUTH_GREEN",
    "SERVE_WEST": "WEST_GREEN",
    "SERVE_PEDESTRIAN": "PED_GREEN",
}


def phase_family_from_name(phase_name: str) -> str:
    normalized_phase = str(phase_name or "").strip().upper()
    if normalized_phase.startswith("NORTH_"):
        return "NORTH"
    if normalized_phase.startswith("EAST_"):
        return "EAST"
    if normalized_phase.startswith("SOUTH_"):
        return "SOUTH"
    if normalized_phase.startswith("WEST_"):
        return "WEST"
    if normalized_phase.startswith("PED_"):
        return "PEDESTRIAN"
    if normalized_phase == "ALL_RED":
        return "ALL_RED"
    return "UNKNOWN"


@dataclass
class _MetricsAccumulator:
    step_count: int = 0
    total_vehicles_spawned: int = 0
    total_vehicles_completed: int = 0
    total_pedestrians_spawned: int = 0
    total_pedestrians_completed: int = 0
    avg_wait_sum: float = 0.0
    avg_queue_sum: float = 0.0
    avg_ped_delay_sum: float = 0.0
    max_queue: int = 0

    def reset(self):
        self.step_count = 0
        self.total_vehicles_spawned = 0
        self.total_vehicles_completed = 0
        self.total_pedestrians_spawned = 0
        self.total_pedestrians_completed = 0
        self.avg_wait_sum = 0.0
        self.avg_queue_sum = 0.0
        self.avg_ped_delay_sum = 0.0
        self.max_queue = 0

    def record(self, *, wait_times: list[float], queue_counts: dict[str, int], pedestrian_count: int, departed: int, arrived: int, departed_peds: int, arrived_peds: int):
        self.step_count += 1
        self.total_vehicles_spawned += departed
        self.total_vehicles_completed += arrived
        self.total_pedestrians_spawned += departed_peds
        self.total_pedestrians_completed += arrived_peds

        current_avg_wait = sum(wait_times) / len(wait_times) if wait_times else 0.0
        current_avg_queue = sum(queue_counts.values()) / len(queue_counts) if queue_counts else 0.0

        self.avg_wait_sum += current_avg_wait
        self.avg_queue_sum += current_avg_queue
        self.avg_ped_delay_sum += float(pedestrian_count)
        self.max_queue = max(self.max_queue, max(queue_counts.values(), default=0))

    def to_dict(self, *, active_vehicle_count: int, active_pedestrian_count: int, queue_by_approach: dict[str, int]) -> dict:
        step_divisor = self.step_count if self.step_count else 1
        return {
            "avg_wait": round(self.avg_wait_sum / step_divisor, 1) if self.step_count else 0.0,
            "avg_queue": round(self.avg_queue_sum / step_divisor, 1) if self.step_count else 0.0,
            "max_queue": self.max_queue,
            "throughput": self.total_vehicles_completed,
            "avg_ped_delay": round(self.avg_ped_delay_sum / step_divisor, 1) if self.step_count else 0.0,
            "total_vehicles_spawned": self.total_vehicles_spawned,
            "total_vehicles_completed": self.total_vehicles_completed,
            "total_pedestrians_spawned": self.total_pedestrians_spawned,
            "total_pedestrians_completed": self.total_pedestrians_completed,
            "step_count": self.step_count,
            "active_vehicle_count": active_vehicle_count,
            "active_pedestrian_count": active_pedestrian_count,
            "queue_by_approach": queue_by_approach,
        }


class SumoSimulationEngine:
    def __init__(self, seed: int | None = 42):
        self.seed = seed if seed is not None else 42
        self.intersection_id = DEFAULT_INTERSECTION_ID
        self._intersection_assets = get_intersection_assets(self.intersection_id)
        self.status = "stopped"
        self.simulation_time = 0.0
        self.duration_limit = 300
        self.traffic_density = "low"
        self.pedestrian_density = "low"
        self.emergency_mode = "disabled"
        self.road_constraint = "None"
        self.lane_closure = False
        self.accident = False
        self.flooding = False
        self.construction = False
        self.temp_blockage = False
        self.controller_type = "fixed_time"
        self.control_mode_label = "Fixed-Time (SUMO/TraCI)"
        self.controller_provenance = "fixed-time"
        self.controller_provenance_label = "Fixed-Time"
        self.rl_control_enabled = False
        self.rl_decision_interval = 5.0
        self.rl_minimum_green_hold = 10.0
        self.rl_pending_action: str | None = None
        self._rl_transition_queue: list[tuple[str, float]] = []
        self.rl_total_phase_switches = 0
        self.current_scenario_name = "No scenario selected"
        self.events: list[dict] = []
        self.metrics = _MetricsAccumulator()
        self.connection = None
        self.connection_label = None
        self.phase_index = 0
        self.phase = self._current_phase_sequence()[0][0]
        self.phase_remaining = self._current_phase_sequence()[0][1]
        self.cycle_count = 0
        self.run_id = "—"
        self.last_action = "Not started"
        self.last_error = "None"
        self._event_counter = 0
        self._last_vehicle_sample: list[dict] = []
        self._last_pedestrian_sample: list[dict] = []
        self._chart_traffic_flow: list[dict] = []
        self._chart_wait_time: list[dict] = []
        self._chart_queue_length: list[dict] = []
        self._chart_throughput: list[dict] = []
        self._emergency_vehicle_ids: set[str] = set()
        self._pedestrian_spawn_elapsed = 0.0
        self._pedestrian_route_index = 0
        self._last_traffic_light_states = self._default_traffic_light_states()
        self._last_metrics = self.metrics.to_dict(
            active_vehicle_count=0,
            active_pedestrian_count=0,
            queue_by_approach={key: 0 for key in self._current_approach_lanes()},
        )

    def start(self, duration_limit: int = 300):
        if self.status == "running":
            return
        if self.status == "paused":
            self.resume()
            return

        self.duration_limit = duration_limit
        self._reset_runtime_state()
        try:
            self._start_connection()
            self._apply_phase()
            self.status = "running"
            self.run_id = f"sumo-{uuid.uuid4().hex[:8]}"
            self._record_action("SUMO simulation started")
            self._refresh_state()
        except Exception as exc:
            self.set_error_state(str(exc), f"SUMO startup failed: {exc}")

    def pause(self):
        if self.status == "running":
            self.status = "paused"
            self._record_action("Simulation paused")

    def resume(self):
        if self.status == "paused":
            self.status = "running"
            self._record_action("Simulation resumed")

    def stop(self):
        if self.status in {"running", "paused", "error"}:
            self.status = "stopped"
            self._record_action("Simulation stopped")
        self._close_connection()

    def reset(self):
        self.stop()
        self._reset_runtime_state()
        self._record_action("Simulation reset")

    def step(self, num_ticks: int = 1):
        if self.status != "running" or self.connection is None:
            return

        for _ in range(num_ticks):
            try:
                self._pedestrian_spawn_elapsed += SUMO_STEP_LENGTH
                self._spawn_pedestrian_if_due()
                self.connection.simulationStep()
                self.simulation_time += SUMO_STEP_LENGTH
                if self.rl_control_enabled:
                    self._advance_rl_runtime()
                else:
                    self.phase_remaining -= SUMO_STEP_LENGTH
                    if self.phase_remaining <= 0:
                        self._advance_phase()
                self._refresh_state()
            except Exception as exc:
                self.set_error_state(str(exc), f"SUMO step failed: {exc}")
                break

            if self.simulation_time >= self.duration_limit:
                self.stop()
                self.status = "completed"
                self._record_action(f"Simulation automatically completed at {self.duration_limit}s limit")
                break

    def configure(self, **kwargs):
        density_fields = {"traffic_density", "pedestrian_density"}
        for key, value in kwargs.items():
            if key == "intersection_id":
                self._set_intersection(value)
                continue
            if hasattr(self, key):
                if key in density_fields and isinstance(value, str):
                    setattr(self, key, value.lower())
                else:
                    setattr(self, key, value)
        if kwargs:
            self._record_action("Scenario settings updated for the next run")

    def configure_from_scenario(self, scenario: dict):
        if scenario.get("intersection_id"):
            self._set_intersection(scenario["intersection_id"])
        if scenario.get("name"):
            self.current_scenario_name = scenario["name"]
        self.configure(**{
            key: scenario[key]
            for key in (
                "traffic_density",
                "pedestrian_density",
                "emergency_mode",
                "road_constraint",
                "lane_closure",
                "construction",
                "accident",
                "flooding",
                "temp_blockage",
            )
            if key in scenario and scenario[key] is not None
        })

    def configure_rl_control(
        self,
        *,
        decision_interval: float = 5.0,
        minimum_green_hold: float = 10.0,
        controller_label: str = "RL Controller",
        controller_provenance: str = "rl",
    ):
        self.rl_control_enabled = True
        self.rl_decision_interval = max(float(decision_interval or 5.0), SUMO_STEP_LENGTH)
        self.rl_minimum_green_hold = max(float(minimum_green_hold or 10.0), SUMO_STEP_LENGTH)
        self.rl_pending_action = None
        self._rl_transition_queue = []
        self.rl_total_phase_switches = 0
        self.controller_type = "rl"
        self.control_mode_label = controller_label
        self.controller_provenance = controller_provenance
        self.controller_provenance_label = controller_label
        if self.phase.endswith("_GREEN"):
            self.phase_remaining = max(self.phase_remaining, self.rl_minimum_green_hold)

    def disable_rl_control(self):
        self.rl_control_enabled = False
        self.rl_pending_action = None
        self._rl_transition_queue = []
        self.controller_type = "fixed_time"
        self.control_mode_label = "Fixed-Time (SUMO/TraCI)"
        self.controller_provenance = "fixed-time"
        self.controller_provenance_label = "Fixed-Time"

    def current_phase_family(self) -> str:
        return phase_family_from_name(self.phase)

    def current_approach_lanes(self) -> dict[str, tuple[str, ...]]:
        return {approach: tuple(lanes) for approach, lanes in self._current_approach_lanes().items()}

    def get_green_phase_for_action(self, action_name: str) -> str | None:
        normalized_action = str(action_name or "").strip().upper()
        return RL_ACTION_TO_GREEN_PHASE.get(normalized_action)

    def build_rl_runtime_state(self) -> dict:
        return {
            "intersection_id": self.intersection_id,
            "phase": self.phase,
            "phase_family": self.current_phase_family(),
            "phase_remaining": max(float(self.phase_remaining), 0.0),
            "simulation_time": float(self.simulation_time),
            "decision_interval": float(self.rl_decision_interval),
            "minimum_green_hold": float(self.rl_minimum_green_hold),
            "queues": dict(self._last_metrics.get("queue_by_approach", {})),
            "metrics": dict(self._last_metrics),
            "vehicles": list(self._last_vehicle_sample),
            "pedestrians": list(self._last_pedestrian_sample),
            "emergency_vehicle_ids": sorted(self._emergency_vehicle_ids),
            "approach_lanes": self.current_approach_lanes(),
            "traffic_density": self.traffic_density,
            "pedestrian_density": self.pedestrian_density,
            "emergency_mode": self.emergency_mode,
            "road_constraint": self.road_constraint,
            "rl_total_phase_switches": int(self.rl_total_phase_switches),
            "rl_pending_action": self.rl_pending_action,
            "status": self.status,
        }

    def apply_rl_action(self, action_name: str) -> dict:
        target_green_phase = self.get_green_phase_for_action(action_name)
        if not target_green_phase:
            return {"applied": False, "reason": "unknown_action"}
        if not self.rl_control_enabled:
            return {"applied": False, "reason": "rl_control_disabled"}
        if self.status != "running" or self.connection is None:
            return {"applied": False, "reason": "engine_not_running"}

        current_family = self.current_phase_family()
        target_family = phase_family_from_name(target_green_phase)
        if current_family == target_family and self.phase.endswith("_GREEN") and not self._rl_transition_queue:
            self.rl_pending_action = None
            return {"applied": False, "reason": "already_serving"}

        if self._rl_transition_queue:
            self.rl_pending_action = str(action_name).strip().upper()
            return {"applied": False, "reason": "transition_in_progress"}

        if self.phase.endswith("_GREEN") and self.phase_remaining > 0:
            self.rl_pending_action = str(action_name).strip().upper()
            return {
                "applied": False,
                "reason": "minimum_green_hold_active",
                "available_in": round(max(self.phase_remaining, 0.0), 2),
            }

        transition_queue = self._build_rl_transition_queue(target_green_phase)
        if not transition_queue:
            return {"applied": False, "reason": "invalid_transition"}

        self.rl_pending_action = None
        next_phase, next_duration = transition_queue.pop(0)
        self._rl_transition_queue = transition_queue
        self._enter_rl_phase(next_phase, next_duration)
        self._record_action(f"RL action requested: {action_name}", kind="signal")
        return {
            "applied": True,
            "phase": self.phase,
            "phase_remaining": round(max(self.phase_remaining, 0.0), 2),
            "target_family": target_family,
        }

    def to_dict(self) -> dict:
        return build_state_payload(
            status=self.status,
            simulation_time=self.simulation_time,
            phase=self.phase,
            phase_remaining=self.phase_remaining,
            cycle_count=self.cycle_count,
            controller_type=self.controller_type,
            vehicles=self._last_vehicle_sample,
            pedestrians=self._last_pedestrian_sample,
            metrics=self._last_metrics,
            events=self.events[-20:],
            scenario={
                "intersection_id": self.intersection_id,
                "traffic_density": self.traffic_density,
                "pedestrian_density": self.pedestrian_density,
                "emergency_mode": self.emergency_mode,
                "road_constraint": self.road_constraint,
            },
            dashboard={
                "current_scenario_name": self.current_scenario_name,
                "control_mode_label": self.control_mode_label,
                "controller_provenance": self.controller_provenance,
                "controller_provenance_label": self.controller_provenance_label,
                "emergency_active_count": self._count_active_emergency_vehicles(),
                "last_action": self.last_action,
                "last_error": self.last_error,
                "run_id": self.run_id,
            },
            charts={
                "traffic_flow": self._chart_traffic_flow,
                "wait_time": self._chart_wait_time,
                "queue_length": self._chart_queue_length,
                "throughput": self._chart_throughput,
            },
            visual={
                "constraint_marker": self._build_constraint_marker(),
            },
            traffic_lights=self._traffic_lights_for_payload(),
            step_length=SUMO_STEP_LENGTH,
        )

    def _start_connection(self):
        sumo_config_path = self._intersection_assets.sumo_config_path
        if not sumo_config_path.exists():
            raise RuntimeError(
                f"Missing SUMO config for {self.intersection_id}: {sumo_config_path}"
            )

        self.connection_label = f"smartflow-{uuid.uuid4().hex}"
        args = [
            get_sumo_binary(),
            "-c",
            str(sumo_config_path),
            "--step-length",
            str(SUMO_STEP_LENGTH),
            "--seed",
            str(self.seed),
            "--no-step-log",
            "true",
            "--duration-log.disable",
            "true",
            "--scale",
            str(DENSITY_SCALE.get(self.traffic_density, 1.0)),
        ]
        traci.start(args, label=self.connection_label)
        self.connection = traci.getConnection(self.connection_label)

    def _close_connection(self):
        if self.connection is None:
            return
        try:
            self.connection.close()
        except Exception:
            pass
        finally:
            self.connection = None
            self.connection_label = None

    def set_error_state(self, error_message: str, event_message: str | None = None):
        self.status = "error"
        self.last_error = error_message
        self.last_action = "Simulation error"
        self._add_event("warning", event_message or error_message)
        self._close_connection()

    def _reset_runtime_state(self):
        initial_phase_name, initial_phase_duration = self._current_phase_sequence()[0]
        self.simulation_time = 0.0
        self.metrics.reset()
        self.phase_index = 0
        self.phase = initial_phase_name
        self.phase_remaining = initial_phase_duration
        self.cycle_count = 0
        self.events = []
        self._event_counter = 0
        self._last_vehicle_sample = []
        self._last_pedestrian_sample = []
        self._pedestrian_spawn_elapsed = 0.0
        self._pedestrian_route_index = 0
        self.run_id = "—"
        self.last_action = "Not started"
        self.last_error = "None"
        self._chart_traffic_flow = []
        self._chart_wait_time = []
        self._chart_queue_length = []
        self._chart_throughput = []
        self._emergency_vehicle_ids = set()
        self.rl_pending_action = None
        self._rl_transition_queue = []
        self.rl_total_phase_switches = 0
        self._last_traffic_light_states = self._default_traffic_light_states()
        self._last_metrics = self.metrics.to_dict(
            active_vehicle_count=0,
            active_pedestrian_count=0,
            queue_by_approach={key: 0 for key in self._current_approach_lanes()},
        )

    def _advance_phase(self):
        phase_sequence = self._current_phase_sequence()
        self.phase_index = (self.phase_index + 1) % len(phase_sequence)
        if self.phase_index == 0:
            self.cycle_count += 1
        self.phase, self.phase_remaining = phase_sequence[self.phase_index]
        self._apply_phase()
        self._record_action(f"Phase changed: {self.phase}", kind="signal")

    def _advance_rl_runtime(self):
        self.phase_remaining = max(0.0, self.phase_remaining - SUMO_STEP_LENGTH)
        if self.phase_remaining > 0:
            return

        if self._rl_transition_queue:
            next_phase, next_duration = self._rl_transition_queue.pop(0)
            self._enter_rl_phase(next_phase, next_duration)
            return

        if self.rl_pending_action:
            pending_action = self.rl_pending_action
            self.rl_pending_action = None
            self.apply_rl_action(pending_action)
            return

        self.phase_remaining = 0.0

    def _enter_rl_phase(self, phase_name: str, duration_seconds: float):
        previous_family = self.current_phase_family()
        self.phase = phase_name
        self.phase_remaining = max(float(duration_seconds), SUMO_STEP_LENGTH)
        self._apply_phase()
        next_family = self.current_phase_family()
        if phase_name.endswith("_GREEN") and next_family not in {"ALL_RED", "UNKNOWN"} and next_family != previous_family:
            self.rl_total_phase_switches += 1
        self._record_action(f"RL phase entered: {phase_name}", kind="signal")

    def _phase_duration_from_sequence(self, phase_name: str, fallback_seconds: float = 3.0) -> float:
        normalized_phase = str(phase_name or "").strip().upper()
        for candidate_phase_name, candidate_duration in self._current_phase_sequence():
            if candidate_phase_name == normalized_phase:
                return float(candidate_duration)
        return float(fallback_seconds)

    def _build_rl_transition_queue(self, target_green_phase: str) -> list[tuple[str, float]]:
        normalized_target = str(target_green_phase or "").strip().upper()
        if not normalized_target:
            return []

        transition_queue: list[tuple[str, float]] = []
        current_phase = str(self.phase or "").strip().upper()

        if current_phase.endswith("_GREEN"):
            yellow_phase = current_phase.replace("_GREEN", "_YELLOW")
            if yellow_phase in self._current_tls_state_map():
                transition_queue.append(
                    (yellow_phase, self._phase_duration_from_sequence(yellow_phase, fallback_seconds=3.0))
                )

        if current_phase != "ALL_RED" and "ALL_RED" in self._current_tls_state_map():
            transition_queue.append(
                ("ALL_RED", self._phase_duration_from_sequence("ALL_RED", fallback_seconds=2.0))
            )

        transition_queue.append((normalized_target, self.rl_minimum_green_hold))
        return transition_queue

    def _apply_phase(self):
        if self.connection is None:
            return
        state = self._current_tls_state_map()[self.phase]
        for tls_id in self._current_controlled_tls_ids():
            self.connection.trafficlight.setRedYellowGreenState(tls_id, state)

    def _refresh_state(self):
        if self.connection is None:
            return

        vehicle_ids = list(self.connection.vehicle.getIDList())
        person_ids = list(self.connection.person.getIDList())
        queue_by_approach = {
            approach: sum(self.connection.lane.getLastStepHaltingNumber(lane_id) for lane_id in lane_ids)
            for approach, lane_ids in self._current_approach_lanes().items()
        }
        wait_times = [self.connection.vehicle.getAccumulatedWaitingTime(vehicle_id) for vehicle_id in vehicle_ids]
        departed_ids = list(self.connection.simulation.getDepartedIDList())
        arrived_ids = list(self.connection.simulation.getArrivedIDList())
        self._emergency_vehicle_ids.difference_update(arrived_ids)
        self._assign_emergency_vehicles(departed_ids)

        departed_person_ids = []
        arrived_person_ids = []
        if hasattr(self.connection.simulation, "getDepartedPersonIDList"):
            departed_person_ids = list(self.connection.simulation.getDepartedPersonIDList())
        if hasattr(self.connection.simulation, "getArrivedPersonIDList"):
            arrived_person_ids = list(self.connection.simulation.getArrivedPersonIDList())

        self.metrics.record(
            wait_times=wait_times,
            queue_counts=queue_by_approach,
            pedestrian_count=len(person_ids),
            departed=len(departed_ids),
            arrived=len(arrived_ids),
            departed_peds=len(departed_person_ids),
            arrived_peds=len(arrived_person_ids),
        )

        self._last_vehicle_sample = vehicle_snapshot(
            self.connection,
            vehicle_ids,
            VEHICLE_SAMPLE_LIMIT,
            self._emergency_vehicle_ids,
        )
        self._last_pedestrian_sample = pedestrian_snapshot(self.connection, person_ids, PEDESTRIAN_SAMPLE_LIMIT)
        self._last_traffic_light_states = self._capture_traffic_light_states()
        self._last_metrics = self.metrics.to_dict(
            active_vehicle_count=len(vehicle_ids),
            active_pedestrian_count=len(person_ids),
            queue_by_approach=queue_by_approach,
        )
        self._append_chart_points(queue_by_approach=queue_by_approach, active_vehicle_count=len(vehicle_ids))

        for approach, queue_count in queue_by_approach.items():
            if queue_count >= 5:
                self._add_event("warning", f"High congestion on {approach} approach")

    def _spawn_pedestrian_if_due(self):
        if self.connection is None:
            return

        interval = PEDESTRIAN_SPAWN_INTERVALS.get(self.pedestrian_density, 8.0)
        if interval is None or self._pedestrian_spawn_elapsed < interval:
            return

        route_templates = self._current_pedestrian_route_templates()
        if not route_templates:
            return
        template = route_templates[self._pedestrian_route_index % len(route_templates)]
        self._pedestrian_route_index += 1
        self._pedestrian_spawn_elapsed = 0.0

        try:
            stages = self.connection.simulation.findIntermodalRoute(
                template["from_edge"],
                template["to_edge"],
            )
        except Exception as exc:
            self._add_event("warning", f"Pedestrian routing failed: {exc}")
            return

        if not stages:
            self._add_event("warning", "Pedestrian routing returned no stages")
            return

        route_edges = tuple(getattr(stages[0], "edges", ()))
        if not route_edges:
            self._add_event("warning", "Pedestrian routing returned an empty walk")
            return

        person_id = f"ped_{int(self.simulation_time)}_{self._pedestrian_route_index}"
        try:
            self.connection.person.add(person_id, route_edges[0], 0.1)
            self.connection.person.appendWalkingStage(person_id, route_edges, -1)
            self._add_event("info", f"Pedestrian spawned on {template['name']} crossing")
        except Exception as exc:
            self.last_error = str(exc)
            self._add_event("warning", f"Pedestrian spawn failed: {exc}")

    def _add_event(self, kind: str, message: str):
        self._event_counter += 1
        self.events.append({
            "id": self._event_counter,
            "time": round(self.simulation_time, 1),
            "kind": kind,
            "message": message,
        })
        if len(self.events) > EVENT_LIMIT:
            self.events = self.events[-EVENT_LIMIT:]

    def _record_action(self, message: str, kind: str = "info"):
        self.last_action = message
        self._add_event(kind, message)

    def _append_chart_points(self, *, queue_by_approach: dict[str, int], active_vehicle_count: int):
        metric_time = round(self.simulation_time, 1)
        self._chart_traffic_flow.append({
            "time": metric_time,
            "north": queue_by_approach.get("north", 0),
            "south": queue_by_approach.get("south", 0),
            "east": queue_by_approach.get("east", 0),
            "west": queue_by_approach.get("west", 0),
            "vehicles": active_vehicle_count,
        })
        self._chart_wait_time.append({
            "time": metric_time,
            "value": self._last_metrics["avg_wait"],
        })
        self._chart_queue_length.append({
            "time": metric_time,
            "value": self._last_metrics["avg_queue"],
        })
        self._chart_throughput.append({
            "time": metric_time,
            "value": self._last_metrics["throughput"],
        })

        for series in (
            self._chart_traffic_flow,
            self._chart_wait_time,
            self._chart_queue_length,
            self._chart_throughput,
        ):
            if len(series) > CHART_HISTORY_LIMIT:
                del series[:-CHART_HISTORY_LIMIT]

    def _count_active_emergency_vehicles(self) -> int:
        return sum(
            1
            for vehicle in self._last_vehicle_sample
            if vehicle.get("emergency")
        )

    def _assign_emergency_vehicles(self, departed_ids: list[str]):
        declared_emergency_ids = {
            vehicle_id
            for vehicle_id in departed_ids
            if self._is_declared_emergency_vehicle(vehicle_id)
        }
        for vehicle_id in declared_emergency_ids:
            if vehicle_id not in self._emergency_vehicle_ids:
                self._emergency_vehicle_ids.add(vehicle_id)
                self._add_event("priority", f"Emergency vehicle detected: {vehicle_id}")

        if self.emergency_mode == "disabled":
            return

        max_active = 1
        if "2" in str(self.emergency_mode):
            max_active = 2

        for vehicle_id in departed_ids:
            if len(self._emergency_vehicle_ids) >= max_active:
                break
            if vehicle_id not in self._emergency_vehicle_ids:
                self._emergency_vehicle_ids.add(vehicle_id)
                self._add_event("priority", f"Emergency vehicle detected: {vehicle_id}")
                try:
                    self.connection.vehicle.setType(vehicle_id, "Emergency")
                except Exception:
                    pass

    def _is_declared_emergency_vehicle(self, vehicle_id: str) -> bool:
        if self.connection is None:
            return False
        try:
            type_id = self.connection.vehicle.getTypeID(vehicle_id).lower()
        except Exception:
            type_id = ""
        try:
            vehicle_class = self.connection.vehicle.getVehicleClass(vehicle_id).lower()
        except Exception:
            vehicle_class = ""
        return type_id == "emergency" or vehicle_class == "emergency"

    def _build_constraint_marker(self) -> dict:
        label = (self.road_constraint or "").strip()
        active = any([
            label and label.lower() != "none",
            self.lane_closure,
            self.accident,
            self.flooding,
            self.construction,
            self.temp_blockage,
        ])
        if not active:
            return {"active": False}

        normalized = label.lower()
        if self.lane_closure or "lane" in normalized:
            x, y, edge_id, text = -18.0, 8.0, "-E1", "Lane Closure"
        elif self.accident or "accident" in normalized:
            x, y, edge_id, text = -24.0, 2.0, "J1", "Accident"
        elif self.flooding or "flood" in normalized:
            x, y, edge_id, text = -28.0, -12.0, "E3", "Flooding"
        elif self.construction or "construct" in normalized:
            x, y, edge_id, text = -24.0, 18.0, "-E2", "Construction"
        elif self.temp_blockage or "block" in normalized:
            x, y, edge_id, text = -30.0, 0.0, "E0", "Temporary Blockage"
        else:
            x, y, edge_id, text = -24.0, 2.0, "J1", label or "Road Constraint"

        return {
            "active": True,
            "label": text,
            "edge_id": edge_id,
            "x": x,
            "y": y,
        }

    def _default_traffic_light_states(self) -> dict[str, dict[str, str]]:
        all_red_state = self._current_tls_state_map()["ALL_RED"]
        return {
            tls_id: {
                "state": all_red_state,
                "phase": "ALL_RED",
            }
            for tls_id in self._current_controlled_tls_ids()
        }

    def _capture_traffic_light_states(self) -> dict[str, dict[str, str]]:
        if self.connection is None:
            return self._default_traffic_light_states()

        tls_state_map = self._current_tls_state_map()
        traffic_lights: dict[str, dict[str, str]] = {}
        for tls_id in self._current_controlled_tls_ids():
            try:
                tls_state = self.connection.trafficlight.getRedYellowGreenState(tls_id)
            except Exception:
                tls_state = tls_state_map.get(self.phase, tls_state_map["ALL_RED"])
            traffic_lights[tls_id] = {
                "state": tls_state,
                "phase": self.phase,
            }
        return traffic_lights

    def _traffic_lights_for_payload(self) -> dict[str, dict[str, str]]:
        if self.status == "stopped":
            return self._default_traffic_light_states()
        return self._last_traffic_light_states or self._default_traffic_light_states()

    def _set_intersection(self, intersection_id: str | None):
        resolved_assets = get_intersection_assets(intersection_id)
        if resolved_assets.intersection_id == self.intersection_id:
            return
        self.intersection_id = resolved_assets.intersection_id
        self._intersection_assets = resolved_assets
        self.phase_index = 0
        self.phase = self._current_phase_sequence()[0][0]
        self.phase_remaining = self._current_phase_sequence()[0][1]
        self._pedestrian_route_index = 0
        self._last_traffic_light_states = self._default_traffic_light_states()
        self._last_metrics = self.metrics.to_dict(
            active_vehicle_count=0,
            active_pedestrian_count=0,
            queue_by_approach={key: 0 for key in self._current_approach_lanes()},
        )

    def _current_phase_sequence(self) -> tuple[tuple[str, float], ...]:
        return self._intersection_assets.phase_sequence

    def _current_tls_state_map(self) -> dict[str, str]:
        return self._intersection_assets.tls_state_map

    def _current_controlled_tls_ids(self) -> tuple[str, ...]:
        return self._intersection_assets.controlled_tls_ids

    def _current_approach_lanes(self) -> dict[str, tuple[str, ...]]:
        return self._intersection_assets.approach_lanes

    def _current_pedestrian_route_templates(self) -> tuple[dict[str, str], ...]:
        return self._intersection_assets.pedestrian_route_templates
