"""Queue reach: how far back from the stop line the stopped queue extends, in metres."""
import json
import unittest
from pathlib import Path

from tests.mixed_traffic_helpers import hold_green, junction_network, place, started_engine

CATALOG = Path(__file__).resolve().parents[1]/"simulation"/"metric_definitions.json"
ROUTE = ["wf", "er"]


class QueueReachTests(unittest.TestCase):
    def red_engine(self, **network_options):
        engine = started_engine(junction_network(**network_options))
        hold_green(engine, "j", "north")
        return engine

    def test_single_file_queue_reach_is_the_rear_of_the_last_car(self):
        engine = self.red_engine()
        place(engine, ROUTE, "car", from_stop_line=0, lateral=-0.65)
        last = place(engine, ROUTE, "car", from_stop_line=6.5, lateral=-0.65)
        engine.step(20)
        lane = engine.network.lanes["wf"]
        self.assertAlmostEqual(engine._queue_reach("wf"), lane.length-(last.position-last.length/2))

    def test_side_by_side_queue_reaches_less_far(self):
        layouts = {"4": [(0.0, -2.3), (0.0, 1.0), (6.5, -2.3), (6.5, 1.0)],  # two abreast on 6.6 m
                   "2": [(0.0, -0.65), (6.5, -0.65), (13.0, -0.65), (19.5, -0.65)]}  # single file on 3.3 m
        reach = {}
        for tag, cars in layouts.items():
            engine = self.red_engine(lanes_tag=tag)
            for distance, lateral in cars:
                place(engine, ROUTE, "car", from_stop_line=distance, lateral=lateral)
            engine.step(200)
            reach[tag] = engine._queue_reach("wf")
        self.assertLess(reach["4"], reach["2"])

    def test_metrics_report_reach_by_approach_and_network_maximum(self):
        engine = self.red_engine()
        place(engine, ROUTE, "car", from_stop_line=0, lateral=-0.65)
        place(engine, ROUTE, "car", from_stop_line=6.5, lateral=-0.65)
        engine.step(20)
        metrics = engine._last_metrics
        west = engine.network.lanes["wf"].approach
        self.assertAlmostEqual(metrics["junctions"]["j"]["queue_reach_m"][west], engine._queue_reach("wf"))
        incoming = [lane.id for lane in engine.network.lanes.values() if lane.target in engine.signals]
        self.assertAlmostEqual(metrics["max_queue_reach_m"], max(engine._queue_reach(lane) for lane in incoming))
        self.assertGreater(metrics["max_queue_reach_m"], 10)

    def test_catalog_defines_queue_reach(self):
        catalog = json.loads(CATALOG.read_text(encoding="utf-8"))
        entry = next(metric for metric in catalog["metrics"] if metric["key"] == "max_queue_reach_m")
        self.assertEqual((entry["unit"], entry["requires_ticks"], entry["label"]), ("metres", False, "Longest current queue reach"))
        self.assertEqual(catalog["version"], "native-metric-interpretation-4")


if __name__ == "__main__":
    unittest.main()
