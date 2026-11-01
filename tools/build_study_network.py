"""Build connected Tagum study junctions (default five) from the cached OSM extract."""
from __future__ import annotations

import argparse
import json
import math
import sys
from collections import defaultdict
from pathlib import Path

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from simulation.road_network import clip, length, NETWORK_PATH, RoadNetwork


COUNT_WORDS = {2: "two", 3: "three", 4: "four", 5: "five", 6: "six"}


def build_study_network(source_path: Path, count: int = 5, junction_ids: list[str] | None = None, name: str = "Tagum connected study network") -> dict:
    if junction_ids:
        count = len(junction_ids)
    if not 2 <= count <= 6:
        raise ValueError("Study network must have 2–6 intersections")
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
    if junction_ids:
        selected = frozenset(int(node) for node in junction_ids)
        if not selected <= set(graph) or not all(graph[node] & selected for node in selected):
            raise ValueError("Requested junctions must be connected study-area junctions")
    elif not groups:
        raise ValueError("No connected study area in this extract")
    else:
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
    source = {**raw["smartflow_source"], "origin": {"lat": latitude, "lon": longitude}, "projection": "local equirectangular, metres; study area only", "assumptions": ["One modeled lane per permitted direction, 3.3 m wide", "30 km/h study speed; not a verified posted limit", f"Experimental traffic signals at the {COUNT_WORDS[count]} selected junctions", "OSM turn restrictions and lane tags require field review", "Boundary stubs truncated at 110 m; no invented road alignment", "Synthetic demand; not measured Tagum counts"]}
    payload = {"id": "tagum_network", "version": 1, "name": name, "source": source, "nodes": list(nodes.values()), "roads": roads}
    network = RoadNetwork(payload)
    if len(network.intersections) != count:
        raise ValueError("Incorrect intersection count")
    return payload


MAJOR_CLASSES = frozenset({"trunk", "trunk_link", "primary", "primary_link", "secondary", "secondary_link", "tertiary", "tertiary_link"})


JUNCTION_MOUTH_STRAIGHT_M = 30.0  # Provisional: field-check that each leg really is straight this far from the junction.


LEG_SIMPLIFY_TOLERANCE_M = 5.0  # Provisional: map vertex jitter, not road shape, below this.


def simplify_leg(shape: list, tolerance_m: float = LEG_SIMPLIFY_TOLERANCE_M) -> list:
    """Douglas-Peucker: drop vertices within `tolerance_m` of the straight line between their neighbours, so map jitter is not drawn as a bend."""
    if len(shape) < 3:
        return list(shape)
    (x1, y1), (x2, y2) = shape[0], shape[-1]
    chord = math.dist(shape[0], shape[-1]) or 1.0
    index, farthest = max(((i, abs((x2-x1)*(y1-point[1])-(x1-point[0])*(y2-y1))/chord) for i, point in enumerate(shape[1:-1], 1)), key=lambda item: item[1])
    if farthest <= tolerance_m:
        return [shape[0], shape[-1]]
    return simplify_leg(shape[:index+1], tolerance_m)[:-1] + simplify_leg(shape[index:], tolerance_m)


def straighten_mouth(shape: list, mouth_m: float = JUNCTION_MOUTH_STRAIGHT_M) -> list:
    """Drop map vertices closer than `mouth_m` to the junction so the leg leaves it straight; lanes either side of a kink there cross."""
    kept = [shape[0]] + [point for point in shape[1:] if math.dist(shape[0], point) >= mouth_m]
    return kept if len(kept) >= 2 else [shape[0], shape[-1]]


