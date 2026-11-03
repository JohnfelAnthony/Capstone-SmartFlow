import threading
import os
from types import SimpleNamespace

import pytest

os.environ.setdefault("SMARTFLOW_SECRET_KEY", "network-revision-guard-test")
os.environ.setdefault("SMARTFLOW_BOOTSTRAP_ADMIN_PASSWORD", "RevisionGuardTest123!")

from backend.simulation_runtime import SimulationRuntime, SimulationRuntimeError
from services.workload_admission import WorkloadConflict, workload_admission


@pytest.mark.parametrize("kind", ["recording", "training/evaluation", "live simulation"])
def test_revision_guard_refuses_active_compute_work(kind):
    runtime = SimulationRuntime()
    lease = workload_admission.acquire(kind)
    try:
        with pytest.raises(SimulationRuntimeError, match="busy"):
            with runtime.network_revision_guard():
                pass
    finally:
        workload_admission.release(lease)


@pytest.mark.parametrize("mode,status", [("live", "running"), ("live", "paused"), ("playback", "paused"), ("playback", "stopped")])
def test_revision_guard_refuses_active_or_loaded_runtime(mode, status):
    runtime = SimulationRuntime()
    runtime._engine = SimpleNamespace(status=status)
    runtime._run_mode = mode
    with pytest.raises(SimulationRuntimeError):
        with runtime.network_revision_guard():
            pass


def test_guard_excludes_compute_and_racing_playback_and_releases_on_error():
    runtime = SimulationRuntime()
    started, finished = threading.Event(), threading.Event()
    def attempt_playback():
        started.set()
        try:
            runtime.start_playback()
        except SimulationRuntimeError:
            pass
        finally:
            finished.set()
    thread = threading.Thread(target=attempt_playback)
    with pytest.raises(RuntimeError, match="injected failure"):
        with runtime.network_revision_guard():
            with pytest.raises(WorkloadConflict):
                workload_admission.acquire("training/evaluation")
            thread.start()
            assert started.wait(2)
            assert not finished.wait(.1)
            raise RuntimeError("injected failure")
    thread.join(3)
    assert finished.is_set() and not thread.is_alive()
    lease = workload_admission.acquire("recording")
    workload_admission.release(lease)


def test_idle_state_is_discarded_only_after_the_registry_commits():
    runtime = SimulationRuntime()
    old_engine = SimpleNamespace(status="stopped")
    runtime._engine = old_engine
    runtime._selected_scenario_id = 17
    runtime._selected_scenario_name = "Old site"
    runtime._owner_user_id = 3
    with pytest.raises(RuntimeError, match="before commit"):
        with runtime.network_revision_guard():
            raise RuntimeError("before commit")
    assert runtime._engine is old_engine and runtime._selected_scenario_id == 17
    with runtime.network_revision_guard() as invalidate:
        invalidate()
        assert runtime._engine is None and runtime._selected_scenario_id is None
        assert runtime._owner_user_id is None
    with pytest.raises(RuntimeError, match="not held"):
        invalidate()


def test_unfinalized_run_blocks_revision_even_if_engine_reports_error():
    runtime = SimulationRuntime()
    runtime._engine = SimpleNamespace(status="error")
    runtime._active_run_id = 42
    with pytest.raises(SimulationRuntimeError, match="Stop"):
        with runtime.network_revision_guard():
            pass
