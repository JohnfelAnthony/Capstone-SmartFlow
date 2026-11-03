import json
import base64
import re
import subprocess
import threading
import urllib.error
import urllib.request
import xml.etree.ElementTree as ET

import pytest

from simulation.network_registry import load_registered_network
from simulation.road_network import lanes_per_direction, width_per_direction
from tools.road_editor.server import ProjectStore, make_server, review_bundle, validate
from tools.road_editor.geometry_checks import lane_envelopes_overlap, lane_touches_island, simple_polygon, simple_polyline
from tests.mixed_traffic_helpers import junction_network


def test_unvalidated_review_binds_network_diagnostics_and_safe_svg():
    network = junction_network().payload
    network["roads"][0]["name"] = "<script>not markup</script>"
    network["islands"] = [{"id": "test-island", "shape": [[20, 20], [25, 20], [25, 25], [20, 25]]}]
    bundle = review_bundle(network)
    assert bundle["network"] == network
    assert bundle["installable"] is False
    assert bundle["draft_sha256"] == bundle["validation"]["fingerprint"]
    assert bundle["validation"]["clearance_checked"] is False
    root = ET.fromstring(bundle["overview_svg"])
    assert root.tag.endswith("svg")
    assert len(root.findall("{http://www.w3.org/2000/svg}polyline")) == len(network["roads"])
    assert len(root.findall("{http://www.w3.org/2000/svg}polygon")) == 1
    assert not root.findall(".//{http://www.w3.org/2000/svg}script")
    invalid = json.loads(json.dumps(network))
    invalid["nodes"].append({"id": "orphan", "x": 1, "y": 1, "boundary": True})
    report = review_bundle(invalid)
    assert not report["validation"]["structurally_valid"]
    assert report["validation"]["fingerprint"] is None and report["draft_sha256"]
    assert any(item["code"] == "disconnected_component" for item in report["validation"]["issues"])


def test_lane_editor_matches_native_and_preserves_width():
    payload = junction_network().payload
    road = payload["roads"][0]
    road["osm_tags"] = {"lanes": "4;3", "name": "original"}
    road.pop("width_per_direction_m", None)
    before = width_per_direction(road)
    script = "import {setRoadLanes as set} from './tools/road_editor/topology.js'; let s=''; for await(const c of process.stdin)s+=c; const n=JSON.parse(s); console.log(JSON.stringify(set(n,n.roads[0].id,3,false)))"
    process = subprocess.run(["node", "--input-type=module", "-e", script], input=json.dumps(payload), text=True, capture_output=True, check=True)
    changed = json.loads(process.stdout)["roads"][0]
    assert lanes_per_direction(changed) == 3
    assert width_per_direction(changed) == before == 6.6
    assert changed["editor_provenance"]["original_osm_lanes"] == "4;3"
    assert changed["osm_tags"]["name"] == "original"


def test_reference_image_is_saved_only_in_project_and_recovery(tmp_path):
    image = {"name": "site.png", "data_url": "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+/aAAAAABJRU5ErkJggg==", "width": 1, "height": 1,
             "x": 3, "y": 4, "scale": .5, "rotation": 30, "opacity": .6, "visible": True, "locked": False}
    network = junction_network().payload
    store = ProjectStore(tmp_path)
    saved = store.save({"name": "site", "network": network, "reference_image": image})
    assert store.read(saved["id"])["reference_image"] == image
    store.recovery({"network": network, "reference_image": image})
    assert store.recovery()["reference_image"] == image
    assert "reference_image" not in network
    with pytest.raises(ValueError, match="signature"):
        store.save({"network": network, "reference_image": {"data_url": "data:image/png;base64,YWJj"}})
    with pytest.raises(ValueError, match="base64"):
        store.save({"network": network, "reference_image": {"data_url": "data:image/png;base64,%%%"}})


