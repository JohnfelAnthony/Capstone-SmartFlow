import io
import json
import os
from zipfile import ZipFile

import pytest

os.environ.setdefault("SMARTFLOW_SECRET_KEY", "desktop-model-test-only")

from desktop.model_import import import_model, inspect_model
from simulation.model_contract import native_contract, phase_plan_for_scenario
from simulation.ql_agent import TabularQLearningAgent
from simulation.traffic_engine import RL_SERVICE_ACTIONS


def test_ql_import_registers_once_and_refuses_old_engine(tmp_path, monkeypatch):
    import config
    import database

    monkeypatch.setattr(config, "DB_PATH", str(tmp_path / "library.db"))
    monkeypatch.setenv("SMARTFLOW_DATA_DIR", str(tmp_path))
    database.init_db()
    model = TabularQLearningAgent(action_count=len(RL_SERVICE_ACTIONS)).to_artifact(metadata={"scenario": {}})
    content = json.dumps(model).encode()
    first = import_model("example.json", content, None)
    second = import_model("renamed.json", content, None)
    assert first["algorithm"] == "ql"
    assert second == {**first, "already_imported": True}
    model["metadata"]["native_contract"]["engine"] = "native-13"
    with pytest.raises(ValueError, match="current Python engine"):
        import_model("old.json", json.dumps(model).encode(), None)
    assert len(database.list_rl_models()) == 1


@pytest.mark.parametrize(("algorithm", "implementation", "marker"), [
    ("dql", "DQN", "exploration_initial_eps"), ("ppo", "PPO", "clip_range"),
])
def test_neural_algorithm_detection_reads_archive_structure_without_deserializing(algorithm, implementation, marker):
    stream = io.BytesIO()
    with ZipFile(stream, "w") as archive:
        archive.writestr("data", json.dumps({marker: 0.2}))
        archive.writestr("policy.pth", b"fixture, not a serialized policy")
        archive.writestr("_stable_baselines3_version", "2.8.0")
    metadata = {
        "scenario": {}, "native_contract": native_contract(), "phase_plan": phase_plan_for_scenario({}),
        "algorithm": algorithm, "implementation": "stable-baselines3." + implementation,
    }
    assert inspect_model("sample.zip", stream.getvalue(), json.dumps(metadata).encode())[0] == algorithm
    metadata["phase_plan"]["phase_keys"].reverse()
    with pytest.raises(ValueError, match="phase order"):
        inspect_model("sample.zip", stream.getvalue(), json.dumps(metadata).encode())
