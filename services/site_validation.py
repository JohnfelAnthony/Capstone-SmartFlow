"""Observed-versus-simulated validation of a no-signal site and the gate that guards training (design 0.15).

Rules this module enforces:
- the same measure definitions apply to observed and simulated data;
- missing, non-finite or insufficient evidence is INCONCLUSIVE, never PASS and never replaced by zero;
- a safety failure, a rejected first-come hypothesis (with enough evidence) or an out-of-tolerance measure is FAIL;
- a pass opens the gate only for the identical physical model and protocol, on a recording that stayed independent.
"""
from __future__ import annotations

import hashlib
import json
import math
import subprocess
import uuid
from datetime import datetime, timezone
from pathlib import Path

DEVELOPMENT_SEEDS = range(101, 111)
SAFETY_FIELDS = ("overlaps", "stuck_junction_vehicles", "gridlock_seconds", "vehicle_conservation_error")
TOLERANCE_MEASURES = ("queue", "discharge", "travel_time", "arrival_order_share")
MODEL_IDENTITY_KEYS = ("engine_version", "engine_content_sha256", "network_sha256", "site_calibration_sha256",
                       "mapping_sha256", "criteria_sha256", "protocol")
PASS, FAIL, INCONCLUSIVE = "PASS", "FAIL", "INCONCLUSIVE"


def _finite(value) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)


def _canonical_sha256(value) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()


def criteria_sha256(criteria: dict) -> str:
    return _canonical_sha256(criteria)


def engine_content_sha256() -> str:
    """Hash of the simulation source, so any code change makes an earlier pass stale."""
    digest = hashlib.sha256()
    for path in sorted((Path(__file__).resolve().parents[1] / "simulation").glob("*.py")):
        digest.update(path.name.encode("utf-8"))
        digest.update(path.read_bytes())
    return digest.hexdigest()


def validate_criteria(criteria: dict) -> dict:
    """Refuse criteria that do not declare every rule up front (design 0.15 'Pre-registration')."""
    if not isinstance(criteria, dict):
        raise ValueError("Criteria must be an object")
    seeds = criteria.get("development_seeds")
    if (not isinstance(seeds, list) or len(set(seeds)) < 5 or len(set(seeds)) != len(seeds)
            or any(isinstance(seed, bool) or not isinstance(seed, int) or seed not in DEVELOPMENT_SEEDS for seed in seeds)):
        raise ValueError("development_seeds must list at least five distinct seeds from 101-110")
    tolerances = criteria.get("tolerances")
    if not isinstance(tolerances, dict) or set(tolerances) != set(TOLERANCE_MEASURES):
        raise ValueError(f"tolerances must declare exactly: {', '.join(TOLERANCE_MEASURES)}")
    for name, tolerance in tolerances.items():
        if not (isinstance(tolerance, dict) and len(tolerance) == 1 and next(iter(tolerance)) in {"abs", "rel"}
                and _finite(next(iter(tolerance.values()))) and next(iter(tolerance.values())) >= 0):
            raise ValueError(f"tolerance for {name} must be exactly one of {{\"abs\": x}} or {{\"rel\": r}} with x, r >= 0")
    for key in ("pair_window_s", "queue_sample_interval_s", "discharge_bin_s"):
        if not _finite(criteria.get(key)) or criteria[key] <= 0:
            raise ValueError(f"{key} must be a positive number")
    if not _finite(criteria.get("tie_tolerance_s")) or not 0 <= criteria["tie_tolerance_s"] < criteria["pair_window_s"]:
        raise ValueError("tie_tolerance_s must be at least 0 and below pair_window_s")
    if not _finite(criteria.get("stopped_speed_mps")) or criteria["stopped_speed_mps"] < 0:
        raise ValueError("stopped_speed_mps must be a non-negative number")
    if not _finite(criteria.get("arrival_order_share_min")) or not 0 < criteria["arrival_order_share_min"] <= 1:
        raise ValueError("arrival_order_share_min must be in (0, 1]")
    if not _finite(criteria.get("max_unfinished_share")) or not 0 <= criteria["max_unfinished_share"] <= 1:
        raise ValueError("max_unfinished_share must be in [0, 1]")
    if isinstance(criteria.get("min_order_pairs"), bool) or not isinstance(criteria.get("min_order_pairs"), int) or criteria["min_order_pairs"] < 1:
        raise ValueError("min_order_pairs must be a whole number of at least 1")
    minimums = criteria.get("min_samples")
    if not isinstance(minimums, dict) or set(minimums) != {"queue", "discharge", "travel_time"} or any(
            isinstance(value, bool) or not isinstance(value, int) or value < 1 for value in minimums.values()):
        raise ValueError("min_samples must give a whole number of at least 1 for queue, discharge and travel_time")
    approaches = criteria.get("approaches")
    if not isinstance(approaches, list) or not approaches or any(not isinstance(item, str) or not item for item in approaches):
        raise ValueError("approaches must list the boundary id of every approach to validate")
    return criteria


