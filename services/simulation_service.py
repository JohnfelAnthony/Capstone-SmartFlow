"""Simulation service - shared engine lifecycle manager with guarded control."""

from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from threading import RLock
from typing import Optional

import config
import database
from services.simulation_flow import FlowState, build_flow_snapshot
from simulation.sumo_config import DEFAULT_INTERSECTION_ID, get_intersection_assets
from simulation.sumo_engine import SumoSimulationEngine

try:
    from flask import has_request_context, session
except ImportError:  # pragma: no cover - exercised in dependency-light unit environments
    def has_request_context() -> bool:
        return False

    session = {}

_engine: Optional[SumoSimulationEngine] = None
_engine_lock = RLock()
_engine_owner: str | None = None
_supervisor_failure_count = 0
_supervisor_next_retry_at: datetime | None = None
_generation_progress: int = 0
_generation_frame_count: int = 0
_generation_estimated_frame_count: int = 0
_generation_artifacts: dict[str, object] = {}
_selected_scenario_id: int | None = None
_selected_scenario_name: str | None = None
_flow_state = FlowState.IDLE.value
_has_completed_run = False
_active_run_id: int | None = None
_active_run_saved = False
_run_mode: str = "live"


def _utc_now() -> datetime:
    return datetime.now(UTC)


def _current_owner_token() -> str:
    if has_request_context():
        session_token = session.get("session_token")
        if session_token:
            return str(session_token)
    return "system"


def _is_session_owner_active(owner_token: str | None) -> bool:
    if not owner_token or owner_token == "system":
        return owner_token == "system"
    return database.get_session_by_token(owner_token) is not None


def _owner_label(owner_token: str | None) -> str:
    if not owner_token:
        return "another session"
    if owner_token == "system":
        return "the system controller"
    return "another active session"


def _reset_supervisor_state():
    global _supervisor_failure_count, _supervisor_next_retry_at
    _supervisor_failure_count = 0
    _supervisor_next_retry_at = None


def _claim_owner(request_owner: str):
    global _engine_owner
    _engine_owner = request_owner


def _clear_owner():
    global _engine_owner
    _engine_owner = None


def _set_selected_scenario(scenario_id: int | None, scenario_name: str | None):
    global _selected_scenario_id, _selected_scenario_name
    _selected_scenario_id = scenario_id
    _selected_scenario_name = (scenario_name or "").strip() or None


def _sync_flow_state(engine: SumoSimulationEngine):
    global _flow_state

    if _flow_state == FlowState.GENERATING.value:
        return
    if (
        _flow_state == FlowState.READY_TO_PLAY.value
        and _run_mode in {"pre-record", "playback"}
        and _active_run_id is not None
        and _selected_scenario_id is not None
        and engine.status in {"stopped", "completed"}
    ):
        return
    if _flow_state == FlowState.LOGGED_OUT.value and engine.status == "stopped":
        return

    if engine.status == "running":
        _flow_state = (
            FlowState.PLAYING_BACK.value
            if _run_mode == "playback"
            else FlowState.LIVE_RUNNING.value
        )
        return
    if engine.status == "paused":
        _flow_state = FlowState.PAUSED.value
        return
    if engine.status == "error":
        _flow_state = FlowState.ERROR.value
        return
    if _has_completed_run and _selected_scenario_id is not None:
        _flow_state = FlowState.COMPLETED.value
        return
    if _selected_scenario_id is not None:
        _flow_state = FlowState.SCENARIO_SELECTED.value
        return
    _flow_state = FlowState.IDLE.value


def _set_idle_scenario_name(engine: SumoSimulationEngine):
    if _selected_scenario_name:
        engine.current_scenario_name = _selected_scenario_name
    else:
        engine.current_scenario_name = "No scenario selected"


def _clear_flow_context():
    global _has_completed_run, _generation_progress, _generation_frame_count
    global _generation_estimated_frame_count, _generation_artifacts
    global _active_run_id, _active_run_saved, _run_mode
    _set_selected_scenario(None, None)
    _has_completed_run = False
    _generation_progress = 0
    _generation_frame_count = 0
    _generation_estimated_frame_count = 0
    _generation_artifacts = {}
    _active_run_id = None
    _active_run_saved = False
    _run_mode = "live"


