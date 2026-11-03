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


def _windows_long_path(path: Path) -> str:
    """Use extended Windows paths for deep restore trees without changing saved paths."""
    value = str(path)
    if os.name != "nt" or value.startswith("\\\\?\\"):
        return value
    if value.startswith("\\\\"):
        return "\\\\?\\UNC\\" + value[2:]
    return "\\\\?\\" + value


def display_path(path: Path) -> str:
    """Plain path for people and API clients; the extended form stays internal to file operations."""
    value = str(path)
    if value.startswith("\\\\?\\UNC\\"):
        return "\\\\" + value[8:]
    return value[4:] if value.startswith("\\\\?\\") else value


def _member(path: Path) -> str:
    resolved = Path(_windows_long_path(path)).resolve()
    project = Path(_windows_long_path(ROOT)).resolve()
    if _within(resolved, project):
        return "files/project/" + resolved.relative_to(project).as_posix()
    storage = Path(_windows_long_path(Path(config.DB_PATH).resolve().parent)).resolve()
    if _within(resolved, storage):
        return "files/storage/" + resolved.relative_to(storage).as_posix()
    if resolved == Path(_windows_long_path(road_network.NETWORK_PATH)).resolve():
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
    from simulation.network_registry import REGISTRY_PATH, _entries, registered_networks
    if REGISTRY_PATH.exists():
        for entry in registered_networks()[1:]:
            site = (REGISTRY_PATH.parent / entry['file']).resolve()
            files[_member(site)] = site
        # Keep explicitly listed immutable revisions needed for rollback. Never
        # glob the directory: it can also contain unrelated research artifacts.
        for entry in _entries(REGISTRY_PATH):
            history = entry.get("revision_history", [])
            if not isinstance(history, list):
                raise ValueError("Invalid network revision history")
            for revision in history:
                if not isinstance(revision, dict) or not isinstance(revision.get("file"), str) or Path(revision["file"]).name != revision["file"] or not isinstance(revision.get("sha256"), str):
                    raise ValueError("Invalid network revision history entry")
                site = REGISTRY_PATH.parent / revision["file"]
                if site.is_symlink() or not site.is_file() or site.resolve().parent != REGISTRY_PATH.parent.resolve():
                    raise ValueError("Network revision history file is missing or unsafe")
                historical = road_network.RoadNetwork(json.loads(site.read_text(encoding="utf-8")))
                if historical.id != entry["id"] or historical.fingerprint != revision["sha256"]:
                    raise ValueError("Network revision history fingerprint mismatch")
                files[_member(site)] = site
        files[_member(REGISTRY_PATH)] = REGISTRY_PATH
    return files


def _desktop_evidence() -> tuple[dict[str, Path], dict[str, str]]:
    """Include only explicitly selected desktop study evidence and preferences."""
    raw = os.environ.get("SMARTFLOW_STUDY_ROOT")
    if not raw:
        return {}, {}
    root = Path(_windows_long_path(Path(raw).resolve()))
    candidates = [root / "config" / "preferences.json"]
    candidates.extend((root / "data" / "sites").glob("*.json"))
    candidates.extend((root / "docs" / "reports").glob("site-validation-*.json"))
    from desktop.site_validation_jobs import JOB_ID
    for path in (root / "data" / "validation-jobs").glob("*.json"):
        if path.is_symlink() or not JOB_ID.fullmatch(path.stem):
            raise ValueError("Unsafe desktop validation-job record")
        candidates.append(path)
    from services.reviewed_revision_store import REVISION_ID, SAFE_NAME, revision_path
    reviewed = root / "data" / "reviewed-revisions"
    if reviewed.exists():
        for revision in reviewed.iterdir():
            if revision.is_symlink():
                raise ValueError("Reviewed revision cannot be a symbolic link")
            if revision.is_dir() and REVISION_ID.fullmatch(revision.name):
                revision_path(root, revision.name)
                manifest = json.loads((revision / "manifest.json").read_text(encoding="utf-8"))
                if {item.name for item in revision.iterdir()} != {"manifest.json", *(manifest.get("artifact_sha256") or {})}:
                    raise ValueError("Reviewed revision files do not match its manifest")
                for item in revision.iterdir():
                    if item.is_symlink() or not item.is_file() or not SAFE_NAME.fullmatch(item.name):
                        raise ValueError("Reviewed revision contains an unsafe file")
                    candidates.append(item)
    files, logical = {}, {}
    for candidate in sorted(candidates):
        if not candidate.exists():
            continue
        resolved = candidate.resolve()
        if not _within(resolved, root) or not resolved.is_file():
            raise ValueError("Desktop evidence must be a file inside the desktop data root")
        name = candidate.relative_to(root).as_posix()
        member = "files/desktop/" + name
        files[member] = resolved
        logical[name] = member
    return files, logical


