"""One name per study condition, shared by reports, exports and comparisons (the TypeScript twin is src/lib/control-labels.ts)."""
from simulation.traffic_engine import NO_SIGNAL_LABEL

FIXED_TIME_LABEL = "Traditional signal (fixed-time)"


def condition_label(control_mode) -> str:
    mode = str(control_mode or "").strip().lower().replace("_", "-")
    if mode == "no-signal":
        return NO_SIGNAL_LABEL
    if mode == "fixed-time":
        return FIXED_TIME_LABEL
    algorithm = mode.split(":")[0]
    if algorithm in {"ql", "dql", "ppo"}:
        return f"SmartFlow RL ({algorithm.upper()})"
    return mode.replace("-", " ") or "unknown"
