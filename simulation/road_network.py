"""Metric road graph, polyline lanes, turn connectors and dynamic routing."""
from __future__ import annotations

import heapq
import copy
import hashlib
import json
import math
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

NETWORK_ID = "tagum_network"
NETWORK_PATH = Path(__file__).resolve().parents[1] / "data/networks/tagum_network.json"
Point = tuple[float, float]


def distance(a: Point, b: Point) -> float:
    return math.hypot(b[0] - a[0], b[1] - a[1])


def length(shape: list[Point]) -> float:
    return sum(distance(a, b) for a, b in zip(shape, shape[1:]))


def sample(shape: list[Point], position: float) -> tuple[float, float, float]:
    remaining = max(0.0, position)
    for index, (a, b) in enumerate(zip(shape, shape[1:])):
        segment_length = distance(a, b)
        if segment_length < 1e-8:
            continue
        if remaining <= segment_length or index == len(shape) - 2:
            fraction = min(1.0, remaining / segment_length)
            return a[0] + fraction * (b[0] - a[0]), a[1] + fraction * (b[1] - a[1]), math.atan2(b[1] - a[1], b[0] - a[0])
        remaining -= segment_length
    return *shape[-1], 0.0


def clip(shape: list[Point], start: float, end: float) -> list[Point]:
    points = [sample(shape, start)[:2]]
    accumulated = 0.0
    for a, b in zip(shape, shape[1:]):
        accumulated += distance(a, b)
        if start < accumulated < end:
            points.append(b)
    points.append(sample(shape, end)[:2])
    return points


def offset(shape: list[Point], meters: float) -> list[Point]:
    result = []
    for index, point in enumerate(shape):
        before, after = shape[max(0, index - 1)], shape[min(len(shape) - 1, index + 1)]
        heading = math.atan2(after[1] - before[1], after[0] - before[0])
        result.append((point[0] + math.sin(heading) * meters, point[1] - math.cos(heading) * meters))
    return result


def convex_hull(points: list[Point]) -> list[Point]:
    """Junction pavement spans lane mouths, not an oversized circular disc."""
    points = sorted(set(points))
    def cross(a, b, c):
        return (b[0]-a[0])*(c[1]-a[1])-(b[1]-a[1])*(c[0]-a[0])
    lower, upper = [], []
    for point in points:
        while len(lower) >= 2 and cross(lower[-2], lower[-1], point) <= 0:
            lower.pop()
        lower.append(point)
    for point in reversed(points):
        while len(upper) >= 2 and cross(upper[-2], upper[-1], point) <= 0:
            upper.pop()
        upper.append(point)
    return lower[:-1]+upper[:-1]


@dataclass(frozen=True)
class Lane:
    id: str
    source: str
    target: str
    shape: list[Point]
    length: float
    speed: float
    approach: str


