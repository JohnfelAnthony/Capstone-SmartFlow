import copy
import json
from pathlib import Path

import pytest

from simulation.road_network import RoadNetwork
from tools.site_b_layout import proposal_svg, site_b_layout

SITE = Path(__file__).resolve().parents[1]/"data/networks/tagum_site_b.json"


def test_optional_islands_round_trip_without_rewriting_source():
    payload = json.loads(SITE.read_text())
    original = copy.deepcopy(payload)
    payload["islands"] = [{"id": "test", "planted": True, "shape": [[0, 0], [2, 0], [2, 10], [0, 10]]}]
    network = RoadNetwork(payload)
    assert network.visual()["islands"][0]["shape"][1] == {"x": 2, "y": 0}
    assert network.fingerprint != RoadNetwork(original).fingerprint


@pytest.mark.parametrize("shape", [[[0, 0]], [[0, 0], [1, 0], [2, 0]], [[0, 0], [1, 0], [0, float("nan")]]])
def test_invalid_islands_are_rejected(shape):
    payload = json.loads(SITE.read_text())
    payload["islands"] = [{"id": "invalid", "shape": shape}]
    with pytest.raises(ValueError, match="Island shape"):
        RoadNetwork(payload)


def test_proposed_frontage_directions_match_adjacent_main_carriageways():
    layout = site_b_layout(json.loads(SITE.read_text()))
    assert len(layout["islands"]) == 6
    for side in (-1, 1):
        main, frontage = [next(c for c in layout["corridors"] if c["id"] == f"{role}-{side}") for role in ("main", "frontage")]
        vectors = [[b-a for a, b in zip(*c["direction"])] for c in (main, frontage)]
        assert sum(a*b for a, b in zip(*vectors)) > 0


def test_site_b_proposal_tracks_study_junction_when_network_is_translated():
    payload = json.loads(SITE.read_text())
    original = site_b_layout(payload)
    shifted = copy.deepcopy(payload)
    for node in shifted["nodes"]:
        node["x"] += 100
        node["y"] -= 50
    for road in shifted["roads"]:
        road["shape"] = [[x + 100, y - 50] for x, y in road["shape"]]
    moved = site_b_layout(shifted)
    for first, second in zip(original["islands"], moved["islands"]):
        for before, after in zip(first["shape"], second["shape"]):
            assert after == pytest.approx([before[0] + 100, before[1] - 50], abs=.002)


def test_site_b_svg_is_a_labelled_review_artifact():
    from xml.etree import ElementTree
    payload = json.loads(SITE.read_text())
    junction = next(node for node in payload["nodes"] if node["id"] == "tagum_site_b_j")
    root = ElementTree.fromstring(proposal_svg(site_b_layout(payload), junction))
    assert len(root.findall("{http://www.w3.org/2000/svg}polygon")) == 10
    assert "not the active simulation network" in " ".join(root.itertext())