def test_reference_image_pixel_limit_is_checked_from_encoded_header(tmp_path):
    import struct
    from tools.road_editor.server import project_bytes
    from tools.road_editor.image_dimensions import image_dimensions
    png = b"\x89PNG\r\n\x1a\n" + b"\x00\x00\x00\rIHDR" + struct.pack(">II", 10000, 5000)
    jpeg = b"\xff\xd8\xff\xc0\x00\x0b\x08" + struct.pack(">HH", 5000, 10000) + b"\x01\x01\x11\x00"
    for mime, data in (("png", png), ("jpeg", jpeg)):
        project = {"network": {}, "reference_image": {"width": 1, "height": 1,
                   "data_url": f"data:image/{mime};base64," + base64.b64encode(data).decode()}}
        with pytest.raises(ValueError, match="40 million"):
            project_bytes(project)
        with pytest.raises(ValueError, match="40 million"):
            ProjectStore(tmp_path).recovery(project)
    malformed = {"network": {}, "reference_image": {"data_url": "data:image/png;base64,iVBORw0KGgo="}}
    with pytest.raises(ValueError, match="header"):
        project_bytes(malformed)
    jpeg_at_limit = b"\xff\xd8\xff\xe0\x00\x04xx\xff\xc0\x00\x0b\x08" + struct.pack(">HH", 5000, 8000) + b"\x01\x01\x11\x00"
    assert image_dimensions(jpeg_at_limit, "data:image/jpeg;base64") == (8000, 5000)
    with pytest.raises(ValueError, match="dimensions"):
        image_dimensions(jpeg_at_limit[:-3], "data:image/jpeg;base64")


def test_native_preview_and_fingerprint_round_trip():
    original = load_registered_network("tagum_site_b")
    payload = json.loads(json.dumps(original.payload))
    result = validate(payload)
    assert result["structurally_valid"]
    assert result["fingerprint"] == original.fingerprint
    assert result["visual"]["network_id"] == payload["id"]
    assert not result["clearance_checked"]
    payload["roads"][0]["width_per_direction_m"] = 4.0
    assert validate(payload)["fingerprint"] != original.fingerprint


def test_island_crossings_and_lane_pavement_are_reported_without_certification():
    payload = json.loads(json.dumps(load_registered_network("tagum_site_b").payload))
    lane = next(iter(load_registered_network("tagum_site_b").lanes.values()))
    a, b = lane.shape[:2]
    x, y = (a[0] + b[0]) / 2, (a[1] + b[1]) / 2
    payload["islands"] = [{"id": "inside-lane", "shape": [[x-1, y-1], [x+1, y-1], [x+1, y+1], [x-1, y+1]]},
                          {"id": "crossed", "shape": [[0, 0], [4, 4], [0, 4], [3, 0]]}]
    result = validate(payload)
    assert not result["structurally_valid"]
    assert result["visual"] is not None  # Invalid geometry remains editable.
    assert not result["clearance_checked"]
    assert any(issue["code"] == "island_self_intersection" and issue["island_id"] == "crossed" for issue in result["issues"])
    assert any(issue["code"] == "island_lane_overlap" and issue["island_id"] == "inside-lane" and issue["lane_id"] == lane.id for issue in result["issues"])


def test_island_beyond_lane_pavement_still_flags_long_vehicle_body():
    from simulation.footprints import rectangle, rectangles_overlap
    from simulation.scenario_config import VEHICLE_TYPES
    network = junction_network()
    payload = network.payload
    lane = network.lanes["wf"]
    x, y = lane.shape[-1]
    payload["islands"] = [{"id": "near-end", "shape": [[x+3.8, y-.2], [x+4, y-.2], [x+4, y+.2], [x+3.8, y+.2]]}]
    assert not lane_touches_island(lane.shape, lane.width, payload["islands"][0]["shape"])
    bus = VEHICLE_TYPES["bus"]
    assert rectangles_overlap(rectangle(x, y, 0, bus["length"], bus["width"]), rectangle(x+3.9, y, 0, .2, .4))
    result = validate(payload)
    issue = next(item for item in result["issues"] if item["code"] == "island_lane_vehicle_envelope" and item["lane_id"] == "wf")
    assert "bus" in issue["potential_vehicle_classes"]
    assert result["clearance_checked"] is False


def test_lane_width_and_polygon_boundary_touch_are_conservatively_detected():
    polygon = [[0, 0], [10, 0], [10, 3], [0, 3]]
    assert simple_polygon(polygon)
    assert lane_touches_island([[-5, -1], [15, -1]], 2, polygon)
    assert not lane_touches_island([[-5, -2], [15, -2]], 2, polygon)
    assert not simple_polygon([[0, 0], [4, 4], [0, 4], [3, 0]])
    assert not simple_polygon([[0, 0], [2, 0], [4, 0]])
    assert not simple_polygon([[0, 0], [2, 0], [4, 0], [0, 0]])


