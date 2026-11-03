import copy
import os
from types import SimpleNamespace

import pytest

os.environ.setdefault("SMARTFLOW_SECRET_KEY", "revision-apply-test-secret")
os.environ.setdefault("SMARTFLOW_BOOTSTRAP_ADMIN_PASSWORD", "RevisionApply123!")

from backend.simulation_runtime import SimulationRuntime
from services.network_revision_apply import apply_revision
from services.network_revision_storage import RevisionConflict
from simulation.network_registry import load_registered_network
from simulation.road_network import RoadNetwork
from tests.test_network_revision_storage import isolated_registry  # noqa: F401


def inputs(isolated_registry):
    registry, original = isolated_registry
    old = load_registered_network("tagum_site_a", registry_path=registry)
    candidate = copy.deepcopy(original)
    candidate["roads"][0]["width_per_direction_m"] = 5.0
    runtime = SimulationRuntime()
    runtime._engine = SimpleNamespace(status="stopped", network=old)
    runtime._selected_scenario_id = 4
    return registry, old, candidate, runtime


def fake_passing_review(monkeypatch, old, candidate):
    # Exercise orchestration only; this is not a real clearance validator.
    monkeypatch.setattr("services.network_revision_apply.preview_revision", lambda *args, **kwargs: {
        "installed_sha256": old.fingerprint, "candidate_sha256": RoadNetwork(candidate).fingerprint,
        "changes": {}, "validation": {"structurally_valid": True, "clearance_checked": True, "issues": []}})


def test_real_validation_refuses_apply_before_audit_or_write(isolated_registry):
    registry, old, candidate, runtime = inputs(isolated_registry)
    events = []
    with pytest.raises(ValueError, match="clearance"):
        apply_revision(registry_path=registry, runtime=runtime, network_id="tagum_site_a", expected_sha256=old.fingerprint,
                       candidate=candidate, scenarios=[], user_id=1, audit=lambda **event: events.append(event))
    assert not events and runtime._engine.network is old
    assert load_registered_network("tagum_site_a", registry_path=registry).fingerprint == old.fingerprint


def test_simulated_clearance_exercises_commit_invalidation_and_audit(isolated_registry, monkeypatch):
    registry, old, candidate, runtime = inputs(isolated_registry)
    fake_passing_review(monkeypatch, old, candidate)
    events = []
    result = apply_revision(registry_path=registry, runtime=runtime, network_id="tagum_site_a", expected_sha256=old.fingerprint,
                            candidate=candidate, scenarios=[], user_id=1, audit=lambda **event: events.append(event))
    assert result["changed"] and runtime._engine is None and runtime._selected_scenario_id is None
    assert load_registered_network("tagum_site_a", registry_path=registry).fingerprint == result["new_sha256"]
    assert [entry["action"] for entry in events] == ["network_revision_apply_requested", "network_revision_applied"]
    with pytest.raises(RevisionConflict):
        apply_revision(registry_path=registry, runtime=runtime, network_id="tagum_site_a", expected_sha256="0" * 64,
                       candidate=candidate, scenarios=[], user_id=1, audit=lambda **event: events.append(event))


def test_audit_failure_before_commit_refuses_switch(isolated_registry, monkeypatch):
    registry, old, candidate, runtime = inputs(isolated_registry)
    fake_passing_review(monkeypatch, old, candidate)
    def audit(**_):
        raise OSError("audit disk failure")
    with pytest.raises(OSError, match="audit disk"):
        apply_revision(registry_path=registry, runtime=runtime, network_id="tagum_site_a", expected_sha256=old.fingerprint,
                       candidate=candidate, scenarios=[], user_id=1, audit=audit)
    assert load_registered_network("tagum_site_a", registry_path=registry).fingerprint == old.fingerprint
    assert runtime._engine.network is old


def test_completion_audit_failure_reports_committed_revision(isolated_registry, monkeypatch):
    registry, old, candidate, runtime = inputs(isolated_registry)
    fake_passing_review(monkeypatch, old, candidate)
    def audit(**event):
        if event["action"] == "network_revision_applied":
            raise OSError("audit disk failure")
    result = apply_revision(registry_path=registry, runtime=runtime, network_id="tagum_site_a", expected_sha256=old.fingerprint,
                            candidate=candidate, scenarios=[], user_id=1, audit=audit)
    assert "audit_warning" in result and runtime._engine is None
    assert load_registered_network("tagum_site_a", registry_path=registry).fingerprint == result["new_sha256"]


def test_apply_endpoint_requires_admin_and_currently_refuses_unchecked_clearance(isolated_registry, monkeypatch):
    from fastapi.testclient import TestClient
    from backend.main import app
    from backend.security import require_current_user
    registry, old, candidate, _ = inputs(isolated_registry)
    monkeypatch.setattr("simulation.network_registry.REGISTRY_PATH", registry)
    monkeypatch.setattr("backend.main.database.get_scenarios", lambda include_archived: [])
    monkeypatch.setattr("backend.main.simulation_runtime", SimulationRuntime())
    payload = {"network": candidate, "expected_sha256": old.fingerprint}
    client = TestClient(app)
    assert client.post("/api/admin/networks/tagum_site_a/apply", json=payload).status_code == 401
    try:
        app.dependency_overrides[require_current_user] = lambda: {"id": 2, "role_name": "viewer"}
        assert client.post("/api/admin/networks/tagum_site_a/apply", json=payload).status_code == 403
        app.dependency_overrides[require_current_user] = lambda: {"id": 1, "role_name": "admin"}
        result = client.post("/api/admin/networks/tagum_site_a/apply", json=payload)
        assert result.status_code == 422 and "clearance" in result.json()["detail"]
        assert load_registered_network("tagum_site_a", registry_path=registry).fingerprint == old.fingerprint
    finally:
        app.dependency_overrides.pop(require_current_user, None)
