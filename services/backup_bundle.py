"""Coherent SQLite and artifact bundles with isolated restore rehearsals."""
from __future__ import annotations

import hashlib
import json
import os
import secrets
import shutil
import sqlite3
import tempfile
import zipfile
from contextlib import closing
from datetime import UTC, datetime
from pathlib import Path

import config
import database
from simulation import road_network


ROOT = Path(config.BASE_DIR).resolve()
PATH_COLUMNS = {
    "simulation_runs": ("timeline_path",),
    "rl_models": ("checkpoint_path",),
    "rl_checkpoints": ("path",),
    "rl_training_jobs": ("log_path",),
    "rl_training_job_items": ("artifact_path", "metadata_path", "evaluation_path"),
}
JSON_COLUMNS = {"scenarios": ("engine_config",), "rl_training_jobs": ("settings_json",)}
JSON_PATH_KEYS = {"source_path", "scenario_file", "evaluation_scenario_file", "job_directory", "resume_model"}


def _digest(path: Path) -> str:
    hasher = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            hasher.update(chunk)
    return hasher.hexdigest()


def _within(path: Path, parent: Path) -> bool:
    return path == parent or parent in path.parents


def _member(path: Path) -> str:
    resolved = path.resolve()
    if _within(resolved, ROOT):
        return "files/project/" + resolved.relative_to(ROOT).as_posix()
    storage = Path(config.DB_PATH).resolve().parent
    if _within(resolved, storage):
        return "files/storage/" + resolved.relative_to(storage).as_posix()
    if resolved == road_network.NETWORK_PATH.resolve():
        return "files/network/" + resolved.name
    raise ValueError(f"Referenced artifact is outside the project and database storage: {path}")


def _source_path(value: str) -> Path:
    candidate = Path(value)
    return (candidate if candidate.is_absolute() else ROOT / candidate).resolve()


def _json_paths(value: object) -> list[str]:
    if isinstance(value, list):
        return [path for item in value for path in _json_paths(item)]
    if not isinstance(value, dict):
        return []
    paths = [item for key, item in value.items() if key in JSON_PATH_KEYS and isinstance(item, str) and item]
    return paths + [path for item in value.values() if isinstance(item, (dict, list)) for path in _json_paths(item)]


def _referenced_paths(snapshot: Path) -> set[str]:
    references: set[str] = set()
    with closing(sqlite3.connect(snapshot)) as conn:
        conn.row_factory = sqlite3.Row
        for table, columns in PATH_COLUMNS.items():
            for row in conn.execute(f"SELECT {', '.join(columns)} FROM {table}"):
                references.update(value for value in row if isinstance(value, str) and value)
        for table, columns in JSON_COLUMNS.items():
            for row in conn.execute(f"SELECT {', '.join(columns)} FROM {table}"):
                for raw in row:
                    try:
                        references.update(_json_paths(json.loads(raw or "{}")))
                    except (TypeError, ValueError) as exc:
                        raise ValueError(f"Invalid saved {table} JSON prevents a coherent backup") from exc
    return references


def _files_for_references(references: set[str]) -> dict[str, Path]:
    files: dict[str, Path] = {}
    for value in sorted(references):
        path = _source_path(value)
        member = _member(path)
        if not path.exists():
            raise ValueError(f"Referenced artifact is missing: {value}")
        if path.is_dir():
            for child in path.rglob("*"):
                if child.is_file():
                    files[_member(child)] = child
        elif path.is_file():
            files[member] = path
            if path.name.endswith(".jsonl.gz"):
                sidecar = Path(str(path).replace(".jsonl.gz", ".manifest.json"))
                if sidecar.exists():
                    files[_member(sidecar)] = sidecar
            elif path.name.endswith(".jsonl"):
                sidecar = path.with_suffix(".manifest.json")
                if sidecar.exists():
                    files[_member(sidecar)] = sidecar
            elif path.suffix in {".zip", ".pt", ".pth"}:
                sidecar = path.with_suffix(".metadata.json")
                if sidecar.exists():
                    files[_member(sidecar)] = sidecar
    network = road_network.NETWORK_PATH.resolve()
    if not network.is_file():
        raise ValueError(f"Configured network source is missing: {network}")
    files[_member(network)] = network
    return files


