import copy
import json
import os
from types import SimpleNamespace

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

os.environ.setdefault("SMARTFLOW_SECRET_KEY", "desktop-study-inputs-test")
os.environ.setdefault("SMARTFLOW_BOOTSTRAP_ADMIN_PASSWORD", "StudyInputsTest123!")

from backend.security import require_current_user
from desktop.server import desktop_app
from desktop.study_inputs import StaleStudyInput, import_input, status
from services.workload_admission import WorkloadConflict, workload_admission
from tests.test_desktop_reviewed_conversion import reviewed  # noqa: F401
from tests.test_study_gate import CRITERIA, LEDGER


def test_import_retains_prior_input_rejects_stale_and_preserves_other_site(tmp_path, reviewed):
    _, mapping = reviewed
    site = "tagum_site_a"
    events = []
    audit = lambda **event: events.append(event)
    result = import_input(root=tmp_path, site=site, kind="mapping", document=mapping, expected_sha256=None, user_id=1, audit=audit)
    first = result["sha256"]
    assert status(tmp_path, site)["inputs"]["mapping"]["sha256"] == first
    modified = copy.deepcopy(mapping)
    modified["initialization"]["evidence"] = "Updated synthetic evidence"
    with pytest.raises(StaleStudyInput):
        import_input(root=tmp_path, site=site, kind="mapping", document=modified, expected_sha256=None, user_id=1, audit=audit)
    result = import_input(root=tmp_path, site=site, kind="mapping", document=modified, expected_sha256=first, user_id=1, audit=audit)
    assert result["sha256"] != first
    archived = list((tmp_path / "data" / "sites").glob("history-mapping-a-*.json"))
    assert len(archived) == 1 and json.loads(archived[0].read_text(encoding="utf-8")) == mapping
    criterion = {"sites": {"tagum_site_a": CRITERIA, "tagum_site_b": CRITERIA}}
    import_input(root=tmp_path, site=site, kind="criteria", document=criterion, expected_sha256=None, user_id=1, audit=audit)
    path = tmp_path / "data" / "sites" / "validation_criteria.json"
    assert set(json.loads(path.read_text(encoding="utf-8"))["sites"]) == {site}
    prior = status(tmp_path, site)["inputs"]["criteria"]["sha256"]
    import_input(root=tmp_path, site="tagum_site_b", kind="criteria", document=criterion, expected_sha256=prior, user_id=1, audit=audit)
    assert set(json.loads(path.read_text(encoding="utf-8"))["sites"]) == {"tagum_site_a", "tagum_site_b"}
    assert len(events) == 8


def test_invalid_busy_and_audit_failure_do_not_write(tmp_path, reviewed):
    _, mapping = reviewed
    with pytest.raises(ValueError, match="another network"):
        import_input(root=tmp_path, site="tagum_site_a", kind="mapping", document={**mapping, "network_sha256": "0" * 64}, expected_sha256=None, user_id=1, audit=lambda **_: None)
    lease = workload_admission.acquire("site validation")
    try:
        with pytest.raises(WorkloadConflict):
            import_input(root=tmp_path, site="tagum_site_a", kind="ledger", document=LEDGER, expected_sha256=None, user_id=1, audit=lambda **_: None)
    finally:
        workload_admission.release(lease)
    def fail_audit(**_):
        raise OSError("audit unavailable")
    with pytest.raises(OSError, match="audit unavailable"):
        import_input(root=tmp_path, site="tagum_site_a", kind="ledger", document=LEDGER, expected_sha256=None, user_id=1, audit=fail_audit)
    assert status(tmp_path, "tagum_site_a")["inputs"]["ledger"]["sha256"] is None


def test_study_input_endpoints_require_admin(tmp_path, monkeypatch):
    frontend = tmp_path / "frontend"
    frontend.mkdir()
    (frontend / "index.html").write_text("test", encoding="utf-8")
    app = FastAPI()
    origin = "http://127.0.0.1:8123"
    wrapped = desktop_app(app, frontend, origin, restore_requests=SimpleNamespace(paths=SimpleNamespace(root=tmp_path)))
    client = TestClient(wrapped, base_url=origin, headers={"Origin": origin})
    url = "/api/desktop/study-inputs/tagum_site_a/ledger"
    payload = {"document": LEDGER, "expected_sha256": None}
    assert client.post(url, json=payload).status_code == 401
    app.dependency_overrides[require_current_user] = lambda: {"id": 2, "role_name": "viewer"}
    assert client.post(url, json=payload).status_code == 403
    app.dependency_overrides[require_current_user] = lambda: {"id": 1, "role_name": "admin"}
    monkeypatch.setattr("database.log_audit_event", lambda **_: None)
    assert client.post(url, json=payload).status_code == 200
    assert client.post(url, json=payload).status_code == 409
    assert client.get("/api/desktop/study-inputs/tagum_site_a").json()["inputs"]["ledger"]["sha256"]
    assert client.post("/api/desktop/study-inputs/unknown/ledger", json=payload).status_code == 422
