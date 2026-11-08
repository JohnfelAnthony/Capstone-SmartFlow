"""Site B with the side streets the owner painted and approved (D46): OpenStreetMap streets attached to the measured core.

The core (`tools/site_b_measured_layout.py`, D32) keeps its carriageways, islands, sheds, site features, the Bonifacio kerb and the
Sobrecarey bus/truck ban. Each new street meets the network at a real shared junction node, and a street ends only at a true network
boundary. Run `python -m tools.site_b_street_grid` to rebuild `data/networks/tagum_site_b.json` offline from the cached extracts.
"""
from __future__ import annotations

import argparse
import copy
import json
import math
from pathlib import Path

from simulation.road_network import RoadNetwork, clip
from tools.build_study_network import LEG_SIMPLIFY_TOLERANCE_M, LOOP_BEND_RADIUS_M, JUNCTION_MOUTH_STRAIGHT_M, nearest_on_shape, round_corners, simplify_leg, straighten_mouth
from tools.site_b_measured_layout import ASSUMPTIONS as CORE_ASSUMPTIONS
from tools.site_b_measured_layout import BEND_FROM_NODE_M, CARRIAGEWAY_CENTRE_M, CARRIAGEWAY_EDGE_M, MEDIAN_WIDTH_M, build_measured_site_b

ROOT = Path(__file__).resolve().parents[1]/"data"/"networks"
SOURCES = (ROOT/"osm_site_b.json", ROOT/"osm_site_b_north.json")
CORRIDOR = ROOT/"history"/"tagum_site_b_osm_corridor.json"
ORIGIN = (7.4382645, 125.8025575)
PREFIX = "tagum_site_b_j"

HIGHWAY_JUNCTION_CLEARANCE_M = 16.0  # Provisional: a side street's stop line stands 5.9 m clear of the 20.3 m dual carriageway; field-check it.
OSMENA_JUNCTION_CLEARANCE_M = 28.0  # Provisional: Osmeña Street leaves the highway at about 38 degrees, so its stop line needs 28 m for its lane to stand clear of the carriageway beside it.
NORTH_EAST_EXTENSION_M = 80.0  # the highway runs this far past the Osmeña junction, so traffic entering there has room before it
STUB_M = 60.0  # Sobrecarey and Dao run this far past the grid, to the boundary where their counted traffic enters

# Approved OSM streets, as (way id, from node, to node). Every chain starts and ends at a junction or a bend of the network.
STREETS = {
    "sobrecarey": [(1435836406, 1402917759, 1217544585)],
    "sobrecarey_stub": [(1435836406, 1217544585, 1304820512)],
    "magsaysay": [(105732734, 1217544585, 1255345377)],
    "osmena": [(105732734, 1255345377, 1217544533), (31614940, 1217544533, 10654283979)],
    "west_loop": [(126581640, 1402917759, 1527897579), (126582225, 1527897579, 1402935111), (126582224, 1402935111, 2918139394)],
    "dao": [(732013634, 1217597311, 1400710199)],
    "dao_stub": [(732013634, 1400710199, 1217597251)],
    "southeast_loop": [(1457627774, 1400710199, 1400710245), (126330385, 1400710245, 1400710237), (126330391, 1400710237, 8107640302)],
}
DAO_INNER_NODE, ACACIA_CORNER_NODE = 1217597311, 1217597477  # the inner link (way 105737414) runs between these two
DJG_NODE, SOBRECAREY_TOP_NODE, BONIFACIO_TOP_NODE, EBONY_NODE = 1402917759, 1217544585, 1255345377, 1400710199
HIGHWAY_NORTHWEST_NODE, HIGHWAY_SOUTHEAST_NODE, OSMENA_FIRST_NODE, OSMENA_SECOND_NODE = 2918139394, 8107640302, 10654283979, 1527881959


def load_osm() -> tuple[dict, dict]:
    nodes, ways = {}, {}
    for path in SOURCES:
        for element in json.loads(path.read_text(encoding="utf-8"))["elements"]:
            if element["type"] == "node":
                nodes[element["id"]] = element
            elif element["type"] == "way":
                ways.setdefault(element["id"], element)
    lat, lon = ORIGIN
    return {i: ((n["lon"]-lon)*111320*math.cos(math.radians(lat)), (n["lat"]-lat)*111320) for i, n in nodes.items()}, ways


