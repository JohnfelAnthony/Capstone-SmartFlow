"""
SMARTFLOW - Configuration Constants
"""

import os


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
SCENARIO_CONFIG_MAX_BYTES = int(os.environ.get("SMARTFLOW_SCENARIO_CONFIG_MAX_BYTES", "16384"))
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

SESSION_TIMEOUT = int(os.environ.get("SMARTFLOW_SESSION_TIMEOUT", "3600"))
SESSION_COOKIE_NAME = os.environ.get("SMARTFLOW_SESSION_COOKIE_NAME", "smartflow_session")
SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SAMESITE = os.environ.get("SMARTFLOW_SESSION_COOKIE_SAMESITE", "Lax")
SESSION_COOKIE_SECURE = _env_bool(
    "SMARTFLOW_SESSION_COOKIE_SECURE",
    PUBLIC_BASE_URL.lower().startswith("https://"),
)
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
