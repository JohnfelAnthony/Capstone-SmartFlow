from __future__ import annotations

import json
import os
import re
import subprocess
import sys
import threading
from datetime import UTC, datetime
from pathlib import Path

import database
import config
from uuid import uuid4
from simulation.model_contract import artifact_metadata, training_junction
from services.training_settings import prepare_settings, validate_advanced, validate_model_for_settings
from services.observation_identity import validate_observed_holdout
from services.workload_admission import workload_admission


ROOT = Path(__file__).resolve().parents[1]
LOG_DIR = Path(os.environ["SMARTFLOW_RL_JOB_DIR"]) if os.environ.get("SMARTFLOW_RL_JOB_DIR") else None
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
_cancel_event = threading.Event()
_cancel_path: Path | None = None


def _utc_now_iso() -> str:
    return datetime.now(UTC).isoformat()


def _python_executable() -> str:
    venv_python = ROOT / ".venv" / "Scripts" / "python.exe"
    return str(venv_python if venv_python.exists() else Path(sys.executable))


def _job_root() -> Path:
    if LOG_DIR is not None:
        return LOG_DIR
    database_path = Path(config.DB_PATH).resolve()
    return database_path.parent / f"{database_path.name}.artifacts" / "rl_training_logs"


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
        "--intersection-id", str(_setting(settings, "intersection_id", settings["scenario_snapshot"]["intersection_id"])),
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
    if settings.get("scenario_id") is not None:
        command.extend(["--scenario-id", str(int(settings["scenario_id"]))])
    if settings.get("scenario_file"):
        command.extend(["--scenario-file", settings["scenario_file"]])
    command.extend(["--decision-interval-seconds", str(settings.get("decision_interval_seconds", 5)),
                    "--minimum-green-hold-seconds", str(settings.get("minimum_green_hold_seconds", 10))])
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
        "--seeds", str(_setting(settings, "evaluation_seeds", "101,102,103,104,105")),
        "--duration-seconds", str(float(_setting(settings, "evaluation_seconds", 300.0))),
        "--warmup-seconds", str(float(_setting(settings, "warmup_seconds", 20.0))),
        "--intersection-id", str(_setting(settings, "intersection_id", settings["evaluation_scenario_snapshot"]["intersection_id"])),
        "--traffic-density", str(_setting(settings, "traffic_density", "medium")),
        "--pedestrian-density", str(_setting(settings, "pedestrian_density", "medium")),
        "--emergency-mode", str(_setting(settings, "emergency_mode", "disabled")),
        "--road-constraint", str(_setting(settings, "road_constraint", "None")),
    ]
    for algorithm, model_path in model_paths.items():
        if algorithm in MODEL_FLAG and model_path:
            command.extend([MODEL_FLAG[algorithm], str(model_path)])
    if settings.get("evaluation_scenario_id") is not None:
        command.extend(["--scenario-id", str(int(settings["evaluation_scenario_id"]))])
    if settings.get("evaluation_scenario_file"):
        command.extend(["--scenario-file", settings["evaluation_scenario_file"]])
    command.extend(["--decision-interval-seconds", str(settings.get("decision_interval_seconds", 5)),
                    "--minimum-green-hold-seconds", str(settings.get("minimum_green_hold_seconds", 10))])
    return command


def enqueue_training_job(*, algorithms: list[str], settings: dict, advanced: dict | None = None, user_id=None) -> int:
    algorithms = list(dict.fromkeys(_normalize_algorithm(value) for value in algorithms))
    if not algorithms:
        raise ValueError("Choose at least one algorithm to train.")
    prepared = prepare_settings(settings)
    if prepared.get("resume_model") and algorithms != [prepared["resume_algorithm"]]:
        raise ValueError("Resume training requires only the selected model's algorithm.")
    if prepared.get("resume_advanced"):
        algorithm = prepared["resume_algorithm"]
        saved = prepared["resume_advanced"]
        supported = {
            "ql": {"alpha", "gamma", "epsilon", "min_epsilon", "epsilon_decay"},
            "dql": {"learning_rate", "learning_starts", "buffer_size", "batch_size", "gamma", "target_update_interval"},
            "ppo": {"learning_rate", "n_steps", "batch_size", "n_epochs", "gamma", "gae_lambda", "clip_range"},
        }[algorithm]
        prepared["advanced"] = validate_advanced(
            {algorithm: {key: saved[key] for key in supported if key in saved}}, algorithms)
    else:
        prepared["advanced"] = validate_advanced(advanced or {}, algorithms)
    return _enqueue(algorithms, prepared, user_id=user_id)


