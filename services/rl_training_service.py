from __future__ import annotations

import json
import os
import re
import signal
import subprocess
import sys
import threading
import time
from datetime import UTC, datetime
from pathlib import Path

import database


ROOT = Path(__file__).resolve().parents[1]
LOG_DIR = ROOT / "data" / "generated" / "rl_training_logs"
DEFAULT_SEEDS = "11,22,33,44,55"
ALGORITHM_LABELS = {
    "ql": "Q-Learning",
    "dql": "Deep Q-Learning",
    "ppo": "PPO",
}
TRAINING_SCRIPT = {
    "ql": "tools/train_ql.py",
    "dql": "tools/train_dql.py",
    "ppo": "tools/train_ppo.py",
}
MODEL_FLAG = {
    "ql": "--ql-model",
    "dql": "--dql-model",
    "ppo": "--ppo-model",
}
PROGRESS_RE = re.compile(
    r"\[(?P<episode>\d+)/(?P<total>\d+)\s+\|\s+(?P<percent>[\d.]+)%\].*?"
    r"(?:timesteps=(?P<timesteps>\d+)/(?P<total_timesteps>\d+).*?)?"
    r"reward=(?P<reward>-?\d+(?:\.\d+)?).*?"
    r"(?:epsilon=(?P<epsilon>\d+(?:\.\d+)?).*?)?"
)
REWARD_RE = re.compile(r"reward=(?P<reward>-?\d+(?:\.\d+)?)")
EPSILON_RE = re.compile(r"epsilon=(?P<epsilon>\d+(?:\.\d+)?)")
TIMESTEPS_RE = re.compile(r"timesteps=(?P<timesteps>\d+)/(?P<total_timesteps>\d+)")
ARTIFACT_RE = re.compile(r"Saved (?:partial )?(?P<label>QL|DQL|PPO) model artifact:\s*(?P<path>.+)$")
METADATA_RE = re.compile(r"Saved (?:partial )?(?P<label>DQL|PPO) metadata:\s*(?P<path>.+)$")
MODEL_ID_RE = re.compile(r"Registered rl_models\.id:\s*(?P<id>\d+)")
EVALUATION_RE = re.compile(r"Saved evaluation summary:\s*(?P<path>.+)$")

_worker_lock = threading.Lock()
_active_process: subprocess.Popen | None = None
_active_job_id: int | None = None
_stop_requested = False


def _utc_now_iso() -> str:
    return datetime.now(UTC).isoformat()


def _python_executable() -> str:
    venv_python = ROOT / ".venv" / "Scripts" / "python.exe"
    return str(venv_python if venv_python.exists() else Path(sys.executable))


def _normalize_algorithm(raw_algorithm: str) -> str:
    algorithm = str(raw_algorithm or "").strip().lower().replace("_", "-")
    if algorithm not in TRAINING_SCRIPT:
        raise ValueError(f"Unsupported training algorithm: {raw_algorithm}")
    return algorithm


def _json_loads(value, default):
    try:
        return json.loads(value or "")
    except Exception:
        return default


def _setting(settings: dict, key: str, default):
    value = settings.get(key, default)
    if value is None or value == "":
        return default
    return value


def build_training_command(algorithm: str, settings: dict, advanced: dict | None = None) -> list[str]:
    algorithm = _normalize_algorithm(algorithm)
    advanced = advanced or {}
    command = [
        _python_executable(),
        "-u",
        TRAINING_SCRIPT[algorithm],
        "--episodes", str(int(_setting(settings, "episodes", 10))),
        "--warmup-seconds", str(float(_setting(settings, "warmup_seconds", 20.0))),
        "--evaluation-seconds", str(float(_setting(settings, "evaluation_seconds", 300.0))),
        "--seeds", str(_setting(settings, "seeds", DEFAULT_SEEDS)),
        "--intersection-id", str(_setting(settings, "intersection_id", "tagum_1")),
        "--traffic-density", str(_setting(settings, "traffic_density", "medium")),
        "--pedestrian-density", str(_setting(settings, "pedestrian_density", "medium")),
        "--emergency-mode", str(_setting(settings, "emergency_mode", "disabled")),
        "--road-constraint", str(_setting(settings, "road_constraint", "None")),
        "--checkpoint-every", str(int(_setting(settings, "checkpoint_every", 25))),
    ]
    if settings.get("resume_model"):
        command.extend(["--resume-model", str(settings["resume_model"])])

    algorithm_advanced = advanced.get(algorithm, {}) if isinstance(advanced, dict) else {}
    flag_map = {
        "ql": {
            "alpha": "--alpha",
            "gamma": "--gamma",
            "epsilon": "--epsilon",
            "min_epsilon": "--min-epsilon",
            "epsilon_decay": "--epsilon-decay",
        },
        "dql": {
            "learning_rate": "--learning-rate",
            "learning_starts": "--learning-starts",
            "buffer_size": "--buffer-size",
            "batch_size": "--batch-size",
            "gamma": "--gamma",
            "target_update_interval": "--target-update-interval",
        },
        "ppo": {
            "learning_rate": "--learning-rate",
            "n_steps": "--n-steps",
            "batch_size": "--batch-size",
            "n_epochs": "--n-epochs",
            "gamma": "--gamma",
            "gae_lambda": "--gae-lambda",
            "clip_range": "--clip-range",
        },
    }
    for key, flag in flag_map[algorithm].items():
        if key in algorithm_advanced and algorithm_advanced[key] not in {None, ""}:
            command.extend([flag, str(algorithm_advanced[key])])
    return command


