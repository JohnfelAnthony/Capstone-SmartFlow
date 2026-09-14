"""Export the scoped SUMO network geometry for the Three.js dashboard view."""

from __future__ import annotations

import json
import math
import os
import sys
import xml.etree.ElementTree as ET
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
LEGACY_OUTPUT_PATH = ROOT / "data" / "generated" / "visual_network.json"
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from simulation.sumo_config import DEFAULT_INTERSECTION_ID, get_intersection_assets


def _resolve_requested_intersection_id() -> str:
    if len(sys.argv) > 1 and sys.argv[1]:
        return str(sys.argv[1]).strip().lower()
    return str(os.environ.get("SMARTFLOW_INTERSECTION_ID", DEFAULT_INTERSECTION_ID)).strip().lower()


INTERSECTION_ID = _resolve_requested_intersection_id()
INTERSECTION_ASSETS = get_intersection_assets(INTERSECTION_ID)
OUTPUT_PATH = INTERSECTION_ASSETS.visual_network_path
SCOPE_PATH = INTERSECTION_ASSETS.sumo_scope_path


def _parse_shape(value: str | None) -> list[dict[str, float]]:
    if not value:
        return []
    points: list[dict[str, float]] = []
    for token in value.split():
        x_text, y_text = token.split(",", 1)
        points.append({"x": float(x_text), "y": float(y_text)})
    return points


def _scope_visual_bounds(scope: dict[str, object]) -> dict[str, float]:
    center = scope.get("visual_center") or {"x": 0.0, "y": 0.0}
    radius = float(scope.get("visual_radius_m") or 260.0)
    center_x = float(center["x"])
    center_y = float(center["y"])
    return {
        "min_x": center_x - radius,
        "min_y": center_y - radius,
        "max_x": center_x + radius,
        "max_y": center_y + radius,
    }


def _clip_segment_to_bounds(
    start: dict[str, float],
    end: dict[str, float],
    bounds: dict[str, float],
) -> tuple[dict[str, float], dict[str, float], float, float] | None:
    x0, y0 = start["x"], start["y"]
    x1, y1 = end["x"], end["y"]
    dx = x1 - x0
    dy = y1 - y0
    u_min = 0.0
    u_max = 1.0

    checks = (
        (-dx, x0 - bounds["min_x"]),
        (dx, bounds["max_x"] - x0),
        (-dy, y0 - bounds["min_y"]),
        (dy, bounds["max_y"] - y0),
    )
    for p_value, q_value in checks:
        if p_value == 0:
            if q_value < 0:
                return None
            continue
        ratio = q_value / p_value
        if p_value < 0:
            u_min = max(u_min, ratio)
        else:
            u_max = min(u_max, ratio)
        if u_min > u_max:
            return None

    return (
        {"x": round(x0 + u_min * dx, 2), "y": round(y0 + u_min * dy, 2)},
        {"x": round(x0 + u_max * dx, 2), "y": round(y0 + u_max * dy, 2)},
        u_min,
        u_max,
    )


def _same_point(left: dict[str, float], right: dict[str, float]) -> bool:
    return abs(left["x"] - right["x"]) < 0.01 and abs(left["y"] - right["y"]) < 0.01


def _clip_shape_to_bounds(
    points: list[dict[str, float]],
    bounds: dict[str, float],
) -> list[dict[str, float]]:
    clipped, _clip_start, _clip_end, _source_length = _clip_shape_to_bounds_with_offsets(points, bounds)
    return clipped