def enqueue_model_evaluation(*, model_id: int, settings: dict, user_id=None) -> int:
    model = database.get_rl_model_by_id(model_id)
    if not model:
        raise ValueError("Selected model no longer exists.")
    prepared = prepare_settings({**settings, "resume_model": None, "resume_model_id": None, "resume_checkpoint_id": None})
    metadata = validate_model_for_settings(model, prepared)
    if not isinstance(metadata.get("seed_set"), list) or not metadata["seed_set"]:
        raise ValueError("Selected model lacks recorded training seeds for held-out evaluation.")
    if not isinstance(metadata.get("scenario"), dict) or metadata["scenario"].get("id") is None:
        raise ValueError("Selected model lacks its training scenario identity for held-out evaluation.")
    if set(str(seed) for seed in metadata.get("seed_set", [])) & set(prepared["evaluation_seeds"].split(",")):
        raise ValueError("Held-out evaluation seeds overlap the selected model's training seeds.")
    trained_scenario = metadata.get("scenario")
    validate_observed_holdout(trained_scenario, prepared["evaluation_scenario_snapshot"])
    if isinstance(trained_scenario, dict) and trained_scenario.get("id") == prepared["evaluation_scenario_id"]:
        raise ValueError("Held-out evaluation must use a scenario different from the model's training scenario.")
    prepared.update(evaluation_only=True, evaluation_model_id=model_id)
    return _enqueue([_normalize_algorithm(model["algorithm"])], prepared, user_id=user_id)


def _enqueue(algorithms: list[str], settings: dict, *, user_id=None) -> int:
    global _active_job_id, _cancel_path
    with _worker_lock:
        if _active_job_id is not None:
            raise RuntimeError("Another training or evaluation job is active. Wait for it to finish or cancel it.")
        lease = workload_admission.acquire("training/evaluation")
        job_id = None
        try:
            job_dir = _job_root() / uuid4().hex
            job_dir.mkdir(parents=True)
            scenario_file = job_dir / "scenario.json"
            scenario_file.write_text(json.dumps(settings["scenario_snapshot"], indent=2), encoding="utf-8")
            evaluation_scenario_file = job_dir / "evaluation_scenario.json"
            evaluation_scenario_file.write_text(json.dumps(settings["evaluation_scenario_snapshot"], indent=2), encoding="utf-8")
            settings = {**settings, "scenario_file": str(scenario_file),
                        "evaluation_scenario_file": str(evaluation_scenario_file), "job_directory": str(job_dir)}
            commands = []
            for algorithm in algorithms:
                if settings.get("evaluation_only"):
                    model = database.get_rl_model_by_id(settings["evaluation_model_id"])
                    command = _evaluation_command([algorithm], settings, {algorithm: model["checkpoint_path"]})
                else:
                    output_path = job_dir / (algorithm + (".json" if algorithm == "ql" else ".zip"))
                    command = build_training_command(algorithm, settings, settings.get("advanced")) + ["--output", str(output_path)]
                commands.append(command)
            job_id = database.create_rl_training_job_with_items(
                user_id=user_id, algorithms=algorithms, settings=settings,
                log_path=str(job_dir / "progress.jsonl"), commands=commands,
            )
            _cancel_path = job_dir / "cancel.requested"
            _cancel_event.clear()
            _active_job_id = job_id
            threading.Thread(target=_run_job, args=(job_id, lease), daemon=True).start()
            return job_id
        except BaseException as exc:
            _active_job_id = None
            workload_admission.release(lease)
            if job_id is not None:
                database.update_rl_training_job(job_id, status="error", ended_at=_utc_now_iso(), message=f"Worker did not start: {exc}")
                for item in database.get_rl_training_job_items(job_id):
                    database.update_rl_training_job_item(item["id"], status="error", ended_at=_utc_now_iso(), message=str(exc))
            raise


