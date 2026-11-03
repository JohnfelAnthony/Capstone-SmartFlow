import io
import json
import zipfile
from pathlib import Path

import pytest

from services.field_observer_import import convert_revision
from services.reviewed_revision_store import import_reviewed_zip, revision_path
from tests.test_field_observer_import import NETWORK, build, mapping, vehicle


def archive(folder: Path, extra=None):
    stream = io.BytesIO()
    with zipfile.ZipFile(stream, "w", zipfile.ZIP_DEFLATED) as bundle:
        for item in folder.iterdir():
            bundle.write(item, item.name)
        if extra:
            bundle.writestr(*extra)
    return stream.getvalue()


def test_reviewed_archive_is_retained_and_converts_without_rewriting(tmp_path):
    original = build(tmp_path, vehicle("e1", 12.4, 20.0, cls="motorcycle"))
    root = tmp_path / "desktop"
    info = import_reviewed_zip(archive(original), root)
    retained = revision_path(root, info["id"])
    assert {item.name: item.read_bytes() for item in retained.iterdir()} == {item.name: item.read_bytes() for item in original.iterdir()}
    result = convert_revision(retained, mapping(), NETWORK, origin_s=0, start_s=0, end_s=900)
    assert result["summary"]["by_class"] == {"motorcycle": 1}
    (retained / "events.csv").write_text("changed", encoding="utf-8")
    with pytest.raises(ValueError, match="changed"):
        revision_path(root, info["id"])


@pytest.mark.parametrize("bad_name", ["../escape.csv", "nested/events.csv", "C:evil.csv", "unknown.txt"])
def test_unsafe_archive_is_rejected_without_publishing(tmp_path, bad_name):
    original = build(tmp_path, [])
    root = tmp_path / "desktop"
    with pytest.raises(ValueError, match="unsafe"):
        import_reviewed_zip(archive(original, (bad_name, "bad")), root)
    assert not list((root / "data" / "reviewed-revisions").iterdir())


def test_changed_and_unmanifested_evidence_is_rejected(tmp_path):
    original = build(tmp_path, [])
    (original / "events.csv").write_text("changed", encoding="utf-8")
    root = tmp_path / "desktop"
    with pytest.raises(ValueError, match="changed"):
        import_reviewed_zip(archive(original), root)
    assert not list((root / "data" / "reviewed-revisions").iterdir())
    manifest = json.loads((original / "manifest.json").read_text(encoding="utf-8"))
    manifest["artifact_sha256"].pop("events.csv")
    (original / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    with pytest.raises(ValueError):
        import_reviewed_zip(archive(original), root)
