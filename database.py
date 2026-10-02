"""
SMARTFLOW — SQLite Database Layer
All schema definitions, CRUD operations, and seed data.
"""

import sqlite3
import os
import json
import secrets
from datetime import UTC, datetime, timedelta
from contextlib import contextmanager
from pathlib import Path

import config
from services.scenario_storage import validate_scenario_json_size

SCENARIO_JSON_FIELDS = (
    "engine_config",
    "lane_closure_config",
    "construction_config",
    "accident_config",
    "flooding_config",
)
AUTH_SESSION_VERSION_SETTING = "auth_session_version"


def get_connection():
    os.makedirs(os.path.dirname(config.DB_PATH), exist_ok=True)
    conn = sqlite3.connect(config.DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    conn.execute("PRAGMA busy_timeout=5000")
    return conn


def _connect_sqlite_file(path: str | Path) -> sqlite3.Connection:
    conn = sqlite3.connect(str(path))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys=ON")
    conn.execute("PRAGMA busy_timeout=5000")
    return conn


def _validate_json_object(field_name: str, raw_json: str | None):
    if not raw_json:
        return
    if not isinstance(raw_json, str):
        raise ValueError(f"JSON configuration for '{field_name}' must be a string.")

    validate_scenario_json_size(field_name, raw_json)

    try:
        parsed = json.loads(raw_json)
    except Exception as exc:
        raise ValueError(f"Invalid JSON configuration in '{field_name}': {str(exc)}") from exc

    if not isinstance(parsed, dict):
        raise ValueError(f"JSON configuration for '{field_name}' must be an object.")


@contextmanager
def get_db():
    conn = get_connection()
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


# ─── Schema ────────────────────────────────────────────────────────

SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS roles (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL UNIQUE,
    description TEXT,
    created_at TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    full_name TEXT NOT NULL,
    username TEXT NOT NULL UNIQUE,
    email TEXT UNIQUE,
    password_hash TEXT NOT NULL,
    role_id INTEGER NOT NULL DEFAULT 2,
    status TEXT NOT NULL DEFAULT 'active',
    must_change_password INTEGER NOT NULL DEFAULT 0,
    created_at TEXT DEFAULT (datetime('now')),
    updated_at TEXT DEFAULT (datetime('now')),
    last_login_at TEXT,
    FOREIGN KEY (role_id) REFERENCES roles(id)
);

CREATE TABLE IF NOT EXISTS permissions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    role_id INTEGER NOT NULL,
    page TEXT NOT NULL,
    action TEXT NOT NULL DEFAULT 'view',
    FOREIGN KEY (role_id) REFERENCES roles(id)
);

CREATE TABLE IF NOT EXISTS user_sessions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    token TEXT NOT NULL,
    created_at TEXT DEFAULT (datetime('now')),
    expires_at TEXT,
    FOREIGN KEY (user_id) REFERENCES users(id)
);

CREATE TABLE IF NOT EXISTS audit_logs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER,
    action TEXT NOT NULL,
    target TEXT,
    details TEXT,
    ip_address TEXT,
    user_agent TEXT,
    timestamp TEXT DEFAULT (datetime('now'))
);


CREATE TABLE IF NOT EXISTS scenarios (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    description TEXT,
    traffic_density TEXT DEFAULT 'Medium',
    pedestrian_density TEXT DEFAULT 'Medium',
    emergency_mode TEXT DEFAULT 'Disabled',
    road_constraint TEXT DEFAULT 'None',
    intersection_id TEXT DEFAULT 'tagum_1',
    lane_closure_config TEXT DEFAULT '{}',
    construction_config TEXT DEFAULT '{}',
    accident_config TEXT DEFAULT '{}',
    flooding_config TEXT DEFAULT '{}',
    created_by INTEGER,
    created_at TEXT DEFAULT (datetime('now')),
    updated_at TEXT DEFAULT (datetime('now')),
    is_official INTEGER DEFAULT 0,
    is_archived INTEGER DEFAULT 0,
    FOREIGN KEY (created_by) REFERENCES users(id)
);