def create_bundle(created_by: int) -> str:
    backup_dir = database._backups_directory()
    timestamp = datetime.now(UTC).strftime("%Y%m%d_%H%M%S_%f")
    filename = f"smartflow_backup_{timestamp}.zip"
    final_path = database._resolve_backup_path(filename)
    with tempfile.TemporaryDirectory(prefix="bundle-", dir=backup_dir) as temporary:
        snapshot = Path(temporary) / "smartflow.db"
        with closing(database.get_connection()) as source, closing(sqlite3.connect(snapshot)) as destination:
            source.backup(destination)
        references = _referenced_paths(snapshot)
        files = _files_for_references(references)
        mapping = {value: _member(_source_path(value)) for value in sorted(references)}
        archive = Path(temporary) / filename
        manifest = {"format": 1, "created_at": datetime.now(UTC).isoformat(),
                    "active_network": _member(road_network.NETWORK_PATH),
                    "references": mapping, "files": {member: {"sha256": _digest(path), "size": path.stat().st_size}
                                                         for member, path in sorted(files.items())},
                    "database_sha256": _digest(snapshot)}
        with zipfile.ZipFile(archive, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=6) as bundle:
            bundle.write(snapshot, "smartflow.db")
            for member, path in sorted(files.items()):
                bundle.write(path, member)
            bundle.writestr("manifest.json", json.dumps(manifest, indent=2))
        os.replace(archive, final_path)
    with database.get_db() as conn:
        conn.execute("INSERT INTO backups (filename, created_by, size_bytes) VALUES (?, ?, ?)",
                     (filename, created_by, final_path.stat().st_size))
    return filename


def _rewrite_json(value: object, paths: dict[str, str]) -> object:
    if isinstance(value, list):
        return [_rewrite_json(item, paths) for item in value]
    if isinstance(value, dict):
        return {key: paths.get(item, item) if key in JSON_PATH_KEYS and isinstance(item, str)
                else _rewrite_json(item, paths) for key, item in value.items()}
    return value


def _rewrite_database(snapshot: Path, paths: dict[str, str]) -> None:
    with closing(sqlite3.connect(snapshot)) as conn, conn:
        conn.row_factory = sqlite3.Row
        for table, columns in PATH_COLUMNS.items():
            for column in columns:
                for original, restored in paths.items():
                    conn.execute(f"UPDATE {table} SET {column} = ? WHERE {column} = ?", (restored, original))
        for table, columns in JSON_COLUMNS.items():
            for column in columns:
                rows = conn.execute(f"SELECT id, {column} FROM {table}").fetchall()
                for row in rows:
                    if not row[column]:
                        continue
                    parsed = json.loads(row[column])
                    rewritten = _rewrite_json(parsed, paths)
                    if rewritten != parsed:
                        conn.execute(f"UPDATE {table} SET {column} = ? WHERE id = ?",
                                     (json.dumps(rewritten), row["id"]))
        conn.execute("DELETE FROM user_sessions")
        conn.execute("INSERT OR REPLACE INTO system_settings (key, value) VALUES (?, ?)",
                     (database.AUTH_SESSION_VERSION_SETTING, secrets.token_hex(32)))
        if conn.execute("PRAGMA integrity_check").fetchone()[0] != "ok":
            raise ValueError("Restored SQLite database failed integrity check")
        if conn.execute("PRAGMA foreign_key_check").fetchone():
            raise ValueError("Restored SQLite database has invalid references")