def _current_user_id() -> int | None:
    if not has_request_context():
        return None
    user_id = session.get("user_id")
    if user_id is None:
        return None
    try:
        return int(user_id)
    except (TypeError, ValueError):
        return None


def _normalize_control_mode(control_mode: str | None) -> str:
    normalized = str(control_mode or "fixed-time").strip().lower().replace("_", "-")
    return normalized or "fixed-time"


def _metrics_payload(engine: SumoSimulationEngine) -> dict:
    metrics = getattr(engine, "_last_metrics", {}) or {}
    return metrics if isinstance(metrics, dict) else {}


def _save_run_metrics(run_id: int, metrics: dict):
    database.save_run_metrics(
        run_id=run_id,
        avg_waiting_time=metrics.get("avg_wait", 0),
        avg_queue_length=metrics.get("avg_queue", 0),
        max_queue_length=metrics.get("max_queue", 0),
        throughput=metrics.get("throughput", 0),
        avg_pedestrian_delay=metrics.get("avg_ped_delay", 0),
        raw_metrics_json=json.dumps(metrics),
    )


def _state_dict(engine) -> dict:
    state_reader = getattr(engine, "get_state", None)
    if callable(state_reader):
        return state_reader()
    return engine.to_dict()


def _generation_state_payload(engine) -> dict:
    return {
        "active": _flow_state == FlowState.GENERATING.value,
        "progress_percent": int(_generation_progress or 0),
        "frame_count": int(_generation_frame_count or 0),
        "estimated_frame_count": int(_generation_estimated_frame_count or 0),
        "selected_scenario_name": _selected_scenario_name or getattr(engine, "current_scenario_name", None),
        "run_id": _active_run_id,
        "run_mode": _run_mode,
        "controller_provenance": _generation_artifacts.get("controller_provenance")
        or getattr(engine, "controller_provenance", None),
        "controller_provenance_label": _generation_artifacts.get("controller_provenance_label")
        or getattr(engine, "controller_provenance_label", None),
        "control_mode_label": _generation_artifacts.get("control_mode_label")
        or getattr(engine, "control_mode_label", None),
        "artifacts": dict(_generation_artifacts),
    }


def _begin_live_run(engine: SumoSimulationEngine, duration_limit: int):
    global _active_run_id, _active_run_saved
    database.init_db()
    user_id = _current_user_id()
    persisted_scenario_id = (
        _selected_scenario_id
        if _selected_scenario_id is not None and database.get_scenario_by_id(_selected_scenario_id)
        else None
    )
    _active_run_id = database.create_run(
        scenario_id=persisted_scenario_id,
        user_id=user_id,
        control_mode=_normalize_control_mode(getattr(engine, "controller_type", "fixed-time")),
        status="running",
        seed=getattr(engine, "seed", None),
        notes=f"SMARTFLOW live scenario run ({duration_limit}s limit)",
    )
    _active_run_saved = False
    database.log_audit_event(
        user_id=user_id,
        action="start_simulation_run",
        target="simulation_runs",
        details=(
            f"Started live run ID={_active_run_id} for scenario "
            f"'{_selected_scenario_name or _selected_scenario_id}' with a {duration_limit}s limit."
        ),
    )


def _begin_pre_record_run(engine: SumoSimulationEngine, duration_limit: int):
    global _active_run_id, _active_run_saved
    database.init_db()
    user_id = _current_user_id()
    persisted_scenario_id = (
        _selected_scenario_id
        if _selected_scenario_id is not None and database.get_scenario_by_id(_selected_scenario_id)
        else None
    )
    _active_run_id = database.create_run(
        scenario_id=persisted_scenario_id,
        user_id=user_id,
        run_mode="pre-record",
        control_mode=_normalize_control_mode(getattr(engine, "controller_type", "fixed-time")),
        status="running",
        seed=getattr(engine, "seed", None),
        notes=f"SMARTFLOW pre-record timeline job ({duration_limit}s limit)",
    )
    _active_run_saved = False
    database.log_audit_event(
        user_id=user_id,
        action="start_timeline_generation",
        target="simulation_runs",
        details=(
            f"Started pre-record timeline generation for run ID={_active_run_id} "
            f"on scenario '{_selected_scenario_name or _selected_scenario_id}' "
            f"with a {duration_limit}s limit."
        ),
    )


