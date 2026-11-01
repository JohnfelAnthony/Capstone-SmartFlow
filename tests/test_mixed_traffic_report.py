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


def test_site_cases_use_their_networks_and_control():
    from tools.mixed_traffic_report import CASES, case_options
    assert case_options("siteA-high-nosignal")[3]["no_signal"] is True
    assert case_options("siteA-high-fixed")[3].get("no_signal") is not True
    assert CASES["siteB-high-grouped"][0] == "siteB"


def test_every_site_condition_and_demand_has_a_case():
    from tools.mixed_traffic_report import CASES
    expected = {f"{site}-{density}-{control}" for site in ("siteA", "siteB") for density in ("medium", "high") for control in ("nosignal", "fixed", "grouped")}
    assert expected <= set(CASES)
    assert len(expected) == 12


def test_grouped_cases_use_a_webster_plan_for_their_own_demand():
    from tools.mixed_traffic_report import case_options
    options = case_options("siteA-medium-grouped")[3]
    plan = next(iter(options["signal_plans"].values()))
    assert plan["phase_order"] == [["north", "south"], ["east", "west"], "pedestrian"]
    assert len(plan["phase_greens"]) == 3 and all(green > 0 for green in plan["phase_greens"])


def test_a_site_case_runs_briefly_and_reports_every_field():
    from tools.mixed_traffic_report import run_case, case_options
    for name in ("siteA-medium-nosignal", "siteB-medium-grouped"):
        network, density, mix, options = case_options(name)
        result = run_case(network, density, mix, 20.0, 101, **options)
        assert CASE_FIELDS <= result.keys()
        assert result["final_vehicle_conservation_error"] == 0


def test_only_runs_the_named_case_prefixes_without_benchmarks(tmp_path):
    out = tmp_path/"r.json"
    assert main(["--only", "siteA-medium-nosignal", "--seconds", "20", "--seeds", "101", "--out", str(out)]) == 0
    report = json.loads(out.read_text(encoding="utf-8"))
    assert set(report["cases"]) == {"siteA-medium-nosignal@101"} and report["benchmarks"] == {}


def test_a_site_case_reports_equal_determinism_digests(tmp_path):
    out = tmp_path/"r.json"
    assert main(["--only", "siteB-medium-grouped", "--seconds", "20", "--seeds", "101", "--determinism", "--out", str(out)]) == 0
    assert json.loads(out.read_text(encoding="utf-8"))["determinism"] == {"siteB-medium-grouped": True}


def test_a_case_reports_the_queue_distribution_the_ql_bin_rule_needs():
    from tools.mixed_traffic_report import queue_distribution
    values = [0] * 10 + [2, 4, 6, 9, 10, 12, 20, 30]
    result = queue_distribution(values)
    assert result["queue_count_p50"] == 0 and result["queue_count_p75"] == 9 and result["queue_count_p90"] == 20
    assert result["nonzero_samples"] == 8 and result["nonzero_share_above_8"] == 5 / 8
    assert queue_distribution([0, 0])["nonzero_share_above_8"] is None
