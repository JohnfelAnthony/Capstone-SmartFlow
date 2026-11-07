"""Pre-generated arrival schedule independent of controller, queues and closures."""
from __future__ import annotations

import hashlib
import json
import random
from dataclasses import dataclass


@dataclass(frozen=True)
class Arrival:
    time: float
    source: str
    destination: str
    vehicle_type: str = "car"


def build_schedule(config: dict, network, seed: int, duration: float) -> list[Arrival]:
    rng = random.Random(seed)
    pairs = [(a, b) for a in network.boundaries for b in network.boundaries if a != b and network.route(a, b)]
    mix = config["vehicle_mix"]
    windows = config["demand_windows"]
    if not windows and not config["trips"] and config["traffic_density"] not in {"none", "single"}:
        rates = {"low": 432, "medium": 1080, "high": 2340, "very high": 3420}
        windows = [{"start": 0, "end": duration, "vehicles_per_hour": rates[config["traffic_density"]]}]
    arrivals = [Arrival(trip["time"], trip["source"], trip["destination"], trip["vehicle_type"]) for trip in config["trips"] if trip["time"] < duration]
    if len(arrivals) > 100000:
        raise ValueError("Experiment exceeds 100,000 scheduled vehicles; shorten the duration or lower demand")
    for window in windows:
        rate = window["vehicles_per_hour"]/3600
        if not rate:
            continue
        time = window["start"] + rng.expovariate(rate)
        od = window.get("od") or [{"source": a, "destination": b, "weight": 1} for a, b in pairs]
        # Default synthetic demand chooses a legal OD for each sampled class.
        # Explicit observed OD streams are validated, never silently redistributed.
        class_od = {}
        if network.lane_vehicle_restrictions and not window.get("od"):
            kinds = [window["vehicle_type"]] if "vehicle_type" in window else [kind for kind, weight in mix.items() if weight > 0]
            for kind in kinds:
                class_od[kind] = [item for item in od if network.route(item["source"], item["destination"], vehicle_type=kind)]
                if not class_od[kind]:
                    raise ValueError(f"No route satisfies vehicle access restrictions for {kind}")
        while time < min(window["end"], duration):
            pair = rng.choices(od, [item["weight"] for item in od])[0]
            kind = window.get("vehicle_type") or rng.choices(list(mix), list(mix.values()))[0]  # a classed stream draws no mix sample
            if class_od and pair not in class_od[kind]:
                eligible = class_od[kind]
                pair = rng.choices(eligible, [item["weight"] for item in eligible])[0]
            arrivals.append(Arrival(round(time, 6), pair["source"], pair["destination"], kind))
            time += rng.expovariate(rate)
            if len(arrivals) > 100000:
                raise ValueError("Experiment exceeds 100,000 scheduled vehicles; shorten the duration or lower demand")
    arrivals.sort(key=lambda arrival: arrival.time)
    return arrivals


def schedule_hash(arrivals: list[Arrival]) -> str:
    return hashlib.sha256(json.dumps([vars(item) for item in arrivals], sort_keys=True).encode()).hexdigest()
