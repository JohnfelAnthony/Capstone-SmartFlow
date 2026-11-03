import os
import subprocess
import sys
from pathlib import Path

import pytest

from desktop import worker_entry
from desktop.worker_commands import service_prefix, worker_prefix


@pytest.mark.parametrize("mode,module", worker_entry.WORKERS.items())
def test_dispatch_maps_only_allowlisted_modes_and_preserves_arguments(monkeypatch, mode, module):
    calls = []
    monkeypatch.setattr(worker_entry.runpy, "run_module", lambda name, run_name: calls.append((name, run_name, list(sys.argv))))
    monkeypatch.setattr(sys, "argv", ["original"])
    worker_entry.dispatch([mode, "--scenario-file", "path with spaces.json", "--seeds", "101,102"])
    assert calls == [(module, "__main__", [module, "--scenario-file", "path with spaces.json", "--seeds", "101,102"])]


def test_commands_refuse_unknown_or_missing_frozen_worker(tmp_path):
    with pytest.raises(ValueError):
        worker_prefix("arbitrary.py", "python")
    executable = tmp_path / "SmartFlow.exe"
    with pytest.raises(FileNotFoundError):
        worker_prefix("train-ql", "python", frozen=True, executable=str(executable))
    worker = tmp_path / "SmartFlowWorker.exe"
    worker.write_bytes(b"")
    assert worker_prefix("train-ql", "python", frozen=True, executable=str(executable)) == [str(worker), "train-ql"]
    assert worker_prefix("evaluate", "python", frozen=False) == ["python", "-u", "tools/evaluate_controllers.py"]
    assert service_prefix("serve", frozen=True, executable=str(executable)) == [str(worker), "serve"]
    assert service_prefix("bootstrap", frozen=False, executable="python") == ["python", "-m", "desktop.bootstrap"]
    with pytest.raises(ValueError):
        service_prefix("arbitrary", frozen=False)


def test_source_training_prefixes_match_existing_script_contract():
    from services.rl_training_service import TRAINING_SCRIPT
    for algorithm, script in TRAINING_SCRIPT.items():
        assert worker_prefix(f"train-{algorithm}", "python", frozen=False)[-1] == script


def test_source_worker_entry_runs_real_cli_help_and_rejects_unknown():
    root = Path(__file__).resolve().parents[1]
    environment = {**os.environ, "SMARTFLOW_SECRET_KEY": "worker-help-test"}
    success = subprocess.run([sys.executable, "-m", "desktop.worker_entry", "train-ql", "--help"], cwd=root,
                             env=environment, text=True, capture_output=True, timeout=45)
    assert success.returncode == 0, success.stderr
    assert "--episodes" in success.stdout
    failure = subprocess.run([sys.executable, "-m", "desktop.worker_entry", "arbitrary.py"], cwd=root,
                             env=environment, text=True, capture_output=True, timeout=10)
    assert failure.returncode == 2
    assert "allowed SmartFlow worker mode" in failure.stderr
