"""Build five connected Tagum junctions from the cached OSM extract."""
from __future__ import annotations

import json
import math
from collections import defaultdict
from pathlib import Path

from simulation.road_network import clip, length, NETWORK_PATH, RoadNetwork


def build_study_network(source_path: Path, count: int = 5) -> dict:
    if not 4 <= count <= 6:
        raise ValueError("Study network must have 4–6 intersections")
    raw = json.loads(source_path.read_text(encoding="utf-8"))
    raw_nodes = {entry["id"]: entry for entry in raw["elements"] if entry["type"] == "node"}
    south, west, north, east = raw["smartflow_source"]["bbox"]
    latitude, longitude = (south+north)/2, (west+east)/2
    coordinates = {node_id: ((node["lon"]-longitude)*111320*math.cos(math.radians(latitude)), (node["lat"]-latitude)*111320) for node_id, node in raw_nodes.items()}
    neighbors, metadata, allowed = defaultdict(set), {}, set()
    for way in raw["elements"]:
        if way["type"] != "way" or way.get("tags", {}).get("access") in {"private", "no"}:
            continue
        tags = way.get("tags", {})
        direction = tags.get("oneway", "yes" if tags.get("junction") == "roundabout" else "no")
        for a, b in zip(way["nodes"], way["nodes"][1:]):
            neighbors[a].add(b)
            neighbors[b].add(a)
            metadata[a, b] = metadata[b, a] = {"osm_way_id": way["id"], "name": tags.get("name", "Unnamed road"), "tags": tags}
            if direction != "-1":
                allowed.add((a, b))
            if direction not in {"yes", "1", "true"}:
                allowed.add((b, a))
    junctions = {node for node, adjacent in neighbors.items() if len(adjacent) != 2}
    segments, traversed = [], set()
    for source in sorted(junctions):
        for neighbor in sorted(neighbors[source]):
            if (source, neighbor) in traversed:
                continue
            chain, previous, current = [source, neighbor], source, neighbor
            while current not in junctions:
                following = next(node for node in neighbors[current] if node != previous)
                chain.append(following)
                previous, current = current, following
            for a, b in zip(chain, chain[1:]):
                traversed.update({(a, b), (b, a)})
            forward = all((a, b) in allowed for a, b in zip(chain, chain[1:]))
            reverse = all((b, a) in allowed for a, b in zip(chain, chain[1:]))
            if not forward and not reverse:
                continue
            if not forward:
                chain.reverse()
            segments.append({"source": chain[0], "target": chain[-1], "shape": [coordinates[node] for node in chain], "oneway": not (forward and reverse), "osm_nodes": chain, **metadata[chain[0], chain[1]]})
    candidates = {node for node in junctions if len(neighbors[node]) >= 3 and south <= raw_nodes[node]["lat"] <= north and west <= raw_nodes[node]["lon"] <= east}
    graph = defaultdict(set)
    for segment in segments:
        a, b = segment["source"], segment["target"]
        if a in candidates and b in candidates and length(segment["shape"]) >= 30:
            graph[a].add(b)
            graph[b].add(a)
    def score(group):
        internal = sum(len(graph[node] & group) for node in group)//2
        extent = sum(math.hypot(*coordinates[node]) for node in group)
        return internal * 1000 - extent
    groups = {frozenset([node]) for node in graph}
    for _ in range(count-1):
        expanded = {group | {neighbor} for group in groups for node in group for neighbor in graph[node] - group}
        groups = set(sorted(expanded, key=lambda group: (-score(group), sorted(group)))[:1000])
    if not groups:
        raise ValueError("No connected study area in this extract")
    selected = sorted(groups, key=lambda group: (-score(group), sorted(group)))[0]
    nodes = {node: {"id": str(node), "x": coordinates[node][0], "y": coordinates[node][1], "lat": raw_nodes[node]["lat"], "lon": raw_nodes[node]["lon"], "boundary": False, "signal_plan": "experimental"} for node in selected}
    roads = []
    for segment in segments:
        a, b = segment["source"], segment["target"]
        if a not in selected and b not in selected:
            continue
        shape = segment["shape"]
        if length(shape) < 30:
            continue
        if a not in selected or b not in selected:
            reverse_shape = a not in selected
            if reverse_shape:
                shape = list(reversed(shape))
            shape = clip(shape, 0, min(length(shape)-10, 110))
            boundary = f"boundary_{len(roads)}"
            nodes[boundary] = {"id": boundary, "x": shape[-1][0], "y": shape[-1][1], "boundary": True}
            if reverse_shape:
                a = boundary
                shape.reverse()
            else:
                b = boundary
        roads.append({"id": f"road{len(roads)}", "source": str(a), "target": str(b), "shape": [[round(x, 3), round(y, 3)] for x, y in shape], "oneway": segment["oneway"], "name": segment["name"], "osm_way_id": segment["osm_way_id"], "osm_node_ids": segment["osm_nodes"], "osm_tags": segment["tags"], "speed_mps": 8.33})
    source = {**raw["smartflow_source"], "origin": {"lat": latitude, "lon": longitude}, "projection": "local equirectangular, metres; study area only", "assumptions": ["One modeled lane per permitted direction, 3.3 m wide", "30 km/h study speed; not a verified posted limit", "Experimental traffic signals at the five selected junctions", "OSM turn restrictions and lane tags require field review", "Boundary stubs truncated at 110 m; no invented road alignment", "Synthetic demand; not measured Tagum counts"]}
    payload = {"id": "tagum_network", "version": 1, "name": "Tagum connected study network", "source": source, "nodes": list(nodes.values()), "roads": roads}
    network = RoadNetwork(payload)
    if len(network.intersections) != count:
        raise ValueError("Incorrect intersection count")
    return payload


if __name__ == "__main__":
    payload = build_study_network(NETWORK_PATH.with_name("tagum_osm.json"))
    NETWORK_PATH.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps({"intersections": [node["id"] for node in payload["nodes"] if not node["boundary"]], "roads": len(payload["roads"]), "names": sorted({road["name"] for road in payload["roads"]})}))
