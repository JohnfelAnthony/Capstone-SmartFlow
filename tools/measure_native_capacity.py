"""Measure native simulation and recording cost on the current machine.

Run from the SmartFlow root with its virtual-environment Python. Measurements
include full per-tick recording serialization and compact render-frame encoding.
"""
from __future__ import annotations

import argparse
import ctypes
import gzip
import json
import os
import platform
import statistics
import time
from pathlib import Path

from services.render_frame_service import build_render_frame
from simulation.traffic_engine import TrafficEngine


def _peak_rss_bytes() -> int | None:
    if os.name != "nt":
        return None

    class ProcessMemoryCounters(ctypes.Structure):
        _fields_ = [("cb", ctypes.c_ulong), ("PageFaultCount", ctypes.c_ulong),
                   ("PeakWorkingSetSize", ctypes.c_size_t), ("WorkingSetSize", ctypes.c_size_t),
                   ("QuotaPeakPagedPoolUsage", ctypes.c_size_t), ("QuotaPagedPoolUsage", ctypes.c_size_t),
                   ("QuotaPeakNonPagedPoolUsage", ctypes.c_size_t), ("QuotaNonPagedPoolUsage", ctypes.c_size_t),
                   ("PagefileUsage", ctypes.c_size_t), ("PeakPagefileUsage", ctypes.c_size_t)]

    counters = ProcessMemoryCounters()
    counters.cb = ctypes.sizeof(counters)
    current_process = ctypes.windll.kernel32.GetCurrentProcess
    current_process.restype = ctypes.c_void_p
    process_memory = ctypes.windll.psapi.GetProcessMemoryInfo
    process_memory.argtypes = [ctypes.c_void_p, ctypes.POINTER(ProcessMemoryCounters), ctypes.c_ulong]
    process_memory.restype = ctypes.c_int
    if not process_memory(current_process(), ctypes.byref(counters), counters.cb):
        return None
    return int(counters.PeakWorkingSetSize)


def _percentile(values: list[float], fraction: float) -> float:
    ordered = sorted(values)
    return ordered[min(len(ordered) - 1, round((len(ordered) - 1) * fraction))]


def measure_case(density: str, duration_seconds: int, seed: int, artifacts: Path) -> dict:
    engine = TrafficEngine(seed=seed)
    engine.configure(traffic_density=density, pedestrian_density="high")
    raw_path = artifacts / f"{density.replace(' ', '_')}.jsonl"
    gzip_path = artifacts / f"{density.replace(' ', '_')}.jsonl.gz"
    step_ms: list[float] = []
    full_frame_ms: list[float] = []
    compact_frame_ms: list[float] = []
    peak_vehicles = 0
    peak_pedestrians = 0
    started = time.perf_counter()
    engine.start(duration_seconds)
    with raw_path.open("wb") as raw:
        while True:
            frame_started = time.perf_counter()
            state = engine.to_dict()
            raw.write((json.dumps(state, separators=(",", ":")) + "\n").encode("utf-8"))
            full_frame_ms.append((time.perf_counter() - frame_started) * 1000)
            render_started = time.perf_counter()
            json.dumps(build_render_frame(state), separators=(",", ":"))
            compact_frame_ms.append((time.perf_counter() - render_started) * 1000)
            peak_vehicles = max(peak_vehicles, state["vehicle_count"])
            peak_pedestrians = max(peak_pedestrians, state["pedestrian_count"])
            if engine.status != "running":
                break
            step_started = time.perf_counter()
            engine.step(1)
            step_ms.append((time.perf_counter() - step_started) * 1000)
    elapsed = time.perf_counter() - started
    with raw_path.open("rb") as source, gzip.open(gzip_path, "wb", compresslevel=6) as target:
        while chunk := source.read(1024 * 1024):
            target.write(chunk)
    result = {
        "traffic_density": density,
        "pedestrian_density": "high",
        "duration_sim_seconds": duration_seconds,
        "wall_seconds": round(elapsed, 3),
        "simulation_to_wall_ratio": round(duration_seconds / elapsed, 3),
        "steps": len(step_ms),
        "step_ms_p50": round(statistics.median(step_ms), 3),
        "step_ms_p95": round(_percentile(step_ms, .95), 3),
        "step_ms_max": round(max(step_ms), 3),
        "full_frame_ms_p95": round(_percentile(full_frame_ms, .95), 3),
        "compact_frame_ms_p95": round(_percentile(compact_frame_ms, .95), 3),
        "peak_vehicles": peak_vehicles,
        "peak_pedestrians": peak_pedestrians,
        "requested_vehicles": engine.requested_vehicles,
        "completed_vehicles": engine.completed,
        "pending_demand": engine._last_metrics["pending_demand"],
        "deferred_demand": engine._last_metrics["deferred_demand"],
        "vehicle_conservation_error": engine._last_metrics["vehicle_conservation_error"],
        "pedestrian_conservation_error": engine._last_metrics["pedestrian_conservation_error"],
        "peak_process_rss_bytes": _peak_rss_bytes(),
        "recording_raw_bytes": raw_path.stat().st_size,
        "recording_gzip_bytes": gzip_path.stat().st_size,
        "overloaded_for_realtime": elapsed > duration_seconds or _percentile(step_ms, .95) > 100,
    }
    if result["steps"] != duration_seconds * 10 or engine.status != "completed":
        raise RuntimeError(f"Native engine did not complete the requested case: {density}")
    if result["vehicle_conservation_error"] or result["pedestrian_conservation_error"]:
        raise RuntimeError(f"Demand conservation failed in capacity case: {density}")
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--duration-seconds", type=int, default=60)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--densities", default="single,low,medium,high,very high",
                        help="Comma-separated native traffic density cases")
    parser.add_argument("--keep-recordings", action="store_true")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.duration_seconds <= 0:
        parser.error("--duration-seconds must be positive")
    densities = [item.strip().lower() for item in args.densities.split(",")]
    if not densities or any(item not in {"single", "low", "medium", "high", "very high"} for item in densities):
        parser.error("--densities must contain native traffic density names")
    output = args.output.resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    artifacts = output.parent / "recordings"
    artifacts.mkdir(exist_ok=True)
    report = {"machine": {"platform": platform.platform(), "processor": platform.processor(),
                          "logical_cpu_count": os.cpu_count(), "python": platform.python_version()},
              "seed": args.seed, "cases": []}
    for density in densities:
        case = measure_case(density, args.duration_seconds, args.seed, artifacts)
        report["cases"].append(case)
        print(f"{density:9} step p95={case['step_ms_p95']:7.2f} ms  sim/wall={case['simulation_to_wall_ratio']:6.2f}x  raw={case['recording_raw_bytes']:>9} B", flush=True)
        if not args.keep_recordings:
            artifact_name = density.replace(" ", "_")
            (artifacts / f"{artifact_name}.jsonl").unlink()
            (artifacts / f"{artifact_name}.jsonl.gz").unlink()
    output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(output)


if __name__ == "__main__":
    main()
