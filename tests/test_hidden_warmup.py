"""Hidden warm-up for live runs and saved recordings (D39). SYNTHETIC demand on provisional geometry.

The engine's clock stays absolute (events, demand, seeds and the compare key are those of an evaluation with the same warm-up); what the
user sees starts at 0 when the warm-up ends, and metrics count only from there.
"""
import gzip
import json
import os

import pytest

from simulation.network_registry import engine_for_scenario
from simulation.scenario_config import DEFAULT_RUN_WARMUP_SECONDS, DEFAULTS, effective_warmup_seconds, validate_config
from simulation.network_registry import load_registered_network

SITE = "tagum_site_a"
WARM_UP = 60.0


def engine_with(config, *, warm_up=WARM_UP, run=30.0, seed=101):
    engine = engine_for_scenario({"network_id": SITE, "engine_config": config}, seed=seed)
    engine.start(warm_up + run)
    return engine


def test_warm_up_is_an_engine_config_setting_old_scenarios_get_the_default_and_bad_values_are_refused():
    network = load_registered_network(SITE)
    assert validate_config(DEFAULTS, {}, network)["warmup_seconds"] == DEFAULT_RUN_WARMUP_SECONDS > 0  # a saved scenario without it
    assert validate_config(DEFAULTS, {"warmup_seconds": 0}, network)["warmup_seconds"] == 0.0
    assert validate_config(DEFAULTS, {"warmup_seconds": 45.5}, network)["warmup_seconds"] == 45.5
    for bad in (-1, 3601, "soon", True, 0.05):
        with pytest.raises(ValueError, match="warm-up"):
            validate_config(DEFAULTS, {"warmup_seconds": bad}, network)


def test_scripted_traffic_has_nothing_to_warm_up():
    medium = validate_config(DEFAULTS, {"traffic_density": "medium", "warmup_seconds": 90}, load_registered_network(SITE))
    assert effective_warmup_seconds(medium) == 90.0
    for scripted in ({"traffic_density": "single"}, {"traffic_density": "none"},
                     {"traffic_density": "none", "trips": [{"time": 5, "source": "boundary_0", "destination": "boundary_1"}]},
                     {"traffic_density": "medium", "pedestrian_trips": [{"time": 5, "junction": "tagum_site_a_j"}]}):
        config = validate_config(DEFAULTS, {**scripted, "warmup_seconds": 90}, load_registered_network(SITE))
        assert effective_warmup_seconds(config) == 0.0, scripted
    counts = {"traffic_density": "none", "demand_windows": [{"start": 0, "end": 86400, "vehicles_per_hour": 300,
                                                           "od": [{"source": "boundary_0", "destination": "boundary_1", "weight": 1}]}]}
    assert effective_warmup_seconds(validate_config(DEFAULTS, {**counts, "warmup_seconds": 90}, load_registered_network(SITE))) == 90.0
    for start, end in ((0, 60), (5, 86400)):
        window = {**counts["demand_windows"][0], "start": start, "end": end}
        config = validate_config(DEFAULTS, {**counts, "demand_windows": [window]}, load_registered_network(SITE))
        assert effective_warmup_seconds(config) == 0.0


def test_the_first_frame_after_the_warm_up_has_vehicles_that_drove_in_and_the_clock_and_metrics_start_at_zero():
    engine = engine_with({"traffic_density": "medium"})
    engine.warm_up(WARM_UP)
    first = engine.to_dict()
    assert first["time"] == 0.0 and first["vehicle_count"] > 0 and first["status"] == "running"
    assert first["metrics"]["measurement_start"] == WARM_UP and first["metrics"]["measurement_seconds"] == 0.0
    assert first["metrics"]["throughput"] == 0 and engine.completed == 0
    assert all(point["time"] >= 0 for series in first["charts"].values() for point in series)
    assert all(event["time"] >= 0 for event in first["events"])  # nothing logged before the visible clock started
    engine.step(50)
    later = engine.to_dict()
    assert later["time"] == 5.0 and later["metrics"]["measurement_seconds"] == 5.0
    assert engine.simulation_time == WARM_UP + 5.0  # the engine's own clock is absolute, as in evaluation


