"""Loopback-only editor service. It never changes a registered network."""
from __future__ import annotations

import argparse
import base64
import binascii
import hashlib
import json
import math
import os
import secrets
import threading
import uuid
import webbrowser
import xml.etree.ElementTree as ET
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse

from simulation.network_registry import load_registered_network, registered_networks
from simulation.road_network import RoadNetwork
from simulation.scenario_config import VEHICLE_TYPES
from tools.road_editor.geometry_checks import lane_envelopes_overlap, lane_touches_island, polygons_touch_or_overlap, simple_polygon, simple_polyline
from tools.road_editor.image_dimensions import image_dimensions

ASSETS = Path(__file__).parent
LIMIT = 5 * 1024 * 1024
PROJECT_LIMIT = 34 * 1024 * 1024  # 20 MB image encoded as base64 plus a bounded network

# Clearance errors have a separate status: a parseable network with a possible
# vehicle/island conflict is not thereby proven physically safe. Geometry and
# directed-connectivity errors, however, make the structure itself invalid.
STRUCTURAL_ERROR_CODES = frozenset({
    "road_self_intersection", "island_self_intersection", "study_junction_missing",
    "boundary_no_exit", "boundary_unreachable", "lane_no_exit",
    "study_unreachable_from_boundary", "boundary_unreachable_from_study",
})


def project_bytes(project):
    """Bound the network separately from the optional local reference image."""
    network = json.dumps(project.get("network"), ensure_ascii=False, allow_nan=False).encode("utf-8")
    if len(network) > LIMIT:
        raise ValueError("Network is larger than 5 MB")
    image = project.get("reference_image")
    if image is not None:
        if not isinstance(image, dict):
            raise ValueError("Reference image must be an object")
        data = image.get("data_url", "")
        if not isinstance(data, str) or not data.startswith(("data:image/png;base64,", "data:image/jpeg;base64,")) or len(data) > 28 * 1024 * 1024:
            raise ValueError("Reference image must be a PNG or JPEG of at most 20 MB")
        try:
            header, encoded = data.split(",", 1)
            decoded = base64.b64decode(encoded, validate=True)
        except (ValueError, binascii.Error):
            raise ValueError("Reference image is not valid base64") from None
        signature = b"\x89PNG\r\n\x1a\n" if header == "data:image/png;base64" else b"\xff\xd8\xff"
        if len(decoded) > 20 * 1024 * 1024 or not decoded.startswith(signature):
            raise ValueError("Reference image has an invalid signature or exceeds 20 MB")
        # Check the encoded file, not browser-supplied dimensions. The browser
        # separately decodes the image before importing it into a project.
        image_dimensions(decoded, header)
    result = json.dumps(project, ensure_ascii=False, allow_nan=False).encode("utf-8")
    if len(result) > PROJECT_LIMIT:
        raise ValueError("Project is too large")
    return result


def disconnected_components(payload):
    """Identify weak components only when node IDs and endpoints are well formed."""
    ids = [node.get("id") for node in payload["nodes"]]
    if any(not isinstance(node_id, str) or not node_id for node_id in ids) or len(set(ids)) != len(ids):
        return []  # The native parser gives the authoritative ID error.
    adjacency = {node_id: set() for node_id in ids}
    for road in payload["roads"]:
        source, target = road.get("source"), road.get("target")
        if not isinstance(source, str) or not isinstance(target, str) or source not in adjacency or target not in adjacency:
            return []  # Let the native parser report malformed endpoints.
        adjacency[source].add(target)
        adjacency[target].add(source)
    remaining, components = set(ids), []
    while remaining:
        frontier, component = [min(remaining)], set()
        while frontier:
            node = frontier.pop()
            if node in component:
                continue
            component.add(node)
            frontier.extend(adjacency[node] - component)
        remaining -= component
        components.append(sorted(component))
    return components if len(components) > 1 else []


