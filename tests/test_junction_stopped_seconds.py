"""Per-junction stopped vehicle-seconds (engine fix plan step 5, used by reward_v3 and the J1-local metric)."""
import unittest

from tests import test_native_traffic_contract as contract


class JunctionStoppedSecondsTests(unittest.TestCase):
    engine = contract.NativeTrafficContractTests.engine
    hold_phase = contract.NativeTrafficContractTests.hold_phase

    def test_red_wait_is_charged_to_its_junction_approach(self):
        engine = self.engine()
        self.hold_phase(engine, "north")
        waiting = engine.add_vehicle(["wf", "er"])
        waiting.position = engine.network.lanes["wf"].length-waiting.length/2
        engine.step(100)
        junction = engine._last_metrics["junctions"]["j"]
        self.assertAlmostEqual(junction["stopped_seconds"], waiting.wait, places=6)
        self.assertGreater(junction["stopped_seconds"], 9)
        self.assertEqual(junction["stopped_seconds_by_approach"]["west"], junction["stopped_seconds"])
        self.assertEqual(sum(junction["stopped_seconds_by_approach"].values()), junction["stopped_seconds"])

    def test_counter_restarts_with_the_measurement(self):
        engine = self.engine()
        self.hold_phase(engine, "north")
        waiting = engine.add_vehicle(["wf", "er"])
        waiting.position = engine.network.lanes["wf"].length-waiting.length/2
        engine.step(100)
        engine.reset_metrics()
        self.assertEqual(engine._last_metrics["junctions"]["j"]["stopped_seconds"], 0)
        engine.step(10)
        self.assertAlmostEqual(engine._last_metrics["junctions"]["j"]["stopped_seconds"], 1.0, places=6)


if __name__ == "__main__":
    unittest.main()
