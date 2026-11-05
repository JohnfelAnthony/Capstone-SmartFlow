"""Count body overlaps at every tick on Site A, by seed, routing mode and closure case (synthetic demand, provisional geometry).

Adaptive routing is no longer reachable at a study site (validate_config makes it static), so the adaptive rows set
`engine.config["routing_mode"]` directly after the engine is built. They show how the loop street fares when congestion
reroutes traffic onto it; the product cannot produce them. Writes one JSON line per run to --out (a new file).
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
os.environ.setdefault("SMARTFLOW_SECRET_KEY", "overlap-matrix")

WEST_CLOSED = [{"time": 300.0, "lane_id": "road2r", "closed": True}, {"time": 1200.0, "lane_id": "road2r", "closed": False}]
STUDY_JUNCTION_CLOSED = [{"time": 0.0, "lane_id": f"road{number}{side}", "closed": True} for number in range(4) for side in "fr"]
LOOP_LANES = {"road6f", "road6r"}
# name, density, no_signal, events, seconds
CASES = [
    ("high fixed, no closure", "high", False, [], 1800.0),
    ("medium no signal, west closed 300-1200 s", "medium", True, WEST_CLOSED, 1800.0),
    ("medium fixed, west closed 300-1200 s", "medium", False, WEST_CLOSED, 1800.0),
    ("high no signal, west closed 300-1200 s", "high", True, WEST_CLOSED, 1800.0),
    ("medium no signal, study junction closed from 0 s", "medium", True, STUDY_JUNCTION_CLOSED, 600.0),
]


def run(job: tuple) -> dict:
    from simulation.footprints import overlapping_pairs
    from simulation.scenario_config import TAGUM_PROVISIONAL_MIX
    from tools.mixed_traffic_report import build_engine
    (name, density, no_signal, events, seconds), seed, routing = job
    engine = build_engine("siteA", density, dict(TAGUM_PROVISIONAL_MIX), seconds, seed, events=events or None, no_signal=no_signal, routing_mode="static")
    engine.config["routing_mode"] = routing
    open_episodes, episodes, most_at_once = {}, [], 0
    while engine.status == "running" and engine.simulation_time < seconds:
        engine.step(1)
        records = engine.vehicle_records()
        now = set(overlapping_pairs(records))
        most_at_once = max(most_at_once, len(now))
        for pair in now - open_episodes.keys():
            lanes = [engine.vehicles[identity].route[0] for identity in pair]
            kinds = [engine.vehicles[identity].vehicle_type for identity in pair]
            open_episodes[pair] = {"start": round(engine.simulation_time, 1), "lanes": lanes, "types": kinds, "on_loop": all(lane in LOOP_LANES for lane in lanes)}
        for pair in [pair for pair in open_episodes if pair not in now]:
            episode = open_episodes.pop(pair)
            episode["end"] = round(engine.simulation_time, 1)
            episodes.append(episode)
    episodes.extend({**episode, "end": round(engine.simulation_time, 1)} for episode in open_episodes.values())
    return {"case": name, "seed": seed, "routing_mode": routing, "seconds": seconds, "episodes": len(episodes), "episodes_on_loop": sum(episode["on_loop"] for episode in episodes),
            "seconds_overlapping": round(sum(episode["end"]-episode["start"] for episode in episodes), 1), "most_pairs_at_once": most_at_once,
            "completed": engine._last_metrics["throughput"], "first_episodes": episodes[:3]}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", required=True, type=Path)
    parser.add_argument("--seeds", default="101,102,103,104,105")
    parser.add_argument("--workers", type=int, default=7)
    args = parser.parse_args()
    if args.out.exists():
        parser.error("output already exists; choose a new path to preserve prior evidence")
    jobs = [(case, int(seed), routing) for case in CASES for seed in args.seeds.split(",") for routing in ("static", "adaptive")]
    jobs.sort(key=lambda job: -job[0][4])
    with ProcessPoolExecutor(args.workers) as pool, args.out.open("w", encoding="utf-8") as out:
        for result in pool.map(run, jobs):
            out.write(json.dumps(result)+"\n")
            out.flush()
            print(f'{result["case"]} seed {result["seed"]} {result["routing_mode"]}: {result["episodes"]} episodes', file=sys.stderr, flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