def chain_of(ways: dict, steps: list[tuple[int, int, int]]) -> list[int]:
    """OSM node ids along consecutive ways; each step runs from one node of a way to another, in either direction."""
    chain: list[int] = []
    for way_id, start, end in steps:
        listed = ways[way_id]["nodes"]
        first, last = listed.index(start), listed.index(end)
        piece = listed[first:last+1] if first <= last else listed[last:first+1][::-1]
        chain += piece[1:] if chain else piece
    return chain


def street_shape(points: list[tuple[float, float]]) -> list[list[float]]:
    """Map jitter under 5 m is drawn straight, so are the first 30 m at each end, and bends are circular arcs of 25 m radius."""
    shape = straighten_mouth(straighten_mouth(simplify_leg(points))[::-1])[::-1]
    return [[round(x, 3), round(y, 3)] for x, y in round_corners(shape)]


class Axis:
    """Metres along the highway from the study junction, and across it toward the north-west (the core's own frame)."""

    def __init__(self, study: dict, neighbor: dict):
        self.origin = (study["x"], study["y"])
        self.span = math.dist(self.origin, (neighbor["x"], neighbor["y"]))
        self.ux, self.uy = (neighbor["x"]-study["x"])/self.span, (neighbor["y"]-study["y"])/self.span

    def along(self, point) -> float:
        return (point[0]-self.origin[0])*self.ux+(point[1]-self.origin[1])*self.uy

    def at(self, along: float, across: float) -> list[float]:
        return [round(self.origin[0]+along*self.ux-across*self.uy, 3), round(self.origin[1]+along*self.uy+across*self.ux, 3)]

    def crossing(self, a, b) -> float:
        """Along-distance where the line through points a and b meets the highway centre line."""
        across = lambda p: -(p[0]-self.origin[0])*self.uy+(p[1]-self.origin[1])*self.ux
        share = across(a)/(across(a)-across(b))
        return self.along((a[0]+share*(b[0]-a[0]), a[1]+share*(b[1]-a[1])))


def non_geometry(road: dict) -> dict:
    return {key: value for key, value in road.items() if key not in {"id", "source", "target", "shape"}}


