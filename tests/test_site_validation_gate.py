"""Validation decision, evidence identity and the gate (plan Task 26, design 0.15). Pure functions: no engine runs."""
import json

import pytest

from services import site_validation as sv

SITE = "tagum_site_a"
APPROACHES = ["boundary_0", "boundary_1"]


def criteria(**changes):
    value = {"development_seeds": [101, 102, 103, 104, 105],
             "tolerances": {"queue": {"abs": 2.0}, "discharge": {"rel": 0.2}, "travel_time": {"rel": 0.25}, "arrival_order_share": {"abs": 0.15}},
             "arrival_order_share_min": 0.8, "pair_window_s": 10.0, "tie_tolerance_s": 0.5, "min_order_pairs": 3,
             "min_samples": {"queue": 4, "discharge": 1, "travel_time": 5}, "queue_sample_interval_s": 30.0, "stopped_speed_mps": 0.5,
             "discharge_bin_s": 900.0, "max_unfinished_share": 0.2, "approaches": APPROACHES}
    return {**value, **changes}


def measures(*, queue=3.0, discharge=50, travel=20.0, share=0.9, eligible=10, samples=6, travel_count=8, unfinished=0, bins=(0,)):
    return {"queue": {name: {"value": queue, "samples": samples} for name in APPROACHES},
            "discharge": {name: {str(index): {"value": discharge, "complete": True} for index in bins} for name in APPROACHES},
            "travel_time": {"mean": travel, "median": travel, "count": travel_count, "unfinished": unfinished, "complete": True},
            "arrival_order": {"eligible": eligible, "respected": round(share * eligible) if eligible else 0,
                              "share": share if eligible else None, "excluded": {}}}


def simulated(**changes):
    return measures(**changes) | {"safety": {"overlaps": 0, "stuck_junction_vehicles": 0, "gridlock_seconds": 0.0, "vehicle_conservation_error": 0}}


def check(observed=None, sim=None, crit=None):
    return sv.check_validation(observed or measures(), sim or simulated(), crit or criteria())


def test_matching_evidence_passes():
    result = check()
    assert (result["status"], result["passed"], result["safety_ok"], result["hypothesis_ok"]) == ("PASS", True, True, True)


def test_tolerance_boundaries_are_inclusive_and_relative_error_at_zero_is_exact():
    assert check(sim=simulated(queue=5.0))["status"] == "PASS"            # |5-3| = 2 <= 2
    assert check(sim=simulated(queue=5.01))["status"] == "FAIL"
    assert check(observed=measures(discharge=0), sim=simulated(discharge=0))["status"] == "PASS"
    assert check(observed=measures(discharge=0), sim=simulated(discharge=1))["status"] == "FAIL"   # rel 0.2 * |0| = 0


@pytest.mark.parametrize("bad", [None, float("nan"), float("inf")])
def test_missing_or_non_finite_values_are_inconclusive_never_pass(bad):
    assert check(sim=simulated(queue=bad))["status"] == "INCONCLUSIVE"
    assert check(observed=measures(travel=bad))["status"] == "INCONCLUSIVE"


def test_insufficient_samples_or_missing_approaches_are_inconclusive():
    assert check(observed=measures(samples=3))["status"] == "INCONCLUSIVE"
    observed = measures()
    del observed["queue"]["boundary_1"]
    assert check(observed=observed)["status"] == "INCONCLUSIVE"
    incomplete = measures()
    incomplete["discharge"]["boundary_0"]["0"]["complete"] = False
    assert check(observed=incomplete)["status"] == "INCONCLUSIVE"
    assert check(observed=measures(travel_count=4))["status"] == "INCONCLUSIVE"


def test_unfinished_cohort_share_above_the_limit_is_inconclusive():
    assert check(observed=measures(unfinished=3, travel_count=8))["status"] == "INCONCLUSIVE"   # 3/11 > 0.2


def test_too_few_eligible_pairs_is_inconclusive_and_does_not_decide_the_hypothesis():
    result = check(observed=measures(eligible=2, share=1.0))
    assert result["status"] == "INCONCLUSIVE" and result["hypothesis_ok"] is None
    assert check(observed=measures(eligible=0))["status"] == "INCONCLUSIVE"


def test_a_failed_arrival_order_hypothesis_with_sufficient_evidence_fails_even_if_simulation_matches():
    result = check(observed=measures(share=0.5, eligible=10), sim=simulated(share=0.5, eligible=10))
    assert (result["status"], result["hypothesis_ok"]) == ("FAIL", False)


def test_arrival_order_share_must_also_match_the_simulation():
    assert check(sim=simulated(share=0.5))["status"] == "FAIL"


@pytest.mark.parametrize("field, value", [("overlaps", 1), ("stuck_junction_vehicles", 1), ("gridlock_seconds", 0.1), ("vehicle_conservation_error", 1)])
def test_every_safety_failure_fails(field, value):
    sim = simulated()
    sim["safety"][field] = value
    result = check(sim=sim)
    assert (result["status"], result["safety_ok"]) == ("FAIL", False)


