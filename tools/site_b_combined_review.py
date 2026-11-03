"""Build a labelled, uninstalled Site B highway/frontage review proposal.

All geometry is provisional. This is not an engine-ready network, a traffic
safety certificate, an actual survey, or an alternative to field validation.
"""
from __future__ import annotations

import argparse
import json
import xml.etree.ElementTree as ET
from pathlib import Path

from simulation.road_network import RoadNetwork, length, sample, width_per_direction
from tools.site_b_centreline_proposal import build_candidate as separate_highway
from tools.site_b_frontage import build_frontage_candidate


def build_combined(payload, frontage_center_m=14.55):
    highway, highway_report = separate_highway(payload)
    combined, frontage_report = build_frontage_candidate(highway, frontage_center_m)
    try:
        RoadNetwork(combined)
        native = {"accepted": True, "reason": "Structure only; vehicle clearance is unverified."}
    except ValueError as exc:
        native = {"accepted": False, "reason": str(exc)}
    return combined, {"status": "unvalidated review only; do not install or use for research",
                      "highway": highway_report, "frontage": frontage_report, "native_structure": native,
                      "limits": ["Islands and their physical enforcement are not included.",
                                 "Dimensions, frontage turns and endpoint transitions require field review.",
                                 "The native engine cannot currently model the short links safely."]}


def overview(payload):
    roads = payload["roads"]
    pts = [point for road in roads for point in road["shape"]]
    xmin, xmax = min(p[0] for p in pts), max(p[0] for p in pts)
    ymin, ymax = min(p[1] for p in pts), max(p[1] for p in pts)
    pad = 45
    root = ET.Element("svg", {"xmlns": "http://www.w3.org/2000/svg", "viewBox": f"{xmin-pad} {-ymax-pad*2} {xmax-xmin+pad*2} {ymax-ymin+pad*3}", "role": "img"})
    ET.SubElement(root, "title").text = "Site B separated highway and frontage proposal: unvalidated review only"
    ET.SubElement(root, "rect", {"x": str(xmin-pad), "y": str(-ymax-pad*2), "width": str(xmax-xmin+pad*2), "height": str(ymax-ymin+pad*3), "fill": "#eff2ec"})
    has_islands = bool(payload.get("islands"))
    ET.SubElement(root, "text", {"x": str(xmin-pad+5), "y": str(-ymax-pad*1.5), "font-size": "10", "font-family": "sans-serif", "fill": "#7e241e"}).text = "UNVALIDATED SITE B — " + ("islands are provisional" if has_islands else "highway/frontage proposal; islands not shown")
    ET.SubElement(root, "text", {"x": str(xmin-pad+5), "y": str(-ymax-pad*1.12), "font-size": "9", "font-family": "sans-serif", "fill": "#203c39"}).text = "Dark: highway | Amber: frontage | Grey: side road | Green/red: island | N ↑"
    if has_islands:
        ET.SubElement(root, "text", {"x": str(xmin-pad+5), "y": str(-ymax-pad*.75), "font-size": "8", "font-family": "sans-serif", "fill": "#7e241e"}).text = "Historical corridor experiment — red islands may intersect pavement"
    for road in roads:
        frontage = road["id"].startswith("frontage_")
        highway = road.get("oneway") and "Highway" in road.get("name", "")
        color = "#ba7629" if frontage else "#374f58" if highway else "#8b9692"
        width = width_per_direction(road) * (1 if road.get("oneway") else 2)
        line = ET.SubElement(root, "polyline", {"points": " ".join(f"{x},{-y}" for x, y in road["shape"]),
                            "stroke": color, "stroke-width": str(width), "fill": "none", "stroke-linejoin": "round"})
        ET.SubElement(line, "title").text = f"{road['id']}: {road.get('name', '')}"
        if road.get("oneway"):
            shape = [tuple(point) for point in road["shape"]]
            total = length(shape)
            if total > 3:
                x, y, angle = sample(shape, total/2)
                import math
                ux, uy = math.cos(angle), math.sin(angle)
                points = [(x+ux*3, y+uy*3), (x-ux*2-uy*1.5, y-uy*2+ux*1.5), (x-ux*2+uy*1.5, y-uy*2-ux*1.5)]
                ET.SubElement(root, "polygon", {"points": " ".join(f"{a},{-b}" for a, b in points), "fill": "#fff8e8"})
    for island in payload.get("islands", []):
        element = ET.SubElement(root, "polygon", {"points": " ".join(f"{x},{-y}" for x, y in island["shape"]), "fill": "#d86c50" if island.get("review_pavement_conflicts") else "#83b46d", "stroke": "#eef2e6", "stroke-width": ".6", "opacity": ".9"})
        ET.SubElement(element, "title").text = f"{island['id']}: provisional; not an enforced obstacle"
    for node in payload["nodes"]:
        if node["id"] in ("tagum_site_b_j", "1115349256") or node["id"].startswith("frontage_study_") or node["id"].startswith("frontage_neighbor_"):
            ET.SubElement(root, "circle", {"cx": str(node["x"]), "cy": str(-node["y"]), "r": "3", "fill": "#e6b838", "stroke": "#453d22", "stroke-width": ".5"})
            if node["id"] in ("tagum_site_b_j", "1115349256"):
                label = "CitiHardware study junction" if node["id"] == "tagum_site_b_j" else "Neighbor: no signal"
                ET.SubElement(root, "text", {"x": str(node["x"]+7), "y": str(-node["y"]-7), "font-size": "9", "font-family": "sans-serif", "fill": "#111", "stroke": "#eff2ec", "stroke-width": "2", "paint-order": "stroke"}).text = label
    return ET.tostring(root, encoding="unicode")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("network", type=Path)
    parser.add_argument("candidate", type=Path)
    parser.add_argument("report", type=Path)
    parser.add_argument("svg", type=Path)
    parser.add_argument("--frontage-center-m", type=float, default=14.55, help="Provisional frontage centre offset in metres")
    args = parser.parse_args()
    paths = [args.network, args.candidate, args.report, args.svg]
    if len({path.resolve() for path in paths}) != len(paths) or any(path.exists() for path in paths[1:]):
        parser.error("Choose three distinct new outputs; existing files are preserved")
    payload = json.loads(args.network.read_text(encoding="utf-8"))
    candidate, report = build_combined(payload, args.frontage_center_m)
    outputs = [(args.candidate, json.dumps(candidate, indent=2)+"\n"), (args.report, json.dumps(report, indent=2)+"\n"), (args.svg, overview(candidate))]
    created = []
    try:
        for path, contents in outputs:
            with path.open("x", encoding="utf-8") as stream:
                created.append(path)
                stream.write(contents)
    except Exception:
        for path in created:
            path.unlink(missing_ok=True)
        raise


if __name__ == "__main__":
    main()
