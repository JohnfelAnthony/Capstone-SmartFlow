"""Provisional photo-based layout proposal; not a replacement traffic network.

Coordinates are native metres. Widths are estimates, not survey measurements.
"""
from __future__ import annotations

import math
from html import escape


def site_b_layout(network: dict) -> dict:
    highway = [road for road in network["roads"] if road.get("oneway") and "Highway" in road.get("name", "")]
    if not highway:
        raise ValueError("Site B proposal needs cached highway alignment")
    road = max(highway, key=lambda road: sum(math.dist(a, b) for a, b in zip(road["shape"], road["shape"][1:])))
    a, b = road["shape"][0], road["shape"][-1]
    dx, dy = b[0]-a[0], b[1]-a[1]
    if dy < 0:
        dx, dy = -dx, -dy
    size = math.hypot(dx, dy)
    if size < 1e-6:
        raise ValueError("Site B proposal needs a nonzero highway direction")
    ux, uy = dx/size, dy/size
    junction = next((node for node in network.get("nodes", []) if node.get("id") == "tagum_site_b_j"), None)
    if junction is None:
        raise ValueError("Site B proposal needs the CitiHardware study junction")
    origin_x, origin_y = junction["x"], junction["y"]

    def point(s, t):
        return [round(origin_x+s*ux-t*uy, 3), round(origin_y+s*uy+t*ux, 3)]

    def rectangle(start, end, low, high):
        return [point(start, low), point(end, low), point(end, high), point(start, high)]

    islands = []
    for side in (-1, 1):
        start, end = sorted((side*35, side*250))
        islands.append({"id": f"central-{side}", "planted": True, "shape": rectangle(start, end, -1, 1)})
        # Deliberately offset openings: imagery shows staggered access, not a common cross.
        start, end = sorted((side*50, side*250))
        for edge in (-1, 1):
            low, high = sorted((edge*10.9, edge*12.9))
            islands.append({"id": f"outer-{side}-{edge}", "planted": True, "shape": rectangle(start, end, low, high)})
    corridors = []
    for side in (-1, 1):
        for role, low, high in (("main", 1, 10.9), ("frontage", 12.9, 16.2)):
            lo, hi = sorted((side*low, side*high))
            corridors.append({"id": f"{role}-{side}", "role": role, "shape": rectangle(-250, 250, lo, hi),
                              "direction": [point(side*230, side*(low+high)/2), point(-side*230, side*(low+high)/2)]})
    return {"status": "layout proposal only; connectivity and physical clearance unaccepted", "islands": islands,
            "corridors": corridors, "estimates_m": {"central_median": 2, "outer_island": 2, "main_carriageway": 9.9,
            "frontage": 3.3, "central_opening": 70, "outer_opening": 100},
            "basis": "Owner-confirmed Site B screenshots supplied November 2, 2026; cached highway axis. Dimensions estimated visually; require survey."}


def proposal_svg(proposal: dict, junction: dict) -> str:
    """Render a labelled review drawing from the same provisional proposal."""
    shapes = proposal["corridors"] + proposal["islands"]
    all_points = [point for shape in shapes for point in shape["shape"]]
    min_x, max_x = min(p[0] for p in all_points), max(p[0] for p in all_points)
    min_y, max_y = min(p[1] for p in all_points), max(p[1] for p in all_points)
    scale = min(520 / max(max_x - min_x, 1), 460 / max(max_y - min_y, 1))
    def project(point):
        return (300 + (point[0] - (min_x + max_x) / 2) * scale,
                300 - (point[1] - (min_y + max_y) / 2) * scale)
    def points(shape):
        return " ".join(f"{x:.2f},{y:.2f}" for x, y in map(project, shape))
    out = ['<svg xmlns="http://www.w3.org/2000/svg" width="900" height="900" viewBox="0 0 600 600">',
           '<rect width="600" height="600" fill="#f0f2ef"/>',
           '<defs><marker id="arrow" markerWidth="7" markerHeight="7" refX="6" refY="3.5" orient="auto"><path d="M0,0 L7,3.5 L0,7 Z" fill="#fff"/></marker></defs>']
    for corridor in proposal["corridors"]:
        out.append(f'<polygon points="{points(corridor["shape"])}" fill="#555" stroke="#aaa"/>')
    for island in proposal["islands"]:
        out.append(f'<polygon points="{points(island["shape"])}" fill="#588855" stroke="#e5d7b1"/>')
    for index, corridor in enumerate(proposal["corridors"]):
        start, end = map(project, corridor["direction"])
        out.append(f'<path d="M {start[0]:.2f},{start[1]:.2f} L {end[0]:.2f},{end[1]:.2f}" stroke="white" stroke-dasharray="5 5" marker-end="url(#arrow)"/>')
        mid_x, mid_y = (start[0]+end[0])/2, (start[1]+end[1])/2
        out.append(f'<text x="{mid_x+4:.2f}" y="{mid_y+index*9-18:.2f}" font-size="9" fill="#111">{index+1}</text>')
        out.append(f'<text x="20" y="{75+index*14}" font-size="9" font-family="sans-serif">{index+1}: {escape(corridor["id"])}</text>')
    x, y = project([junction["x"], junction["y"]])
    out.extend([f'<circle cx="{x:.2f}" cy="{y:.2f}" r="4" fill="#f9a825"/>',
                f'<text x="{x+7:.2f}" y="{y-7:.2f}" font-size="9">CitiHardware study junction</text>',
                '<g font-family="sans-serif" fill="#111"><text x="15" y="24" font-size="15">Site B: provisional corridor and island proposal</text>',
                '<text x="15" y="42" font-size="10">Green: proposed islands; grey: main and frontage corridors</text>',
                '<text x="15" y="562" font-size="10">Estimated dimensions; side-street connections are not reconstructed.</text>',
                '<text x="15" y="580" font-size="10">Review only: this is not the active simulation network.</text></g></svg>'])
    return "".join(out)


if __name__ == "__main__":
    import argparse
    import json
    from pathlib import Path
    parser = argparse.ArgumentParser(description="Write a provisional Site B layout and labelled SVG without overwriting evidence")
    parser.add_argument("--network", type=Path, required=True)
    parser.add_argument("--json-output", type=Path, required=True)
    parser.add_argument("--svg-output", type=Path, required=True)
    args = parser.parse_args()
    network = json.loads(args.network.read_text(encoding="utf-8"))
    proposal = site_b_layout(network)
    junction = next(item for item in network["nodes"] if item["id"] == "tagum_site_b_j")
    # Refuse existing output: older layout evidence remains intact.
    if args.json_output.exists() or args.svg_output.exists():
        parser.error("Choose new output paths; existing review evidence is never replaced")
    with args.json_output.open("x", encoding="utf-8") as output:
        output.write(json.dumps(proposal, indent=2))
    try:
        with args.svg_output.open("x", encoding="utf-8") as output:
            output.write(proposal_svg(proposal, junction))
    except Exception:
        args.json_output.unlink(missing_ok=True)
        raise
