import ctypes
import os
import subprocess
import sys
from ctypes import wintypes

import pytest

from desktop.windows_job import WindowsJob


pytestmark = pytest.mark.skipif(os.name != "nt", reason="Windows job objects require Windows")


def process_wait_handle(pid):
    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
    kernel.OpenProcess.restype = wintypes.HANDLE
    kernel.WaitForSingleObject.argtypes = [wintypes.HANDLE, wintypes.DWORD]
    kernel.WaitForSingleObject.restype = wintypes.DWORD
    kernel.CloseHandle.argtypes = [wintypes.HANDLE]
    handle = kernel.OpenProcess(0x00100000, False, pid)  # SYNCHRONIZE
    if not handle:
        raise ctypes.WinError(ctypes.get_last_error())
    return kernel, handle


def test_close_job_stops_child_and_grandchild():
    child_code = "import subprocess,sys; sys.stdin.readline(); p=subprocess.Popen([sys.executable,'-c','import time; time.sleep(120)'],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL); print(p.pid,flush=True); sys.stdin.read()"
    job = WindowsJob()
    unrelated = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(120)"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    process = subprocess.Popen([sys.executable, "-c", child_code], stdin=subprocess.PIPE, stdout=subprocess.PIPE, text=True)
    grandchild_handle = None
    try:
        job.assign(process)
        process.stdin.write("start\n")
        process.stdin.flush()
        pid = int(process.stdout.readline())
        kernel, grandchild_handle = process_wait_handle(pid)
        assert kernel.WaitForSingleObject(grandchild_handle, 0) == 0x102  # WAIT_TIMEOUT
        job.close()
        assert process.wait(timeout=10) is not None
        assert kernel.WaitForSingleObject(grandchild_handle, 10000) == 0  # WAIT_OBJECT_0
        assert unrelated.poll() is None
    finally:
        job.close()
        if process.poll() is None:
            process.kill()
            process.wait(timeout=10)
        if grandchild_handle:
            kernel.CloseHandle(grandchild_handle)
        process.stdin.close()
        process.stdout.close()
        unrelated.terminate()
        unrelated.wait(timeout=10)


def test_owner_crash_closes_job_and_stops_backend():
    code = "from desktop.windows_job import WindowsJob; import subprocess,sys; job=WindowsJob(); p=subprocess.Popen([sys.executable,'-c','import time; time.sleep(120)'],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL); job.assign(p); print(p.pid,flush=True); sys.stdin.read()"
    owner = subprocess.Popen([sys.executable, "-c", code], stdin=subprocess.PIPE, stdout=subprocess.PIPE, text=True)
    handle = None
    try:
        pid = int(owner.stdout.readline())
        kernel, handle = process_wait_handle(pid)
        assert kernel.WaitForSingleObject(handle, 0) == 0x102
        owner.kill()
        owner.wait(timeout=10)
        assert kernel.WaitForSingleObject(handle, 10000) == 0
    finally:
        if owner.poll() is None:
            owner.kill()
            owner.wait(timeout=10)
        if handle:
            kernel.CloseHandle(handle)
        owner.stdin.close()
        owner.stdout.close()
