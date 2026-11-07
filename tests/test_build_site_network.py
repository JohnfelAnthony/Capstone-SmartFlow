"""Single-junction site networks built from an OpenStreetMap extract."""
import json
import math
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from simulation.road_network import RoadNetwork, length
from tools.build_study_network import build_site_network

ROOT = Path(__file__).resolve().parents[1]
TOOL = ROOT / "tools" / "build_study_network.py"
LAT0, LON0 = 7.46, 125.80
CENTRE = (LAT0, LON0)
EAST_WAY, DAO_WAY = 102, 732013634


def lat_lon(x, y):
    return LAT0 + y / 111320, LON0 + x / (111320 * math.cos(math.radians(LAT0)))


class Extract:
    """Build a tiny OSM JSON payload from metric points (x east, y north) around the centre."""

    def __init__(self):
        self.nodes, self.ways = {}, []

    def node(self, node_id, x, y):
        self.nodes[node_id] = lat_lon(x, y)
        return node_id

    def way(self, way_id, nodes, **tags):
        self.ways.append({"type": "way", "id": way_id, "nodes": nodes, "tags": tags})

    def save(self, folder):
        elements = [{"type": "node", "id": node_id, "lat": lat, "lon": lon} for node_id, (lat, lon) in self.nodes.items()]
        payload = {"elements": elements + self.ways,
                   "smartflow_source": {"provider": "OpenStreetMap", "license": "ODbL-1.0", "bbox": [7.455, 125.795, 7.465, 125.805]}}
        path = Path(folder) / "osm.json"
        path.write_text(json.dumps(payload), encoding="utf-8")
        return path


def cross(east_crossing_at=None):
    """A secondary cross with 300 m arms; a residential street joins the north arm 48 m out."""
    osm = Extract()
    osm.node(1, 0, 0)
    for node_id, (x, y) in {10: (0, 300), 20: (300, 0), 30: (0, -300), 40: (-300, 0)}.items():
        osm.node(node_id, x, y)
    osm.node(11, 0, 48)
    osm.node(12, -60, 48)
    osm.way(101, [1, 11, 10], highway="secondary", name="Dalisay Gante Road", lanes="4")
    osm.way(103, [1, 30], highway="secondary", name="Dalisay Gante Road", lanes="4")
    osm.way(104, [1, 40], highway="secondary", name="Capitol Circumferential Road", lanes="4")
    osm.way(105, [11, 12], highway="residential", name="Side Street")
    if east_crossing_at is None:
        osm.way(EAST_WAY, [1, 20], highway="secondary", name="Capitol Circumferential Road", lanes="4")
    else:
        osm.node(21, east_crossing_at, 0)
        osm.node(22, east_crossing_at, 150)
        osm.node(23, east_crossing_at, -150)
        osm.way(EAST_WAY, [1, 21, 20], highway="secondary", name="Capitol Circumferential Road", lanes="4")
        osm.way(106, [22, 21, 23], highway="tertiary", name="Gazmen Road")
    return osm


def split_highway():
    """Site B's shape: two one-way carriageways 9 m apart, a median link, a street on each side."""
    osm = Extract()
    osm.node(1, -4.5, 0)
    osm.node(2, 4.5, 0)
    for node_id, (x, y) in {10: (-4.5, 300), 11: (-4.5, -300), 20: (4.5, -300), 21: (4.5, 300), 30: (-300, 0), 40: (300, 0)}.items():
        osm.node(node_id, x, y)
    osm.way(201, [10, 1], highway="trunk", name="Davao-Agusan National Highway", oneway="yes", lanes="3")
    osm.way(202, [1, 11], highway="trunk", name="Davao-Agusan National Highway", oneway="yes", lanes="3")
    osm.way(203, [20, 2], highway="trunk", name="Davao-Agusan National Highway", oneway="yes", lanes="3")
    osm.way(204, [2, 21], highway="trunk", name="Davao-Agusan National Highway", oneway="yes", lanes="3")
    osm.way(205, [1, 2], highway="secondary", lanes="2")
    osm.way(206, [1, 30], highway="secondary", name="Sobrecarey Street", lanes="4")
    osm.way(DAO_WAY, [2, 40], highway="tertiary", name="Dao Street", lanes="2")
    return osm


