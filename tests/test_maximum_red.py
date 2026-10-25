"""Bounded wait for green under any controller (engine fix plan P1-4)."""
import unittest

from simulation.traffic_engine import TrafficEngine
from tests import test_native_traffic_contract as contract


def cross_engine(**config):
    engine = TrafficEngine(seed=11, network=contract.cross_network())
    engine.configure(pedestrian_density="none", routing_mode="static", **config)
    engine.start(900)
    return engine


def longest_red_for_demanded_approaches(engine, seconds, action=None):
    """Longest time any approach with waiting vehicles went without green."""
    signal = engine.signals["j"]
    last_green = {approach: engine.simulation_time for approach in signal.approaches if approach != "pedestrian"}
    longest = 0.0
    for tick in range(int(seconds/0.1)):
        if action and tick % 50 == 0:
            engine.apply_rl_action(action)
        engine.step()
        if signal.stage == "green" and signal.family in last_green:
            last_green[signal.family] = engine.simulation_time
        demanded = {engine.network.lanes[vehicle.lane_id].approach for vehicle in engine.vehicles.values()
                    if not vehicle.connector and engine.network.lanes[vehicle.lane_id].target == "j"}
        for approach in demanded & last_green.keys():
            longest = max(longest, engine.simulation_time-last_green[approach])
    return longest


class MaximumRedTests(unittest.TestCase):
    def test_policy_that_always_asks_for_north_cannot_starve_other_approaches(self):
        engine = cross_engine(traffic_density="medium")
        engine.configure_rl_control(decision_interval=5, minimum_green_hold=10)
        signal = engine.signals["j"]
        longest = longest_red_for_demanded_approaches(engine, 600, action="SERVE_NORTH")
        # Requested at 120 s; served after any other overdue approach's minimum green and clearance (before P1-4: 305 s).
        allowance = (len(signal.approaches)-1)*(signal.minimum_green+signal.yellow_seconds+signal.all_red_seconds)
        self.assertLessEqual(longest, 120+allowance)
        self.assertGreater(engine.safety_overrides, 0)

    def test_default_cap_never_interrupts_a_legal_fixed_time_plan(self):
        engine = cross_engine(traffic_density="medium", signal_plans={"j": {"green_seconds": 40, "maximum_green": 60}})
        signal = engine.signals["j"]
        # Five services of 40 s green: an approach waits 4 x 44 + 41 - 40 + ... = cycle - green = 177 s for green.
        self.assertEqual(signal.maximum_red, 4*44+41-40)
        longest_red_for_demanded_approaches(engine, 600)
        self.assertEqual(engine.safety_overrides, 0)

    def test_default_cap_is_120_seconds_for_the_default_plan(self):
        self.assertEqual(cross_engine(traffic_density="none").signals["j"].maximum_red, 120)

    def test_explicit_cap_below_the_plans_own_red_is_rejected(self):
        engine = TrafficEngine(seed=11, network=contract.cross_network())
        with self.assertRaisesRegex(ValueError, "maximum_red_seconds"):
            engine.configure(signal_plans={"j": {"green_seconds": 40, "maximum_green": 60, "maximum_red_seconds": 120}})
        engine.configure(signal_plans={"j": {"maximum_red_seconds": 90}})
        self.assertEqual(engine.signals["j"].maximum_red, 90)


if __name__ == "__main__":
    unittest.main()
