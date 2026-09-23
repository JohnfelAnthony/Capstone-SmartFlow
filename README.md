# SmartFlow

Documentation reviewed: **2026-09-23** (Asia/Singapore). Scope: **this `SmartFlow` folder**, containing the React application and Python backend.

SmartFlow is a capstone traffic simulation and decision-support project for a bounded study area in Tagum City. It is intended to compare traffic signal strategies and adaptive routes under ordinary traffic, peak demand and road disruptions. The current direction is a **React web application, a custom Python traffic engine, and a dynamic Three.js visualization**. SUMO is being replaced in the active application.

**Current status:** implementation is in progress. After the documentation review, the owner requested resumed engine work. The resulting `native-3` checkpoint passed all **40 Python tests**, API compilation and a three-seed synthetic headless experiment on September 23. Field calibration, research-scale RL evaluation, current frontend acceptance and deployment readiness remain outstanding. The plan uses the owner's approximately 35-day deadline estimate; required RL coverage still needs adviser confirmation.

## Read these four documents in order

| Document | What it answers |
| --- | --- |
| [README.md](README.md) | Where to start, how to run the new stack, and where the main files live. |
| [Project purpose and scope](docs/PROJECT_OVERVIEW.md) | Why the project exists, chapter requirements, users, agreed direction and research boundaries. |
| [Architecture and delivery plan](docs/ARCHITECTURE_AND_PLAN.md) | Technical-lead review, alternatives, decisions, architecture, 35-day delivery plan, risks and release/recovery gates. |
| [Progress and handoff](docs/PROGRESS_AND_HANDOFF.md) | What exists, what was actually verified, known gaps, and where implementation should resume. |

These are the four maintained working documents. The separately requested [Project history, chapter archive and migration record](PROJECT_HISTORY_AND_MIGRATION.md) preserves both codebases' history, the full text of the old and revised manuscripts, source PDFs and a relocation checklist. Read it before moving SmartFlow away from its parent. `AGENTS.md` and Markdown under skill/tool directories are supporting instructions. Earlier migration plans and status reports are superseded. Do not use the parent folder's Dash application as the specification for this React application.

## Start locally

Run commands from **`SmartFlow`**, not its parent directory. The working development environment has a project-local Python virtual environment and Node/npm. Python 3.13 was used during the recent engine work. Dependency versions are in [package.json](package.json), [package-lock.json](package-lock.json) and [requirements.txt](requirements.txt).

First-time setup:

```powershell
npm install
npm run venv:create
npm run venv:install
```

Start the Python API:

```powershell
npm run api
```

Start React in another terminal:

```powershell
npm run dev
```

The API defaults to `http://127.0.0.1:8000`. Open the URL printed by Vite, normally `http://localhost:5173`. Sign in, select **Tagum — Single Car Demo**, apply its settings, and start. The basic demonstration is five connected junctions, roads, signal heads and one active car. Camera controls include orbit, pan, zoom, follow car and reset camera.

`run_api.py` supplies development bootstrap defaults when environment variables are absent. On a fresh database the administrator username is `admin` and its initial development password is `SmartFlowAdmin1`. Existing databases keep their existing credentials; environment overrides also take precedence. This is development setup, not the production credential policy.

| Setting | Purpose |
| --- | --- |
| `SMARTFLOW_SECRET_KEY` | Session secret; provide an explicit value for deployment. |
| `SMARTFLOW_BOOTSTRAP_ADMIN_PASSWORD` | Initial administrator password for a fresh database. |
| `SMARTFLOW_DB_PATH` | Database location; defaults to `data/smartflow.db` inside this folder. |
| `SMARTFLOW_API_HOST`, `SMARTFLOW_API_PORT` | API bind address and port. |
| `SMARTFLOW_API_RELOAD` | Opt-in development auto-reload. Otherwise restart the API after Python changes. |
| `VITE_SMARTFLOW_API_BASE_URL` | Frontend API address. |

