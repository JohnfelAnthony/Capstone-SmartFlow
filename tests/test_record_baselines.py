"""tools/record_fixed_time_baselines.py backs up the database, then records one fixed-time run per active scenario."""
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

os.environ.setdefault("SMARTFLOW_SECRET_KEY", "record-baselines-tests-only")
os.environ.setdefault("SMARTFLOW_BOOTSTRAP_ADMIN_PASSWORD", "BaselineTestAdmin42!")

import config
import database
from simulation.traffic_engine import ENGINE_VERSION

ROOT = Path(__file__).resolve().parents[1]
TOOL = ROOT/"tools"/"record_fixed_time_baselines.py"


class RecordBaselinesTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory(prefix="baselines-test-", dir=Path(__file__).resolve().parent)
        self.database_path = Path(self.directory.name)/"test.db"
        with patch.object(config, "DB_PATH", str(self.database_path)):
            database.init_db()
            database.seed_data()
            scenarios = database.get_scenarios()
            for scenario in scenarios[1:]:
                database.update_scenario(scenario["id"], is_archived=1)
            self.scenario = scenarios[0]

    def tearDown(self):
        self.directory.cleanup()

    def run_tool(self, *arguments):
        environment = {**os.environ, "SMARTFLOW_DB_PATH": str(self.database_path)}
        return subprocess.run([sys.executable, str(TOOL), "--seed", "101", *arguments], cwd=ROOT, env=environment,
                              capture_output=True, text=True, timeout=600)

    def test_without_confirm_it_exits_2_and_changes_nothing(self):
        result = self.run_tool("--seconds", "30")
        self.assertEqual(result.returncode, 2, result.stderr)
        with patch.object(config, "DB_PATH", str(self.database_path)):
            self.assertEqual(database.get_runs(limit=10), [])
        self.assertFalse((self.database_path.parent/"backups").exists())

    def test_with_confirm_it_backs_up_and_records_a_fixed_time_run_on_this_engine(self):
        result = self.run_tool("--seconds", "30", "--confirm")
        self.assertEqual(result.returncode, 0, result.stderr)
        backups = list((self.database_path.parent/"backups").glob(f"smartflow_backup_*_pre_{ENGINE_VERSION}_baselines.db"))
        self.assertEqual(len(backups), 1)
        with patch.object(config, "DB_PATH", str(self.database_path)):
            runs = database.get_runs(limit=10)
            self.assertEqual(len(runs), 1)
            run = runs[0]
            self.assertEqual((run["scenario_id"], run["status"], run["run_mode"], run["control_mode"]),
                             (self.scenario["id"], "completed", "pre-record", "fixed-time"))
            metrics = database.get_run_metrics(run["id"])
        self.assertEqual(json.loads(metrics["raw_metrics_json"])["experiment"]["engine_version"], ENGINE_VERSION)
        self.assertIn(str(run["id"]), result.stdout)


if __name__ == "__main__":
    unittest.main()
