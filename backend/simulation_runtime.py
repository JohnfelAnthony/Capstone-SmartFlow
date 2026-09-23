from __future__ import annotations

import json
from datetime import UTC, datetime
from threading import Event, RLock, Thread
from time import monotonic
from typing import Any

import database
from backend.schemas import (
    SimulationConfigureRequest,
    SimulationStartRequest,
    SimulationStateResponse,
)
from services.simulation_flow import FlowState, build_flow_snapshot
from simulation.road_network import NETWORK_ID as DEFAULT_INTERSECTION_ID
from simulation.traffic_engine import STEP_LENGTH
from simulation.traffic_engine import TrafficEngine
from simulation.timeline_engine import TimelinePlaybackEngine


DEFAULT_DURATION_SECONDS = 300
DEFAULT_SEED = 42


class SimulationRuntimeError(RuntimeError):
    """Raised when a simulation action is not valid for the current runtime state."""


class SimulationRuntime:
    def __init__(self) -> None:
        self._lock = RLock()
        self._engine: TrafficEngine | None = None
        self._selected_scenario_id: int | None = None
        self._selected_scenario_name: str | None = None
        self._duration_seconds = DEFAULT_DURATION_SECONDS
        self._seed = DEFAULT_SEED
        self._control_mode = "fixed-time"
        self._run_mode = "live"
        self._runner_stop_event: Event | None = None
        self._runner_thread: Thread | None = None
        self._active_run_id: int | None = None
        self._active_run_saved = False
        self._active_run_user_id: int | None = None

    def get_state(self) -> SimulationStateResponse:
        with self._lock:
            return self._response()

    def configure(self, payload: SimulationConfigureRequest) -> SimulationStateResponse:
        with self._lock:
            if self._engine is not None and self._engine.status in {"running", "paused"}:
                raise SimulationRuntimeError("Stop or reset the current run before changing scenario settings.")
            candidate_seed = self._seed if payload.seed is None else int(payload.seed)
            candidate = TrafficEngine(seed=candidate_seed)
            if isinstance(self._engine, TrafficEngine) and payload.scenario_id is None:
                candidate.configure(**self._engine.config)
                candidate.current_scenario_name = self._engine.current_scenario_name
            scenario = self._scenario_from_request(payload.scenario_id)
            if scenario:
                candidate.configure_from_scenario(self._engine_scenario_payload(scenario))
            overrides = self._configure_overrides(payload)
            if overrides:
                candidate.configure(**overrides)
            from services.native_controller import apply_controller
            mode = apply_controller(candidate, payload.control_mode or (self._control_mode if self._run_mode == "live" else "fixed-time"))
            # Commit only after all inputs and the model contract have been checked.
            self._finalize_terminal_run_locked()
            self._stop_background_runner_locked()
            self._engine, self._seed, self._control_mode = candidate, candidate_seed, mode
            self._run_mode = "live"
            if scenario:
                self._selected_scenario_id = int(scenario["id"])
                self._selected_scenario_name = str(scenario["name"])
            if payload.duration_seconds is not None:
                self._duration_seconds = int(payload.duration_seconds)
            return self._response()

    def start(self, payload: SimulationStartRequest | None = None, *, user_id: int | None = None) -> SimulationStateResponse:
        with self._lock:
            payload = payload or SimulationStartRequest()
            active = self._engine is not None and self._engine.status in {"running", "paused"}
            if active and payload.model_dump(exclude_none=True):
                raise SimulationRuntimeError("Stop or reset the current run before changing start settings.")
            if self._run_mode == "playback" and payload.scenario_id is None:
                raise SimulationRuntimeError("Use playback/start for a recording, or configure a scenario for a live run.")
            if payload.scenario_id is not None or payload.seed is not None or payload.control_mode is not None:
                self.configure(
                    SimulationConfigureRequest(
                        scenario_id=payload.scenario_id,
                        duration_seconds=payload.duration_seconds,
                        seed=payload.seed,
                        control_mode=payload.control_mode,
                    )
                )
            elif payload.duration_seconds is not None:
                self._duration_seconds = int(payload.duration_seconds)

            if self._selected_scenario_id is None:
                raise SimulationRuntimeError("Configure a scenario before starting the simulation.")

            engine = self._get_engine()
            self._run_mode = "live"
            self._finalize_terminal_run_locked()
            new_run = engine.status not in {"running", "paused"} and self._active_run_id is None
            # Validate and initialize before allocating a database run. Invalid
            # demand must not leave a permanent 'running' row behind.
            engine.start(self._duration_seconds)
            if new_run:
                self._begin_run_locked(engine, user_id=user_id)
            if engine.status == "running":
                self._start_background_runner_locked()
            elif engine.status == "error":
                self._finalize_run_locked("error", engine.last_error or "Python engine startup failed.")
            return self._response()

    def pause(self) -> SimulationStateResponse:
        with self._lock:
            self._get_engine().pause()
            if self._active_run_id is not None:
                database.update_run(self._active_run_id, status="paused")
            return self._response()

    def resume(self) -> SimulationStateResponse:
        with self._lock:
            self._get_engine().resume()
            if self._active_run_id is not None:
                database.update_run(self._active_run_id, status="running")
            return self._response()

    def stop(self) -> SimulationStateResponse:
        with self._lock:
            self._stop_background_runner_locked()
            engine = self._get_engine()
            should_finalize = engine.status in {"running", "paused", "error"} and self._active_run_id is not None
            stop_status = "error" if engine.status == "error" else "stopped"
            stop_reason = engine.last_error if stop_status == "error" else "Simulation stopped manually."
            engine.stop()
            if should_finalize:
                self._finalize_run_locked(stop_status, stop_reason or "Simulation stopped.")
            return self._response()

    def reset(self) -> SimulationStateResponse:
        with self._lock:
            self._stop_background_runner_locked()
            engine = self._get_engine()
            if engine.status in {"running", "paused", "error"} and self._active_run_id is not None:
                reset_status = "error" if engine.status == "error" else "stopped"
                reset_reason = engine.last_error if reset_status == "error" else "Simulation reset manually."
                self._finalize_run_locked(reset_status, reset_reason or "Simulation reset.")
            self._control_mode = "fixed-time"
            self._replace_engine(seed=self._seed)
            self._selected_scenario_id = None
            self._selected_scenario_name = None
            self._duration_seconds = DEFAULT_DURATION_SECONDS
            self._control_mode = "fixed-time"
            self._run_mode = "live"
            return self._response()

    def step(self, num_ticks: int = 1) -> SimulationStateResponse:
        with self._lock:
            engine = self._get_engine()
            try:
                engine.step(num_ticks)
            except Exception as exc:
                engine.status = "error"
                engine.last_error = f"Traffic engine failed: {exc}"
                self._finalize_terminal_run_locked()
                raise SimulationRuntimeError(engine.last_error) from exc
            self._finalize_terminal_run_locked()
            return self._response()

    def load_playback(self, run_id: int) -> SimulationStateResponse:
        with self._lock:
            run = database.get_run_by_id(run_id)
            if not run:
                raise SimulationRuntimeError("Recorded run not found.")
            if str(run.get("run_mode") or "").lower() != "pre-record":
                raise SimulationRuntimeError("Only pre-record runs can be loaded for playback.")
            if str(run.get("status") or "").lower() != "completed":
                raise SimulationRuntimeError("Timeline generation must complete before playback.")
            timeline_path = str(run.get("timeline_path") or "").strip()
            if not timeline_path:
                raise SimulationRuntimeError("Recorded run has no timeline artifact.")

            playback_engine = TimelinePlaybackEngine(int(run_id), timeline_path)
            if playback_engine.status == "error":
                raise SimulationRuntimeError(playback_engine.last_error)
            playback_engine.seek(0)
            # Loading/validating the candidate cannot interrupt a live run.
            self._stop_background_runner_locked()
            if (
                self._engine is not None
                and self._engine.status in {"running", "paused", "error"}
                and self._active_run_id is not None
            ):
                reset_status = "error" if self._engine.status == "error" else "stopped"
                reset_reason = self._engine.last_error if reset_status == "error" else "Playback loaded; live run stopped."
                self._finalize_run_locked(reset_status, reset_reason or "Playback loaded.")
            elif self._engine is not None:
                self._engine.stop()

            self._engine = playback_engine
            self._run_mode = "playback"
            self._control_mode = "playback"
            self._selected_scenario_id = int(run["scenario_id"]) if run.get("scenario_id") is not None else None
            self._selected_scenario_name = run.get("scenario_name") or "Recorded scenario"
            self._duration_seconds = int(float(run.get("duration_seconds") or self._duration_seconds or DEFAULT_DURATION_SECONDS))
            self._active_run_id = None
            self._active_run_saved = False
            self._active_run_user_id = None
            return self._response()

    def start_playback(self) -> SimulationStateResponse:
        with self._lock:
            if self._run_mode != "playback" or self._engine is None:
                raise SimulationRuntimeError("Load a recorded run before playback.")
            self._engine.start(self._duration_seconds)
            if self._engine.status == "running":
                self._start_background_runner_locked()
            return self._response()

    def seek_playback(self, frame_index: int) -> SimulationStateResponse:
        with self._lock:
            if self._run_mode != "playback" or self._engine is None or not hasattr(self._engine, "seek"):
                raise SimulationRuntimeError("Load a recorded run before seeking.")
            self._engine.seek(frame_index)
            return self._response()

    def _get_engine(self, *, seed: int | None = None) -> TrafficEngine:
        if self._engine is None:
            self._replace_engine(seed=seed if seed is not None else self._seed)
        return self._engine

    def _replace_engine(self, *, seed: int) -> None:
        self._stop_background_runner_locked()
        if self._engine is not None:
            self._engine.stop()
        self._seed = int(seed)
        self._engine = TrafficEngine(seed=self._seed)
        self._engine.current_scenario_name = "No scenario selected"
        self._apply_control_mode(self._control_mode)

    def _start_background_runner_locked(self) -> None:
        if self._runner_thread is not None and self._runner_thread.is_alive():
            return
        stop_event = Event()
        self._runner_stop_event = stop_event
        self._runner_thread = Thread(
            target=self._run_step_loop,
            args=(stop_event,),
            name="smartflow-native-runtime",
            daemon=True,
        )
        self._runner_thread.start()

    def _stop_background_runner_locked(self) -> None:
        stop_event = self._runner_stop_event
        if stop_event is not None:
            stop_event.set()
        # A runner may be waiting for this lock. Never join it while holding it.
        # It checks its own cancellation event after acquiring the lock below.
        self._runner_stop_event = None
        self._runner_thread = None

    def _run_step_loop(self, stop_event: Event) -> None:
        next_tick = monotonic() + STEP_LENGTH
        while not stop_event.wait(max(0.0, next_tick-monotonic())):
            with self._lock:
                if stop_event.is_set():
                    return
                engine = self._engine
                if engine is None:
                    return
                if engine.status == "running":
                    try:
                        engine.step(1)
                    except Exception as exc:
                        engine.status = "error"
                        engine.last_error = f"Traffic engine failed: {exc}"
                if engine.status in {"completed", "error", "stopped"}:
                    self._finalize_terminal_run_locked()
                    stop_event.set()
                    return
            # Include computation in the wall-clock budget; do not add a full
            # sleep after every step or skip simulation ticks under load.
            next_tick = max(next_tick+STEP_LENGTH, monotonic())

    def _finalize_terminal_run_locked(self):
        engine = self._engine
        if engine is None or self._active_run_id is None or engine.status not in {"completed", "error", "stopped"}:
            return
        reason = (f"Simulation automatically completed at {engine.duration_limit}s limit."
                  if engine.status == "completed" else engine.last_error
                  if engine.status == "error" else "Simulation stopped.")
        self._finalize_run_locked(engine.status, reason)

    def _utc_now(self) -> str:
        return datetime.now(UTC).isoformat()

    def _normalize_control_mode(self, engine: TrafficEngine) -> str:
        return str(getattr(engine, "controller_provenance", self._control_mode) or self._control_mode).strip().lower().replace("_", "-")

    def _metrics_payload(self, engine: TrafficEngine) -> dict[str, Any]:
        metrics = getattr(engine, "_last_metrics", {}) or {}
        result = dict(metrics) if isinstance(metrics, dict) else {}
        if hasattr(engine, "experiment_metadata"):
            result["experiment"] = engine.experiment_metadata()
        return result

    def _save_run_metrics(self, run_id: int, metrics: dict[str, Any]) -> None:
        database.save_run_metrics(
            run_id=run_id,
            avg_waiting_time=metrics.get("avg_wait", 0),
            avg_queue_length=metrics.get("avg_queue", 0),
            max_queue_length=metrics.get("max_queue", 0),
            throughput=metrics.get("throughput", 0),
            avg_pedestrian_delay=metrics.get("avg_ped_delay", 0),
            raw_metrics_json=json.dumps(metrics),
        )

    def _begin_run_locked(self, engine: TrafficEngine, *, user_id: int | None) -> None:
        scenario_id = self._selected_scenario_id if self._selected_scenario_id is not None else None
        self._active_run_id = database.create_run(
            scenario_id=scenario_id,
            user_id=user_id,
            run_mode="live",
            control_mode=self._normalize_control_mode(engine),
            rl_model_id=(getattr(engine.runtime_policy, "artifact_metadata", {}) or {}).get("model_id"),
            status="running",
            seed=getattr(engine, "seed", None),
            notes=f"SMARTFLOW FastAPI live run ({self._duration_seconds}s limit)",
        )
        self._active_run_saved = False
        self._active_run_user_id = user_id
        engine.run_id = str(self._active_run_id)
        database.log_audit_event(
            user_id=user_id,
            action="api_start_simulation_run",
            target="simulation_runs",
            details=f"Started live run ID={self._active_run_id} for scenario '{self._selected_scenario_name or scenario_id}'.",
        )

    def _finalize_run_locked(self, run_status: str, reason: str) -> None:
        if self._active_run_id is None or self._active_run_saved or self._engine is None:
            return
        normalized_status = str(run_status or "completed").strip().lower() or "completed"
        metrics = self._metrics_payload(self._engine)
        duration_seconds = float(max(getattr(self._engine, "simulation_time", 0), 0))
        database.update_run(
            self._active_run_id,
            control_mode=self._normalize_control_mode(self._engine),
            status=normalized_status,
            end_time=self._utc_now(),
            duration_seconds=duration_seconds,
            notes=reason,
        )
        self._save_run_metrics(self._active_run_id, metrics)
        database.log_audit_event(
            user_id=self._active_run_user_id,
            action=f"api_{normalized_status}_simulation_run",
            target="simulation_runs",
            details=f"Run ID={self._active_run_id} ended with status '{normalized_status}' after {duration_seconds:.1f}s. {reason}",
        )
        self._active_run_saved = True
        self._active_run_id = None
        self._active_run_user_id = None

    def _scenario_from_request(self, scenario_id: int | None) -> dict[str, Any] | None:
        if scenario_id is None:
            return None
        scenario = database.get_scenario_by_id(scenario_id)
        if not scenario:
            raise SimulationRuntimeError("Scenario not found.")
        if bool(scenario.get("is_archived")):
            raise SimulationRuntimeError("Archived scenarios cannot be started.")
        return scenario

    def _engine_scenario_payload(self, scenario: dict[str, Any]) -> dict[str, Any]:
        return dict(scenario)

    def _configure_overrides(self, payload: SimulationConfigureRequest) -> dict[str, Any]:
        payload_dict = payload.model_dump(exclude_none=True)
        for ignored_key in ("scenario_id", "duration_seconds", "seed", "control_mode"):
            payload_dict.pop(ignored_key, None)
        native = payload_dict.pop("engine_config", {})
        payload_dict.update(native)
        return payload_dict

    def _apply_control_mode(self, control_mode: str | None) -> None:
        from services.native_controller import apply_controller
        requested = control_mode or self._control_mode
        if self._engine is not None:
            self._control_mode = apply_controller(self._engine, requested)

    def _response(self) -> SimulationStateResponse:
        engine = self._engine
        if engine is None:
            state = self._idle_state()
            status = "stopped"
        else:
            state = engine.to_dict()
            status = str(state.get("status") or engine.status)
        state["flow"] = self._flow_snapshot(status)
        return SimulationStateResponse(
            status=status,
            selected_scenario_id=self._selected_scenario_id,
            selected_scenario_name=self._selected_scenario_name,
            duration_seconds=self._duration_seconds,
            seed=self._seed,
            control_mode=self._control_mode,
            state=state,
        )

    def _idle_state(self) -> dict[str, Any]:
        return {
            "time": 0.0,
            "step_length": STEP_LENGTH,
            "status": "stopped",
            "phase": "ALL_RED",
            "phase_remaining": 0.0,
            "cycle_count": 0,
            "controller_type": "fixed_time",
            "vehicles": [],
            "vehicle_count": 0,
            "pedestrians": [],
            "pedestrian_count": 0,
            "queues": {},
            "metrics": {},
            "events": [],
            "scenario": {
                "intersection_id": DEFAULT_INTERSECTION_ID,
                "traffic_density": "medium",
                "pedestrian_density": "medium",
                "emergency_mode": "disabled",
                "road_constraint": "None",
            },
            "dashboard": {
                "current_scenario_name": "No scenario selected",
                "control_mode_label": "Fixed-Time (Python)",
                "controller_provenance": "fixed-time",
                "controller_provenance_label": "Fixed-Time",
                "last_action": "Not started",
                "last_error": "None",
                "run_id": "-",
            },
            "charts": {
                "traffic_flow": [],
                "wait_time": [],
                "queue_length": [],
                "throughput": [],
            },
            "visual": {},
            "traffic_lights": {},
        }

    def _flow_snapshot(self, engine_status: str) -> dict[str, Any]:
        flow_state = FlowState.IDLE.value
        has_completed_run = False
        if self._run_mode == "playback" and engine_status == "running":
            flow_state = FlowState.PLAYING_BACK.value
        elif self._run_mode == "playback" and engine_status in {"stopped", "paused"}:
            flow_state = FlowState.PAUSED.value
        elif engine_status == "running":
            flow_state = FlowState.LIVE_RUNNING.value
        elif engine_status == "paused":
            flow_state = FlowState.PAUSED.value
        elif engine_status == "completed":
            flow_state = FlowState.COMPLETED.value
            has_completed_run = True
        elif engine_status == "error":
            flow_state = FlowState.ERROR.value
        elif self._selected_scenario_id is not None:
            flow_state = FlowState.SCENARIO_SELECTED.value

        last_error = None
        if self._engine is not None:
            last_error = getattr(self._engine, "last_error", None)

        return build_flow_snapshot(
            flow_state=flow_state,
            selected_scenario_id=self._selected_scenario_id,
            selected_scenario_name=self._selected_scenario_name,
            has_completed_run=has_completed_run,
            last_error=last_error,
            run_mode=self._run_mode,
        )


simulation_runtime = SimulationRuntime()
