"""Verify the disposable shell builder selects the intended frontend."""
import os
import sys
from pathlib import Path

import pytest

from desktop import build_shell_prototype

pytestmark = pytest.mark.skipif(os.name != "nt", reason="Windows-only prototype builder")


def test_shell_builder_uses_explicit_frontend_without_overwriting_dist(tmp_path, monkeypatch):
    root = tmp_path / "repository"
    (root / "desktop").mkdir(parents=True)
    frontend = tmp_path / "separate-frontend"
    frontend.mkdir()
    (frontend / "index.html").write_text("desktop build", encoding="utf-8")
    calls = []
    monkeypatch.setattr(build_shell_prototype, "__file__", str(root / "desktop" / "build_shell_prototype.py"))
    monkeypatch.setattr(sys, "argv", ["build_shell_prototype", "--frontend", str(frontend)])
    monkeypatch.setattr("desktop.engine_manifest.create_manifest", lambda _root: {"test": True})
    def fake_build(command, **kwargs):
        calls.append((command, kwargs))
        bundle = Path(command[command.index("--distpath") + 1]) / "SmartFlowPrototype"
        bundle.mkdir(parents=True)
        (bundle / "SmartFlow.exe").write_bytes(b"shell")
        (bundle / "SmartFlowWorker.exe").write_bytes(b"worker")
    monkeypatch.setattr(build_shell_prototype.subprocess, "run", fake_build)
    build_shell_prototype.main()
    assert calls[0][1]["env"]["SMARTFLOW_PROTOTYPE_FRONTEND"] == str(frontend.resolve())
    assert not (root / "dist").exists()
    records = list((root / "tmp").glob("desktop-shell-experiment-*/build-inventory.json"))
    assert len(records) == 1 and '"SmartFlowWorker.exe"' in records[0].read_text(encoding="utf-8")


def test_shell_builder_rejects_missing_frontend(tmp_path, monkeypatch):
    monkeypatch.setattr(sys, "argv", ["build_shell_prototype", "--frontend", str(tmp_path)])
    with pytest.raises(SystemExit, match="Build the desktop frontend"):
        build_shell_prototype.main()