def _within(simulated: float, observed: float, tolerance: dict) -> bool:
    if "abs" in tolerance:
        return abs(simulated - observed) <= tolerance["abs"]
    return abs(simulated - observed) <= tolerance["rel"] * abs(observed)


def check_validation(observed: dict, simulated: dict, criteria: dict) -> dict:
    """Compare observed and simulated measures under pre-registered criteria."""
    validate_criteria(criteria)
    failures: list[str] = []
    insufficient: list[str] = []
    comparisons: dict = {"queue": {}, "discharge": {}, "travel_time": {}, "arrival_order": {}}
    tolerances, minimums = criteria["tolerances"], criteria["min_samples"]

    def compare(group, key, name, sim_value, obs_value, tolerance):
        if not (_finite(sim_value) and _finite(obs_value)):
            insufficient.append(f"{name}: a value is missing or not finite")
            comparisons[group][key] = {"observed": obs_value, "simulated": sim_value, "within": None}
            return
        within = _within(sim_value, obs_value, tolerance)
        comparisons[group][key] = {"observed": obs_value, "simulated": sim_value, "tolerance": tolerance, "within": within}
        if not within:
            failures.append(f"{name}: simulated {sim_value:g} vs observed {obs_value:g} is outside {tolerance}")

    for approach in criteria["approaches"]:
        obs_queue, sim_queue = observed.get("queue", {}).get(approach), simulated.get("queue", {}).get(approach)
        if obs_queue is None or sim_queue is None:
            insufficient.append(f"queue {approach}: no measure for this approach")
        elif not (_finite(obs_queue.get("samples")) and obs_queue["samples"] >= minimums["queue"]):
            insufficient.append(f"queue {approach}: {obs_queue.get('samples')} complete samples, {minimums['queue']} required")
        else:
            compare("queue", approach, f"queue {approach}", sim_queue.get("value"), obs_queue.get("value"), tolerances["queue"])
        obs_bins, sim_bins = observed.get("discharge", {}).get(approach, {}), simulated.get("discharge", {}).get(approach, {})
        usable = {index: item for index, item in obs_bins.items() if item.get("complete")}
        if len(usable) < minimums["discharge"] or len(usable) < len(obs_bins):
            insufficient.append(f"discharge {approach}: {len(usable)} complete bins of {len(obs_bins)}, all of at least {minimums['discharge']} required")
        for index, item in usable.items():
            compare("discharge", f"{approach}/{index}", f"discharge {approach} bin {index}", (sim_bins.get(index) or {}).get("value"), item.get("value"), tolerances["discharge"])

    obs_travel, sim_travel = observed.get("travel_time") or {}, simulated.get("travel_time") or {}
    total = (obs_travel.get("count") or 0) + (obs_travel.get("unfinished") or 0)
    if not obs_travel.get("complete") or (obs_travel.get("count") or 0) < minimums["travel_time"]:
        insufficient.append(f"travel time: {obs_travel.get('count')} completed trips, {minimums['travel_time']} required, with complete line coverage")
    elif total and obs_travel["unfinished"] / total > criteria["max_unfinished_share"]:
        insufficient.append(f"travel time: {obs_travel['unfinished']} of {total} cohort vehicles unfinished, above {criteria['max_unfinished_share']:g}")
    else:
        compare("travel_time", "mean", "mean travel time", sim_travel.get("mean"), obs_travel.get("mean"), tolerances["travel_time"])

    obs_order, sim_order = observed.get("arrival_order") or {}, simulated.get("arrival_order") or {}
    hypothesis_ok = None
    minimum_pairs = criteria["min_order_pairs"]
    if (obs_order.get("eligible") or 0) < minimum_pairs:
        insufficient.append(f"arrival order: {obs_order.get('eligible') or 0} observed eligible pairs, {minimum_pairs} required")
    else:
        hypothesis_ok = _finite(obs_order.get("share")) and obs_order["share"] >= criteria["arrival_order_share_min"]
        if not hypothesis_ok:
            failures.append(f"arrival order: observed share {obs_order.get('share')} is below the first-come hypothesis threshold {criteria['arrival_order_share_min']}")
        if (sim_order.get("eligible") or 0) < minimum_pairs:
            insufficient.append(f"arrival order: {sim_order.get('eligible') or 0} simulated eligible pairs, {minimum_pairs} required")
        else:
            compare("arrival_order", "share", "arrival-order share", sim_order.get("share"), obs_order.get("share"), tolerances["arrival_order_share"])

    safety = simulated.get("safety")
    safety_ok = False
    if not isinstance(safety, dict) or any(not _finite(safety.get(field)) for field in SAFETY_FIELDS):
        insufficient.append("safety: overlaps, stuck vehicles, gridlock time and conservation error were not all measured")
    else:
        broken = [f"{field}={safety[field]:g}" for field in SAFETY_FIELDS if safety[field] != 0]
        safety_ok = not broken
        if broken:
            failures.append("safety: " + ", ".join(broken))

    status = FAIL if failures else INCONCLUSIVE if insufficient else PASS
    return {"status": status, "passed": status == PASS, "safety_ok": safety_ok, "hypothesis_ok": hypothesis_ok,
            "reasons": [*failures, *insufficient], "comparisons": comparisons}