def build_evaluation_command(algorithms: list[str], settings: dict, model_paths: dict[str, str]) -> list[str]:
    controllers = ["fixed-time"] + [
        algorithm for algorithm in algorithms if algorithm in model_paths and model_paths[algorithm]
    ]
    command = [
        _python_executable(),
        "-u",
        "tools/evaluate_controllers.py",
        "--controllers", ",".join(controllers),
        "--seeds", str(_setting(settings, "seeds", DEFAULT_SEEDS)),
        "--duration-seconds", str(float(_setting(settings, "evaluation_seconds", 300.0))),
        "--warmup-seconds", str(float(_setting(settings, "warmup_seconds", 20.0))),
        "--intersection-id", str(_setting(settings, "intersection_id", "tagum_1")),
        "--traffic-density", str(_setting(settings, "traffic_density", "medium")),
        "--pedestrian-density", str(_setting(settings, "pedestrian_density", "medium")),
        "--emergency-mode", str(_setting(settings, "emergency_mode", "disabled")),
        "--road-constraint", str(_setting(settings, "road_constraint", "None")),
    ]
    for algorithm, model_path in model_paths.items():
        if algorithm in MODEL_FLAG and model_path:
            command.extend([MODEL_FLAG[algorithm], str(model_path)])
    return command


def enqueue_training_job(*, algorithms: list[str], settings: dict, advanced: dict | None = None, user_id=None) -> int:
    global _active_job_id
    normalized_algorithms = [_normalize_algorithm(algorithm) for algorithm in algorithms]
    if not normalized_algorithms:
        raise ValueError("Choose at least one algorithm to train.")
    if settings.get("resume_model") and len(normalized_algorithms) != 1:
        raise ValueError("Resume training supports one selected algorithm at a time.")

    with _worker_lock:
        if _active_job_id is not None:
            active_job = database.get_rl_training_job(_active_job_id)
            if active_job and active_job.get("status") in {"queued", "running", "stopping"}:
                raise RuntimeError("Another RL training job is already running.")

        LOG_DIR.mkdir(parents=True, exist_ok=True)
        timestamp = datetime.now(UTC).strftime("%Y%m%d_%H%M%S")
        log_path = LOG_DIR / f"rl_training_{timestamp}.jsonl"
        payload_settings = {**settings, "advanced": advanced or {}}
        job_id = int(
            database.create_rl_training_job(
                user_id=user_id,
                selected_algorithms=normalized_algorithms,
                settings=payload_settings,
                log_path=str(log_path),
            )
        )
        for index, algorithm in enumerate(normalized_algorithms):
            command = build_training_command(algorithm, settings, advanced)
            database.create_rl_training_job_item(
                job_id=job_id,
                algorithm=algorithm,
                sequence_index=index,
                command=command,
            )

        worker = threading.Thread(target=_run_job, args=(job_id,), daemon=True)
        _active_job_id = job_id
        worker.start()
        return job_id


