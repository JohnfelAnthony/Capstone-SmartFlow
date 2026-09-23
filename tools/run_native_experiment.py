"""Run/reproduce a native experiment without the API, database or renderer."""
import argparse
import json
from pathlib import Path

from simulation.road_network import load_network
from simulation.scenario_config import number, read_trip_csv
from simulation.traffic_engine import TrafficEngine


def run_experiment(scenario, *, seed=42, duration=300, warmup=0, network=None, policy=None):
    warmup = number(warmup, "warmup", 0, 86400)
    duration = number(duration, "measurement duration", .1, 86400)
    engine = TrafficEngine(seed=seed, network=network)
    engine.configure_from_scenario(scenario)
    engine.start(duration+warmup)
    warmup_ticks = round(warmup/engine.step_length)
    if abs(warmup_ticks*engine.step_length-warmup) > 1e-7:
        raise ValueError("Warmup must be a multiple of 0.1 seconds")
    engine.step(warmup_ticks)
    engine.reset_metrics()
    if policy is not None:
        engine.set_runtime_policy(policy)
    while engine.status == "running":
        engine.step(100)
    return {"experiment": engine.experiment_metadata(), "network": engine.network.payload,
            "metrics": engine.to_dict()["metrics"], "events": engine.events,
            "status": engine.status}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--scenario", type=Path, required=True, help="JSON scenario or engine config")
    parser.add_argument("--network", type=Path, help="Native metric network JSON; defaults to Tagum study network")
    parser.add_argument("--trips", type=Path, help="Optional measured/synthetic trip CSV")
    parser.add_argument("--duration", type=float, default=300)
    parser.add_argument("--warmup", type=float, default=0)
    parser.add_argument("--seeds", type=int, nargs="+", default=[42])
    parser.add_argument("--controller", choices=["fixed-time", "ql", "dql", "ppo"], default="fixed-time")
    parser.add_argument("--model", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    scenario = json.loads(args.scenario.read_text(encoding="utf-8"))
    if args.trips:
        scenario.setdefault("engine_config", {})["trips"] = read_trip_csv(args.trips)
    policy = None
    if args.controller != "fixed-time":
        if args.model is None:
            parser.error("RL controllers require --model")
        from simulation.rl_policy_runtime import load_runtime_policy
        policy = load_runtime_policy(args.controller, args.model)
    network = load_network(args.network) if args.network else None
    results = [run_experiment(scenario, seed=seed, duration=args.duration, warmup=args.warmup, network=network, policy=policy) for seed in args.seeds]
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps({"runs": results}, indent=2, allow_nan=False), encoding="utf-8")
    print(f"Saved {len(results)} experiment(s) to {args.output}")


if __name__ == "__main__":
    main()
