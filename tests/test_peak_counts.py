"""Peak-traffic video counts as scenario demand (docs/superpowers/specs/2026-11-13-peak-video-counts-in-scenarios-design.md).

The counted side is kept exactly; the unmeasured side is shared equally among legal routes (owner, 2026-11-13).
Site A counted vehicles leaving by each road; Site B's detector counted vehicles arriving on three roads, Dao Street gets Sobrecarey's rate.
"""
from collections import defaultdict

import pytest

from services.movement_counts import approach_boundaries
from services.peak_counts import LABEL, load_peak_counts, peak_counts_demand
from simulation.network_registry import load_registered_network
from simulation.scenario_config import DEFAULTS, validate_config
from simulation.traffic_engine import TrafficEngine


def demand(site: str, config: dict | None = None) -> tuple[dict, dict, dict]:
    result = peak_counts_demand(network_id=site, engine_config=config or {"pedestrian_density": "low"})
    return result["engine_config"], result["summary"], load_peak_counts(site)


def legs(site: str) -> tuple[dict, dict]:
    boundaries = approach_boundaries(load_registered_network(site))
    return {entry: name for name, (entry, _) in boundaries.items()}, {exit_: name for name, (_, exit_) in boundaries.items()}


def streams(site: str, config: dict) -> list[tuple[str, str, str, float]]:
    """(origin road, exit road, vehicle type, vehicles in the video) for every demand window."""
    entries, exits = legs(site)
    seconds = load_peak_counts(site)["video"]["seconds"]
    return [(entries[window["od"][0]["source"]], exits[window["od"][0]["destination"]], window["vehicle_type"],
             window["vehicles_per_hour"]*seconds/3600) for window in config["demand_windows"]]


def test_site_a_keeps_every_counted_exit_total_and_shares_origins_equally():
    config, _, counts = demand("tagum_site_a")
    totals, shares = defaultdict(float), defaultdict(set)
    for origin, exit_, kind, vehicles in streams("tagum_site_a", config):
        assert origin != exit_
        totals[(exit_, kind)] += vehicles
        shares[(exit_, kind)].add(round(vehicles, 9))
    for road, classes in counts["counts"].items():
        for kind, counted in classes.items():
            assert totals[(road, kind)] == pytest.approx(counted)
    assert all(len(values) == 1 for values in shares.values()), "every legal origin gets the same share"
    assert {len([s for s in streams("tagum_site_a", config) if (s[1], s[2]) == key]) for key in shares} == {3}


def test_site_b_keeps_every_counted_arrival_gives_dao_sobrecarey_rate_and_no_heavy_vehicle_to_sobrecarey():
    config, _, counts = demand("tagum_site_b")
    totals, shares = defaultdict(float), defaultdict(set)
    for origin, exit_, kind, vehicles in streams("tagum_site_b", config):
        assert origin != exit_
        assert not (exit_ == "north" and kind in {"bus", "truck"}), "buses and trucks are banned on Sobrecarey Street"
        totals[(origin, kind)] += vehicles
        shares[(origin, kind)].add(round(vehicles, 9))
    for road, classes in {**counts["counts"], **counts["assumed"]}.items():
        for kind, counted in classes.items():
            assert totals[(road, kind)] == pytest.approx(counted)
    assert counts["assumed"]["south"] == counts["counts"]["north"]
    assert counts["counts"]["north"]["bus"] == counts["counts"]["north"]["truck"] == 0 and counts["counts"]["north"]["tricycle"] == 17
    assert all(len(values) == 1 for values in shares.values())


def test_every_stream_is_a_route_through_the_study_junction():
    for site in ("tagum_site_a", "tagum_site_b"):
        network = load_registered_network(site)
        config, _, _ = demand(site)
        for window in config["demand_windows"]:
            route = network.route(window["od"][0]["source"], window["od"][0]["destination"], vehicle_type=window["vehicle_type"])
            assert route and network.intersections[0] in {network.lanes[lane].target for lane in route}, window["label"]


