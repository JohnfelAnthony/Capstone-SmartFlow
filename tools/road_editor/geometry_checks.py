"""Conservative draft checks; these do not certify swept vehicle clearance."""
from __future__ import annotations

import math

EPS = 1e-9


def _cross(a, b, c):
    return (b[0] - a[0]) * (c[1] - a[1]) - (b[1] - a[1]) * (c[0] - a[0])


def _on_segment(a, b, p):
    return (abs(_cross(a, b, p)) <= EPS and min(a[0], b[0]) - EPS <= p[0] <= max(a[0], b[0]) + EPS
            and min(a[1], b[1]) - EPS <= p[1] <= max(a[1], b[1]) + EPS)


def _intersects(a, b, c, d):
    # A bounding-box rejection avoids expensive orientation and point-on-edge
    # checks for the many distant segment pairs in long, diagonal islands.
    if (max(a[0], b[0]) + EPS < min(c[0], d[0]) or max(c[0], d[0]) + EPS < min(a[0], b[0])
            or max(a[1], b[1]) + EPS < min(c[1], d[1]) or max(c[1], d[1]) + EPS < min(a[1], b[1])):
        return False
    ab_c, ab_d, cd_a, cd_b = _cross(a, b, c), _cross(a, b, d), _cross(c, d, a), _cross(c, d, b)
    if ((ab_c > EPS and ab_d < -EPS) or (ab_c < -EPS and ab_d > EPS)) and ((cd_a > EPS and cd_b < -EPS) or (cd_a < -EPS and cd_b > EPS)):
        return True
    return any((_on_segment(a, b, c), _on_segment(a, b, d), _on_segment(c, d, a), _on_segment(c, d, b)))


def simple_polygon(points):
    """Reject degenerate area, zero-length edges and self-crossings or touches."""
    if len(points) > 3 and points[0] == points[-1]:
        points = points[:-1]
    count = len(points)
    if count < 3 or any(points[i] == points[(i + 1) % count] for i in range(count)):
        return False
    # Translation avoids losing precision when coordinates have large offsets.
    origin = points[0]
    twice_area = sum((a[0]-origin[0])*(b[1]-origin[1]) - (b[0]-origin[0])*(a[1]-origin[1])
                     for a, b in zip(points, points[1:] + points[:1]))
    if abs(twice_area) <= EPS:
        return False
    for i in range(count):
        for j in range(i + 1, count):
            if j == i + 1 or (i == 0 and j == count - 1):
                continue
            if _intersects(points[i], points[(i + 1) % count], points[j], points[(j + 1) % count]):
                return False
    return True


def simple_polyline(points):
    """Reject self-crossings, self-touches and adjacent segments that retrace."""
    if len(points) < 2 or any(a == b for a, b in zip(points, points[1:])):
        return False
    segments = list(zip(points, points[1:]))
    for i, (a, b) in enumerate(segments):
        for j in range(i + 1, len(segments)):
            c, d = segments[j]
            if j == i + 1:
                if abs(_cross(a, b, d)) <= EPS and ((a[0]-b[0])*(d[0]-b[0]) + (a[1]-b[1])*(d[1]-b[1])) > EPS:
                    return False
                continue
            if _intersects(a, b, c, d):
                return False
    return True


def _point_distance(p, a, b):
    dx, dy = b[0] - a[0], b[1] - a[1]
    denominator = dx * dx + dy * dy
    t = max(0., min(1., ((p[0] - a[0]) * dx + (p[1] - a[1]) * dy) / denominator)) if denominator else 0.
    return math.hypot(p[0] - a[0] - t * dx, p[1] - a[1] - t * dy)


def lane_envelopes_overlap(first, first_width, second, second_width):
    """Conservative swept-width test; endpoint round caps can cause false positives."""
    clearance = (first_width + second_width) / 2
    for a, b in zip(first, first[1:]):
        for c, d in zip(second, second[1:]):
            if (max(a[0], b[0]) + clearance < min(c[0], d[0]) or
                    max(c[0], d[0]) + clearance < min(a[0], b[0]) or
                    max(a[1], b[1]) + clearance < min(c[1], d[1]) or
                    max(c[1], d[1]) + clearance < min(a[1], b[1])):
                continue
            if _intersects(a, b, c, d):
                return True
            gap = min(_point_distance(a, c, d), _point_distance(b, c, d),
                      _point_distance(c, a, b), _point_distance(d, a, b))
            if gap < clearance - EPS:
                return True
    return False


def lane_overlap_ranges(first, first_width, second, second_width):
    """Conservative along-path ranges for overlapping swept-width envelopes.

    A whole segment is included whenever any part may overlap; long or curved
    segments can therefore make the returned ranges much larger than the true
    conflict. These ranges are not a traffic reservation or a safety proof.
    """
    def segments(points):
        distance = 0.
        for a, b in zip(points, points[1:]):
            end = distance + math.dist(a, b)
            yield a, b, distance, end
            distance = end
    hits = [(a0, a1, b0, b1) for a, b, a0, a1 in segments(first)
            for c, d, b0, b1 in segments(second)
            if lane_envelopes_overlap([a, b], first_width, [c, d], second_width)]
    if not hits:
        return None
    return {"first": [min(hit[0] for hit in hits), max(hit[1] for hit in hits)],
            "second": [min(hit[2] for hit in hits), max(hit[3] for hit in hits)]}


def _inside(point, polygon):
    x, y = point
    inside = False
    for a, b in zip(polygon, polygon[1:] + polygon[:1]):
        if _on_segment(a, b, point):
            return True
        if (a[1] > y) != (b[1] > y) and x < (b[0] - a[0]) * (y - a[1]) / (b[1] - a[1]) + a[0]:
            inside = not inside
    return inside


def polygons_touch_or_overlap(first, second):
    """Conservative intersection for simple polygons, including edge contact."""
    if len(first) < 3 or len(second) < 3:
        return False
    if (_inside(first[0], second) or _inside(second[0], first)):
        return True
    return any(_intersects(a, b, c, d) for a, b in zip(first, first[1:] + first[:1])
               for c, d in zip(second, second[1:] + second[:1]))


def lane_touches_island(shape, width, polygon):
    """Detect centerline/width overlap with an island; excludes connector sweeps."""
    edges = list(zip(polygon, polygon[1:] + polygon[:1]))
    for a, b in zip(shape, shape[1:]):
        if _inside(a, polygon) or _inside(b, polygon):
            return True
        for c, d in edges:
            if _intersects(a, b, c, d):
                return True
            if min(_point_distance(a, c, d), _point_distance(b, c, d), _point_distance(c, a, b), _point_distance(d, a, b)) <= width / 2 + EPS:
                return True
    return False
