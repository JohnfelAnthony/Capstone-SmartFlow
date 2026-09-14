"""Authenticated visual-network loader for renderer-safe client payloads."""

from __future__ import annotations

import json
import math
from pathlib import Path

import config
from simulation.sumo_config import DEFAULT_INTERSECTION_ID, get_intersection_assets


MAX_ROADS = 48
MAX_LANES_PER_ROAD = 8
MAX_INTERNAL_LANES = 32
MAX_WALKING_AREAS = 24
MAX_CROSSINGS = 24
MAX_SIGNALS = 12
MAX_SIGNAL_GROUPS = 48
MAX_SHAPE_POINTS = 96
MAX_TEXT_LENGTH = 48
MAX_ABS_COORDINATE = 10000.0


def _clamp_number(value, fallback: float = 0.0, minimum: float = -MAX_ABS_COORDINATE,
                  maximum: float = MAX_ABS_COORDINATE) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return fallback
    if not math.isfinite(number):
        return fallback
    return min(max(number, minimum), maximum)


def _clamp_int(value, fallback: int = 0, minimum: int = 0, maximum: int = 999) -> int:
    try:
        number = int(value)
    except (TypeError, ValueError):
        return fallback
    return min(max(number, minimum), maximum)


def _sanitize_text(value, fallback: str = "", max_length: int = MAX_TEXT_LENGTH) -> str:
    if value is None:
        return fallback
    text = str(value).strip()
    if not text:
        return fallback
    return text[:max_length]


def _sanitize_point(value) -> dict[str, float] | None:
    if not isinstance(value, dict):
        return None
    x = _clamp_number(value.get("x"), fallback=float("nan"))
    y = _clamp_number(value.get("y"), fallback=float("nan"))
    if not math.isfinite(x) or not math.isfinite(y):
        return None
    return {"x": round(x, 2), "y": round(y, 2)}


def _sanitize_shape(value, *, min_points: int = 2, max_points: int = MAX_SHAPE_POINTS) -> list[dict[str, float]]:
    if not isinstance(value, list):
        return []
    points: list[dict[str, float]] = []
    for item in value[:max_points]:
        point = _sanitize_point(item)
        if point is None:
            continue
        if not points or points[-1] != point:
            points.append(point)
    if len(points) < min_points:
        return []
    return points


def _sanitize_bounds(raw_bounds: dict | None) -> dict[str, float]:
    bounds = raw_bounds if isinstance(raw_bounds, dict) else {}
    min_x = _clamp_number(bounds.get("min_x"), -50.0)
    min_y = _clamp_number(bounds.get("min_y"), -50.0)
    max_x = _clamp_number(bounds.get("max_x"), 50.0)
    max_y = _clamp_number(bounds.get("max_y"), 50.0)
    if min_x >= max_x:
        min_x, max_x = -50.0, 50.0
    if min_y >= max_y:
        min_y, max_y = -50.0, 50.0
    return {
        "min_x": round(min_x, 2),
        "min_y": round(min_y, 2),
        "max_x": round(max_x, 2),
        "max_y": round(max_y, 2),
    }


def _average_shape_center(shape: list[dict[str, float]]) -> tuple[float, float]:
    if not shape:
        return 0.0, 0.0
    return (
        sum(point["x"] for point in shape) / len(shape),
        sum(point["y"] for point in shape) / len(shape),
    )


def _sanitize_lane(raw_lane: dict) -> dict[str, object] | None:
    shape = _sanitize_shape(raw_lane.get("shape"), min_points=2)
    if not shape:
        return None
    return {
        "id": _sanitize_text(raw_lane.get("id"), fallback=f"lane-{_clamp_int(raw_lane.get('index'))}"),
        "index": _clamp_int(raw_lane.get("index"), maximum=32),
        "width": round(_clamp_number(raw_lane.get("width"), 3.2, minimum=0.5, maximum=16.0), 2),
        "allow": _sanitize_text(raw_lane.get("allow")),
        "disallow": _sanitize_text(raw_lane.get("disallow")),
        "source_length": round(_clamp_number(raw_lane.get("source_length"), 0.0, minimum=0.0, maximum=MAX_ABS_COORDINATE), 2),
        "clip_start_position": round(_clamp_number(raw_lane.get("clip_start_position"), 0.0, minimum=0.0, maximum=MAX_ABS_COORDINATE), 2),
        "clip_end_position": round(_clamp_number(raw_lane.get("clip_end_position"), 0.0, minimum=0.0, maximum=MAX_ABS_COORDINATE), 2),
        "shape": shape,
    }


