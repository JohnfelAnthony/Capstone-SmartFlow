"""Conservative finite-line crossing proposals in displayed pixel coordinates."""

import math

from .core import identifier, number, require

LINE_EVENTS = ("vehicle_arrival", "vehicle_discharge", "pedestrian_start", "pedestrian_complete")
# What each line is for. A priority line records the time a vehicle enters the priority zone; it feeds the arrival-order
# check, not demand. The role is optional and kept with the line so exports show which line plays which part.
LINE_ROLES = {"arrival": ("vehicle_arrival",), "priority": ("vehicle_discharge",), "stopline": ("vehicle_discharge",),
              "exit": ("vehicle_discharge",), "crossing": ("pedestrian_start", "pedestrian_complete")}


def validate_config(config: dict, manifest: dict) -> None:
    require(config.get("schema_version") == 1, "Unsupported counting-line format.")
    require(config.get("source_sha256") == manifest["source_sha256"] and
            config.get("take_id") == manifest["take_id"], "Counting lines belong to a different recording/take.")
    require(config.get("coordinate_space") == "display_pixels", "Expected display_pixels coordinates.")
    rotation = config.get("rotation_clockwise")
    require(rotation in (0, 90, 180, 270), "Rotation must be 0, 90, 180 or 270 degrees clockwise.")
    width, height = manifest["media"]["width"], manifest["media"]["height"]
    if rotation in (90, 270):
        width, height = height, width
    require(config.get("width") == width and config.get("height") == height, "Counting-line image dimensions changed.")
    for name in ("max_gap_s", "deadband_px"):
        require(isinstance(config.get(name), (int, float)) and not isinstance(config[name], bool), f"{name} must be numeric.")
    require(0 < number(config.get("max_gap_s"), "max_gap_s") <= 2, "max_gap_s must be in (0, 2].")
    require(0 < number(config.get("deadband_px"), "deadband_px") < min(width, height) / 4,
            "deadband_px must be positive and less than a quarter of the image size.")
    require(isinstance(config.get("lines"), list) and bool(config["lines"]), "Add at least one counting line.")
    ids = set()
    for line in config["lines"]:
        line_id = identifier(line["id"], "line id")
        require(line_id not in ids, "Duplicate counting-line ID.")
        ids.add(line_id)
        require(line.get("event_type") in LINE_EVENTS, "Unsupported line event type; turning movements need manual review.")
        require(line.get("direction") in ("negative_to_positive", "positive_to_negative"), "Select one line-crossing direction.")
        identifier(line.get("location_id", ""), "location_id")
        key = "approach_id" if line["event_type"].startswith("vehicle_") else "crossing_id"
        identifier(line.get(key, ""), key)
        role = line.get("role")
        if role is not None:
            require(role in LINE_ROLES, "Unknown line role.")
            require(line["event_type"] in LINE_ROLES[role], f"A {role} line cannot record {line['event_type']} events.")
        for point in (line["a"], line["b"]):
            require(isinstance(point, list) and len(point) == 2, "Each endpoint needs [x, y].")
            require(all(isinstance(value, (int, float)) and not isinstance(value, bool) for value in point),
                    "Line endpoints must be numeric coordinates.")
            require(0 <= number(point[0], "x") < width and 0 <= number(point[1], "y") < height,
                    "Line endpoints must be inside the displayed frame.")
        require(math.dist(line["a"], line["b"]) > 2 * config["deadband_px"], "Counting line is too short.")


class LineCounter:
    """One proposal per track/line, with deadband, finite endpoints and gap limits.

    This does not repair ID switches or infer a pedestrian's intention. A reviewer
    must reject riders/sidewalk traffic and check objects absent from proposals.
    """

    def __init__(self, config: dict):
        self.config = config
        self.states = {}
        self.fired = set()

    def update(self, track: dict, time_s: float) -> list[dict]:
        point = ((track["x1"] + track["x2"]) / 2, track["y2"])
        pedestrian = track["detected_class"] == "person"
        proposals = []
        for line in self.config["lines"]:
            if line["event_type"].startswith("pedestrian_") != pedestrian:
                continue
            key = (track["track_id"], line["id"])
            if key in self.fired:
                continue
            a, b = line["a"], line["b"]
            dx, dy = b[0] - a[0], b[1] - a[1]
            distance = (dx * (point[1] - a[1]) - dy * (point[0] - a[0])) / math.hypot(dx, dy)
            side = 1 if distance > self.config["deadband_px"] else -1 if distance < -self.config["deadband_px"] else 0
            previous = self.states.get(key)
            # Deadband observations do not refresh the last stable-side time:
            # a long stationary/occluded interval cannot fabricate a crossing.
            if side == 0:
                continue
            self.states[key] = (side, point, distance, time_s)
            if previous is None or time_s - previous[3] > self.config["max_gap_s"] or previous[0] == side:
                continue
            direction = "negative_to_positive" if previous[0] < side else "positive_to_negative"
            if direction != line["direction"]:
                continue
            fraction = previous[2] / (previous[2] - distance)
            intersection = (previous[1][0] + fraction * (point[0] - previous[1][0]),
                            previous[1][1] + fraction * (point[1] - previous[1][1]))
            projection = ((intersection[0] - a[0]) * dx + (intersection[1] - a[1]) * dy) / (dx * dx + dy * dy)
            if 0 <= projection <= 1:
                self.fired.add(key)
                proposals.append(line)
        # Bound memory for departed tracks; fired IDs stay to prevent recounts.
        if len(self.states) > 2000:
            cutoff = time_s - self.config["max_gap_s"]
            self.states = {key: value for key, value in self.states.items() if value[3] >= cutoff}
        return proposals
