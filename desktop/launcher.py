"""Source-only desktop window prototype; not a distributable launcher."""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import threading
from pathlib import Path

from desktop.lifecycle import DesktopBackend
from desktop.instance_lock import InstanceLock
from desktop.paths import DesktopPaths
from desktop.restore_switch import RestoreSwitch
from desktop.worker_commands import service_prefix
from desktop.bootstrap import WeakPasswordError


def bootstrap(paths: DesktopPaths, password: str) -> None:
    environment = {k: v for k, v in os.environ.items() if not k.startswith("SMARTFLOW_")}
    request = {"data_root": str(paths.root), "resources": str(paths.resources), "password": password}
    result = subprocess.run(service_prefix("bootstrap"), cwd=str(paths.resources if getattr(sys, "frozen", False) else Path(__file__).resolve().parents[1]),
                            env=environment, input=json.dumps(request), text=True, encoding="utf-8", capture_output=True,
                            timeout=90, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    try:
        response = json.loads(result.stdout)
    except ValueError:
        raise RuntimeError("Desktop setup failed before returning a result") from None
    if result.returncode or not response.get("ok"):
        if response.get("code") == "weak_password":
            raise WeakPasswordError(response.get("error", "Choose a stronger password"))
        raise RuntimeError(response.get("error", "Desktop setup failed"))


def prompt_confirmed_password(ask, warn):
    """Request matching credentials; cancelling either prompt cancels setup."""
    while True:
        password = ask("Choose a password for the admin account:")
        if password is None:
            return None
        confirmation = ask("Confirm the admin password:")
        if confirmation is None:
            return None
        if password == confirmation:
            return password
        warn("Passwords do not match. Please try again.")


def run(paths: DesktopPaths, *, window_module=None, dialogs=None) -> bool:
    """Start a source prototype. The caller owns the GUI thread."""
    if window_module is None:
        try:
            import webview as window_module
        except ImportError:
            raise RuntimeError("Install pywebview in the desktop prototype environment first") from None
    if dialogs is None:
        import tkinter as tk
        from tkinter import messagebox, simpledialog
        hidden = tk.Tk()
        hidden.withdraw()

        class NativeDialogs:
            @staticmethod
            def first_password():
                return prompt_confirmed_password(
                    lambda prompt: simpledialog.askstring("SmartFlow setup", prompt, show="*", parent=hidden),
                    lambda message: messagebox.showerror("SmartFlow setup", message, parent=hidden),
                )

            @staticmethod
            def weak_password(reason):
                messagebox.showerror("SmartFlow setup", reason, parent=hidden)

            @staticmethod
            def warning():
                return messagebox.askokcancel("SmartFlow desktop prototype", "This is an unfinished prototype for synthetic data. Training and restore have not completed packaged acceptance. Closing it stops its backend. Continue?", parent=hidden)

            @staticmethod
            def confirm_close():
                import ctypes
                return ctypes.windll.user32.MessageBoxW(None, "Close SmartFlow? Active work must be stopped first.", "SmartFlow", 0x24) == 6

            @staticmethod
            def busy(reason):
                import ctypes
                ctypes.windll.user32.MessageBoxW(None, reason, "SmartFlow is still working", 0x30)

        dialogs = NativeDialogs()
    else:
        hidden = None
    backend = None
    supervisor_lock = None
    monitor_stop = threading.Event()
    monitor = None
    backend_lock = threading.Lock()
    try:
        frontend = paths.resources / "dist"
        if not (frontend / "index.html").is_file():
            raise RuntimeError("Build the desktop frontend before starting the prototype")
        if not dialogs.warning():
            return False
        control_root = paths.root
        supervisor_lock = InstanceLock(control_root / "config" / "supervisor")
        supervisor_lock.__enter__()
        if os.name == "nt":  # held until exit; the installer (AppMutex) refuses to replace running binaries
            import ctypes
            ctypes.windll.kernel32.CreateMutexW(None, False, "SmartFlowDesktopRunning")
        switch = RestoreSwitch(control_root, paths.resources, frontend)
        selected = switch.active_root()
        paths = DesktopPaths(paths.resources, selected)
        if not Path(paths.environment()["SMARTFLOW_DB_PATH"]).exists():
            while True:
                password = dialogs.first_password()
                if password is None:
                    return False
                try:
                    bootstrap(paths, password)
                    break
                except WeakPasswordError as exc:
                    dialogs.weak_password(str(exc))
                finally:
                    del password
        backend = DesktopBackend(paths, frontend)
        backend.control_root = control_root
        origin = backend.start()
        window_module.settings["ALLOW_DOWNLOADS"] = True
        window_module.settings["ALLOW_FILE_URLS"] = False
        window_module.settings["OPEN_EXTERNAL_LINKS_IN_BROWSER"] = True
        window = window_module.create_window("SmartFlow — desktop prototype", origin, width=1280, height=800, min_size=(1000, 650), confirm_close=False)
        selected_renderer = []

        def require_edge(renderer):
            selected_renderer.append(renderer)
            return renderer == "edgechromium"

        window.events.initialized += require_edge

        def close_if_idle():
            if not dialogs.confirm_close():
                return False
            with backend_lock:
                accepted, reason = backend.request_shutdown()
            if not accepted:
                dialogs.busy(reason or "Stop active work and try again.")
            return accepted

        window.events.closing += close_if_idle
        def monitor_restore():
            nonlocal backend
            while not monitor_stop.wait(1):
                with backend_lock:
                    process = getattr(backend, "process", None)
                    if process is not None and process.poll() is not None:
                        if not getattr(backend, "shutdown_accepted", False):
                            dialogs.busy("The SmartFlow backend stopped unexpectedly. Close and reopen the application. "
                                         f"If the problem continues, check the log in {backend.paths.root / 'logs' / 'backend.log'}.")
                        return
                    candidate = backend.poll_restore()
                    if not candidate:
                        continue
                    try:
                        backend, new_origin = switch.activate(backend, Path(candidate))
                    except Exception as exc:
                        backend.release_restore()
                        dialogs.busy(str(exc))
                        if getattr(exc, "origin", None):
                            window.load_url(exc.origin)
                        continue
                    try:
                        window.load_url(new_origin)
                    except Exception:
                        dialogs.busy("Restore succeeded, but the window could not reload. Close and reopen SmartFlow to use the restored data.")

        if hasattr(backend, "poll_restore"):
            monitor = threading.Thread(target=monitor_restore, daemon=True)
            monitor.start()
        window_module.start(gui="edgechromium", private_mode=False, storage_path=str(paths.root / "webview"))
        if selected_renderer and selected_renderer[0] != "edgechromium":
            raise RuntimeError("Microsoft Edge WebView2 is required. Install the WebView2 runtime and retry.")
        return True
    finally:
        monitor_stop.set()
        if monitor is not None:
            monitor.join(timeout=15)
        try:
            if backend is not None:
                backend.stop()
        finally:
            if supervisor_lock is not None:
                supervisor_lock.__exit__(None, None, None)
            if hidden is not None:
                hidden.destroy()


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the unfinished SmartFlow desktop source prototype")
    parser.add_argument("--data-dir", type=Path)
    args = parser.parse_args()
    try:
        run(DesktopPaths.discover(data_root=args.data_dir))
    except Exception as exc:
        try:
            import tkinter as tk
            from tkinter import messagebox
            root = tk.Tk()
            root.withdraw()
            messagebox.showerror("SmartFlow desktop prototype", str(exc), parent=root)
            root.destroy()
        except Exception:
            print(f"Desktop startup failed: {exc}", file=sys.stderr)
        raise SystemExit(1) from None


if __name__ == "__main__":
    main()
