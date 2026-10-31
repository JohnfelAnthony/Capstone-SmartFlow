import pytest

from simulation.model_contract import native_contract, validate_metadata
from simulation.network_registry import engine_for_scenario, load_registered_network
from simulation.rl_env import SmartFlowRLEnv


def test_contract_is_bound_to_the_training_network():
    site = load_registered_network("tagum_site_a")
    assert native_contract(site)["network_sha256"] == site.fingerprint
    with pytest.raises(ValueError, match="not trained for the current Python engine and road network"):
        validate_metadata({"native_contract": native_contract(site)}, load_registered_network("tagum_site_b"))


def test_rl_environment_uses_scenario_network():
    env = SmartFlowRLEnv(scenario={"network_id": "tagum_site_a", "engine_config": {"traffic_density": "low"}}, seed=11, warmup_seconds=0, evaluation_seconds=5)
    try:
        observation, _ = env.reset(seed=11)
        assert env.engine.network.id == "tagum_site_a"
        assert len(observation) == 22
    finally:
        env.close()


def test_site_a_policy_cannot_control_site_b():
    site_a = load_registered_network("tagum_site_a")
    engine = engine_for_scenario({"network_id": "tagum_site_b", "engine_config": {}})
    class Policy:
        artifact_metadata = {"native_contract": native_contract(site_a)}
        def predict(self, observation, info):
            return None
    with pytest.raises(ValueError, match="not trained for the current Python engine and road network"):
        engine.set_runtime_policy(Policy())


def test_ql_artifact_round_trip_preserves_site_contract(tmp_path):
    from simulation.ql_agent import TabularQLearningAgent
    from simulation.rl_policy_runtime import load_runtime_policy
    site_a = load_registered_network("tagum_site_a")
    site_b = load_registered_network("tagum_site_b")
    artifact = tmp_path / "site_ql.json"
    agent = TabularQLearningAgent(action_count=5)
    agent.save(artifact, metadata={"scenario": {"network_id": site_a.id, "engine_config": {}}})
    policy = load_runtime_policy("ql", artifact, network=site_a)
    assert policy.artifact_metadata["native_contract"]["network_sha256"] == site_a.fingerprint
    with pytest.raises(ValueError, match="not trained for the current Python engine and road network"):
        load_runtime_policy("ql", artifact, network=site_b)


def test_two_episode_synthetic_smoke_ql_training_preserves_site_identity(tmp_path):
    import json
    import subprocess
    import sys
    from pathlib import Path
    site = load_registered_network("tagum_site_a")
    scenario = tmp_path / "scenario.json"
    scenario.write_text(json.dumps({"network_id": site.id, "network_sha256": site.fingerprint,
                                    "name": "Synthetic test", "engine_config": {"traffic_density": "low"}}), encoding="utf-8")
    output = tmp_path / "site_ql.json"
    root = Path(__file__).resolve().parents[1]
    result = subprocess.run([sys.executable, "tools/train_ql.py", "--scenario-file", str(scenario),
                             "--episodes", "2", "--warmup-seconds", "0", "--evaluation-seconds", "5",
                             "--max-steps-per-episode", "1", "--checkpoint-every", "0", "--skip-db", "--synthetic-smoke-test", "--output", str(output)],
                            cwd=root, capture_output=True, text=True, timeout=120)
    assert result.returncode == 0, result.stderr + result.stdout
    artifact = json.loads(output.read_text(encoding="utf-8"))
    assert artifact["metadata"]["native_contract"]["network_sha256"] == site.fingerprint


def test_site_training_through_the_api_needs_an_open_validation_gate(monkeypatch):
    import database
    from services.training_settings import prepare_settings
    site = load_registered_network("tagum_site_a")
    scenario = {"id": 7, "name": "Site", "network_id": site.id, "network_sha256": site.fingerprint, "engine_config": {}, "is_archived": 0}
    monkeypatch.setattr(database, "get_scenario_by_id", lambda scenario_id: scenario)
    with pytest.raises(ValueError, match="independent validation gate"):
        prepare_settings({"scenario_id": 7})


def test_training_worker_validates_model_against_job_network(tmp_path, monkeypatch):
    import database
    from services import rl_training_service as worker
    from simulation.ql_agent import TabularQLearningAgent

    site = load_registered_network("tagum_site_a")
    artifact = tmp_path / "site_ql.json"
    TabularQLearningAgent(action_count=5).save(
        artifact, metadata={"scenario": {"network_id": site.id, "engine_config": {}}}
    )
    monkeypatch.setattr(worker, "_process_lines", lambda *args: iter([
        f"Saved QL model artifact: {artifact}", "Registered rl_models.id: 17"
    ]))
    monkeypatch.setattr(database, "get_rl_model_by_id", lambda _: {"id": 17})
    monkeypatch.setattr(database, "update_rl_training_job", lambda *a, **k: None)
    monkeypatch.setattr(database, "update_rl_training_job_item", lambda *a, **k: None)
    item = {"id": 1, "algorithm": "ql", "command_json": "[]", "sequence_index": 0}
    settings = {"scenario_snapshot": {"network_id": site.id}}
    assert worker._run_command_item(1, item, tmp_path / "log", 1, settings) == str(artifact)
