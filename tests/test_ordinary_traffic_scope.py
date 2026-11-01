"""The revised study cannot enable emergency traffic through alternate inputs."""
import copy
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock, patch

from simulation.traffic_engine import TrafficEngine, ENGINE_VERSION
from simulation.scenario_config import VEHICLE_TYPES
from simulation.rl_state import extract_rl_snapshot
from simulation.rl_reward import calculate_reward
from simulation.model_contract import native_contract, validate_metadata
from services.metric_definitions import METRIC_CATALOG
from services.scenario_migration import import_snapshot, native_snapshot, resolve_legacy_scenario, migration_report


class OrdinaryTrafficScopeTests(unittest.TestCase):
    def setUp(self):
        self.engine = TrafficEngine(seed=7)
        self.network = self.engine.network
        self.pair = next((a, b) for a in self.network.boundaries for b in self.network.boundaries
                         if a != b and self.network.route(a, b))

    def test_removed_inputs_are_rejected_atomically(self):
        original = copy.deepcopy(self.engine.config)
        trip = dict(time=0, source=self.pair[0], destination=self.pair[1], vehicle_type="emergency")
        for settings in ({"emergency_mode": "enabled"}, {"emergency_mode": "enabled (1 ambulance)"},
                         {"vehicle_mix": {"emergency": 1}}, {"trips": [trip]}):
            with self.subTest(settings=settings), self.assertRaises(ValueError):
                self.engine.configure(**settings)
            self.assertEqual(self.engine.config, original)
        with self.assertRaisesRegex(ValueError, "vehicle type"):
            self.engine.add_vehicle(self.network.route(*self.pair), vehicle_type="emergency")

    def test_legacy_disabled_scenario_normalizes_to_ordinary_traffic(self):
        self.engine.configure(emergency_mode="disabled", traffic_density="high")
        self.assertNotIn("emergency_mode", self.engine.config)
        self.engine.start(15)
        self.engine.step(150)
        state = self.engine.to_dict()
        self.assertTrue(self.engine.arrivals)
        self.assertEqual(set(VEHICLE_TYPES), {"car", "motorcycle", "tricycle", "bus", "truck"})
        self.assertTrue(all(arrival.vehicle_type in VEHICLE_TYPES for arrival in self.engine.arrivals))
        self.assertFalse(any("emergency" in key for key in state["metrics"]))
        self.assertNotIn("emergency_mode", state["scenario"])
        self.assertTrue(all("emergency" not in vehicle for vehicle in state["vehicles"]))

    def test_legacy_scope_cannot_be_hidden_by_native_envelope_or_override(self):
        trip = dict(time=0, source=self.pair[0], destination=self.pair[1], vehicle_type="emergency")
        for removed in ({"emergency_mode": "enabled"}, {"vehicle_mix": {"emergency": 1}}, {"trips": [trip]}):
            for identity in ({"network_id": self.network.id}, {"intersection_id": "tagum_1"}):
                scenario = {**identity, **removed, "engine_config": {"emergency_mode": "disabled"}}
                original = copy.deepcopy(scenario)
                for converter in (import_snapshot, native_snapshot, resolve_legacy_scenario):
                    with self.subTest(removed=removed, identity=identity, converter=converter.__name__):
                        with self.assertRaisesRegex(ValueError, "outside the study scope"):
                            converter(scenario)
                        self.assertEqual(scenario, original)
                self.assertEqual(migration_report([scenario])["scenarios"][0]["status"], "blocked")
        before = self.engine.to_dict()
        scenario = {"network_id": self.network.id, "emergency_mode": "enabled",
                    "engine_config": {"traffic_density": "high"}, "name": "Must not commit"}
        with self.assertRaisesRegex(ValueError, "outside the study scope"):
            self.engine.configure_from_scenario(scenario)
        self.assertEqual(self.engine.to_dict(), before)

    def test_disabled_legacy_native_snapshot_is_normalized_without_rewriting_source(self):
        scenario = {"network_id": self.network.id, "emergency_mode": "Disabled",
                    "engine_config": {"emergency_mode": "disabled", "vehicle_mix": {"bus": 1}}}
        original = copy.deepcopy(scenario)
        for converter in (import_snapshot, native_snapshot):
            result = converter(scenario)
            self.assertNotIn("emergency_mode", result)
            self.assertNotIn("emergency_mode", result["engine_config"])
            self.assertEqual(result["engine_config"]["vehicle_mix"], {"bus": 1})
        self.assertEqual(scenario, original)

    def test_observation_reward_and_artifact_contract_match_new_scope(self):
        snapshot = extract_rl_snapshot(self.engine)
        self.assertEqual(len(snapshot.observation), 20)
        self.assertEqual(len(snapshot.ql_state), 14)
        self.assertFalse(any("emergency" in key for key in vars(snapshot)))
        self.assertFalse(any("emergency" in key for key in calculate_reward(snapshot, snapshot).to_dict()))
        self.assertFalse(any("emergency" in item["key"] for item in METRIC_CATALOG["metrics"]))
        self.assertEqual(METRIC_CATALOG["engine_version"], ENGINE_VERSION)
        legacy = {**native_contract(), "engine": "native-3", "observation": "native-local-30-v1"}
        with self.assertRaisesRegex(ValueError, "Train a new model"):
            validate_metadata({"native_contract": legacy})
        validate_metadata({"native_contract": native_contract()})

    def test_old_models_are_rejected_by_inference_and_ql_resume_loaders(self):
        from simulation.ql_agent import TabularQLearningAgent
        from simulation.rl_policy_runtime import QLRuntimePolicy, DQLRuntimePolicy, PPORuntimePolicy
        from tools.train_ql import _load_resume_artifact
        legacy = {"native_contract": {**native_contract(), "engine": "native-3",
                                      "observation": "native-local-30-v1"}}
        with tempfile.TemporaryDirectory(dir=Path(__file__).resolve().parent) as directory:
            artifact = Path(directory) / "old.json"
            payload = TabularQLearningAgent(action_count=5).to_artifact()
            payload["metadata"] = legacy
            artifact.write_text(json.dumps(payload), encoding="utf-8")
            original = artifact.read_bytes()
            for loader in (QLRuntimePolicy.load, _load_resume_artifact):
                with self.subTest(loader=loader.__qualname__), self.assertRaisesRegex(ValueError, "Train a new model"):
                    loader(artifact)
            self.assertEqual(artifact.read_bytes(), original)
            neural = Path(directory) / "old.zip"
            neural.write_bytes(b"Unmodified historical artifact; must not reach deserialization")
            neural.with_suffix(".metadata.json").write_text(json.dumps(legacy), encoding="utf-8")
            for policy, model_name in ((DQLRuntimePolicy, "DQN"), (PPORuntimePolicy, "PPO")):
                with self.subTest(policy=policy.__name__), patch(f"simulation.rl_policy_runtime.{model_name}") as model:
                    with self.assertRaisesRegex(ValueError, "Train a new model"):
                        policy.load(neural)
                    model.load.assert_not_called()
            from simulation.dql_training import DQLTrainingConfig, train_deep_q_learning
            from simulation.ppo_training import PPOTrainingConfig, train_ppo
            for train, settings, module, model_name in (
                    (train_deep_q_learning, DQLTrainingConfig(total_timesteps=1), "dql_training", "DQN"),
                    (train_ppo, PPOTrainingConfig(total_timesteps=1), "ppo_training", "PPO")):
                environment = Mock()
                output = Path(directory) / (module + ".zip")
                with self.subTest(resume=module), patch(f"simulation.{module}.{model_name}") as model:
                    with self.assertRaisesRegex(ValueError, "Train a new model"):
                        train(env_factory=lambda: environment, config=settings,
                              output_path=output, resume_model_path=neural)
                    model.load.assert_not_called()
                    environment.close.assert_called_once()
                    self.assertFalse(output.exists())

    def test_native_3_recording_is_rejected_even_for_the_same_network(self):
        from simulation.timeline_engine import TimelinePlaybackEngine
        with tempfile.TemporaryDirectory(dir=Path(__file__).resolve().parent) as directory:
            path = Path(directory) / "historical.jsonl"
            frame = {**self.engine.to_dict(), "engine_version": "native-3"}
            path.write_text(json.dumps(frame) + "\n", encoding="utf-8")
            path.with_suffix(".manifest.json").write_text(json.dumps({"experiment": {
                "engine_version": "native-3", "network_sha256": self.network.fingerprint}}), encoding="utf-8")
            original = path.read_bytes()
            playback = TimelinePlaybackEngine(1, str(path))
            self.assertEqual(playback.status, "error")
            self.assertIn("incompatible", playback.last_error)
            self.assertEqual(path.read_bytes(), original)