class SiteNetworkTests(unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.TemporaryDirectory()
        self.addCleanup(self.folder.cleanup)

    def build(self, osm, **options):
        return build_site_network(osm.save(self.folder.name), CENTRE, network_id=options.pop("network_id", "site_test"),
                                  name="Test", **options)

    def test_a_cross_with_a_side_street_keeps_all_four_legs(self):
        payload = self.build(cross())
        network = RoadNetwork(payload)
        self.assertEqual(len(network.intersections), 1)
        self.assertEqual(len(network.incoming[network.intersections[0]]), 4)
        self.assertTrue(all(length(road["shape"]) >= 240 for road in payload["roads"]))

    def test_split_highway_points_join_into_one_junction(self):
        network = RoadNetwork(self.build(split_highway(), network_id="site_b_test"))
        self.assertEqual(len(network.intersections), 1)
        self.assertEqual(len(network.incoming[network.intersections[0]]), 4)
        self.assertEqual(len(network.payload["roads"]), 6)

    def test_a_leg_stops_10_m_before_the_next_major_junction(self):
        payload = self.build(cross(east_crossing_at=120))
        east = next(road for road in payload["roads"] if road["osm_way_id"] == EAST_WAY)
        self.assertAlmostEqual(length(east["shape"]), 110.0, delta=0.5)

    def test_unnamed_major_crossing_still_stops_the_leg(self):
        osm = cross(east_crossing_at=120)
        for way in osm.ways:
            if way["id"] in {EAST_WAY, 106}:
                way["tags"].pop("name", None)
        payload = self.build(osm)
        east = next(road for road in payload["roads"] if road["osm_way_id"] == EAST_WAY)
        self.assertAlmostEqual(length(east["shape"]), 110.0, delta=0.5)

    def test_a_leg_shorter_than_30_m_is_refused_by_name(self):
        with self.assertRaisesRegex(ValueError, r"Leg along Dao Street \(way 732013634\) is only 20.0 m"):
            self.build(split_highway(), approach_overrides_m={str(DAO_WAY): 20})

    def test_the_network_has_the_requested_id_and_assumptions(self):
        payload = self.build(cross())
        self.assertEqual(payload["id"], "site_test")
        self.assertIn("No traffic signal exists today; signal plans are proposals", payload["source"]["assumptions"])

    def test_output_is_required_on_the_command_line(self):
        source = cross().save(self.folder.name)
        result = subprocess.run([sys.executable, str(TOOL), "--site", "7.46,125.80", "--network-id", "x", "--name", "x",
                                 "--source", str(source)], capture_output=True, cwd=ROOT)
        self.assertEqual(result.returncode, 2)


if __name__ == "__main__":
    unittest.main()



class JunctionMouthTests(unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.TemporaryDirectory()
        self.addCleanup(self.folder.cleanup)

    def build(self, osm):
        return build_site_network(osm.save(self.folder.name), CENTRE, network_id="site_test", name="Test")

    def test_a_kink_near_the_junction_is_drawn_straight_for_the_first_30_m(self):
        # OSM vertex jitter 20 m out bends the leg 20 degrees; opposing lanes on either side of such a kink cross and vehicles overlap.
        osm = cross()
        osm.node(2, 6, 20)
        osm.ways[0]["nodes"] = [1, 2, 11, 10]
        payload = self.build(osm)
        north = next(road for road in payload["roads"] if road["osm_way_id"] == 101)
        self.assertGreaterEqual(math.dist(north["shape"][0], north["shape"][1]), 30.0)
        self.assertIn("first 30 m of every leg", " ".join(payload["source"]["assumptions"]))

    def test_a_leg_without_a_nearby_vertex_keeps_its_shape(self):
        payload = self.build(cross())
        east = next(road for road in payload["roads"] if road["osm_way_id"] == EAST_WAY)
        self.assertEqual(len(east["shape"]), 2)
        self.assertAlmostEqual(length(east["shape"]), 250.0, delta=0.5)


class LegSimplificationTests(JunctionMouthTests):
    def wobbly(self, offset):
        osm = cross()
        osm.node(3, 2.0, 80)
        osm.node(4, offset, 160)
        osm.ways[0]["nodes"] = [1, 11, 3, 4, 10]
        return self.build(osm)

    def test_map_wobble_under_5_m_is_drawn_straight(self):
        north = next(road for road in self.wobbly(3.0)["roads"] if road["osm_way_id"] == 101)
        self.assertEqual(len(north["shape"]), 2)
        self.assertIn("5 m", " ".join(self.wobbly(3.0)["source"]["assumptions"]))

    def test_a_real_bend_keeps_its_shape(self):
        north = next(road for road in self.wobbly(12.0)["roads"] if road["osm_way_id"] == 101)
        self.assertGreater(len(north["shape"]), 2)


class SiteALoopTests(unittest.TestCase):
    """Site A before the street grid (kept under history): the single-junction network plus the West-North side-street loop, reproducible."""

    SOURCE = ROOT / "data" / "networks" / "osm_site_a.json"
    NETWORKS = ROOT / "data" / "networks"

    def build(self, **options):
        from tools.build_study_network import build_site_a_network
        return build_site_a_network(self.SOURCE, **options)

    def test_generator_reproduces_the_kept_loop_network(self):
        kept = json.loads((self.NETWORKS / "tagum_site_a_loop.json").read_text(encoding="utf-8"))
        self.assertEqual(self.build(), kept)

    def test_generator_reproduces_the_kept_single_junction_network(self):
        kept = json.loads((self.NETWORKS / "history" / "tagum_site_a_single_junction.json").read_text(encoding="utf-8"))
        self.assertEqual(self.build(with_loop=False), kept)

    def test_loop_adds_two_first_come_junctions_and_keeps_the_study_junction_first(self):
        payload = self.build()
        network = RoadNetwork(payload)
        self.assertEqual(network.intersections, ["tagum_site_a_j", "tagum_site_a_j2", "tagum_site_a_j3"])
        modes = {node["id"]: node.get("default_control_mode") for node in payload["nodes"] if not node["boundary"]}
        self.assertEqual(modes, {"tagum_site_a_j": None, "tagum_site_a_j2": "first_come", "tagum_site_a_j3": "first_come"})
        self.assertEqual([road["id"] for road in payload["roads"][:4]], ["road0", "road1", "road2", "road3"])

    def test_loop_street_is_about_275_metres_and_labelled_provisional(self):
        payload = self.build()
        loop = next(road for road in payload["roads"] if road["name"] == "Unnamed side street")
        self.assertAlmostEqual(length(loop["shape"]), 275.0, delta=30)
        assumptions = " ".join(payload["source"]["assumptions"])
        for phrase in ("provisional", "not field-checked", "start empty", "no traffic was observed"):
            self.assertIn(phrase, assumptions)

    def test_loop_end_off_the_drawn_leg_is_refused(self):
        from tools.build_study_network import build_site_network, SITE_A_CENTRE
        loop = {"name": "x", "osm_nodes": [1387566813, 1527791811]}
        with self.assertRaises(ValueError):
            build_site_network(self.SOURCE, SITE_A_CENTRE, network_id="tagum_site_a", name="x", detour_loops=[loop])


class SiteAStreetGridTests(unittest.TestCase):
    """Site A as installed: every public street in the owner's crop, with the owner's three choices of 7 November."""

    SOURCE = ROOT / "data" / "networks" / "osm_site_a.json"

    @classmethod
    def setUpClass(cls):
        from tools.build_study_network import build_site_a_street_grid
        cls.payload = build_site_a_street_grid(cls.SOURCE)
        cls.network = RoadNetwork(cls.payload)

    def test_generator_reproduces_the_installed_network(self):
        installed = json.loads((ROOT / "data" / "networks" / "tagum_site_a.json").read_text(encoding="utf-8"))
        self.assertEqual(self.payload, installed)

    def test_site_a_stays_first_and_the_only_junction_without_first_come(self):
        self.assertEqual(self.network.intersections[0], "tagum_site_a_j")
        modes = {node["id"]: node.get("default_control_mode") for node in self.payload["nodes"] if not node["boundary"]}
        self.assertIsNone(modes.pop("tagum_site_a_j"))
        self.assertEqual(set(modes.values()), {"first_come"})
        self.assertIn("tagum_site_a_j2", modes); self.assertIn("tagum_site_a_j3", modes)

    def test_main_roads_keep_their_ids_names_and_the_west_approach_length(self):
        roads = {road["id"]: road for road in self.payload["roads"]}
        expected = {"road0": ("tagum_site_a_j", "Dalisay Gante Road"), "road1": ("tagum_site_a_j", "Dalisay Gante Road"),
                    "road2": ("tagum_site_a_j", "Capitol Circumferential Road"), "road3": ("tagum_site_a_j", "Capitol Circumferential Road"),
                    "road4": ("tagum_site_a_j2", "Capitol Circumferential Road"), "road5": ("tagum_site_a_j3", "Dalisay Gante Road")}
        for road_id, (source, name) in expected.items():
            self.assertEqual((roads[road_id]["source"], roads[road_id]["name"]), (source, name))
        self.assertEqual((roads["road2"]["target"], roads["road1"]["target"]), ("tagum_site_a_j2", "tagum_site_a_j3"))
        # Owner: the 48 m street west of Site A is left out, so the west approach still reaches j2, 226 m out.
        self.assertAlmostEqual(length(roads["road2"]["shape"]), 226.0, delta=1)
        self.assertFalse(any(761662360 == road["osm_way_id"] for road in self.payload["roads"]))

    def test_new_roads_are_unnamed_side_streets(self):
        main = {"Capitol Circumferential Road", "Dalisay Gante Road"}
        for road in self.payload["roads"]:
            self.assertEqual(road["name"] in main, not road.get("minor", False), road["id"])
            if road["name"] not in main:
                self.assertEqual(road["name"], "Unnamed road")

    def test_only_the_four_main_road_ends_and_the_study_junction_take_generated_demand(self):
        self.assertEqual(self.network.demand_boundaries, ["boundary_0", "boundary_1", "boundary_2", "boundary_3"])
        self.assertEqual(self.network.pedestrian_junctions, ["tagum_site_a_j"])  # owner's decision: pedestrians cross only at Site A
        self.assertGreater(len(self.network.boundaries), 4)

    def test_every_main_road_trip_goes_through_site_a_unless_a_closure_forces_a_detour(self):
        ends = self.network.demand_boundaries
        congested = {
            lane.id: lane.length / lane.speed + (0 if lane.minor else 200)
            for lane in self.network.lanes.values()
        }
        for costs in (None, congested):
            for source in ends:
                for target in ends:
                    if source == target:
                        continue
                    route = self.network.route(source, target, costs=costs)
                    self.assertTrue(route)
                    self.assertFalse(any(self.network.lanes[lane].minor for lane in route))
                    self.assertIn("tagum_site_a_j", [self.network.lanes[lane].target for lane in route])
        detour = self.network.route("boundary_2", "boundary_1", closed={"road2r"}, costs=congested)
        self.assertTrue(detour)
        self.assertTrue(any(self.network.lanes[lane].minor for lane in detour))

    def test_scheduled_pedestrians_and_published_paths_use_only_the_study_junction(self):
        from simulation.traffic_engine import TrafficEngine

        engine = TrafficEngine(network=self.network)
        for junction in self.network.intersections[1:]:
            with self.subTest(junction=junction), self.assertRaisesRegex(ValueError, "Pedestrian crossings are disabled"):
                engine.configure(pedestrian_trips=[{"time": 1, "junction": junction}])

        engine.configure(pedestrian_trips=[{"time": 1, "junction": "tagum_site_a_j"}])
        self.assertEqual([path["junction_id"] for path in engine.pedestrian_paths()], ["tagum_site_a_j"])

    def test_the_market_is_drawn_and_labelled(self):
        features = self.payload["site_features"]
        self.assertEqual([f["label"] for f in features if f.get("label")], ["Tagum Public Market"])
        self.assertEqual(sum(1 for f in features if f["kind"] == "building"), 11)
