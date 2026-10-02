# SmartFlow project history, chapter archive and migration record

Recorded: **September 23, 2026 (Asia/Singapore)**. This is a portable snapshot for moving the `SmartFlow` folder away from its parent `trapik2` folder. It preserves what the project proposed, how the manuscripts changed, what each codebase contains, what has actually been tested, and what remains unfinished.

**Read sections 1–9 for the explanation. Appendices A and B contain the extracted text of the complete original and revised PDFs, including their references.** Exact PDF copies are stored inside SmartFlow alongside this record's supporting sources. Figures and table layout remain authoritative in those PDFs; extracted text alone cannot reproduce them faithfully.

This record does not move either codebase, delete the parent folder, or declare the capstone finished. It is a historical companion to the four maintained working documents: [README](README.md), [project overview](docs/PROJECT_OVERVIEW.md), [architecture and plan](docs/ARCHITECTURE_AND_PLAN.md), and [progress and handoff](docs/PROGRESS_AND_HANDOFF.md).

Jump to the full manuscripts: [original chapters](#appendix-a-original-chapters-1-and-2) · [revised chapters](#appendix-b-revised-chapters-1-and-2).

## 1. Orientation: two codebases and three stages of the project

**`trapik2` is the older project workspace. `SmartFlow` is the newer application nested inside it.** The two contain similarly named Python modules, databases, models and generated artifacts, but their current runtimes are different. A filename such as `simulation/engine.py` or the mere presence of a `sumo/` folder does not identify the active engine.

| Stage | Research/software direction | Meaning today |
| --- | --- | --- |
| Original Chapters 1–2 | Agent-based traffic simulation emphasizing autonomous vehicle/pedestrian behavior and RL signal optimization, using SUMO/TraCI. | Original proposal and historical requirements. |
| Revised Chapters 1–2 | Data-based simulation, signal optimization/planning, adaptive routing, closures and event scenarios; the signal controller is the RL learning agent. Still specifies SUMO/TraCI and local use. | Current supplied manuscript, incorporating the owner's reported defense revisions. |
| Later project decisions and current code | React/Three.js website with FastAPI and a custom Python engine; bounded connected OSM-derived road network; routing separate from RL signals; offline training. | Current implementation direction, which still needs to be reflected in the manuscript. |

The revised manuscript did **not** remove SUMO. That was a subsequent owner decision. Likewise, a connected five-junction simulation does **not** mean RL currently coordinates all five junctions.

```text
Original workspace: trapik2/
  app.py -> Dash/Flask -> services/simulation_service.py
         -> simulation/sumo_engine.py -> SUMO + TraCI
  pages/ + callbacks.py + assets/three-bridge.mjs
  SQLite + saved models + evaluations + recordings

Current application: SmartFlow/
  src/ -> React/TypeScript/Vite + Three.js
       -> backend/main.py -> backend/simulation_runtime.py
       -> simulation/traffic_engine.py (native-3)
  data/networks/ -> cached OSM + versioned study graph
  Python RL/headless tools + SQLite + recording/replay
```

Both folders have their own `.git` directories. SmartFlow's inspected Git root is SmartFlow itself. Its current uncommitted native-engine work is newer than the last committed entry (`4e3d3e4`, dated September 14, 2026, “Improve Change Password”). Copying only a committed revision would therefore omit current progress.

## 2. Sources, dates and historical accuracy

All page numbers in this record mean **one-based PDF page positions**, including the title page.

| Source | Date / extent | How to interpret it |
| --- | --- | --- |
| Original `SMARTFLOW_CHAP1_AND 2.docx.pdf` | Cover: June 2026; 73 PDF pages; observed file modification: September 10, 2026, 09:53:36 +08:00. | Original supplied manuscript. Cover and modification dates describe different events. |
| Revised `FINAL_SIGURO_CHAPTER1_AND_2.docx.pdf` | Cover: June 2026; 74 PDF pages; observed file modification: September 21, 2026, 21:46:39 +08:00. | Revised supplied manuscript. The unchanged cover month does not make it the same draft. |
| Parent `docs/SMARTFLOW_Codebase_Status.md` | Internally generated May 30, 2026; last updated June 4, 2026. | Historical Dash/SUMO status, not a September native-engine release certificate. |
| Parent `smartflow_documentation_report.md` | File modified September 21, 2026, 20:32:18 +08:00; body describes June 2026 status. | Index/synthesis of older documents. Its “fully functional” language and largely planned React status need qualification. |
| Cached OSM extract | Retrieval recorded September 21, 2026, 14:10:12 UTC. | Date of map retrieval, not a traffic survey or proof of actual signal/lane conditions. |
| Current planning discussion | Owner reported roughly 35 days remaining on September 22. | Provisional window September 23–October 27; exact submission/defense deadline unconfirmed. |
| This implementation/archive checkpoint | September 23, 2026. | Current source inspection and verification described below. |

The PDF metadata exposes document titles and Google Docs/Skia producer information, but no explicit creation/modification date was present in the inspected metadata fields. File timestamps are recorded as observed, not treated as proof of the exact defense or revision date.

No separate panel-recommendation document was identified among the root project documents inspected for this archive. The owner states that the revised PDF reflects panel suggestions. The comparison below records **observable manuscript changes**; it does not invent verbatim panel comments or assign a particular change to a named panelist.

Corrections to the earlier documentation report:

- The parent has **30 Python test files containing 176 test methods**, counted from source. “30 test suites” is not a captured current pass result. The old suite was not rerun for this record.
- The React application is substantially beyond the old scaffold-only description: pages, APIs, streaming, native geometry, recording and RL adapters exist.
- SmartFlow's active engine no longer uses SUMO/TraCI. Historical modules and assets still remain in the folder.
- Existing models, reports and timeline files demonstrate prior development activity. Their presence alone does not prove calibrated research results or compatibility with the current engine.

## 3. Original and revised Chapter 1: what changed

### Original Chapter 1

Original title: **SMARTFLOW: AN AI-DRIVEN AGENT-BASED SIMULATION OF AUTONOMOUS VEHICLES AND PEDESTRIANS WITH REINFORCEMENT LEARNING–BASED TRAFFIC SIGNAL OPTIMIZATION**.

Chapter 1 occupies original PDF pages **2–22**. It contains the background, objectives, significance, scope/limitations, related literature and studies, comparison table, and definitions. The literature review is inside Chapter 1; Chapter 2 is the methodology.

The original problem is proactive traffic analysis at a selected high-volume Tagum intersection and adjacent roads: test congestion and disruptions before physical implementation. It emphasizes heterogeneous vehicle and pedestrian agents, scenario-based demand, and an RL signal controller operating in SUMO through TraCI. Its five specific objectives, on page 6, are summarized as:

1. Model a selected Tagum intersection, its road layout, traffic patterns and pedestrians.
2. Represent vehicles/pedestrians as autonomous entities with heterogeneous behavior and interaction.
3. Generate traffic dynamically from configurable scenarios and demand.
4. Implement adaptive RL traffic-signal control.
5. Evaluate densities, pedestrians, emergencies, closures, construction and accidents.

The original scope also discusses aggressive driving, inconsistent lane discipline, delayed reactions and non-compliant pedestrian movement (page 9). These are **proposal claims**, not proof that either codebase implemented all of them. The current native engine's mixed vehicle dimensions and speeds do not fulfill those richer behavioral claims by themselves.

The original excludes live CCTV/GPS/sensor ingestion, physical signal actuation and a citywide model. It describes simulation-generated “real-time” metrics, not a live feed from Tagum roads. Performance improvements mentioned in the background belong to cited literature; they are not measured SmartFlow outcomes.

### Revised Chapter 1

Revised title: **SMARTFLOW: A Simulation-Based Approach to Traffic Signal Optimization and Adaptive Routing Using Reinforcement Learning**.

Chapter 1 occupies revised PDF pages **2–24**. The six objectives appear on page 5:

1. Model a specific real-world Tagum intersection using road maps, traffic statistics and geographical features.
2. Use actual traffic data to represent traffic volume and conditions.
3. Provide an interface to configure traffic parameters and signal-system settings.
4. Test closures and roadway changes and assess rerouting options.
5. Model event scenarios such as peak periods, holidays and closures.
6. Use RL for traffic-signal learning and information about signal arrangements.

The revised scope (pages 7–9) explicitly identifies the **signal controller as the learning agent**. Vehicles and pedestrians are traffic entities generated from supplied conditions/data. It includes a selected intersection with connected junctions/roads, evaluation of existing and proposed signals, and intersections that may currently be unsignalized. The project remains a bounded simulation study, not all of Tagum or a physical signal-installation project.

New or expanded literature topics include traffic-data-based simulation, road closures/rerouting, event-based simulation, and simulation-based signal planning (pages 11–13). The related-systems table adds these planning/data dimensions (pages 21–22).

### Chapter 1 comparison

| Topic | Original | Revised | Effect on current delivery |
| --- | --- | --- | --- |
| Main framing | Autonomous agent behavior plus adaptive signals. | Simulation-based planning, signals and routing. | Prioritize defensible experiments and decision support. |
| Learning agent | Wording strongly emphasizes autonomous vehicles/pedestrians; signal RL is also described. | Explicitly the signal controller; road users are simulated entities. | Do not claim every car/pedestrian is a trained AI agent. |
| Demand evidence | Configurable/scenario demand and field-inspired modeling. | Actual local traffic data is an explicit objective. | Synthetic examples cannot fulfill the observed-data requirement alone. |
| Geography | One intersection and adjacent roads. | Selected intersection plus connected junctions/roads. | Five connected junctions are a bounded implementation choice requiring final study-boundary agreement. |
| Road changes | Disruption testing. | Closures, road modifications and rerouting analysis. | Preserve connectivity, event timing, routes and comparative outcomes. |
| Events | Variable densities and disruptions. | Explicit peak/weekend/holiday/event scenarios. | Demand windows exist; actual event inputs still need evidence. |
| Signal planning | Optimize existing simulated signal operation. | Also examine proposed signal placement/configuration, including unsignalized locations. | Configurable control modes are a foundation, not an automatic placement optimizer. |
| Technology | SUMO/TraCI. | Still SUMO/TraCI. | Later native-engine decision requires another manuscript alignment pass. |
| Physical deployment | Excluded. | Excluded, with engineering review needed before real implementation. | Hosting a website does not authorize or demonstrate road-system deployment. |

The revised title can suggest RL-based routing, while the revised scope says RL focuses on signal operation. The owner later allowed routing to use a separate algorithm. The final title, objectives, diagrams and implementation description should explain that separation consistently. Required RL coverage and mandatory algorithm comparisons remain open academic questions.

## 4. Original and revised Chapter 2: what remains and what needs alignment

Original Chapter 2 is on PDF pages **23–69**, followed by references on **70–73**. Revised Chapter 2 is on pages **25–70**, followed by references on **71–74**.

Both describe a **hybrid Waterfall/Agile methodology**: structured planning, analysis and design, followed by iterative implementation, testing/evaluation and refinement. Both include project-team organization, work breakdown, a Gantt chart, architecture, conceptual framework, functional/non-functional requirements, use cases, context/data-flow diagrams, ERD/data dictionary, technologies, testing, security and maintenance.

| Area | What the supplied chapters say | Current interpretation / gap |
| --- | --- | --- |
| Architecture | User/dashboard, SUMO simulation, Python/TraCI communication, RL/PyTorch, SQLite, outputs. | React/FastAPI now fronts a native Python engine. Replace obsolete SUMO/TraCI paths in the eventual revised manuscript. |
| Data process | Collect, preprocess and extract simulated traffic features for learning/evaluation. Revised text strengthens use of actual traffic inputs. | Separate raw field observations, derived demand, simulation outputs and learned artifacts. Import capability is not calibration. |
| Learning | Signal state/action/reward interaction; comparison against fixed-time control. Both specifically discuss PyTorch DQN (original page 59; revised page 60). | QL, DQL/DQN and PPO code exists, but the manuscripts do not by themselves prove that every algorithm is mandatory for defense. |
| Inputs/outputs | Scenario/disruption configuration, lifecycle commands, signals, metrics, reports and controller comparisons. Revised conceptual framework includes validated roads/data, rerouting and signal-planning outputs. | Preserve complete config and provenance and expose actual controller identity. |
| Database | Conceptual entities for accounts, scenarios, road constraints, signal modes, runs, metrics, RL outputs and reports. | Implemented SQLite schemas also include roles, sessions, audits, model registry and training jobs; they are not a literal one-to-one copy of the conceptual ERD. |
| Testing | Functional/integration tests, scenario tests, RL reward/convergence/stability and traffic metrics; a system test plan. | Automated smoke/regression results establish software behavior, not that RL improves real traffic. |
| Quality/security | Access control, local data protection, logs, backups, input validation and maintenance plans referencing ISO frameworks. | These are intended practices; neither document establishes certification or a completed hosted-security assessment. |
| Operations | Local desktop environment and locally stored data. | Local web operation remains possible; online hosting is a later direction with unresolved provider and concurrency limits. |

The revised Chapter 2 is an evolution of the same design rather than a complete technology rewrite. Its diagrams still contain SUMO/TraCI. Its requirements put more weight on confirmed traffic data, storage consistency, secured configuration and repeatable runs with unchanged inputs. Its Gantt chart is a manuscript planning artifact, not evidence that each phase has been completed or a replacement for the September 35-day delivery plan.

## 5. Progress of the older trapik2 codebase

Paths in this section are relative to the **old parent root**, which may be left behind after relocation. The descriptions below preserve its role without requiring those links to remain available.

| Area | Evidence in the old codebase | Status and qualification |
| --- | --- | --- |
| App and navigation | `app.py`, `layout.py`, `callbacks.py`, `pages/`, `components/`. | Substantial Dash/Flask application; this is not the React entry point. |
| Accounts/admin | `auth.py`, `database.py`, login/register/change-password and user/role/audit/backup pages. | Implemented source and historical tests. No new security certification or full rerun in this archive pass. |
| Scenarios | `pages/scenarios.py`, scenario service, SQLite scenario records. | CRUD, official/custom/archive states and selected intersection inputs. |
| Traffic runtime | `services/simulation_service.py` imports `SumoSimulationEngine`; `simulation/sumo_engine.py`, `sumo_state.py`, `sumo_config.py`. | Active old simulation depends on SUMO/TraCI. The service includes shared-engine/session ownership logic. |
| Map assets | `sumo/Tagum_1`, `sumo/Tagum_2`, older `sumo/intersection_1`. | Two named study asset sets exist. The Tagum 3 document is a placeholder contract; no `Tagum_3` directory was present. |
| Rendering | Three.js bridge, canvas renderers, visual-network exporter, generated geometry. | Geometry-backed 2D/3D infrastructure. Old app also references external CDNs. |
| Recording/replay | Timeline generator/playback engine, generated JSONL/gzip, Compare Runs page. | Established historical workflow with saved artifacts. |
| RL | Gym environment, state/reward, QL/DQL/PPO training, checkpoint/resume, model loaders, CLI evaluation and training page. | Offline training/evaluation pipeline exists. June status identifies full live model selection and research-scale generalization as unfinished. |
| Reporting | Runs/Reports and Compare pages; report/evaluation files. | Prior report/export work exists; do not label every historical artifact a validated result. |
| FastAPI bridge | Parent `backend/` also exists and imports the SUMO engine. | An earlier bridge coexists with Dash; it is distinct from SmartFlow's later native API. |
| Earlier custom simulation | `simulation/engine.py`, vehicles, pedestrians and controller modules. | Older reference/test implementation predating the active SUMO path; it is not the current new native engine. |
| Tests | 30 files, 176 methods from AST inspection. | Inventory only; old runtime and old suite were not rerun. |

Observed old artifact inventory: 24 files under `data/models/`, four evaluation files, 57 timeline-directory files, five generated report files and three backup files. Counts include sidecars/compressed variants; they are not counts of independently validated experiments. The old model registry contains absolute paths back into trapik2, and old training-job log paths are also absolute. Preserve that workspace as historical evidence if those results matter.

The older codebase implemented much of the original application's workflow. It does **not** prove that the original ambitious behavioral models, local calibration, generalizable RL improvement or final research evaluation were completed.

## 6. Progress of the newer SmartFlow codebase

Paths here are relative to the **SmartFlow folder being retained**.

| Area | Current implementation | Remaining qualification |
| --- | --- | --- |
| Frontend | React/TypeScript/Vite, Three.js; dashboard, scenarios, training, runs/reports, comparison and admin pages. | Current engine pass did not rebuild or visually verify the frontend; previous browser/build evidence predates some changes. |
| API | FastAPI routes, auth bridge, scenario/run persistence, WebSocket frames, native runtime. | One shared process-local live engine remains. Independent concurrent operators and hosted ownership/security still need acceptance work. |
| Map/network | Cached OSM extract and `data/networks/tagum_network.json`; five junctions, 12 road segments, 24 directed lanes. | Lane widths/counts, signals, turns and demand need field validation. Map geometry is not actual traffic data. |
| Native traffic | `simulation/traffic_engine.py`, version `native-3`; 0.1-second stepping, IDM-style following, hard gaps, connected turns, downstream storage and exclusive junction reservations. | One vehicle reserves the whole junction; no lane changing/overtaking/motorcycle filtering. Capacity realism remains a research risk. |
| Vehicles/pedestrians | Different vehicle dimensions/speed factors; pedestrian crossings and waiting; emergency service requests through safety rules. | These are modeled behaviors, not calibrated local behavior or independently trained agents. |
| Scenarios/events | Complete native configuration, signal plans/offsets, scheduled demand, trips/CSV, mixed vehicles, lane closures/reopenings and speed restrictions. | Real observations and a final data-collection protocol are still needed. Legacy detailed disruption JSON is rejected explicitly until migrated. |
| Routing | Travel-time/queue costs, connectivity and supplied turn restrictions; closure avoidance and congestion rerouting with a threshold/cooldown. | Separate from signal RL; arbitrary browser-based road editing/import is unfinished. |
| RL | QL, DQL/DQN and PPO adapters, 30-value observations and five service actions; training/save/load/inference and compatibility checks. | One selected junction is controlled. Smoke training establishes execution, not quality, optimality or coordinated network learning. |
| Metrics/evidence | Vehicle/pedestrian waits, queues, throughput, travel time, speed/density, pending/dropped/unfinished demand and conservation diagnostics. | Research must report the unfinished population and avoid conclusions from reward or completed trips alone. |
| Recording/evaluation | JSONL/gzip, manifests, replay, complete-input comparison signatures, headless experiments, saved-scenario training/evaluation tools. | Current tests cover representative paths; full browser/research release acceptance remains. |
| Historic assets | Old SUMO modules/assets, copied model/report/evaluation files still exist. | Retained history is not an active SUMO dependency or a current native result. |

### What the September 23 continuation changed

The owner resumed Python engine work after the documentation review. Before changes, the existing **27-test suite passed**. The continuation then addressed additional gaps and introduced `native-3`:

- Scenario updates preserve omitted fields, including `engine_config`; supplying an explicit object replaces it, and `{}` clears it. This protects older clients that omit native settings. The React types/editor still need a deliberate native-settings UI.
- Nested malformed configuration now raises validation errors instead of reaching uncontrolled type errors. Nonempty legacy disruption fields produce migration guidance rather than being silently ignored.
- Scheduled closures are applied before arrivals at the same timestamp, including time zero; failed demand scheduling preserves prior engine state.
- A blocked all-way-stop exit no longer prevents an unrelated usable exit from receiving service.
- RL minimum holds respect the controlled junction's limits without changing other junctions; requests to control a different junction are rejected. Policy decisions and safety intervention information are recorded separately.
- Runtime policy metadata includes an artifact content hash, and registered model identity is attached to live/recorded results. Evaluator and headless paths share native policy stepping.
- Failed playback validation does not interrupt a live run. Startup failure does not allocate an orphan running record. Manual completion finalizes stored metrics immediately; live scheduling accounts for computation time.
- Recording initialization failures are persisted as errors. Playback validates recorded version, continuity, frame count and completion. Render frames preserve closed-lane IDs and expose entity counts/limits.

These behavior changes alter the experiment contract. **SUMO-era and `native-2` models/recordings must not be reused as `native-3` experiments.** Retain them as historical artifacts; regenerate compatible models/recordings for new evaluation. Do not edit metadata to bypass compatibility checks.

### Captured verification at this checkpoint

All commands below ran from SmartFlow on September 23, 2026. Integration tests use temporary databases/artifacts; this verification did not use the main research database for test writes.

| Check | Captured outcome |
| --- | --- |
| `.venv/Scripts/python.exe -m unittest discover -s tests -v` before continuation | 27 tests passed in 79.577 seconds. |
| New engine regressions, targeted run | Seven passed. |
| Full suite after continuation | **40 tests passed in 72.961 seconds**, across five files: 7 core, 12 experiment, 12 integration, 2 learning, 7 regression methods. |
| Learning coverage within that suite | Actual short QL/DQL/PPO training, save/load and inference; Gym environment checks. No model-quality claim. |
| API/evidence coverage | Scenario preservation/clear/rejection, safe bad-playback handling, startup failure, manual completion, JSON export provenance, recording failure, and matched headless/evaluator results. |
| `npm run check:api` | Passed Python compilation. This command is not a frontend build. |
| `git diff --check -- backend simulation services tools tests` | No whitespace errors in the tracked diff; Git emitted line-ending notices. |
| Native peak-event CLI, seeds 11/22/33 | Three completed synthetic experiments, each 20 seconds of warmup plus 300 measurement seconds. Both vehicle and pedestrian conservation errors were zero. |

The synthetic CLI output is at `data/generated/experiments/native3_checkpoint_20260923.json`. It is ignored by Git under the current rules, so a source-only clone will not include it unless deliberately retained.

| Seed | Requested vehicles | Lifetime completed | Unfinished at cutoff | Dropped | Vehicle / pedestrian conservation error |
| --- | ---: | ---: | ---: | ---: | --- |
| 11 | 100 | 20 | 80 | 0 | 0 / 0 |
| 22 | 108 | 23 | 85 | 0 | 0 / 0 |
| 33 | 117 | 28 | 89 | 0 | 0 / 0 |

These are accounting checks for a synthetic fixed-time scenario, not measured Tagum traffic or evidence of RL improvement. The many unfinished trips matter and must remain visible. Passing conservation does not resolve the simplified junction-capacity assumption.

### Progress against the chapters

“Implemented/tested” below refers to specified software evidence, not fulfillment of the whole research objective.

| Requirement | Older trapik2 progress | Current SmartFlow progress | Evidence still needed |
| --- | --- | --- | --- |
| Original objective 1 / revised objective 1: local road environment | SUMO map assets and visual export for Tagum 1/2. | Connected five-junction OSM-derived graph; geometry/connectivity tests. | Final study boundary, field-checked lanes/turns/signals and map assumptions. |
| Original objective 2: heterogeneous autonomous road users | SUMO/TraCI entities and older agent-oriented code/docs. | Mixed vehicle dimensions/speeds, following, protected pedestrian crossings. | Do not claim learned road-user behavior, noncompliance, filtering or overtaking without implementation and evidence. Revised scope narrows this claim. |
| Original objective 3 / revised objective 2: traffic inputs | Configurable density/scenario generation. | Seeded arrivals, demand windows, explicit trips and CSV/provenance support. | Actual dated counts, turning/OD estimates, calibration and held-out data. |
| Revised objective 3: configurable interface | Dash scenario/control workflows. | React/API workflows; native API round trips tested. | Browser native-settings editing, model selection and complete UI acceptance. |
| Original objective 5 / revised objective 4: disruptions/rerouting | SUMO disruption configuration and scenario infrastructure. | Closures/reopening, slowdown events, alternative routes and custom graph path in Python. | Calibrated closure cases, defined roadway-change comparisons and a user-facing editor if required. |
| Revised objective 5: event scenarios | Density/disruption scenario support. | Additive time windows and synthetic peak/construction/recovery example. | Observed/justified event schedules, holiday assumptions and comparative evaluation. |
| Original objective 4 / revised objective 6: RL signals | Offline QL/DQL/PPO train/evaluate/replay pipeline. | Native training, model binding, inference and protected actions pass smoke checks. | Research-quality training, held-out comparisons, required junction coverage and adviser-approved protocol. |
| Revised signal-placement purpose | Existing intersection signal operation. | Per-junction signal plans and simplified all-way-stop alternative. | Credible unsignalized baseline, candidate placements, calibration and justified findings; no automatic optimal-placement result exists. |
| Chapter 2 persistence/reporting | SQLite, timelines, reports and comparison infrastructure. | Current provenance and representative save/replay/export tests. | Complete browser acceptance, result reproducibility on another machine and final manuscript tables. |
| Chapter 2 deployment/security/maintenance | Local Dash assumptions and historical guardrails. | Local native API/UI foundations. | Hosted ownership/session/resource limits, recovery rehearsal and deployment verification. |

No defensible overall “percentage complete” can be calculated from file counts. The software foundation is substantial; final data validation, calibrated model validity, research evaluation, UI integration and deployment are separate unfinished deliverables.

## 7. What to preserve when moving SmartFlow

The purpose of this section is to avoid leaving unique evidence behind. **No relocation, deletion, database rewrite or paid hosting action has been performed by this record.**

1. **Keep a complete checkpoint of both folders before moving.** Preserve SmartFlow's uncommitted and untracked work as well as its own `.git`. Keep the old parent as an archive until the relocated app and needed research evidence have been verified.
2. **Move the whole SmartFlow project, including this file and `docs/research_sources/`.** Both manuscripts now have byte-identical copies there. The archive and working-document links use paths relative to SmartFlow rather than depending on the old parent location.
3. **Preserve source and reproducible inputs:** `src/`, `public/`, `backend/`, `simulation/`, `services/`, `tools/`, `scripts/`, `tests/`, configuration/entry-point files, npm lockfile, Python requirements, and `data/networks/` plus `data/scenarios/`.
4. **Back up data/artifacts separately.** The current Git ignore rules exclude the main SQLite database, backups, models, `data/generated/` and `assets/generated/`. A Git push or fresh clone alone is not a full research backup. Stop writers and make a coherent database/artifact backup; do not copy only an actively changing SQLite file while ignoring its journaling state.
5. **Preserve unique older evidence deliberately.** The parent has more timeline-directory files than SmartFlow (57 versus 51 at inspection). Models/evaluations may be copied historical artifacts; matching file counts or sizes are not proof that all content is identical. This archive includes manuscripts and a history, not the entire old source, database or approximately 661 MB of old timelines.
6. **Recreate environment dependencies at the destination.** Use the existing `package-lock.json`, `requirements.txt` and `requirements-dev.txt`; rebuild `.venv` and install Node dependencies. Existing `.venv`, `node_modules`, caches and `dist/` are replaceable environment/build outputs, not the authoritative source. Do not depend on moving a Windows virtual environment unchanged.
7. **Launch from the new SmartFlow root.** Core config and network paths resolve within SmartFlow, but some recording/report paths are relative to the working directory. Review environment overrides such as `SMARTFLOW_DB_PATH`, API/frontend addresses and model/artifact paths before starting. Keep secrets private and provision them separately.
8. **Check database references after relocation.** The inspected current main database had 18 nonempty model paths, 21 timeline paths and three training-log paths; these were relative, with no detected parent-folder references in those fields. This is a scoped check, not a guarantee that every string in every database/config/artifact is portable. The old database had absolute model/log paths back to trapik2; do not overwrite the current database with it as a shortcut.
9. **Regenerate current native models/recordings as needed.** Historic SUMO assets can stay archived. They are neither native model inputs nor compatible `native-3` policies. Do not mistake copied old evaluation reports for new-engine results.
10. **Verify the destination before retiring the parent:** Python suite, API compilation, frontend build, login, native configure/start/pause/stop, recording/replay, report export, and one headless experiment. Check that the process uses the new database and source location. A fresh-location test has not yet been performed.

Initial commands, from the relocated SmartFlow root:

```powershell
npm ci
npm run venv:create
npm run venv:install
.venv/Scripts/python.exe -m pip install -r requirements-dev.txt
.venv/Scripts/python.exe -m unittest discover -s tests -v
npm run check:api
npm run build
```

Start the API with `npm run api` and React in another terminal with `npm run dev`. Use README for the current configuration requirements. Native operation does not require installing SUMO; directly invoking retained historical SUMO modules does.

## 8. Decisions and work that remain open

- **Academic scope:** confirm the exact deadline, final roads/junctions, whether RL controls one junction or multiple/coordinated junctions, and which algorithms the panel requires. The owner explicitly said the RL scope was unclear.
- **Actual data:** collect/obtain dated vehicle/pedestrian counts, turning movements or OD estimates, queues/travel observations, road/signal details and provenance. Separate calibration data from evaluation data.
- **Model validity:** test discharge/capacity and traffic plausibility, especially the whole-junction reservation simplification and single modeled lane per direction. Data collection cannot be replaced by OSM import or visual polish.
- **Research results:** define a fair fixed-time baseline, matched arrivals, warmup/window semantics, repeated seeds, uncertainties, incomplete trips, and signal-versus-routing comparisons. Negative or inconclusive results remain valid findings.
- **Application completion:** native settings/model selection in the React workflow, current 3D geometry/constraint display checks, full browser build/workflow acceptance, and bounded online operation.
- **Manuscript alignment:** replace obsolete SUMO/TraCI design claims with the native architecture; explain the separate routing algorithm, actual study boundary, controller scope, data provenance, limitations and current database schema. Do not alter the archived original/revised texts to pretend these later changes were already present.
- **Claims needing care:** the revised title and scope must agree about routing/RL; literature performance percentages are not SmartFlow results; referenced ISO practices are not certification; signalized-versus-stop experiments are not a civil-engineering installation recommendation.

The 35-day delivery plan prioritizes one complete reproducible experiment workflow, early scope/model/data gates and a five-day submission buffer. This history records progress; it does not authorize expanding into a citywide simulator or changing academic requirements without an explicit decision.

## 9. Archive integrity and how to use the manuscript appendices

Exact sources retained within SmartFlow:

- [Original Chapters 1–2 PDF](<docs/research_sources/SMARTFLOW_CHAP1_AND 2.docx.pdf>) — 73 pages, 5,083,799 bytes.
- [Revised Chapters 1–2 PDF](docs/research_sources/FINAL_SIGURO_CHAPTER1_AND_2.docx.pdf) — 74 pages, 5,103,869 bytes.

SHA-256 fingerprints, verified against the parent originals after copying:

```text
Original: da1098b0b8b0adcc5e195c12bddef1e7c3c968f1506831ee6d02a45de76bca61
Revised:  662779c2c50c78b3aadf9cdb8664fe5636ed2c3270ef5206e36c906fab57a7c6
```

The appendices are **source-text transcriptions, not newly rewritten chapters**. Each source PDF page is represented once, in source order. The extraction retains wording, spelling and literature reference markers; only outer page whitespace is trimmed. Code blocks keep the layout-oriented text from being interpreted as Markdown. PDF layout, images, diagrams, reading order and table-cell alignment cannot be guaranteed by text extraction; consult the copied PDFs for those. No missing or blank-text page was found in either extraction. References are included so citations are not separated from their source bibliography.

The narrative above is the current interpretation and progress assessment. The material below is the historical manuscript and may contain obsolete SUMO plans, proposal language or unresolved wording. Its inclusion does not turn those statements into implemented facts or independently verified literature claims.

**Archive verification, September 23:** all 73 original and 74 revised page transcriptions were compared with a fresh layout-text extraction from the copied PDFs and matched exactly after trimming outer page whitespace. Both copied PDFs matched the parent originals by SHA-256. All 38 local file links across this record and the four working documents resolved within SmartFlow; code fences were balanced. This verifies text/source integrity and local link portability, not a fresh-location application launch. Figures were reviewed in representative rendered pages; the copied PDFs preserve every original diagram and image.

## Appendix A. Original Chapters 1 and 2

Complete text extracted from the 73-page original manuscript. PDF page positions include the title page; figures remain in the linked source PDF.

### Original title page

#### Original PDF page 1

```text
SMARTFLOW: AN AI-DRIVEN AGENT-BASED SIMULATION OF
  AUTONOMOUS VEHICLES AND PEDESTRIANS WITH REINFORCEMENT
             LEARNING–BASED TRAFFIC SIGNAL OPTIMIZATION




















                        A Capstone Project Presented to
                      Faculty of the Institute of Computing
                          Davao del Norte State College
                            New Visayas, Panabo City



                         A Capstone Project Presented by:




                            Johnfel Anthony B. Caredo
                               Prille Vincent Salibay
                                  Karen B. Solano




                                     June 2026
```

### Original Chapter 1 — Introduction

#### Original PDF page 2

```text
CHAPTER I

                                        INTRODUCTION



Background of the Study
        The    rapid    urbanization      and    increasing     population     density     in  cities
worldwide    have    created    significant   challenges    in  traffic management,       including
traffic congestion,      environmental      pollution,   increased     fuel   consumption,       and
inefficiencies   in urban mobility services [1]. As the number of vehicles continues
to  rise,   transportation      infrastructures      in  many      urban     areas    struggle     to
accommodate        growing     traffic  demand,      resulting   in  longer    travel   times   and
substantial economic losses. These challenges have made traffic congestion one
of the most pressing transportation issues faced by cities worldwide, highlighting
the need for more effective and adaptive traffic management strategies [2].

        Despite    the   implementation      of  various    traffic management        approaches,
many urban centers continue to rely on conventional traffic signal control systems
that  operate    using   fixed  or  pre-timed    schedules      [3]. These    systems     are  often
unable to adapt to      changing traffic conditions, causing inefficient traffic flow and
increased congestion [4].        As  a result,   green signal phases        may be allocated to
underutilized    lanes   while   heavily   congested     approaches       experience     prolonged
delays.   This   lack   of  adaptability    not  only   reduces    traffic  throughput     but  also
contributes     to  economic       losses,    commuter       dissatisfaction,     and    increased
greenhouse gas emissions. Consequently, transportation researcher s and traffic
management agencies are exploring              more intelligent     and   proactive approaches
capable of responding to dynamic traffic environments.

        To    address      these    global    traffic   management         challenges,     Artificial
Intelligence    (AI)   has    emerged      as   a   promising     technology      for   developing
intelligent transportation systems and adaptive traffic control solutions [2]. Recent
```

#### Original PDF page 3

```text
studies   have    demonstrated       that  AI-driven    signal   control   systems,     particularly
those   utilizing   Deep    Reinforcement        Learning     (DRL),    significantly   outperform
traditional fixed-time controllers by dynamically adjusting signal timings according
to real-time   traffic conditions,    reducing    average     traffic delays by    up  to  30%    [5].
Furthermore, the scientific community has extensively explored the integration of
Reinforcement      Learning     (RL)   and   multi-agent    systems     to solve complex       traffic
dilemmas. Research has shown that DRL applied within the Simulation of Urban
Mobility (SUMO)       environment      can reduce intersection waiting times by as much
as  33%    compared      to conventional      control  systems     [6]. To  improve the      realism
and adaptability of intelligent traffic control models, microscopic traffic simulation
frameworks      have    been    developed     to   enable    AI  agents    to  generalize    across
dynamic and      previously    unseen    traffic  scenarios [7]. Additionally, benchmarking
studies   have    reported    that  RL-enhanced        traffic management        approaches      can
reduce delays by up to 80% in high-demand traffic situations while contributing to
environmental       sustainability    through     reduced     vehicle    idle  times    and    lower
greenhouse gas emissions [8]. Collectively, these developments demonstrate the
growing    role  of  AI-driven    simulation    and   Reinforcement       Learning     as  effective
solutions for modern traffic management and urban mobility challenges.

        The   traffic crisis  in  the  Philippines has      reached    a critical threshold,     with
recent   data   from 2025     identifying   the country as     one   of  the most    congested in
Asia   [8]. Projections     from   the  Japan    International    Cooperation      Agency     (JICA)
indicate that without significant technological intervention, the volume of vehicles
in major Philippine urban centers will increase by more than 2.25 times by 2035,
further exacerbating      the billions   of pesos lost     daily in economic       productivity.   To
combat this, the Philippine Development Plan (PDP) 2023–2028 emphasizes the
"digital transformation"     of  physical   connectivity,    calling  for the adoption of smart
transport    infrastructure    to  improve     urban    mobility   and   climate    resilience    [9].
However, most current local          implementations remain         limited to surveillance and
manual    enforcement       rather   than   autonomous       optimization.     This   national   gap
highlights     the    urgency       for   locally-developed,        AI-driven      solutions     like
```

#### Original PDF page 4

```text
SMARTFLOW          that   can   adapt    to  the  unique    road   constraints    and    behavioral
patterns of Filipino commuters.

        The    study   is  focused     on   a   primary    high-volume      intersection     and   its
immediately      adjacent    road    networks     in  Tagum     City,   Davao     del  Norte.   This
specific  locale   was selected      because     it represents a     critical "bottleneck"    where
diverse   road   constraints—such        as public   utility vehicle   (PUV) stops, pedestrian
crossings,    and   narrow    lane   widths—frequently        disrupt   traffic flow.  To  maintain
high   fidelity, the   simulation    environment      is  modeled      as  a  real-world-inspired
simulation model of the actual site, using field observations and visual references
to replicate   real-world geometry and agent behaviors. By limiting the scope to a
single  intersection    and   its connected road segments, the study ensures a deep,
granular analysis of traffic impact and signal efficiency without the computational
overhead of a city-wide model.

        Despite     the  implementation        of  modern     traffic  management        strategies,
urban centers like Tagum City continue to struggle with the unpredictable impacts
of road constraints. Currently, traffic management offices often operate reactively
responding     to congestion only after it       has already formed due to incidents such
as  road   construction,    lane closures, or      accidents.    There    is a  significant lack of
proactive    decision-support      tools   that  can    simulate    and   analyze     how   specific
physical   constraints    may    influence    congestion     buildup   and   traffic flow. Without
the  ability to  "test"  road   closures    or  evaluate    signal effectiveness      in a  realistic
simulation    environment      before   actual   implementation,      authorities    are  forced   to
rely on   trial-and-error, which     leads to avoidable economic losses and commuter
dissatisfaction.    This   study   addresses      the  need    for  an  AI-driven,    agent-based
platform   that   can   analyze     the  ripple   effects   of  road   constraints    and    provide
optimized signal responses using Reinforcement Learning to mitigate bottlenecks
before they manifest in the real world.

        This    study    proposes       SMARTFLOW,           an    AI-driven    simulation-based
decision-support platform designed to analyze the impact of road constraints and
```

#### Original PDF page 5

```text
optimize traffic flow through Reinforcement Learning (RL). Utilizing the Simulation
of  Urban    Mobility    (SUMO)      and   the   TraCI    API,   the   system    implements      an
agent-based model        where vehicles and pedestrians act as autonomous entities
with  intelligent  behaviors.    Unlike   traditional   static  traffic management       systems,
SMARTFLOW          enables     traffic managers      to  simulate    various   traffic  scenarios,
such   as road construction,      accidents, lane closures, and flooding, to proactively
evaluate     congestion      patterns    and    traffic  signal    responsiveness.        The    RL
component      dynamically     adjusts    traffic signal   timings    based    on   current   traffic
conditions,   providing    a  data-driven    approach     to  traffic management and urban
mobility planning.

        This   study   aligns   with   Sustainable     Development       Goal   (SDG)     9, which
promotes     industry,   innovation,   and   resilient  infrastructure,    and   SDG    11,  which
focuses   on   creating sustainable cities and communities through improved urban
mobility and    transportation systems. Furthermore, the study supports the Davao
del Norte   State College      (DNSC)     Research, Development, and Extension (RDE)
Agenda     on   Information    and    Communication        Technology      for Development       by
applying     Artificial    Intelligence,     simulation      technologies,       and     intelligent
decision-support        systems      to    address      transportation      and     infrastructure
challenges.

        Generally,    SMARTFLOW functions as             a simulation-based       traffic analysis
and  decision-support      system     that  enables    users   to model traffic scenarios and
evaluate    the  effects   of  different   road   constraints    on   traffic flow.  The    system
utilizes  Reinforcement       Learning    to  generate     adaptive    traffic signal   decisions,
allowing    traffic  managers       and    researchers      to  assess     traffic  performance,
compare     signal   control   strategies,   and   identify   potential   congestion    mitigation
measures before real-world implementation.




Objectives of the Study
```

#### Original PDF page 6

```text
General Objective

        To develop SMARTFLOW, an AI-driven agent-based traffic simulation and
decision-support      system      that   models     autonomous        vehicle    and    pedestrian
behavior     and    utilizes   Reinforcement        Learning     for   adaptive     traffic  signal
optimization under varying traffic and road constraint conditions.

Specific Objectives

    1.  Design a traffic simulation environment based on a selected intersection in
        Tagum City, incorporating road layout, traffic flow patterns, and pedestrian
        behavior.
    2.  Develop     an   agent-based       model    where     vehicles    and   pedestrians      are
        represented     as   autonomous       entities  with  heterogeneous       behaviors     and
        dynamic interaction within the simulation environment.
    3.  Implement       dynamic       traffic   generation      using     scenario-based        and
        configurable traffic demand models instead of relying on static predefined
        inputs.
    4.  Develop a Reinforcement Learning–based traffic signal control component
        that optimizes signal timing based on real-time traffic conditions.
    5.  Simulate     and   evaluate     multiple   traffic  and   road    constraint    scenarios,
        including   varying    traffic densities,   pedestrian    demand      levels,  emergency
        vehicle   conditions,    lane   closures,    road    construction,    and   accidents,    to
        assess      the    adaptability     and     performance        of   the    reinforcement
        learning–based traffic signal control system.

        Significance of the Study

                This     study     contributes     to    the    advancement        of    intelligent
        transportation      systems      by    integrating     agent-based        modeling      and
        reinforcement        learning     into    a    localized      traffic   simulation      and
        decision-support       platform.     The    proposed      system      enables     dynamic
        interaction    between     autonomous        vehicle   and   pedestrian     agents    while
```

#### Original PDF page 7

```text
allowing     adaptive     traffic  signal    optimization      through    Reinforcement
        Learning (RL).     Unlike   traditional   traffic management approaches that rely
        on   static  signal    timing   and   reactive    congestion     handling,    the   system
        provides    a  simulation-based      environment      where    various traffic and road
        constraint    scenarios    can   be  analyzed     before   real-world    implementation.
        By   incorporating    conditions    such    as  varying   traffic densities,    pedestrian
        demand,     emergency      vehicle    presence,    lane closures, road construction,
        and   accidents,     the  study    promotes     a  more    proactive    and    data-driven
        approach to urban traffic management.

        The findings of this study are expected to benefit the following:

    ●   Local Government Units (LGUs) and Traffic Management Authorities.
        The   system     may    serve   as  a  simulation-based       decision-support      tool for
        evaluating    traffic conditions,    road   constraints,    and   adaptive   traffic signal
        strategies     prior   to   actual     implementation.       This    can    assist    traffic
        management        offices   in  anticipating    congestion     buildup    and   assessing
        possible traffic responses under disruptive road conditions.

    ●   Traffic    Planners      and    Urban      Developers.       The    simulation     platform
        provides insights into traffic flow behavior, congestion patterns, and signal
        performance, supporting more informed planning and development of road
        networks, intersections, and traffic management strategies.

    ●   Traffic   Enforcers.      Through     simulated    traffic  scenarios    and   congestion
        analysis,    traffic  enforcers    may     gain   a  better   understanding       of  traffic
        bottlenecks      and    road    behavior,    which     can    support     more    effective
        on-ground traffic management and coordination.

    ●   Drivers    and   Road     Users.    The   implementation      of adaptive traffic signal
        optimization     may    help   reduce    unnecessary      waiting   times    and   improve
        overall   traffic flow   efficiency,   contributing    to  a  more     convenient     travel
        experience.
```

#### Original PDF page 8

```text
●   Pedestrians.      The    system    incorporates     pedestrian     behavior     within  the
        simulation environment,        promoting     safer and more balanced traffic signal
        management that considers pedestrian crossing activity alongside vehicle
        movement.

    ●   Researchers        and    Future    Developers.       This    study   may    serve    as   a
        reference     and   foundation     for   future   research    involving    reinforcement
        learning,   intelligent  transportation     systems,    agent-based      simulation,    and
        AI-driven traffic management technologies.


Scope and Limitations

        This   study   focuses    on   the  development      of  SMARTFLOW,          an  AI-driven
agent-based      traffic simulation    system     designed     to  model    and   analyze    traffic
behavior within a selected intersection and its adjacent road segments in Tagum
City. The system operates through a localized simulation environment developed
using the Simulation of Urban Mobility (SUMO), where vehicles and pedestrians
are represented as autonomous agents capable of dynamic interaction within the
road network.     Reinforcement Learning         (RL) is implemented as one of the traffic
signal   control   mechanisms,        allowing    the   system     to  optimize    signal    timing
decisions based on simulation-generated traffic conditions.

        The    simulation    environment      incorporates     essential    traffic components,
including vehicle flow, pedestrian crossings, lane usage, traffic signal operations,
and   configurable    traffic scenario    parameters.      These    parameters     include   traffic
density,   pedestrian    density,   and    emergency      vehicle    status.  The    system    also
includes    configurable     road    constraint    conditions,     including    constraint    type,
severity   level,  and   affected   lane.  Road    constraint    scenarios    may    include   lane
closures,   road   construction,     accidents,    and   temporary     road   blockages.    These
conditions    are   simulated     to  evaluate     system     adaptability    and   traffic  signal
performance under varying traffic and road disruption situations.
```

#### Original PDF page 9

```text
To   improve     realism,   the   study    incorporates     heterogeneous        driver   and
pedestrian      behaviors       within    the    simulation      environment.       Vehicles      and
pedestrians are      modeled with      varying behavioral patterns,         including aggressive
driving  tendencies,     inconsistent     lane  discipline,   delayed     reaction behavior,      and
non-compliant      pedestrian      movement,      to   better   approximate      real-world    urban
traffic conditions.     The    study   also    utilizes  field  observations,      traffic behavior
analysis,   and   visual   references     from    the  selected    area   to  approximate      actual
road geometry and traffic flow behavior within the simulation environment.

        However, the      system     does   not utilize live traffic feeds, CCTV processing,
GPS    tracking,   or  real-time   sensor    integration.    The   real-time    metrics   within   the
simulation      environment         generated        by     the     system       refer     only     to
simulation-generated        traffic  data   within    the  SUMO       environment      and    do  not
represent    live  road   conditions.     The   simulation    environment       serves    only  as   a
real-world-inspired      approximation       intended    for  traffic  analysis    and   evaluation
purposes.

        The   study    is limited   to a  simulation-based implementation            and   does not
involve    deployment       within   actual    traffic  infrastructure.     The    system     is   not
connected     to  physical    traffic signals,    Internet   of  Things    (IoT)  devices,    or  live
traffic management systems. Additionally, the study is limited to a localized road
network surrounding        a selected     intersection   and   does    not represent a city-wide
traffic model. While      the system includes configurable traffic scenarios,               selected
road   constraint    conditions,    and    varying    behavioral     patterns,   it does    not  fully
account    for  all real-world variables      such as    extreme     weather conditions,       highly
unpredictable      human      decisions,     large-scale     traffic  network      interactions,    or
complex multi-city traffic dynamics.

        Despite    these   limitations, the    study   aims   to  demonstrate the       potential   of
integrating     agent-based        simulation      and     Reinforcement         Learning      as    a
simulation-based        decision-support         approach       for    adaptive      traffic   signal
```

#### Original PDF page 10

```text
optimization and traffic analysis under varying traffic scenario and road constraint
configurations.

Review of Related Literature and Studies

Related Literature

Traditional Traffic Management Systems
        Traditional    traffic management        primarily   relies  on   fixed-time   control   and
manual     enforcement       to  regulate    urban     mobility.   Fixed-time     signal   systems
function   based    on  preset    timing  plans    developed     from   historical   traffic volume
studies [11].   While these     systems     are  cost-effective and      easy to    maintain, they
are   inherently    unable     to  accommodate         stochastic     traffic fluctuations,     often
leading    to  excessive     delays    and    queue     spillback   during    peak    periods    and
inefficient green time allocation during varying demand conditions  [12]. In many
developing     urban   centers,    the  limitations   of  these   static systems are      mitigated
through    manual    traffic  enforcement,      where    officers   override    signal   operations
based    on  visual   observation     [13].  However,     this reactive    approach     is prone   to
human     error  and   lacks   the  data-driven     precision   required    to optimize    complex
road networks [14].

Intelligent Transportation Systems (ITS) in the Philippine Context
        Intelligent   Transportation     Systems     (ITS) integrate     information technology
and data-driven strategies to improve traffic efficiency and road safety [15]. In the
Philippines,    ITS    development       has    focused     on   smart    city  frameworks       that
combine     automated       monitoring     with   reactive    congestion      management        [16].
Despite the widespread deployment of traffic signal systems in urban areas, most
implementations       rely   on   fixed-time    counters    that   change     lights   sequentially
regardless of actual traffic conditions         in respective     lanes. These     predetermined
timing   systems      fail to  adapt    to   real-time    traffic density    variations,    causing
unnecessary delays        and congestion even when some lanes have minimal or no
traffic [17].   This   highlights    the  critical  need    for adaptive     traffic management
```

#### Original PDF page 11

```text
systems     that  can    continuously      monitor    lane-specific     conditions    and    provide
centralized     coordination       to    optimize     traffic   flow    across     interconnected
intersections.

Integration of Artificial Intelligence in Traffic Management
        The integration      of Artificial Intelligence (AI) marks a shift from reactive to
proactive    traffic  management.         AI  applications     utilize   machine     learning    and
predictive   analysis    to transform     chaotic   vehicular    patterns   into organized     flows
[18].  By    processing      real-time    traffic  data    from    surveillance     cameras      and
neighboring        intersection       information       through       distributed       Multi-Agent
Reinforcement Learning algorithms, AI-driven traffic control systems can optimize
multiple    objectives    including     reducing     average     vehicle    queue     lengths    and
minimizing waiting times        at  interconnected intersections [19]. This technological
evolution   provides    the   necessary     foundation     for more    specialized applications,
such   as   computer     vision   and    reinforcement      learning,   to  handle    the  dynamic
variables of urban road networks.

Reinforcement Learning in Traffic Signal Control
        Reinforcement       Learning     (RL)   has   emerged     as   a superior    alternative    to
traditional   control   by  allowing    agents    to  learn   optimal   signal   policies   through
continuous     interaction    with   a   simulated    environment       [20].  Unlike    rule-based
systems,     RL   controllers    utilize  reward    systems      to  dynamically     adjust    signal
phases     based     on   current   demand      [21].   Global    studies    indicate    that  Deep
Reinforcement       Learning    (DRL)    architectures,     when    integrated     with  simulation
platforms,     can    significantly     reduced      delays     [22].   Countries      successfully
implementing      RL    in  traffic  simulations     demonstrate      that   these    systems     are
particularly   effective   at managing      unpredictable      variables,   such    as  emergency
vehicle presence and pedestrian surges [23].

Agent-Based Traffic Simulation and SUMO
        Agent-based       modeling    (ABM)     provides the     microscopic     detail necessary
for  realistic   traffic  simulation,    treating    every   vehicle    and    pedestrian     as   an
```

#### Original PDF page 12

```text
autonomous entity       with unique     behaviors [24]. The Simulation of Urban Mobility
(SUMO)     is widely    recognized     in the  literature   as  the industry-standard       tool for
testing  RL-based      controllers,   owing    to its high-fidelity   modeling     and   the  TraCI
API, which enables real-time signal manipulation [25]. These simulations enable
researchers     to  model    "heterogeneous"        traffic—including     public   utility vehicles
(PUVs)    and    aggressive     driving    behaviors—which         is essential    for  accurately
representing the Philippine traffic landscape [26].

Related Studies and Systems

Dual-Targeting Deep Reinforcement Learning Traffic Signal Control System

        A study    by Kodama       et al. [27] proposed      a multi-agent traffic light control
system based on a dual-targeting algorithm, which emphasizes the reinforcement
of  traffic optimization     experience.     The    system    utilizes  a   deep    reinforcement
learning (DRL) agent integrated with the Simulation of Urban Mobility (SUMO) to
reduce waiting times at complex intersections.

The framework       consists of    a neural network handled by a Traffic Signal Control
System (TSCS). As illustrated in the conceptual diagram in Fig. 1, the input state
includes    vehicle   position    (($P_t$),    lane   density    ($D_t$),    change     in  density
($\Delta   D_t$),    and   velocity   ($V_t$),    which    are   processed      through    multiple
hidden layers (256 and 128 ReLU units) to output Q-values for action selection.
The   system     operates     through     a  closed-loop      interaction    where     the  SUMO
environment     provides    traffic states, and the      RL  agent   issues signal     commands
(actions) while receiving rewards based on the minimization of cumulative waiting
time.
```

#### Original PDF page 13

```text
Fig. 1. Conceptual diagram of the proposed traffic light control
                                             system.

        The   effectiveness     of the   dual-targeting    algorithm    was   validated    through
extensive     simulation     trials.   The    performance       output,     shown     in   Fig.   2,
demonstrates the       learning curves across 1,000 trials.         While    standard DQN and
Multistep     DQN       architectures      showed       higher     variance,      the    proposed
"Dual-Targeting" method achieved a significantly lower unbiased sample variance
of 0.02    at  the  1,000th    trial. This   visual  evidence     confirms    that  the   adaptive
learning   agent   successfully     stabilizes  and   minimizes     vehicle   waiting   time   as  it
gains more experience within the simulation.







       Fig. 2. Simulation results showing the reduction in waiting time using
                                  the proposed RL method.

        This system is highly related to SMARTFLOW as both utilize DRL and the
SUMO environment for adaptive signal optimization.                 A technical    benchmark for
state-space     definitions   (position   and   density)   and   reward    functions    based    on
"accumulated      waiting    time"   [30].   However,      SMARTFLOW          expands      on   this
foundation    by   introducing     localized   road    constraint   scenarios,     such   as   lane
closures     and    accidents      and    modeling      heterogeneous         pedestrian-vehicle
```

#### Original PDF page 14

```text
interactions to serve as a proactive decision-support tool for authorities in Tagum
City.

TrafficSim: Learning to Simulate Realistic Multi-Agent Behaviors

        A  research     study   by  Suo    et  al. [28] introduced     TrafficSim, a     multi-agent
behavior    model     designed     to  generate     realistic   and   socially   consistent     traffic
simulations.    Unlike    traditional   environments      that   rely  on   rigid, heuristic-based
traffic rules,  this system     leverages    real-world data      to learn   directly  from   human
demonstrations,       allowing    it to  capture    naturalistic    driving   behaviors     such    as
yielding, merging, and complex interactions.

The   TrafficSim    architecture     utilizes  an   implicit  latent   variable   model     to  jointly
generate    socially   consistent     plans   for  all actors    in a  scene.    As   shown    in  the
architectural   framework      in Fig. 3, the system processes a bird’s-eye view (BEV)
representation of the map and actor states through a CNN-based encoder. It then
employs     a graph    neural network (GNN)          to  model interactions between          agents,
followed by an MLP decoder that predicts long-term trajectories







Fig. 3. System architecture of TrafficSim illustrating the CNN encoder, interaction
                                graph, and trajectory decoder.

        The    effectiveness     of  the  TrafficSim    system     is demonstrated       through    its
ability to  generate     socially   consistent     and   diverse    multi-agent    trajectories.    As
illustrated  in Fig.  4,  the system     generates multiple plausible "futures" (shown in
red  and    blue)   for  each    vehicle    agent   based     on   a  single   observation     of  the
environment.     When     these    predictions    are  compared       to the actual ground truth
(shown     in  green),    the   results    confirm    that   the   system     accurately     predicts
```

#### Original PDF page 15

```text
naturalistic driving behaviors, such as lane maintenance and collision avoidance,
which are essential for high-fidelity urban simulations.









            Fig. 4. Visual output of TrafficSim showing diverse multi-agent
                  trajectory predictions and ground truth comparison.

        This study is highly relevant to SMARTFLOW as it provides the theoretical
and technical     justification for modeling vehicles and pedestrians as autonomous
agents with complex, non-linear behaviors. While TrafficSim focuses primarily on
learning   trajectories from real-world       datasets    to  improve self-driving evaluation,
SMARTFLOW          adopts selected      agent-based simulation principles           to a localized
Tagum     City   intersection    to   optimize    traffic  signal   timing   via   Reinforcement
Learning.    By   incorporating    Suo    et  al.’s findings   on  "socially   consistent"    agent
behavior,    SMARTFLOW           ensures     that  its  simulation    environment       remains     a
high-fidelity "localized simulation environment" of the actual study site.

IoT-Based Adaptive Traffic Signal Controller for Congestion Reduction

        A study    by AlMulla    et al.  [29]  developed     an adaptable traffic light control
system designed to improve flow at intersections by adjusting signal timing in real
time.  The   research     focuses    on   moving    away     from   rigid, pre-timed    controllers
toward a system that perceives actual road demand through integrated sensors.

        The system's architecture relies on an Internet of Things (IoT) framework
that utilizes  ultrasonic sensors positioned at specific distances along the road to
detect    vehicle    presence      and    measure      queue      length.    As   shown      in  the
architectural   framework      in  Fig.  5, data   from   these   sensors     is processed     by   a
```

#### Original PDF page 16

```text
central controller    that applies a smart algorithm to modify the default 60-second
green   time.   The   controller   dynamically      extends    or  reduces     the phase duration
based    on  the detected congestion          level,  ensuring    that  the intersection remains
responsive to fluctuating traffic volumes.


















         Fig. 5. System architecture of the IoT-based adaptive traffic signal
                                             controller.

        The system’s performance was validated through a working prototype and
an accompanying mobile application. As illustrated in Fig. 6, the system provides
a real-time visualization of congestion levels (e.g., Low, Medium, High) through a
smartphone       interface.   The    results   of  the   study    confirmed     that   the  adaptive
approach not      only  improved overall traffic flow but also significantly reduced the
average wait time for drivers at the intersection.
```

#### Original PDF page 17

```text
Fig. 6. Sample output showing the real-time congestion monitoring
                                           application.

        This   study   is  highly   relevant    to SMARTFLOW           as  it demonstrates       the
practical   application    of   queue-length      detection     for  signal   optimization.    Like
AlMulla   et al., SMARTFLOW seeks to replace inefficient fixed-time systems with
adaptive   logic.  However,     while   this  existing  system     focuses    on  a  physical   IoT
sensor deployment, SMARTFLOW utilizes Simulation of Urban Mobility (SUMO)
to model these same adaptive principles under localized road constraints—such
as accidents     or roadwork—allowing for a more diverse range of "what-if" testing
without the high cost of physical hardware installation.

Synthesis of Related Studies and Systems

        The      reviewed       studies     demonstrate         that    Artificial    Intelligence,
Reinforcement      Learning,     and   agent-based      simulation     have   become      effective
approaches for      adaptive traffic management          and   congestion    reduction. Existing
systems    successfully     implement     dynamic traffic signal optimization, multi-agent
interaction     modeling,      and     intelligent    traffic    analysis     using     simulation
environments such as SUMO and machine learning frameworks.

        However,     most    existing    studies   primarily    focus   on   generalized     urban
simulations,    real-time   sensor    integration,   or  trajectory   prediction    models,    with
limited  emphasis     on  localized traffic environments and road            constraint   analysis
within  the  Philippine    context.   Additionally,   many    systems either rely heavily        on
IoT  infrastructure    or  focus   solely  on   vehicle   optimization    without   incorporating
heterogeneous       pedestrian     behavior    and    localized   disruptive    traffic  scenarios
such as lane closures, flooding, and road construction.

        To   address    these    gaps,   SMARTFLOW           proposes     a  localized   AI-driven
agent-based        traffic   simulation       system      that     combines       Reinforcement
Learning–based traffic signal optimization with heterogeneous vehicle-pedestrian
interaction   and   road   constraint    simulation.    Unlike   existing   systems,     the  study
```

#### Original PDF page 18

```text
focuses on a selected intersection  its adjacent road segments in Tagum City and
aims   to   provide    a  simulation-based      decision-support      platform   capable     of
evaluating   adaptive   traffic responses     under   varying  traffic and   road  disruption
conditions.



Table  1.Comparative Analysis of Related Traffic Management Systems and
SMARTFLOW


    Features         Dual-Target        TrafficSim         IoT-Based        SMARTFLOW
                       ing  DRL             [28]           Adaptive
                          [27]                           Traffic Signal
                                                           Controller
                                                               [29]

 Main                Deep             Multi-Agent       IoT +               RL +
 Technology          Reinforcem       Trajectory        Adaptive            Agent-Base
                     ent Learning     Learning          Signal Control      Simulation

 Simulation          SUMO             Learned           Prototype-Bas       SUMO
 Environment                          Traffic           ed Traffic
                                      Environment       System

 Adaptive            ✔                                  ✔                   ✔
 Signal Control

 Autonomous          Partial          ✔                                     ✔
 Agents

 Pedestrian                           Partial                               ✔
 Modeling
```

#### Original PDF page 19

```text
Road                                                                           ✔
 Constraints
 Analysis

 Emergency                                                 Partial              ✔
 Vehicle
 Handling

 Real-Time                                                 ✔
 Infrastructure
 Dependency

 Localized                                                                      ✔
 Traffic
 Simulation


        Table   1  presents    the  comparative      analysis   of  existing  systems     and   the
proposed     SMARTFLOW          Traffic  System.     The   comparison      shows    that  existing
systems    have    contributed    important    features    to  traffic management,        such   as
deep   reinforcement      learning    for  adaptive    signal  control,   multi-agent    behavior
modeling, and IoT-based traffic monitoring.            However, each existing system also
has   limitations    when     compared       to  the   objectives     of  SMARTFLOW.           The
Dual-Targeting     DRL    system    provides    adaptive    signal  control   using SUMO and
reinforcement      learning,   but   it  does    not  fully  address     pedestrian     modeling,
emergency       vehicle    handling,    road    constraint    analysis,    or   localized    traffic
simulation.    TrafficSim     focuses     on    autonomous        multi-agent     behavior     and
trajectory learning, but it does not directly support adaptive traffic signal control or
road   constraint    analysis.    Meanwhile,      the  IoT-Based      Adaptive     Traffic  Signal
Controller    supports     adaptive    signal    control   and    partial  emergency       vehicle
handling,    but  it depends      on  physical    infrastructure    and   does    not  provide    a
simulation-based environment for testing different traffic disruption scenarios.
```

#### Original PDF page 20

```text
In contrast, SMARTFLOW integrates reinforcement learning, agent-based
simulation, pedestrian modeling, emergency vehicle handling, and localized road
constraint   analysis    within   a  SUMO-based         simulation    environment.      The   table
highlights that   SMARTFLOW addresses the               gaps   found in the existing systems
by  providing    a  simulation-based       decision-support      platform    that  can   evaluate
traffic scenarios   such    as lane   closures, road construction, accidents, pedestrian
congestion,     and   emergency       vehicle    conditions     without   relying   on   real-time
physical   infrastructure.    This   makes    SMARTFLOW          more    suitable   for  localized
traffic analysis in the selected intersection in Tagum City, as it combines adaptive
traffic signal   optimization    with  realistic  vehicle-pedestrian      interaction   and   road
disruption testing. Therefore, the comparison supports the need for the proposed
system and justifies its      development as       a more    comprehensive       AI-driven traffic
simulation and optimization tool.

Definition of Terms

Agent-Based       Simulation.     A   simulation   modeling     approach     in which individual
entities,  such   as   vehicles    and   pedestrians,     are   represented     as   autonomous
agents capable of interacting within a virtual environment.

Artificial Intelligence (AI). The capability of computer systems to perform tasks
that typically require human intelligence, such as learning, decision-making, and
adaptive problem-solving.

Autonomous         Agent.      An    independent       entity   capable      of   perceiving     its
environment     and   making    decisions    or performing actions without direct human
intervention.

Decision-Support System. A computer-based system designed to assist users
in analyzing scenarios and making informed decisions through data analysis and
simulation.
```

#### Original PDF page 21

```text
Emergency       Vehicle    Priority.   A   traffic management        mechanism       that  adjusts
signal  timing   to  provide    faster  passage     for  emergency      vehicles    during   traffic
operations.

Heterogeneous        Agent    Behavior.     The   variation   of  behavioral    patterns   among
simulated agents includes differences in driving style, pedestrian movement, and
rule compliance.

Intersection     Traffic    Flow.    The   movement       and   interaction    of  vehicles    and
pedestrians within a signalized road intersection.

Queue    Length.    The number       of vehicles    waiting at   a traffic signal or congested
roadway segment.

Reinforcement Learning (RL). A machine learning technique in which an agent
learns optimal    actions by interacting with an environment and receiving rewards
or penalties based on its decisions.

Road Constraint. A condition or obstruction that affects normal traffic flow, such
as lane closures, road construction, accidents, flooding, or temporary blockages.

Simulation      of  Urban     Mobility    (SUMO).     An   open-source       microscopic     traffic
simulation    software    used    for modeling     and   analyzing    vehicle    and   pedestrian
movement within road networks.

Traffic   Signal     Control.    The    management         and    adjustment     of   traffic  light
operations to regulate vehicle and pedestrian movement at intersections.

Traffic  Simulation.      The   use   of computer-based        models    to  replicate,  analyze,
and evaluate traffic behavior within a virtual environment.

Adaptive Traffic System. A traffic management system that dynamically adjusts
traffic signal timing based on changing traffic conditions and traffic demand.
```

#### Original PDF page 22

```text
Pedestrian     Demand. The         volume or     frequency of pedestrians requiring access
to cross a specific roadway or intersection.

Traffic Density. The concentration of vehicles within a specific roadway segment
or traffic area at a given time.
```

### Original Chapter 2 — Methodology

#### Original PDF page 23

```text
CHAPTER II

                                       METHODOLOGY

        The study     adopts a    Hybrid Development         Methodology that combines the
structured approach of the Waterfall model and the flexibility of Agile practices to
effectively support the development of the SMARTFLOW system, as illustrated in
Figure 7. The Waterfall approach is applied during the initial stages of the study,
particularly in planning, requirements analysis, and system design. This ensures
that the system objectives, simulation requirements, traffic modeling components,
and system structure are clearly defined before development begins. Meanwhile,
Agile  practices    are  utilized  during    the  implementation,      testing,  and   refinement
phases, allowing      iterative development, continuous simulation, repeated testing,
debugging,     and   incremental     improvement       of system     components      such    as  the
traffic  simulation     environment,       reinforcement       learning–based       traffic  signal
controller, and dashboard interface. This integration provides a balance between
structure and    adaptability,   making it suitable for an AI-driven simulation system
that  involves    both   defined   requirements      and   continuous      experimentation      and
optimization.

        The study     begins   with  the Planning      Phase, where      the proponents define
the  project   scope,    objectives,   timeline,   and    required   resources     based    on   the
approved capstone proposal. During this phase, the proponents also identify the
selected    intersection     and    traffic  scenarios     to   be   used     in  the   simulation
environment and establish the overall direction and feasibility of the system.

        In  the  Analysis    Phase,     the  proponents      gather   and   finalize  the   system
requirements      by  analyzing     traffic conditions,    traffic  flow   behavior,    pedestrian
movement,       and    the   requirements      necessary      for   the   development       of   the
```

#### Original PDF page 24

```text
simulation      and     reinforcement        learning      components.         Functional       and
non-functional requirements are also identified during this phase.

In the  Design Phase, the proponents translate the identified requirements into a
structured   system    architecture,    including the    design    of the simulation workflow,
reinforcement      learning    framework,     dashboard       interface,   and   overall    system
interaction flow. Diagrams and system models are also prepared to visualize how
the system will operate.

        During    the   Implementation        Phase,     the   proponents      will  develop     the
SMARTFLOW         system    using an iterative approach. The simulation environment,
reinforcement     learning integration, and dashboard           interface   will be built, tested,
and   improved      through     repeated     development       cycles.    The   proponents       will
configure    the   SUMO      simulation    environment,      model     vehicle   and   pedestrian
agents, integrate Python and TraCI communication, implement the reinforcement
learning model, and develop the local dashboard and SQLite database. Since the
system has     not yet   been launched, this       phase will    focus on    preparing the core
system    components       for  testing   and   evaluation.    Each    iteration   will  allow  the
proponents to identify issues, apply improvements, and refine the system before
proceeding to the final testing and evaluation phase.

        In  the   Testing    Phase,    the   proponents      conduct    continuous      simulation
testing  to  evaluate    system    behavior     under   different  traffic  scenarios    and   road
constraint   conditions.    This   includes    testing  the   simulation    environment,     traffic
signal responses, reinforcement learning performance, and dashboard outputs.

        Finally,   in  the    Refinement      Phase,     the   proponents      conduct     system
refinement     activities  by   identifying   detected     issues    and   applying     necessary
debugging,     adjustments,      and   optimizations      to  improve    system     performance,
reliability, and   usability.   This   phase    includes    refining   simulation    parameters,
improving     reinforcement      learning    performance,       correcting    identified   system
issues,   and    enhancing      the   overall   efficiency   of  the   SMARTFLOW           system.
Although    limited   within  the   duration   of  the  study,   this phase    ensures    that  the
```

#### Original PDF page 25

```text
system    remains    stable,  functional,   and   suitable   for  future  enhancements       and
extended simulation scenarios.


























                      Figure 7. Hybrid Development Methodology



SYSTEM PLANNING

Project Team Organization

        The project    team,   as shown     in Figure   8, is organized to ensure effective
coordination,    clear   communication,      and    proper   distribution   of  responsibilities
throughout    the development of the SMARTFLOW system. The Adviser provides
academic    and   technical   guidance     to ensure    that  the study   meets the     required
research    standards.    The   Project   Manager     and   Documentation       lead   oversees
project  planning,   task coordination,     progress monitoring,       timeline  management,
and  the  preparation    of  project   documentation.     Under    this  role  are  the System
Developer    and   the   System    Analyst.   The   System    Developer     is responsible     for
```

#### Original PDF page 26

```text
coding,    system      implementation,       simulation     development,       and    technical
integration.  Meanwhile, the      System    Analyst   is responsible for analyzing system
requirements,     identifying   system    processes,     and   supporting    the   design   and
evaluation    of  the  SMARTFLOW          system.    This   structure   allows    the  team   to
maintain     balanced      coordination      between       academic       guidance,      project
management, documentation, technical development, and system analysis.






























                          Figure 8. Project Team Organization



Work Breakdown Structure

        The    Work    Breakdown       Structure    shown     in   Figure    9  presents     the
phase-based      breakdown      of  the   SMARTFLOW          Traffic   System    development
process.   It follows  the  Hybrid   Development Methodology           adopted in the     study,
where   the  early   phases    follow  a  structured    Waterfall   approach    and   the  later
```

#### Original PDF page 27

```text
phases    follow   an  Agile   approach     through    continuous     testing,  refinement,    and
improvement.      The   WBS organizes the         project into   six major   phases:    Planning,
Analysis, Design, Implementation, Testing and Evaluation, and Refinement.

        During   the Planning     Phase,    the proponents define the project scope and
objectives, identify    the project timeline and required resources, select the target
intersection   in Tagum     City, and   identify the   traffic scenarios and road constraint
conditions to be included in the simulation. This phase establishes the foundation
of the   project   by  clarifying  what    the  system    aims   to  develop    and   what   traffic
situations it needs to represent.

        The Analysis Phase focuses on understanding the traffic environment and
the system requirements. This includes analyzing traffic flow behavior, pedestrian
movement,      and   the  requirements     needed     for the  simulation    and   reinforcement
learning   components.      In  this phase, the     proponents also identify the        functional
and   non-functional     requirements      of  the  system    and   define   the   reinforcement
learning requirements needed for adaptive traffic signal control.

        In the Design Phase, the proponents prepare the structure and models of
the  SMARTFLOW           system.    This   includes    designing    the   system    architecture,
simulation workflow, reinforcement learning framework, dashboard interface, and
system diagrams.       These design outputs serve          as the guide for how the system
components will interact during development and simulation execution.

        During    the   Implementation        Phase,    the   proponents      will  develop     the
SMARTFLOW         system    using an iterative approach. The simulation environment,
reinforcement     learning integration, and dashboard           interface   will be built, tested,
and   improved      through     repeated     development       cycles.   The    proponents      will
configure    the   SUMO      simulation    environment,      model    vehicle    and   pedestrian
agents, integrate Python and TraCI communication, implement the reinforcement
learning model, and develop the local dashboard and SQLite database. Since the
system has     not yet   been launched, this       phase will    focus on    preparing the core
system    components       for  testing   and   evaluation.    Each    iteration   will allow   the
```

#### Original PDF page 28

```text
proponents to identify issues, apply improvements, and refine the system before
proceeding to the final testing and evaluation phase.

        The    Testing   and    Evaluation     Phase    involves    running    traffic  and   road
constraint scenarios to assess the behavior and performance of the system. This
phase    includes     testing   fixed-time    and    reinforcement      learning–based       signal
control, collecting performance metrics, and comparing and analyzing the results.
The evaluation focuses on determining how effectively the system supports traffic
simulation and adaptive signal optimization.

        Finally, the Refinement Phase focuses on improving the system based on
the  results   of testing   and   evaluation.    This  includes    debugging     system    issues,
adjusting simulation parameters, improving reinforcement learning performance,
and finalizing system outputs and reports. This phase ensures that the system is
made more      stable,  usable, and suitable for presentation, evaluation, and future
enhancement.

        Overall,   the  Work    Breakdown      Structure    provides    a clear   and   organized
guide   for  managing     the   development      of  the  SMARTFLOW           Traffic  System.    It
ensures that    each    major   task is  properly grouped, sequenced, and aligned with
the hybrid methodology used in the study.
```

#### Original PDF page 29

```text
Figure 9. Work Breakdown Structure




Gantt Chart

        The Gantt chart shown in Figure 10 presents the timeline and schedule of
activities for the   development of the       SMARTFLOW          Traffic System.     It is aligned
with  the  Hybrid   Development       Methodology      and   the Work    Breakdown      Structure
adopted    in the   study.  The   chart begins with      the structured Waterfall      phases of
Planning, Analysis, and Design,          followed by    the Agile-based iterative phases of
Implementation, Testing and Evaluation, and Refinement.

        The    Planning    Phase     covers    the   definition   of  the   project   scope    and
objectives,    identification   of  timeline    and    resources,     selection    of  the   target
intersection, and    identification of traffic scenario parameters and road constraint
conditions.   The    Analysis    Phase    focuses     on  analyzing    traffic  flow,  pedestrian
movement,     system    requirements,      and reinforcement learning requirements. The
Design    Phase    includes    the  preparation     of the  system     architecture,   simulation
workflow,   reinforcement      learning   framework,      dashboard     interface,   and   system
diagrams.

        The Implementation, Testing and Evaluation, and Refinement phases are
presented     as  overlapping     and   iterative   activities.  During    implementation,      the
proponents      build   the   SUMO       simulation     environment,      model     vehicle    and
pedestrian     agents,   integrate    Python,    TraCI,    and   the   reinforcement      learning
model,   and   develop     the  dashboard      and   SQLite    database.    During    testing  and
evaluation,    the   proponents      run   traffic  and    road   constraint     scenarios,    test
fixed-time and reinforcement learning–based signal control, collect performance
metrics, and compare and analyze the results. During refinement, the proponents
debug    system     issues,    adjust   simulation    parameters,      improve     reinforcement
learning performance, and finalize system outputs and reports.
```

#### Original PDF page 30

```text
The    Gantt    chart   also   shows     that  the   iterative   phases     may    repeat
depending     on  testing results and system improvements.             This reflects    the Agile
component of the methodology, where issues found during testing are addressed
through    refinement      and    may    return    to  implementation       for   correction    or
enhancement.       Overall,   the   Gantt    chart   supports     the  organized     and    timely
completion of the     SMARTFLOW Traffic           System while     remaining consistent with
the six major phases of the Work Breakdown Structure.



















                                   Figure 10. Gantt Chart



SYSTEM ANALYSIS

System Architecture

        The system architecture of the SMARTFLOW Traffic System, as illustrated
in  Figure   11,   presents    a  structured    framework      that   demonstrates      how    the
different  components       of  the  system    interact   to  simulate,   analyze,    store,  and
present   traffic  data  under    varying   traffic and    road   constraint   scenarios    using
reinforcement     learning.    The    system    is  composed       of  six  major    layers:   the
User/Client     Layer,    Simulation     Layer,    Control    and    Communication         Layer,
Intelligence Layer, Database Layer, and Outputs Layer.
```

#### Original PDF page 31

```text
The User Layer represents the authorized operator, such as a researcher
or CTTMO personnel, who interacts with the system through the local dashboard.
Through this     layer, the   operator can log in,      configure    traffic scenarios, set road
constraints, select the control mode, run or stop the simulation, monitor real-time
traffic metrics within the simulation, view performance reports, and log out of the
system.

        The Simulation      Layer utilizes the Simulation of Urban Mobility (SUMO) to
model    the   localized     traffic environment.       This   layer   includes     road    network
modeling,     vehicle     simulation,     pedestrian      simulation,     and    road    constraint
configuration. It   represents the      selected intersection,      lanes, links, traffic signals,
vehicle  movement,       pedestrian    crossings,    and disruption scenarios such as lane
closures, road construction, accidents, and emergency vehicle conditions.

        The    Control    and   Communication        Layer    serves    as   the   communication
bridge   between     the  simulation    environment      and   the intelligent   decision-making
component.      This  layer   uses   Python    and   TraCI    to retrieve   real-time traffic data
from SUMO,       control simulation execution, and send traffic signal control actions
back to the SUMO environment.

        The    Intelligence     Layer    contains    the   Reinforcement        Learning     Engine
implemented using PyTorch. This layer observes the current traffic state, selects
signal   actions,   computes      rewards,     and   learns   an   optimal   policy   for  adaptive
signal   control.    It supports      traffic signal    optimization     by   aiming     to  reduce
congestion,    minimize     waiting   time,   improve    traffic flow   efficiency,  and   prioritize
emergency and pedestrian movement when necessary.

        The    Database     Layer    uses    SQLite    as   a  lightweight    local  database     for
storing and managing system data. It stores user accounts, traffic scenarios, road
constraints,   signal   control  modes,     simulation    runs, traffic metrics, reinforcement
learning   outputs,   and   performance       reports. This    allows   the system to organize
```

#### Original PDF page 32

```text
local  data    without    requiring    a  centralized     database      server   or   cloud-based
storage.

        The Outputs      Layer   presents    the results generated by         the system. These
outputs    include   real-time    traffic  metrics    within   the   simulation,    queue    length
analysis,   waiting    time   analysis,   traffic  reports,   reinforcement      learning    versus
fixed-time    signal   control   comparison,      and   dashboard      visualizations.     Through
these   outputs, the    operator can evaluate        the performance of the SMARTFLOW
system under different traffic scenarios and road constraint conditions.

        Overall,      the    system       architecture       demonstrates         an    integrated
simulation-based intelligent       traffic management environment where the operator
configures    scenarios,    SUMO      executes    the   traffic simulation, Python      and TraCI
manage     communication,       the reinforcement learning engine determines adaptive
signal  actions,   SQLite    stores   the  generated     data, and the      dashboard presents
reports and visualizations for traffic analysis and decision support.
```

#### Original PDF page 33

```text
Figure 11. System Architecture Diagram


Conceptual Framework

        Figure   12  shows     the  conceptual     framework     of the SMARTFLOW           Traffic
System.    The framework presents         how    the system receives       configuration inputs
from  the   Authorized    Operator,    processes     these inputs through       a SUMO-based
simulation   environment      and   reinforcement     learning–based traffic signal       control,
and produces      simulation-generated monitoring results and performance                  reports
through a local dashboard. Based on the requirements of researchers and traffic
management personnel, the framework ensures that the system provides useful
tools for configuring traffic scenarios, applying road constraint conditions, running
simulations,      monitoring      traffic   behavior,      and    comparing        reinforcement
learning–based signal control with fixed-time traffic signal control.
















                            Figure 12. Conceptual Framework

Input

        The   input   of  the  system     includes    the  data   and    configuration    settings
provided    by  the   Authorized     Operator.    These    inputs   include   login  credentials,
traffic  scenario      configuration,      road     constraint     configuration,      simulation
commands,       and    control   mode     selection.    The   traffic  scenario     configuration
includes   traffic density,   pedestrian    density,   and   emergency      vehicle status. The
```

#### Original PDF page 34

```text
road   constraint    configuration     includes    the  constraint    type,   severity   level,  and
affected lane. The system also receives simulation commands such as initialize,
start, pause,    stop,   reset,   and   reconfigure    simulation.    In  addition,   the  operator
selects   the control mode, either fixed-time          traffic signal control or reinforcement
learning–based traffic signal control. These inputs are stored and managed using
the local SQLite database before being used during simulation execution.

Process

        The process      begins when       the Authorized Operator logs in           to the system
through    the  local   dashboard.     After  authentication,     the   operator    configures    the
traffic scenario     and   road   constraint    settings.    The   system     then   initializes  the
SUMO simulation environment based on the configured traffic density, pedestrian
density,  emergency       vehicle   status,   constraint   type,   severity   level,  and   affected
lane. Vehicles and pedestrians are simulated as autonomous agents that interact
within the selected intersection and adjacent road segments.

        During simulation runtime, Python and TraCI serve as the communication
layer  between     SUMO       and   the  signal   control   component.      The   system     collects
simulation-generated        traffic data    such   as   queue    length,   waiting    time,  vehicle
count,   pedestrian    count,   traffic  density,  and   signal   state.  If fixed-time control is
selected, the system applies predefined signal timings for baseline comparison. If
reinforcement     learning–based       control is selected, the RL controller analyzes the
current    simulation-generated         traffic  state,   selects     adaptive     signal   actions,
computes     reward    values,    and   updates    signal   decisions    to  improve    traffic flow.
The   generated      traffic  metrics,    signal   decisions,    RL    outputs,    and   simulation
records    are   stored    in  the   SQLite    database      for  monitoring,     evaluation,    and
reporting.

Output

        The     output    of    the   system      is   a   local    dashboard       that   presents
simulation-generated        traffic  monitoring     results   and   performance       reports.   The
```

#### Original PDF page 35

```text
dashboard displays simulation status, traffic metrics, queue length, waiting time,
throughput, congestion level, pedestrian activity, emergency vehicle activity, road
constraint status, and traffic signal state. The system also generates performance
reports   and   comparison      results   between      reinforcement     learning–based       signal
control and fixed-time traffic signal control. These outputs help researchers and
traffic management personnel evaluate traffic behavior, assess the impact of road
constraints,    and   support    simulation-based       decision-making       for  adaptive    traffic
signal optimization.


Functional and Non-functional Requirements

        The    functional    and    non-functional      requirements      define    the   expected
capabilities   and   quality attributes of the proposed SMARTFLOW Traffic System.
The functional requirements describe the              core  features of the system, including
traffic   simulation,     road     constraint     scenario      management,         reinforcement
learning–based        traffic  signal    optimization,     real-time    monitoring      within    the
simulation,     and     performance        evaluation.      Meanwhile,       the    non-functional
requirements       describe     the    operational     quality    of   the   system     based      on
characteristics such as performance efficiency, reliability, usability, maintainability,
and   adaptability   aligned with ISO/IEC 25010 software              quality standards.      These
requirements      ensure    that   the  system     operates     efficiently,  produces     accurate
simulation results, and supports effective traffic analysis and decision-making.


Functional Requirements

The system shall provide the following functionalities:

    1.  The system      shall allow    the user to configure traffic scenario parameters,
        including traffic density, pedestrian density, and emergency vehicle status.
    2.  The   system     shall  allow   the  user   to configure road      constraint   conditions,
        including    constraint    type,   severity   level,   and   affected    lane.   Constraint
        types    may    include    lane    closures,    road    construction,     accidents,     and
```

#### Original PDF page 36

```text
temporary road blockages.
    3.  The   system     shall  initialize  and   execute    a  traffic simulation    environment
        using the Simulation of Urban Mobility (SUMO).
    4.  The system      shall simulate     the movement and interaction of vehicles and
        pedestrians      within   the   selected     road    network     and    configured     traffic
        conditions.
    5.  The system      shall collect simulation-generated traffic data, such as queue
        length,   waiting   time,   vehicle   count,   pedestrian     count,  and   traffic density,
        from the simulation environment during runtime.
    6.  The system shall process simulation data through a Python-based control
        layer integrated with SUMO using the Traffic Control Interface (TraCI).
    7.  The system      shall implement a reinforcement learning–based traffic signal
        controller using PyTorch for adaptive signal optimization.
    8.  The   system     shall  determine      and   apply   traffic signal   phases    and   timing
        adjustments      based    on  the   current   simulation-generated        traffic state and
        road conditions.
    9.  The    system    shall   continuously     update     simulated    traffic  conditions    and
        repeat the reinforcement learning decision-making process throughout the
        simulation runtime.
    10. The   system     shall  display   simulation-generated        traffic metrics,   simulation
        status,   signal    states,   and    scenario     information     through    a   dashboard
        interface.
    11. The    system     shall   allow    the   user   to   start,  pause,     stop,   reset,   and
        reconfigure simulation scenarios through the dashboard interface.
    12. The   system     shall  store  user   credentials,    simulation    configurations,     road
        constraint    settings,   traffic  metrics,    reinforcement      learning    outputs,   and
        performance       reports   using   SQLite    as  a  lightweight    local  database,     with
        optional export to CSV or JSON files.
    13. The system shall generate simulation results and performance reports that
        can be used to evaluate and compare reinforcement learning–based traffic
```

#### Original PDF page 37

```text
signal optimization with fixed-time traffic control methods.


Non-functional Requirements

The following are the non-functional requirements of the system:

    1.  The    system     shall   process    simulation     data    and   update     traffic signal
        decisions in real time with minimal delay to ensure smooth and continuous
        simulation execution.
    2.  The   system     shall   maintain    stable   simulation    execution     and   consistent
        reinforcement     learning    performance with minimal          system interruptions or
        processing errors.
    3.  The    system      shall   provide     a   simple,     organized,     and    user-friendly
        dashboard      that   enables     users    to  easily   configure     scenarios,    control
        simulations, and interpret traffic metrics.
    4.  The system shall ensure secure handling and storage of locally generated
        simulation     data    and    configuration      files   within   the    local   operating
        environment.
    5.  The   system    shall  operate on standard         desktop    environments      capable of
        supporting SUMO, Python, PyTorch, and related simulation tools.
    6.  The    system    shall   follow   a  modular     design    structure    to  support    easy
        updates,    debugging,      and   enhancement        of  the  simulation     environment,
        reinforcement learning model, and dashboard components.
    7.  The     system      shall   support      future    expansion      to   additional     traffic
        intersections, road scenarios, traffic parameters, and simulation conditions
        without requiring major system redesign.
    8.  The   system    shall  remain    accessible     locally  without requiring     continuous
        internet connectivity during simulation execution.


Use Case Diagram
```

#### Original PDF page 38

```text
The use case diagram, as illustrated in Figure 13, presents the interaction
between    the primary actor and the SMARTFLOW Traffic System. The system is
designed     as  a  localized   simulation-based       traffic analysis    and   decision-support
platform   accessible     to  authorized    operators     such   as   researchers     and   CTTMO
personnel      for   traffic  scenario     configuration,      road    constraint     testing,   and
reinforcement learning–based traffic signal optimization.

        The primary actor identified in the system is the Authorized Operator, who
is  responsible      for   configuring,     controlling,    monitoring,     and    evaluating     the
simulation    environment      through     a  local   dashboard      interface.   The    dashboard
serves as the main access point for managing simulation activities and analyzing
traffic behavior under different traffic scenario and road constraint configurations.

        The   primary    use   cases    of the  system include user authentication, traffic
scenario    configuration,     road   constraint    configuration,    simulation     management,
traffic monitoring     within   the   simulation,    and    system     performance      evaluation.
Through    the   authentication     feature,   authorized    personnel     can   securely    access
the   system    by   entering    locally   managed       login   credentials,    which    are   then
validated before the user is allowed to operate the simulation platform.

The traffic   scenario configuration       functionality allows the Authorized Operator to
define traffic  conditions    by setting parameters such as traffic density, pedestrian
density,    and    emergency       vehicle    status.    In   addition,    the    road    constraint
configuration feature enables the operator to define road disruption conditions by
specifying the constraint type, severity level, and affected lane. These configured
conditions influence vehicle and pedestrian behavior and modify the operational
state of the simulated road network during simulation execution.

        Once     the    simulation     is   initiated,   the    system     executes      the   traffic
environment        within     the     SUMO        simulation       platform      and     processes
simulation-generated traffic conditions based on the selected control mode. The
operator    may    select  either   fixed-time    control   or  reinforcement     learning–based
```

#### Original PDF page 39

```text
control.   When     reinforcement      learning–based       control    is selected,    the   system
applies   adaptive    signal   decisions    dynamically     to  optimize    traffic flow  efficiency
and reduce     congestion. When fixed-time control is selected, the system applies
predefined signal timing for comparison and baseline evaluation.

        Throughout      the simulation process, the         Authorized     Operator can monitor
traffic conditions     and    evaluate    system     performance       through     the   dashboard
interface.   The    system     displays     simulation    outputs     such   as   queue     lengths,
average     delay,    traffic  throughput,      traffic  signal    states,    congestion      levels,
pedestrian activity, and simulation-generated performance metrics. The operator
may   also   initialize, start,  pause,    stop,  reset, and reconfigure        the  simulation for
further testing and analysis.

        Overall, the use case diagram demonstrates how authorized users interact
with the SMARTFLOW Traffic System to configure traffic scenarios, manage road
constraints,   control   simulation    execution,     monitor    traffic behavior, and     evaluate
the  effectiveness      of  reinforcement      learning–based        traffic  signal   optimization
compared       with   fixed-time     traffic  signal    control    within    a   simulated     traffic
environment.
```

#### Original PDF page 40

```text
Figure 13. Use Case Diagram
```

#### Original PDF page 41

```text
Context Flow Diagram

        The Context Flow Diagram shown in Figure 14 presents a high-level view
of the SMARTFLOW Traffic System, illustrating how the system interacts with the
external   entity   and   how    data   flows   across    the   simulation-based       platform.    It
focuses    on  the  logical   flow  of  system    inputs   and   outputs   without    detailing  the
internal processes of the system.

        In the diagram, the main external entity is the Authorized Operator, which
may   include   researchers,      traffic management        personnel,    or  CTTMO      staff.  The
Authorized     Operator     provides    the   main   inputs    to  the  system,    such    as  login
credentials,     traffic   scenario      configuration,      road    constraint     configuration,
simulation    commands,       and   fixed-time    or  reinforcement     learning–based       control
mode    selection.   The traffic scenario configuration         includes    parameters such as
traffic density,  pedestrian     density,  and   emergency      vehicle status, while the road
constraint configuration      includes    the constraint type, severity level, and affected
lane.  These     inputs   allow   the   system    to  initialize  and   execute    the   simulation
environment based on the configured traffic and road conditions.

        The    SMARTFLOW           Traffic  System      processes     the   provided     inputs   by
executing    the  traffic simulation,    generating     vehicle and     pedestrian    movements,
applying   road   constraint conditions, and controlling          traffic signals   based    on  the
selected    control   mode.     When     reinforcement      learning    mode     is selected,    the
system uses the trained RL controller to determine adaptive signal actions. When
fixed-time mode is selected, the system applies predefined traffic signal timing for
baseline comparison.

        The   system     produces     outputs    for  the  Authorized     Operator     through   the
dashboard     interface.   These    outputs    include   real-time    traffic metrics   and   status
within   the   simulation,     traffic  signal    states,    queue     lengths,    waiting    times,
```

#### Original PDF page 42

```text
throughput,      congestion      levels,    pedestrian      activity,   simulation      logs,    and
performance       reports.    The    generated       results   support     the   evaluation      and
comparison      of   reinforcement      learning–based        adaptive     traffic  signal   control
against   fixed-time    traffic signal  control   under different traffic scenario and road
constraint configurations.

        The    diagram     also   shows     key   data   flows   such    as  user   inputs,    traffic
scenario    configurations,     road   constraint    configurations,     simulation    commands,
traffic performance      metrics,    and   generated     reports.   These     flows   demonstrate
how input data is      processed by the SMARTFLOW system and transformed into
meaningful      outputs      that   support      traffic   analysis,     decision-making,        and
simulation-based evaluation.




















                     Figure 14. Context flow diagram of the system.



Data Flow Diagram
```

#### Original PDF page 43

```text
The Data Flow Diagram           shown in Figure 15,        the system     is decomposed
into  five  major   processes:     User    Account    Authentication,      Traffic  Scenario    and
Road    Constraint    Configuration,     Simulation    and   Data   Collection,    Signal Control
Processing, and Monitoring and Reporting. The Authorized Operator, which may
include researchers       or CTTMO      personnel, serves as the primary external entity
that  interacts   with  the   system.    The   operator    provides    login  credentials,    traffic
scenario   configuration,    road constraint configuration, simulation commands, and
control mode selection.

        The   User   Account     Authentication     process validates      the login credentials
provided    by  the   Authorized     Operator.    To  perform     this validation,    the  process
sends a    user account      query   to the SQLite database and retrieves user account
records.   After  the credentials are checked, only authorized users are allowed to
access and operate the SMARTFLOW simulation system.

        After    authentication,       the    Traffic   Scenario       and    Road      Constraint
Configuration     process    manages      the  traffic scenario    and   road   constraint   inputs
provided by     the Authorized     Operator. The      traffic scenario configuration includes
traffic density,  pedestrian    density,   and   emergency      vehicle status, while the road
constraint configuration      includes    the constraint type, severity level, and affected
lane.  These    configured     scenario    and   road constraint     settings are stored in      the
SQLite    database     as   part   of  the   system     configuration.    The    saved    scenario
configurations can then be         retrieved and     used   by the   system    during   simulation
execution.

        The     Simulation     and     Data     Collection     process     receives     simulation
commands       from   the  Authorized     Operator,    such   as  starting,   pausing,    stopping,
resetting,  or  running    the  simulation.    This   process    retrieves   the  traffic scenario
configuration,    road    constraint    settings,   and    simulation    parameters       from   the
SQLite database.       Based on     these   data, the    system    executes the SUMO-based
traffic simulation    and   collects   simulation-generated       traffic  information,    such   as
vehicle  count, pedestrian activity, queue length, waiting time, traffic density, and
```

#### Original PDF page 44

```text
traffic flow  conditions.   The collected     simulation data      and traffic metrics are then
stored in the database for further processing and evaluation.

        The Signal Control Processing process handles the control mode selected
by the Authorized Operator. This process determines whether the system will use
fixed-time    signal   control    or  reinforcement      learning–based        signal   control.   It
retrieves traffic metrics and signal control parameters from the SQLite database,
analyzes the current simulation-generated traffic conditions, and generates signal
decisions.   In  reinforcement      learning   mode,    the   process    also  produces     reward
data  used   to evaluate     and improve      signal control    decisions. These outputs         are
stored in the database and later used for monitoring, reporting, and performance
comparison.

        The    Monitoring     and    Reporting      process     retrieves    simulation     results,
reinforcement     learning outputs, and historical reports from the SQLite database.
This process presents the system outputs to the Authorized Operator through the
dashboard interface. The main outputs include real-time metrics and status within
the  simulation,    traffic  signal   state,  and   performance       reports   with  comparison
results.  These     outputs   allow   the   operator    to  monitor   the   simulation,    observe
signal  behavior, and evaluate the         performance of reinforcement learning–based
traffic signal control compared with fixed-time traffic signal control.

        Overall, the Level 1 Data Flow Diagram demonstrates how SMARTFLOW
manages user inputs, traffic scenario configuration, road constraint configuration,
simulation execution,      signal control processing, database storage, and reporting
through a centralized SQLite database. By matching the number and meaning of
the external data flows shown in the Context Flow Diagram, the DFD provides a
clearer   and   more     consistent    representation      of  how    data    flows   through    the
SMARTFLOW Traffic System.
```

#### Original PDF page 45

```text
Figure 15. Data flow diagram of the system.

Traffic Scenario Configuration

Pedestrtian Density Configuration



SYSTEM DESIGN

Entity Relationship Diagram

        The   Entity   Relationship     Diagram     illustrated   in Figure    16   presents    the
database     structure   of   the  SMARTFLOW           Traffic  System     using   SQLite     as  a
lightweight    local   database.     Since    the   system     is  designed     as   a   localized
simulation-based platform, SQLite is used to store and manage essential system
data without requiring a centralized database server or cloud-based storage. The
database supports the organization of user account credentials, traffic scenarios,
road   constraint    configurations,     signal   control   modes,     simulation    runs,   traffic
metrics, reinforcement learning outputs, and performance reports.
```

#### Original PDF page 46

```text
The User Accounts entity          stores the login credentials used to access the
system    dashboard.      Since    the   system    is  designed     as   a  localized    prototype,
role-based access control is         not included     in the current scope, and the account
record   is mainly    used   for  authentication.     The   Traffic  Scenarios     entity  contains
predefined      traffic  conditions      such     as   normal      traffic,  heavy     congestion,
pedestrian-intensive       conditions,    and    emergency       traffic scenarios.     The    Road
Constraints     entity   stores    disruption    settings    such     as   lane   closures,     road
construction, accidents, and pedestrian congestion, which may be applied during
simulation execution.

        The   Signal    Control   Modes     entity   identifies  the   control   strategy   used   in
each simulation run,       such as fixed-time control or reinforcement learning–based
adaptive    control.  The   Simulation     Runs entity    serves as     the central    table  of  the
database     because     it records   each    executed     simulation    and   links  the  selected
user   account,    traffic scenario,    road   constraint,    and   signal   control   mode.    This
entity  also  stores   important    execution     details  such   as the   start time,   end   time,
and simulation status.

        The    Traffic  Metrics    entity   records    the   summarized       performance       data
generated     after   each    simulation     run,   including    queue    length,    waiting   time,
throughput,    pedestrian     delay,   traffic density,   and    signal  efficiency.   Since   each
simulation    run    produces      one    final  set   of  summarized        traffic  metrics,    the
relationship    between     Simulation     Runs    and   Traffic  Metrics    is  one-to-one.     The
Performance      Reports     entity  contains    the  summarized       results   and   comparison
output   of  each   simulation     run.  Since    each   simulation     run  produces     one   final
performance      report, the relationship between Simulation Runs and Performance
Reports     is   also    one-to-one.      Meanwhile,       the    RL    Outputs     entity    stores
reinforcement     learning–related      data   such    as  traffic state   information,    selected
signal actions, reward values, and timestamps. Since the reinforcement learning
model may generate multiple actions and rewards during a single simulation run,
one simulation run may have multiple RL output records.
```

#### Original PDF page 47

```text
The relationships between the entities are represented using Crow’s Foot
notation.   One    user   account    may    be  associated     with   multiple   simulation    runs,
while  each    simulation    run   is linked   to  one   user   account.   Similarly,   one   traffic
scenario,   one    road   constraint,   and   one    signal  control   mode     may    be  used   in
multiple  simulation    runs, but    each simulation run uses only one selected record
from each of these entities. A simulation run may generate multiple traffic metric
records and reinforcement learning outputs, which may then be used to produce
performance reports.

        Overall,   the ERD shows how SMARTFLOW organizes and connects the
data  needed     for  simulation    execution,     reinforcement     learning   processing,     and
performance      evaluation.    This   database     structure    allows    the  system     to  store
simulation    data   locally,  maintain    organized     records,    and   support    comparison
between adaptive and fixed-time traffic signal control strategies.





















                          Figure 16. Entity Relationship Diagram
```

#### Original PDF page 48

```text
Data Dictionary
        The   data    dictionary   of  the   SMARTFLOW          Traffic  System     provides    a
detailed   description    of the   data   elements    used    in the  system’s    SQLite    local
database.    It serves   as   a  reference    for understanding      how   data   is organized,
stored,  and   managed to support system functions             such as    user  authentication,
traffic scenario configuration, road constraint management, simulation execution,
reinforcement learning output tracking, and performance reporting.
        The   system     is  composed      of   several   tables,   including    Users,   Traffic
Scenarios,    Road    Constraints,    Signal   Control   Modes,     Simulation    Runs,   Traffic
Metrics, RL    Outputs,   and   Performance Reports. Each table contains              fields with
defined   data   types,   constraints,    and    descriptions    to  ensure    consistent    data
storage and accurate retrieval of simulation-related information.

Table 2. User


    Field        Data Type       Length       Constraints                 Description
    Name

 accuont_i      INTEGER         -           PRIMARY              Unique identifier for each
 d                                          KEY                  authorized user

 username       TEXT            50          UNIQUE,      NOT     Username      used    for local
                                            NULL                 system login

 password       TEXT            255         NOT NULL             Password          used      for
                                                                 authentication

 date_creat     DATETIME        -           NOT NULL             Date    and   time   the  user
 ed                                                              record was created


Table 3. Traffic Scenarios
```

#### Original PDF page 49

```text
Field       Data Type       Length       Constraints                Description
   Name

 scenario_i     INTEGER         -          PRIMARY KEY          Unique    identifier for each
 d                                                              traffic scenario

 scenario_      TEXT            100        NOT NULL             Name       of    the    traffic
 name                                                           scenario

 traffic_den    TEXT            30         NOT NULL             Traffic               density
 sity                                                           classification     such     as
                                                                normal or heavy

 pedestrian     TEXT            30         NOT NULL             Level      of     pedestrian
 _demand                                                        activity in the simulation

 emergenc       TEXT            30         NULL                 Indicates     presence      of
 y_conditio                                                     emergency             vehicle
 n                                                              conditions

 descriptio     TEXT            255        NULL                 Additional    description   of
 n                                                              the scenario


Table 4. Road  Constraints

    Field       Data Type       Length       Constraints                Description
   Name

 constraint    INTEGER          -          PRIMARY              Unique identifier for each
 _id                                       KEY                  road constraint
```

#### Original PDF page 50

```text
constraint    TEXT             50         NOT NULL             Type    of  road   constraint
 _type                                                          such   as   lane  closure   or
                                                                accident

 affected_l    TEXT             50         NOT NULL             Lane     or   road    section
 ane                                                            affected by the constraint

 severity_l    TEXT             20         NOT NULL             Severity    classification   of
 evel                                                           the constraint

 status        TEXT             20         NOT NULL             Current status of the road
                                                                constraint

 descriptio    TEXT             255        NULL                 Additional             details
 n                                                              regarding the constraint



Table 5. Signal Control Modes


    Field       Data Type       Length       Constraints                Description
   Name

 control_m     INTEGER          -          PRIMARY              Unique    identifier for each
 ode_id                                    KEY                  control mode

 mode_na       TEXT             50         NOT NULL             Name of the signal control
 me                                                             mode

 fixed_time    INTEGER          -          NULL                 Preset   signal  duration   for
 _duration                                                      fixed-time control

 rl_model_     TEXT             100        NULL                 Name    or  identifier  of the
 used                                                           RL model used

 descriptio    TEXT             255        NULL                 Additional        information
 n                                                              about the control mode
```

#### Original PDF page 51

```text
Table 6. Simulation Runs

    Field       Data Type       Length      Constraints               Description
   Name

 run_id        INTEGER          -          PRIMARY            Unique    identifier for each
                                           KEY                simulation run

 account_i     INTEGER          -          FOREIGN            Reference          to      the
 d                                         KEY                authorized user

 scenario_i    INTEGER          -          FOREIGN            Reference to the selected
 d                                         KEY                traffic scenario

 constraint    INTEGER          -          FOREIGN            Reference     to the  applied
 _id                                       KEY                road constraint

 control_m     INTEGER          -          FOREIGN            Reference to the selected
 ode_id                                    KEY                signal control mode

 start_time    DATETIME         -          NOT NULL           Simulation                start
                                                              timestamp

 end_time      DATETIME         -          NULL               Simulation end timestamp

 simulation    TEXT             30         NOT NULL           Current     status    of   the
 _status                                                      simulation



Table 7. Traffic Metrics


    Field       Data Type       Length      Constraints               Description
   Name

 metric_id     INTEGER          -          PRIMARY            Unique identifier for traffic
                                           KEY                metric data
```

#### Original PDF page 52

```text
run_id        INTEGER          -           FOREIGN            Reference         to       the
                                            KEY                simulation run

 queue_len     REAL             -           NOT NULL           Measured     vehicle   queue
 gth                                                           length

 waiting_ti    REAL             -           NOT NULL           Average      waiting      time
 me                                                            during simulation

 throughpu     REAL             -           NOT NULL           Number        of     vehicles
 t                                                             passing      through       the
                                                               intersection

 pedestrian    REAL             -           NULL               Delay     experienced       by
 _delay                                                        pedestrians

 traffic_den   REAL             -           NULL               Measured traffic density
 sity

 signal_effi   REAL             -           NULL               Efficiency  score   of  signal
 ciency                                                        control



Table 8. RL Outputs


    Field        Data Type      Length       Constraints               Description
   Name

 output_id      INTEGER         -           PRIMARY           Unique     identifier  for   RL
                                            KEY               output data

 run_id         INTEGER         -           FOREIGN           Reference          to       the
                                            KEY               simulation run
```

#### Original PDF page 53

```text
state_data    TEXT             500        NOT NULL          Encoded        traffic    state
                                                             information

 selected_     TEXT             100        NOT NULL          Traffic     signal       action
 action                                                      selected by the RL model

 reward_va     REAL             -          NOT NULL          Reward     value    generated
 lue                                                         during RL processing

 timestamp     DATETIME         -          NOT NULL          Date    and    time   the   RL
                                                             action was generated



Table 9. Performance Reports


    Field       Data Type       Length      Constraints              Description
    Name

 report_id      INTEGER        -           PRIMARY           Unique    identifier for each
                                           KEY               performance report

 run_id         INTEGER        -           FOREIGN           Reference          to      the
                                           KEY               simulation run

 summary_       TEXT           1000        NOT NULL          Summary       of   simulation
 result                                                      performance results

 compariso      TEXT           1000        NULL              Comparison           between
 n_result                                                    fixed-time   and    RL-based
                                                             dual control

 generated      TEXT           100         NULL              User     or   process     that
 _by                                                         generated the report
```

#### Original PDF page 54

```text
date_gene       DATETIME         -           NOT NULL            Date   and    time  the   report
 rated                                                            was generated



Technologies, Concepts, and Theories

        This    section    presents     the   key    models,     algorithms,     concepts,      and
technologies    utilized  in the   development of      the SMARTFLOW Traffic System. It
explains how traffic simulation data is generated, processed, analyzed, and used
for  reinforcement      learning–based       traffic  signal   optimization.     The   discussion
follows the   major stages      of the  system    workflow,    including data collection, data
pre-processing,          feature       extraction,        reinforcement          learning–based
decision-making, and system implementation technologies.

Data Collection

        Data collection in SMARTFLOW is performed within the SUMO simulation
environment. Instead of using live CCTV feeds, IoT sensors, or GPS devices, the
system gathers traffic-related data generated during simulation runs. These data
include   vehicle    count,    pedestrian     count,   queue     length,   waiting    time,   traffic
density,  throughput,     pedestrian    delay,   emergency      vehicle   presence,     and   traffic
signal  states.   Through     TraCI,   Python    retrieves   these   simulation    values   in  real
time  and   forwards them      to  the control   and   decision-making components            of the
system.

Data Pre-Processing

        Before the collected simulation data is used by the reinforcement learning
controller, it undergoes      pre-processing to ensure that it is organized, consistent,
and   suitable   for analysis.    This  includes    formatting    traffic state  values,   filtering
unnecessary      simulation    outputs,   normalizing     numerical     values   such   as   queue
length   and    waiting    time,   and   converting     raw   traffic  data   into   a  structured
observation     state.  Pre-processing       helps   reduce    errors   and    ensures    that   the
```

#### Original PDF page 55

```text
reinforcement learning model receives clean and meaningful input during training
and evaluation.

Feature Extraction

        Feature    extraction    involves    identifying   the most relevant      traffic attributes
that  influence   signal control decisions. In SMARTFLOW,                 the  extracted    features
may    include    queue    length    per   lane,   average     waiting    time,   vehicle   density,
pedestrian demand, emergency vehicle presence, current signal phase, and road
constraint   status.   These     features    represent    the  current   traffic  condition   of  the
simulated intersection and serve as the input state for the reinforcement learning
model.

Reinforcement Learning–Based Decision-Making

        The   SMARTFLOW           Traffic  System     uses   Reinforcement       Learning     as  the
decision-making      approach      for adaptive    traffic  signal control. In the     system,    the
traffic signal   controller   acts  as  the   learning   agent,    while  the   SUMO simulation
environment      serves     as   the   traffic environment       where     traffic conditions     are
observed and signal actions are applied through TraCI.

        The agent     observes the      current traffic state     of the intersection,     including
queue    length,   vehicle    count,   average     waiting    time,  traffic  density,   pedestrian
demand,     emergency      vehicle    presence,    road   constraint    status,   and   the  current
traffic signal  phase.    Based on     this state, the agent selects a signal action, such
as changing to the next valid traffic phase or maintaining or extending the current
phase depending on the traffic condition.

        Instead of using a fixed signal timing, the system allows the agent to learn
from   different  traffic  situations   and    evaluate    whether     its chosen     signal   action
improves      traffic   flow.   The     learning     process      considers      important     traffic
performance      factors   such    as   vehicle   waiting    time,   queue    length,    pedestrian
delay, traffic throughput, and emergency vehicle priority. Actions that help reduce
congestion, minimize delay, improve vehicle movement, and prioritize emergency
```

#### Original PDF page 56

```text
vehicles   are  treated as more favorable, while actions that increase waiting time,
queue buildup, or pedestrian delay are considered less effective.

        The   training  process     is performed     using simulation-generated data from
repeated    SUMO     episodes rather than live CCTV, GPS, or physical sensor data.
Each    episode    represents     a  complete     simulation    run   under   a  selected    traffic
scenario,    such     as   normal     traffic,  heavy     congestion,      pedestrian-intensive
conditions,   emergency       vehicle   conditions,    lane  closures,    road   construction,    or
accidents.

        During training, SUMO generates the traffic conditions, TraCI transfers the
observed traffic state to the reinforcement learning component, the agent selects
a  signal   action,   and    the  system     evaluates     the  result   based     on   the  traffic
performance      outcome.     Through      repeated    simulation     experiences,      the  agent
improves     its decision-making        and   learns   how    to   select   signal   actions    that
produce better traffic performance.

        In this study, the reinforcement learning–based signal control approach will
be  tested   and   compared      against   a  fixed-time    traffic signal  control   baseline    to
determine whether the adaptive system can improve waiting time, queue length,
throughput, pedestrian delay, and emergency vehicle response.



Technologies Used in the System

Simulation of Urban Mobility (SUMO)

        The   system     primarily   utilizes  Simulation    of  Urban    Mobility   (SUMO),     an
open-source      traffic  simulation     platform    used    to   model    and    simulate     road
networks,    vehicle  movement, pedestrian          behavior, and traffic signal operations.
SUMO serves as the main simulation environment of the SMARTFLOW system,
allowing   the   proponents      to  create   realistic  traffic  conditions,    road   constraint
scenarios, and traffic flow behavior within the selected intersection in Tagum City.
```

#### Original PDF page 57

```text
Through    SUMO,      the  system    can   simulate    different  traffic densities,    pedestrian
activity,  emergency        vehicle    scenarios,      lane    closures,     road    construction,
accidents.





















                    Figure 17. Simulation of Urban Mobility (SUMO)

Reinforcement Learning (RL)

        To   enable    adaptive     traffic  signal   optimization,     the   system    integrates
Reinforcement      Learning     (RL)   techniques.     Reinforcement       Learning    allows    the
system to learn optimal traffic signal control strategies by continuously interacting
with  the   simulation     environment.      The   RL   model     observes     traffic conditions,
performs    signal   control   actions,    receives    reward    feedback,     and   improves     its
decision-making performance over repeated simulation episodes. This approach
enables the     SMARTFLOW system to dynamically adapt traffic signals based on
changing     traffic  flow,   pedestrian     demand,      and    road    constraint    conditions,
improving overall traffic efficiency compared to traditional fixed-time traffic signal
control.
```

#### Original PDF page 58

```text
Figure 18. Reinforcement Learning (RL)

Python and TraCI

        Python   will serve as    the main programming         language    for  connecting    the
simulation,   reinforcement      learning   controller,   dashboard     logic,  and   database
operations.    Its module-based       structure   supports    organized     development      and
integration of system components. TraCI, or Traffic Control Interface, will be used
because    it provides    programmatic      access   to  a  running   SUMO      simulation   and
allows   Python    to   retrieve  simulation     values   and    send   traffic  signal   control
commands       in   real   time.    Together,     Python     and    TraCI    are   relevant    to
SMARTFLOW         because    they   form the   communication layer between the SUMO
environment and the RL-based decision-making component.
```

#### Original PDF page 59

```text
Figure 19. Python and TraCl

PyTorch

        PyTorch    will be used to implement and train the Deep Q-Network (DQN)
model   for  the  reinforcement      learning   component      of  the  SMARTFLOW           Traffic
System.    It provides optimized      tensor   operations    and deep learning support that
are  suitable   for training  neural network–based models            on CPUs and GPUs. In
SMARTFLOW,         PyTorch     is relevant   because     it will be   used   to  build  the  DQN
model that estimates the best traffic signal action based on the current simulation
state,  such   as  queue     length,  waiting   time,  traffic density,   pedestrian    demand,
emergency     vehicle   presence, and road constraint conditions. It will also support
model    training  by   processing     simulation    experiences      generated     from   SUMO
episodes,    computing     training  loss,  and   updating    model    parameters     to improve
adaptive traffic signal decision-making.
```

#### Original PDF page 60

```text
Figure 20. PyTorch




Database Management System

In terms of data management, the             SMARTFLOW Traffic System utilizes SQLite
as  its  Database      Management        System     (DBMS)      to  store   and    organize    user
credentials,   traffic scenarios,    road   constraints,    simulation   results, reinforcement
learning   outputs,   and   performance       reports.  This   allows   efficient  data   retrieval,
simulation     monitoring,      and     performance       evaluation      within    the    system.
Additionally,   the   database      supports     local   storage    without    requiring   internet
connectivity or    a centralized server, making the system lightweight, reliable, and
suitable    for   simulation-based        traffic  analysis     and    adaptive     traffic  signal
optimization.
```

#### Original PDF page 61

```text
Figure 21. Database Management System (DBMS)


SYSTEM TESTING AND IMPLEMENTATION

              The System Testing and Implementation phase focuses on ensuring that
the  SMARTFLOW          Traffic  System    operates    properly    and   satisfies  the specified
system requirements.        During   this phase, comprehensive testing is conducted to
validate  the   integration   of  the  major   system    components,      including    the SUMO
simulation     environment,      Python-TraCI       communication         layer,   reinforcement
learning–based       traffic  signal    controller,   SQLite     database,      and    dashboard
interface.  The testing process evaluates the           performance of the        adaptive traffic
signal  optimization    system    using   metrics    such   as  average    waiting   time,  queue
length,   throughput,     traffic density,   pedestrian     delay,   and   signal   efficiency   to
ensure    accurate    and   responsive     traffic management       under    varying   traffic and
road constraint conditions.

              The SMARTFLOW system will undergo unit testing, integration testing,
and  scenario-based       testing  to  verify  the  functionality   of  individual   components
and  the   overall  system.    Test  cases    are  designed     to simulate both      normal and
disruptive      traffic     scenarios,        including       heavy       traffic     congestion,
```

#### Original PDF page 62

```text
pedestrian-intensive      conditions,    lane closures, road construction, accidents, and
emergency       vehicle    situations.   These     tests   verify   whether     the   system     can
correctly   process    simulation     data,  apply    adaptive    traffic signal   decisions,    and
maintain stable simulation performance throughout execution.

             In addition to functional testing, the Reinforcement Learning (RL)–based
traffic signal  controller   will be  evaluated using       RL-specific performance metrics,
including   cumulative     reward, convergence         rate,  policy stability, average      waiting
time, queue     length, and traffic throughput. These metrics will be used to assess
the   learning    efficiency,   adaptability,    and    effectiveness      of  the   RL    agent    in
optimizing    traffic  signal   decisions     under    different   traffic  and   road    constraint
scenarios. The results will also be compared with fixed-time traffic signal control
to determine the overall performance improvement achieved by the RL model.

           A summary       of the  testing results should be        presented     in  tabular  form,
highlighting the status and performance of each major component, such as traffic
simulation, reinforcement learning processing, signal control execution, database
storage,    dashboard      monitoring,     and    performance      reporting.    This   allows    the
proponents      to   identify   issues    and    confirm     that   the   functionalities    of   the
SMARTFLOW system meet the expected operational standards.

            To support the validation process, a System Test Plan should be prepared
outlining   the   objectives,     testing   scope,    simulation     environment,      test   cases,
procedures,     and    acceptance      criteria.  This   ensures     that  the   testing   activities
remain organized, systematic, and aligned with the functional and non-functional
requirements of the study.

           Following successful testing, the implementation phase involves deploying
the  SMARTFLOW           system    within   a  localized    desktop    simulation    environment.
This includes     configuring the     SUMO simulation platform, integrating Python and
TraCI communication, implementing the reinforcement learning model, setting up
the SQLite database, and deploying the local dashboard interface. The deployed
system will be used by researchers and authorized traffic management personnel
```

#### Original PDF page 63

```text
to evaluate    traffic  scenarios,    monitor    simulation    performance,      and   assess    the
effectiveness of the Reinforcement Learning–based traffic signal controller before
any  real-world implementation. After deployment, final validation is conducted to
confirm    that   the   system     performs     correctly    within   the   intended     operating
environment.     Users    may   also   be  oriented    on  the  proper    use  of  the simulation
dashboard and traffic analysis features.

            Finally, continuous monitoring and evaluation are conducted to assess
system    performance,      identify   simulation    issues,   and    improve    adaptive     traffic
signal optimization strategies. This phase ensures that the SMARTFLOW system
remains functional, reliable, and adaptable for future traffic simulation studies and
intelligent transportation system research.




SYSTEM MAINTENANCE

     The System Maintenance phase focuses on ensuring the continued reliability,
functionality,   and    improvement        of  the   SMARTFLOW            Traffic  System      after
implementation. This phase involves monitoring system performance, identifying
and   correcting    system     issues,   and    applying    necessary      updates     to  improve
simulation accuracy, reinforcement learning performance, and overall usability.

        Maintenance       activities   may     include    regular    checking     of  the   SUMO
simulation      environment,        updating      Python      and     reinforcement        learning
components,       refining    traffic  scenario     and     road    constraint    configurations,
improving     dashboard      features,    and    maintaining     the   SQLite    database.      The
proponents      may    also   adjust    simulation    parameters,      optimize    reinforcement
learning behavior,     and correct detected errors based on testing results and user
feedback.

        Additionally,   continued     evaluation    of  traffic simulation     performance      and
adaptive     signal    control    behavior     may     be    conducted      to   support     future
```

#### Original PDF page 64

```text
enhancements and expanded traffic analysis scenarios. This phase ensures that
SMARTFLOW remains stable, maintainable, and suitable for future development
in intelligent traffic management and simulation-based decision-support research.




System Security Plan

        To ensure the protection of system data and simulation resources, a System
Security   Plan   will be   implemented       for the   SMARTFLOW          Traffic  System.    The
system will enforce user authentication and role-based access control to prevent
unauthorized      access     to  the   simulation     dashboard,      database,     and    system
configurations.      Since    the    system      operates      within   a    localized    desktop
environment,     locally  stored simulation     data, reinforcement learning outputs, and
configuration    files  will be   protected    through    secure   access     management       and
regular database backup procedures.

         The system will also apply secure communication and processing practices
between    the SUMO simulation environment, Python-TraCI communication layer,
reinforcement learning components, and SQLite database. Input validation, error
handling,     and    secure     coding    practices     will  be    implemented        to  reduce
vulnerabilities and ensure accurate traffic simulation processing. In addition, audit
logs  and   monitoring    functions    may   be   used   to  track  user   activities, simulation
execution, and system events for security and troubleshooting purposes.

        The System Security Plan shown in Table 4 follows ISO/IEC 27001–aligned
security  practices    to  support   the  confidentiality,   integrity,  and availability of the
SMARTFLOW          Traffic   System.     These     security   controls    help   ensure     secure
system operation,      reliable simulation     processing, and protected management of
traffic simulation data and reinforcement learning outputs.

Table 10. System Security Plan
```

#### Original PDF page 65

```text
Security Domain (ISO             Control Area          Description / Implementation in
           27001)                                                    the System



 A.5           Information     Security Policy         The system will implement security
 Security Policies                                     policies for user access, simulation
                                                       control, and local data protection.



 A.6    Organization       of  Roles            and    Roles     such     as     Administrator,
 Information Security          Responsibilities        Researcher,         and      Authorized
                                                       Operator will    have   defined system
                                                       privileges.



 A.9 Access Control            User        Access      The system will enforce role-based
                               Management              access     control   (RBAC)      through
                                                       secured login credentials.



 A.9 Access Control            Authentication          Username           and         password
                               Mechanism               authentication will be implemented
                                                       to restrict unauthorized access.



 A.10 Cryptography             Data Protection         Local      simulation       data      and
                                                       exported     files  will  be   protected
                                                       through      secure      storage      and
                                                       backup mechanisms.
```

#### Original PDF page 66

```text
A.12          Operations      Data    Processing      Input  validation and error handling
 Security                      Integrity               will    ensure       accurate       traffic
                                                       simulation    processing     and   stable
                                                       system operation.



 A.12          Operations      Logging          and    The   system     will maintain    logs   of
 Security                      Monitoring              simulation    activities,  user  actions,
                                                       and   system    events   for  monitoring
                                                       and troubleshooting.



 A.13   Communications         Secure                  Communication        between      SUMO,
 Security                      Communication           Python,    TraCI,   and   reinforcement
                                                       learning    components        will  follow
                                                       secure processing practices.



 A.11     Physical      and    Device                  Desktop devices and local storage
 Environmental                 Protection              used   for  simulation    execution    will
 Security                                              be    secured      from    unauthorized
                                                       physical access.



 A.17          Information     Data        Backup      Regular       backup        of    SQLite
 Security     Aspects      of  and Recovery            databases     and   simulation    reports
 Business Continuity                                   will be   performed     to  ensure   data
                                                       recovery.
```

#### Original PDF page 67

```text
A.16          Information      Incident               Procedures will     be established      for
 Security          Incident     Response               detecting, reporting,     and   resolving
 Management                                            system     errors   or  security-related
                                                       issues.



 A.14               System      Secure                 Secure          coding         practices,
 Acquisition,                   Development            debugging,      and   system     updates
 Development,           and                            will    be      applied       throughout
 Maintenance                                           development and maintenance.






System Maintenance Plan

       In addition, a System Maintenance Plan will be established to support the
continued operation, improvement, and sustainability of the SMARTFLOW Traffic
System     after   implementation.       This   plan    includes    scheduled      maintenance
activities   such    as    simulation     optimization,     reinforcement      learning     model
refinement, SQLite database maintenance, dashboard improvement, and system
performance       monitoring.     Procedures      for   troubleshooting,      debugging,       and
correcting system      errors will  also be   implemented to       maintain stable simulation
performance.

        Furthermore, system documentation will be continuously updated to record
configuration    changes, reinforcement        learning adjustments,       simulation   updates,
and    maintenance        activities.   This     ensures     easier     future    enhancement,
maintainability,   and  expansion of the       SMARTFLOW         system    for  additional traffic
scenarios and intelligent transportation studies.

        The    System    Maintenance       Plan   shown    in  Table   11  aligns  maintenance
activities  with   ISO/IEC     25010    software    quality   attributes   to  ensure    that  the
```

#### Original PDF page 68

```text
SMARTFLOW         Traffic  System    remains    reliable,  efficient, maintainable,     secure,
and adaptable over time.

Table 11. System Maintenance Plan



    ISO 25010           Maintenance                    Description                 Frequenc
    Attribute              Activity                                                     y



 Reliability          System                 Monitoring            simulation     Continuou
                      Monitoring             execution,    system     stability,  s
                                             and dashboard operation



 Performance          Performance            Improving              simulation    Regularly
 Efficiency           Optimization           processing        speed       and
                                             reinforcement            learning
                                             performance



 Usability            Dashboard              Updating     dashboard     layout    As
                      Improvement            and   controls  based    on  user    Needed
                                             feedback



 Security             Security Updates       Applying     system     updates,     Periodicall
                                             access                     control   y
                                             improvements, and database
                                             backup procedures
```

#### Original PDF page 69

```text
Maintainability      Debugging        and    Correcting         bugs        and    Regularly
                      Code                    improving     system     structure
                      Refactoring             for easier maintenance



 Compatibility        System Updates          Ensuring     compatibility     with   As
                                              SUMO,       Python,      PyTorch,     Needed
                                              and desktop environments



 Reliability          Simulation              Adjusting     traffic  simulation     Periodicall
                      Calibration             parameters                     and    y
                                              reinforcement             learning
                                              configurations



 Performance          Database                Managing      SQLite    database      Monthly
 Efficiency           Optimization            cleanup, indexing, and report
                                              storage optimization
```

### Original references

#### Original PDF page 70

```text
REFERENCES:


[1]  Injac,   Z.,  Arsić,    S.,  Drašković,      D.,   &   Arsić,   M.   (2025).    Urban     traffic
        management         using    artificial  intelligence:    A   sustainable     approach      to
        enhancing      urban   mobility.   Journal    of  Traffic  and   Transport     Theory    and
        Practice (JTTTP), 10(1), 30-35.

[2] Akinade,     A.O.,   Adepoju,     P.A.,   &  Ige,  A.B.    Artificial Intelligence    in  Traffic
        Management: A Review of Smart Solutions and Urban Impact.

 [3] Rathore,   S.  P. S.,  Farhaoui, Y., Aniebonam, E. E.,           Nagpal, T., & Kaushik, P.
        (2025,    March).    AI-driven     traffic congestion      management:        a  predictive
        analytics approach for smart cities. In 2025 IEEE International Conference
        on Interdisciplinary Approaches in Technology and Management for Social
        Innovation (IATMSI) (Vol. 3, pp. 1-6). IEEE.

[4]   S.  Rudhra,    S.   Vinod,   P.  Arthi  and   L.  Kurinjimalar,    "Density    Based    Traffic
        Signal System," 2024 International Conference on Power, Energy, Control
        and Transmission Systems (ICPECTS), Chennai, India, 2024, pp. 1-3, doi:
        10.1109/ICPECTS62210.2024.10780421.
```

#### Original PDF page 71

```text
[5]  Gheorghe, C., & Şoica, A. (2025). Revolutionizing Urban Mobility: A
        Systematic Review of AI, IoT, and Predictive Analytics in Adaptive Traffic
        Control Systems for Road Networks. Electronics.

[6] Kodama,     N.,  Harada, T.,    &  Miyazaki, K. (2022). Traffic signal control system
        using     deep     reinforcement       learning     with   emphasis       on    reinforcing
        successful experiences. IEEE Access, 10, 128943-128950.

[7] Huang, S. Y., Chang, H. C., Chen, Y. C., Wei, T. H., Yeh, I. H., Kuan, S. Y., ...
        &   Wu,    I.  (2026).    A  Robust     and    Efficient   Multi-Agent     Reinforcement
        Learning      Framework         for    Traffic    Signal     Control.     arXiv     preprint
        arXiv:2603.12096.

[8]  Almomany,       A.,   Eedi,   E.,   &   Sutcu,    M.   (2025).    Real-time     traffic  signal
        optimization      for   urban    mobility:    a   reinforcement       learning-enhanced
        framework with application to Kuwait City. Frontiers in Robotics and AI, 12,
        1669952.

[9] United    Nations,    "Goal   9:  Build   resilient  infrastructure,   promote     sustainable
        industrialization    and   foster  innovation,"    Sustainable     Development       Goals,
        2023.

[10] United Nations, "Goal 11: Make cities and human settlements inclusive, safe,
        resilient and sustainable,"

Sustainable Development Goals, 2023.

[11]  M.   Muralidharan       and    R.  Pedarsani,      "Analysis     of  fixed-time    control   in
        signalized     intersection     networks,"     IEEE     Transactions      on    Control    of
        Network Systems, vol. 2, no. 1, pp. 22-31, 2014.

[12] Syla, V., & Lala, A. (2026). Microsimulation-Based Evaluation of Fixed-Time
        and Vehicle-Actuated Traffic Signal Control Strategies Using PTV Vissim
        in an Urban Corridor. Informatica, 50(5).

[13] C. Aboy, M. Chua, S. Gochuico, J. Nuesca, and M. Suwanpimol, "PC-Based
        Adaptive     Road     Traffic   Control    System,"     Undergraduate        thesis,   Dept.
        Electron. Commun. Eng., De La Salle Univ., Manila, Philippines, 1994.

[14]  Geotab,    "Video   Intelligence    and   AI-driven enforcement         in the  Philippines,"
        PR Newswire Asia, May 2026.

[15] Grand View Research, "Philippines Intelligent Transportation System Market
        Size & Outlook,"
```

#### Original PDF page 72

```text
[16] DOST-PCIEERD,           "An  Analysis of    Smart    City Development        Frameworks      in
        the Philippines," UP CIDS Policy Brief

[17]  Dubey,    A.,  Lakhani,     M.,  Dave,    S.,  &   Patoliya,   J.  J. (2017,    December).
        Internet of Things based adaptive traffic management system as a part of
        Intelligent  Transportation      System    (ITS). In 2017     international    conference
        on soft computing and its engineering applications (icSoftComp) (pp. 1-6).
        IEEE.

[18]   Zemmouchi-Ghomari,            L.   (2025).     Artificial   intelligence     in   intelligent
        transportation    systems.     Journal   of  Intelligent  Manufacturing      and   Special
        Equipment, 6(1), 26-42.

[19]  Damadam,       S.,  Zourbakhsh,      M.,   Javidan,    R.,  &  Faroughi,    A.   (2022).   An
        Intelligent    IoT    Based      Traffic    Light    Management          System:      Deep
        Reinforcement Learning. Smart Cities, 5 (4), 1293-1311.

[20] Kodama, N., Harada, T., & Miyazaki, K. (2022). Traffic signal control system
        using    deep     reinforcement       learning     with    emphasis      on    reinforcing
        successful experiences. IEEE Access, 10, 128943-128950.

[21] H. Zhang, "Multi-Agent Reinforcement Learning Framework for Traffic Signal
        Control," arXiv preprint arXiv:2603.12096, 2026.

[22] T.  Miller,  "Quantifying    the  Impact    of  RL   on Urban     Congestion,"     Journal   of
        Urban Systems, vol. 15, no. 4, pp. 201-215, 2025.

[23]  A.  Al-Wajih,   "AI   in ITS:   Real-Time     Decision-Making       Architectures,"     IEEE
        Access, vol. 13, pp. 14502-14518, 2025.

[24] M. J. Williams, "Agent-Based Modeling of Urban Mobility Landscapes," IEEE
        Transactions on Smart Cities, vol. 9, no. 2, pp. 112-125, 2024.

[25]  D.  Krajzewicz,     "SUMO      -  Simulation    of  Urban    MObility,"   IEEE    Intelligent
        Transportation Systems Conference, 2012.

[26] NEDA,     "Philippine   Development       Plan 2023-2028: Digital Transformation for
        Connectivity," 2023.

[27] Kodama, N., Harada, T., & Miyazaki, K. (2022). Traffic signal control system
        using    deep     reinforcement       learning     with    emphasis      on    reinforcing
        successful experiences. IEEE Access, 10, 128943-128950.

[28] S.  Suo,    S. Regalado,      S.  Casas,    and   R.  Urtasun,    "TrafficSim: Learning      to
        Simulate      Realistic    Multi-Agent      Behaviors,"      in  Proceedings        of  the
```

#### Original PDF page 73

```text
IEEE/CVF      Conference      on   Computer      Vision    and   Pattern    Recognition
        (CVPR), 2021, pp. 10400-10409.

[29]  K.  AlMulla,   S.  Ashkanani,     F. Hassan,     H.  AlMesbahi,     M.   Alazmi,   and   M.
        Nadeem,     “IoT-Based     Adaptive    Traffic  Signal   Controller    to Optimize    the
        Flow   of Traffic and   Reduce Congestion,”        in Proceedings      of the 2024 1st
        Mediterranean Smart Cities Conference (MSCC), 2024
```

## Appendix B. Revised Chapters 1 and 2

Complete text extracted from the 74-page revised manuscript. PDF page positions include the title page; figures remain in the linked source PDF.

### Revised title page

#### Revised PDF page 1

```text
SMARTFLOW: A Simulation-Based Approach to Traffic Signal Optimization
              and Adaptive Routing Using Reinforcement Learning




















                          A Capstone Project Presented to
                        Faculty of the Institute of Computing
                            Davao del Norte State College
                               New Visayas, Panabo City



                           A Capstone Project Presented by:




                              Johnfel Anthony B. Caredo
                                  Prille Vincent Salibay
                                     Karen B. Solano




                                        June 2026
```

### Revised Chapter 1 — Introduction

#### Revised PDF page 2

```text
CHAPTER I

                                        INTRODUCTION


Background of the Study
        Urbanization, which has led to an influx of people to various cities as well
as   more    people     in  most    cities  throughout      the   world,   has    brought     various
problems    in  traffic management, such as           traffic congestion, pollution caused by
vehicles, increased fuel consumption among vehicles, and inefficiencies in urban
mobility [1].   As the number of vehicles keep increasing, transport infrastructures
in many     urban    areas    fail to  handle     the  growing     demand      for  transportation,
resulting in longer travel times and economic losses [2]. In this context of various
problems    facing urban transportation, it is clear that traffic congestion remains a
problem to deal with as far as urban transportation is concerned.

        Even    with  the   adoption    of several    methods for managing          traffic, a  lot of
urban centers still depend on the           fixed scheme or timed schedule which is also
known    as   the  traditional   way    of functioning     of the   lights  [3]. These    traditional
methods      have    little  capability    to  react    to   changes     in   conditions.     Hence,
transportation     researchers      and    authorities    have    been    investigating     ways    of
changing     the  way    traffic is  planned    and   controlled    through    the  intelligent   and
data-driven systems.

        Research       has    been    conducted       on   using    Artificial   Intelligence    (AI),
simulations,     and    Reinforcement        Learning      (RL)   in   intelligent   transportation
systems     to   help   with   traffic  signals    management        and    analyzing     traffic  [5].
Research results reveal that AI-based traffic control can make changes to signals
based    on   simulated     traffic flow,  while   microscopic      traffic simulations     offer  an
opportunity    to test  out different scenarios before implementing any changes [6].
Agent-based       simulation     allows    vehicles    and    pedestrians      to  be    treated    as
independent      entities,   thus   permitting    a   closer   look   into  traffic  dynamics      [7].
```

#### Revised PDF page 3

```text
Simulation and AI technologies          are   enough    to  show the     ability of technology to
ensure proactive traffic analysis and decision making.

        Amid    growing     urban     mobility   pressures      in  the   Philippines,    transport
systems     are    consequently       overloaded.      The    Philippine    Development        Plan
(2023–2028)      notes   the   need    for information     technology-driven       approaches      to
enhance connectivity and efficiency in lines with the use of organized technology
aimed    at  promoting      the  innovative     transport    mechanisms.       Nonetheless,      the
deployment of simulation-based decision-support systems is yet to be maximally
utilized on a local scale. Therefore, local systems that can take into consideration
the existing road condition patterns and offer options in traffic management may
give more room for making decisions and further planning.

        This   study   centers    on  a  specific   junction   and   the  nearby    road   network
located in Tagum City,       Davao     del Norte.   Validation    of the  research area will be
conducted by means of field observational technique and consultations held with
pertinent    local   government       agencies      to   ensure     that   the   simulated     road
configuration     and   traffic  conditions     reflect  corresponding       ground     conditions.
Information    dealing    with  road   and   traffic conditions    in  the  real  sector   shall  be
used as    references for simulation development             when available from authorized
sources.

        The    proposed     system,     called   SMARTFLOW,           is to   be   used    for  both
evaluating    traffic movements       in  conjunction     with  the   traffic network    and   as   a
decision-preparation instrument          based upon simulated outcomes and data. This
system    will enable    users   to  set  up  the  various    elements     related   to traffic and
study   incident   scenarios,    such    as  road   closures    and    other   factors  that  could
impact   normal     traffic operations.     This   system     will also   assist   in determining
various routing     schemes and the        configuration of traffic signals based upon the
simulation's   data. One     of  the purposes of SMARTFLOW is to help simulate the
implications    of  potential   actions    regarding    the  management        of  traffic  prior  to
performing them.
```

#### Revised PDF page 4

```text
This   research    contributes    to  the  implementation      of  the Davao del      Norte
State College Research, Development and Extension (RDE) Agenda 2026–2030
particularly  the   Innovation    and   Inclusion    (I2) Agenda     of the college     by utilizing
ICT  for  a localized   transportation     issue[19].   The study     is also aligned     to that of
the UN Sustainable Development Goal 11 (Sustainable Cities and Communities)
that  creates     more    efficient,   resilient   and    sustainable     urban     mobility    [10].
Moreover, the study is not only synonymous to the CHED A.C.H.I.E.V.E. Agenda,
but  also    its Harmonized       SDG-Based        Research      and    Innovation     goal   which
advocates     for  researches     and   innovations     that  respond     to local,  national   and
international    concerns      as   well   as   contributing    to   the   achievement       of  the
Sustainable     Development       Goals    [10],  [16].  Lastly,   the  research     supports    the
Department      of  Science     and   Technology      Harmonized       National    Research     and
Development Agenda (HNRDA) in the sustainability pillar as it employs science,
technology and innovation for a local transport and urban mobility matter [3].

        However,     there    is still a  strong   demand      for  localized   decision-support
systems    that  have    the  capacity    to utilize  site-specific   data   and   give  the  traffic
management entities the         chance to observe how the road disturbances, routing
choices, and traffic light arrangements           would likely    behave before any changes
to the   built environment      are   made.    In  the   case   of  Tagum     City,  the  ability  to
validate the results of a simulation through the use of current roadway conditions
and     traffic   data     could     provide      useful     information      for    traffic-related
decision-making       purposes.     The   main    purpose     of  this  study   is  to  develop    a
program    called   SMARTFLOW          that  will enable localized      simulation-based traffic
analysis, scenario testing, evaluation of routing methods, and signal planning.
```

#### Revised PDF page 5

```text
Objectives of the Study

General Objective

        To   create    SMARTFLOW,           The   main   objective  of  this  project  is to  develop   a
Reinforcement     Learning-based      simulation   approach     for  traﬃc   signal   optimization   and

adaptive routing for urban development planning. Speciﬁcally        , this study aims to:


    1.  Design      an   environment       of   simulation     to  model     a   specific    real-world
        intersection     in   Tagum     City   which     can   include    road    maps,     traffic flow
        statistics,    and    geographical       features     around      the   intersection      to  be
        modeled.
    2.  Use actual traffic data for modeling purposes to simulate the traffic volume
        and traffic state for the modeled intersection.
    3.  Create a simulation interface which enables users to set traffic parameters
        (like size   and timing of signal systems) to design and test possible traffic
        scenarios.
    4.  Run different types of scenarios on the model (road closures, modification
        of existing    roadways, etc.)       to analyze     the effect of proposed changes on
        traffic flow and to develop plans for rerouting vehicles.
    5.  Conduct      modeling      of   event    driven    scenarios     (e.g.   peak    traffic  times,
        holidays,     road   closures,     etc.)  in  order    to  study    traffic  behavior     under
        different conditions.
    6.  Use    reinforcement      learning technology to         allow the    traffic  signal   to learn
        from the traffic conditions and provide information on how to arrange traffic
        signals.



Significance of the Study
```

#### Revised PDF page 6

```text
This study     aids off the    development of simulation-based             and data-driven
traffic  management         by    amalgamating         traffic  data    from    real-world,     traffic
simulation,     road     closure      and     rerouting     scenarios,      and     Reinforcement
Learning-based       traffic signal   control.  SMARTFLOW creates an environment for
evaluating    traffic  conditions    as   well  as  possible    traffic management         strategies
prior  to implementation.       Through     the  simulation     of both   existing and proposed
traffic  signal   conditions,     the   system     supports     analyzing     whether      a  certain
intersection    will benefit   from    traffic signal   and    which   signal   configuration     can
result in better traffic performance.

The findings of this research is likely to serve advantages to:

    ●   Local Government Units (LGUs) and Traffic Management Authorities.
        The system will potentially act as a decision-support tool for assessing the
        existing traffic   situation   with  respect    to the potential installation of signals
        and   development       of  signal   operations,     possible    closures    of  roads   as  a
        result of construction activity, and alternative routing options. This will help
        traffic  management        authorities    go  through     possible    traffic management
        options that could be implemented prior to applying changes to the current
        traffic situation on the roadway.
    ●   Traffic   Planners      and    Urban     Developers.       This   simulation    will  provide
        traffic flux, queue configuration, waiting time, and other traffic performance
        metrics in various      scenarios. This will help traffic planning and evaluation
        with   respect   to the   implementation of signal systems, road management
        techniques, and other transportation interventions.
    ●   Traffic    Enforcement        Officers.     The    system    can    be   utilized  by   traffic
        enforcement      officers to   study the     potential ramifications of various         traffic
        events on road closures, rerouting, and overall traffic flow within the study
        area. This will yield more preparedness and coordination for any disruptive
        traffic conditions.
    ●   Drivers     and     Users     of    the   Roadways.         The    evaluation      of  signal
        installation,   signal    operation,    and    alternative    routing    opportunities     will
```

#### Revised PDF page 7

```text
serve   the purpose of enhancing traffic flow therefore reducing delays and
        enhancing travel experience.
    ●   Pedestrians.       The    simulation     will  take    into  account     pedestrians      and
        pedestrian movement and activity will be considered when determining the
        operational characteristics of traffic signal systems and traffic situations.
    ●   Researchers        and   Future    Developers.       The results of this      research can
        be   used    as  a  reference     for  future   studies   containing     traffic simulation,
        reinforcement      learning-based       traffic signal   control,   traffic rerouting,    and
        event-based      traffic  scenarios    in  addition   to  data-driven     decision-support
        mechanisms for urban transit.

Scope and Limitations

        The    subject    of  the  present    research     is  SMARTFLOW           development,      a
simulation-based traffic analysis and decision support tool for a given intersection
and surrounding       road constructions nearby Tagum City in Davao del Norte. The
method for simulation creation          will be developed using         the  Simulation of Urban
Mobility   (SUMO).     The simulation site       will be created on      the basis    of  the actual
road construction of the selected study site. Various data collection methods will
be used for validation of the simulation site. The available traffic data which was
acquired    from   appropriate     sources    located    in  Tagum     City. The    traffic data   will
include   traffic volume     and   relevant    traffic conditions    within   the  site  simulation.
Other   landmarks      located    in the  study    site and    other  road    condition   that   were
used in simulation site building will also be used in the simulation development.

        The simulation denotes vehicles and pedestrians as traffic entities that are
created according to traffic volume and conditions specifically being acquired by
data  provided    or accomplished.        The component of Reinforcement Learning                  will
be applied in the traffic signal control process, in which traffic signal control is an
agent    of  learning.    The    agent    will observe      traffic conditions     that   are   being
simulated    and    will  choose     an   appropriate     signal   action   according     to  certain
performance      metrics    defined.   This   will enable    evaluation     of  the  existing   traffic
```

#### Revised PDF page 8

```text
conditions and proposed signaling placement and configurations at pre-selected
intersection    areas    that   include    those    areas     that   do   not   currently    have    a
signalization.

        The    SMARTFLOW           system    will  enable    the   simulation    of  various    traffic
scenarios,     including    normal     traffic situations,    peak    traffic  hours,    weekends,
holidays, road barriers, and accidents, among other cases of traffic disturbances.
Furthermore,      the  SMARTFLOW           system    will allow   for  road   closure   and    detour
assessment,      which will   enable    the analysis of other road configurations as well
as how    traffic flows based on the initial configuration of the roads following their
closure.   Traffic  simulation    performance       measures      generated     by  SMARTFLOW
will ultimately   include    vehicle   waiting   time,   queue counts,      traffic volume,     travel
time, and traffic density, among others.

        This   research     has    been    conducted      on   a   small   area    with   a  specific
intersection    and   some     connects     junctions   and    roads.   It does   not   claim   to  be
representative      for  the   whole     of  the   Tagum      City.  The    effectiveness     of   the
simulation    process    will  depend     on  the   accessibility   of  the  relevant    traffic data
obtained from references and records. As a result, the simulated data will provide
estimates    of modeled traffic conditions based on available values without giving
actual measurements on an instantaneous traffic basis.

        The   system     does not    include   live  traffic feeds   and   CCTV, GPS        tracking,
IoT  devices,    and   real-time    traffic  sensors    will not   be  part  of  the   system.    The
technology     will also   not  interface   with   or  control   any   traffic signals   and/or    the
actual   physical    traffic  infrastructure.     Therefore,     the  suggested      use    of  traffic
signals will only be judged in a simulation environment and will not be seen as an
actual  recommendation         for  implementation       in the field   until further engineering
evaluations and approvals are made.

        The   Reinforcement       Learning     component      will  only  focus    on  traffic signal
operation in    the simulated environment as            it affects its results.   Quality   of traffic
data, simulation settings, defined traffic scenarios, and rewards and performance
```

#### Revised PDF page 9

```text
metrics set by the contributors will determine the effectiveness of this component.
This research does not include construction, installations, or operations of traffic
signals,   physical    modifications     to   roads,   or  implementation       of  any    rerouting
schemes on the actual road network.


Review of Related Literature and Studies

Related Literature

Traditional Traffic Management Systems

The   conventional     approach     to  managing      traffic remains     based    on  fixed   signal
schedules and manual enforcement of traffic regulations [11]. Fixed signal control
involves pre-determined settings derived from the previous research done on the
traffic volume    [12]. Although the fixed signal control is convenient and simple to
operate, its predetermined signal timing is often not adaptive to traffic fluctuating
demand     led  to queuing     and excessive delays [13]. The research undertaken on
the smart    control   of the intersections suggests that the applied computer-based
technologies     make    it more   efficient  and   save   time compared       to the other traffic
management strategies [14]. The             limitations discussed above suggest the need
for conducting      the  assessment       of  the  traffic  conditions    as  well   as  evaluating
several possible signal configuration options prior to the actual implementation.

Intelligent Transportation Systems (ITS) in the Philippine Context

Intelligent   Transportation      Systems       (ITS)   are   a   combination      of   information
technology,     transportation     data,   and    other   data-driven     solutions    in  order    to
manage     traffic  flow,  enhance      mobility,   and   promote      road   safety   [15].  In  the
context   of  the  Philippines,    the development       of ITS    implies going hand       in hand
with   the   smart-city    movement,       in  use    of  the   technologies      to  solve    urban
transportation    problems     [16]. As   previous research       showed, the      adaptive    traffic
management        approaches      are   utilized  through    traffic  data   to  adjust   the  traffic
management systems to the             changes    in  traffic conditions [17]. The existing ITS
```

#### Revised PDF page 10

```text
technologies     can be either based upon real-time sensors or utilizing the existing
data in order to simulate efficient ITS applications.


Integration of Artificial Intelligence in Traffic Management

The   use    of  Artificial  Intelligence    (AI)  in  traffic  control   systems      has   enabled
techniques of traffic monitoring and           support    for transport-related decisions [18].
There   have    been methods       based on      AI  used   for  traffic signal   control, including
procedures applying        Deep Reinforcement Learning             to  find  suitable traffic signal
operations     based    on   the  current    traffic situation   [19].   In  addition   to  that,  the
researches      have     included      the   use    of    the   method      of   combined       agent
reinforcement       learning,      providing     evidence       of   the    applicability     of   the
learning-based      part for the    control of traffic flow rather than using the traditional
systems     based    on   fixed  rules   [21].  Nevertheless,      the   aforementioned       studies
have   implemented       the  use   of  current   data as    well as   the Internet    of Things or
several    intelligent    agents,     which     is   different    from    the   method      used     in
SMARTFLOW.          Thus,    SMARTFLOW           is  based    on   the  principle   of  applying     AI
specifically    through     Reinforcement        Learning     for   traffic  signal    control   in   a
simulated setting with vehicles and pedestrians represented by traffic entities, not
autonomous AI agents.

Reinforcement Learning in Traffic Signal Control

Reinforcement Learning (RL) is a machine learning method that allows an agent
to  gain   knowledge       about    making     decisions     through     its interaction     with  the
environment.      It receives    feedback     on  its actions.    For  instance,    in traffic signal
control,  the traffic signal control is      the learning     agent   while   the traffic signals of
the simulation make the environment [20]. Earlier works utilizing DL techniques in
traffic signal   have    established     the   possibility  of  enhancing      traffic performance
through    simulation    [20][22].   RL   traffic signal  systems use       data   such as    vehicle
count and density, waiting time, and queue length as states while phase change
of signals to be chosen as actions and traffic performance measures are used as
```

#### Revised PDF page 11

```text
reward     [21][23].   These     methods      enable     the   implementation        of  the   RL    in
SMARTFLOW, where             traffic signal control    has been used as the learning agent
and various     traffic conditions    and   traffic signal   control configurations have been
evaluated     in  addition   to  evaluating     the   possible    implementation       of  the  traffic
signal at a specific intersection.

Agent-Based Traffic Simulation and SUMO

Agent-based and microscopic traffic simulation methods provide a very detailed
representation     of  the   individual   traffic  entities   and   their  interactions    in a  road
network     [24].  These     methods      allow   for   the  representation       of  vehicles    and
pedestrians separately in a simulated environment; however, they do not operate
in the same way as autonomous agents with artificial intelligence. The Simulation
of Urban    Mobility (SUMO) is        an  open-source microscopic and multimodal traffic
simulation    tool, which allows for modeling          vehicles, pedestrians, road networks
and traffic signal operation. Furthermore, SUMO incorporates the TraCI interface
which   makes     it possible    for  external    applications     to  control   and   interact   with
simulation    elements      while   it is  running    [25].  Earlier   studies    used    SUMO      for
examining      traffic signal    control   and    use   of  Reinforcement       Learning     [25].   In
SMARTFLOW, SUMO will               be  used   to  simulate the selected intersection as well
as connected road segments in the city of Tagum using the validated road design
and local traffic data. The traffic signal controller will be used to interact with the
simulation     as  Reinforcement        Learning     agent    for  the   implementation        of  the
project.

Traffic Data-Based Simulation

The practical     implementation      of  traffic simulation is strongly associated with the
quality of input data regarding the genesis of traffic generation for the simulation
model.    Traffic   input   data   with   respect     to  traffic  flows,   traffic  counts,    traffic
generation rates, and other relevant traffic information can be used as inputs for
traffic generation     for  the   simulation    model     [26].  Use    of observed      or  officially
published     traffic  information     can    prove    to  offer   a  more    realistic   simulation
```

#### Revised PDF page 12

```text
compared to hypothetical traffic levels. In this study, local traffic data available for
Tagum     City  will be   utilized  to  estimate    the   traffic inputs   to  be   used   within the
simulation    environment      for  the  study area.     Field verifications     and consultations
with  relevant    local   government       offices   would    also    be  performed      in  order   to
validate   if the road   configurations and characteristics of the specific intersection
selected remained consistent.

Road Closure and Traffic Rerouting

Various    incidents    such   as   accidents,    construction,     maintenance,       emergencies,
public  events    and   other   disruptions    lead to closings of roads which in turn may
throttle  traffic flow   by  limiting the   capacity of the      roads   and   making vehicles to
divert to other roads [27]. With the use of traffic simulation on road closures, the
potential   effects   of road    closing   as well   as options     for diversion can be        known
even before any such          restriction takes    place [28].    A section of road in question
which   is  restricted   or  limited   in a  simulated     environment allows        comparison of
alternative   routes    based    on   travel  time,   waiting   time,   queue    length    and   traffic
flow. The project will factor in road closures and rerouting in the selected Tagum
City road network to analyze how road closure impacts traffic conditions in case
of road closure so as to discover alternatives.

Event-Based Traffic Simulation

Traffic situations    change     based on the      intensity   of  traffic at certain times, traffic
conditions on roads, availability of road usage, and external events. For instance,
peak times, weekends, public holidays, collisions, road constructions, and public
ceremonies may create unique traffic situations compared to regular road usage
[29]. Event-based or scenario-driven traffic simulation allows testing the situation
under    controlled    conditions     and    comparing      the   results    [30].  In  this   regard,
SMARTFLOW will implement event-based scenarios in order to test the different
situations concerning traffic volume and conditions on the roads, and it will cover
scenarios     connected      to  the   peak     periods,    weekends,       public   holidays,    road
blocks, accidents, and roadworks.
```

#### Revised PDF page 13

```text
Simulation-Based Decision Support for Traffic Signal Planning

Simulation models for decision-support systems offer a tool for the evaluation of
different  strategies    in the  field of transportation prior to their deployment in the
actual road system [31]. Within the field of traffic planning, it is possible to utilize
simulation in    the comparison       of traffic  conditions    so as   to assess    the impact of
various   traffic  control   measures      with  parameters      such   as   waiting   time,  queue
length,  travel   time  and    volume    of  traffic. Thus,   when dealing       with  traffic signal
analysis    the    activities   require    to   evaluate     not    only   how     to  operate     an
already-existing signal but also establish whether the traffic signal can be helpful
at the  analyzed     point  and what     specific settings should be used with respect to
specific traffic conditions existing there. In this regard, SMARTFLOW is based on
the  same    principle   whereby the      application    of  local data,   validated    Tagum City
road    environment,       event-based        scenarios,      road    closures     and     diversion
procedures and the Reinforcement Learning-based control system are combined
together   to  obtain   simulated     performance      results   suitable   for  the  evaluation of
possible traffic point placement.



Related Studies and Systems

Dual-Targeting Deep Reinforcement Learning Traffic Signal Control System

        In the research conducted by Kodama et al. [32], a multi-agent traffic light
control  mechanism       based    on   a  dual-targeting     approach of deep        reinforcement
learning   (DRL)    in  conjunction     with   Simulation    of  Urban    Mobility   (SUMO)      was
suggested.     The    proposed     model     works    with   traffic-state   parameters     like  the
positions of vehicles, density of the lanes, the variations found in density, and the
speed of    the vehicles,    so that traffic signal commands           can be prescribed while
minimizing the total wait time from a number of vehicles as a whole. Each of the
```

#### Revised PDF page 14

```text
situations under deliberation shows how the SUMO platform can provide a good
environment      for  training    a  traffic  signal   controller    based     on   reinforcement
learning.    Moreover,      such    a   piece     of  research      is  directly   connected       to
SMARTFLOW,          given     that   both   models      apply    reinforcement      learning    and
SUMO-based approach for traffic signal controlling; whereas the only focus of the
study was on identifying the optimization meaning of traffic signals with the help
of  DRL,    SMARTFLOW          broadens      the  entire   idea   associated     with  the   use   of
simulation by adding a validated localized intersection in Tagum City, real data on
traffic and occurrences       based on traffic events, and management of traffic such
as closure and rerouting.

        The   framework      consists   of a  neural   network    handled by      a Traffic  Signal
Control   System     (TSCS).    As   illustrated in the   conceptual     diagram    in  Fig.  1, the
input  state   includes   vehicle   position    (($P_t$),   lane  density    ($D_t$),   change     in
density   ($\Delta    D_t$),    and   velocity    ($V_t$),    which    are   processed     through
multiple   hidden   layers   (256   and 128     ReLU units)     to output    Q-values    for action
selection.   The    system    operates     through    a  closed-loop     interaction    where    the
SUMO      environment      provides    traffic  states,   and   the   RL   agent    issues    signal
commands       (actions)    while   receiving    rewards     based     on   the  minimization      of
cumulative waiting time.
```

#### Revised PDF page 15

```text
Fig. 1. Conceptual diagram of the proposed traffic light control
                                             system.

        Extensive     simulations    were    performed      to  test  the  effectiveness     of  the
dual-targeting    algorithm.    The   results  of  these   simulations     are shown     in Fig.  2.
Here,   learning    curves    for  each   of  1000    trials are   shown.    Although     both   the
standard DQN       and Multistep DQN         architectures exhibited greater        variance,    the
proposed     “Dual-Targeting”      method     provided    a   much    lower   unbiased     sample
variance   of  0.02  after  1000 trials.   Such    evidence from the simulations validates
that the agent achieves stabilization and reduction in vehicle waiting time as the
agent learns within the simulation environment.



















       Fig. 2. Simulation results showing the reduction in waiting time using
                                  the proposed RL method.

        The   system    is  closely   related  to  SMARTFLOW          since   both   make    use of
Deep    Reinforcement      Learning     (DRL)    and   the  SUMO      environment     to  optimize
```

#### Revised PDF page 16

```text
traffic signals.   It explains   the   techniques     to  determine     traffic state  and   how    to
design reward function from traffic related parameters, e.g. total waiting time [30].
However, SMARTFLOW              is more advanced in that it uses these methods on an
intersection    in  Tagum     City  which    has    already    been    verified  to  be   similar   to
real-life circumstance.

TrafficSim: Learning to Simulate Realistic Multi-Agent Behaviors

        According to a research study by Suo et al. [33], the TrafficSim introduced
the Multi Agent Behavior         Model which can provide realistic and socially realistic
traffic simulations in the area of real life data. The TrafficSim study creates traffic
behavior    through     human      demonstration       and   models     the   behavior     of  traffic
participants   through    neural   network     architecture.   This study     opens avenues for
data-driven    simulations     of traffic  as  well  as   producing    realistic  traffic behavior,
even   though     it cannot    be  implemented       for  SMARTFLOW           due   to  the  study’s
difference. On the contrary to TrafficSim, SMARTFLOW will make use of SUMO
to portray vehicles and pedestrians as             traffic entities  through the     application    of
the  local traffic data,   while   Reinforcement       Learning will    be implemented        on  the
traffic signal controller. Hence, while TrafficSim has shown evidence for providing
data-driven traffic simulation, but SMARTFLOW will utilize localized traffic signal
evaluation related to traffic management circumstances.

        TrafficSim    makes     use    of  an   implicit  latent  variable    model    to  generate
socially  consistent    plans for each agent in a scene. The architectural framework
of TrafficSim    is  presented     in Fig.  3.  Here the    system     has  taken   the bird’s   eye
view (BEV) of the map, which includes the states of agents into account through
a CNN based encoder. It then employs a graph neural network (GNN) in order to
model the interactions amongst the various agents on the scene. Finally, it uses
the  MLP    decoder     to predict   future   trajectories   or movements of agents over a
longer time duration.
```

#### Revised PDF page 17

```text
Fig. 3. System architecture of TrafficSim illustrating the CNN encoder, interaction
                                graph, and trajectory decoder.

        The effectiveness of the TrafficSim system has been illustrated in the form
of its  ability  to  create   diverse    and    socially   consistent    trajectories    for  multiple
agents in    a multi-agent model. An illustration can be seen in Figure 4 where for
each   vehicle    agent,    multiple   feasible    future   trajectories   have    been    predicted,
using   a  single    observation     of   the  given    environment.      When     the   predictions,
marked in red and blue are compared to the actual trajectory, predicted as green,
it highlights   the  fact  that  the   TrafficSim    system has      made accurate predictions
about    the   behaviour      of  drivers    in  normal     conditions,     including    the   driving
behaviour characteristics of maintaining lane and avoiding collision, essential for
the realistic urban modeling.







            Fig. 4. Visual output of TrafficSim showing diverse multi-agent
                   trajectory predictions and ground truth comparison.

        The relation of this study to SMARTFLOW is because it shows how actual
data and data-based traffic simulation can be used to model traffic behavior in a
simulated setting. TrafficSim will deal with learning realistic vehicle trajectories for
self-driving tests    while   SMARTFLOW          will focus on modeling         vehicle demand in
terms of traffic data at an intersection of Tagum City. The difference here is that
TrafficSim      models      autonomous         learning-agents        for    the    vehicles     while
```

#### Revised PDF page 18

```text
SMARTFLOW          will use   reinforcement     learning to add to       the optimization of the
traffic signal   controller    and   will  test  the   various   signal    strategies    within  the
simulation environment.

IoT-Based Adaptive Traffic Signal Controller for Congestion Reduction

        AlMulla et al. described an adaptive traffic light controller designed based
on Internet of Things (IoT) technology and utilizing ultrasonic devices in detecting
the presence of vehicles and their queues to change the timing of the traffic light
signal. The experiment shows the way traffic-related information is utilized for the
modification of the     signals   changing cycles       and the    reduction of waiting time of
cars as a result, as compared to the standard system that is static. Although the
experiment     is  directly   related   to  SMARTFLOW           because     it demonstrates      the
effectiveness and usability of traffic-controlled signal systems, their methodology
is based     on   the   use   of  physical    sensors     and   real-time    systems.     Whereas
SMARTFLOW          is based    only   on  the simulation system using          SUMO simulation
environment     and   available    traffic information    and data,     comparing     the systems
used.   SMARTFLOW          has the    unique   advantage of allowing the          user to   analyze
such factors as the roads configuration and changes, in case of emergencies.

        The architecture of this system uses an Internet of Things (IoT) framework
that incorporates the      placement of ultrasonic sensors at fixed spacing along the
roadway     to  monitor    the  presence     of  vehicles    and   measure     the   length   of the
queue.   According     to  the  architecture shown        in Fig.  5, the information obtained
from  the   sensors    is sent   to  a  central  controller   that  uses   a smart algorithm to
modify   the  default   green    time  of  60   seconds.    The    controller  uses    the  level  of
congestion     it detects to dynamically       either  increase    or decrease     the amount      of
time allocated for each phase of the traffic signal, thus ensuring that the junction
is able to adapt flexible traffic conditions.
```

#### Revised PDF page 19

```text
Fig. 5. System architecture of the IoT-based adaptive traffic signal
                                             controller.

        Performance of the system was validated with a working prototype, along
with a mobile app. The system indicates congestion levels like low, medium and
high  as   shown     in Fig.   6  using   smartphone       interface.   The   study   showed      that
adaptive   method     increased the overall traffic flow and also reduced the average
waiting time significantly at the intersection.















         Fig. 6. Sample output showing the real-time congestion monitoring
                                            application.

        The relevance of this study to SMARTFLOW is shown by the practical use
of traffic  data   such   as   the  queue     length   in  an  adaptive    traffic signal   controls
```

#### Revised PDF page 20

```text
system.    Similar   to  the  work    of  AlMulla   et  al., SMARTFLOW           also  uses   traffic
conditions    as  a  basis   for the   evaluation    of traffic  signals.   However,     unlike  the
present   system     that  utilizes  physical   IoT  sensors    for real-time    traffic detection,
SMARTFLOW          does   employ SUMO and existing traffic data to develop localized
traffic  conditions.     This    system     allows     SMARTFLOW           to   test   the    signal
configurations, road closures, changes in routes, and many more events without
making any changes to the physical sensor system.

Synthesis of Related Studies and Systems

        The    studies     reviewed     have     shown      Reinforcement       Learning,      traffic
simulation,    and   adaptive     signal   control    can   contribute    significantly   to  traffic
management.       For   example,    Kodama et       al, used Deep      Reinforcement      Learning
and   SUMO     for  traffic control   while   Suo   et al, used    real-world data     for detailed
traffic simulation.   AlMulla    et al showed the use of traffic information for adaptive
control   based    on   IoTbased      physical    systems.     Thus,    these    studies   mention
important    approaches      for traffic  signal  optimization,    data-based simulation and
traffic-responsive control activities.

        Nonetheless,      the  systems     analyzed    above    are not    in accordance      to the
intended     purpose     of   SMARTFLOW.          Existing    works     have    concentrated      on
adaptive     traffic  signal    control,   data-driven      traffic  simulation     or   real   time
sensor-based       traffic  management         while   not   putting    emphasis      on    utilizing
localized traffic data and a proven road environment to determine proposed traffic
signal  placements      and   configurations for various       traffic scenarios. Further, very
few cases integrate       road   closure and     rerouting approaches        with Reinforcement
Learning based evaluation of traffic signals in a localized Philippine intersection.

        To fill the  existing gap, SMARTFLOW              has  developed a simulation-based
traffic decision-making      support    system targeted at a particular location including
Tagum City's main       intersection as well as relevant road sections. The model for
the present project will incorporate the characteristics of the considered locations
```

#### Revised PDF page 21

```text
including   updated     information    collected   locally  to  simulate    traffic flow  within
SUMO.     The   traffic signal  controller   will be   improved    by   using  Reinforcement
Learning    for  the  valuation    of  the  selected    signal  configuration     and   actions.
Event-based     methods     will be   used   to  enable   discussions    of  emergency      road
closures    and   rerouting    of  vehicles    from   one   point   to  another    in  order   to
investigate   the  impact    of  different  traffic scenarios    on  the  traffic flow   for the
studied area.

Table  1.Comparative Analysis of Related Traffic Management Systems and
SMARTFLOW


    Features          Dual-Target        TrafficSim         IoT-Based         SMARTFLOW
                        ing  DRL             [33]            Adaptive
                           [32]                           Traffic Signal
                                                            Controller
                                                                [34]

 Main                 Deep             Multi-Agent        IoT +              RL +
 Technology           Reinforcem       Trajectory         Adaptive           Agent-Base
                      ent Learning     Learning           Signal Control     Simulation

 Simulation           SUMO             Learned            Prototype-Bas      SUMO
 Environment                           Traffic            ed Traffic
                                       Environment        System

 Adaptive             ✔                                   ✔                  ✔
 Signal Control

 Traffic                               ✔                                     ✔
 Data-Based
 Simulation

 Autonomous                            ✔
```

#### Revised PDF page 22

```text
Agents

 Road Closure                                                                 ✔
 Analysis

 Rerouting                                                                    ✔
 Analysis

 Event-Baseed                                                                 ✔
 Scenarios

 Localized                                                                    ✔
 Traffic
 Simulation

 Traffic Signal                                                               ✔
 Placements
 Evaluation

 Real-time                                                ✔
 Infrastructure
 Dependency

 Decision                                                                     ✔
 Support
 Function


        Table  1  summarizes      the analysis of the     literature on traffic management
related  to  the  proposed    SMARTFLOW system. In contrast              to the  other models
analyzed such as the use of deep reinforcement learning, traffic simulation using
data-driven multi-agent systems, and the use of IoT-based signal control systems
in traffic management as presented below, where a large part of the focus is on
implementation     and differs   from one study      to  another.  The Dual-Targeting DRL
model demonstrates        the effectiveness    of  the SUMO      and   RL for adaptive signal
```

#### Revised PDF page 23

```text
control,  while   on   the   other   hand   the   TrafficSim    model    employs     a  method     of
learning realistic    traffic patterns   from   data. The    use   of  the IoT-based system is
able to provide real time traffic signal control while utilizing information based on
pre-constructed       infrastructure.    The     SMARTFLOW           system     utilizes   a   local,
simulation-based      approach      utilizing  available   traffic data   and   a  proven    Tagum
City road   environment      as follows. The      use   of reinforcement      learning applied     to
traffic  light  signals,    analysis    of  road    closure    and    rerouting,    event    -based
scenarios, and evaluation of possible traffic signal installations are all included in
the SMARTFLOW model.

Definition of Terms

Agent-Based        Simulation.     A   type   of simulation     modeling    approach      that  uses
models in which individual entities (e.g. vehicles, pedestrians), each of which can
act  as  an   agent    with  individualized    autonomy      to  allow   for interactions    among
them using technologies in simulations.
Artificial   Intelligence     (AI).  A   definition   of  AI  is  that  the   term   refers   to  the
capability of computer systems to accomplish tasks that normally require the use
of human     intelligence to carry out the activity, such as learning how to complete
tasks by itself.
Autonomous        Agent.    Autonomous        agents    are  independent      entities  capable    of
interacting   with  their environment, making         decisions    and/or carrying out actions
without the need for human intervention.
Decision-Support         System.     A   type  of  system     used   by   computer     systems     to
assist  users    in analyzing     and   making     decisions    about    activities  based    on  an
analysis   of  scenarios     derived    from   simulated    events    and    simulations    through
data analysis processes.
Emergency Vehicle Priority. A traffic management process where the timing of
traffic signals is changed to allow for equipment to gain faster entry into the area
where it is needed via the operation of traffic signals.
Heterogeneous        Agent    Behavior. Differences in behavioral patterns associated
with  agents    used   in  simulations    to  depict   daily  activities performed by       agents,
```

#### Revised PDF page 24

```text
including   different  characteristics for different agents based on their behavior as
drivers and in terms of walking behavior.
Intersection Traffic Flow. Refers specifically to traffic causing a movement and
interaction of any agent type at an intersection controlled by a traffic signal.
Queue     Length.    A   measure      of  the  number      of  vehicles    waiting   at   the  same
signalized intersection.
Reinforcement        Learning      (RL).   A  type   of  machine     learning    used   to  develop
optimal    actions   by   having    the   agent    observe    its  environment      and    receiving
rewards or penalties for its actions based on how well its performed.
Road Constraint. A definition of some condition that prevents the normal flow of
traffic across the roadway (e.g., lane closure, road construction accident).
Simulation      of   Urban     Mobility    (SUMO).      An    open-source      "traffic  simulation
software"    used    to  model     traffic  movement       based     on   the   actions    taken   by
individuals using the software.
Traffic Signal Control. The process of managing actions within the traffic signal
process to control the flow of traffic at the intersection.
Traffic Simulation. A type of traffic simulation where computer simulation can be
used to model the flow of traffic in the virtual system.
Adaptive     Traffic   System.     An   automated      traffic management        system     that  can
change     the   timing   of  traffic  signal   systems      as   traffic conditions     and   traffic
demands change.
Pedestrian     Demand.       The   number     of pedestrians      who   need to cross      a certain
street or intersection.
Traffic Density. The density of traffic in terms of the number of vehicles present
on a specific roadway at any point in time.
```

### Revised Chapter 2 — Methodology

#### Revised PDF page 25

```text
CHAPTER II

                                       METHODOLOGY

        This     work     employs       the    Hybrid     Development         Methodology,        the
complementarity between          the structured procedures of          the  Waterfall model and
the  flexible  strategies    of  Agile.  In  the  first stages    of  the  project,   the  Waterfall
model served as a base for the study including planning, requirements elicitation,
and   system      design.    This    way,    precise    objectives    in   the   form   of   system
specification    and   requirements      for  traffic simulation     and   traffic modeling     were
achieved before the development process began. In contrast, the Agile principles
were   applied    at  the  stages    of  implementation,       testing,  and   refinement.     Thus,
iterated simulation,     continuous testing, debugging and repeated improvement of
the  simulation     environment,      traffic  signal   controller    based     on   reinforcement
learning (in particular the developed dashboard) could be performed. Therefore,
the combination      of the   Waterfall   approach     and Agile    principles helped create a
balance    of   structure   and    flexibility, which    perfectly    matches     the   purpose     of
AI-based traffic simulation.
        The    project   starts  with   the   Planning     Phase    where     the  project    team's
members      define   the   purpose,     goals,   timetable,    and   resources     which    will  be
needed    based    on   what   was    outlined   in the   approved     project   proposal.    In  this
phase,    they  also   determine     the   study   site  and   traffic scenarios     to  use  in  the
simulation and define the viability and direction of the system.
        During    the   Analysis    Phase,     the  project   team    collects   final  information
regarding    the  system    requirements      through the     study of    traffic condition, traffic
pattern,  pedestrian     behavior,    and   requirement     details to develop      the simulation
and reinforcement learning applications.
        Within   the   Design    Phase,    the  promoters     turn   all identified requirements
into  organized     architecture    of   the  system,     which   includes    all  designs    of  the
workflow     of   simulation,     framework       of   reinforcement       learning,    dashboard
interface,   and    system     interactivity  flow.   Also,   the  developers      create    several
```

#### Revised PDF page 26

```text
diagrams    and   models     of  the system,     so as   to provide    a visual   interface   of the
operation of the system.
        During the implementation phase of the project, the SMARTFLOW system
will be developed using an iterative approach. Development cycles of simulation
environment and reinforcement learning integration and dashboard interface will
be   carried     out.   Development        cycles     will  involve     building,    testing,    and
improvement        of    the    system      components         for   various     iterations.    The
implementation       will  involve    configuration     of  SUMO      simulation     environment,
development      of  agents     for  both   vehicles    and   pedestrians,     integration   of  the
Python     and    TraCI     communication        protocol,    design     and    development        of
reinforcement     learning    model,   and   local   dashboard     and SQLite      database. The
key objective of this phase will be to prepare the core components of the system
for the final testing and evaluation.
        The proponents carry out several series of tests during the Testing Phase
of the  project   to assess    how   the system      behaves with regards to various traffic
scenarios and road constraints. The proponents take into account the simulation
environment       and    traffic   lights   response,      the    results    they    obtain     from
reinforcement learning, and the display of data on the dashboard.
        The Refinement Phase is           marked by      the refinement of the system which
involves   fixing all detected     problems and making          adjustments to      the simulation
processes. It represents the last phase of the project. Although the refinement of
the  system     is  only   performed     for  the   duration    of  this  particular   study,   it is
expected that this will help maintain the stability of the system during future tests.
```

#### Revised PDF page 27

```text
Figure 7. Hybrid Development Methodology



SYSTEM PLANNING

Project Team Organization

        As  can be noted from Figure          8, the project team      is structured in    such   a
way   that allows for effective coordination, good communication, and appropriate
delegation of responsibilities during the process of developing the SMARTFLOW
system.    The   Advisor    provides    the  academic     as   well  as  the   technical   advice
needed     to  ensure    that  the   study   adheres     to  the   established     standards     of
research. The project manager and the documents leader manages the planning
phase    of the  project,   provides   assistance     with  coordination    of  tasks,  monitors
progress,   supervises     the  scheduling    of  activities, and   manages the       creation of
relevant project documents. Under this role is an individual known as the system
developer and      the system analyst. The        system    developer has the responsibility
of  programming,        implementing       the   system,     developing      simulations,     and
integrating the technology. The system analyst has the responsibility of analyzing
```

#### Revised PDF page 28

```text
the requirements of the system, discovering the various processes of the system,
and  assisting    in the  formulation    and   evaluation    of  the  SMARTFLOW         system.
Such   an  organization makes it possible for the team to have coordinated efforts
in providing academic guidance, project management, documentation, technical
development, and system analysis.
































                          Figure 8. Project Team Organization



Work Breakdown Structure

        The display of the     Work Breakdown Structure in Figure 9 shows how the
SMARTFLOW         Traffic  System    Development       is broken   down    on  the basis of its
phases. This    methodology for the development of the project is categorized into
```

#### Revised PDF page 29

```text
two parts   (the Hybrid Development Method) in which the earlier phases use the
Waterfall   Methodology       while  the   latter ones    use   Agile  approach.     There    are  6
phases in total in this WBS.

        The phases      include,   Planning,    Analysis, Design,      Implementation, Testing
and Evaluation, and Refinement.  In the Planning Phase, the authors will discuss
the  scope    of  the  project   and   its  purpose,    create   a  timetable    for  the  project,
specify  the location for the selected traffic incidence location in Tagum City, and
describe    the   various    traffic  instances.     The    phase    also   serves     to  lay   the
groundwork for      the development       phase by     clarifying the   goal of the project and
its content needs to conform to any traffic challenges that should occur during the
entire development of the system.

        The   Analysis    Phase    is about    understanding      the  traffic situation   and   the
requirements of the       system.   This involves     examining the various types of traffic
flow   behavior,    the   pedestrians’      movements       and    the   requirements      for   the
simulation and reinforcement learning components. The proponents also identify
the necessary functional and non-functional requirements of the system.

        The Design Phase is where the structure and models of the SMARTFLOW
system    are   prepared.     This   involves    the   design    of  the  system     architecture,
simulation   workflow, reinforcement learning framework, dashboard, and                     system
diagrams. These designs provide a guide to how the various components of the
system will interact during development and simulation execution.

        This   Implementation       Phase     of  the  project    consists   of  the   building   of
SMARTFLOW,           employing       the    iterative   process      through     its   simulation,
reinforcement learning, and dashboard. Both the simulation and the integration of
reinforcements      are   going    to   be   developed      and   improved      over    time.   The
proponents will     work on the     configuration of the      SUMO simulation process, the
modeling     of   vehicles    and    pedestrian      agents,     the   implementation       of   the
reinforcement     learning    based    on  Python     and   TraCI   communication,       etc.  This
phase will still concentrate on the implementation stages, as the system has not
```

#### Revised PDF page 30

```text
been launched yet. This part of the project is going to emphasize the preparation
of the core elements that will be necessary during the future tests. Every iteration
of the  Implementation Phase provides an opportunity                 to discover the     problems
and find ways to resolve them, thus improving SMARTFLOW.

        The   Testing   and   Evaluation     Phase    includes    the conducting of testing of
traffic and   road   constraints   for  assessing the     system performance.         The testing
will involve both fixed-time and SMART-based signal controls in order to measure
the effectiveness of the project, as well as evaluation of multiple metrics resulting
from the implementation process.

        The   Refinement      Stage concentrates       on  enhancing the       system based      on
the outcomes      of the testing and evaluation        processes. This involves debugging
problems    with   the  system, adjusting      the simulation parameters, and enhancing
the  performance      of the   reinforcement     learning   algorithm. The      stage concludes
with the finalization of the system's output and reports.

        In  conclusion,     the  Work     Breakdown      Structure    is  a  valid   plan   for the
development       of  SMARTFLOW           Traffic  System     since    it organizes     the   tasks
according to the particular purpose of the study.
```

#### Revised PDF page 31

```text
Figure 9. Work Breakdown Structure




Gantt Chart

        The   Gantt    chart  depicted    in Figure    10  illustrates  the  timeline   and   work
schedule of the SMARTFLOW Traffic System. The schedule conforms to both the
Hybrid Development Methodology and the Work Breakdown Structure adopted in
this study. The Gantt Chart begins with the four Waterfall phases (i.e., Planning,
Analysis, Design) and ends with the Agile phases of Implementation, Testing and
Evaluation, and Refinement.

        The Planning      Phase consists      of determining     the objectives and scope of
the  system    project,  establishing    the   time  and   resources     required,   selecting an
intersection   for  the  project,  and   determining     the  parameters of the       project and
constraints of the roadway under consideration. During the Analysis phase of this
project, problems of traffic flow, pedestrian flow, the needs of the system, and the
needs   of  reinforcement      learning   are  examined.     The    Design    phase    consists   of
creating    the    system      architecture,     simulation     process,     environment       with
reinforcement learning, dashboards, and models of the system.

        The   phases    of  Implementation,      Testing   and Evaluation, and Refinement
are  shown    as   overlapping,    sequential,    and   iterative  processes. Implementation
will involve creation    of  the SUMO       simulation   environment,      modeling of vehicles
and  pedestrians,     integration   of  Python,    TraCI   and   reinforcement      learning,   and
creation of   a dashboard      and   SQLite database.       Testing   and   Evaluation involves
running a number of test cases for road conditions, testing the two approaches of
traffic signal  control,  getting   traffic performance measures, making comparisons
of the results. Finally, Refinement will involve fixing bugs, changing the simulation
profile, enhancing the learning capability, and producing final outputs and reports.

        The   chart   shows    that   the  iterative  phases     will undergo    repeated     loops
based on the results of Testing and Evaluation and improvements in the system.
```

#### Revised PDF page 32

```text
This  is in  line  with  the  Agile aspect of the      methodology,      whereby    any problem
uncovered in Testing and Evaluation can either be dealt with through Refinement
or return   to  Implementation       for correction    or  enhancement.       The   chart   clearly
demonstrates       the   organizational     and    time    efficient  processes      involved     in
developing the SMARTFLOW Traffic System, while still adhering to the six major
phases of Work Breakdown Structure.





















                                    Figure 10. Gantt Chart



SYSTEM ANALYSIS

System Architecture

        A broad    overview of     the architecture of the SMARTFLOW Traffic System
is shown    in  the  Figure   11.  In fact,  the architecture     demonstrates the       nature of
how   all  components       of  the  system     will interact   with  each    other   to  perform,
analyze, and store information about traffic data in the system, using principles of
reinforcement     learning.   The    architecture    includes   the   following   six  layers:  the
User   Layer;   the  Simulation     Layer;   the  Control   and   Communication        Layer;   the
Intelligence Layer; the Database Layer; and the Outputs Layer.
```

#### Revised PDF page 33

```text
The User Layer consists of an authorized operator such as a researcher
or  a  CTTMO      employee,      who    will be   able   to  use   the  system     through    a  local
dashboard. The User Layer allows the operator to log in to the system, simulate
traffic scenario, set constraints on roads, select operating mode, start or stop the
simulation, monitor the traffic data in real time, and log out of the system.

        The    Simulation     Layer     uses    SUMO      technology      for  simulation     of  the
localized   traffic  environment       that  includes    the   simulation     of  roads,   vehicles,
pedestrians and road constraints. The major aspects covered by this layer are its
representation of     intersections and       lanes,  traffic signals, vehicle movements as
well as pedestrian crossings and impact of all possible events taking place at the
locality like lane closure, accidents, construction etc.

        The Control and Communication Layer is the communication link between
the  simulation    environment      and   the intelligent   decision-making layer.        The layer
uses Python and TraCI to collect real-time traffic data from SUMO and control its
execution.

        The   Intelligence Layer provides the          Reinforcement       Learning Engine part
which   was    implemented       using   PyTorch,     responsible     for observing     the  current
traffic situation,   deciding    signal   actions,    calculating    rewards,    and    learning   an
optimal policy for adaptive signal control. In addition, the aim of the Traffic Signal
Optimization     process     is  to  reduce     congestion,     waiting    time,   enhance     traffic
efficiency as well as prioritize emergency and pedestrian movement if necessary.

        The Database Layer has SQLite as a lightweight local database used for
storing   and   managing      the  system's     data.  Various    information     is stored   in  this
database     including     user   accounts,     traffic  scenarios,     road   limitations,    signal
control methods, running simulations, traffic indicators, and rewards output. This
makes it possible for the system to manage the local information without needing
a central database server or cloud information storage.
```

#### Revised PDF page 34

```text
The   Outputs     Layer    represents     the  actual   outputs    of  the  system     which
consist of real-time traffic data in the simulation, a queue length and waiting-time
analysis,   traffic  reports,   a  comparison      of  reinforcement     learning    to  static  time
signal   control   and    any   dashboard      visualizations.    The    user   can    analyze    the
efficiency   of  the  SMARTFLOW           system    for  varying    traffic conditions    and   road
limitations through the available outputs.

        In conclusion, the architecture demonstrates a combination of standalone
systems     centered     around     the   use    of  a   simulation     based    intelligent   traffic
management        system     where     scenarios     are   set   up   by   the   user,   the   traffic
simulation    is  run   using   SUMO,      communications        are   done    using   Python    and
TraCI, adaptive signal controls are defined by the reinforcement learning engine,
the  output    data    is stored    in  SQLite    and    the  reports    and   visualizations     are
provided using dashboard interface.
```

#### Revised PDF page 35

```text
Figure 11. System Architecture Diagram


Conceptual Framework

        In  Figure    12,   the   conceptual     framework      of  the   SMARTFLOW          Traffic
System is illustrated. The framework shows how the system obtains configuration
inputs    from    the   Authorized      Operator,     processes       this  configuration      input
information      through      a    SUMO-based           simulation      environment,        applies
reinforcement     learning-based       traffic signal   control,   and    generates     monitoring
results   and    performance       reports    using   a   local   dashboard.      Based     on   the
requirements     of  researchers     and   traffic management       personnel, the      framework
guarantees     that   the   system     can   facilitate  useful   tools   for  configuring    traffic
scenarios,    road    constraint    conditions,    running    simulations,     monitoring     traffic
behavior,    and    comparing      reinforcement       learning-based       signal   control    with
fixed-time traffic signal control.
















                             Figure 12. Conceptual Framework
Input
        The   Authorized     Operator    will  enter the   system’s    input   which involves all
configuration    settings   and   data.   The   input   includes   login   data,  traffic scenario
configuration data,     road constraint configuration         data, all simulation commands,
and control mode selection. For traffic configuration data, there is traffic density,
pedestrian     density,    and    emergency       vehicles'    status.    The    road    constraint
```

#### Revised PDF page 36

```text
configuration    includes    the   constraint   type,   severity   level,  and   the affected lane.
The system      also  receives simulation commands              such   as initialize, start, pause,
stop, reset, and reconfigure simulation. In addition, the operator will select either
fixed-time   traffic  control   or reinforcement learning-based           traffic  control.  Each    of
the inputs will be managed and stored through the local SQLite database before
execution.

Process
        In  the   beginning,     the  Authorized     Operator     logs   into  the  system     via  the
local  dashboard.      After   signing   in,  the  operator    sets   up  the   parameters      of the
traffic scenario     and    road    constraints.    Thus,    the   system     initiates  the   SUMO
simulation    environment       based    on   the   traffic density    configuration,     pedestrian
density,  emergency       vehicle status, type      of  constraint,   severity of    the constraint,
and lane    affected.   Now during      the simulation execution, the communication link
between     SUMO     and signal     control units    in  the system is     realized using Python
and TraCI. The system collects traffic data from SUMO simulation results (queue
length,   waiting time, number        of  vehicles, number       of pedestrians,      traffic density,
and signal    state).  If fixed-time control      is used,   the system      automatically utilizes
predefined signal timing to         construct a    baseline.    If RL-based control is applied,
the system evaluates current simulation traffic data, determines adequate signal
actions,    calculates    rewards,      and    revises    the   decision    regarding     signals    to
enhance     traffic  flow.  The   traffic  data,   signal   actions,   the  output    from   RL,   and
simulation logs are all saved in an SQLite database for further analysis.


Output
        The    system    generates     outputs    which include a      local interface that      gives
traffic monitoring     results   and   performance      report   based on the      simulated data.
The    output    will  be   able    to  indicate    details   about    simulation     status,    traffic
parameter, queue length, delay, throughput, congestion level, pedestrian activity,
service of emergency vehicles, the state of constraint on road, and signal states.
```

#### Revised PDF page 37

```text
The    output    is  also    able   to  provide     information     regarding     the   reports    on
performance       and    comparison       of  the    performance       of  the    model    with   the
reinforcement     learning    model    to  that  of  the  fixed-time    control   based    on  traffic
simulation.

Functional and Non-functional Requirements

        Functional    and   non-functional     requirements basically describe and define
the   required     functions     and    properties     of  the   system      expected      from   the
SMARTFLOW           Traffic   System.      Functional      requirements       address      the   core
functionalities   of  a  system    in  terms   of  traffic simulation    management        including
management        of  simulated    traffic  and   road   constraint    scenarios,    reinforcement
learning based operations of traffic signals, and effective performance evaluation
of  the  overall   system.     Non-functional      requirements      represent     the  operational
quality    based     on    certain    points    including     efficiency,    reliability,  usability,
maintainability, and adaptability as per ISO/IEC 25010 standards.


Functional Requirements

This system will have the following functions:

    1.  The system will allow the user to set factors involved in the traffic scenario
        such   as   the  traffic density,   pedestrian     density,   and status of     emergency
        vehicles.
    2.  The system will also enable the user to configure constraints for the road,
        as per the type of constraint, type of traffic regulation, and severity of that
        type of regulation.
    3.  The    system    will  simulate    the  traffic  using   SUMO      (Simulation     of  Urban
        Mobility).
    4.  The system will simulate the movements, as well as interactions between
        different vehicles and pedestrians.
```

#### Revised PDF page 38

```text
5.  The system      will also collect traffic data from the simulation and store it in
        the database while making use of Python programming language.
    6.  The   system     will make    use   of  reinforcement      learning   to maintain control
        signals.
    7.  The system      will be   able to get signals regarding the phases of the signal
        based on the       data  generated     from   the traffic simulation and will optimize
        traffic signals as per each situation.
    8.  The system will keep updating the traffic situation somewhere making use
        of the previous data regarding the reinforcement process.
    9.  The system will provide the user with all necessary information in the form
        of the system dashboard interface.
    10. The system will allow the user to start, pause, stop, modify, and reset the
        traffic simulation with the help of a dashboard interface.
    11. The   system     will save the    user   credentials, traffic data,     and   other   related
        information using SQLite (for database), along with an option to export the
        information into either a CSV or JSON file.
    12. Finally, the   system    will generate     final reports   based on the different data
        points    collected    from   the   traffic signal   optimization     and    reinforcement
        method.

Non-Functional Requirements

These are the system non-functional requirements:

    1.  Simulation scenarios should run and traffic data should be processed in a
        reasonable      time  given    the  complexity     of  the  chosen    scenario     and   road
        network.
    2.  Dashboard       should    be  clear   and   effective   enabling     authorized     users   to
        configure    different   scenarios,     run  the   simulations,    examine     results,   and
        download performance reports.
    3.  The system should be performing efficiently in simulating and it should log
        the  information     without   any   unexpected      loss of   information. The      system
```

#### Revised PDF page 39

```text
must    work   with  given    and   confirmed     traffic data   of  the  particular   road
        network.
    4.  The system      designed on      modular    basis; traffic data and traffic simulation
        can be modified as per need whenever required.
    5.  The system should support operating systems like SUMO, Python, TraCI,
        PyTorch, and local database.
    6.  The system must provide consistency as well as completeness in storage
        of traffic data and configuration.
    7.  Configuration      and    simulation     functionalities     must    be    secured     from
        unauthorized access and managed by authentication procedure.
    8.  It should provide a way to include new road and traffic simulation without
        any major redesign.
    9.  It is important    for  users   to  perform    all the  simulations     again   and   again
        without    changing     input   values;    users    would     be   able   to  make     valid
        comparisons.



Use Case Diagram

        The   use   case   diagram     presented    in  Figure   13   illustrates the interaction
between      an   primary     actor    and    the    SMARTFLOW           Traffic   System.      The
SMARTFLOW          Traffic System is a localized simulation-based traffic analysis and
decision-support      system     that   authorized     operators     access     to  create    traffic
scenarios    and   perform    testing  and   reinforcement      learning   algorithms    for  traffic
signal control.

        The primary actor identified in the system is the Authorized Operator, who
is responsible     for  the  configuration,    control,   monitoring,    and   evaluation    of  the
simulation environment from the           local dashboard interface. The dashboard also
serves   as   the   primary    method     of  access,    allowing    the  operator    to  manage
simulation     activities    and     analyze     how     traffic   behaves       under     different
configurations.
```

#### Revised PDF page 40

```text
Primary    use   cases    within   the  system     include   user   authentication,     traffic
scenario    configuration,     road   constraint    configuration,     simulation    management,
traffic monitoring     in  the   simulation,    and   system     performance       evaluation.    The
authentication     portion   of  the   system    allows    the  authorized     actor   to  enter   the
credentials that are managed locally to access the system.

        Traffic    scenario     configuration      enables      the   Authorized       Operator     to
configure    traffic  characteristics     by   setting   parameters      like  the   level  of  traffic
density,    pedestrian      density,    and    availability    of   emergency       vehicles.     The
subfunctionality     of  road   constraint    configuration     allows    the  operator    to  define
road   restrictions    by   stating   the   type   and   level   of  restriction.   These     defined
conditions help in shaping up the behavior of both vehicles and pedestrians and
in adjusting the simulated scenario of operation under MAP.

        When     the   simulation    process     starts,  the   system    starts  using    the  traffic
environment and executing the traffic conditions based on the selected mode of
operation in Reverse Engineers. The operator can select the fixed-time control or
reinforcement      learning    control.    In  case     of  the   reinforcement      control    mode
selection,    the  RE    will  provide    the  adaptive     signal   decisions     dynamically      for
efficient traffic flow and avoiding congestion.

        Via   the   dashboard       interface,    the   Authorized     Operator      is  capable     of
observing the traffic status and evaluating the system's operating characteristics
throughout     the  simulation.     The   outputs    of the   simulation    are  displayed     in  this
system, such as the lengths of the queues, average delay, traffic throughput, the
states   of  traffic  signals   and   congestion      levels,   and   pedestrian     behavior.    The
Authorized Operator can also activate, pause, stop, and reset the simulation.

        The    use   case   diagram     exhibits    how   authorized     users    interact  with   the
SMARTFLOW           Traffic   System      to  specify    traffic  conditions,     manage       driving
conditions, operate the execution of the simulation, observe traffic behavior, and
evaluate    the effectiveness      of reinforcement      learning–based       traffic light planning
as opposed to fixed-time planning in the simulation.
```

#### Revised PDF page 41

```text
Figure 13. Use Case Diagram
```

#### Revised PDF page 42

```text
Context Flow Diagram

        The   Context    Flow    Diagram     as  illustrated  in  Figure   14   shows the     whole
approach of SMARTFLOW Traffic System                   and  how    it interacts  with  the outside
entity   and    transfer    information      through     simulation-based        environment.       It
highlights   how   the   logical  flow of system inputs       and   outputs without      going into
internal details of the system.

        The   important    external    entity  in this diagram     is the   Authorized    Operator
that includes all those who might include, people doing                 research, traffic control
personnel and CTTMO employees. The Authorized operator provides input to the
system    in  terms    of  login   details,  traffic  environment      settings,    road   settings,
simulation    commands        and    fixed   or  reinforcement      control   modes.The        traffic
scenario    settings   include   inputs   like  traffic density,   pedestrian    density   and    the
status   of  emergency      vehicle;   whereas,     the   road   settings   contain    the  type   of
constraint,   severity    level  and    lane   details.  Based     on  the   settings   mentioned
above, the system is enabled to initialize through simulation mode accordingly.

        The SMARTFLOW Traffic             System     processes the provided data via traffic
simulation,    vehicle    and    pedestrian      movement       simulation,     road    constraints
implementation, and signal control based on the chosen control mode. In case of
reinforcement     learning    mode,     the  system     uses    the  trained    RL   controller   for
determining     the  adaptive    signal   actions   while   in  case   of  fixed-time   mode;     the
defined traffic signal timing is used in the system for the baseline comparison.

        On   the   constant    and    interactive   dashboard       interface,   the  key   outputs
generated by      the system for the Authorized Operator include real-time vehicular
metrics and status, signals statuses, queue lengths, delays, throughput, and any
congestion levels across the operational layout along with pedestrians’ activities.
Thus,    the    presented      results    may    facilitate   making      an   assessment        and
comparison      of  a  learning-based       adaptive    traffic signal   control   approach     with
```

#### Revised PDF page 43

```text
fixed-time   traffic signal   control   based    on  the various     operational configurations
and vehicle flows of the road environment.

        As seen in the      figure, there are also other important flows of data which
are  user    input,  traffic  scenarios     configuration,    road    constraints    configuration,
simulation commands, traffic performances metrics, and reports generation that
give an overview of how the SMARTFLOW system processes the incoming input
data  and   converts     it into outputs    that play an important role in traffic analysis,
decision making and simulation based evaluation.




















                     Figure 14. Context flow diagram of the system.



Data Flow Diagram

        The Data Flow Diagram           illustrated   in Figure 15 places the system in five
different   conceptual     processes,      namely     User    Account     Authentication,     Traffic
Scenario    and   Road     Constraint    Configuration,     Simulation     and   Data   Collection,
```

#### Revised PDF page 44

```text
Signal   Control    Processing,     and   Monitoring     and   Reporting.     The   main    external
entity interacting with the      system    would    be the   Authorized     Operator,    which can
be  either  a researcher or      CTTMO personnel. The            Authorized Operator will give
the login credentials to access the system in addition to providing configurations
relating  to traffic scenarios, road      constraints, simulation commands, and control
modes.

        The   User    Account     Authentication     process     verifies  the  login  information
provided    by  the   Authorized     Operator     by  sending     a  user   query   to  the  SQLite
database     and    retrieving   user    account    records.    After   checking     for  the   login
credentials,    the  system     will  only  allow    access    to  the   system    for  authorized
personnel making the process very secure.

        After   gaining    authorization,    the   process    of   Traffic  Scenario     and   Road
Constraint Configuration has been carried out for the management of the inputs
of traffic scenarios and road constraint by the Authorized Operator. In the Traffic
scenario    configuration    the  various    configurations     such   as density of     traffic, the
density of pedestrians and the state of emergency vehicles have been made. On
the  other   hand   the  configuration     of  the  road   constraint deals     with the   types of
constraints,   severity   level   of the  enforcement      and lane     affected.  The scenarios
configurations     and   the   road   constraints     configured     are  saved     in the   SQLite
database and the saved scenarios can be retrieved from the database in order to
carry out the required simulation.

        The Simulation and data collection process gets the commands regarding
simulation execution from the Authorized Operator and there are various types of
commands       executed     regarding    simulation    execution    such as     starting, pausing,
stopping, resetting and running of simulation. This process helps in retrieving the
Traffic scenario configurations, road constraint configurations and the simulation
parameters from SQLite database. Based on these catalogues the SUMO based
traffic simulation is    executed and      traffic information such as        pedestrian    activity,
vehicle   count,   queue    length,   waiting    time   traffic density    and   flow  of  traffic  is
```

#### Revised PDF page 45

```text
collected.   The    information    collected    is  saved    again    in  the  database     for  its
processing purposes.

        The   Clearing    Process     refers   to  the   Handling    of  identified   or  reported
deficiencies    in Light   Emitting   Diode    (LED)    technology     on   the  Airport  Surface
Detection    Equipment      Model    3  (ASDE-3)      System.     The   Deficiency    Processing
System provides       a process    flow with these actions and associated text through
Structured     Query    Language       (SQL)    programming        commands.       This   process
provides    the  ability  to monitor,    record,   edit, and   manage      deficiencies    through
updating the accounting activity in the deferral and reporting processes.

        The   Deficiency    Processing System        captures    the process flow, with each
deficiency being received from the airport through SQL programming commands.
The   process    then  identifies   the  deficiency   through the action       taken which     may
include   reviewing    the   database    for  the   last time   the   deficiency   was    reported
through    creating    an   entry   in  the  Deficiency     Processing      Database     via   SQL
programming commands.

        A  majority   of  the  deficiencies    reported    to the FAA     involves   the ASDE-3
systems    receiving    units  where    information     is required    to  validate   and  quickly
identify  the   deficiency.   It also   provides    the   ability  to  record   the   data   which
enables    quick   validation    as  well   as  allows    for  internal  and    external   reports
through the use of the SQL programming commands.
```

#### Revised PDF page 46

```text
Figure 15. Data flow diagram of the system.



SYSTEM DESIGN

Entity Relationship Diagram
        The   Entity   Relationship     Diagram      represented     in  Figure    16  shows     the
database structure of the SMARTFLOW Traffic System with SQLite being utilized
as  a   light  weight    database     for  local   systems.    Being    a   localized   simulation
platform, SQLite is selected for the storage and management of vital system data
without   the   use    of  centralized     databases      or  cloud   storage.    The    database
provides    organization     for  user   credentials,    traffic scenarios,    road   constraints,
signal  durations,    simulation    runs,  traffic  data,  reinforcement     learning data,     and
reports.

        The   User   Accounts     entity  has   login  credentials    for  users   accessing the
system\'s dashboard. Since the system is a localized prototype, it does not have
role based    access control      at this time, and     so the account will only be used for
```

#### Revised PDF page 47

```text
authentication     purposes.     The    Traffic   Scenarios     entity   has   the   default   traffic
conditions including normal traffic, heavy traffic, pedestrian heavy conditions and
emergency      situations.   The    Road    Constraints     entity  has   the   disruption    values
including   lane closure, road      works, accidents, and pedestrian congestion which
can be used in experimental runs.

        An   entity   known     as  Signal    Control    Modes     indicates    how    control   was
applied   in  each    simulation    run  such    as  dependent      signal   control   or  adaptive
control  utilizing  reinforcement      learning.   The   Simulation     Runs entity acts      as the
main table of the database in order to keep track of the details of each simulation
that  has taken place      and   the various     parameters that are selected          by the   user
along   with   the   highway     condition     and   mode     of  control    of  the   signal.   Key
information    regarding     each   simulation    including    the  commencement          time,  end
time, and current status of execution is included in this entity.

        The    Traffic  Metrics    entity  has    the  role   to  record   the   summary      of  the
outcomes of the       simulations    performed. For example queue length, throughput,
waiting  time, traffic density, and signal efficiency are made available here. Since
there is only once outcome generated for each simulation in which traffic metrics
is derived,   there   is a  one-to-one relationship between the above mentioned two
entities.  The    Performance       Reports     are   designed      to  store   the   summary      of
performance results based on the execution of each simulation run. Again, there
is only one performance report generated from each simulation run thus entailing
a one-to-one     relationship. At    the same time, RL Outputs of the             entity will  store
information relating to various aspects of the model including traffic state, reward
value, signal    operations made,       and timestamps        which can result      in multiple RL
outputs being produced in one simulation run only.

        The    relationships      between      the   entities    of  the    system     have    been
established by     making use of Crow’s Foot Notation. Under this framework, one
user  account can be       associated     with several     simulations while      each simulation
account will    refer to only one user account. Likewise, each traffic scenario, road
```

#### Revised PDF page 48

```text
restriction,  and   signal   control  mode     can   appear    in several    simulation runs but
each   simulation    run   will refer   to only   one   selection    from   each    of the   above.
Through    a  singular   simulation,    traffic metric   and   RL   outputs    can   be  produced
providing possibilities for generating performance reports.

        Thus    the  ERD    identifies  the   way in   which SMARTFLOW integrates               and
organizes    its  data   for  performing     simulations,    carrying    out  the   reinforcement
learning process, and conducting           performance evaluations. The structure of the
database allows the SMARTFLOW program to be able to store data on execution
of simulations     in the  local  database     and   keep    record files   maintained properly
and   execute    comparison      between     the   use   of  adaptive    control  and   fixed   time
traffic control modes.





















                          Figure 16. Entity Relationship Diagram
```

#### Revised PDF page 49

```text
Data Dictionary
        The   SMARTFLOW          Traffic  System     Data   Dictionary    gives   an  extensive
overview of the elements of data that make up the SQLite local database used in
the system. This aids in comprehending how both the storage and arrangement
of data occur while using functions such as user authentication, configuring traffic
scenarios,    managing      road   constraints,    performing     simulations,     tracking   the
output from reinforcement learning, and generating performance reports.

        The   database    is made up of many tables some of which               include   Users,
Traffic Scenarios,     Road    Constraints,    Signal   Control   Modes,    Simulation     Runs,
Traffic Metrics, RL Outputs, and Performance Reports. Each of these tables has
columns or    fields that signify the    specific type of data a given table contains as
well  as  its necessary     conditions    and   descriptions   for  effective  data   entry  and
retrieval related to the simulation.


Table 2. User


    Field        Data Type       Length       Constraints                Description
    Name

 accuont_i      INTEGER         -           PRIMARY              Unique identifier for each
 d                                          KEY                  authorized user

 username       TEXT            50          UNIQUE,      NOT     Username      used   for  local
                                            NULL                 system login

 password       TEXT            255         NOT NULL             Password         used       for
                                                                 authentication

 date_creat     DATETIME        -           NOT NULL             Date    and   time   the  user
 ed                                                              record was created
```

#### Revised PDF page 50

```text
Table 3. Traffic Scenarios


    Field       Data Type       Length       Constraints                Description
   Name

 scenario_i     INTEGER         -          PRIMARY KEY          Unique    identifier for each
 d                                                              traffic scenario

 scenario_      TEXT            100        NOT NULL             Name       of    the    traffic
 name                                                           scenario

 traffic_den    TEXT            30         NOT NULL             Traffic               density
 sity                                                           classification     such     as
                                                                normal or heavy

 pedestrian     TEXT            30         NOT NULL             Level      of     pedestrian
 _demand                                                        activity in the simulation

 emergenc       TEXT            30         NULL                 Indicates     presence      of
 y_conditio                                                     emergency             vehicle
 n                                                              conditions

 descriptio     TEXT            255        NULL                 Additional    description    of
 n                                                              the scenario


Table 4. Road  Constraints

    Field       Data Type       Length       Constraints                Description
   Name

 constraint    INTEGER          -          PRIMARY              Unique identifier for each
 _id                                       KEY                  road constraint
```

#### Revised PDF page 51

```text
constraint    TEXT             50         NOT NULL             Type    of  road   constraint
 _type                                                          such   as   lane  closure   or
                                                                accident

 affected_l    TEXT             50         NOT NULL             Lane     or   road    section
 ane                                                            affected by the constraint

 severity_l    TEXT             20         NOT NULL             Severity    classification   of
 evel                                                           the constraint

 status        TEXT             20         NOT NULL             Current status of the road
                                                                constraint

 descriptio    TEXT             255        NULL                 Additional             details
 n                                                              regarding the constraint



Table 5. Signal Control Modes


    Field       Data Type       Length       Constraints                Description
   Name

 control_m     INTEGER          -          PRIMARY              Unique    identifier for each
 ode_id                                    KEY                  control mode

 mode_na       TEXT             50         NOT NULL             Name of the signal control
 me                                                             mode

 fixed_time    INTEGER          -          NULL                 Preset   signal  duration   for
 _duration                                                      fixed-time control

 rl_model_     TEXT             100        NULL                 Name    or  identifier  of the
 used                                                           RL model used

 descriptio    TEXT             255        NULL                 Additional        information
 n                                                              about the control mode
```

#### Revised PDF page 52

```text
Table 6. Simulation Runs

    Field       Data Type       Length      Constraints               Description
   Name

 run_id        INTEGER          -          PRIMARY            Unique    identifier for each
                                           KEY                simulation run

 account_i     INTEGER          -          FOREIGN            Reference          to      the
 d                                         KEY                authorized user

 scenario_i    INTEGER          -          FOREIGN            Reference to the selected
 d                                         KEY                traffic scenario

 constraint    INTEGER          -          FOREIGN            Reference     to the  applied
 _id                                       KEY                road constraint

 control_m     INTEGER          -          FOREIGN            Reference to the selected
 ode_id                                    KEY                signal control mode

 start_time    DATETIME         -          NOT NULL           Simulation                start
                                                              timestamp

 end_time      DATETIME         -          NULL               Simulation end timestamp

 simulation    TEXT             30         NOT NULL           Current     status    of   the
 _status                                                      simulation



Table 7. Traffic Metrics


    Field       Data Type       Length      Constraints               Description
   Name

 metric_id     INTEGER          -          PRIMARY            Unique identifier for traffic
                                           KEY                metric data
```

#### Revised PDF page 53

```text
run_id        INTEGER          -           FOREIGN            Reference         to       the
                                            KEY                simulation run

 queue_len     REAL             -           NOT NULL           Measured     vehicle   queue
 gth                                                           length

 waiting_ti    REAL             -           NOT NULL           Average      waiting      time
 me                                                            during simulation

 throughpu     REAL             -           NOT NULL           Number        of     vehicles
 t                                                             passing      through       the
                                                               intersection

 pedestrian    REAL             -           NULL               Delay     experienced       by
 _delay                                                        pedestrians

 traffic_den   REAL             -           NULL               Measured traffic density
 sity

 signal_effi   REAL             -           NULL               Efficiency  score   of  signal
 ciency                                                        control



Table 8. RL Outputs


    Field        Data Type      Length       Constraints               Description
   Name

 output_id      INTEGER         -           PRIMARY           Unique     identifier  for   RL
                                            KEY               output data

 run_id         INTEGER         -           FOREIGN           Reference          to       the
                                            KEY               simulation run
```

#### Revised PDF page 54

```text
state_data    TEXT             500        NOT NULL          Encoded        traffic    state
                                                             information

 selected_     TEXT             100        NOT NULL          Traffic     signal       action
 action                                                      selected by the RL model

 reward_va     REAL             -          NOT NULL          Reward     value    generated
 lue                                                         during RL processing

 timestamp     DATETIME         -          NOT NULL          Date    and    time   the   RL
                                                             action was generated



Table 9. Performance Reports


    Field       Data Type       Length      Constraints              Description
    Name

 report_id      INTEGER        -           PRIMARY           Unique    identifier for each
                                           KEY               performance report

 run_id         INTEGER        -           FOREIGN           Reference          to      the
                                           KEY               simulation run

 summary_       TEXT           1000        NOT NULL          Summary       of   simulation
 result                                                      performance results

 compariso      TEXT           1000        NULL              Comparison           between
 n_result                                                    fixed-time   and    RL-based
                                                             dual control

 generated      TEXT           100         NULL              User     or   process     that
 _by                                                         generated the report
```

#### Revised PDF page 55

```text
date_gene       DATETIME         -            NOT NULL            Date   and    time  the   report
 rated                                                             was generated



Technologies, Concepts, and Theories

        In   this   section,     the   essential     models,      algorithms,     concepts,      and
technologies     employed     in the development        of the SMARTFLOW Traffic System
are   discussed.     The    manner      in  which    traffic  simulation     data    is  produced,
processed, analyzed, and what is the use of this information for optimizing traffic
signals.

Data Collection

        Data    collection   in  SMARTFLOW           takes   place    in the   SUMO      simulation
environment.     This means that       SMARTFLOW does not rely on live CCTV feeds,
IoT sensors, or GPS devices, instead, it collects data related to traffic generated
during   simulation     runs.   The    available    information    consists    of  vehicle    count,
pedestrian     count,   queue     length,   waiting    time,   traffic  density,   traffic  volume,
pedestrian    delay,   presence      of  emergency       vehicles,   and    traffic signal   status.
Using   TraCI,   the  simulation     values   are  accessed in real-time        from   Python    and
sent to the control and decision-making parts of the system.

Data Pre-Processing

        Before    the training data is fed into the reinforcement learning controller, it
is pre-processed      first. The  main goal of the pre-processing is to make sure that
the data is formatted according to the required specifications, organized properly,
and is ready for analysis and evaluation.

Feature Extraction

        The process of feature extraction is essentially that of identifying the most
relevant attributes of the traffic that will be used in the decision to control signals.
```

#### Revised PDF page 56

```text
The features selected        in SMARTFLOW may include queue length in each lane,
average    wait  time,   vehicle   density, number       of pedestrians, emergency vehicles,
signal   phase,    and    road    fall-back   status    meaning      the   attributes   in  question
correspond      to   the    current     traffic  situation    at   the    simulated     intersection
representing the input state for the reinforcement learning model.

Reinforcement Learning-Based Decision-Making

        The    Decision-Making        process     at  the   SMARTFLOW           Traffic   System     is
conducted      using    Reinforcement       Learning     for  the   adaptive     control    of  traffic
signals. In   SMARTFLOW,          the learning     agent   is the  traffic  signal  control system
and   the   traffic environment       is represented      by   the  simulated     system     allowing
observations of traffic situations and corresponding signal actions through TraCI.

        The agent will monitor the current state of traffic in the intersection such as
queue    length,   number     of  vehicles,   average     time   of  waiting,   traffic density,   the
need for pedestrians, presence of emergency vehicles, the state of the road and
current    phase    of   the   signal    at  the   intersection.     After   observing     all  these
characteristics, the     agent   will decide what      action has     to be taken regarding the
signals e.g. whether to shift to the next appropriate phase or for instance, prolong
or shorten the current phase according to the traffic situation at hand.

        It is important to note that instead of a fixed timing of the signals, the agent
will learn  from various      traffic situations and find out       whether its own action has
improved traffic conditions. Significant aspects of traffic performance observed by
the  agent    include    waiting    time   of  vehicles,    length   of  the   queue,     amount     of
pedestrian traffic, traffic flow and priority of emergency vehicles.

        Reinforcement       learning    is done using      simulated data instead        of  any   live
data such as CCTV, GPS, or physical sensors. Each simulation is regarded as a
separate      episode      thus     providing      different     conditions      regarding      traffic
characteristics in order to       evaluate whether the action results in improved traffic
conditions or not.
```

#### Revised PDF page 57

```text
In   SMARTFLOW,          input    traffic  characteristics     are    generated     during
simulations    and   then   transferred    through    TraCI   so   that  the  agent   can   decide
upon a    corresponding action and results from the previous actions may support
better decision making in the future.

        In  the  present   study,   the  reinforcement     learning-based approach          will be
validated    by   means     of  comparing      results    with   a  fixed-time    signal    control
approach     so  that  further  improvements       such   as   shorter   waiting   times,  shorter
queues,    better   efficiency    and   priority  for  emergency       vehicles,   etc.,  may    be
achieved.



Technologies Used in the System

Simulation of Urban Mobility (SUMO)

        The    system    utilizes  mainly    Simulation     of  Urban    Mobility   (SUMO),      an
open-source      platform   for  traffic simulation    that  allows   for  roadway     designs    to
support    simulation     of  traffic  flows    in  vehicular    movement       and    pedestrian
activities. It  serves   as   the  main    simulation    environment     of  the  SMARTFLOW
system,   thus   providing    the  developers     of SMARTFLOW with            an  opportunity    to
design   realistic  traffic conditions,    street   constraint   conditions,    and   traffic flows
within the intersection of Tagum City under study. Because of SUMO, the current
system    can   simulate    several   traffic densities,   pedestrian    activities,  emergency
vehicle   response,    traffic  congestion     during   road   closures,    among     many    other
things.
```

#### Revised PDF page 58

```text
Figure 17. Simulation of Urban Mobility (SUMO)

Reinforcement Learning (RL)

        Because      it enables     adaptive     traffic signal    optimization,    the   system
employs    Reinforcement      Learning    (RL)   as  part  of  its technique. Due to the       RL
technique, the system can determine the traffic signal control mechanism through
continued    interaction   with  the  simulation    system.    The   RL   model   observes     the
traffic conditions,   executes     the  control   strategy   and   receives    a  reward.    As  a
result, the modelling methodology helps improve the decision-making capabilities
of the SMARTFLOW system.
```

#### Revised PDF page 59

```text
Figure 18. Reinforcement Learning (RL)

Python and TraCI

        Python serves as the programming language that connects the simulation
environment      with   the   reinforcement      learning   model     through    the   dashboard
functionality   and   databases     of  the  simulation    system.    Because     of  its modular
nature,  it provides   an   organized way      of developing and integrating the          parts of
the  system.    An  extremely     important    Python    module for traffic simulation       is the
Traffic Control    Interface   (TraCI), which     enables software      access    to the running
simulation    in  SUMO      and   provides    Python    software     modules     with  the   traffic
control command.
```

#### Revised PDF page 60

```text
Figure 19. Python and TraCl

PyTorch

        The Deep      Q-Network     (DQN) model       to  be  implemented in SMARTFLOW
Traffic System’s reinforcement learning module will use PyTorch as the software
framework.    PyTorch     is well-acclaimed     for  its optimized    tensor   manipulation and
deep    learning     advantages       that   are   essential    for   the   training    of  neural
network-based        models      on    both    CPUs      and    GPUs.      Its   applicability    in
SMARTFLOW          Traffic  System     comes     from   its  utilization  in constructing     DQN
model    implementation      that   estimates    optimal    traffic signal   operation    from   all
attributes  concerning the present state of simulation which may comprise, but is
not limited   to queue    length, waiting time, traffic density, pedestrian requirement,
presence of emergency vehicle, and road conditions. It will also play a key role in
training the model through simulation experiences generated in SUMO episodes,
the calculation of training loss, and adjustment of model parameters for improved
adaptive traffic signal decision-making.
```

#### Revised PDF page 61

```text
Figure 20. PyTorch




Database Management System

        To   handle    data   in  SMARTFLOW           Traffic  System,    the   users   can    take
advantage     of SQLite    as  the DBMS       for storing and organizing user data,          traffic
cases, road constraints, simulation results, reinforcement learning outcomes, and
performance     reports in order to allow ease of retrieval of all relevant information
as  pertains   simulation    of  such    processes.    The    database     can   also  store  data
locally  without   the   need    for  internet   connection     or  the  use    of a  centralized
database server to make the system to be lightweight and reliable.
```

#### Revised PDF page 62

```text
Figure 21. Database Management System (DBMS)


SYSTEM TESTING AND IMPLEMENTATION

        The    System      Testing    and   Implementation        phase    is   concerned      with
confirming    the   operational    efficiency   of  the   SMARTFLOW          Traffic  System     by
validating    the   system     requirements      to   be   met.   In   this  phase,     extensive
examination of     the entire program       will be performed      to ascertain that the major
components      of  the  system     are  successfully     integrated   into  one   another.   This
integration   process    unfolds   as  a  testing  process    where the     first examination     is
undertaken to check how well           each   part of  the SMARTFLOW           system performs
through   various    metrics   applicable    to  the  system.     One   of  the  key  aspects    of
testing revolves around matching the system specifications regarding the waiting
time,  the  number     of  vehicles    queued    up,   traffic density,  and   efficiency   of  the
traffic control signals.

        Thus,    the   system    will  undergo      unit  testing,   integration    testing,   and
scenario-application      testing  so  as  to be   assured of     the successful operation of
the  connection.     The   test  cases    will be  developed      in a  manner     that  they   will
enable the    simulation    of both regular and disruptive transport modes in order to
```

#### Revised PDF page 63

```text
check whether the system will be able to interpret, process, and produce relevant
data in a stable manner.

        Apart from functional testing, the RL-based traffic signal controller will also
be subjected to tests conducted by using the RL-related performance indicators,
like reward, rate of convergence, stability of the policy, average waiting time, the
length of the queue, etc. These measurements will be taken into account in order
to  assess    how    efficiently  and    effectively   the  model     with  RL    algorithms    can
process the traffic signal requests and establish proper control over the vehicles
and different mobile devices.

        A testing results summary presented in tabular format shows the operating
status  and    performance      of  each   major    component,      such   as  traffic simulation,
reinforcement      learning   process,     signal   control   operations,    database      storage,
dashboards, and report performances. This will enable the proponents to monitor
issues   and   ensure     that  the  functions    of  the  SMARTFLOW           system    meet    the
required operational standards.

         In order to facilitate the validations process, a System Test Plan should be
drafted  that  defines the    goals, scope, environment, test cases, procedures, and
acceptance criteria for testing. This enables testing to take place in an organized,
orderly,    and     systematic      fashion     according      to    defined     functional     and
non-functional requirements.

        The   implementation       phase     occurs    when    the  SMARTFLOW           system     is
deployed    in  simulated    desktop    local environment. The implementation includes
configuring    the SUMO platform,        establishing    Python and      TraCI communication,
developing the reinforcement learning algorithm, setting up SQLite database, and
building   the  local  dashboard.     The SMARTFLOW            system will    be used by      users
and   pre-authorized     traffic managers      for testing   out traffic scenarios before real
implementation.       The    SMARTFLOW           system     performs     the   functions    of   the
Reinforcement      Learning     based    traffic signal   controller   for validation   purposes.
Further   validations   will  be  conducted     to  ensure that the      SMARTFLOW          system
```

#### Revised PDF page 64

```text
performs    in  the   prescribed     environment.      Additionally,   some    persons     will  be
trained on how to      use the    simulation dashboard        and  traffic analysis   features of
SMARTFLOW system.

        In   conclusion,     After   simulation,     the   SMARTFLOW           system     will   be
monitored    and   evaluated     for  its efficiency   in  order  to  improve    adaptive    traffic
signal optimization system further.


SYSTEM MAINTENANCE

     The System Maintenance            phase is   concerned with       the maintenance       of the
SMARTFLOW          Traffic  System     after  its deployment.      The   System     Maintenance
phase    involves   the  observation     of the   performance      of the  system,    diagnosing
malfunctions    in  the  system,    and   implementing     required    modifications    based on
detected faults that will improve the functional accuracy of the simulation as well
as the   reinforcement     learning quality in the system and enhance the usability of
the application.

        Some     of the   maintenance      tasks   include   periodic   checks    on  the  SUMO
simulator,   upgrades      to  the   Python    and   reinforcement      learning    components,
improvements to the road constraints and traffic scenario setups, enhancements
of the   graphical   user   interface   and    influence   over   the  SQLite    database.     The
implementers       may     modify     the   simulation     parameters       and    optimize     the
reinforcement learning behavior based on test results and users’ responses.

        In addition to that, constant monitoring of the           traffic simulation results as
well as  the behavior     of  the adaptive signal      control may     continue to ensure that
future improvements will be possible and the number of possible traffic scenarios
can be increased.
```

#### Revised PDF page 65

```text
System Security Plan

          In order to protect the data in the system and resources associated with
the simulation, an implementation process has to go through an application of a
System     Security    Plan   for  the   SMARTFLOW           Traffic  System.     The    approach
adopted    in this system shall     ensure user authentication and role-based control.
The security requirement protects unauthorized access to the system dashboard,
database,    and   the  system    configuration.     The   functionality of the    system    exists
locally; therefore,    simulation    data,  results   of reinforcement      learning   as  well as
configuration data are both owned locally.

          The   system uses secure communication method and secure processing
that  is  enhanced       by  stable    communication       between      the  SUMO       simulation
environment, the communication medium associated with Python-TraCI, features
of reinforcement     learning, an    SQLite database that helps reduce vulnerability of
the   components       in  the   system.     The   aspects     of  input   validation    shall   be
implemented into the       system    to ensure    proper operation and protection against
malicious inputs and scripts.

          System    Security Plan     provided    in Table IV    implements     ISO/IEC 27001-
security   practices,    which     will  allow   protecting     confidentiality,   integrity,  and
availability  of data   in  SMARTFLOW          Traffic  system.    The   characterized security
controls   will   provide    for  secure     system    operations,     reliable   processing      of
simulation    results,  as   well   as  secure    management        of  reinforcement     learning
outputs.



Table 10. System Security Plan



 Security Domain (ISO             Control Area           Description / Implementation in
           27001)                                                     the System
```

#### Revised PDF page 66

```text
A.5           Information      Security Policy         The system will implement security
 Security Policies                                      policies for user access, simulation
                                                        control, and local data protection.



 A.6    Organization       of   Roles           and     Roles     such     as     Administrator,
 Information Security           Responsibilities        Researcher,         and      Authorized
                                                        Operator will    have   defined system
                                                        privileges.



 A.9 Access Control             User        Access      The system will enforce role-based
                                Management              access     control   (RBAC)      through
                                                        secured login credentials.



 A.9 Access Control             Authentication          Username           and         password
                                Mechanism               authentication will be implemented
                                                        to restrict unauthorized access.



 A.10 Cryptography              Data Protection         Local      simulation       data      and
                                                        exported     files  will  be   protected
                                                        through      secure      storage      and
                                                        backup mechanisms.



 A.12           Operations      Data   Processing       Input  validation and error handling
 Security                       Integrity               will    ensure       accurate       traffic
                                                        simulation    processing     and   stable
                                                        system operation.
```

#### Revised PDF page 67

```text
A.12          Operations      Logging          and    The   system     will maintain    logs  of
 Security                      Monitoring              simulation    activities, user   actions,
                                                       and   system    events   for  monitoring
                                                       and troubleshooting.



 A.13   Communications         Secure                  Communication        between      SUMO,
 Security                      Communication           Python,    TraCI,   and   reinforcement
                                                       learning    components       will   follow
                                                       secure processing practices.



 A.11     Physical      and    Device                  Desktop devices and local storage
 Environmental                 Protection              used   for  simulation    execution    will
 Security                                              be    secured     from     unauthorized
                                                       physical access.



 A.17          Information     Data        Backup      Regular       backup       of     SQLite
 Security     Aspects      of  and Recovery            databases     and   simulation    reports
 Business Continuity                                   will be   performed     to ensure    data
                                                       recovery.



 A.16          Information     Incident                Procedures will     be established     for
 Security          Incident    Response                detecting, reporting,     and  resolving
 Management                                            system    errors   or   security-related
                                                       issues.
```

#### Revised PDF page 68

```text
A.14               System     Secure                  Secure         coding          practices,
 Acquisition,                  Development             debugging,     and    system     updates
 Development,           and                            will    be      applied      throughout
 Maintenance                                           development and maintenance.






System Maintenance Plan

        A   System    Maintenance      Program     is to  be  developed     to ensure    that  the
continued operation, advancement, and sustainability of the SMARTFLOW Traffic
System will    be attained    once it has been implemented and running. Included in
this  program     are  scheduled      maintenance      operations     that  involve   simulation
optimization,    reinforcement      learning    model    improvements,       SQLite    database
maintenance,      dashboard     enhancements,        and   performance      monitoring     of  the
system.    Implementation       of  troubleshooting,     debugging,      and   error   correction
protocols   will also  be   done   to  attain  the  continuous    stable performance       of the
simulation.

     In addition,   system    documentation will      be continued to be updated to show
necessary    information    regarding    configuration    changes,     reinforcement     learning
change,    simulation   updates,    and   the  performed     maintenance.      This  will ensure
that the  SMARTFLOW          system    can   be  enhanced      more   easily   in the  future for
various traffic scenarios and intelligent transportation studies.

      The System Maintenance           Plan  shown in Table      11 is  developed     to  link the
maintenance operations        to  the ISO/IEC 25010 software          quality attributes which
ensure that the SMARTFLOW Traffic System will continue to be reliable, efficient,
maintainable, secure, and flexible.

Table 11. System Maintenance Plan
```

#### Revised PDF page 69

```text
ISO 25010           Maintenance                   Description                Frequency
    Attribute              Activity



 Reliability          System                 Monitoring           simulation     Continuous
                      Monitoring             execution,    system    stability,
                                             and dashboard operation



 Performance          Performance            Improving            simulation     Regularly
 Efficiency           Optimization           processing       speed       and
                                             reinforcement           learning
                                             performance



 Usability            Dashboard              Updating    dashboard     layout    As Needed
                      Improvement            and controls based on user
                                             feedback



 Security             Security Updates       Applying    system     updates,     Periodically
                                             access                   control
                                             improvements,                and
                                             database                 backup
                                             procedures



 Maintainability      Debugging       and    Correcting        bugs       and    Regularly
                      Code                   improving    system    structure
                      Refactoring            for easier maintenance
```

#### Revised PDF page 70

```text
Compatibility         System Updates         Ensuring     compatibility    with   As Needed
                                              SUMO,       Python,     PyTorch,
                                              and desktop environments



 Reliability           Simulation             Adjusting     traffic simulation     Periodically
                       Calibration            parameters                    and
                                              reinforcement            learning
                                              configurations



 Performance           Database               Managing      SQLite database        Monthly
 Efficiency            Optimization           cleanup,       indexing,      and
                                              report storage optimization
```

### Revised references

#### Revised PDF page 71

```text
REFERENCES:

[1]  Injac,   Z.,  Arsić,    S.,  Drašković,      D.,   &   Arsić,   M.   (2025).    Urban     traffic
        management         using    artificial  intelligence:    A   sustainable     approach      to
        enhancing      urban   mobility.   Journal    of  Traffic  and   Transport     Theory    and
        Practice (JTTTP), 10(1), 30-35.

[2] Akinade,     A.O.,   Adepoju,     P.A.,   &  Ige,   A.B.   Artificial Intelligence    in  Traffic
        Management: A Review of Smart Solutions and Urban Impact.

 [3] Rathore,   S.  P. S.,  Farhaoui, Y., Aniebonam, E. E.,           Nagpal, T., & Kaushik, P.
        (2025,    March).    AI-driven     traffic congestion      management:        a  predictive
        analytics approach for smart cities. In 2025 IEEE International Conference
        on Interdisciplinary Approaches in Technology and Management for Social
        Innovation (IATMSI) (Vol. 3, pp. 1-6). IEEE.

[4]   S.  Rudhra,    S.   Vinod,   P.  Arthi  and   L.  Kurinjimalar,    "Density    Based    Traffic
        Signal System," 2024 International Conference on Power, Energy, Control
        and Transmission Systems (ICPECTS), Chennai, India, 2024, pp. 1-3, doi:
        10.1109/ICPECTS62210.2024.10780421.

[5]  Gheorghe, C., & Şoica, A. (2025). Revolutionizing Urban Mobility: A
        Systematic Review of AI, IoT, and Predictive Analytics in Adaptive Traffic
        Control Systems for Road Networks. Electronics.

[6] Kodama,     N.,  Harada, T.,    &   Miyazaki, K. (2022). Traffic signal control system
        using     deep     reinforcement       learning     with    emphasis      on    reinforcing
        successful experiences. IEEE Access, 10, 128943-128950.

[7] Huang, S. Y., Chang, H. C., Chen, Y. C., Wei, T. H., Yeh, I. H., Kuan, S. Y., ...
        &   Wu,    I.  (2026).    A   Robust    and    Efficient   Multi-Agent     Reinforcement
        Learning       Framework        for    Traffic    Signal     Control.     arXiv     preprint
        arXiv:2603.12096.

[8]  Almomany,       A.,   Eedi,   E.,   &   Sutcu,    M.   (2025).    Real-time     traffic  signal
        optimization      for   urban    mobility:    a   reinforcement       learning-enhanced
        framework with application to Kuwait City. Frontiers in Robotics and AI, 12,
        1669952.

[9] United    Nations,    "Goal   9:  Build   resilient  infrastructure,    promote    sustainable
        industrialization    and   foster  innovation,"    Sustainable      Development       Goals,
        2023.
```

#### Revised PDF page 72

```text
[10] United Nations, "Goal 11: Make cities and human settlements inclusive, safe,
        resilient and sustainable," Sustainable Development Goals, 2023.

[11]  M.   Muralidharan      and    R.   Pedarsani,     "Analysis     of  fixed-time    control   in
        signalized     intersection    networks,"      IEEE    Transactions      on    Control    of
        Network Systems, vol. 2, no. 1, pp. 22-31, 2014.

[12] Syla, V., & Lala, A. (2026). Microsimulation-Based Evaluation of Fixed-Time
        and Vehicle-Actuated Traffic Signal Control Strategies Using PTV Vissim
        in an Urban Corridor. Informatica, 50(5).

[13] C. Aboy, M. Chua, S. Gochuico, J. Nuesca, and M. Suwanpimol, "PC-Based
        Adaptive     Road     Traffic  Control    System,"     Undergraduate        thesis,   Dept.
        Electron. Commun. Eng., De La Salle Univ., Manila, Philippines, 1994.

[14] Geotab,     "Video   Intelligence    and   AI-driven enforcement        in the  Philippines,"
        PR Newswire Asia, May 2026.

[15] Grand View Research, "Philippines Intelligent Transportation System Market
        Size & Outlook,"

[16] DOST-PCIEERD,           "An  Analysis of    Smart    City Development        Frameworks      in
        the Philippines," UP CIDS Policy Brief

[17]  Dubey,    A.,  Lakhani,     M.,  Dave,    S.,  &   Patoliya,   J.  J. (2017,    December).
        Internet of Things based adaptive traffic management system as a part of
        Intelligent  Transportation      System    (ITS). In 2017     international    conference
        on soft computing and its engineering applications (icSoftComp) (pp. 1-6).
        IEEE.

[18]   Zemmouchi-Ghomari,            L.   (2025).     Artificial   intelligence     in   intelligent
        transportation    systems.     Journal   of  Intelligent  Manufacturing      and   Special
        Equipment, 6(1), 26-42.

[19]  Damadam,       S.,  Zourbakhsh,      M.,   Javidan,    R.,  &  Faroughi,    A.   (2022).   An
        Intelligent    IoT    Based      Traffic    Light    Management          System:      Deep
        Reinforcement Learning. Smart Cities, 5 (4), 1293-1311.

[20] Kodama, N., Harada, T., & Miyazaki, K. (2022). Traffic signal control system
        using    deep     reinforcement       learning     with    emphasis      on    reinforcing
        successful experiences. IEEE Access, 10, 128943-128950.

[21] H. Zhang, "Multi-Agent Reinforcement Learning Framework for Traffic Signal
        Control," arXiv preprint arXiv:2603.12096, 2026.
```

#### Revised PDF page 73

```text
[22] T.  Miller,  "Quantifying    the  Impact    of  RL   on Urban     Congestion,"     Journal   of
        Urban Systems, vol. 15, no. 4, pp. 201-215, 2025.

[23]  A.  Al-Wajih,   "AI   in ITS:   Real-Time     Decision-Making       Architectures,"     IEEE
        Access, vol. 13, pp. 14502-14518, 2025.

[24] M. J. Williams, "Agent-Based Modeling of Urban Mobility Landscapes," IEEE
        Transactions on Smart Cities, vol. 9, no. 2, pp. 112-125, 2024.

[25]  D.  Krajzewicz,     "SUMO      -  Simulation    of  Urban    MObility,"    IEEE    Intelligent
        Transportation Systems Conference, 2012.

[26]X.  Ma,   X.  Hu, and D.     Schramm, “Traffic Demand Accuracy Study Based on
        Public Data,”    Applied Sciences, vol. 15, no. 21, p. 11589, Oct. 2025, doi:
        10.3390/app152111589.

[27]S.  Chin,   O.   Franzese,     D.  Greene,    H.  Hwang,     and   R.  Gibson,    “Temporary
        Losses     of   Highway      Capacity     and   Impacts      on   Performance,”      2002.
        Accessed:            Aug.          11,         2026.          [Online].         Available:
        https://info.ornl.gov/sites/publications/Files/Pub57166.pdf

[28]Osogami,      T., Mizuta,   H.,  &  Idé,  T.  (2013,   October).    Identifying   the   optimal
        road   closure    with   simulation.    In   Proceedings      of  the   20th   ITS   World
        Congress Tokyo (Vol. 2013).

[29]Rakha,     H.,   &   Van   Aerde,    M.   (1995).    Statistical   analysis    of  day-to-day
        variations   in  real-time    traffic flow  data.   Transportation      research    record,
        26-34.

[30] Ahmad, O. (2005, July). Issues related to the commonality and comparability
        of driving simulation scenarios. In IMAGE Conference.

[31] Papageorgiou, G., Damianou,            P.,  Pitsillides, A.,  Aphamis, T., & Ioannou, P.
        (2007). A computer simulation           scenario analysis approach as           a decision
        support tool for transportation systems planning. WIT Transactions on The
        Built Environment, 96, 177-187.

[32] Kodama, N., Harada, T., & Miyazaki, K. (2022). Traffic signal control system
        using     deep    reinforcement       learning     with    emphasis       on   reinforcing
        successful experiences. IEEE Access, 10, 128943-128950.

[33] S.  Suo,    S.  Regalado,     S.  Casas,    and   R.  Urtasun,    "TrafficSim: Learning      to
        Simulate      Realistic    Multi-Agent      Behaviors,"      in   Proceedings       of   the
```

#### Revised PDF page 74

```text
IEEE/CVF      Conference      on   Computer      Vision   and   Pattern    Recognition
        (CVPR), 2021, pp. 10400-10409.

[34] K.  AlMulla,    S.  Ashkanani,    F.  Hassan,    H.   AlMesbahi,    M.   Alazmi,   and   M.
        Nadeem,     “IoT-Based     Adaptive    Traffic  Signal   Controller   to Optimize    the
        Flow  of  Traffic and   Reduce Congestion,”        in Proceedings     of the 2024 1st
        Mediterranean Smart Cities Conference (MSCC), 2024
```
