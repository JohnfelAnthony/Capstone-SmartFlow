"""Static conflict ranges are deliberately broad review evidence, not safety proof."""
import copy
import json
from pathlib import Path

from simulation.road_network import RoadNetwork
from tools.road_editor.geometry_checks import lane_overlap_ranges
from tools.site_b_conflict_regions import analyze
from tools.site_b_oriented_regions import analyze as oriented_analyze, cells, conflict_ranges
from simulation.footprints import rectangle, rectangles_overlap


def test_ranges_cover_crossing_segments_and_exclude_distant_roads():
    first = [(0, 0), (10, 0), (20, 0)]
    second = [(5, -10), (5, 10)]
    assert lane_overlap_ranges(first, 2, second, 2) == {"first": [0, 10], "second": [0, 20]}
    assert lane_overlap_ranges(first, 2, [(0, 20), (20, 20)], 2) is None


def corridor_network():
    """These reviews analysed the OSM corridor, which is kept as history now that Site B follows the overhead imagery."""
    return RoadNetwork(json.loads((Path(__file__).resolve().parents[1] / "data/networks/history/tagum_site_b_osm_corridor.json").read_text(encoding="utf-8")))


def test_site_b_ranges_cover_observed_opposing_lane_wait_without_mutating_input():
    payload = corridor_network().payload
    original = copy.deepcopy(payload)
    report = analyze(payload)
    assert payload == original
    conflict = next(item for item in report["conflicts"] if {item["first_lane"], item["second_lane"]} == {"road2f", "road3f"})
    ranges = {conflict["first_lane"]: conflict["first_range_m"], conflict["second_lane"]: conflict["second_range_m"]}
    assert ranges["road2f"][0] <= 4.3145 <= ranges["road2f"][1]
    assert ranges["road3f"][0] <= 145.0847 <= ranges["road3f"][1]
    assert report["network_fingerprint"] == corridor_network().fingerprint
    assert "no reservation" in report["status"]


def test_saved_report_names_the_current_unvalidated_network():
    report_path = Path(__file__).resolve().parents[1] / "docs/reports/site-b-conflict-regions-provisional.json"
    saved = json.loads(report_path.read_text(encoding="utf-8"))
    assert saved == analyze(corridor_network().payload)


def test_oriented_ranges_cover_overlapping_sampled_vehicle_bodies():
    first = cells([(0, 0), (20, 0)], 6, 3)
    second = cells([(10, -10), (10, 10)], 6, 3)
    result = conflict_ranges(first, second)
    assert result is not None
    for x in range(1, 20, 2):
        for y in range(-9, 10, 2):
            if rectangles_overlap(rectangle(x, 0, 0, 4, 2), rectangle(10, y, 1.5707963267948966, 4, 2)):
                assert any(low <= x <= high for low, high in result["first"])
                assert any(low <= y + 10 <= high for low, high in result["second"])


def test_oriented_site_b_ranges_cover_observed_opposing_lane_wait():
    payload = corridor_network().payload
    result = oriented_analyze(payload)
    conflict = next(item for item in result["conflicts"] if {item["first_lane"], item["second_lane"]} == {"road2f", "road3f"})
    ranges = {conflict["first_lane"]: conflict["first_ranges_m"], conflict["second_lane"]: conflict["second_ranges_m"]}
    assert any(low <= 4.3145 <= high for low, high in ranges["road2f"])
    assert any(low <= 145.0847 <= high for low, high in ranges["road3f"])
    assert result["network_fingerprint"] == corridor_network().fingerprint
