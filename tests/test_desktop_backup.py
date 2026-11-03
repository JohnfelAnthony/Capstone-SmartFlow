import json
import zipfile
from pathlib import Path

import pytest

import config
import database
from services import backup_bundle


def test_desktop_evidence_and_preferences_restore_to_stage(tmp_path, monkeypatch):
    root = tmp_path / "desktop"
    files = {
        "config/preferences.json": '{"smartflow-theme":"light"}',
        "data/sites/tagum_site_a_mapping.json": '{"site":"fixture"}',
        "data/sites/tagum_site_a_ledger.json": '{"day":"synthetic"}',
        "docs/reports/site-validation-tagum_site_a-validation-fixture.json": '{"decision":"FAIL"}',
    }
    for name, contents in files.items():
        path = root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(contents, encoding="utf-8")
    (root / "config" / "installation-secret").write_text("must-not-be-in-backup", encoding="utf-8")
    monkeypatch.setenv("SMARTFLOW_STUDY_ROOT", str(root))
    monkeypatch.setattr(config, "DB_PATH", str(root / "data" / "fixture.db"))
    database.init_db()
    filename = backup_bundle.create_bundle(None)
    archive = database._resolve_backup_path(filename)
    with zipfile.ZipFile(archive) as bundle:
        manifest = json.loads(bundle.read("manifest.json"))
        assert set(manifest["desktop_evidence"]) == set(files)
        assert not any("installation-secret" in name for name in bundle.namelist())
    backup = next(item for item in database.list_backups() if item["filename"] == filename)
    stage = backup_bundle.restore_bundle_to_stage(backup["id"])
    environment = json.loads((stage / "restore_environment.json").read_text(encoding="utf-8"))
    restored_root = Path(environment["SMARTFLOW_STUDY_ROOT"])
    assert restored_root.is_relative_to(stage)
    for name, contents in files.items():
        assert (restored_root / name).read_text(encoding="utf-8") == contents
    assert not (restored_root / "config" / "installation-secret").exists()


@pytest.mark.parametrize("name", ["data/sites/../secret.json", "data/sites/a\\b.json", "config/installation-secret", "docs/reports/../../secret.json"])
def test_restore_rejects_unsafe_desktop_evidence_names(tmp_path, name):
    member = "files/desktop/" + name
    manifest = {"desktop_evidence": {name: member}, "files": {member: {}}}
    with pytest.raises(ValueError):
        backup_bundle._desktop_evidence_layout(tmp_path, manifest, {})


def test_display_path_drops_only_the_extended_prefix():
    from pathlib import Path
    from services.backup_bundle import display_path
    assert display_path(Path("\\\\?\\C:\\data\\restore-1")) == "C:\\data\\restore-1"
    assert display_path(Path("\\\\?\\UNC\\host\\share\\x")) == "\\\\host\\share\\x"
    assert display_path(Path(r"C:\data")) == r"C:\data"
