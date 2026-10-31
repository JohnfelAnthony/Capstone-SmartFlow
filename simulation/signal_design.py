"""Provisional Webster calculations; results require field review before use."""
from __future__ import annotations

import math
from dataclasses import dataclass

from simulation.scenario_config import DEFAULTS

# Provisional: replace with locally measured or cited passenger-car equivalents.
PCU_FACTORS_PROVISIONAL = {"car": 1.0, "motorcycle": 0.5, "tricycle": 1.0, "bus": 2.0, "truck": 2.5}
# Provisional: replace with measured or cited site-specific saturation flow.
SATURATION_PCU_PER_HOUR_PER_3_3_M = 1800.0


@dataclass(frozen=True)
class WebsterResult:
    cycle_seconds: float
    webster_cycle_seconds: float
    phase_order: list
    phase_greens: list[float]
    flow_ratios: list[float]
    total_flow_ratio: float
    lost_time_seconds: float
    warnings: list[str]
    assumptions: dict


def _nonnegative(value, label):
    if isinstance(value, bool) or not isinstance(value, (float, int)) or not math.isfinite(value) or value < 0:
        raise ValueError(f"{label} must be a nonnegative finite number")
    return float(value)


def flows_from_counts(vehicles_per_hour_by_class: dict, pcu: dict = PCU_FACTORS_PROVISIONAL) -> dict:
    if not isinstance(vehicles_per_hour_by_class, dict):
        raise ValueError("Counts must map approaches to vehicle classes")
    result = {}
    for approach, counts in vehicles_per_hour_by_class.items():
        if not isinstance(counts, dict):
            raise ValueError(f"Counts for {approach} must map vehicle classes to rates")
        total = 0.0
        for kind, count in counts.items():
            if kind not in pcu:
                raise ValueError(f"No passenger-car equivalent for {kind}")
            total += _nonnegative(count, "vehicle count") * _nonnegative(pcu[kind], "PCU factor")
        result[approach] = total
    return result


def saturation_from_network(network, junction: str) -> dict:
    if junction not in network.intersections:
        raise ValueError("Unknown junction")
    result = {}
    for lane_id in network.incoming[junction]:
        lane = network.lanes[lane_id]
        result[lane.approach] = result.get(lane.approach, 0.0) + lane.width / 3.3 * SATURATION_PCU_PER_HOUR_PER_3_3_M
    return result


