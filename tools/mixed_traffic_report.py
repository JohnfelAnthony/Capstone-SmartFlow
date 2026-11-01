"""Safety, behaviour and speed report for the mixed-traffic engine work.

Records native-5 first (the baseline), then checks native-6 against it. Every case runs with an
overlap check at every tick; the speed benchmarks run first, alone and without those checks.
"""
from __future__ import annotations

import argparse
import json
import math
import random
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from simulation.footprints import overlapping_pairs, state_digest  # noqa: E402
from simulation.road_network import RoadNetwork  # noqa: E402
from simulation.scenario_config import CARS_ONLY_MIX, TAGUM_PROVISIONAL_MIX  # noqa: E402
from simulation.traffic_engine import ENGINE_VERSION, TrafficEngine  # noqa: E402

NETWORKS = {"5j": ROOT/"data"/"networks"/"tagum_network.json", "2j": ROOT/"data"/"networks"/"tagum_network_2j.json",
            "siteA": ROOT/"data"/"networks"/"tagum_site_a.json", "siteB": ROOT/"data"/"networks"/"tagum_site_b.json"}
CARS_ONLY, TAGUM = CARS_ONLY_MIX, TAGUM_PROVISIONAL_MIX
MIXES = {"cars": CARS_ONLY, "tagum": TAGUM}
CASES = {
    "5j-medium-cars": ("5j", "medium", "cars", {}),
    "5j-low-tagum": ("5j", "low", "tagum", {}),
    "5j-medium-tagum": ("5j", "medium", "tagum", {}),
    "5j-high-tagum": ("5j", "high", "tagum", {}),
    "2j-medium-tagum": ("2j", "medium", "tagum", {}),
    "2j-medium-tagum-nofilter": ("2j", "medium", "tagum", {"sideways_decisions": False}),
    "2j-high-tagum": ("2j", "high", "tagum", {}),
    "2j-veryhigh-tagum": ("2j", "very high", "tagum", {}),
    "5j-closure-tagum": ("5j", "medium", "tagum", {"closure": True}),
    "5j-allwaystop-tagum": ("5j", "medium", "tagum", {"all_way_stop": True}),
}
# Two-site study (design 0.13): each site at medium and high demand under no signal, its default fixed-time plan and a grouped Webster plan.
SITE_CONTROLS = {"nosignal": {"no_signal": True}, "fixed": {}, "grouped": {"grouped": True}}
for _site in ("siteA", "siteB"):
    for _density in ("medium", "high"):
        for _control, _extras in SITE_CONTROLS.items():
            CASES[f"{_site}-{_density}-{_control}"] = (_site, _density, "tagum", dict(_extras))
GROUPED_PHASES = [["north", "south"], ["east", "west"], "pedestrian"]
SYNTHETIC_VEHICLES_PER_HOUR = {"low": 432, "medium": 1080, "high": 2340, "very high": 3420}  # simulation/demand.py, spread evenly over boundaries
QUICK_CASES = ("2j-medium-tagum", "5j-medium-cars")
FRONT_ROW_M = 1.0
MIN_FRONT_ROW_SAMPLES = 20
SAMPLE_EVERY_TICKS = 10
DISCHARGE_TICKS = 100
_network_cache: dict[str, RoadNetwork] = {}


class NoFilteringEngine(TrafficEngine):
    """Filtering off, everything else equal: sideways decisions never move a vehicle."""

    def _decide_lateral(self, vehicle, lane):
        return None


def load_network(name: str) -> RoadNetwork:
    if name not in _network_cache:
        _network_cache[name] = RoadNetwork(json.loads(NETWORKS[name].read_text(encoding="utf-8")))
    return _network_cache[name]


def percentile_95(values: list[float]) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    return float(ordered[max(0, math.ceil(0.95*len(ordered))-1)])


def grouped_plan(network_name: str, density: str, mix: dict) -> dict:
    """A provisional Webster plan for the case's own synthetic demand: every boundary sends an equal share of the rate."""
    from simulation.signal_design import flows_from_counts, plan_from_result, saturation_from_network, webster_plan
    network = load_network(network_name)
    junction = network.intersections[0]
    # simulation/demand.py draws a uniformly random routable boundary pair, so a source's share is its share of those pairs.
    pairs = [(a, b) for a in network.boundaries for b in network.boundaries if a != b and network.route(a, b)]
    approach_of = {lane.source: lane.approach for lane in network.lanes.values() if lane.target == junction and lane.source in network.boundaries}
    counts = {approach_of[boundary]: {kind: SYNTHETIC_VEHICLES_PER_HOUR[density]*share*sum(1 for a, _ in pairs if a == boundary)/len(pairs) for kind, share in mix.items()}
              for boundary in network.boundaries if boundary in approach_of}
    result = webster_plan(GROUPED_PHASES, flows_from_counts(counts), saturation_from_network(network, junction))
    return {junction: plan_from_result(result, {})}


