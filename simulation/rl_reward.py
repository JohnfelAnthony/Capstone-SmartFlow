from __future__ import annotations

from dataclasses import asdict, dataclass

from .rl_state import APPROACH_ORDER, MAX_PEDESTRIAN_WAITING, MAX_QUEUE_COUNT, RLSnapshot, _clamp, _normalize

REWARD_VERSION = "reward_v3"
# One lane is green at a time; the engine discharges a saturated lane at about one vehicle per 2.0-2.4 s.
SATURATION_HEADWAY_SECONDS = 2.0


@dataclass(frozen=True)
class RewardBreakdown:
    total: float
    discharge_bonus: float
    delay_penalty: float
    queue_penalty: float
    pedestrian_penalty: float
    switch_penalty: float

    def to_dict(self) -> dict[str, float]:
        return asdict(self)


def calculate_reward(previous_snapshot: RLSnapshot, current_snapshot: RLSnapshot) -> RewardBreakdown:
    """reward_v3: only the controlled junction, only what happened since the previous decision."""
    interval = current_snapshot.simulation_time - previous_snapshot.simulation_time
    stopped_seconds = max(0.0, current_snapshot.junction_stopped_seconds - previous_snapshot.junction_stopped_seconds)
    passages = max(0, current_snapshot.junction_passages - previous_snapshot.junction_passages)
    # Stopped vehicle-seconds per second is the mean number of stopped vehicles; spread over the approaches.
    mean_stopped_per_approach = stopped_seconds / interval / len(APPROACH_ORDER) if interval > 0 else 0.0

    delay_penalty = 1.0 * _normalize(mean_stopped_per_approach, MAX_QUEUE_COUNT)
    queue_penalty = 0.5 * _normalize(float(max(current_snapshot.queue_by_approach.values(), default=0)), MAX_QUEUE_COUNT)
    discharge_bonus = 0.5 * _normalize(float(passages), interval / SATURATION_HEADWAY_SECONDS) if interval > 0 else 0.0
    pedestrian_penalty = 0.25 * _normalize(float(current_snapshot.pedestrian_waiting_count), MAX_PEDESTRIAN_WAITING)
    phase_switch_delta = max(0, current_snapshot.total_phase_switches - previous_snapshot.total_phase_switches)
    switch_penalty = 0.05 * _clamp(float(phase_switch_delta), 0.0, 1.0)

    total_reward = discharge_bonus - delay_penalty - queue_penalty - pedestrian_penalty - switch_penalty

    return RewardBreakdown(
        total=round(total_reward, 6),
        discharge_bonus=round(discharge_bonus, 6),
        delay_penalty=round(delay_penalty, 6),
        queue_penalty=round(queue_penalty, 6),
        pedestrian_penalty=round(pedestrian_penalty, 6),
        switch_penalty=round(switch_penalty, 6),
    )
