"""Rebuild Site B from the cached OSM corridor using sizes measured on the owner's overhead imagery.

All sizes are estimates read against the image scale bar (252 px = 50 m); none is surveyed. Coordinates below are
metres (along, across) from the study junction: along runs north-east toward the neighboring junction, across runs
north-west. Features near the neighboring junction are measured from it, because the OSM spacing (170.4 m) and the
image spacing (166 m) differ slightly.
"""
from __future__ import annotations

import argparse
import copy
import json
import math
from pathlib import Path

from simulation.road_network import RoadNetwork

CARRIAGEWAY_WIDTH_M = 9.2
MEDIAN_WIDTH_M = 1.9
MEDIAN_KERB_GAP_M = .1
CARRIAGEWAY_CENTRE_M = MEDIAN_WIDTH_M/2 + CARRIAGEWAY_WIDTH_M/2
CARRIAGEWAY_EDGE_M = MEDIAN_WIDTH_M/2 + CARRIAGEWAY_WIDTH_M
# Road centre lines join at the junction node, so they bend to it inside the setback, out of sight.
BEND_FROM_NODE_M = 14.0
STUDY_SETBACK_M, NEIGHBOR_SETBACK_M = 22.0, 29.5
SOUTHWEST_END_M, NORTHEAST_END_M = 250.0, 190.0
STUDY, NEIGHBOR = "tagum_site_b_j", "1115349256"
SIDE_ROAD_WIDTHS_M = {"road0": 3.45, "road1": 6.85, "road6": 4.65, "road7": 5.0}
NW_ISLAND, SE_ISLAND = (10.6, 14.9), (-14.2, -10.6)
STREET_LIGHT_SPACING_M, STREET_LIGHT_ARM_M = 40.0, 3.0
DAO_FAR_END, ACACIA_FAR_END = (.8, -246.4), (165.8, -245.0)
ASSUMPTIONS = [
    "Provisional OSM corridor, not field validated",
    "Carriageways, median, islands, openings and stop lines are estimated from the owner's overhead imagery (scale bar; imagery dated 2025-05-03) and Street View (June-July 2026); check every size in the field",
    "Service lanes, concrete strips, aprons, sheds, street lights and buildings are drawn only: no simulated traffic uses them",
    "The median and islands are not engine obstacles; lanes and turn paths are placed around them and acceptance counts any vehicle contact",
    "Owner-confirmed access rule (2026-11-07): buses and trucks are prohibited on Sobrecarey Street in both directions; this is local knowledge, not independently verified signage or a cited ordinance",
    "Bonifacio stays open to buses and trucks. The simulation keeps them in the kerb lane on the highway approach from the northeast so their tail clears the median during the turn. Confirm real lane use in the field",
    "No U-turns are simulated at the mid-block median gaps, and their zebras and stop lines are paint only",
    "The yellow box markings in the 2025 imagery are not drawn: the 2026 Street View shows no yellow, pending confirmation",
    "Beyond the imagery (more than about 175 m southwest of the study junction) the same layout is assumed",
    "Dao and Acacia continue straight past the imagery, leaving out their OSM far bends, so their far alignment and end points are approximate",
    "Only CitiHardware is a candidate signal/RL junction",
    "Neighboring junction uses first-come no-signal control",
    "Synthetic demand; no traffic effectiveness claimed",
]