def build_site_network(source_path: Path, centre: tuple[float, float], *, network_id: str, name: str,
                       join_radius_m: float = 25.0, approach_m: float = 250.0,
                       approach_overrides_m: dict[str, float] | None = None,
                       extra_assumptions: list[str] | None = None) -> dict:
    """Build a provisional, isolated junction; geometry and restrictions need field review."""
    if not network_id or join_radius_m <= 0 or approach_m <= 0:
        raise ValueError("A network id and positive distances are required")
    raw = json.loads(source_path.read_text(encoding="utf-8"))
    lat, lon = centre
    nodes = {e["id"]: e for e in raw["elements"] if e["type"] == "node"}
    coords = {i: ((n["lon"] - lon) * 111320 * math.cos(math.radians(lat)), (n["lat"] - lat) * 111320) for i, n in nodes.items()}
    adjacency = defaultdict(list)
    major_ways = defaultdict(set)
    for way in raw["elements"]:
        if way["type"] != "way" or way.get("tags", {}).get("access") in {"private", "no"}:
            continue
        tags = way.get("tags", {})
        if tags.get("highway") not in MAJOR_CLASSES:
            continue
        direction = tags.get("oneway", "yes" if tags.get("junction") == "roundabout" else "no")
        for a, b in zip(way["nodes"], way["nodes"][1:]):
            if a not in nodes or b not in nodes:
                raise ValueError(f"Way {way['id']} references missing node")
            adjacency[a].append((b, way, direction != "-1", direction not in {"yes", "1", "true"}))
            adjacency[b].append((a, way, direction not in {"yes", "1", "true"}, direction != "-1"))
            major_ways[a].add(way["id"]); major_ways[b].add(way["id"])
    candidates = [i for i in adjacency if len(major_ways[i]) >= 2 or len(adjacency[i]) >= 3]
    if not candidates:
        raise ValueError("No major-road junction found near site")
    closest = min(candidates, key=lambda i: math.hypot(*coords[i]))
    if math.hypot(*coords[closest]) > join_radius_m:
        raise ValueError("No major-road junction found within join radius")
    joined = {i for i in candidates if math.hypot(*coords[i]) <= join_radius_m}
    centre_id = network_id + "_j"
    output_nodes = [{"id": centre_id, "x": 0, "y": 0, "lat": lat, "lon": lon, "boundary": False}]
    roads = []
    overrides = approach_overrides_m or {}
    for start in sorted(joined):
        for nxt, way, forward, reverse in sorted(adjacency[start], key=lambda edge: (edge[0], edge[1]["id"])):
            if nxt in joined:
                continue
            chain = [start, nxt]
            prev, current = start, nxt
            first_way = way
            while True:
                choices = [edge for edge in adjacency[current] if edge[0] != prev and edge[0] not in joined]
                current_name = way.get("tags", {}).get("name")
                other_roads = [edge for edge in choices if edge[1]["id"] != way["id"] and
                               (not current_name or edge[1].get("tags", {}).get("name") != current_name)]
                if other_roads or not choices:
                    break
                same = [edge for edge in choices if edge[1]["id"] == way["id"]]
                if not same and len(choices) != 1:
                    break
                following, next_way, fwd, rev = (same or choices)[0]
                if following in chain:
                    break
                forward, reverse = forward and fwd, reverse and rev
                chain.append(following)
                prev, current, way = current, following, next_way
            shape = [(0.0, 0.0)] + [coords[i] for i in chain[1:]]
            total = length(shape)
            ends_at_major = bool(other_roads)
            requested = float(overrides.get(str(first_way["id"]), approach_m))
            available = total - 10 if ends_at_major else total
            limit = min(requested, available)
            if limit < 30:
                raise ValueError(f"Leg along {first_way.get('tags', {}).get('name', 'Unnamed road')} (way {first_way['id']}) is only {limit:.1f} m; raise --approach or check the map")
            shape = straighten_mouth(simplify_leg(clip(shape, 0, limit)))
            if not forward and not reverse:
                raise ValueError(f"Inconsistent direction on way {first_way['id']}")
            boundary = f"boundary_{len(roads)}"
            output_nodes.append({"id": boundary, "x": shape[-1][0], "y": shape[-1][1], "boundary": True})
            source, target = centre_id, boundary
            if not forward:
                source, target = target, source
                shape.reverse(); chain.reverse()
            tags = first_way.get("tags", {})
            roads.append({"id": f"road{len(roads)}", "source": source, "target": target,
                          "shape": [[round(x, 3), round(y, 3)] for x, y in shape],
                          "oneway": not (forward and reverse), "name": tags.get("name", "Unnamed road"),
                          "osm_way_id": first_way["id"], "osm_node_ids": chain, "osm_tags": tags, "speed_mps": 8.33})
    assumptions = ["Lane counts from OSM lanes tags; carriageway widths need field measurement", "30 km/h study speed; not a verified posted limit", "Driveways, service roads and minor side streets along approaches are not modelled", "No traffic signal exists today; signal plans are proposals", f"Approach length {approach_m:g} m per leg unless field queue reach needs more", "Synthetic demand until Field Observer counts are imported", f"The first {JUNCTION_MOUTH_STRAIGHT_M:g} m of every leg is drawn straight from the junction, and map bends under {LEG_SIMPLIFY_TOLERANCE_M:g} m are drawn straight; check both against the road"]
    source = {**raw["smartflow_source"], "origin": {"lat": lat, "lon": lon}, "projection": "local equirectangular, metres; study area only", "assumptions": assumptions + (extra_assumptions or [])}
    payload = {"id": network_id, "version": 1, "name": name, "source": source, "nodes": output_nodes, "roads": roads}
    RoadNetwork(payload)
    return payload


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--junctions", help="Comma-separated OSM node ids to keep instead of auto-selecting five")
    parser.add_argument("--name", default="Tagum connected study network")
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--site", help="Site centre LAT,LON")
    parser.add_argument("--network-id")
    parser.add_argument("--source", type=Path, default=NETWORK_PATH.with_name("tagum_osm.json"))
    parser.add_argument("--approach-m", type=float, default=250.0)
    parser.add_argument("--approach", action="append", default=[])
    parser.add_argument("--assumption", action="append", default=[])
    args = parser.parse_args()
    if args.site:
        if not args.network_id:
            parser.error("--network-id is required with --site")
        try:
            site = tuple(map(float, args.site.split(",")))
            if len(site) != 2:
                raise ValueError("--site requires LAT,LON")
            overrides = dict(item.split("=", 1) for item in args.approach)
            payload = build_site_network(args.source, site, network_id=args.network_id, name=args.name, approach_m=args.approach_m, approach_overrides_m=overrides, extra_assumptions=args.assumption)
        except ValueError as exc:
            parser.error(str(exc))
    else:
        payload = build_study_network(args.source, junction_ids=args.junctions.split(",") if args.junctions else None, name=args.name)
    args.output.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps({"intersections": [node["id"] for node in payload["nodes"] if not node["boundary"]], "roads": len(payload["roads"]), "names": sorted({road["name"] for road in payload["roads"]})}))
