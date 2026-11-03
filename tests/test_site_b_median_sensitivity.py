import json
from pathlib import Path

from simulation.road_network import RoadNetwork
from tools.site_b_measured_layout import build_measured_site_b
from tools.site_b_median_sensitivity import candidate_from_corridor, comparison_svg


def test_candidate_only_changes_two_islands_and_keeps_baseline_reproducible():
    corridor = json.loads(Path("data/networks/history/tagum_site_b_osm_corridor.json").read_text(encoding="utf-8"))
    original = build_measured_site_b(corridor)
    fingerprint = RoadNetwork(original).fingerprint
    candidate = candidate_from_corridor(corridor)
    assert RoadNetwork(build_measured_site_b(corridor)).fingerprint == fingerprint
    before = {item["id"]: item for item in original["islands"]}
    after = {item["id"]: item for item in candidate["islands"]}
    assert {key for key in before if before[key] != after[key]} == {"median_between", "median_ne"}
    assert original["roads"] == candidate["roads"]
    svg = comparison_svg(original, candidate)
    assert "UNINSTALLED TRIAL" in svg and "median_between +4m" in svg and "median_ne +8m" in svg
