from __future__ import annotations

import asyncio
import csv
import gzip
import json
import secrets
import string
from pathlib import Path

from fastapi import Cookie, Depends, FastAPI, HTTPException, Query, Request, Response, WebSocket, WebSocketDisconnect, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse

import auth
import config
import database
from backend.schemas import (
    AdminPasswordResetResponse,
    AdminRole,
    AdminRoleListResponse,
    AdminUser,
    AdminUserCreateRequest,
    AdminUserCreateResponse,
    AdminUserListResponse,
    AdminUserUpdateRequest,
    AuditLogListResponse,
    AuditLogRecord,
    BackupActionResponse,
    BackupListResponse,
    BackupRecord,
    ChangePasswordRequest,
    ComparePairResponse,
    CompareRunBundle,
    CompareRunListResponse,
    CompareRunOption,
    CompareTimelineFrame,
    CompareTimelineMeta,
    CurrentUser,
    HealthResponse,
    LoginRequest,
    LoginResponse,
    MessageResponse,
    Permission,
    RegisterRequest,
    RegisterResponse,
    ReportExportRequest,
    RLEvaluateModelRequest,
    RLJobActionResponse,
    RLLogLine,
    RLModelListResponse,
    RLModelRecord,
    RLTrainingJob,
    RLTrainingJobItem,
    RLTrainingJobListResponse,
    RLTrainingStartRequest,
    RLTrainingStatusResponse,
    Scenario,
    ScenarioListResponse,
    ScenarioWriteRequest,
    SimulationActionResponse,
    SimulationConfigureRequest,
    SimulationRunListResponse,
    SimulationRunRecord,
    SimulationStartRequest,
    SimulationStateResponse,
    SimulationStepRequest,
    TimelineGenerateRequest,
    TimelineGenerateResponse,
    PlaybackLoadRequest,
    PlaybackSeekRequest,
    RolePermissionUpdateRequest,
    RunFavoriteRequest,
    RunTimelineResponse,
)
from backend.security import (
    API_SESSION_COOKIE,
    api_user_from_session_token,
    clear_api_session,
    create_api_session,
    landing_path_for_api_user,
    optional_current_user,
    require_current_user,
    require_permission,
    scenario_model,
    user_model,
)
from backend.simulation_runtime import SimulationRuntimeError, simulation_runtime
from services import render_frame_service, rl_training_service, timeline_generator, visual_network_service


ALLOWED_DEV_ORIGINS = [
    "http://127.0.0.1:5173",
    "http://localhost:5173",
]


app = FastAPI(
    title="SMARTFLOW API",
    version=config.APP_VERSION,
    description="FastAPI bridge for the React/Vite SMARTFLOW migration.",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_DEV_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["Content-Type", "X-CSRF-Token"],
)


@app.on_event("startup")
def startup() -> None:
    database.init_db()
    database.seed_data()
    database.reconcile_incomplete_runs()
    database.reconcile_incomplete_rl_training_jobs()


@app.get("/api/health", response_model=HealthResponse)
def health() -> HealthResponse:
    with database.get_db() as conn:
        conn.execute("SELECT 1").fetchone()
    return HealthResponse(
        status="healthy",
        app=config.APP_NAME,
        version=config.APP_VERSION,
        database="sqlite",
    )


def require_any_permission(user: dict, permissions: list[tuple[str, str]]) -> None:
    last_error: HTTPException | None = None
    for page, action in permissions:
        try:
            require_permission(user, page, action)
            return
        except HTTPException as exc:
            last_error = exc
    if last_error:
        raise last_error
    raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Permission denied.")


def require_admin(user: dict) -> None:
    if str(user.get("role_name") or user.get("role") or "").lower() != "admin":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Administrator access required.")


def simulation_action_response(message: str, simulation: SimulationStateResponse) -> SimulationActionResponse:
    return SimulationActionResponse(message=message, simulation=simulation)


def simulation_conflict(exc: SimulationRuntimeError) -> HTTPException:
    return HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc))


def normalize_optional_email(email: str | None) -> str | None:
    normalized_email = str(email or "").strip()
    return normalized_email or None


def validate_registration_payload(payload: RegisterRequest) -> tuple[str, str | None]:
    username = payload.username.strip()
    if not username.replace("_", "").replace("-", "").isalnum():
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Username may only contain letters, numbers, underscores, and hyphens.",
        )
    if payload.password != payload.confirm_password:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Passwords do not match.")
    password_errors = auth.validate_password_strength(payload.password)
    if password_errors:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=password_errors[0])
    email = normalize_optional_email(payload.email)
    return username, email


def temporary_password() -> str:
    alphabet = string.ascii_letters + string.digits
    token = "".join(secrets.choice(alphabet) for _ in range(10))
    return f"Sf-{token}9Aa"


def admin_user_model(row: dict, *, current_user_id: int | None = None) -> AdminUser:
    activity = database.get_user_activity_summary(row["id"])
    return AdminUser(
        id=int(row["id"]),
        full_name=str(row["full_name"]),
        username=str(row["username"]),
        email=row.get("email"),
        role=str(row.get("role_name") or row.get("role") or ""),
        role_id=int(row["role_id"]),
        status=str(row["status"]),
        created_at=row.get("created_at"),
        updated_at=row.get("updated_at"),
        last_login_at=row.get("last_login_at"),
        must_change_password=bool(row.get("must_change_password")),
        run_count=int(activity.get("run_count") or 0),
        audit_count=int(activity.get("audit_count") or 0),
        is_self=current_user_id == int(row["id"]),
    )


def admin_role_model(row: dict) -> AdminRole:
    role_name = str(row.get("name") or "")
    return AdminRole(
        id=int(row["id"]),
        name=role_name,
        description=row.get("description"),
        permissions=[
            Permission(page=permission["page"], action=permission["action"])
            for permission in database.get_permissions_for_role(row["id"])
        ],
        locked=role_name.lower() == "admin",
    )


def audit_log_model(row: dict) -> AuditLogRecord:
    return AuditLogRecord(
        id=int(row["id"]),
        user_id=row.get("user_id"),
        username=row.get("username"),
        action=str(row.get("action") or ""),
        target=str(row.get("target") or ""),
        details=row.get("details"),
        timestamp=row.get("timestamp"),
        ip_address=row.get("ip_address"),
        user_agent=row.get("user_agent"),
    )


def backup_model(row: dict) -> BackupRecord:
    return BackupRecord(
        id=int(row["id"]),
        filename=str(row["filename"]),
        created_by=row.get("created_by"),
        username=row.get("username"),
        created_at=row.get("created_at"),
        size_bytes=int(row.get("size_bytes") or 0),
    )


def json_value(value: object, default: object) -> object:
    if isinstance(value, (dict, list)):
        return value
    try:
        return json.loads(str(value or ""))
    except Exception:
        return default


def rl_model_record(row: dict) -> RLModelRecord:
    return RLModelRecord(
        id=int(row["id"]),
        algorithm=str(row.get("algorithm") or "").upper(),
        name=row.get("name"),
        checkpoint_path=row.get("checkpoint_path"),
        training_date=row.get("training_date") or row.get("created_at"),
        best_evaluation_score=row.get("best_evaluation_score"),
    )


