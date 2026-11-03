import copy
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from services.network_revision_storage import RevisionConflict, store_revision
from simulation.network_registry import load_registered_network


@pytest.fixture
def isolated_registry(tmp_path):
    source = Path(__file__).resolve().parents[1] / "data" / "networks" / "tagum_site_a.json"
    payload = json.loads(source.read_text(encoding="utf-8"))
    (tmp_path / "original.json").write_text(json.dumps(payload), encoding="utf-8")
    registry = tmp_path / "registry.json"
    registry.write_text(json.dumps({"networks": [{"id": "tagum_site_a", "file": "original.json", "extra": "preserve"}], "extra": "preserve"}), encoding="utf-8")
    return registry, payload


def test_revision_is_immutable_and_old_network_remains(isolated_registry):
    registry, original = isolated_registry
    old_hash = load_registered_network("tagum_site_a", registry_path=registry).fingerprint
    candidate = copy.deepcopy(original)
    candidate["roads"][0]["width_per_direction_m"] = 5.0
    result = store_revision(registry, "tagum_site_a", old_hash, candidate)
    assert result["changed"] and result["old_sha256"] == old_hash and result["new_sha256"] != old_hash
    assert load_registered_network("tagum_site_a", registry_path=registry).fingerprint == result["new_sha256"]
    assert json.loads((registry.parent / "original.json").read_text(encoding="utf-8")) == original
    updated = json.loads(registry.read_text(encoding="utf-8"))
    assert updated["extra"] == "preserve" and updated["networks"][0]["extra"] == "preserve"
    assert updated["networks"][0]["revision_history"] == [{"file": "original.json", "sha256": old_hash}]
    assert not store_revision(registry, "tagum_site_a", result["new_sha256"], candidate)["changed"]
    with pytest.raises(RevisionConflict, match="changed"):
        store_revision(registry, "tagum_site_a", old_hash, original)
    # Rollback is another revision and never deletes the newer one.
    rollback = store_revision(registry, "tagum_site_a", result["new_sha256"], original)
    assert rollback["new_sha256"] == old_hash
    assert (registry.parent / result["file"]).is_file()


def test_failed_registry_replace_keeps_old_revision(isolated_registry, monkeypatch):
    registry, original = isolated_registry
    old_hash = load_registered_network("tagum_site_a", registry_path=registry).fingerprint
    candidate = copy.deepcopy(original)
    candidate["roads"][0]["width_per_direction_m"] = 5.0
    def fail_replace(*_):
        raise OSError("simulated write failure")
    monkeypatch.setattr("services.network_revision_storage.os.replace", fail_replace)
    with pytest.raises(OSError, match="simulated"):
        store_revision(registry, "tagum_site_a", old_hash, candidate)
    assert load_registered_network("tagum_site_a", registry_path=registry).fingerprint == old_hash
    assert not list(registry.parent.glob("*.tmp"))


def test_backup_includes_and_verifies_explicit_revision_history(isolated_registry, monkeypatch):
    monkeypatch.setenv("SMARTFLOW_SECRET_KEY", "isolated-revision-test-key")
    import config
    import simulation.network_registry as network_registry
    from services import backup_bundle
    registry, original = isolated_registry
    old_hash = load_registered_network("tagum_site_a", registry_path=registry).fingerprint
    candidate = copy.deepcopy(original)
    candidate["roads"][0]["width_per_direction_m"] = 5.0
    result = store_revision(registry, "tagum_site_a", old_hash, candidate)
    monkeypatch.setattr(config, "DB_PATH", str(registry.parent / "scratch.db"))
    monkeypatch.setattr(network_registry, "REGISTRY_PATH", registry)
    original_list = network_registry.registered_networks
    monkeypatch.setattr(network_registry, "registered_networks", lambda: original_list(registry))
    files = backup_bundle._files_for_references(set())
    assert registry.parent / "original.json" in files.values()
    assert registry.parent / result["file"] in files.values()
    (registry.parent / "original.json").write_text("{}", encoding="utf-8")
    with pytest.raises(ValueError):
        backup_bundle._files_for_references(set())


def test_guarded_registry_commit_discards_previous_idle_network(isolated_registry, monkeypatch):
    monkeypatch.setenv("SMARTFLOW_SECRET_KEY", "isolated-revision-test-key")
    from backend.simulation_runtime import SimulationRuntime
    registry, original = isolated_registry
    old = load_registered_network("tagum_site_a", registry_path=registry)
    runtime = SimulationRuntime()
    runtime._engine = SimpleNamespace(status="stopped", network=old)
    runtime._selected_scenario_id = 10
    candidate = copy.deepcopy(original)
    candidate["roads"][0]["width_per_direction_m"] = 5.0
    with runtime.network_revision_guard() as invalidate:
        result = store_revision(registry, "tagum_site_a", old.fingerprint, candidate)
        invalidate()
    assert runtime._engine is None and runtime._selected_scenario_id is None
    assert load_registered_network("tagum_site_a", registry_path=registry).fingerprint == result["new_sha256"]
