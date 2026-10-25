"""Junction reservations must always be released (engine fix plan P0-1)."""
import json
import unittest
from pathlib import Path

from simulation.road_network import RoadNetwork
from simulation.scenario_config import VEHICLE_TYPES
from simulation.traffic_engine import MIN_GAP, TrafficEngine
from tests import test_native_traffic_contract as contract

TWO_JUNCTION_NETWORK = Path(__file__).resolve().parents[1] / "data/networks/tagum_network_2j.json"


def two_junction_line(link_length=60):
    """w -> j1 -> j2 -> e, one-way, so a red at j2 can hold a queue on the j1-j2 link."""
    coordinates = {"w": (-150, 0), "j1": (0, 0), "j2": (link_length, 0), "e": (link_length+150, 0),
                   "n1": (0, 150), "n2": (link_length, 150)}
    nodes = [{"id": name, "x": x, "y": y, "boundary": not name.startswith("j")} for name, (x, y) in coordinates.items()]
    roads = [{"id": road, "source": start, "target": end, "shape": [coordinates[start], coordinates[end]], "oneway": True, "speed_mps": 8.33}
             for road, start, end in (("in", "w", "j1"), ("link", "j1", "j2"), ("out", "j2", "e"), ("n1", "n1", "j1"), ("n2", "n2", "j2"))]
    return RoadNetwork({"id": "two-junction-line", "nodes": nodes, "roads": roads, "source": {"kind": "synthetic"}})


def hold(engine, node, family):
    signal = engine.signals[node]
    signal.index, signal.stage, signal.elapsed = signal.approaches.index(family), "green", 0
    signal.external, signal.maximum_green = True, 180


class JunctionReleaseTests(unittest.TestCase):
    # Reuse the synthetic-cross helpers without collecting that test class twice.
    engine = contract.NativeTrafficContractTests.engine
    hold_phase = contract.NativeTrafficContractTests.hold_phase

    def test_any_admitted_vehicle_clears_and_releases_behind_a_held_queue(self):
        """For every class pair and queue length on the link: the vehicle never enters, or it enters and releases.
        The queue is held by a red at the next junction, like spillback towards the first one."""
        outcomes = set()
        for entering_type in VEHICLE_TYPES:
            for queued_type in VEHICLE_TYPES:
                for queued_count in range(0, 12):
                    with self.subTest(entering=entering_type, queued=queued_type, count=queued_count):
                        engine = TrafficEngine(seed=7, network=two_junction_line())
                        engine.configure(traffic_density="none", pedestrian_density="none")
                        engine.start(300)
                        hold(engine, "j1", "west")
                        hold(engine, "j2", "north")
                        route = engine.network.route("w", "e")
                        link = engine.network.lanes[route[1]]
                        front = link.length
                        for _ in range(queued_count):
                            queued = engine.add_vehicle(route[1:], vehicle_type=queued_type)
                            if queued is None:
                                break  # the link is already full back to j1
                            queued.position = front-queued.length/2
                            front -= queued.length+MIN_GAP
                        entering = engine.add_vehicle(route, vehicle_type=entering_type)
                        entering.position = engine.network.lanes[route[0]].length-entering.length/2
                        entered = False
                        for _ in range(400):
                            engine.step()
                            entered = entered or entering.reserved_junction == "j1"
                        outcomes.add(entered)
                        if entered:
                            self.assertEqual(entering.lane_id, route[1])
                            self.assertNotEqual(entering.reserved_junction, "j1")
                            self.assertNotIn("j1", engine.reservations)
                        else:
                            self.assertEqual(entering.lane_id, route[0])
        self.assertEqual(outcomes, {True, False}, "both admitted and refused cases must be exercised")

    def test_watchdog_metrics_flag_blocked_green_but_not_red_waits(self):
        engine = self.engine(network=contract.cross_network())
        signal = self.hold_phase(engine, "west")
        waiting = engine.add_vehicle(["wf", "er"])
        waiting.position = engine.network.lanes["wf"].length-waiting.length/2
        waiting.stop_arrival = engine.simulation_time
        engine.last_vehicle_movement = engine.simulation_time-61
        self.assertGreater(engine._gridlock_seconds(), 60)
        signal.index = signal.approaches.index("north")
        self.assertEqual(engine._gridlock_seconds(), 0)
        waiting.reserved_junction, waiting.stopped_for = "j", 31.0
        engine._refresh_metrics()
        self.assertEqual(engine._last_metrics["stuck_junction_vehicles"], 1)

    def test_two_junction_network_keeps_completing_trips_at_medium_demand(self):
        network = RoadNetwork(json.loads(TWO_JUNCTION_NETWORK.read_text(encoding="utf-8")))
        engine = TrafficEngine(seed=101, network=network)
        engine.configure(traffic_density="medium")
        engine.start(duration_limit=900)
        completed_at = {}
        while engine.status == "running":
            engine.step(100)
            completed_at[round(engine.simulation_time)] = engine.completed
            self.assertEqual(engine._last_metrics["stuck_junction_vehicles"], 0)
            self.assertEqual(engine._last_metrics["gridlock_seconds"], 0)
        # Before the fix both junctions locked each other from about t=600 s with 52 completed trips.
        self.assertGreater(completed_at[900], completed_at[600])
        self.assertEqual(engine._last_metrics["vehicle_conservation_error"], 0)


if __name__ == "__main__":
    unittest.main()
