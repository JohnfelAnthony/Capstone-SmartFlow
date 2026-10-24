# SmartFlow manuscript and current codebase review

> **Scope update — October 24, 2026:** Emergency vehicles, emergency priority, emergency metrics and emergency RL features are excluded from SmartFlow by the owner’s decision. Any earlier descriptions below are historical and do not define current functionality. Current simulation classes are car, motorcycle, tricycle, bus and truck. Original manuscripts and research artifacts are preserved. See the October 24 scope decision in the architecture document.


Reviewed October 8, 2026, Asia/Singapore. This is an assessment and proposed work sequence. It does not implement the recommendations or revise the source manuscripts.

## Main assessment

SmartFlow has a substantial simulation and research-workflow foundation. Its current gap is establishing a defensible connection between the selected real Tagum sites, reviewed observations, a credible baseline model, and comparative planning results. More interface pages alone cannot establish that connection.

The root `FINAL_SIGURO_CHAPTER1_AND_2.docx.pdf` is byte-for-byte identical to the revised manuscript already in `docs/research_sources/`. Both have 74 pages, 5,103,869 bytes, and SHA-256 `662779c2c50c78b3aadf9cdb8664fe5636ed2c3270ef5206e36c906fab57a7c6`. The new root copy therefore adds no manuscript changes relative to the archived revised draft. It still provides the six objectives against which the current implementation should be assessed.

There are two distinct tasks: finish the evidence needed for the research objectives, and revise the manuscript to describe the architecture and limitations actually implemented. Restoring obsolete SUMO dependencies would conflict with the project's approved native-engine direction.

## Review coverage and limits

- Read all 74 pages of the root final PDF; inspected rendered objective, conceptual-framework, unrelated-airport-text and ERD pages (PDF positions 5, 35, 45 and 48).
- Read the 15 project Markdown documents listed below. The history archive includes all 73 original manuscript page transcriptions and all 74 revised transcriptions. Original appendix text was read in full; revised text already read in the final PDF was reused, and all additional archive wording/layout fragments were read separately. This avoids treating the long archive as merely an index.
- Followed the current configuration, network, traffic/signal, import, training/evaluation, calibration/search and Field Observer implementations and their relevant tests. Application source, rather than historical pass counts or an existing `dist/`, establishes the behavior discussed here.
- Ran focused software checks against current source, with isolated test databases and synthetic artifacts. Did not rerun the entire application suite, rebuild the frontend or perform a new browser acceptance pass.
- Did not inspect the main research SQLite database or assume private/ignored footage and historical model artifacts were current field evidence. This review does not establish the absence of data held elsewhere; it establishes that the reviewed implementation/documentation does not demonstrate completed field validation or a measured Tagum improvement.
- Dependency documentation, installed skill reference libraries, generated temporary test-copy documentation and virtual-environment files were outside the project-documentation reading scope.
- Preserved existing application edits, original manuscripts and pre-existing documentation. This report and ignored analysis/verification artifacts are new.

The project Markdown documents read were:

1. `AGENTS.md`
2. `README.md`
3. `IMPLEMENTATION_HANDOFF.md`
4. `PROJECT_HISTORY_AND_MIGRATION.md`
5. `docs/PROJECT_OVERVIEW.md`
6. `docs/ARCHITECTURE_AND_PLAN.md`
7. `docs/PROGRESS_AND_HANDOFF.md`
8. `docs/RESEARCH_METHOD.md`
9. `docs/RESEARCH_WORKSPACE.md`
10. `docs/FIELD_RECORDING_PROTOCOL.md`
11. `docs/FIELD_DATA_SMARTFLOW_INTEGRATION.md`
12. `docs/VIDEO_OBSERVATION_TOOL_PLAN.md`
13. `deploy/README.md`
14. `tools/field_observer/README.md`
15. `tools/field_observer/THIRD_PARTY.md`

## What the manuscript actually requires

The general objective on PDF page 5 is a simulation-based approach to traffic signal optimization and adaptive routing for urban development planning. Its six specific objectives are paraphrased below; statuses separate software capability from research fulfillment.

