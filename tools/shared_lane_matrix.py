"""Shared-lane closure (hypothetical): overlap, stuck, stalled and conservation checks at every tick, and how far each direction slows (synthetic demand).

For each case the closure runs through the product path (a scenario record through `engine_for_scenario`, `apply_controller`) with the response
"share"; the same seed is then run again with nothing closed, and the time vehicles take to drive each direction of the road during the
closure is compared. Writes one JSON line per run to --out (a new file).
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
os.environ.setdefault("SMARTFLOW_SECRET_KEY", "shared-lane-matrix")

START_S, END_S = 300.0, 1200.0
# (site, the closed direction that shares), seeds are given per site
CASES = [("tagum_site_a", "road2r"), ("tagum_site_a", "road3f"), ("tagum_site_a", "road1f"), ("tagum_site_b", "road1f"), ("tagum_site_b", "road1r")]
CONTROLS = ("no-signal", "fixed-time")
ZERO_TARGETS = ("max_stalled_vehicles", "max_stuck_junction_vehicles", "conservation_error")


def build(site: str, lane: str | None, control: str, seed: int, seconds: float):
    from services.native_controller import apply_controller
    from simulation.network_registry import engine_for_scenario
    from simulation.scenario_config import TAGUM_PROVISIONAL_MIX
    config = {"traffic_density": "medium", "pedestrian_density": "medium", "vehicle_mix": dict(TAGUM_PROVISIONAL_MIX)}
    if lane:
        config.update(events=[{"time": START_S, "lane_id": lane, "closed": True}, {"time": END_S, "lane_id": lane, "closed": False}], closure_responses={lane: "share"})
    engine = engine_for_scenario({"network_id": site, "engine_config": config}, seed=seed)
    apply_controller(engine, control)
    engine.start(int(seconds))
    return engine


def drive(engine, lanes: tuple[str, str], seconds: float, *, check_overlaps: bool) -> dict:
    """Run to `seconds`; per lane, the mean time vehicles that entered it during the closure took to cross it, and how many did."""
    from simulation.footprints import overlapping_pairs
    entered: dict[tuple[str, str], float] = {}
    crossing: dict[str, list[float]] = {lane: [] for lane in lanes}
    overlaps = 0 if check_overlaps else None
    most_stalled = most_stuck = most_held = conservation_error = 0
    shared_ticks = 0
    while engine.status == "running" and engine.simulation_time < seconds:
        engine.step(1)
        now = engine.simulation_time
        seen = set()
        for vehicle in engine.vehicles.values():
            lane = vehicle.route[0]
            if lane in lanes:
                key = (vehicle.id, lane)
                seen.add(key)
                if key not in entered and START_S <= now <= END_S and vehicle.position < 6:
                    entered[key] = now
        for key in [key for key in entered if key not in seen]:
            started = entered.pop(key)
            if engine.vehicles.get(key[0]) is not None or key[0] not in engine.vehicles:
                crossing[key[1]].append(now-started)
        metrics = engine._last_metrics
        most_stalled, most_stuck, most_held = max(most_stalled, metrics["stalled_vehicles"]), max(most_stuck, metrics["stuck_junction_vehicles"]), max(most_held, metrics["closure_held_vehicles"])
        conservation_error = max(conservation_error, abs(metrics["vehicle_conservation_error"]))
        shared_ticks += bool(metrics["shared_lane_roads"])
        if overlaps is not None:
            overlaps = max(overlaps, len(overlapping_pairs(engine.vehicle_records())))
    metrics = engine._last_metrics
    return {"max_overlapping_pairs": overlaps, "max_stalled_vehicles": most_stalled, "max_stuck_junction_vehicles": most_stuck, "max_closure_held_vehicles": most_held,
            "conservation_error": conservation_error, "completed": metrics["throughput"], "diverted_vehicles": metrics["diverted_vehicles"],
            "seconds_shared": round(shared_ticks*0.1, 1), "crossings": {lane: len(times) for lane, times in crossing.items()},
            "mean_crossing_s": {lane: round(sum(times)/len(times), 2) if times else None for lane, times in crossing.items()}}


def run(job: tuple) -> dict:
    site, lane, control, seed, seconds = job
    kept = lane[:-1]+("r" if lane.endswith("f") else "f")
    lanes = (lane, kept)
    shared = drive(build(site, lane, control, seed, seconds), lanes, seconds, check_overlaps=True)
    base = drive(build(site, None, control, seed, seconds), lanes, seconds, check_overlaps=False)
    slowdown = {name: (round(shared["mean_crossing_s"][name]/base["mean_crossing_s"][name], 2) if shared["mean_crossing_s"][name] and base["mean_crossing_s"][name] else None) for name in lanes}
    return {"site": site, "shared_lane": lane, "kept_lane": kept, "control": control, "seed": seed, "seconds": seconds, "shared": shared, "no_closure": base,
            "crossing_time_ratio": slowdown}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", required=True, type=Path)
    parser.add_argument("--seeds-a", default="101,102,103,104,105")
    parser.add_argument("--seeds-b", default="101,102,103")
    parser.add_argument("--seconds", type=float, default=1800.0)
    parser.add_argument("--workers", type=int, default=5)
    parser.add_argument("--cases", default=",".join(str(index) for index in range(len(CASES))), help="comma-separated indexes into CASES")
    parser.add_argument("--controls", default=",".join(CONTROLS))
    args = parser.parse_args()
    if args.out.exists():
        parser.error("output already exists; choose a new path to preserve prior evidence")
    cases = [CASES[int(index)] for index in args.cases.split(",")]
    jobs = [(site, lane, control, int(seed), args.seconds) for site, lane in cases for control in args.controls.split(",")
            for seed in (args.seeds_a if site == "tagum_site_a" else args.seeds_b).split(",")]
    failed = 0
    with ProcessPoolExecutor(args.workers) as pool, args.out.open("x", encoding="utf-8") as out:
        futures = [pool.submit(run, job) for job in jobs]
        for result in (future.result() for future in as_completed(futures)):
            problem = {}
            for condition in ("shared", "no_closure"):
                targets = (*ZERO_TARGETS, "max_overlapping_pairs") if condition == "shared" else ZERO_TARGETS
                missed = {key: result[condition].get(key) for key in targets if result[condition].get(key) != 0}
                if missed:
                    problem[condition] = missed
            result["missed_targets"] = problem
            failed += bool(problem)
            out.write(json.dumps(result)+"\n")
            out.flush()
            shared = result["shared"]
            print(f'{result["site"]} {result["shared_lane"]} {result["control"]} seed {result["seed"]}: completed {shared["completed"]}{" PROBLEM "+json.dumps(problem) if problem else ""}', file=sys.stderr, flush=True)
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
