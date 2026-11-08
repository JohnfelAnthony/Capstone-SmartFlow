"""Site B rebuilt to the owner's overhead imagery: physically separated carriageways and barrier-respecting turn paths."""
import json
import math
from pathlib import Path

import pytest

from simulation.footprints import overlapping_pairs, rectangle
from simulation.mixed_traffic import lateral_bounds
from simulation.road_network import RoadNetwork, clip, distance, length, sample
from simulation.scenario_config import VEHICLE_TYPES
from simulation.traffic_engine import TrafficEngine
from tools.mixed_traffic_report import build_engine, case_options, count_island_intrusions, polygons_touch_or_overlap
from tools.site_b_measured_layout import CARRIAGEWAY_WIDTH_M, MEDIAN_WIDTH_M, build_measured_site_b

ROOT = Path(__file__).resolve().parents[1]/"data"/"networks"
INSTALLED = json.loads((ROOT/"tagum_site_b.json").read_text(encoding="utf-8"))
MEASURED = json.loads((ROOT/"tagum_site_b_pre_street_grid.json").read_text(encoding="utf-8"))  # the measured core on its own: the installed Site B before the street grid (D46)
CORRIDOR = json.loads((ROOT/"history"/"tagum_site_b_osm_corridor.json").read_text(encoding="utf-8"))
NETWORK = RoadNetwork(INSTALLED)
STUDY, NEIGHBOR = NETWORK.intersections[:2]
HIGHWAY = {"road2", "road3", "road4", "road5", "road8", "road9"}


def to_boundary(network, route, vehicle_type=None):
    """The route continued by the cheapest way on to a boundary, for tests that place a vehicle on a turn at a junction that no longer ends at one."""
    return route + network.route(network.lanes[route[-1]].target, set(network.boundaries), previous=route[-1], vehicle_type=vehicle_type)


def along_across(point):
    """Metres along the highway from the study junction, and across it toward the north-west."""
    start, end = NETWORK.nodes[STUDY], NETWORK.nodes[NEIGHBOR]
    span = distance((start["x"], start["y"]), (end["x"], end["y"]))
    ux, uy = (end["x"]-start["x"])/span, (end["y"]-start["y"])/span
    dx, dy = point[0]-start["x"], point[1]-start["y"]
    return dx*ux+dy*uy, -dx*uy+dy*ux


def distance_to_polygon(point, polygon):
    best = math.inf
    for a, b in zip(polygon, polygon[1:]+polygon[:1]):
        dx, dy = b[0]-a[0], b[1]-a[1]
        t = max(0, min(1, ((point[0]-a[0])*dx+(point[1]-a[1])*dy)/(dx*dx+dy*dy or 1)))
        best = min(best, math.hypot(point[0]-a[0]-t*dx, point[1]-a[1]-t*dy))
    return best


def test_generator_reproduces_the_measured_core():
    assert build_measured_site_b(CORRIDOR) == MEASURED


def test_ids_and_control_are_preserved_from_the_corridor():
    assert [node["id"] for node in MEASURED["nodes"]] == [node["id"] for node in CORRIDOR["nodes"]]
    assert [road["id"] for road in MEASURED["roads"]] == [road["id"] for road in CORRIDOR["roads"]]
    assert [node["id"] for node in INSTALLED["nodes"][:2]] == [node["id"] for node in CORRIDOR["nodes"][:2]]
    assert {road["id"] for road in CORRIDOR["roads"]} <= {road["id"] for road in INSTALLED["roads"]}
    assert NETWORK.nodes[NEIGHBOR]["default_control_mode"] == "first_come"
    assert NETWORK.visual()["junctions"][0]["id"] == STUDY


def test_carriageways_are_separated_by_the_measured_median():
    for road in INSTALLED["roads"]:
        if road["id"] in HIGHWAY:
            assert road["width_per_direction_m"] == CARRIAGEWAY_WIDTH_M
    for lane_id, side in (("road2f", 1), ("road3f", -1), ("road4f", 1), ("road5f", -1), ("road8f", -1), ("road9f", 1)):
        for point in NETWORK.lanes[lane_id].shape:
            across = along_across(point)[1]*side
            assert across-CARRIAGEWAY_WIDTH_M/2 == pytest.approx(MEDIAN_WIDTH_M/2, abs=.01), lane_id


def test_stop_lines_sit_where_the_imagery_shows_them():
    assert along_across(NETWORK.lanes["road2f"].shape[-1])[0] == pytest.approx(21, abs=1.5)
    assert along_across(NETWORK.lanes["road5f"].shape[-1])[0] == pytest.approx(-21, abs=1.5)
    span = along_across((NETWORK.nodes[NEIGHBOR]["x"], NETWORK.nodes[NEIGHBOR]["y"]))[0]
    assert along_across(NETWORK.lanes["road3f"].shape[-1])[0]-span == pytest.approx(-28.5, abs=1.5)
    assert along_across(NETWORK.lanes["road9f"].shape[-1])[0]-span == pytest.approx(28.5, abs=1.5)