def build_site_b_street_grid(points: dict | None = None, ways: dict | None = None) -> dict:
    """The measured Site B plus every approved side street, as one connected network."""
    if points is None or ways is None:
        points, ways = load_osm()
    corridor = json.loads(CORRIDOR.read_text(encoding="utf-8"))
    corridor_nodes = {node["id"]: node for node in corridor["nodes"]}
    axis = Axis(corridor_nodes["tagum_site_b_j"], corridor_nodes["1115349256"])
    span, at, centre, bend = axis.span, axis.at, CARRIAGEWAY_CENTRE_M, BEND_FROM_NODE_M
    a_northwest, a_southeast = axis.along(points[HIGHWAY_NORTHWEST_NODE]), axis.along(points[HIGHWAY_SOUTHEAST_NODE])
    a_northeast = axis.crossing(points[OSMENA_FIRST_NODE], points[OSMENA_SECOND_NODE])
    clear = HIGHWAY_JUNCTION_CLEARANCE_M
    # Islands and street lights stay clear of a new junction's stop lines; the planted strip only on the side the street crosses.
    gaps = ((a_northwest-clear, a_northwest+clear, ("median", "light", "nw")), (a_southeast-clear, a_southeast+clear, ("median", "light", "se")),
            (a_northeast-OSMENA_JUNCTION_CLEARANCE_M, a_northeast+OSMENA_JUNCTION_CLEARANCE_M, ("median", "light", "nw")))
    payload = build_measured_site_b(corridor, gaps=gaps)
    nodes = {node["id"]: node for node in payload["nodes"]}
    roads = {road["id"]: road for road in payload["roads"]}
    study, neighbor = nodes["tagum_site_b_j"], nodes["1115349256"]
    neighbor["generated_demand"] = False  # owner's decision (Nov 9): generated pedestrians cross only at the study junction
    here = lambda node: [node["x"], node["y"]]
    lat0, lon0 = ORIGIN
    new_nodes: dict[str, dict] = {}
    new_roads: list[dict] = []

    def junction(key: str, point, clearance: float | None = None) -> str:
        new_nodes[key] = {"id": key, "x": round(point[0], 3), "y": round(point[1], 3), "lat": lat0+point[1]/111320,
                          "lon": lon0+point[0]/(111320*math.cos(math.radians(lat0))), "boundary": False, "default_control_mode": "first_come", "generated_demand": False,
                          **({"junction_clearance_m": clearance} if clearance else {})}
        return key

    def add(source: str, target: str, shape: list, *, template: dict | None = None, steps: list | None = None, minor: bool = True) -> dict:
        road = {"id": None, "source": source, "target": target, "shape": shape, "oneway": False, "name": "Unnamed road", "speed_mps": 8.33, **(template or {})}
        if steps:
            chain, tags = chain_of(ways, steps), ways[steps[0][0]].get("tags", {})
            ids = list(dict.fromkeys(way for way, _, _ in steps))
            road.update(osm_way_id=ids[0], osm_node_ids=chain, osm_tags=tags if len(ids) == 1 else {**tags, "note": "OSM ways " + ", ".join(str(w) for w in ids)})
        if minor:
            road["minor"] = True
        else:
            road.pop("minor", None)
        new_roads.append(road)
        return road

    # The highway south-west of the study junction: a junction on the median centre line at each street, each carriageway cut in three.
    j_northwest = junction("northwest", at(a_northwest, 0), clear)
    j_southeast = junction("southeast", at(a_southeast, 0), clear)
    pn, ps = here(new_nodes[j_northwest]), here(new_nodes[j_southeast])
    out, back = roads["road4"], roads["road5"]
    out_kind, back_kind = non_geometry(out), non_geometry(back)
    end_out, end_back = here(nodes["boundary_4"]), here(nodes["boundary_5"])
    out.update(target=j_southeast, shape=[here(study), at(-bend, centre), at(a_southeast+bend, centre), ps])
    back.update(source=j_southeast, shape=[ps, at(a_southeast+bend, -centre), at(-bend, -centre), here(study)])
    add(j_southeast, j_northwest, [ps, at(a_southeast-bend, centre), at(a_northwest+bend, centre), pn], template=out_kind, minor=False)
    far_out = add(j_northwest, "boundary_4", [pn, at(a_northwest-bend, centre), end_out], template=out_kind, minor=False)
    add(j_northwest, j_southeast, [pn, at(a_northwest+bend, -centre), at(a_southeast-bend, -centre), ps], template=back_kind, minor=False)
    far_back = add("boundary_5", j_northwest, [end_back, at(a_northwest-bend, -centre), pn], template=back_kind, minor=False)

    # The highway north-east: the Osmeña junction, then on to new ends.
    j_northeast = junction("northeast", at(a_northeast, 0), OSMENA_JUNCTION_CLEARANCE_M)
    pe, end_along = here(new_nodes[j_northeast]), a_northeast+NORTH_EAST_EXTENSION_M
    nodes["boundary_8"].update(zip(("x", "y"), at(end_along, -centre)))
    nodes["boundary_9"].update(zip(("x", "y"), at(end_along, centre)))
    out, back = roads["road8"], roads["road9"]
    out_kind, back_kind = non_geometry(out), non_geometry(back)
    out.update(target=j_northeast, shape=[here(neighbor), at(span+bend, -centre), at(a_northeast-bend, -centre), pe])
    back.update(source=j_northeast, shape=[pe, at(a_northeast-bend, centre), at(span+bend, centre), here(neighbor)])
    exit_east = add(j_northeast, "boundary_8", [pe, at(a_northeast+bend, -centre), at(end_along, -centre)], template=out_kind, minor=False)
    entry_east = add("boundary_9", j_northeast, [at(end_along, centre), at(a_northeast+bend, centre), pe], template=back_kind, minor=False)

    # Sobrecarey Street runs on north to Magsaysay Street, Bonifacio Street joins it there, and Osmeña Street comes back down to the highway.
    sobrecarey, bonifacio = roads["road1"], roads["road7"]
    j_west = junction("sobrecarey_west", points[DJG_NODE])
    j_top = junction("sobrecarey_north", points[SOBRECAREY_TOP_NODE])
    j_bonifacio = junction("bonifacio_north", points[BONIFACIO_TOP_NODE])
    sobrecarey.update(target=j_west, shape=[sobrecarey["shape"][0], sobrecarey["shape"][1], here(new_nodes[j_west])])
    kind = non_geometry(sobrecarey)
    sobrecarey_pieces = [add(j_west, j_top, street_shape([points[i] for i in chain_of(ways, STREETS["sobrecarey"])]), template=kind, steps=STREETS["sobrecarey"], minor=False)]
    stub = clip(street_shape([points[i] for i in chain_of(ways, STREETS["sobrecarey_stub"])]), 0, STUB_M)
    nodes["boundary_1"].update(x=round(stub[-1][0], 3), y=round(stub[-1][1], 3))
    sobrecarey_pieces.append(add(j_top, "boundary_1", [[round(x, 3), round(y, 3)] for x, y in stub], template=kind, steps=STREETS["sobrecarey_stub"], minor=False))
    bonifacio.update(target=j_bonifacio, minor=True, shape=[bonifacio["shape"][0], bonifacio["shape"][1], here(new_nodes[j_bonifacio])])
    add(j_top, j_bonifacio, street_shape([points[i] for i in chain_of(ways, STREETS["magsaysay"])]), steps=STREETS["magsaysay"])
    add(j_bonifacio, j_northeast, street_shape([points[i] for i in chain_of(ways, STREETS["osmena"])][:-1]+[tuple(pe)]), steps=STREETS["osmena"])

    # Doctor Juan Gonzales Avenue and the two streets that carry it round to the highway.
    add(j_west, j_northwest, street_shape([points[i] for i in chain_of(ways, STREETS["west_loop"])][:-1]+[tuple(pn)]), steps=STREETS["west_loop"])

    # Dao Street on to Ebony Street, the inner link up to Acacia Street, and the loop back to the highway through the median opening.
    dao = roads["road0"]
    inner = nearest_on_shape([tuple(q) for q in dao["shape"]], points[DAO_INNER_NODE])[1]
    j_inner = junction("dao_inner", inner)
    j_ebony = junction("ebony", points[EBONY_NODE])
    dao.update(target=j_inner, shape=[dao["shape"][0], dao["shape"][1], here(new_nodes[j_inner])])
    kind = non_geometry(dao)
    add(j_inner, j_ebony, street_shape([inner]+[points[i] for i in chain_of(ways, STREETS["dao"])][1:]), template=kind, steps=STREETS["dao"], minor=False)
    stub = clip(street_shape([points[i] for i in chain_of(ways, STREETS["dao_stub"])]), 0, STUB_M)
    nodes["boundary_0"].update(x=round(stub[-1][0], 3), y=round(stub[-1][1], 3))
    add(j_ebony, "boundary_0", [[round(x, 3), round(y, 3)] for x, y in stub], template=kind, steps=STREETS["dao_stub"], minor=False)
    add(j_ebony, j_southeast, street_shape([points[i] for i in chain_of(ways, STREETS["southeast_loop"])][:-1]+[tuple(ps)]), steps=STREETS["southeast_loop"])
    # Acacia Street ends at the inner link: the link joins it at a corner the core's own Acacia line already passes through.
    acacia = roads["road6"]
    corner = points[ACACIA_CORNER_NODE]
    if nearest_on_shape([tuple(q) for q in acacia["shape"]], corner)[2] > 1.0:
        raise ValueError("The inner link no longer meets the core's Acacia line")
    acacia.update(target=j_inner, minor=True, shape=[[round(x, 3), round(y, 3)] for x, y in round_corners([tuple(acacia["shape"][0]), tuple(acacia["shape"][1]), corner, tuple(here(new_nodes[j_inner]))])])
    del nodes["boundary_6"], nodes["boundary_7"]

    # Names and numbers: junctions by distance from the study junction, new roads likewise (the core's ten roads keep theirs).
    junctions = sorted(new_nodes.values(), key=lambda node: (math.hypot(node["x"]-study["x"], node["y"]-study["y"]), node["id"]))
    rename = {node["id"]: f"{PREFIX}{number}" for number, node in enumerate(junctions, 2)}
    for node in junctions:
        node["id"] = rename[node["id"]]
    for road in [*roads.values(), *new_roads]:
        road["source"], road["target"] = rename.get(road["source"], road["source"]), rename.get(road["target"], road["target"])
    from_study = lambda point: math.hypot(point[0]-study["x"], point[1]-study["y"])
    new_roads.sort(key=lambda road: (min(from_study(road["shape"][0]), from_study(road["shape"][-1])), road["source"], road["target"]))
    for number, road in enumerate(new_roads, len(roads)):
        road["id"] = f"road{number}"
    payload["nodes"] = [study, neighbor, *junctions, *(nodes[key] for key in ("boundary_0", "boundary_1", "boundary_4", "boundary_5", "boundary_8", "boundary_9"))]
    payload["roads"] = [*roads.values(), *new_roads]

    # Rules the core carries, extended: the Sobrecarey ban on every lane of the street, no U-turn through a median opening at an entry, the Bonifacio kerb.
    lanes = lambda *items: [f"{road['id']}{direction}" for road in items for direction in "fr"]
    payload["lane_vehicle_restrictions"] = {lane: ["bus", "truck"] for lane in (*lanes(sobrecarey), *lanes(*sobrecarey_pieces))}
    payload["prohibited_turns"] = [*payload["prohibited_turns"], [f"{far_back['id']}f", f"{far_out['id']}f"], [f"{entry_east['id']}f", f"{exit_east['id']}f"]]
    payload["entry_kerb_vehicle_types"] = {f"{entry_east['id']}f": ["bus", "truck"], **payload["entry_kerb_vehicle_types"]}
    extend_northeast(payload, axis, a_northeast, end_along)
    payload["source"]["assumptions"] = [*CORE_ASSUMPTIONS, *grid_assumptions(points)]
    payload["source"]["supplement"] = {"file": SOURCES[1].name, "reason": "Magsaysay Street and the north ends of Sobrecarey, Bonifacio and Osmeña Streets lie beyond the first extract"}
    RoadNetwork(payload)
    return payload


