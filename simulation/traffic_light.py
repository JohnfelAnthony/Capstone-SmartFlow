"""Traffic light signal phase state machine for a four-way intersection.

Phases (fixed cycle)
--------------------
NS_GREEN   — North-South green, East-West red
NS_YELLOW  — North-South yellow (transition)
ALL_RED    — All-red clearance
EW_GREEN   — East-West green, North-South red
EW_YELLOW  — East-West yellow (transition)
"""

from .constants import NS_GREEN, NS_YELLOW, ALL_RED, EW_GREEN, EW_YELLOW


class SignalPhase:
    """A single named phase with a fixed duration."""

    def __init__(self, name: str, duration: float, ns: str, ew: str):
        self.name = name
        self.duration = duration
        self.ns = ns
        self.ew = ew

    def __repr__(self):
        return f"<{self.name}: NS={self.ns} EW={self.ew} ({self.duration}s)>"


PHASE_CYCLE = [
    SignalPhase("NS_GREEN",  NS_GREEN,  "green",  "red"),
    SignalPhase("NS_YELLOW", NS_YELLOW, "yellow", "red"),
    SignalPhase("ALL_RED",   ALL_RED,   "red",    "red"),
    SignalPhase("EW_GREEN",  EW_GREEN,  "red",    "green"),
    SignalPhase("EW_YELLOW", EW_YELLOW, "red",    "yellow"),
]

PHASE_NAMES = [p.name for p in PHASE_CYCLE]


class TrafficLight:
    """Signal state machine that steps through a fixed cycle."""

    def __init__(self, initial_idx: int = 0, cycle: list = None):
        self.cycle = cycle or PHASE_CYCLE
        self.idx = initial_idx % len(self.cycle)
        self._phase = self.cycle[self.idx]
        self.remaining = self._phase.duration
        self.cycle_count = 0

    @property
    def phase(self) -> str:
        return self._phase.name

    @property
    def ns_state(self) -> str:
        return self._phase.ns

    @property
    def ew_state(self) -> str:
        return self._phase.ew

    def signal_for_approach(self, approach: str) -> str:
        if approach in ("north", "south"):
            return self.ns_state
        return self.ew_state

    def update(self, dt: float):
        self.remaining -= dt
        if self.remaining <= 0.0:
            self._advance()
            return True
        return False

    def _advance(self):
        self.idx = (self.idx + 1) % len(self.cycle)
        self._phase = self.cycle[self.idx]
        self.remaining = self._phase.duration
        if self.idx == 0:
            self.cycle_count += 1

    def reset(self, initial_idx: int = 0):
        self.idx = initial_idx % len(self.cycle)
        self._phase = self.cycle[self.idx]
        self.remaining = self._phase.duration
        self.cycle_count = 0

    def to_dict(self) -> dict:
        return {
            "phase": self.phase,
            "ns_state": self.ns_state,
            "ew_state": self.ew_state,
            "remaining": round(self.remaining, 1),
            "cycle_count": self.cycle_count,
        }