def test_polygon_overlap_detects_crossing_touch_and_containment():
    from tools.road_editor.geometry_checks import polygons_touch_or_overlap

    square = [[0, 0], [4, 0], [4, 4], [0, 4]]
    assert polygons_touch_or_overlap(square, [[4, 1], [6, 1], [6, 3], [4, 3]])
    assert polygons_touch_or_overlap(square, [[-1, 1], [5, 1], [5, 2], [-1, 2]])
    assert polygons_touch_or_overlap(square, [[1, 1], [2, 1], [2, 2], [1, 2]])
    assert not polygons_touch_or_overlap(square, [[4.01, 1], [6, 1], [6, 3], [4.01, 3]])


def test_zero_area_island_is_reported_as_invalid_structure():
    payload = junction_network().payload
    payload["islands"] = [{"id": "flat", "shape": [[30, 30], [32, 30], [34, 30]]}]
    result = validate(payload)
    assert not result["structurally_valid"]
    assert any(issue["code"] == "structure" and "nonzero area" in issue["message"] for issue in result["issues"])
    assert not result["clearance_checked"]


def test_overlapping_or_touching_islands_are_flagged_for_review():
    payload = junction_network().payload
    payload["islands"] = [
        {"id": "one", "shape": [[40, 40], [44, 40], [44, 44], [40, 44]]},
        {"id": "two", "shape": [[44, 41], [48, 41], [48, 43], [44, 43]]},
    ]
    result = validate(payload)
    issue = next(item for item in result["issues"] if item["code"] == "island_overlap")
    assert {issue["island_id"], issue["other_island_id"]} == {"one", "two"}
    assert issue["severity"] == "warning" and not result["clearance_checked"]
    payload["islands"][1]["shape"] = [[45, 41], [48, 41], [48, 43], [45, 43]]
    result = validate(payload)
    assert not any(item["code"] == "island_overlap" for item in result["issues"])


def test_lane_envelopes_report_possible_conflicts_outside_junctions():
    assert lane_envelopes_overlap([[0, 0], [20, 0]], 4, [[10, -20], [10, 20]], 4)
    assert not lane_envelopes_overlap([[0, 0], [20, 0]], 4, [[0, 4], [20, 4]], 4)
    assert lane_envelopes_overlap([[0, 0], [20, 0]], 4, [[0, 3], [20, 3]], 4)
    payload = junction_network().payload
    north = next(road for road in payload["roads"] if road["id"] == "n")
    north["shape"] = [[0, 150], [-70, 20], [-70, -20], [0, 0]]
    result = validate(payload)
    matches = [issue for issue in result["issues"] if issue["code"] == "lane_envelope_overlap" and {issue["road_id"], issue["other_road_id"]} == {"w", "n"}]
    assert matches and all(issue["severity"] == "warning" for issue in matches)
    assert result["clearance_checked"] is False


def test_self_crossing_roads_and_duplicate_ids_are_reported():
    assert simple_polyline([[0, 0], [2, 0], [4, 0]])
    assert not simple_polyline([[0, 0], [4, 4], [0, 4], [4, 0]])
    assert not simple_polyline([[0, 0], [4, 0], [2, 0]])
    assert not simple_polyline([[0, 0], [4, 0], [4, 4], [0, 0]])
    payload = junction_network().payload
    payload["roads"][0]["shape"] = [[-150, 0], [-20, 30], [-80, 30], [-20, -30], [0, 0]]
    result = validate(payload)
    assert not result["structurally_valid"]
    assert any(issue["code"] == "road_self_intersection" and issue["road_id"] == payload["roads"][0]["id"] for issue in result["issues"])
    duplicate = junction_network().payload
    duplicate["nodes"].append(dict(duplicate["nodes"][0]))
    assert not validate(duplicate)["structurally_valid"]


