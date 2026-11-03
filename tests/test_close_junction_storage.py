"""Synthetic evidence for the close-junction design; no production rule is changed."""
import pytest

from simulation import road_network
from simulation.traffic_engine import TrafficEngine
from tests.test_junction_deadlock import hold, two_junction_line


def test_reducing_clipping_alone_strands_long_vehicles_before_a_short_link(monkeypatch):
    # This deliberately unsafe geometry experiment is isolated to the test.
    # It demonstrates why merely lowering the parser clearance is insufficient.
    monkeypatch.setattr(road_network, "JUNCTION_CLEARANCE_M", 2.0)
    monkeypatch.setattr(road_network, "STOP_LINE_SETBACK_M", 0.0)
    network = two_junction_line(link_length=14.55)
    route = network.route("w", "e")
    engine = TrafficEngine(seed=7, network=network)
    engine.configure(traffic_density="none", pedestrian_density="none")
    engine.driver_variation_scale = 0
    engine.start(300)
    hold(engine, "j1", "west")
    hold(engine, "j2", "west")
    bus = engine.add_vehicle(route, vehicle_type="bus")
    assert bus is not None
    link = network.lanes[route[1]]
    assert link.length == pytest.approx(10.55)
    assert engine.stop_line(link.id) < bus.length + bus.minimum_gap + 1.0
    assert not engine._exit_has_space(link.id, bus)
    bus.position = network.lanes[route[0]].length - bus.length / 2
    engine.step(300)
    assert bus.reserved_junction is None
    assert bus.route[0] == route[0]
    assert engine.lifetime_completed == 0
