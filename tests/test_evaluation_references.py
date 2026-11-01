"""Evaluate RL against the no-signal and traditional references (plan Task 18, design 0.10)."""
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import config
import database
from services.rl_reporting_service import build_combined_ranking
from services.rl_training_service import build_evaluation_command
from simulation.model_contract import native_contract, phase_plan
from simulation.network_registry import engine_for_scenario, load_registered_network
from simulation.traffic_engine import TrafficEngine
from tools import evaluate_controllers
from tools.evaluate_controllers import DEFAULT_SEEDS, FINAL_EVALUATION_SEEDS, _build_summary, _run_controller_once

ROOT = Path(__file__).resolve().parents[1]
SITE = "tagum_site_a"


def metric(mean):
    return {"mean": mean, "min": mean, "max": mean, "std": 0.0, "available_count": 1, "run_count": 1}


def controller_summary(wait, queue, throughput):
    return {"avg_wait": metric(wait), "avg_queue": metric(queue), "throughput": metric(throughput)}


class EvaluationReferenceTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory(prefix="evaluation-", dir=Path(__file__).resolve().parent)
        self.db_path = str(Path(self.directory.name) / "evaluation.db")
        patcher = patch.object(config, "DB_PATH", self.db_path)
        patcher.start()
        self.addCleanup(patcher.stop)
        self.addCleanup(self.directory.cleanup)
        database.init_db()
        self.scenario = {"name": "Synthetic evaluation", "network_id": SITE, "engine_config": {"traffic_density": "low"}}
        self.scenario_id = database.create_scenario("Synthetic evaluation", network_id=SITE, engine_config={"traffic_density": "low"})

    def run_once(self, controller, seed=101, policies=None, warmup=3, duration=3):
        return _run_controller_once(controller=controller, seed=seed, scenario=self.scenario, scenario_id=self.scenario_id, duration_seconds=duration,
                                    warmup_seconds=warmup, decision_interval_seconds=1, minimum_green_hold_seconds=5, policies=policies or {},
                                    model_ids={}, record_timeline=False)

    def test_evaluation_command_includes_both_references_before_the_models(self):
        command = build_evaluation_command(["ql"], {}, {"ql": "m.json"})
        self.assertEqual(command[command.index("--controllers") + 1].split(","), ["no-signal", "fixed-time", "ql"])

    def test_evaluation_defaults_to_the_development_seeds(self):
        self.assertEqual(DEFAULT_SEEDS, (101, 102, 103, 104, 105))
        self.assertEqual(FINAL_EVALUATION_SEEDS, tuple(range(201, 221)))

    def test_final_seeds_need_the_final_flag(self):
        environment = {**os.environ, "SMARTFLOW_DB_PATH": self.db_path}
        refused = subprocess.run([sys.executable, "tools/evaluate_controllers.py", "--controllers", "no-signal", "--seeds", "201", "--duration-seconds", "2",
                                  "--warmup-seconds", "0", "--scenario-id", str(self.scenario_id)], cwd=ROOT, capture_output=True, text=True, timeout=120, env=environment)
        self.assertNotEqual(refused.returncode, 0)
        self.assertIn("Seeds 201–220 are reserved for the final evaluation", refused.stderr)

    def test_the_no_signal_reference_warms_up_with_no_signal(self):
        modes = []
        original_step = TrafficEngine.step

        def recording_step(engine, num_ticks=1):
            if engine.simulation_time < 3:
                modes.append({signal.mode for signal in engine.signals.values()})
            return original_step(engine, num_ticks)

        with patch.object(TrafficEngine, "step", recording_step):
            self.run_once("no-signal")
        self.assertTrue(modes and all(seen == {"first_come"} for seen in modes))

    def test_the_fixed_time_reference_warms_up_under_its_plan(self):
        modes = []
        original_step = TrafficEngine.step

        def recording_step(engine, num_ticks=1):
            if engine.simulation_time < 3:
                modes.append({signal.mode for signal in engine.signals.values()})
            return original_step(engine, num_ticks)

        with patch.object(TrafficEngine, "step", recording_step):
            self.run_once("fixed-time")
        self.assertTrue(modes and all(seen == {"signalized"} for seen in modes))

    def test_a_policy_controls_the_warm_up_too(self):
        engine = engine_for_scenario(self.scenario, seed=0)
        policy = SimpleNamespace(controller_provenance="ql", artifact_metadata={"native_contract": native_contract(load_registered_network(SITE)), "phase_plan": phase_plan(engine)},
                                 predict=lambda observation, info: SimpleNamespace(action_name="SERVE_PHASE_1"))
        controlled = []
        original_step = TrafficEngine.step

        def recording_step(engine, num_ticks=1):
            if engine.simulation_time < 3:
                controlled.append(engine.rl_control_enabled)
            return original_step(engine, num_ticks)

        with patch.object(TrafficEngine, "step", recording_step):
            self.run_once("ql", policies={"ql": policy})
        self.assertTrue(controlled and all(controlled))

    def test_results_report_unfinished_demand_and_the_summary_reports_spread(self):
        results = [self.run_once("no-signal", seed=seed) for seed in (101, 102)]
        for result in results:
            self.assertIn("pending_demand", result)
            self.assertIn("unfinished_vehicles", result)
        summary = _build_summary(results)["no-signal"]["avg_wait"]
        for key in ("mean", "std", "min", "max"):
            self.assertIn(key, summary)

    def test_ranking_compares_against_both_references(self):
        ranking = build_combined_ranking({"no-signal": controller_summary(30, 8, 100), "fixed-time": controller_summary(20, 6, 110), "ql": controller_summary(15, 5, 120)})
        ql = next(row for row in ranking if row["controller"] == "ql")
        self.assertEqual(ql["beats_no_signal"], {"avg_wait": True, "avg_queue": True, "throughput": True})
        self.assertEqual(ql["beats_fixed_time"], {"avg_wait": True, "avg_queue": True, "throughput": True})
        self.assertEqual(ql["comparison_to_no_signal"]["avg_wait"]["relation"], "lower")
        self.assertEqual(next(row for row in ranking if row["controller"] == "no-signal")["comparison_to_no_signal"]["avg_wait"]["relation"], "baseline")

    def test_ranking_without_a_no_signal_run_is_unchanged(self):
        ranking = build_combined_ranking({"fixed-time": controller_summary(20, 6, 110), "ql": controller_summary(15, 5, 120)})
        self.assertTrue(all("beats_no_signal" not in row and "comparison_to_no_signal" not in row for row in ranking))

    def test_the_output_names_the_warm_up_control_window_and_final_flag(self):
        output = Path(self.directory.name) / "evaluation.json"
        default_scenario_id = database.create_scenario("Default network", engine_config={"traffic_density": "low"})  # a study site needs the validation gate
        with patch.object(sys, "argv", ["evaluate_controllers", "--scenario-id", str(default_scenario_id), "--controllers", "no-signal,fixed-time", "--seeds", "101",
                                        "--duration-seconds", "2", "--warmup-seconds", "1", "--output", str(output)]):
            self.assertEqual(evaluate_controllers.main(), 0)
        payload = json.loads(output.read_text())
        self.assertEqual((payload["warmup_seconds"], payload["warmup_control"], payload["measurement_window_seconds"], payload["final"]),
                         (1.0, "evaluated controller", 2.0, False))
        self.assertEqual({result["controller"] for result in payload["results"]}, {"no-signal", "fixed-time"})


if __name__ == "__main__":
    unittest.main()
