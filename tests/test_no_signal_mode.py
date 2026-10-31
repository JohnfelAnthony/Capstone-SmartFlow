import pytest

from services.native_controller import apply_controller
from simulation.traffic_engine import TrafficEngine
from tests.mixed_traffic_helpers import junction_network, place, started_engine


def test_no_signal_survives_start_and_preserves_scenario_settings():
    engine = TrafficEngine(network=junction_network())
    fixed_config = engine.experiment_metadata()["config"]
    apply_controller(engine, "no-signal")
    engine.start(60)
    metadata = engine.experiment_metadata()
    assert {signal.mode for signal in engine.signals.values()} == {"first_come"}
    assert metadata["config"] == fixed_config
    assert metadata["control"]["junction_control"] == "first_come"
    assert engine.controller_provenance == "no-signal"
    assert {item["state"] for item in engine.to_dict()["traffic_lights"].values()} == {"n"}
    control = engine.junction_controls()["j"]
    assert (control["controller"], control["timing_kind"], control["remaining_seconds"]) == ("no-signal", "none", None)


def test_switch_to_fixed_time_and_reject_rl_while_unsignalized():
    engine = TrafficEngine(network=junction_network())
    apply_controller(engine, "no-signal")
    with pytest.raises(ValueError, match="RL signal control requires a signalized controlled junction"):
        engine.configure_rl_control()
    apply_controller(engine, "fixed-time")
    engine.start(60)
    assert {signal.mode for signal in engine.signals.values()} == {"signalized"}
    assert engine.experiment_metadata()["control"].get("junction_control") is None


def test_explicit_first_come_plan_cannot_enable_rl():
    engine = TrafficEngine(network=junction_network())
    engine.configure(signal_plans={"j": {"mode": "first_come"}})
    with pytest.raises(ValueError, match="RL signal control requires a signalized controlled junction"):
        engine.configure_rl_control()


def test_no_signal_and_fixed_time_have_matching_experiment_keys():
    from types import SimpleNamespace
    from backend.main import compare_key
    first, second = TrafficEngine(network=junction_network()), TrafficEngine(network=junction_network())
    apply_controller(first, "no-signal")
    apply_controller(second, "fixed-time")
    first.start(60)
    second.start(60)
    run = SimpleNamespace(id=1)
    assert compare_key(run, None, {"experiment": first.experiment_metadata()}) == \
        compare_key(run, None, {"experiment": second.experiment_metadata()})


def test_blocked_no_signal_traffic_is_counted_by_gridlock_watchdog():
    engine = started_engine(junction_network(), signal_plans={"j": {"mode": "first_come"}})
    place(engine, ["wf", "er"], "car", from_stop_line=3, lateral=0, speed=0)
    engine.close_lane("er", True)
    engine.step(650)
    assert engine._last_metrics["gridlock_seconds"] > 0


def test_no_signal_recording_persists_its_controller(tmp_path, monkeypatch):
    import json
    import config
    import database
    from services import timeline_generator

    monkeypatch.setattr(config, "DB_PATH", str(tmp_path / "test.db"))
    monkeypatch.setattr(timeline_generator, "_artifact_paths", lambda run_id: (
        tmp_path / "run.jsonl", tmp_path / "run.jsonl.gz", tmp_path / "run.manifest.json"))
    monkeypatch.setattr(timeline_generator, "_prune_old_raw_timelines", lambda: None)
    database.init_db()
    scenario_id = database.create_scenario("Synthetic no signal", network_id="tagum_site_a", engine_config={})
    run_id = database.create_run(scenario_id, None, run_mode="pre-record", status="running", seed=101)
    worker = timeline_generator.generate_timeline(scenario_id, 5, run_id, seed=101, control_mode="no-signal")
    worker.join(timeout=60)
    assert not worker.is_alive()
    run = database.get_run_by_id(run_id)
    assert run["status"] == "completed", run.get("notes")
    assert run["control_mode"] == "no-signal"
    manifest = json.loads((tmp_path / "run.manifest.json").read_text(encoding="utf-8"))
    assert manifest["experiment"]["control"]["junction_control"] == "first_come"
    from simulation.timeline_engine import TimelinePlaybackEngine
    from simulation.traffic_engine import NO_SIGNAL_LABEL
    playback = TimelinePlaybackEngine(run_id, str(tmp_path / "run.jsonl.gz"))
    assert playback.status != "error", playback.last_error
    assert (playback.source_controller_provenance, playback.source_controller_label) == ("no-signal", NO_SIGNAL_LABEL)
    frame = playback.to_dict()
    assert {item["state"] for item in frame["traffic_lights"].values()} == {"n"}
    assert {item["controller"] for item in frame["junction_controls"].values()} == {"no-signal"}
