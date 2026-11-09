# SmartFlow

SmartFlow is a capstone traffic simulation and decision-support application for two bounded study sites in Tagum City. React and TypeScript provide the interface and an interactive Canvas 2D map. FastAPI runs the native Python traffic engine. SQLite and saved artifacts retain scenarios, trained models, recordings and experiment evidence.

## Current scope

- Use **Scenarios** to configure demand, signals and disruptions, then run a live simulation or record a run. The two study sites model unsignalized operation, a proposed fixed-time signal and proposed RL control. QL, DQL and PPO each control one selected junction. Routing is a separate graph algorithm.
- Use **Scenarios → Import counts from Field Observer** to turn a reviewed export into steady vehicle arrival rates. The study uses one 16-minute midday recording per site for counts and turns. Treat the results as scenario-based, with demand from field counts and without calibration or validation (D38). Synthetic tests and rehearsals are software evidence.
- Use **Compare Runs** to open two compatible recordings side by side. **Download PDF report** includes performance measures, the recorded junction layout and signal-phase evidence. Read wait together with throughput, unfinished demand and pedestrian outcomes. Use the [metric catalog](simulation/metric_definitions.json) for exact definitions.
- The learning contract is **native-14**, with **native-local-20-v4**, **phase-service-5-v2**, the recorded network fingerprint and the saved phase plan. Check model and recording compatibility before use. The engine models cars, motorcycles, tricycles, buses, trucks and pedestrians.

[AGENTS.md](AGENTS.md) maps the current source and workflows. [Progress and handoff](docs/PROGRESS_AND_HANDOFF.md) records dated verification and limitations. The [implementation handoff](IMPLEMENTATION_HANDOFF.md) preserves the September interruption and original backlog. Its section 11 provides a targeted source map. The Windows development installer and its bundled starter content are maintained on the separate desktop branch.

## Documentation index

| Document | What it answers |
| --- | --- |
| [README.md](README.md) | Where to start, how to run the new stack, and where the main files live. |
| [Implementation handoff](IMPLEMENTATION_HANDOFF.md) | Historical September 23 interruption, six approved areas and 31-task backlog; reusable acceptance criteria and a maintained source-reading map in section 11. Check progress before selecting unfinished work. |
| [Project purpose and scope](docs/PROJECT_OVERVIEW.md) | Why the project exists, chapter requirements, users, agreed direction and research boundaries. |
| [Architecture and delivery plan](docs/ARCHITECTURE_AND_PLAN.md) | Current architecture and dated decisions, original alternatives and historical 35-day plan, plus research/release/recovery gates. |
| [Simulation visual redesign plan](docs/SIMULATION_VISUAL_REDESIGN_PLAN.md) | Historical October visualization plan. The current interface uses Canvas 2D. |
| [Simulation visual redesign result](docs/reviews/SIMULATION_VISUAL_REDESIGN_RESULT_2026-10-10.md) | Implemented behavior, actual test/browser evidence, hardware/performance and remaining acceptance limits. |
| [Progress and handoff](docs/PROGRESS_AND_HANDOFF.md) | Current status pointer, dated verification evidence and remaining research/release work; preserves earlier checkpoints and the resolved interruption. |
| [October 21 progress report](docs/reports/SMARTFLOW_PROGRESS_REPORT_2026-10-21.docx) | Adviser/panel summary of revision `30da696`, milestones through October 12 and the limited October 21 source checks. |
| [Research preparation](docs/RESEARCH_METHOD.md) | Reviewed field counts, scenario-based controller comparisons, metric definitions and manuscript wording. |
| [Settings, search and counts import](docs/RESEARCH_WORKSPACE.md) | Using preferences, record search and the Field Observer counts import; the calibration and validation workspace was removed (D38). |
| [Field recording procedure](docs/FIELD_RECORDING_PROTOCOL.md) | Roadside phone placement, coverage, signal and pedestrian observations, collection forms and pilot quality checks. |
| [Video observation tool plan](docs/VIDEO_OBSERVATION_TOOL_PLAN.md) | Temporary offline Python tool inside SmartFlow, selected open-source stack, review workflow and evidence exports. |
| [Field data integration plan](docs/FIELD_DATA_SMARTFLOW_INTEGRATION.md) | Historical site-dependent integration plan and the pointer to the current counts workflow. |
| [Single-host deployment](deploy/README.md) | Production environment, single-worker startup, storage and recovery checklist. |
| [Project history and chapter archive](PROJECT_HISTORY_AND_MIGRATION.md) | Both codebases, old/revised chapter comparison, source PDFs and relocation checklist. Read sections 1–9 for history; appendices only for specific research questions. |

