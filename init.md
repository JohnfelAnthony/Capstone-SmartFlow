# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

SMARTFLOW is a Dash + SUMO + TraCI + Three.js traffic simulation platform for researching adaptive signal control at a Tagum City intersection. Users configure scenarios, run SUMO-based simulations, observe live metrics/charts, and view a Three.js 3D scene.

## Key Commands

```bash
# Run the app (requires SUMO on PATH for simulation features)
.venv\Scripts\python app.py
# Opens at http://localhost:8050 — default admin: admin / SmartFlow2026!

# Run all tests (unittest, not pytest)
.venv\Scripts\python -m unittest discover -s tests

# Run a single test file
.venv\Scripts\python -m unittest tests.test_sumo_simulation_service

# Run a single test class/method
.venv\Scripts\python -m unittest tests.test_sumo_simulation_service.TestSumoSimulationService
.venv\Scripts\python -m unittest tests.test_sumo_simulation_service.TestSumoSimulationService.test_service_can_start_step_and_stop_a_sumo_run

# Export SUMO geometry to Three.js visual network JSON
python -m tools.export_sumo_visual_network

# Activate virtual environment
.venv\Scripts\Activate.ps1

# Install dependencies
pip install -r requirements.txt
```

**Note:** The `Traffic-Simulation/` directory is a separate standalone IDM/Pygame project with its own pyproject.toml and pytest configuration.

## Architecture

### Runtime Data Flow
1. **SUMO network** (`sumo/intersection_1/inter.sumocfg`) is started/stepped via TraCI by `simulation/sumo_engine.py`
2. **`services/simulation_service.py`** holds a shared engine singleton accessible from Dash callbacks
3. **`callbacks.py`** wires Dash UI to the service — updates KPIs, charts, status, and 3D payloads
4. **`tools/export_sumo_visual_network.py`** exports clipped SUMO geometry to `assets/generated/visual_network.json`
5. **`assets/three-bridge.mjs`** renders roads, crossings, signals, vehicles, and pedestrians from exported geometry + live state

### Key Modules

| Module | Purpose |
|--------|---------|
| `app.py` | Dash app entry point, routing, auth guards |
| `config.py` | App constants (DB path, session timeout, defaults) |
| `database.py` | SQLite schema, CRUD, seed data |
| `auth.py` | Flask session auth, login/rate-limit, permission checks |
| `callbacks.py` | All Dash interactive callbacks |
| `components/` | Reusable Dash components (header, sidebar, traffic_map) |
| `pages/` | One file per route: dashboard, simulation, scenarios, live_traffic, etc. |
| `simulation/sumo_engine.py` | Active: SUMO/TraCI engine lifecycle |
| `simulation/sumo_state.py` | Active: builds state payload from TraCI |
| `simulation/sumo_config.py` | Active: intersection config (TLS IDs, lanes, phase sequence) |
| `services/simulation_service.py` | Active: shared engine lifecycle manager |
| `services/metrics_service.py` | Metrics aggregation helpers |
| `services/scenario_service.py` | Scenario CRUD from DB |
| `tools/export_sumo_visual_network.py` | Exports SUMO net geometry for Three.js |
| `assets/three-bridge.mjs` | Three.js 3D scene renderer (ES module) |
| `sumo/intersection_1/` | SUMO network files (.net.xml, .rou.xml, .sumocfg) |

### Legacy Files (reference only, not primary runtime)
- `simulation/engine.py`, `network.py`, `vehicles.py`, `pedestrians.py`, `traffic_light.py`, `controllers.py`, `metrics.py` — old custom Python engine (pre-SUMO)

### Auth & Routing
- Routes defined in `app.py`: `PAGE_ROUTES` (user pages), `ADMIN_PAGE_ROUTES` (admin pages)
- Role-based permission checks via `auth.has_permission(page_key, 'view')`
- Public routes: `/login`, `/register`, `/logout`
- Registration mode: `approval-only` (config.py)
- Session timeout: 3600s, login rate-limiting in database layer

### DB Schema
- SQLite at `data/smartflow.db` with WAL journaling
- Tables: `roles`, `users`, `sessions`, `permissions`, `role_permissions`, `login_attempts`, `audit_log`, `scenarios`, `simulation_runs`, `run_metrics`

### Testing Notes
- Tests use `unittest.TestCase` (stdlib), discovered from `tests/` directory
- SUMO-dependent tests will fail if SUMO is not on PATH — check `simulation/sumo_config.get_sumo_binary()`
- Test files prefixed `test_` in `tests/`

### Dependencies (root requirements.txt)
- dash, plotly, pandas, werkzeug, dash-svg

### Three.js Bridge
- `assets/three-bridge.mjs` is loaded as an ES module via `<script type="module">`
- Reads from `assets/generated/visual_network.json` (static geometry) and receives live entity state via Dash component updates