def test_a_run_with_a_hidden_warm_up_is_exactly_an_evaluation_with_the_same_warm_up():
    hidden = engine_with({"traffic_density": "medium"})
    hidden.warm_up(WARM_UP)
    hidden.step(200)
    by_hand = engine_with({"traffic_density": "medium"})  # what tools/evaluate_controllers.py does
    by_hand.step(int(WARM_UP*10))
    by_hand.reset_metrics()
    by_hand.step(200)
    assert hidden.to_dict()["metrics"] == by_hand.to_dict()["metrics"]
    assert hidden.vehicle_records() == by_hand.vehicle_records()
    again = engine_with({"traffic_density": "medium"})
    again.warm_up(WARM_UP)
    again.step(200)
    assert again.vehicle_records() == hidden.vehicle_records()  # same seed, same result


def test_events_keep_the_simulations_own_clock_so_a_closure_timed_in_the_warm_up_still_applies():
    events = [{"time": 20, "lane_id": "road2r", "closed": True, "label": "inside the warm-up"},
              {"time": WARM_UP + 10, "lane_id": "road1f", "closed": True, "label": "ten seconds into the visible run"}]
    engine = engine_with({"traffic_density": "medium", "events": events})
    engine.warm_up(WARM_UP)
    assert "road2r" in engine.closed_lanes and "road1f" not in engine.closed_lanes
    engine.step(90)  # visible 9.0 s
    assert "road1f" not in engine.closed_lanes
    engine.step(20)  # visible 11.0 s
    assert "road1f" in engine.closed_lanes


def test_a_warm_up_under_a_policy_or_the_no_signal_rule_is_controlled_by_it():
    engine = engine_with({"traffic_density": "medium"})
    engine.enable_no_signal_control()
    engine.warm_up(WARM_UP)
    assert engine.no_signal_control and engine.to_dict()["time"] == 0.0


@pytest.fixture
def api(tmp_path, monkeypatch):
    os.environ.setdefault("SMARTFLOW_SECRET_KEY", "hidden-warm-up-test-only")
    from fastapi.testclient import TestClient
    import config
    from backend.main import app
    from backend.simulation_runtime import simulation_runtime
    monkeypatch.setattr(config, "DB_PATH", str(tmp_path / "warmup.db"))
    monkeypatch.setattr(config, "BOOTSTRAP_ADMIN_PASSWORD", "WarmUpAdmin42!")
    with TestClient(app) as client:
        simulation_runtime.reset(force=True)
        assert client.post("/api/auth/login", json={"username": "admin", "password": "WarmUpAdmin42!"}).status_code == 200
        yield client, simulation_runtime
        simulation_runtime.reset(force=True)


def test_a_live_start_returns_after_the_warm_up_with_the_clock_at_zero_and_the_full_visible_duration(api):
    from unittest.mock import patch
    client, runtime = api
    created = client.post("/api/scenarios", json={"name": "Warm", "network_id": SITE, "engine_config": {"traffic_density": "medium", "warmup_seconds": 40}})
    assert created.status_code == 200, created.text
    assert created.json()["engine_config"]["warmup_seconds"] == 40.0
    assert client.post("/api/simulation/configure", json={"scenario_id": created.json()["id"], "duration_seconds": 30}).status_code == 200
    with patch.object(runtime, "_start_background_runner_locked"):  # no real-time stepping: look at the first frame as the stream would send it
        started = client.post("/api/simulation/start", json={})
    assert started.status_code == 200, started.text
    simulation = started.json()["simulation"]
    assert simulation["state"]["time"] == 0.0 and simulation["state"]["vehicle_count"] > 0
    assert simulation["duration_seconds"] == 30
    assert simulation["state"]["experiment"]["measurement_start"] == 40.0
    assert runtime._engine.duration_limit == 70  # warm-up plus the visible run, as an evaluation would ask for
    runtime._engine.step(300)
    assert runtime._engine.status == "completed" and runtime._engine.to_dict()["time"] == 30.0
    runtime._finalize_terminal_run_locked()
    import database
    assert database.get_runs()[0]["duration_seconds"] == 30.0  # the visible length, not warm-up plus run


