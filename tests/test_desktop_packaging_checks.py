import sys
from types import SimpleNamespace

import pytest

from desktop.packaging_checks import require_cpu_ml


@pytest.mark.parametrize("torch_version,cuda,sb3_version,valid", [
    ("2.12.0+cpu", None, "2.8.0", True),
    ("2.12.0+cu130", "13.0", "2.8.0", False),
    ("2.11.0+cpu", None, "2.8.0", False),
    ("2.12.0+cpu", None, "2.9.0", False),
])
def test_ml_build_checks_versions_and_refuses_cuda(monkeypatch, torch_version, cuda, sb3_version, valid):
    monkeypatch.setitem(sys.modules, "torch", SimpleNamespace(__version__=torch_version, version=SimpleNamespace(cuda=cuda)))
    monkeypatch.setitem(sys.modules, "stable_baselines3", SimpleNamespace(__version__=sb3_version))
    if valid:
        require_cpu_ml()
    else:
        with pytest.raises(RuntimeError):
            require_cpu_ml()