def enqueue_model_evaluation(*, model_id: int, settings: dict, user_id=None) -> int:
    global _active_job_id
    model = database.get_rl_model_by_id(int(model_id))
    if not model:
        raise ValueError(f"RL model #{model_id} was not found.")
    algorithm = _normalize_algorithm(model.get("algorithm"))
    model_path = model.get("checkpoint_path")
    if not model_path:
        raise ValueError(f"RL model #{model_id} has no checkpoint path.")

    with _worker_lock:
        if _active_job_id is not None:
            active_job = database.get_rl_training_job(_active_job_id)
            if active_job and active_job.get("status") in {"queued", "running", "stopping"}:
                raise RuntimeError("Another RL training or evaluation job is already running.")

        LOG_DIR.mkdir(parents=True, exist_ok=True)
        timestamp = datetime.now(UTC).strftime("%Y%m%d_%H%M%S")
        log_path = LOG_DIR / f"rl_evaluation_{timestamp}.jsonl"
        command = build_evaluation_command([algorithm], settings, {algorithm: model_path})
        job_id = int(
            database.create_rl_training_job(
                user_id=user_id,
                selected_algorithms=[algorithm],
                settings={**settings, "evaluation_only": True},
                log_path=str(log_path),
            )
        )
        item_id = database.create_rl_training_job_item(
            job_id=job_id,
            algorithm=algorithm,
            sequence_index=0,
            command=command,
        )
        database.update_rl_training_job_item(
            item_id,
            rl_model_id=int(model_id),
            artifact_path=model_path,
        )

        worker = threading.Thread(
            target=_run_evaluation_only,
            args=(job_id, int(item_id), algorithm, model_path),
            daemon=True,
        )
        _active_job_id = job_id
        worker.start()
        return job_id


def stop_training_job(job_id: int | None = None):
    global _stop_requested
    with _worker_lock:
        if job_id is not None and _active_job_id is not None and int(job_id) != int(_active_job_id):
            return
        _stop_requested = True
        if _active_job_id is not None:
            database.update_rl_training_job(
                _active_job_id,
                status="stopping",
                message="Stopping after graceful interrupt.",
            )
        if _active_process is not None and _active_process.poll() is None:
            _interrupt_process(_active_process)


def training_status(job_id: int | None = None) -> dict:
    job = database.get_rl_training_job(job_id) if job_id else database.get_latest_rl_training_job()
    if not job:
        return {"job": None, "items": [], "log_lines": [], "models": model_rows()}
    return {
        "job": job,
        "items": database.get_rl_training_job_items(job["id"]),
        "log_lines": read_log_tail(job.get("log_path"), limit=160),
        "models": model_rows(),
    }


def model_rows(limit: int = 200) -> list[dict]:
    rows = []
    for model in database.list_rl_models(limit=limit):
        rows.append(
            {
                "id": model.get("id"),
                "algorithm": str(model.get("algorithm") or "").upper(),
                "name": model.get("name"),
                "checkpoint_path": model.get("checkpoint_path"),
                "training_date": model.get("training_date") or model.get("created_at"),
                "best_evaluation_score": model.get("best_evaluation_score"),
            }
        )
    return rows


def read_log_tail(log_path: str | None, *, limit: int = 120) -> list[dict]:
    if not log_path:
        return []
    path = Path(log_path)
    if not path.exists():
        return []
    lines = path.read_text(encoding="utf-8", errors="replace").splitlines()[-limit:]
    records = []
    for line in lines:
        try:
            records.append(json.loads(line))
        except Exception:
            records.append({"type": "stdout", "text": line})
    return records


def _run_job(job_id: int):
    global _active_job_id, _active_process, _stop_requested
    job = database.get_rl_training_job(job_id)
    if not job:
        return
    settings = _json_loads(job.get("settings_json"), {})
    selected_algorithms = _json_loads(job.get("selected_algorithms_json"), [])
    items = database.get_rl_training_job_items(job_id)
    log_path = Path(job.get("log_path") or LOG_DIR / f"rl_training_{job_id}.jsonl")
    model_paths: dict[str, str] = {}

    with _worker_lock:
        _active_job_id = job_id
        _stop_requested = False
    database.update_rl_training_job(
        job_id,
        status="running",
        started_at=_utc_now_iso(),
        message="Training started.",
    )
    _append_log(log_path, {"type": "system", "text": f"Training job #{job_id} started."})

    try:
        for item in items:
            if _stop_requested:
                _mark_item_interrupted(item["id"], "Stopped before this algorithm started.")
                continue
            algorithm = item["algorithm"]
            command = _json_loads(item.get("command_json"), [])
            artifact_path = _run_command_item(
                job_id=job_id,
                item=item,
                command=command,
                log_path=log_path,
                item_count=len(items),
            )
            if artifact_path:
                model_paths[algorithm] = artifact_path
                evaluation_path = _run_evaluation(
                    job_id=job_id,
                    algorithms=[algorithm],
                    settings=settings,
                    model_paths={algorithm: artifact_path},
                    log_path=log_path,
                )
                if evaluation_path:
                    database.update_rl_training_job_item(item["id"], evaluation_path=evaluation_path)

        completed_algorithms = [
            algorithm for algorithm in selected_algorithms if algorithm in model_paths
        ]
        if len(completed_algorithms) > 1 and not _stop_requested:
            _run_evaluation(
                job_id=job_id,
                algorithms=completed_algorithms,
                settings=settings,
                model_paths=model_paths,
                log_path=log_path,
            )

        final_status = "interrupted" if _stop_requested else "completed"
        database.update_rl_training_job(
            job_id,
            status=final_status,
            progress_percent=100 if not _stop_requested else job.get("progress_percent", 0),
            ended_at=_utc_now_iso(),
            message="Training stopped." if _stop_requested else "Training completed.",
        )
        _append_log(log_path, {"type": "system", "text": f"Training job #{job_id} {final_status}."})
    except Exception as exc:
        database.update_rl_training_job(
            job_id,
            status="error",
            ended_at=_utc_now_iso(),
            message=str(exc),
        )
        _append_log(log_path, {"type": "error", "text": str(exc)})
    finally:
        with _worker_lock:
            _active_job_id = None
            _active_process = None
            _stop_requested = False


