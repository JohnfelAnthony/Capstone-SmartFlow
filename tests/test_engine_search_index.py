"""The per-tick vehicle index is a pure speed-up: results equal a scan of every vehicle."""
import json
import unittest
from pathlib import Path

from simulation.road_network import RoadNetwork
from simulation.traffic_engine import TrafficEngine

NETWORK = RoadNetwork(json.loads((Path(__file__).resolve().parents[1] / "data/networks/tagum_network_2j.json").read_text(encoding="utf-8")))


class FullScanEngine(TrafficEngine):
    def _candidates(self, *lookups):
        return list(self.vehicles.values())


def trajectory(engine_class, seconds=240):
    engine = engine_class(seed=101, network=NETWORK)
    engine.configure(traffic_density="high", pedestrian_density="medium")
    engine.start(seconds)
    states = []
    while engine.status == "running":
        engine.step(50)
        states.append(repr([(vehicle.id, tuple(vehicle.route), vehicle.position, vehicle.speed, vehicle.connector_position,
                             vehicle.reserved_junction) for vehicle in engine.vehicles.values()]))
    return states, engine.completed


class SearchIndexTests(unittest.TestCase):
    def test_indexed_engine_matches_full_scan_under_congestion(self):
        indexed, completed = trajectory(TrafficEngine)
        full_scan, full_scan_completed = trajectory(FullScanEngine)
        self.assertGreater(completed, 0)
        self.assertEqual(completed, full_scan_completed)
        self.assertEqual(indexed, full_scan)


if __name__ == "__main__":
    unittest.main()
