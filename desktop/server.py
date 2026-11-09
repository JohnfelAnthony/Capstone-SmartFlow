"""Same-origin desktop frontend adapter; does not launch or configure SmartFlow."""
from __future__ import annotations

from pathlib import Path
from urllib.parse import urlsplit

from fastapi import FastAPI, Request
from fastapi.responses import FileResponse, JSONResponse


class LoopbackBoundary:
    """Limit the desktop app to one exact loopback origin, including websockets."""

    def __init__(self, app, origin: str):
        parsed = urlsplit(origin)
        if parsed.scheme != "http" or parsed.hostname != "127.0.0.1" or not parsed.port or parsed.path or parsed.query or parsed.fragment or parsed.username:
            raise ValueError("Desktop origin must be http://127.0.0.1:<port>")
        self.app = app
        self.origin = origin
        self.host = parsed.netloc

    async def __call__(self, scope, receive, send):
        if scope["type"] not in {"http", "websocket"}:
            await self.app(scope, receive, send)
            return
        headers = {}
        for key, value in scope.get("headers", []):
            name = key.lower()
            if name in headers and name in (b"host", b"origin"):
                await self.reject(scope, send)
                return
            headers[name] = value
        host_ok = headers.get(b"host", b"").decode("latin-1") == self.host
        origin = headers.get(b"origin")
        needs_origin = scope["type"] == "websocket" or scope.get("method", "GET") not in {"GET", "HEAD", "OPTIONS"}
        origin_ok = (origin is None and not needs_origin) or (origin is not None and origin.decode("latin-1") == self.origin)
        if not host_ok or not origin_ok:
            await self.reject(scope, send)
            return
        await self.app(scope, receive, send)

    @staticmethod
    async def reject(scope, send):
        if scope["type"] == "websocket":
            await send({"type": "websocket.close", "code": 1008})
        else:
            await JSONResponse({"detail": "Desktop access requires the local application origin."}, status_code=403)(scope, None, send)


def desktop_app(app: FastAPI, frontend: Path, origin: str, preferences_path: Path | None = None, restore_requests=None):
    """Append frontend routes after API routes; missing API/assets never become HTML."""
    root = Path(frontend).resolve()
    if not (root / "index.html").is_file():
        raise FileNotFoundError("Desktop frontend build is missing index.html")

    if preferences_path is not None:
        from desktop.preferences import DesktopPreferences
        preferences = DesktopPreferences(preferences_path)

        @app.get("/api/desktop/preferences", include_in_schema=False)
        def get_preferences():
            try:
                return preferences.read()
            except (ValueError, OSError) as exc:
                return JSONResponse({"detail": str(exc)}, status_code=500)

        @app.post("/api/desktop/preferences", include_in_schema=False)
        async def set_preferences(request: Request):
            try:
                body = await request.body()
                if len(body) > 16384:
                    raise ValueError("Preference request is too large")
                import json
                payload = json.loads(body)
                if not isinstance(payload, dict) or set(payload) != {"key", "value"}:
                    raise ValueError("Expected a preference key and value")
                preferences.update(payload["key"], payload["value"])
                return {"ok": True}
            except (ValueError, OSError) as exc:
                return JSONResponse({"detail": str(exc)}, status_code=400)

    if restore_requests is not None:
        from fastapi import Depends, HTTPException
        from backend.security import require_current_user
        from backend.main import require_admin

        @app.post("/api/desktop/rl/models/import", include_in_schema=False)
        async def import_rl_model(request: Request, user: dict = Depends(require_current_user)):
            require_admin(user)
            import asyncio
            import base64
            from desktop.model_import import MAX_REQUEST_BYTES, import_model, json_object

            body = bytearray()
            async for chunk in request.stream():
                if len(body) + len(chunk) > MAX_REQUEST_BYTES:
                    raise HTTPException(status_code=413, detail="The model upload exceeds the size limit.")
                body.extend(chunk)
            try:
                payload = json_object(body)
                name = payload["filename"]
                if (not isinstance(name, str) or not 1 <= len(name) <= 200
                        or any(not char.isprintable() or char in "/\\:" for char in name)):
                    raise ValueError("Invalid model filename.")
                if payload.get("trusted") is not True:
                    raise ValueError("Confirm that the model comes from a source you trust.")
                metadata = payload.get("metadata")
                if metadata is not None and payload.get("metadata_filename") != Path(name).with_suffix(".metadata.json").name:
                    raise ValueError("The metadata filename must match the ZIP filename.")
                content = base64.b64decode(payload["content"], validate=True)
                sidecar = base64.b64decode(metadata, validate=True) if metadata is not None else None
                return await asyncio.to_thread(import_model, name, content, sidecar)
            except (KeyError, TypeError, ValueError, OSError) as exc:
                raise HTTPException(status_code=422, detail=str(exc) or "Invalid SmartFlow model.") from exc

        @app.post("/api/desktop/backups/{backup_id}/activate", include_in_schema=False)
        def activate_backup(backup_id: int, user: dict = Depends(require_current_user)):
            require_admin(user)
            try:
                restore_requests.prepare(backup_id)
            except (ValueError, OSError) as exc:
                raise HTTPException(status_code=409, detail=str(exc)) from exc
            return {"message": "Backup verified. The desktop will restart; if work is active, stop it and retry."}

        @app.get("/api/desktop/reviewed-revisions", include_in_schema=False)
        def reviewed_revisions(user: dict = Depends(require_current_user)):
            require_admin(user)
            from services.reviewed_revision_store import list_revisions
            return {"revisions": list_revisions(restore_requests.paths.root)}

        @app.post("/api/desktop/reviewed-revisions", include_in_schema=False)
        async def import_reviewed(request: Request, user: dict = Depends(require_current_user)):
            require_admin(user)
            from services.reviewed_revision_store import MAX_ARCHIVE_BYTES, import_reviewed_zip
            content = bytearray()
            async for chunk in request.stream():
                if len(content) + len(chunk) > MAX_ARCHIVE_BYTES:
                    raise HTTPException(status_code=413, detail="Reviewed ZIP exceeds the 32 MB limit")
                content.extend(chunk)
            try:
                import asyncio
                return await asyncio.to_thread(import_reviewed_zip, bytes(content), restore_requests.paths.root)
            except (ValueError, OSError) as exc:
                raise HTTPException(status_code=422, detail=str(exc)) from exc

    @app.get("/{path:path}", include_in_schema=False)
    async def frontend_route(path: str, request: Request):
        if path == "api" or path.startswith("api/") or path == "assets" or path.startswith("assets/"):
            candidate = (root / path).resolve()
            if path.startswith("assets/") and root in candidate.parents and candidate.is_file():
                return FileResponse(candidate)
            return JSONResponse({"detail": "Not found"}, status_code=404)
        candidate = (root / path).resolve()
        if candidate != root and root not in candidate.parents:
            return JSONResponse({"detail": "Not found"}, status_code=404)
        if candidate.is_file():
            return FileResponse(candidate)
        if Path(path).suffix:
            return JSONResponse({"detail": "Not found"}, status_code=404)
        return FileResponse(root / "index.html")

    return LoopbackBoundary(app, origin)
