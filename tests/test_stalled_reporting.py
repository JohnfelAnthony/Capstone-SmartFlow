"""A run that ends with `stalled_vehicles` above zero (the known rare side-by-side freeze, D37) is reported, never silently used."""
from types import SimpleNamespace

from tools.evaluate_controllers import failed_matched_seeds, stalled_vehicle_runs
from tools.stage_acceptance import ZERO_TARGETS, missed_targets


def result(controller, seed, stalled):
    return {"controller": controller, "seed": seed, "run_id": seed * 10, "metrics": {"stalled_vehicles": stalled}}


def test_evaluation_lists_every_run_that_ended_with_a_stalled_vehicle():
    results = [result("fixed-time", 101, 0), result("fixed-time", 102, 1), result("ppo", 102, 3), {"controller": "ppo", "seed": 103, "run_id": 1, "metrics": {}}]
    assert stalled_vehicle_runs(results) == [
        {"controller": "fixed-time", "seed": 102, "run_id": 1020, "stalled_vehicles": 1},
        {"controller": "ppo", "seed": 102, "run_id": 1020, "stalled_vehicles": 3},
    ]


def test_the_run_report_row_carries_the_stalled_vehicle_count():
    from backend.main import run_report_row
    run = SimpleNamespace(id=1, scenario_name="s", run_mode="offline", control_mode="fixed-time", status="completed", start_time=None, end_time=None, duration_seconds=1.0,
                          seed=1, rl_model_id=None, notes=None, timeline_path=None, metrics={"raw_metrics": {
                              "stalled_vehicles": 0, "peak_stalled_vehicles": 2, "first_stall_seconds": 66, "max_overlapping_pairs": 1,
                          }})
    row = run_report_row(run)
    assert row["Stalled Vehicles At Run End"] == 0
    assert row["Peak Stalled Vehicles"] == 2
    assert row["First Stall Measurement Seconds"] == 66
    assert row["Peak Overlapping Vehicle Pairs"] == 1


def test_resolved_stalls_and_overlaps_flag_matched_seeds():
    stall = result("fixed-time", 101, 0)
    stall["metrics"].update(peak_stalled_vehicles=3, first_stall_seconds=67)
    overlap = result("ppo", 102, 0)
    overlap["metrics"]["max_overlapping_pairs"] = 1
    rows = [stall, result("ppo", 101, 0), overlap, result("fixed-time", 103, 0)]
    assert stalled_vehicle_runs(rows)[0]["first_stall_seconds"] == 67
    assert failed_matched_seeds(rows) == {
        101: [{"controller": "fixed-time", "run_id": 1010, "issues": {"peak_stalled_vehicles": 3}}],
        102: [{"controller": "ppo", "run_id": 1020, "issues": {"max_overlapping_pairs": 1}}],
    }


def test_closure_held_vehicles_do_not_excuse_other_stuck_vehicles():
    row = dict.fromkeys(ZERO_TARGETS, 0)
    row.update(max_stuck_junction_vehicles=9, max_closure_held_vehicles=1, max_unexplained_stuck_junction_vehicles=8)
    assert missed_targets(row) == {"max_unexplained_stuck_junction_vehicles": 8}
    del row["max_unexplained_stuck_junction_vehicles"]
    assert missed_targets(row) == {"max_unexplained_stuck_junction_vehicles": None}
