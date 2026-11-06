"""Permission-aware search and the metric definitions."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query

import database
from backend.security import require_current_user, require_permission
from services.metric_definitions import METRIC_CATALOG

router = APIRouter()

@router.get("/api/metrics/definitions")
def metric_definitions(user: dict = Depends(require_current_user)):
    return METRIC_CATALOG


def may(user: dict, page: str, action: str = "view") -> bool:
    try:
        require_permission(user, page, action)
        return True
    except HTTPException:
        return False


@router.get("/api/search")
def search(q: str = Query(min_length=1, max_length=160), user: dict = Depends(require_current_user)):
    query = q.strip().lower()
    if not query:
        return {"results": [], "has_more": False}
    results = []
    pages = [("Dashboard", "dashboard"), ("Scenarios", "scenarios"), ("RL Training", "rl-training"),
             ("Runs & Reports", "runs-reports"), ("Compare Runs", "compare"), ("Settings", "profile"), ("Help", "help")]
    for title, permission in pages:
        if query in title.lower() and may(user, permission):
            results.append({"kind": "Page", "id": None, "title": title, "description": "Open workspace", "page": title})
    # Literal substring search: '%' and '_' are text, not SQL wildcard operators.
    pattern = "%" + query.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_") + "%"
    sources = [
        ("scenarios", "scenarios", "Scenario", "Scenarios", "name", "COALESCE(description,'')"),
        ("simulation_runs", "runs-reports", "Run", "Runs & Reports", "CAST(id AS TEXT)", "COALESCE(notes,'') || ' ' || control_mode || ' ' || status"),
        ("rl_models", "rl-training", "Model", "RL Training", "COALESCE(name, algorithm)", "algorithm"),
    ]
    has_more = False
    with database.get_db() as conn:
        for table, permission, kind, page, title, description in sources:
            if not may(user, permission):
                continue
            rows = conn.execute(f"SELECT id, {title} AS title, {description} AS description FROM {table} WHERE lower({title} || ' ' || {description}) LIKE ? ESCAPE '\\' ORDER BY id DESC LIMIT 26", (pattern,)).fetchall()
            has_more = has_more or len(rows) > 25
            results.extend({"kind": kind, "id": row["id"], "title": f"Run #{row['id']}" if kind == "Run" else row["title"],
                            "description": row["description"] or "", "page": page} for row in rows[:25])
    return {"results": results, "has_more": has_more}