def validate(payload):
    """Use the native parser for structural checks, without claiming clearance."""
    issues = []
    if not isinstance(payload, dict):
        return {"issues": [{"severity": "error", "code": "payload", "message": "Network must be an object."}], "visual": None, "fingerprint": None, "structurally_valid": False, "clearance_checked": False, "traffic_validation_run": False}
    try:
        for kind in ("nodes", "roads"):
            if not isinstance(payload.get(kind), list) or not all(isinstance(v, dict) for v in payload[kind]):
                raise ValueError(f"{kind} must be a list of objects")
        for road in payload["roads"]:
            shape = road.get("shape")
            if not isinstance(shape, list) or len(shape) < 2:
                raise ValueError(f"Road {road.get('id', '?')} needs at least two points")
            for point in shape:
                if not isinstance(point, list) or len(point) != 2 or any(isinstance(x, bool) or not isinstance(x, (int, float)) or not math.isfinite(x) for x in point):
                    raise ValueError(f"Road {road.get('id', '?')} has invalid coordinates")
            if any(a == b for a, b in zip(shape, shape[1:])):
                raise ValueError(f"Road {road.get('id', '?')} has duplicate adjacent points")
        components = disconnected_components(payload)
        if components:
            return {"issues": [{"severity": "error", "code": "disconnected_component", "message": f"Disconnected component contains: {', '.join(component)}.", "node_id": component[0], "node_ids": component} for component in components],
                    "visual": None, "fingerprint": None, "structurally_valid": False, "clearance_checked": False, "traffic_validation_run": False}
        network = RoadNetwork(payload)
        visual = network.visual()
    except (ValueError, KeyError, TypeError, IndexError, OverflowError) as exc:
        return {"issues": [{"severity": "error", "code": "structure", "message": str(exc)}], "visual": None, "fingerprint": None, "structurally_valid": False, "clearance_checked": False, "traffic_validation_run": False}
    for road in payload["roads"]:
        if not simple_polyline(road["shape"]):
            issues.append({"severity": "error", "code": "road_self_intersection", "message": f"Road {road['id']} crosses, touches or retraces itself.", "road_id": road["id"]})
    lanes = list(network.lanes.values())
    for index, first in enumerate(lanes):
        for second in lanes[index + 1:]:
            if lane_envelopes_overlap(first.shape, first.width, second.shape, second.width):
                issues.append({"severity": "warning", "code": "lane_envelope_overlap", "message": f"Lanes {first.id} and {second.id} may overlap outside connectors; inspect their geometry and traffic behavior.",
                               "road_id": first.id[:-1], "other_road_id": second.id[:-1], "lane_id": first.id, "other_lane_id": second.id})
    for index, island in enumerate(network.islands):
        if not simple_polygon(island["shape"]):
            continue
        for other in network.islands[index + 1:]:
            if simple_polygon(other["shape"]) and polygons_touch_or_overlap(island["shape"], other["shape"]):
                issues.append({"severity": "warning", "code": "island_overlap",
                               "message": f"Islands {island['id']} and {other['id']} overlap or touch; review whether their boundaries are intentional.",
                               "island_id": island["id"], "other_island_id": other["id"]})
    for island in network.islands:
        polygon = island["shape"]
        if not simple_polygon(polygon):
            issues.append({"severity": "error", "code": "island_self_intersection", "message": f"Island {island['id']} crosses or touches itself.", "island_id": island["id"]})
            continue
        # A circumscribed body radius covers every possible vehicle heading;
        # using the full lane width as possible lateral centre position is
        # deliberately conservative and may yield false positives.
        body_radii = {name: math.hypot(spec["length"], spec["width"]) / 2 for name, spec in VEHICLE_TYPES.items()}
        for lane in network.lanes.values():
            if lane_touches_island(lane.shape, lane.width, polygon):
                issues.append({"severity": "error", "code": "island_lane_overlap", "message": f"Island {island['id']} touches lane {lane.id} pavement.", "island_id": island["id"], "lane_id": lane.id})
            else:
                possible = [name for name, radius in body_radii.items() if lane_touches_island(lane.shape, lane.width + 2 * radius, polygon)]
                if possible:
                    issues.append({"severity": "error", "code": "island_lane_vehicle_envelope", "message": f"Island {island['id']} may conflict with a vehicle on lane {lane.id}; inspect body clearance.",
                                   "island_id": island["id"], "lane_id": lane.id, "potential_vehicle_classes": possible})
        # A vehicle centre may use any permitted lateral offset and its body may
        # rotate on a curve. A circumscribed circle plus the widest adjacent lane
        # gives a conservative envelope; overlap is a possible conflict, not
        # proof that a particular vehicle actually contacts the island.
        body_radius = max(body_radii.values())
        for junction in network.intersections:
            for incoming in network.incoming[junction]:
                for outgoing in network.outgoing[junction]:
                    if not network.turn_allowed(incoming, outgoing):
                        continue
                    width = max(network.lanes[incoming].width, network.lanes[outgoing].width) + 2 * body_radius
                    if lane_touches_island(network.connector(incoming, outgoing), width, polygon):
                        issues.append({"severity": "error", "code": "island_connector_envelope", "message": f"Island {island['id']} may conflict with movement {incoming} to {outgoing}; inspect vehicle clearance.",
                                       "island_id": island["id"], "incoming_lane_id": incoming, "outgoing_lane_id": outgoing})
    for boundary in network.boundaries:
        others = [item for item in network.boundaries if item != boundary]
        if network.outgoing[boundary] and not any(network.route(boundary, item) for item in others):
            issues.append({"severity": "error", "code": "boundary_no_exit", "message": f"Traffic entering at {boundary} cannot reach another boundary.", "node_id": boundary})
        if network.incoming[boundary] and not any(network.route(item, boundary) for item in others):
            issues.append({"severity": "error", "code": "boundary_unreachable", "message": f"No other boundary can reach exit {boundary}.", "node_id": boundary})
    for junction in network.intersections:
        for incoming in network.incoming[junction]:
            if not any(network.turn_allowed(incoming, outgoing) for outgoing in network.outgoing[junction]):
                issues.append({"severity": "error", "code": "lane_no_exit", "message": f"Lane {incoming} has no permitted exit at {junction}.", "node_id": junction, "lane_id": incoming})
    study = {"tagum_site_a": "tagum_site_a_j", "tagum_site_b": "tagum_site_b_j"}.get(network.id)
    if study and study not in network.intersections:
        issues.append({"severity": "error", "code": "study_junction_missing", "message": f"Required study junction {study} is missing or marked as a boundary."})
    elif study:
        for boundary in network.boundaries:
            if network.outgoing[boundary] and not network.route(boundary, study):
                issues.append({"severity": "error", "code": "study_unreachable_from_boundary", "message": f"Traffic entering at {boundary} cannot reach the study junction.", "node_id": boundary})
            if network.incoming[boundary] and not network.route(study, boundary):
                issues.append({"severity": "error", "code": "boundary_unreachable_from_study", "message": f"Traffic from the study junction cannot reach exit {boundary}.", "node_id": boundary})
    issues.append({"severity": "warning", "code": "clearance_unchecked", "message": "Full vehicle-footprint and connector clearance has not been checked. This draft is not eligible for activation."})
    issues.append({"severity": "warning", "code": "traffic_unchecked", "message": "Traffic behavior and field accuracy have not been validated."})
    return {"issues": issues, "visual": visual, "fingerprint": network.fingerprint, "structurally_valid": not any(issue["code"] in STRUCTURAL_ERROR_CODES for issue in issues), "clearance_checked": False, "traffic_validation_run": False}


