import os
from copy import deepcopy

import pytest
from fastapi.testclient import TestClient

os.environ.setdefault("SMARTFLOW_SECRET_KEY", "route-preview-tests-only")
os.environ.setdefault("SMARTFLOW_BOOTSTRAP_ADMIN_PASSWORD", "RoutePreviewAdmin42!")

import auth
import config
import database
from backend import main
from backend.schemas import SimulationConfigureRequest, SimulationStartRequest
from backend.simulation_runtime import SimulationRuntime
from services import route_preview
from simulation.network_registry import load_registered_network
from simulation.road_network import RoadNetwork


PASSWORD = "RoutePreviewViewer42!"
SITE_A = "tagum_site_a"
CONTEXT = {"source": {"kind": "network", "network_id": SITE_A}, "vehicle_type": "car"}


@pytest.fixture
def scratch_app(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "DB_PATH", str(tmp_path / "route-preview.db"))
    database.init_db()
    database.seed_data()
    role_id = database.get_role_by_name("user")["id"]
    for action, allowed in (("view", True), ("create", False), ("edit", False), ("run", False)):
        database.update_role_permission(role_id, "scenarios", action, allowed)
    user_id = database.create_user("Route Viewer", "route_viewer", None, auth.hash_password(PASSWORD), role_id=role_id)
    scenario_id = database.create_scenario(
        "Preview while a run is active", network_id=SITE_A,
        engine_config={"traffic_density": "none", "pedestrian_density": "none", "warmup_seconds": 0},
    )
    runtime = SimulationRuntime()
    monkeypatch.setattr(main, "simulation_runtime", runtime)
    monkeypatch.setattr(runtime, "_start_background_runner_locked", lambda: None)
    try:
        with TestClient(main.app) as viewer:
            login = viewer.post("/api/auth/login", json={"username": "route_viewer", "password": PASSWORD})
            assert login.status_code == 200, login.text
            yield viewer, role_id, user_id, scenario_id, runtime
    finally:
        runtime.reset(force=True)


def trip(context=CONTEXT, fingerprint=None, **overrides):
    return {
        **context,
        "expected_network_sha256": fingerprint or load_registered_network(SITE_A).fingerprint,
        "entry_id": "boundary_2",
        "destination_id": "boundary_1",
        **overrides,
    }


def test_view_only_user_can_preview_without_edit_or_run_permission(scratch_app):
    viewer, _, user_id, _, _ = scratch_app
    for action in ("create", "edit", "run"):
        assert not database.check_user_permission(user_id, "scenarios", action)
    assert viewer.post("/api/routes/context", json=CONTEXT).status_code == 200
    response = viewer.post("/api/routes/preview", json=trip())
    assert response.status_code == 200, response.text
    assert response.json()["outcome"] == "unchanged"


def test_preview_requires_authentication_and_scenarios_view(scratch_app):
    viewer, role_id, _, _, _ = scratch_app
    database.update_role_permission(role_id, "scenarios", "view", False)
    with TestClient(main.app) as anonymous:
        for endpoint, payload in (("context", CONTEXT), ("preview", trip())):
            assert anonymous.post(f"/api/routes/{endpoint}", json=payload).status_code == 401
            assert viewer.post(f"/api/routes/{endpoint}", json=payload).status_code == 403


def test_context_and_preview_use_same_network_fingerprint(scratch_app):
    viewer, _, _, scenario_id, _ = scratch_app
    context_request = {**CONTEXT, "source": {"kind": "scenario", "scenario_id": scenario_id}}
    response = viewer.post("/api/routes/context", json=context_request)
    assert response.status_code == 200, response.text
    context = response.json()
    assert context["network_binding"] == "saved_fingerprint"
    assert context["geometry"]["network_id"] == SITE_A
    response = viewer.post("/api/routes/preview", json=trip(context_request, context["network_sha256"]))
    assert response.status_code == 200, response.text
    assert response.json()["network_sha256"] == context["network_sha256"]
    assert "geometry" not in response.json()