| Objective, PDF page 5 | Current implementation | Required work/evidence |
| --- | --- | --- |
| 1. Model a specific real Tagum intersection using maps, geography and traffic statistics. | Connected OSM-derived five-junction graph, generated lane/turn geometry and 2D/3D rendering exist. | Register the actual final sites and study boundary; verify lanes, storage, permitted movements, crossings and existing control. The supplied graph is not automatically the selected study area. |
| 2. Use actual traffic data to represent volumes and conditions. | Four CSV schemas, source retention/hashes, explicit trips, mixed vehicle types and a separate offline observation tool exist. | Review actual recordings/counts, document missing coverage and inferred inputs, convert observations faithfully, calibrate and independently validate. An `observed` label is a source declaration, not verification of accuracy. |
| 3. Provide configurable traffic and signal settings for scenario testing. | Saved `engine_config`, scenario editing, signal plans, demand windows, timed disruptions and execution workflows exist. | Support whichever measured site settings the present contract cannot represent; preserve configuration through all workflows. Existing controls are useful but cannot represent arbitrary real signal plans. |
| 4. Test closures/road modifications and evaluate rerouting alternatives. | Lane closure/reopening, speed restrictions, turn restrictions and graph-based rerouting exist; routing regressions pass. | Build justified site-specific cases and report detour effects. Lane events are not a general editor for new road alignments, lane counts or physical intersection redesign. |
| 5. Represent peak periods, holidays, closures and other events. | Timed demand windows and road events can express event scenarios. | Use observed peak inputs or explicitly justified event assumptions; preserve labels distinguishing measured and hypothetical conditions. A named holiday preset alone is insufficient evidence. |
| 6. Use RL signal learning and provide information about signal arrangements. | QL, DQL/DQN and PPO training, model registration, inference, held-out scenario/seed checks and controller evaluation exist. | Establish a credible baseline and completed held-out experiments, then report supported existing-versus-proposed signal comparisons. Training execution does not establish improvement or optimal signal placement. |

PDF pages 7-9 bound the work to a selected intersection and connected roads, exclude live road feeds and physical signal actuation, and include proposed signals at potentially unsignalized sites. A bounded connected network is compatible with that framing; a citywide expansion is not required. The current RL controller operates one selected junction, while the other junctions use their saved plans. Required final RL coverage needs academic confirmation; the PDF does not by itself mandate coordinated multi-agent control.

PDF page 60 explicitly describes PyTorch DQN. Current DQL training uses `stable-baselines3.DQN`; this is an implementation of the relevant neural algorithm, rather than a missing DQN feature. QL and PPO are additional implemented comparators. Confirm the required comparison set instead of assuming all three are mandatory.

The title/general framing can imply RL routing, but the scope identifies signal control as the learning problem. Current routing is a graph shortest-path calculation using travel-time/congestion costs. Make that distinction explicit throughout the final manuscript.

## What is already useful in the system

The existing application supports saved scenarios and complete native settings, deterministic simulation, mixed vehicle dimensions/speeds, protected pedestrian service, emergency priority, demand and disruption schedules, adaptive routes, live visualization, recording/replay, reports, comparison and offline learning. Account permissions, audits, backup/restore and bounded single-worker operation are also represented.

Settings, Search and Calibration & Validation now have explicit application destinations. Search respects permissions and opens saved records. Calibration stores frozen fixed-time baseline snapshots, reference definitions, tolerances and reviewer notes; validation enforces separate source periods and frozen structural settings. The sidebar clock has been removed. These are current source features, not outstanding additions from the older handoff.

Key code evidence:

- [Explicit application destinations](../../src/App.tsx), lines 181-198.
- [Native traffic/control implementation](../../simulation/traffic_engine.py), including signal timing at lines 32-83, reservation admission at lines 495-528, metrics at lines 593-645 and selected-junction control at lines 672-722.
- [Observed-data conversion](../../services/observed_data_import.py), lines 63-176.
- [Research records/search](../../backend/research_routes.py), lines 48-79 and 151-286.
- [DQN adapter](../../simulation/dql_training.py), including the `stable-baselines3.DQN` implementation metadata.
- [Repeated controller evaluation](../../tools/evaluate_controllers.py), lines 368-406 and 466-589.
- [Provisional observation validation/export](../../tools/field_observer/field_observer/core.py), lines 184-328.

## Ranked changes to the system and research workflow

### 1. Establish the final study-site contract and run one field pilot