def _clip_shape_to_bounds_with_offsets(
    points: list[dict[str, float]],
    bounds: dict[str, float],
) -> tuple[list[dict[str, float]], float, float, float]:
    clipped: list[dict[str, float]] = []
    source_offset = 0.0
    clip_start_position: float | None = None
    clip_end_position = 0.0
    for index in range(len(points) - 1):
        start_point = points[index]
        end_point = points[index + 1]
        segment_length = math.hypot(end_point["x"] - start_point["x"], end_point["y"] - start_point["y"])
        segment = _clip_segment_to_bounds(points[index], points[index + 1], bounds)
        if segment is None or segment_length <= 0.001:
            source_offset += segment_length
            continue
        start, end, u_min, u_max = segment
        segment_start_position = source_offset + (u_min * segment_length)
        segment_end_position = source_offset + (u_max * segment_length)
        if clip_start_position is None:
            clip_start_position = segment_start_position
        clip_end_position = segment_end_position
        if not clipped or not _same_point(clipped[-1], start):
            clipped.append(start)
        if not _same_point(clipped[-1], end):
            clipped.append(end)
        source_offset += segment_length
    return clipped, clip_start_position or 0.0, clip_end_position, source_offset


def _lane_payload(lane: ET.Element, bounds: dict[str, float]) -> dict[str, object]:
    width = float(lane.get("width") or 3.2)
    shape, clip_start_position, clip_end_position, measured_source_length = _clip_shape_to_bounds_with_offsets(
        _parse_shape(lane.get("shape")),
        bounds,
    )
    source_length = float(lane.get("length") or measured_source_length or 0.0)
    return {
        "id": lane.get("id", ""),
        "index": int(lane.get("index") or 0),
        "width": width,
        "allow": lane.get("allow", ""),
        "disallow": lane.get("disallow", ""),
        "source_length": round(source_length, 2),
        "clip_start_position": round(clip_start_position, 2),
        "clip_end_position": round(clip_end_position, 2),
        "shape": shape,
    }


def _compose_lane_id(edge_id: str, lane_index: int | str) -> str:
    return f"{edge_id}_{int(lane_index)}"


def _edge_payload(edge: ET.Element, bounds: dict[str, float]) -> dict[str, object]:
    lanes = [
        lane_payload
        for lane in edge.findall("lane")
        for lane_payload in [_lane_payload(lane, bounds)]
        if lane_payload["shape"]
    ]
    lane_shapes = [lane["shape"] for lane in lanes if lane["shape"]]
    return {
        "edge_id": edge.get("id", ""),
        "function": edge.get("function", "normal"),
        "from": edge.get("from", ""),
        "to": edge.get("to", ""),
        "shape": _clip_shape_to_bounds(_parse_shape(edge.get("shape")), bounds) or (lane_shapes[0] if lane_shapes else []),
        "lanes": lanes,
    }


def _lane_payload_for_index(edge: ET.Element | None, lane_index: int, bounds: dict[str, float]) -> dict[str, object] | None:
    if edge is None:
        return None
    for lane in edge.findall("lane"):
        if int(lane.get("index") or 0) == lane_index:
            lane_payload = _lane_payload(lane, bounds)
            return lane_payload if lane_payload["shape"] else None
    return None


def _edge_references_scope(edge: ET.Element, route_edges: set[str], tls_ids: set[str]) -> bool:
    edge_id = edge.get("id", "")
    if any(edge_id.startswith(f":{tls_id}_") for tls_id in tls_ids):
        return True
    crossing_edges = set((edge.get("crossingEdges") or "").split())
    return bool(crossing_edges & route_edges)


def _signal_control_geometry(shape: list[dict[str, float]], width: float) -> tuple[list[dict[str, float]], dict[str, float], float]:
    if len(shape) < 2:
        return [], {"x": 0.0, "y": 0.0}, 0.0

    end = shape[-1]
    previous = shape[-2]
    dx = end["x"] - previous["x"]
    dy = end["y"] - previous["y"]
    length = math.hypot(dx, dy)
    if length <= 0.001:
        return [], {"x": round(end["x"], 2), "y": round(end["y"], 2)}, 0.0

    unit_x = dx / length
    unit_y = dy / length
    normal_x = -unit_y
    normal_y = unit_x
    back_offset = min(max(width * 0.2, 0.35), 0.8)
    anchor_x = end["x"] - unit_x * back_offset
    anchor_y = end["y"] - unit_y * back_offset
    half_width = max(width * 0.5, 0.7)

    stop_line = [
        {"x": round(anchor_x - normal_x * half_width, 2), "y": round(anchor_y - normal_y * half_width, 2)},
        {"x": round(anchor_x + normal_x * half_width, 2), "y": round(anchor_y + normal_y * half_width, 2)},
    ]
    anchor = {"x": round(anchor_x, 2), "y": round(anchor_y, 2)}
    heading = round(math.degrees(math.atan2(dy, dx)), 2)
    return stop_line, anchor, heading