def build_engine(network_name: str, density: str, mix: dict, seconds: float, seed: int, *, events=None,
                 all_way_stop: bool = False, sideways_decisions: bool = True, no_signal: bool = False, signal_plans: dict | None = None) -> TrafficEngine:
    network = load_network(network_name)
    engine = (TrafficEngine if sideways_decisions else NoFilteringEngine)(seed=seed, network=network)
    settings = {"traffic_density": density, "pedestrian_density": "medium", "vehicle_mix": dict(mix)}
    if events:
        settings["events"] = events
    if all_way_stop:
        settings["signal_plans"] = {node: {"mode": "all_way_stop"} for node in network.intersections}
    if signal_plans:
        settings["signal_plans"] = signal_plans
    engine.configure(**settings)
    if no_signal:
        engine.enable_no_signal_control()
    engine.start(int(math.ceil(seconds)))
    return engine


def run_case(network_name: str, density: str, mix: dict, seconds: float, seed: int, *, events=None,
             all_way_stop: bool = False, sideways_decisions: bool = True, no_signal: bool = False, signal_plans: dict | None = None) -> dict:
    started = time.perf_counter()
    engine = build_engine(network_name, density, mix, seconds, seed, events=events, all_way_stop=all_way_stop,
                          sideways_decisions=sideways_decisions, no_signal=no_signal, signal_plans=signal_plans)
    network = engine.network
    node = engine.controlled_junction
    incoming = [network.lanes[lane_id] for lane_id in network.incoming[node]]
    signal = engine.signals[node]
    max_overlaps = max_stuck = 0
    max_gridlock = 0.0
    queue_samples, active_samples = [], []
    front_row_total = front_row_motorcycles = queue_total = queue_motorcycles = 0
    discharges, open_discharge = [], None
    was_green = signal.stage == "green"
    while engine.status == "running" and engine.simulation_time < seconds:
        engine.step(1)
        max_overlaps = max(max_overlaps, len(overlapping_pairs(engine.vehicle_records())))
        metrics = engine._last_metrics
        max_stuck = max(max_stuck, metrics["stuck_junction_vehicles"])
        max_gridlock = max(max_gridlock, metrics["gridlock_seconds"])
        is_green = signal.stage == "green"
        if is_green and not was_green and signal.family != "pedestrian":
            green_lanes = [lane.id for lane in incoming if signal.serves(lane.approach)]
            open_discharge = [engine.ticks+DISCHARGE_TICKS, green_lanes, sum(engine.lane_exits[lane] for lane in green_lanes)]
        was_green = is_green
        if open_discharge and engine.ticks >= open_discharge[0]:
            discharges.append(sum(engine.lane_exits[lane] for lane in open_discharge[1])-open_discharge[2])
            open_discharge = None
        if engine.ticks % SAMPLE_EVERY_TICKS:
            continue
        by_approach_queue, by_approach_active = {}, {}
        for vehicle in engine.vehicles.values():
            lane = network.lanes[vehicle.lane_id]
            if vehicle.connector is not None or lane.target != node:
                continue
            by_approach_active[lane.approach] = by_approach_active.get(lane.approach, 0)+1
            if vehicle.speed > 0.1:
                continue
            by_approach_queue[lane.approach] = by_approach_queue.get(lane.approach, 0)+1
            is_motorcycle = vehicle.vehicle_type == "motorcycle"
            queue_total += 1
            queue_motorcycles += is_motorcycle
            if engine.stop_line(lane.id)-(vehicle.position+vehicle.length/2) <= FRONT_ROW_M:
                front_row_total += 1
                front_row_motorcycles += is_motorcycle
        approaches = {lane.approach for lane in incoming}
        queue_samples += [by_approach_queue.get(approach, 0) for approach in approaches]
        active_samples += [by_approach_active.get(approach, 0) for approach in approaches]
    enough_front_row = front_row_total >= MIN_FRONT_ROW_SAMPLES
    return {
        "runtime_s": round(time.perf_counter()-started, 3),
        "simulated_s": engine.simulation_time,
        "max_overlapping_pairs": int(max_overlaps),
        "max_stuck_junction_vehicles": int(max_stuck),
        "max_gridlock_seconds": float(max_gridlock),
        "final_vehicle_conservation_error": engine._last_metrics["vehicle_conservation_error"],
        "completed": engine.lifetime_completed,
        "queue_count_p95": percentile_95(queue_samples),
        "active_count_p95": percentile_95(active_samples),
        "front_row_motorcycle_share": front_row_motorcycles/front_row_total if enough_front_row else None,
        "queue_motorcycle_share": queue_motorcycles/queue_total if enough_front_row else None,
        "front_row_samples": front_row_total,
        "mean_discharge_first_10s": sum(discharges)/len(discharges) if discharges else None,
        "green_onsets_measured": len(discharges),
    }


