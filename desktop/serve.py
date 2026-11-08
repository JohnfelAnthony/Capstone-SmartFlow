"""Source-mode desktop backend process with a private readiness handshake."""
from __future__ import annotations

import asyncio
import json
import os
import socket
import sqlite3
import sys
from pathlib import Path

from desktop.paths import DesktopPaths
from desktop.instance_lock import InstanceLock


async def serve(request: dict) -> None:
    paths = DesktopPaths.discover(data_root=Path(request["data_root"]), resources=Path(request["resources"]))
    if paths.root == paths.resources or paths.resources in paths.root.parents:
        raise ValueError("Desktop data must be outside the installation resources")
    with InstanceLock(paths.root):
        await _serve_locked(request, paths)


async def _serve_locked(request: dict, paths: DesktopPaths) -> None:
    database = Path(paths.environment()["SMARTFLOW_DB_PATH"])
    secret_path = paths.root / "config" / "installation-secret"
    if not database.is_file() or not secret_path.is_file():
        raise ValueError("Desktop setup must complete before starting the backend")
    secret = secret_path.read_text(encoding="ascii").strip()
    if len(secret) < 40:
        raise ValueError("Desktop installation secret is invalid")
    nonce = request.get("nonce")
    if not isinstance(nonce, str) or len(nonce) < 24:
        raise ValueError("A private startup identity is required")
    frontend = Path(request["frontend"]).resolve()
    if not (frontend / "index.html").is_file():
        raise ValueError("Desktop frontend build is missing")

    # Fail closed before backend startup can modify the database schema or data.
    from desktop.migration_snapshot import snapshot_before_start
    try:
        snapshot_before_start(database, paths.root / "data")
    except (OSError, sqlite3.Error, ValueError) as exc:
        raise RuntimeError(
            f"Could not create the pre-start database snapshot in {paths.root / 'data' / 'pre-start-snapshots'}. "
            f"Check available disk space and folder access; your database was not migrated. Details: {exc}"
        ) from exc
    # Claim before any migration so an interrupted newer upgrade cannot later
    # be mistaken for a database safe for an older cooperating desktop build.
    from desktop.schema_guard import claim_schema_version
    claim_schema_version(database)

    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as listener:
        if hasattr(socket, "SO_EXCLUSIVEADDRUSE"):
            listener.setsockopt(socket.SOL_SOCKET, socket.SO_EXCLUSIVEADDRUSE, 1)
        listener.bind(("127.0.0.1", 0))
        listener.listen(128)
        listener.setblocking(False)
        origin = f"http://127.0.0.1:{listener.getsockname()[1]}"
        for name in tuple(os.environ):
            if name.startswith("SMARTFLOW_"):
                del os.environ[name]
        os.environ.update({**paths.environment(), "SMARTFLOW_SECRET_KEY": secret,
                           "SMARTFLOW_PUBLIC_BASE_URL": origin, "SMARTFLOW_ALLOWED_ORIGINS": origin})
        control_root = Path(request.get("control_root", str(paths.root))).resolve()
        if paths.root == control_root:
            paths.upgrade_stock_networks()

        import uvicorn
        from backend.main import app
        from desktop.server import desktop_app

        from desktop.restore_requests import RestoreRequests
        restores = RestoreRequests(paths, control_root, frontend)
        server = uvicorn.Server(uvicorn.Config(desktop_app(app, frontend, origin, paths.root / "config" / "preferences.json", restores), log_level="warning", access_log=False))
        task = asyncio.create_task(server.serve(sockets=[listener]))
        for _ in range(600):
            if server.started:
                print(json.dumps({"ready": True, "origin": origin, "nonce": nonce}), flush=True)
                control = asyncio.create_task(_control_loop(server, restores))
                await task
                control.cancel()
                return
            if task.done():
                await task
                raise RuntimeError("Desktop backend stopped before it became ready")
            await asyncio.sleep(.05)
        server.should_exit = True
        await task
        raise TimeoutError("Desktop backend did not become ready in time")


async def _control_loop(server, restores):
    from backend.simulation_runtime import simulation_runtime
    from desktop.shutdown import reserve_idle_shutdown
    from services.workload_admission import workload_admission
    while True:
        line = await asyncio.to_thread(sys.stdin.readline)
        if not line:
            server.should_exit = True
            return
        try:
            request = json.loads(line)
            if request == {"command": "poll_restore"}:
                print(json.dumps({"candidate": restores.claim()}), flush=True)
                continue
            if request == {"command": "release_restore"}:
                restores.release()
                print(json.dumps({"released": True}), flush=True)
                continue
            if request != {"command": "shutdown_if_idle"}:
                raise ValueError("Unknown desktop control command")
            lease, reason = reserve_idle_shutdown(workload_admission, simulation_runtime)
            print(json.dumps({"accepted": lease is not None, "reason": reason}), flush=True)
            if lease is not None:
                server.should_exit = True
                return
        except (ValueError, TypeError) as exc:
            print(json.dumps({"accepted": False, "reason": str(exc)}), flush=True)


def main() -> None:
    try:
        asyncio.run(serve(json.loads(sys.stdin.readline())))
    except Exception as exc:
        print(json.dumps({"ready": False, "error": str(exc)}), flush=True)
        raise SystemExit(1) from None


if __name__ == "__main__":
    main()