def extend_northeast(payload: dict, axis: Axis, a_junction: float, end_along: float) -> None:
    """The core's pavement strips end 190 m past the neighbouring junction; carry them and the planted median to the new highway ends."""
    edge, start = CARRIAGEWAY_EDGE_M, axis.span+190.0
    box = lambda a0, a1, c0, c1: [axis.at(a0, c0), axis.at(a1, c0), axis.at(a1, c1), axis.at(a0, c1)]
    payload["site_features"] += [{"id": "strip_nw_northeast", "kind": "concrete", "shape": box(start, end_along, edge, 18.8)},
                                 {"id": "strip_se_northeast", "kind": "concrete", "shape": box(start, end_along, -18.5, -edge)},
                                 {"id": "service_lane_nw_northeast", "kind": "service_lane", "shape": box(start, end_along, 18.8, 21.9)},
                                 {"id": "service_lane_se_northeast", "kind": "service_lane", "shape": box(start, end_along, -21, -18.5)}]
    half = MEDIAN_WIDTH_M/2-.1
    payload["islands"].append({"id": "median_northeast_end", "shape": box(a_junction+OSMENA_JUNCTION_CLEARANCE_M, end_along, -half, half), "planted": True})


def grid_assumptions(points: dict) -> list[str]:
    return [
        "Side streets (D46) are provisional geometry from OpenStreetMap, painted and approved by the owner, not field-checked: Sobrecarey, Bonifacio and Osmeña Streets north to Magsaysay Street, "
        "Magsaysay Street, the west loop (Doctor Juan Gonzales Avenue and two unnamed streets), Dao Street on to Ebony Street, the loop back to the highway through the median opening, and the inner link to Acacia Street",
        f"Map bends under {LEG_SIMPLIFY_TOLERANCE_M:g} m are drawn straight, the first {JUNCTION_MOUTH_STRAIGHT_M:g} m at each end of a new street is drawn straight, and bends are circular arcs of {LOOP_BEND_RADIUS_M:g} m radius",
        "New streets are unnamed and one lane each way; they join the highway on its median centre line, where the carriageways bend to the junction inside its stop lines",
        "Every new junction uses first-come right-of-way, and Site B stays the only signal and RL candidate",
        "Pedestrians cross only at the study junction and the neighbouring junction, as before; people crossing the new streets are not modelled",
        "Generated traffic starts and ends only at the boundaries of the highway, Sobrecarey Street and Dao Street; side streets carry traffic only when route choice detours it (they cost three times their driving time)",
        "Sobrecarey and Dao Streets run 60 m past the grid to boundaries, so the counted traffic still enters them; the streets the owner did not paint beyond the grid are not modelled",
        "Acacia Street ends at the inner link, so the Acacia and Bonifacio boundaries of the earlier layout are gone; the earlier layout is kept as a listed revision",
        "The highway runs 80 m past the Osmeña junction; its pavement strips and median there are drawn only",
    ]


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=ROOT/"tagum_site_b.json")
    args = parser.parse_args()
    built = build_site_b_street_grid()
    args.output.write_text(json.dumps(built, indent=2, ensure_ascii=False)+"\n", encoding="utf-8")
    print(f"Wrote {args.output} ({RoadNetwork(built).fingerprint[:12]})")
