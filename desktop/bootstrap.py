"""Private first-run initialization for the source-mode desktop prototype.

The caller supplies credentials over stdin to a separate process, before importing
any SmartFlow configuration in that process. This module does not expose an API.
"""
from __future__ import annotations

import json
import os
import secrets
import sqlite3
import sys
import uuid
from contextlib import closing
from pathlib import Path

from desktop.paths import DesktopPaths


class WeakPasswordError(ValueError):
    """Administrator setup may safely retry a rejected password."""


def initialize(paths: DesktopPaths, password: str) -> None:
    if not isinstance(password, str) or not password:
        raise ValueError("A first administrator password is required")
    if paths.root == paths.resources or paths.resources in paths.root.parents:
        raise ValueError("Desktop data must be outside the installation resources")
    if any(name in sys.modules for name in ("config", "database", "auth")):
        raise RuntimeError("Desktop setup must run in a fresh process before application imports")
    database_path = Path(paths.environment()["SMARTFLOW_DB_PATH"])
    secret_path = paths.root / "config" / "installation-secret"
    if database_path.exists():
        raise FileExistsError("An existing desktop database will not be replaced")
    if secret_path.exists():
        secret = secret_path.read_text(encoding="ascii").strip()
        if len(secret) < 40:
            raise ValueError("Existing installation secret is invalid; restore it from backup")
    else:
        secret_path.parent.mkdir(parents=True, exist_ok=True)
        secret = secrets.token_urlsafe(48)
        try:
            with secret_path.open("x", encoding="ascii") as stream:
                stream.write(secret)
                stream.flush()
                os.fsync(stream.fileno())
        except FileExistsError:
            raise RuntimeError("Desktop setup is already running") from None

    paths.seed_networks()
    database_path.parent.mkdir(parents=True, exist_ok=True)
    staged = database_path.with_name(".setup-" + uuid.uuid4().hex + ".db")
    env = {**paths.environment(), "SMARTFLOW_DB_PATH": str(staged), "SMARTFLOW_SECRET_KEY": secret}
    # Desktop setup never inherits development credentials or hosted configuration.
    for name in tuple(os.environ):
        if name.startswith("SMARTFLOW_"):
            del os.environ[name]
    os.environ.update(env)
    try:
        import auth
        import config
        import database

        errors = auth.validate_password_strength(password)
        if errors:
            raise WeakPasswordError("; ".join(errors))
        if Path(config.DB_PATH).resolve() != staged.resolve():
            raise RuntimeError("Desktop setup must run in a fresh process before application imports")
        config.BOOTSTRAP_ADMIN_PASSWORD = password
        config.BOOTSTRAP_SECONDARY_ADMIN_PASSWORD = None
        config.BOOTSTRAP_STANDARD_USER_PASSWORD = None
        database.init_db()
        database.seed_data()
        with closing(sqlite3.connect(staged)) as connection:
            busy, _, _ = connection.execute("PRAGMA wal_checkpoint(TRUNCATE)").fetchone()
            if busy:
                raise RuntimeError("Could not finalize the new desktop database")
        # On Windows rename is atomic and refuses an existing destination.
        if os.name == "nt":
            os.rename(staged, database_path)
        else:
            os.link(staged, database_path)
    finally:
        staged.unlink(missing_ok=True)
        Path(str(staged) + "-wal").unlink(missing_ok=True)
        Path(str(staged) + "-shm").unlink(missing_ok=True)


def main() -> None:
    try:
        request = json.load(sys.stdin)
        paths = DesktopPaths.discover(data_root=Path(request["data_root"]), resources=Path(request["resources"]))
        initialize(paths, request["password"])
        print(json.dumps({"ok": True}))
    except WeakPasswordError as exc:
        print(json.dumps({"ok": False, "code": "weak_password", "error": str(exc)}))
        raise SystemExit(1) from None
    except Exception as exc:
        print(json.dumps({"ok": False, "error": str(exc)}))
        raise SystemExit(1) from None


if __name__ == "__main__":
    main()
