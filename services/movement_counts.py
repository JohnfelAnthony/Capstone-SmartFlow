"""The one scenario CSV layout: from,to,vehicle_type,count — vehicles per hour for each movement at a study site."""
from __future__ import annotations

import csv
import hashlib
import io
import math

from simulation.network_registry import load_registered_network
from simulation.scenario_config import DEFAULTS, STEADY_DEMAND_END_SECONDS, VEHICLE_TYPES, is_study_site, number, validate_config

COLUMNS = ("from", "to", "vehicle_type", "count")
MAX_CSV_BYTES = 1_000_000


def _heading(lane, at_start: bool) -> float:
    a, b = lane.shape[:2] if at_start else lane.shape[-2:]
    return math.atan2(b[1]-a[1], b[0]-a[0])


def _turn(first: float, second: float) -> float:
    return abs((first-second+math.pi) % (2*math.pi)-math.pi)


def _leg_boundary(network, lane, upstream: bool) -> str:
    """The boundary node a leg reaches, going straight on through any neighboring junction."""
    node = lane.source if upstream else lane.target
    while not network.nodes[node].get("boundary"):
        if upstream:
            candidates = [network.lanes[other] for other in network.incoming[node] if network.turn_allowed(other, lane.id)]
            lane = min(candidates, key=lambda other: _turn(_heading(other, False), _heading(lane, True)))
            node = lane.source
        else:
            candidates = [network.lanes[other] for other in network.outgoing[node] if network.turn_allowed(lane.id, other)]
            lane = min(candidates, key=lambda other: _turn(_heading(lane, False), _heading(other, True)))
            node = lane.target
    return node


def approach_boundaries(network) -> dict[str, tuple[str, str]]:
    """Each approach of the study junction (the network's first) as its (entry boundary, exit boundary)."""
    if not is_study_site(network.id):
        raise ValueError("Movement counts need a study site")
    junction = network.intersections[0]
    outgoing = [network.lanes[lane_id] for lane_id in network.outgoing[junction]]
    result, used = {}, set()
    for lane_id in network.incoming[junction]:
        incoming = network.lanes[lane_id]
        # A split carriageway leaves on a different road, so the leg's exit is the lane running back the way the entry came.
        backward = _heading(incoming, False)+math.pi
        exit_lane = min(outgoing, key=lambda lane: _turn(_heading(lane, True), backward))
        if exit_lane.id in used:
            raise ValueError("Two approaches match one exit; the site needs an explicit approach mapping")
        used.add(exit_lane.id)
        result[incoming.approach] = (_leg_boundary(network, incoming, True), _leg_boundary(network, exit_lane, False))
    return result


def import_movement_counts(*, csv_text: str, network_id: str, engine_config: dict) -> dict:
    """Replace the draft's vehicle demand with one steady stream per movement and class; pedestrians are untouched."""
    if not isinstance(csv_text, str) or not csv_text.strip():
        raise ValueError("The CSV file is empty")
    if len(csv_text.encode("utf-8")) > MAX_CSV_BYTES:
        raise ValueError("The CSV file must be at most 1 MB")
    network = load_registered_network(network_id)
    approaches = approach_boundaries(network)
    reader = csv.DictReader(io.StringIO(csv_text.lstrip("﻿"), newline=""))
    headers = [name.strip().lower() for name in reader.fieldnames or []]
    if tuple(headers) != COLUMNS:
        raise ValueError(f"CSV columns must be exactly: {','.join(COLUMNS)}")
    windows, seen = [], set()
    for row_number, raw in enumerate(reader, start=2):
        if None in raw or any(value is None for value in raw.values()):
            raise ValueError(f"Row {row_number}: needs exactly 4 values")
        row = {key.strip().lower(): value.strip().lower() for key, value in raw.items()}
        if not any(row.values()):
            continue
        for column in ("from", "to"):
            if row[column] not in approaches:
                raise ValueError(f"Row {row_number}: {column} '{row[column]}' must be one of {', '.join(sorted(approaches))}")
        if row["from"] == row["to"]:
            raise ValueError(f"Row {row_number}: from and to must be different approaches")
        if row["vehicle_type"] not in VEHICLE_TYPES:
            raise ValueError(f"Row {row_number}: vehicle_type must be one of {', '.join(VEHICLE_TYPES)}")
        try:
            count = number(row["count"], "count", 0, 36000)
        except ValueError as exc:
            raise ValueError(f"Row {row_number}: count must be a number from 0 to 36000 vehicles per hour") from exc
        movement = (row["from"], row["to"], row["vehicle_type"])
        if movement in seen:
            raise ValueError(f"Row {row_number}: {' → '.join(movement[:2])} {movement[2]} appears twice")
        seen.add(movement)
        if count:
            windows.append({"start": 0.0, "end": STEADY_DEMAND_END_SECONDS, "vehicles_per_hour": count, "vehicle_type": row["vehicle_type"],
                            "label": f"{row['from']} to {row['to']} {row['vehicle_type']}",
                            "od": [{"source": approaches[row["from"]][0], "destination": approaches[row["to"]][1], "weight": 1}]})
    if not windows:
        raise ValueError("The CSV needs at least one row with a count above 0")
    candidate = {**engine_config, "traffic_density": "none", "trips": [], "demand_windows": windows,
                 "demand_source": {"kind": "synthetic", "description": f"Movement counts CSV, provenance not recorded (sha256 {hashlib.sha256(csv_text.encode('utf-8')).hexdigest()[:12]})"}}
    return {"engine_config": validate_config(DEFAULTS, candidate, network),
            "rows": len(windows), "vehicles_per_hour": sum(window["vehicles_per_hour"] for window in windows)}