def _network_for_sampled_review(payload):
    diagnostic = validate(payload)
    if not diagnostic["structurally_valid"]:
        raise ValueError("Fix structural errors before running sampled connector review")
    network = RoadNetwork(payload)
    point_count = sum(len(road["shape"]) for road in payload["roads"]) + sum(len(island["shape"]) for island in network.islands)
    if len(network.intersections) > 20 or len(network.islands) > 50 or point_count > 2000:
        raise ValueError("Sampled review supports at most 20 junctions, 50 islands and 2,000 geometry points")
    return network


def sampled_island_review(payload):
    """Run the sampled connector-body diagnostic on a valid draft."""
    network = _network_for_sampled_review(payload)
    from tools.site_b_island_sweep_review import review
    return review(network)


def sampled_lane_review(payload):
    """Run the sampled lane-body diagnostic without asserting clearance."""
    network = _network_for_sampled_review(payload)
    from tools.site_b_island_sweep_review import review_lanes
    return review_lanes(network)


def review_bundle(payload):
    """Capture one unvalidated draft, diagnostics and a simple centreline overview."""
    result = validate(payload)
    if not isinstance(payload, dict) or not isinstance(payload.get("roads"), list):
        raise ValueError("Draft needs a roads list for the overview")
    shapes = []
    for road in payload["roads"]:
        if not isinstance(road, dict) or not isinstance(road.get("shape"), list):
            raise ValueError("Each road needs a shape for the overview")
        points = road["shape"]
        if len(points) < 2 or any(not isinstance(p, list) or len(p) != 2 or any(isinstance(v, bool) or not isinstance(v, (int, float)) or not math.isfinite(v) for v in p) for p in points):
            raise ValueError("Road shapes need finite points for the overview")
        shapes.append((str(road.get("id", "")), points))
    if not shapes:
        raise ValueError("At least one road is needed for the overview")
    coords = [point for _, shape in shapes for point in shape]
    xmin, xmax = min(p[0] for p in coords), max(p[0] for p in coords)
    ymin, ymax = min(p[1] for p in coords), max(p[1] for p in coords)
    span = max(xmax-xmin, ymax-ymin, 30)
    margin = span * .1
    svg = ET.Element("svg", {"xmlns": "http://www.w3.org/2000/svg", "viewBox": f"{xmin-margin} {-ymax-margin} {xmax-xmin+2*margin} {ymax-ymin+2*margin}", "role": "img"})
    ET.SubElement(svg, "title").text = "Unvalidated road-centreline overview; not for installation"
    ET.SubElement(svg, "rect", {"x": str(xmin-margin), "y": str(-ymax-margin), "width": str(xmax-xmin+2*margin), "height": str(ymax-ymin+2*margin), "fill": "#eff3ef"})
    for island in payload.get("islands", []):
        points = island.get("shape") if isinstance(island, dict) else None
        if isinstance(points, list) and len(points) >= 3 and all(isinstance(p, list) and len(p) == 2 and all(isinstance(v, (int, float)) and not isinstance(v, bool) and math.isfinite(v) for v in p) for p in points):
            polygon = ET.SubElement(svg, "polygon", {"points": " ".join(f"{x},{-y}" for x, y in points), "fill": "#96b579" if island.get("planted") else "#d8d9d4", "stroke": "#668259", "stroke-width": str(span*.002)})
            ET.SubElement(polygon, "title").text = str(island.get("id", ""))
    for road_id, shape in shapes:
        line = ET.SubElement(svg, "polyline", {"points": " ".join(f"{x},{-y}" for x, y in shape), "fill": "none", "stroke": "#366e68", "stroke-width": str(span*.004)})
        ET.SubElement(line, "title").text = road_id
    for node in payload.get("nodes", []):
        if isinstance(node, dict) and all(isinstance(node.get(k), (int, float)) and not isinstance(node[k], bool) and math.isfinite(node[k]) for k in ("x", "y")):
            dot = ET.SubElement(svg, "circle", {"cx": str(node["x"]), "cy": str(-node["y"]), "r": str(span*.004), "fill": "#b66325"})
            ET.SubElement(dot, "title").text = str(node.get("id", ""))
    ET.SubElement(svg, "text", {"x": str(xmin-margin*.8), "y": str(-ymax-margin*.4), "font-size": str(span*.025), "fill": "#762d24"}).text = "UNVALIDATED DRAFT — centre lines only"
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True, allow_nan=False).encode()
    return {"kind": "unvalidated_road_editor_review", "installable": False, "draft_sha256": hashlib.sha256(canonical).hexdigest(), "network": payload,
            "validation": {key: value for key, value in result.items() if key != "visual"}, "overview_svg": ET.tostring(svg, encoding="unicode")}