def test_missing_safety_data_cannot_pass():
    sim = simulated()
    del sim["safety"]
    assert check(sim=sim)["status"] == "INCONCLUSIVE"


def test_a_definite_failure_outranks_missing_evidence_elsewhere():
    assert check(observed=measures(travel_count=1), sim=simulated(queue=50.0))["status"] == "FAIL"


@pytest.mark.parametrize("change", [{"tolerances": {"queue": {"abs": 1.0}}}, {"development_seeds": [1, 2, 3]}, {"approaches": []},
                                    {"tolerances": {**criteria()["tolerances"], "queue": {"abs": 1.0, "rel": 0.1}}}, {"pair_window_s": 0}])
def test_incomplete_criteria_are_refused(change):
    with pytest.raises(ValueError):
        sv.validate_criteria(criteria(**change))


def test_criteria_hash_changes_with_any_declared_value():
    assert sv.criteria_sha256(criteria()) == sv.criteria_sha256(criteria())
    assert sv.criteria_sha256(criteria()) != sv.criteria_sha256(criteria(pair_window_s=12.0))


IDENTITY = {"engine_version": "native-6", "engine_content_sha256": "e1", "network_sha256": "n1", "site_calibration_sha256": "c1",
            "mapping_sha256": "m1", "criteria_sha256": "k1", "protocol": {"origin_s": 0.0, "start_s": 120.0, "end_s": 1020.0, "lead_out_s": 120.0}}
LEDGER = {"criteria_sha256": "k1", "criteria_commit": "abc123", "frozen_at": "2026-11-05T09:00:00+08:00",
          "held_out": {"recording": "day3", "manifest_sha256": "h3", "first_outcome_access_at": "2026-11-06T10:00:00+08:00"},
          "development_recordings": ["day1"], "informed_by": ["day1"], "accesses": [{"recording": "day1", "at": "2026-11-01T09:00:00+08:00", "purpose": "calibration"}]}


def report(**changes):
    value = {"status": "PASS", "purpose": "validation", "site": SITE, "report_id": "20261106T020000Z-ab12cd34",
             "identity": {**IDENTITY, "revision_manifest_sha256": "h3"}}
    return {**value, **changes}


def gate(rep=None, identity=None, ledger=None):
    return sv.validation_gate(rep or report(), identity or IDENTITY, LEDGER if ledger is None else ledger)


def test_a_current_independent_pass_opens_the_gate():
    assert gate() == {"open": True, "reasons": []}


@pytest.mark.parametrize("key", ["engine_version", "engine_content_sha256", "network_sha256", "site_calibration_sha256", "mapping_sha256", "criteria_sha256", "protocol"])
def test_any_change_to_the_validated_model_or_protocol_makes_the_pass_stale(key):
    result = gate(identity={**IDENTITY, key: "changed" if key != "protocol" else {**IDENTITY["protocol"], "start_s": 60.0}})
    assert result["open"] is False and any("stale" in reason for reason in result["reasons"])


@pytest.mark.parametrize("rep", [report(status="FAIL"), report(status="INCONCLUSIVE"), report(purpose="calibration")])
def test_only_a_validation_purpose_pass_opens_the_gate(rep):
    assert gate(rep)["open"] is False


def test_a_recording_that_informed_a_revision_is_not_independent():
    ledger = {**LEDGER, "informed_by": ["day1", "day3"]}
    assert any("informed" in reason for reason in gate(ledger=ledger)["reasons"])


def test_a_recording_used_for_development_is_not_held_out():
    ledger = {**LEDGER, "development_recordings": ["day1", "day3"]}
    assert gate(ledger=ledger)["open"] is False


def test_criteria_must_be_frozen_before_any_outcome_was_accessed():
    ledger = {**LEDGER, "held_out": {**LEDGER["held_out"], "first_outcome_access_at": "2026-11-04T10:00:00+08:00"}}
    assert any("before" in reason for reason in gate(ledger=ledger)["reasons"])
    early_access = {**LEDGER, "accesses": [*LEDGER["accesses"], {"recording": "day3", "at": "2026-11-03T09:00:00+08:00", "purpose": "diagnosis"}]}
    assert gate(ledger=early_access)["open"] is False


def test_missing_independence_evidence_closes_the_gate():
    assert gate(ledger={})["open"] is False
    assert gate(ledger={**LEDGER, "criteria_commit": ""})["open"] is False
    assert gate(rep=report(identity={**IDENTITY, "revision_manifest_sha256": "other"}))["open"] is False


def test_the_report_is_written_once_and_never_overwritten(tmp_path):
    first = sv.write_report({"site": SITE, "purpose": "validation", "status": "PASS"}, tmp_path)
    second = sv.write_report({"site": SITE, "purpose": "validation", "status": "FAIL"}, tmp_path)
    assert first != second and first.exists() and second.exists()
    assert json.loads(first.read_text())["status"] == "PASS"
    assert first.name.startswith(f"site-validation-{SITE}-validation-")