def test_lanes_never_touch_a_barrier():
    for lane in NETWORK.lanes.values():
        half = lane.width/2
        for a, b in zip(lane.shape, lane.shape[1:]):
            size = math.hypot(b[0]-a[0], b[1]-a[1]) or 1
            nx, ny = -(b[1]-a[1])/size*half, (b[0]-a[0])/size*half
            pavement = [(a[0]+nx, a[1]+ny), (b[0]+nx, b[1]+ny), (b[0]-nx, b[1]-ny), (a[0]-nx, a[1]-ny)]
            for island in NETWORK.islands:
                assert not polygons_touch_or_overlap(pavement, island["shape"]), (lane.id, island["id"])


def test_turn_connector_vertices_have_centerline_distance_from_barrier_edges():
    """This vertex-only check does not establish vehicle-body or continuous clearance."""
    half_bus_width = 1.3
    for node in NETWORK.intersections:
        for incoming in NETWORK.incoming[node]:
            for outgoing in NETWORK.outgoing[node]:
                if not NETWORK.turn_allowed(incoming, outgoing):
                    continue
                for point in NETWORK.connector(incoming, outgoing):
                    for island in NETWORK.islands:
                        assert distance_to_polygon(point, island["shape"]) >= half_bus_width, (incoming, outgoing, island["id"])


def test_no_actual_size_contacts_on_allowed_turns():
    """Check reachable entry offsets on both sides of each turn, including the designated kerb lane."""
    engine = TrafficEngine(network=NETWORK)
    islands = [(island, min(p[0] for p in island["shape"]), min(p[1] for p in island["shape"]), max(p[0] for p in island["shape"]), max(p[1] for p in island["shape"]))
               for island in NETWORK.islands]
    contacts = set()
    for kind, spec in VEHICLE_TYPES.items():
        for node in NETWORK.intersections:
            for incoming in NETWORK.incoming[node]:
                for outgoing in NETWORK.outgoing[node]:
                    if not NETWORK.turn_allowed(incoming, outgoing, vehicle_type=kind):
                        continue
                    connector = NETWORK.connector(incoming, outgoing)
                    total = length(connector)
                    low, high = lateral_bounds(NETWORK.lanes[incoming].width, spec["width"])
                    exit_low, exit_high = lateral_bounds(NETWORK.lanes[outgoing].width, spec["width"])
                    kerb = engine._entry_kerb_position(NETWORK.lanes[incoming], kind, spec["width"])
                    for entry in (low, 0.0, high) if kerb is None else (kerb,):
                        exit_lateral = min(exit_high, max(exit_low, entry))
                        for step in range(int(total/.2)+2):
                            at = min(total, step*.2)
                            x, y, heading = sample(connector, at)
                            lateral = entry+(exit_lateral-entry)*at/total
                            body = rectangle(x+math.sin(heading)*lateral, y-math.cos(heading)*lateral, heading, spec["length"], spec["width"])
                            xs, ys = [c[0] for c in body], [c[1] for c in body]
                            for island, left, bottom, right, top in islands:
                                if min(xs) <= right and left <= max(xs) and min(ys) <= top and bottom <= max(ys) and polygons_touch_or_overlap(body, island["shape"]):
                                    contacts.add((kind, incoming, outgoing, round(entry, 2), island["id"]))
    assert not contacts


def _net_reversal(connector, entry, exit_lateral):
    """Metres a lane position moves backward along the turn, comparing whole path segments so a polyline's corners do not count."""
    total, travelled, points = length(connector), 0.0, []
    for a, b in zip(connector, connector[1:]):
        segment = math.dist(a, b)
        heading = math.atan2(b[1]-a[1], b[0]-a[0])
        lateral = entry+(exit_lateral-entry)*(travelled+segment/2)/total
        points.append(((a[0]+b[0])/2+math.sin(heading)*lateral, (a[1]+b[1])/2-math.cos(heading)*lateral, heading))
        travelled += segment
    return sum(math.dist(p[:2], q[:2]) for p, q in zip(points, points[1:])
               if all((q[0]-p[0])*math.cos(heading)+(q[1]-p[1])*math.sin(heading) < 0 for heading in (p[2], q[2])))


@pytest.mark.parametrize("incoming,outgoing", [("road2f", "road1f"), ("road9f", "road7f")])
def test_no_lane_position_runs_backward_round_a_sharp_turn(incoming, outgoing):
    """On a too-tight path the inside of the wide lane folds back: the state that froze Site B for good (fixed-time, seed 102, 1505 s)."""
    connector = NETWORK.connector(incoming, outgoing)
    for spec in VEHICLE_TYPES.values():
        low, high = lateral_bounds(NETWORK.lanes[incoming].width, spec["width"])
        exit_low, exit_high = lateral_bounds(NETWORK.lanes[outgoing].width, spec["width"])
        for entry in (low, 0.0, high):
            assert _net_reversal(connector, entry, min(exit_high, max(exit_low, entry))) == 0