def test_boundary_reachability_respects_turn_restrictions():
    payload = junction_network().payload
    payload["prohibited_turns"] = [["wf", "er"], ["wf", "nr"], ["wf", "sr"]]
    result = validate(payload)
    assert not result["structurally_valid"]
    assert result["visual"] is not None
    assert any(issue["code"] == "boundary_no_exit" and issue["node_id"] == "w" for issue in result["issues"])
    assert not any(issue["code"] == "boundary_unreachable" and issue["node_id"] == "w" for issue in result["issues"])
    assert any(issue["code"] == "lane_no_exit" and issue["lane_id"] == "wf" for issue in result["issues"])


def test_disconnected_components_and_missing_study_junction_are_actionable():
    payload = junction_network().payload
    payload["nodes"].append({"id": "orphan", "x": 200, "y": 200, "boundary": True})
    result = validate(payload)
    assert not result["structurally_valid"] and result["visual"] is None
    assert any(issue["code"] == "disconnected_component" and issue["node_ids"] == ["orphan"] for issue in result["issues"])
    payload = junction_network().payload
    payload["id"] = "tagum_site_a"
    result = validate(payload)
    assert not result["structurally_valid"]
    assert any(issue["code"] == "study_junction_missing" for issue in result["issues"])


def test_study_reachability_is_checked_even_when_a_boundary_has_other_exits():
    payload = json.loads(json.dumps(load_registered_network("tagum_site_b").payload))
    payload["prohibited_turns"] = [["road6r", "road2f"], ["road3f", "road6f"]]
    result = validate(payload)
    assert not result["structurally_valid"]
    assert any(issue["code"] == "study_unreachable_from_boundary" and issue["node_id"] == "boundary_6" for issue in result["issues"])
    assert any(issue["code"] == "boundary_unreachable_from_study" and issue["node_id"] == "boundary_6" for issue in result["issues"])
    assert not any(issue["code"] == "boundary_no_exit" and issue["node_id"] == "boundary_6" for issue in result["issues"])


def test_split_operation_round_trips_with_native_routing_and_restrictions():
    from simulation.road_network import RoadNetwork
    payload = junction_network().payload
    payload["prohibited_turns"] = [["wf", "er"], ["nf", "wr"]]
    script = "import {splitRoadAtLongestMidpoint as split} from './tools/road_editor/topology.js'; let s=''; for await(const c of process.stdin)s+=c; console.log(JSON.stringify(split(JSON.parse(s),'w')))"
    process = subprocess.run(["node", "--input-type=module", "-e", script], input=json.dumps(payload), text=True, capture_output=True, check=True)
    result = json.loads(process.stdout)
    network = RoadNetwork(result["network"])
    assert network.nodes[result["nodeId"]]["default_control_mode"] == "first_come"
    assert (result["newRoadId"] + "f", "er") in network.prohibited_turns
    assert ("nf", result["newRoadId"] + "r") in network.prohibited_turns
    assert network.route("w", "e") == []
    assert network.route("n", "w") == []
    assert network.route("w", "s")


def test_connect_crossing_creates_native_routes_at_no_signal_junction():
    from simulation.road_network import RoadNetwork
    payload = {"id": "synthetic-crossing", "source": "test", "nodes": [
        {"id": "w", "x": -100, "y": 0, "boundary": True}, {"id": "e", "x": 100, "y": 0, "boundary": True},
        {"id": "s", "x": 0, "y": -100, "boundary": True}, {"id": "n", "x": 0, "y": 100, "boundary": True}],
        "roads": [{"id": "ew", "source": "w", "target": "e", "shape": [[-100, 0], [100, 0]], "oneway": False},
                  {"id": "ns", "source": "s", "target": "n", "shape": [[0, -100], [0, 100]], "oneway": False}]}
    script = "import {connectCrossing as connect} from './tools/road_editor/topology.js'; let s=''; for await(const c of process.stdin)s+=c; console.log(JSON.stringify(connect(JSON.parse(s),'ew','ns')))"
    process = subprocess.run(["node", "--input-type=module", "-e", script], input=json.dumps(payload), text=True, capture_output=True, check=True)
    result = json.loads(process.stdout)
    network = RoadNetwork(result["network"])
    assert network.nodes[result["nodeId"]]["default_control_mode"] == "first_come"
    assert len(network.incoming[result["nodeId"]]) == 4
    assert network.route("w", "e") and network.route("w", "n")


