from __future__ import annotations

import argparse
import gzip
import json
import statistics
import sys
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools.training_inputs import load_training_scenario
from simulation.training_control import check_training_cancelled

import config
import database
from services.timeline_artifacts import timeline_artifact_paths
from services.observation_identity import has_observed_inputs, validate_observed_holdout
from simulation.model_contract import artifact_metadata
from services.rl_reporting_service import (
    build_combined_ranking,
    load_model_learning_summary,
    primary_evaluation_score,
)
from simulation.rl_policy_runtime import RuntimePolicy, load_runtime_policy
from simulation.scenario_config import number
from simulation.traffic_engine import STEP_LENGTH
from simulation.traffic_engine import TrafficEngine


DEFAULT_SEEDS = (11, 22, 33, 44, 55)
SUPPORTED_CONTROLLERS = ("fixed-time", "ql", "dql", "ppo")


def _utc_now_iso() -> str:
    return datetime.now(UTC).isoformat()


def _parse_seed_set(raw_seed_set: str) -> tuple[int, ...]:
    seeds = tuple(
        int(seed.strip())
        for seed in str(raw_seed_set or "").split(",")
        if seed.strip()
    )
    if not seeds:
        raise argparse.ArgumentTypeError("seed set must contain at least one integer.")
    return seeds


def _parse_controller_set(raw_controllers: str) -> tuple[str, ...]:
    controllers = tuple(
        controller.strip().lower().replace("_", "-")
        for controller in str(raw_controllers or "").split(",")
        if controller.strip()
    )
    unsupported = sorted(set(controllers) - set(SUPPORTED_CONTROLLERS))
    if unsupported:
        raise argparse.ArgumentTypeError(f"unsupported controller(s): {', '.join(unsupported)}")
    return controllers or SUPPORTED_CONTROLLERS


def _latest_model_path(controller: str) -> Path | None:
    model_dir = ROOT / "data" / "models" / controller
    if not model_dir.exists():
        return None
    if controller == "ql":
        patterns = ("*.json",)
        excluded_suffixes = (".metadata.json",)
    elif controller in {"dql", "ppo"}:
        patterns = ("*.zip",)
        excluded_suffixes = ()
    else:
        patterns = ("*.zip", "*.json")
        excluded_suffixes = (".metadata.json",)

    candidates = []
    for pattern in patterns:
        for path in model_dir.glob(pattern):
            if any(path.name.endswith(suffix) for suffix in excluded_suffixes):
                continue
            candidates.append(path)
    candidates = sorted(
        candidates,
        key=lambda path: path.stat().st_mtime,
        reverse=True,
    )
    return candidates[0] if candidates else None


def _artifact_paths(run_id: int) -> tuple[Path, Path, Path]:
    return timeline_artifact_paths(run_id)


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


def _find_or_create_scenario(scenario: dict) -> int:
    for row in database.get_scenarios(include_archived=True):
        if (
            str(row.get("name") or "") == scenario["name"]
            and str(row.get("intersection_id") or "") == scenario["intersection_id"]
        ):
            return int(row["id"])
    return int(
        database.create_scenario(
            name=scenario["name"],
            intersection_id=scenario["intersection_id"],
            description="Offline RL evaluation scenario.",
            traffic_density=scenario["traffic_density"],
            pedestrian_density=scenario["pedestrian_density"],
            emergency_mode=scenario["emergency_mode"],
            road_constraint=scenario["road_constraint"],
            is_official=0,
        )
    )


def _find_rl_model_id_by_path(model_path: Path | None) -> int | None:
    if model_path is None:
        return None
    with database.get_db() as conn:
        cursor = conn.execute(
            "SELECT id FROM rl_models WHERE checkpoint_path = ? ORDER BY id DESC LIMIT 1",
            (str(model_path),),
        )
        row = cursor.fetchone()
        return int(row["id"]) if row else None


def _reset_official_metrics(engine: TrafficEngine):
    engine.reset_metrics()


def _configure_engine_for_controller(
    engine: TrafficEngine,
    controller: str,
    policies: dict[str, RuntimePolicy],
    *,
    decision_interval_seconds: float,
    minimum_green_hold_seconds: float,
):
    if controller == "fixed-time":
        engine.disable_rl_control()
        return
    if controller in {"ql", "dql", "ppo"}:
        if controller not in policies:
            raise ValueError(f"{controller.upper()} controller requires a runtime policy.")
        engine.set_runtime_policy(
            policies[controller],
            decision_interval=decision_interval_seconds,
            minimum_green_hold=minimum_green_hold_seconds,
        )
        return
    raise ValueError(f"Unsupported controller: {controller}")


