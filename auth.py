"""
SMARTFLOW - Authentication & Session Management
"""

import secrets
from datetime import UTC, datetime, timedelta

try:
    from flask import has_request_context, request, session
except ImportError:  # pragma: no cover - used only by dependency-light unit tests
    class _FallbackRequest:
        headers: dict = {}
        remote_addr: str = ""

    class _FallbackSession(dict):
        permanent = False

    def has_request_context() -> bool:
        return False

    request = _FallbackRequest()
    session = _FallbackSession()

import config
import database

LANDING_ROUTE_ORDER = (
    ("dashboard", "view", "/dashboard"),
    ("simulation", "view", "/simulation"),
    ("scenarios", "view", "/scenarios"),
    ("performance", "view", "/performance"),
    ("ai-agent", "view", "/ai-agent"),
    ("rl-training", "view", "/rl-training"),
    ("runs-reports", "view", "/runs-reports"),
    ("profile", "view", "/profile"),
    ("help", "view", "/help"),
)

ADMIN_RESTORABLE_ROUTES = {
    "/admin/users",
    "/admin/roles",
    "/admin/audit",
    "/admin/backups",
}


def hash_password(password: str) -> str:
    from werkzeug.security import generate_password_hash

    return generate_password_hash(password)


def verify_password(password: str, hashed: str) -> bool:
    from werkzeug.security import check_password_hash

    return check_password_hash(hashed, password)


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


def _request_ip_address() -> str:
    if not has_request_context():
        return ""
    forwarded_for = (request.headers.get("X-Forwarded-For") or "").strip()
    if forwarded_for:
        return forwarded_for.split(",")[0].strip()
    return (request.remote_addr or "").strip()


def ensure_csrf_token() -> str:
    token = session.get("csrf_token")
    if not token:
        token = secrets.token_hex(32)
        session["csrf_token"] = token
    return token


def validate_csrf_request() -> bool:
    expected_token = session.get("csrf_token")
    if not expected_token:
        return False
    request_token = request.headers.get(config.CSRF_HEADER_NAME, "")
    return secrets.compare_digest(request_token, expected_token)


def _write_user_snapshot(user: dict):
    session["user_id"] = user["id"]
    session["username"] = user["username"]
    session["full_name"] = user["full_name"]
    session["role"] = user["role_name"]
    session["role_id"] = user["role_id"]
    session["must_change_password"] = bool(user["must_change_password"])


def _write_auth_session_version():
    session["auth_session_version"] = database.get_auth_session_version()


def _user_role_name(user: dict | None) -> str:
    if not isinstance(user, dict):
        return ""
    role_name = user.get("role") or user.get("role_name") or ""
    return str(role_name).strip().lower()


def _can_restore_route(user: dict, route: str) -> bool:
    normalized_route = str(route or "").strip()
    if not normalized_route:
        return False

    user_id = user.get("id")
    if not user_id:
        return False

    if normalized_route in ADMIN_RESTORABLE_ROUTES:
        return _user_role_name(user) == "admin"

    for page, action, candidate_route in LANDING_ROUTE_ORDER:
        if normalized_route == candidate_route:
            if _user_role_name(user) == "admin":
                return True
            return database.check_user_permission(user_id, page, action)

    return False


def authenticate(username: str, password: str) -> tuple[dict | None, str | None]:
    """Authenticate and return (user_dict, failure_reason)."""
    if not username or not password:
        return None, "invalid"

    username = username.strip()
    request_ip = _request_ip_address()

    if database.is_login_blocked(username, request_ip):
        return None, "locked"

    user = database.get_user_by_username(username)
    if not user or not verify_password(password, user["password_hash"]):
        database.record_login_attempt(username, False, request_ip)
        return None, "invalid"

    if user["status"] == "inactive":
        return user, "inactive"

    if user["status"] != "active":
        return None, "invalid"

    database.record_login_attempt(username, True, request_ip)
    return user, None