def stop_training_job(job_id: int | None = None):
    with _worker_lock:
        if _active_job_id is None or (job_id is not None and job_id != _active_job_id):
            return
        job = database.get_rl_training_job(_active_job_id)
        if not job or job["status"] not in {"queued", "running", "stopping"}:
            return
        if _cancel_path is not None:
            _cancel_path.touch()
        _cancel_event.set()
        database.update_rl_training_job(_active_job_id, status="stopping",
            message="Cancellation requested; saving a partial model at the next simulation boundary.")


def active_job_id() -> int | None:
    with _worker_lock:
        return _active_job_id


def model_rows(limit: int = 200, algorithm: str | None = None) -> list[dict]:
    rows = []
    for model in database.list_rl_models(limit=limit, algorithm=algorithm):
        row = {**model, "algorithm": str(model["algorithm"]).upper(), "compatible": False,
               "compatibility_message": "", "controlled_junction": None, "checkpoints": []}
        normalized_algorithm = str(model["algorithm"]).lower()
        try:
            _normalize_algorithm(normalized_algorithm)
            metadata = artifact_metadata(normalized_algorithm, model.get("checkpoint_path") or "")
            row.update(compatible=True, controlled_junction=training_junction(metadata),
                       decision_interval_seconds=metadata.get("decision_interval_seconds", 5),
                       minimum_green_hold_seconds=metadata.get("minimum_green_hold_seconds", 10),
                       training_status=metadata.get("training_status", "unknown"))
        except (ValueError, KeyError, TypeError, OSError) as exc:
            row["compatibility_message"] = str(exc)
        for checkpoint in database.list_rl_checkpoints(model["id"]):
            item = {**checkpoint, "compatible": False, "compatibility_message": ""}
            try:
                _normalize_algorithm(normalized_algorithm)
                checkpoint_metadata = artifact_metadata(normalized_algorithm, checkpoint.get("path") or "")
                item["compatible"] = True
                if row["controlled_junction"] is None:
                    row.update(controlled_junction=training_junction(checkpoint_metadata),
                               decision_interval_seconds=checkpoint_metadata.get("decision_interval_seconds", 5),
                               minimum_green_hold_seconds=checkpoint_metadata.get("minimum_green_hold_seconds", 10),
                               training_status=checkpoint_metadata.get("training_status", "checkpoint"))
            except (ValueError, KeyError, TypeError, OSError) as exc:
                item["compatibility_message"] = str(exc)
            row["checkpoints"].append(item)
        rows.append(row)
    return rows


def training_status(job_id: int | None = None) -> dict:
    job = database.get_rl_training_job(job_id) if job_id else database.get_latest_rl_training_job()
    return {"job": job, "items": database.get_rl_training_job_items(job["id"]) if job else [],
            "log_lines": read_log_tail(job.get("log_path")) if job else [], "models": model_rows(),
            "active_job_id": _active_job_id}


def read_log_tail(log_path: str | None, *, limit: int = 160) -> list[dict]:
    if not log_path or not Path(log_path).is_file():
        return []
    # Bounded read: long jobs must not reread their entire log on every poll.
    with Path(log_path).open("rb") as stream:
        stream.seek(max(0, stream.seek(0, 2) - 131072))
        lines = stream.read().decode("utf-8", errors="replace").splitlines()[-limit:]
    records = []
    for line in lines:
        try:
            records.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return records


class TrainingCancelled(Exception):
    pass


def _check_cancelled():
    if _cancel_event.is_set():
        raise TrainingCancelled("Training cancelled. Saved checkpoints remain available.")


