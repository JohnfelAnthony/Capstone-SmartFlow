import json
from pathlib import Path

import pytest

from desktop.engine_manifest import create_manifest, verify_manifest
from services import site_validation


def test_manifest_equivalence_and_frozen_identity(tmp_path, monkeypatch):
    root = Path(__file__).resolve().parents[1]
    source = root / "simulation"
    target = tmp_path / "simulation"
    target.mkdir()
    for path in source.glob("*.py"):
        (target / path.name).write_bytes(path.read_bytes())
    manifest = create_manifest(tmp_path)
    (tmp_path / "engine-manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    expected = site_validation.engine_content_sha256()
    assert verify_manifest(tmp_path)["engine_content_sha256"] == expected
    (tmp_path / "services").mkdir()
    monkeypatch.setattr(site_validation, "__file__", str(tmp_path / "services" / "site_validation.py"))
    monkeypatch.setattr(site_validation.sys, "frozen", True, raising=False)
    assert site_validation.engine_content_sha256() == expected
    (target / "traffic_engine.py").write_text("modified", encoding="utf-8")
    with pytest.raises(ValueError, match="cannot be verified"):
        site_validation.engine_content_sha256()


@pytest.mark.parametrize("change", ["missing", "extra", "missing_manifest", "invalid_manifest"])
def test_manifest_rejects_missing_or_changed_inventory(tmp_path, change):
    root = Path(__file__).resolve().parents[1]
    target = tmp_path / "simulation"
    target.mkdir()
    for path in (root / "simulation").glob("*.py"):
        (target / path.name).write_bytes(path.read_bytes())
    manifest = create_manifest(tmp_path)
    file = tmp_path / "engine-manifest.json"
    file.write_text(json.dumps(manifest), encoding="utf-8")
    if change == "missing":
        (target / "traffic_engine.py").unlink()
    elif change == "extra":
        (target / "unexpected.py").write_text("pass", encoding="utf-8")
    elif change == "missing_manifest":
        file.unlink()
    else:
        file.write_text("{}", encoding="utf-8")
    with pytest.raises(ValueError, match="cannot be verified"):
        verify_manifest(tmp_path)