def _finalize_active_run(engine: SumoSimulationEngine, status: str, *, reason: str):
    global _active_run_saved
    if _run_mode == "playback" or _active_run_id is None or _active_run_saved:
        return

    normalized_status = str(status or "completed").strip().lower() or "completed"
    metrics = _metrics_payload(engine)
    duration_seconds = float(max(getattr(engine, "simulation_time", 0), 0))

    database.update_run(
        _active_run_id,
        control_mode=_normalize_control_mode(getattr(engine, "controller_type", "fixed-time")),
        status=normalized_status,
        end_time=_utc_now().isoformat(),
        duration_seconds=duration_seconds,
        notes=reason,
    )
    _save_run_metrics(_active_run_id, metrics)
    database.log_audit_event(
        user_id=_current_user_id(),
        action=f"{normalized_status}_simulation_run",
        target="simulation_runs",
        details=(
            f"Run ID={_active_run_id} for scenario "
            f"'{_selected_scenario_name or _selected_scenario_id}' ended with status "
            f"'{normalized_status}' after {duration_seconds:.1f}s. {reason}"
        ),
    )
    _active_run_saved = True


def _control_allowed(request_owner: str, *, allow_takeover_when_idle: bool = False) -> bool:
    engine = get_engine()
    if _engine_owner in (None, request_owner):
        return True
    if not _is_session_owner_active(_engine_owner):
        return True
    return allow_takeover_when_idle and engine.status in {"stopped", "error"}


def _deny_control(action_name: str):
    engine = get_engine()
    engine.last_error = f"Simulation control denied: {action_name} is locked by {_owner_label(_engine_owner)}."
    engine._add_event("warning", engine.last_error)


def _claim_if_allowed(action_name: str, *, allow_takeover_when_idle: bool = False, silent: bool = False) -> str | None:
    request_owner = _current_owner_token()
    if _control_allowed(request_owner, allow_takeover_when_idle=allow_takeover_when_idle):
        _claim_owner(request_owner)
        return request_owner
    if not silent:
        _deny_control(action_name)
    return None


def _block_generation_mutation(engine, action_name: str) -> bool:
    if _flow_state != FlowState.GENERATING.value:
        return False
    engine.last_error = f"Cannot {action_name} while a timeline is still generating."
    engine.last_action = "Action blocked"
    engine._add_event("warning", engine.last_error)
    return True


def _schedule_retry(engine: SumoSimulationEngine, failure_message: str):
    global _supervisor_failure_count, _supervisor_next_retry_at

    _supervisor_failure_count += 1
    capped_failures = min(_supervisor_failure_count, config.SIMULATION_SUPERVISOR_MAX_RETRIES)
    delay_seconds = min(
        config.SIMULATION_SUPERVISOR_MAX_DELAY_SECONDS,
        config.SIMULATION_SUPERVISOR_BASE_DELAY_SECONDS * (2 ** max(0, capped_failures - 1)),
    )
    _supervisor_next_retry_at = _utc_now() + timedelta(seconds=delay_seconds)
    engine.last_error = failure_message
    engine.last_action = f"Supervisor retry scheduled in {delay_seconds}s"
    engine._add_event(
        "warning",
        f"SUMO supervisor scheduled retry #{_supervisor_failure_count} in {delay_seconds}s",
    )


def _recover_if_ready(engine: SumoSimulationEngine) -> bool:
    if engine.status != "error":
        return engine.status == "running"

    if _supervisor_failure_count >= config.SIMULATION_SUPERVISOR_MAX_RETRIES:
        engine.last_action = "Automatic recovery exhausted; manual restart required"
        return False

    if _supervisor_next_retry_at and _utc_now() < _supervisor_next_retry_at:
        return False

    engine._add_event("warning", "SUMO supervisor attempting recovery")
    engine.start()
    if engine.status == "running":
        _reset_supervisor_state()
        engine.last_action = "Supervisor recovered the simulation"
        engine._add_event("info", "SUMO supervisor recovered the simulation")
        _sync_flow_state(engine)
        return True

    _schedule_retry(engine, engine.last_error or "SUMO recovery attempt failed")
    _sync_flow_state(engine)
    return False