def _run_job(job_id: int, workload_lease=None):
    global _active_job_id, _active_process
    current_item = None
    log_path = None
    try:
        job = database.get_rl_training_job(job_id)
        if not job:
            raise RuntimeError(f"Training job #{job_id} disappeared before launch.")
        settings = _json_loads(job.get("settings_json"), {})
        items = database.get_rl_training_job_items(job_id)
        if not items:
            raise RuntimeError("Training job has no queued algorithms.")
        log_path = Path(job["log_path"])
        scenario_file = Path(settings["scenario_file"])
        scenario_bytes = scenario_file.read_bytes()
        scenario = json.loads(scenario_bytes)
        import hashlib
        if hashlib.sha256(json.dumps(scenario, sort_keys=True).encode()).hexdigest() != settings["scenario_sha256"]:
            raise RuntimeError("Saved scenario snapshot changed after the job was queued.")
        evaluation_scenario = json.loads(Path(settings["evaluation_scenario_file"]).read_bytes())
        if hashlib.sha256(json.dumps(evaluation_scenario, sort_keys=True).encode()).hexdigest() != settings["evaluation_scenario_sha256"]:
            raise RuntimeError("Saved held-out scenario snapshot changed after the job was queued.")
        _check_cancelled()
        database.update_rl_training_job(job_id, status="running", started_at=_utc_now_iso(), message="Job started.")
        model_paths = {}
        for item in items:
            current_item = item
            _check_cancelled()
            if settings.get("evaluation_only"):
                model = database.get_rl_model_by_id(settings["evaluation_model_id"])
                database.update_rl_training_job_item(item["id"], status="running", started_at=_utc_now_iso(), rl_model_id=model["id"])
                model_paths[item["algorithm"]] = model["checkpoint_path"]
            else:
                model_paths[item["algorithm"]] = _run_command_item(job_id, item, log_path, len(items))
        _check_cancelled()
        database.update_rl_training_job(job_id, current_algorithm="evaluation", current_item_id=None,
            progress_percent=90, message="Evaluating saved models against fixed-time on the held-out scenario snapshot.")
        for item in items:
            database.update_rl_training_job_item(item["id"], status="evaluating", message="Model saved; evaluation pending.")
        output_path = None
        for line in _process_lines(_evaluation_command(list(model_paths), settings, model_paths), log_path, "evaluation"):
            match = EVALUATION_RE.search(line)
            if match:
                output_path = match.group("path").strip()
        if not output_path or not Path(output_path).is_file():
            raise RuntimeError("Evaluation finished without saving a result file. Inspect the job log.")
        payload = json.loads(Path(output_path).read_text(encoding="utf-8"))
        expected_count = (1+len(model_paths))*len(settings["evaluation_seeds"].split(","))
        results = payload.get("results", [])
        if len(results) != expected_count or any(result.get("status") != "completed" for result in results):
            raise RuntimeError("Evaluation did not complete every controller/seed comparison.")
        _check_cancelled()
        for item in items:
            database.update_rl_training_job_item(item["id"], status="completed", progress_percent=100,
                evaluation_path=output_path, ended_at=_utc_now_iso(), message="Training and evaluation completed." if not settings.get("evaluation_only") else "Evaluation completed.")
        provenance = settings.get("scenario_snapshot", {}).get("engine_config", {}).get("demand_source", {}).get("kind", "synthetic")
        database.update_rl_training_job(job_id, status="completed", progress_percent=100, ended_at=_utc_now_iso(),
            message=f"Job completed. {provenance.capitalize()} inputs; results require separate validation before effectiveness claims.")
    except (Exception, KeyboardInterrupt) as exc:
        interrupted = isinstance(exc, (TrainingCancelled, KeyboardInterrupt)) or _cancel_event.is_set()
        status = "interrupted" if interrupted else "error"
        message = str(exc) or "Job interrupted"
        for item in database.get_rl_training_job_items(job_id):
            if item["status"] in {"queued", "running", "evaluating"} or (current_item and current_item["id"] == item["id"]):
                database.update_rl_training_job_item(item["id"], status=status, ended_at=_utc_now_iso(), message=message)
        database.update_rl_training_job(job_id, status=status, ended_at=_utc_now_iso(), message=message)
        if log_path is not None:
            _append_log(log_path, {"type": status, "text": message})
    finally:
        workload_admission.release(workload_lease)
        with _worker_lock:
            if _active_job_id == job_id:
                _active_job_id = None
                _active_process = None