def create_session(user: dict):
    """Create a new authenticated session with a rotated server-side token."""
    existing_token = session.get("session_token")
    if existing_token:
        database.delete_session_by_token(existing_token)

    session.clear()
    session.permanent = True
    _write_user_snapshot(user)
    _write_auth_session_version()
    session["csrf_token"] = secrets.token_hex(32)

    token = secrets.token_hex(32)
    database.create_user_session(user["id"], token, _session_expiry_string())
    session["session_token"] = token

    database.update_last_login(user["id"])
    database.log_audit_event(
        user_id=user["id"],
        action="login",
        target="auth",
        details=f"User '{user['username']}' logged in successfully",
    )


def rotate_current_session_token():
    user_id = session.get("user_id")
    current_token = session.get("session_token")
    if not user_id:
        return

    if current_token:
        database.delete_session_by_token(current_token)

    new_token = secrets.token_hex(32)
    database.create_user_session(user_id, new_token, _session_expiry_string())
    session["session_token"] = new_token
    _write_auth_session_version()
    session.permanent = True


def clear_session():
    """Clear session and delete token from database."""
    user_id = session.get("user_id")
    username = session.get("username")
    token = session.get("session_token")

    if token:
        database.delete_session_by_token(token)

    if user_id:
        database.log_audit_event(
            user_id=user_id,
            action="logout",
            target="auth",
            details=f"User '{username}' logged out",
        )

    session.clear()
    session["csrf_token"] = secrets.token_hex(32)


def validate_current_session() -> bool:
    """Check that the current session is still valid and sync role/status from the database."""
    user_id = session.get("user_id")
    token = session.get("session_token")
    session_version = session.get("auth_session_version")

    if not user_id or not token or not session_version:
        return False

    current_session_version = database.get_auth_session_version()
    if not secrets.compare_digest(str(session_version), current_session_version):
        database.delete_session_by_token(token)
        return False

    db_session = database.get_session_by_token(token)
    if not db_session or db_session["user_id"] != user_id:
        return False

    user = database.get_user_by_id(user_id)
    if not user or user["status"] != "active":
        database.delete_session_by_token(token)
        return False

    expires_at = _parse_timestamp(db_session.get("expires_at"))
    if expires_at is None or expires_at < _utc_now():
        database.delete_session_by_token(token)
        return False

    _write_user_snapshot(user)
    session["auth_session_version"] = current_session_version
    session.permanent = True
    ensure_csrf_token()
    database.update_session_expiry(token, _session_expiry_string())
    return True


def get_current_user() -> dict | None:
    uid = session.get("user_id")
    if not uid:
        return None
    if not validate_current_session():
        clear_session()
        return None
    user = database.get_user_by_id(uid)
    if not user:
        return None
    return {
        "id": user["id"],
        "username": user["username"],
        "full_name": user["full_name"],
        "role": user["role_name"],
        "status": user["status"],
        "must_change_password": bool(user["must_change_password"]),
    }


def is_authenticated() -> bool:
    return bool(
        session.get("user_id")
        and session.get("session_token")
        and session.get("auth_session_version")
    )


def is_admin() -> bool:
    user = get_current_user()
    return bool(user and user["status"] == "active" and user["role"] == "admin")


def has_permission(page: str, action: str = "view") -> bool:
    user = get_current_user()
    if not user:
        return False
    if user["status"] != "active":
        return False
    if user["role"] == "admin":
        return True
    return database.check_user_permission(user["id"], page, action)


def get_authenticated_landing_path(user: dict | None = None) -> str | None:
    current_user = user or get_current_user()
    if not current_user or current_user.get("status") != "active":
        return None

    last_visited_path = session.get("last_visited_path")
    if _can_restore_route(current_user, last_visited_path):
        return str(last_visited_path)

    if _user_role_name(current_user) == "admin":
        return "/dashboard"

    user_id = current_user.get("id")
    if not user_id:
        return None

    for page, action, route in LANDING_ROUTE_ORDER:
        if database.check_user_permission(user_id, page, action):
            return route
    return None


def validate_password_strength(password: str) -> list[str]:
    errors = []
    if len(password) < config.MIN_PASSWORD_LENGTH:
        errors.append(f"Password must be at least {config.MIN_PASSWORD_LENGTH} characters")
    if not any(character.isupper() for character in password):
        errors.append("Password must contain at least one uppercase letter")
    if not any(character.islower() for character in password):
        errors.append("Password must contain at least one lowercase letter")
    if not any(character.isdigit() for character in password):
        errors.append("Password must contain at least one digit")
    return errors
