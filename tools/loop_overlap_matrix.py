"""Count body overlaps at every tick on Site A with the closure responses, through the product path (synthetic demand, provisional geometry).

Every engine is built the way the application builds one: a scenario record (`network_id` and `engine_config`, with the closure and its
response) goes through `engine_for_scenario`, and the controller through `services.native_controller.apply_controller`. Nothing is set on the
engine afterwards, so 'avoid jams' runs adaptive only because the scenario chose it. Writes one JSON line per run to --out (a new file).
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
os.environ.setdefault("SMARTFLOW_SECRET_KEY", "overlap-matrix")

WEST_CLOSED = [{"time": 300.0, "lane_id": "road2r", "closed": True}, {"time": 1200.0, "lane_id": "road2r", "closed": False}]
LOOP_LANES = {"road6f", "road6r"}
RESPONSES = ("side_street", "side_street_adaptive", "nearest_exit")
CONTROLS = ("no-signal", "fixed-time")


def run(job: tuple) -> dict:
    from services.native_controller import apply_controller
    from simulation.footprints import overlapping_pairs
    from simulation.network_registry import engine_for_scenario
    from simulation.scenario_config import TAGUM_PROVISIONAL_MIX
    response, control, seed, seconds = job
    scenario = {"network_id": "tagum_site_a", "engine_config": {
        "traffic_density": "medium", "pedestrian_density": "medium", "vehicle_mix": dict(TAGUM_PROVISIONAL_MIX),
        "events": [dict(event) for event in WEST_CLOSED], "closure_responses": {"road2r": response}}}
    engine = engine_for_scenario(scenario, seed=seed)
    apply_controller(engine, control)
    engine.start(int(seconds))
    routing = engine.config["routing_mode"]
    open_episodes, episodes, most_at_once = {}, [], 0
    most = {"stalled_vehicles": 0, "stuck_junction_vehicles": 0, "closure_held_vehicles": 0}
    while engine.status == "running" and engine.simulation_time < seconds:
        engine.step(1)
        now = set(overlapping_pairs(engine.vehicle_records()))
        most_at_once = max(most_at_once, len(now))
        metrics = engine._last_metrics
        for key in most:
            most[key] = max(most[key], metrics[key])
        for pair in now - open_episodes.keys():
            lanes = [engine.vehicles[identity].route[0] for identity in pair]
            open_episodes[pair] = {"start": round(engine.simulation_time, 1), "lanes": lanes, "types": [engine.vehicles[identity].vehicle_type for identity in pair],
                                   "on_loop": all(lane in LOOP_LANES for lane in lanes)}
        for pair in [pair for pair in open_episodes if pair not in now]:
            episode = open_episodes.pop(pair)
            episode["end"] = round(engine.simulation_time, 1)
            episodes.append(episode)
    episodes.extend({**episode, "end": round(engine.simulation_time, 1)} for episode in open_episodes.values())
    metrics = engine._last_metrics
    return {"response": response, "control": control, "seed": seed, "routing_mode": routing, "seconds": seconds, "episodes": len(episodes),
            "episodes_on_loop": sum(episode["on_loop"] for episode in episodes), "seconds_overlapping": round(sum(episode["end"]-episode["start"] for episode in episodes), 1),
            "most_pairs_at_once": most_at_once, **{f"max_{key}": value for key, value in most.items()}, "completed": metrics["throughput"],
            "diverted_vehicles": metrics["diverted_vehicles"], "reroutes": metrics["reroutes"], "loop_exits": metrics["lanes"]["road6f"]["exits"], "first_episodes": episodes[:3]}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", required=True, type=Path)
    parser.add_argument("--seeds", default="101,102,103,104,105")
    parser.add_argument("--seconds", type=float, default=1800.0)
    parser.add_argument("--workers", type=int, default=4)
    args = parser.parse_args()
    if args.out.exists():
        parser.error("output already exists; choose a new path to preserve prior evidence")
    jobs = [(response, control, int(seed), args.seconds) for response in RESPONSES for control in CONTROLS for seed in args.seeds.split(",")]
    with ProcessPoolExecutor(args.workers) as pool, args.out.open("w", encoding="utf-8") as out:
        futures = [pool.submit(run, job) for job in jobs]
        for result in (future.result() for future in as_completed(futures)):
            out.write(json.dumps(result)+"\n")
            out.flush()
            print(f'{result["response"]} {result["control"]} seed {result["seed"]} ({result["routing_mode"]}): {result["episodes"]} episodes', file=sys.stderr, flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
