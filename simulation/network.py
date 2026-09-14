"""Four-way signalized intersection road network.

Coordinate conventions
----------------------
- Intersection centre = (0, 0).
- X points east, Y points north (standard Cartesian).
- All distances in metres.

Approach directions
-------------------
- **north** — vehicles enter at y = +100 m, travel south (−y), exit at y = −100 m.
- **south** — vehicles enter at y = −100 m, travel north (+y), exit at y = +100 m.
- **east**  — vehicles enter at x = +100 m, travel west (−x), exit at x = −100 m.
- **west**  — vehicles enter at x = −100 m, travel east (+x), exit at x = +100 m.

Lanes
-----
Each approach has 2 entry lanes (index 0 = left, index 1 = right relative
to the travel direction).  Lane centres are offset ±1.75 m from the road
centreline.

- Lane 0: left-turn + straight.
- Lane 1: straight + right-turn.

Routes
------
Each `(approach, lane, turn)` combination has a pre-defined list of (x, y)
waypoints the vehicle follows sequentially.
"""

from dataclasses import dataclass
from typing import List, Tuple

WP = Tuple[float, float]
Route = List[WP]


# ────────────────────────────────────────────────────────────────────────────
# Per-approach lane metadata
# ────────────────────────────────────────────────────────────────────────────

@dataclass
class LaneDef:
    """A single entry lane on one approach."""
    idx: int
    x_offset: float
    allowed_turns: Tuple[str, ...]


@dataclass
class ApproachDef:
    """Geometry and lanes for one intersection leg."""
    name: str
    axis: str                    # "y" (north/south) or "x" (east/west)
    entry_sign: int              # +1 = spawn at +, travel toward 0
    lanes: Tuple[LaneDef, ...]


# ────────────────────────────────────────────────────────────────────────────
# Route tables — built once
# ────────────────────────────────────────────────────────────────────────────

_SL = 14.0
_IE = 7.0
_SD = 100.0
_L0 = -1.75
_L1 = +1.75


def _build_routes() -> dict:
    """Return dict keyed by (approach, lane, turn) → Route."""
    R = {}

    # ── North approach (y = +100 → y = −100) ──────────────────────────
    R["north", 0, "straight"] = [
        (_L0, _SD), (_L0, _SL), (_L0, -_SL), (_L0, -_SD - 10),
    ]
    R["north", 1, "straight"] = [
        (_L1, _SD), (_L1, _SL), (_L1, -_SL), (_L1, -_SD - 10),
    ]
    R["north", 0, "left"] = [
        (_L0, _SD), (_L0, _SL),
        (_L0, _IE / 2), (0.0, 0.0), (_IE / 2, -_L0),
        (_SL, -_L0), (_SD + 10, -_L0),
    ]
    R["north", 1, "right"] = [
        (_L1, _SD), (_L1, _SL),
        (_L1, _IE / 2), (-_IE / 2, _L1),
        (-_SL, _L1), (-_SD - 10, _L1),
    ]

    # ── South approach (y = −100 → y = +100) ──────────────────────────
    R["south", 0, "straight"] = [
        (_L0, -_SD), (_L0, -_SL), (_L0, _SL), (_L0, _SD + 10),
    ]
    R["south", 1, "straight"] = [
        (_L1, -_SD), (_L1, -_SL), (_L1, _SL), (_L1, _SD + 10),
    ]
    R["south", 0, "left"] = [
        (_L0, -_SD), (_L0, -_SL),
        (_L0, -_IE / 2), (0.0, 0.0), (-_IE / 2, _L0),
        (-_SL, _L0), (-_SD - 10, _L0),
    ]
    R["south", 1, "right"] = [
        (_L1, -_SD), (_L1, -_SL),
        (_L1, -_IE / 2), (_IE / 2, -_L1),
        (_SL, -_L1), (_SD + 10, -_L1),
    ]

    # ── East approach (x = +100 → x = −100) ───────────────────────────
    R["east", 0, "straight"] = [
        (_SD, _L0), (_SL, _L0), (-_SL, _L0), (-_SD - 10, _L0),
    ]
    R["east", 1, "straight"] = [
        (_SD, _L1), (_SL, _L1), (-_SL, _L1), (-_SD - 10, _L1),
    ]
    R["east", 0, "left"] = [
        (_SD, _L0), (_SL, _L0),
        (_IE / 2, _L0), (0.0, 0.0), (_L0, -_IE / 2),
        (_L0, -_SL), (_L0, -_SD - 10),
    ]
    R["east", 1, "right"] = [
        (_SD, _L1), (_SL, _L1),
        (_IE / 2, _L1), (-_L1, _IE / 2),
        (-_L1, _SL), (-_L1, _SD + 10),
    ]

    # ── West approach (x = −100 → x = +100) ───────────────────────────
    R["west", 0, "straight"] = [
        (-_SD, _L0), (-_SL, _L0), (_SL, _L0), (_SD + 10, _L0),
    ]
    R["west", 1, "straight"] = [
        (-_SD, _L1), (-_SL, _L1), (_SL, _L1), (_SD + 10, _L1),
    ]
    R["west", 0, "left"] = [
        (-_SD, _L0), (-_SL, _L0),
        (-_IE / 2, _L0), (0.0, 0.0), (-_L0, _IE / 2),
        (-_L0, _SL), (-_L0, _SD + 10),
    ]
    R["west", 1, "right"] = [
        (-_SD, _L1), (-_SL, _L1),
        (-_IE / 2, _L1), (_L1, -_IE / 2),
        (_L1, -_SL), (_L1, -_SD - 10),
    ]

    return R


