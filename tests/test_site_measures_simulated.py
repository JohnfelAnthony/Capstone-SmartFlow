"""Simulated measures on a synthetic cross, using the same definitions as the observed side (plan Task 26)."""
import pytest

from services import site_validation as sv
from simulation.traffic_engine import TrafficEngine
from tests.mixed_traffic_helpers import junction_network

MAPPING = {"locations": {
    "arrival_w": {"role": "arrival", "boundary": "w", "approach_id": "west", "distance_from_junction_m": 100.0},
    "arrival_n": {"role": "arrival", "boundary": "n", "approach_id": "north", "distance_from_junction_m": 100.0},
    "stop_w": {"role": "stopline", "boundary": "w", "approach_id": "west"}, "stop_n": {"role": "stopline", "boundary": "n", "approach_id": "north"},
    "priority_w": {"role": "priority", "boundary": "w", "approach_id": "west", "distance_from_junction_m": 30.0},
    "priority_n": {"role": "priority", "boundary": "n", "approach_id": "north", "distance_from_junction_m": 30.0},
    "exit_e": {"role": "exit", "boundary": "e", "distance_from_junction_m": 100.0}, "exit_s": {"role": "exit", "boundary": "s", "distance_from_junction_m": 100.0}},
    "lead_out_s": 120.0, "movement_conflicts": {"identity": "v1", "pairs": [["w->e", "n->s"]]}}
CRITERIA = {"queue_sample_interval_s": 30.0, "discharge_bin_s": 50.0, "pair_window_s": 10.0, "tie_tolerance_s": 0.5,
            "stopped_speed_mps": 0.5, "approaches": ["w", "n"], "min_samples": {"queue": 1, "discharge": 1, "travel_time": 1}}


def trip(time_s, source, destination, vehicle_type="car"):
    return {"time": time_s, "source": source, "destination": destination, "vehicle_type": vehicle_type}


def factory(trips):
    def make(seed):
        engine = TrafficEngine(seed=seed, network=junction_network())
        engine.configure(traffic_density="none", pedestrian_density="none", trips=trips, routing_mode="static")
        return engine
    return make


def measure(trips, *, seeds=(101,), origin_s=0.0, start_s=0.0, end_s=100.0, mapping=MAPPING):
    return sv.simulated_measures({}, mapping, seeds=seeds, origin_s=origin_s, start_s=start_s, end_s=end_s, criteria=CRITERIA, engine_factory=factory(trips))


def test_discharge_and_travel_time_use_the_mapped_lines():
    result = measure([trip(1, "w", "e")])
    assert {key: item["value"] for key, item in result["discharge"]["w"].items()} == {"0": 1, "1": 0}
    assert all(item["value"] == 0 for item in result["discharge"]["n"].values())
    travel = result["travel_time"]
    assert (travel["count"], travel["unfinished"], travel["complete"]) == (1, 0, True)
    assert 15 < travel["mean"] < 60


def test_a_vehicle_that_entered_before_the_window_is_kept_and_counted_at_its_stop_line():
    # Entered at 1 s, window starts at 15 s: the engine is never reset, so its later stop-line crossing still counts.
    result = measure([trip(1, "w", "e"), trip(40, "w", "e")], start_s=15.0, end_s=115.0)
    assert sum(item["value"] for item in result["discharge"]["w"].values()) == 2
    assert result["travel_time"]["count"] == 1  # only the vehicle that crossed the arrival line inside the window is in the cohort


def test_a_vehicle_that_cannot_leave_is_reported_as_unfinished():
    result = measure([trip(1, "w", "e"), trip(2, "w", "e")], end_s=20.0)
    assert result["travel_time"]["count"] + result["travel_time"]["unfinished"] == 2


def test_queue_is_sampled_at_the_shared_instants():
    result = measure([trip(1, "w", "e")], end_s=100.0)
    assert result["queue"]["w"]["samples"] == 4 and result["queue"]["n"]["samples"] == 4  # 0, 30, 60, 90 s
    assert result["queue"]["n"]["value"] == 0.0


def test_the_earlier_arrival_enters_first_under_first_come():
    result = measure([trip(1, "w", "e"), trip(4, "n", "s")])
    order = result["arrival_order"]
    assert (order["eligible"], order["respected"], order["share"]) == (1, 1, 1.0)


def test_safety_measures_are_reported_and_clean_on_a_light_load():
    safety = measure([trip(1, "w", "e"), trip(4, "n", "s")])["safety"]
    assert safety == {"overlaps": 0, "stuck_junction_vehicles": 0, "gridlock_seconds": 0.0, "vehicle_conservation_error": 0}


