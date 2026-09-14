"""Simulation flow state helpers for SMARTFLOW."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from enum import Enum


class FlowState(str, Enum):
    IDLE = "IDLE"
    SCENARIO_SELECTED = "SCENARIO_SELECTED"
    GENERATING = "GENERATING"
    READY_TO_PLAY = "READY_TO_PLAY"
    LIVE_RUNNING = "LIVE_RUNNING"
    PLAYING_BACK = "PLAYING_BACK"
    PAUSED = "PAUSED"
    COMPLETED = "COMPLETED"
    ERROR = "ERROR"
    LOGGED_OUT = "LOGGED_OUT"


@dataclass(slots=True)
class FlowSnapshot:
    state: str
    tone: str
    status_label: str
    status_detail: str
    live_indicator_label: str
    selected_scenario_id: int | None = None
    selected_scenario_name: str | None = None
    has_selected_scenario: bool = False
    has_completed_run: bool = False
    progress: int = 0
    controls: dict[str, bool] = field(default_factory=dict)

    def to_dict(self) -> dict:
        return asdict(self)


def build_flow_snapshot(
    *,
    flow_state: str,
    selected_scenario_id: int | None,
    selected_scenario_name: str | None,
    has_completed_run: bool,
    last_error: str | None = None,
    generation_progress: int = 0,
    run_mode: str = "live",
) -> dict:
    has_selected_scenario = selected_scenario_id is not None
    scenario_name = (selected_scenario_name or "").strip() or None

    if flow_state == FlowState.GENERATING.value:
        snapshot = FlowSnapshot(
            state=flow_state,
            tone="running",
            status_label="Generating Timeline",
            status_detail=f"Fast-forwarding timeline for {scenario_name or 'the selected scenario'}.",
            live_indicator_label="BUSY",
            selected_scenario_id=selected_scenario_id,
            selected_scenario_name=scenario_name,
            has_selected_scenario=has_selected_scenario,
            has_completed_run=False,
            progress=generation_progress,
            controls={"start": False, "pause": False, "stop": False, "reset": False},
        )
        return snapshot.to_dict()

    if flow_state == FlowState.READY_TO_PLAY.value:
        snapshot = FlowSnapshot(
            state=flow_state,
            tone="ready",
            status_label="Timeline Ready",
            status_detail="Timeline generated. Press Play Recording to review it.",
            live_indicator_label="READY",
            selected_scenario_id=selected_scenario_id,
            selected_scenario_name=scenario_name,
            has_selected_scenario=has_selected_scenario,
            has_completed_run=False,
            controls={"start": True, "pause": False, "stop": False, "reset": True},
        )
        return snapshot.to_dict()

    if flow_state == FlowState.PLAYING_BACK.value:
        snapshot = FlowSnapshot(
            state=flow_state,
            tone="running",
            status_label="Playing Back",
            status_detail="Streaming pre-recorded timeline.",
            live_indicator_label="PLAYING",
            selected_scenario_id=selected_scenario_id,
            selected_scenario_name=scenario_name,
            has_selected_scenario=has_selected_scenario,
            has_completed_run=False,
            controls={"start": False, "pause": True, "stop": True, "reset": False},
        )
        return snapshot.to_dict()

    if flow_state == FlowState.LIVE_RUNNING.value:
        snapshot = FlowSnapshot(
            state=flow_state,
            tone="running",
            status_label="Live Running",
            status_detail=f"Streaming live updates for {scenario_name or 'the selected scenario'}.",
            live_indicator_label="LIVE",
            selected_scenario_id=selected_scenario_id,
            selected_scenario_name=scenario_name,
            has_selected_scenario=has_selected_scenario,
            has_completed_run=False,
            controls={"start": False, "pause": True, "stop": True, "reset": False},
        )
        return snapshot.to_dict()

    if flow_state == FlowState.PAUSED.value:
        pause_detail = (
            "Recorded scenario playback is paused and can be resumed."
            if run_mode == "playback"
            else "The live scenario is paused and can be resumed."
        )
        snapshot = FlowSnapshot(
            state=flow_state,
            tone="paused",
            status_label="Paused",
            status_detail=pause_detail,
            live_indicator_label="PAUSED",
            selected_scenario_id=selected_scenario_id,
            selected_scenario_name=scenario_name,
            has_selected_scenario=has_selected_scenario,
            has_completed_run=False,
            controls={"start": True, "pause": False, "stop": True, "reset": True},
        )
        return snapshot.to_dict()

    if flow_state == FlowState.ERROR.value:
        error_text = (last_error or "").strip() or "Simulation runtime error."
        snapshot = FlowSnapshot(
            state=flow_state,
            tone="error",
            status_label="Error",
            status_detail=error_text,
            live_indicator_label="ERROR",
            selected_scenario_id=selected_scenario_id,
            selected_scenario_name=scenario_name,
            has_selected_scenario=has_selected_scenario,
            has_completed_run=False,
            controls={"start": False, "pause": False, "stop": True, "reset": True},
        )
        return snapshot.to_dict()

    if flow_state == FlowState.COMPLETED.value:
        snapshot = FlowSnapshot(
            state=flow_state,
            tone="completed",
            status_label="Completed",
            status_detail="The previous live run has ended. Reset before starting again.",
            live_indicator_label="DONE",
            selected_scenario_id=selected_scenario_id,
            selected_scenario_name=scenario_name,
            has_selected_scenario=has_selected_scenario,
            has_completed_run=has_completed_run,
            controls={"start": False, "pause": False, "stop": False, "reset": True},
        )
        return snapshot.to_dict()

    if flow_state == FlowState.SCENARIO_SELECTED.value:
        snapshot = FlowSnapshot(
            state=flow_state,
            tone="ready",
            status_label="Scenario Ready",
            status_detail=f"{scenario_name or 'Selected scenario'} is ready. Start when you are ready.",
            live_indicator_label="READY",
            selected_scenario_id=selected_scenario_id,
            selected_scenario_name=scenario_name,
            has_selected_scenario=has_selected_scenario,
            has_completed_run=False,
            controls={"start": True, "pause": False, "stop": False, "reset": True},
        )
        return snapshot.to_dict()

    if flow_state == FlowState.LOGGED_OUT.value:
        snapshot = FlowSnapshot(
            state=flow_state,
            tone="idle",
            status_label="Logged Out",
            status_detail="Session ended. Simulation state cleared.",
            live_indicator_label="IDLE",
            selected_scenario_id=None,
            selected_scenario_name=None,
            has_selected_scenario=False,
            has_completed_run=False,
            controls={"start": False, "pause": False, "stop": False, "reset": False},
        )
        return snapshot.to_dict()

    snapshot = FlowSnapshot(
        state=FlowState.IDLE.value,
        tone="idle",
        status_label="Ready",
        status_detail="Select a scenario to enable the simulation flow.",
        live_indicator_label="IDLE",
        selected_scenario_id=None,
        selected_scenario_name=None,
        has_selected_scenario=False,
        has_completed_run=False,
        controls={"start": False, "pause": False, "stop": False, "reset": False},
    )
    return snapshot.to_dict()
