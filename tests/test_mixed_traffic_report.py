"""The mixed-traffic report tool writes every field the acceptance checks read."""
import json

from tools.mixed_traffic_report import QUICK_CASES, main

CASE_FIELDS = {"runtime_s", "max_overlapping_pairs", "max_stuck_junction_vehicles", "max_stalled_vehicles", "max_gridlock_seconds",
               "final_vehicle_conservation_error", "completed", "queue_count_p95", "active_count_p95",
               "front_row_motorcycle_share", "queue_motorcycle_share", "mean_discharge_first_10s",
               "network_id", "network_fingerprint", "island_count", "max_island_intrusions", "requested_vehicles",
               "active_vehicles", "pending_vehicles", "dropped_vehicles", "unfinished_vehicles", "longest_completion_gap_s"}


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
        assert case["unfinished_vehicles"] == case["active_vehicles"] + case["pending_vehicles"]
        assert case["requested_vehicles"] == case["completed"] + case["unfinished_vehicles"] + case["dropped_vehicles"]
        if not case["island_count"]:
            assert case["max_island_intrusions"] is None


def test_island_intrusion_counts_bodies_and_touching_edges():
    from tools.mixed_traffic_report import count_island_intrusions
    records = [{"x": 0, "y": 0, "angle": 90, "length": 4, "width": 2}]
    islands = [{"shape": [[1, -1], [3, -1], [3, 1], [1, 1]]},
               {"shape": [[2, -1], [4, -1], [4, 1], [2, 1]]},
               {"shape": [[10, 10], [11, 10], [11, 11], [10, 11]]}]
    assert count_island_intrusions(records, islands) == 2
    assert count_island_intrusions(records, []) == 0


def test_full_determinism_covers_every_seed_and_requested_duration(tmp_path, monkeypatch):
    import tools.mixed_traffic_report as report_tool
    calls = []
    monkeypatch.setattr(report_tool, "determinism_equal_case", lambda name, seconds, seed: calls.append((name, seconds, seed)) or True)
    monkeypatch.setattr(report_tool, "run_case", lambda *args, **kwargs: {})
    out = tmp_path / "report.json"
    assert main(["--only", "siteB-medium-nosignal", "--seconds", "60", "--seeds", "101,102", "--acceptance-determinism", "--out", str(out)]) == 0
    report = json.loads(out.read_text(encoding="utf-8"))
    assert calls == [("siteB-medium-nosignal", 60., 101), ("siteB-medium-nosignal", 60., 102)]
    assert report["determinism_full"] == {"siteB-medium-nosignal@101": {"seconds": 60., "equal": True}, "siteB-medium-nosignal@102": {"seconds": 60., "equal": True}}


def test_report_never_replaces_existing_evidence(tmp_path):
    import pytest
    out = tmp_path / "report.json"
    out.write_text("prior evidence", encoding="utf-8")
    with pytest.raises(SystemExit):
        main(["--quick", "--out", str(out)])
    assert out.read_text(encoding="utf-8") == "prior evidence"


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


def test_site_a_closure_cases_close_the_west_inbound_piece_under_static_routing():
    from tools.mixed_traffic_report import CASES, case_options
    for density in ("medium", "high"):
        for control in ("nosignal", "fixed"):
            plain, closed = f"siteA-static-{density}-{control}", f"siteA-static-{density}-{control}-closure"
            assert CASES[plain][0] == CASES[closed][0] == "siteA"
            assert case_options(plain)[3]["routing_mode"] == case_options(closed)[3]["routing_mode"] == "static"
            assert "events" not in case_options(plain)[3]
            assert case_options(closed)[3]["events"] == [{"time": 300.0, "lane_id": "road2r", "closed": True}, {"time": 1200.0, "lane_id": "road2r", "closed": False}]


def test_a_closure_case_reports_what_the_closure_did():
    from tools.mixed_traffic_report import run_case
    from simulation.scenario_config import TAGUM_PROVISIONAL_MIX
    report = run_case("siteA", "medium", TAGUM_PROVISIONAL_MIX, 60, 101, routing_mode="static",
                      events=[{"time": 5.0, "lane_id": "road2r", "closed": True}])
    for key in ("reroutes", "diverted_vehicles", "closure_blocked_vehicles", "max_closure_held_vehicles", "loop_exits"):
        assert key in report
    assert report["loop_exits"].keys() == {"road6f", "road6r"}
