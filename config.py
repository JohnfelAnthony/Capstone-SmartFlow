"""
SMARTFLOW - Configuration Constants
"""

import os
from urllib.parse import urlsplit


def _env_bool(name: str, default: bool = False) -> bool:
    value = os.environ.get(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


BASE_DIR = os.path.dirname(os.path.abspath(__file__))

SECRET_KEY = os.environ.get("SMARTFLOW_SECRET_KEY")
if not SECRET_KEY:
    raise RuntimeError(
        "SMARTFLOW_SECRET_KEY is required. Set a strong secret key before starting SMARTFLOW."
    )

DB_PATH = os.environ.get(
    "SMARTFLOW_DB_PATH",
    os.path.join(BASE_DIR, "data", "smartflow.db"),
)
VISUAL_NETWORK_PATH = os.environ.get(
    "SMARTFLOW_VISUAL_NETWORK_PATH",
    os.path.join(BASE_DIR, "data", "generated", "visual_network.json"),
)
VISUAL_NETWORK_MAX_BYTES = int(os.environ.get("SMARTFLOW_VISUAL_NETWORK_MAX_BYTES", "524288"))
SCENARIO_CONFIG_MAX_BYTES = int(os.environ.get("SMARTFLOW_SCENARIO_CONFIG_MAX_BYTES", "2097152"))
if SCENARIO_CONFIG_MAX_BYTES < 1:
    raise RuntimeError("SMARTFLOW_SCENARIO_CONFIG_MAX_BYTES must be positive.")
MAX_RECORDING_SECONDS = int(os.environ.get("SMARTFLOW_MAX_RECORDING_SECONDS", "3600"))
if not 1 <= MAX_RECORDING_SECONDS <= 24 * 60 * 60:
    raise RuntimeError("SMARTFLOW_MAX_RECORDING_SECONDS must be between 1 and 86400.")
RECORDING_BYTES_PER_SECOND_RESERVE = 512 * 1024
RECORDING_FREE_SPACE_RESERVE = 256 * 1024 * 1024
LOGIN_ATTEMPT_RETENTION_DAYS = int(os.environ.get("SMARTFLOW_LOGIN_ATTEMPT_RETENTION_DAYS", "30"))
SIMULATION_SUPERVISOR_BASE_DELAY_SECONDS = int(
    os.environ.get("SMARTFLOW_SIMULATION_SUPERVISOR_BASE_DELAY_SECONDS", "2")
)
SIMULATION_SUPERVISOR_MAX_DELAY_SECONDS = int(
    os.environ.get("SMARTFLOW_SIMULATION_SUPERVISOR_MAX_DELAY_SECONDS", "30")
)
SIMULATION_SUPERVISOR_MAX_RETRIES = int(
    os.environ.get("SMARTFLOW_SIMULATION_SUPERVISOR_MAX_RETRIES", "5")
)

DEBUG = _env_bool("SMARTFLOW_DEBUG", False)
PORT = int(os.environ.get("SMARTFLOW_PORT", "8050"))
PUBLIC_BASE_URL = os.environ.get("SMARTFLOW_PUBLIC_BASE_URL", "").strip()
PRODUCTION = os.environ.get("SMARTFLOW_ENV", "").strip().lower() == "production"


def _origin(value: str) -> str:
    parsed = urlsplit(value)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc or parsed.path not in {"", "/"} or parsed.query or parsed.fragment:
        raise RuntimeError(f"Invalid SmartFlow origin: {value!r}")
    return f"{parsed.scheme}://{parsed.netloc}"


_configured_origins = os.environ.get("SMARTFLOW_ALLOWED_ORIGINS", "").strip()
ALLOWED_ORIGINS = (
    [_origin(value.strip()) for value in _configured_origins.split(",") if value.strip()]
    if _configured_origins
    else ([_origin(PUBLIC_BASE_URL)] if PUBLIC_BASE_URL else ["http://127.0.0.1:5173", "http://localhost:5173"])
)
if PRODUCTION:
    if not PUBLIC_BASE_URL or not PUBLIC_BASE_URL.startswith("https://"):
        raise RuntimeError("SMARTFLOW_PUBLIC_BASE_URL must be an HTTPS origin in production.")
    if _origin(PUBLIC_BASE_URL) not in ALLOWED_ORIGINS:
        raise RuntimeError("Production public origin must be allowed by SMARTFLOW_ALLOWED_ORIGINS.")
    if any(not origin.startswith("https://") for origin in ALLOWED_ORIGINS):
        raise RuntimeError("Production allowed browser origins must use HTTPS.")
    if len(SECRET_KEY) < 32 or SECRET_KEY == "local-dev-change-before-production":
        raise RuntimeError("Production requires a unique SMARTFLOW_SECRET_KEY of at least 32 characters.")

SESSION_TIMEOUT = int(os.environ.get("SMARTFLOW_SESSION_TIMEOUT", "3600"))
SESSION_COOKIE_NAME = os.environ.get("SMARTFLOW_SESSION_COOKIE_NAME", "smartflow_session")
SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SAMESITE = os.environ.get("SMARTFLOW_SESSION_COOKIE_SAMESITE", "Lax")
SESSION_COOKIE_SECURE = _env_bool(
    "SMARTFLOW_SESSION_COOKIE_SECURE",
    PUBLIC_BASE_URL.lower().startswith("https://"),
)
if PRODUCTION and not SESSION_COOKIE_SECURE:
    raise RuntimeError("Production requires secure session cookies.")
CSRF_COOKIE_NAME = "smartflow_csrf_token"
CSRF_HEADER_NAME = "X-CSRF-Token"

DEFAULT_ADMIN_USERNAME = "admin"
BOOTSTRAP_ADMIN_PASSWORD = os.environ.get("SMARTFLOW_BOOTSTRAP_ADMIN_PASSWORD")
BOOTSTRAP_SECONDARY_ADMIN_PASSWORD = os.environ.get("SMARTFLOW_BOOTSTRAP_SECONDARY_ADMIN_PASSWORD")
BOOTSTRAP_STANDARD_USER_PASSWORD = os.environ.get("SMARTFLOW_BOOTSTRAP_STANDARD_USER_PASSWORD")
BOOTSTRAP_RESERVED_PASSWORDS = tuple(
    password
    for password in (
        BOOTSTRAP_ADMIN_PASSWORD,
        BOOTSTRAP_SECONDARY_ADMIN_PASSWORD,
        BOOTSTRAP_STANDARD_USER_PASSWORD,
    )
    if password
)

APP_NAME = "SmartFlow Traffic"
APP_VERSION = "1.0.0"
APP_TAGLINE = "AI-Driven Traffic Simulation & Decision Support"
TIMELINE_GZIP_ENABLED = _env_bool("SMARTFLOW_TIMELINE_GZIP_ENABLED", True)
TIMELINE_KEEP_RECENT_RAW = int(os.environ.get("SMARTFLOW_TIMELINE_KEEP_RECENT_RAW", "6"))

REGISTRATION_MODE = os.environ.get("SMARTFLOW_REGISTRATION_MODE", "approval-only").strip().lower()
if REGISTRATION_MODE not in {"approval-only", "open", "disabled"}:
    raise RuntimeError(
        "SMARTFLOW_REGISTRATION_MODE must be one of: 'approval-only', 'open', 'disabled'."
    )

MIN_PASSWORD_LENGTH = int(os.environ.get("SMARTFLOW_MIN_PASSWORD_LENGTH", "8"))

LOGGING_LEVEL = "INFO"
