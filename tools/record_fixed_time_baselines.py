"""Back up the database, then record one pre-recorded fixed-time run per active scenario on the current engine.

Writes to the database named by SMARTFLOW_DB_PATH (as the app does); nothing changes without --confirm.
"""
from __future__ import annotations

import argparse
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import config  # noqa: E402
import database  # noqa: E402
from services import timeline_generator  # noqa: E402
from simulation.traffic_engine import ENGINE_VERSION  # noqa: E402


def backup_database() -> Path:
    """Snapshot the database with SQLite's backup API before anything is written."""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    destination = database._resolve_backup_path(f"smartflow_backup_{timestamp}_pre_{ENGINE_VERSION}_baselines.db")
    source = database.get_connection()
    try:
        database._checkpoint_wal(source)
        database._copy_database_snapshot(source, destination)
    finally:
        source.close()
    return destination


def record_baselines(seed: int, seconds: int) -> list[int]:
    run_ids = []
    for scenario in database.get_scenarios():
        run_id = database.create_run(scenario["id"], None, control_mode="fixed-time", run_mode="pre-record", status="running", seed=seed,
                                     notes=f"{ENGINE_VERSION} fixed-time baseline, {seconds}s, seed {seed}.")
        worker = timeline_generator.generate_timeline(scenario["id"], seconds, run_id, seed=seed, control_mode="fixed-time")
        worker.join()
        run = database.get_run_by_id(run_id)
        if run["status"] != "completed":
            raise RuntimeError(f"Run {run_id} for scenario '{scenario['name']}' ended {run['status']}: {run.get('notes')}")
        print(f"scenario {scenario['id']} '{scenario['name']}': run {run_id}")
        run_ids.append(run_id)
    return run_ids


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--seed", type=int, default=101)
    parser.add_argument("--seconds", type=int, default=300)
    parser.add_argument("--confirm", action="store_true", help="actually back up and write to the database")
    arguments = parser.parse_args(argv)
    if not arguments.confirm:
        print(f"Would back up {config.DB_PATH} and record one {arguments.seconds}s fixed-time run per active scenario "
              f"(seed {arguments.seed}) on {ENGINE_VERSION}. Re-run with --confirm.", file=sys.stderr)
        return 2
    print(f"backup: {backup_database()}")
    run_ids = record_baselines(arguments.seed, arguments.seconds)
    print("run ids: " + ", ".join(str(run_id) for run_id in run_ids))
    return 0


if __name__ == "__main__":
    sys.exit(main())