def _desktop_evidence_layout(staged: Path, manifest: dict, restored: dict[str, Path]) -> Path | None:
    entries = manifest.get("desktop_evidence")
    if entries is None:
        return None
    if not isinstance(entries, dict):
        raise ValueError("Invalid desktop evidence manifest")
    destination_root = staged / "desktop"
    from services.reviewed_revision_store import REVISION_ID, SAFE_NAME
    from desktop.site_validation_jobs import JOB_ID
    for name, member in entries.items():
        if not isinstance(name, str) or not isinstance(member, str):
            raise ValueError("Invalid desktop evidence entry")
        parts = name.split("/")
        allowed = (name == "config/preferences.json" or
                   (len(parts) == 3 and parts[:2] == ["data", "sites"] and parts[2].endswith(".json")) or
                   (len(parts) == 3 and parts[:2] == ["data", "validation-jobs"] and parts[2].endswith(".json") and JOB_ID.fullmatch(parts[2][:-5])) or
                   (len(parts) == 3 and parts[:2] == ["docs", "reports"] and parts[2].startswith("site-validation-") and parts[2].endswith(".json")) or
                   (len(parts) == 4 and parts[:2] == ["data", "reviewed-revisions"] and REVISION_ID.fullmatch(parts[2]) and SAFE_NAME.fullmatch(parts[3])))
        if not allowed or any(part in ("", ".", "..") or "\\" in part or ":" in part for part in parts):
            raise ValueError("Unsafe desktop evidence path")
        if member != "files/desktop/" + name or member not in manifest["files"]:
            raise ValueError("Desktop evidence is missing from the verified bundle")
        destination = (destination_root / name).resolve()
        if not _within(destination, destination_root.resolve()):
            raise ValueError("Desktop evidence escapes the restore directory")
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(restored[member], destination)
    return destination_root


def create_bundle(created_by: int) -> str:
    backup_dir = Path(_windows_long_path(database._backups_directory()))
    timestamp = datetime.now(UTC).strftime("%Y%m%d_%H%M%S_%f")
    filename = f"smartflow_backup_{timestamp}.zip"
    final_path = Path(_windows_long_path(database._resolve_backup_path(filename)))
    with tempfile.TemporaryDirectory(prefix="bundle-", dir=backup_dir) as temporary:
        snapshot = Path(temporary) / "smartflow.db"
        with closing(database.get_connection()) as source, closing(sqlite3.connect(snapshot)) as destination:
            source.backup(destination)
        references = _referenced_paths(snapshot)
        files = _files_for_references(references)
        desktop_files, desktop_evidence = _desktop_evidence()
        files.update(desktop_files)
        mapping = {value: _member(_source_path(value)) for value in sorted(references)}
        archive = Path(temporary) / filename
        manifest = {"format": 1, "created_at": datetime.now(UTC).isoformat(),
                    "active_network": _member(road_network.NETWORK_PATH),
                    "references": mapping, "files": {member: {"sha256": _digest(path), "size": path.stat().st_size}
                                                         for member, path in sorted(files.items())},
                    "database_sha256": _digest(snapshot)}
        from simulation.network_registry import REGISTRY_PATH
        if REGISTRY_PATH.exists():
            manifest['network_registry'] = _member(REGISTRY_PATH)
        if desktop_evidence:
            manifest['desktop_evidence'] = desktop_evidence
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


