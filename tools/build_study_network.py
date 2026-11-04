"""Build connected Tagum study junctions (default five) from the cached OSM extract."""
from __future__ import annotations

import argparse
import heapq
import json
import math
import sys
from collections import defaultdict
from pathlib import Path

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from simulation.road_network import clip, length, NETWORK_PATH, RoadNetwork
from tools.site_b_layout import site_b_layout


COUNT_WORDS = {2: "two", 3: "three", 4: "four", 5: "five", 6: "six"}


def build_study_network(source_path: Path, count: int = 5, junction_ids: list[str] | None = None, name: str = "Tagum connected study network", *, source_payload: dict | None = None, boundary_m: float = 110) -> dict:
    if junction_ids:
        count = len(junction_ids)
    if not 2 <= count <= 6:
        raise ValueError("Study network must have 2–6 intersections")
    raw = source_payload if source_payload is not None else json.loads(source_path.read_text(encoding="utf-8"))
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
            shape = clip(shape, 0, min(length(shape)-10, boundary_m))
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


def nearest_on_shape(shape: list, point: tuple) -> tuple[float, tuple[float, float], float]:
    """(distance along the shape, nearest point on it, how far the point is from the shape)."""
    best, walked = None, 0.0
    for (x1, y1), (x2, y2) in zip(shape, shape[1:]):
        dx, dy = x2-x1, y2-y1
        run = math.hypot(dx, dy)
        share = max(0.0, min(1.0, ((point[0]-x1)*dx+(point[1]-y1)*dy)/(run*run)))
        found = (x1+share*dx, y1+share*dy)
        gap = math.dist(found, point)
        if best is None or gap < best[2]:
            best = (walked+share*run, found, gap)
        walked += run
    return best


LOOP_CORNER_TANGENT_M = 25.0  # Provisional: drawn rounding of a sharp corner on a two-way side street; opposing bodies overlap at a square corner.


def round_corners(shape: list, tangent_m: float = LOOP_CORNER_TANGENT_M) -> list:
    """Replace each bend of more than 5 degrees by a smooth curve starting `tangent_m` (at most 45% of the shorter side) before it."""
    points = [tuple(shape[0])]
    for before, corner, after in zip(shape, shape[1:], shape[2:]):
        to_before, to_after = math.dist(corner, before), math.dist(corner, after)
        heading_in = math.atan2(corner[1]-before[1], corner[0]-before[0])
        heading_out = math.atan2(after[1]-corner[1], after[0]-corner[0])
        turn = abs(math.atan2(math.sin(heading_out-heading_in), math.cos(heading_out-heading_in)))
        if turn < math.radians(5):
            points.append(tuple(corner))
            continue
        reach = min(tangent_m, 0.45*to_before, 0.45*to_after)
        start = (corner[0]+(before[0]-corner[0])*reach/to_before, corner[1]+(before[1]-corner[1])*reach/to_before)
        end = (corner[0]+(after[0]-corner[0])*reach/to_after, corner[1]+(after[1]-corner[1])*reach/to_after)
        for step in range(9):
            t = step/8
            points.append(tuple((1-t)**2*start[k]+2*t*(1-t)*corner[k]+t*t*end[k] for k in (0, 1)))
    points.append(tuple(shape[-1]))
    return points


LOOP_ATTACH_TOLERANCE_M = 5.0  # the leg is drawn straight, so an OSM junction may sit this far off the drawn road
LOOP_MINOR_CLASSES = frozenset({"residential", "unclassified", "living_street", "service"})


