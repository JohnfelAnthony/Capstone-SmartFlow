"""The validation gate in front of study-site training and final evaluation.

A network is a study site when `data/sites/<id>_mapping.json` exists. Training or evaluating one needs a current,
independent PASS (services.site_validation.validation_gate) for the identical physical model; a filename or a
scenario-level flag is never trusted. `--synthetic-smoke-test` on the command-line tools skips the gate for code checks
and marks the scenario so the artifact cannot be mistaken for study evidence.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

from services import site_validation as sv

ROOT = Path(__file__).resolve().parents[1]


def is_study_site(network_id: str | None, root: Path | None = None) -> bool:
    return bool(network_id) and ((root or ROOT) / "data" / "sites" / f"{network_id}_mapping.json").exists()


def _load_json(path: Path, label: str, reasons: list[str]):
    if not path.exists():
        reasons.append(f"no {label} ({path.name})")
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except ValueError:
        reasons.append(f"{label} ({path.name}) is not valid JSON")
        return None


def study_gate(engine, root: Path | None = None) -> dict:
    """Open only when the newest matching validation report is a current independent PASS."""
    root = root or ROOT
    site = engine.network.id
    reasons: list[str] = []
    mapping = _load_json(root / "data" / "sites" / f"{site}_mapping.json", "site mapping", reasons)
    all_criteria = _load_json(root / "data" / "sites" / "validation_criteria.json", "pre-registered validation criteria", reasons)
    ledger = _load_json(root / "data" / "sites" / f"{site}_ledger.json", "study ledger", reasons)
    criteria = ((all_criteria or {}).get("sites") or {}).get(site)
    if all_criteria is not None:
        try:
            sv.validate_criteria(criteria)
        except ValueError as exc:
            reasons.append(f"criteria for {site} are unusable: {exc}")
            criteria = None
    reports = sorted((root / "docs" / "reports").glob(f"site-validation-{site}-validation-*.json"), reverse=True)
    if not reports:
        reasons.append("no independent validation report")
    if reasons or mapping is None or criteria is None or ledger is None:
        return {"open": False, "reasons": reasons}
    metadata = engine.experiment_metadata()
    identity = sv.current_identity(engine_version=metadata["engine_version"], network_sha256=engine.network.fingerprint,
                                   site_calibration_sha256=metadata["site_calibration_sha256"], mapping=mapping, criteria=criteria)
    newest: dict | None = None
    for path in reports:
        result = sv.validation_gate(json.loads(path.read_text(encoding="utf-8")), identity, ledger)
        if result["open"]:
            return result
        newest = newest or {"open": False, "reasons": [f"newest report {path.name}: {reason}" for reason in result["reasons"]]}
    return newest


def require_study_gate(engine, root: Path | None = None) -> None:
    if not is_study_site(engine.network.id, root):
        return
    result = study_gate(engine, root)
    if not result["open"]:
        raise ValueError(f"Study-site work on {engine.network.id} requires an open independent validation gate: " + "; ".join(result["reasons"]))


def gate_study_scenario(snapshot: dict, *, smoke: bool = False) -> dict:
    """Gate a training/evaluation scenario snapshot; a smoke run is allowed but marked."""
    network_id = snapshot.get("network_id") or snapshot.get("intersection_id")
    if not is_study_site(network_id):
        return snapshot
    if smoke:
        print(f"SYNTHETIC SMOKE TEST on study site {network_id}: a code check, not study evidence; the artifact is marked.", file=sys.stderr)
        return {**snapshot, "synthetic_smoke_test": True}
    from simulation.network_registry import engine_for_scenario
    require_study_gate(engine_for_scenario(snapshot, seed=101))
    return snapshot