Record actual site names, coordinates, network node/lane mappings, permitted movements, lane/storage dimensions, crossings, control type and measured timing. The cached network itself declares experimental signals, one modeled lane per direction, 3.3 m widths, an assumed 30 km/h study speed and synthetic demand. Those declarations are honest assumptions, not field validation.

Start with the existing protocol's proposed 10-minute stationary-phone pilot and an independently reconciled manual reference. Use the pilot to identify essential fidelity and measurement changes before building a large import interface. This pilot does not reduce the final study scope. With one phone and sequential takes, do not describe separately recorded sites as a simultaneously observed network.

Acceptance: the team can trace every modeled approach, control group and essential input to field evidence or an explicit justified assumption; unsupported required behavior has a concrete repair or agreed scope decision.

### 2. Complete the observation review/audit and conversion workflow

Field Observer v0.3 produces useful proposals, corrections, timestamp-preserving evidence tables and immutable provisional exports. Its current `quality_report.json` explicitly states that Gate A is unimplemented, Gate B is not recorded and field accuracy is unverified. Automatic/sample-audited acceptance is deliberately rejected. Keep those distinctions until real audit evidence exists.

The existing plan distinguishes an independently evaluated raw automatic result (Gate A, if automatic acceptance is sought) from independently audited final reviewed measurements (Gate B). A failed automatic gate can still lead to usable manually reconciled evidence; it must not be relabeled as automatic accuracy. Evaluate the necessary categories/locations and missing detections, not only objects the detector proposed.

Implement a versioned adapter from reviewed evidence to native scenario inputs when the pilot establishes the necessary mapping. Keep original source bytes/hashes, take identity, times, coverage, corrections, accepted class and measured-versus-inferred fields. Do not interpret an unknown view as a zero count or infer full network OD from a visible local turn.

The current importer converts aggregate vehicle counts into evenly spaced **car** arrivals. Only explicit trip rows preserve supported class and entry time. Field Observer can record jeepneys, bicycles and other/unknown categories that the engine's six vehicle types cannot all represent. Preserve raw categories and justify any supported mapping; add necessary behavior/classes only where site evidence requires them. Pedestrian native inputs currently retain time/junction but not crossing identity and direction.

Acceptance: one reviewed pilot package converts into a reproducible saved scenario with understandable mappings and assumptions; required input coverage is sufficient for the claimed experiment. Plan for the 1 MB/5,000-row import and 2 MiB serialized-scenario limits without silent truncation.

### 3. Make the fixed baseline credible for the observed site

This is the most consequential engine issue. The engine reserves an entire junction for one vehicle. It also generates one lane per permitted road direction and models simplified pedestrian service. Those simplifications can limit discharge and change queues even if collisions/accounting tests pass.

Current signal plans have one shared green duration, a sequence of separate cardinal approaches plus pedestrian service, common clearance settings and an offset. They cannot faithfully encode unequal phase greens, simultaneous opposing approaches, movement-specific arrows or crosswalk-specific permissions. An all-way-stop alternative exists, but it is not a universal model of unsignalized local operation.

Use the pilot to decide which lane/storage, movement conflict, signal grouping/timing and pedestrian changes are essential. Verify baseline discharge, queue progression and service pattern before interpreting RL gains. If the required site behavior cannot be reproduced, change the model or narrow the claim with academic agreement.

Acceptance: the fixed baseline reproduces the measured control pattern and meets predeclared tolerances for relevant field measures. Safety and conservation remain enforced under congestion and disruptions.

### 4. Align measurements, calibration and RL contracts

The engine already records lane exits, junction passages, lane queues and whole-network summaries. Extend extraction to the required location, movement, class and time-window definitions rather than claiming that no local counts exist. The present calibration workspace's `local_reference` pathway allows a manually supplied matched measurement and extraction method; it is not an automated observer-to-simulator evaluator or automatic parameter optimizer.

Keep these distinctions:

- Whole-network `throughput` is completed boundary trips in the measurement window, not local stop-line discharge.
- `avg_queue` is a time average per incoming signal lane, not a single approach snapshot or total queue.
- `avg_wait` includes active and completed admitted vehicles; pending arrivals are excluded.
- `avg_travel_time` averages completed trips and excludes unfinished trips.
- Density, pedestrian delay, unknown queues and unfinished populations need their units and observation definitions stated.

