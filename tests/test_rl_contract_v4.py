"""RL contract v4 and the native-7 engine: phase-slot actions, a 20-value observation, phase-plan checks (plan Task 17)."""
import json
import subprocess
import sys
from pathlib import Path

import pytest

from simulation.model_contract import native_contract, phase_plan, validate_metadata
from simulation.network_registry import engine_for_scenario, load_registered_network
from simulation.rl_state import extract_rl_snapshot
from simulation.traffic_engine import ENGINE_VERSION, RL_SERVICE_ACTIONS, phase_slots

SITE = "tagum_site_a"
NETWORK = load_registered_network(SITE)
JUNCTION = NETWORK.intersections[0]
NS_EW = [["north", "south"], ["east", "west"], "pedestrian"]
EW_NS = [["east", "west"], ["north", "south"], "pedestrian"]
SINGLES = ["north", "east", "south", "west", "pedestrian"]
ROOT = Path(__file__).resolve().parents[1]


def engine_with(order=None, *, rl=True, greens=None):
    plan = {} if order is None else {"phase_order": order}
    if greens:
        plan["phase_greens"] = greens
    engine = engine_for_scenario({"network_id": SITE, "engine_config": {"signal_plans": {JUNCTION: plan} if plan else {}, "traffic_density": "low"}}, seed=7)
    if rl:
        engine.configure_rl_control()
    engine.start(120)
    return engine


class StubPolicy:
    controller_provenance = "ql"

    def __init__(self, metadata):
        self.artifact_metadata = metadata

    def predict(self, observation, info):
        raise AssertionError("not called")


def test_contract_names_and_engine_version():
    assert ENGINE_VERSION == "native-7"
    assert {key: value for key, value in native_contract(NETWORK).items() if key != "network_sha256"} == {
        "engine": "native-7", "observation": "native-local-20-v4", "actions": "phase-service-5-v2"}
    assert RL_SERVICE_ACTIONS == ("SERVE_PHASE_1", "SERVE_PHASE_2", "SERVE_PHASE_3", "SERVE_PHASE_4", "SERVE_PEDESTRIAN")


def test_native_6_models_are_refused():
    with pytest.raises(ValueError, match="Train a new model"):
        validate_metadata({"native_contract": {"engine": "native-6", "observation": "native-local-22-v3", "actions": "protected-service-5-v1",
                                               "network_sha256": NETWORK.fingerprint}}, NETWORK)


def test_the_observation_has_20_values_with_no_network_flags():
    for order in (None, NS_EW):
        snapshot = extract_rl_snapshot(engine_with(order))
        assert len(snapshot.observation) == 20 and all(0.0 <= value <= 1.0 for value in snapshot.observation)
        assert len(snapshot.ql_state) == 1 + 4 + 4 + 4 + 1


def test_the_phase_one_hot_follows_the_slot_of_the_current_phase():
    grouped = extract_rl_snapshot(engine_with(NS_EW))
    assert grouped.observation[:5] == [1.0, 0.0, 0.0, 0.0, 0.0]
    swapped = extract_rl_snapshot(engine_with(EW_NS))
    assert swapped.observation[:5] == [1.0, 0.0, 0.0, 0.0, 0.0]  # slot 1 is whatever the plan serves first


def test_phase_slots_are_vehicle_phases_then_the_walk_phase():
    assert phase_slots(engine_with(NS_EW).signals[JUNCTION]) == ["north+south", "east+west", None, None, "pedestrian"]
    assert phase_slots(engine_with(None).signals[JUNCTION]) == ["north", "east", "south", "west", "pedestrian"]


def test_the_mask_follows_the_phase_slots():
    engine = engine_with(NS_EW)
    engine.step(110)  # past the RL minimum green hold
    snapshot = extract_rl_snapshot(engine)
    assert snapshot.valid_action_mask == (1, 1, 0, 0, 1)


def test_serve_phase_2_requests_the_second_group_and_a_missing_slot_is_refused():
    engine = engine_with(NS_EW)
    engine.step(110)
    assert engine.apply_rl_action("SERVE_PHASE_2")["applied"] is True
    assert engine.signals[JUNCTION].pending == "east+west"
    assert engine.apply_rl_action("SERVE_PHASE_3") == {"applied": False, "reason": "unavailable_phase"}


def test_default_plans_keep_the_compass_order_in_the_slots():
    engine = engine_with(None)
    engine.step(110)
    assert engine.apply_rl_action("SERVE_PHASE_3")["applied"] is True
    assert engine.signals[JUNCTION].pending == "south"


def trained(order, **kwargs):
    engine = engine_with(order, rl=False, **kwargs)
    return phase_plan(engine)


def test_a_model_is_refused_when_the_phase_order_differs():
    model = StubPolicy({"native_contract": native_contract(NETWORK), "phase_plan": trained(NS_EW)})
    with pytest.raises(ValueError, match="Selected model was trained for phases .* this scenario uses"):
        engine_with(EW_NS, rl=False).set_runtime_policy(model)


def test_a_model_without_a_recorded_phase_plan_is_refused():
    with pytest.raises(ValueError, match="phase plan"):
        engine_with(NS_EW, rl=False).set_runtime_policy(StubPolicy({"native_contract": native_contract(NETWORK)}))


def test_a_model_accepts_different_green_times_for_the_same_phases():
    model = StubPolicy({"native_contract": native_contract(NETWORK), "phase_plan": trained(NS_EW)})
    engine_with(NS_EW, rl=False, greens=[30, 20, 10]).set_runtime_policy(model)


def test_the_phase_plan_names_the_junction_and_the_keys():
    assert trained(NS_EW) == {"junction": JUNCTION, "phase_keys": ["north+south", "east+west", "pedestrian"]}
    assert trained(None) == {"junction": JUNCTION, "phase_keys": ["north", "east", "south", "west", "pedestrian"]}


def test_training_metadata_records_the_phase_plan(tmp_path):
    scenario = tmp_path / "scenario.json"
    scenario.write_text(json.dumps({"network_id": SITE, "network_sha256": NETWORK.fingerprint, "name": "Synthetic",
                                    "engine_config": {"traffic_density": "low", "signal_plans": {JUNCTION: {"phase_order": NS_EW}}}}), encoding="utf-8")
    output = tmp_path / "ql.json"
    result = subprocess.run([sys.executable, "tools/train_ql.py", "--scenario-file", str(scenario), "--episodes", "2", "--warmup-seconds", "0",
                             "--evaluation-seconds", "5", "--max-steps-per-episode", "1", "--checkpoint-every", "0", "--skip-db",
                             "--synthetic-smoke-test", "--output", str(output)], cwd=ROOT, capture_output=True, text=True, timeout=180)
    assert result.returncode == 0, result.stderr + result.stdout
    metadata = json.loads(output.read_text(encoding="utf-8"))["metadata"]
    assert metadata["phase_plan"] == {"junction": JUNCTION, "phase_keys": ["north+south", "east+west", "pedestrian"]}
    assert metadata["native_contract"]["engine"] == "native-7"
