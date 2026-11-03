import subprocess
import sys
from pathlib import Path

import pytest

from desktop.instance_lock import InstanceInUse, InstanceLock


def test_different_roots_and_release(tmp_path):
    first, other = tmp_path / "data", tmp_path / "other"
    with InstanceLock(first), InstanceLock(other):
        with pytest.raises(InstanceInUse):
            with InstanceLock(first):
                pass
    with InstanceLock(first):
        pass


def test_crashed_process_releases_lock(tmp_path):
    root = tmp_path / "data"
    code = "from desktop.instance_lock import InstanceLock; import sys; lock=InstanceLock(sys.argv[1]); lock.__enter__(); print('ready', flush=True); sys.stdin.read()"
    process = subprocess.Popen([sys.executable, "-c", code, str(root)], stdin=subprocess.PIPE, stdout=subprocess.PIPE, text=True)
    try:
        assert process.stdout.readline().strip() == "ready"
        with pytest.raises(InstanceInUse):
            with InstanceLock(root):
                pass
        process.kill()
        process.wait(timeout=10)
        with InstanceLock(root):
            pass
    finally:
        if process.poll() is None:
            process.kill()
            process.wait(timeout=10)
        process.stdin.close()
        process.stdout.close()