def _build_signal_groups(
    root: ET.Element,
    edge_lookup: dict[str, ET.Element],
    bounds: dict[str, float],
    tls_ids: set[str],
) -> list[dict[str, object]]:
    grouped_controls: dict[tuple[str, str], dict[str, object]] = {}

    for connection in root.findall("connection"):
        tls_id = connection.get("tl", "")
        if tls_id not in tls_ids:
            continue

        from_edge_id = connection.get("from", "")
        from_lane_index = int(connection.get("fromLane") or 0)
        source_edge = edge_lookup.get(from_edge_id)
        lane_payload = _lane_payload_for_index(source_edge, from_lane_index, bounds)
        if lane_payload is None:
            continue

        lane_id = lane_payload["id"] or _compose_lane_id(from_edge_id, from_lane_index)
        lane_allow = str(lane_payload.get("allow", ""))
        lane_disallow = str(lane_payload.get("disallow", ""))
        edge_function = source_edge.get("function", "") if source_edge is not None else ""
        kind = "pedestrian" if "pedestrian" in lane_allow and "pedestrian" not in lane_disallow else "vehicle"
        if edge_function in {"walkingarea", "crossing"}:
            kind = "pedestrian"

        key = (tls_id, lane_id)
        group = grouped_controls.get(key)
        if group is None:
            stop_line, anchor, heading = _signal_control_geometry(lane_payload["shape"], float(lane_payload["width"]))
            group = {
                "id": f"{tls_id}:{lane_id}",
                "signal_id": tls_id,
                "lane_id": lane_id,
                "from_edge_id": from_edge_id,
                "kind": kind,
                "width": lane_payload["width"],
                "heading": heading,
                "anchor": anchor,
                "stop_line": stop_line,
                "link_indices": [],
                "via_lane_ids": [],
            }
            grouped_controls[key] = group

        link_index = connection.get("linkIndex")
        if link_index is not None:
            group["link_indices"].append(int(link_index))

        via_lane_id = connection.get("via", "")
        if via_lane_id:
            group["via_lane_ids"].append(via_lane_id)

    signal_groups = list(grouped_controls.values())
    for group in signal_groups:
        group["link_indices"] = sorted(set(group["link_indices"]))
        group["via_lane_ids"] = sorted(set(group["via_lane_ids"]))

    return sorted(signal_groups, key=lambda item: (item["kind"], item["lane_id"]))


def _format_color(color_str: str) -> str:
    if not color_str:
        return "#808080"
    if "," in color_str:
        parts = color_str.split(",")
        if len(parts) >= 3:
            return f"rgb({parts[0]}, {parts[1]}, {parts[2]})"
    return color_str


def _parse_polygons(sumo_dir: Path, net_file_name: str) -> list[dict[str, object]]:
    base = Path(net_file_name).stem
    if base.endswith(".net"):
        base = base[:-4]
    
    poly_files = [
        sumo_dir / f"{base}.poly.xml",
        sumo_dir / f"{base}.add.xml",
        sumo_dir / f"{base}.add"
    ]
    
    polygons = []
    for p in poly_files:
        if p.exists():
            try:
                root = ET.parse(p).getroot()
                seen_polygon_ids: set[str] = set()
                for poly in root.findall(".//poly"):
                    polygon_id = poly.get("id", "")
                    if polygon_id and polygon_id in seen_polygon_ids:
                        continue
                    if polygon_id:
                        seen_polygon_ids.add(polygon_id)
                    polygons.append({
                        "id": polygon_id,
                        "color": _format_color(poly.get("color", "")),
                        "fill": poly.get("fill", "0") in ("1", "true", "True"),
                        "layer": float(poly.get("layer") or 0.0),
                        "shape": _parse_shape(poly.get("shape")),
                    })
            except Exception as e:
                print(f"Failed to parse {p}: {e}")
    return polygons