def add_detour_loop(roads: list, nodes: list, raw: dict, coords: dict, loop: dict, *, network_id: str, number: int) -> dict:
    """Join two legs by a side-street loop. Each end splits its leg at a new first-come junction; the leg's road nearest
    the study junction keeps its id. Minor streets along the loop are drawn as one plain two-way road."""
    osm_nodes = {entry["id"]: entry for entry in raw["elements"] if entry["type"] == "node"}
    adjacency = defaultdict(dict)
    for way in raw["elements"]:
        tags = way.get("tags", {}) if way["type"] == "way" else {}
        if way["type"] == "way" and tags.get("highway") in LOOP_MINOR_CLASSES and tags.get("access") not in {"private", "no"}:
            for a, b in zip(way["nodes"], way["nodes"][1:]):
                adjacency[a][b] = adjacency[b][a] = math.dist(coords[a], coords[b])
    # Each stretch between the chosen OSM nodes follows the shortest minor streets, so the loop is a fixed list of nodes.
    chain = [loop["osm_nodes"][0]]
    for start, goal in zip(loop["osm_nodes"], loop["osm_nodes"][1:]):
        distance, previous, queue = {start: 0.0}, {}, [(0.0, start)]
        while queue:
            cost, node = heapq.heappop(queue)
            if node == goal:
                break
            if cost > distance[node]:
                continue
            for neighbour, step in adjacency[node].items():
                if cost+step < distance.get(neighbour, math.inf):
                    distance[neighbour], previous[neighbour] = cost+step, node
                    heapq.heappush(queue, (cost+step, neighbour))
        if goal not in previous:
            raise ValueError(f"Detour loop {loop['name']!r}: no minor-street path from OSM node {start} to {goal}")
        stretch = [goal]
        while stretch[-1] != start:
            stretch.append(previous[stretch[-1]])
        chain.extend(reversed(stretch[:-1]))
    attached = []
    for position, osm_id in enumerate((chain[0], chain[-1])):
        host = next((road for road in roads if osm_id in road["osm_node_ids"]), None)
        if host is None:
            raise ValueError(f"Detour loop {loop['name']!r}: OSM node {osm_id} is not on any modelled leg")
        along, point, gap = nearest_on_shape([tuple(p) for p in host["shape"]], coords[osm_id])
        if host["source"] != nodes[0]["id"]:
            raise ValueError(f"Detour loop {loop['name']!r}: leg {host['id']} does not start at the study junction")
        if gap > LOOP_ATTACH_TOLERANCE_M:
            raise ValueError(f"Detour loop {loop['name']!r}: OSM node {osm_id} is {gap:.1f} m from the drawn leg")
        junction = f"{network_id}_j{number+position}"
        lat = nodes[0]["lat"]+point[1]/111320
        lon = nodes[0]["lon"]+point[0]/(111320*math.cos(math.radians(nodes[0]["lat"])))
        nodes.append({"id": junction, "x": round(point[0], 3), "y": round(point[1], 3), "lat": lat, "lon": lon, "boundary": False, "default_control_mode": "first_come"})
        shape = [tuple(p) for p in host["shape"]]
        inner, outer = clip(shape, 0, along), clip(shape, along, length(shape))
        inner[-1] = outer[0] = point
        outer_index = host["osm_node_ids"].index(osm_id)
        roads.append({**host, "id": f"road{len(roads)}", "source": junction, "target": host["target"], "shape": [[round(x, 3), round(y, 3)] for x, y in outer],
                      "osm_node_ids": host["osm_node_ids"][outer_index:]})
        host.update(target=junction, shape=[[round(x, 3), round(y, 3)] for x, y in inner], osm_node_ids=host["osm_node_ids"][:outer_index+1])
        attached.append((junction, point))
    shape = round_corners([attached[0][1], *[coords[osm_id] for osm_id in chain[1:-1]], attached[1][1]])
    way_ids = [next(way["id"] for way in raw["elements"] if way["type"] == "way" and a in way["nodes"] and b in way["nodes"] and way.get("tags", {}).get("highway") in LOOP_MINOR_CLASSES)
               for a, b in zip(chain, chain[1:])]
    roads.append({"id": f"road{len(roads)}", "source": attached[0][0], "target": attached[1][0], "shape": [[round(x, 3), round(y, 3)] for x, y in shape],
                  "oneway": False, "name": loop["name"], "osm_way_id": way_ids[0], "osm_node_ids": chain,
                  "osm_tags": {"highway": "residential/unclassified", "note": "minor streets joined as one plain road; OSM ways " + ", ".join(str(w) for w in dict.fromkeys(way_ids))},
                  "speed_mps": 8.33})
    return {"junctions": [junction for junction, _ in attached], "length_m": round(length(shape), 1)}