# ────────────────────────────────────────────────────────────────────────────
# Public API
# ────────────────────────────────────────────────────────────────────────────

class Network:
    """Four-way intersection road network with pre-computed turn routes."""

    APPROACHES = ("north", "south", "east", "west")
    TURNS = ("straight", "left", "right")

    def __init__(self):
        self._routes = _build_routes()

        self.approach_defs = (
            ApproachDef("north", "y", +1, (
                LaneDef(0, -1.75, ("left", "straight")),
                LaneDef(1, +1.75, ("straight", "right")),
            )),
            ApproachDef("south", "y", -1, (
                LaneDef(0, -1.75, ("left", "straight")),
                LaneDef(1, +1.75, ("straight", "right")),
            )),
            ApproachDef("east", "x", -1, (
                LaneDef(0, -1.75, ("left", "straight")),
                LaneDef(1, +1.75, ("straight", "right")),
            )),
            ApproachDef("west", "x", +1, (
                LaneDef(0, -1.75, ("left", "straight")),
                LaneDef(1, +1.75, ("straight", "right")),
            )),
        )
        self._by_name = {a.name: a for a in self.approach_defs}

        # Crosswalk definitions: four crosswalks, one per side
        self.crosswalks = {
            "north": {"x1": -4.0, "x2": 4.0, "y": _SL},
            "south": {"x1": -4.0, "x2": 4.0, "y": -_SL},
            "east":  {"y1": -4.0, "y2": 4.0, "x": _SL},
            "west":  {"y1": -4.0, "y2": 4.0, "x": -_SL},
        }

    def get_approach(self, name: str) -> ApproachDef:
        return self._by_name[name]

    def has_route(self, approach: str, lane: int, turn: str) -> bool:
        return (approach, lane, turn) in self._routes

    def get_route(self, approach: str, lane: int, turn: str) -> Route:
        key = (approach, lane, turn)
        if key not in self._routes:
            raise ValueError(
                f"No route for approach={approach!r} lane={lane} turn={turn!r}"
            )
        return list(self._routes[key])

    def get_spawn_point(self, approach: str, lane: int) -> WP:
        return self.get_route(approach, lane, "straight")[0]

    def get_stop_line(self, approach: str) -> WP:
        """Return (x, y) of the stop line centre on this approach."""
        route = self.get_route(approach, 0, "straight")
        return route[1]

    def get_all_lane_keys(self):
        for app in self.APPROACHES:
            adef = self.get_approach(app)
            for lane in (0, 1):
                for turn in adef.lanes[lane].allowed_turns:
                    if self.has_route(app, lane, turn):
                        yield (app, lane, turn)

    def to_dict(self) -> dict:
        return {
            "approaches": [
                {"name": a.name, "axis": a.axis,
                 "lanes": [{"idx": l.idx, "allowed_turns": list(l.allowed_turns)}
                           for l in a.lanes]}
                for a in self.approach_defs
            ],
            "num_routes": len(self._routes),
            "crosswalks": self.crosswalks,
        }
