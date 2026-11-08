from types import SimpleNamespace

import pytest

from desktop import launcher
from desktop.paths import DesktopPaths


def test_password_confirmation_allows_retry_or_cancel():
    answers = iter(["FirstPass1", "Mismatch1", "SecondPass2", "SecondPass2"])
    warnings = []
    assert launcher.prompt_confirmed_password(lambda _prompt: next(answers), warnings.append) == "SecondPass2"
    assert warnings == ["Passwords do not match. Please try again."]
    answers = iter(["FirstPass1", None])
    assert launcher.prompt_confirmed_password(lambda _prompt: next(answers), warnings.append) is None


def test_weak_password_can_retry_before_backend_starts(tmp_path, monkeypatch):
    resources, root = tmp_path / "resources", tmp_path / "user data"
    (resources / "dist").mkdir(parents=True)
    (resources / "dist" / "index.html").write_text("test")
    passwords, events = iter(["weak", "StrongPass123"]), []

    def setup(_paths, password):
        events.append("setup:" + password)
        if password == "weak":
            raise launcher.WeakPasswordError("Choose a stronger password")

    class Backend:
        def __init__(self, _paths, _frontend):
            pass
        def start(self):
            events.append("backend")
            return "http://127.0.0.1:12345"
        def stop(self):
            events.append("stop")

    class Event:
        def __iadd__(self, _handler):
            return self

    fake = SimpleNamespace(settings={}, create_window=lambda *_args, **_kwargs: SimpleNamespace(events=SimpleNamespace(initialized=Event(), closing=Event())),
                           start=lambda **_kwargs: None)
    dialogs = SimpleNamespace(warning=lambda: True, first_password=lambda: next(passwords),
                              weak_password=lambda _reason: events.append("weak"))
    monkeypatch.setattr(launcher, "bootstrap", setup)
    monkeypatch.setattr(launcher, "DesktopBackend", Backend)
    assert launcher.run(DesktopPaths.discover(data_root=root, resources=resources), window_module=fake, dialogs=dialogs)
    assert events == ["setup:weak", "weak", "setup:StrongPass123", "backend", "stop"]


def test_window_starts_only_after_setup_and_stops_owned_backend(tmp_path, monkeypatch):
    resources, root = tmp_path / "resources", tmp_path / "user data"
    (resources / "dist").mkdir(parents=True)
    (resources / "dist" / "index.html").write_text("test")
    paths = DesktopPaths.discover(data_root=root, resources=resources)
    events = []

    def setup(actual_paths, password):
        assert actual_paths == paths and password == "StrongPass123"
        events.append("setup")

    class Backend:
        def __init__(self, actual_paths, frontend):
            assert actual_paths == paths and frontend == resources / "dist"
        def start(self):
            events.append("backend")
            return "http://127.0.0.1:12345"
        def stop(self):
            events.append("stop")
        def request_shutdown(self):
            events.append("shutdown")
            if events.count("shutdown") == 1:
                return False, "recording is active"
            return True, None

    class Event:
        def __iadd__(self, handler):
            self.handler = handler
            return self

    initialized = Event()
    closing = Event()

    def create_window(title, origin, **_kwargs):
        assert title == "SmartFlow"
        assert origin == "http://127.0.0.1:12345"
        events.append("window")
        return SimpleNamespace(events=SimpleNamespace(initialized=initialized, closing=closing))

    def start(**kwargs):
        assert kwargs["gui"] == "edgechromium"
        assert initialized.handler("edgechromium")
        events.append("loop")
        assert closing.handler() is False
        assert closing.handler() is True

    fake = SimpleNamespace(settings={}, create_window=create_window, start=start)
    dialogs = SimpleNamespace(warning=lambda: True, first_password=lambda: "StrongPass123", confirm_close=lambda: True, busy=lambda _reason: events.append("busy"))
    monkeypatch.setattr(launcher, "bootstrap", setup)
    monkeypatch.setattr(launcher, "DesktopBackend", Backend)
    assert launcher.run(paths, window_module=fake, dialogs=dialogs)
    assert events == ["setup", "backend", "window", "loop", "shutdown", "busy", "shutdown", "stop"]
    assert fake.settings["ALLOW_FILE_URLS"] is False


