"""Allowlisted command entry point for the future frozen worker executable."""
from __future__ import annotations

import multiprocessing
import runpy
import sys

WORKERS = {"train-ql": "tools.train_ql", "train-dql": "tools.train_dql", "train-ppo": "tools.train_ppo",
           "evaluate": "tools.evaluate_controllers"}
SERVICES = {"serve": "desktop.serve", "bootstrap": "desktop.bootstrap", "recover": "desktop.recover"}


def dispatch(arguments: list[str]) -> None:
    modes = {**WORKERS, **SERVICES}
    if not arguments or arguments[0] not in modes:
        raise ValueError("Choose an allowed SmartFlow worker mode: " + ", ".join(modes))
    module = modes[arguments[0]]
    sys.argv = [module, *arguments[1:]]
    runpy.run_module(module, run_name="__main__")


def main() -> None:
    multiprocessing.freeze_support()
    if len(sys.argv) < 2 or sys.argv[1] not in {**WORKERS, **SERVICES}:
        print("Choose an allowed SmartFlow worker mode: " + ", ".join({**WORKERS, **SERVICES}), file=sys.stderr)
        raise SystemExit(2)
    dispatch(sys.argv[1:])


if __name__ == "__main__":
    main()
