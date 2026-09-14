"""Simulation-wide constants. All distances in metres, times in seconds."""

# ── Time step ────────────────────────────────────────────────
DT = 0.5                     # simulation tick interval (seconds)

# ── Road geometry ───────────────────────────────────────────
LANE_WIDTH = 3.5             # single lane width (m)
ROAD_WIDTH = 7.0             # total road width for two lanes (m)
LANE_OFFSET = 1.75           # lane centre from road centreline (m)

# Intersection
INTERSECTION_HALF = 3.5      # intersection extends  3.5 m from centre
STOP_LINE_OFFSET = 14.0      # stop line distance from centre (m)
CROSSWALK_WIDTH = 3.0        # crosswalk stripe zone width (m)

# Spawn / despawn
SPAWN_DISTANCE = 100.0       # vehicles appear this far from centre (m)
DESPAWN_DISTANCE = 110.0     # vehicles removed past this distance (m)
WAYPOINT_RADIUS = 2.0        # distance to consider waypoint "reached" (m)

# ── Vehicle parameters ──────────────────────────────────────
VEHICLE_LENGTH = 4.5         # car length (m)
VEHICLE_WIDTH = 2.0          # car width (m)
MAX_SPEED = 13.89            # ~50 km/h (m/s)
MIN_GAP = 2.5                # min gap between stopped vehicles (m)
TIME_HEADWAY = 1.2           # desired time gap to lead vehicle (s)
COMFORT_ACCEL = 1.5          # max acceleration (m/s²)
COMFORT_DECEL = -2.5         # max deceleration (m/s²)
MAX_DECEL = -4.5             # hard braking (m/s²)
SPEED_LIMIT = 13.89          # max allowed speed (m/s)

# ── Fixed-time signal phases (seconds) ──────────────────────
NS_GREEN = 30
NS_YELLOW = 3
ALL_RED = 2
EW_GREEN = 30
EW_YELLOW = 3

# ── Pedestrian parameters ──────────────────────────────────
PED_SPEED = 1.4              # walking speed (m/s)
PED_START_GAP = 0.5          # gap between pedestrians on same crosswalk (m)

# ── Spawn rates (vehicles / hour / approach) ───────────────
SPAWN_RATES = {
    "low": 300,
    "medium": 600,
    "heavy": 1200,
}
PED_SPAWN_RATES = {
    "low": 60,
    "medium": 180,
    "heavy": 360,
}
