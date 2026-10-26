"""DQL and PPO act in the app exactly as in training (engine fix plan P1-6)."""
import unittest

import numpy as np

from simulation.rl_policy_runtime import DQLRuntimePolicy, PPORuntimePolicy
from simulation.rl_state import RL_SERVICE_ACTIONS
from tests import test_native_traffic_contract as contract


class FixedActionModel:
    """Stands in for an SB3 model that always chooses one action."""

    def __init__(self, action):
        self.action = action

    def predict(self, observation, deterministic=True):
        return np.array(self.action), None

    def predict_q_values(self, observation):
        return [1.0 if index == self.action else 0.0 for index in range(len(RL_SERVICE_ACTIONS))]


class RuntimeParityTests(unittest.TestCase):
    def test_masked_out_action_is_kept_as_the_policy_chose_it(self):
        blocked = 2
        mask = tuple(int(index != blocked) for index in range(len(RL_SERVICE_ACTIONS)))
        for policy_class in (DQLRuntimePolicy, PPORuntimePolicy):
            with self.subTest(policy=policy_class.__name__):
                prediction = policy_class(FixedActionModel(blocked)).predict(np.zeros(22, dtype=np.float32), {"valid_action_mask": mask})
                self.assertEqual(prediction.action, blocked)
                self.assertEqual(prediction.action_name, RL_SERVICE_ACTIONS[blocked])

    def test_app_records_the_request_and_the_engine_result(self):
        engine = contract.NativeTrafficContractTests.engine(self)
        engine.configure_rl_control(decision_interval=5, minimum_green_hold=10)
        requested = next(name for name in RL_SERVICE_ACTIONS if name != "SERVE_PEDESTRIAN"
                         and name.removeprefix("SERVE_").lower() != engine.signals["j"].family)
        engine.runtime_policy = PPORuntimePolicy(FixedActionModel(RL_SERVICE_ACTIONS.index(requested)))
        engine.step()
        decision = engine.last_policy_decision
        self.assertEqual(decision["action"], requested)
        self.assertIn("applied", decision)
        self.assertIn("reason", decision)


if __name__ == "__main__":
    unittest.main()