def _restore_layout(staged: Path, manifest: dict) -> dict[str, Path]:
    """Compact source directories while keeping job trees and sidecars together.

    Repeating a source checkout's full relative path beneath its restore directory
    can exceed Windows path limits. Bundle names remain immutable; only the new
    isolated filesystem locations use short directory aliases.
    """
    members = set(manifest['files']) | set(manifest['references'].values())
    for member in members:
        if not isinstance(member, str) or not member.startswith('files/') or '..' in Path(member).parts:
            raise ValueError('Unsafe backup member path')
        if Path(member).as_posix() != member:
            raise ValueError('Backup member path must be canonical')
        if not _within((staged / member).resolve(), staged):
            raise ValueError('Backup member escapes the restore directory')
    referenced_directories = sorted(members - set(manifest['files']), key=lambda name: (len(name), name))
    anchors = []
    for member in referenced_directories:
        if not any(member == parent or member.startswith(parent + '/') for parent in anchors):
            anchors.append(member)
    for member in sorted(manifest['files']):
        if not any(member.startswith(parent + '/') for parent in anchors):
            parent = Path(member).parent.as_posix()
            if parent not in anchors:
                anchors.append(parent)
    layout = {}
    for member in members:
        parent = next(parent for parent in sorted(anchors, key=len, reverse=True)
                      if member == parent or member.startswith(parent + '/'))
        relative = Path(member).relative_to(parent)
        destination = (staged / 'files' / str(anchors.index(parent)) / relative).resolve()
        if not _within(destination, staged):
            raise ValueError('Backup member escapes the restore directory')
        layout[member] = destination
    return layout


def _stage_inventory(root: Path) -> dict:
    files = {}
    for path in sorted(root.rglob("*")):
        if path.is_symlink():
            raise ValueError("Restore stage contains a symbolic link")
        if path.is_file() and path != root / "restore_seal.json":
            files[path.relative_to(root).as_posix()] = {"size": path.stat().st_size, "sha256": _digest(path)}
    return files


def _write_restore_seal(root: Path) -> None:
    (root / "restore_seal.json").write_text(json.dumps(_stage_inventory(root), sort_keys=True), encoding="utf-8")


