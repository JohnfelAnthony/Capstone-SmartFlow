"""Build the Site B corridor from cached OSM; joined median crossings remain provisional."""
import copy
import math
from collections import defaultdict
from pathlib import Path


def build_site_b_corridor(source_path: Path) -> dict:
    import json
    from tools.build_study_network import build_study_network
    from simulation.road_network import RoadNetwork

    raw = json.loads(source_path.read_text(encoding="utf-8"))
    nodes = {e["id"]: e for e in raw["elements"] if e["type"] == "node"}
    ways = [e for e in raw["elements"] if e["type"] == "way" and e.get("tags", {}).get("name")]
    adjacent, highway = defaultdict(set), set()
    for way in ways:
        for a, b in zip(way["nodes"], way["nodes"][1:]):
            adjacent[a].add(b); adjacent[b].add(a)
        if "Highway" in way.get("tags", {}).get("name", ""):
            highway.update(way["nodes"])
    candidates = sorted(i for i in highway if len(adjacent[i]) >= 3)
    def metres(a, b):
        return math.hypot((a["lon"]-b["lon"])*110380, (a["lat"]-b["lat"])*111320)
    groups = []
    for i in candidates:
        group = next((g for g in groups if any(metres(nodes[i], nodes[j]) < 25 for j in g)), None)
        if group is None:
            groups.append([i])
        else:
            group.append(i)
    for i in sorted(adjacent):
        if i not in highway and len(adjacent[i]) >= 3:
            group = next((g for g in groups if 376307655 in g and any(metres(nodes[i], nodes[j]) < 25 for j in g)), None)
            if group is not None:
                group.append(i)
    remap = {i: min(g) for g in groups for i in g}
    merged = copy.deepcopy(raw)
    new_nodes = {i: copy.deepcopy(n) for i, n in nodes.items() if remap.get(i, i) == i}
    for group in groups:
        n = new_nodes[min(group)]
        n["lat"] = sum(nodes[i]["lat"] for i in group)/len(group)
        n["lon"] = sum(nodes[i]["lon"] for i in group)/len(group)
    new_ways = []
    for way in ways:
        chain = []
        for i in way["nodes"]:
            j = remap.get(i, i)
            if not chain or chain[-1] != j:
                chain.append(j)
        if len(chain) > 1:
            new_ways.append({**way, "nodes": chain})
    merged["elements"] = list(new_nodes.values())+new_ways
    focus = remap[376307655]
    north = sorted((min(g) for g in groups if new_nodes[min(g)]["lat"] > new_nodes[focus]["lat"]), key=lambda i: metres(new_nodes[focus], new_nodes[i]))
    selected = [focus, north[0]]
    payload = build_study_network(source_path, junction_ids=[str(i) for i in selected], source_payload=merged, boundary_m=250,
                                  name="Site B — CitiHardware and neighboring highway junction")
    old_id = str(focus)
    for node in payload["nodes"]:
        if node["id"] == old_id:
            node["id"] = "tagum_site_b_j"
        if not node["boundary"]:
            node["default_control_mode"] = "first_come" if node["id"] != "tagum_site_b_j" else "signalized"
            node["label"] = "CitiHardware study junction" if node["id"] == "tagum_site_b_j" else "Neighboring highway junction (no signal)"
    for road in payload["roads"]:
        for endpoint in ("source", "target"):
            if road[endpoint] == old_id:
                road[endpoint] = "tagum_site_b_j"
    payload["nodes"].sort(key=lambda n: n["id"] != "tagum_site_b_j")
    payload.update(id="tagum_site_b", version=2)
    payload["source"]["assumptions"] = ["Provisional OSM corridor, not field validated", "Only CitiHardware is a candidate signal/RL junction", "Neighboring junction uses first-come no-signal control", "Nearby median nodes joined within 25 m; divided-road reconstruction remains outstanding", "Unnamed local links omitted; frontage topology remains outstanding", "Boundary legs extend up to 250 m, stopping before the next mapped junction", "Synthetic demand; no traffic effectiveness claimed"]
    RoadNetwork(payload)
    return payload