def build_measured_site_b(corridor: dict, *, island_builder=None) -> dict:
    payload = copy.deepcopy(corridor)
    nodes = {node["id"]: node for node in payload["nodes"]}
    study, neighbor = nodes[STUDY], nodes[NEIGHBOR]
    span = math.hypot(neighbor["x"]-study["x"], neighbor["y"]-study["y"])
    ux, uy = (neighbor["x"]-study["x"])/span, (neighbor["y"]-study["y"])/span

    def at(along: float, across: float) -> list[float]:
        return [round(study["x"]+along*ux-across*uy, 3), round(study["y"]+along*uy+across*ux, 3)]

    def box(a0: float, a1: float, c0: float, c1: float) -> list[list[float]]:
        return [at(a0, c0), at(a1, c0), at(a1, c1), at(a0, c1)]

    def rounded(a0: float, a1: float, c0: float, c1: float) -> list[list[float]]:
        """A raised island with rounded noses."""
        middle, radius = (c0+c1)/2, min((c1-c0)/2, (a1-a0)/2)
        half = (c1-c0)/2
        steps = [i*math.pi/8 for i in range(-4, 5)]
        cap_end = [at(a1-radius+radius*math.cos(t), middle+half*math.sin(t)) for t in steps]
        cap_start = [at(a0+radius-radius*math.cos(t), middle-half*math.sin(t)) for t in steps]
        return cap_end+cap_start

    centre, edge = CARRIAGEWAY_CENTRE_M, CARRIAGEWAY_EDGE_M
    study_point, neighbor_point = at(0, 0), at(span, 0)
    study["x"], study["y"] = study_point
    neighbor["x"], neighbor["y"] = neighbor_point
    ends = {"boundary_4": at(-SOUTHWEST_END_M, centre), "boundary_5": at(-SOUTHWEST_END_M, -centre),
            "boundary_8": at(span+NORTHEAST_END_M, -centre), "boundary_9": at(span+NORTHEAST_END_M, centre),
            "boundary_0": at(*DAO_FAR_END), "boundary_6": at(*ACACIA_FAR_END)}
    for node_id, point in ends.items():
        nodes[node_id]["x"], nodes[node_id]["y"] = point
    study.update(junction_clearance_m=STUDY_SETBACK_M, pedestrian_crossing=[at(18.5, edge), at(18.5, -edge)])
    neighbor.update(junction_clearance_m=NEIGHBOR_SETBACK_M, pedestrian_crossing=[at(span-25.3, edge), at(span-25.3, -edge)])

    bend = BEND_FROM_NODE_M
    highway_shapes = {
        "road2": [neighbor_point, at(span-bend, centre), at(bend, centre), study_point],
        "road3": [study_point, at(bend, -centre), at(span-bend, -centre), neighbor_point],
        "road4": [study_point, at(-bend, centre), ends["boundary_4"]],
        "road5": [ends["boundary_5"], at(-bend, -centre), study_point],
        "road8": [neighbor_point, at(span+bend, -centre), ends["boundary_8"]],
        "road9": [ends["boundary_9"], at(span+bend, centre), neighbor_point],
    }
    for road in payload["roads"]:
        if road["id"] in highway_shapes:
            road.update(shape=highway_shapes[road["id"]], width_per_direction_m=CARRIAGEWAY_WIDTH_M)
        else:
            road["width_per_direction_m"] = SIDE_ROAD_WIDTHS_M[road["id"]]
        if road["id"] == "road1":
            # Sobrecarey is straight on the imagery, and its OSM vertices fit one line within about a metre.
            # Its centre line meets the highway edge at the box centre, not at the merged OSM node.
            road["shape"] = [study_point, at(.25, 10.2), road["shape"][-1]]
        elif road["id"] == "road0":
            # Straight past any queue, as on the imagery. A far bend is left out: opposing bodies pivot into each other at one.
            road["shape"] = [study_point, road["shape"][1], ends["boundary_0"]]
        elif road["id"] == "road6":
            road["shape"] = [neighbor_point, road["shape"][1], ends["boundary_6"]]
        elif road["id"] == "road7":
            # Bonifacio's OSM vertices also fit one line, which passes just beside the node.
            road["shape"] = [neighbor_point, at(span+16, 10), road["shape"][-1]]

    # The two far ends have separate entry and exit nodes, so the parser would otherwise allow a U-turn through the opening.
    payload["prohibited_turns"] = [["road5f", "road4f"], ["road9f", "road8f"]]
    payload["lane_vehicle_restrictions"] = {lane: ["bus", "truck"] for lane in ("road1f", "road1r")}
    payload["entry_kerb_vehicle_types"] = {"road9f": ["bus", "truck"]}
    payload["islands"] = (island_builder or _islands)(span, rounded)
    payload["site_features"] = _site_features(span, at, box)
    payload["source"]["assumptions"] = ASSUMPTIONS
    RoadNetwork(payload)
    return payload