def prepare_desktop_restore(staged: Path, destination: Path, secret_file: Path) -> Path:
    """Create an independent candidate root from an already verified restore stage.

    The destination is its final path: moving it later invalidates stored absolute
    artifact paths. This function neither selects it nor stops a running backend.
    """
    staged = Path(staged).resolve(strict=True)
    destination = Path(destination).resolve()
    secret_file = Path(secret_file).resolve(strict=True)
    if destination == staged or _within(destination, staged) or _within(staged, destination):
        raise ValueError("Restore candidate and verification stage must be separate directories")
    secret = secret_file.read_text(encoding="ascii").strip()
    if len(secret) < 40:
        raise ValueError("The existing desktop installation secret is invalid")
    if destination.exists():
        raise FileExistsError("Restore candidate already exists")
    destination.mkdir(parents=True, exist_ok=False)
    try:
        artifacts = destination / "data" / "restored"
        shutil.copytree(_windows_long_path(staged), _windows_long_path(artifacts), symlinks=True)
        extended_artifacts = Path(_windows_long_path(artifacts))
        seal = json.loads((extended_artifacts / "restore_seal.json").read_text(encoding="utf-8"))
        if not isinstance(seal, dict) or _stage_inventory(extended_artifacts) != seal:
            raise ValueError("Verified restore stage changed before candidate preparation")
        environment = json.loads((artifacts / "restore_environment.json").read_text(encoding="utf-8"))
        layout = json.loads((artifacts / "restore_layout.json").read_text(encoding="utf-8"))
        if not isinstance(layout, dict) or not environment.get("SMARTFLOW_NETWORK_REGISTRY_PATH"):
            raise ValueError("A complete verified desktop bundle and network registry are required")

        def copied_path(value: str) -> Path:
            if not isinstance(value, str):
                raise ValueError("Invalid staged artifact path")
            original = Path(value).resolve()
            if not _within(original, staged):
                raise ValueError("Staged artifact escapes the verification directory")
            result = artifacts / original.relative_to(staged)
            resolved = Path(_windows_long_path(result)).resolve(strict=True)
            if not _within(resolved, extended_artifacts.resolve()):
                raise ValueError("Copied artifact escapes the candidate directory")
            return result

        snapshot = copied_path(environment["SMARTFLOW_DB_PATH"])
        active_network = copied_path(environment["SMARTFLOW_NETWORK_PATH"])
        registry = copied_path(environment["SMARTFLOW_NETWORK_REGISTRY_PATH"])
        evidence = copied_path(environment["SMARTFLOW_STUDY_ROOT"]) if environment.get("SMARTFLOW_STUDY_ROOT") else None
        entries = json.loads(registry.read_text(encoding="utf-8")).get("networks")
        if not isinstance(entries, list):
            raise ValueError("Invalid restored network registry")
        site_files = []
        ids, filenames = set(), {"registry.json", "tagum_network.json"}
        for entry in entries:
            name, network_id = entry.get("file"), entry.get("id")
            if (not isinstance(name, str) or not name or Path(name).name != name or "/" in name or "\\" in name
                    or name.casefold() in filenames or not isinstance(network_id, str) or not network_id or network_id in ids):
                raise ValueError("Invalid restored network registry entry")
            ids.add(network_id)
            filenames.add(name.casefold())
            site = Path(_windows_long_path(registry.parent / name)).resolve(strict=True)
            if not _within(site, extended_artifacts.resolve()) or road_network.load_network(site).id != network_id:
                raise ValueError("Restored network does not match its registry id")
            site_files.append(site)
            history = entry.get("revision_history", [])
            if not isinstance(history, list):
                raise ValueError("Invalid restored network revision history")
            for revision in history:
                if not isinstance(revision, dict):
                    raise ValueError("Invalid restored network revision history entry")
                historical_name = revision.get("file")
                if (not isinstance(historical_name, str) or not historical_name or
                        Path(historical_name).name != historical_name or "/" in historical_name or
                        "\\" in historical_name or ":" in historical_name or
                        historical_name.casefold() in {"registry.json", "tagum_network.json"}):
                    raise ValueError("Unsafe restored network revision history file")
                historical_path = Path(_windows_long_path(registry.parent / historical_name))
                if historical_path.is_symlink() or not _within(historical_path.resolve(strict=True), extended_artifacts.resolve()):
                    raise ValueError("Restored network revision history escapes storage")
                historical = road_network.load_network(historical_path)
                if historical.id != network_id or historical.fingerprint != revision.get("sha256"):
                    raise ValueError("Restored network revision history fingerprint mismatch")
                site_files.append(historical_path)
        road_network.load_network(active_network)
        mappings = {}
        for relative in layout.values():
            source = (staged / relative).resolve()
            copied = copied_path(str(source))
            # Persist the extended form only when necessary; shorter paths stay
            # human-readable and long paths remain usable by Windows consumers.
            mappings[str(source)] = _windows_long_path(copied) if os.name == "nt" and len(str(copied)) >= 240 else str(copied)
        data = destination / "data"
        # The verification database may still have a WAL; copying only its main
        # file would silently drop committed changes.
        with closing(sqlite3.connect(snapshot)) as source, closing(sqlite3.connect(data / "smartflow.db")) as target:
            source.backup(target)
        network_dir = data / "networks"
        network_dir.mkdir()
        shutil.copyfile(active_network, network_dir / "tagum_network.json")
        shutil.copyfile(registry, network_dir / "registry.json")
        for site in site_files:
            shutil.copyfile(site, _windows_long_path(network_dir / site.name))
        if evidence:
            shutil.copytree(_windows_long_path(evidence), _windows_long_path(destination), dirs_exist_ok=True)
        config_dir = destination / "config"
        config_dir.mkdir(exist_ok=True)
        shutil.copyfile(secret_file, config_dir / "installation-secret")
        candidate_db = data / "smartflow.db"
        _rewrite_database(candidate_db, mappings)
        extended_destination = Path(_windows_long_path(destination)).resolve()
        for value in _referenced_paths(candidate_db):
            candidate = Path(_windows_long_path(Path(value))).resolve()
            if not _within(candidate, extended_destination) or not candidate.exists():
                raise ValueError(f"Restored artifact is not contained in the candidate: {value}")
        return destination
    except BaseException:
        # The copied evidence can exceed the legacy Windows path limit even
        # when the candidate root itself is short.
        shutil.rmtree(_windows_long_path(destination))
        raise