def _moment(value):
    try:
        parsed = datetime.fromisoformat(str(value))
    except ValueError:
        return None
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)


def validation_gate(report: dict, current_identity: dict, ledger: dict) -> dict:
    """Open only for a current, independent PASS of the same physical model and protocol."""
    reasons: list[str] = []
    identity = report.get("identity") or {}
    if report.get("purpose") != "validation":
        reasons.append(f"the report's purpose is '{report.get('purpose')}', not an independent validation")
    if report.get("status") != PASS:
        reasons.append(f"the report's status is {report.get('status')}, not PASS")
    for key in MODEL_IDENTITY_KEYS:
        if identity.get(key) != current_identity.get(key):
            reasons.append(f"stale: {key} changed since the report")
    ledger = ledger or {}
    held_out = ledger.get("held_out") or {}
    recording = held_out.get("recording")
    if not ledger.get("criteria_commit"):
        reasons.append("missing independence evidence: the ledger records no criteria commit")
    if not ledger.get("criteria_sha256") or ledger.get("criteria_sha256") != identity.get("criteria_sha256"):
        reasons.append("missing independence evidence: the ledger's criteria hash does not match the report")
    if not held_out.get("manifest_sha256") or held_out.get("manifest_sha256") != identity.get("revision_manifest_sha256"):
        reasons.append("missing independence evidence: the nominated held-out recording is not the one validated")
    if recording in (ledger.get("development_recordings") or []):
        reasons.append(f"the recording '{recording}' was used for development, so it is not held out")
    if recording in (ledger.get("informed_by") or []):
        reasons.append(f"the model or criteria were informed by the recording '{recording}'; it is not independent")
    frozen, first_access = _moment(ledger.get("frozen_at")), _moment(held_out.get("first_outcome_access_at"))
    if frozen is None or first_access is None:
        reasons.append("missing independence evidence: freeze time or first outcome-access time is not recorded")
    else:
        if first_access <= frozen:
            reasons.append("the held-out outcomes were first accessed before the criteria and model were frozen")
        for access in ledger.get("accesses") or []:
            moment = _moment(access.get("at"))
            if access.get("recording") == recording and (moment is None or moment <= frozen):
                reasons.append("the held-out recording was accessed before the freeze")
                break
    return {"open": not reasons, "reasons": reasons}


def require_validation_gate(report: dict, current_identity: dict, ledger: dict) -> None:
    """Raise with every reason when the gate is closed; used by study training and final evaluation."""
    result = validation_gate(report, current_identity, ledger)
    if not result["open"]:
        raise ValueError("The validation gate is closed: " + "; ".join(result["reasons"]))


def new_report_id() -> str:
    return f"{datetime.now(timezone.utc):%Y%m%dT%H%M%S%fZ}-{uuid.uuid4().hex[:8]}"