class ProjectStore:
    def __init__(self, directory):
        self.directory = Path(directory)
        self.directory.mkdir(parents=True, exist_ok=True)
        self.lock = threading.RLock()

    def path(self, project_id):
        try:
            if str(uuid.UUID(project_id)) != project_id:
                raise ValueError()
        except (ValueError, TypeError, AttributeError):
            raise ValueError("Invalid project ID") from None
        return self.directory / (project_id + ".json")

    def read(self, project_id):
        with self.lock:
            return json.loads(self.path(project_id).read_text(encoding="utf-8"))

    def list(self):
        result = []
        with self.lock:
            for path in self.directory.glob("*.json"):
                try:
                    if path.name == "recovery.json":
                        continue
                    item = json.loads(path.read_text(encoding="utf-8"))
                    result.append({key: item.get(key) for key in ("id", "name", "revision")})
                except (OSError, ValueError):
                    continue
        return result

    def recovery(self, draft=None, *, clear=False):
        """Keep recovery separate from explicitly saved, revisioned projects."""
        path = self.directory / "recovery.json"
        with self.lock:
            if clear:
                path.unlink(missing_ok=True)
                return None
            if draft is None:
                if not path.exists():
                    return None
                return json.loads(path.read_text(encoding="utf-8"))
            if not isinstance(draft, dict) or not isinstance(draft.get("network"), dict):
                raise ValueError("Recovery needs a network object")
            data = project_bytes(draft)
            temporary = self.directory / (uuid.uuid4().hex + ".tmp")
            try:
                temporary.write_bytes(data)
                os.replace(temporary, path)
            finally:
                temporary.unlink(missing_ok=True)
            return {"saved": True}

    def save(self, project, expected=None):
        with self.lock:
            project_id = project.get("id") or str(uuid.uuid4())
            path = self.path(project_id)
            current = self.read(project_id) if path.exists() else None
            if current and expected != current["revision"]:
                raise ValueError("Project changed in another window. Reopen it before saving.")
            if not current and expected not in (None, 0):
                raise ValueError("Project no longer exists. Save a new copy.")
            if not isinstance(project.get("network"), dict):
                raise ValueError("Project needs a network object")
            result = {**project, "id": project_id, "project_version": 1, "revision": (current["revision"] if current else 0) + 1}
            data = project_bytes(result)
            temporary = self.directory / (project_id + "." + uuid.uuid4().hex + ".tmp")
            try:
                temporary.write_bytes(data)
                os.replace(temporary, path)
            finally:
                temporary.unlink(missing_ok=True)
            return result


