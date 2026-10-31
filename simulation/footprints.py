"""Vehicle footprint geometry and run fingerprints for the mixed-traffic safety checks."""
from __future__ import annotations

import hashlib
import math

Corners = list[tuple[float, float]]
LATERAL_STATE = ("lateral", "lateral_speed", "lateral_target", "lateral_cooldown_until", "yaw",
                 "connector_entry_lateral", "connector_exit_lateral")


def rectangle(x: float, y: float, heading: float, length: float, width: float) -> Corners:
    """Four corners of a body centred at (x, y); heading in radians, x east, y north."""
    forward_x, forward_y = math.cos(heading)*length/2, math.sin(heading)*length/2
    right_x, right_y = math.sin(heading)*width/2, -math.cos(heading)*width/2
    return [(x+forward_x+right_x, y+forward_y+right_y), (x+forward_x-right_x, y+forward_y-right_y),
            (x-forward_x-right_x, y-forward_y-right_y), (x-forward_x+right_x, y-forward_y+right_y)]


def rectangles_overlap(a: Corners, b: Corners, tolerance: float = 1e-6) -> bool:
    """Separating-axis test; touching or separated within the tolerance is not an overlap."""
    for corners in (a, b):
        for index in range(2):
            (x1, y1), (x2, y2) = corners[index], corners[index+1]
            axis_x, axis_y = y1-y2, x2-x1
            norm = math.hypot(axis_x, axis_y)
            projected_a = [(px*axis_x+py*axis_y)/norm for px, py in a]
            projected_b = [(px*axis_x+py*axis_y)/norm for px, py in b]
            if max(projected_a) <= min(projected_b)+tolerance or max(projected_b) <= min(projected_a)+tolerance:
                return False
    return True


def record_rectangle(record: dict) -> Corners:
    """Body of a vehicle_records() entry, whose angle is (90 - degrees(heading)) % 360."""
    return rectangle(record["x"], record["y"], math.radians(90-record["angle"]), record["length"], record["width"])


def overlapping_pairs(records: list[dict]) -> list[tuple[str, str]]:
    """Sorted ID pairs whose bodies overlap; a sweep along x keeps it cheap enough for every tick."""
    bodies = sorted(((min(px for px, _ in corners), max(px for px, _ in corners), record["id"], corners)
                     for record in records for corners in [record_rectangle(record)]), key=lambda body: body[0])
    pairs, active = [], []
    for low, high, identity, corners in bodies:
        active = [body for body in active if body[1] >= low]
        pairs.extend(tuple(sorted((identity, other_id))) for _, _, other_id, other in active if rectangles_overlap(corners, other))
        active.append((low, high, identity, corners))
    return sorted(pairs)


def _longitudinal(vehicle) -> tuple:
    return (vehicle.id, tuple(vehicle.route), repr(vehicle.position), repr(vehicle.speed), repr(vehicle.wait),
            vehicle.connector is not None, repr(vehicle.connector_position), vehicle.reserved_junction)


def _longitudinal_sample(engine) -> list:
    return [_longitudinal(vehicle) for vehicle in sorted(engine.vehicles.values(), key=lambda vehicle: vehicle.id)]


def _state_sample(engine) -> tuple:
    # getattr lets the same fingerprint run on engines that have no sideways state yet.
    vehicles = [_longitudinal(vehicle)+tuple(repr(getattr(vehicle, name, None)) for name in LATERAL_STATE)
                for vehicle in sorted(engine.vehicles.values(), key=lambda vehicle: vehicle.id)]
    return (vehicles, sorted((node, sorted(ids)) for node, ids in engine.reservations.items()),
            sorted(engine.reservation_approach.items()))


def _digest(engine, seconds: float, sample_every_ticks: int, sample) -> str:
    digest = hashlib.sha256()
    while engine.simulation_time < seconds and engine.status == "running":
        engine.step(1)
        if engine.ticks % sample_every_ticks == 0:
            digest.update(repr(sample(engine)).encode())
    digest.update(repr(sample(engine)).encode())
    return digest.hexdigest()


def longitudinal_digest(engine, seconds: float, sample_every_ticks: int = 50) -> str:
    """Fingerprint of along-the-road state only, for comparing against native-5 behaviour."""
    return _digest(engine, seconds, sample_every_ticks, _longitudinal_sample)


def state_digest(engine, seconds: float, sample_every_ticks: int = 50) -> str:
    """Same-seed determinism fingerprint, including sideways state and junction reservations."""
    return _digest(engine, seconds, sample_every_ticks, _state_sample)
