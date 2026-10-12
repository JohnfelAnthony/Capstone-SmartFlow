"""Render-frame serialization for the live 2D/3D visualizers."""

from __future__ import annotations

import copy
import json
import math
import time
from collections import defaultdict

from simulation.road_network import NETWORK_ID as DEFAULT_INTERSECTION_ID
from simulation.signal_state import canonical_signal_states


MAX_RENDER_VEHICLES = 300
MAX_RENDER_PEDESTRIANS = 128
# Retained import names: presentation limits are identical for live and replay.
LIVE_MAX_RENDER_VEHICLES = MAX_RENDER_VEHICLES
LIVE_MAX_RENDER_PEDESTRIANS = MAX_RENDER_PEDESTRIANS
MAX_RENDER_STATE_BYTES = 262144


class RenderFrameBudgetError(ValueError):
    """Research metadata alone cannot fit in the renderer transport budget."""


def encode_render_frame(frame: dict) -> str:
    """The exact JSON encoding measured here and sent by the WebSocket."""
    return json.dumps(frame, ensure_ascii=False, separators=(",", ":"), allow_nan=False)


def _distributed_entities(entities: list, limit: int) -> list[dict]:
    """Stable round-robin slots across lanes (or pedestrian junction IDs)."""
    groups = defaultdict(list)
    for entity in entities:
        if isinstance(entity, dict):
            groups[str(entity.get("lane_id") or "")].append(entity)
    for group in groups.values():
        group.sort(key=lambda entity: str(entity.get("id") or ""))
    ordered_groups = [groups[key] for key in sorted(groups)]
    selected = []
    offset = 0
    while len(selected) < limit:
        added = False
        for group in ordered_groups:
            if offset < len(group):
                selected.append(group[offset])
                added = True
                if len(selected) == limit:
                    return selected
        if not added:
            break
        offset += 1
    return selected


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
    vehicle = {
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
    if "wait_time" in raw_vehicle:
        vehicle["wait_time"] = _safe_float(raw_vehicle["wait_time"])
    return vehicle


def _serialize_pedestrian_entity(raw_pedestrian: dict) -> dict:
    pedestrian = {
        "id": _safe_text(raw_pedestrian.get("id"), "pedestrian"),
        "x": _safe_float(raw_pedestrian.get("x")),
        "y": _safe_float(raw_pedestrian.get("y")),
        "speed": _safe_float(raw_pedestrian.get("speed")),
        "lane_id": _safe_text(raw_pedestrian.get("lane_id")),
        "stopped": bool(raw_pedestrian.get("stopped")),
    }
    if "wait_time" in raw_pedestrian:
        pedestrian["wait_time"] = _safe_float(raw_pedestrian["wait_time"])
    return pedestrian


def _serialize_visual_payload(raw_visual: dict | None) -> dict:
    raw_visual = raw_visual if isinstance(raw_visual, dict) else {}
    constraint_marker = raw_visual.get("constraint_marker", {})
    visual = {
        "closed_lanes": [str(lane) for lane in raw_visual.get("closed_lanes", [])],
        "slow_lanes": {str(lane): _safe_float(factor, 1) for lane, factor in raw_visual.get("slow_lanes", {}).items()},
        "constraint_marker": {
            "active": bool(constraint_marker.get("active")),
            "x": _safe_float(constraint_marker.get("x")),
            "y": _safe_float(constraint_marker.get("y")),
        }
    }
    if isinstance(raw_visual.get("pedestrian_paths"), list):
        visual["pedestrian_paths"] = copy.deepcopy(raw_visual["pedestrian_paths"])
    return visual


def _serialize_junction_controls(raw_controls: dict | None) -> dict:
    if not isinstance(raw_controls, dict):
        return {}
    # Optional snapshot metadata stays absent in older recordings. Copy instead
    # of inferring elapsed time, pending requests or controller behavior.
    return {str(junction): copy.deepcopy(control)
            for junction, control in raw_controls.items() if isinstance(control, dict)}


def _set_coverage(frame: dict, reason: str | None = None) -> None:
    vehicle_total = frame["vehicle_count"]
    pedestrian_total = frame["pedestrian_count"]
    limited = len(frame["vehicles"]) < vehicle_total or len(frame["pedestrians"]) < pedestrian_total
    frame["render_coverage"] = {
        "vehicles": {"total": vehicle_total, "shown": len(frame["vehicles"])},
        "pedestrians": {"total": pedestrian_total, "shown": len(frame["pedestrians"])},
        "limited": limited,
        "reason": reason if limited else None,
    }


def _enforce_byte_budget(frame: dict) -> dict:
    if len(encode_render_frame(frame).encode("utf-8")) <= MAX_RENDER_STATE_BYTES:
        return frame
    vehicles, pedestrians = frame["vehicles"], frame["pedestrians"]
    frame["vehicles"], frame["pedestrians"] = [], []
    _set_coverage(frame, "byte_limit")
    if len(encode_render_frame(frame).encode("utf-8")) > MAX_RENDER_STATE_BYTES:
        raise RenderFrameBudgetError(
            f"Render metadata exceeds {MAX_RENDER_STATE_BYTES} bytes; authoritative telemetry was preserved."
        )

    # Both ordered lists already allocate slots across lanes/junctions. Reduce
    # their prefixes proportionally, never deleting metrics, events or timing.
    total = len(vehicles) + len(pedestrians)
    low, high = 0, total
    while low < high:
        candidate = (low + high + 1) // 2
        vehicle_count = candidate * len(vehicles) // total
        pedestrian_count = candidate - vehicle_count
        frame["vehicles"] = vehicles[:vehicle_count]
        frame["pedestrians"] = pedestrians[:pedestrian_count]
        _set_coverage(frame, "byte_limit")
        if len(encode_render_frame(frame).encode("utf-8")) <= MAX_RENDER_STATE_BYTES:
            low = candidate
        else:
            high = candidate - 1
    vehicle_count = low * len(vehicles) // total if total else 0
    frame["vehicles"] = vehicles[:vehicle_count]
    frame["pedestrians"] = pedestrians[:low-vehicle_count]
    _set_coverage(frame, "byte_limit")
    return frame


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
    """Build the compact renderer payload shared by native state fallbacks and WebSocket streaming."""

    status = state.get("status", "stopped")
    phase = "ALL_RED" if status == "stopped" else state.get("phase", "ALL_RED")
    ns_state, ew_state = canonical_signal_states(phase)
    playback = state.get("playback", {}) if isinstance(state.get("playback"), dict) else {}
    flow = state.get("flow", {}) if isinstance(state.get("flow"), dict) else {}
    live_mode_active = _is_live_flow_state(flow)
    max_vehicle_count = MAX_RENDER_VEHICLES
    max_pedestrian_count = MAX_RENDER_PEDESTRIANS

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
            for vehicle in _distributed_entities(state.get("vehicles", []), max_vehicle_count)
        ],
        "pedestrians": [
            _serialize_pedestrian_entity(pedestrian)
            for pedestrian in _distributed_entities(state.get("pedestrians", []), max_pedestrian_count)
        ],
        "visual": _serialize_visual_payload(state.get("visual", {})),
        "junction_controls": _serialize_junction_controls(state.get("junction_controls")),
        "traffic_lights": _serialize_traffic_lights(state.get("traffic_lights")),
    }
    metrics = state.get("metrics") if isinstance(state.get("metrics"), dict) else {}
    for source, target in (("lanes", "lane_metrics"), ("junctions", "junction_metrics")):
        if isinstance(metrics.get(source), dict):
            frame[target] = copy.deepcopy(metrics[source])
    experiment = state.get("experiment")
    if isinstance(experiment, dict) and any(key in experiment for key in ("last_policy_decision", "last_safety_override")):
        frame["controller_events"] = {key: copy.deepcopy(experiment.get(key))
                                      for key in ("last_policy_decision", "last_safety_override")}
    if sequence is not None:
        frame["sequence"] = int(sequence)
    _set_coverage(frame, "entity_limit")
    return _enforce_byte_budget(frame)
