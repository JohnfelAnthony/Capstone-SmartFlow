"""Read-only comparison of a provisional road network with the installed site."""
from __future__ import annotations

import json

from simulation.network_registry import load_registered_network
from tools.road_editor.server import LIMIT, validate

STUDY_SITES = {"tagum_site_a", "tagum_site_b"}


def _changes(old: dict, new: dict, key: str) -> dict:
    def indexed(payload):
        items = payload.get(key, [])
        if not isinstance(items, list) or any(not isinstance(item, dict) or not isinstance(item.get("id"), str) for item in items):
            return None
        result = {item["id"]: item for item in items}
        return result if len(result) == len(items) else None

    before, after = indexed(old), indexed(new)
    if before is None or after is None:
        return {"available": False, "reason": "Object IDs are missing or duplicated."}
    return {"available": True, "added": sorted(after.keys() - before.keys()),
            "removed": sorted(before.keys() - after.keys()),
            "modified": sorted(key for key in before.keys() & after.keys() if before[key] != after[key])}


def preview_revision(network_id: str, candidate: dict, scenarios: list[dict], *, registry_path=None) -> dict:
    if network_id not in STUDY_SITES:
        raise ValueError("Only the two registered study sites can be reviewed")
    if not isinstance(candidate, dict) or candidate.get("id") != network_id:
        raise ValueError("The candidate network ID must match the selected site")
    try:
        size = len(json.dumps(candidate, ensure_ascii=False, allow_nan=False).encode("utf-8"))
    except (TypeError, ValueError) as exc:
        raise ValueError("The candidate must contain finite JSON values") from exc
    if size > LIMIT:
        raise ValueError("The candidate network is larger than 5 MB")
    installed = (load_registered_network(network_id, registry_path=registry_path)
                 if registry_path is not None else load_registered_network(network_id))
    diagnostic = validate(candidate)
    candidate_hash = diagnostic.get("fingerprint")
    affected = [{"id": row["id"], "name": row["name"], "network_sha256": row.get("network_sha256"),
                 "archived": bool(row.get("is_archived"))}
                for row in scenarios if row.get("network_id") == network_id
                and (candidate_hash is None or row.get("network_sha256") != candidate_hash)]
    return {"network_id": network_id, "installed_sha256": installed.fingerprint, "candidate_sha256": candidate_hash,
            "installed_visual": installed.visual(),
            "changes": {key: _changes(installed.payload, candidate, key) for key in ("nodes", "roads", "islands")},
            "affected_scenarios": affected, "validation": diagnostic, "installable": False,
            "message": "Review only. Physical clearance is not certified and this candidate cannot be applied yet."}
