"""Coarse direction summaries; individual lane signals remain authoritative."""


def canonical_signal_states(phase: str) -> tuple[str, str]:
    color = "green" if phase.endswith("_GREEN") else "yellow" if phase.endswith("_YELLOW") else "red"
    if phase.startswith(("NORTH_", "SOUTH_", "NS_")):
        return color, "red"
    if phase.startswith(("EAST_", "WEST_", "EW_")):
        return "red", color
    return "red", "red"