def test_network_change_between_context_and_preview_returns_409(scratch_app, monkeypatch):
    viewer, _, _, scenario_id, _ = scratch_app
    response = viewer.post("/api/routes/context", json=CONTEXT)
    assert response.status_code == 200, response.text
    fingerprint = response.json()["network_sha256"]
    payload = deepcopy(load_registered_network(SITE_A).payload)
    payload["roads"][0]["width_per_direction_m"] = 9.4
    changed = RoadNetwork(payload)
    assert changed.fingerprint != fingerprint
    monkeypatch.setattr(route_preview, "load_registered_network", lambda _network_id: changed)
    response = viewer.post("/api/routes/preview", json=trip(fingerprint=fingerprint))
    assert response.status_code == 409
    assert "Reload" in response.json()["detail"]
    stale = {**CONTEXT, "source": {"kind": "scenario", "scenario_id": scenario_id}}
    response = viewer.post("/api/routes/context", json=stale)
    assert response.status_code == 409
    assert "Migrate or recreate" in response.json()["detail"]


def test_missing_source_and_invalid_trip_return_expected_errors(scratch_app):
    viewer, _, _, _, _ = scratch_app
    for source in ({"kind": "scenario", "scenario_id": 100000}, {"kind": "network", "network_id": "unknown"}):
        context = {**CONTEXT, "source": source}
        assert viewer.post("/api/routes/context", json=context).status_code == 404
        assert viewer.post("/api/routes/preview", json=trip(context)).status_code == 404
    response = viewer.post("/api/routes/preview", json=trip(destination_id="boundary_2"))
    assert response.status_code == 422
    assert "permitted generated trip" in response.json()["detail"]


@pytest.mark.parametrize("changes", [
    {"closure_override": None},
    {"closure_override": {"closed_lanes": ["road2r"], "closure_responses": {"road2r": "custom"}}},
    {"closure_override": {"closed_lanes": ["road2r"]}},
    {"source": {"kind": "network", "network_id": SITE_A, "scenario_id": 1}},
    {"expected_network_sha256": "invalid"},
    {"entry_id": " "},
    {"vehicle_type": "unknown"},
    {"engine_config": {}},
    {"closure_override": {"closed_lanes": ["road2r"] * 1025, "closure_responses": {}}},
])
def test_malformed_preview_requests_have_readable_errors(scratch_app, changes):
    viewer, _, _, _, _ = scratch_app
    response = viewer.post("/api/routes/preview", json=trip(**changes))
    assert response.status_code == 422
    assert isinstance(response.json()["detail"], str)


def saved_rows():
    tables = ("scenarios", "roles", "permissions", "rl_models", "rl_checkpoints", "rl_training_jobs",
              "rl_training_job_items", "simulation_runs", "run_metrics", "audit_logs")
    with database.get_db() as connection:
        return {table: [tuple(row) for row in connection.execute(f"SELECT * FROM {table} ORDER BY rowid")]
                for table in tables}


def test_preview_with_disposable_arrival_engines_preserves_saved_data_and_live_runtime(scratch_app, tmp_path):
    viewer, _, _, scenario_id, runtime = scratch_app
    runtime.configure(SimulationConfigureRequest(scenario_id=scenario_id))
    started = runtime.start(SimulationStartRequest(duration_seconds=10, seed=101))
    assert started.status == "running" and started.active_run_id is not None
    engine = runtime._engine
    before_runtime = runtime.get_state().model_dump()
    before_db = saved_rows()
    before_paths = sorted(path for path in tmp_path.rglob("*") if path.suffix not in {".db-wal", ".db-shm"})
    context_request = {**CONTEXT, "source": {"kind": "scenario", "scenario_id": scenario_id}}
    context = viewer.post("/api/routes/context", json=context_request)
    assert context.status_code == 200, context.text
    response = viewer.post("/api/routes/preview", json=trip(
        context_request, context.json()["network_sha256"],
        closure_override={"closed_lanes": ["road2r"], "closure_responses": {"road2r": "share"}},
    ))
    assert response.status_code == 200, response.text
    assert response.json()["uses_shared_pavement"]
    assert runtime._engine is engine
    assert runtime.get_state().model_dump() == before_runtime
    assert saved_rows() == before_db
    assert sorted(path for path in tmp_path.rglob("*") if path.suffix not in {".db-wal", ".db-shm"}) == before_paths
