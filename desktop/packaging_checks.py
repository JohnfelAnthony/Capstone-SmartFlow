"""Checks for optional CPU-only prototype build dependencies."""


def require_cpu_ml():
    try:
        import torch
        import stable_baselines3
    except ImportError as exc:
        raise RuntimeError("CPU PyTorch and Stable-Baselines3 are required for the ML prototype") from exc
    if torch.__version__.split("+")[0] != "2.12.0" or torch.version.cuda is not None:
        raise RuntimeError("The ML prototype requires the CPU-only PyTorch 2.12.0 build")
    if stable_baselines3.__version__ != "2.8.0":
        raise RuntimeError("The ML prototype requires Stable-Baselines3 2.8.0")
