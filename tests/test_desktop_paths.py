from pathlib import Path
import json
import os
import shutil
import subprocess
import sys

import pytest

from desktop.paths import DesktopPaths, _source_hash, network_resource_names


def test_seed_is_idempotent_and_keeps_user_data(tmp_path):
    resources = tmp_path / "resources"
    source = resources / "data" / "networks"
    source.mkdir(parents=True)
    names = ("registry.json", "tagum_network.json", "tagum_site_a.json", "tagum_site_b.json")
    for name in names:
        (source / name).write_text("original", encoding="utf-8")
    (source / "registry.json").write_text('{"networks":[{"file":"tagum_site_a.json"},{"file":"tagum_site_b.json"}]}', encoding="utf-8")
    paths = DesktopPaths.discover(data_root=tmp_path / "user data" / "测试", resources=resources)
    paths.seed_networks()
    changed = paths.root / "data" / "networks" / "tagum_site_b.json"
    changed.write_text("user edit", encoding="utf-8")
    paths.seed_networks()
    assert changed.read_text(encoding="utf-8") == "user edit"
    assert Path(paths.environment()["SMARTFLOW_DB_PATH"]).parent == paths.root / "data"
    assert Path(paths.environment()["SMARTFLOW_DATA_DIR"]) == paths.root / "data"
    assert Path(paths.environment()["SMARTFLOW_IMPORT_DIR"]) == paths.root / "data" / "imports"
    assert Path(paths.environment()["SMARTFLOW_STUDY_ROOT"]) == paths.root
    assert (source / "tagum_site_b.json").read_text(encoding="utf-8") == "original"


def test_incomplete_resources_fail_before_writing(tmp_path):
    resources = tmp_path / "resources"
    resources.mkdir()
    paths = DesktopPaths.discover(data_root=tmp_path / "data", resources=resources)
    with pytest.raises(FileNotFoundError):
        paths.seed_networks()
    assert not paths.root.exists()


@pytest.mark.parametrize("customized", [False, True])
def test_upgrade_keeps_prior_networks_and_leaves_custom_layouts_alone(tmp_path, monkeypatch, customized):
    from simulation.road_network import RoadNetwork

    resources = tmp_path / "installation"
    source = resources / "data" / "networks"
    packaged = Path(__file__).resolve().parents[1] / "data" / "networks"
    source.mkdir(parents=True)
    for name in network_resource_names(packaged):
        shutil.copyfile(packaged / name, source / name)
    paths = DesktopPaths.discover(data_root=tmp_path / "desktop data", resources=resources)
    paths.seed_networks()
    target = paths.root / "data" / "networks"
    bundled = json.loads((source / "registry.json").read_text(encoding="utf-8"))
    old_entries = []
    old_hashes = {}
    old_fingerprints = {}
    for entry in bundled["networks"]:
        stock_path = target / entry["file"]
        payload = json.loads(stock_path.read_text(encoding="utf-8"))
        payload["name"] += " (previous default)"
        stock = json.dumps(payload).encode("utf-8")
        stock_path.write_bytes(stock)
        old_entries.append({"id": entry["id"], "file": entry["file"]})
        old_hashes[entry["id"]] = _source_hash(stock)
        old_fingerprints[entry["id"]] = RoadNetwork(payload).fingerprint
    monkeypatch.setattr("desktop.paths._LEGACY_STOCK_HASHES", old_hashes)
    registry = target / "registry.json"
    legacy_registry = json.dumps({"networks": old_entries}).encode("utf-8")
    registry.write_bytes(legacy_registry)
    if customized:
        edited = target / old_entries[0]["file"]
        edited.write_bytes(edited.read_bytes() + b" ")

    paths.upgrade_stock_networks()
    updated = registry.read_bytes()
    if customized:
        assert updated == legacy_registry
        assert edited.read_bytes().endswith(b" ")
        return
    for entry, original in zip(json.loads(updated)["networks"], bundled["networks"], strict=True):
        assert entry["file"] != original["file"]
        assert (target / entry["file"]).read_bytes() == (source / original["file"]).read_bytes()
        assert {"file": original["file"], "sha256": old_fingerprints[entry["id"]]} in entry["revision_history"]
    assert all((target / name).is_file() for name in network_resource_names(source))
    paths.upgrade_stock_networks()
    assert registry.read_bytes() == updated


def test_desktop_report_and_training_defaults_stay_in_data_root(tmp_path):
    data = tmp_path / "Desktop data" / "data"
    environment = {key: value for key, value in os.environ.items() if not key.startswith("SMARTFLOW_")}
    environment.update({"SMARTFLOW_SECRET_KEY": "isolated-test-secret", "SMARTFLOW_DATA_DIR": str(data),
                        "SMARTFLOW_DB_PATH": str(data / "fixture.db")})
    code = """
from pathlib import Path
import os
from backend.main import report_export_directory
from tools.train_ql import _default_output_path as ql
from tools.train_dql import _default_output_path as dql
from tools.train_ppo import _default_output_path as ppo
from tools.evaluate_controllers import _latest_model_path
root = Path(os.environ['SMARTFLOW_DATA_DIR']).resolve()
for path in (report_export_directory(), ql(), dql(), ppo()):
    assert root in path.resolve().parents, path
model = root / 'models' / 'ql' / 'fixture.json'
model.parent.mkdir(parents=True)
model.write_text('{}')
assert _latest_model_path('ql') == model
"""
    result = subprocess.run([sys.executable, "-c", code], env=environment, text=True, capture_output=True, timeout=60)
    assert result.returncode == 0, result.stdout + result.stderr


def test_web_data_default_is_unchanged(monkeypatch):
    from services.data_paths import data_directory
    monkeypatch.delenv("SMARTFLOW_DATA_DIR", raising=False)
    assert data_directory() == Path(__file__).resolve().parents[1] / "data"