def test_cancellation_does_not_start_or_create_data(tmp_path):
    resources = tmp_path / "resources"
    (resources / "dist").mkdir(parents=True)
    (resources / "dist" / "index.html").write_text("test")
    root = tmp_path / "data"
    paths = DesktopPaths.discover(data_root=root, resources=resources)
    assert not launcher.run(paths, window_module=SimpleNamespace(), dialogs=SimpleNamespace(warning=lambda: False))
    assert not root.exists()


def test_missing_frontend_does_not_create_data(tmp_path):
    paths = DesktopPaths.discover(data_root=tmp_path / "data", resources=tmp_path / "resources")
    with pytest.raises(RuntimeError, match="SmartFlow desktop interface is missing"):
        launcher.run(paths, window_module=SimpleNamespace(), dialogs=SimpleNamespace())
    assert not paths.root.exists()


def test_launcher_uses_persisted_restored_root_and_holds_supervisor_lock(tmp_path, monkeypatch):
    from desktop.instance_lock import InstanceInUse, InstanceLock
    from desktop.restore_switch import RestoreSwitch

    resources, root = tmp_path / "resources", tmp_path / "data"
    frontend = resources / "dist"
    frontend.mkdir(parents=True)
    (frontend / "index.html").write_text("test", encoding="utf-8")
    switch = RestoreSwitch(root, resources, frontend)
    candidate = switch.candidate_path()
    (candidate / "data").mkdir(parents=True)
    (candidate / "data" / "smartflow.db").write_bytes(b"fixture")
    switch._commit(candidate)
    seen = []

    class Backend:
        def __init__(self, paths, _frontend):
            seen.append(paths.root)
        def start(self):
            return "http://127.0.0.1:12345"
        def stop(self):
            pass

    class Event:
        def __iadd__(self, _handler):
            return self

    def start(**_kwargs):
        with pytest.raises(InstanceInUse):
            with InstanceLock(root / "config" / "supervisor"):
                pass

    fake = SimpleNamespace(settings={}, create_window=lambda *_args, **_kwargs: SimpleNamespace(events=SimpleNamespace(initialized=Event(), closing=Event())), start=start)
    monkeypatch.setattr(launcher, "DesktopBackend", Backend)
    assert launcher.run(DesktopPaths.discover(data_root=root, resources=resources), window_module=fake, dialogs=SimpleNamespace(warning=lambda: True))
    assert seen == [candidate.resolve()]
    with InstanceLock(root / "config" / "supervisor"):
        pass


def test_launcher_monitors_restore_and_reloads_window(tmp_path, monkeypatch):
    from threading import Event as Signal
    resources, root = tmp_path / "resources", tmp_path / "data"
    frontend = resources / "dist"
    frontend.mkdir(parents=True)
    (frontend / "index.html").write_text("test", encoding="utf-8")
    (root / "data").mkdir(parents=True)
    (root / "data" / "smartflow.db").write_bytes(b"fixture")
    loaded = Signal()
    calls = []

    class Backend:
        def __init__(self, paths, _frontend):
            self.paths = paths
            self.polled = False
        def start(self):
            return "http://127.0.0.1:12345"
        def stop(self):
            calls.append("stop")
        def poll_restore(self):
            if not self.polled:
                self.polled = True
                return str(root / "candidate")
            return None
        def release_restore(self):
            calls.append("release")

    class Switch:
        def __init__(self, *_args):
            pass
        def active_root(self):
            return root.resolve()
        def activate(self, current, candidate):
            assert candidate == root / "candidate"
            calls.append("activate")
            return current, "http://127.0.0.1:54321"

    class Event:
        def __iadd__(self, _handler):
            return self

    def load_url(url):
        assert url == "http://127.0.0.1:54321"
        calls.append("reload")
        loaded.set()

    window = SimpleNamespace(events=SimpleNamespace(initialized=Event(), closing=Event()), load_url=load_url)
    fake = SimpleNamespace(settings={}, create_window=lambda *_args, **_kwargs: window,
                           start=lambda **_kwargs: loaded.wait(10))
    monkeypatch.setattr(launcher, "DesktopBackend", Backend)
    monkeypatch.setattr(launcher, "RestoreSwitch", Switch)
    assert launcher.run(DesktopPaths.discover(data_root=root, resources=resources), window_module=fake,
                        dialogs=SimpleNamespace(warning=lambda: True, busy=lambda message: pytest.fail(message)))
    assert calls == ["activate", "reload", "stop"]


