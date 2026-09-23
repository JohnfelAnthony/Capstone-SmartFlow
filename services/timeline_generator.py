import gzip
import json
import logging
import threading
from datetime import UTC, datetime
from pathlib import Path

import config
import database
from simulation.traffic_engine import TrafficEngine

logger = logging.getLogger(__name__)


def _utc_now_iso() -> str:
    return datetime.now(UTC).isoformat()


def _save_metrics(run_id: int, metrics: dict):
    database.save_run_metrics(
        run_id=run_id,
        avg_waiting_time=metrics.get("avg_wait", 0),
        avg_queue_length=metrics.get("avg_queue", 0),
        max_queue_length=metrics.get("max_queue", 0),
        throughput=metrics.get("throughput", 0),
        avg_pedestrian_delay=metrics.get("avg_ped_delay", 0),
        raw_metrics_json=json.dumps(metrics),
    )


def _artifact_paths(run_id: int) -> tuple[Path, Path, Path]:
    timeline_dir = Path("assets/generated/timelines")
    timeline_dir.mkdir(parents=True, exist_ok=True)
    raw_path = timeline_dir / f"run_{run_id}.jsonl"
    gzip_path = timeline_dir / f"run_{run_id}.jsonl.gz"
    manifest_path = timeline_dir / f"run_{run_id}.manifest.json"
    return raw_path, gzip_path, manifest_path


def _estimated_frame_count(duration_limit: int, step_length: float) -> int:
    safe_step_length = max(float(step_length or 0.1), 0.001)
    return int(max(1, round((duration_limit or 0) / safe_step_length)) + 1)


def _write_gzip_copy(source_path: Path, gzip_path: Path) -> dict:
    with source_path.open("rb") as src, gzip.open(gzip_path, "wb", compresslevel=6) as dst:
        while True:
            chunk = src.read(1024 * 1024)
            if not chunk:
                break
            dst.write(chunk)
    return {
        "algorithm": "gzip",
        "raw_bytes": source_path.stat().st_size,
        "compressed_bytes": gzip_path.stat().st_size,
    }


def _prune_old_raw_timelines():
    keep_recent_raw = max(int(config.TIMELINE_KEEP_RECENT_RAW), 0)
    timeline_dir = Path("assets/generated/timelines")
    raw_files = sorted(
        timeline_dir.glob("run_*.jsonl"),
        key=lambda path: path.stat().st_mtime,
        reverse=True,
    )
    for raw_path in raw_files[keep_recent_raw:]:
        gzip_path = raw_path.with_suffix(".jsonl.gz")
        if gzip_path.exists():
            try:
                raw_path.unlink(missing_ok=True)
            except OSError:
                logger.warning("Failed to prune raw timeline %s", raw_path)


def _build_manifest(
    *,
    run_id: int,
    scenario: dict | None,
    engine: TrafficEngine,
    duration_limit: int,
    frame_count: int,
    raw_path: Path,
    gzip_path: Path,
    manifest_path: Path,
    compression: dict | None,
) -> dict:
    controller_provenance = str(
        getattr(engine, "controller_provenance", "")
        or getattr(engine, "controller_type", "")
        or "unknown"
    )
    controller_provenance_label = str(
        getattr(engine, "controller_provenance_label", "")
        or controller_provenance.replace("-", " ").title()
    )
    actual_duration = float(getattr(engine, "simulation_time", 0) or 0)
    step_length = float(getattr(engine, "step_length", 0.1) or 0.1)
    return {
        "manifest_version": 2,
        "experiment": engine.experiment_metadata(),
        "network": engine.network.payload,
        "generated_at": _utc_now_iso(),
        "app": {
            "name": config.APP_NAME,
            "version": config.APP_VERSION,
        },
        "run": {
            "id": run_id,
            "mode": "pre-record",
            "status": "completed",
            "seed": getattr(engine, "seed", None),
        },
        "scenario": {
            "id": scenario.get("id") if scenario else None,
            "name": scenario.get("name") if scenario else None,
            "intersection_id": getattr(engine, "intersection_id", None),
        },
        "controller": {
            "type": getattr(engine, "controller_type", "unknown"),
            "label": getattr(engine, "control_mode_label", "Unknown Controller"),
            "provenance": controller_provenance,
            "provenance_label": controller_provenance_label,
        },
        "timeline": {
            "requested_duration_seconds": float(duration_limit or 0),
            "actual_duration_seconds": actual_duration,
            "step_length_seconds": step_length,
            "frame_count": int(frame_count),
            "estimated_frame_count": _estimated_frame_count(duration_limit, step_length),
        },
        "artifacts": {
            "timeline_jsonl": str(raw_path),
            "timeline_jsonl_gz": str(gzip_path),
            "manifest_json": str(manifest_path),
            "timeline_path_canonical": str(gzip_path if gzip_path.exists() else raw_path),
            "compression": compression or {},
        },
    }


