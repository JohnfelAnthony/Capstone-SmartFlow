"""Regression evidence for native engine input, timing and control boundaries."""
import copy
import unittest
from unittest.mock import patch

from services.render_frame_service import build_render_frame
from simulation.road_network import RoadNetwork
from simulation.traffic_engine import TrafficEngine


class NativeRegressionTests(unittest.TestCase):
    def setUp(self):
        self.engine = TrafficEngine(seed=17)
        network = self.engine.network
        self.source, self.destination = next((a, b) for a in network.boundaries for b in network.boundaries if network.route(a, b))

    def trip(self, time=0):
        return {"time": time, "source": self.source, "destination": self.destination}

    def test_malformed_nested_inputs_fail_without_mutating_configuration(self):
        original = copy.deepcopy(self.engine.config)
        junction = self.engine.controlled_junction
        for settings in (
            {"routing_mode": []}, {"intersection_id": {}},
            {"events": [{"time": 0, "lane_id": [], "closed": True}]},
            {"signal_plans": {junction: {"phase_order": None}}},
            {"signal_plans": {junction: {"mode": []}}},
            {"demand_source": {"kind": []}},
            {"trips": [{**self.trip(), "vehicle_type": []}]},
        ):
            with self.subTest(settings=settings), self.assertRaises(ValueError):
                self.engine.configure(**settings)
            self.assertEqual(self.engine.config, original)
        for native in (None, False, [], "null", "invalid-json"):
            with self.subTest(native=native), self.assertRaises(ValueError):
                self.engine.configure_from_scenario({"engine_config": native})
            self.assertEqual(self.engine.config, original)

    def test_legacy_disruption_details_are_not_silently_ignored(self):
        with self.assertRaisesRegex(ValueError, "migrate"):
            self.engine.configure_from_scenario({"lane_closure_config": {"lane_id": "old-sumo-lane"}})
        self.engine.configure_from_scenario({"lane_closure_config": "{}"})

    def test_closures_precede_arrivals_at_zero_and_later_event_times(self):
        outgoing = self.engine.network.outgoing[self.source]
        for time in (0, 2):
            with self.subTest(time=time):
                engine = TrafficEngine()
                engine.configure(traffic_density="none", trips=[self.trip(time)], events=[
                    {"time": time, "lane_id": lane, "closed": True} for lane in outgoing])
                engine.start(5)
                engine.step(time*10)
                self.assertEqual(len(engine.vehicles), 0)
                self.assertEqual(len(engine.pending_demand), 1)
                self.assertEqual(engine._last_metrics["vehicle_conservation_error"], 0)

    def test_start_rejection_preserves_the_previous_completed_state(self):
        self.engine.start(1)
        self.engine.step(10)
        before = self.engine.to_dict()
        with patch("simulation.traffic_engine.build_schedule", side_effect=ValueError("excess demand")):
            with self.assertRaisesRegex(ValueError, "excess demand"):
                self.engine.start(30)
        self.assertEqual(self.engine.to_dict(), before)
        self.assertEqual(self.engine.duration_limit, 1)

    def test_blocked_stop_approach_does_not_block_an_unrelated_exit(self):
        network = RoadNetwork({"id": "cross", "nodes": [
            {"id": "j", "x": 0, "y": 0},
            {"id": "w", "x": -100, "y": 0, "boundary": True},
            {"id": "e", "x": 100, "y": 0, "boundary": True},
            {"id": "n", "x": 0, "y": 100, "boundary": True},
            {"id": "s", "x": 0, "y": -100, "boundary": True}], "roads": [
            {"id": "west", "source": "w", "target": "j", "shape": [[-100, 0], [0, 0]]},
            {"id": "east", "source": "j", "target": "e", "shape": [[0, 0], [100, 0]]},
            {"id": "north", "source": "n", "target": "j", "shape": [[0, 100], [0, 0]]},
            {"id": "south", "source": "j", "target": "s", "shape": [[0, 0], [0, -100]]}]})
        engine = TrafficEngine(network=network)
        engine.configure(traffic_density="none", closed_lanes=["eastf"], signal_plans={"j": {"mode": "all_way_stop"}})
        engine.start(10)
        blocked = engine.add_vehicle(["westf", "eastf"])
        free = engine.add_vehicle(["northf", "southf"])
        for car in (blocked, free):
            car.position = network.lanes[car.lane_id].length-car.length/2
        blocked.stop_arrival, free.stop_arrival = 0, .1
        free_position = free.position
        engine.step(20)
        self.assertIsNone(blocked.reserved_junction)
        self.assertEqual(free.reserved_junction, "j")
        self.assertGreater(free.position, free_position)

    def test_rl_holds_preserve_other_junctions_and_reject_impossible_timing(self):
        node = self.engine.controlled_junction
        other = next(j for j in self.engine.network.intersections if j != node)
        self.engine.configure(traffic_density="none", signal_plans={
            node: {"minimum_green": 15, "green_seconds": 16, "maximum_green": 20},
            other: {"minimum_green": 6, "green_seconds": 8}})
        self.engine.start(30)
        with self.assertRaisesRegex(ValueError, "maximum green"):
            self.engine.configure_rl_control(minimum_green_hold=30)
        self.assertFalse(self.engine.rl_control_enabled)
        self.engine.configure_rl_control(minimum_green_hold=10)
        self.assertEqual(self.engine.signals[node].minimum_green, 15)
        self.assertEqual(self.engine.signals[other].minimum_green, 6)
        action = "SERVE_"+self.engine.signals[node].family.upper()
        self.assertEqual(self.engine.apply_rl_action(action, other)["reason"], "uncontrolled_junction")
        self.engine.apply_rl_action(action)
        self.engine.step()
        self.assertEqual(self.engine._last_metrics["policy_decisions"], 1)
        self.assertEqual(self.engine.experiment_metadata()["last_policy_decision"]["action"], action)
        self.engine.stop()
        self.engine.start(30)
        self.assertEqual(self.engine.signals[node].minimum_green, 15)

    def test_render_frame_keeps_disruptions_and_discloses_entity_limits(self):
        lane = next(iter(self.engine.network.lanes))
        self.engine.configure(closed_lanes=[lane])
        self.engine.start(1)
        frame = build_render_frame(self.engine.to_dict())
        self.assertEqual(frame["visual"]["closed_lanes"], [lane])
        self.assertEqual(frame["vehicle_count"], len(self.engine.vehicles))
        self.assertIn("vehicles", frame["render_limits"])


if __name__ == "__main__":
    unittest.main()