def get_engine() -> SumoSimulationEngine:
    global _engine
    with _engine_lock:
        if _engine is None:
            _engine = SumoSimulationEngine(seed=42)
            _set_idle_scenario_name(_engine)
            _sync_flow_state(_engine)
        return _engine


def reset_engine(seed: int = 42):
    global _engine
    with _engine_lock:
        _engine = SumoSimulationEngine(seed=seed)
        _set_idle_scenario_name(_engine)
        _clear_owner()
        _reset_supervisor_state()
        _sync_flow_state(_engine)


def start(duration_limit: int = 300, run_mode: str = "live") -> str:
    global _has_completed_run, _flow_state, _run_mode, _active_run_id, _engine
    global _generation_progress, _generation_frame_count, _generation_estimated_frame_count
    global _generation_artifacts, _active_run_saved
    with _engine_lock:
        if _claim_if_allowed("start", allow_takeover_when_idle=True) is None:
            return get_engine().status

        engine = get_engine()
        if _selected_scenario_id is None:
            engine.last_error = "Select a scenario before starting the simulation."
            engine.last_action = "Start blocked"
            engine._add_event("warning", engine.last_error)
            _sync_flow_state(engine)
            return engine.status

        _has_completed_run = False
        _run_mode = run_mode

        if run_mode == "pre-record":
            _flow_state = FlowState.GENERATING.value
            _generation_progress = 0
            _generation_frame_count = 0
            _generation_estimated_frame_count = max(
                1,
                int(round((duration_limit or 0) / max(float(getattr(engine, "step_length", 0.1) or 0.1), 0.001))) + 1,
            )
            _generation_artifacts = {
                "controller_provenance": getattr(engine, "controller_provenance", None),
                "controller_provenance_label": getattr(engine, "controller_provenance_label", None),
                "control_mode_label": getattr(engine, "control_mode_label", None),
            }
            _begin_pre_record_run(engine, duration_limit)
            engine.last_action = "Generating timeline..."
            
            from services.timeline_generator import generate_timeline
            
            def _on_gen_complete(status, payload):
                global _flow_state, _generation_progress, _generation_frame_count
                global _generation_estimated_frame_count, _generation_artifacts, _engine
                with _engine_lock:
                    if status == "completed":
                        from simulation.timeline_engine import TimelinePlaybackEngine

                        payload = payload or {}
                        _generation_artifacts = dict(payload)
                        _generation_frame_count = int(payload.get("frame_count") or _generation_frame_count or 0)
                        _generation_estimated_frame_count = int(
                            payload.get("estimated_frame_count") or _generation_estimated_frame_count or 0
                        )
                        _engine = TimelinePlaybackEngine(_active_run_id, payload.get("timeline_path"))
                        if _engine.status == "error":
                            _flow_state = FlowState.ERROR.value
                            _engine.last_action = "Timeline load failed"
                        else:
                            _flow_state = FlowState.READY_TO_PLAY.value
                            _generation_progress = 100
                            _engine.last_action = "Timeline generated and ready to play"
                            _engine.last_error = "None"
                    else:
                        _flow_state = FlowState.ERROR.value
                        _generation_artifacts = {}
                        engine.last_error = payload or "Generation failed"
                        engine.last_action = "Generation failed"
            
            def _on_gen_progress(progress_payload):
                global _generation_progress, _generation_frame_count, _generation_estimated_frame_count
                if isinstance(progress_payload, dict):
                    _generation_progress = int(progress_payload.get("progress_percent") or 0)
                    _generation_frame_count = int(progress_payload.get("frame_count") or 0)
                    _generation_estimated_frame_count = int(
                        progress_payload.get("estimated_frame_count") or _generation_estimated_frame_count or 0
                    )
                else:
                    _generation_progress = int(progress_payload or 0)
                
            generate_timeline(_selected_scenario_id, duration_limit, _active_run_id, _on_gen_complete, _on_gen_progress)
            return "generating"
            
        elif run_mode == "playback":
            if _active_run_id is None:
                engine.last_error = "No active run to playback."
                _sync_flow_state(engine)
                return engine.status
                
            from simulation.timeline_engine import TimelinePlaybackEngine
            if not isinstance(_engine, TimelinePlaybackEngine):
                run_record = database.get_run_by_id(_active_run_id)
                _engine = TimelinePlaybackEngine(_active_run_id, run_record.get("timeline_path") if run_record else None)
            _engine.start(duration_limit)
            if _engine.status == "running":
                database.log_audit_event(
                    user_id=_current_user_id(),
                    action="start_playback_run",
                    target="simulation_runs",
                    details=(
                        f"Started playback for run ID={_active_run_id} "
                        f"on scenario '{_selected_scenario_name or _selected_scenario_id}'."
                    ),
                )
            _sync_flow_state(_engine)
            return _engine.status
            
        else:
            _begin_live_run(engine, duration_limit)
            engine.start(duration_limit)
            if engine.status == "running":
                _reset_supervisor_state()
            elif engine.status == "error":
                _finalize_active_run(
                    engine,
                    "error",
                    reason=engine.last_error or "SUMO startup failed before the live run could begin.",
                )
                _reset_supervisor_state()
            _sync_flow_state(engine)
            return engine.status


