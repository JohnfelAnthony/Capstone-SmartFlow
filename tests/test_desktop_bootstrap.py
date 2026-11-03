import json
import os
import shutil
import sqlite3
import subprocess
import sys
from pathlib import Path

from werkzeug.security import check_password_hash


ROOT = Path(__file__).resolve().parents[1]


def setup(root, password):
    # Explicitly clear development bootstrap values, including secret and database.
    resources = root.parent / "packaged resources"
    target = resources / "data" / "networks"
    target.mkdir(parents=True, exist_ok=True)
    for name in ("registry.json", "tagum_network.json", "tagum_site_a.json", "tagum_site_b.json"):
        shutil.copyfile(ROOT / "data" / "networks" / name, target / name)
    environment = {key: value for key, value in os.environ.items() if not key.startswith("SMARTFLOW_")}
    return subprocess.run([sys.executable, "-m", "desktop.bootstrap"], cwd=ROOT, env=environment,
                          input=json.dumps({"data_root": str(root), "resources": str(resources), "password": password}),
                          text=True, capture_output=True, timeout=60)


def test_fresh_bootstrap_and_refusal_to_reset(tmp_path):
    root = tmp_path / "Desktop data"
    result = setup(root, "StrongPass123")
    assert result.returncode == 0, result.stdout + result.stderr
    assert "StrongPass123" not in result.stdout + result.stderr
    database_path = root / "data" / "smartflow.db"
    with sqlite3.connect(database_path) as connection:
        username, password_hash = connection.execute("SELECT username, password_hash FROM users").fetchone()
        assert username == "admin"
        assert "StrongPass123" not in password_hash
        assert check_password_hash(password_hash, "StrongPass123")
    secret = (root / "config" / "installation-secret").read_text()
    assert len(secret) >= 40
    retry = setup(root, "AnotherPass123")
    assert retry.returncode != 0
    assert "will not be replaced" in retry.stdout
    assert (root / "config" / "installation-secret").read_text() == secret


def test_weak_password_does_not_create_database(tmp_path):
    root = tmp_path / "weak"
    result = setup(root, "weak")
    assert result.returncode != 0
    assert json.loads(result.stdout)["code"] == "weak_password"
    assert not (root / "data" / "smartflow.db").exists()
    secret = (root / "config" / "installation-secret").read_text(encoding="ascii")
    retry = setup(root, "StrongPass123")
    assert retry.returncode == 0, retry.stdout + retry.stderr
    assert (root / "data" / "smartflow.db").is_file()
    assert (root / "config" / "installation-secret").read_text(encoding="ascii") == secret