def _vehicle_turning_ahead_of_a_follower(engine, incoming, outgoing, entry, exit_lateral):
    leader = engine.add_vehicle(to_boundary(NETWORK, [incoming, outgoing]), vehicle_type="motorcycle")
    follower = engine.add_vehicle(to_boundary(NETWORK, [incoming, outgoing]), vehicle_type="motorcycle")
    connector = NETWORK.connector(incoming, outgoing)
    leader.position, leader.connector, leader.connector_position = NETWORK.lanes[incoming].length, connector, .9*length(connector)
    leader.connector_entry_lateral, leader.connector_exit_lateral = entry, exit_lateral
    follower.position = NETWORK.lanes[incoming].length-2
    engine._tick_index = None
    return leader, follower


def test_a_sharp_turn_goes_one_vehicle_at_a_time():
    engine = build_engine("siteB", "none", {"car": 1}, 120, 1)
    leader, follower = _vehicle_turning_ahead_of_a_follower(engine, "road2f", "road1f", 2.9, 2.9)
    assert engine._must_wait_at_line(follower)
    leader.connector, leader.route = None, to_boundary(NETWORK, ["road1f"])
    assert not engine._must_wait_at_line(follower)


def test_a_gentler_turn_still_takes_followers_in():
    engine = build_engine("siteB", "none", {"car": 1}, 120, 1)
    _, follower = _vehicle_turning_ahead_of_a_follower(engine, "road5f", "road0f", 2.9, 1.2)
    assert not engine._must_wait_at_line(follower)


@pytest.mark.parametrize("incoming,outgoing", [("road2f", "road1f"), ("road9f", "road7f")])
def test_crowded_sharp_turn_traffic_all_gets_through(incoming, outgoing):
    """A dense mixed stream of right-turners, the traffic that froze this turn, must drain with nobody left standing in the junction."""
    engine = build_engine("siteB", "none", {"car": 1}, 400, 1, no_signal=True)
    classes = ["motorcycle", "motorcycle", "tricycle", "car", "motorcycle", "motorcycle", "tricycle", "motorcycle"]
    added, longest_stop = 0, 0.0
    while engine.status == "running" and engine.simulation_time < 400:
        if added < 32 and engine.simulation_time >= added*1.2 and engine.add_vehicle(to_boundary(NETWORK, [incoming, outgoing]), vehicle_type=classes[added % len(classes)]):
            added += 1
        engine.step(1)
        longest_stop = max([longest_stop, *[vehicle.stopped_for for vehicle in engine.vehicles.values() if vehicle.reserved_junction]])
        if added == 32 and not engine.vehicles:
            break
    assert added == 32 and not engine.vehicles, f"{len(engine.vehicles)} left at {engine.simulation_time}s"
    assert longest_stop < 30


def test_side_roads_are_straight_past_the_junction():
    """Opposing bodies pivot into each other at any bend in a two-way road, and the imagery shows these roads straight."""
    for lane_id in ("road0f", "road0r", "road1f", "road1r", "road6f", "road6r", "road7f", "road7r"):
        shape = NETWORK.lanes[lane_id].shape
        if lane_id.startswith("road6"):  # Acacia now turns into the inner link, 163 m on; only its first 30 m by the junction are checked
            total = NETWORK.lanes[lane_id].length
            shape = clip(shape, 0, 30) if lane_id == "road6f" else clip(shape, total-30, total)
        headings = [math.atan2(b[1]-a[1], b[0]-a[0]) for a, b in zip(shape, shape[1:])]
        turns = [abs((second-first+math.pi) % (2*math.pi)-math.pi) for first, second in zip(headings, headings[1:])]
        assert math.degrees(max(turns, default=0)) < .01, lane_id


def test_median_openings_match_the_imagery():
    median_along = sorted((along_across(p)[0] for island in NETWORK.islands if island["id"].startswith("median") for p in island["shape"]))
    assert not [x for x in median_along if -17 < x < 14]
    assert any(-18 < x < -17 for x in median_along) and any(14 < x < 15 for x in median_along)


def test_site_features_reach_the_visual_payload():
    visual = NETWORK.visual()
    kinds = {feature["kind"] for feature in visual["site_features"]}
    assert {"concrete", "service_lane", "junction_pavement", "building", "shed", "marking", "street_light"} <= kinds
    labels = {feature.get("label") for feature in visual["site_features"]}
    assert {"Citi Hardware", "Jollibee"} <= labels
    assert all(isinstance(point, dict) for feature in visual["site_features"] for point in feature["shape"])


