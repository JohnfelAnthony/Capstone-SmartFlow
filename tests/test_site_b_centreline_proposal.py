"""Checks for an uninstalled geometry experiment, not field acceptance."""
import copy
import json
import math
import subprocess
import sys
from pathlib import Path
import pytest

from simulation.road_network import RoadNetwork, sample
from tools.site_b_centreline_proposal import HIGHWAY_ROADS, build_candidate


SITE = Path(__file__).resolve().parents[1] / "data/networks/history/tagum_site_b_osm_corridor.json"


def test_experiment_preserves_source_connections_and_separates_highway_midpoints():
    original = json.loads(SITE.read_text(encoding="utf-8"))
    before = copy.deepcopy(original)
    candidate, report = build_candidate(original)
    assert original == before
    assert candidate == build_candidate(original)[0]
    old = {road["id"]: road for road in original["roads"]}
    new = {road["id"]: road for road in candidate["roads"]}
    for road_id in HIGHWAY_ROADS:
        assert new[road_id]["shape"][0] == old[road_id]["shape"][0]
        assert new[road_id]["shape"][-1] == old[road_id]["shape"][-1]
        assert (new[road_id]["source"], new[road_id]["target"]) == (old[road_id]["source"], old[road_id]["target"])
    assert all(new[name] == old[name] for name in old.keys() - set(HIGHWAY_ROADS))
    network = RoadNetwork(candidate)
    a, b = network.lanes["road2f"], network.lanes["road3f"]
    separation = math.dist(sample(a.shape, a.length/2)[:2], sample(b.shape, b.length/2)[:2])
    assert separation > (a.width+b.width)/2
    assert network.fingerprint == report["network_fingerprint"]
    assert "do not install" in report["status"]


def test_cli_preserves_source_and_refuses_existing_output(tmp_path):
    candidate, report = tmp_path/"candidate.json", tmp_path/"report.json"
    command = [sys.executable, "-m", "tools.site_b_centreline_proposal", str(SITE), str(candidate), str(report)]
    before = SITE.read_bytes()
    result = subprocess.run(command, text=True, capture_output=True)
    assert result.returncode == 0, result.stderr
    output = candidate.read_bytes()
    assert subprocess.run(command, capture_output=True).returncode != 0
    assert candidate.read_bytes() == output and SITE.read_bytes() == before


def test_historical_experiment_refuses_to_overwrite_a_layout_with_islands():
    original = json.loads(SITE.read_text(encoding="utf-8"))
    original["islands"] = [{"id": "existing", "shape": [[0, 0], [1, 0], [1, 1]]}]
    with pytest.raises(ValueError, match="existing islands"):
        build_candidate(original)


def test_guard_cli_records_candidate_fingerprint_without_overwriting(tmp_path):
    candidate, _ = build_candidate(json.loads(SITE.read_text(encoding="utf-8")))
    source, output = tmp_path / "candidate.json", tmp_path / "run.json"
    source.write_text(json.dumps(candidate), encoding="utf-8")
    command = [sys.executable, "-m", "tools.site_b_guard_prototype", "--network", str(source), "--out", str(output), "--seconds", "1", "--seeds", "101"]
    result = subprocess.run(command, capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
    saved = json.loads(output.read_text(encoding="utf-8"))
    assert saved["network_fingerprint"] == RoadNetwork(candidate).fingerprint
    assert saved["case_name"] == "siteB-medium-nosignal"
    assert saved["cases"]["101"]["simulated_s"] == 1
    assert saved["cases"]["101"]["max_island_intrusions"] is None
    previous = output.read_bytes()
    assert subprocess.run(command, capture_output=True).returncode != 0
    assert output.read_bytes() == previous
    altered = tmp_path / "clearance-experiment.json"
    altered_command = [*command[:command.index("--out")], "--out", str(altered), "--seconds", "1", "--seeds", "101", "--experimental-clearance-m", "20"]
    result = subprocess.run(altered_command, capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
    altered_report = json.loads(altered.read_text(encoding="utf-8"))
    assert altered_report["experimental_minimum_junction_clearance_m"] == 20
    assert "without changing" in altered_report["geometry_warning"]
    assert altered_report["network_fingerprint"] == saved["network_fingerprint"]
