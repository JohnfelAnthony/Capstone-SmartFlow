# SmartFlow

Documentation reviewed: **2026-10-02** (Asia/Singapore). Scope: **this `SmartFlow` folder**, containing the React application and Python backend.

SmartFlow is a capstone traffic simulation and decision-support project for a bounded study area in Tagum City. It is intended to compare traffic signal strategies and adaptive routes under ordinary traffic, peak demand and road disruptions. The current direction is a **React web application, a custom Python traffic engine, and a dynamic Three.js visualization**. SUMO is being replaced in the active application.

**Latest captured status, October 2:** approved audit priorities 1–6 remain repaired. The delivery pass adds four CSV blank templates and current-network synthetic examples, import guidance, explicit measurement/provenance report columns, and manuscript draft wording. A clean separate-location installation passed 99 Python tests, API compilation, lint, build and startup smoke. After the final CSV attachment change, its four focused tests, compilation, lint and builds passed again. An isolated browser verified all eight template downloads, import/save/reopen, restored replay/model loading and CSV/JSON report contents. Lint has zero errors and the existing TanStack warning. Evidence and remaining deployment/research decisions are in [Progress and handoff](docs/PROGRESS_AND_HANDOFF.md). The September 23 [implementation handoff](IMPLEMENTATION_HANDOFF.md), sections 1–4 and 11, remains the historical repair map and task index. Synthetic software checks do not establish Tagum controller effectiveness; field observations, calibration and final study decisions remain open.

## Start a new implementation chat here

Open **this SmartFlow folder** as the workspace. Read [AGENTS.md](AGENTS.md), this README, handoff sections 1–4 and 11, and the project overview. Then read only the source and tests for the selected delivery slice. No parent Trapik2 files are needed to understand the current scope and recorded history. Documentation provides orientation; the relevant source still needs inspection before it is changed.

## Documentation index

| Document | What it answers |
| --- | --- |
| [README.md](README.md) | Where to start, how to run the new stack, and where the main files live. |
| [Implementation handoff](IMPLEMENTATION_HANDOFF.md) | Latest interrupted state, six approved areas, all 31 backlog tasks, acceptance criteria and a targeted code-reading map. Read sections 1–4 and 11 first; other sections as needed. |
| [Project purpose and scope](docs/PROJECT_OVERVIEW.md) | Why the project exists, chapter requirements, users, agreed direction and research boundaries. |
| [Architecture and delivery plan](docs/ARCHITECTURE_AND_PLAN.md) | Technical-lead review, alternatives, decisions, architecture, 35-day delivery plan, risks and release/recovery gates. |
| [Progress and handoff](docs/PROGRESS_AND_HANDOFF.md) | Latest status pointer and dated verification evidence; clearly separates the earlier passing checkpoint from later unfinished work. |
| [Research preparation](docs/RESEARCH_METHOD.md) | Observation form, calibration/evaluation protocol, metric definitions and open study decisions. |
| [Field recording procedure](docs/FIELD_RECORDING_PROTOCOL.md) | Roadside phone placement, coverage, signal and pedestrian observations, collection forms and pilot quality checks. |
| [Video observation tool plan](docs/VIDEO_OBSERVATION_TOOL_PLAN.md) | Temporary offline Python tool inside SmartFlow, selected open-source stack, review workflow and evidence exports. |
| [Field data integration plan](docs/FIELD_DATA_SMARTFLOW_INTEGRATION.md) | Required demand/signal fidelity changes, dataset conversion, calibration, validation and field-informed RL experiments. |
| [Single-host deployment](deploy/README.md) | Production environment, single-worker startup, storage and recovery checklist. |
| [Project history and chapter archive](PROJECT_HISTORY_AND_MIGRATION.md) | Both codebases, old/revised chapter comparison, source PDFs and relocation checklist. Read sections 1–9 for history; appendices only for specific research questions. |

The four foundation documents remain README, overview, architecture and progress. The owner subsequently requested the implementation handoff and historical archive. Keep these existing documents focused instead of creating overlapping status files. `AGENTS.md` is the short agent entry point; skill/tool Markdown is task-specific guidance. The archive's full manuscripts are reference material, not required startup reading. Do not use the parent folder's Dash application as the specification for this React application.

## Start locally

Run commands from **`SmartFlow`**, not its parent directory. The working development environment has a project-local Python virtual environment and Node/npm. Python 3.13 was used during the recent engine work. Dependency versions are in [package.json](package.json), [package-lock.json](package-lock.json) and [requirements.txt](requirements.txt).

First-time setup:

```powershell
npm ci
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
| `SMARTFLOW_ENV`, `SMARTFLOW_PUBLIC_BASE_URL`, `SMARTFLOW_ALLOWED_ORIGINS` | Production mode, public HTTPS origin and exact browser origins; see [deployment guide](deploy/README.md). |
| `SMARTFLOW_BOOTSTRAP_ADMIN_PASSWORD` | Initial administrator password for a fresh database. |
| `SMARTFLOW_DB_PATH` | Database location; defaults to `data/smartflow.db` inside this folder. |
| `SMARTFLOW_SCENARIO_CONFIG_MAX_BYTES` | Positive serialized UTF-8 byte limit per scenario JSON field, shared by demand import and saving; defaults to 2 MiB (2,097,152 bytes). Expanded arrival schedules count toward it. |
| `SMARTFLOW_NETWORK_PATH` | Optional native network path, used when running an isolated restored bundle. |
| `SMARTFLOW_MAX_RECORDING_SECONDS` | Optional per-recording duration limit; defaults to 3,600 seconds. |
| `SMARTFLOW_API_HOST`, `SMARTFLOW_API_PORT` | API bind address and port. |
| `SMARTFLOW_API_RELOAD` | Opt-in development auto-reload. Otherwise restart the API after Python changes. |
| `VITE_SMARTFLOW_API_BASE_URL` | Frontend API address. |

Recreate `.venv` when moving the project to another machine. A pre-existing `dist/` build or running server may predate the latest source edits.

For a teammate's clean setup, copy the source, dependency manifests, `data/networks`, `data/scenarios` and documentation into a separate folder. Install Node/npm and Python, then run the first-time setup above in that folder. Build with `npm run build`; recreate dependencies instead of copying `node_modules`, `.venv` or an old `dist`. Keep the original database and artifact directories together when preserving results, or use a verified ZIP restore for relocation. A clean source copy seeds demonstration scenarios; it does not contain your saved research inputs or models.

To rehearse the package from the current checkout, choose a **new, nonexistent** target directory:

```powershell
.venv/Scripts/python.exe tools/verify_standalone.py tmp/team-install-check
```

This copies source and checks manuscript PDF hashes, installs from the npm lockfile into a fresh dependency directory, creates a new Python environment, runs the full Python tests, API compilation, lint and build, then checks login/configure/start/stop against an isolated database. It leaves the copy and evidence available for inspection. Browser import/replay/export checks follow these automated checks.

In **Scenarios → Create/Edit → CSV import**, choose a schema and download its blank template or synthetic example. Examples use IDs from the currently loaded network and select the synthetic source label. Fill blank templates with actual records before importing; keep originals and collection provenance. Detailed columns and units are in [Research preparation](docs/RESEARCH_METHOD.md#csv-template-and-import-guide).

## Verification commands

Run these checks after implementation or relocation; the latest dated results are in [Progress and handoff](docs/PROGRESS_AND_HANDOFF.md):

```powershell
.venv/Scripts/python.exe -m pip install -r requirements-dev.txt
.venv/Scripts/python.exe -m unittest discover -s tests -v
npm run check:api
npm run lint
npm run build
```

Use an isolated database for integration checks. Tests create temporary databases; `data/native-verification.db` is a separate development verification database, not the canonical research dataset. The detailed evidence and pending checks are in [Progress and handoff](docs/PROGRESS_AND_HANDOFF.md).

## Backup and local capacity checks

An administrator can create a ZIP bundle on **Backup & Restore** after stopping live runs, recordings and training. It contains a SQLite snapshot and referenced artifacts. **Verify restore** creates an isolated directory and returns its path; read `restore_environment.json` there to start a separate API against that copy. Supply a separate `SMARTFLOW_SECRET_KEY` when launching it. Legacy `.db` entries contain SQLite only and are staged without replacing the live database. The active SQLite download is an export, not an artifact backup.

To repeat the synthetic native capacity measurement on the machine that will run SmartFlow:

```powershell
.venv/Scripts/python.exe -m tools.measure_native_capacity --duration-seconds 60 --output tmp/capacity.json
.venv/Scripts/python.exe -m tools.measure_native_capacity --duration-seconds 300 --densities 'high,very high' --output tmp/capacity-stress.json
```

The command reports step and frame cost, simulation/wall ratio, process memory, recording size and demand conservation. Add `?perf=1` to the app URL to show the 3D render-loop fps and draw calls during a visible production-build run. Hidden tabs and Vite hot reload can distort browser fps. The local September 27 measurements and limits are in the progress document; they do not certify other hardware or real-world traffic capacity.

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
