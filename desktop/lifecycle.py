"""Own and observe a source-mode desktop backend without touching other processes."""
from __future__ import annotations

import json
import os
import queue
import secrets
import subprocess
import sys
import threading
from pathlib import Path
from urllib.parse import urlsplit

from desktop.paths import DesktopPaths
from desktop.worker_commands import service_prefix


class DesktopBackend:
    def __init__(self, paths: DesktopPaths, frontend: Path):
        self.paths = paths
        self.control_root = paths.root
        self.frontend = Path(frontend)
        self.process: subprocess.Popen | None = None
        self.log = None
        self.job = None
        self.control_lock = threading.Lock()
        self.control_failed = False
        self.shutdown_accepted = False

    def start(self, timeout: float = 40) -> str:
        if self.process is not None:
            raise RuntimeError("This desktop backend is already started")
        logs = self.paths.root / "logs"
        logs.mkdir(parents=True, exist_ok=True)
        self.log = (logs / "backend.log").open("a", encoding="utf-8")
        environment = {key: value for key, value in os.environ.items() if not key.startswith("SMARTFLOW_")}
        nonce = secrets.token_urlsafe(32)
        try:
            self.process = subprocess.Popen(
                service_prefix("serve"), cwd=str(self.paths.resources if getattr(sys, "frozen", False) else Path(__file__).resolve().parents[1]),
                env=environment, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=self.log,
                text=True, encoding="utf-8", creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
            )
            if os.name == "nt":
                from desktop.windows_job import WindowsJob
                self.job = WindowsJob()
                self.job.assign(self.process)
            request = {"data_root": str(self.paths.root), "resources": str(self.paths.resources),
                       "frontend": str(self.frontend), "nonce": nonce, "control_root": str(self.control_root)}
            self.process.stdin.write(json.dumps(request) + "\n")
            self.process.stdin.flush()
            self.control_failed = False
            self.shutdown_accepted = False
            responses: queue.Queue[str] = queue.Queue(maxsize=1)
            process = self.process
            threading.Thread(target=lambda: responses.put(process.stdout.readline()), daemon=True).start()
            try:
                line = responses.get(timeout=timeout)
            except queue.Empty:
                raise TimeoutError("Desktop backend did not become ready; see backend.log") from None
            try:
                response = json.loads(line)
            except (ValueError, TypeError):
                raise RuntimeError("Desktop backend stopped without a valid readiness response; see backend.log") from None
            if not response.get("ready"):
                raise RuntimeError(f"Desktop backend could not start: {response.get('error', 'unknown error')}")
            if response.get("nonce") != nonce:
                raise RuntimeError("Desktop backend startup identity did not match")
            origin = response.get("origin", "")
            parsed = urlsplit(origin)
            if parsed.scheme != "http" or parsed.hostname != "127.0.0.1" or not parsed.port or parsed.path or parsed.query or parsed.fragment:
                raise RuntimeError("Desktop backend returned an invalid local address")
            return origin
        except BaseException:
            self.stop()
            raise

    def request_shutdown(self, timeout: float = 10) -> tuple[bool, str | None]:
        with self.control_lock:
            process = self.process
            if process is None or process.poll() is not None:
                return True, None
            if self.control_failed:
                return False, "The desktop control channel is unavailable. Keep the window open and inspect the log."
            try:
                process.stdin.write(json.dumps({"command": "shutdown_if_idle"}) + "\n")
                process.stdin.flush()
                output: queue.Queue[str] = queue.Queue(maxsize=1)
                threading.Thread(target=lambda: output.put(process.stdout.readline()), daemon=True).start()
                response = json.loads(output.get(timeout=timeout))
                if not isinstance(response, dict) or not isinstance(response.get("accepted"), bool):
                    raise ValueError("Invalid desktop control response")
                self.shutdown_accepted = response["accepted"]
                return response["accepted"], response.get("reason")
            except (OSError, ValueError, queue.Empty):
                self.control_failed = True
                return False, "The desktop backend did not respond. Keep the window open and inspect the log."

    def poll_restore(self, timeout: float = 10) -> str | None:
        with self.control_lock:
            process = self.process
            if process is None or process.poll() is not None or self.control_failed:
                return None
            try:
                process.stdin.write(json.dumps({"command": "poll_restore"}) + "\n")
                process.stdin.flush()
                output: queue.Queue[str] = queue.Queue(maxsize=1)
                threading.Thread(target=lambda: output.put(process.stdout.readline()), daemon=True).start()
                response = json.loads(output.get(timeout=timeout))
                candidate = response["candidate"]
                if candidate is not None and not isinstance(candidate, str):
                    raise ValueError("Invalid desktop restore response")
                return candidate
            except (OSError, ValueError, KeyError, TypeError, queue.Empty):
                self.control_failed = True
                return None

    def release_restore(self, timeout: float = 10) -> None:
        with self.control_lock:
            process = self.process
            if process is None or process.poll() is not None or self.control_failed:
                return
            try:
                process.stdin.write(json.dumps({"command": "release_restore"}) + "\n")
                process.stdin.flush()
                output: queue.Queue[str] = queue.Queue(maxsize=1)
                threading.Thread(target=lambda: output.put(process.stdout.readline()), daemon=True).start()
                if json.loads(output.get(timeout=timeout)) != {"released": True}:
                    raise ValueError("Invalid desktop restore response")
            except (OSError, ValueError, queue.Empty):
                self.control_failed = True

    def stop(self, timeout: float = 10) -> None:
        process, self.process = self.process, None
        try:
            if process is not None:
                if process.stdin and not process.stdin.closed:
                    process.stdin.close()
                if process.poll() is None:
                    try:
                        if not self.shutdown_accepted:
                            process.terminate()
                        process.wait(timeout=timeout)
                    except subprocess.TimeoutExpired:
                        process.kill()
                        process.wait(timeout=timeout)
                if process.stdout:
                    process.stdout.close()
        finally:
            if self.job:
                self.job.close()
                self.job = None
            if self.log:
                self.log.close()
                self.log = None