def restore_bundle_to_stage(backup_id: int) -> Path:
    with database.get_db() as conn:
        row = conn.execute("SELECT filename FROM backups WHERE id = ?", (backup_id,)).fetchone()
    if not row:
        raise ValueError("Backup not found")
    archive = Path(_windows_long_path(database._resolve_backup_path(row["filename"])))
    if archive.suffix != ".zip":
        raise ValueError("This legacy database-only backup cannot verify models and recordings")
    if not archive.is_file():
        raise FileNotFoundError(f"Backup file is missing: {archive.name}")
    restore_root = Path(_windows_long_path(database._backups_directory() / "restores"))
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
            restored_members = _restore_layout(staged, manifest)
            for member, info in manifest["files"].items():
                destination = restored_members[member]
                destination.parent.mkdir(parents=True, exist_ok=True)
                destination.write_bytes(bundle.read(member))
                if destination.stat().st_size != info["size"] or _digest(destination) != info["sha256"]:
                    raise ValueError(f"Backup artifact checksum mismatch: {member}")
            desktop_root = _desktop_evidence_layout(staged, manifest, restored_members)
            paths = {}
            for original, member in manifest["references"].items():
                if not isinstance(original, str) or not isinstance(member, str) or not member.startswith("files/"):
                    raise ValueError("Invalid backup artifact reference")
                restored = restored_members[member]
                if not _within(restored, staged) or not restored.exists():
                    raise ValueError(f"Referenced artifact is missing from bundle: {member}")
                paths[original] = str(restored)
            _rewrite_database(snapshot, paths)
            network_member = manifest.get("active_network", "files/project/data/networks/tagum_network.json")
            if network_member not in manifest["files"]:
                raise ValueError("Configured network is missing from the backup bundle")
            from services.scenario_migration import migrate_connection
            registry_member = manifest.get('network_registry')
            if registry_member is not None and registry_member not in manifest['files']:
                raise ValueError('Network registry is missing from the backup bundle')
            restored_registry = restored_members[registry_member] if registry_member else staged / 'missing-registry.json'
            with closing(sqlite3.connect(snapshot)) as conn, conn:
                conn.row_factory = sqlite3.Row
                conn.execute('BEGIN IMMEDIATE')
                report = migrate_connection(conn, apply=True, network=road_network.load_network(restored_members[network_member]), registry_path=restored_registry)
            (staged / 'scenario_migration_report.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
            (staged / 'restore_layout.json').write_text(json.dumps({
                member: path.relative_to(staged).as_posix() for member, path in restored_members.items()
            }, indent=2), encoding='utf-8')
            (staged / "restore_environment.json").write_text(json.dumps({
                "SMARTFLOW_DB_PATH": str(snapshot),
                "SMARTFLOW_NETWORK_PATH": str(restored_members[network_member]),
                **({"SMARTFLOW_NETWORK_REGISTRY_PATH": str(restored_registry)} if registry_member else {}),
                **({"SMARTFLOW_STUDY_ROOT": str(desktop_root)} if desktop_root else {}),
                "note": "Start a separate SmartFlow API process with these environment variables and its own secret key."
            }, indent=2), encoding="utf-8")
            _write_restore_seal(staged)
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
                if 'scenarios' in tables:
                    from services.scenario_migration import migrate_connection
                    conn.row_factory = sqlite3.Row
                    report = migrate_connection(conn, apply=True)
                    (staged / 'scenario_migration_report.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
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
