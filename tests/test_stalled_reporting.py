"""A run that ends with `stalled_vehicles` above zero (the known rare side-by-side freeze, D37) is reported, never silently used."""
from types import SimpleNamespace

from tools.evaluate_controllers import stalled_vehicle_runs


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
                          seed=1, rl_model_id=None, notes=None, timeline_path=None, metrics={"raw_metrics": {"stalled_vehicles": 2}})
    assert run_report_row(run)["Stalled Vehicles At Run End"] == 2
