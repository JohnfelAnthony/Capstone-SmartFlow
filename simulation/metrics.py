"""Simulation metrics — computed live from engine state."""

from typing import List
from .vehicles import Vehicle
from .pedestrians import Pedestrian


class MetricsCollector:
    """Computes and stores per-step and cumulative metrics."""

    def __init__(self):
        self.reset()

    def reset(self):
        self.step_count = 0
        self.total_vehicles_spawned = 0
        self.total_vehicles_completed = 0
        self.total_pedestrians_spawned = 0
        self.total_pedestrians_completed = 0

        # Running sums for averaging
        self._wait_sum = 0.0
        self._queue_sum = 0.0
        self._ped_delay_sum = 0.0
        self._max_queue = 0

    def update(self, vehicles: List[Vehicle], pedestrians: List[Pedestrian]):
        self.step_count += 1

        active = [v for v in vehicles if v.active and v.state == "active"]
        waiting = [v for v in active if v.speed < 0.1]

        # Waiting time
        for v in active:
            self._wait_sum += v.wait_time * 0.5  # weighted by dt rationale

        # Queue length
        queue = len(waiting)
        self._queue_sum += queue
        self._max_queue = max(self._max_queue, queue)

        # Pedestrian delay
        for p in pedestrians:
            if p.state == "waiting":
                self._ped_delay_sum += 0.5  # per-step contribution

    def record_spawn(self, count: int = 0, peds: int = 0):
        self.total_vehicles_spawned += count
        self.total_pedestrians_spawned += peds

    def record_completion(self, count: int = 0, peds: int = 0):
        self.total_vehicles_completed += count
        self.total_pedestrians_completed += peds

    @property
    def avg_wait(self) -> float:
        if self.step_count == 0:
            return 0.0
        return round(self._wait_sum / self.step_count, 1)

    @property
    def avg_queue(self) -> float:
        if self.step_count == 0:
            return 0.0
        return round(self._queue_sum / self.step_count, 1)

    @property
    def max_queue(self) -> int:
        return self._max_queue

    @property
    def avg_ped_delay(self) -> float:
        if self.step_count == 0:
            return 0.0
        return round(self._ped_delay_sum / self.step_count, 1)

    @property
    def throughput(self) -> int:
        return self.total_vehicles_completed

    def to_dict(self) -> dict:
        return {
            "avg_wait": self.avg_wait,
            "avg_queue": self.avg_queue,
            "max_queue": self.max_queue,
            "throughput": self.throughput,
            "avg_ped_delay": self.avg_ped_delay,
            "total_vehicles_spawned": self.total_vehicles_spawned,
            "total_vehicles_completed": self.total_vehicles_completed,
            "total_pedestrians_spawned": self.total_pedestrians_spawned,
            "total_pedestrians_completed": self.total_pedestrians_completed,
            "step_count": self.step_count,
        }
