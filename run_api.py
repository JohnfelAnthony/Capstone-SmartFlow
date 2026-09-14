from __future__ import annotations

import os

import uvicorn


def main() -> None:
    os.environ.setdefault("SMARTFLOW_SECRET_KEY", "local-dev-change-before-production")
    os.environ.setdefault("SMARTFLOW_BOOTSTRAP_ADMIN_PASSWORD", "SmartFlowAdmin1")

    host = os.environ.get("SMARTFLOW_API_HOST", "127.0.0.1")
    port = int(os.environ.get("SMARTFLOW_API_PORT", "8000"))
    reload_enabled = os.environ.get("SMARTFLOW_API_RELOAD", "").strip().lower() in {
        "1",
        "true",
        "yes",
        "on",
    }

    uvicorn.run("backend.main:app", host=host, port=port, reload=reload_enabled)


if __name__ == "__main__":
    main()
