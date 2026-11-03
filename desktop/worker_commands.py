"""Build only known worker commands for source and frozen runtimes."""
from __future__ import annotations

import sys
from pathlib import Path

SCRIPTS = {"train-ql": "tools/train_ql.py", "train-dql": "tools/train_dql.py",
           "train-ppo": "tools/train_ppo.py", "evaluate": "tools/evaluate_controllers.py"}


def worker_prefix(mode: str, source_python: str, *, frozen: bool | None = None, executable: str | None = None) -> list[str]:
    if mode not in SCRIPTS:
        raise ValueError(f"Unsupported worker mode: {mode}")
    if frozen is None:
        frozen = bool(getattr(sys, "frozen", False))
    if not frozen:
        return [source_python, "-u", SCRIPTS[mode]]
    worker = Path(executable or sys.executable).resolve().parent / "SmartFlowWorker.exe"
    if not worker.is_file():
        raise FileNotFoundError("The packaged SmartFlow worker is missing; reinstall the application.")
    return [str(worker), mode]


def service_prefix(mode: str, *, frozen: bool | None = None, executable: str | None = None) -> list[str]:
    if mode not in {"serve", "bootstrap"}:
        raise ValueError(f"Unsupported desktop service: {mode}")
    if frozen is None:
        frozen = bool(getattr(sys, "frozen", False))
    if not frozen:
        return [executable or sys.executable, "-m", f"desktop.{mode}"]
    worker = Path(executable or sys.executable).resolve().parent / "SmartFlowWorker.exe"
    if not worker.is_file():
        raise FileNotFoundError("The packaged SmartFlow worker is missing; reinstall the application.")
    return [str(worker), mode]
