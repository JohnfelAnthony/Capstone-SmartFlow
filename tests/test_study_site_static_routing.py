"""At the two study sites every path runs static routing (reroute around closures only) unless the scenario has a closure whose response is
'avoid jams'; the five-junction test network keeps adaptive routing.

A scenario saved or submitted as adaptive at a study site is not refused (every saved study-site scenario carries the old default):
it is normalised to static wherever the engine configuration is validated, and the stored config then says static. Only a scenario with a
closure set to "Use the side street and avoid jams" runs adaptive (tests/test_closure_responses.py).
"""
import json
from types import SimpleNamespace

import pytest

from simulation.network_registry import engine_for_scenario, load_registered_network
from simulation.scenario_config import DEFAULTS, validate_config
from simulation.traffic_engine import TrafficEngine

STUDY_SITES = ["tagum_site_a", "tagum_site_b"]
ADAPTIVE = {"network_id": None, "engine_config": {"traffic_density": "low", "routing_mode": "adaptive"}}


def saved_as_adaptive(network_id):
    return {**ADAPTIVE, "network_id": network_id}


@pytest.mark.parametrize("site", STUDY_SITES)
def test_a_new_engine_at_a_study_site_defaults_to_static(site):
    assert TrafficEngine(network=load_registered_network(site)).config["routing_mode"] == "static"


@pytest.mark.parametrize("site", STUDY_SITES)
def test_configure_adaptive_at_a_study_site_runs_static(site):
    engine = TrafficEngine(network=load_registered_network(site))
    engine.configure(routing_mode="adaptive")
    assert engine.config["routing_mode"] == "static"


@pytest.mark.parametrize("site", STUDY_SITES)
def test_live_and_recording_engines_built_from_a_saved_adaptive_scenario_run_static(site):
    engine = TrafficEngine(network=load_registered_network(site))
    engine.configure_from_scenario(saved_as_adaptive(site))
    assert engine.config["routing_mode"] == "static"


@pytest.mark.parametrize("site", STUDY_SITES)
def test_engine_for_scenario_runs_static_for_evaluation_and_validation(site):
    assert engine_for_scenario(saved_as_adaptive(site), seed=3).config["routing_mode"] == "static"


def test_training_environment_runs_static_at_a_study_site():
    from simulation.rl_env import SmartFlowRLEnv
    env = SmartFlowRLEnv(scenario=saved_as_adaptive("tagum_site_a"), seed=11, warmup_seconds=0, evaluation_seconds=5)
    env.reset(seed=11)
    assert env.engine.config["routing_mode"] == "static"


@pytest.mark.parametrize("site", STUDY_SITES)
def test_a_scenario_saved_as_adaptive_is_stored_as_static(site):
    import database
    stored = json.loads(database.validated_native_scenario(site, {"routing_mode": "adaptive"})["engine_config"])
    assert stored["routing_mode"] == "static"


def test_the_five_junction_network_keeps_adaptive_routing():
    network = load_registered_network("tagum_network")
    assert TrafficEngine(network=network).config["routing_mode"] == "adaptive"
    assert validate_config(DEFAULTS, {"routing_mode": "adaptive"}, network)["routing_mode"] == "adaptive"
    assert validate_config(DEFAULTS, {"routing_mode": "static"}, network)["routing_mode"] == "static"
    assert engine_for_scenario({"network_id": "tagum_network", "engine_config": {"routing_mode": "adaptive"}}).config["routing_mode"] == "adaptive"


def test_an_unknown_routing_mode_is_still_refused_at_a_study_site():
    with pytest.raises(ValueError, match="routing_mode"):
        validate_config(DEFAULTS, {"routing_mode": "fastest"}, load_registered_network("tagum_site_a"))


def test_static_routing_at_a_study_site_still_reroutes_around_a_closure():
    engine = TrafficEngine(seed=7, network=load_registered_network("tagum_site_a"))
    engine.configure(traffic_density="none", pedestrian_density="none", routing_mode="adaptive", closed_lanes=["road2r"],
                     trips=[{"time": 1, "source": "boundary_2", "destination": "boundary_1", "vehicle_type": "car"}])
    engine.start(400)
    engine.step(4000)
    assert engine._last_metrics["throughput"] == 1 and engine._last_metrics["lanes"]["road6f"]["exits"] == 1


def test_comparison_keys_keep_the_routing_mode_in_python():
    from backend.main import compare_key
    run = SimpleNamespace(id=1)

    def manifest(mode):
        return {"experiment": {"engine_version": "native-9", "seed": 1, "config": {"traffic_density": "low", "routing_mode": mode}}}
    assert compare_key(run, None, manifest("adaptive")) != compare_key(run, None, manifest("static"))
    assert compare_key(run, None, manifest("static")) == compare_key(run, None, manifest("static"))


def test_the_routing_comparison_still_pairs_runs_that_differ_only_in_routing():
    from backend.main import compare_kind
    from backend import main

    def option(run_id, mode):
        experiment = {"engine_version": "native-9", "seed": 1, "config": {"traffic_density": "low", "routing_mode": mode}}
        run = SimpleNamespace(id=run_id, timeline_path=f"t{run_id}", control_mode="fixed-time", rl_model_id=None)
        return SimpleNamespace(run=run, timeline=None), {"experiment": experiment}
    (left, left_manifest), (right, right_manifest) = option(1, "adaptive"), option(2, "static")
    manifests = {"t1": left_manifest, "t2": right_manifest}
    original = main.compare_manifest
    main.compare_manifest = lambda path: manifests[path]
    try:
        assert compare_kind(left, right) == "routing"
    finally:
        main.compare_manifest = original


def test_scenario_options_tell_the_page_that_routing_follows_the_closure_choice_at_study_sites():
    from services.native_scenario_service import configuration_options
    assert configuration_options("tagum_site_a")["routing_follows_closure_choice"] is True
    assert configuration_options("tagum_site_a")["defaults"]["routing_mode"] == "static"
    assert configuration_options("tagum_network")["routing_follows_closure_choice"] is False
