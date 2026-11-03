"""Preview retained, reviewed observations using the native conversion rules."""
from __future__ import annotations

from pathlib import Path
import json
import os
import uuid

from services.field_observer_import import convert_revision
from services.reviewed_revision_store import revision_path
from simulation.network_registry import load_registered_network


def preview_conversion(*, study_root: Path, revision_id: str, mapping: dict,
                       origin_s: float, start_s: float, end_s: float) -> dict:
    network, result = _convert(study_root, revision_id, mapping, origin_s, start_s, end_s)
    return {"revision_id": revision_id, "network_id": network.id, "network_sha256": network.fingerprint,
            "summary": result["summary"], "timing": result["timing"], "provenance": result["provenance"],
            "message": "Preview only. No scenario was created and the site validation gate remains unchanged."}


def _convert(study_root, revision_id, mapping, origin_s, start_s, end_s):
    if not isinstance(mapping, dict) or mapping.get("network_id") not in {"tagum_site_a", "tagum_site_b"}:
        raise ValueError("The mapping must identify Site A or Site B")
    revision = revision_path(study_root, revision_id)
    network = load_registered_network(mapping["network_id"])
    result = convert_revision(revision, mapping, network, origin_s=origin_s, start_s=start_s, end_s=end_s)
    return network, result


def create_scenario_from_review(*, study_root: Path, revision_id: str, mapping: dict, origin_s: float,
                                start_s: float, end_s: float, expected_network_sha256: str,
                                expected_mapping_sha256: str, expected_manifest_sha256: str,
                                name: str, collected_on: str, source_kind: str, user_id: int) -> dict:
    """Reconvert a reviewed preview, retain inputs, and create a provisional scenario."""
    import database
    from services.observed_data_import import import_observations
    name = name.strip() if isinstance(name, str) else ""
    if not name or len(name) > 150:
        raise ValueError("Scenario name must contain 1–150 characters")
    if source_kind not in {"observed", "synthetic"}:
        raise ValueError("Choose observed or synthetic evidence")
    network, converted = _convert(study_root, revision_id, mapping, origin_s, start_s, end_s)
    provenance = converted["provenance"]
    if (network.fingerprint != expected_network_sha256 or provenance["mapping_sha256"] != expected_mapping_sha256 or
            provenance["manifest_sha256"] != expected_manifest_sha256):
        raise ValueError("The revision, mapping or network changed; preview the conversion again")
    if converted["summary"]["trips"] == 0 and not converted["pedestrian_counts_csv"]:
        raise ValueError("This conversion has no vehicle or pedestrian demand to import")
    canonical_mapping = json.dumps(mapping, sort_keys=True, separators=(",", ":"))
    source_description = f"Reviewed Field Observer revision {revision_id}; provisional, field validation not established"
    settings = {"traffic_density": "none", "pedestrian_density": "none"}
    if converted["summary"]["trips"]:
        settings = import_observations(kind="trips", csv_text=converted["trips_csv"], source_description=source_description,
                                       source_kind=source_kind, collected_on=collected_on, engine_config=settings,
                                       network_id=network.id, provenance=provenance)["engine_config"]
    if converted["pedestrian_counts_csv"]:
        settings = import_observations(kind="pedestrian_counts", csv_text=converted["pedestrian_counts_csv"], source_description=source_description,
                                       source_kind=source_kind, collected_on=collected_on, engine_config=settings,
                                       network_id=network.id, provenance=provenance)["engine_config"]
    mapping_dir = Path(study_root) / "data" / "sites"
    mapping_dir.mkdir(parents=True, exist_ok=True)
    saved_mapping = mapping_dir / f"mapping-{provenance['mapping_sha256']}.json"
    if saved_mapping.exists():
        if saved_mapping.read_text(encoding="utf-8") != canonical_mapping:
            raise ValueError("The retained mapping does not match its fingerprint")
    else:
        temporary = mapping_dir / f".mapping-{uuid.uuid4().hex}.tmp"
        try:
            with temporary.open("x", encoding="utf-8") as stream:
                stream.write(canonical_mapping)
                stream.flush()
                os.fsync(stream.fileno())
            if saved_mapping.exists():
                if saved_mapping.read_text(encoding="utf-8") != canonical_mapping:
                    raise ValueError("The retained mapping does not match its fingerprint")
            else:
                os.replace(temporary, saved_mapping)
        finally:
            temporary.unlink(missing_ok=True)
    scenario_id = database.create_scenario(name=name, description=source_description, network_id=network.id,
                                           engine_config=settings, created_by=user_id)
    response = {"scenario_id": scenario_id, "network_id": network.id, "summary": converted["summary"],
                "message": "Scenario created with provisional demand. Independent site validation is still required."}
    try:
        database.log_audit_event(user_id=user_id, action="desktop_reviewed_scenario_created", target="scenarios",
                                 details=f"Created scenario {scenario_id} from reviewed revision {revision_id}; mapping {provenance['mapping_sha256']}")
    except Exception:
        response["audit_warning"] = "The scenario was created, but its audit entry could not be written."
    return response
