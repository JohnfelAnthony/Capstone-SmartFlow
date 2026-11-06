"""stalled_vehicles: a lane vehicle stopped over 60 s that nothing legitimately holds (engine native-10).

stuck_junction_vehicles only sees vehicles holding a reservation or held at a closed exit, and gridlock_seconds needs the whole network
to stand still, so a few vehicles frozen at a line with an empty junction read as clean (seed 108 at Site A, 958 s).
"""
from simulation.network_registry import load_registered_network
from simulation.traffic_engine import TrafficEngine
from tests.mixed_traffic_helpers import hold_green, junction_network, place, started_engine


def site_a_scene(kinds):
    engine = TrafficEngine(seed=7, network=load_registered_network("tagum_site_a"))
    engine.configure(traffic_density="none", pedestrian_density="none", routing_mode="static")
    engine.enable_no_signal_control()
    engine.driver_variation_scale = 0
    engine.start(300)
    vehicles = []
    for kind, position, lateral, arrival in kinds:
        vehicle = engine.add_vehicle(["road4r", "road6f", "road5f"], vehicle_type=kind, speed=0.0)
        vehicle.position, vehicle.lateral, vehicle.lateral_target = position, lateral, lateral
        vehicle.approach_arrival = vehicle.stop_arrival = arrival
        vehicles.append(vehicle)
    return engine, vehicles


def test_a_head_vehicle_held_with_an_empty_junction_is_stalled_but_the_one_queued_behind_it_is_not():
    engine, (head, behind) = site_a_scene([("car", 13.0, 0.0, 10.0), ("car", 7.0, 0.0, 11.0)])
    engine._first_come_permission = lambda vehicle, node: False  # a hold that nothing explains
    engine.step(500)
    assert engine._last_metrics["stalled_vehicles"] == 0
    engine.step(200)
    assert head.stopped_for > 60 and behind.stopped_for > 60
    assert engine._last_metrics["stalled_vehicles"] == 1


def test_a_vehicle_waiting_at_a_red_light_is_not_stalled():
    engine = started_engine(junction_network())
    hold_green(engine, "j", "north")
    waiting = place(engine, ["wf", "er"], "car", from_stop_line=2, lateral=0)
    engine.step(900)
    assert waiting.stopped_for > 60 and engine._last_metrics["stalled_vehicles"] == 0


def test_a_vehicle_held_at_a_closed_exit_is_counted_there_and_not_as_stalled():
    engine = started_engine(junction_network(), closed_lanes=["er", "nr", "sr"])
    place(engine, ["wf", "er"], "car", from_stop_line=2, lateral=0)
    engine.step(900)
    assert engine._last_metrics["closure_held_vehicles"] == 1 and engine._last_metrics["stalled_vehicles"] == 0


def test_a_clear_run_has_no_stalled_vehicles():
    engine, _ = site_a_scene([("car", 13.0, 0.0, 10.0)])
    engine.step(1200)
    assert engine._last_metrics["throughput"] == 1 and engine._last_metrics["stalled_vehicles"] == 0


def test_a_junction_with_a_vehicle_held_by_a_full_or_closed_exit_explains_the_vehicles_waiting_their_turn():
    """Seed 101, high traffic, no signal, west closed 300-1200 s: the loop street was jammed back to its start, the head of the west stub could not
    enter it (exit full), and the vehicles waiting behind it for their order at the line read as stalled."""
    engine = started_engine(junction_network(), closed_lanes=["er", "nr", "sr"])
    assert engine._node_has_exit_hold("j") is False
    place(engine, ["wf", "er"], "car", from_stop_line=0.5, lateral=0)
    engine.step(50)
    assert engine._node_has_exit_hold("j") is True


def test_a_full_exit_whose_own_head_is_going_nowhere_does_not_explain_the_wait():
    """The chain must end at something real: a moving vehicle, a closure, a red, or an exit that clears. A lane already on the chain, or a head
    at the end of the network with nothing holding it, makes the whole chain a stall."""
    engine = started_engine(junction_network())
    blocked = place(engine, ["wf", "er"], "car", from_stop_line=0.5, lateral=0)
    assert engine._full_exit_clears("er", {"er"}) is False  # a lane already on the chain: each exit full because of the next
    engine._exit_has_space = lambda lane_id, vehicle: lane_id != "er"
    leader = engine.add_vehicle(["er"], vehicle_type="car", speed=0.0)
    leader.position = engine.network.lanes["er"].length-2
    assert engine._full_exit_clears("er", set()) is False  # its head stands at the end of the network with nothing holding it
    leader.speed = 3.0
    assert engine._full_exit_clears("er", set()) is True  # its head is moving
    assert blocked.route[1] == "er"