def _run_evaluation_only(job_id: int, item_id: int, algorithm: str, model_path: str):
    global _active_job_id, _active_process, _stop_requested
    job = database.get_rl_training_job(job_id)
    if not job:
        return
    settings = _json_loads(job.get("settings_json"), {})
    log_path = Path(job.get("log_path") or LOG_DIR / f"rl_evaluation_{job_id}.jsonl")
    with _worker_lock:
        _active_job_id = job_id
        _stop_requested = False
    database.update_rl_training_job(
        job_id,
        status="running",
        current_algorithm=algorithm,
        current_item_id=item_id,
        started_at=_utc_now_iso(),
        message=f"Evaluating {ALGORITHM_LABELS.get(algorithm, algorithm.upper())}.",
    )
    database.update_rl_training_job_item(
        item_id,
        status="running",
        started_at=_utc_now_iso(),
        message="Evaluation started.",
    )
    try:
        evaluation_path = _run_evaluation(
            job_id=job_id,
            algorithms=[algorithm],
            settings=settings,
            model_paths={algorithm: model_path},
            log_path=log_path,
        )
        database.update_rl_training_job_item(
            item_id,
            status="completed" if evaluation_path else "error",
            progress_percent=100,
            evaluation_path=evaluation_path,
            ended_at=_utc_now_iso(),
            message="Evaluation completed." if evaluation_path else "Evaluation failed.",
        )
        database.update_rl_training_job(
            job_id,
            status="completed" if evaluation_path else "error",
            progress_percent=100,
            ended_at=_utc_now_iso(),
            message="Evaluation completed." if evaluation_path else "Evaluation failed.",
        )
    finally:
        with _worker_lock:
            _active_job_id = None
            _active_process = None
            _stop_requested = False


def _run_command_item(*, job_id: int, item: dict, command: list[str], log_path: Path, item_count: int) -> str | None:
    global _active_process
    item_id = int(item["id"])
    algorithm = item["algorithm"]
    artifact_path = None
    metadata_path = None
    model_id = None
    sequence_index = int(item.get("sequence_index") or 0)
    database.update_rl_training_job(
        job_id,
        current_algorithm=algorithm,
        current_item_id=item_id,
        message=f"Training {ALGORITHM_LABELS.get(algorithm, algorithm.upper())}.",
    )
    database.update_rl_training_job_item(
        item_id,
        status="running",
        started_at=_utc_now_iso(),
        message="Training started.",
    )
    _append_log(log_path, {"type": "command", "algorithm": algorithm, "text": " ".join(command)})

    process = _start_process(command)
    with _worker_lock:
        _active_process = process
    assert process.stdout is not None
    for raw_line in process.stdout:
        line = raw_line.rstrip()
        if not line:
            continue
        _append_log(log_path, {"type": "stdout", "algorithm": algorithm, "text": line})
        progress = _parse_progress(line)
        if progress:
            overall_progress = ((sequence_index + (progress["progress_percent"] / 100.0)) / max(item_count, 1)) * 100
            database.update_rl_training_job_item(item_id, **progress)
            database.update_rl_training_job(job_id, progress_percent=round(overall_progress, 3))
        artifact_match = ARTIFACT_RE.search(line)
        if artifact_match:
            artifact_path = artifact_match.group("path").strip()
            database.update_rl_training_job_item(item_id, artifact_path=artifact_path)
        metadata_match = METADATA_RE.search(line)
        if metadata_match:
            metadata_path = metadata_match.group("path").strip()
            database.update_rl_training_job_item(item_id, metadata_path=metadata_path)
        model_match = MODEL_ID_RE.search(line)
        if model_match:
            model_id = int(model_match.group("id"))
            database.update_rl_training_job_item(item_id, rl_model_id=model_id)

    return_code = process.wait()
    with _worker_lock:
        _active_process = None

    if return_code == 0:
        database.update_rl_training_job_item(
            item_id,
            status="completed",
            progress_percent=100,
            artifact_path=artifact_path,
            metadata_path=metadata_path,
            rl_model_id=model_id,
            ended_at=_utc_now_iso(),
            message="Training completed.",
        )
    elif return_code == 130:
        database.update_rl_training_job_item(
            item_id,
            status="interrupted",
            artifact_path=artifact_path,
            metadata_path=metadata_path,
            rl_model_id=model_id,
            ended_at=_utc_now_iso(),
            message="Training interrupted after partial save.",
        )
    else:
        database.update_rl_training_job_item(
            item_id,
            status="error",
            ended_at=_utc_now_iso(),
            message=f"Training exited with code {return_code}.",
        )
    return artifact_path if return_code in {0, 130} else None