def load_playback(run_id: int) -> bool:
    """Prepare the service to playback an existing timeline run."""
    global _active_run_id, _flow_state, _run_mode, _selected_scenario_id, _selected_scenario_name
    global _has_completed_run, _engine, _generation_artifacts, _generation_progress
    global _generation_frame_count, _generation_estimated_frame_count
    with _engine_lock:
        if _claim_if_allowed("load_playback", allow_takeover_when_idle=True) is None:
            return False
        if _block_generation_mutation(get_engine(), "load a saved playback"):
            return False
             
        run = database.get_run_by_id(run_id)
        if not run:
            return False
        if str(run.get("run_mode") or "live") != "pre-record":
            return False
            
        previous_run_mode = _run_mode
        old_engine = get_engine()
        if old_engine.status in {"running", "paused", "error"} and previous_run_mode != "playback":
            previous_status = "error" if old_engine.status == "error" else "stopped"
            previous_reason = (
                old_engine.last_error or "Active run closed while loading a saved playback."
                if previous_status == "error"
                else "Active live run stopped to load a saved playback."
            )
            _finalize_active_run(old_engine, previous_status, reason=previous_reason)
        old_engine.stop()

        _active_run_id = run_id
        _selected_scenario_id = run['scenario_id']
        _selected_scenario_name = run.get('scenario_name')
        _has_completed_run = False
        _run_mode = "playback"
        _flow_state = FlowState.READY_TO_PLAY.value
        _generation_progress = 100
        
        # Reset the runtime and preload the recorded timeline without starting playback yet.
        from simulation.timeline_engine import TimelinePlaybackEngine
        _engine = TimelinePlaybackEngine(run_id, run.get("timeline_path"))
        if _engine.status == "error":
            return False
        playback_state = _engine.get_state().get("playback", {})
        _generation_frame_count = int(playback_state.get("frame_count", 0) or 0)
        _generation_estimated_frame_count = _generation_frame_count
        _generation_artifacts = {
            "timeline_path": run.get("timeline_path"),
            "controller_provenance": getattr(_engine, "source_controller_provenance", None),
            "controller_provenance_label": getattr(_engine, "source_controller_provenance", "").replace("-", " ").title()
            if getattr(_engine, "source_controller_provenance", None)
            else None,
            "control_mode_label": getattr(_engine, "control_mode_label", None),
        }
        _flow_state = FlowState.READY_TO_PLAY.value
        database.log_audit_event(
            user_id=_current_user_id(),
            action="load_playback_run",
            target="simulation_runs",
            details=(
                f"Loaded recorded playback for run ID={run_id} "
                f"on scenario '{_selected_scenario_name or _selected_scenario_id}'."
            ),
        )
        return True


def pause() -> str:
    with _engine_lock:
        if _claim_if_allowed("pause") is None:
            return get_engine().status
        engine = get_engine()
        engine.pause()
        _sync_flow_state(engine)
        return engine.status


def resume() -> str:
    with _engine_lock:
        if _claim_if_allowed("resume") is None:
            return get_engine().status
        engine = get_engine()
        engine.resume()
        _sync_flow_state(engine)
        return engine.status