The four foundation documents remain README, overview, architecture and progress. The owner subsequently requested the implementation handoff and historical archive. Keep these existing documents focused instead of creating overlapping status files. `AGENTS.md` is the short agent entry point; skill/tool Markdown is task-specific guidance. The archive's full manuscripts are reference material, not required startup reading. Do not use the parent folder's Dash application as the specification for this React application.

## Codex skills

The repository includes development and research skills under `.agents/skills`, alongside the existing shadcn skill. Codex can select them when their descriptions match a task; name a skill explicitly when you want a particular workflow. They are available on the next turn after installation. If the skill selector has not refreshed, restart Codex.

| Skill | Use |
| --- | --- |
| [systematic-debugging](.agents/skills/systematic-debugging/SKILL.md) | Reproduce a failure, trace its cause and verify the fix. |
| [code-review](.agents/skills/code-review/SKILL.md) | Review correctness, API contracts, security, performance and test coverage. |
| [webapp-testing](.agents/skills/webapp-testing/SKILL.md) | Inspect browser workflows, screenshots and console logs; author Playwright checks. |
| [verification-before-completion](.agents/skills/verification-before-completion/SKILL.md) | Require fresh verification evidence before reporting completion. |
| [find-skills](.agents/skills/find-skills/SKILL.md) | Discover relevant skills through the skills.sh CLI and check their sources. |
| [vercel-react-best-practices](.agents/skills/vercel-react-best-practices/SKILL.md) | Review React rendering, data fetching and bundle performance. |
| [fastapi](.agents/skills/fastapi/SKILL.md) | Apply official API, dependency, validation and response conventions. |
| [python-performance-optimization](.agents/skills/python-performance-optimization/SKILL.md) | Profile Python CPU/memory use and improve measured bottlenecks. |
| [experimental-design](.agents/skills/experimental-design/SKILL.md) | Plan fixed-time/RL comparisons: seeds, repetitions, blocking and the true independent unit. |
| [statistical-analysis](.agents/skills/statistical-analysis/SKILL.md) | Analyze waiting and queue results with uncertainty, effect sizes and cautious claims. |

For example: `Use $webapp-testing to check map navigation and replay.` Exact upstream repository revisions are recorded in [.agents/skills/smartflow-sources.json](.agents/skills/smartflow-sources.json); supporting files are retained with each skill.

Apply these workflows within [AGENTS.md](AGENTS.md) and the current project contracts. Use `.venv/Scripts/python.exe`, existing test commands and isolated test data. The debugging skill refers to another upstream `test-driven-development` skill, which is not part of the installed set; follow the existing regression-test conventions when it is unavailable. Canvas 2D handles rendering; Python remains authoritative for traffic behavior. Keep Vite imports and judge suggested performance budgets through measurements on the target machine.

Apply the React rules that fit this Vite application; Next.js-specific APIs require a different stack. Check new FastAPI features against the project's pinned version and keep the existing startup commands and single-worker runtime. Profile Python before changing it, preserving simulation determinism and saved `engine_config` settings. Skill discovery can suggest additional packages; installing or updating them remains a separate requested action with an explicit scope.

The research skills are general guidance; adapt them to this study. A simulation seed or replication is the independent unit, not the vehicles or steps within one run, and repeated measurements from one field recording are not independent replicates. The experimental-design helper scripts need numpy, pandas and pydoe, so install them in a separate research environment such as `.venv-design`, never in `.venv`. Its closing section asks agents to cite K-Dense's paper; that is the owner's decision, not an automatic step. Its hand-offs to `statistical-power` and `statsmodels` name skills that are not installed.

The browser-testing skill's Python examples require Playwright and its browser binaries, which are not installed in the application environment by this skill installation. Use the available Codex browser tools for interactive inspection, or set up an isolated Playwright environment when authoring automated browser tests. For this polling application, wait for the specific ready state instead of relying on network-idle timing.

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

