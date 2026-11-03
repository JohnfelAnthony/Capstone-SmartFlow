"""Each road direction gets a width and lane count from map data."""
import json
import math
import unittest
from pathlib import Path

from simulation.road_network import (JUNCTION_CLEARANCE_M, RoadNetwork, clip, distance, lanes_per_direction, length, widest_arc, offset,
                                     width_per_direction)
from tests.mixed_traffic_helpers import junction_network

NETWORK_5J = Path(__file__).resolve().parents[1]/"data"/"networks"/"tagum_network.json"


def road(tag, oneway=False, width=None):
    result = {"id": "r", "oneway": oneway, "osm_tags": {} if tag is None else {"lanes": tag}}
    if width is not None:
        result["width_per_direction_m"] = width
    return result


class RoadWidthTests(unittest.TestCase):
    def test_lane_count_comes_from_the_osm_lanes_tag(self):
        self.assertEqual((lanes_per_direction(road("4")), lanes_per_direction(road("2")), lanes_per_direction(road("2", oneway=True)),
                          lanes_per_direction(road(None))), (2, 1, 2, 1))

    def test_unusual_lane_tags_fall_back_safely(self):
        self.assertEqual([lanes_per_direction(road(tag)) for tag in ("2;3", "", "abc", "1.5", "0", " 4 ")], [1, 1, 1, 1, 1, 2])

    def test_width_is_lane_count_times_3_3_unless_a_field_width_is_given(self):
        self.assertAlmostEqual(width_per_direction(road("4")), 6.6)
        self.assertEqual(width_per_direction(road("2", width=5.0)), 5.0)

    def test_out_of_range_field_width_is_rejected(self):
        for bad in (1.0, 20.0, "wide", float("nan")):
            with self.assertRaisesRegex(ValueError, "width_per_direction_m"):
                width_per_direction(road("2", width=bad))

    def test_lane_centre_line_sits_half_the_width_from_the_road_centre(self):
        for tag, expected_y in (("4", -3.3), ("2", -1.65)):
            lane = junction_network(lanes_tag=tag).lanes["wf"]
            self.assertTrue(all(math.isclose(y, expected_y, abs_tol=1e-9) for _, y in lane.shape), (tag, lane.shape))

    def test_wide_crossing_roads_push_the_stop_line_back(self):
        network = junction_network(arm_widths={"n": 12.0, "s": 12.0})
        self.assertAlmostEqual(network.lanes["wf"].shape[-1][0], -13.5)

    def test_a_junction_can_set_its_own_stop_line_setback(self):
        payload = junction_network(lanes_tag="4").payload
        payload["nodes"][0]["junction_clearance_m"] = 22.0
        network = RoadNetwork(payload)
        self.assertAlmostEqual(network.lanes["wf"].shape[-1][0], -22.0)
        self.assertAlmostEqual(network.lanes["ef"].shape[-1][0], 22.0)

    def test_out_of_range_junction_setback_is_rejected(self):
        for bad in (2.0, 41.0, "far", True):
            payload = junction_network().payload
            payload["nodes"][0]["junction_clearance_m"] = bad
            with self.assertRaisesRegex(ValueError, "junction_clearance_m"):
                RoadNetwork(payload)

    def test_a_setback_junction_holds_its_turn_line_longer(self):
        plain = junction_network(lanes_tag="4")
        payload = junction_network(lanes_tag="4").payload
        payload["nodes"][0]["junction_clearance_m"] = 22.0
        wide = RoadNetwork(payload)
        # A right-angle turn: how far has the path curved by a third of the way along?
        def drift(network):
            path = network.connector("wf", "nr")
            return abs(path[7][1]-path[0][1])/abs(path[-1][1]-path[0][1])
        self.assertLess(drift(wide), drift(plain))

    def test_a_sharp_turn_takes_the_widest_arc_that_fits(self):
        # 135 degrees left round a corner 20 m ahead of the lane end and 15 m before the exit lane starts.
        turn = math.radians(135)
        corner = (20.0, 0.0)
        exit_start = (corner[0]+15*math.cos(turn), corner[1]+15*math.sin(turn))
        path = widest_arc((0.0, 0.0), 0.0, exit_start, turn)
        radius = 15/math.tan(turn/2)
        centre = (5.0, radius)
        self.assertEqual(tuple(path[0]), (0.0, 0.0))
        self.assertAlmostEqual(path[1][0], 5.0)
        self.assertAlmostEqual(path[1][1], 0.0)
        self.assertAlmostEqual(path[-1][0], exit_start[0])
        self.assertAlmostEqual(path[-1][1], exit_start[1])
        for point in path[1:]:
            self.assertAlmostEqual(distance(point, centre), radius, delta=.01*radius)

    def test_only_a_sharp_turn_whose_lines_meet_takes_an_arc(self):
        self.assertIsNone(widest_arc((0.0, 0.0), 0.0, (20.0, 20.0), math.radians(90)))
        self.assertIsNone(widest_arc((0.0, 0.0), 0.0, (-20.0, 5.0), math.radians(135)))

    def test_a_setback_junction_keeps_a_straight_path_straight(self):
        payload = junction_network(lanes_tag="4").payload
        payload["nodes"][0]["junction_clearance_m"] = 22.0
        path = RoadNetwork(payload).connector("wf", "er")
        self.assertTrue(all(abs(point[1]-path[0][1]) < 1e-6 for point in path))

    def test_networks_without_a_setback_keep_their_turn_paths(self):
        network = junction_network(lanes_tag="4")
        path = network.connector("wf", "nr")
        a, b = path[0], path[-1]
        limit = min(10.0, distance(a, b)*.65)
        t = .5
        expected_x = (1-t)**3*a[0]+3*(1-t)**2*t*(a[0]+limit)+3*(1-t)*t*t*b[0]+t**3*b[0]
        self.assertAlmostEqual(path[10][0], expected_x)

    def test_site_features_are_validated_and_reach_the_visual_payload(self):
        payload = junction_network().payload
        payload["site_features"] = [{"id": "lot", "kind": "concrete", "shape": [[0, 40], [10, 40], [10, 50]]}]
        visual = RoadNetwork(payload).visual()
        self.assertEqual(visual["site_features"][0]["shape"][1], {"x": 10, "y": 40})
        for bad in ({"id": "", "kind": "concrete", "shape": [[0, 0], [1, 1]]}, {"id": "x", "kind": "spaceship", "shape": [[0, 0], [1, 1]]},
                    {"id": "x", "kind": "concrete", "shape": [[0, 0]]}, {"id": "x", "kind": "concrete", "shape": [[0, 0], [1, float("nan")]]}):
            payload["site_features"] = [bad]
            with self.assertRaises(ValueError):
                RoadNetwork(payload)

    def test_pedestrians_can_follow_an_explicit_crossing(self):
        from tests.mixed_traffic_helpers import started_engine
        payload = junction_network().payload
        payload["nodes"][0]["pedestrian_crossing"] = [[30.0, 10.0], [30.0, -10.0]]
        engine = started_engine(RoadNetwork(payload))
        self.assertEqual(engine.pedestrian_paths()[0]["shape"], [{"x": 30.0, "y": 10.0}, {"x": 30.0, "y": -10.0}])

    def test_clipping_to_the_full_length_never_repeats_the_last_point(self):
        # A repeated point has no direction, so offsetting the lane would throw its end sideways.
        shape = [(0.1*index, 0.3*index) for index in range(40)]
        clipped = clip(shape, 1.0, length(shape)+1e-9)
        self.assertNotEqual(clipped[-1], clipped[-2])
        self.assertEqual(clipped[-1], shape[-1])

    def test_existing_networks_only_change_their_four_lane_roads(self):
        payload = json.loads(NETWORK_5J.read_text(encoding="utf-8"))
        network = RoadNetwork(payload)
        roads = {item["id"]: item for item in payload["roads"]}
        for lane in network.lanes.values():
            tag = roads[lane.id[:-1]]["osm_tags"]["lanes"]
            if tag == "4":
                self.assertEqual((round(lane.width, 9), lane.lane_count), (6.6, 2))
                continue
            self.assertEqual((lane.width, lane.lane_count), (3.3, 1))
            shape = [tuple(point) for point in roads[lane.id[:-1]]["shape"]]
            if lane.id.endswith("r"):
                shape.reverse()
            start = 0 if network.nodes[lane.source].get("boundary") else 9
            end = length(shape) if network.nodes[lane.target].get("boundary") else length(shape)-9
            self.assertEqual(lane.shape, offset(clip(shape, start, end), 1.65))

    def test_visual_payload_reports_real_width_and_stop_line_length(self):
        network = RoadNetwork(json.loads(NETWORK_5J.read_text(encoding="utf-8")))
        visual = network.visual()
        for item in visual["roads"]:
            for lane_visual in item["lanes"]:
                lane = network.lanes[lane_visual["id"]]
                self.assertEqual((lane_visual["width"], lane_visual["lane_count"]), (lane.width, lane.lane_count))
        for group in visual["signal_groups"]:
            a, b = ((point["x"], point["y"]) for point in group["stop_line"])
            self.assertAlmostEqual(distance(a, b), network.lanes[group["lane_id"]].width)
            self.assertEqual(group["width"], network.lanes[group["lane_id"]].width)

    def test_junction_clearance_keeps_its_nine_metre_minimum(self):
        self.assertEqual(JUNCTION_CLEARANCE_M, 9.0)


if __name__ == "__main__":
    unittest.main()