def build_site_network(source_path: Path, centre: tuple[float, float], *, network_id: str, name: str,
                       join_radius_m: float = 25.0, approach_m: float = 250.0,
                       approach_overrides_m: dict[str, float] | None = None,
                       extra_assumptions: list[str] | None = None, detour_loops: list[dict] | None = None) -> dict:
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
    loop_assumptions = []
    for loop in detour_loops or []:
        added = add_detour_loop(roads, output_nodes, raw, coords, loop, network_id=network_id, number=2+len(loop_assumptions))
        loop_assumptions += [f"Detour loop '{loop['name']}' ({added['length_m']:g} m, new junctions {' and '.join(added['junctions'])}) is provisional geometry from OpenStreetMap, not field-checked; "
                             f"its minor streets are drawn as one plain two-way road with corners rounded over {LOOP_CORNER_TANGENT_M:g} m, and its two junctions use first-come right-of-way, not a signal.",
                             "The loop's side streets start empty: no traffic was observed there and none is generated on them; only road closures send vehicles onto the loop."]
    assumptions = ["Lane counts from OSM lanes tags; carriageway widths need field measurement", "30 km/h study speed; not a verified posted limit", "Driveways, service roads and minor side streets along approaches are not modelled", "No traffic signal exists today; signal plans are proposals", f"Approach length {approach_m:g} m per leg unless field queue reach needs more", "Synthetic demand until Field Observer counts are imported", f"The first {JUNCTION_MOUTH_STRAIGHT_M:g} m of every leg is drawn straight from the junction, and map bends under {LEG_SIMPLIFY_TOLERANCE_M:g} m are drawn straight; check both against the road"]
    source = {**raw["smartflow_source"], "origin": {"lat": lat, "lon": lon}, "projection": "local equirectangular, metres; study area only", "assumptions": assumptions + loop_assumptions + (extra_assumptions or [])}
    payload = {"id": network_id, "version": 1, "name": name, "source": source, "nodes": output_nodes, "roads": roads}
    RoadNetwork(payload)
    return payload


SITE_A_CENTRE = (7.4617375, 125.8026196)
SITE_A_NAME = "Site A — Capitol Circumferential Rd × Dalisay Gante Rd"
# OSM nodes found by the loop survey: the Capitol Circumferential Road junction 226 m west of the study junction, the corner
# of the residential/unclassified street, its junction with the short residential link, and the Dalisay Gante Road junction 67 m north.
SITE_A_WEST_NORTH_LOOP = {"name": "Unnamed side street", "osm_nodes": [1387566813, 1527791811, 7116314100, 1402951602]}


def build_site_a_network(source_path: Path, *, with_loop: bool = True) -> dict:
    """Site A as installed (`with_loop`) or as it was with one junction (kept under data/networks/history)."""
    return build_site_network(source_path, SITE_A_CENTRE, network_id="tagum_site_a", name=SITE_A_NAME,
                              detour_loops=[SITE_A_WEST_NORTH_LOOP] if with_loop else None)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--junctions", help="Comma-separated OSM node ids to keep instead of auto-selecting five")
    parser.add_argument("--name", default="Tagum connected study network")
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--site", help="Site centre LAT,LON")
    parser.add_argument("--site-b-corridor", action="store_true", help="Expand Site B to the next highway junction using cached OSM")
    parser.add_argument("--network-id")
    parser.add_argument("--source", type=Path, default=NETWORK_PATH.with_name("tagum_osm.json"))
    parser.add_argument("--approach-m", type=float, default=250.0)
    parser.add_argument("--approach", action="append", default=[])
    parser.add_argument("--assumption", action="append", default=[])
    parser.add_argument("--site-a", action="store_true", help="Rebuild the installed Site A (with its West-North loop) from the cached OSM extract")
    args = parser.parse_args()
    if args.site_a:
        payload = build_site_a_network(args.source if args.source != NETWORK_PATH.with_name("tagum_osm.json") else NETWORK_PATH.with_name("osm_site_a.json"))
    elif args.site_b_corridor:
        from tools.site_b_corridor import build_site_b_corridor
        payload = build_site_b_corridor(args.source)
    elif args.site:
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
