"""Two vehicles from different approaches level at the mouth of one exit must not wait for each other for good.

Found at Site B's neighbouring junction (D45): with the Dao road closed, three vehicles from the south-west carriageway and two from
the north-east one stopped inside the junction, all turning into Acacia Street, each seeing the other level with it as the leader it
had to wait for. Neither body touched the other.
"""
import pytest

from simulation.network_registry import load_registered_network
from simulation.road_network import length
from simulation.traffic_engine import TrafficEngine


def two_vehicles_level_at_the_mouth():
    network = load_registered_network("tagum_site_b")
    engine = TrafficEngine(seed=7, network=network)
    engine.configure(traffic_density="none", pedestrian_density="none", routing_mode="static")
    engine.enable_no_signal_control()
    engine.driver_variation_scale = 0
    engine.start(60)
    placed = []
    # The frozen state as traced: (approach lane, class, metres into the connector, entry lateral, lateral now, exit lateral)
    for first, vehicle_type, at, entry, lateral, exit_lateral in (("road3f", "tricycle", 34.208, 0.81, 0.81, 0.81), ("road9f", "car", 61.06, -3.6, -1.075, -1.04)):
        vehicle = engine.add_vehicle([first, "road6f", "road13f", "road18f"], vehicle_type=vehicle_type)
        vehicle.position = network.lanes[first].length
        vehicle.connector, vehicle.connector_position = network.connector(first, "road6f"), at
        vehicle.connector_entry_lateral, vehicle.lateral, vehicle.connector_exit_lateral, vehicle.lateral_target = entry, lateral, exit_lateral, lateral
        engine._reserve(vehicle, "1115349256", network.lanes[first].approach)
        placed.append(vehicle)
    return engine, placed


def test_vehicles_level_at_the_mouth_of_one_exit_both_get_through():
    engine, placed = two_vehicles_level_at_the_mouth()
    first, second = placed
    assert engine._crossing_gap(first, second) < 0 and engine._crossing_gap(second, first) < 0  # each sees the other ahead
    ids = {vehicle.id for vehicle in placed}
    for _ in range(600):
        engine.step(1)
        if not ids & set(engine.vehicles) or all(engine.vehicles[i].connector is None for i in ids if i in engine.vehicles):
            break
    assert all(vehicle.id not in engine.vehicles or vehicle.connector is None for vehicle in placed), "still waiting for each other inside the junction"


def test_the_wait_is_the_one_this_rule_ends(monkeypatch):
    monkeypatch.setattr(TrafficEngine, "_goes_first", lambda self, vehicle, other, connector_length: False)
    engine, placed = two_vehicles_level_at_the_mouth()
    for _ in range(600):
        engine.step(1)
    assert any(vehicle.id in engine.vehicles and vehicle.connector is not None for vehicle in placed)