class RoadNetwork:
    def __init__(self, payload: dict):
        payload = copy.deepcopy(payload)
        if not payload.get("id") or not payload.get("nodes") or not payload.get("roads"):
            raise ValueError("Network requires id, nodes and roads")
        for collection in (payload["nodes"], payload["roads"]):
            ids = [item.get("id") for item in collection]
            if any(not isinstance(value, str) or not value for value in ids) or len(ids) != len(set(ids)):
                raise ValueError("Network IDs must be unique nonempty strings")
        for node in payload["nodes"]:
            if not all(isinstance(node.get(key), (int, float)) and math.isfinite(node[key]) for key in ("x", "y")):
                raise ValueError("Node coordinates must be finite metres")
        self.payload = payload
        self.fingerprint = hashlib.sha256(json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
        self.id = payload["id"]
        self.nodes = {node["id"]: node for node in payload["nodes"]}
        self.intersections = [node_id for node_id, node in self.nodes.items() if not node.get("boundary")]
        self.lanes: dict[str, Lane] = {}
        self.outgoing: dict[str, list[str]] = {node: [] for node in self.nodes}
        self.incoming: dict[str, list[str]] = {node: [] for node in self.nodes}
        for road in payload["roads"]:
            if road.get("source") not in self.nodes or road.get("target") not in self.nodes or road["source"] == road["target"]:
                raise ValueError("Road endpoints must reference distinct nodes")
            shape = road.get("shape", [])
            if len(shape) < 2 or any(len(point) != 2 or any(not isinstance(value, (float, int)) or not math.isfinite(value) for value in point) for point in shape):
                raise ValueError("Road shape needs at least two finite metric points")
            for endpoint, node_id in ((shape[0], road["source"]), (shape[-1], road["target"])):
                if distance(endpoint, (self.nodes[node_id]["x"], self.nodes[node_id]["y"])) > 1:
                    raise ValueError("Road geometry must meet its endpoint nodes within one metre")
            speed = road.get("speed_mps", 8.33)
            if not isinstance(speed, (int, float)) or not math.isfinite(speed) or not .5 <= speed <= 40:
                raise ValueError("Road speed must be between 0.5 and 40 m/s")
            for reverse in ([False] if road.get("oneway") else [False, True]):
                shape = [tuple(point) for point in road["shape"]]
                source, target = road["source"], road["target"]
                if reverse:
                    shape.reverse()
                    source, target = target, source
                total = length(shape)
                start = 0 if self.nodes[source].get("boundary") else 9
                end = total if self.nodes[target].get("boundary") else total - 9
                if end - start < 8:
                    raise ValueError(f"Road {road['id']} too short for junction clearance")
                lane_shape = offset(clip(shape, start, end), 1.65 if not road.get("oneway") else 0)
                heading = sample(lane_shape, length(lane_shape))[2]
                approach = ("west", "south", "east", "north")[round(heading / (math.pi / 2)) % 4]
                lane_id = f"{road['id']}{'r' if reverse else 'f'}"
                lane = Lane(lane_id, source, target, lane_shape, length(lane_shape), road.get("speed_mps", 8.33), approach)
                self.lanes[lane_id] = lane
                self.outgoing[source].append(lane_id)
                self.incoming[target].append(lane_id)
        if not self.lanes or not self.intersections:
            raise ValueError("Network needs roads and intersections")
        self.boundaries = [node_id for node_id in self.nodes if self.nodes[node_id].get("boundary")]
        if len(self.boundaries) < 2:
            raise ValueError("Network needs at least two boundary nodes")
        reached, frontier = set(), [next(iter(self.nodes))]
        while frontier:
            node = frontier.pop()
            if node in reached:
                continue
            reached.add(node)
            frontier.extend(self.lanes[lane].target for lane in self.outgoing[node])
            frontier.extend(self.lanes[lane].source for lane in self.incoming[node])
        if len(reached) != len(self.nodes):
            raise ValueError("Study network must be connected with no isolated nodes")
        self.prohibited_turns = set()
        for turn in payload.get("prohibited_turns", []):
            if len(turn) != 2 or any(lane not in self.lanes for lane in turn) or self.lanes[turn[0]].target != self.lanes[turn[1]].source:
                raise ValueError("Turn restrictions must reference connected lanes")
            self.prohibited_turns.add(tuple(turn))

    def turn_allowed(self, incoming: str, outgoing: str) -> bool:
        first, second = self.lanes[incoming], self.lanes[outgoing]
        return first.target == second.source and first.source != second.target and (incoming, outgoing) not in self.prohibited_turns

    @lru_cache(maxsize=512)
    def connector(self, incoming: str, outgoing: str) -> list[Point]:
        first, second = self.lanes[incoming], self.lanes[outgoing]
        if not self.turn_allowed(incoming, outgoing):
            raise ValueError("Disconnected or prohibited turn")
        a, b = first.shape[-1], second.shape[0]
        ah, bh = sample(first.shape, first.length)[2], sample(second.shape, 0)[2]
        control_distance = min(10.0, distance(a, b) * 0.65)
        c = (a[0] + math.cos(ah) * control_distance, a[1] + math.sin(ah) * control_distance)
        d = (b[0] - math.cos(bh) * control_distance, b[1] - math.sin(bh) * control_distance)
        return [tuple((1-t)**3*a[k] + 3*(1-t)**2*t*c[k] + 3*(1-t)*t*t*d[k] + t**3*b[k] for k in (0, 1)) for t in (i / 20 for i in range(21))]

    def route(self, source: str, destination: str, *, closed: set[str] | None = None, costs: dict[str, float] | None = None, previous: str | None = None) -> list[str]:
        closed, costs = closed or set(), costs or {}
        queue = [(0.0, source, previous or "", [])]
        visited = set()
        while queue:
            cost, node, incoming, path = heapq.heappop(queue)
            if node == destination:
                return path
            key = (node, incoming)
            if key in visited:
                continue
            visited.add(key)
            for lane_id in self.outgoing.get(node, []):
                lane = self.lanes[lane_id]
                prohibited = incoming and not self.turn_allowed(incoming, lane_id)
                if lane_id in closed or prohibited:
                    continue
                heapq.heappush(queue, (cost + max(0.01, costs.get(lane_id, lane.length / lane.speed)), lane.target, lane_id, path + [lane_id]))
        return []

    def visual(self) -> dict:
        roads, signal_groups, signals = [], [], []
        points = [point for road in self.payload["roads"] for point in road["shape"]]
        point_dict = lambda p: {"x": p[0], "y": p[1]}
        for index, lane in enumerate(self.lanes.values()):
            shape = [point_dict(point) for point in lane.shape]
            roads.append({"index": index, "function": "normal", "toward_intersection": True, "away_from_intersection": True, "shape": shape, "lanes": [{"id": lane.id, "index": 0, "width": 3.3, "allow": "passenger", "disallow": "", "source_length": lane.length, "clip_start_position": 0, "clip_end_position": lane.length, "shape": shape}]})
            if lane.target in self.intersections:
                x, y, heading = sample(lane.shape, lane.length)
                signal_groups.append({"id": lane.id, "signal_id": lane.id, "lane_id": lane.id, "from_edge_id": lane.id, "kind": "vehicle", "width": 3.3, "heading": math.degrees(heading), "anchor": {"x": x, "y": y}, "stop_line": [point_dict((x + math.sin(heading)*1.65, y-math.cos(heading)*1.65)), point_dict((x-math.sin(heading)*1.65, y+math.cos(heading)*1.65))], "link_indices": [0], "via_lane_ids": []})
        for node_id in self.intersections:
            node = self.nodes[node_id]
            corners = []
            for lane_id in self.incoming[node_id]+self.outgoing[node_id]:
                lane = self.lanes[lane_id]
                x, y, heading = sample(lane.shape, lane.length if lane.target == node_id else 0)
                corners.extend((x + sign*math.sin(heading)*1.7, y-sign*math.cos(heading)*1.7) for sign in (-1, 1))
            polygon = [point_dict(point) for point in convex_hull(corners)]
            signals.append({"id": node_id, "kind": "traffic_light", "x": node["x"], "y": node["y"], "shape": polygon})
        return {"version": 2, "network_id": self.id, "source_net": "OpenStreetMap cached study network", "scope": {"mode": "connected-network"}, "bounds": {"min_x": min(p[0] for p in points)-20, "max_x": max(p[0] for p in points)+20, "min_y": min(p[1] for p in points)-20, "max_y": max(p[1] for p in points)+20}, "roads": roads, "internal_lanes": [], "crossings": [], "walking_areas": [], "signals": signals, "signal_groups": signal_groups, "polygons": [], "source": self.payload["source"], "junctions": [self.nodes[node_id] for node_id in self.intersections]}


def load_network(path: Path = NETWORK_PATH) -> RoadNetwork:
    return RoadNetwork(json.loads(path.read_text(encoding="utf-8")))
