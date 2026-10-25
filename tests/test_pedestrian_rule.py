"""Fixed-time and RL follow the same pedestrian-phase rule (engine fix plan P1-3)."""
import unittest

from simulation.traffic_engine import Pedestrian, TrafficEngine
from tests import test_native_traffic_contract as contract


def cross_engine(plan=None):
    engine = TrafficEngine(seed=5, network=contract.cross_network())
    engine.configure(traffic_density="low", pedestrian_density="none", signal_plans={"j": plan or {}})
    engine.start(900)
    return engine


def pedestrian_green_starts(engine, seconds, action=None):
    """Times at which the pedestrian phase turned green."""
    signal, starts, was_green = engine.signals["j"], [], False
    for tick in range(int(seconds/0.1)):
        if action and tick % 50 == 0:
            engine.apply_rl_action(action)
        engine.step()
        is_green = signal.family == "pedestrian" and signal.stage == "green"
        if is_green and not was_green:
            starts.append(engine.simulation_time)
        was_green = is_green
    return starts


class PedestrianRuleTests(unittest.TestCase):
    def test_on_call_is_the_default_and_skips_the_phase_when_nobody_waits(self):
        engine = cross_engine()
        self.assertEqual(engine.signals["j"].pedestrian_phase, "on_call")
        self.assertEqual(pedestrian_green_starts(engine, 300), [])

    def test_on_call_serves_a_waiting_pedestrian_within_one_cycle(self):
        engine = cross_engine()
        pedestrian = Pedestrian("ped-test", "j")
        engine.pedestrians[pedestrian.id] = pedestrian
        engine.pedestrian_serial = 1
        starts = pedestrian_green_starts(engine, 120)
        self.assertTrue(starts)
        self.assertLessEqual(starts[0], 4*(14+3+1)+1)
        self.assertEqual(engine.completed_pedestrians, 1)

    def test_every_cycle_keeps_the_fixed_time_walk_phase_without_pedestrians(self):
        starts = pedestrian_green_starts(cross_engine({"pedestrian_phase": "every_cycle"}), 300)
        cycle = 4*(14+3+1)+(14+1)
        self.assertGreaterEqual(len(starts), 3)
        self.assertTrue(all(abs(later-earlier-cycle) < 0.2 for earlier, later in zip(starts, starts[1:])))

    def test_every_cycle_holds_rl_to_the_fixed_time_walk_interval(self):
        engine = cross_engine({"pedestrian_phase": "every_cycle"})
        engine.configure_rl_control(decision_interval=5, minimum_green_hold=10)
        signal = engine.signals["j"]
        starts = pedestrian_green_starts(engine, 600, action="SERVE_NORTH")
        own_red = 4*(14+3+1)+(14+1)-14
        allowance = (len(signal.approaches)-1)*(signal.minimum_green+signal.yellow_seconds+signal.all_red_seconds)
        self.assertGreaterEqual(len(starts), 3)
        gaps = [later-earlier for earlier, later in zip([0.0]+starts, starts)]
        self.assertLessEqual(max(gaps), own_red+allowance)

    def test_unknown_pedestrian_rule_is_rejected(self):
        engine = TrafficEngine(seed=5, network=contract.cross_network())
        with self.assertRaisesRegex(ValueError, "pedestrian_phase"):
            engine.configure(signal_plans={"j": {"pedestrian_phase": "sometimes"}})


if __name__ == "__main__":
    unittest.main()