def restore_bundle_to_stage(backup_id: int) -> Path:
    with database.get_db() as conn:
        row = conn.execute("SELECT filename FROM backups WHERE id = ?", (backup_id,)).fetchone()
    if not row:
        raise ValueError("Backup not found")
    archive = database._resolve_backup_path(row["filename"])
    if archive.suffix != ".zip":
        raise ValueError("This legacy database-only backup cannot verify models and recordings")
    if not archive.is_file():
        raise FileNotFoundError(f"Backup file is missing: {archive.name}")
    restore_root = database._backups_directory() / "restores"
    restore_root.mkdir(parents=True, exist_ok=True)
    staged = Path(tempfile.mkdtemp(prefix="restore-", dir=restore_root)).resolve()
    try:
        with zipfile.ZipFile(archive) as bundle:
            manifest = json.loads(bundle.read("manifest.json"))
            if (manifest.get("format") != 1 or not isinstance(manifest.get("files"), dict)
                    or not isinstance(manifest.get("references"), dict)):
                raise ValueError("Unsupported backup bundle manifest")
            expected_names = {"manifest.json", "smartflow.db", *manifest["files"]}
            if set(bundle.namelist()) != expected_names:
                raise ValueError("Backup bundle contains unexpected or missing entries")
            snapshot = staged / "smartflow.db"
            snapshot.write_bytes(bundle.read("smartflow.db"))
            if _digest(snapshot) != manifest.get("database_sha256"):
                raise ValueError("Backup database checksum mismatch")
            for member, info in manifest["files"].items():
                if not member.startswith("files/") or ".." in Path(member).parts:
                    raise ValueError("Unsafe backup member path")
                destination = (staged / member).resolve()
                if not _within(destination, staged):
                    raise ValueError("Backup member escapes the restore directory")
                destination.parent.mkdir(parents=True, exist_ok=True)
                destination.write_bytes(bundle.read(member))
                if destination.stat().st_size != info["size"] or _digest(destination) != info["sha256"]:
                    raise ValueError(f"Backup artifact checksum mismatch: {member}")
            paths = {}
            for original, member in manifest["references"].items():
                if not isinstance(original, str) or not isinstance(member, str) or not member.startswith("files/"):
                    raise ValueError("Invalid backup artifact reference")
                restored = (staged / member).resolve()
                if not _within(restored, staged) or not restored.exists():
                    raise ValueError(f"Referenced artifact is missing from bundle: {member}")
                paths[original] = str(restored)
            _rewrite_database(snapshot, paths)
            network_member = manifest.get("active_network", "files/project/data/networks/tagum_network.json")
            if network_member not in manifest["files"]:
                raise ValueError("Configured network is missing from the backup bundle")
            (staged / "restore_environment.json").write_text(json.dumps({
                "SMARTFLOW_DB_PATH": str(snapshot),
                "SMARTFLOW_NETWORK_PATH": str(staged / network_member),
                "note": "Start a separate SmartFlow API process with these environment variables and its own secret key."
            }, indent=2), encoding="utf-8")
        return staged
    except Exception as exc:
        if not _within(staged, restore_root.resolve()):
            raise RuntimeError("Refusing to clean up a restore directory outside backup storage")
        shutil.rmtree(staged)
        if isinstance(exc, (zipfile.BadZipFile, sqlite3.DatabaseError, KeyError, TypeError)):
            raise ValueError(f"Invalid backup bundle: {exc}") from exc
        raise


def restore_legacy_database_to_stage(backup_id: int) -> Path:
    with database.get_db() as conn:
        row = conn.execute("SELECT filename FROM backups WHERE id = ?", (backup_id,)).fetchone()
    if not row:
        raise ValueError("Backup not found")
    source = database._resolve_backup_path(row["filename"])
    if source.suffix != ".db":
        raise ValueError("This backup is not a legacy SQLite file")
    if not source.is_file():
        raise FileNotFoundError(f"Backup file is missing: {source.name}")
    restore_root = database._backups_directory() / "restores"
    restore_root.mkdir(parents=True, exist_ok=True)
    staged = Path(tempfile.mkdtemp(prefix="legacy-restore-", dir=restore_root)).resolve()
    try:
        snapshot = staged / "smartflow.db"
        shutil.copy2(source, snapshot)
        with closing(sqlite3.connect(snapshot)) as conn, conn:
            if conn.execute("PRAGMA integrity_check").fetchone()[0] != "ok":
                raise ValueError("Legacy SQLite backup failed integrity check")
            if conn.execute("PRAGMA foreign_key_check").fetchone():
                raise ValueError("Legacy SQLite backup has invalid references")
            tables = {item[0] for item in conn.execute("SELECT name FROM sqlite_master WHERE type = 'table'")}
            if "user_sessions" in tables:
                conn.execute("DELETE FROM user_sessions")
            if "system_settings" in tables:
                conn.execute("INSERT OR REPLACE INTO system_settings (key, value) VALUES (?, ?)",
                             (database.AUTH_SESSION_VERSION_SETTING, secrets.token_hex(32)))
        (staged / "restore_environment.json").write_text(json.dumps({
            "SMARTFLOW_DB_PATH": str(snapshot),
            "warning": "Legacy SQLite backups exclude models, networks, recordings and other referenced files."
        }, indent=2), encoding="utf-8")
        return staged
    except Exception as exc:
        if not _within(staged, restore_root.resolve()):
            raise RuntimeError("Refusing to clean up a restore directory outside backup storage")
        shutil.rmtree(staged)
        if isinstance(exc, sqlite3.DatabaseError):
            raise ValueError(f"Invalid legacy SQLite backup: {exc}") from exc
        raise