def _sanitize_road(raw_road: dict, controlled_tls_ids: set[str], index: int) -> dict[str, object] | None:
    if not isinstance(raw_road, dict):
        return None
    lanes = [
        lane
        for lane in (
            _sanitize_lane(raw_lane)
            for raw_lane in (raw_road.get("lanes") or [])[:MAX_LANES_PER_ROAD]
        )
        if lane
    ]
    if not lanes:
        return None
    shape = _sanitize_shape(raw_road.get("shape"), min_points=2) or lanes[0]["shape"]
    return {
        "index": index,
        "function": _sanitize_text(raw_road.get("function"), fallback="normal"),
        "toward_intersection": _sanitize_text(raw_road.get("to")) in controlled_tls_ids,
        "away_from_intersection": _sanitize_text(raw_road.get("from")) in controlled_tls_ids,
        "shape": shape,
        "lanes": lanes,
    }


def _sanitize_edge_collection(raw_edges: list, *, limit: int,
                              controlled_tls_ids: set[str]) -> list[dict[str, object]]:
    collection: list[dict[str, object]] = []
    if not isinstance(raw_edges, list):
        return collection
    for index, raw_edge in enumerate(raw_edges[:limit]):
        sanitized = _sanitize_road(raw_edge, controlled_tls_ids, index)
        if sanitized:
            collection.append(sanitized)
    return collection


def _sanitize_signals(raw_signals: list) -> list[dict[str, object]]:
    signals: list[dict[str, object]] = []
    if not isinstance(raw_signals, list):
        return signals
    for index, raw_signal in enumerate(raw_signals[:MAX_SIGNALS]):
        if not isinstance(raw_signal, dict):
            continue
        shape = _sanitize_shape(raw_signal.get("shape"), min_points=3)
        center_x, center_y = _average_shape_center(shape)
        signals.append({
            "id": f"signal-{index}",
            "kind": "major" if index == 0 else "minor",
            "x": round(_clamp_number(raw_signal.get("x"), center_x), 2),
            "y": round(_clamp_number(raw_signal.get("y"), center_y), 2),
            "shape": shape,
        })
    return signals


def _sanitize_signal_group(raw_group: dict) -> dict[str, object] | None:
    if not isinstance(raw_group, dict):
        return None

    stop_line = _sanitize_shape(raw_group.get("stop_line"), min_points=2, max_points=2)
    anchor = _sanitize_point(raw_group.get("anchor"))
    link_indices = []
    for raw_index in (raw_group.get("link_indices") or [])[:8]:
        link_indices.append(_clamp_int(raw_index, maximum=64))

    if not stop_line or anchor is None or not link_indices:
        return None

    kind = _sanitize_text(raw_group.get("kind"), fallback="vehicle")
    if kind not in {"vehicle", "pedestrian"}:
        kind = "vehicle"

    return {
        "id": _sanitize_text(raw_group.get("id"), fallback="signal-group"),
        "signal_id": _sanitize_text(raw_group.get("signal_id"), fallback="signal-0"),
        "lane_id": _sanitize_text(raw_group.get("lane_id"), fallback="lane-0"),
        "from_edge_id": _sanitize_text(raw_group.get("from_edge_id")),
        "kind": kind,
        "width": round(_clamp_number(raw_group.get("width"), 3.2, minimum=0.5, maximum=16.0), 2),
        "heading": round(_clamp_number(raw_group.get("heading"), 0.0, minimum=-360.0, maximum=360.0), 2),
        "anchor": anchor,
        "stop_line": stop_line,
        "link_indices": link_indices,
        "via_lane_ids": [
            _sanitize_text(value)
            for value in (raw_group.get("via_lane_ids") or [])[:8]
            if _sanitize_text(value)
        ],
    }


def _sanitize_polygons(raw_polygons: list) -> list[dict[str, object]]:
    polygons: list[dict[str, object]] = []
    if not isinstance(raw_polygons, list):
        return polygons
    for index, raw_poly in enumerate(raw_polygons[:64]):
        if not isinstance(raw_poly, dict):
            continue
        shape = _sanitize_shape(raw_poly.get("shape"), min_points=3, max_points=128)
        if not shape:
            continue
        polygons.append({
            "id": _sanitize_text(raw_poly.get("id"), fallback=f"poly-{index}"),
            "color": _sanitize_text(raw_poly.get("color"), fallback="#808080"),
            "fill": bool(raw_poly.get("fill")),
            "layer": round(_clamp_number(raw_poly.get("layer"), 0.0, minimum=-100.0, maximum=100.0), 2),
            "shape": shape,
        })
    return polygons