def stop() -> str:
    global _has_completed_run
    with _engine_lock:
        if _claim_if_allowed("stop") is None:
            return get_engine().status
        engine = get_engine()
        ended_run = (
            engine.status in {"running", "paused", "error"}
            and _selected_scenario_id is not None
            and _run_mode != "playback"
        )
        _has_completed_run = ended_run
        if ended_run:
            stop_status = "error" if engine.status == "error" else "stopped"
            stop_reason = (
                engine.last_error or "Simulation stopped after an error."
                if stop_status == "error"
                else "Simulation stopped manually by the user."
            )
            _finalize_active_run(engine, stop_status, reason=stop_reason)
        engine.stop()
        _clear_owner()
        _reset_supervisor_state()
        if _run_mode == "playback" and _active_run_id is not None and _selected_scenario_id is not None:
            _flow_state = FlowState.READY_TO_PLAY.value
        _sync_flow_state(engine)
        return engine.status


def reset() -> str:
    global _has_completed_run, _active_run_id, _active_run_saved, _run_mode, _flow_state
    global _generation_progress, _generation_frame_count, _generation_estimated_frame_count, _generation_artifacts
    with _engine_lock:
        if _claim_if_allowed("reset", allow_takeover_when_idle=True) is None:
            return get_engine().status
        if _block_generation_mutation(get_engine(), "reset the simulation"):
            return get_engine().status

        old_engine = get_engine()
        old_settings = {
            "intersection_id": getattr(old_engine, "intersection_id", DEFAULT_INTERSECTION_ID),
            "traffic_density": old_engine.traffic_density,
            "pedestrian_density": old_engine.pedestrian_density,
            "emergency_mode": old_engine.emergency_mode,
            "road_constraint": old_engine.road_constraint,
        }
        if old_engine.status in {"running", "paused", "error"}:
            reset_status = "error" if old_engine.status == "error" else "stopped"
            reset_reason = (
                old_engine.last_error or "Simulation reset after an error."
                if reset_status == "error"
                else "Simulation reset by the user."
            )
            _finalize_active_run(old_engine, reset_status, reason=reset_reason)
        old_engine.stop()
        reset_engine(seed=42)
        engine = get_engine()
        engine.configure(**old_settings)
        _clear_flow_context()
        _set_idle_scenario_name(engine)
        _flow_state = FlowState.IDLE.value
        _sync_flow_state(engine)
        return engine.status


def step(num_ticks: int = 1):
    with _engine_lock:
        if _claim_if_allowed("step", silent=True) is None:
            return

        engine = get_engine()
        if engine.status == "error" and not _recover_if_ready(engine):
            return
        if engine.status != "running":
            return

        engine.step(num_ticks)
        if engine.status == "completed":
            _has_completed_run = _run_mode != "playback"
            _clear_owner()
            _reset_supervisor_state()
            try:
                if _run_mode == "playback":
                    _flow_state = FlowState.READY_TO_PLAY.value
                else:
                    _finalize_active_run(
                        engine,
                        "completed",
                        reason=f"Simulation automatically completed at the {engine.duration_limit}s limit.",
                    )
            except Exception as e:
                engine.last_error = f"Failed to save metrics: {e}"
        elif engine.status == "error":
            _reset_supervisor_state()
        else:
            _reset_supervisor_state()
        _sync_flow_state(engine)


def get_state() -> dict:
    engine = get_engine()
    state = _state_dict(engine)
    dashboard = state.setdefault("dashboard", {})
    if _active_run_id is not None:
        dashboard["run_id"] = _active_run_id
    state["generation"] = _generation_state_payload(engine)
    state["flow"] = get_flow_snapshot()
    return state


def get_flow_snapshot() -> dict:
    engine = get_engine()
    _sync_flow_state(engine)
    return build_flow_snapshot(
        flow_state=_flow_state,
        selected_scenario_id=_selected_scenario_id,
        selected_scenario_name=_selected_scenario_name or getattr(engine, "current_scenario_name", None),
        has_completed_run=_has_completed_run,
        last_error=engine.last_error,
        generation_progress=_generation_progress,
        run_mode=_run_mode,
    )


def current_status() -> str:
    return get_engine().status


def current_intersection_id() -> str:
    engine = get_engine()
    return str(getattr(engine, "intersection_id", DEFAULT_INTERSECTION_ID) or DEFAULT_INTERSECTION_ID)


def get_active_intersection_assets():
    return get_intersection_assets(current_intersection_id())