def test_turn_editor_matches_native_turns_and_routes():
    from simulation.road_network import RoadNetwork
    payload = junction_network().payload
    script = "import {setMovementAllowed as set} from './tools/road_editor/topology.js'; let s=''; for await(const c of process.stdin)s+=c; console.log(JSON.stringify(set(JSON.parse(s),'j','wf','er',false)))"
    process = subprocess.run(["node", "--input-type=module", "-e", script], input=json.dumps(payload), text=True, capture_output=True, check=True)
    edited = RoadNetwork(json.loads(process.stdout))
    assert not edited.turn_allowed("wf", "er")
    assert not edited.route("w", "e")
    assert edited.route("w", "n")


def test_island_near_connector_is_flagged_even_outside_road_lane():
    network = junction_network()
    payload = network.payload
    connector = network.connector("wf", "er")
    x, y = connector[len(connector) // 2]
    payload["islands"] = [{"id": "connector-island", "shape": [[x-.3, y-.3], [x+.3, y-.3], [x+.3, y+.3], [x-.3, y+.3]]}]
    result = validate(payload)
    assert any(issue["code"] == "island_connector_envelope" and issue["incoming_lane_id"] == "wf"
               and issue["outgoing_lane_id"] == "er" for issue in result["issues"])
    assert not result["clearance_checked"]


def test_invalid_draft_and_project_revision(tmp_path):
    network = json.loads(json.dumps(load_registered_network("tagum_site_b").payload))
    network["roads"][0]["shape"][1] = network["roads"][0]["shape"][0]
    assert not validate(network)["structurally_valid"]
    store = ProjectStore(tmp_path)
    saved = store.save({"name": "Draft", "network": network})
    assert store.read(saved["id"])["network"] == network
    next_revision = store.save(saved, expected=1)
    assert next_revision["revision"] == 2
    with pytest.raises(ValueError, match="another window"):
        store.save(saved, expected=1)
    with pytest.raises(ValueError, match="Invalid project"):
        store.read("../outside")
    store.recovery({"network": network, "project": saved})
    assert store.recovery()["network"] == network
    assert len(store.list()) == 1
    store.recovery(clear=True)
    assert store.recovery() is None
    assert store.read(saved["id"])["revision"] == 2


def test_loopback_security_and_export_refusal(tmp_path, monkeypatch):
    monkeypatch.setattr("tools.road_editor.server.sampled_island_review", lambda network: {"fingerprint": "reviewed", "sampled_sweeps": 0, "conflicts": []})
    monkeypatch.setattr("tools.road_editor.server.sampled_lane_review", lambda network: {"fingerprint": "lane-review", "sampled_positions": 0, "conflicts": []})
    server = make_server(tmp_path)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    base = f"http://127.0.0.1:{server.server_port}"
    try:
        with urllib.request.urlopen(base + "/") as response:
            html = response.read().decode()
        token = re.search(r'name="editor-token" content="([^"]+)"', html).group(1)
        payload = json.dumps({"network": load_registered_network("tagum_site_b").payload}).encode()
        def post(path, headers):
            req = urllib.request.Request(base + path, data=payload, headers=headers, method="POST")
            return urllib.request.urlopen(req)
        with pytest.raises(urllib.error.HTTPError) as rejected:
            post("/api/validate", {"X-Editor-Token": "wrong"})
        assert rejected.value.code == 400
        with pytest.raises(urllib.error.HTTPError):
            post("/api/sampled-island-review", {"X-Editor-Token": "wrong"})
        with pytest.raises(urllib.error.HTTPError):
            post("/api/sampled-lane-review", {"X-Editor-Token": "wrong"})
        with pytest.raises(urllib.error.HTTPError) as cross_origin:
            post("/api/validate", {"X-Editor-Token": token, "Origin": "http://example.com"})
        assert cross_origin.value.code == 400
        with post("/api/validate", {"X-Editor-Token": token}) as response:
            assert json.load(response)["structurally_valid"]
        with post("/api/sampled-island-review", {"X-Editor-Token": token}) as response:
            assert json.load(response)["fingerprint"] == "reviewed"
        with post("/api/sampled-lane-review", {"X-Editor-Token": token}) as response:
            assert json.load(response)["fingerprint"] == "lane-review"
        with pytest.raises(urllib.error.HTTPError) as refused:
            post("/api/export", {"X-Editor-Token": token})
        assert refused.value.code == 422
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)
