import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

os.environ.setdefault("SMARTFLOW_SECRET_KEY", "movement-counts-test-only")
from fastapi.testclient import TestClient

import config
from backend.main import app

from services.movement_counts import approach_boundaries, import_movement_counts
from simulation.demand import build_schedule
from simulation.network_registry import load_registered_network
from simulation.scenario_config import DEFAULTS, validate_config

SITE_A_CSV = "from,to,vehicle_type,count\nnorth,south,car,360\nwest,east,truck,36\nsouth,north,motorcycle,0\n"


class MovementCountTests(unittest.TestCase):
    def test_rows_become_one_demand_stream_per_movement_and_class(self):
        network = load_registered_network("tagum_site_a")
        boundaries = approach_boundaries(network)
        config = import_movement_counts(csv_text=SITE_A_CSV, network_id="tagum_site_a", engine_config={"pedestrian_density": "low"})["engine_config"]
        self.assertEqual(config["traffic_density"], "none")
        self.assertEqual(config["pedestrian_density"], "low")
        self.assertEqual(config["trips"], [])
        windows = [(w["od"][0]["source"], w["od"][0]["destination"], w["vehicle_type"], w["vehicles_per_hour"]) for w in config["demand_windows"]]
        self.assertEqual(windows, [(boundaries["north"][0], boundaries["south"][1], "car", 360.0),
                                   (boundaries["west"][0], boundaries["east"][1], "truck", 36.0)])

    def test_split_highway_exits_match_their_leg_by_direction(self):
        # Site B's highway legs enter and leave through different boundary nodes.
        self.assertEqual(approach_boundaries(load_registered_network("tagum_site_b")),
                         {"south": ("boundary_0", "boundary_0"), "west": ("boundary_2", "boundary_5"),
                          "north": ("boundary_3", "boundary_3"), "east": ("boundary_4", "boundary_1")})

    def test_schedule_keeps_each_stream_class(self):
        config = import_movement_counts(csv_text=SITE_A_CSV, network_id="tagum_site_a", engine_config={})["engine_config"]
        network = load_registered_network("tagum_site_a")
        arrivals = build_schedule(validate_config(DEFAULTS, config, network), network, 7, 3600)
        self.assertEqual({a.vehicle_type for a in arrivals}, {"car", "truck"})
        trucks = [a for a in arrivals if a.vehicle_type == "truck"]
        self.assertTrue(all(a.source == approach_boundaries(network)["west"][0] for a in trucks))
        self.assertTrue(250 < sum(a.vehicle_type == "car" for a in arrivals) < 470)

    def test_rejects_bad_files_with_a_plain_message(self):
        cases = {
            "from,to,vehicle_type,count,date\nnorth,south,car,1,2026-01-01\n": "columns",
            "from,to,vehicle_type,count\nnorth,uptown,car,10\n": "uptown",
            "from,to,vehicle_type,count\nnorth,north,car,10\n": "different",
            "from,to,vehicle_type,count\nnorth,south,jeepney,10\n": "vehicle_type",
            "from,to,vehicle_type,count\nnorth,south,car,-1\n": "count",
            "from,to,vehicle_type,count\nnorth,south,car,10\nnorth,south,car,5\n": "twice",
            "from,to,vehicle_type,count\nnorth,south,car,0\n": "at least one",
            "": "empty",
        }
        for csv_text, message in cases.items():
            with self.subTest(csv_text=csv_text), self.assertRaisesRegex(ValueError, message):
                import_movement_counts(csv_text=csv_text, network_id="tagum_site_a", engine_config={})

    def test_multi_junction_networks_are_refused(self):
        with self.assertRaisesRegex(ValueError, "single-junction"):
            import_movement_counts(csv_text=SITE_A_CSV, network_id="tagum_network", engine_config={})


class MovementCountApiTests(unittest.TestCase):
    def test_endpoint_returns_the_draft_config_or_a_422_message(self):
        with tempfile.TemporaryDirectory(prefix="movement-counts-", dir=Path(__file__).resolve().parent) as directory, \
                patch.object(config, "DB_PATH", str(Path(directory) / "counts.db")), \
                patch.object(config, "BOOTSTRAP_ADMIN_PASSWORD", "CountsAdmin42!"), TestClient(app) as client:
            self.assertEqual(client.post("/api/auth/login", json={"username": "admin", "password": "CountsAdmin42!"}).status_code, 200)
            response = client.post("/api/scenarios/movement-counts", json={"csv_text": SITE_A_CSV, "network_id": "tagum_site_a", "engine_config": {}})
            self.assertEqual(response.status_code, 200, response.text)
            self.assertEqual((response.json()["rows"], response.json()["vehicles_per_hour"]), (2, 396.0))
            bad = client.post("/api/scenarios/movement-counts", json={"csv_text": "a,b\n1,2\n", "network_id": "tagum_site_a", "engine_config": {}})
            self.assertEqual(bad.status_code, 422)
            self.assertIn("columns", bad.json()["detail"])


if __name__ == "__main__":
    unittest.main()