Calibrate against one reviewed period, freeze geometry/control/behavior and measurement definitions/tolerances, then validate on an independent period. Different random seeds or chunks from the same recording do not create independent field data.

If phase groups, geometry or supported action meaning change, update configuration validation, stepping, RL observations/actions/reward, model metadata, API frames, rendering and replay coherently. Current policies use a 30-value observation/five-service-action contract and bind to the versioned network/selected junction. Reject incompatible old artifacts and retrain; do not modify metadata to bypass compatibility checks.

Acceptance: independent validation meets the declared protocol; final models and reports identify the frozen input/model versions and scope. The ability to launch training does not presently enforce field validity, so synthetic workflow testing and final research training need explicit evidence status.

### 5. Finish a planner-facing experiment and signal-planning workflow

Build on the existing evaluator and Compare Runs. Repeated controller runs, held-out scenarios/seeds and mean/min/max/standard-deviation summaries already exist. The remaining work is a complete study protocol and interpretable evidence, including paired comparisons/uncertainty where appropriate, rather than rebuilding evaluation from scratch.

Compare fixed-time versus the required RL controller on matched inputs. Evaluate routing separately by holding signal control constant. For signal planning, define existing/unsignalized, proposed fixed-time and proposed RL configurations where applicable, and compare them under the same relevant demand and measurement protocol. Do not present the simplified all-way-stop case as the actual existing condition unless field evidence supports it.

Reports should include baseline identity, site/source/model/network hashes, calibration and validation status, matched demand, warmup/window, repetitions, effect sizes/uncertainty, unfinished/dropped demand, pedestrian/emergency effects and limitations. A finding may be beneficial, harmful or inconclusive. A numerical winner does not prove global optimal placement or authorize physical installation.

Acceptance: a reviewer can reproduce the experiment and follow the evidence from observed inputs to the limited recommendation. Confirm primary outcomes, tolerances and repetition counts with the adviser; there is no universal number supplied by this review.

### 6. Expose that workflow in the sidebar

These proposed destinations are useful because they serve missing objectives, not because the sidebar needs more entries:

| Destination | Purpose | Implementation approach |
| --- | --- | --- |
| **Study Sites** | Actual site identity, study boundary, lane/turn/crossing mapping, current control and assumptions. | Keep it small initially; one supported pilot site with versioned evidence. |
| **Field Data / Observations** | Reviewed datasets, recording periods, coverage/audit status, import mapping and provenance. | Integrate the existing separate observer workflow; keep CV dependencies outside the native app environment. |
| **Experiments & Evaluation** | Repeatable scenario/controller/routing comparisons with held-out inputs and uncertainty. | Extend existing training/evaluation and Compare Runs capabilities. |
| **Signal Planning** | Existing-versus-proposed control cases, evidence-backed findings and limitations. | Initially a structured report/workflow within Experiments; separate page only if its work justifies it. |

Retain and connect Scenarios, Calibration & Validation, RL Training and Runs & Reports. Avoid a second calibration page, decorative indicators, new algorithms or citywide features while field/model validity remains unresolved.

## Changes to the manuscript

Page numbers below are one-based PDF positions, including the cover.

