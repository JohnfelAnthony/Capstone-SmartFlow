import json
import math
from pathlib import Path

import pytest

from simulation.road_network import RoadNetwork


def star(bearings):
    nodes = [{"id": "j", "x": 0, "y": 0}]
    roads = []
    for index, bearing in enumerate(bearings):
        angle = math.radians(bearing)
        x, y = 100 * math.sin(angle), 100 * math.cos(angle)
        nodes.append({"id": str(index), "x": x, "y": y, "boundary": True})
        roads.append({"id": str(index), "source": str(index), "target": "j", "shape": [[x, y], [0, 0]]})
    return {"id": "star", "nodes": nodes, "roads": roads}


def test_skewed_legs_are_distinct_and_keep_circular_order():
    network = RoadNetwork(star([38, 128, 217, 354]))
    names = [network.lanes[f"{i}f"].approach for i in range(4)]
    expected = ["north", "east", "south", "west"]
    assert tuple(names) in {tuple(expected[i:] + expected[:i]) for i in range(4)}


def test_five_incoming_legs_are_refused():
    with pytest.raises(ValueError, match="Junction j has 5 approaches"):
        RoadNetwork(star([0, 72, 144, 216, 288]))


def test_regular_cross_is_unchanged():
    network = RoadNetwork(star([0, 90, 180, 270]))
    assert [network.lanes[f"{i}f"].approach for i in range(4)] == ["north", "east", "south", "west"]


@pytest.mark.parametrize("filename,expected", [
    ("tagum_network.json", {"1226402048": ["east", "north", "south", "west"], "1217544499": ["east", "north", "south"], "376306710": ["east", "north", "south", "west"], "1217544567": ["north", "south", "west"], "1217544575": ["north", "south", "west"]}),
    ("tagum_network_2j.json", {"1226402048": ["east", "north", "south", "west"], "1217544499": ["east", "north", "south"]}),
])
def test_existing_networks_retain_approach_names(filename, expected):
    path = Path(__file__).resolve().parents[1] / "data" / "networks" / filename
    network = RoadNetwork(json.loads(path.read_text(encoding="utf-8")))
    assert {node: sorted(network.lanes[lane].approach for lane in network.incoming[node]) for node in network.intersections} == expected
