"""Coordinate a network switch only after authoritative clearance checks pass."""
from __future__ import annotations

import json
from pathlib import Path

from services.network_revision_preview import preview_revision
from services.network_revision_storage import RevisionConflict, store_revision


def apply_revision(*, registry_path: Path, runtime, network_id: str, expected_sha256: str,
                   candidate: dict, scenarios: list[dict], user_id: int, audit) -> dict:
    """Recheck, record intent, commit and clear idle state under shared exclusion.

    Current editor validation never certifies clearance, so real candidates are
    refused. The audit callback records intent before any registry mutation.
    """
    with runtime.network_revision_guard() as invalidate:
        review = preview_revision(network_id, candidate, scenarios, registry_path=registry_path)
        if review["installed_sha256"] != expected_sha256:
            raise RevisionConflict("The installed network changed; review the draft again")
        checked = review["validation"]
        if (not checked.get("structurally_valid") or not checked.get("clearance_checked") or
                not review["candidate_sha256"] or any(issue.get("severity") == "error" for issue in checked["issues"])):
            raise ValueError("Draft cannot be applied: structural and complete physical-clearance checks must pass")
        details = {"network_id": network_id, "old_sha256": expected_sha256,
                   "new_sha256": review["candidate_sha256"], "changes": review["changes"],
                   "clearance_checked": True}
        # If the audit store is unavailable, no registry mutation is attempted.
        audit(user_id=user_id, action="network_revision_apply_requested", target=network_id,
              details=json.dumps(details, sort_keys=True))
        result = store_revision(registry_path, network_id, expected_sha256, candidate)
        if result["changed"]:
            invalidate()
        try:
            audit(user_id=user_id, action="network_revision_applied", target=network_id,
                  details=json.dumps({**details, "changed": result["changed"]}, sort_keys=True))
        except Exception:
            # A committed registry must never be reported as a failed write or
            # silently rolled back after the runtime has observed it.
            result["audit_warning"] = "Revision committed, but the completion audit entry could not be written. The request entry was recorded."
        return result