def generate_timeline(
    scenario_id: int,
    duration_limit: int,
    run_id: int,
    on_complete=None,
    on_progress=None,
    *,
    seed: int | None = None,
    control_mode: str | None = None,
):
    """Run the Python engine headlessly as fast as possible to generate a timeline."""

    def _worker():
        engine = None
        timeline_path = None
        try:
            engine = TrafficEngine(seed=seed)
            timeline_path, gzip_path, manifest_path = _artifact_paths(run_id)
            estimated_frame_count = _estimated_frame_count(duration_limit, engine.step_length)
            scenario = database.get_scenario_by_id(scenario_id)
            if not scenario:
                raise ValueError("Scenario not found")
            engine.configure_from_scenario(scenario)
            from services.native_controller import apply_controller
            apply_controller(engine, control_mode)
            engine.start(duration_limit)
            engine.run_id = str(run_id)
            if engine.status == "error":
                logger.error("Timeline generator failed to start: %s", engine.last_error)
                database.update_run(
                    run_id,
                    run_mode="pre-record",
                    status="error",
                    end_time=_utc_now_iso(),
                    duration_seconds=0,
                    timeline_path=str(timeline_path),
                    notes=engine.last_error or "Timeline generator failed to start.",
                )
                database.log_audit_event(
                    action="error_timeline_generation",
                    target="simulation_runs",
                    details=f"Run ID={run_id} failed to start timeline generation: {engine.last_error}",
                )
                if on_complete:
                    on_complete("error", engine.last_error)
                return

            with timeline_path.open("w", encoding="utf-8") as timeline_file:
                frame_count = 0
                timeline_file.write(json.dumps(engine.to_dict()) + "\n")
                frame_count += 1
                if on_progress:
                    on_progress(
                        {
                            "progress_percent": 1,
                            "frame_count": frame_count,
                            "estimated_frame_count": estimated_frame_count,
                        }
                    )

                last_progress = 0
                while engine.status == "running":
                    engine.step(1)
                    if engine.status in {"running", "completed"}:
                        timeline_file.write(json.dumps(engine.to_dict()) + "\n")
                        frame_count += 1

                    if on_progress and duration_limit > 0:
                        current_progress = int((engine.simulation_time / duration_limit) * 100)
                        if current_progress > last_progress:
                            last_progress = current_progress
                            on_progress(
                                {
                                    "progress_percent": min(current_progress, 100),
                                    "frame_count": frame_count,
                                    "estimated_frame_count": estimated_frame_count,
                                }
                            )

            final_metrics = {**engine.to_dict().get("metrics", {}), "experiment": engine.experiment_metadata()}
            _save_metrics(run_id, final_metrics)
            compression = {}
            if config.TIMELINE_GZIP_ENABLED:
                compression = _write_gzip_copy(timeline_path, gzip_path)

            manifest = _build_manifest(
                run_id=run_id,
                scenario=scenario,
                engine=engine,
                duration_limit=duration_limit,
                frame_count=frame_count,
                raw_path=timeline_path,
                gzip_path=gzip_path,
                manifest_path=manifest_path,
                compression=compression,
            )
            manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")

            canonical_timeline_path = gzip_path if gzip_path.exists() else timeline_path
            database.update_run(
                run_id,
                run_mode="pre-record",
                status="completed",
                control_mode=engine.controller_provenance,
                rl_model_id=(getattr(engine.runtime_policy, "artifact_metadata", {}) or {}).get("model_id"),
                end_time=_utc_now_iso(),
                duration_seconds=float(engine.simulation_time),
                timeline_path=str(canonical_timeline_path),
                notes=f"Timeline generated with {frame_count} recorded frames.",
            )
            database.log_audit_event(
                action="complete_timeline_generation",
                target="simulation_runs",
                details=(
                    f"Run ID={run_id} completed timeline generation with "
                    f"{frame_count} frames at {canonical_timeline_path}."
                ),
            )
            if on_progress:
                on_progress(
                    {
                        "progress_percent": 100,
                        "frame_count": frame_count,
                        "estimated_frame_count": estimated_frame_count,
                    }
                )

            _prune_old_raw_timelines()

            if on_complete:
                on_complete(
                    "completed",
                    {
                        "timeline_path": str(canonical_timeline_path),
                        "raw_timeline_path": str(timeline_path),
                        "gzip_timeline_path": str(gzip_path) if gzip_path.exists() else None,
                        "manifest_path": str(manifest_path),
                        "frame_count": frame_count,
                        "estimated_frame_count": estimated_frame_count,
                        "controller_provenance": manifest["controller"]["provenance"],
                        "controller_provenance_label": manifest["controller"]["provenance_label"],
                        "control_mode_label": manifest["controller"]["label"],
                    },
                )

        except Exception as exc:
            logger.exception("Timeline generation failed")
            database.update_run(
                run_id,
                run_mode="pre-record",
                status="error",
                end_time=_utc_now_iso(),
                duration_seconds=float(getattr(engine, "simulation_time", 0) or 0),
                timeline_path=str(timeline_path) if timeline_path is not None else None,
                notes=str(exc),
            )
            database.log_audit_event(
                action="error_timeline_generation",
                target="simulation_runs",
                details=f"Run ID={run_id} failed during timeline generation: {exc}",
            )
            if on_complete:
                on_complete("error", str(exc))
        finally:
            if engine is not None:
                engine.stop()

    thread = threading.Thread(target=_worker, daemon=True)
    thread.start()
    return thread