CREATE TABLE IF NOT EXISTS scenario_constraints (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    scenario_id INTEGER NOT NULL,
    constraint_type TEXT NOT NULL,
    config_json TEXT DEFAULT '{}',
    FOREIGN KEY (scenario_id) REFERENCES scenarios(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS simulation_runs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    scenario_id INTEGER,
    user_id INTEGER,
    run_mode TEXT DEFAULT 'live',
    control_mode TEXT DEFAULT 'fixed-time',
    rl_model_id INTEGER,
    status TEXT DEFAULT 'idle',
    start_time TEXT,
    end_time TEXT,
    duration_seconds REAL DEFAULT 0,
    seed INTEGER,
    notes TEXT,
    timeline_path TEXT,
    is_baseline INTEGER DEFAULT 0,
    is_favorite INTEGER DEFAULT 0,
    created_at TEXT DEFAULT (datetime('now')),
    FOREIGN KEY (scenario_id) REFERENCES scenarios(id),
    FOREIGN KEY (user_id) REFERENCES users(id)
);

CREATE TABLE IF NOT EXISTS run_metrics (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id INTEGER NOT NULL,
    avg_waiting_time REAL DEFAULT 0,
    avg_queue_length REAL DEFAULT 0,
    max_queue_length INTEGER DEFAULT 0,
    throughput INTEGER DEFAULT 0,
    avg_pedestrian_delay REAL DEFAULT 0,
    emergency_clearance_time REAL DEFAULT 0,
    signal_phase_efficiency REAL DEFAULT 0,
    congestion_severity TEXT DEFAULT 'low',
    raw_metrics_json TEXT DEFAULT '{}',
    recorded_at TEXT DEFAULT (datetime('now')),
    FOREIGN KEY (run_id) REFERENCES simulation_runs(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS rl_models (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    algorithm TEXT DEFAULT 'DQN',
    version TEXT DEFAULT '1.0',
    checkpoint_path TEXT,
    intersection_support_json TEXT DEFAULT '[]',
    training_scenarios_json TEXT DEFAULT '[]',
    observation_version TEXT DEFAULT 'obs_v1',
    reward_version TEXT DEFAULT 'reward_v1',
    action_space_version TEXT DEFAULT 'action_v1',
    seed_set_json TEXT DEFAULT '[]',
    training_date TEXT,
    best_evaluation_score REAL,
    created_at TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS rl_checkpoints (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    model_id INTEGER NOT NULL,
    episode INTEGER DEFAULT 0,
    reward REAL DEFAULT 0,
    loss REAL DEFAULT 0,
    epsilon REAL DEFAULT 1.0,
    path TEXT,
    created_at TEXT DEFAULT (datetime('now')),
    FOREIGN KEY (model_id) REFERENCES rl_models(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS rl_training_jobs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER,
    status TEXT DEFAULT 'queued',
    selected_algorithms_json TEXT DEFAULT '[]',
    settings_json TEXT DEFAULT '{}',
    progress_percent REAL DEFAULT 0,
    current_algorithm TEXT,
    current_item_id INTEGER,
    log_path TEXT,
    message TEXT,
    started_at TEXT,
    ended_at TEXT,
    created_at TEXT DEFAULT (datetime('now')),
    FOREIGN KEY (user_id) REFERENCES users(id)
);

CREATE TABLE IF NOT EXISTS rl_training_job_items (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    job_id INTEGER NOT NULL,
    algorithm TEXT NOT NULL,
    sequence_index INTEGER NOT NULL DEFAULT 0,
    status TEXT DEFAULT 'queued',
    command_json TEXT DEFAULT '[]',
    progress_percent REAL DEFAULT 0,
    latest_episode INTEGER DEFAULT 0,
    latest_reward REAL,
    latest_epsilon REAL,
    latest_timesteps INTEGER DEFAULT 0,
    artifact_path TEXT,
    metadata_path TEXT,
    rl_model_id INTEGER,
    evaluation_path TEXT,
    message TEXT,
    started_at TEXT,
    ended_at TEXT,
    created_at TEXT DEFAULT (datetime('now')),
    FOREIGN KEY (job_id) REFERENCES rl_training_jobs(id) ON DELETE CASCADE,
    FOREIGN KEY (rl_model_id) REFERENCES rl_models(id) ON DELETE SET NULL
);

CREATE TABLE IF NOT EXISTS notifications (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER,
    message TEXT NOT NULL,
    type TEXT DEFAULT 'info',
    read INTEGER DEFAULT 0,
    created_at TEXT DEFAULT (datetime('now')),
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS system_settings (
    key TEXT PRIMARY KEY,
    value TEXT,
    updated_at TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS backups (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    filename TEXT NOT NULL,
    created_by INTEGER,
    created_at TEXT DEFAULT (datetime('now')),
    size_bytes INTEGER DEFAULT 0,
    FOREIGN KEY (created_by) REFERENCES users(id)
);

CREATE TABLE IF NOT EXISTS login_attempts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT NOT NULL,
    ip_address TEXT,
    timestamp TEXT DEFAULT (datetime('now')),
    success INTEGER NOT NULL DEFAULT 0
);

CREATE INDEX IF NOT EXISTS idx_users_role_id ON users(role_id);
CREATE INDEX IF NOT EXISTS idx_permissions_role_id ON permissions(role_id);
CREATE INDEX IF NOT EXISTS idx_user_sessions_user_id ON user_sessions(user_id);
CREATE INDEX IF NOT EXISTS idx_user_sessions_token ON user_sessions(token);
CREATE INDEX IF NOT EXISTS idx_scenarios_created_by ON scenarios(created_by);
CREATE INDEX IF NOT EXISTS idx_scenario_constraints_scenario_id ON scenario_constraints(scenario_id);
CREATE INDEX IF NOT EXISTS idx_simulation_runs_scenario_id ON simulation_runs(scenario_id);
CREATE INDEX IF NOT EXISTS idx_simulation_runs_user_id ON simulation_runs(user_id);
CREATE INDEX IF NOT EXISTS idx_simulation_runs_status ON simulation_runs(status);
CREATE INDEX IF NOT EXISTS idx_simulation_runs_created_at ON simulation_runs(created_at);
CREATE INDEX IF NOT EXISTS idx_run_metrics_run_id ON run_metrics(run_id);
CREATE INDEX IF NOT EXISTS idx_rl_checkpoints_model_id ON rl_checkpoints(model_id);
CREATE INDEX IF NOT EXISTS idx_rl_training_jobs_status ON rl_training_jobs(status);
CREATE INDEX IF NOT EXISTS idx_rl_training_job_items_job_id ON rl_training_job_items(job_id);
CREATE INDEX IF NOT EXISTS idx_notifications_user_id ON notifications(user_id);
CREATE INDEX IF NOT EXISTS idx_backups_created_by ON backups(created_by);
CREATE INDEX IF NOT EXISTS idx_audit_logs_timestamp ON audit_logs(timestamp);
CREATE INDEX IF NOT EXISTS idx_audit_logs_action ON audit_logs(action);
"""


def init_db():
    with get_db() as conn:
        conn.executescript(SCHEMA_SQL)
    _migrate_login_attempts()
    _migrate_audit_logs()
    _migrate_simulation_runs()
    _migrate_scenarios()
    _migrate_rl_models()
    normalize_standalone_artifact_paths()
    prune_login_attempts()
    get_auth_session_version()


def _migrate_login_attempts():
    with get_db() as conn:
        columns = {
            row["name"]
            for row in conn.execute("PRAGMA table_info(login_attempts)").fetchall()
        }
        if columns and "ip_address" not in columns:
            conn.execute("ALTER TABLE login_attempts ADD COLUMN ip_address TEXT")
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_login_attempts_username_ip_time ON login_attempts(username, ip_address, timestamp)"
        )


def _migrate_audit_logs():
    with get_db() as conn:
        columns = {
            row["name"]
            for row in conn.execute("PRAGMA table_info(audit_logs)").fetchall()
        }
        if columns and "user_agent" not in columns:
            conn.execute("ALTER TABLE audit_logs ADD COLUMN user_agent TEXT")


def _migrate_simulation_runs():
    with get_db() as conn:
        columns = {
            row["name"]
            for row in conn.execute("PRAGMA table_info(simulation_runs)").fetchall()
        }
        if columns and "run_mode" not in columns:
            conn.execute("ALTER TABLE simulation_runs ADD COLUMN run_mode TEXT DEFAULT 'live'")
        if columns and "timeline_path" not in columns:
            conn.execute("ALTER TABLE simulation_runs ADD COLUMN timeline_path TEXT")


def _migrate_scenarios():
    with get_db() as conn:
        columns = {
            row["name"]
            for row in conn.execute("PRAGMA table_info(scenarios)").fetchall()
        }
        if columns and "engine_config" not in columns:
            conn.execute("ALTER TABLE scenarios ADD COLUMN engine_config TEXT DEFAULT '{}'")
        if columns and "intersection_id" not in columns:
            conn.execute("ALTER TABLE scenarios ADD COLUMN intersection_id TEXT DEFAULT 'tagum_1'")


def _migrate_rl_models():
    expected_columns = {
        "intersection_support_json": "TEXT DEFAULT '[]'",
        "training_scenarios_json": "TEXT DEFAULT '[]'",
        "observation_version": "TEXT DEFAULT 'obs_v1'",
        "reward_version": "TEXT DEFAULT 'reward_v1'",
        "action_space_version": "TEXT DEFAULT 'action_v1'",
        "seed_set_json": "TEXT DEFAULT '[]'",
        "training_date": "TEXT",
        "best_evaluation_score": "REAL",
    }
    with get_db() as conn:
        columns = {
            row["name"]
            for row in conn.execute("PRAGMA table_info(rl_models)").fetchall()
        }
        for column_name, column_definition in expected_columns.items():
            if columns and column_name not in columns:
                conn.execute(f"ALTER TABLE rl_models ADD COLUMN {column_name} {column_definition}")


def _portable_data_path(value) -> str | None:
    if not value:
        return value

    raw_value = str(value)
    normalized_value = raw_value.replace("\\", "/")
    marker = "/data/"
    marker_index = normalized_value.lower().find(marker)
    if marker_index < 0:
        return raw_value

    relative_path = normalized_value[marker_index + 1 :]
    return relative_path.replace("/", os.sep)


def normalize_standalone_artifact_paths() -> int:
    """Convert copied absolute artifact paths into portable SmartFlow data paths."""
    path_columns = {
        "rl_models": ("checkpoint_path",),
        "rl_checkpoints": ("path",),
        "rl_training_jobs": ("log_path",),
        "rl_training_job_items": ("artifact_path", "metadata_path", "evaluation_path"),
    }
    updated_count = 0
    with get_db() as conn:
        for table_name, columns in path_columns.items():
            table_columns = {
                row["name"]
                for row in conn.execute(f"PRAGMA table_info({table_name})").fetchall()
            }
            if not table_columns:
                continue
            active_columns = [column for column in columns if column in table_columns]
            if not active_columns:
                continue

            select_columns = ", ".join(["id", *active_columns])
            rows = conn.execute(f"SELECT {select_columns} FROM {table_name}").fetchall()
            for row in rows:
                updates = {}
                for column in active_columns:
                    next_value = _portable_data_path(row[column])
                    if next_value != row[column]:
                        updates[column] = next_value
                if updates:
                    set_clause = ", ".join(f"{column} = ?" for column in updates)
                    conn.execute(
                        f"UPDATE {table_name} SET {set_clause} WHERE id = ?",
                        [*updates.values(), row["id"]],
                    )
                    updated_count += len(updates)
    return updated_count


def _migrate_roles():
    """Migrate old role names (researcher -> user, remove researcher_pending/disabled)."""
    with get_db() as conn:
        cur = conn.execute("SELECT name FROM roles WHERE name = 'researcher'")
        if cur.fetchone():
            conn.execute(
                "UPDATE roles SET name = 'user', description = 'Standard platform access' WHERE name = 'researcher'"
            )
            conn.execute("DELETE FROM roles WHERE name IN ('researcher_pending', 'disabled')")
            conn.execute("UPDATE users SET role_id = 2 WHERE role_id IN (3, 4)")
            conn.execute("UPDATE permissions SET role_id = 2 WHERE role_id IN (3, 4)")


def seed_data():
    _migrate_roles()
    with get_db() as conn:
        # Seed roles if empty
        cursor = conn.execute("SELECT COUNT(*) FROM roles")
        if cursor.fetchone()[0] == 0:
            roles = [
                ('admin', 'Full platform access'),
                ('user', 'Standard platform access'),
            ]
            conn.executemany(
                "INSERT INTO roles (name, description) VALUES (?, ?)", roles
            )

        # Seed users if empty
        cursor = conn.execute("SELECT COUNT(*) FROM users")
        if cursor.fetchone()[0] == 0:
            from auth import hash_password
            if not config.BOOTSTRAP_ADMIN_PASSWORD:
                raise RuntimeError(
                    "SMARTFLOW_BOOTSTRAP_ADMIN_PASSWORD is required to seed the initial administrator account."
                )

            seed_users = [
                (
                    'System Administrator',
                    'admin',
                    'admin@smartflow.local',
                    hash_password(config.BOOTSTRAP_ADMIN_PASSWORD),
                    1,
                    'active',
                    1,
                ),
            ]

            if config.BOOTSTRAP_SECONDARY_ADMIN_PASSWORD:
                seed_users.append(
                    (
                        'Lab Manager',
                        'admin2',
                        'admin2@smartflow.local',
                        hash_password(config.BOOTSTRAP_SECONDARY_ADMIN_PASSWORD),
                        1,
                        'active',
                        1,
                    )
                )

            if config.BOOTSTRAP_STANDARD_USER_PASSWORD:
                seed_users.append(
                    (
                        'Juan dela Cruz',
                        'user',
                        'user@smartflow.local',
                        hash_password(config.BOOTSTRAP_STANDARD_USER_PASSWORD),
                        2,
                        'active',
                        1,
                    )
                )

            conn.executemany(
                """INSERT INTO users (full_name, username, email, password_hash,
                   role_id, status, must_change_password)
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                seed_users
            )

        # Seed system settings if empty
        cursor = conn.execute("SELECT COUNT(*) FROM system_settings")
        if cursor.fetchone()[0] == 0:
            settings = [
                ('registration_mode', config.REGISTRATION_MODE),
                ('session_timeout', str(config.SESSION_TIMEOUT)),
                ('min_password_length', str(config.MIN_PASSWORD_LENGTH)),
                ('app_name', config.APP_NAME),
                ('app_version', config.APP_VERSION),
                ('maintenance_mode', '0'),
                ('logging_level', 'INFO'),
            ]
            conn.executemany(
                "INSERT INTO system_settings (key, value) VALUES (?, ?)",
                settings
            )

        from simulation.road_network import NETWORK_ID, load_network

        active_network = load_network()
        network_label = "Tagum" if active_network.id == NETWORK_ID else active_network.payload.get("name", active_network.id)
        network_description = (
            "Five connected OSM junctions; one car; synthetic study signals."
            if active_network.id == NETWORK_ID else "Configured network; one car; synthetic study signals."
        )
        official_scenarios = [
            (f"{network_label} — Single Car Demo", network_description,
             'Single', 'None', 'Disabled', 'None', active_network.id,
             '{}', '{}', '{}', '{}', None, 1, 0),
            (f"{network_label} — Network Traffic", 'Synthetic traffic for engine experiments; not measured counts.',
             'Medium', 'Low', 'Disabled', 'None', active_network.id,
             '{}', '{}', '{}', '{}', None, 1, 0),
        ]

        # Seed scenarios if empty
        cursor = conn.execute("SELECT COUNT(*) FROM scenarios")
        if cursor.fetchone()[0] == 0:
            conn.executemany(
                """INSERT INTO scenarios (name, description, traffic_density,
                   pedestrian_density, emergency_mode, road_constraint, intersection_id,
                   lane_closure_config, construction_config, accident_config,
                   flooding_config, created_by, is_official, is_archived)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                official_scenarios
            )

            conn.execute(
                """INSERT INTO audit_logs (user_id, action, target, details)
                   VALUES (?, ?, ?, ?)""",
                (None, 'system', 'database', 'Database initialized with seed data')
            )

        for scenario_row in official_scenarios:
            conn.execute(
                """INSERT INTO scenarios (name, description, traffic_density,
                   pedestrian_density, emergency_mode, road_constraint, intersection_id,
                   lane_closure_config, construction_config, accident_config,
                   flooding_config, created_by, is_official, is_archived)
                   SELECT ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?
                   WHERE NOT EXISTS (
                       SELECT 1 FROM scenarios WHERE name = ? AND intersection_id = ?
                   )""",
                (*scenario_row, scenario_row[0], scenario_row[6]),
            )

        # Seed permissions if empty
        cursor = conn.execute("SELECT COUNT(*) FROM permissions")
        if cursor.fetchone()[0] == 0:
            permissions = [
                # user permissions
                (2, 'dashboard', 'view'),
                (2, 'simulation', 'view'),
                (2, 'simulation', 'run'),
                (2, 'scenarios', 'view'),
                (2, 'scenarios', 'create'),
                (2, 'scenarios', 'edit'),
                (2, 'scenarios', 'delete'),
                (2, 'live-traffic', 'view'),
                (2, 'performance', 'view'),
                (2, 'ai-agent', 'view'),
                (2, 'rl-training', 'view'),
                (2, 'rl-training', 'run'),
                (2, 'runs-reports', 'view'),
                (2, 'runs-reports', 'export'),
                (2, 'compare', 'view'),
                (2, 'profile', 'view'),
                (2, 'help', 'view'),
            ]
            conn.executemany(
                "INSERT INTO permissions (role_id, page, action) VALUES (?, ?, ?)",
                permissions
            )
            
        # Idempotent inserts for new user page permissions
        conn.execute(
            """INSERT INTO permissions (role_id, page, action)
               SELECT 2, 'profile', 'view'
               WHERE NOT EXISTS (
                   SELECT 1 FROM permissions WHERE role_id = 2 AND page = 'profile' AND action = 'view'
               )"""
        )
        conn.execute(
            """INSERT INTO permissions (role_id, page, action)
               SELECT 2, 'help', 'view'
               WHERE NOT EXISTS (
                   SELECT 1 FROM permissions WHERE role_id = 2 AND page = 'help' AND action = 'view'
               )"""
        )
        conn.execute(
            """INSERT INTO permissions (role_id, page, action)
               SELECT 2, 'compare', 'view'
               WHERE NOT EXISTS (
                   SELECT 1 FROM permissions WHERE role_id = 2 AND page = 'compare' AND action = 'view'
               )"""
        )
        conn.execute(
            """INSERT INTO permissions (role_id, page, action)
               SELECT 2, 'rl-training', 'view'
               WHERE NOT EXISTS (
                   SELECT 1 FROM permissions WHERE role_id = 2 AND page = 'rl-training' AND action = 'view'
               )"""
        )


# ─── New Helpers (Permissions, Sessions, Email) ────────────────────

def get_user_by_email(email):
    if not email:
        return None
    with get_db() as conn:
        cursor = conn.execute(
            """SELECT u.*, r.name as role_name FROM users u
               JOIN roles r ON u.role_id = r.id
               WHERE u.email = ?""",
            (email,)
        )
        row = cursor.fetchone()
        return dict(row) if row else None


def list_roles():
    with get_db() as conn:
        cursor = conn.execute(
            "SELECT id, name, description FROM roles ORDER BY id"
        )
        return [dict(row) for row in cursor.fetchall()]


def get_permissions_for_role(role_id):
    with get_db() as conn:
        cursor = conn.execute(
            "SELECT page, action FROM permissions WHERE role_id = ?",
            (role_id,)
        )
        return [dict(row) for row in cursor.fetchall()]


def check_user_permission(user_id, page, action):
    with get_db() as conn:
        cursor = conn.execute(
            """SELECT COUNT(*) FROM users u
               JOIN permissions p ON u.role_id = p.role_id
               WHERE u.id = ? AND u.status = 'active' AND p.page = ? AND p.action = ?""",
            (user_id, page, action)
        )
        return cursor.fetchone()[0] > 0


def create_user_session(user_id, token, expires_at):
    with get_db() as conn:
        conn.execute(
            """INSERT INTO user_sessions (user_id, token, expires_at)
               VALUES (?, ?, ?)""",
            (user_id, token, expires_at)
        )


def get_session_by_token(token):
    with get_db() as conn:
        cursor = conn.execute(
            "SELECT * FROM user_sessions WHERE token = ?",
            (token,)
        )
        row = cursor.fetchone()
        return dict(row) if row else None


def delete_session_by_token(token):
    with get_db() as conn:
        conn.execute("DELETE FROM user_sessions WHERE token = ?", (token,))


def delete_sessions_for_user(user_id):
    with get_db() as conn:
        conn.execute("DELETE FROM user_sessions WHERE user_id = ?", (user_id,))


def delete_all_sessions():
    with get_db() as conn:
        conn.execute("DELETE FROM user_sessions")


def update_session_expiry(token, expires_at):
    with get_db() as conn:
        conn.execute(
            "UPDATE user_sessions SET expires_at = ? WHERE token = ?",
            (expires_at, token)
        )


def delete_expired_sessions():
    with get_db() as conn:
        conn.execute(
            "DELETE FROM user_sessions WHERE datetime('now') > datetime(expires_at)"
        )


# ─── User CRUD ─────────────────────────────────────────────────────

def create_user(full_name, username, email, password_hash, role_id=2,
                status='active', must_change_password=0):
    with get_db() as conn:
        cursor = conn.execute(
            """INSERT INTO users (full_name, username, email, password_hash,
               role_id, status, must_change_password)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (full_name, username, email, password_hash, role_id, status,
             must_change_password)
        )
        return cursor.lastrowid


def get_user_by_username(username):
    with get_db() as conn:
        cursor = conn.execute(
            """SELECT u.*, r.name as role_name FROM users u
               JOIN roles r ON u.role_id = r.id
               WHERE u.username = ?""",
            (username,)
        )
        row = cursor.fetchone()
        return dict(row) if row else None


def get_user_by_id(user_id):
    with get_db() as conn:
        cursor = conn.execute(
            """SELECT u.*, r.name as role_name FROM users u
               JOIN roles r ON u.role_id = r.id
               WHERE u.id = ?""",
            (user_id,)
        )
        row = cursor.fetchone()
        return dict(row) if row else None


def update_user(user_id, invalidate_sessions=True, **kwargs):
    if not kwargs:
        return
    kwargs['updated_at'] = datetime.now().isoformat()
    set_clause = ', '.join(f"{k} = ?" for k in kwargs)
    values = list(kwargs.values()) + [user_id]
    with get_db() as conn:
        conn.execute(
            f"UPDATE users SET {set_clause} WHERE id = ?", values
        )

    sensitive_fields = {'role_id', 'status', 'password_hash', 'must_change_password'}
    if invalidate_sessions and sensitive_fields.intersection(kwargs):
        delete_sessions_for_user(user_id)


def update_last_login(user_id):
    with get_db() as conn:
        conn.execute(
            "UPDATE users SET last_login_at = ? WHERE id = ?",
            (datetime.now().isoformat(), user_id)
        )


def list_users(role_id=None, status=None):
    with get_db() as conn:
        query = """SELECT u.*, r.name as role_name FROM users u
                   JOIN roles r ON u.role_id = r.id WHERE 1=1"""
        params = []
        if role_id is not None:
            query += " AND u.role_id = ?"
            params.append(role_id)
        if status is not None:
            query += " AND u.status = ?"
            params.append(status)
        query += " ORDER BY u.created_at DESC"
        cursor = conn.execute(query, params)
        return [dict(row) for row in cursor.fetchall()]


def delete_user(user_id):
    delete_sessions_for_user(user_id)
    with get_db() as conn:
        conn.execute("DELETE FROM users WHERE id = ?", (user_id,))


def count_active_admins():
    with get_db() as conn:
        cursor = conn.execute(
            """SELECT COUNT(*) FROM users u
               JOIN roles r ON u.role_id = r.id
               WHERE r.name = 'admin' AND u.status = 'active'"""
        )
        return cursor.fetchone()[0]


# ─── Scenario CRUD ─────────────────────────────────────────────────

def create_scenario(name, intersection_id='tagum_1', description='', traffic_density='Medium',
                    pedestrian_density='Medium', emergency_mode='Disabled',
                    road_constraint='None',
                    lane_closure_config='{}',
                    construction_config='{}', accident_config='{}',
                    flooding_config='{}', created_by=None,
                    is_official=0, is_archived=0, engine_config='{}'):
    for field_name, cfg in (
        ("engine_config", engine_config),
        ("lane_closure_config", lane_closure_config),
        ("construction_config", construction_config),
        ("accident_config", accident_config),
        ("flooding_config", flooding_config),
    ):
        _validate_json_object(field_name, cfg)

    with get_db() as conn:
        cursor = conn.execute(
            """INSERT INTO scenarios (name, description, traffic_density,
               pedestrian_density, emergency_mode, road_constraint, intersection_id,
               lane_closure_config, construction_config, accident_config,
               flooding_config, created_by, is_official, is_archived, engine_config)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (name, description, traffic_density, pedestrian_density,
             emergency_mode, road_constraint, intersection_id, lane_closure_config,
             construction_config, accident_config, flooding_config,
             created_by, is_official, is_archived, engine_config)
        )
        return cursor.lastrowid


def get_scenarios(include_archived=False, official_only=False):
    with get_db() as conn:
        query = "SELECT * FROM scenarios WHERE 1=1"
        params = []
        if not include_archived:
            query += " AND is_archived = 0"
        if official_only:
            query += " AND is_official = 1"
        query += " ORDER BY name"
        cursor = conn.execute(query, params)
        return [dict(row) for row in cursor.fetchall()]


def get_scenario_by_id(scenario_id):
    with get_db() as conn:
        cursor = conn.execute(
            "SELECT * FROM scenarios WHERE id = ?", (scenario_id,)
        )
        row = cursor.fetchone()
        return dict(row) if row else None


def update_scenario(scenario_id, **kwargs):
    if not kwargs:
        return
    for field in SCENARIO_JSON_FIELDS:
        if field in kwargs:
            _validate_json_object(field, kwargs[field])

    kwargs['updated_at'] = datetime.now().isoformat()
    set_clause = ', '.join(f"{k} = ?" for k in kwargs)
    values = list(kwargs.values()) + [scenario_id]
    with get_db() as conn:
        conn.execute(
            f"UPDATE scenarios SET {set_clause} WHERE id = ?", values
        )


def delete_scenario(scenario_id):
    timeline_paths = []
    with get_db() as conn:
        cursor = conn.execute(
            "SELECT timeline_path FROM simulation_runs WHERE scenario_id = ?",
            (scenario_id,),
        )
        timeline_paths = [row["timeline_path"] for row in cursor.fetchall() if row["timeline_path"]]
        conn.execute("DELETE FROM simulation_runs WHERE scenario_id = ?", (scenario_id,))
        conn.execute("DELETE FROM scenarios WHERE id = ?", (scenario_id,))
    for timeline_path in timeline_paths:
        _delete_timeline_artifacts(timeline_path)


# ─── Simulation Runs CRUD ──────────────────────────────────────────
def create_run(scenario_id, user_id, control_mode='fixed-time',
               rl_model_id=None, status='running', seed=None, notes=None,
               duration_seconds=0, start_time=None, end_time=None,
               run_mode='live', timeline_path=None):
    with get_db() as conn:
        normalized_start_time = start_time or datetime.now().isoformat()
        normalized_duration = float(duration_seconds or 0)
        cursor = conn.execute(
            """INSERT INTO simulation_runs (scenario_id, user_id, run_mode, control_mode,
               rl_model_id, status, start_time, end_time, duration_seconds, seed, notes, timeline_path)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                scenario_id,
                user_id,
                run_mode,
                control_mode,
                rl_model_id,
                status,
                normalized_start_time,
                end_time,
                normalized_duration,
                seed,
                notes,
                timeline_path,
            )
        )
        return cursor.lastrowid


def get_runs(scenario_id=None, user_id=None, control_mode=None,
             status=None, limit=100):
    with get_db() as conn:
        query = """SELECT r.*, s.name as scenario_name,
                   u.username as user_name
                   FROM simulation_runs r
                   LEFT JOIN scenarios s ON r.scenario_id = s.id
                   LEFT JOIN users u ON r.user_id = u.id
                   WHERE 1=1"""
        params = []
        if scenario_id is not None:
            query += " AND r.scenario_id = ?"
            params.append(scenario_id)
        if user_id is not None:
            query += " AND r.user_id = ?"
            params.append(user_id)
        if control_mode is not None:
            query += " AND r.control_mode = ?"
            params.append(control_mode)
        if status is not None:
            query += " AND r.status = ?"
            params.append(status)
        query += " ORDER BY r.created_at DESC LIMIT ?"
        params.append(limit)
        cursor = conn.execute(query, params)
        return [dict(row) for row in cursor.fetchall()]


def get_run_by_id(run_id):
    with get_db() as conn:
        cursor = conn.execute(
            """SELECT r.*, s.name as scenario_name,
               u.username as user_name
               FROM simulation_runs r
               LEFT JOIN scenarios s ON r.scenario_id = s.id
               LEFT JOIN users u ON r.user_id = u.id
               WHERE r.id = ?""",
            (run_id,)
        )
        row = cursor.fetchone()
        return dict(row) if row else None


def reconcile_incomplete_runs() -> int:
    """Mark orphaned in-progress runs as stopped after an app restart."""
    reconciled_count = 0
    recovery_note = "Recovered after SMARTFLOW restarted before the run finalized."
    recovered_at = datetime.now(UTC).isoformat()
    with get_db() as conn:
        cursor = conn.execute(
            """SELECT id, notes FROM simulation_runs
               WHERE status = 'running' AND end_time IS NULL"""
        )
        stale_runs = cursor.fetchall()
        for row in stale_runs:
            existing_notes = (row["notes"] or "").strip()
            merged_notes = (
                f"{existing_notes} | {recovery_note}"
                if existing_notes
                else recovery_note
            )
            conn.execute(
                """UPDATE simulation_runs
                   SET status = ?, end_time = ?, notes = ?
                   WHERE id = ?""",
                ("stopped", recovered_at, merged_notes, row["id"]),
            )
            reconciled_count += 1
    return reconciled_count


def update_run(run_id, **kwargs):
    if not kwargs:
        return
    set_clause = ', '.join(f"{k} = ?" for k in kwargs)
    values = list(kwargs.values()) + [run_id]
    with get_db() as conn:
        conn.execute(
            f"UPDATE simulation_runs SET {set_clause} WHERE id = ?", values
        )


# â”€â”€â”€ RL Model CRUD â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
def create_rl_model(
    *,
    name,
    algorithm='ql',
    version='1.0',
    checkpoint_path=None,
    intersection_support=None,
    training_scenarios=None,
    observation_version='obs_v1',
    reward_version='reward_v1',
    action_space_version='action_v1',
    seed_set=None,
    training_date=None,
    best_evaluation_score=None,
):
    with get_db() as conn:
        cursor = conn.execute(
            """INSERT INTO rl_models (
               name, algorithm, version, checkpoint_path,
               intersection_support_json, training_scenarios_json,
               observation_version, reward_version, action_space_version,
               seed_set_json, training_date, best_evaluation_score
               )
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                name,
                algorithm,
                version,
                checkpoint_path,
                json.dumps(intersection_support or []),
                json.dumps(training_scenarios or []),
                observation_version,
                reward_version,
                action_space_version,
                json.dumps(seed_set or []),
                training_date or datetime.now(UTC).isoformat(),
                best_evaluation_score,
            ),
        )
        return cursor.lastrowid


def create_rl_checkpoint(
    *,
    model_id,
    episode=0,
    reward=0,
    loss=0,
    epsilon=1.0,
    path=None,
):
    with get_db() as conn:
        cursor = conn.execute(
            """INSERT INTO rl_checkpoints (
               model_id, episode, reward, loss, epsilon, path
               )
               VALUES (?, ?, ?, ?, ?, ?)""",
            (model_id, episode, reward, loss, epsilon, path),
        )
        return cursor.lastrowid


def list_rl_checkpoints(model_id):
    with get_db() as conn:
        return [dict(row) for row in conn.execute(
            "SELECT * FROM rl_checkpoints WHERE model_id = ? ORDER BY id DESC", (model_id,)
        ).fetchall()]


def get_rl_checkpoint_by_id(checkpoint_id):
    with get_db() as conn:
        row = conn.execute("SELECT * FROM rl_checkpoints WHERE id = ?", (checkpoint_id,)).fetchone()
        return dict(row) if row else None


def get_rl_model_by_id(model_id):
    with get_db() as conn:
        cursor = conn.execute("SELECT * FROM rl_models WHERE id = ?", (model_id,))
        row = cursor.fetchone()
        return dict(row) if row else None


def update_rl_model_evaluation_score(model_id, best_evaluation_score):
    with get_db() as conn:
        conn.execute(
            "UPDATE rl_models SET best_evaluation_score = ? WHERE id = ?",
            (best_evaluation_score, model_id),
        )


def list_rl_models(limit=200, algorithm=None):
    with get_db() as conn:
        query = "SELECT * FROM rl_models WHERE 1=1"
        params = []
        if algorithm:
            query += " AND algorithm = ?"
            params.append(str(algorithm).lower())
        query += " ORDER BY datetime(COALESCE(training_date, created_at)) DESC, id DESC LIMIT ?"
        params.append(int(limit))
        cursor = conn.execute(query, params)
        return [dict(row) for row in cursor.fetchall()]


def create_rl_training_job(*, user_id=None, selected_algorithms=None, settings=None, log_path=None):
    with get_db() as conn:
        cursor = conn.execute(
            """INSERT INTO rl_training_jobs (
               user_id, status, selected_algorithms_json, settings_json, log_path, message
               )
               VALUES (?, ?, ?, ?, ?, ?)""",
            (
                user_id,
                "queued",
                json.dumps(selected_algorithms or []),
                json.dumps(settings or {}),
                log_path,
                "Queued",
            ),
        )
        return cursor.lastrowid


def create_rl_training_job_item(*, job_id, algorithm, sequence_index, command=None):
    with get_db() as conn:
        cursor = conn.execute(
            """INSERT INTO rl_training_job_items (
               job_id, algorithm, sequence_index, status, command_json, message
               )
               VALUES (?, ?, ?, ?, ?, ?)""",
            (
                job_id,
                str(algorithm).lower(),
                int(sequence_index),
                "queued",
                json.dumps(command or []),
                "Queued",
            ),
        )
        return cursor.lastrowid


def create_rl_training_job_with_items(*, user_id=None, algorithms, settings, log_path, commands):
    """Persist a queued job and every item in one transaction."""
    if len(algorithms) != len(commands) or not algorithms:
        raise ValueError("Each training algorithm needs exactly one command")
    with get_db() as conn:
        cursor = conn.execute(
            """INSERT INTO rl_training_jobs
               (user_id, status, selected_algorithms_json, settings_json, log_path, message)
               VALUES (?, 'queued', ?, ?, ?, 'Queued')""",
            (user_id, json.dumps(algorithms), json.dumps(settings), log_path),
        )
        job_id = int(cursor.lastrowid)
        for index, (algorithm, command) in enumerate(zip(algorithms, commands)):
            conn.execute(
                """INSERT INTO rl_training_job_items
                   (job_id, algorithm, sequence_index, status, command_json, message)
                   VALUES (?, ?, ?, 'queued', ?, 'Queued')""",
                (job_id, algorithm, index, json.dumps(command)),
            )
        return job_id


def update_rl_training_job(job_id, **kwargs):
    if not kwargs:
        return
    set_clause = ", ".join(f"{key} = ?" for key in kwargs)
    values = list(kwargs.values()) + [job_id]
    with get_db() as conn:
        conn.execute(f"UPDATE rl_training_jobs SET {set_clause} WHERE id = ?", values)


def update_rl_training_job_item(item_id, **kwargs):
    if not kwargs:
        return
    set_clause = ", ".join(f"{key} = ?" for key in kwargs)
    values = list(kwargs.values()) + [item_id]
    with get_db() as conn:
        conn.execute(f"UPDATE rl_training_job_items SET {set_clause} WHERE id = ?", values)


def get_rl_training_job(job_id):
    with get_db() as conn:
        cursor = conn.execute("SELECT * FROM rl_training_jobs WHERE id = ?", (job_id,))
        row = cursor.fetchone()
        return dict(row) if row else None


def get_rl_training_job_items(job_id):
    with get_db() as conn:
        cursor = conn.execute(
            """SELECT * FROM rl_training_job_items
               WHERE job_id = ?
               ORDER BY sequence_index ASC, id ASC""",
            (job_id,),
        )
        return [dict(row) for row in cursor.fetchall()]


def get_latest_rl_training_job():
    with get_db() as conn:
        cursor = conn.execute(
            """SELECT * FROM rl_training_jobs
               ORDER BY datetime(created_at) DESC, id DESC
               LIMIT 1"""
        )
        row = cursor.fetchone()
        return dict(row) if row else None


def list_rl_training_jobs(limit=50):
    with get_db() as conn:
        cursor = conn.execute(
            """SELECT * FROM rl_training_jobs
               ORDER BY datetime(created_at) DESC, id DESC
               LIMIT ?""",
            (int(limit),),
        )
        return [dict(row) for row in cursor.fetchall()]


def reconcile_incomplete_rl_training_jobs() -> int:
    recovered_at = datetime.now(UTC).isoformat()
    with get_db() as conn:
        cursor = conn.execute(
            """SELECT id FROM rl_training_jobs
               WHERE status IN ('queued', 'running', 'stopping')"""
        )
        rows = cursor.fetchall()
        for row in rows:
            conn.execute(
                """UPDATE rl_training_jobs
                   SET status = ?, ended_at = ?, message = ?
                   WHERE id = ?""",
                ("interrupted", recovered_at, "Recovered after SMARTFLOW restarted.", row["id"]),
            )
            conn.execute(
                """UPDATE rl_training_job_items
                   SET status = ?, ended_at = ?, message = ?
                   WHERE job_id = ? AND status IN ('queued', 'running', 'stopping')""",
                ("interrupted", recovered_at, "Recovered after SMARTFLOW restarted.", row["id"]),
            )
        return len(rows)


def save_run_metrics(run_id, avg_waiting_time=0, avg_queue_length=0,
                     max_queue_length=0, throughput=0,
                     avg_pedestrian_delay=0, emergency_clearance_time=0,
                     signal_phase_efficiency=0, congestion_severity='low',
                     raw_metrics_json='{}'):
    with get_db() as conn:
        cursor = conn.execute(
            """INSERT INTO run_metrics (run_id, avg_waiting_time,
               avg_queue_length, max_queue_length, throughput,
               avg_pedestrian_delay, emergency_clearance_time,
               signal_phase_efficiency, congestion_severity,
               raw_metrics_json)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (run_id, avg_waiting_time, avg_queue_length, max_queue_length,
             throughput, avg_pedestrian_delay, emergency_clearance_time,
             signal_phase_efficiency, congestion_severity, raw_metrics_json)
        )
        return cursor.lastrowid


def get_run_metrics(run_id):
    with get_db() as conn:
        cursor = conn.execute(
            """SELECT * FROM run_metrics WHERE run_id = ?
               ORDER BY recorded_at DESC LIMIT 1""",
            (run_id,)
        )
        row = cursor.fetchone()
        return dict(row) if row else None


# ─── Audit Logs ────────────────────────────────────────────────────

def log_audit_event(user_id=None, action='', target='', details=''):
    ip_address = None
    user_agent = None
    try:
        from flask import has_request_context, request

        if has_request_context():
            forwarded_for = (request.headers.get('X-Forwarded-For') or '').strip()
            ip_address = forwarded_for.split(',')[0].strip() if forwarded_for else (request.remote_addr or '').strip()
            user_agent = (request.headers.get('User-Agent') or '').strip() or None
    except Exception:
        ip_address = None
        user_agent = None

    with get_db() as conn:
        conn.execute(
            """INSERT INTO audit_logs (user_id, action, target, details, ip_address, user_agent)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (user_id, action, target, details, ip_address, user_agent)
        )


def get_audit_logs(user_id=None, action=None, limit=200):
    with get_db() as conn:
        query = """SELECT a.*, u.username FROM audit_logs a
                   LEFT JOIN users u ON a.user_id = u.id WHERE 1=1"""
        params = []
        if user_id is not None:
            query += " AND a.user_id = ?"
            params.append(user_id)
        if action is not None:
            query += " AND a.action = ?"
            params.append(action)
        query += " ORDER BY a.timestamp DESC LIMIT ?"
        params.append(limit)
        cursor = conn.execute(query, params)
        return [dict(row) for row in cursor.fetchall()]


# ─── System Settings ───────────────────────────────────────────────

def get_setting(key, default=None):
    with get_db() as conn:
        cursor = conn.execute(
            "SELECT value FROM system_settings WHERE key = ?", (key,)
        )
        row = cursor.fetchone()
        return row['value'] if row else default


def set_setting(key, value):
    with get_db() as conn:
        conn.execute(
            """INSERT INTO system_settings (key, value, updated_at)
               VALUES (?, ?, datetime('now'))
               ON CONFLICT(key) DO UPDATE SET
               value = excluded.value, updated_at = datetime('now')""",
            (key, value)
        )


# ─── Notifications ─────────────────────────────────────────────────

def get_auth_session_version() -> str:
    version = get_setting(AUTH_SESSION_VERSION_SETTING)
    if version:
        return str(version)

    version = secrets.token_hex(16)
    set_setting(AUTH_SESSION_VERSION_SETTING, version)
    return version


def rotate_auth_session_version() -> str:
    version = secrets.token_hex(16)
    set_setting(AUTH_SESSION_VERSION_SETTING, version)
    return version


def is_maintenance_mode() -> bool:
    return str(get_setting('maintenance_mode', '0')).strip() == '1'


def set_maintenance_mode(enabled: bool):
    set_setting('maintenance_mode', '1' if enabled else '0')


def get_notifications(user_id, unread_only=False, limit=50):
    with get_db() as conn:
        query = "SELECT * FROM notifications WHERE user_id = ?"
        params = [user_id]
        if unread_only:
            query += " AND read = 0"
        query += " ORDER BY created_at DESC LIMIT ?"
        params.append(limit)
        cursor = conn.execute(query, params)
        return [dict(row) for row in cursor.fetchall()]


def create_notification(user_id, message, notif_type='info'):
    with get_db() as conn:
        conn.execute(
            """INSERT INTO notifications (user_id, message, type)
               VALUES (?, ?, ?)""",
            (user_id, message, notif_type)
        )


def mark_notification_read(notif_id):
    with get_db() as conn:
        conn.execute(
            "UPDATE notifications SET read = 1 WHERE id = ?", (notif_id,)
        )


# ─── Roles ─────────────────────────────────────────────────────────

def get_roles():
    with get_db() as conn:
        cursor = conn.execute("SELECT * FROM roles ORDER BY id")
        return [dict(row) for row in cursor.fetchall()]


def get_role_by_name(name):
    with get_db() as conn:
        cursor = conn.execute(
            "SELECT * FROM roles WHERE name = ?", (name,)
        )
        row = cursor.fetchone()
        return dict(row) if row else None


# ─── Constraints CRUD ──────────────────────────────────────────────

def get_scenario_constraints(scenario_id):
    with get_db() as conn:
        cursor = conn.execute(
            "SELECT * FROM scenario_constraints WHERE scenario_id = ?",
            (scenario_id,)
        )
        return [dict(row) for row in cursor.fetchall()]


def save_scenario_constraint(scenario_id, constraint_type, config_json):
    _validate_json_object(f"constraint '{constraint_type}'", config_json)

    with get_db() as conn:
        conn.execute(
            """INSERT INTO scenario_constraints (scenario_id, constraint_type, config_json)
               VALUES (?, ?, ?)""",
            (scenario_id, constraint_type, config_json)
        )


def delete_scenario_constraints(scenario_id):
    with get_db() as conn:
        conn.execute(
            "DELETE FROM scenario_constraints WHERE scenario_id = ?",
            (scenario_id,)
        )


def _delete_timeline_artifacts(timeline_path):
    path = Path(timeline_path)
    candidates = {path}

    if path.suffix == ".gz" and path.name.endswith(".jsonl.gz"):
        raw_path = path.with_suffix("")
        candidates.add(raw_path)
        candidates.add(raw_path.with_suffix(".manifest.json"))
    elif path.suffix == ".jsonl":
        candidates.add(path.with_suffix(".jsonl.gz"))
        candidates.add(path.with_suffix(".manifest.json"))
    elif path.name.endswith(".manifest.json"):
        raw_path = path.with_suffix("").with_suffix(".jsonl")
        candidates.add(raw_path)
        candidates.add(raw_path.with_suffix(".jsonl.gz"))

    for candidate in candidates:
        try:
            candidate.unlink(missing_ok=True)
        except OSError:
            pass


def delete_run(run_id):
    timeline_path = None
    with get_db() as conn:
        cursor = conn.execute(
            "SELECT timeline_path FROM simulation_runs WHERE id = ?",
            (run_id,),
        )
        row = cursor.fetchone()
        if row:
            timeline_path = row["timeline_path"]
        conn.execute("DELETE FROM simulation_runs WHERE id = ?", (run_id,))
    if timeline_path:
        _delete_timeline_artifacts(timeline_path)


def count_user_runs(user_id):
    """Return total simulation runs created by a user."""
    with get_db() as conn:
        cursor = conn.execute(
            "SELECT COUNT(*) FROM simulation_runs WHERE user_id = ?",
            (user_id,)
        )
        return cursor.fetchone()[0]


def get_user_activity_summary(user_id):
    """Return quick stats about a user's activity."""
    with get_db() as conn:
        run_count = conn.execute(
            "SELECT COUNT(*) FROM simulation_runs WHERE user_id = ?", (user_id,)
        ).fetchone()[0]
        audit_count = conn.execute(
            "SELECT COUNT(*) FROM audit_logs WHERE user_id = ?", (user_id,)
        ).fetchone()[0]
        return {
            'run_count': run_count,
            'audit_count': audit_count,
        }


# ─── Dynamic Permissions CRUD ──────────────────────────────────────

def update_role_permission(role_id, page, action, enabled):
    with get_db() as conn:
        if enabled:
            cursor = conn.execute(
                "SELECT COUNT(*) FROM permissions WHERE role_id = ? AND page = ? AND action = ?",
                (role_id, page, action)
            )
            if cursor.fetchone()[0] == 0:
                conn.execute(
                    "INSERT INTO permissions (role_id, page, action) VALUES (?, ?, ?)",
                    (role_id, page, action)
                )
        else:
            conn.execute(
                "DELETE FROM permissions WHERE role_id = ? AND page = ? AND action = ?",
                (role_id, page, action)
            )


# ─── Backup & Restore CRUD ─────────────────────────────────────────

def list_backups():
    with get_db() as conn:
        cursor = conn.execute(
            """SELECT b.*, u.username FROM backups b
               LEFT JOIN users u ON b.created_by = u.id
               ORDER BY b.created_at DESC"""
        )
        return [dict(row) for row in cursor.fetchall()]


def _backups_directory() -> Path:
    directory = Path(config.DB_PATH).resolve().parent / 'backups'
    directory.mkdir(parents=True, exist_ok=True)
    return directory


def _resolve_backup_path(filename: str) -> Path:
    normalized_name = os.path.basename(str(filename or '').strip())
    if normalized_name != filename:
        raise ValueError('Invalid backup filename')
    if not normalized_name.startswith('smartflow_backup_') or not normalized_name.endswith(('.db', '.zip')):
        raise ValueError('Unsupported backup filename')

    backups_dir = _backups_directory()
    candidate = (backups_dir / normalized_name).resolve()
    if backups_dir not in candidate.parents or candidate.parent != backups_dir:
        raise ValueError('Backup path escapes the backup directory')
    return candidate


def _checkpoint_wal(conn: sqlite3.Connection):
    conn.execute("PRAGMA wal_checkpoint(TRUNCATE)")


def _copy_database_snapshot(source_conn: sqlite3.Connection, destination_path: Path):
    if destination_path.exists():
        destination_path.unlink()

    destination_conn = _connect_sqlite_file(destination_path)
    try:
        source_conn.backup(destination_conn)
        destination_conn.commit()
    finally:
        destination_conn.close()


def create_backup(created_by):
    from datetime import datetime

    _backups_directory()

    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S_%f')
    filename = f"smartflow_backup_{timestamp}.db"
    dest_path = _resolve_backup_path(filename)

    source_conn = get_connection()
    try:
        _checkpoint_wal(source_conn)
        _copy_database_snapshot(source_conn, dest_path)
    finally:
        source_conn.close()

    size_bytes = dest_path.stat().st_size

    with get_db() as conn:
        conn.execute(
            """INSERT INTO backups (filename, created_by, size_bytes)
               VALUES (?, ?, ?)""",
            (filename, created_by, size_bytes)
        )
    return filename


def restore_backup(backup_id):
    with get_db() as conn:
        cursor = conn.execute("SELECT filename FROM backups WHERE id = ?", (backup_id,))
        row = cursor.fetchone()
        if not row:
            raise ValueError("Backup not found")
        filename = row['filename']
    
    src_path = _resolve_backup_path(filename)

    if not src_path.exists():
        raise FileNotFoundError(f"Backup file '{filename}' does not exist on disk.")

    set_maintenance_mode(True)
    try:
        backup_conn = _connect_sqlite_file(src_path)
        live_conn = get_connection()
        try:
            _checkpoint_wal(live_conn)
            backup_conn.backup(live_conn)
            live_conn.commit()
            _checkpoint_wal(live_conn)
        finally:
            live_conn.close()
            backup_conn.close()
        init_db()
        delete_all_sessions()
        rotate_auth_session_version()
    finally:
        set_maintenance_mode(False)

    return filename


def delete_backup_from_db(backup_id):
    with get_db() as conn:
        cursor = conn.execute("SELECT filename FROM backups WHERE id = ?", (backup_id,))
        row = cursor.fetchone()
        if not row:
            return
        filename = row['filename']
        file_path = _resolve_backup_path(filename)
        conn.execute("DELETE FROM backups WHERE id = ?", (backup_id,))

    if file_path.exists():
        file_path.unlink()


# ─── Login Attempt Tracking ──────────────────────────────────────

MAX_LOGIN_ATTEMPTS = 5
LOGIN_LOCKOUT_BASE_SECONDS = 300
LOGIN_LOCKOUT_MAX_SECONDS = 3600


def _utc_sqlite_timestamp(offset_seconds: int = 0) -> str:
    return (datetime.now(UTC) + timedelta(seconds=offset_seconds)).strftime('%Y-%m-%d %H:%M:%S')


def _lockout_window_seconds(failure_count: int) -> int:
    if failure_count < MAX_LOGIN_ATTEMPTS:
        return 0
    escalation_steps = failure_count - MAX_LOGIN_ATTEMPTS
    return min(LOGIN_LOCKOUT_MAX_SECONDS, LOGIN_LOCKOUT_BASE_SECONDS * (2 ** escalation_steps))


def prune_login_attempts(retention_days: int | None = None):
    retention_window = retention_days or config.LOGIN_ATTEMPT_RETENTION_DAYS
    cutoff = _utc_sqlite_timestamp(-(retention_window * 86400))
    with get_db() as conn:
        conn.execute(
            "DELETE FROM login_attempts WHERE datetime(timestamp) < datetime(?)",
            (cutoff,),
        )


def record_login_attempt(username: str, success: bool, ip_address: str | None = None):
    normalized_ip = (ip_address or '').strip()
    with get_db() as conn:
        cutoff = _utc_sqlite_timestamp(-(config.LOGIN_ATTEMPT_RETENTION_DAYS * 86400))
        conn.execute(
            "DELETE FROM login_attempts WHERE datetime(timestamp) < datetime(?)",
            (cutoff,),
        )
        if success:
            conn.execute(
                "DELETE FROM login_attempts WHERE username = ? AND COALESCE(ip_address, '') = ? AND success = 0",
                (username, normalized_ip),
            )
        conn.execute(
            "INSERT INTO login_attempts (username, ip_address, timestamp, success) VALUES (?, ?, ?, ?)",
            (username, normalized_ip, _utc_sqlite_timestamp(), 1 if success else 0),
        )


def is_login_blocked(username: str, ip_address: str | None = None) -> bool:
    normalized_ip = (ip_address or '').strip()
    with get_db() as conn:
        cursor = conn.execute(
            """SELECT COUNT(*) AS failure_count, MAX(timestamp) AS last_failure
               FROM login_attempts
               WHERE username = ?
                 AND COALESCE(ip_address, '') = ?
                 AND success = 0
                 AND datetime(timestamp) >= datetime(?)""",
            (username, normalized_ip, _utc_sqlite_timestamp(-LOGIN_LOCKOUT_MAX_SECONDS)),
        )
        row = cursor.fetchone()
        failures = int(row['failure_count'] or 0) if row else 0
        if failures < MAX_LOGIN_ATTEMPTS:
            return False

        last_failure = row['last_failure'] if row else None
        if not last_failure:
            return False

        lockout_window = _lockout_window_seconds(failures)
        cutoff = _utc_sqlite_timestamp(-lockout_window)
        return last_failure >= cutoff
