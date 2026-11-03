"""Atomic idle-only shutdown admission for the desktop supervisor."""
from services.workload_admission import DESKTOP_SHUTDOWN, WorkloadConflict


def reserve_idle_shutdown(admission, runtime):
    try:
        lease = admission.acquire(DESKTOP_SHUTDOWN)
    except WorkloadConflict as exc:
        return None, str(exc)
    try:
        state = runtime.get_state()
        if state.status in {"running", "paused"}:
            admission.release(lease)
            return None, "A simulation or replay is active. Stop it in SmartFlow before closing."
        return lease, None
    except BaseException:
        admission.release(lease)
        raise
