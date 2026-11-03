import pytest

from desktop.build_inventory import inventory, verify


def test_inventory_detects_changed_added_and_missing_files(tmp_path):
    (tmp_path / "SmartFlow.exe").write_bytes(b"shell")
    worker = tmp_path / "SmartFlowWorker.exe"
    worker.write_bytes(b"worker")
    recorded = inventory(tmp_path)
    assert verify(tmp_path, recorded)
    worker.write_bytes(b"changed")
    assert not verify(tmp_path, recorded)
    worker.write_bytes(b"worker")
    extra = tmp_path / "extra"
    extra.write_bytes(b"extra")
    assert not verify(tmp_path, recorded)
    extra.unlink()
    worker.unlink()
    with pytest.raises(ValueError, match="two-executable"):
        verify(tmp_path, recorded)
