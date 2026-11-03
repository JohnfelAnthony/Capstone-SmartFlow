"""Shared writable-data location, independent of packaged resource paths."""
from __future__ import annotations

import os
from pathlib import Path


def data_directory() -> Path:
    configured = os.environ.get("SMARTFLOW_DATA_DIR")
    return Path(configured).resolve() if configured else Path(__file__).resolve().parents[1] / "data"