def rl_job_model(row: dict) -> RLTrainingJob:
    return RLTrainingJob(
        id=int(row["id"]),
        user_id=row.get("user_id"),
        status=str(row.get("status") or "unknown"),
        selected_algorithms=list(json_value(row.get("selected_algorithms_json"), [])),
        settings=dict(json_value(row.get("settings_json"), {})),
        progress_percent=float(row.get("progress_percent") or 0),
        current_algorithm=row.get("current_algorithm"),
        current_item_id=row.get("current_item_id"),
        log_path=row.get("log_path"),
        message=row.get("message"),
        started_at=row.get("started_at"),
        ended_at=row.get("ended_at"),
        created_at=row.get("created_at"),
    )


def rl_job_item_model(row: dict) -> RLTrainingJobItem:
    return RLTrainingJobItem(
        id=int(row["id"]),
        job_id=int(row["job_id"]),
        algorithm=str(row.get("algorithm") or ""),
        sequence_index=int(row.get("sequence_index") or 0),
        status=str(row.get("status") or "unknown"),
        progress_percent=float(row.get("progress_percent") or 0),
        latest_episode=int(row.get("latest_episode") or 0),
        latest_reward=row.get("latest_reward"),
        latest_epsilon=row.get("latest_epsilon"),
        latest_timesteps=int(row.get("latest_timesteps") or 0),
        artifact_path=row.get("artifact_path"),
        metadata_path=row.get("metadata_path"),
        rl_model_id=row.get("rl_model_id"),
        evaluation_path=row.get("evaluation_path"),
        message=row.get("message"),
        started_at=row.get("started_at"),
        ended_at=row.get("ended_at"),
        created_at=row.get("created_at"),
    )


def rl_log_line_model(row: dict) -> RLLogLine:
    return RLLogLine(
        ts=row.get("ts"),
        type=row.get("type"),
        algorithm=row.get("algorithm"),
        text=str(row.get("text") or ""),
    )


def rl_training_status_response(raw_status: dict) -> RLTrainingStatusResponse:
    job = raw_status.get("job")
    return RLTrainingStatusResponse(
        job=rl_job_model(job) if job else None,
        items=[rl_job_item_model(item) for item in raw_status.get("items") or []],
        log_lines=[rl_log_line_model(line) for line in raw_status.get("log_lines") or []],
        models=[rl_model_record(model) for model in raw_status.get("models") or []],
    )


def role_exists(role_id: int) -> bool:
    return any(int(role["id"]) == int(role_id) for role in database.list_roles())


def unique_user_constraints(*, user_id: int | None, username: str | None, email: str | None) -> None:
    normalized_username = str(username or "").strip()
    if normalized_username:
        existing = database.get_user_by_username(normalized_username)
        if existing and int(existing["id"]) != int(user_id or 0):
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="This username is already taken.")
    normalized_email = normalize_optional_email(email)
    if normalized_email:
        existing = database.get_user_by_email(normalized_email)
        if existing and int(existing["id"]) != int(user_id or 0):
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="This email address is already registered.")


def assert_not_last_active_admin(target_user: dict, *, next_role_id: int | None = None, next_status: str | None = None) -> None:
    if str(target_user.get("role_name") or "").lower() != "admin":
        return
    if str(target_user.get("status") or "").lower() != "active":
        return
    next_role = target_user.get("role_id") if next_role_id is None else next_role_id
    next_role_name = next(
        (role["name"] for role in database.list_roles() if int(role["id"]) == int(next_role)),
        target_user.get("role_name"),
    )
    next_user_status = str(next_status or target_user.get("status") or "").lower()
    would_remain_active_admin = str(next_role_name or "").lower() == "admin" and next_user_status == "active"
    if would_remain_active_admin:
        return
    if database.count_active_admins() <= 1:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Cannot remove the last active administrator.")


def backup_by_id(backup_id: int) -> dict | None:
    return next((backup for backup in database.list_backups() if int(backup["id"]) == int(backup_id)), None)


@app.post("/api/auth/login", response_model=LoginResponse)
def login(payload: LoginRequest, request: Request, response: Response) -> LoginResponse:
    from backend.security import authenticate_for_api

    user, failure_reason = authenticate_for_api(payload.username, payload.password, request)
    if failure_reason == "locked":
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many failed login attempts. Try again later.",
        )
    if failure_reason == "inactive":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Account is inactive and requires administrator approval.",
        )
    if failure_reason or not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid username or password.")

    create_api_session(response, user)
    return LoginResponse(user=user_model(user), landing_path=landing_path_for_api_user(user))


@app.post("/api/auth/register", response_model=RegisterResponse)
def register(payload: RegisterRequest) -> RegisterResponse:
    registration_mode = database.get_setting("registration_mode", config.REGISTRATION_MODE)
    if registration_mode == "disabled":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Registration is currently disabled. Please contact an administrator.",
        )

    username, email = validate_registration_payload(payload)
    if database.get_user_by_username(username):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="This username is already taken. Please choose another.",
        )
    if email and database.get_user_by_email(email):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="This email address is already registered.")

    user_role = database.get_role_by_name("user")
    role_id = int(user_role["id"]) if user_role else 2
    account_status = "active" if registration_mode == "open" else "inactive"
    user_id = database.create_user(
        full_name=payload.full_name.strip(),
        username=username,
        email=email,
        password_hash=auth.hash_password(payload.password),
        role_id=role_id,
        status=account_status,
    )
    database.log_audit_event(
        user_id=user_id,
        action="api_register",
        target="auth",
        details=f"New user registered through the FastAPI bridge: '{username}' ({payload.full_name.strip()}).",
    )
    if account_status == "active":
        return RegisterResponse(
            message="Account created successfully. You can now log in.",
            account_status=account_status,
        )
    return RegisterResponse(
        message="Account request submitted successfully. An administrator must approve your access before you can sign in.",
        account_status=account_status,
    )


@app.get("/api/auth/me", response_model=CurrentUser)
def me(user: dict = Depends(require_current_user)) -> CurrentUser:
    return user_model(user)


@app.post("/api/auth/change-password", response_model=MessageResponse)
def change_password(
    payload: ChangePasswordRequest,
    user: dict = Depends(require_current_user),
) -> MessageResponse:
    db_user = database.get_user_by_id(user["id"])
    if not db_user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found.")
    if not auth.verify_password(payload.current_password, db_user["password_hash"]):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Current password is incorrect.")
    if payload.new_password != payload.confirm_password:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="New passwords do not match.")
    password_errors = auth.validate_password_strength(payload.new_password)
    if password_errors:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=password_errors[0])
    if config.BOOTSTRAP_RESERVED_PASSWORDS and payload.new_password in config.BOOTSTRAP_RESERVED_PASSWORDS:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Cannot reuse a bootstrap password.")
    if payload.new_password == payload.current_password:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="New password must be different from current password.",
        )

    database.update_user(
        user["id"],
        invalidate_sessions=False,
        password_hash=auth.hash_password(payload.new_password),
    )
    database.log_audit_event(
        user_id=user["id"],
        action="api_change_password",
        target="user",
        details=f"User '{db_user['username']}' updated their password through the FastAPI bridge.",
    )
    return MessageResponse(message="Password updated successfully.")


@app.post("/api/auth/logout")
def logout(
    response: Response,
    user: dict | None = Depends(optional_current_user),
    smartflow_api_session: str | None = Cookie(default=None, alias="smartflow_api_session"),
) -> dict:
    clear_api_session(response, smartflow_api_session, user)
    return {"ok": True}


