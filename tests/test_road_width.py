"""Each road direction gets a width and lane count from map data."""
import json
import math
import unittest
from pathlib import Path

from simulation.road_network import (JUNCTION_CLEARANCE_M, RoadNetwork, clip, distance, lanes_per_direction, length, offset,
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
