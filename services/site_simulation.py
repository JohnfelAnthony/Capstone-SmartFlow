"""Simulated measures for site validation: run the no-signal engine and record what the observed side reports.

Every definition matches `services.site_measures`: the same video-relative sample instants, the same mapped lines
(arrival, stop line, exit), the same discharge bins, and arrival-order pairs judged from priority-zone and stop-line
entry times. The engine is never reset at measurement start, so lead-in demand stays in the system.
"""
from __future__ import annotations

import math
import statistics

from services.site_measures import classify_pairs, locations_with_role, summarize_queue, summarize_travel
from simulation.footprints import overlapping_pairs
from simulation.scenario_config import site_calibration_sha256
from simulation.traffic_engine import STEP_LENGTH

DEVELOPMENT_SEEDS = range(101, 111)
OVERLAP_CHECK_EVERY_TICKS = 5   # bodies are compared twice per simulated second
SAFETY_CHECK_EVERY_TICKS = 10


def _lanes_at(network, node: str):
    incoming = {lane.source: lane for lane in network.lanes.values() if lane.target == node and lane.source in network.boundaries}
    outgoing = {lane.target: lane for lane in network.lanes.values() if lane.source == node and lane.target in network.boundaries}
    return incoming, outgoing


def _decision_readiness(engine, entering) -> dict[str, bool]:
    """Which waiting vehicles of other approaches could have gone at this vehicle's decision (same predicates as the engine's)."""
    node = engine.network.lanes[entering.route[0]].target
    entering_approach = engine.network.lanes[entering.route[0]].approach
    ready = {}
    for other in engine.vehicles.values():
        if other is entering or other.connector is not None or other.reserved_junction or len(other.route) < 2 or other.approach_arrival is None:
            continue
        lane = engine.network.lanes[other.route[0]]
        if lane.target != node or lane.approach == entering_approach:
            continue
        leader, _, _ = engine._lane_obstacle(other, lane)
        clear_ahead = leader is None or leader.reserved_junction == node
        ready[other.id] = bool(other.route[1] not in engine.closed_lanes and engine._exit_has_space(other.route[1], other)
                               and not engine._must_wait_at_line(other) and clear_ahead
                               and not engine._sweep_blocked(other, node) and not engine._meets_committed_path(other))
    return ready


