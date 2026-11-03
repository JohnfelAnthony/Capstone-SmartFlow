import copy
import os

os.environ.setdefault("SMARTFLOW_SECRET_KEY", "network-preview-tests-only")
os.environ.setdefault("SMARTFLOW_BOOTSTRAP_ADMIN_PASSWORD", "PreviewTestPass123!")

from fastapi.testclient import TestClient
from backend.main import app
from backend.security import require_current_user
from simulation.network_registry import load_registered_network


def test_admin_preview_is_read_only_and_lists_changes_and_affected_scenarios(monkeypatch):
    installed = load_registered_network("tagum_site_a")
    original = copy.deepcopy(installed.payload)
    candidate = copy.deepcopy(original)
    candidate["roads"][0]["width_per_direction_m"] = 5.0
    monkeypatch.setattr("backend.main.database.get_scenarios", lambda include_archived: [
        {"id": 1, "name": "Saved study", "network_id": "tagum_site_a", "network_sha256": installed.fingerprint, "is_archived": 0},
        {"id": 2, "name": "Other site", "network_id": "tagum_site_b", "network_sha256": "old", "is_archived": 0},
    ])
    app.dependency_overrides[require_current_user] = lambda: {"id": 1, "role_name": "admin"}
    try:
        response = TestClient(app).post("/api/admin/networks/tagum_site_a/preview", json={"network": candidate})
        assert response.status_code == 200, response.text
        result = response.json()
        assert result["installed_sha256"] == installed.fingerprint
        assert result["candidate_sha256"] != installed.fingerprint
        assert candidate["roads"][0]["id"] in result["changes"]["roads"]["modified"]
        assert [row["id"] for row in result["affected_scenarios"]] == [1]
        assert result["installable"] is False and result["validation"]["clearance_checked"] is False
        assert installed.payload == original
    finally:
        app.dependency_overrides.pop(require_current_user, None)


def test_preview_refuses_non_admin_wrong_site_and_malformed_geometry(monkeypatch):
    candidate = copy.deepcopy(load_registered_network("tagum_site_a").payload)
    monkeypatch.setattr("backend.main.database.get_scenarios", lambda include_archived: [])
    assert TestClient(app).post("/api/admin/networks/tagum_site_a/preview", json={"network": candidate}).status_code == 401
    app.dependency_overrides[require_current_user] = lambda: {"id": 2, "role_name": "viewer"}
    try:
        client = TestClient(app)
        assert client.post("/api/admin/networks/tagum_site_a/preview", json={"network": candidate}).status_code == 403
        app.dependency_overrides[require_current_user] = lambda: {"id": 1, "role_name": "admin"}
        assert client.post("/api/admin/networks/tagum_site_b/preview", json={"network": candidate}).status_code == 422
        candidate["roads"][0]["shape"] = []
        result = client.post("/api/admin/networks/tagum_site_a/preview", json={"network": candidate})
        assert result.status_code == 200
        assert not result.json()["validation"]["structurally_valid"]
        assert result.json()["candidate_sha256"] is None
    finally:
        app.dependency_overrides.pop(require_current_user, None)
