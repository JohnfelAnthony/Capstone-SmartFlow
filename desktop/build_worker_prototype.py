"""Build a disposable Windows worker experiment; not a distribution build."""
from __future__ import annotations

import os
import json
import subprocess
import sys
import uuid
import argparse
from pathlib import Path

from desktop.paths import STUDY_SITE_RESOURCE_NAMES, network_resource_names


def main() -> None:
    parser = argparse.ArgumentParser(description="Build a disposable worker experiment")
    parser.add_argument("--with-ml", action="store_true", help="Include the checked CPU-only ML stack")
    args = parser.parse_args()
    if os.name != "nt":
        raise SystemExit("Build this Windows experiment on Windows")
    root = Path(__file__).resolve().parents[1]
    output = root / "tmp" / ("desktop-worker-experiment-" + uuid.uuid4().hex[:12])
    output.mkdir(parents=True, exist_ok=False)
    from desktop.engine_manifest import create_manifest
    manifest = output / "engine-manifest.json"
    manifest.write_text(json.dumps(create_manifest(root), indent=2), encoding="utf-8")
    if args.with_ml:
        from desktop.packaging_checks import require_cpu_ml
        require_cpu_ml()
    command = [sys.executable, "-m", "PyInstaller", "--noconfirm", "--onedir", "--name", "SmartFlowWorker",
               "--paths", str(root), "--distpath", str(output / "dist"), "--workpath", str(output / "work"),
               "--specpath", str(output)]
    if not args.with_ml:
        command.extend(["--exclude-module", "torch", "--exclude-module", "stable_baselines3"])
    else:
        command.extend(["--collect-data", "stable_baselines3"])
    for module in ("tools.train_ql", "tools.train_dql", "tools.train_ppo", "tools.evaluate_controllers", "desktop.serve", "desktop.bootstrap"):
        command.extend(["--hidden-import", module])
    # The frozen worker verifies the engine inventory before starting.
    for source in sorted((root / "simulation").glob("*.py")):
        command.extend(["--add-data", f"{source};simulation"])
    command.extend(["--add-data", f"{root / 'simulation' / 'metric_definitions.json'};simulation"])
    command.extend(["--add-data", f"{manifest};."])
    for name in network_resource_names(root / "data" / "networks"):
        command.extend(["--add-data", f"{root / 'data' / 'networks' / name};data/networks"])
    for name in STUDY_SITE_RESOURCE_NAMES:
        command.extend(["--add-data", f"{root / 'data' / 'sites' / name};data/sites"])
    command.append(str(root / "desktop" / "worker_entry.py"))
    print(f"Building disposable worker experiment in {output}", flush=True)
    environment = os.environ.copy()
    environment.pop("PYTHONPATH", None)
    environment["PYTHONNOUSERSITE"] = "1"
    subprocess.run(command, cwd=root, env=environment, check=True)
    print(f"Worker experiment: {output / 'dist' / 'SmartFlowWorker' / 'SmartFlowWorker.exe'}", flush=True)


if __name__ == "__main__":
    main()