def _run_seed(engine, seed: int, mapping: dict, criteria: dict, *, origin_s: float, start_s: float, end_s: float) -> dict:
    network = engine.network
    if len(network.intersections) != 1:
        raise ValueError("Site validation measures a single-junction site network")
    node = network.intersections[0]
    incoming, outgoing = _lanes_at(network, node)
    lead_out_s = float(mapping["lead_out_s"])
    interval, bin_s = criteria["queue_sample_interval_s"], criteria["discharge_bin_s"]
    arrival_pos = {line["boundary"]: incoming[line["boundary"]].length - float(line["distance_from_junction_m"])
                   for line in locations_with_role(mapping, "arrival").values()}
    exit_pos = {line["boundary"]: float(line["distance_from_junction_m"]) for line in locations_with_role(mapping, "exit").values()}
    stop_boundaries = [line["boundary"] for line in locations_with_role(mapping, "stopline").values()]

    engine.enable_no_signal_control()
    engine.start(end_s + lead_out_s - origin_s)
    decisions: dict[str, dict[str, bool]] = {}
    original_reserve = engine._reserve

    def reserve_and_record(vehicle, reserved_node, approach):
        decisions[vehicle.id] = _decision_readiness(engine, vehicle)
        original_reserve(vehicle, reserved_node, approach)

    engine._reserve = reserve_and_record
    records: dict[str, dict] = {}
    queue_samples: dict[str, dict[int, float]] = {boundary: {} for boundary in criteria["approaches"]}
    sample_ticks = {round((start_s + index * interval - origin_s) / STEP_LENGTH): index for index in range(math.ceil((end_s - start_s) / interval))}
    overlaps = stuck = conservation = 0
    gridlock = 0.0

    def observe(tick: int):
        video_time = engine.simulation_time + origin_s
        for vehicle in engine.vehicles.values():
            lane = network.lanes[vehicle.route[0]]
            record = records.get(vehicle.id)
            if record is None:
                record = records[vehicle.id] = {"approach": lane.source, "movement": f"{lane.source}->{network.lanes[vehicle.route[-1]].target}",
                                                "arrival": None, "priority": None, "stop": None, "exit": None}
            front = vehicle.position + vehicle.length / 2
            home = incoming.get(record["approach"])
            if home is not None and lane.id == home.id:
                if record["arrival"] is None and record["approach"] in arrival_pos and front >= arrival_pos[record["approach"]]:
                    record["arrival"] = video_time
                if record["stop"] is None and (vehicle.connector is not None or front >= engine.stop_line(lane.id)):
                    record["stop"] = video_time
            elif lane.target in exit_pos and lane.source == node and vehicle.connector is None and record["exit"] is None and front >= exit_pos[lane.target]:
                record["exit"] = video_time
            if record["priority"] is None and vehicle.approach_arrival is not None:
                record["priority"] = vehicle.approach_arrival + origin_s
        if tick in sample_ticks:
            for boundary in queue_samples:
                lane = incoming.get(boundary)
                queue_samples[boundary][sample_ticks[tick]] = float(sum(
                    1 for vehicle in engine.vehicles.values()
                    if lane is not None and vehicle.route[0] == lane.id and vehicle.connector is None and vehicle.speed <= criteria["stopped_speed_mps"]))

    observe(0)
    for tick in range(1, int(round((end_s + lead_out_s - origin_s) / STEP_LENGTH)) + 1):
        engine.step(1)
        observe(tick)
        if tick % OVERLAP_CHECK_EVERY_TICKS == 0:
            overlaps += len(overlapping_pairs(engine.vehicle_records()))
        if tick % SAFETY_CHECK_EVERY_TICKS == 0:
            metrics = engine._last_metrics
            stuck = max(stuck, metrics["stuck_junction_vehicles"])
            gridlock = max(gridlock, metrics["gridlock_seconds"])
            conservation = max(conservation, abs(metrics["vehicle_conservation_error"]))

    discharge = {}
    bin_count = int((end_s - start_s) / bin_s + 1e-9)
    for boundary in stop_boundaries:
        discharge[boundary] = {str(index): {"value": sum(1 for record in records.values() if record["approach"] == boundary and record["stop"] is not None
                                                          and start_s + index * bin_s <= record["stop"] < start_s + (index + 1) * bin_s), "complete": True}
                               for index in range(bin_count)}
    durations, unfinished = [], 0
    for record in records.values():
        if record["arrival"] is not None and start_s <= record["arrival"] < end_s:
            if record["exit"] is None:
                unfinished += 1
            else:
                durations.append(record["exit"] - record["arrival"])

    window = [(vehicle_id, record) for vehicle_id, record in records.items() if record["priority"] is not None and start_s <= record["priority"] < end_s]
    window.sort(key=lambda item: item[1]["priority"])
    pairs = []
    for index, (first_id, first) in enumerate(window):
        for second_id, second in window[index + 1:]:
            if second["priority"] - first["priority"] > criteria["pair_window_s"]:
                break
            if first["approach"] == second["approach"]:
                continue
            readiness = "unknown"
            if first["stop"] is None or second["stop"] is None or first["stop"] <= second["stop"]:
                readiness = "ready"  # the earlier arrival entered first (or nobody entered), so readiness cannot decide the pair
            elif first_id in decisions.get(second_id, {}):
                readiness = "ready" if decisions[second_id][first_id] else "blocked"
            pairs.append({"movement_a": first["movement"], "movement_b": second["movement"], "priority_a": first["priority"], "priority_b": second["priority"],
                          "entry_a": first["stop"], "entry_b": second["stop"], "readiness": readiness, "visible": True})
    return {"seed": seed, "queue": summarize_queue(queue_samples, list(queue_samples)), "discharge": discharge,
            "travel_time": summarize_travel(durations, unfinished, True), "arrival_order": classify_pairs(pairs, mapping, criteria),
            "safety": {"overlaps": overlaps, "stuck_junction_vehicles": stuck, "gridlock_seconds": gridlock, "vehicle_conservation_error": conservation},
            "metadata": engine.experiment_metadata()}


