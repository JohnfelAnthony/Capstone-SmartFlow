"""Atomic admission for one compute workload in this API process."""
from threading import Lock

DESKTOP_SHUTDOWN = "desktop shutdown"


class WorkloadConflict(RuntimeError):
    pass


class WorkloadAdmission:
    def __init__(self):
        self._lock = Lock()
        self._lease = None
        self._kind = None

    def acquire(self, kind: str, existing=None):
        with self._lock:
            if existing is not None and existing is self._lease and kind == self._kind:
                return existing
            if self._lease is not None:
                raise WorkloadConflict(
                    f"SmartFlow is busy with {self._kind}. Stop it or wait for completion before starting {kind}."
                )
            self._lease, self._kind = object(), kind
            return self._lease

    def release(self, lease):
        with self._lock:
            if lease is not None and lease is self._lease:
                self._lease = self._kind = None

    def check_replay_allowed(self):
        """Replay is non-compute work, but may not start during final shutdown."""
        with self._lock:
            if self._kind == DESKTOP_SHUTDOWN:
                raise WorkloadConflict("SmartFlow is shutting down; replay cannot start.")


workload_admission = WorkloadAdmission()