def _run_command_item(job_id: int, item: dict, log_path: Path, item_count: int) -> str:
    item_id, algorithm = item["id"], item["algorithm"]
    database.update_rl_training_job(job_id, current_algorithm=algorithm, current_item_id=item_id,
                                   message=f"Training {ALGORITHM_LABELS[algorithm]}.")
    database.update_rl_training_job_item(item_id, status="running", started_at=_utc_now_iso())
    artifact_path = None
    model_id = None
    for line in _process_lines(_json_loads(item["command_json"], []), log_path, algorithm):
        progress = _parse_progress(line)
        if progress:
            database.update_rl_training_job_item(item_id, **progress)
            overall = 90*(item["sequence_index"] + progress["progress_percent"]/100)/item_count
            database.update_rl_training_job(job_id, progress_percent=round(overall, 3))
        match = ARTIFACT_RE.search(line)
        if match:
            artifact_path = match.group("path").strip()
            database.update_rl_training_job_item(item_id, artifact_path=artifact_path)
        match = METADATA_RE.search(line)
        if match:
            database.update_rl_training_job_item(item_id, metadata_path=match.group("path").strip())
        match = MODEL_ID_RE.search(line)
        if match:
            model_id = int(match.group("id"))
            database.update_rl_training_job_item(item_id, rl_model_id=model_id)
    if not artifact_path or not model_id or not database.get_rl_model_by_id(model_id):
        raise RuntimeError(f"{algorithm.upper()} finished without a registered model artifact. Inspect the job log.")
    artifact_metadata(algorithm, artifact_path)
    database.update_rl_training_job_item(item_id, status="completed", progress_percent=100,
                                        message="Model saved; evaluation pending.")
    return artifact_path


def _evaluation_command(algorithms, settings, model_paths):
    return build_evaluation_command(algorithms, settings, model_paths) + [
        "--output", str(Path(settings["job_directory"]) / "evaluation.json"),
        "--record-timeline-seed", "-1",
    ]


def _process_lines(command: list[str], log_path: Path, algorithm: str):
    global _active_process
    _check_cancelled()
    _append_log(log_path, {"type": "command", "algorithm": algorithm, "text": " ".join(command)})
    process = _start_process(command)
    with _worker_lock:
        _active_process = process
    threading.Thread(target=_watch_cancellation, args=(process,), daemon=True).start()
    tail = []
    try:
        assert process.stdout is not None
        for raw_line in process.stdout:
            line = raw_line.rstrip()
            if not line:
                continue
            tail = (tail + [line])[-5:]
            _append_log(log_path, {"type": "stdout", "algorithm": algorithm, "text": line})
            yield line
        return_code = process.wait()
        _check_cancelled()
        if return_code == 130:
            raise TrainingCancelled("Training interrupted after saving its partial artifact.")
        if return_code != 0:
            raise RuntimeError(f"{algorithm.upper()} exited with code {return_code}: " + " | ".join(tail)[-1500:])
    finally:
        if process.poll() is None:
            process.terminate()
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait()
        if process.stdout:
            process.stdout.close()
        with _worker_lock:
            if _active_process is process:
                _active_process = None


def _start_process(command: list[str]) -> subprocess.Popen:
    environment = {**os.environ, "SMARTFLOW_DB_PATH": str(config.DB_PATH),
                   "SMARTFLOW_TRAINING_CANCEL_FILE": str(_cancel_path), "PYTHONIOENCODING": "utf-8",
                   "OMP_NUM_THREADS": "1", "MKL_NUM_THREADS": "1"}
    return subprocess.Popen(command, cwd=str(ROOT), stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                            text=True, encoding="utf-8", errors="replace", bufsize=1, env=environment,
                            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0) if os.name == "nt" else 0)


def _watch_cancellation(process):
    while process.poll() is None:
        if _cancel_event.wait(timeout=.5):
            try:
                process.wait(timeout=30)
            except subprocess.TimeoutExpired:
                process.terminate()
                try:
                    process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    process.kill()
            return


def _parse_progress(line: str) -> dict | None:
    match = PROGRESS_RE.search(line)
    reward = REWARD_RE.search(line)
    if not match or not reward:
        return None
    payload = {"latest_episode": int(match.group("episode")), "latest_reward": float(reward.group("reward")),
               "progress_percent": round(max(0, min(float(match.group("percent")), 100)), 3), "message": line}
    epsilon = EPSILON_RE.search(line)
    if epsilon:
        payload["latest_epsilon"] = float(epsilon.group("epsilon"))
    timesteps = TIMESTEPS_RE.search(line)
    if timesteps:
        payload["latest_timesteps"] = int(timesteps.group("timesteps"))
    return payload


def _append_log(log_path: Path, record: dict):
    with log_path.open("a", encoding="utf-8") as stream:
        stream.write(json.dumps({"ts": _utc_now_iso(), **record}, ensure_ascii=True) + "\n")
