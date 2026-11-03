"""Synthetic topology checks for an uninstalled image-based Site B proposal."""
import copy
import json
import subprocess
import sys
from pathlib import Path

import pytest

from simulation.road_network import RoadNetwork
from tools.site_b_frontage import build_frontage_candidate

SITE = Path(__file__).resolve().parents[1] / "data/networks/history/tagum_site_b_osm_corridor.json"


def test_frontage_candidate_splits_side_streets_and_matches_highway_direction():
    original = json.loads(SITE.read_text(encoding="utf-8"))
    before = copy.deepcopy(original)
    candidate, report = build_frontage_candidate(original)
    assert original == before
    assert candidate == build_frontage_candidate(original)[0]
    assert "do not install" in report["status"]
    assert len(candidate["roads"]) == len(original["roads"]) + 10
    for item in report["crossings"]:
        node = next(node for node in candidate["nodes"] if node["id"] == item["id"])
        assert node["default_control_mode"] == "first_come"
        touching = [road for road in candidate["roads"] if node["id"] in (road["source"], road["target"])]
        assert len(touching) == 4
        assert sum(1 for road in touching if road["target"] == node["id"] or not road["oneway"]) == 3
        assert item["shortfall_m"] > 0
    directions = {item["side"]: item for item in report["directions"]}
    assert directions[-1]["adjacent_highway"] == "road5" and directions[-1]["axis_sign"] == 1
    assert directions[1]["adjacent_highway"] == "road4" and directions[1]["axis_sign"] == -1
    for side, suffix in ((-1, "right"), (1, "left")):
        highway = next(road for road in original["roads"] if road["id"] == directions[side]["adjacent_highway"])
        highway_vector = [highway["shape"][-1][i]-highway["shape"][0][i] for i in (0, 1)]
        for segment in (road for road in candidate["roads"] if road["id"].startswith(f"frontage_{suffix}_")):
            vector = [segment["shape"][-1][i]-segment["shape"][0][i] for i in (0, 1)]
            assert segment["oneway"] and sum(a*b for a, b in zip(vector, highway_vector)) > 0
    with pytest.raises(ValueError, match="too short for junction clearance"):
        RoadNetwork(candidate)


def test_candidate_reports_image_based_shortfalls_instead_of_changing_geometry():
    original = json.loads(SITE.read_text(encoding="utf-8"))
    _, report = build_frontage_candidate(original)
    crossings = {entry["side_road"]: entry for entry in report["crossings"]}
    assert crossings["road0"]["inner_length_m"] == pytest.approx(14.55, abs=.05)
    assert crossings["road1"]["inner_length_m"] == pytest.approx(18.20, abs=.05)
    assert all(entry["required_length_m"] >= 26 for entry in crossings.values())
    assert all(entry["shortfall_m"] > 0 for entry in crossings.values())


def test_current_site_setbacks_are_included_in_shortfall_report():
    current = json.loads((SITE.parents[1] / "tagum_site_b.json").read_text(encoding="utf-8"))
    candidate, report = build_frontage_candidate(current)
    crossings = {entry["side_road"]: entry for entry in report["crossings"]}
    assert crossings["road0"]["required_length_m"] == pytest.approx(22 + 9 + 8)
    assert crossings["road6"]["required_length_m"] == pytest.approx(29.5 + 9 + 8)
    assert all(entry["shortfall_m"] > 0 for entry in crossings.values())
    with pytest.raises(ValueError, match="too short for junction clearance"):
        RoadNetwork(candidate)


def test_split_roads_preserve_restrictions_at_original_endpoints():
    original = json.loads(SITE.read_text(encoding="utf-8"))
    original["prohibited_turns"] = [["road0r", "road3f"], ["road5f", "road0f"],
                                    ["road0f", "otherf"], ["otherr", "road0r"]]
    candidate, _ = build_frontage_candidate(original)
    assert candidate["prohibited_turns"] == [["road0r", "road3f"], ["road5f", "road0f"],
                                             ["road0_outerf", "otherf"], ["otherr", "road0_outerr"]]
    assert original["prohibited_turns"][2] == ["road0f", "otherf"]
    original["prohibited_turns"] = [["road0f"]]
    with pytest.raises(ValueError, match="Turn restrictions"):
        build_frontage_candidate(original)


def test_candidate_cli_keeps_input_and_refuses_to_replace_outputs(tmp_path):
    output, report = tmp_path / "candidate.json", tmp_path / "report.json"
    command = [sys.executable, "-m", "tools.site_b_frontage", "--network", str(SITE), "--candidate", str(output), "--report", str(report)]
    before = SITE.read_bytes()
    process = subprocess.run(command, text=True, capture_output=True)
    assert process.returncode == 0, process.stderr
    assert not json.loads(report.read_text(encoding="utf-8"))["native_structure"]["accepted"]
    candidate_before = output.read_bytes()
    repeated = subprocess.run(command, text=True, capture_output=True)
    assert repeated.returncode != 0 and output.read_bytes() == candidate_before
    assert SITE.read_bytes() == before
