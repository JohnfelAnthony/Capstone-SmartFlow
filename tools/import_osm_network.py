"""Cache OSM roads for the native simulator; never requires SUMO or netedit."""
from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import Request, urlopen


def download_roads(bbox: str, output: Path) -> None:
    coordinates = [float(value) for value in bbox.split(",")]
    if len(coordinates) != 4:
        raise ValueError("bbox must be south,west,north,east")
    south, west, north, east = coordinates
    if not (-90 <= south < north <= 90 and -180 <= west < east <= 180):
        raise ValueError("Invalid geographic bounds")
    if north - south > 0.03 or east - west > 0.03:
        raise ValueError("Use a small study area (at most 0.03 degrees per side)")
    query = f'[out:json][timeout:35];way["highway"~"^(primary|secondary|tertiary|residential|unclassified|living_street|primary_link|secondary_link|tertiary_link)$"]({bbox});(._;>;);out body;'
    endpoint = "https://overpass-api.de/api/interpreter"
    request = Request(endpoint, data=urlencode({"data": query}).encode(), headers={"User-Agent": "SmartFlow-Capstone/2.0 (bounded road geometry import)"})
    with urlopen(request, timeout=50) as response:
        payload = json.load(response)
    if payload.get("remark") or not payload.get("elements"):
        raise RuntimeError(f"Incomplete OSM response: {payload.get('remark', 'no elements')}")
    payload["smartflow_source"] = {"provider": "OpenStreetMap", "license": "ODbL-1.0", "attribution": "© OpenStreetMap contributors", "url": "https://www.openstreetmap.org/copyright", "endpoint": endpoint, "bbox": coordinates, "downloaded_at": datetime.now(timezone.utc).isoformat(), "query": query}
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    print(f"Saved {len(payload['elements'])} OSM elements to {output}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--bbox", default="7.443,125.801,7.451,125.810")
    parser.add_argument("--output", type=Path, default=Path(__file__).resolve().parents[1] / "data/networks/tagum_osm.json")
    arguments = parser.parse_args()
    download_roads(arguments.bbox, arguments.output)