def _run_evaluation(*, job_id: int, algorithms: list[str], settings: dict, model_paths: dict[str, str], log_path: Path) -> str | None:
    global _active_process
    command = build_evaluation_command(algorithms, settings, model_paths)
    _append_log(log_path, {"type": "command", "algorithm": "evaluation", "text": " ".join(command)})
    process = _start_process(command)
    with _worker_lock:
        _active_process = process
    evaluation_path = None
    assert process.stdout is not None
    for raw_line in process.stdout:
        line = raw_line.rstrip()
        if not line:
            continue
        _append_log(log_path, {"type": "stdout", "algorithm": "evaluation", "text": line})
        evaluation_match = EVALUATION_RE.search(line)
        if evaluation_match:
            evaluation_path = evaluation_match.group("path").strip()
    return_code = process.wait()
    with _worker_lock:
        _active_process = None
    if return_code != 0:
        _append_log(log_path, {"type": "error", "algorithm": "evaluation", "text": f"Evaluation exited with code {return_code}."})
    database.update_rl_training_job(job_id, message="Evaluation completed." if return_code == 0 else "Evaluation failed.")
    return evaluation_path


def _start_process(command: list[str]) -> subprocess.Popen:
    creationflags = 0
    if os.name == "nt":
        creationflags = getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0)
    return subprocess.Popen(
        command,
        cwd=str(ROOT),
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1,
        creationflags=creationflags,
    )


def _interrupt_process(process: subprocess.Popen):
    try:
        if os.name == "nt":
            process.send_signal(signal.CTRL_BREAK_EVENT)
        else:
            process.send_signal(signal.SIGINT)
    except Exception:
        process.terminate()

    deadline = time.time() + 20
    while process.poll() is None and time.time() < deadline:
        time.sleep(0.25)
    if process.poll() is None:
        process.terminate()


def _parse_progress(line: str) -> dict | None:
    match = PROGRESS_RE.search(line)
    if not match:
        return None
    reward_match = REWARD_RE.search(line)
    if not reward_match:
        return None
    episode = int(match.group("episode"))
    total = max(int(match.group("total")), 1)
    payload = {
        "latest_episode": episode,
        "latest_reward": float(reward_match.group("reward")),
        "progress_percent": round(min(float(match.group("percent")), 100.0), 3),
        "message": line,
    }
    epsilon_match = EPSILON_RE.search(line)
    if epsilon_match is not None:
        payload["latest_epsilon"] = float(epsilon_match.group("epsilon"))
    timesteps_match = TIMESTEPS_RE.search(line)
    if timesteps_match is not None:
        payload["latest_timesteps"] = int(timesteps_match.group("timesteps"))
        payload["progress_percent"] = round((episode / total) * 100, 3)
    return payload


def _mark_item_interrupted(item_id: int, message: str):
    database.update_rl_training_job_item(
        item_id,
        status="interrupted",
        ended_at=_utc_now_iso(),
        message=message,
    )


def _append_log(log_path: Path, record: dict):
    log_path.parent.mkdir(parents=True, exist_ok=True)
    payload = {"ts": _utc_now_iso(), **record}
    with log_path.open("a", encoding="utf-8") as log_file:
        log_file.write(json.dumps(payload, ensure_ascii=True) + "\n")