def test_launcher_reports_unexpected_backend_exit_once(tmp_path, monkeypatch):
    from threading import Event as Signal

    resources, root = tmp_path / "resources", tmp_path / "data"
    frontend = resources / "dist"
    frontend.mkdir(parents=True)
    (frontend / "index.html").write_text("test", encoding="utf-8")
    (root / "data").mkdir(parents=True)
    (root / "data" / "smartflow.db").write_bytes(b"fixture")
    notified, messages = Signal(), []

    class Backend:
        def __init__(self, paths, _frontend):
            self.paths = paths
            self.process = SimpleNamespace(poll=lambda: 1)
            self.shutdown_accepted = False
        def start(self):
            return "http://127.0.0.1:12345"
        def poll_restore(self):
            pytest.fail("A stopped backend should not be polled for restore")
        def stop(self):
            pass

    class Event:
        def __iadd__(self, _handler):
            return self

    def show_message(message):
        messages.append(message)
        notified.set()

    window = SimpleNamespace(events=SimpleNamespace(initialized=Event(), closing=Event()))
    fake = SimpleNamespace(settings={}, create_window=lambda *_args, **_kwargs: window,
                           start=lambda **_kwargs: notified.wait(10))
    monkeypatch.setattr(launcher, "DesktopBackend", Backend)
    assert launcher.run(DesktopPaths.discover(data_root=root, resources=resources), window_module=fake,
                        dialogs=SimpleNamespace(warning=lambda: True, busy=show_message))
    assert len(messages) == 1 and "stopped unexpectedly" in messages[0] and "backend.log" in messages[0]


def test_launcher_does_not_report_accepted_shutdown_as_crash(tmp_path, monkeypatch):
    from threading import Event as Signal

    resources, root = tmp_path / "resources", tmp_path / "data"
    frontend = resources / "dist"
    frontend.mkdir(parents=True)
    (frontend / "index.html").write_text("test", encoding="utf-8")
    (root / "data").mkdir(parents=True)
    (root / "data" / "smartflow.db").write_bytes(b"fixture")
    checked, messages = Signal(), []

    class Backend:
        def __init__(self, paths, _frontend):
            self.paths = paths
            self.process = SimpleNamespace(poll=lambda: (checked.set(), 0)[1])
            self.shutdown_accepted = True
        def start(self):
            return "http://127.0.0.1:12345"
        def poll_restore(self):
            pytest.fail("A stopped backend should not be polled for restore")
        def stop(self):
            pass

    class Event:
        def __iadd__(self, _handler):
            return self

    window = SimpleNamespace(events=SimpleNamespace(initialized=Event(), closing=Event()))
    fake = SimpleNamespace(settings={}, create_window=lambda *_args, **_kwargs: window,
                           start=lambda **_kwargs: checked.wait(10))
    monkeypatch.setattr(launcher, "DesktopBackend", Backend)
    assert launcher.run(DesktopPaths.discover(data_root=root, resources=resources), window_module=fake,
                        dialogs=SimpleNamespace(warning=lambda: True, busy=messages.append))
    assert messages == []
