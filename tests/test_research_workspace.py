"""Permission-scoped search. The calibration and validation records API was removed (D38); saved records stay in the database untouched."""
import json
import os
import sqlite3
import tempfile
import unittest
from contextlib import closing
from pathlib import Path
from unittest.mock import patch

os.environ.setdefault("SMARTFLOW_SECRET_KEY", "research-workspace-test-only")
from fastapi.testclient import TestClient
import auth
import config
import database
from backend.main import app
from backend.simulation_runtime import simulation_runtime


class ResearchWorkspaceTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory(prefix="research-", dir=Path(__file__).resolve().parent)
        self.root = Path(self.directory.name)
        self.patches = [patch.object(config, "DB_PATH", str(self.root / "research.db")),
                        patch.object(config, "BOOTSTRAP_ADMIN_PASSWORD", "ResearchAdmin42!")]
        for item in self.patches:
            item.start()
        self.client = TestClient(app)
        self.client.__enter__()
        simulation_runtime.reset(force=True)
        self.assertEqual(self.client.post("/api/auth/login", json={"username": "admin", "password": "ResearchAdmin42!"}).status_code, 200)
        self.scenario_id = database.create_scenario("Research baseline 100%_fixture", description="Literal search fixture",
            engine_config=json.dumps({"traffic_density": "none", "pedestrian_density": "none"}))

    def tearDown(self):
        simulation_runtime.reset(force=True)
        self.client.__exit__(None, None, None)
        for item in reversed(self.patches):
            item.stop()
        self.assertTrue(self.root.resolve().is_relative_to(Path(__file__).resolve().parent))
        self.directory.cleanup()

    def test_search_literal_substrings_deep_links_and_permissions(self):
        model = database.create_rl_model(name="Research model fixture")
        results = self.client.get("/api/search", params={"q": "research"}).json()["results"]
        self.assertTrue(any(row["kind"] == "Scenario" and row["id"] == self.scenario_id for row in results))
        self.assertTrue(any(row["kind"] == "Model" and row["id"] == model for row in results))
        self.assertTrue(any(row["page"] == "Settings" for row in self.client.get("/api/search", params={"q": "settings"}).json()["results"]))
        literal = self.client.get("/api/search", params={"q": "100%_fixture"}).json()["results"]
        self.assertEqual(len(literal), 1)
        self.assertEqual(self.client.get("/api/search", params={"q": "' OR 1=1 --"}).json()["results"], [])
        database.create_user("Research viewer", "research_viewer", None, auth.hash_password("ViewerOnly42!"), role_id=2)
        database.update_role_permission(2, "rl-training", "view", False)
        viewer = TestClient(app)  # use the already initialized database; no second startup/permission seeding
        self.assertEqual(viewer.post("/api/auth/login", json={"username": "research_viewer", "password": "ViewerOnly42!"}).status_code, 200)
        self.assertFalse(any(row["kind"] == "Model" for row in viewer.get("/api/search", params={"q": "research"}).json()["results"]))
        self.assertEqual(TestClient(app).get("/api/search", params={"q": "research"}).status_code, 401)

    def test_the_calibration_page_and_records_api_are_gone_but_saved_records_stay(self):
        for path in ("/api/calibration", "/api/calibration/1", "/api/calibration/1/export"):
            self.assertEqual(self.client.get(path).status_code, 404, path)
        self.assertEqual(self.client.post("/api/calibration", json={}).status_code, 404)
        self.assertFalse(any(row["page"] == "Calibration & Validation" for row in self.client.get("/api/search", params={"q": "calibration"}).json()["results"]))
        with closing(sqlite3.connect(config.DB_PATH)) as conn:  # the table is kept so earlier records are not lost
            self.assertEqual(conn.execute("SELECT count(*) FROM sqlite_master WHERE name='calibration_records'").fetchone()[0], 1)


if __name__ == "__main__":
    unittest.main()