def make_server(data_dir, port=0):
    token = secrets.token_urlsafe(32)
    store = ProjectStore(data_dir)

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *_args):
            pass

        def response(self, content, status=200, content_type="application/json; charset=utf-8"):
            data = json.dumps(content, ensure_ascii=False, allow_nan=False).encode() if content_type.startswith("application/json") else content
            self.send_response(status)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(data)))
            self.send_header("Cache-Control", "no-store")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.send_header("Content-Security-Policy", "default-src 'self'; style-src 'self'; script-src 'self'; connect-src 'self'; img-src 'self' data:; object-src 'none'; base-uri 'none'; frame-ancestors 'none'")
            self.end_headers()
            self.wfile.write(data)

        def check_host(self):
            if self.headers.get("Host") not in (f"127.0.0.1:{self.server.server_port}", f"localhost:{self.server.server_port}"):
                raise ValueError("Only local requests are allowed")

        def do_GET(self):
            try:
                self.check_host()
                path = urlparse(self.path).path
                if path == "/":
                    data = (ASSETS / "index.html").read_text(encoding="utf-8").replace("__TOKEN__", token).encode()
                    self.response(data, content_type="text/html; charset=utf-8")
                elif path in ("/app.js", "/scene.js", "/topology.js", "/style.css"):
                    self.response((ASSETS / path[1:]).read_bytes(), content_type="text/javascript; charset=utf-8" if path.endswith(".js") else "text/css; charset=utf-8")
                elif path == "/api/networks":
                    self.response(registered_networks())
                elif path.startswith("/api/networks/"):
                    self.response(load_registered_network(path.rsplit("/", 1)[1]).payload)
                elif path == "/api/projects":
                    self.response(store.list())
                elif path == "/api/recovery":
                    self.response(store.recovery())
                elif path.startswith("/api/projects/"):
                    self.response(store.read(path.rsplit("/", 1)[1]))
                else:
                    self.response({"error": "Not found"}, 404)
            except ConnectionError:
                pass
            except (ValueError, OSError, KeyError, TypeError) as exc:
                self.response({"error": str(exc)}, 400)

        def do_POST(self):
            try:
                self.check_host()
                if not secrets.compare_digest(self.headers.get("X-Editor-Token", ""), token):
                    raise ValueError("Refresh the editor before making changes")
                if self.headers.get("Origin", f"http://{self.headers['Host']}") != f"http://{self.headers['Host']}":
                    raise ValueError("Cross-site requests are not accepted")
                size = int(self.headers.get("Content-Length", "0"))
                request_limit = PROJECT_LIMIT if urlparse(self.path).path in ("/api/projects", "/api/recovery") else LIMIT
                if not 0 < size <= request_limit:
                    raise ValueError("Request exceeds the allowed size")
                body = json.loads(self.rfile.read(size), parse_constant=lambda _: (_ for _ in ()).throw(ValueError("Non-finite value")))
                if not isinstance(body, dict):
                    raise ValueError("Expected a JSON object")
                path = urlparse(self.path).path
                if path == "/api/validate":
                    self.response(validate(body.get("network")))
                elif path == "/api/sampled-island-review":
                    self.response(sampled_island_review(body.get("network")))
                elif path == "/api/sampled-lane-review":
                    self.response(sampled_lane_review(body.get("network")))
                elif path == "/api/review":
                    self.response(review_bundle(body.get("network")))
                elif path == "/api/projects":
                    self.response(store.save(body.get("project", {}), body.get("expected_revision")))
                elif path == "/api/recovery":
                    self.response(store.recovery(body.get("draft"), clear=body.get("clear") is True))
                elif path == "/api/export":
                    result = validate(body.get("network"))
                    self.response({"error": "Validated export is unavailable until full vehicle-footprint and island clearance checks are implemented.", "validation": result}, 422)
                else:
                    self.response({"error": "Not found"}, 404)
            except ConnectionError:
                pass
            except (ValueError, OSError, KeyError, TypeError) as exc:
                self.response({"error": str(exc)}, 400)

    server = ThreadingHTTPServer(("127.0.0.1", port), Handler)
    server.daemon_threads = True
    return server


def main():
    parser = argparse.ArgumentParser(description="SmartFlow local road editor")
    parser.add_argument("--port", type=int, default=0)
    parser.add_argument("--no-browser", action="store_true")
    parser.add_argument("--data-dir", type=Path, default=Path.home() / ".smartflow" / "road-editor")
    args = parser.parse_args()
    server = make_server(args.data_dir, args.port)
    url = f"http://127.0.0.1:{server.server_port}/"
    print(f"Road Editor: {url} (Ctrl+C to stop)", flush=True)
    if not args.no_browser:
        webbrowser.open(url)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
