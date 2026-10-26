"""reward_v3: local to the controlled junction and computed per decision interval (engine fix plan P1-5)."""
import dataclasses
import math
import unittest

from simulation.rl_reward import calculate_reward
from simulation.rl_state import MAX_PEDESTRIAN_WAITING, MAX_QUEUE_COUNT, extract_rl_snapshot
from tests import test_native_traffic_contract as contract


class RewardV3Tests(unittest.TestCase):
    def setUp(self):
        engine = contract.NativeTrafficContractTests.engine(self)
        self.base = dataclasses.replace(extract_rl_snapshot(engine), simulation_time=100.0, junction_stopped_seconds=0.0,
                                        junction_passages=0, total_phase_switches=0, pedestrian_waiting_count=0,
                                        queue_by_approach={"north": 0, "east": 0, "south": 0, "west": 0})

    def later(self, seconds=5.0, **changes):
        return dataclasses.replace(self.base, simulation_time=self.base.simulation_time+seconds, **changes)

    def test_terms_come_from_the_interval_at_the_controlled_junction(self):
        reward = calculate_reward(self.base, self.later(junction_stopped_seconds=60.0, junction_passages=2,
                                                        queue_by_approach={"north": 6, "east": 0, "south": 3, "west": 0},
                                                        pedestrian_waiting_count=4))
        # 60 stopped vehicle-seconds over 5 s is 12 stopped vehicles, 3 per approach.
        self.assertAlmostEqual(reward.delay_penalty, 3/MAX_QUEUE_COUNT, places=6)
        self.assertAlmostEqual(reward.queue_penalty, 0.5*6/MAX_QUEUE_COUNT, places=6)
        self.assertGreater(reward.discharge_bonus, 0)
        self.assertAlmostEqual(reward.pedestrian_penalty, 0.25*4/MAX_PEDESTRIAN_WAITING, places=6)
        self.assertNotIn("max_queue_penalty", reward.to_dict())

    def test_old_delay_does_not_carry_into_later_intervals(self):
        stopped = self.later(junction_stopped_seconds=600.0)
        unchanged = dataclasses.replace(stopped, simulation_time=stopped.simulation_time+5)
        self.assertEqual(calculate_reward(stopped, unchanged).delay_penalty, 0)

    def test_more_discharge_and_less_delay_score_higher(self):
        good = calculate_reward(self.base, self.later(junction_stopped_seconds=10.0, junction_passages=2))
        bad = calculate_reward(self.base, self.later(junction_stopped_seconds=80.0, junction_passages=0))
        self.assertGreater(good.total, bad.total)

    def test_zero_length_interval_is_finite(self):
        reward = calculate_reward(self.base, self.base)
        self.assertTrue(all(math.isfinite(value) for value in reward.to_dict().values()))


if __name__ == "__main__":
    unittest.main()
