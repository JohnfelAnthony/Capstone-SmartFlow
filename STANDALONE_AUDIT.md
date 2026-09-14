# SmartFlow Standalone Audit

This folder is now intended to work as the project root for the React/FastAPI migration.

## Runtime Files Included

The following root Dash-project runtime assets were copied into `SmartFlow` because the migrated app still needs them:

- `backend/` for FastAPI routes, schemas, auth/session helpers, and simulation runtime.
- `auth.py`, `config.py`, and `database.py` for users, sessions, permissions, scenarios, runs, metrics, and SQLite configuration.
- `simulation/` for SUMO, RL state/reward, policy runtime, training logic, and replay/timeline logic.
- `services/` for scenario, visual network, render-frame, simulation, timeline, RL training, and reporting services.
- `tools/` for visual-network export, controller evaluation, and RL training scripts.
- `sumo/` for the available SUMO networks and configs.
- `data/` for SQLite, visual-network JSON, models, generated evaluations, logs, reports, and backups.
- `assets/` for generated timelines plus legacy static assets still referenced by Python tools/services.
- `requirements.txt` for Python dependencies.

## Dash Files Intentionally Not Included

These old Dash UI files were not copied into the standalone root because React/FastAPI is replacing them:

- `app.py`
- `callbacks.py`
- `layout.py`
- `pages/`
- `components/`
- scratch files and local cache folders

The Dash app remains useful as a reference in the old `trapik2` folder until React reaches feature parity, but these files are not required for the standalone React/FastAPI runtime.

## Known Asset Status

Tagum 1 and Tagum 2 have SUMO files and generated visual-network JSON.

Tagum 3 is currently contract-only. The registry keeps the `tagum_3` key for future work, but its SUMO folder and generated visual network are not present yet. The React scenario form only offers Tagum 1 and Tagum 2 until those files are added.

See `docs/SMARTFLOW_Tagum3_Contract.md` for the exact files required later.