@app.get("/api/admin/users", response_model=AdminUserListResponse)
def admin_list_users(
    role_id: int | None = None,
    status_filter: str | None = Query(default=None, alias="status"),
    user: dict = Depends(require_current_user),
) -> AdminUserListResponse:
    require_admin(user)
    rows = database.list_users(role_id=role_id, status=status_filter)
    return AdminUserListResponse(users=[admin_user_model(row, current_user_id=user["id"]) for row in rows])


@app.post("/api/admin/users", response_model=AdminUserCreateResponse)
def admin_create_user(
    payload: AdminUserCreateRequest,
    user: dict = Depends(require_current_user),
) -> AdminUserCreateResponse:
    require_admin(user)
    if payload.status not in {"active", "inactive"}:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Status must be active or inactive.")
    if not role_exists(payload.role_id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Role not found.")

    username = payload.username.strip()
    email = normalize_optional_email(payload.email)
    unique_user_constraints(user_id=None, username=username, email=email)

    password = temporary_password()
    user_id = database.create_user(
        full_name=payload.full_name.strip(),
        username=username,
        email=email,
        password_hash=auth.hash_password(password),
        role_id=payload.role_id,
        status=payload.status,
        must_change_password=int(payload.must_change_password),
    )
    created = database.get_user_by_id(user_id)
    database.log_audit_event(
        user_id=user["id"],
        action="api_admin_create_user",
        target="users",
        details=f"Created user '{username}' through the FastAPI admin API.",
    )
    return AdminUserCreateResponse(
        user=admin_user_model(created, current_user_id=user["id"]),
        temporary_password=password,
        message="User created successfully.",
    )


@app.put("/api/admin/users/{user_id}", response_model=AdminUser)
def admin_update_user(
    user_id: int,
    payload: AdminUserUpdateRequest,
    user: dict = Depends(require_current_user),
) -> AdminUser:
    require_admin(user)
    target_user = database.get_user_by_id(user_id)
    if not target_user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found.")

    updates = payload.model_dump(exclude_unset=True)
    if not updates:
        return admin_user_model(target_user, current_user_id=user["id"])
    if "status" in updates and updates["status"] not in {"active", "inactive"}:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Status must be active or inactive.")
    if "role_id" in updates and not role_exists(updates["role_id"]):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Role not found.")

    if "full_name" in updates:
        updates["full_name"] = updates["full_name"].strip()
    if "username" in updates:
        updates["username"] = updates["username"].strip()
    if "email" in updates:
        updates["email"] = normalize_optional_email(updates["email"])
    if "must_change_password" in updates:
        updates["must_change_password"] = int(bool(updates["must_change_password"]))

    unique_user_constraints(
        user_id=user_id,
        username=updates.get("username"),
        email=updates.get("email"),
    )
    assert_not_last_active_admin(
        target_user,
        next_role_id=updates.get("role_id"),
        next_status=updates.get("status"),
    )

    database.update_user(user_id, **updates)
    updated = database.get_user_by_id(user_id)
    database.log_audit_event(
        user_id=user["id"],
        action="api_admin_update_user",
        target="users",
        details=f"Updated user '{updated['username']}' through the FastAPI admin API.",
    )
    return admin_user_model(updated, current_user_id=user["id"])


@app.post("/api/admin/users/{user_id}/reset-password", response_model=AdminPasswordResetResponse)
def admin_reset_user_password(
    user_id: int,
    user: dict = Depends(require_current_user),
) -> AdminPasswordResetResponse:
    require_admin(user)
    target_user = database.get_user_by_id(user_id)
    if not target_user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found.")
    if int(user_id) == int(user["id"]):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Use change password to update your own password.")

    password = temporary_password()
    database.update_user(
        user_id,
        password_hash=auth.hash_password(password),
        must_change_password=1,
    )
    updated = database.get_user_by_id(user_id)
    database.log_audit_event(
        user_id=user["id"],
        action="api_admin_reset_password",
        target="users",
        details=f"Reset password for user '{updated['username']}' through the FastAPI admin API.",
    )
    return AdminPasswordResetResponse(
        temporary_password=password,
        message="Password reset successfully.",
        user=admin_user_model(updated, current_user_id=user["id"]),
    )


@app.delete("/api/admin/users/{user_id}", response_model=MessageResponse)
def admin_delete_user(
    user_id: int,
    user: dict = Depends(require_current_user),
) -> MessageResponse:
    require_admin(user)
    target_user = database.get_user_by_id(user_id)
    if not target_user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found.")
    if int(user_id) == int(user["id"]):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="You cannot delete your own account.")
    assert_not_last_active_admin(target_user, next_status="deleted")

    database.delete_user(user_id)
    database.log_audit_event(
        user_id=user["id"],
        action="api_admin_delete_user",
        target="users",
        details=f"Deleted user '{target_user['username']}' through the FastAPI admin API.",
    )
    return MessageResponse(message="User deleted successfully.")


@app.get("/api/admin/roles", response_model=AdminRoleListResponse)
def admin_list_roles(user: dict = Depends(require_current_user)) -> AdminRoleListResponse:
    require_admin(user)
    return AdminRoleListResponse(roles=[admin_role_model(role) for role in database.list_roles()])


@app.put("/api/admin/roles/{role_id}/permissions", response_model=AdminRole)
def admin_update_role_permissions(
    role_id: int,
    payload: RolePermissionUpdateRequest,
    user: dict = Depends(require_current_user),
) -> AdminRole:
    require_admin(user)
    role = next((role for role in database.list_roles() if int(role["id"]) == int(role_id)), None)
    if not role:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Role not found.")
    if str(role["name"]).lower() == "admin":
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Administrator permissions are locked.")

    for permission_update in payload.updates:
        database.update_role_permission(
            role_id,
            permission_update.page,
            permission_update.action,
            permission_update.enabled,
        )
    database.log_audit_event(
        user_id=user["id"],
        action="api_admin_update_role_permissions",
        target="roles",
        details=f"Updated {len(payload.updates)} permission setting(s) for role '{role['name']}'.",
    )
    return admin_role_model(role)


@app.get("/api/admin/audit-logs", response_model=AuditLogListResponse)
def admin_list_audit_logs(
    user_id: int | None = None,
    action: str | None = None,
    limit: int = Query(default=200, ge=1, le=1000),
    user: dict = Depends(require_current_user),
) -> AuditLogListResponse:
    require_admin(user)
    rows = database.get_audit_logs(user_id=user_id, action=action, limit=limit)
    return AuditLogListResponse(logs=[audit_log_model(row) for row in rows])


@app.get("/api/admin/backups", response_model=BackupListResponse)
def admin_list_backups(user: dict = Depends(require_current_user)) -> BackupListResponse:
    require_admin(user)
    return BackupListResponse(backups=[backup_model(row) for row in database.list_backups()])


@app.post("/api/admin/backups", response_model=BackupActionResponse)
def admin_create_backup(user: dict = Depends(require_current_user)) -> BackupActionResponse:
    require_admin(user)
    filename = database.create_backup(user["id"])
    backup = next((row for row in database.list_backups() if row["filename"] == filename), None)
    database.log_audit_event(
        user_id=user["id"],
        action="api_admin_create_backup",
        target="backups",
        details=f"Created database backup '{filename}'.",
    )
    return BackupActionResponse(
        message="Backup created successfully.",
        backup=backup_model(backup) if backup else None,
    )