| Priority | Location | Correction |
| --- | --- | --- |
| High | Pages 7, 26, 29, 31, 33-39, 55-64 and 70, including architecture/technology figures | Describe React/TypeScript/Vite/Three.js, FastAPI and the native Python engine. Replace obsolete SUMO/TraCI paths in current-system descriptions and figures. Preserve SUMO as related-work/history where applicable. |
| High | Page 45 | Replace unrelated airport ASDE-3/FAA deficiency-processing paragraphs with SmartFlow signal-processing and monitoring/reporting data flow. This is visible manuscript content, not merely an extraction artifact. |
| High | Title, objective framing, scope and architecture | State clearly that RL controls traffic signals and adaptive routing uses a separate graph algorithm. Specify selected-junction scope and distinguish offline learning from policy inference during simulation. |
| High | Objective 2, pages 5 and 55-57 | Explain field-data acquisition/review and derived demand separately from simulation-generated observations used by RL. Offline phone-video observation does not imply live CCTV ingestion. |
| High | Pages 46 and 65-66 | Resolve the contradiction between excluding RBAC and requiring administrator/researcher/operator privileges. Describe implemented roles/permissions and local operating assumptions consistently. |
| High | ERD/data dictionary, pages 46-54 | Update the conceptual eight-entity diagram to the implemented schema/actual relationships and external artifacts. Current schema creation defines 18 tables, including roles/sessions/audits/models/checkpoints/jobs/calibration. Document `password_hash`, `engine_config` and frozen evidence rather than implying plaintext passwords or nonexistent literal RL-output/report tables. |
| Medium | Metrics/data dictionary and evaluation sections | Align throughput, queues, waits, density units, populations and window semantics with actual code and field references. Define any claimed signal-efficiency measure and support it with a real calculation. |
| Medium | Page 16 and proposal/results wording | Qualify statements that the environment is already verified against real operation. Use consistent tense and identify implemented features, synthetic software verification and completed field results separately. |
| Medium | References, pages 71-74; related citations on page 4 | Audit internal citation alignment. Reference [19] is an IoT traffic paper despite its use for DNSC RDE; [16] does not identify the claimed CHED source. [6], [20] and [32] repeat the same Kodama reference; [7] and [21] use the same arXiv identifier with different author/title entries. Verify against originals before correcting or making claims about authenticity. |
| Medium | Testing/security/maintenance sections | Report actual dated evidence and unresolved checks. Referencing ISO practices is not evidence of certification. Reconcile local web operation, one process-local compute workload, backups and recovery with the actual deployment plan. |

Prepare these changes in a new manuscript revision. Do not overwrite the retained original/revised manuscript PDFs or rewrite the historical appendices to conceal their wording.

## Documentation consistency and structure

The repository structure is appropriate for this architecture: `src/` handles interaction/rendering; `backend/` owns API/runtime orchestration; `simulation/` owns native traffic/learning; `services/` supports persistence/import/training; `tools/` contains headless experiments and the isolated observer; `tests/`, `docs/`, `data/` and `deploy/` have clear roles. This review found no reason to reorganize those boundaries or reconnect the historical parent application.

The strongest next-step documents are `FIELD_RECORDING_PROTOCOL.md`, `FIELD_DATA_SMARTFLOW_INTEGRATION.md`, `VIDEO_OBSERVATION_TOOL_PLAN.md` and `RESEARCH_METHOD.md`. Much of the roadmap above is already anticipated there. Their proposed changes must remain distinguished from implemented behavior.

Refresh the navigation summaries in the maintained docs: README's headline “Latest captured status” is October 2 even though it contains October 4 additions; the architecture opening calls the interrupted September 23 handoff the latest implementation state despite later repair evidence. Keep those dated checkpoint records, but point readers first to the current state. Add a compact objective -> feature -> code -> test -> field-evidence matrix rather than a completion percentage based on file counts.

The final study identities/boundary, required RL junction coverage, mandatory algorithms, agreed validation/evaluation protocol and exact submission date remain academic decisions to record. A historical provisional October 27 schedule is not a confirmed deadline.

## Fresh verification, October 8

| Check | Outcome |
| --- | --- |
| `.venv/Scripts/python.exe -m unittest discover -s tests -p test_native_traffic_contract.py -v` | 12 passed, 2.722 seconds. Synthetic traffic, signal-clearance and routing regressions. |
| `.venv/Scripts/python.exe -m unittest discover -s tests -p test_research_workspace.py -v` | 8 passed, 7.316 seconds. Frozen calibration records, independent validation protocol, search permissions and exports/restore. |
| Field Observer environment, `python -m unittest discover -s tests -v` from `tools/field_observer/` | 30 passed, 16.996 seconds. Initial sandbox execution hit temporary-fixture write/cleanup permission errors. The unchanged suite passed on the authorized unrestricted rerun. |

Total: 50 focused tests passed. The larger October 4 record of 107 application tests and 30 observer tests is historical evidence, not a fresh full-suite result from this review. These tests validate specified software mechanics; none demonstrate detector field accuracy, representative Tagum demand, calibrated intersection capacity or RL superiority.

Recommended first deliverable: one identified real site, independently reviewed pilot measurements, a justified native input conversion, and a fixed baseline that can reproduce the relevant observed behavior. That deliverable resolves what software changes are actually necessary and creates a credible starting point for the final research comparisons.
