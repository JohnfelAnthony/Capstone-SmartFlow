"""Owner's decision: sign-in never locks an account after wrong passwords."""
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient

import config
from backend.main import app


class LoginWithoutLockTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory(prefix="login-test-")
        self.patches = [patch.object(config, "DB_PATH", str(Path(self.directory.name)/"login.db")),
                        patch.object(config, "BOOTSTRAP_ADMIN_PASSWORD", "LoginAdmin42!")]
        for item in self.patches:
            item.start()
        self.client = TestClient(app)
        self.client.__enter__()

    def tearDown(self):
        self.client.__exit__(None, None, None)
        for item in reversed(self.patches):
            item.stop()
        self.directory.cleanup()

    def test_many_wrong_passwords_never_lock_the_account(self):
        for _ in range(8):
            wrong = self.client.post("/api/auth/login", json={"username": "admin", "password": "not-the-password"})
            self.assertEqual((wrong.status_code, wrong.json()["detail"]), (401, "Invalid username or password."))
        right = self.client.post("/api/auth/login", json={"username": "admin", "password": "LoginAdmin42!"})
        self.assertEqual(right.status_code, 200, right.text)

    def test_the_signed_in_user_carries_the_account_creation_date_for_settings(self):
        self.client.post("/api/auth/login", json={"username": "admin", "password": "LoginAdmin42!"})
        created = self.client.get("/api/auth/me").json()["created_at"]
        self.assertRegex(created, r"^\d{4}-\d{2}-\d{2}")
