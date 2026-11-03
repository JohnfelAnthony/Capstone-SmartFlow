from simulation.road_network import RoadNetwork
from tests.mixed_traffic_helpers import junction_network
from tools import site_b_island_sweep_review
from tools.road_editor.server import sampled_island_review, sampled_lane_review
import pytest


def test_sweep_review_detects_vehicle_body_contact_and_identifies_network(monkeypatch):
    payload = junction_network().payload
    baseline = RoadNetwork(payload)
    point = baseline.connector("wf", "er")[1]
    # Place a small obstacle alongside the path: the vehicle body reaches it
    # even though its centre line does not intersect the obstacle.
    payload["islands"] = [{"id": "obstacle", "shape": [[point[0] - .1, point[1] + .5],
                          [point[0] + .1, point[1] + .5], [point[0] + .1, point[1] + .7],
                          [point[0] - .1, point[1] + .7]]}]
    network = RoadNetwork(payload)
    monkeypatch.setattr(site_b_island_sweep_review, "VEHICLE_TYPES", {"bus": {"length": 10, "width": 2.6}})
    result = site_b_island_sweep_review.review(network)
    assert result["fingerprint"] == network.fingerprint
    assert result["sampled_sweeps"] > 0
    assert any(item["island"] == "obstacle" and item["vehicle_class"] == "bus" for item in result["conflicts"])
    assert any(item["actual_size_body_first_sample_m"] is not None for item in result["conflicts"])
    assert "diagnostic only" in result["status"]
    editor_result = sampled_island_review(payload)
    assert editor_result["fingerprint"] == network.fingerprint
    assert any(item["island"] == "obstacle" and item["actual_size_body_first_sample_m"] is not None
               for item in editor_result["conflicts"])


def test_editor_refuses_sampled_review_of_invalid_structure():
    payload = junction_network().payload
    payload["roads"][0]["shape"][1] = payload["roads"][0]["shape"][0]
    with pytest.raises(ValueError, match="structural errors"):
        sampled_island_review(payload)


def test_lane_body_sampling_detects_an_island_beside_the_centerline(monkeypatch):
    from simulation.road_network import sample

    payload = junction_network().payload
    lane = RoadNetwork(payload).lanes["wf"]
    x, y, _ = sample(lane.shape, lane.length / 2)
    payload["islands"] = [{"id": "near-lane", "shape": [[x-.1, y+.5], [x+.1, y+.5],
                                                            [x+.1, y+.7], [x-.1, y+.7]]}]
    network = RoadNetwork(payload)
    monkeypatch.setattr(site_b_island_sweep_review, "VEHICLE_TYPES", {"bus": {"length": 10, "width": 2.6}})
    result = site_b_island_sweep_review.review_lanes(network)
    assert result["fingerprint"] == network.fingerprint
    assert any(item["lane"] == "wf" and item["island"] == "near-lane" for item in result["conflicts"])
    assert "diagnostic only" in result["status"]
    editor_result = sampled_lane_review(payload)
    assert editor_result["fingerprint"] == network.fingerprint
    assert any(item["lane"] == "wf" and item["island"] == "near-lane" for item in editor_result["conflicts"])
    with pytest.raises(ValueError, match="spacing"):
        site_b_island_sweep_review.review_lanes(network, spacing_m=0)


@pytest.mark.xfail(strict=True, reason="Provisional Site B connector sweeps touch median islands; geometry needs review")
def test_site_b_connector_footprint_envelopes_clear_islands():
    from simulation.network_registry import load_registered_network
    result = site_b_island_sweep_review.review(load_registered_network("tagum_site_b"))
    assert result["conflicts"] == []