@app.post("/api/admin/backups/{backup_id}/restore", response_model=BackupActionResponse)
def admin_restore_backup(
    backup_id: int,
    user: dict = Depends(require_current_user),
) -> BackupActionResponse:
    require_admin(user)
    backup = backup_by_id(backup_id)
    if not backup:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Backup not found.")
    database.log_audit_event(
        user_id=user["id"],
        action="api_admin_restore_backup",
        target="backups",
        details=f"Restored database backup '{backup['filename']}'. Sessions will be invalidated.",
    )
    try:
        database.restore_backup(backup_id)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    return BackupActionResponse(
        message="Backup restored successfully. Active sessions were invalidated.",
        backup=backup_model(backup),
    )


@app.delete("/api/admin/backups/{backup_id}", response_model=MessageResponse)
def admin_delete_backup(
    backup_id: int,
    user: dict = Depends(require_current_user),
) -> MessageResponse:
    require_admin(user)
    backup = backup_by_id(backup_id)
    if not backup:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Backup not found.")
    database.delete_backup_from_db(backup_id)
    database.log_audit_event(
        user_id=user["id"],
        action="api_admin_delete_backup",
        target="backups",
        details=f"Deleted database backup '{backup['filename']}'.",
    )
    return MessageResponse(message="Backup deleted successfully.")


@app.get("/api/admin/backups/{backup_id}/download")
def admin_download_backup(
    backup_id: int,
    user: dict = Depends(require_current_user),
) -> FileResponse:
    require_admin(user)
    backup = backup_by_id(backup_id)
    if not backup:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Backup not found.")
    try:
        backup_path = database._resolve_backup_path(backup["filename"])
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    if not backup_path.exists():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Backup file not found on disk.")
    database.log_audit_event(
        user_id=user["id"],
        action="api_admin_download_backup",
        target="backups",
        details=f"Downloaded database backup '{backup['filename']}'.",
    )
    return FileResponse(path=backup_path, filename=backup["filename"], media_type="application/octet-stream")


@app.get("/api/admin/database/download")
def admin_download_database(user: dict = Depends(require_current_user)) -> FileResponse:
    require_admin(user)
    database_path = Path(config.DB_PATH).resolve()
    if not database_path.exists():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Database file not found.")
    database.log_audit_event(
        user_id=user["id"],
        action="api_admin_download_database",
        target="backups",
        details="Downloaded the live SQLite database file.",
    )
    return FileResponse(path=database_path, filename=database_path.name, media_type="application/octet-stream")


@app.get("/api/rl/models", response_model=RLModelListResponse)
def list_rl_models(
    algorithm: str | None = None,
    limit: int = Query(default=200, ge=1, le=1000),
    user: dict = Depends(require_current_user),
) -> RLModelListResponse:
    require_permission(user, "rl-training", "view")
    rows = database.list_rl_models(limit=limit, algorithm=algorithm)
    return RLModelListResponse(models=[rl_model_record(row) for row in rows])


@app.get("/api/rl/jobs", response_model=RLTrainingJobListResponse)
def list_rl_training_jobs(
    limit: int = Query(default=50, ge=1, le=500),
    user: dict = Depends(require_current_user),
) -> RLTrainingJobListResponse:
    require_permission(user, "rl-training", "view")
    return RLTrainingJobListResponse(jobs=[rl_job_model(row) for row in database.list_rl_training_jobs(limit=limit)])


@app.get("/api/rl/status", response_model=RLTrainingStatusResponse)
def get_rl_training_status(
    job_id: int | None = None,
    user: dict = Depends(require_current_user),
) -> RLTrainingStatusResponse:
    require_permission(user, "rl-training", "view")
    return rl_training_status_response(rl_training_service.training_status(job_id))


@app.post("/api/rl/jobs", response_model=RLJobActionResponse)
def start_rl_training_job(
    payload: RLTrainingStartRequest,
    user: dict = Depends(require_current_user),
) -> RLJobActionResponse:
    require_permission(user, "rl-training", "view")
    try:
        job_id = rl_training_service.enqueue_training_job(
            algorithms=payload.algorithms,
            settings=payload.settings,
            advanced=payload.advanced,
            user_id=user["id"],
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    database.log_audit_event(
        user_id=user["id"],
        action="api_rl_training_start",
        target="rl_training_jobs",
        details=f"Queued RL training job #{job_id} for algorithms: {', '.join(payload.algorithms)}.",
    )
    return RLJobActionResponse(message=f"Queued RL training job #{job_id}.", job_id=job_id)


@app.post("/api/rl/jobs/{job_id}/stop", response_model=RLJobActionResponse)
def stop_rl_training_job(
    job_id: int,
    user: dict = Depends(require_current_user),
) -> RLJobActionResponse:
    require_permission(user, "rl-training", "view")
    if not database.get_rl_training_job(job_id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="RL training job not found.")
    rl_training_service.stop_training_job(job_id)
    database.log_audit_event(
        user_id=user["id"],
        action="api_rl_training_stop",
        target="rl_training_jobs",
        details=f"Stop requested for RL training job #{job_id}.",
    )
    return RLJobActionResponse(
        message="Stop requested. The training script will save a partial artifact if possible.",
        job_id=job_id,
    )


@app.post("/api/rl/evaluate", response_model=RLJobActionResponse)
def evaluate_rl_model(
    payload: RLEvaluateModelRequest,
    user: dict = Depends(require_current_user),
) -> RLJobActionResponse:
    require_permission(user, "rl-training", "view")
    try:
        job_id = rl_training_service.enqueue_model_evaluation(
            model_id=payload.model_id,
            settings=payload.settings,
            user_id=user["id"],
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    database.log_audit_event(
        user_id=user["id"],
        action="api_rl_model_evaluate",
        target="rl_models",
        details=f"Queued evaluation job #{job_id} for RL model #{payload.model_id}.",
    )
    return RLJobActionResponse(message=f"Queued evaluation job #{job_id}.", job_id=job_id)


@app.get("/api/scenarios", response_model=ScenarioListResponse)
def list_scenarios(
    include_archived: bool = False,
    official_only: bool = False,
    user: dict = Depends(require_current_user),
) -> ScenarioListResponse:
    require_permission(user, "scenarios", "view")
    rows = database.get_scenarios(include_archived=include_archived, official_only=official_only)
    return ScenarioListResponse(scenarios=[scenario_model(row) for row in rows])


@app.get("/api/scenarios/{scenario_id}", response_model=Scenario)
def get_scenario(scenario_id: int, user: dict = Depends(require_current_user)) -> Scenario:
    require_permission(user, "scenarios", "view")
    row = database.get_scenario_by_id(scenario_id)
    if not row:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Scenario not found.")
    return scenario_model(row)


def scenario_write_values(payload: ScenarioWriteRequest) -> dict:
    return {
        "name": payload.name.strip(),
        "description": payload.description or "",
        "traffic_density": payload.traffic_density,
        "pedestrian_density": payload.pedestrian_density,
        "emergency_mode": payload.emergency_mode,
        "road_constraint": payload.road_constraint,
        "intersection_id": payload.intersection_id,
        "lane_closure_config": json.dumps(payload.lane_closure_config),
        "construction_config": json.dumps(payload.construction_config),
        "accident_config": json.dumps(payload.accident_config),
        "flooding_config": json.dumps(payload.flooding_config),
    }


def run_record_model(row: dict) -> SimulationRunRecord:
    metrics = database.get_run_metrics(row["id"])
    metric_payload = None
    if metrics:
        metric_payload = dict(metrics)
        raw_metrics_json = metric_payload.get("raw_metrics_json")
        if raw_metrics_json:
            try:
                metric_payload["raw_metrics"] = json.loads(raw_metrics_json)
            except (TypeError, ValueError):
                metric_payload["raw_metrics"] = {}
    return SimulationRunRecord(
        id=int(row["id"]),
        scenario_id=row.get("scenario_id"),
        scenario_name=row.get("scenario_name"),
        user_id=row.get("user_id"),
        user_name=row.get("user_name"),
        run_mode=row.get("run_mode") or "live",
        control_mode=row.get("control_mode") or "fixed-time",
        status=row.get("status") or "unknown",
        start_time=row.get("start_time"),
        end_time=row.get("end_time"),
        duration_seconds=float(row.get("duration_seconds") or 0),
        seed=row.get("seed"),
        notes=row.get("notes"),
        timeline_path=row.get("timeline_path"),
        is_favorite=bool(row.get("is_favorite")),
        metrics=metric_payload,
    )


def report_export_directory() -> Path:
    directory = Path(config.BASE_DIR) / "data" / "generated" / "reports"
    directory.mkdir(parents=True, exist_ok=True)
    return directory


def run_metric_value(run: SimulationRunRecord, key: str, default: object = "") -> object:
    metrics = run.metrics or {}
    value = metrics.get(key)
    return default if value is None else value


def run_report_row(run: SimulationRunRecord) -> dict[str, object]:
    return {
        "Run ID": run.id,
        "Scenario": run.scenario_name or "Unknown",
        "Run Mode": run.run_mode,
        "Control Mode": run.control_mode,
        "Status": run.status,
        "Started": run.start_time or "",
        "Ended": run.end_time or "",
        "Duration Seconds": run.duration_seconds,
        "Seed": run.seed or "",
        "Average Wait Seconds": run_metric_value(run, "avg_waiting_time"),
        "Average Queue Length": run_metric_value(run, "avg_queue_length"),
        "Maximum Queue Length": run_metric_value(run, "max_queue_length"),
        "Throughput": run_metric_value(run, "throughput"),
        "Average Pedestrian Delay": run_metric_value(run, "avg_pedestrian_delay"),
        "Timeline Path": run.timeline_path or "",
        "Notes": run.notes or "",
    }


def run_records_for_export(run_ids: list[int]) -> list[SimulationRunRecord]:
    records = []
    for run_id in run_ids:
        row = database.get_run_by_id(run_id)
        if row:
            records.append(run_record_model(row))
    return records


def write_runs_csv(records: list[SimulationRunRecord]) -> Path:
    path = report_export_directory() / f"smartflow_runs_export_{secrets.token_hex(6)}.csv"
    rows = [run_report_row(record) for record in records]
    headers = list(rows[0].keys())
    with path.open("w", encoding="utf-8", newline="") as csv_file:
        writer = csv.DictWriter(csv_file, fieldnames=headers)
        writer.writeheader()
        writer.writerows(rows)
    return path


def write_runs_json(records: list[SimulationRunRecord]) -> Path:
    path = report_export_directory() / f"smartflow_runs_export_{secrets.token_hex(6)}.json"
    payload = [record.model_dump() for record in records]
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=True), encoding="utf-8")
    return path


