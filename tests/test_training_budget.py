"""Default RL training budget and warmup (engine fix plan P1-7)."""
import importlib
import unittest

from services.rl_training_service import build_training_command
from simulation.dql_training import calculate_dql_timesteps
from simulation.rl_env import DEFAULT_EPISODE_SECONDS, DEFAULT_TRAINING_EPISODES, DEFAULT_WARMUP_SECONDS, SmartFlowRLEnv


class TrainingBudgetTests(unittest.TestCase):
    def test_default_budget_is_about_one_hundred_thousand_decisions_from_developed_traffic(self):
        decisions = calculate_dql_timesteps(episodes=DEFAULT_TRAINING_EPISODES, evaluation_seconds=DEFAULT_EPISODE_SECONDS,
                                            decision_interval_seconds=5.0)
        self.assertGreaterEqual(decisions, 100_000)
        self.assertGreaterEqual(DEFAULT_WARMUP_SECONDS, 300)

    def test_every_entry_point_uses_the_same_defaults(self):
        expected = {"episodes": DEFAULT_TRAINING_EPISODES, "warmup_seconds": DEFAULT_WARMUP_SECONDS,
                    "evaluation_seconds": DEFAULT_EPISODE_SECONDS}
        for module_name in ("tools.train_ql", "tools.train_dql", "tools.train_ppo"):
            with self.subTest(module=module_name):
                arguments = importlib.import_module(module_name)._build_parser().parse_args([])
                self.assertEqual({key: getattr(arguments, key) for key in expected}, expected)
        evaluation = importlib.import_module("tools.evaluate_controllers")._build_parser().parse_args([])
        self.assertEqual((evaluation.warmup_seconds, evaluation.duration_seconds), (DEFAULT_WARMUP_SECONDS, DEFAULT_EPISODE_SECONDS))
        command = build_training_command("dql", {})
        for flag, value in (("--episodes", str(DEFAULT_TRAINING_EPISODES)), ("--warmup-seconds", str(DEFAULT_WARMUP_SECONDS)),
                            ("--evaluation-seconds", str(DEFAULT_EPISODE_SECONDS))):
            self.assertEqual(command[command.index(flag)+1], value)
        environment = SmartFlowRLEnv()
        self.assertEqual((environment.warmup_seconds, environment.evaluation_seconds), (DEFAULT_WARMUP_SECONDS, DEFAULT_EPISODE_SECONDS))


if __name__ == "__main__":
    unittest.main()