def write_report(report: dict, directory: Path) -> Path:
    """Persist one attempt under a unique id; an earlier attempt, even the same day's, is never overwritten."""
    report_id = report.get("report_id") or new_report_id()
    report = {**report, "report_id": report_id}
    path = Path(directory) / f"site-validation-{report['site']}-{report['purpose']}-{report_id}.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "x", encoding="utf-8") as handle:
        json.dump(report, handle, indent=2, sort_keys=True)
    return path


def method_protocol(criteria: dict, mapping: dict) -> dict:
    """The measurement method a pass is valid for; the recording's own times are recorded separately as the window."""
    keys = ("queue_sample_interval_s", "discharge_bin_s", "stopped_speed_mps", "pair_window_s", "tie_tolerance_s")
    return {**{key: criteria[key] for key in keys}, "lead_out_s": float(mapping["lead_out_s"]), "initialization": mapping.get("initialization")}


def current_identity(*, engine_version: str, network_sha256: str, site_calibration_sha256: str, mapping: dict, criteria: dict) -> dict:
    """The physical model and protocol a validation applies to; the gate compares this with a report's identity."""
    return {"engine_version": engine_version, "engine_content_sha256": engine_content_sha256(), "network_sha256": network_sha256,
            "site_calibration_sha256": site_calibration_sha256, "mapping_sha256": _canonical_sha256(mapping),
            "criteria_sha256": criteria_sha256(criteria), "protocol": method_protocol(criteria, mapping)}


def _file_sha256(path: Path) -> str | None:
    return hashlib.sha256(path.read_bytes()).hexdigest() if path.exists() else None


def _source_revision() -> str | None:
    try:
        return subprocess.run(["git", "rev-parse", "HEAD"], cwd=Path(__file__).resolve().parents[1], capture_output=True, text=True, timeout=10, check=True).stdout.strip() or None
    except (OSError, subprocess.SubprocessError):
        return None


def run_validation(*, scenario: dict, revision_dir: Path, mapping: dict, criteria: dict, purpose: str, origin_s: float, start_s: float, end_s: float,
                   reports_dir: Path, ledger: dict | None = None, engine_factory=None) -> tuple[dict, Path]:
    """Measure the video and the no-signal simulation the same way, decide, and keep the attempt as an immutable report.

    `purpose` is "calibration" (development data) or "validation" (the nominated untouched recording). Only a validation
    PASS whose ledger proves independence can open the training gate.
    """
    from services.site_measures import observed_measures
    from services.site_simulation import simulated_measures
    if purpose not in {"calibration", "validation"}:
        raise ValueError("purpose must be calibration or validation")
    validate_criteria(criteria)
    revision_dir = Path(revision_dir)
    observed = observed_measures(revision_dir, mapping, start_s=start_s, end_s=end_s, criteria=criteria)
    simulated = simulated_measures(scenario, mapping, seeds=criteria["development_seeds"], origin_s=origin_s, start_s=start_s, end_s=end_s,
                                   criteria=criteria, engine_factory=engine_factory)
    decision = check_validation(observed, simulated, criteria)
    model = simulated["model_identity"]
    identity = {**current_identity(engine_version=model["engine_version"], network_sha256=model["network_sha256"],
                                   site_calibration_sha256=model["site_calibration_sha256"], mapping=mapping, criteria=criteria),
                "source_revision": _source_revision(), "revision_manifest_sha256": _file_sha256(revision_dir / "manifest.json"), "reviewed_bins_sha256": _file_sha256(revision_dir / "reviewed_bins.csv"),
                "queue_samples_sha256": _file_sha256(revision_dir / "queue_samples.csv"), "priority_review_sha256": _file_sha256(revision_dir / "priority_review.csv"),
                "demand_sha256": model["demand_sha256"], "seeds": model["seeds"],
                "window": {"origin_s": float(origin_s), "start_s": float(start_s), "end_s": float(end_s)}}
    report = {"schema_version": 1, "site": mapping["network_id"], "purpose": purpose, "status": decision["status"], "report_id": new_report_id(),
              "decision": decision, "observed": observed, "simulated": simulated, "identity": identity, "ledger": ledger or None}
    report["gate"] = validation_gate(report, identity, ledger or {})
    return report, write_report(report, reports_dir)

from services.site_measures import classify_pairs, observed_measures  # noqa: E402,F401  (the shared measure definitions)
from services.site_simulation import simulated_measures  # noqa: E402,F401