def test_summary_counts_vehicles_entering_in_5_10_and_15_minutes():
    _, a, _ = demand("tagum_site_a")
    _, b, _ = demand("tagum_site_b")
    assert (a["counted_vehicles"], a["assumed_vehicles"]) == (1052, 0)
    assert (b["counted_vehicles"], b["assumed_vehicles"]) == (650, 50)
    assert a["entering"] == {"5": 314, "10": 629, "15": 943}
    assert b["entering"] == {"5": 217, "10": 434, "15": 651}
    assert {road["approach"]: (road["leaving"], road["leaving_assumed"]) for road in a["roads"]}["north"] == (190, False)
    assert {road["approach"]: (road["arriving"], road["arriving_assumed"]) for road in b["roads"]}["south"] == (50, True)
    assert any("detector" in note for note in b["notes"]) and any("Dao Street" in note for note in b["notes"])
    assert any(note.startswith("17 detected buses and trucks on Sobrecarey Street count as tricycles") for note in b["notes"])


def test_the_scenario_is_labelled_and_only_site_a_sets_pedestrians_from_the_count():
    a, summary_a, _ = demand("tagum_site_a")
    b, summary_b, _ = demand("tagum_site_b", {"pedestrian_density": "medium", "green_seconds": 20.0})
    for config in (a, b):
        assert config["traffic_density"] == "none" and config["demand_source"]["kind"] == "field_counts"
        assert config["demand_source"]["description"].startswith(LABEL)
        assert "not calibrated or validated" in config["demand_source"]["description"]
    assert (a["pedestrian_density"], a["pedestrian_rate_per_hour"]) == ("counted", pytest.approx(15*3600/1004.1216666666667))
    assert summary_a["pedestrians"]["counted"] == 15
    assert (b["pedestrian_density"], b["green_seconds"], summary_b["pedestrians"]) == ("medium", 20.0, None)
    assert "pedestrian_rate_per_hour" not in b


def test_a_network_without_peak_counts_is_refused():
    with pytest.raises(ValueError):
        peak_counts_demand(network_id="tagum_network", engine_config={})


def test_counted_pedestrians_need_a_rate_and_the_rate_goes_with_any_other_choice():
    network = load_registered_network("tagum_site_a")
    with pytest.raises(ValueError):
        validate_config(DEFAULTS, {"pedestrian_density": "counted"}, network)
    observed = validate_config(DEFAULTS, {"pedestrian_density": "counted", "pedestrian_rate_per_hour": 54}, network)
    assert observed["pedestrian_rate_per_hour"] == 54
    assert "pedestrian_rate_per_hour" not in validate_config(observed, {"pedestrian_density": "low"}, network)
    assert "pedestrian_rate_per_hour" not in validate_config(DEFAULTS, {"pedestrian_density": "low"}, network)


def test_counted_pedestrians_arrive_at_the_counted_rate():
    engine = TrafficEngine(seed=11, network=load_registered_network("tagum_site_a"))
    engine.configure(traffic_density="none", pedestrian_density="counted", pedestrian_rate_per_hour=54.0)
    engine.start(4*3600)
    engine.step(4*36000)
    assert 4*54*0.75 < engine.pedestrian_serial < 4*54*1.25


def test_the_endpoint_returns_demand_and_summary_and_the_old_importers_are_gone(tmp_path, monkeypatch):
    import os
    os.environ.setdefault("SMARTFLOW_SECRET_KEY", "peak-counts-test-only")
    from fastapi.testclient import TestClient

    import config
    from backend.main import app
    monkeypatch.setattr(config, "DB_PATH", str(tmp_path / "peak.db"))
    monkeypatch.setattr(config, "BOOTSTRAP_ADMIN_PASSWORD", "PeakAdmin42!")
    with TestClient(app) as client:
        assert client.post("/api/auth/login", json={"username": "admin", "password": "PeakAdmin42!"}).status_code == 200
        for site in ("tagum_site_a", "tagum_site_b"):
            response = client.post("/api/scenarios/peak-counts", json={"network_id": site, "engine_config": {}})
            assert response.status_code == 200, response.text
            assert response.json()["summary"]["label"] == LABEL
        refused = client.post("/api/scenarios/peak-counts", json={"network_id": "tagum_network", "engine_config": {}})
        assert refused.status_code == 422 and "study sites" in refused.json()["detail"]
        for removed in ("/api/scenarios/movement-counts", "/api/scenarios/field-observer-counts"):
            assert client.post(removed, json={}).status_code in {404, 405}
