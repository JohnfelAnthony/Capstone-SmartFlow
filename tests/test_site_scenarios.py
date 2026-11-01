from pathlib import Path

import pytest

from services.native_scenario_service import configuration_options
from simulation.network_registry import engine_for_scenario, load_registered_network


def test_configuration_options_follow_selected_network():
    options = configuration_options("tagum_site_b")
    assert options["network_id"] == "tagum_site_b"
    assert len(options["junctions"]) == 1


def test_changed_network_fingerprint_refuses_scenario():
    with pytest.raises(ValueError, match="network changed since this scenario was saved"):
        engine_for_scenario({"network_id": "tagum_site_a", "network_sha256": "old", "engine_config": {}})


def test_current_network_fingerprint_is_accepted():
    network = load_registered_network("tagum_site_a")
    engine = engine_for_scenario({"network_id": network.id, "network_sha256": network.fingerprint, "engine_config": {}})
    assert engine.network.fingerprint == network.fingerprint


def test_database_validation_uses_selected_site():
    import database
    result = database.validated_native_scenario("tagum_site_a", {})
    assert result["network_id"] == "tagum_site_a"
    assert result["network_sha256"] == load_registered_network("tagum_site_a").fingerprint


def test_migration_report_keeps_registered_scenario():
    from services.scenario_migration import migration_report
    network = load_registered_network("tagum_site_a")
    report = migration_report([{"id": 1, "network_id": network.id, "network_sha256": network.fingerprint, "engine_config": {}}])
    assert report["scenarios"][0]["status"] == "unchanged"


def test_saved_scenario_pins_network_and_rejects_changed_hash(tmp_path, monkeypatch):
    import config
    import database
    monkeypatch.setattr(config, "DB_PATH", str(tmp_path / "site.db"))
    database.init_db()
    scenario_id = database.create_scenario("Site test", network_id="tagum_site_a", engine_config={})
    row = database.get_scenario_by_id(scenario_id)
    assert row["network_sha256"] == load_registered_network("tagum_site_a").fingerprint
    with database.get_db() as connection:
        connection.execute("UPDATE scenarios SET network_sha256=? WHERE id=?", ("stale", scenario_id))
    with pytest.raises(ValueError, match="network changed since this scenario was saved"):
        database.update_scenario(scenario_id, engine_config={})


def test_live_runtime_configures_site_scenario(monkeypatch):
    import database
    from backend.schemas import SimulationConfigureRequest
    from backend.simulation_runtime import SimulationRuntime
    network = load_registered_network("tagum_site_b")
    scenario = {"id": 7, "name": "Synthetic site", "network_id": network.id,
                "network_sha256": network.fingerprint, "engine_config": {}, "is_archived": 0}
    monkeypatch.setattr(database, "get_scenario_by_id", lambda scenario_id: scenario)
    runtime = SimulationRuntime()
    runtime.configure(SimulationConfigureRequest(scenario_id=7))
    assert runtime._engine.network.id == network.id


def test_site_recording_uses_embedded_network_for_playback(tmp_path, monkeypatch):
    import config
    import database
    from services import timeline_generator
    from simulation.timeline_engine import TimelinePlaybackEngine

    monkeypatch.setattr(config, "DB_PATH", str(tmp_path / "site.db"))
    monkeypatch.setattr(timeline_generator, "_artifact_paths", lambda run_id: (tmp_path / "run.jsonl", tmp_path / "run.jsonl.gz", tmp_path / "run.manifest.json"))
    monkeypatch.setattr(timeline_generator, "_prune_old_raw_timelines", lambda: None)
    database.init_db()
    scenario_id = database.create_scenario("Site recording", network_id="tagum_site_a", engine_config={"traffic_density": "low"})
    run_id = database.create_run(scenario_id, None, run_mode="pre-record", status="running", seed=101)
    thread = timeline_generator.generate_timeline(scenario_id, 5, run_id, seed=101)
    thread.join(timeout=60)
    assert not thread.is_alive()
    run = database.get_run_by_id(run_id)
    assert run["status"] == "completed", run.get("notes")
    manifest = __import__("json").loads((tmp_path / "run.manifest.json").read_text(encoding="utf-8"))
    assert manifest["network"]["id"] == "tagum_site_a"
    playback = TimelinePlaybackEngine(run_id, timeline_path=run["timeline_path"])
    assert playback.status != "error", playback.last_error


def test_visual_network_uses_requested_site():
    from services.visual_network_service import load_client_visual_network
    assert load_client_visual_network("tagum_site_b")["network_id"] == "tagum_site_b"


def test_network_lookup_api_returns_options(monkeypatch):
    import backend.main as main
    monkeypatch.setattr(main, "require_any_permission", lambda user, permissions: None)
    assert main.native_configuration_options(network_id="tagum_site_a", user={})["network_id"] == "tagum_site_a"
    assert [item["id"] for item in main.networks(user={})] == ["tagum_network", "tagum_site_a", "tagum_site_b"]


def test_bundle_restores_site_networks_from_bundle(tmp_path, monkeypatch):
    import json
    import config
    import database
    from services.backup_bundle import create_bundle, restore_bundle_to_stage
    from simulation.network_registry import load_registered_network

    monkeypatch.setattr(config, "DB_PATH", str(tmp_path / "site.db"))
    database.init_db()
    scenario_id = database.create_scenario("Site backup", network_id="tagum_site_a", engine_config={})
    filename = create_bundle(None)
    backup = next(item for item in database.list_backups() if item["filename"] == filename)
    staged = restore_bundle_to_stage(backup["id"])
    environment = json.loads((staged / "restore_environment.json").read_text(encoding="utf-8"))
    registry = Path(environment["SMARTFLOW_NETWORK_REGISTRY_PATH"])
    assert registry.is_relative_to(staged)
    assert load_registered_network("tagum_site_a", registry_path=registry).fingerprint == load_registered_network("tagum_site_a").fingerprint
    assert load_registered_network("tagum_site_b", registry_path=registry).id == "tagum_site_b"
    report = json.loads((staged / "scenario_migration_report.json").read_text(encoding="utf-8"))
    assert next(row for row in report["scenarios"] if row["id"] == scenario_id)["status"] == "unchanged"


def test_site_lookup_endpoints_over_http(monkeypatch):
    from fastapi.testclient import TestClient
    import backend.main as main
    monkeypatch.setattr(main, "require_any_permission", lambda user, permissions: None)
    main.app.dependency_overrides[main.require_current_user] = lambda: {"id": 1}
    try:
        client = TestClient(main.app)
        assert client.get("/api/networks").json()[1]["id"] == "tagum_site_a"
        assert client.get("/api/simulation/options", params={"network_id": "tagum_site_b"}).json()["network_id"] == "tagum_site_b"
        assert client.get("/api/simulation/options", params={"network_id": "missing"}).status_code == 422
    finally:
        main.app.dependency_overrides.pop(main.require_current_user, None)