def build_visual_network() -> dict[str, object]:
    if not SCOPE_PATH.exists():
        raise FileNotFoundError(
            f"Missing scope definition for {INTERSECTION_ID}: {SCOPE_PATH}"
        )
    scope = json.loads(SCOPE_PATH.read_text(encoding="utf-8"))
    net_path = INTERSECTION_ASSETS.sumo_dir / scope["net_file"]
    route_edges = set(scope["route_edges"])
    tls_ids = set(scope["controlled_tls_ids"])
    root = ET.parse(net_path).getroot()
    bounds = _scope_visual_bounds(scope)
    edge_lookup = {
        edge.get("id", ""): edge
        for edge in root.findall("edge")
    }

    roads: list[dict[str, object]] = []
    crossings: list[dict[str, object]] = []
    walking_areas: list[dict[str, object]] = []
    internal_lanes: list[dict[str, object]] = []
    for edge in edge_lookup.values():
        edge_id = edge.get("id", "")
        edge_function = edge.get("function", "normal")
        if edge_id in route_edges:
            payload = _edge_payload(edge, bounds)
            if payload["lanes"]:
                roads.append(payload)
        elif edge_function == "crossing" and _edge_references_scope(edge, route_edges, tls_ids):
            payload = _edge_payload(edge, bounds)
            if payload["lanes"]:
                crossings.append(payload)
        elif edge_function == "walkingarea" and _edge_references_scope(edge, route_edges, tls_ids):
            payload = _edge_payload(edge, bounds)
            if payload["lanes"]:
                walking_areas.append(payload)
        elif any(edge_id.startswith(f":{tls_id}_") for tls_id in tls_ids):
            payload = _edge_payload(edge, bounds)
            if payload["lanes"]:
                internal_lanes.append(payload)

    junctions = {
        junction.get("id"): junction
        for junction in root.findall("junction")
        if junction.get("id") in tls_ids
    }
    signals = []
    for tls_id in scope["controlled_tls_ids"]:
        junction = junctions.get(tls_id)
        if junction is None:
            continue
        signals.append(
            {
                "id": tls_id,
                "x": float(junction.get("x") or 0.0),
                "y": float(junction.get("y") or 0.0),
                "shape": _parse_shape(junction.get("shape")),
            }
        )

    signal_groups = _build_signal_groups(root, edge_lookup, bounds, tls_ids)
    polygons = _parse_polygons(INTERSECTION_ASSETS.sumo_dir, scope["net_file"])

    return {
        "version": 1,
        "scope": {
            "mode": scope["mode"],
            "controlled_tls_ids": scope["controlled_tls_ids"],
        },
        "source_net": scope["net_file"],
        "bounds": bounds,
        "roads": roads,
        "internal_lanes": internal_lanes,
        "crossings": crossings,
        "walking_areas": walking_areas,
        "signals": signals,
        "signal_groups": signal_groups,
        "polygons": polygons,
    }


def main() -> None:
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    network = build_visual_network()
    OUTPUT_PATH.write_text(json.dumps(network, indent=2), encoding="utf-8")
    print(f"Wrote {OUTPUT_PATH.relative_to(ROOT)} for {INTERSECTION_ID}")
    if INTERSECTION_ID == DEFAULT_INTERSECTION_ID:
        LEGACY_OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
        LEGACY_OUTPUT_PATH.write_text(json.dumps(network, indent=2), encoding="utf-8")
        print(f"Updated legacy {LEGACY_OUTPUT_PATH.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
