"""The validation gate in front of study-site training and evaluation (design 0.15 'Gate validity', plan Task 26)."""
import json
import subprocess
import sys
from pathlib import Path

import pytest

from services import site_validation as sv
from services.study_gate import is_study_site, require_study_gate, study_gate
from simulation.network_registry import engine_for_scenario, load_registered_network

ROOT = Path(__file__).resolve().parents[1]
SITE = "tagum_site_a"
CRITERIA = {"development_seeds": [101, 102, 103, 104, 105], "tolerances": {"queue": {"abs": 2.0}, "discharge": {"rel": 0.2}, "travel_time": {"rel": 0.25},
            "arrival_order_share": {"abs": 0.15}}, "arrival_order_share_min": 0.8, "pair_window_s": 10.0, "tie_tolerance_s": 0.5, "min_order_pairs": 3,
            "min_samples": {"queue": 4, "discharge": 1, "travel_time": 5}, "queue_sample_interval_s": 30.0, "stopped_speed_mps": 0.5,
            "discharge_bin_s": 900.0, "max_unfinished_share": 0.2, "approaches": ["boundary_0"]}
MAPPING = {"network_id": SITE, "lead_out_s": 120, "locations": {}, "initialization": {"state": "empty", "verified_by": "T", "evidence": "fixture"}}
LEDGER = {"criteria_commit": "abc123", "frozen_at": "2026-11-05T09:00:00+08:00", "held_out": {"recording": "day3", "manifest_sha256": "h3",
          "first_outcome_access_at": "2026-11-06T10:00:00+08:00"}, "development_recordings": ["day1"], "informed_by": ["day1"], "accesses": []}


def site_engine(**config):
    return engine_for_scenario({"network_id": SITE, "engine_config": config}, seed=101)


def lay_out(root: Path, engine, *, status="PASS", purpose="validation"):
    (root / "data" / "sites").mkdir(parents=True)
    (root / "docs" / "reports").mkdir(parents=True)
    (root / "data" / "sites" / f"{SITE}_mapping.json").write_text(json.dumps(MAPPING))
    (root / "data" / "sites" / "validation_criteria.json").write_text(json.dumps({"schema_version": 1, "sites": {SITE: CRITERIA}}))
    identity = sv.current_identity(engine_version=engine.experiment_metadata()["engine_version"], network_sha256=engine.network.fingerprint,
                                   site_calibration_sha256=engine.experiment_metadata()["site_calibration_sha256"], mapping=MAPPING, criteria=CRITERIA)
    (root / "data" / "sites" / f"{SITE}_ledger.json").write_text(json.dumps({**LEDGER, "criteria_sha256": identity["criteria_sha256"]}))
    sv.write_report({"site": SITE, "purpose": purpose, "status": status, "identity": {**identity, "revision_manifest_sha256": "h3"}}, root / "docs" / "reports")


def test_study_sites_are_the_networks_with_a_mapping_file_and_defaults_are_not():
    assert is_study_site(SITE) and is_study_site("tagum_site_b")
    assert not is_study_site("tagum_network") and not is_study_site("tagum_network_2j")


def test_default_networks_need_no_gate():
    require_study_gate(engine_for_scenario({"network_id": "tagum_network", "engine_config": {}}))


def test_a_study_site_without_evidence_is_refused_with_the_missing_pieces_named():
    with pytest.raises(ValueError, match="independent validation gate.*tagum_site_a"):
        require_study_gate(site_engine())
    reasons = study_gate(site_engine())["reasons"]
    assert any("criteria" in reason for reason in reasons)


def test_a_current_independent_pass_opens_the_gate(tmp_path):
    engine = site_engine()
    lay_out(tmp_path, engine)
    assert study_gate(engine, root=tmp_path) == {"open": True, "reasons": []}


def test_changing_the_site_calibration_makes_the_pass_stale(tmp_path):
    lay_out(tmp_path, site_engine())
    from simulation.scenario_config import VEHICLE_TYPES
    changed = site_engine(site_calibration={"schema_version": 1, "network_id": SITE, "first_come_approach_speed_mps": 5.0, "approach_zone_m": 30.0,
                          "turn_speed_mps": 5.0, "class_speed_factors": {name: spec["speed_factor"] for name, spec in VEHICLE_TYPES.items()}})
    result = study_gate(changed, root=tmp_path)
    assert result["open"] is False and any("stale" in reason and "site_calibration_sha256" in reason for reason in result["reasons"])


def test_a_calibration_or_failed_report_does_not_open_the_gate(tmp_path):
    engine = site_engine()
    lay_out(tmp_path, engine, status="FAIL")
    assert study_gate(engine, root=tmp_path)["open"] is False


def test_the_newest_passing_validation_counts_and_an_older_failure_is_kept_as_history(tmp_path):
    engine = site_engine()
    lay_out(tmp_path, engine, status="FAIL")
    identity = json.loads(next((tmp_path / "docs" / "reports").glob("*.json")).read_text())["identity"]
    sv.write_report({"site": SITE, "purpose": "validation", "status": "PASS", "identity": identity}, tmp_path / "docs" / "reports")
    assert study_gate(engine, root=tmp_path)["open"] is True
    assert len(list((tmp_path / "docs" / "reports").glob("*.json"))) == 2


def run_cli(*arguments):
    return subprocess.run([sys.executable, *arguments], cwd=ROOT, capture_output=True, text=True, timeout=120)


def site_scenario(tmp_path):
    site = load_registered_network(SITE)
    path = tmp_path / "scenario.json"
    path.write_text(json.dumps({"network_id": site.id, "network_sha256": site.fingerprint, "name": "Synthetic", "engine_config": {"traffic_density": "low"}}))
    return path


def test_command_line_training_of_a_study_site_is_refused_without_the_gate(tmp_path):
    result = run_cli("tools/train_ql.py", "--scenario-file", str(site_scenario(tmp_path)), "--episodes", "1", "--warmup-seconds", "0",
                     "--evaluation-seconds", "5", "--max-steps-per-episode", "1", "--checkpoint-every", "0", "--skip-db", "--output", str(tmp_path / "m.json"))
    assert result.returncode != 0 and "independent validation gate" in result.stderr + result.stdout
    assert not (tmp_path / "m.json").exists()


def test_the_synthetic_smoke_flag_runs_and_marks_the_artifact_as_not_study_evidence(tmp_path):
    result = run_cli("tools/train_ql.py", "--scenario-file", str(site_scenario(tmp_path)), "--episodes", "1", "--warmup-seconds", "0",
                     "--evaluation-seconds", "5", "--max-steps-per-episode", "1", "--checkpoint-every", "0", "--skip-db", "--synthetic-smoke-test",
                     "--output", str(tmp_path / "m.json"))
    assert result.returncode == 0, result.stderr + result.stdout
    assert json.loads((tmp_path / "m.json").read_text())["metadata"]["scenario"]["synthetic_smoke_test"] is True
    assert "SYNTHETIC SMOKE TEST" in result.stdout + result.stderr


def test_command_line_evaluation_of_a_study_site_is_refused_without_the_gate(tmp_path):
    result = run_cli("tools/evaluate_controllers.py", "--scenario-file", str(site_scenario(tmp_path)), "--controllers", "fixed-time", "--seeds", "101",
                     "--duration-seconds", "5", "--warmup-seconds", "0", "--skip-db")
    assert result.returncode != 0
