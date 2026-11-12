"""Build the tracked peak-traffic count files (data/sites/<site>_peak_counts.json) from the local Field Observer copies.

The copies in data/generated/field_observations/ are git-ignored research evidence; the server reads only the files this writes.
Run again whenever a count changes:  .venv/Scripts/python.exe tools/build_peak_counts.py
"""
from __future__ import annotations

import csv
import hashlib
import json
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "data" / "generated" / "field_observations"
OUTPUT = ROOT / "data" / "sites"
CLASSES = ("car", "motorcycle", "tricycle", "bus", "truck")
ROAD_NAMES = {
    "tagum_site_a": {"north": "Dalisay Gante Road", "south": "Dalisay Gante Road", "west": "Capitol Circumferential Road", "east": "Capitol Circumferential Road"},
    "tagum_site_b": {"north": "Sobrecarey Street", "south": "Dao Street", "west": "Davao-Agusan National Highway", "east": "Davao-Agusan National Highway"},
}


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _zero() -> dict[str, int]:
    return {kind: 0 for kind in CLASSES}


def site_a() -> dict:
    path = SOURCE / "site_a" / "road-totals.csv"
    rows = list(csv.DictReader(path.open(encoding="utf-8", newline="")))
    roads = [row for row in rows if row["scope"] == "road"]
    recording = next(row for row in rows if row["scope"] == "recording")
    counts = {row["road"]: {kind: int(row[kind]) for kind in CLASSES} for row in roads}
    assert all(sum(counts[row["road"]].values()) == int(row["total"]) for row in roads), "a road's classes do not add up to its total"
    return {
        "network_id": "tagum_site_a", "label": "Peak traffic", "video": {"file": "IMG_2511.MOV", "seconds": float(roads[0]["video_duration_s"]),
                                                                          "take_id": roads[0]["take_id"], "source_sha256": roads[0]["source_sha256"]},
        "method": "manual", "reviewed": True, "count_direction": "leaving", "counts": counts, "assumed": {}, "relabelled": [],
        "pedestrians": int(recording["pedestrian_total"]), "road_names": ROAD_NAMES["tagum_site_a"],
        "built_from": [{"file": "data/generated/field_observations/site_a/road-totals.csv", "sha256": _sha256(path)}],
    }


def site_b() -> dict:
    proposals, run_path = SOURCE / "site_b" / "proposals.csv", SOURCE / "site_b" / "run.json"
    run = json.loads(run_path.read_text(encoding="utf-8"))
    lines = {"W": "west", "E": "east", "N": "north"}  # the video's counting lines on the simulated roads
    detected: dict[str, Counter] = {road: Counter() for road in lines.values()}
    for row in csv.DictReader(proposals.open(encoding="utf-8", newline="")):
        assert row["event_type"] == "vehicle_arrival", row["event_id"]
        detected[lines[row["approach_id"]]][row["detected_class"]] += 1
    counts = {road: {kind: classes.get(kind, 0) for kind in CLASSES} for road, classes in detected.items()}
    leftovers = {road: {kind: n for kind, n in classes.items() if kind not in CLASSES} for road, classes in detected.items()}
    assert not any(leftovers.values()), f"detector classes that are not vehicles: {leftovers}"
    # Buses and trucks are banned on Sobrecarey Street (D42) and the detector has no tricycle class: the owner counts them as tricycles.
    relabelled = counts["north"]["bus"] + counts["north"]["truck"]
    counts["north"]["tricycle"] += relabelled
    counts["north"]["bus"] = counts["north"]["truck"] = 0
    return {
        "network_id": "tagum_site_b", "label": "Peak traffic", "video": {"file": "IMG_2516.MOV", "seconds": 968.0,  # 16 min 8 s
                                                                          "take_id": run["take_id"], "source_sha256": run["source_sha256"]},
        "method": "automatic_detector", "reviewed": False, "count_direction": "arriving", "counts": counts,
        "detected": {road: dict(sorted(classes.items())) for road, classes in detected.items()},
        # Dao Street had no counting line; the owner gives it Sobrecarey's rate and mix.
        "assumed": {"south": dict(counts["north"])},
        "relabelled": [{"road": "north", "from": ["bus", "truck"], "to": "tricycle", "vehicles": relabelled}],
        "pedestrians": None, "road_names": ROAD_NAMES["tagum_site_b"],
        "built_from": [{"file": "data/generated/field_observations/site_b/proposals.csv", "sha256": _sha256(proposals)},
                       {"file": "data/generated/field_observations/site_b/run.json", "sha256": _sha256(run_path)}],
    }


def main() -> None:
    for counts in (site_a(), site_b()):
        target = OUTPUT / f"{counts['network_id']}_peak_counts.json"
        target.write_text(json.dumps({"schema": "smartflow_peak_counts", "version": 1, **counts}, indent=2) + "\n", encoding="utf-8")
        print(f"wrote {target.relative_to(ROOT)}: {sum(sum(classes.values()) for classes in counts['counts'].values())} counted vehicles")


if __name__ == "__main__":
    main()
