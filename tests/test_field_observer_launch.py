import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

os.environ.setdefault("SMARTFLOW_SECRET_KEY", "field-observer-launch-test-only")
from fastapi.testclient import TestClient

import config
import auth
import database
from backend import main
from backend.main import app


class FieldObserverLaunchTests(unittest.TestCase):
    def test_only_admins_start_the_launcher(self):
        with tempfile.TemporaryDirectory(prefix="launch-", dir=Path(__file__).resolve().parent) as directory, \
                patch.object(config, "DB_PATH", str(Path(directory) / "launch.db")), \
                patch.object(config, "BOOTSTRAP_ADMIN_PASSWORD", "LaunchAdmin42!"), \
                patch.object(main.subprocess, "Popen") as popen, TestClient(app) as client:
            self.assertEqual(client.post("/api/auth/login", json={"username": "admin", "password": "LaunchAdmin42!"}).status_code, 200)
            response = client.post("/api/tools/field-observer/open")
            self.assertEqual(response.status_code, 200, response.text)
            self.assertIn("Start Field Observer.cmd", popen.call_args.args[0][-1])
            database.create_user("Viewer", "viewer", "viewer@example.test", auth.hash_password("ViewerPass42!x"), role_id=2)
            client.post("/api/auth/logout")
            self.assertEqual(client.post("/api/auth/login", json={"username": "viewer", "password": "ViewerPass42!x"}).status_code, 200)
            self.assertEqual(client.post("/api/tools/field-observer/open").status_code, 403)
            self.assertEqual(popen.call_count, 1)


if __name__ == "__main__":
    unittest.main()