def _build_manifest(
    *,
    run_id: int,
    scenario_id: int,
    scenario: dict,
    controller: str,
    engine: TrafficEngine,
    requested_duration_seconds: float,
    frame_count: int,
    raw_path: Path,
    gzip_path: Path,
    manifest_path: Path,
    compression: dict,
) -> dict:
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
            "seed": engine.seed,
        },
        "scenario": {
            "id": scenario_id,
            "name": scenario["name"],
            "intersection_id": engine.intersection_id,
        },
        "controller": {
            "type": engine.controller_type,
            "label": engine.control_mode_label,
            "provenance": controller,
            "provenance_label": engine.controller_provenance_label,
        },
        "timeline": {
            "requested_duration_seconds": float(requested_duration_seconds),
            "actual_duration_seconds": float(engine.simulation_time),
            "step_length_seconds": STEP_LENGTH,
            "frame_count": int(frame_count),
            "estimated_frame_count": int(round(requested_duration_seconds / STEP_LENGTH)) + 1,
        },
        "artifacts": {
            "timeline_jsonl": str(raw_path),
            "timeline_jsonl_gz": str(gzip_path),
            "manifest_json": str(manifest_path),
            "timeline_path_canonical": str(gzip_path if gzip_path.exists() else raw_path),
            "compression": compression,
        },
    }


def _run_controller_once(
    *,
    controller: str,
    seed: int,
    scenario: dict,
    scenario_id: int,
    duration_seconds: float,
    warmup_seconds: float,
    decision_interval_seconds: float,
    minimum_green_hold_seconds: float,
    policies: dict[str, RuntimePolicy],
    model_ids: dict[str, int | None],
    record_timeline: bool,
) -> dict:
    duration_seconds = number(duration_seconds, "measurement duration", STEP_LENGTH, 86400)
    warmup_seconds = number(warmup_seconds, "warmup", 0, 86400)
    for value in (duration_seconds, warmup_seconds):
        if abs(value/STEP_LENGTH-round(value/STEP_LENGTH)) > 1e-7:
            raise ValueError("Evaluation durations must be multiples of 0.1 seconds")
    total_duration_seconds = float(warmup_seconds) + float(duration_seconds)
    engine = TrafficEngine(seed=seed)
    engine.configure_from_scenario(scenario)
    _configure_engine_for_controller(
        engine,
        controller,
        policies,
        decision_interval_seconds=decision_interval_seconds,
        minimum_green_hold_seconds=minimum_green_hold_seconds,
    )

    if warmup_seconds > 0:
        engine.disable_rl_control()

    run_id = database.create_run(
        scenario_id=scenario_id,
        user_id=None,
        run_mode="pre-record" if record_timeline else "evaluation",
        control_mode=controller,
        rl_model_id=model_ids.get(controller),
        status="running",
        seed=seed,
        notes=f"Offline evaluation for {controller}.",
    )

    raw_path = gzip_path = manifest_path = None
    timeline_file = None
    frame_count = 0
    metrics = {}
    official_metrics_reset = warmup_seconds <= 0

    try:
        engine.start(duration_limit=total_duration_seconds)
        engine.run_id = str(run_id)
        if engine.status == "error":
            raise RuntimeError(engine.last_error or "Python engine failed to start.")

        if record_timeline:
            raw_path, gzip_path, manifest_path = _artifact_paths(run_id)
            timeline_file = raw_path.open("w", encoding="utf-8")
            timeline_file.write(json.dumps(engine.to_dict()) + "\n")
            frame_count += 1

        while engine.status == "running":
            check_training_cancelled()
            engine.step(1)
            if not official_metrics_reset and engine.simulation_time >= warmup_seconds:
                _reset_official_metrics(engine)
                official_metrics_reset = True
                _configure_engine_for_controller(engine, controller, policies, decision_interval_seconds=decision_interval_seconds, minimum_green_hold_seconds=minimum_green_hold_seconds)
            if record_timeline and engine.status in {"running", "completed"}:
                timeline_file.write(json.dumps(engine.to_dict()) + "\n")
                frame_count += 1

        metrics = dict(engine.to_dict().get("metrics", {}))
        metrics["experiment"] = engine.experiment_metadata()
        metrics["rl_total_phase_switches"] = int(getattr(engine, "rl_total_phase_switches", 0) or 0)
        database.save_run_metrics(
            run_id=run_id,
            avg_waiting_time=metrics.get("avg_wait", 0),
            avg_queue_length=metrics.get("avg_queue", 0),
            max_queue_length=metrics.get("max_queue", 0),
            throughput=metrics.get("throughput", 0),
            avg_pedestrian_delay=metrics.get("avg_ped_delay", 0),
            raw_metrics_json=json.dumps(metrics),
        )

        timeline_path = None
        if record_timeline and timeline_file is not None:
            timeline_file.close()
            timeline_file = None
            compression = _write_gzip_copy(raw_path, gzip_path) if config.TIMELINE_GZIP_ENABLED else {}
            manifest = _build_manifest(
                run_id=run_id,
                scenario_id=scenario_id,
                scenario=scenario,
                controller=controller,
                engine=engine,
                requested_duration_seconds=total_duration_seconds,
                frame_count=frame_count,
                raw_path=raw_path,
                gzip_path=gzip_path,
                manifest_path=manifest_path,
                compression=compression,
            )
            manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
            timeline_path = str(gzip_path if gzip_path.exists() else raw_path)

        database.update_run(
            run_id,
            status="completed",
            end_time=_utc_now_iso(),
            duration_seconds=float(engine.simulation_time),
            timeline_path=timeline_path,
            notes=f"Offline evaluation completed for {controller}.",
        )
        return {
            "run_id": run_id,
            "controller": controller,
            "experiment": engine.experiment_metadata(),
            "seed": seed,
            "status": "completed",
            "duration_seconds": float(engine.simulation_time),
            "metrics": metrics,
            "timeline_path": timeline_path,
        }
    except (Exception, KeyboardInterrupt) as exc:
        database.update_run(
            run_id,
            status="interrupted" if isinstance(exc, KeyboardInterrupt) else "error",
            end_time=_utc_now_iso(),
            duration_seconds=float(getattr(engine, "simulation_time", 0.0) or 0.0),
            notes=str(exc),
        )
        raise
    finally:
        if timeline_file is not None:
            timeline_file.close()
        engine.stop()


