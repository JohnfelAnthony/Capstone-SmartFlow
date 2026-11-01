"""The Webster endpoint returns a provisional plan that the scenario validator accepts (plan Tasks 15-16)."""
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

os.environ.setdefault("SMARTFLOW_SECRET_KEY", "signal-design-test-only")
from fastapi.testclient import TestClient

import config
from backend.main import app
from backend.simulation_runtime import simulation_runtime
from simulation.network_registry import load_registered_network
from simulation.scenario_config import DEFAULTS, validate_config
from simulation.signal_design import saturation_from_network

SITE = "tagum_site_a"
PHASES = [["north", "south"], ["east", "west"], "pedestrian"]


class SignalDesignApiTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory(prefix="signal-design-", dir=Path(__file__).resolve().parent)
        self.patches = [patch.object(config, "DB_PATH", str(Path(self.directory.name) / "design.db")),
                        patch.object(config, "BOOTSTRAP_ADMIN_PASSWORD", "DesignAdmin42!")]
        for item in self.patches:
            item.start()
        self.client = TestClient(app)
        self.client.__enter__()
        simulation_runtime.reset(force=True)
        self.assertEqual(self.client.post("/api/auth/login", json={"username": "admin", "password": "DesignAdmin42!"}).status_code, 200)
        self.network = load_registered_network(SITE)
        self.saturation = saturation_from_network(self.network, self.network.intersections[0])

    def tearDown(self):
        simulation_runtime.reset(force=True)
        self.client.__exit__(None, None, None)
        for item in reversed(self.patches):
            item.stop()
        self.directory.cleanup()

    def counts(self, share_of_saturation):
        return {approach: {"car": share_of_saturation * flow} for approach, flow in self.saturation.items()}

    def design(self, **changes):
        body = {"network_id": SITE, "phase_order": PHASES, "approach_counts": self.counts(0.15), **changes}
        return self.client.post("/api/signal-design", json=body)

    def test_the_four_site_approaches_are_the_compass_names_the_plan_groups_use(self):
        self.assertEqual(set(self.saturation), {"north", "south", "east", "west"})

    def test_a_design_returns_a_plan_the_scenario_validator_accepts_and_labels_it_provisional(self):
        response = self.design()
        self.assertEqual(response.status_code, 200, response.text)
        body = response.json()
        plan = body["plan"]
        self.assertEqual(plan["phase_order"], PHASES)
        self.assertEqual(len(plan["phase_greens"]), 3)
        validated = validate_config(DEFAULTS, {"signal_plans": {self.network.intersections[0]: plan}}, self.network)
        self.assertEqual(validated["signal_plans"][self.network.intersections[0]]["phase_greens"], plan["phase_greens"])
        self.assertTrue(body["result"]["assumptions"]["provisional"])
        self.assertAlmostEqual(body["result"]["total_flow_ratio"], 0.30, places=2)

    def test_more_flow_on_a_phase_lengthens_its_green(self):
        base = self.design().json()["result"]["phase_greens"]
        counts = self.counts(0.15)
        counts["east"]["car"] *= 2
        busier = self.design(approach_counts=counts).json()["result"]["phase_greens"]
        self.assertGreater(busier[1] / busier[0], base[1] / base[0])

    def test_oversaturated_demand_is_refused_with_the_reason(self):
        response = self.design(approach_counts=self.counts(0.6))
        self.assertEqual(response.status_code, 422)
        self.assertIn("Total flow ratio Y must be below 1", response.text)

    def test_a_plan_without_a_walk_phase_is_refused(self):
        response = self.design(phase_order=[["north", "south"], ["east", "west"]])
        self.assertEqual(response.status_code, 422)
        self.assertIn("walk phase", response.text)

    def test_unknown_networks_and_junctions_are_refused(self):
        self.assertEqual(self.design(network_id="nowhere").status_code, 422)
        self.assertEqual(self.design(junction="nowhere").status_code, 422)

    def test_a_viewer_without_edit_permission_cannot_design(self):
        anonymous = TestClient(app)
        self.assertEqual(anonymous.post("/api/signal-design", json={"network_id": SITE, "phase_order": PHASES, "approach_counts": {}}).status_code, 401)


if __name__ == "__main__":
    unittest.main()
