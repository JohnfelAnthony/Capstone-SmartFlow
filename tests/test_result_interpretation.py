"""Interpretation regressions use synthetic values, never field-effectiveness evidence."""
import json
import math
import os
import unittest

from services.metric_definitions import METRIC_CATALOG, metric_value, interpreted_metrics
from services.rl_reporting_service import build_combined_ranking, primary_evaluation_score
from simulation.traffic_engine import TrafficEngine

os.environ.setdefault("SMARTFLOW_SECRET_KEY", "interpretation-tests-only")
from tools.evaluate_controllers import _build_summary


def summaries(rows):
    return {controller: {key: {"mean": value} for key, value in values.items()}
            for controller, values in rows.items()}


class ResultInterpretationTests(unittest.TestCase):
    def test_constructed_lower_wait_is_not_an_overall_recommendation(self):
        rows = build_combined_ranking(summaries({
            "fixed-time": dict(avg_wait=20, throughput=90, unfinished_vehicles=10,
                               avg_ped_delay=10, requested_vehicles=100, dropped_vehicles=0),
            "ppo": dict(avg_wait=19, throughput=10, unfinished_vehicles=90,
                        avg_ped_delay=100, requested_vehicles=100, dropped_vehicles=0),
        }))
        policy = rows[0]
        self.assertEqual(policy["controller"], "ppo")
        self.assertEqual(policy["waiting_time_rank"], 1)
        self.assertEqual(policy["traffic_performance_rank"], policy["waiting_time_rank"])
        self.assertIsNone(policy["overall_recommendation"])
        self.assertIn("not an overall", policy["ranking_criterion"].lower())
        tradeoffs = policy["comparison_to_fixed_time"]
        self.assertEqual(tradeoffs["throughput"]["difference"], -80)
        self.assertEqual(tradeoffs["unfinished_vehicles"]["difference"], 80)
        self.assertEqual(tradeoffs["avg_ped_delay"]["difference"], 90)
        self.assertEqual(tradeoffs["avg_wait"]["percent_change"], -5)

    def test_missing_nonfinite_and_empty_populations_cannot_win(self):
        rows = build_combined_ranking(summaries({
            "fixed-time": dict(avg_wait=10, throughput=2),
            "missing": {}, "nan": dict(avg_wait=math.nan),
            "empty": dict(avg_wait=0, total_vehicles_completed=0, active_vehicle_count=0),
        }))
        self.assertEqual(rows[0]["controller"], "fixed-time")
        for row in rows[1:]:
            self.assertIsNone(row["waiting_time_rank"])
            self.assertIsNone(row["primary_evaluation_score"])
            self.assertIsNone(row["beats_fixed_time"]["avg_wait"])
        json.dumps(rows, allow_nan=False)
        self.assertIsNone(primary_evaluation_score({"avg_wait": {"mean": math.inf}}))

    def test_ties_and_zero_reference_are_explicit(self):
        rows = build_combined_ranking(summaries({
            "fixed-time": dict(avg_wait=0, throughput=2, total_vehicles_completed=2, active_vehicle_count=0),
            "ql": dict(avg_wait=0, throughput=2, total_vehicles_completed=2, active_vehicle_count=0),
            "ppo": dict(avg_wait=0, throughput=1, total_vehicles_completed=1, active_vehicle_count=0),
        }))
        self.assertEqual([row["waiting_time_rank"] for row in rows], [1, 1, 3])
        self.assertIsNone(rows[1]["comparison_to_fixed_time"]["avg_wait"]["percent_change"])
        self.assertEqual(rows[1]["comparison_to_fixed_time"]["avg_wait"]["relation"], "tie")

    def test_zero_is_distinct_from_missing_or_empty(self):
        empty = TrafficEngine().to_dict()["metrics"]
        self.assertEqual(empty["avg_wait"], 0)
        self.assertIsNone(metric_value(empty, "avg_wait"))
        self.assertIsNone(metric_value(empty, "avg_travel_time"))
        self.assertIsNone(metric_value(empty, "avg_ped_delay"))
        self.assertEqual(metric_value(empty, "throughput"), 0)
        self.assertIsNone(metric_value(empty, "throughput_per_hour"))
        self.assertEqual(metric_value({**empty, "measurement_seconds": 2}, "throughput_per_hour"), 0)
        self.assertIsNone(metric_value({}, "throughput"))
        populated = {**empty, "active_vehicle_count": 2, "avg_wait": 0}
        self.assertEqual(metric_value(populated, "avg_waiting_time"), 0)
        self.assertFalse(interpreted_metrics(empty)["avg_wait"]["available"])

    def test_stored_aliases_keep_unknown_populations_unavailable(self):
        historical = {"avg_waiting_time": 0, "throughput": 0}
        self.assertIsNone(metric_value(historical, "avg_wait"))
        self.assertEqual(metric_value(historical, "throughput"), 0)
        saved = {"avg_waiting_time": 99, "raw_metrics": {
            "avg_wait": 4, "total_vehicles_completed": 2, "active_vehicle_count": 1}}
        self.assertEqual(metric_value(saved, "avg_waiting_time"), 4)
        self.assertIsNone(metric_value({"throughput": True}, "throughput"))
        self.assertIsNone(metric_value({"throughput": 5, "experiment": {"engine_version": "historical-other-engine"}}, "throughput"))

    def test_definitions_explain_window_and_unsupported_emissions(self):
        definitions = {item["key"]: item for item in METRIC_CATALOG["metrics"]}
        self.assertIn("pre-window", definitions["avg_travel_time"]["definition"])
        self.assertIn("warmup", definitions["requested_vehicles"]["definition"])
        self.assertIn("outgoing boundary lanes", definitions["max_queue"]["definition"])
        self.assertIn("Unavailable", METRIC_CATALOG["unsupported"]["emissions"])

    def test_summary_excludes_unavailable_values_and_exposes_coverage(self):
        valid = {"avg_wait": 12, "total_vehicles_completed": 2, "active_vehicle_count": 0}
        empty = {"avg_wait": 0, "total_vehicles_completed": 0, "active_vehicle_count": 0}
        summary = _build_summary([{"controller": "ql", "metrics": valid}, {"controller": "ql", "metrics": empty}])
        self.assertEqual(summary["ql"]["avg_wait"], {"mean": 12, "min": 12, "max": 12,
            "std": 0, "available_count": 1, "run_count": 2})
        self.assertIsNone(summary["ql"]["avg_travel_time"]["mean"])
        self.assertIsNone(primary_evaluation_score(summary["ql"]))


if __name__ == "__main__":
    unittest.main()