def _islands(span: float, rounded) -> list[dict]:
    half = MEDIAN_WIDTH_M/2-MEDIAN_KERB_GAP_M
    medians = {"sw_far": (-SOUTHWEST_END_M, -87), "gap_tip": (-76, -73.4), "sw_near": (-68.6, -23.2), "study_sw_tip": (-19.8, -17.2),
               "study_ne_tip": (14.3, 16.9), "between": (20.6, span-27.4), "neighbor_sw_tip": (span-23.4, span-21.2),
               "neighbor_ne_tip": (span+21.7, span+24), "ne": (span+27, span+163.7)}
    planted_sides = {"nw_far": (NW_ISLAND, -SOUTHWEST_END_M, -112), "nw_strip": ((13.9, 14.9), -112, -40), "nw_between": (NW_ISLAND, 43, span-19),
                     "nw_beyond_1": (NW_ISLAND, span+46, span+92), "nw_beyond_2": (NW_ISLAND, span+102, span+167.5),
                     "se_far": (SE_ISLAND, -SOUTHWEST_END_M, -93), "se_near": (SE_ISLAND, -57, -15), "se_after_dao": (SE_ISLAND, 14, 32),
                     "se_before_acacia": (SE_ISLAND, span-49, span-20), "se_beyond_1": (SE_ISLAND, span+22, span+116), "se_beyond_2": (SE_ISLAND, span+134, span+176)}
    islands = [{"id": f"median_{name}", "shape": rounded(a0, a1, -half, half), "planted": True} for name, (a0, a1) in medians.items()]
    islands += [{"id": f"side_{name}", "shape": rounded(a0, a1, *band), "planted": True} for name, (band, a0, a1) in planted_sides.items()]
    islands.append({"id": "side_nw_paved_nose", "shape": rounded(32, 43, *NW_ISLAND), "planted": False})
    return islands


