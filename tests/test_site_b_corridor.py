from pathlib import Path

import pytest

from simulation.road_network import RoadNetwork
from simulation.traffic_engine import TrafficEngine
from tools.site_b_corridor import build_site_b_corridor

SOURCE = Path(__file__).resolve().parents[1]/"data/networks/osm_site_b.json"


def test_corridor_connects_study_and_neighbor_with_no_signal():
    payload = build_site_b_corridor(SOURCE)
    network = RoadNetwork(payload)
    assert len(network.intersections) == 2
    assert network.intersections[0] == "tagum_site_b_j"
    neighbor = network.intersections[1]
    assert all(group["permanent_no_signal"] for group in network.visual()["signal_groups"] if network.lanes[group["lane_id"]].target == neighbor)
    assert network.route("tagum_site_b_j", neighbor)
    assert network.route(neighbor, "tagum_site_b_j")
    engine = TrafficEngine(network=network, seed=101)
    engine.configure(traffic_density="medium", pedestrian_density="none")
    engine.start(120)
    assert engine.signals[neighbor].mode == "first_come"
    assert engine.signals["tagum_site_b_j"].mode == "signalized"
    engine.step(1200)
    assert engine.lifetime_completed > 0
    assert engine._last_metrics["vehicle_conservation_error"] == 0


def test_neighbor_cannot_be_selected_for_rl_or_overridden_with_a_signal():
    network = RoadNetwork(build_site_b_corridor(SOURCE))
    neighbor = network.intersections[1]
    engine = TrafficEngine(network=network)
    with pytest.raises(ValueError, match="outside the study"):
        engine.configure(controlled_junction=neighbor)
    engine.configure(signal_plans={neighbor: {"mode": "signalized"}})
    engine.start(30)
    assert engine.signals[neighbor].mode == "first_come"
