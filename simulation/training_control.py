"""Cooperative cancellation at simulation boundaries, including on Windows."""
import os
from pathlib import Path


def check_training_cancelled() -> None:
    cancel_file = os.environ.get("SMARTFLOW_TRAINING_CANCEL_FILE")
    if cancel_file and Path(cancel_file).is_file():
        raise KeyboardInterrupt("Training cancellation requested")
