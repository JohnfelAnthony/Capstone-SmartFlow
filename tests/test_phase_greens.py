"""A green time per signal phase (plan Task 14, design 0.8)."""
import unittest

from simulation.scenario_config import DEFAULTS, fixed_red_seconds, validate_config, walk_red_seconds
from tests.mixed_traffic_helpers import junction_network, started_engine

PLAN = {"phase_order": [["north", "south"], ["east", "west"], "pedestrian"], "phase_greens": [39, 23, 10], "pedestrian_phase": "every_cycle"}


class PhaseGreenTests(unittest.TestCase):
    def test_each_phase_uses_its_own_green(self):
        engine = started_engine(junction_network(), signal_plans={"j": PLAN})
        signal = engine.signals["j"]
        durations, last_index, started = {}, signal.index, 0.0
        for _ in range(int(85 / 0.1)):
            engine.step()
            if signal.stage == "green" and signal.index != last_index:
                if last_index is not None:
                    durations[last_index] = round(engine.simulation_time - started, 1)
                last_index, started = signal.index, engine.simulation_time
        # each vehicle phase lasts its own green plus yellow and all-red
        self.assertEqual([durations[index] for index in (0, 1)], [39.0 + 3.0 + 1.0, 23.0 + 3.0 + 1.0])
        self.assertEqual(signal.phase_greens, [39.0, 23.0, 10.0])

    def test_remaining_time_counts_down_the_current_phase_green(self):
        engine = started_engine(junction_network(), signal_plans={"j": PLAN})
        signal = engine.signals["j"]
        self.assertEqual(signal.current_green, 39.0)
        self.assertAlmostEqual(signal.remaining, 39.0)

    def test_fixed_red_uses_each_phase_green(self):
        # cycle = (39+1+3) + (23+1+3) = 70; vehicle reds are 31 and 47; the largest is returned
        self.assertEqual(fixed_red_seconds([["north", "south"], ["east", "west"]], 14, 3, 1, phase_greens=[39, 23]), 47.0)

    def test_plans_without_phase_greens_are_unchanged(self):
        # today's default: cycle 4x(14+1+3) + (14+1) = 87, red 87 - 14 = 73
        self.assertEqual(fixed_red_seconds(["north", "east", "south", "west", "pedestrian"], 14, 3, 1), 73.0)

    def test_maximum_red_check_uses_the_longest_vehicle_red(self):
        # cycle 70 + (10 + 1) = 81; vehicle reds 42 and 58; the walk red 71 is not counted
        self.assertEqual(fixed_red_seconds(PLAN["phase_order"], 14, 3, 1, phase_greens=PLAN["phase_greens"]), 58.0)
        validate_config(DEFAULTS, {"signal_plans": {"j": {**PLAN, "maximum_red_seconds": 60}}}, junction_network())
        with self.assertRaisesRegex(ValueError, "shorter than this plan's own fixed-time red"):
            validate_config(DEFAULTS, {"signal_plans": {"j": {**PLAN, "maximum_red_seconds": 50}}}, junction_network())

    def test_walk_interval_is_the_walk_phase_red(self):
        self.assertEqual(walk_red_seconds(PLAN["phase_order"], 14, 3, 1, phase_greens=PLAN["phase_greens"]), 71.0)
        engine = started_engine(junction_network(), signal_plans={"j": PLAN})
        self.assertEqual(engine.signals["j"].walk_interval, 71.0)

    def test_phase_greens_must_match_the_phases_and_stay_within_the_green_bounds(self):
        for greens in ([39, 23], [39, 23, 10, 5], [39, 23, 4], [39, 23, 61], [39, "x", 10], [39, 23, float("nan")]):
            with self.assertRaises(ValueError, msg=greens):
                validate_config(DEFAULTS, {"signal_plans": {"j": {**PLAN, "phase_greens": greens}}}, junction_network())


if __name__ == "__main__":
    unittest.main()
