"""Cache OSM roads for the native simulator; never requires SUMO or netedit."""
from __future__ import annotations

import argparse
import json
import math
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import Request, urlopen

# Trunk roads carry the national highway at the Site B study junction.
ROAD_CLASSES = ("trunk", "trunk_link", "primary", "primary_link", "secondary", "secondary_link", "tertiary",
                "tertiary_link", "residential", "unclassified", "living_street")
METRES_PER_DEGREE = 111320


def _check_bbox(south: float, west: float, north: float, east: float) -> None:
    if not (-90 <= south < north <= 90 and -180 <= west < east <= 180):
        raise ValueError("Invalid geographic bounds")
    if north - south > 0.03 or east - west > 0.03:
        raise ValueError("Use a small study area (at most 0.03 degrees per side)")


def overpass_query(bbox: str) -> str:
    return f'[out:json][timeout:35];way["highway"~"^({"|".join(ROAD_CLASSES)})$"]({bbox});(._;>;);out body;'


def site_bbox(latitude: float, longitude: float, radius_m: float = 450.0) -> str:
    """A square box of radius_m around a study site, as south,west,north,east."""
    half_lat = radius_m / METRES_PER_DEGREE
    half_lon = radius_m / (METRES_PER_DEGREE * math.cos(math.radians(latitude)))
    south, west, north, east = latitude - half_lat, longitude - half_lon, latitude + half_lat, longitude + half_lon
    _check_bbox(south, west, north, east)
    return ",".join(f"{value:.6f}" for value in (south, west, north, east))


def download_roads(bbox: str, output: Path) -> None:
    coordinates = [float(value) for value in bbox.split(",")]
    if len(coordinates) != 4:
        raise ValueError("bbox must be south,west,north,east")
    _check_bbox(*coordinates)
    query = overpass_query(bbox)
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
    area = parser.add_mutually_exclusive_group(required=True)
    area.add_argument("--bbox", help="south,west,north,east")
    area.add_argument("--site", help="LAT,LON of a study junction; fetches a box of --radius-m around it")
    parser.add_argument("--radius-m", type=float, default=450.0)
    parser.add_argument("--output", type=Path, required=True)
    arguments = parser.parse_args()
    if arguments.site:
        latitude, longitude = (float(value) for value in arguments.site.split(","))
        bbox = site_bbox(latitude, longitude, arguments.radius_m)
    else:
        bbox = arguments.bbox
    download_roads(bbox, arguments.output)
