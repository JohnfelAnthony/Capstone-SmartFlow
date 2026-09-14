from __future__ import annotations

from dataclasses import asdict, dataclass

from .rl_state import APPROACH_ORDER, RLSnapshot, _clamp, _normalize

MAX_THROUGHPUT_DELTA = 10.0
EMERGENCY_SERVED_PENALTY_SCALE = 0.25


@dataclass(frozen=True)
class RewardBreakdown:
    total: float
    throughput_bonus: float
    wait_penalty: float
    queue_penalty: float
    max_queue_penalty: float
    pedestrian_penalty: float
    emergency_penalty: float
    switch_penalty: float

    def to_dict(self) -> dict[str, float]:
        return asdict(self)


def _critical_emergency_penalty(snapshot: RLSnapshot) -> float:
    critical_approach = None
    critical_proximity = 0.0
    for approach in APPROACH_ORDER:
        if not snapshot.emergency_presence_by_approach[approach]:
            continue
        proximity = float(snapshot.emergency_proximity_by_approach[approach] or 0.0)
        if proximity >= critical_proximity:
            critical_approach = approach
            critical_proximity = proximity

    if not critical_approach:
        return 0.0

    served_family = snapshot.phase_family.lower()
    if served_family == critical_approach:
        return round(critical_proximity * EMERGENCY_SERVED_PENALTY_SCALE, 6)
    return round(critical_proximity, 6)


def calculate_reward(previous_snapshot: RLSnapshot, current_snapshot: RLSnapshot) -> RewardBreakdown:
    throughput_delta = max(0, current_snapshot.throughput - previous_snapshot.throughput)
    throughput_bonus = 0.5 * _normalize(float(throughput_delta), MAX_THROUGHPUT_DELTA)
    wait_penalty = 1.0 * _normalize(current_snapshot.avg_wait, 120.0)
    queue_penalty = 0.8 * _normalize(current_snapshot.avg_queue, 30.0)
    max_queue_penalty = 0.4 * _normalize(float(current_snapshot.max_queue), 30.0)
    pedestrian_penalty = 0.5 * _normalize(float(current_snapshot.pedestrian_waiting_count), 20.0)
    emergency_penalty = 1.5 * _critical_emergency_penalty(current_snapshot)
    phase_switch_delta = max(0, current_snapshot.total_phase_switches - previous_snapshot.total_phase_switches)
    switch_penalty = 0.05 * _clamp(float(phase_switch_delta), 0.0, 1.0)

    total_reward = (
        throughput_bonus
        - wait_penalty
        - queue_penalty
        - max_queue_penalty
        - pedestrian_penalty
        - emergency_penalty
        - switch_penalty
    )

    return RewardBreakdown(
        total=round(total_reward, 6),
        throughput_bonus=round(throughput_bonus, 6),
        wait_penalty=round(wait_penalty, 6),
        queue_penalty=round(queue_penalty, 6),
        max_queue_penalty=round(max_queue_penalty, 6),
        pedestrian_penalty=round(pedestrian_penalty, 6),
        emergency_penalty=round(emergency_penalty, 6),
        switch_penalty=round(switch_penalty, 6),
    )