def test_provenance_says_the_sizes_are_estimates():
    text = " ".join(INSTALLED["source"]["assumptions"]).lower()
    assert "estimated" in text and "field" in text
    assert "no simulated traffic" in text


def test_pedestrians_walk_the_real_zebra():
    engine = build_engine("siteB", "none", {"car": 1}, 30, 101, no_signal=True)
    path = next(item for item in engine.pedestrian_paths() if item["junction_id"] == STUDY)["shape"]
    start, end = (path[0]["x"], path[0]["y"]), (path[1]["x"], path[1]["y"])
    assert along_across(start)[0] == pytest.approx(18.5, abs=.5) and along_across(end)[0] == pytest.approx(18.5, abs=.5)
    assert abs(along_across(start)[1]) == pytest.approx(10.15, abs=.5) and abs(along_across(end)[1]) == pytest.approx(10.15, abs=.5)


def _site_b_sweeps(engine):
    sweeps = []
    node = STUDY
    for incoming in NETWORK.incoming[node]:
        for outgoing in NETWORK.outgoing[node]:
            if NETWORK.turn_allowed(incoming, outgoing):
                sweeps.append(engine._build_sweep(incoming, outgoing, -.6, .4, 4.5, 1.8))
    return sweeps


def test_conflict_search_matches_the_plain_all_pairs_search():
    """The block prefilter is only a speed-up: it must find the same furthest conflict as comparing every pair of bodies."""
    from simulation.traffic_engine import _boxes_overlap, rectangles_overlap
    engine = build_engine("siteB", "none", {"car": 1}, 30, 101, no_signal=True)
    sweeps = _site_b_sweeps(engine)
    pairs = [(a, b) for index, a in enumerate(sweeps) for b in sweeps[index+1::3]]
    assert len(pairs) >= 20
    for own, other in pairs:
        plain = next((point for point, corners, box in reversed(other)
                      if any(_boxes_overlap(box, own_box) and rectangles_overlap(own_corners, corners) for _, own_corners, own_box in own)), None)
        assert engine._last_conflict_point(own, other) == plain


def test_sweep_caches_stay_bounded_without_changing_results(monkeypatch):
    import simulation.traffic_engine as traffic_engine
    monkeypatch.setattr(traffic_engine, "SWEEP_CACHE_LIMIT", 3)
    engine = build_engine("siteB", "none", {"car": 1}, 30, 101, no_signal=True)
    first = engine.add_vehicle(to_boundary(NETWORK, ["road2f", "road4f"]), vehicle_type="car")
    expected = engine._build_sweep("road2f", "road4f", first.lateral, engine._exit_lateral(first), first.length, first.width)
    for lateral in (-1.0, -.5, 0.0, .5, 1.0):
        sweep = engine._sweep_for(first, lateral, 0.0)
        engine._sweep_bounds(sweep)
        assert len(engine._sweep_cache) <= 3
    assert engine._sweep_for(first, first.lateral, engine._exit_lateral(first)) == expected
    assert len(engine._conflict_point_cache) <= 3 and len(engine._sweep_bounds_cache) <= 3


@pytest.mark.parametrize("seed", [101, 102])
def test_medium_no_signal_traffic_stays_on_the_road(seed):
    network, density, mix, options = case_options("siteB-medium-nosignal")
    engine = build_engine(network, density, mix, 90, seed, **options)
    while engine.status == "running":
        engine.step(1)
        records = engine.vehicle_records()
        assert not overlapping_pairs(records), f"overlap at {engine.simulation_time}s"
        assert not count_island_intrusions(records, engine.network.islands), f"island contact at {engine.simulation_time}s"
    assert engine._last_metrics["vehicle_conservation_error"] == 0


@pytest.mark.parametrize("kind", ["bus", "truck"])
def test_bonifacio_heavy_vehicle_completes_turn_with_opposing_traffic(kind):
    engine = build_engine("siteB", "none", {"car": 1}, 300, 101, no_signal=True)  # Bonifacio now runs 446 m on, so the vehicles need time to finish their routes
    heavy = engine.add_vehicle(to_boundary(NETWORK, ["road9f", "road7f"], kind), vehicle_type=kind, speed=3)
    heavy.position = engine.network.lanes["road9f"].length-12
    opposing = engine.add_vehicle(to_boundary(NETWORK, ["road7r", "road8f"]), speed=3)
    opposing.position = engine.network.lanes["road7r"].length-12
    while engine.status == "running":
        engine.step(1)
        records = engine.vehicle_records()
        assert not overlapping_pairs(records)
        assert not count_island_intrusions(records, engine.network.islands)
    assert engine.completed == 2
    assert engine._last_metrics["vehicle_conservation_error"] == 0