def _sanitize_signal_groups(raw_signal_groups: list) -> list[dict[str, object]]:
    groups: list[dict[str, object]] = []
    if not isinstance(raw_signal_groups, list):
        return groups
    for raw_group in raw_signal_groups[:MAX_SIGNAL_GROUPS]:
        sanitized = _sanitize_signal_group(raw_group)
        if sanitized:
            groups.append(sanitized)
    return groups


def _resolve_requested_intersection_id(explicit_intersection_id: str | None = None) -> str:
    if explicit_intersection_id:
        return str(explicit_intersection_id).strip().lower() or DEFAULT_INTERSECTION_ID
    try:
        from services import simulation_service

        return simulation_service.current_intersection_id()
    except Exception:
        return DEFAULT_INTERSECTION_ID


def _resolve_network_path(intersection_id: str | None = None) -> Path:
    requested_intersection_id = _resolve_requested_intersection_id(intersection_id)
    requested_assets = get_intersection_assets(requested_intersection_id)
    candidate_paths = [requested_assets.visual_network_path]

    default_assets = get_intersection_assets(DEFAULT_INTERSECTION_ID)
    if requested_assets.intersection_id == DEFAULT_INTERSECTION_ID:
        candidate_paths.append(Path(config.VISUAL_NETWORK_PATH))
    else:
        candidate_paths.extend(
            [
                default_assets.visual_network_path,
                Path(config.VISUAL_NETWORK_PATH),
            ]
        )

    for candidate_path in candidate_paths:
        if candidate_path.exists():
            return candidate_path

    return requested_assets.visual_network_path


def load_client_visual_network(intersection_id: str | None = None) -> dict[str, object]:
    network_path = _resolve_network_path(intersection_id)
    if not network_path.exists():
        raise FileNotFoundError(f"Visual network file not found: {network_path}")
    if network_path.stat().st_size > config.VISUAL_NETWORK_MAX_BYTES:
        raise ValueError("Visual network payload exceeds the configured byte limit.")

    raw_network = json.loads(network_path.read_text(encoding="utf-8"))
    scope = raw_network.get("scope") if isinstance(raw_network, dict) else {}
    controlled_tls_ids = {
        _sanitize_text(value)
        for value in (scope.get("controlled_tls_ids") or [])
        if _sanitize_text(value)
    }

    return {
        "version": 1,
        "source_net": _sanitize_text(raw_network.get("source_net") if isinstance(raw_network, dict) else ""),
        "scope": {
            "mode": _sanitize_text(scope.get("mode") if isinstance(scope, dict) else ""),
        },
        "bounds": _sanitize_bounds(raw_network.get("bounds") if isinstance(raw_network, dict) else None),
        "roads": _sanitize_edge_collection(
            raw_network.get("roads") if isinstance(raw_network, dict) else [],
            limit=MAX_ROADS,
            controlled_tls_ids=controlled_tls_ids,
        ),
        "internal_lanes": _sanitize_edge_collection(
            raw_network.get("internal_lanes") if isinstance(raw_network, dict) else [],
            limit=MAX_INTERNAL_LANES,
            controlled_tls_ids=controlled_tls_ids,
        ),
        "crossings": _sanitize_edge_collection(
            raw_network.get("crossings") if isinstance(raw_network, dict) else [],
            limit=MAX_CROSSINGS,
            controlled_tls_ids=controlled_tls_ids,
        ),
        "walking_areas": _sanitize_edge_collection(
            raw_network.get("walking_areas") if isinstance(raw_network, dict) else [],
            limit=MAX_WALKING_AREAS,
            controlled_tls_ids=controlled_tls_ids,
        ),
        "signals": _sanitize_signals(raw_network.get("signals") if isinstance(raw_network, dict) else []),
        "signal_groups": _sanitize_signal_groups(raw_network.get("signal_groups") if isinstance(raw_network, dict) else []),
        "polygons": _sanitize_polygons(raw_network.get("polygons") if isinstance(raw_network, dict) else []),
    }