Recreate `.venv` when moving the project to another machine. A pre-existing `dist/` build or running server may predate the latest source edits.

## Verification commands

The Python suite and API compilation passed for the September 23 `native-3` checkpoint. The frontend build and complete browser workflow still need current-source acceptance. Run these checks after further changes or relocation:

```powershell
.venv/Scripts/python.exe -m pip install -r requirements-dev.txt
.venv/Scripts/python.exe -m unittest discover -s tests -v
npm run check:api
npm run build
```

Use an isolated database for integration checks. Tests create temporary databases; `data/native-verification.db` is a separate development verification database, not the canonical research dataset. The detailed evidence and pending checks are in [Progress and handoff](docs/PROGRESS_AND_HANDOFF.md).

## Headless experiments

The native runner accepts a JSON scenario, seeds, a measurement duration and an optional warmup. It does not need the browser or API. This example completed for seeds 11, 22 and 33 at the September 23 checkpoint, with zero vehicle/pedestrian conservation error; it is a synthetic execution check, not a research result:

```powershell
.venv/Scripts/python.exe -m tools.run_native_experiment --scenario data/scenarios/tagum_peak_event.json --duration 300 --warmup 20 --seeds 11 22 33 --output data/generated/experiments/tagum_peak.json
```

The example scenario is explicitly **synthetic**. It contains changing demand and timed construction/closure/reopening events. `--trips` accepts a CSV with `time,source,destination,vehicle_type` columns; `vehicle_type` is optional. Source and destination must be connected boundary IDs from the study network. The JSON must separately identify the data's provenance. Loading a CSV does not make its data observed or calibrated.

The Q-learning, DQL and PPO entry points are `tools/train_ql.py`, `tools/train_dql.py` and `tools/train_ppo.py`; comparison is `tools/evaluate_controllers.py`. Their current parsers include `--scenario-id` for complete saved scenarios. Run a tool with `--help` for its exact arguments. API-backed tools importing `config.py` require `SMARTFLOW_SECRET_KEY` in the environment. Current native model compatibility rules are described in the architecture document.

## Repository guide

| Path | Responsibility |
| --- | --- |
| `src/` | React/TypeScript pages, API clients, state consumption and visualization. |
| `src/simulation/SimulationScene3D.tsx` | Procedural roads, signals, vehicles and camera controls. |
| `backend/` | FastAPI routes, request schemas, security bridge and live runtime. |
| `simulation/traffic_engine.py` | **Current authoritative traffic engine.** |
| `simulation/road_network.py`, `scenario_config.py`, `demand.py` | Native road graph, input validation and scheduled demand. |
| `simulation/rl_*.py`, `ql_*.py`, `dql_training.py`, `ppo_training.py` | RL environment, observations, reward, policies and training. |
| `services/` | Native controller selection, recording, frame serialization and application services. |
| `database.py`, `auth.py`, `config.py` | Persistence, authentication and configuration. |
| `data/networks/` | Cached OSM extract and derived study network. |
| `data/scenarios/` | Native example scenario inputs. |
| `tools/`, `tests/` | Import, experiment and training commands; automated behavior checks. |

Older simulation modules and `sumo/` assets still exist inside this folder. They are historical material, not the active engine contract. Follow the explicit entry points above rather than inferring architecture from similar filenames.

## Road data

The supplied road extract was downloaded on **2026-09-21 at 14:10:12 UTC**. The derived network retains source metadata and assumptions. Geometry comes from [OpenStreetMap contributors](https://www.openstreetmap.org/copyright), under ODbL. Road geometry, measured traffic demand and experimental signal placement are different kinds of data.

Map refresh is a deliberate maintenance operation, not a prerequisite for running the application:

```powershell
python tools/import_osm_network.py
python -m tools.build_study_network
```

Refreshing may change geometry and invalidate model/recording compatibility. Preserve the exact network snapshot used in capstone experiments.
