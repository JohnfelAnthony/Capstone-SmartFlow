"""Create an uninstalled review-only Site B median sensitivity candidate."""
from __future__ import annotations

import argparse
import json
import xml.etree.ElementTree as ET
from pathlib import Path

from simulation.road_network import RoadNetwork
from tools.site_b_island_sweep_review import review
from tools.site_b_measured_layout import _islands, build_measured_site_b


def candidate_from_corridor(corridor):
    def trial_islands(span, rounded):
        def adjusted(a0, a1, c0, c1):
            if abs(a0 - 20.6) < .001:
                a0 += 4
            if abs(a0 - (span + 27)) < .001:
                a0 += 8
            return rounded(a0, a1, c0, c1)
        return _islands(span, adjusted)
    candidate = build_measured_site_b(corridor, island_builder=trial_islands)
    candidate["source"]["assumptions"] = [*candidate["source"]["assumptions"],
        "Uninstalled sensitivity candidate: median starts shifted 4 m and 8 m; dimensions not field verified"]
    return candidate


def comparison_svg(original, candidate):
    changed = {"median_between", "median_ne"}
    islands = {item["id"]: item for item in original["islands"]}
    replacements = {item["id"]: item for item in candidate["islands"]}
    points = [point for island in original["islands"] for point in island["shape"]]
    xmin, xmax = min(p[0] for p in points), max(p[0] for p in points)
    ymin, ymax = min(p[1] for p in points), max(p[1] for p in points)
    root = ET.Element("svg", {"xmlns": "http://www.w3.org/2000/svg", "viewBox": f"{xmin-30} {-ymax-50} {xmax-xmin+60} {ymax-ymin+90}"})
    ET.SubElement(root, "title").text = "Site B median sensitivity comparison: uninstalled, unverified"
    ET.SubElement(root, "rect", {"x": str(xmin-30), "y": str(-ymax-50), "width": str(xmax-xmin+60), "height": str(ymax-ymin+90), "fill": "#eef2eb"})
    for road in original["roads"]:
        ET.SubElement(root, "polyline", {"points": " ".join(f"{x},{-y}" for x, y in road["shape"]), "stroke": "#7c8786", "stroke-width": "1.5", "fill": "none"})
    for island in original["islands"]:
        ET.SubElement(root, "polygon", {"points": " ".join(f"{x},{-y}" for x, y in island["shape"]), "fill": "#9ab08e" if island["id"] not in changed else "#d36159", "opacity": ".75"})
    for name in sorted(changed):
        island = replacements[name]
        ET.SubElement(root, "polygon", {"points": " ".join(f"{x},{-y}" for x, y in island["shape"]), "fill": "none", "stroke": "#135bb0", "stroke-width": "1.4"})
        point = island["shape"][-1]
        ET.SubElement(root, "text", {"x": str(point[0]+3), "y": str(-point[1]-3), "font-size": "5", "fill": "#123d75"}).text = name + (" +4m" if name == "median_between" else " +8m")
    for node in original["nodes"]:
        if node["id"] in {"tagum_site_b_j", "1115349256"}:
            ET.SubElement(root, "circle", {"cx": str(node["x"]), "cy": str(-node["y"]), "r": "2", "fill": "#262626"})
            ET.SubElement(root, "text", {"x": str(node["x"]+3), "y": str(-node["y"]+6), "font-size": "5"}).text = "CitiHardware" if node["id"] == "tagum_site_b_j" else "Neighbor (no signal)"
    ET.SubElement(root, "text", {"x": str(xmin-25), "y": str(-ymax-32), "font-size": "7", "fill": "#8c2020"}).text = "UNINSTALLED TRIAL — not surveyed or safety validated"
    ET.SubElement(root, "text", {"x": str(xmin-25), "y": str(-ymax-20), "font-size": "6"}).text = "Red: current median | Blue outline: shorter trial median | Grey: road centerlines"
    return ET.tostring(root, encoding="unicode")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("corridor", type=Path)
    parser.add_argument("output_prefix", type=Path)
    args = parser.parse_args()
    files = [Path(str(args.output_prefix) + suffix) for suffix in ("-candidate.json", "-review.json", "-comparison.svg")]
    if any(path.exists() for path in files):
        parser.error("Output already exists; choose a new prefix")
    corridor = json.loads(args.corridor.read_text(encoding="utf-8"))
    original, candidate = build_measured_site_b(corridor), candidate_from_corridor(corridor)
    report = {"status": "uninstalled sensitivity trial; not survey or clearance acceptance", "original": review(RoadNetwork(original)), "candidate": review(RoadNetwork(candidate))}
    for path, content in zip(files, (json.dumps(candidate, indent=2), json.dumps(report, indent=2), comparison_svg(original, candidate))):
        with path.open("x", encoding="utf-8") as stream:
            stream.write(content + "\n")
    print("Wrote uninstalled review files:", *(str(path) for path in files))


if __name__ == "__main__":
    main()
