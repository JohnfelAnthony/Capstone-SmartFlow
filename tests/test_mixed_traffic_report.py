"""The mixed-traffic report tool writes every field the acceptance checks read."""
import json

from tools.mixed_traffic_report import QUICK_CASES, main

CASE_FIELDS = {"runtime_s", "max_overlapping_pairs", "max_stuck_junction_vehicles", "max_gridlock_seconds",
               "final_vehicle_conservation_error", "completed", "queue_count_p95", "active_count_p95",
               "front_row_motorcycle_share", "queue_motorcycle_share", "mean_discharge_first_10s"}


def test_quick_report_has_both_cases_and_every_field(tmp_path):
    out = tmp_path/"r.json"
    assert main(["--quick", "--out", str(out)]) == 0
    report = json.loads(out.read_text(encoding="utf-8"))
    assert report["engine_version"] and set(report["cases"]) == {f"{name}@101" for name in QUICK_CASES}
    for case in report["cases"].values():
        assert CASE_FIELDS <= case.keys()
        # Not asserted to be 0: native-5 can overlap vehicles of different movements inside a junction (Task 7 fixes it).
        assert isinstance(case["max_overlapping_pairs"], int)
        assert case["final_vehicle_conservation_error"] == 0