def test_every_declared_seed_is_run_and_reported_and_the_result_is_reproducible():
    trips = [trip(1, "w", "e"), trip(4, "n", "s")]
    first = measure(trips, seeds=(101, 102, 103))
    assert [item["seed"] for item in first["per_seed"]] == [101, 102, 103]
    assert first == measure(trips, seeds=(101, 102, 103))


def test_the_resolved_model_identity_is_recorded():
    identity = measure([trip(1, "w", "e")])["model_identity"]
    assert identity["controller"] == "no-signal" and identity["seeds"] == [101]
    assert identity["site_calibration_sha256"] and identity["network_sha256"] and identity["engine_version"]


def test_final_seeds_are_refused_in_development_runs():
    with pytest.raises(ValueError, match="development seeds"):
        measure([trip(1, "w", "e")], seeds=(201,))


def test_a_validation_attempt_writes_an_immutable_report_with_the_full_evidence_identity(tmp_path):
    from tests.test_site_measures_observed import build, MAPPING as OBSERVED_MAPPING, CRITERIA as OBSERVED_CRITERIA, START, END
    folder = build(tmp_path)
    criteria = {**sv_criteria(), "approaches": ["w", "n"]}
    kwargs = dict(scenario={}, revision_dir=folder, mapping=with_exit_distances({**OBSERVED_MAPPING, "network_id": "test_cross"}), criteria=criteria, purpose="calibration",
                  origin_s=0.0, start_s=START, end_s=END, reports_dir=tmp_path / "reports", engine_factory=factory([trip(1, "w", "e")]))
    first, first_path = sv.run_validation(**kwargs)
    second, second_path = sv.run_validation(**kwargs)
    assert first["status"] == "INCONCLUSIVE" and first["purpose"] == "calibration" and first_path != second_path
    identity = first["identity"]
    for key in ("engine_version", "engine_content_sha256", "network_sha256", "site_calibration_sha256", "mapping_sha256", "criteria_sha256",
                "revision_manifest_sha256", "reviewed_bins_sha256", "demand_sha256", "seeds", "protocol"):
        assert identity[key], key
    assert identity["window"] == {"origin_s": 0.0, "start_s": START, "end_s": END}
    assert identity["protocol"]["lead_out_s"] == 120.0 and identity["protocol"]["queue_sample_interval_s"] == 30.0
    assert first["gate"]["open"] is False  # a calibration attempt never opens the training gate
    assert sorted(tmp_path.joinpath("reports").glob("site-validation-test_cross-calibration-*.json")) == sorted([first_path, second_path])


def sv_criteria():
    return {"development_seeds": [101, 102, 103, 104, 105], "tolerances": {"queue": {"abs": 2.0}, "discharge": {"rel": 0.2}, "travel_time": {"rel": 0.25},
            "arrival_order_share": {"abs": 0.15}}, "arrival_order_share_min": 0.8, "pair_window_s": 10.0, "tie_tolerance_s": 0.5, "min_order_pairs": 3,
            "min_samples": {"queue": 4, "discharge": 1, "travel_time": 5}, "queue_sample_interval_s": 30.0, "stopped_speed_mps": 0.5,
            "discharge_bin_s": 300.0, "max_unfinished_share": 0.2, "approaches": ["w", "n"]}


def test_the_command_line_refuses_final_seeds_and_a_missing_purpose(tmp_path, capsys):
    import json
    from tools import validate_site
    criteria_file = tmp_path / "criteria.json"
    criteria_file.write_text(json.dumps({"schema_version": 1, "sites": {"test_cross": {**sv_criteria(), "development_seeds": [201, 202, 203, 204, 205]}}}))
    with pytest.raises(SystemExit) as refused:
        validate_site.main(["--scenario-id", "1", "--revision", str(tmp_path), "--mapping", str(tmp_path / "m.json"), "--criteria", str(criteria_file),
                            "--purpose", "validation", "--origin-s", "0", "--start-s", "0", "--end-s", "100", "--site", "test_cross"])
    assert refused.value.code != 0
    assert "development_seeds" in capsys.readouterr().err
    with pytest.raises(SystemExit):
        validate_site.main(["--scenario-id", "1"])


def with_exit_distances(mapping):
    import copy
    mapping = copy.deepcopy(mapping)
    for item in mapping["locations"].values():
        if item["role"] == "exit":
            item["distance_from_junction_m"] = 100.0
    return mapping
