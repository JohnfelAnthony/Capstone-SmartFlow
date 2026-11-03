from types import SimpleNamespace
from threading import Event, Thread

import pytest

from desktop.shutdown import reserve_idle_shutdown
from services.workload_admission import DESKTOP_SHUTDOWN, WorkloadAdmission, WorkloadConflict


def test_busy_workload_or_paused_replay_refuses_shutdown():
    admission = WorkloadAdmission()
    runtime = SimpleNamespace(get_state=lambda: SimpleNamespace(status="stopped"))
    lease = admission.acquire("recording")
    reserved, reason = reserve_idle_shutdown(admission, runtime)
    assert reserved is None and "recording" in reason
    admission.release(lease)
    runtime.get_state = lambda: SimpleNamespace(status="paused")
    reserved, reason = reserve_idle_shutdown(admission, runtime)
    assert reserved is None and "active" in reason
    lease = admission.acquire("recording")
    admission.release(lease)


def test_idle_shutdown_excludes_racing_new_work():
    admission = WorkloadAdmission()
    runtime = SimpleNamespace(get_state=lambda: SimpleNamespace(status="stopped"))
    reserved, reason = reserve_idle_shutdown(admission, runtime)
    assert reserved is not None and reason is None
    with pytest.raises(WorkloadConflict):
        admission.acquire("recording")


def test_shutdown_blocks_replay_start_and_resume_but_not_other_work(monkeypatch):
    import backend.simulation_runtime as module
    admission = WorkloadAdmission()
    monkeypatch.setattr(module, "workload_admission", admission)
    engine = SimpleNamespace(status="paused", start=lambda _duration: None, resume=lambda: None)
    runtime = module.SimulationRuntime()
    runtime._engine = engine
    runtime._run_mode = "playback"
    runtime._response = lambda: SimpleNamespace(status=engine.status)
    shutdown = admission.acquire(DESKTOP_SHUTDOWN)
    with pytest.raises(module.SimulationRuntimeError, match="shutting down"):
        runtime.start_playback()
    with pytest.raises(module.SimulationRuntimeError, match="shutting down"):
        runtime.resume()
    admission.release(shutdown)
    training = admission.acquire("training/evaluation")
    assert runtime.start_playback().status == "paused"
    admission.release(training)


def test_shutdown_racing_replay_observes_active_replay(monkeypatch):
    import backend.simulation_runtime as module
    reserved = Event()
    class ObservableAdmission(WorkloadAdmission):
        def acquire(self, kind, existing=None):
            lease = super().acquire(kind, existing)
            if kind == DESKTOP_SHUTDOWN:
                reserved.set()
            return lease
    admission = ObservableAdmission()
    monkeypatch.setattr(module, "workload_admission", admission)
    entered, proceed = Event(), Event()
    engine = SimpleNamespace(status="stopped")
    def start(_duration):
        entered.set()
        assert proceed.wait(10)
        engine.status = "running"
    engine.start = start
    runtime = module.SimulationRuntime()
    runtime._engine = engine
    runtime._run_mode = "playback"
    runtime._response = lambda: SimpleNamespace(status=engine.status)
    runtime._start_background_runner_locked = lambda: None
    replay = Thread(target=runtime.start_playback)
    outcome = []
    replay.start()
    assert entered.wait(10)
    shutdown = Thread(target=lambda: outcome.append(reserve_idle_shutdown(admission, runtime)))
    shutdown.start()
    assert reserved.wait(10)
    proceed.set()
    replay.join(timeout=10)
    shutdown.join(timeout=10)
    assert not replay.is_alive() and not shutdown.is_alive()
    assert outcome and outcome[0][0] is None and "active" in outcome[0][1]
