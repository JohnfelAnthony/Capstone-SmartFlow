from __future__ import annotations

import json
import secrets
from datetime import UTC, datetime, timedelta
from typing import Any

from fastapi import Cookie, HTTPException, Request, Response, status

import auth
import config
import database
from backend.schemas import CurrentUser, Permission, Scenario


API_SESSION_COOKIE = "smartflow_api_session"


def _utc_now() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


def _session_expiry_string() -> str:
    return (_utc_now() + timedelta(seconds=config.SESSION_TIMEOUT)).strftime("%Y-%m-%d %H:%M:%S")


def _parse_timestamp(value: str | None) -> datetime | None:
    if not value:
        return None
    for parser in (datetime.fromisoformat, lambda raw: datetime.strptime(raw, "%Y-%m-%d %H:%M:%S")):
        try:
            return parser(value)
        except (TypeError, ValueError):
            continue
    return None


def request_ip_address(request: Request) -> str:
    forwarded_for = (request.headers.get("X-Forwarded-For") or "").strip()
    if forwarded_for:
        return forwarded_for.split(",")[0].strip()
    return (request.client.host if request.client else "").strip()


def _permission_models(role_id: int) -> list[Permission]:
    return [
        Permission(page=row["page"], action=row["action"])
        for row in database.get_permissions_for_role(role_id)
    ]


def user_model(user: dict) -> CurrentUser:
    return CurrentUser(
        id=int(user["id"]),
        username=str(user["username"]),
        full_name=str(user["full_name"]),
        email=user.get("email"),
        role=str(user.get("role_name") or user.get("role") or ""),
        role_id=int(user["role_id"]),
        status=str(user["status"]),
        must_change_password=bool(user["must_change_password"]),
        permissions=_permission_models(int(user["role_id"])),
    )


def create_api_session(response: Response, user: dict) -> str:
    token = secrets.token_hex(32)
    database.create_user_session(user["id"], token, _session_expiry_string())
    database.update_last_login(user["id"])
    database.log_audit_event(
        user_id=user["id"],
        action="api_login",
        target="auth",
        details=f"User '{user['username']}' logged in through the FastAPI bridge.",
    )
    response.set_cookie(
        API_SESSION_COOKIE,
        token,
        max_age=config.SESSION_TIMEOUT,
        httponly=True,
        secure=config.SESSION_COOKIE_SECURE,
        samesite=config.SESSION_COOKIE_SAMESITE.lower(),
        path="/",
    )
    return token


def clear_api_session(response: Response, token: str | None, user: dict | None = None) -> None:
    if token:
        database.delete_session_by_token(token)
    if user:
        database.log_audit_event(
            user_id=user["id"],
            action="api_logout",
            target="auth",
            details=f"User '{user['username']}' logged out from the FastAPI bridge.",
        )
    response.delete_cookie(API_SESSION_COOKIE, path="/")


def _user_from_token(token: str | None) -> dict | None:
    if not token:
        return None
    db_session = database.get_session_by_token(token)
    if not db_session:
        return None
    expires_at = _parse_timestamp(db_session.get("expires_at"))
    if expires_at is None or expires_at < _utc_now():
        database.delete_session_by_token(token)
        return None
    user = database.get_user_by_id(db_session["user_id"])
    if not user or user["status"] != "active":
        database.delete_session_by_token(token)
        return None
    database.update_session_expiry(token, _session_expiry_string())
    return user


def require_current_user(
    smartflow_api_session: str | None = Cookie(default=None, alias=API_SESSION_COOKIE),
) -> dict:
    user = _user_from_token(smartflow_api_session)
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Authentication required.")
    return user


def optional_current_user(
    smartflow_api_session: str | None = Cookie(default=None, alias=API_SESSION_COOKIE),
) -> dict | None:
    return _user_from_token(smartflow_api_session)


def api_user_from_session_token(token: str | None) -> dict | None:
    return _user_from_token(token)


def require_permission(user: dict, page: str, action: str = "view") -> None:
    role_name = str(user.get("role_name") or "").lower()
    if role_name == "admin":
        return
    if database.check_user_permission(user["id"], page, action):
        return
    raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Permission denied.")


def authenticate_for_api(username: str, password: str, request: Request) -> tuple[dict | None, str | None]:
    normalized_username = username.strip()
    ip_address = request_ip_address(request)
    if database.is_login_blocked(normalized_username, ip_address):
        return None, "locked"

    user = database.get_user_by_username(normalized_username)
    if not user or not auth.verify_password(password, user["password_hash"]):
        database.record_login_attempt(normalized_username, False, ip_address)
        return None, "invalid"
    if user["status"] == "inactive":
        return user, "inactive"
    if user["status"] != "active":
        return None, "invalid"

    database.record_login_attempt(normalized_username, True, ip_address)
    return user, None


def landing_path_for_api_user(user: dict) -> str | None:
    if str(user.get("role_name") or "").lower() == "admin":
        return "/dashboard"
    for page, action, route in auth.LANDING_ROUTE_ORDER:
        if database.check_user_permission(user["id"], page, action):
            return route
    return None


def _json_object(value: Any) -> dict[str, Any]:
    if isinstance(value, dict):
        return value
    if not value:
        return {}
    try:
        parsed = json.loads(str(value))
    except (TypeError, ValueError, json.JSONDecodeError):
        return {}
    return parsed if isinstance(parsed, dict) else {}


def scenario_model(row: dict) -> Scenario:
    return Scenario(
        id=int(row["id"]),
        name=str(row["name"]),
        description=row.get("description") or "",
        traffic_density=str(row.get("traffic_density") or "Medium"),
        pedestrian_density=str(row.get("pedestrian_density") or "Medium"),
        emergency_mode=str(row.get("emergency_mode") or "Disabled"),
        road_constraint=str(row.get("road_constraint") or "None"),
        intersection_id=str(row.get("intersection_id") or "tagum_1"),
        lane_closure_config=_json_object(row.get("lane_closure_config")),
        construction_config=_json_object(row.get("construction_config")),
        accident_config=_json_object(row.get("accident_config")),
        flooding_config=_json_object(row.get("flooding_config")),
        created_by=row.get("created_by"),
        created_at=row.get("created_at"),
        updated_at=row.get("updated_at"),
        is_official=bool(row.get("is_official")),
        is_archived=bool(row.get("is_archived")),
    )