def case_options(name: str) -> tuple[str, str, dict, dict]:
    network_name, density, mix_name, extras = CASES[name]
    options = {"sideways_decisions": extras.get("sideways_decisions", True), "all_way_stop": extras.get("all_way_stop", False),
               "no_signal": extras.get("no_signal", False)}
    if extras.get("grouped"):
        options["signal_plans"] = grouped_plan(network_name, density, MIXES[mix_name])
    if extras.get("closure"):
        lane_id = load_network(network_name).incoming[TrafficEngine(seed=1, network=load_network(network_name)).controlled_junction][0]
        options["events"] = [{"time": 200, "lane_id": lane_id, "closed": True}, {"time": 500, "lane_id": lane_id, "closed": False}]
    return network_name, density, MIXES[mix_name], options


def benchmark_cars_only(seconds: float = 900, seed: int = 101) -> float:
    engine = build_engine("5j", "medium", CARS_ONLY, seconds, seed)
    started = time.perf_counter()
    while engine.status == "running":
        engine.step(100)
    return round(time.perf_counter()-started, 3)


def benchmark_rl_env() -> dict:
    from simulation.rl_env import SmartFlowRLEnv
    environment = SmartFlowRLEnv(scenario={"traffic_density": "medium", "pedestrian_density": "medium", "vehicle_mix": dict(TAGUM)})
    actions = random.Random(1)
    started = time.perf_counter()
    environment.reset()
    decisions, finished = 0, False
    while not finished:
        _, _, terminated, truncated, _ = environment.step(actions.randrange(5))
        decisions += 1
        finished = terminated or truncated
    elapsed = time.perf_counter()-started
    # Wall time includes the warmup in reset(), as training pays it too.
    return {"decisions": decisions, "elapsed_s": round(elapsed, 3), "decisions_per_second": round(decisions/elapsed, 3)}


def determinism_equal() -> bool:
    digests = [state_digest(build_engine("2j", "medium", TAGUM, 300, 101), 300) for _ in range(2)]
    return digests[0] == digests[1]


DETERMINISM_SECONDS = 120.0


def determinism_equal_case(name: str, seconds: float = DETERMINISM_SECONDS, seed: int = 101) -> bool:
    """The same case built and stepped twice gives the same state digest."""
    network_name, density, mix, options = case_options(name)
    digests = [state_digest(build_engine(network_name, density, mix, seconds, seed, **options), seconds) for _ in range(2)]
    return digests[0] == digests[1]


def log(message: str):
    print(message, file=sys.stderr, flush=True)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", required=True, type=Path)
    parser.add_argument("--seconds", type=float, default=1800.0)
    parser.add_argument("--seeds", default="101,102")
    parser.add_argument("--quick", action="store_true", help="60 s, seed 101, two cases, no benchmarks")
    parser.add_argument("--determinism", action="store_true", help="also check that each selected case gives equal state digests when run twice")
    parser.add_argument("--only", help="comma-separated case-name prefixes (for example siteA,siteB); the benchmarks are skipped")
    args = parser.parse_args(argv)
    seconds, seeds = (60.0, [101]) if args.quick else (args.seconds, [int(seed) for seed in args.seeds.split(",")])
    prefixes = tuple(args.only.split(",")) if args.only else ()
    names = QUICK_CASES if args.quick else tuple(name for name in CASES if not prefixes or name.startswith(prefixes))
    if not names:
        parser.error(f"no case starts with {args.only}")
    report = {"engine_version": ENGINE_VERSION, "seconds": seconds, "seeds": seeds, "cases": {}, "benchmarks": {}}
    if not args.quick and not prefixes:
        log("benchmarks: cars-only 900 s run")
        report["benchmarks"]["cars_only_5j_medium_900s_runtime_s"] = benchmark_cars_only()
        log("benchmarks: RL environment episode")
        rl = benchmark_rl_env()
        report["benchmarks"]["rl_env_decisions_per_second"] = rl["decisions_per_second"]
        report["benchmarks"]["rl_env_episode"] = rl
        log("benchmarks: determinism")
        report["benchmarks"]["determinism_digest_equal"] = determinism_equal()
    if args.determinism:
        report["determinism"] = {}
        for name in names:
            log(f"determinism {name}")
            report["determinism"][name] = determinism_equal_case(name)
    for name in names:
        network_name, density, mix, options = case_options(name)
        for seed in seeds:
            log(f"case {name}@{seed}")
            report["cases"][f"{name}@{seed}"] = run_case(network_name, density, mix, seconds, seed, **options)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(report, indent=2, sort_keys=True)+"\n", encoding="utf-8")
    log(f"wrote {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
