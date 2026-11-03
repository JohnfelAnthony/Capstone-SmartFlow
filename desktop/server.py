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
        from pydantic import BaseModel, Field, ValidationError
        from backend.security import require_current_user
        from backend.main import require_admin
        from desktop.site_validation_jobs import DesktopValidationJobs
        from services.workload_admission import WorkloadConflict

        validation_jobs = DesktopValidationJobs(restore_requests.paths.root)

        class ConversionPreviewRequest(BaseModel):
            mapping: dict
            origin_s: float = Field(ge=0, allow_inf_nan=False)
            start_s: float = Field(ge=0, allow_inf_nan=False)
            end_s: float = Field(ge=0, allow_inf_nan=False)

        class ConversionCreateRequest(ConversionPreviewRequest):
            name: str = Field(min_length=1, max_length=150)
            collected_on: str = Field(min_length=10, max_length=10)
            source_kind: str
            expected_network_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
            expected_mapping_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
            expected_manifest_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")

        class SiteValidationRequest(BaseModel):
            scenario_id: int = Field(ge=1, strict=True)
            revision_id: str = Field(pattern=r"^[0-9a-f]{32}$")
            purpose: str
            origin_s: float = Field(ge=0, allow_inf_nan=False, strict=True)
            start_s: float = Field(ge=0, allow_inf_nan=False, strict=True)
            end_s: float = Field(ge=0, allow_inf_nan=False, strict=True)

        class StudyInputRequest(BaseModel):
            document: dict
            expected_sha256: str | None = Field(default=None, pattern=r"^[0-9a-f]{64}$")

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

        @app.post("/api/desktop/reviewed-revisions/{revision_id}/conversion-preview", include_in_schema=False)
        async def conversion_preview(revision_id: str, request: Request, user: dict = Depends(require_current_user)):
            require_admin(user)
            from desktop.reviewed_conversion import preview_conversion
            import asyncio
            import json
            body = bytearray()
            async for chunk in request.stream():
                if len(body) + len(chunk) > 2 * 1024 * 1024:
                    raise HTTPException(status_code=413, detail="Mapping request exceeds 2 MB")
                body.extend(chunk)
            try:
                data = ConversionPreviewRequest.model_validate(json.loads(body))
                return await asyncio.to_thread(preview_conversion, study_root=restore_requests.paths.root,
                                               revision_id=revision_id, **data.model_dump())
            except (ValueError, OSError, TypeError, KeyError, ValidationError) as exc:
                raise HTTPException(status_code=422, detail=str(exc)) from exc

        @app.post("/api/desktop/reviewed-revisions/{revision_id}/create-scenario", include_in_schema=False)
        async def create_reviewed_scenario(revision_id: str, request: Request, user: dict = Depends(require_current_user)):
            require_admin(user)
            from desktop.reviewed_conversion import create_scenario_from_review
            import asyncio
            import json
            body = bytearray()
            async for chunk in request.stream():
                if len(body) + len(chunk) > 2 * 1024 * 1024:
                    raise HTTPException(status_code=413, detail="Mapping request exceeds 2 MB")
                body.extend(chunk)
            try:
                data = ConversionCreateRequest.model_validate(json.loads(body))
                return await asyncio.to_thread(create_scenario_from_review, study_root=restore_requests.paths.root,
                                               revision_id=revision_id, user_id=user["id"], **data.model_dump())
            except (ValueError, OSError, TypeError, KeyError, ValidationError) as exc:
                raise HTTPException(status_code=422, detail=str(exc)) from exc

        @app.post("/api/desktop/site-validation-jobs", include_in_schema=False)
        async def start_site_validation(request: Request, user: dict = Depends(require_current_user)):
            require_admin(user)
            import asyncio
            import json
            body = bytearray()
            async for chunk in request.stream():
                if len(body) + len(chunk) > 16384:
                    raise HTTPException(status_code=413, detail="Validation request exceeds 16 KB")
                body.extend(chunk)
            try:
                data = SiteValidationRequest.model_validate(json.loads(body))
                return await asyncio.to_thread(validation_jobs.start, **data.model_dump())
            except WorkloadConflict as exc:
                raise HTTPException(status_code=409, detail=str(exc)) from exc
            except (ValueError, OSError, TypeError, KeyError, ValidationError) as exc:
                raise HTTPException(status_code=422, detail=str(exc)) from exc

        @app.get("/api/desktop/site-validation-jobs", include_in_schema=False)
        def list_site_validation(user: dict = Depends(require_current_user)):
            require_admin(user)
            return {"jobs": validation_jobs.list()}

        @app.get("/api/desktop/site-validation-jobs/{job_id}", include_in_schema=False)
        def get_site_validation(job_id: str, user: dict = Depends(require_current_user)):
            require_admin(user)
            job = validation_jobs.get(job_id)
            if job is None:
                raise HTTPException(status_code=404, detail="Validation job not found")
            return job

        @app.get("/api/desktop/study-inputs/{site}", include_in_schema=False)
        def study_input_status(site: str, user: dict = Depends(require_current_user)):
            require_admin(user)
            from desktop.study_inputs import status
            try:
                return status(restore_requests.paths.root, site)
            except (ValueError, OSError) as exc:
                raise HTTPException(status_code=422, detail=str(exc)) from exc

        @app.post("/api/desktop/study-inputs/{site}/{kind}", include_in_schema=False)
        async def import_study_input(site: str, kind: str, request: Request, user: dict = Depends(require_current_user)):
            require_admin(user)
            from desktop.study_inputs import StaleStudyInput, import_input
            from database import log_audit_event
            import asyncio
            import json
            body = bytearray()
            async for chunk in request.stream():
                if len(body) + len(chunk) > 2 * 1024 * 1024:
                    raise HTTPException(status_code=413, detail="Study input request exceeds 2 MB")
                body.extend(chunk)
            try:
                data = StudyInputRequest.model_validate(json.loads(body))
                return await asyncio.to_thread(import_input, root=restore_requests.paths.root, site=site, kind=kind,
                                               user_id=user["id"], audit=log_audit_event, **data.model_dump())
            except (StaleStudyInput, WorkloadConflict) as exc:
                raise HTTPException(status_code=409, detail=str(exc)) from exc
            except (ValueError, OSError, TypeError, KeyError, ValidationError) as exc:
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
