"""Vehicle access applies to demand, explicit trips and closure detours."""
import copy

import pytest

from simulation.demand import build_schedule
from simulation.network_registry import load_registered_network
from simulation.road_network import RoadNetwork
from simulation.scenario_config import DEFAULTS, validate_config
from simulation.traffic_engine import TrafficEngine


def restricted_network():
    payload = copy.deepcopy(load_registered_network("tagum_site_b").payload)
    payload["lane_vehicle_restrictions"] = {lane: ["bus", "truck"] for lane in ("road1f", "road1r")}
    return RoadNetwork(payload)


@pytest.mark.parametrize("kind", ["bus", "truck"])
def test_sobrecarey_is_unreachable_in_both_directions_for_heavy_vehicles(kind):
    network = restricted_network()
    for source, target in (("boundary_9", "boundary_1"), ("boundary_1", "boundary_4")):
        assert network.route(source, target)
        assert not network.route(source, target, vehicle_type=kind)
    assert network.route("boundary_9", "boundary_4", vehicle_type=kind)
    assert network.route("boundary_9", "boundary_7", vehicle_type=kind)  # Bonifacio is unchanged


def test_synthetic_demand_keeps_heavy_vehicles_on_legal_routes():
    network = restricted_network()
    config = validate_config(DEFAULTS, {"traffic_density": "high", "vehicle_mix": {"truck": 1}}, network)
    arrivals = build_schedule(config, network, 101, 600)
    assert arrivals and all(a.vehicle_type == "truck" for a in arrivals)
    assert all(network.route(a.source, a.destination, vehicle_type=a.vehicle_type) for a in arrivals)
    assert arrivals == build_schedule(config, network, 101, 600)


@pytest.mark.parametrize("classed", [False, True])
def test_explicit_demand_cannot_silently_drop_or_redirect_prohibited_counts(classed):
    network = restricted_network()
    window = {"start": 0, "end": 300, "vehicles_per_hour": 60,
              "od": [{"source": "boundary_9", "destination": "boundary_1"}]}
    if classed:
        window["vehicle_type"] = "bus"
    with pytest.raises(ValueError, match="vehicle access"):
        validate_config(DEFAULTS, {"vehicle_mix": {"bus": 1}, "demand_windows": [window]}, network)


def test_explicit_trip_and_direct_insertion_respect_access():
    network = restricted_network()
    with pytest.raises(ValueError, match="vehicle access"):
        validate_config(DEFAULTS, {"trips": [{"time": 0, "source": "boundary_9", "destination": "boundary_1", "vehicle_type": "truck"}]}, network)
    engine = TrafficEngine(network=network)
    with pytest.raises(ValueError, match="vehicle access"):
        engine.add_vehicle(network.route("boundary_9", "boundary_1"), vehicle_type="truck")
    assert network.route("boundary_9", "boundary_1", vehicle_type="car")


def test_diversion_never_uses_a_restricted_exit():
    network = restricted_network()
    engine = TrafficEngine(network=network)
    engine.closed_lanes = {lane.id for lane in network.lanes.values()
                           if lane.target in network.boundaries and lane.id != "road1f"}
    assert not engine._best_open_exit("tagum_site_b_j", "road2f", None, vehicle_type="truck")
    assert engine._best_open_exit("tagum_site_b_j", "road2f", None, vehicle_type="car")
    assert "boundary_9" in engine._closure_blocked_sources("truck")
    assert "boundary_9" not in engine._closure_blocked_sources("car")


@pytest.mark.parametrize("rules", [{"missing": ["bus"]}, {"road1f": ["unknown"]}, {"road1f": "bus"}])
def test_invalid_access_metadata_is_rejected(rules):
    payload = copy.deepcopy(restricted_network().payload)
    payload["lane_vehicle_restrictions"] = rules
    with pytest.raises(ValueError, match="vehicle restrictions"):
        RoadNetwork(payload)


def test_registered_site_and_builder_record_only_sobrecarey_access():
    network = load_registered_network("tagum_site_b")
    assert network.lane_vehicle_restrictions == {lane: frozenset({"bus", "truck"}) for lane in ("road1f", "road1r")}
    assert not load_registered_network("tagum_site_a").lane_vehicle_restrictions


def test_closure_rerouting_and_live_spawning_keep_heavy_vehicles_off_sobrecarey():
    network = restricted_network()
    engine = TrafficEngine(network=network, seed=101)
    engine.configure(traffic_density="low", pedestrian_density="none", vehicle_mix={"bus": 1, "truck": 1},
                     closed_lanes=["road4f"], closure_responses={"road4f": "nearest_exit"})
    engine.start(120)
    while engine.status == "running":
        engine.step()
        assert all(not {"road1f", "road1r"}.intersection(vehicle.route) for vehicle in engine.vehicles.values())
        assert engine._last_metrics["vehicle_conservation_error"] == 0
    assert engine.vehicle_serial > 0


def test_shared_sobrecarey_retains_access_restrictions():
    from simulation.contraflow import shared_network
    network = restricted_network()
    shared = shared_network(network, {"road1": "road1r"})
    for lane in ("road1f", "road1r"):
        assert not shared.lane_allows(lane, "bus")
        assert shared.lane_allows(lane, "car")


def test_previous_network_is_preserved_and_included_in_backup():
    import json
    from pathlib import Path
    from services import backup_bundle
    from simulation.network_registry import engine_for_scenario
    root = Path(__file__).resolve().parents[1]
    history = root / "data/networks/tagum_site_b_pre_sobrecarey_access.json"
    old = RoadNetwork(json.loads(history.read_text(encoding="utf-8")))
    assert old.fingerprint == "b2a951536ed1cac8dd575dfc8977d23e7ab422b1060b66942dbe7c04832c2f2e"
    assert history in backup_bundle._files_for_references(set()).values()
    with pytest.raises(ValueError, match="changed|match"):
        engine_for_scenario({"network_id": old.id, "network_sha256": old.fingerprint, "engine_config": {}})
