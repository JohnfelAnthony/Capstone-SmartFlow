"""Render-frame serialization for the live 2D/3D visualizers."""

from __future__ import annotations

import math
import time

from simulation.road_network import NETWORK_ID as DEFAULT_INTERSECTION_ID
from simulation.signal_state import canonical_signal_states


MAX_RENDER_VEHICLES = 120
MAX_RENDER_PEDESTRIANS = 48
LIVE_MAX_RENDER_VEHICLES = 80
LIVE_MAX_RENDER_PEDESTRIANS = 32
MAX_RENDER_STATE_BYTES = 262144


def _safe_float(value, default: float = 0.0) -> float:
    try:
        numeric_value = float(value)
    except (TypeError, ValueError):
        return default
    return numeric_value if math.isfinite(numeric_value) else default


def _safe_text(value, default: str = "", max_length: int = 48) -> str:
    if value is None:
        return default
    text = str(value).strip()
    return text[:max_length] if text else default


def _is_live_flow_state(flow: dict | None) -> bool:
    return _safe_text((flow or {}).get("state"), "IDLE", max_length=24) == "LIVE_RUNNING"


def _serialize_vehicle_entity(raw_vehicle: dict) -> dict:
    return {
        "id": _safe_text(raw_vehicle.get("id"), "vehicle"),
        "x": _safe_float(raw_vehicle.get("x")),
        "y": _safe_float(raw_vehicle.get("y")),
        "angle": _safe_float(raw_vehicle.get("angle")),
        "speed": _safe_float(raw_vehicle.get("speed")),
        "lane_id": _safe_text(raw_vehicle.get("lane_id")),
        "lane_position": _safe_float(raw_vehicle.get("lane_position")),
        "length": _safe_float(raw_vehicle.get("length"), 4.5),
        "width": _safe_float(raw_vehicle.get("width"), 1.8),
        "stopped": bool(raw_vehicle.get("stopped")),
        "visual_type": _safe_text(raw_vehicle.get("visual_type"), "car"),
        "emergency": bool(raw_vehicle.get("emergency")),
    }


def _serialize_pedestrian_entity(raw_pedestrian: dict) -> dict:
    return {
        "id": _safe_text(raw_pedestrian.get("id"), "pedestrian"),
        "x": _safe_float(raw_pedestrian.get("x")),
        "y": _safe_float(raw_pedestrian.get("y")),
        "speed": _safe_float(raw_pedestrian.get("speed")),
        "lane_id": _safe_text(raw_pedestrian.get("lane_id")),
        "stopped": bool(raw_pedestrian.get("stopped")),
    }


def _serialize_visual_payload(raw_visual: dict | None) -> dict:
    raw_visual = raw_visual if isinstance(raw_visual, dict) else {}
    constraint_marker = raw_visual.get("constraint_marker", {})
    return {
        "closed_lanes": [str(lane) for lane in raw_visual.get("closed_lanes", [])],
        "slow_lanes": {str(lane): _safe_float(factor, 1) for lane, factor in raw_visual.get("slow_lanes", {}).items()},
        "constraint_marker": {
            "active": bool(constraint_marker.get("active")),
            "x": _safe_float(constraint_marker.get("x")),
            "y": _safe_float(constraint_marker.get("y")),
        }
    }


def _serialize_traffic_lights(raw_traffic_lights: dict | None) -> dict:
    if not isinstance(raw_traffic_lights, dict):
        return {}

    serialized: dict[str, dict[str, str]] = {}
    for raw_signal_id, raw_entry in raw_traffic_lights.items():
        signal_id = _safe_text(raw_signal_id, max_length=16)
        if not signal_id or not isinstance(raw_entry, dict):
            continue

        state = _safe_text(raw_entry.get("state"), max_length=64)
        phase = _safe_text(raw_entry.get("phase"), max_length=32)
        if not state:
            continue

        serialized[signal_id] = {
            "state": state,
            "phase": phase or "ALL_RED",
        }

    return serialized


def build_render_frame(
    state: dict,
    *,
    render_ts: float | None = None,
    sequence: int | None = None,
    current_intersection_id: str | None = None,
) -> dict:
    """Build the compact renderer payload shared by Dash fallback and SSE."""

    status = state.get("status", "stopped")
    phase = "ALL_RED" if status == "stopped" else state.get("phase", "ALL_RED")
    ns_state, ew_state = canonical_signal_states(phase)
    playback = state.get("playback", {}) if isinstance(state.get("playback"), dict) else {}
    flow = state.get("flow", {}) if isinstance(state.get("flow"), dict) else {}
    live_mode_active = _is_live_flow_state(flow)
    max_vehicle_count = LIVE_MAX_RENDER_VEHICLES if live_mode_active else MAX_RENDER_VEHICLES
    max_pedestrian_count = LIVE_MAX_RENDER_PEDESTRIANS if live_mode_active else MAX_RENDER_PEDESTRIANS

    frame = {
        "time": _safe_float(state.get("time", 0)),
        "render_ts": _safe_float(render_ts if render_ts is not None else time.time(), 0),
        "step_length": _safe_float(state.get("step_length", 0.1), 0.1),
        "status": _safe_text(status, "stopped"),
        "flow_state": _safe_text(flow.get("state"), "IDLE", max_length=24),
        "intersection_id": _safe_text(
            state.get("scenario", {}).get("intersection_id") or current_intersection_id,
            DEFAULT_INTERSECTION_ID,
            max_length=24,
        ),
        "phase": _safe_text(phase, "ALL_RED"),
        "ns_state": ns_state,
        "ew_state": ew_state,
        "playback": {
            "active": bool(playback),
            "frame_index": int(playback.get("frame_index", 0) or 0),
            "frame_count": int(playback.get("frame_count", 0) or 0),
        },
        "render_mode": "live" if live_mode_active else "playback" if bool(playback) else "idle",
        "vehicle_count": int(state.get("vehicle_count", len(state.get("vehicles", [])))),
        "pedestrian_count": int(state.get("pedestrian_count", len(state.get("pedestrians", [])))),
        "render_limits": {"vehicles": max_vehicle_count, "pedestrians": max_pedestrian_count},
        "vehicles": [
            _serialize_vehicle_entity(vehicle)
            for vehicle in state.get("vehicles", [])[:max_vehicle_count]
            if isinstance(vehicle, dict)
        ],
        "pedestrians": [
            _serialize_pedestrian_entity(pedestrian)
            for pedestrian in state.get("pedestrians", [])[:max_pedestrian_count]
            if isinstance(pedestrian, dict)
        ],
        "visual": _serialize_visual_payload(state.get("visual", {})),
        "traffic_lights": _serialize_traffic_lights(state.get("traffic_lights")),
    }
    if sequence is not None:
        frame["sequence"] = int(sequence)
    return frame
