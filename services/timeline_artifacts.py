"""Recording locations shared by API and CLI producers."""
from pathlib import Path

import config


def timeline_directory() -> Path:
    database_path = Path(config.DB_PATH).resolve()
    return database_path.parent / f"{database_path.name}.artifacts" / "timelines"


def timeline_artifact_paths(run_id: int) -> tuple[Path, Path, Path]:
    directory = timeline_directory()
    directory.mkdir(parents=True, exist_ok=True)
    return (directory / f"run_{run_id}.jsonl",
            directory / f"run_{run_id}.jsonl.gz",
            directory / f"run_{run_id}.manifest.json")
