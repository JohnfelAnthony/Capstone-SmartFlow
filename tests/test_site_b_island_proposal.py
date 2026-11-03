"""Historical corridor geometry experiment; never a field or safety result."""
import copy
import json
from pathlib import Path

import pytest

from simulation.road_network import RoadNetwork
from tools.site_b_island_proposal import build_island_proposal


ROOT = Path(__file__).resolve().parents[1]
HISTORY = ROOT / "data/networks/history/tagum_site_b_osm_corridor.json"


def test_island_experiment_is_separate_and_reports_conflicts():
    original = json.loads(HISTORY.read_text(encoding="utf-8"))
    before = copy.deepcopy(original)
    candidate, report = build_island_proposal(original)
    assert original == before
    assert len(candidate["islands"]) == 9
    assert all(island["planted"] for island in candidate["islands"])
    assert report["island_review"]["frontage_center_offset_m"] == 15.25
    assert report["island_review"]["nominal_island_width_m"] == 2
    assert report["island_review"]["pavement_conflicts"]
    assert report["source_network_fingerprint"] == RoadNetwork(original).fingerprint
    assert all(item["roads"] for item in report["island_review"]["pavement_conflicts"])
    assert not report["native_structure"]["accepted"]
    with pytest.raises(ValueError, match="too short"):
        RoadNetwork(candidate)


def test_experiment_refuses_newer_network_with_existing_islands():
    original = json.loads(HISTORY.read_text(encoding="utf-8"))
    original["islands"] = [{"id": "existing", "shape": [[0, 0], [1, 0], [1, 1]]}]
    with pytest.raises(ValueError, match="existing islands"):
        build_island_proposal(original)
