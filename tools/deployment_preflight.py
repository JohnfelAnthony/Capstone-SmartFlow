"""Fail early when a single-process HTTPS deployment lacks its prerequisites."""
from __future__ import annotations

import os
import shutil
from pathlib import Path

import config
from simulation.road_network import NETWORK_PATH


ROOT = Path(__file__).resolve().parents[1]


def check() -> list[str]:
    errors: list[str] = []
    if not config.PRODUCTION:
        errors.append("SMARTFLOW_ENV must be production.")
    if Path.cwd().resolve() != ROOT:
        errors.append(f"Start from the SmartFlow root: {ROOT}")
    if not NETWORK_PATH.is_file():
        errors.append(f"Native network file is missing: {NETWORK_PATH}")
    if not (ROOT / "dist" / "index.html").is_file():
        errors.append("Built frontend is missing; run npm ci and npm run build.")

    database_path = Path(config.DB_PATH).resolve()
    if not database_path.is_file() and not config.BOOTSTRAP_ADMIN_PASSWORD:
        errors.append("A fresh database requires SMARTFLOW_BOOTSTRAP_ADMIN_PASSWORD.")
    if config.BOOTSTRAP_ADMIN_PASSWORD and len(config.BOOTSTRAP_ADMIN_PASSWORD) < 12:
        errors.append("The bootstrap admin password must contain at least 12 characters.")
    storage_path = database_path.parent
    if not storage_path.is_dir():
        errors.append(f"Database storage directory does not exist: {storage_path}")
    else:
        if not os.access(storage_path, os.W_OK):
            errors.append(f"Database storage directory is not writable: {storage_path}")
        recording_reserve = (config.RECORDING_FREE_SPACE_RESERVE
                             + config.MAX_RECORDING_SECONDS * config.RECORDING_BYTES_PER_SECOND_RESERVE)
        minimum_free = recording_reserve + 1024**3
        if shutil.disk_usage(storage_path).free < minimum_free:
            errors.append(f"Database storage needs at least {minimum_free / 1024**3:.1f} GiB free for the recording cap and operating reserve.")
    return errors


def main() -> int:
    errors = check()
    for error in errors:
        print(f"ERROR: {error}")
    if errors:
        return 1
    print(f"Production preflight passed. Database: {Path(config.DB_PATH).resolve()}")
    print(f"Allowed browser origins: {', '.join(config.ALLOWED_ORIGINS)}")
    print("Use exactly one API worker; live and training state is process-local.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