def _site_features(span: float, at, box) -> list[dict]:
    edge = CARRIAGEWAY_EDGE_M
    west, east = -SOUTHWEST_END_M, span+NORTHEAST_END_M
    features = [
        {"id": "strip_nw", "kind": "concrete", "shape": box(west, east, edge, 18.8)},
        {"id": "strip_se", "kind": "concrete", "shape": box(west, east, -18.5, -edge)},
        {"id": "service_lane_nw", "kind": "service_lane", "shape": box(west, east, 18.8, 21.9)},
        {"id": "service_lane_se", "kind": "service_lane", "shape": box(west, east, -21, -18.5)},
        {"id": "driveway_se", "kind": "service_lane", "shape": box(-93, -75, -14.2, -edge)},
        {"id": "jollibee_lot", "kind": "plaza", "shape": [at(-93.8, 66.5), at(-80.4, 77.4), at(-22.8, 22.8), at(-62.5, 22.8)]},
        {"id": "citi_lane", "kind": "parking", "shape": [at(-22, 22), at(-1, 22), at(-45, 110), at(-61, 110)]},
        {"id": "citi_hardware", "kind": "building", "label": "Citi Hardware", "tone": "light", "shape": [at(14.9, 35.2), at(49.6, 63.5), at(11.7, 110), at(-23, 81.7)]},
        {"id": "jollibee", "kind": "building", "label": "Jollibee", "tone": "green", "shape": [at(-65, 59.5), at(-51, 42.7), at(-60.5, 34.7), at(-75.4, 49.6)]},
        {"id": "pavement_study", "kind": "junction_pavement", "junction": STUDY, "zebra_lanes": ["road2f", "road3f", "road4f", "road5f"], "shape": [at(*point) for point in (
            (-21.5, -edge), (-3.6, -edge), (-3.6, -23), (3.6, -23), (3.6, -edge), (21.5, -edge), (21.5, edge), (32, edge), (32, 14.9), (26, 17.2),
            (9.7, 17.2), (5.6, 23), (-2.1, 17.2), (-13, 17.2), (-13, 14.9), (-40, 14.9), (-40, edge), (-21.5, edge))]},
        {"id": "pavement_neighbor", "kind": "junction_pavement", "junction": NEIGHBOR, "zebra_lanes": ["road2f", "road3f", "road8f", "road9f"], "shape": [at(span+a, c) for a, c in (
            (-28.4, -edge), (-13.4, -edge), (-13.4, -28), (-3.8, -28), (-3.8, -edge), (28.4, -edge), (28.4, edge), (34.6, edge), (34.6, 17.4),
            (27, 17.4), (21.3, 21), (12, 17.4), (12, 14.9), (-19, 14.9), (-19, edge), (-28.4, edge))]},
    ]
    sheds = [(-94.9, -90.3, 13.6, 14.7), (-74, -69, 13.6, 14.7), (-52, -46.4, 13.6, 14.7),
             (48.6, 56.2, -14.9, -12.6), (63.5, 70.4, -14.9, -12.6), (78, 85, -14.9, -12.6), (92.3, 99.5, -14.9, -12.6)]
    features += [{"id": f"shed_{index}", "kind": "shed", "shape": box(*shed)} for index, shed in enumerate(sheds, 1)]
    dashes = [((-13, 14.2), (32, 14.2)), ((-13, 16.9), (26, 16.9)), ((-6, -13.9), (12.2, -13.9)), ((-6, -16.2), (12.2, -16.2)),
              ((span+12, 15.2), (span+34.6, 15.2)), ((span+12, 17.2), (span+34.6, 17.2)), ((span-13.4, -12.9), (span-3.8, -12.9)), ((span-13.4, -15.5), (span-3.8, -15.5))]
    features += [{"id": f"mouth_dashes_{index}", "kind": "dashes", "shape": [at(*a), at(*b)]} for index, (a, b) in enumerate(dashes, 1)]
    half = MEDIAN_WIDTH_M/2
    for name, a0, a1, stop_nw, stop_se in (("sw", -73, -69, -67.8, -74.9), ("ne", span+165, span+169, span+170.2, span+163.8)):
        for side, c0, c1 in (("nw", half, edge), ("se", -edge, -half)):
            stripes = int(c1-c0)
            features += [{"id": f"zebra_{name}_{side}_{index}", "kind": "marking", "shape": box(a0, a1, c0+.25+index, c0+.75+index)} for index in range(stripes)]
        features.append({"id": f"stop_{name}_nw", "kind": "marking", "shape": box(stop_nw-.2, stop_nw+.2, half, edge)})
        features.append({"id": f"stop_{name}_se", "kind": "marking", "shape": box(stop_se-.2, stop_se+.2, -edge, -half)})
    lit = ((-SOUTHWEST_END_M, -87), (-68.6, -23.2), (20.6, span-27.4), (span+27, span+163.7))
    positions = [start+10+index*STREET_LIGHT_SPACING_M for start, end in lit for index in range(int((end-start-20)//STREET_LIGHT_SPACING_M)+1)]
    features += [{"id": f"light_{index}", "kind": "street_light", "shape": [at(a, -STREET_LIGHT_ARM_M), at(a, 0), at(a, STREET_LIGHT_ARM_M)]} for index, a in enumerate(positions, 1)]
    return features


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, default=Path("data/networks/history/tagum_site_b_osm_corridor.json"))
    parser.add_argument("--output", type=Path, default=Path("data/networks/tagum_site_b.json"))
    args = parser.parse_args()
    built = build_measured_site_b(json.loads(args.source.read_text(encoding="utf-8")))
    args.output.write_text(json.dumps(built, indent=2, ensure_ascii=False)+"\n", encoding="utf-8")
    print(f"Wrote {args.output} ({RoadNetwork(built).fingerprint[:12]})")
