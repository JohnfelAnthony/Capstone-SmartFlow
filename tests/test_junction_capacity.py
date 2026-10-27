"""Junction capacity plausibility (engine fix plan P1-2)."""
import unittest

from simulation.road_network import RoadNetwork
from simulation.traffic_engine import MIN_GAP, TrafficEngine
from tests import test_native_traffic_contract as contract


def long_approach_cross(length=400, speed=8.33):
    nodes = [{"id": "j", "x": 0, "y": 0}] + [{"id": name, "x": x, "y": y, "boundary": True}
                                             for name, x, y in (("w", -length, 0), ("e", length, 0), ("n", 0, length), ("s", 0, -length))]
    roads = [{"id": name, "source": name, "target": "j", "shape": [[x, y], [0, 0]], "speed_mps": speed}
             for name, x, y in (("w", -length, 0), ("e", length, 0), ("n", 0, length), ("s", 0, -length))]
    return RoadNetwork({"id": "capacity-cross", "nodes": nodes, "roads": roads, "source": {"kind": "synthetic"}})


class JunctionCapacityTests(unittest.TestCase):
    hold_phase = contract.NativeTrafficContractTests.hold_phase

    def saturated_discharge(self, destination, vehicle_type="car", green_seconds=60):
        """Queue the west approach on red, give it one green, return (vehicles discharged, steady headway s)."""
        engine = TrafficEngine(seed=3, network=long_approach_cross())
        engine.configure(traffic_density="none", pedestrian_density="none", routing_mode="static",
                         trips=[{"time": index*0.5, "source": "w", "destination": destination, "vehicle_type": vehicle_type} for index in range(120)])
        engine.driver_variation_scale = 0  # class values only, so the headway compares with native-5
        engine.start(600)
        # Building a long queue needs a 240 s red, longer than the maximum-red guard allows in normal operation.
        self.hold_phase(engine, "north").maximum_red = 600
        engine.step(2400)
        west_lane = next(lane.id for lane in engine.network.lanes.values() if lane.source == "w")
        self.assertGreater(engine._lane_queues()[west_lane], 30, "the approach must be saturated before green")
        self.hold_phase(engine, "west")
        exits, previous = [], engine.lane_exits[west_lane]
        for _ in range(int(green_seconds/0.1)):
            engine.step()
            if engine.lane_exits[west_lane] > previous:
                exits.append(engine.simulation_time)
                previous = engine.lane_exits[west_lane]
        headways = [later-earlier for earlier, later in zip(exits, exits[1:])][3:]
        return len(exits), sum(headways)/len(headways)

    def test_through_movement_discharges_near_urban_saturation_flow(self):
        discharged, headway = self.saturated_discharge("e")
        # Engine IDM at 30 km/h implies about 1,400 veh/h (2.5 s); before P1-2 it was 7.9 s and 8 vehicles per minute.
        self.assertLessEqual(headway, 3.0)
        self.assertGreaterEqual(headway, 1.6)
        self.assertGreaterEqual(discharged, 18)

    def test_turning_movement_is_slower_than_through_but_not_one_at_a_time(self):
        _, through_headway = self.saturated_discharge("e")
        discharged, turn_headway = self.saturated_discharge("n")
        self.assertGreater(turn_headway, through_headway)
        self.assertLessEqual(turn_headway, 4.0)
        self.assertGreaterEqual(discharged, 14)

    def test_next_approach_waits_until_junction_is_clear(self):
        engine = contract.NativeTrafficContractTests.engine(self, network=contract.cross_network())
        engine.driver_variation_scale = 0
        signal = self.hold_phase(engine, "west")
        crossing = engine.add_vehicle(["wf", "er"])
        crossing.position = engine.network.lanes["wf"].length-crossing.length/2
        while crossing.connector is None:
            engine.step()
        signal.index = signal.approaches.index("north")
        waiting = engine.add_vehicle(["nf", "sr"])
        waiting.position = engine.network.lanes["nf"].length-waiting.length/2
        while crossing.reserved_junction == "j":
            engine.step()
            self.assertIsNone(waiting.reserved_junction)
        for _ in range(20):
            engine.step()
        self.assertEqual(waiting.reserved_junction, "j")

    def test_vehicles_on_one_connector_keep_their_gap(self):
        engine = contract.NativeTrafficContractTests.engine(self, network=long_approach_cross())
        engine.driver_variation_scale = 0
        self.hold_phase(engine, "west")
        route = engine.network.route("w", "e")
        cars = []
        for offset in range(5):
            car = engine.add_vehicle(route)
            car.position = engine.network.lanes[route[0]].length-car.length/2-offset*(car.length+MIN_GAP+.5)
            cars.append(car)
        for _ in range(300):
            engine.step()
            on_connector = sorted((car for car in engine.vehicles.values() if car.connector), key=lambda car: car.connector_position)
            for rear, front in zip(on_connector, on_connector[1:]):
                self.assertGreaterEqual(front.connector_position-rear.connector_position-(front.length+rear.length)/2, MIN_GAP-1e-6)
        self.assertEqual(engine.completed+len(engine.vehicles), 5)


if __name__ == "__main__":
    unittest.main()
