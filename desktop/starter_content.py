"""Install the packaged Site A demonstration into the active desktop library."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import re
import shutil
from tempfile import TemporaryDirectory

STARTER_ID = "site-a-seed101-v1"
CONTROLLERS = ("fixed-time", "ql", "dql")
METRIC_COLUMNS = (
    "avg_waiting_time", "avg_queue_length", "max_queue_length", "throughput",
    "avg_pedestrian_delay", "signal_phase_efficiency", "congestion_severity", "raw_metrics_json",
)


def file_digest(path: Path) -> str:
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def verify_content(folder: Path) -> dict:
    catalog = json.loads((folder / "catalog.json").read_text(encoding="utf-8"))
    if catalog["id"] != STARTER_ID or tuple(catalog["runs"]) != CONTROLLERS or set(catalog["models"]) != {"ql", "dql"}:
        raise ValueError("The desktop starter catalog must include both models and the three Site A recordings.")
    files = set(catalog["models"].values())
    files.add(Path(catalog["models"]["dql"]).with_suffix(".metadata.json").name)
    files.update(f"{controller}.{suffix}" for controller in CONTROLLERS for suffix in ("jsonl.gz", "manifest.json"))
    if set(catalog["sha256"]) != files or {path.name for path in folder.iterdir()} != files | {"catalog.json"}:
        raise ValueError("The desktop starter catalog and its files disagree.")
    for name in files:
        path = folder / name
        if not re.fullmatch(r"[A-Za-z0-9_.-]+", name) or path.is_symlink() or not path.is_file() or file_digest(path) != catalog["sha256"][name]:
            raise ValueError(f"Invalid or changed starter artifact: {name}")
    return catalog


def install_starter_content(folder: Path) -> bool:
    if not folder.is_dir():
        return False
    import database
    from desktop.model_import import register_model, write_artifact
    from services.timeline_artifacts import timeline_directory

    with database.get_db() as connection:
        connection.execute("BEGIN IMMEDIATE")
        connection.execute("CREATE TABLE IF NOT EXISTS desktop_starter_content (id TEXT PRIMARY KEY)")
        if connection.execute("SELECT 1 FROM desktop_starter_content WHERE id = ?", (STARTER_ID,)).fetchone():
            return False
        catalog = verify_content(folder)
        scenario = catalog["scenario"]
        native = database.validated_native_scenario(scenario["network_id"], scenario["engine_config"])
        if native["network_sha256"] != scenario["network_sha256"]:
            raise ValueError("The starter recordings require the bundled Site A network.")
        scenario_id = connection.execute(
            "INSERT INTO scenarios (name, description, network_id, network_sha256, engine_config) VALUES (?, ?, ?, ?, ?)",
            ("Site A starter comparison", "Synthetic Site A demonstration, seed 101.",
             native["network_id"], native["network_sha256"], native["engine_config"]),
        ).lastrowid
        model_ids = {}
        for algorithm, filename in catalog["models"].items():
            model_path = folder / filename
            metadata = model_path.with_suffix(".metadata.json").read_bytes() if algorithm == "dql" else None
            model = register_model(connection, filename, model_path.read_bytes(), metadata)
            if model["algorithm"] != algorithm:
                raise ValueError("The starter model does not match its catalog algorithm.")
            model_ids[algorithm] = model["id"]

        destination = timeline_directory() / STARTER_ID
        destination.mkdir(parents=True, exist_ok=True)
        for controller, record in catalog["runs"].items():
            timeline = destination / f"{controller}.jsonl.gz"
            model_id = model_ids.get(controller)
            run_id = connection.execute(
                """INSERT INTO simulation_runs (scenario_id, rl_model_id, control_mode, run_mode, status,
                           start_time, end_time, duration_seconds, seed, timeline_path, notes)
                   VALUES (?, ?, ?, 'pre-record', 'completed', ?, ?, ?, ?, ?, ?)""",
                (scenario_id, model_id, controller, record["start_time"], record["end_time"], record["duration_seconds"],
                 record["seed"], str(timeline), record["notes"]),
            ).lastrowid
            metrics = record["metrics"]
            connection.execute(
                f"INSERT INTO run_metrics (run_id, {', '.join(METRIC_COLUMNS)}) VALUES ({', '.join(['?'] * (1 + len(METRIC_COLUMNS)))})",
                (run_id, *(metrics[column] for column in METRIC_COLUMNS)),
            )
            with TemporaryDirectory(prefix="replay-", dir=destination) as temporary:
                staged = Path(temporary) / timeline.name
                shutil.copyfile(folder / timeline.name, staged)
                staged.replace(timeline)
            manifest = json.loads((folder / f"{controller}.manifest.json").read_text(encoding="utf-8"))
            manifest["run"]["id"] = run_id
            manifest["scenario"]["id"] = scenario_id
            if model_id is not None:
                manifest["experiment"]["policy"]["model_id"] = model_id
            manifest["artifacts"]["timeline_path_canonical"] = str(timeline)
            write_artifact(destination / f"{controller}.manifest.json", json.dumps(manifest).encode("utf-8"))
        connection.execute("INSERT INTO desktop_starter_content (id) VALUES (?)", (STARTER_ID,))
    return True
