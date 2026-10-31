"""Grouped signal phases: opposite approaches share a green (plan Task 13, design 0.8)."""
import unittest

from simulation.scenario_config import DEFAULTS, validate_config
from tests.mixed_traffic_helpers import assert_never_overlap, busy_engine, junction_network, started_engine

GROUPED = {"signal_plans": {"j": {"phase_order": [["north", "south"], ["east", "west"], "pedestrian"]}}}


def car(time_s, source, destination):
    return {"time": time_s, "source": source, "destination": destination, "vehicle_type": "car"}


class GroupedPhaseTests(unittest.TestCase):
    def test_opposite_approaches_get_green_together(self):
        engine = started_engine(junction_network(), trips=[car(0, "n", "s"), car(0, "s", "n")], routing_mode="static", **GROUPED)
        signal = engine.signals["j"]
        both_inside_under_one_green = False
        for _ in range(2400):
            engine.step()
            reserved = engine.reservations.get("j", set())
            if len(reserved) == 2 and signal.phase == "NORTH+SOUTH_GREEN":
                both_inside_under_one_green = True
                break
        self.assertTrue(both_inside_under_one_green, "north and south never entered during their shared green")

    def test_a_group_serves_every_approach_in_it_and_no_others(self):
        engine = started_engine(junction_network(), **GROUPED)
        signal = engine.signals["j"]
        self.assertEqual(signal.approaches, ["north+south", "east+west", "pedestrian"])
        self.assertEqual(signal.phase, "NORTH+SOUTH_GREEN")
        self.assertEqual([signal.serves(name) for name in ("north", "south", "east", "west", "pedestrian")], [True, True, False, False, False])

    def test_a_left_turn_waits_for_oncoming_through_traffic(self):
        engine = started_engine(junction_network(), trips=[car(0, "s", "n"), car(1, "n", "e")], routing_mode="static", **GROUPED)
        reserved_at = {}
        for _ in range(3000):
            engine.step()
            for vehicle in engine.vehicles.values():
                if vehicle.reserved_junction:
                    reserved_at.setdefault(vehicle.id, engine.simulation_time)
            assert_never_overlap(self, engine, 0)
        through, turner = "car-1", "car-2"
        self.assertIn(through, reserved_at)
        self.assertIn(turner, reserved_at)
        self.assertGreaterEqual(reserved_at[turner], reserved_at[through])
        self.assertEqual(engine.completed, 2)

    def test_no_overlap_with_grouped_phases_under_load(self):
        assert_never_overlap(self, busy_engine(junction_network(), density="medium", **GROUPED), 3000)

    def test_each_approach_must_appear_exactly_once(self):
        for order in ([["north", "south"], ["north", "east"], "west", "pedestrian"], [["north", "south"], ["east", "west"]],
                      [["north"], ["south", "east", "west"], "pedestrian"], [["north", "south"], ["east", "west", "pedestrian"]]):
            with self.assertRaisesRegex(ValueError, "phase_order must contain every available approach and pedestrian exactly once"):
                validate_config(DEFAULTS, {"signal_plans": {"j": {"phase_order": order}}}, junction_network())

    def test_plans_listing_single_approaches_load_unchanged(self):
        plan = {"phase_order": ["north", "east", "south", "west", "pedestrian"]}
        self.assertEqual(validate_config(DEFAULTS, {"signal_plans": {"j": plan}}, junction_network())["signal_plans"]["j"]["phase_order"], plan["phase_order"])
        grouped = validate_config(DEFAULTS, GROUPED, junction_network())["signal_plans"]["j"]["phase_order"]
        self.assertEqual(grouped, GROUPED["signal_plans"]["j"]["phase_order"])

    def test_rl_control_is_refused_on_grouped_phases_until_the_phase_slot_contract(self):
        from simulation.traffic_engine import TrafficEngine
        engine = TrafficEngine(seed=7, network=junction_network())
        engine.configure(**GROUPED)
        with self.assertRaisesRegex(ValueError, "grouped phases"):
            engine.configure_rl_control()


if __name__ == "__main__":
    unittest.main()
