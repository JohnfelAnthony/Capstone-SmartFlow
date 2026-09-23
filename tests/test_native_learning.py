"""Small real training/save/load checks, not evidence of policy quality."""
import tempfile
import unittest
from pathlib import Path

import torch
from stable_baselines3.common.env_checker import check_env

from simulation.dql_training import DQLTrainingConfig, train_deep_q_learning
from simulation.ppo_training import PPOTrainingConfig, train_ppo
from simulation.ql_agent import TabularQLearningAgent
from simulation.ql_training import train_tabular_q_learning
from simulation.rl_env import SmartFlowRLEnv
from simulation.rl_policy_runtime import load_runtime_policy
from simulation.traffic_engine import TrafficEngine


class NativeLearningTests(unittest.TestCase):
    @staticmethod
    def environment(algorithm="ql"):
        return SmartFlowRLEnv(scenario={"traffic_density": "medium"}, warmup_seconds=0,
                              evaluation_seconds=12, decision_interval_seconds=1,
                              controller_provenance=algorithm)

    def test_gym_contract_and_ql_training(self):
        env = self.environment()
        try:
            check_env(env, warn=True)
        finally:
            env.close()
        agent = TabularQLearningAgent(action_count=5)
        results = train_tabular_q_learning(env_factory=self.environment, agent=agent, episodes=2, seed_set=(1, 2))
        self.assertEqual(len(results), 2)
        self.assertTrue(all(result.truncated for result in results))
        self.assertGreater(agent.state_count, 0)
        update = agent.update((0,), 0, 2, (1,), terminated=True)
        self.assertEqual(update.target, 2)

    def test_dql_and_ppo_train_save_load_and_drive_native_engine(self):
        torch.set_num_threads(1)
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            dql_path, _ = train_deep_q_learning(env_factory=lambda: self.environment("dql"),
                config=DQLTrainingConfig(total_timesteps=24, learning_starts=4, batch_size=4, buffer_size=100), output_path=root/"dql.zip")
            ppo_path, _ = train_ppo(env_factory=lambda: self.environment("ppo"),
                config=PPOTrainingConfig(total_timesteps=24, n_steps=8, batch_size=4, n_epochs=1), output_path=root/"ppo.zip")
            for kind, path in (("dql", dql_path), ("ppo", ppo_path)):
                with self.subTest(algorithm=kind):
                    policy = load_runtime_policy(kind, path)
                    engine = TrafficEngine()
                    engine.set_runtime_policy(policy, decision_interval=1)
                    engine.start(16)
                    engine.step(160)
                    self.assertEqual(engine.status, "completed")
                    self.assertEqual(engine.controller_provenance, kind)
                    self.assertGreater(engine.next_policy_time, 15)


if __name__ == "__main__":
    unittest.main()