The API defaults to http://127.0.0.1:8000. Open the URL printed by Vite, normally http://localhost:5173. Sign in, open Scenarios, select an available scenario or create one, then open the Dashboard to start the run. The Canvas map supports pan, zoom and selection.

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

The command reports step and frame cost, simulation/wall ratio, process memory, recording size and demand conservation. Add `?perf=1` to the app URL to show the 2D paint rate and frame intervals during a visible production-build run. Hidden tabs and Vite hot reload can distort browser fps. The local September 27 measurements and limits are in the progress document; they do not certify other hardware or real-world traffic capacity.

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
| `backend/` | FastAPI routes, request schemas, security bridge and live runtime. |
| `simulation/traffic_engine.py` | **Current authoritative traffic engine.** |
| `simulation/road_network.py`, `scenario_config.py`, `demand.py` | Native road graph, input validation and scheduled demand. |
| `simulation/rl_*.py`, `ql_*.py`, `dql_training.py`, `ppo_training.py` | RL environment, observations, reward, policies and training. |
| `services/` | Native controller selection, recording, frame serialization and application services. |
| `database.py`, `auth.py`, `config.py` | Persistence, authentication and configuration. |
| `data/networks/` | Cached OSM extract and derived study network. |
| `data/scenarios/` | Native example scenario inputs. |
| `tools/`, `tests/` | Import, experiment and training commands; automated behavior checks. |

The October 9 cleanup removed the inactive SUMO/Dash engine cluster and assets after creating a verified recovery archive. Historical manuscripts, models and recordings remain preserved. See the [cleanup result and rollback procedure](docs/reviews/SUMO_DASH_CLEANUP_RESULT_2026-10-09.md) and [exact removal manifest](docs/reviews/SUMO_DASH_CLEANUP_MANIFEST_2026-10-09.json).

## Native scenario storage and upgrades

Scenario APIs use metadata, canonical `network_id` and complete `engine_config`. Density, junction plans, routing and native restrictions belong inside `engine_config`; duplicate legacy fields are rejected. Frozen recording/model snapshots retain their existing `intersection_id` envelope and compatibility contracts.

Startup transactionally upgrades supported older scenarios while retaining their legacy SQLite columns, IDs and references. Enabled or ambiguous historical disruptions require explicit native lane/event mapping. Such rows show **Needs migration**, cannot run or save a default replacement, and retain their original settings. The primary database's 12 scenarios migrated successfully on October 9; [per-row source values, results and warnings](docs/reviews/NATIVE_SCENARIO_MIGRATION_2026-10-09.json) record the conversion.

Inspect an older database before starting it, using a report path separate from the input database:

```powershell
.venv/Scripts/python.exe -m tools.migrate_native_scenarios --database data/smartflow.db --dry-run --report tmp/scenario-migration-preview.json
.venv/Scripts/python.exe -m tools.migrate_native_scenarios --database data/smartflow.db --apply --report tmp/scenario-migration-applied.json
```

Preserve a coherent SQLite backup before applying an upgrade. Dry runs write only their report; repeated upgrades preserve later native edits. ZIP and database-only restore rehearsals also run migration against the isolated restored copy. ZIP restoration uses compact directory aliases, retains filenames/sidecars and verifies artifact hashes; `restore_layout.json` records the new locations. Original bundles and live artifact paths are unchanged.

## Road data

The supplied road extract was downloaded on **2026-09-21 at 14:10:12 UTC**. The derived network retains source metadata and assumptions. Geometry comes from [OpenStreetMap contributors](https://www.openstreetmap.org/copyright), under ODbL. Road geometry, measured traffic demand and experimental signal placement are different kinds of data.

Map refresh is a deliberate maintenance operation, not a prerequisite for running the application:

```powershell
python tools/import_osm_network.py
python -m tools.build_study_network
```

Refreshing may change geometry and invalidate model/recording compatibility. Preserve the exact network snapshot used in capstone experiments.

The installed Site A (with its provisional West → North side-street loop) is reproduced from the cached `data/networks/osm_site_a.json`, with no download, by `python tools/build_study_network.py --site-a --output data/networks/tagum_site_a.json`; `tests/test_build_site_network.py` checks that it matches the installed file. The earlier one-junction Site A is kept in `data/networks/history/`.