def completed_run_record(run_id: int) -> SimulationRunRecord:
    row = database.get_run_by_id(run_id)
    if not row:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Run not found.")
    return run_record_model(row)


COMPARE_FRAME_LIMIT = 5000
COMPARE_APPROACHES = ("north", "east", "south", "west")
_COMPARE_TIMELINE_FRAME_CACHE: dict[str, dict] = {}


def compare_float(value: object, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def compare_int(value: object, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def resolve_artifact_path(path_value: str | None) -> Path | None:
    if not path_value:
        return None
    raw_path = Path(path_value)
    candidates = [raw_path] if raw_path.is_absolute() else [Path(config.BASE_DIR) / raw_path]
    candidates.append(Path(config.BASE_DIR) / "assets" / "generated" / "timelines" / raw_path.name)
    for candidate in candidates:
        if candidate.exists():
            return candidate.resolve()
    return candidates[0].resolve()


def compare_manifest_path(timeline_path: str | None) -> Path | None:
    path = resolve_artifact_path(timeline_path)
    if not path:
        return None
    if path.name.endswith(".jsonl.gz"):
        return path.with_name(path.name.removesuffix(".jsonl.gz") + ".manifest.json")
    if path.suffix == ".jsonl":
        return path.with_suffix(".manifest.json")
    if path.name.endswith(".manifest.json"):
        return path
    return None


def compare_manifest(timeline_path: str | None) -> dict:
    manifest_path = compare_manifest_path(timeline_path)
    if not manifest_path or not manifest_path.exists():
        return {}
    try:
        return json.loads(manifest_path.read_text(encoding="utf-8"))
    except Exception:
        return {}


def timeline_file_exists(timeline_path: str | None) -> bool:
    path = resolve_artifact_path(timeline_path)
    return bool(path and path.exists())


def compare_timeline_meta(run: SimulationRunRecord, manifest: dict) -> CompareTimelineMeta:
    timeline = manifest.get("timeline", {}) if isinstance(manifest, dict) else {}
    scenario = manifest.get("scenario", {}) if isinstance(manifest, dict) else {}
    return CompareTimelineMeta(
        intersection_id=scenario.get("intersection_id"),
        requested_duration_seconds=compare_float(timeline.get("requested_duration_seconds") or run.duration_seconds),
        actual_duration_seconds=compare_float(timeline.get("actual_duration_seconds") or run.duration_seconds),
        step_length_seconds=compare_float(timeline.get("step_length_seconds")),
        frame_count=compare_int(timeline.get("frame_count")),
    )


def compare_signature(run: SimulationRunRecord, timeline: CompareTimelineMeta) -> tuple:
    duration = round(compare_float(timeline.requested_duration_seconds or run.duration_seconds), 1)
    return (run.scenario_id, timeline.intersection_id, run.seed, duration)


def compare_key(run: SimulationRunRecord, timeline: CompareTimelineMeta) -> str:
    return "|".join(str(part) for part in compare_signature(run, timeline))


def compare_run_label(run: SimulationRunRecord, manifest: dict) -> str:
    controller = manifest.get("controller", {}) if isinstance(manifest, dict) else {}
    controller_label = controller.get("provenance_label") or run.control_mode.replace("-", " ").title()
    scenario_label = run.scenario_name or "Unknown Scenario"
    seed_label = run.seed if run.seed is not None else "none"
    return f"#{run.id} | {controller_label} | {scenario_label} | seed {seed_label}"


def compare_run_option(row: dict) -> CompareRunOption:
    run = run_record_model(row)
    manifest = compare_manifest(run.timeline_path)
    timeline = compare_timeline_meta(run, manifest)
    return CompareRunOption(
        run=run,
        label=compare_run_label(run, manifest),
        timeline=timeline,
        compatibility_key=compare_key(run, timeline),
    )


def compare_run_options(limit: int = 500) -> list[CompareRunOption]:
    options = []
    for row in database.get_runs(status="completed", limit=limit):
        if str(row.get("run_mode") or "").lower() != "pre-record":
            continue
        if not timeline_file_exists(row.get("timeline_path")):
            continue
        option = compare_run_option(row)
        if option.timeline.frame_count > 0:
            options.append(option)
    return options


def compare_option_by_run_id(run_id: int) -> CompareRunOption:
    row = database.get_run_by_id(run_id)
    if not row:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Run not found.")
    if str(row.get("run_mode") or "").lower() != "pre-record":
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Only pre-record timeline runs can be compared.")
    if str(row.get("status") or "").lower() != "completed":
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Timeline generation must be completed before comparison.")
    if not timeline_file_exists(row.get("timeline_path")):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Timeline artifact was not found on disk.")
    option = compare_run_option(row)
    if option.timeline.frame_count <= 0:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Timeline manifest does not contain comparable frames.")
    return option


def compare_run_metrics(run_id: int) -> dict:
    metrics = database.get_run_metrics(run_id)
    if not metrics:
        return {}
    payload = dict(metrics)
    raw_metrics_json = payload.get("raw_metrics_json")
    if raw_metrics_json:
        try:
            payload["raw_metrics"] = json.loads(raw_metrics_json)
        except (TypeError, ValueError):
            payload["raw_metrics"] = {}
    return payload


def sample_frame_indices(frame_count: int, limit: int = COMPARE_FRAME_LIMIT) -> list[int]:
    if frame_count <= limit:
        return list(range(frame_count))
    if limit <= 1:
        return [0]
    return sorted({round(index * (frame_count - 1) / (limit - 1)) for index in range(limit)})


def condense_compare_frame(index: int, raw_frame: dict) -> CompareTimelineFrame:
    metrics = raw_frame.get("metrics", {}) if isinstance(raw_frame.get("metrics"), dict) else {}
    queues = raw_frame.get("queues", {}) if isinstance(raw_frame.get("queues"), dict) else {}
    return CompareTimelineFrame(
        index=index,
        time=compare_float(raw_frame.get("time")),
        phase=str(raw_frame.get("phase") or "UNKNOWN"),
        phase_remaining=compare_float(raw_frame.get("phase_remaining")),
        queues={approach: compare_float(queues.get(approach)) for approach in COMPARE_APPROACHES},
        vehicle_count=compare_int(raw_frame.get("vehicle_count")),
        pedestrian_count=compare_int(raw_frame.get("pedestrian_count")),
        avg_wait=compare_float(metrics.get("avg_wait")),
        avg_queue=compare_float(metrics.get("avg_queue")),
        max_queue=compare_float(metrics.get("max_queue")),
        throughput=compare_float(metrics.get("throughput")),
        avg_ped_delay=compare_float(metrics.get("avg_ped_delay")),
    )


def read_compare_frames(timeline_path: str | None) -> list[CompareTimelineFrame]:
    path = resolve_artifact_path(timeline_path)
    if not path or not path.exists():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Timeline artifact was not found on disk.")
    stat = path.stat()
    cache_key = str(path.resolve())
    cached = _COMPARE_TIMELINE_FRAME_CACHE.get(cache_key)
    if cached and cached.get("mtime_ns") == stat.st_mtime_ns and cached.get("size") == stat.st_size:
        return cached["frames"]

    opener = gzip.open if path.suffix == ".gz" else open
    raw_frames = []
    with opener(path, "rt", encoding="utf-8") as timeline_file:
        for line in timeline_file:
            stripped_line = line.strip()
            if stripped_line:
                raw_frames.append(json.loads(stripped_line))

    indices = sample_frame_indices(len(raw_frames))
    frames = [condense_compare_frame(index, raw_frames[index]) for index in indices]
    _COMPARE_TIMELINE_FRAME_CACHE[cache_key] = {
        "mtime_ns": stat.st_mtime_ns,
        "size": stat.st_size,
        "frames": frames,
    }
    return frames


def compare_pair_response(left_run_id: int, right_run_id: int) -> ComparePairResponse:
    if int(left_run_id) == int(right_run_id):
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Select two different runs to compare.")
    left_option = compare_option_by_run_id(left_run_id)
    right_option = compare_option_by_run_id(right_run_id)
    if left_option.compatibility_key != right_option.compatibility_key:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Selected runs are not compatible. Scenario, intersection, seed, duration, and timeline availability must match.",
        )

    left_frames = read_compare_frames(left_option.run.timeline_path)
    right_frames = read_compare_frames(right_option.run.timeline_path)
    frame_count = min(len(left_frames), len(right_frames))
    warnings = []
    if len(left_frames) != len(right_frames):
        warnings.append("Timeline frame counts differ; playback is limited to the shorter recording.")
    return ComparePairResponse(
        left=CompareRunBundle(option=left_option, frames=left_frames[:frame_count], metrics=compare_run_metrics(left_option.run.id)),
        right=CompareRunBundle(option=right_option, frames=right_frames[:frame_count], metrics=compare_run_metrics(right_option.run.id)),
        frame_count=frame_count,
        warnings=warnings,
    )


@app.post("/api/scenarios", response_model=Scenario)
def create_scenario(payload: ScenarioWriteRequest, user: dict = Depends(require_current_user)) -> Scenario:
    require_permission(user, "scenarios", "create")
    try:
        scenario_id = database.create_scenario(
            **scenario_write_values(payload),
            created_by=user["id"],
            is_official=0,
            is_archived=0,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc
    database.log_audit_event(
        user_id=user["id"],
        action="api_create_scenario",
        target="scenarios",
        details=f"Created scenario '{payload.name.strip()}' through the FastAPI bridge.",
    )
    return scenario_model(database.get_scenario_by_id(scenario_id))


@app.put("/api/scenarios/{scenario_id}", response_model=Scenario)
def update_scenario(
    scenario_id: int,
    payload: ScenarioWriteRequest,
    user: dict = Depends(require_current_user),
) -> Scenario:
    require_permission(user, "scenarios", "edit")
    row = database.get_scenario_by_id(scenario_id)
    if not row:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Scenario not found.")
    try:
        database.update_scenario(scenario_id, **scenario_write_values(payload))
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc
    database.log_audit_event(
        user_id=user["id"],
        action="api_update_scenario",
        target="scenarios",
        details=f"Updated scenario ID={scenario_id} through the FastAPI bridge.",
    )
    return scenario_model(database.get_scenario_by_id(scenario_id))


@app.post("/api/scenarios/{scenario_id}/archive", response_model=Scenario)
def archive_scenario(scenario_id: int, user: dict = Depends(require_current_user)) -> Scenario:
    require_permission(user, "scenarios", "edit")
    row = database.get_scenario_by_id(scenario_id)
    if not row:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Scenario not found.")
    database.update_scenario(scenario_id, is_archived=1)
    database.log_audit_event(
        user_id=user["id"],
        action="api_archive_scenario",
        target="scenarios",
        details=f"Archived scenario ID={scenario_id} through the FastAPI bridge.",
    )
    return scenario_model(database.get_scenario_by_id(scenario_id))


@app.post("/api/scenarios/{scenario_id}/restore", response_model=Scenario)
def restore_scenario(scenario_id: int, user: dict = Depends(require_current_user)) -> Scenario:
    require_permission(user, "scenarios", "edit")
    row = database.get_scenario_by_id(scenario_id)
    if not row:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Scenario not found.")
    database.update_scenario(scenario_id, is_archived=0)
    database.log_audit_event(
        user_id=user["id"],
        action="api_restore_scenario",
        target="scenarios",
        details=f"Restored scenario ID={scenario_id} through the FastAPI bridge.",
    )
    return scenario_model(database.get_scenario_by_id(scenario_id))


@app.get("/api/simulation/state", response_model=SimulationStateResponse)
def simulation_state(user: dict = Depends(require_current_user)) -> SimulationStateResponse:
    require_any_permission(user, [("simulation", "view"), ("dashboard", "view")])
    return simulation_runtime.get_state()


@app.get("/api/simulation/runs", response_model=SimulationRunListResponse)
def list_simulation_runs(
    run_mode: str | None = None,
    status_filter: str | None = Query(default=None, alias="status"),
    scenario_id: int | None = None,
    limit: int = 30,
    user: dict = Depends(require_current_user),
) -> SimulationRunListResponse:
    require_any_permission(user, [("simulation", "view"), ("dashboard", "view"), ("runs-reports", "view")])
    rows = database.get_runs(scenario_id=scenario_id, status=status_filter, limit=max(1, min(int(limit), 100)))
    if run_mode:
        normalized_mode = run_mode.strip().lower()
        rows = [row for row in rows if str(row.get("run_mode") or "").lower() == normalized_mode]
    return SimulationRunListResponse(runs=[run_record_model(row) for row in rows])


@app.get("/api/runs", response_model=SimulationRunListResponse)
def list_runs_report(
    scenario_id: int | None = None,
    run_mode: str | None = None,
    control_mode: str | None = None,
    status_filter: str | None = Query(default=None, alias="status"),
    limit: int = Query(default=200, ge=1, le=1000),
    user: dict = Depends(require_current_user),
) -> SimulationRunListResponse:
    require_permission(user, "runs-reports", "view")
    rows = database.get_runs(
        scenario_id=scenario_id,
        control_mode=control_mode,
        status=status_filter,
        limit=limit,
    )
    if run_mode:
        normalized_mode = run_mode.strip().lower()
        rows = [row for row in rows if str(row.get("run_mode") or "").lower() == normalized_mode]
    return SimulationRunListResponse(runs=[run_record_model(row) for row in rows])


@app.get("/api/runs/{run_id}", response_model=SimulationRunRecord)
def get_run_report(
    run_id: int,
    user: dict = Depends(require_current_user),
) -> SimulationRunRecord:
    require_permission(user, "runs-reports", "view")
    row = database.get_run_by_id(run_id)
    if not row:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Run not found.")
    return run_record_model(row)


@app.get("/api/runs/{run_id}/metrics")
def get_run_report_metrics(
    run_id: int,
    user: dict = Depends(require_current_user),
) -> dict:
    require_permission(user, "runs-reports", "view")
    if not database.get_run_by_id(run_id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Run not found.")
    metrics = database.get_run_metrics(run_id)
    if not metrics:
        return {}
    payload = dict(metrics)
    raw_metrics_json = payload.get("raw_metrics_json")
    if raw_metrics_json:
        try:
            payload["raw_metrics"] = json.loads(raw_metrics_json)
        except (TypeError, ValueError):
            payload["raw_metrics"] = {}
    return payload


@app.get("/api/runs/{run_id}/timeline", response_model=RunTimelineResponse)
def get_run_report_timeline(
    run_id: int,
    user: dict = Depends(require_current_user),
) -> RunTimelineResponse:
    require_permission(user, "runs-reports", "view")
    option = compare_option_by_run_id(run_id)
    return RunTimelineResponse(
        run=option.run,
        timeline=option.timeline,
        frames=read_compare_frames(option.run.timeline_path),
        manifest=compare_manifest(option.run.timeline_path),
    )


@app.post("/api/runs/{run_id}/favorite", response_model=SimulationRunRecord)
def favorite_run_report(
    run_id: int,
    payload: RunFavoriteRequest,
    user: dict = Depends(require_current_user),
) -> SimulationRunRecord:
    require_permission(user, "runs-reports", "view")
    row = database.get_run_by_id(run_id)
    if not row:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Run not found.")
    database.update_run(run_id, is_favorite=1 if payload.is_favorite else 0)
    database.log_audit_event(
        user_id=user["id"],
        action="api_favorite_run",
        target="simulation_runs",
        details=f"Set favorite={payload.is_favorite} for run #{run_id}.",
    )
    return run_record_model(database.get_run_by_id(run_id))


@app.delete("/api/runs/{run_id}", response_model=MessageResponse)
def delete_run_report(
    run_id: int,
    user: dict = Depends(require_current_user),
) -> MessageResponse:
    require_permission(user, "runs-reports", "delete")
    row = database.get_run_by_id(run_id)
    if not row:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Run not found.")
    database.delete_run(run_id)
    database.log_audit_event(
        user_id=user["id"],
        action="api_delete_run",
        target="simulation_runs",
        details=f"Deleted run #{run_id} through the FastAPI reports API.",
    )
    return MessageResponse(message=f"Run #{run_id} deleted.")


@app.post("/api/reports/export")
def export_runs_report(
    payload: ReportExportRequest,
    user: dict = Depends(require_current_user),
) -> FileResponse:
    require_permission(user, "runs-reports", "export")
    run_ids = [int(run_id) for run_id in payload.run_ids]
    if not run_ids:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Select at least one run to export.")
    records = run_records_for_export(run_ids)
    if not records:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No selected runs were found.")

    export_format = payload.format.strip().lower()
    if export_format == "csv":
        path = write_runs_csv(records)
        media_type = "text/csv"
    elif export_format == "json":
        path = write_runs_json(records)
        media_type = "application/json"
    else:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Export format must be csv or json.")

    database.log_audit_event(
        user_id=user["id"],
        action="api_export_runs",
        target="reports",
        details=f"Exported {len(records)} run(s) as {export_format.upper()}.",
    )
    return FileResponse(path=path, filename=path.name, media_type=media_type)


@app.get("/api/compare/runs", response_model=CompareRunListResponse)
def list_compare_runs(
    limit: int = Query(default=500, ge=1, le=1000),
    user: dict = Depends(require_current_user),
) -> CompareRunListResponse:
    require_permission(user, "compare", "view")
    return CompareRunListResponse(runs=compare_run_options(limit=limit))


@app.get("/api/compare/compatible-runs", response_model=CompareRunListResponse)
def list_compatible_compare_runs(
    left_run_id: int = Query(ge=1),
    user: dict = Depends(require_current_user),
) -> CompareRunListResponse:
    require_permission(user, "compare", "view")
    left_option = compare_option_by_run_id(left_run_id)
    compatible_options = [
        option
        for option in compare_run_options(limit=1000)
        if option.run.id != left_option.run.id and option.compatibility_key == left_option.compatibility_key
    ]
    return CompareRunListResponse(runs=compatible_options)


@app.get("/api/compare/pair", response_model=ComparePairResponse)
def get_compare_pair(
    left_run_id: int = Query(ge=1),
    right_run_id: int = Query(ge=1),
    user: dict = Depends(require_current_user),
) -> ComparePairResponse:
    require_permission(user, "compare", "view")
    return compare_pair_response(left_run_id, right_run_id)


@app.post("/api/simulation/timelines", response_model=TimelineGenerateResponse)
def generate_simulation_timeline(
    payload: TimelineGenerateRequest,
    user: dict = Depends(require_current_user),
) -> TimelineGenerateResponse:
    require_permission(user, "simulation", "run")
    scenario = database.get_scenario_by_id(payload.scenario_id)
    if not scenario:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Scenario not found.")
    if bool(scenario.get("is_archived")):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Archived scenarios cannot be recorded.")

    run_id = database.create_run(
        scenario_id=payload.scenario_id,
        user_id=user["id"],
        run_mode="pre-record",
        control_mode=str(payload.control_mode or "fixed-time").strip().lower().replace("_", "-"),
        status="running",
        seed=payload.seed,
        duration_seconds=0,
        notes=f"Timeline generation requested for {payload.duration_seconds}s.",
    )
    database.log_audit_event(
        user_id=user["id"],
        action="api_generate_timeline",
        target="simulation_runs",
        details=f"Started pre-record timeline generation run ID={run_id} for scenario '{scenario['name']}'.",
    )
    timeline_generator.generate_timeline(
        scenario_id=payload.scenario_id,
        duration_limit=payload.duration_seconds,
        run_id=run_id,
        seed=payload.seed,
        control_mode=payload.control_mode,
    )
    return TimelineGenerateResponse(
        message="Timeline generation started.",
        run=completed_run_record(run_id),
    )


@app.post("/api/simulation/playback/load", response_model=SimulationActionResponse)
def load_playback(
    payload: PlaybackLoadRequest,
    user: dict = Depends(require_current_user),
) -> SimulationActionResponse:
    require_any_permission(user, [("simulation", "view"), ("dashboard", "view")])
    try:
        simulation = simulation_runtime.load_playback(payload.run_id)
    except SimulationRuntimeError as exc:
        raise simulation_conflict(exc) from exc
    database.log_audit_event(
        user_id=user["id"],
        action="api_load_playback",
        target="simulation_runs",
        details=f"Loaded pre-record run ID={payload.run_id} for playback.",
    )
    return simulation_action_response("Playback loaded.", simulation)


@app.post("/api/simulation/playback/start", response_model=SimulationActionResponse)
def start_playback(user: dict = Depends(require_current_user)) -> SimulationActionResponse:
    require_any_permission(user, [("simulation", "run"), ("dashboard", "view")])
    try:
        simulation = simulation_runtime.start_playback()
    except SimulationRuntimeError as exc:
        raise simulation_conflict(exc) from exc
    return simulation_action_response("Playback started.", simulation)


@app.post("/api/simulation/playback/seek", response_model=SimulationActionResponse)
def seek_playback(
    payload: PlaybackSeekRequest,
    user: dict = Depends(require_current_user),
) -> SimulationActionResponse:
    require_any_permission(user, [("simulation", "run"), ("dashboard", "view")])
    try:
        simulation = simulation_runtime.seek_playback(payload.frame_index)
    except SimulationRuntimeError as exc:
        raise simulation_conflict(exc) from exc
    return simulation_action_response("Playback seeked.", simulation)


@app.post("/api/simulation/configure", response_model=SimulationActionResponse)
def configure_simulation(
    payload: SimulationConfigureRequest,
    user: dict = Depends(require_current_user),
) -> SimulationActionResponse:
    require_permission(user, "simulation", "run")
    try:
        simulation = simulation_runtime.configure(payload)
    except SimulationRuntimeError as exc:
        raise simulation_conflict(exc) from exc
    database.log_audit_event(
        user_id=user["id"],
        action="api_configure_simulation",
        target="simulation",
        details=f"Configured scenario ID={payload.scenario_id or 'custom'} through the FastAPI bridge.",
    )
    return simulation_action_response("Simulation configured.", simulation)


@app.post("/api/simulation/start", response_model=SimulationActionResponse)
def start_simulation(
    payload: SimulationStartRequest | None = None,
    user: dict = Depends(require_current_user),
) -> SimulationActionResponse:
    require_permission(user, "simulation", "run")
    try:
        simulation = simulation_runtime.start(payload, user_id=user["id"])
    except SimulationRuntimeError as exc:
        raise simulation_conflict(exc) from exc
    database.log_audit_event(
        user_id=user["id"],
        action="api_start_simulation",
        target="simulation",
        details=f"Started simulation through the FastAPI bridge with status '{simulation.status}'.",
    )
    return simulation_action_response("Simulation start requested.", simulation)


@app.post("/api/simulation/pause", response_model=SimulationActionResponse)
def pause_simulation(user: dict = Depends(require_current_user)) -> SimulationActionResponse:
    require_permission(user, "simulation", "run")
    simulation = simulation_runtime.pause()
    return simulation_action_response("Simulation paused.", simulation)


@app.post("/api/simulation/resume", response_model=SimulationActionResponse)
def resume_simulation(user: dict = Depends(require_current_user)) -> SimulationActionResponse:
    require_permission(user, "simulation", "run")
    simulation = simulation_runtime.resume()
    return simulation_action_response("Simulation resumed.", simulation)


@app.post("/api/simulation/stop", response_model=SimulationActionResponse)
def stop_simulation(user: dict = Depends(require_current_user)) -> SimulationActionResponse:
    require_permission(user, "simulation", "run")
    simulation = simulation_runtime.stop()
    return simulation_action_response("Simulation stopped.", simulation)


@app.post("/api/simulation/reset", response_model=SimulationActionResponse)
def reset_simulation(user: dict = Depends(require_current_user)) -> SimulationActionResponse:
    require_permission(user, "simulation", "run")
    simulation = simulation_runtime.reset()
    return simulation_action_response("Simulation reset.", simulation)


@app.post("/api/simulation/step", response_model=SimulationActionResponse)
def step_simulation(
    payload: SimulationStepRequest,
    user: dict = Depends(require_current_user),
) -> SimulationActionResponse:
    require_permission(user, "simulation", "run")
    simulation = simulation_runtime.step(payload.num_ticks)
    return simulation_action_response("Simulation advanced.", simulation)


@app.websocket("/ws/simulation")
async def simulation_websocket(
    websocket: WebSocket,
    smartflow_api_session: str | None = Cookie(default=None, alias=API_SESSION_COOKIE),
) -> None:
    user = api_user_from_session_token(smartflow_api_session)
    if not user:
        await websocket.close(code=1008)
        return
    try:
        require_any_permission(user, [("simulation", "view"), ("dashboard", "view")])
    except HTTPException:
        await websocket.close(code=1008)
        return

    await websocket.accept()
    sequence = 0
    had_active_run = False
    try:
        while True:
            simulation = simulation_runtime.get_state()
            frame = render_frame_service.build_render_frame(
                simulation.state,
                sequence=sequence,
            )
            await websocket.send_json(frame)
            sequence += 1

            if simulation.status in {"running", "paused"}:
                had_active_run = True
            if had_active_run and simulation.status in {"stopped", "completed", "error"}:
                await websocket.close(code=1000)
                return

            await asyncio.sleep(0.1)
    except WebSocketDisconnect:
        return
    except RuntimeError:
        return


@app.get("/api/visual-network")
def visual_network(
    intersection_id: str | None = None,
    user: dict = Depends(require_current_user),
) -> dict:
    try:
        require_permission(user, "dashboard", "view")
    except HTTPException:
        require_permission(user, "simulation", "view")
    try:
        return visual_network_service.load_client_visual_network(intersection_id)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Visual network unavailable.") from exc
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Visual network payload rejected.") from exc
