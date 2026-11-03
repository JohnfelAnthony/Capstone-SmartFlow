from pathlib import Path
import subprocess
import sys

import pytest

from desktop.paths import DesktopPaths
from desktop.restore_switch import RestoreSwitch, RestoreSwitchError


class FakeBackend:
    def __init__(self, paths, frontend, *, fail=False):
        self.paths, self.frontend, self.fail = paths, frontend, fail
        self.running = True
        self.busy = False
        self.starts = 0

    def request_shutdown(self):
        return (False, "Stop active work") if self.busy else (True, None)

    def stop(self):
        self.running = False

    def start(self):
        self.starts += 1
        if self.fail:
            raise RuntimeError("synthetic startup failure")
        self.running = True
        return "http://127.0.0.1:12345"


@pytest.fixture
def setup_switch(tmp_path):
    control = tmp_path / "desktop"
    resources = tmp_path / "resources"
    frontend = resources / "dist"
    frontend.mkdir(parents=True)
    (control / "data").mkdir(parents=True)
    (control / "data" / "smartflow.db").write_bytes(b"old")
    switch = RestoreSwitch(control, resources, frontend, backend_factory=FakeBackend)
    candidate = switch.candidate_path()
    (candidate / "data").mkdir(parents=True)
    (candidate / "data" / "smartflow.db").write_bytes(b"candidate")
    old = FakeBackend(DesktopPaths(resources.resolve(), control.resolve()), frontend)
    return switch, old, candidate


def test_activate_commits_only_after_candidate_starts(setup_switch):
    switch, old, candidate = setup_switch
    new, origin = switch.activate(old, candidate)
    assert not old.running and new.running
    assert origin == "http://127.0.0.1:12345"
    assert switch.active_root() == candidate.resolve()
    assert (switch.control_root / "data" / "smartflow.db").read_bytes() == b"old"


def test_busy_backend_is_not_stopped(setup_switch):
    switch, old, candidate = setup_switch
    old.busy = True
    with pytest.raises(RestoreSwitchError, match="Stop active work"):
        switch.activate(old, candidate)
    assert old.running and switch.active_root() == switch.control_root


def test_failed_start_restarts_previous_backend(setup_switch):
    switch, old, candidate = setup_switch
    switch.backend_factory = lambda paths, frontend: FakeBackend(paths, frontend, fail=True)
    with pytest.raises(RestoreSwitchError, match="previous data is active again") as error:
        switch.activate(old, candidate)
    assert error.value.backend is old and old.running and old.starts == 1
    assert switch.active_root() == switch.control_root


def test_failed_pointer_commit_restarts_previous_backend(setup_switch, monkeypatch):
    switch, old, candidate = setup_switch
    def fail(_):
        raise OSError("synthetic disk failure")
    monkeypatch.setattr(switch, "_commit", fail)
    with pytest.raises(RestoreSwitchError, match="previous data is active again"):
        switch.activate(old, candidate)
    assert old.running and switch.active_root() == switch.control_root


def test_refuses_external_or_missing_roots(setup_switch, tmp_path):
    switch, old, candidate = setup_switch
    with pytest.raises(ValueError, match="outside restore storage"):
        switch.activate(old, tmp_path / "unrelated")
    (candidate / "data" / "smartflow.db").unlink()
    with pytest.raises(RestoreSwitchError, match="missing"):
        switch.activate(old, candidate)
    assert old.running


@pytest.mark.parametrize("crash_stage,expected_root", [
    ("after_stop", "old"), ("before_commit", "old"), ("after_commit", "candidate"),
])
def test_abrupt_supervisor_exit_keeps_a_complete_data_root(setup_switch, crash_stage, expected_root):
    """Restart selection is old or fully committed even if the supervisor dies."""
    switch, _, candidate = setup_switch
    script = r'''
import os, sys
from pathlib import Path
from desktop.paths import DesktopPaths
from desktop.restore_switch import RestoreSwitch

control, resources, frontend, candidate = map(Path, sys.argv[1:5])
stage = sys.argv[5]
class Backend:
    def __init__(self, paths, frontend):
        self.paths = paths
        self.frontend = frontend
    def request_shutdown(self):
        return True, None
    def stop(self):
        if stage == "after_stop" and self.paths.root == control:
            os._exit(91)
    def start(self):
        if stage == "before_commit" and self.paths.root == candidate:
            os._exit(91)
        return "http://127.0.0.1:12345"
switch = RestoreSwitch(control, resources, frontend, backend_factory=Backend)
commit = switch._commit
def crash_after_commit(root):
    commit(root)
    if stage == "after_commit":
        os._exit(91)
switch._commit = crash_after_commit
switch.activate(Backend(DesktopPaths(resources, control), frontend), candidate)
raise AssertionError("Crash was not triggered")
'''
    result = subprocess.run([sys.executable, "-c", script, str(switch.control_root), str(switch.resources),
                             str(switch.frontend), str(candidate.resolve()), crash_stage],
                            capture_output=True, text=True, timeout=30)
    assert result.returncode == 91, result.stdout + result.stderr
    expected = switch.control_root if expected_root == "old" else candidate.resolve()
    assert switch.active_root() == expected
    assert (expected / "data" / "smartflow.db").read_bytes() == (b"old" if expected_root == "old" else b"candidate")
    assert (switch.control_root / "data" / "smartflow.db").read_bytes() == b"old"
