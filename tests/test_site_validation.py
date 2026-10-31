"""Per-site calibration, observed-versus-simulated measures and the validation gate (plan Task 26, design 0.15)."""
import copy
import json
import math

import pytest

import database
from simulation import traffic_engine
from simulation.footprints import state_digest
from simulation.network_registry import engine_for_scenario, load_registered_network
from simulation.scenario_config import (SITE_CALIBRATION_DEFAULTS, VEHICLE_TYPES, resolve_site_calibration,
                                        site_calibration_sha256, validate_config, DEFAULTS)
from simulation.traffic_engine import TrafficEngine
from tests.mixed_traffic_helpers import busy_engine, junction_network


def calibration(site="tagum_site_a", **changes):
    value = {"schema_version": 1, "network_id": site, "first_come_approach_speed_mps": 5.5, "approach_zone_m": 35.0,
             "turn_speed_mps": 4.0, "class_speed_factors": {name: spec["speed_factor"] for name, spec in VEHICLE_TYPES.items()}}
    return {**value, **changes}


# --- Saved per-site calibration -------------------------------------------------------------------------------------

def test_absent_calibration_resolves_to_the_existing_constants_and_a_stable_hash():
    resolved = resolve_site_calibration(None, "tagum_site_a")
    assert resolved["approach_zone_m"] == traffic_engine.APPROACH_ZONE_M == 30.0
    assert resolved["first_come_approach_speed_mps"] == traffic_engine.FIRST_COME_APPROACH_SPEED_MPS == 4.0
    assert resolved["turn_speed_mps"] == traffic_engine.TURN_SPEED_MPS == 5.0
    assert resolved["class_speed_factors"] == {name: spec["speed_factor"] for name, spec in VEHICLE_TYPES.items()}
    assert site_calibration_sha256(resolved) == site_calibration_sha256(resolve_site_calibration(None, "tagum_site_a"))
    assert site_calibration_sha256(resolved) != site_calibration_sha256(resolve_site_calibration(calibration(), "tagum_site_a"))


@pytest.mark.parametrize("change, message", [
    ({"network_id": "tagum_site_b"}, "another site"),
    ({"approach_zone_m": 0}, "approach_zone_m"),
    ({"turn_speed_mps": -1}, "turn_speed_mps"),
    ({"first_come_approach_speed_mps": float("nan")}, "first_come_approach_speed_mps"),
    ({"first_come_approach_speed_mps": float("inf")}, "first_come_approach_speed_mps"),
    ({"class_speed_factors": {"car": 1.0}}, "all five"),
    ({"class_speed_factors": {**{n: 1.0 for n in VEHICLE_TYPES}, "pedicab": 1.0}}, "all five"),
    ({"class_speed_factors": {**{n: 1.0 for n in VEHICLE_TYPES}, "bus": 0}}, "class_speed_factors"),
    ({"schema_version": 2}, "schema_version"),
    ({"surprise": 1}, "Unknown"),
])
def test_invalid_calibration_is_rejected(change, message):
    with pytest.raises(ValueError, match=message):
        resolve_site_calibration(calibration(**change), "tagum_site_a")


def test_the_scenario_validator_keeps_the_complete_object_and_rejects_another_site():
    network = load_registered_network("tagum_site_a")
    kept = validate_config(DEFAULTS, {"site_calibration": calibration()}, network)["site_calibration"]
    assert kept == calibration()
    with pytest.raises(ValueError, match="another site"):
        validate_config(DEFAULTS, {"site_calibration": calibration("tagum_site_b")}, network)
    assert "site_calibration" not in validate_config(DEFAULTS, {}, network)


def test_calibration_changes_this_engine_only_and_never_the_module_defaults():
    site_a, site_b = load_registered_network("tagum_site_a"), load_registered_network("tagum_site_b")
    plain = TrafficEngine(seed=101, network=site_a)
    tuned = TrafficEngine(seed=101, network=site_b)
    tuned.configure(site_calibration=calibration("tagum_site_b", approach_zone_m=50.0, turn_speed_mps=3.0))
    assert tuned.site_calibration["approach_zone_m"] == 50.0
    assert plain.site_calibration["approach_zone_m"] == 30.0
    assert (traffic_engine.APPROACH_ZONE_M, traffic_engine.TURN_SPEED_MPS) == (30.0, 5.0)


def test_calibrated_values_reach_the_behaviour_they_name():
    engine = TrafficEngine(seed=7, network=junction_network())
    engine.driver_variation_scale = 0
    factors = {name: spec["speed_factor"] for name, spec in VEHICLE_TYPES.items()} | {"motorcycle": 0.5}
    engine.configure(traffic_density="none", pedestrian_density="none", site_calibration=calibration("test_cross", class_speed_factors=factors, turn_speed_mps=3.0))
    engine.start(60)
    assert engine.add_vehicle(["wf", "er"], vehicle_type="motorcycle").speed_factor == 0.5
    assert engine._movement_speed("wf", "nr") == 3.0  # a turn takes the calibrated turn speed
    assert engine._movement_speed("wf", "er") == engine.network.lanes["wf"].speed  # a through movement keeps road speed


def test_an_unchanged_calibration_leaves_signalized_and_first_come_results_unchanged():
    def digest(**config):
        return state_digest(busy_engine(junction_network(), seed=101, density="medium", **config), 120.0)
    defaults = {name: value for name, value in SITE_CALIBRATION_DEFAULTS.items()}
    explicit = calibration("test_cross", class_speed_factors={name: spec["speed_factor"] for name, spec in VEHICLE_TYPES.items()}, **defaults)
    assert digest() == digest(site_calibration=explicit)
    first_come = {"signal_plans": {"j": {"mode": "first_come"}}}
    assert digest(**first_come) == digest(site_calibration=explicit, **first_come)


def test_the_resolved_hash_travels_with_the_run_and_the_saved_scenario(tmp_path, monkeypatch):
    import config
    monkeypatch.setattr(config, "DB_PATH", str(tmp_path / "calibration.db"))
    database.init_db()
    saved = calibration()
    scenario_id = database.create_scenario("Calibrated Site A", network_id="tagum_site_a", engine_config={"site_calibration": saved})
    scenario = database.get_scenario_by_id(scenario_id)
    assert json.loads(scenario["engine_config"])["site_calibration"] == saved
    engine = engine_for_scenario(scenario, seed=101)
    metadata = engine.experiment_metadata()
    assert metadata["site_calibration_sha256"] == site_calibration_sha256(resolve_site_calibration(saved, "tagum_site_a"))
    assert metadata["config"]["site_calibration"] == saved
    uncalibrated = TrafficEngine(seed=101, network=load_registered_network("tagum_site_a")).experiment_metadata()
    assert uncalibrated["site_calibration_sha256"] == site_calibration_sha256(resolve_site_calibration(None, "tagum_site_a"))