def _metric_summary(values: list[float]) -> dict:
    if not values:
        return {"mean": 0, "min": 0, "max": 0, "std": 0}
    return {
        "mean": round(statistics.fmean(values), 6),
        "min": round(min(values), 6),
        "max": round(max(values), 6),
        "std": round(statistics.pstdev(values), 6) if len(values) > 1 else 0.0,
    }


def _build_summary(results: list[dict]) -> dict:
    metric_keys = (
        "avg_wait",
        "avg_queue",
        "max_queue",
        "throughput",
        "avg_ped_delay",
        "avg_travel_time",
        "avg_admitted_boundary_wait",
        "boundary_wait_seconds",
        "unfinished_vehicles",
        "pending_demand",
        "dropped_vehicles",
        "requested_vehicles",
        "vehicle_conservation_error",
        "pedestrian_conservation_error",
        "rl_total_phase_switches",
    )
    summary: dict[str, dict] = {}
    for controller in sorted({result["controller"] for result in results}):
        controller_results = [result for result in results if result["controller"] == controller]
        summary[controller] = {
            metric_key: _metric_summary(
                [float(result["metrics"].get(metric_key, 0) or 0) for result in controller_results]
            )
            for metric_key in metric_keys
        }
    return summary


def _build_model_learning(
    *,
    controllers: tuple[str, ...],
    model_paths: dict[str, Path | None],
    model_ids: dict[str, int | None],
) -> dict:
    learning = {}
    for controller in controllers:
        if controller not in {"ql", "dql", "ppo"}:
            continue
        model_id = model_ids.get(controller)
        model_record = database.get_rl_model_by_id(model_id) if model_id else None
        learning[controller] = load_model_learning_summary(
            controller,
            model_paths.get(controller),
            model_id=model_id,
            model_record=model_record,
        )
    return learning


def _update_model_evaluation_scores(summary: dict, model_ids: dict[str, int | None]):
    for controller, model_id in model_ids.items():
        if not model_id:
            continue
        score = primary_evaluation_score(summary.get(controller))
        if score is None:
            continue
        database.update_rl_model_evaluation_score(model_id, score)


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Evaluate SMARTFLOW controllers using the fixed comparison protocol."
    )
    parser.add_argument("--controllers", type=_parse_controller_set, default=SUPPORTED_CONTROLLERS)
    parser.add_argument("--seeds", type=_parse_seed_set, default=DEFAULT_SEEDS)
    parser.add_argument("--duration-seconds", type=float, default=300.0)
    parser.add_argument("--warmup-seconds", type=float, default=20.0)
    parser.add_argument("--decision-interval-seconds", type=float, default=5.0)
    parser.add_argument("--minimum-green-hold-seconds", type=float, default=10.0)
    parser.add_argument("--intersection-id", default="tagum_network")
    parser.add_argument("--scenario-id", type=int, help="Use the complete saved scenario, including native engine_config")
    parser.add_argument("--scenario-file", type=Path, help="Immutable scenario snapshot for this job")
    parser.add_argument("--scenario-name", default="SMARTFLOW Evaluation Scenario")
    parser.add_argument("--traffic-density", default="medium")
    parser.add_argument("--pedestrian-density", default="medium")
    parser.add_argument("--emergency-mode", default="disabled")
    parser.add_argument("--road-constraint", default="None")
    parser.add_argument("--ql-model", type=Path, default=None)
    parser.add_argument("--dql-model", type=Path, default=None)
    parser.add_argument("--ppo-model", type=Path, default=None)
    parser.add_argument("--record-timeline-seed", type=int, default=None)
    parser.add_argument("--output", type=Path, default=None)
    return parser


