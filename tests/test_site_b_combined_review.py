"""Review-only proposal: combines geometry; it is not simulation-ready."""
import copy
import json
import subprocess
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

import pytest

from simulation.road_network import RoadNetwork
from tools.site_b_combined_review import build_combined, overview

SITE = Path(__file__).resolve().parents[1] / "data/networks/history/tagum_site_b_osm_corridor.json"


def test_combined_candidate_preserves_input_and_exposes_short_link_rejection():
    payload = json.loads(SITE.read_text(encoding="utf-8"))
    before = copy.deepcopy(payload)
    candidate, report = build_combined(payload)
    assert payload == before
    assert candidate == build_combined(payload)[0]
    frontage = [road for road in candidate["roads"] if road["id"].startswith("frontage_")]
    assert len(frontage) == 6 and all(road["oneway"] for road in frontage)
    assert len([node for node in candidate["nodes"] if node.get("default_control_mode") == "first_come"]) >= 5
    assert not report["native_structure"]["accepted"]
    assert "too short" in report["native_structure"]["reason"]
    with pytest.raises(ValueError, match="too short"):
        RoadNetwork(candidate)
    root = ET.fromstring(overview(candidate))
    labels = " ".join(root.itertext())
    assert "UNVALIDATED SITE B" in labels and "islands not shown" in labels
    assert "CitiHardware study junction" in labels and "Neighbor: no signal" in labels
    assert len(root.findall("{http://www.w3.org/2000/svg}polygon")) == sum(1 for road in candidate["roads"] if road.get("oneway"))


def test_cli_refuses_to_replace_review_files(tmp_path):
    candidate, report, svg = (tmp_path/name for name in ("candidate.json", "report.json", "overview.svg"))
    command = [sys.executable, "-m", "tools.site_b_combined_review", str(SITE), str(candidate), str(report), str(svg)]
    original = SITE.read_bytes()
    result = subprocess.run(command, capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
    existing = [path.read_bytes() for path in (candidate, report, svg)]
    assert subprocess.run(command, capture_output=True).returncode != 0
    assert existing == [path.read_bytes() for path in (candidate, report, svg)]
    assert SITE.read_bytes() == original
