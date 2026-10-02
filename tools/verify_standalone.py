"""Copy current source and rebuild it from a separate SmartFlow directory.

The source checkout and its ignored data are never modified. The caller chooses
an empty target directory; leave it in place for inspecting the evidence.
"""
from __future__ import annotations

import argparse
import hashlib
import os
import shutil
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SOURCE_DIRS = ("src", "public", "backend", "simulation", "services", "tools", "scripts", "tests", "docs", "assets", "deploy", ".agents")
ROOT_FILES = (
    "AGENTS.md", "README.md", "IMPLEMENTATION_HANDOFF.md", "PROJECT_HISTORY_AND_MIGRATION.md",
    "auth.py", "config.py", "database.py", "run_api.py", "components.json", "eslint.config.js",
    "index.html", "package.json", "package-lock.json", "requirements.txt", "requirements-dev.txt",
    "tsconfig.json", "tsconfig.app.json", "tsconfig.node.json", "vite.config.ts",
)


def copy_source(target: Path) -> None:
    if target.exists():
        raise ValueError(f"Target already exists: {target}")
    if target == ROOT or ROOT.is_relative_to(target):
        raise ValueError("Target must be a separate empty directory.")
    target.mkdir(parents=True)
    ignore = shutil.ignore_patterns("__pycache__", "*.pyc", "generated", "node_modules", ".venv", "dist")
    for directory in SOURCE_DIRS:
        shutil.copytree(ROOT / directory, target / directory, ignore=ignore)
    for filename in ROOT_FILES:
        shutil.copy2(ROOT / filename, target / filename)
    shutil.copytree(ROOT / "data" / "networks", target / "data" / "networks")
    shutil.copytree(ROOT / "data" / "scenarios", target / "data" / "scenarios")
    for manuscript in (ROOT / "docs" / "research_sources").glob("*.pdf"):
        copied = target / "docs" / "research_sources" / manuscript.name
        if hashlib.sha256(manuscript.read_bytes()).digest() != hashlib.sha256(copied.read_bytes()).digest():
            raise RuntimeError(f"Manuscript copy did not match: {manuscript.name}")


def run(command: list[str], cwd: Path, env: dict[str, str]) -> None:
    print(f"Running in {cwd}: {' '.join(command)}", flush=True)
    subprocess.run(command, cwd=cwd, env=env, check=True)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("target", type=Path, help="New empty destination directory")
    args = parser.parse_args()
    target = args.target.resolve()
    copy_source(target)
    env = os.environ.copy()
    env.pop("PYTHONPATH", None)
    for setting in ("SMARTFLOW_NETWORK_PATH", "SMARTFLOW_TRAINING_CANCEL_FILE", "VITE_SMARTFLOW_API_BASE_URL"):
        env.pop(setting, None)
    env.update({
        "SMARTFLOW_ENV": "development",
        "SMARTFLOW_DB_PATH": str(target / "data" / "standalone-check.db"),
        "SMARTFLOW_IMPORT_DIR": str(target / "data" / "imports"),
        "SMARTFLOW_SECRET_KEY": "standalone-smoke-only-secret",
        "SMARTFLOW_BOOTSTRAP_ADMIN_PASSWORD": "StandaloneSmoke42!",
        "NPM_CONFIG_CACHE": str(target / ".npm-cache"),
        "PIP_CACHE_DIR": str(target / ".pip-cache"),
    })
    npm = "npm.cmd" if os.name == "nt" else "npm"
    run([npm, "ci"], target, env)
    run([sys.executable, "-m", "venv", ".venv"], target, env)
    python = target / ".venv" / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
    run([str(python), "-m", "pip", "install", "-r", "requirements-dev.txt"], target, env)
    run([str(python), "-m", "unittest", "discover", "-s", "tests", "-v"], target, env)
    run([npm, "run", "check:api"], target, env)
    run([npm, "run", "lint"], target, env)
    run([npm, "run", "build"], target, env)
    smoke = (
        "from fastapi.testclient import TestClient; "
        "from backend.main import app; "
        "client=TestClient(app); client.__enter__(); "
        "assert client.get('/api/health').status_code == 200; "
        "assert client.post('/api/auth/login', json={'username':'admin','password':'StandaloneSmoke42!'}).status_code == 200; "
        "scenario=next(row for row in client.get('/api/scenarios').json()['scenarios'] if row['traffic_density']=='Single'); "
        "assert client.post('/api/simulation/configure', json={'scenario_id':scenario['id']}).status_code == 200; "
        "assert client.post('/api/simulation/start', json={}).status_code == 200; "
        "assert client.post('/api/simulation/stop', json={}).status_code == 200; "
        "client.__exit__(None,None,None); print('Standalone API smoke passed')"
    )
    run([str(python), "-c", smoke], target, env)
    print(f"Separate-location rebuild and smoke passed: {target}")


if __name__ == "__main__":
    main()