def webster_plan(phase_order, flows_pcu_per_hour, saturation_pcu_per_hour, *, yellow_seconds=3.0,
                 all_red_seconds=1.0, startup_lost_seconds=2.0, pedestrian_green_seconds=None,
                 minimum_green=10.0, maximum_green=60.0, cycle_limits=(40.0, 120.0)):
    yellow = _nonnegative(yellow_seconds, "yellow_seconds")
    all_red = _nonnegative(all_red_seconds, "all_red_seconds")
    startup = _nonnegative(startup_lost_seconds, "startup_lost_seconds")
    minimum = _nonnegative(minimum_green, "minimum_green")
    maximum = _nonnegative(maximum_green, "maximum_green")
    if minimum <= 0 or maximum < minimum or len(cycle_limits) != 2:
        raise ValueError("Invalid green or cycle limits")
    low, high = (_nonnegative(v, "cycle limit") for v in cycle_limits)
    if low <= 0 or high < low:
        raise ValueError("Invalid green or cycle limits")
    if not isinstance(phase_order, list) or not phase_order:
        raise ValueError("At least one phase is required")
    phases, seen = [], set()
    for phase in phase_order:
        names = [phase] if isinstance(phase, str) else phase
        if not isinstance(names, list) or not names or any(not isinstance(v, str) or not v for v in names):
            raise ValueError("Invalid phase")
        if "pedestrian" in names and names != ["pedestrian"]:
            raise ValueError("Pedestrians require a separate phase")
        if any(name in seen for name in names) or len(set(names)) != len(names):
            raise ValueError("Each approach may appear in one phase only")
        seen.update(names)
        phases.append(names)
    vehicle_phases = [p for p in phases if p != ["pedestrian"]]
    if not vehicle_phases:
        raise ValueError("At least one vehicle phase is required")
    approaches = {name for phase in vehicle_phases for name in phase}
    if not approaches <= {"north", "east", "south", "west"}:
        raise ValueError("Vehicle phases must use known approach names")
    if set(flows_pcu_per_hour) - approaches or set(saturation_pcu_per_hour) - approaches:
        raise ValueError("Flow and saturation inputs must belong to a vehicle phase")
    ratios = []
    for names in vehicle_phases:
        values = []
        for name in names:
            flow = _nonnegative(flows_pcu_per_hour.get(name, 0), f"{name} flow")
            saturation = _nonnegative(saturation_pcu_per_hour.get(name), f"{name} saturation")
            if saturation <= 0:
                raise ValueError(f"{name} saturation must be positive")
            values.append(flow / saturation)
        ratios.append(max(values))
    total = sum(ratios)
    if total >= 1:
        raise ValueError(f"Total flow ratio Y must be below 1 for a fixed-time plan (Y={total:.2f})")
    has_walk = ["pedestrian"] in phases
    walk = _nonnegative(pedestrian_green_seconds if pedestrian_green_seconds is not None else
                        max(7, math.ceil(DEFAULTS["crossing_length"] / DEFAULTS["pedestrian_speed"])), "pedestrian green") if has_walk else 0
    if has_walk and not minimum <= walk <= maximum:
        raise ValueError("Pedestrian green must be within the phase green bounds")
    lost = len(vehicle_phases) * (startup + all_red) + (walk + all_red if has_walk else 0)
    optimal = math.ceil((1.5 * lost + 5) / (1 - total) - 1e-9)
    cycle = min(high, max(low, optimal))
    warnings = []
    if optimal < low:
        warnings.append(f"Cycle raised to the minimum cycle of {low:g} s (Webster gave {optimal:g} s)")
    if optimal > high:
        warnings.append(f"Cycle lowered to the maximum cycle of {high:g} s (Webster gave {optimal:g} s)")
    if total == 0:
        warnings.append("No vehicle demand; every phase gets its minimum green")
    greens, vehicle_index = [], 0
    for phase in phases:
        if phase == ["pedestrian"]:
            greens.append(walk)
            continue
        displayed = round((cycle - lost) * ratios[vehicle_index] / total + startup - yellow, 1) if total else minimum
        vehicle_index += 1
        if displayed < minimum:
            warnings.append(f"Phase {vehicle_index} green raised to the minimum green of {minimum:g} s")
        elif displayed > maximum:
            warnings.append(f"Phase {vehicle_index} green lowered to the maximum green of {maximum:g} s")
        greens.append(min(maximum, max(minimum, displayed)))
    actual = round(sum(g + all_red + (0 if p == ["pedestrian"] else yellow) for p, g in zip(phases, greens)), 1)
    if actual < low or actual > high:
        warnings.append(f"Actual cycle {actual:g} s is outside the cycle limits")
    return WebsterResult(actual, float(optimal), phase_order, greens, ratios, total, lost, warnings,
                         {"provisional": True, "startup_lost_seconds": startup, "pcu_factors": dict(PCU_FACTORS_PROVISIONAL),
                          "saturation_pcu_per_hour_per_3_3_m": SATURATION_PCU_PER_HOUR_PER_3_3_M})


def plan_from_result(result: WebsterResult, base_plan: dict) -> dict:
    if "pedestrian" not in result.phase_order:
        raise ValueError("A scenario plan needs a walk phase; include 'pedestrian' in phase_order")
    vehicle_greens = [green for phase, green in zip(result.phase_order, result.phase_greens) if phase != "pedestrian"]
    own_red = max(result.cycle_seconds - green for green in vehicle_greens)
    if "maximum_red_seconds" in base_plan and base_plan["maximum_red_seconds"] < own_red:
        raise ValueError(f"maximum_red_seconds is shorter than this plan's own fixed-time red ({own_red:g} s)")
    return {**base_plan, "mode": "signalized", "phase_order": result.phase_order, "phase_greens": result.phase_greens}