def main() -> int:
    args = _build_parser().parse_args()
    database.init_db()

    scenario = {
        "name": args.scenario_name,
        "intersection_id": args.intersection_id,
        "traffic_density": args.traffic_density,
        "pedestrian_density": args.pedestrian_density,
        "emergency_mode": args.emergency_mode,
        "road_constraint": args.road_constraint,
    }
    scenario = load_training_scenario(args, scenario)

    model_paths = {
        "ql": args.ql_model or _latest_model_path("ql"),
        "dql": args.dql_model or _latest_model_path("dql"),
        "ppo": args.ppo_model or _latest_model_path("ppo"),
    }
    policies: dict[str, RuntimePolicy] = {}
    model_ids: dict[str, int | None] = {}
    for controller in ("ql", "dql", "ppo"):
        if controller not in args.controllers:
            continue
        model_path = model_paths[controller]
        if model_path is None:
            raise SystemExit(f"No {controller.upper()} model found. Pass --{controller}-model or train {controller.upper()} first.")
        metadata = artifact_metadata(controller, model_path)
        trained_scenario = metadata.get("scenario")
        if not isinstance(trained_scenario, dict):
            if has_observed_inputs(scenario):
                raise ValueError("Model lacks its training snapshot for held-out observed evaluation.")
        else:
            validate_observed_holdout(trained_scenario, scenario)
        policies[controller] = load_runtime_policy(controller, model_path)
        model_ids[controller] = _find_rl_model_id_by_path(model_path)

    scenario_id = args.scenario_id or _find_or_create_scenario(scenario)

    timeline_seed = args.record_timeline_seed
    if timeline_seed is None:
        timeline_seed = args.seeds[0]

    print("Starting SMARTFLOW controller evaluation")
    print(f"Scenario ID: {scenario_id}, scenario: {json.dumps(scenario, sort_keys=True)}")
    print(f"Controllers: {args.controllers}, seeds: {args.seeds}")
    for controller, model_path in model_paths.items():
        if controller in args.controllers and model_path:
            print(f"{controller.upper()} model: {model_path}")
    print(f"Recording replay timelines for seed: {timeline_seed}")

    results = []
    for controller in args.controllers:
        for seed in args.seeds:
            record_timeline = int(seed) == int(timeline_seed)
            result = _run_controller_once(
                controller=controller,
                seed=int(seed),
                scenario=scenario,
                scenario_id=scenario_id,
                duration_seconds=args.duration_seconds,
                warmup_seconds=args.warmup_seconds,
                decision_interval_seconds=args.decision_interval_seconds,
                minimum_green_hold_seconds=args.minimum_green_hold_seconds,
                policies=policies,
                model_ids=model_ids,
                record_timeline=record_timeline,
            )
            results.append(result)
            print(
                "{controller} seed={seed}: avg_wait={avg_wait}, avg_queue={avg_queue}, "
                "throughput={throughput}, run_id={run_id}, timeline={timeline}".format(
                    controller=controller,
                    seed=seed,
                    avg_wait=result["metrics"].get("avg_wait", 0),
                    avg_queue=result["metrics"].get("avg_queue", 0),
                    throughput=result["metrics"].get("throughput", 0),
                    run_id=result["run_id"],
                    timeline=result["timeline_path"] or "not-recorded",
                )
            )

    output_path = args.output or (
        ROOT
        / "data"
        / "generated"
        / "evaluations"
        / f"controller_eval_{datetime.now(UTC).strftime('%Y%m%d_%H%M%S')}.json"
    )
    output_path.parent.mkdir(parents=True, exist_ok=True)
    summary = _build_summary(results)
    model_learning = _build_model_learning(
        controllers=args.controllers,
        model_paths=model_paths,
        model_ids=model_ids,
    )
    _update_model_evaluation_scores(summary, model_ids)

    payload = {
        "generated_at": _utc_now_iso(),
        "protocol": "compare_v1",
        "scenario_id": scenario_id,
        "scenario": scenario,
        "controllers": list(args.controllers),
        "seeds": list(args.seeds),
        "duration_seconds": args.duration_seconds,
        "warmup_seconds": args.warmup_seconds,
        "model_paths": {
            controller: str(model_paths[controller])
            for controller in args.controllers
            if controller in model_paths and model_paths[controller]
        },
        "results": results,
        "summary": summary,
        "model_learning": model_learning,
        "combined_ranking": build_combined_ranking(summary, model_learning),
    }
    output_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    print(f"Saved evaluation summary: {output_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