@pytest.mark.parametrize("paused", [False, True])
def test_start_on_an_active_run_preserves_its_clock_and_measurement(api, paused):
    from unittest.mock import patch

    import database

    client, runtime = api
    created = client.post("/api/scenarios", json={
        "name": "Start retry", "network_id": SITE,
        "engine_config": {"traffic_density": "medium", "warmup_seconds": 40},
    })
    assert created.status_code == 200, created.text
    with patch.object(runtime, "_start_background_runner_locked"):
        first = client.post("/api/simulation/start", json={"scenario_id": created.json()["id"], "duration_seconds": 300})
        assert first.status_code == 200, first.text
        runtime._engine.step(50)
        if paused:
            assert client.post("/api/simulation/pause").status_code == 200
        retried = client.post("/api/simulation/start", json={})
    assert retried.status_code == 200, retried.text
    state = retried.json()["simulation"]["state"]
    assert state["status"] == "running"
    assert state["time"] == 5.0
    assert state["experiment"]["measurement_start"] == 40.0
    assert state["metrics"]["measurement_seconds"] == 5.0
    assert state["dashboard"]["run_id"] == first.json()["simulation"]["state"]["dashboard"]["run_id"]
    assert [run["status"] for run in database.get_runs()] == ["running"]


def test_an_old_scenario_without_the_setting_loads_with_the_default(api):
    import database
    client, _ = api
    scenario_id = database.create_scenario("Old", network_id=SITE, engine_config={"traffic_density": "medium"})
    with database.get_db() as conn:
        conn.execute("UPDATE scenarios SET engine_config = ? WHERE id = ?", (json.dumps({"traffic_density": "medium"}), scenario_id))
    resolved = client.get(f"/api/scenarios/{scenario_id}/native-config")  # what the details and the engine use: saved settings plus defaults
    assert resolved.status_code == 200, resolved.text
    assert resolved.json()["engine_config"]["warmup_seconds"] == DEFAULT_RUN_WARMUP_SECONDS


def test_a_recording_starts_after_the_warm_up(tmp_path, monkeypatch):
    import config
    import database
    from services import timeline_generator
    monkeypatch.setattr(config, "DB_PATH", str(tmp_path / "rec.db"))
    monkeypatch.setattr(timeline_generator, "_artifact_paths", lambda run_id: (tmp_path / "run.jsonl", tmp_path / "run.jsonl.gz", tmp_path / "run.manifest.json"))
    monkeypatch.setattr(timeline_generator, "_prune_old_raw_timelines", lambda: None)
    database.init_db()
    scenario_id = database.create_scenario("Recorded", network_id=SITE, engine_config={"traffic_density": "medium", "warmup_seconds": 40})
    run_id = database.create_run(scenario_id, None, run_mode="pre-record", status="running", seed=101)
    worker = timeline_generator.generate_timeline(scenario_id, 5, run_id, seed=101)
    worker.join(timeout=120)
    assert not worker.is_alive()
    run = database.get_run_by_id(run_id)
    assert run["status"] == "completed", run.get("notes")
    frames = [json.loads(line) for line in gzip.open(tmp_path / "run.jsonl.gz", "rt", encoding="utf-8")]
    assert len(frames) == 51 and frames[0]["time"] == 0.0 and frames[-1]["time"] == 5.0 and frames[0]["vehicle_count"] > 0
    assert run["duration_seconds"] == 5.0
    manifest = json.loads((tmp_path / "run.manifest.json").read_text(encoding="utf-8"))
    assert manifest["timeline"]["actual_duration_seconds"] == 5.0 and manifest["experiment"]["measurement_start"] == 40.0
    assert manifest["experiment"]["duration_seconds"] == 45  # the compare key matches an evaluation of 40 s warm-up and 5 s measured
