"""Junction reservations must always be released (engine fix plan P0-1)."""
import json
import unittest
from pathlib import Path

from simulation.road_network import RoadNetwork
from simulation.scenario_config import VEHICLE_TYPES
from simulation.traffic_engine import TrafficEngine
from tests import test_native_traffic_contract as contract

TWO_JUNCTION_NETWORK = Path(__file__).resolve().parents[1] / "data/networks/tagum_network_2j.json"


class JunctionReleaseTests(unittest.TestCase):
    # Reuse the synthetic-cross helpers without collecting that test class twice.
    engine = contract.NativeTrafficContractTests.engine
    hold_phase = contract.NativeTrafficContractTests.hold_phase

    def test_any_admitted_vehicle_clears_and_releases_behind_a_stopped_leader(self):
        """For every class pair and leader position: the vehicle never enters, or it enters and releases."""
        for entering_type in VEHICLE_TYPES:
            for leader_type in VEHICLE_TYPES:
                for leader_rear in (1.0, 3.0, 5.25, 7.0, 9.0, 11.0, 13.0, 15.0, 17.0, 20.0, 25.0):
                    with self.subTest(entering=entering_type, leader=leader_type, leader_rear=leader_rear):
                        engine = self.engine(network=contract.cross_network())
                        self.hold_phase(engine, "west")
                        leader = engine.add_vehicle(["er"], vehicle_type=leader_type)
                        entering = engine.add_vehicle(["wf", "er"], vehicle_type=entering_type)
                        entering.position = engine.network.lanes["wf"].length-entering.length/2
                        entered = False
                        for _ in range(400):
                            # The leader stands still, like the tail of a queue that is not moving.
                            leader.position, leader.speed = leader_rear+leader.length/2, 0.0
                            engine.step()
                            entered = entered or entering.reserved_junction is not None
                        if entered:
                            self.assertEqual(entering.lane_id, "er")
                            self.assertIsNone(entering.reserved_junction)
                            self.assertNotIn("j", engine.reservations)
                        else:
                            self.assertEqual(entering.lane_id, "wf")

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
