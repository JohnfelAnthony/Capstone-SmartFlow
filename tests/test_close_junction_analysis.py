"""The design report identifies storage hazards; it is not a safety validator."""
import copy
import json
import subprocess
import sys
from pathlib import Path

import pytest
from tools.close_junction_analysis import analyze
from tools.site_b_frontage import build_frontage_candidate


SITE = Path(__file__).resolve().parents[1] / "data/networks/history/tagum_site_b_osm_corridor.json"


def line_network(distance):
    nodes = [
        {"id": "w", "x": -150, "y": 0, "boundary": True},
        {"id": "j1", "x": 0, "y": 0},
        {"id": "j2", "x": distance, "y": 0},
        {"id": "e", "x": distance + 150, "y": 0, "boundary": True},
    ]
    roads = [
        {"id": road, "source": a, "target": b, "shape": [[x1, 0], [x2, 0]], "oneway": True}
        for road, a, b, x1, x2 in (("in", "w", "j1", -150, 0),
                                   ("link", "j1", "j2", 0, distance),
                                   ("out", "j2", "e", distance, distance + 150))
    ]
    return {"id": "line", "nodes": nodes, "roads": roads}


def test_site_b_groups_the_four_short_links_without_mutating_candidate():
    source = json.loads(SITE.read_text(encoding="utf-8"))
    candidate, _ = build_frontage_candidate(source)
    before = copy.deepcopy(candidate)
    report = analyze(candidate)
    assert candidate == before
    assert {item["road_id"] for item in report["short_links"]} == {"road0", "road1", "road6", "road7"}
    assert all(not item["parser_accepts_length"] for item in report["short_links"])
    assert {frozenset(group) for group in report["candidate_groups"]} == {
        frozenset({"tagum_site_b_j", "frontage_study_left", "frontage_study_right"}),
        frozenset({"1115349256", "frontage_neighbor_left", "frontage_neighbor_right"}),
    }


def test_a_parser_accepted_link_can_still_lack_storage_for_a_bus():
    report = analyze(line_network(31))
    link = report["short_links"][0]
    assert link["parser_accepts_length"]
    assert "bus" in link["classes_that_cannot_fit_even_if_empty"]
    assert report["candidate_groups"] == [["j1", "j2"]]
    assert analyze(line_network(60))["candidate_groups"] == []


def test_explicit_junction_clearance_changes_storage_and_invalid_values_are_refused():
    network = line_network(60)
    network["nodes"][1]["junction_clearance_m"] = 30
    network["nodes"][2]["junction_clearance_m"] = 30
    report = analyze(network)
    link = report["short_links"][0]
    assert link["current_usable_upper_bound_m"] == pytest.approx(0)
    assert not link["parser_accepts_length"]
    assert report["candidate_groups"] == [["j1", "j2"]]
    network["nodes"][1]["junction_clearance_m"] = True
    with pytest.raises(ValueError, match="Invalid junction clearance"):
        analyze(network)


def test_cli_refuses_existing_output_and_preserves_input(tmp_path):
    network, output = tmp_path / "network.json", tmp_path / "report.json"
    network.write_text(json.dumps(line_network(31)), encoding="utf-8")
    before = network.read_bytes()
    command = [sys.executable, "-m", "tools.close_junction_analysis", str(network), str(output)]
    result = subprocess.run(command, capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
    report_before = output.read_bytes()
    assert subprocess.run(command, capture_output=True).returncode != 0
    assert output.read_bytes() == report_before
    assert network.read_bytes() == before