def configure(**kwargs):
    with _engine_lock:
        if _claim_if_allowed("configure", allow_takeover_when_idle=True) is None:
            return
        engine = get_engine()
        if _block_generation_mutation(engine, "change scenario settings"):
            return
        if _run_mode == "playback":
            engine.last_error = "Playback uses recorded data. Reset or load a live scenario before changing settings."
            engine.last_action = "Scenario settings blocked"
            engine._add_event("warning", engine.last_error)
            return
        engine.configure(**kwargs)
        _sync_flow_state(engine)


def load_scenario(scenario_dict: dict):
    global _has_completed_run, _active_run_id, _active_run_saved, _run_mode, _flow_state
    global _generation_progress, _generation_frame_count, _generation_estimated_frame_count, _generation_artifacts
    with _engine_lock:
        if _claim_if_allowed("load scenario", allow_takeover_when_idle=True) is None:
            return
        engine = get_engine()
        if _block_generation_mutation(engine, "load a new scenario"):
            return
        if _run_mode == "playback":
            engine.stop()
            reset_engine(seed=getattr(engine, "seed", 42))
            engine = get_engine()
        if engine.status in {"running", "paused"} and _run_mode != "playback":
            engine.last_error = "Stop or reset the current run before loading a different scenario."
            engine.last_action = "Scenario change blocked"
            engine._add_event("warning", engine.last_error)
            _sync_flow_state(engine)
            return
        if engine.status in {"stopped", "error"}:
            reset_engine(seed=engine.seed)
            engine = get_engine()
        engine.configure_from_scenario(scenario_dict)
        _set_selected_scenario(scenario_dict.get("id"), scenario_dict.get("name"))
        _has_completed_run = False
        _active_run_id = None
        _active_run_saved = False
        _run_mode = "live"
        _generation_progress = 0
        _generation_frame_count = 0
        _generation_estimated_frame_count = 0
        _generation_artifacts = {}
        _flow_state = FlowState.SCENARIO_SELECTED.value
        _sync_flow_state(engine)


def clear_selected_scenario():
    with _engine_lock:
        engine = get_engine()
        if _block_generation_mutation(engine, "clear the selected scenario"):
            return
        if engine.status in {"running", "paused", "error"}:
            clear_status = "error" if engine.status == "error" else "stopped"
            clear_reason = (
                engine.last_error or "Scenario cleared after an error."
                if clear_status == "error"
                else "Selected scenario cleared by the user."
            )
            _finalize_active_run(engine, clear_status, reason=clear_reason)
        current_seed = get_engine().seed
        reset_engine(seed=current_seed)
        engine = get_engine()
        _clear_flow_context()
        _set_idle_scenario_name(engine)
        _sync_flow_state(engine)


def reset_session_state():
    global _flow_state
    with _engine_lock:
        engine = get_engine()
        if engine.status in {"running", "paused", "error"}:
            session_end_status = "error" if engine.status == "error" else "stopped"
            session_end_reason = (
                engine.last_error or "Session reset after an error."
                if session_end_status == "error"
                else "Simulation session ended during logout."
            )
            _finalize_active_run(engine, session_end_status, reason=session_end_reason)
        current_seed = get_engine().seed
        reset_engine(seed=current_seed)
        engine = get_engine()
        _clear_flow_context()
        _set_idle_scenario_name(engine)
        _flow_state = FlowState.LOGGED_OUT.value


def restore_authenticated_state():
    global _flow_state
    with _engine_lock:
        engine = get_engine()
        if _flow_state != FlowState.LOGGED_OUT.value:
            return
        _flow_state = (
            FlowState.SCENARIO_SELECTED.value
            if _selected_scenario_id is not None
            else FlowState.IDLE.value
        )
        _sync_flow_state(engine)


def seek_playback(frame_index: int) -> str:
    global _flow_state
    with _engine_lock:
        engine = get_engine()
        seeker = getattr(engine, "seek", None)
        if not callable(seeker):
            return engine.status
        seeker(frame_index)
        if _selected_scenario_id is not None:
            if engine.status == "running":
                _flow_state = FlowState.PLAYING_BACK.value
            elif engine.status == "paused":
                _flow_state = FlowState.PAUSED.value
            else:
                _flow_state = FlowState.READY_TO_PLAY.value
        return engine.status
