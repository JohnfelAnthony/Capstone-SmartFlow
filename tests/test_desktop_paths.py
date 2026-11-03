from pathlib import Path
import os
import subprocess
import sys

import pytest

from desktop.paths import DesktopPaths


def test_seed_is_idempotent_and_keeps_user_data(tmp_path):
    resources = tmp_path / "resources"
    source = resources / "data" / "networks"
    source.mkdir(parents=True)
    names = ("registry.json", "tagum_network.json", "tagum_site_a.json", "tagum_site_b.json")
    for name in names:
        (source / name).write_text("original", encoding="utf-8")
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
