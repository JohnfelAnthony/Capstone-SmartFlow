"""Provisional mixed-traffic parameters: class driving values and per-vehicle driver variety.

All values are provisional (2026-10 design) and are to be calibrated against Field Observer data.
"""
from __future__ import annotations

import math
import random
from dataclasses import dataclass


@dataclass(frozen=True)
class DrivingParameters:
    time_headway: float
    minimum_gap: float
    max_acceleration: float
    max_lateral_speed: float


@dataclass(frozen=True)
class DriverProfile:
    speed_multiplier: float
    time_headway: float
    minimum_gap: float
    max_acceleration: float
    max_lateral_speed: float


CLASS_DRIVING = {
    "car": DrivingParameters(1.2, 2.0, 1.5, 0.5),
    "motorcycle": DrivingParameters(0.8, 1.0, 2.0, 1.0),
    "tricycle": DrivingParameters(1.2, 1.5, 1.0, 0.6),
    "bus": DrivingParameters(1.5, 2.5, 0.8, 0.3),
    "truck": DrivingParameters(1.5, 2.5, 0.8, 0.3),
}
DRIVER_STREAM_SALT = 0x445256
SPEED_VARIATION_SD = 0.08
SPEED_MULTIPLIER_RANGE = (0.8, 1.2)
HEADWAY_VARIATION_SD = 0.15
HEADWAY_MULTIPLIER_RANGE = (0.7, 1.4)


SIDE_CLEARANCE_M = 0.3
# Least gap a sideways move leaves beside a neighbour: bands are lane coordinates, and where a lane bends two bodies
# straddling the bend point slightly apart, so flush bands overlap as drawn (covers ~0.3 degrees over a 10 m body).
ALONGSIDE_GAP_M = 0.05
EDGE_CLEARANCE_M = 0.1
LATERAL_GRID_M = 0.25
# Cars, buses and trucks keep to the centre-line side of their lane portion; tricycles keep to the kerb.
LANE_KEEPING_CLASSES = frozenset({"car", "bus", "truck"})
KERB_KEEPING_CLASSES = frozenset({"tricycle"})
# Sideways decisions. The turn-side weight must exceed the move cost, or a turning vehicle never gains enough to move.
LATERAL_DECISION_TICKS = 5
MOVE_GAIN_THRESHOLD_M = 2.0
MOVE_COST_PER_M = 1.0
KEEPING_WEIGHT_PER_M = 2.0
TURN_SIDE_WEIGHT_PER_M = 2.0
TURN_SIDE_DISTANCE_M = 30.0
MOVE_COOLDOWN_SECONDS = 2.0
ROOM_HORIZON_M = 50.0
MAX_YAW_DEGREES = 10.0
# Riders shuffle sideways with their feet when slow or stopped; other classes move sideways only while moving forward.
MOTORCYCLE_SHUFFLE_MPS = 0.3


def lateral_bounds(lane_width: float, vehicle_width: float, edge_clearance: float = EDGE_CLEARANCE_M) -> tuple[float, float]:
    """Range of a body's centre across its lane (positive toward the right-hand kerb)."""
    half = (lane_width-vehicle_width)/2-edge_clearance
    return (0.0, 0.0) if half < 0 else (-half, half)


def bands_overlap(lateral_a: float, width_a: float, lateral_b: float, width_b: float, clearance: float = SIDE_CLEARANCE_M) -> bool:
    return abs(lateral_a-lateral_b) < (width_a+width_b)/2+clearance-1e-9


def body_box(length: float, width: float, yaw: float) -> tuple[float, float]:
    """Along-road length and across-road width of the road-aligned box around a body turned by yaw."""
    if yaw == 0:
        return length, width
    turn = abs(yaw)
    return length*math.cos(turn)+width*math.sin(turn), length*math.sin(turn)+width*math.cos(turn)


def candidate_laterals(lane_width: float, vehicle_width: float) -> list[float]:
    low, high = lateral_bounds(lane_width, vehicle_width)
    steps = int(math.floor((high-low)/LATERAL_GRID_M+1e-9))
    values = [round(low+index*LATERAL_GRID_M, 6) for index in range(steps+1)]
    if values[-1] < round(high, 6):
        values.append(round(high, 6))
    return values


def sub_lane_of(lateral: float, lane_width: float, lane_count: int) -> int:
    return min(lane_count-1, max(0, int((lateral+lane_width/2)//(lane_width/lane_count))))


def keeping_position(vehicle_type: str, vehicle_width: float, lane_width: float, lane_count: int, sub_lane: int) -> float | None:
    """Where a class prefers to sit in a lane portion; None for motorcycles, which have no keeping position."""
    low, high = lateral_bounds(lane_width, vehicle_width)
    if vehicle_type in LANE_KEEPING_CLASSES:
        preferred = -lane_width/2+sub_lane*(lane_width/lane_count)+EDGE_CLEARANCE_M+vehicle_width/2
        return min(high, max(low, preferred))
    if vehicle_type in KERB_KEEPING_CLASSES:
        return high
    return None


def _clip(value: float, bounds: tuple[float, float]) -> float:
    return min(bounds[1], max(bounds[0], value))


def sample_driver(vehicle_type: str, rng: random.Random, variation_scale: float) -> DriverProfile:
    """Always draws exactly two gaussians (speed, then headway), so the stream stays aligned at any scale."""
    speed_noise, headway_noise = rng.gauss(0, SPEED_VARIATION_SD), rng.gauss(0, HEADWAY_VARIATION_SD)
    base = CLASS_DRIVING[vehicle_type]
    speed_multiplier = _clip(1 + variation_scale*speed_noise, SPEED_MULTIPLIER_RANGE)
    headway_multiplier = _clip(1 + variation_scale*headway_noise, HEADWAY_MULTIPLIER_RANGE)
    return DriverProfile(speed_multiplier, base.time_headway*headway_multiplier, base.minimum_gap,
                         base.max_acceleration, base.max_lateral_speed)
