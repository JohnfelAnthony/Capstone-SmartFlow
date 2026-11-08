"""A vehicle behind, in the next sideways band, must keep clear of where the one ahead will be after this tick on a bent lane.

Found on the Site A street grid (D41, high demand, no signal, seed 101, 761.5 s): a bus passing the 9.8 degree bend on Capitol east
(road3r, about 56 m from j12) swung its rear into a motorcycle level with its tail. The motorcycle was held against where the bus stood,
then the bus moved and its turned rear met the motorcycle. Seed 102 (medium, 1749.5 s) showed the same at the same bend with the
motorcycle stopped two ticks before the bus's rear reached it, so one tick of look-ahead is not enough.
"""
import pytest

from simulation.footprints import overlapping_pairs
from simulation.network_registry import load_registered_network
from simulation.traffic_engine import TrafficEngine


@pytest.mark.parametrize("bus_at,bus_lateral,bus_speed,motorcycle_at,motorcycle_lateral,motorcycle_speed", [
    (57.95, 1.35, 6.66, 52.25, -0.83, 7.81),  # seed 101, high demand
    (47.85, 1.67, 7.32, 43.07, -0.33, 8.52),  # seed 102, medium demand
])
def test_a_motorcycle_beside_a_bus_tail_on_a_bend_is_never_touched_by_the_bus_rear(bus_at, bus_lateral, bus_speed, motorcycle_at, motorcycle_lateral, motorcycle_speed):
    engine = TrafficEngine(seed=7, network=load_registered_network("tagum_site_a"))
    engine.configure(traffic_density="none", pedestrian_density="none", routing_mode="static")
    engine.enable_no_signal_control()
    engine.driver_variation_scale = 0
    engine.start(300)
    route = ["road3r", "road2f", "road4f"]
    bus = engine.add_vehicle(route, vehicle_type="bus", speed=bus_speed)
    bus.position, bus.lateral, bus.lateral_target = bus_at, bus_lateral, bus_lateral
    motorcycle = engine.add_vehicle(route, vehicle_type="motorcycle", speed=motorcycle_speed)
    motorcycle.position, motorcycle.lateral, motorcycle.lateral_target = motorcycle_at, motorcycle_lateral, motorcycle_lateral
    assert "road3r" in engine._bent_lanes and not overlapping_pairs(engine.vehicle_records())
    for _ in range(100):
        engine.step(1)
        assert not overlapping_pairs(engine.vehicle_records()), f"overlap at {engine.simulation_time:.1f}s"
    assert motorcycle.position > 60  # held only as long as needed, not stopped