def _mean(values):
    values = [value for value in values if value is not None]
    return statistics.fmean(values) if values else None


def _aggregate(runs: list[dict]) -> dict:
    """Mean over the declared seeds for queue, discharge and travel time; pooled pairs for arrival order."""
    queue = {boundary: {"value": _mean([run["queue"][boundary]["value"] for run in runs]), "samples": sum(run["queue"][boundary]["samples"] for run in runs)}
             for boundary in runs[0]["queue"]}
    discharge = {boundary: {index: {"value": _mean([run["discharge"][boundary][index]["value"] for run in runs]), "complete": True}
                            for index in runs[0]["discharge"][boundary]} for boundary in runs[0]["discharge"]}
    medians = [run["travel_time"]["median"] for run in runs if run["travel_time"]["median"] is not None]
    travel = {"mean": _mean([run["travel_time"]["mean"] for run in runs]), "median": statistics.median(medians) if medians else None,
              "count": sum(run["travel_time"]["count"] for run in runs), "unfinished": sum(run["travel_time"]["unfinished"] for run in runs), "complete": True}
    eligible = sum(run["arrival_order"]["eligible"] for run in runs)
    respected = sum(run["arrival_order"]["respected"] for run in runs)
    excluded: dict[str, int] = {}
    for run in runs:
        for reason, count in run["arrival_order"]["excluded"].items():
            excluded[reason] = excluded.get(reason, 0) + count
    safety = {"overlaps": sum(run["safety"]["overlaps"] for run in runs), "stuck_junction_vehicles": max(run["safety"]["stuck_junction_vehicles"] for run in runs),
              "gridlock_seconds": max(run["safety"]["gridlock_seconds"] for run in runs),
              "vehicle_conservation_error": max(run["safety"]["vehicle_conservation_error"] for run in runs)}
    return {"queue": queue, "discharge": discharge, "travel_time": travel,
            "arrival_order": {"eligible": eligible, "respected": respected, "share": respected / eligible if eligible else None, "excluded": excluded},
            "safety": safety}


def simulated_measures(scenario: dict, mapping: dict, *, seeds, origin_s: float, start_s: float, end_s: float, criteria: dict, engine_factory=None) -> dict:
    """Run the scenario under no-signal control for each development seed and measure it like the video."""
    seeds = list(seeds)
    if not seeds or any(isinstance(seed, bool) or seed not in DEVELOPMENT_SEEDS for seed in seeds):
        raise ValueError("Validation runs use the development seeds 101-110; final seeds 201-220 are reserved for the final study")
    if engine_factory is None:
        from simulation.network_registry import engine_for_scenario
        engine_factory = lambda seed: engine_for_scenario(scenario, seed=seed)  # noqa: E731
    runs = [_run_seed(engine_factory(seed), seed, mapping, criteria, origin_s=origin_s, start_s=start_s, end_s=end_s) for seed in seeds]
    metadata = runs[0]["metadata"]
    result = _aggregate(runs)
    result["per_seed"] = [{key: value for key, value in run.items() if key != "metadata"} for run in runs]
    result["model_identity"] = {"engine_version": metadata["engine_version"], "network_sha256": metadata["network_sha256"],
                                "site_calibration_sha256": metadata["site_calibration_sha256"], "demand_sha256": metadata["demand_sha256"],
                                "controller": "no-signal", "seeds": seeds}
    return result
