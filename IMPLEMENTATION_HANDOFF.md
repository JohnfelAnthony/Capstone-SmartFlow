# SmartFlow implementation handoff

Prepared: **2026-09-23, Asia/Singapore**. Intended reader: the project owner and the next implementation chat using **GPT-6 SOL, High**.

**Status update, 2026-09-24:** This document records the September 23 interruption. The six approved areas were subsequently implemented and verified on synthetic inputs; see the current checkpoint in [docs/PROGRESS_AND_HANDOFF.md](docs/PROGRESS_AND_HANDOFF.md). The remaining 31-task plan and research limitations still apply where relevant.

**Start here: the current working tree is unfinished and is not a release candidate.** The native engine, RL adapters, scenario storage and application pages already exist. Finish their connections and prove complete workflows before adding breadth. In particular, the RL API types were updated immediately before the implementation interruption, but the React training page was not updated to match. A fresh TypeScript check during this handoff fails in that page.

This document covers **all 31 tasks** from the advisory list, gives implementation and acceptance instructions, and records the unfinished six-task implementation effort. It does not claim that the entire 31-task backlog was implemented or that every future operation has already been authorized. The immediate previously approved implementation scope was tasks 1–6 in the owner's six-item request, reproduced below. The owner switched this conversation to preparing this handoff; application implementation was not continued while writing it.

Paths below are relative to the **SmartFlow repository root**, so this file remains useful after relocation. Current location: `C:\Users\jhepo\Desktop\trapik2\SmartFlow`. Git HEAD at inspection: **`5eb80ca`**, subject `ASTRAAA`. There are substantial uncommitted and untracked changes on top of that commit. Git HEAD alone does not describe the code being handed over.

## 1. Project purpose, decisions and boundaries

SmartFlow is a capstone traffic simulation and decision-support system for a bounded Tagum City study area. Researchers should be able to define traffic conditions, simulate connected roads, compare signal strategies and adaptive routing, and preserve understandable evidence.

Decisions already made:

- Use **React/TypeScript** for the web interface, **Three.js** for the dynamic visualization, and **FastAPI/Python** for authoritative traffic logic.
- Replace SUMO in the active application. Historical SUMO modules/assets remain; their presence is not a reason to reconnect TraCI.
- Use imported map geometry, initially cached OpenStreetMap data. Road geometry does not provide observed traffic counts, verified turn permissions or calibrated signal timings.
- Keep adaptive routing separate from RL signal control. A graph routing algorithm can choose paths while RL requests signal service.
- The supplied network is provisional: five junctions, twelve roads and twenty-four directed lanes. The final study intersections and field data have not been selected/collected.
- The current RL environment controls **one selected junction**. Other junctions use configured fixed-time or all-way-stop control. Network-wide coordinated RL has not been established as a required deliverable.
- The primary product is a web application that can also run locally. Training can run locally without SUMO or a browser. A hosted service and a separate desktop installer are different future delivery choices.
- Synthetic data is appropriate for software verification. It cannot establish real Tagum effectiveness or replace calibration.

Known simulation limits: one modeled lane per direction, conservative whole-junction reservations allowing one vehicle at a time, and simplified mixed-vehicle/pedestrian behavior. Do not claim lane changing, motorcycle filtering, realistic intersection capacity or field validation just because vehicles animate correctly.

The owner previously estimated approximately 35 days remaining. Reconfirm the actual submission date in the new chat; do not restart that countdown automatically. The required RL coverage and mandatory algorithm breadth remain questions for the owner/adviser. They do not prevent repairing the current workflow.

### Read before changing code

1. [AGENTS.md](AGENTS.md), [README.md](README.md) and [package.json](package.json).
2. This document's **sections 1–4 and 11**, then [project overview](docs/PROJECT_OVERVIEW.md). This is the initial context pack; it does not require reading every document or the whole repository.
3. Select the relevant delivery slice. Use section 11 to read its actual source, adjacent contracts and tests. Read sections 5–9 for the relevant backlog/acceptance details.
4. Consult [architecture and plan](docs/ARCHITECTURE_AND_PLAN.md) for decisions and release gates, and [progress](docs/PROGRESS_AND_HANDOFF.md) for the earlier `native-3` evidence. Read the pertinent sections rather than treating both as mandatory full startup reads.
5. Consult [project history and chapter archive](PROJECT_HISTORY_AND_MIGRATION.md), **sections 1–9**, for both codebases and chapter changes. Its full-manuscript appendices and copied PDFs are reference material for exact wording/figures, not routine coding context.
6. Resolve disagreement using current source and fresh verification for software facts; use the revised manuscript and explicit owner decisions for requirements. All these resources are inside SmartFlow; starting a new chat here does not require the parent Trapik2 workspace.

Both archived manuscripts still describe SUMO/TraCI. Preserve those originals. Later manuscript revisions should explain the chosen native engine and its limitations. The parent Trapik2/Dash application is historical context, not the specification for the new React workflow.

## 2. Immediate approved scope and completion standard

The interrupted implementation was explicitly approved for these six areas:

| Area | Required end state | Evidence needed |
| --- | --- | --- |
| Traffic-logic correctness | Consistent following gaps, queues, downstream blocking, turns, signal clearance, pedestrians and emergency priority. | Behavioral tests with meaningful safety and eventual-progress assertions, plus visual inspection of representative runs. |
| Disruption configuration | Users can schedule closures, reopening and speed restrictions, see affected roads and observe available detours. | Save/edit/reload/run round trip, event-boundary tests and browser demonstration. |
| Routing verification | Valid paths, closure avoidance, congestion-based rerouting, explicit no-route behavior and resistance to route oscillation. | Synthetic graph cases, including one driven by actual engine congestion rather than only mocked costs. |
| Signal-controller configuration | Users select a controlled junction and its plan; actual RL/fixed-time/stop-control identities are visible. | Persisted plans, model-to-junction compatibility checks and a live run proving the selected controller is applied. |
| Fixed-time baseline workflow | A credible reference controller and repeatable runs from saved settings and seed. | Repeated full runs with matching inputs/results; clear disclosure of shared safety/emergency rules. |
| RL training interface | Saved scenario selection, settings, progress, cancellation, checkpoints/resume and clear failures all work. | Real short QL/DQL/PPO jobs through the application/API, cancellation/resume verification and failure-path checks. |

Do not mark these six areas finished merely because the frontend builds or individual learning functions run. Conversely, completing them does not require all 31 broader backlog items, final field calibration, a paid hosting account or network-wide RL.

## 3. Exact state at the interruption

### 3.1 Verification ledger

| Evidence | Result and scope |
| --- | --- |
| Earlier `native-3` checkpoint | The maintained progress document records **40 Python tests passed**, API compilation passed and a three-seed synthetic headless experiment passed. These predate the latest training-worker edits. |
| New traffic-contract test run | Output captured during the interrupted implementation showed all ten methods in `tests/test_native_traffic_contract.py` passing. The combined command then entered neural learning tests. A later attempt to poll that command returned an unknown session handle, so do not claim completion of that whole combined run. |
| Earlier scenario-editor build | A completed build result was retrieved: TypeScript and Vite passed, with a large JavaScript chunk warning. This build predates the latest RL API type changes. |
| Fresh handoff TypeScript check | `node_modules/.bin/tsc.cmd --noEmit -p tsconfig.app.json --incremental false` **failed**. Errors are in `src/components/rl-training-page.tsx`: removed legacy settings fields, removed `resume_model`, and missing initial `active_job_id`. |
| Fresh handoff Python syntax inspection | AST parsing of **62 Python files** under `backend`, `services`, `simulation`, `tools` and `tests` found **zero syntax errors**. This does not execute imports, validate SQL, run the worker or prove learning behavior. |
| New worker/API/browser integration | **Not yet verified.** No successful end-to-end job through the rewritten worker is recorded. No browser acceptance of the new scenario controls or training flow is recorded. |

A pre-existing `dist/` directory, test count, stale server process or old model file is not evidence for the latest source. Revalidate the specific affected paths after implementation.

### 3.2 Changes already present in source

These are implementation facts, **not acceptance claims**:

| Files | Work already written | Remaining work |
| --- | --- | --- |
| `tests/test_native_traffic_contract.py` | Ten synthetic cases for mixed-vehicle gaps/queues, downstream storage, turns, yellow/all-red, slow pedestrians versus emergencies, no-route recovery, routing hysteresis, closure detours, speed-event restoration and repeatable fixed timing. | Strengthen the emergency progress assertion and add a reroute test using real engine-generated congestion costs. Run with the full suite. |
| `simulation/traffic_engine.py` | Scheduled speed factor `1` removes the restriction; `visual.slow_lanes` and `junction_controls()` were added. Runtime policy binding rejects an explicit training-junction mismatch. | Propagate control/road-state fields to frames/types/renderers; verify lifecycle and compatibility changes. |
| `services/native_scenario_service.py` | Derives lane/junction labels, default plans and network metadata from the actual network. | Test the API and avoid relying permanently on the current lane-ID suffix convention if network import changes. |
| `backend/main.py` | Added `GET /api/simulation/options` and `GET /api/scenarios/{scenario_id}/native-config`; model/status response mapping expanded. | Test permissions, errors, returned settings and current frontend integration. |
| `src/api/native-scenario.ts`, `src/api/scenarios.ts` | Native signal plans, road events, routing settings and `engine_config` types/API methods. | Keep aligned with backend validation and runtime payloads. |
| `src/components/native-scenario-controls.tsx` | Reusable selects/numbers; controlled-junction and plan controls; phase ordering; routing thresholds; timed events; initial closure/speed controls; configuration summary. | Browser usability, validation, persistence and runtime verification. |
| `src/components/scenarios-page.tsx` | Loads resolved native settings before editing, preserves configuration, exposes new controls and surfaces form errors. | Check all save/edit/reload paths. Review explicit fallback to native defaults when legacy resolution fails; do not silently discard settings. |
| `src/components/ui/alert.tsx`, `field.tsx`, `progress.tsx` | Added using shadcn and adjusted utility imports to the repository alias. | Reuse them in the unfinished training/dashboard UI. Do not regenerate unrelated components. |
| `services/training_settings.py` | New preflight validation: saved scenario, numeric limits, seeds, signal compatibility, advanced parameters, registered resume IDs, scenario snapshot/hash. | Run real API tests. Refine validation errors and consistency of resume settings. |
| `services/rl_training_service.py` | Worker rewritten around unique job directories, saved scenario snapshots, cancellation markers, validated artifacts, actual terminal errors, model/checkpoint catalog and bounded log reads. | High-priority integration verification; lifecycle details below are unfinished. |
| `simulation/training_control.py`, `simulation/rl_env.py` | Cooperative cancellation checks at reset/step and during chunked warmup. | Verify partial saves for every algorithm and termination during startup/optimization/evaluation. |
| `tools/training_inputs.py`, training/evaluation CLI tools | Added `--scenario-file`; snapshot loading takes precedence over mutable saved-scenario loading. QL metadata now carries decision/hold timing. Evaluation checks cancellation. | Verify all four CLI entry points, cancellation and snapshot provenance. |
| `database.py` | Added checkpoint-list and checkpoint-by-ID queries. | Test existing databases and registered checkpoint lookup; no new checkpoint table was needed. |
| `simulation/model_contract.py` | Cached metadata reads, artifact-presence validation and extraction of trained junction. | Review malformed metadata, missing scope metadata and compatibility guarantees. |
| `simulation/rl_policy_runtime.py`, `services/native_controller.py` | Loaded policy metadata includes trained junction/timing; live binding uses trained decision/hold timing. | Check selected-model inference, evaluation/live consistency and metadata default behavior. |
| `backend/schemas.py`, `src/api/rl.ts` | Added compatibility, checkpoints, trained junction/timing and `active_job_id`; replaced UI raw resume path with model/checkpoint IDs. | **The training page still uses the old contract. Fix this first.** |

### 3.3 Work that has not yet been done

- `src/components/rl-training-page.tsx` remains the old implementation. It does not submit `scenario_id`; it copies legacy fields from the selected scenario, uses raw resume paths and has no checkpoint picker. Its fallback model selection can silently select the first model.
- `src/components/dashboard-page.tsx` still sends legacy configuration overrides. `handleStart()` sends only duration, so selecting a new scenario without applying it can start the previously configured scenario.
- The dashboard has no completed explicit fixed-time/registered-model selection and repeatable-seed workflow.
- Runtime junction-control metadata is not yet carried through the render-frame/UI contract.
- The 3D/2D renderers do not yet implement the required native road-closure and speed-restriction display.
- New worker lifecycle tests and browser acceptance tests have not been added or completed.
- No field data collection, calibration, research-scale training, migration or deployment was performed by this implementation effort.

### 3.4 Existing worktree content to preserve

At inspection, Git reports modifications to the source files above, `PROJECT_HISTORY_AND_MIGRATION.md`, `docs/PROGRESS_AND_HANDOFF.md`, and package files. It also reports deletions of old extracted PDF scratch files under `tmp/pdfs/`. Those historical/archive changes predate the immediate worker edits; do not reset, restore or delete them indiscriminately.

Several new implementation files are **untracked**. A patch of tracked files alone will omit them. `data/models/`, `data/generated/`, the default database and backups are ignored by Git. A Git clone alone is not a complete project/evidence backup.

No current training process has been positively confirmed live for the handoff. Do not rely on session IDs from this conversation. Inspect actual processes/ports or the live API before starting duplicates; do not terminate unrelated Python/Node processes.

## 4. First repair sequence for the next chat

Use this order before expanding to the broader backlog:

1. Read the documents and inspect `git status`, including untracked files. Preserve the current worktree.
2. Repair the RL page against `src/api/rl.ts`. Do not restore obsolete fields merely to make TypeScript pass.
3. Add focused integration tests for the rewritten training worker. Use an isolated database and artifact directory, including inside spawned child processes.
4. Complete saved-scenario-to-dashboard configuration, explicit controller selection and seed handling.
5. Propagate per-junction controller and native disruption state into the stream and visualization.
6. Close remaining traffic/routing verification gaps.
7. Run the complete acceptance journey and relevant automated checks. Fix demonstrated failures.
8. Record verified results and limitations in the existing progress document. Only then mark the six approved areas complete.

### 4.1 Repair the RL training page

Main file: `src/components/rl-training-page.tsx`. Reuse existing cards, tables and charts when useful. Read the applicable shadcn skill before changing shadcn UI.

Implementation instructions:

1. Replace legacy training defaults with the new settings shape: `scenario_id`, `episodes`, `seeds`, `warmup_seconds`, `evaluation_seconds`, `decision_interval_seconds`, `minimum_green_hold_seconds`, `checkpoint_every`, `resume_model_id`, `resume_checkpoint_id`.
2. Initialize `RLTrainingStatusResponse` with `active_job_id: null`.
3. Submit the exact selected saved-scenario ID. Fetch its normalized configuration for a read-only summary. Keep scenario demand, road events, signal plans and controlled junction in that scenario; do not recreate a partial scenario from unrelated training dropdowns.
4. Explain that training changes one selected junction and the remaining junctions follow their saved plans. Label synthetic inputs and show the scenario name/junction before queuing.
5. Provide associated field labels, numeric limits, readable validation errors and loading states. Reject missing/invalid settings before submission, while retaining server validation as authoritative.
6. Prevent duplicate submissions with a pending-action state. Disable incompatible actions while another job is active. Distinguish the **job being viewed** from the server's **active job**.
7. Poll without overlapping requests or letting an older response replace a newer job selection. Do not overwrite useful action errors with an automatic “refreshed” notice.
8. Show current stage, algorithm, progress, latest episode/reward and terminal message. Evaluation is a separate stage; avoid displaying 100% completed while evaluation is unfinished.
9. Cancel the actual active job and show `stopping` until terminal state. Keep checkpoints visible after interruption.
10. Make model selection explicit. Show compatibility status/reason, trained junction and timing requirements. Add a checkpoint selector and a clear “start new training” action that clears resume IDs.
11. When resuming, select the matching single algorithm. Respect saved training parameters or clearly explain supported changes; never display newly entered hyperparameters as applied if the loaded model still uses old values.
12. Permit a compatible registered checkpoint to resume even if the parent final model was never saved. This requires checking checkpoint metadata, not only the parent model's compatibility flag.
13. Offer a clearly labeled short workflow-check preset. It must still execute real learning, saving, evaluation and inference; it is not a fabricated progress animation.

Proposed starting smoke settings, to be adjusted if actual validation requires it:

```json
{
  "episodes": 2,
  "seeds": "11",
  "warmup_seconds": 0,
  "evaluation_seconds": 20,
  "decision_interval_seconds": 1,
  "minimum_green_hold_seconds": 5,
  "checkpoint_every": 1,
  "resume_model_id": null,
  "resume_checkpoint_id": null
}
```

Attach an actual saved `scenario_id` from the isolated test database. Suggested DQL smoke parameters: `learning_starts=4`, `buffer_size=100`, `batch_size=4`. Suggested PPO smoke parameters: `n_steps=8`, `batch_size=4`, `n_epochs=1`. Ensure the run contains policy updates and that PPO rollout rounding is disclosed. These settings are for execution verification, not final capstone training.

### 4.2 Review and finish the rewritten worker

Read `services/rl_training_service.py` and `services/training_settings.py` in full before editing. The old failure mode was that a child could fail while the parent job was reported completed. The new implementation is intended to prevent that, but it has not been accepted with real subprocess jobs.

Current intended flow:

```text
Validate request and saved scenario
  -> create unique job directory and scenario.json
  -> persist queued job/items
  -> run selected training subprocesses sequentially
  -> validate saved registered models
  -> evaluate fixed-time and trained models on the same scenario/seeds
  -> validate evaluation result completeness
  -> persist completed / interrupted / error
```

Review these specific unresolved edges:

- `_run_job()` reads the job/settings/items before entering its main `try`. Test failures there and during enqueue/database writes so a stale active-job lock does not prevent future work.
- Job creation and item creation are multiple database operations. Make partial-enqueue failure visible and recoverable.
- Cancellation must work before process launch, during warmup, inside an episode, between algorithms, and during evaluation. The current watchdog waits up to 30 seconds for a cooperative exit, then terminates. Verify cleanup and truthful partial-save messaging after forced termination.
- The cancellation marker is process-specific through `SMARTFLOW_TRAINING_CANCEL_FILE`. Ensure a subsequent job never inherits the preceding job's cancelled state.
- Failure while evaluating multiple trained models currently has coarse item attribution. Distinguish “model saved” from “evaluation failed” for every affected item instead of incorrectly implying a complete end-to-end result.
- Evaluation-only jobs need useful current-item and progress display. The implementation presently provides little intermediate evaluation progress.
- Neural CLI progress uses total timesteps; on resume that can include previous training. Show additional work requested/completed accurately, including PPO rollout overshoot.
- `DQN.load()`/`PPO.load()` and QL resume may retain existing learning parameters. Decide and expose whether resume means continue with saved parameters or apply supported overrides. Metadata must describe the settings actually used.
- DQL checkpoints currently save a model archive, not an explicitly saved replay buffer. Do not promise exact training-state continuation unless replay buffer/RNG/optimizer requirements are implemented and tested. Continuing from learned weights can be acceptable if clearly described.
- Catalog compatibility checks should tolerate missing/in-progress/corrupt files with a useful reason. A missing final artifact must not hide an otherwise usable registered checkpoint.
- `training_junction()` falls back to the first network junction for older metadata. Decide how to handle uncertain provenance without silently approving a mismatched artifact. Preserve explicit compatibility rejection and update fixtures deliberately if the contract becomes stricter.
- `scenario_sha256` is saved, but integrity and provenance should be checked throughout launch, model metadata and evaluation output. A snapshot file should not silently change an already queued experiment.
- Automatic post-training evaluation currently passes `--record-timeline-seed -1`, so it saves evaluation results/runs without replay timelines. This is not proof of the separate recording workflow.
- The worker's completion message currently says “Synthetic results” unconditionally. If observed scenarios later become available, derive provenance wording from the saved scenario rather than hard-coding it.
- Model catalog reads metadata and registered paths; do not add arbitrary model uploads or arbitrary local resume paths as a shortcut. Avoid loading neural artifacts merely to populate a list.

Required automated cases: invalid request creates no queued job; archived/missing scenario; invalid seeds/durations; wrong junction/algorithm/checkpoint; process startup failure; nonzero exit; exit zero without artifact; evaluation failure; cancellation races; successful QL/DQL/PPO save/load/infer; checkpoint resume; scenario edited after enqueue; a second job after failure/cancellation; active-job conflict.

### 4.3 Connect saved scenarios to live simulation and baseline runs

Main files: `src/components/dashboard-page.tsx`, `src/api/simulation.ts`, `backend/schemas.py`, `backend/simulation_runtime.py`, `services/native_controller.py`.

- `configureSelectedScenario()` currently sends `road_constraint` alongside the saved scenario. `road_constraint: "None"` can reset initial native closures/speed restrictions. Preserve the full resolved `engine_config`; omit unchanged legacy overrides or replace that legacy quick-edit flow with an explicit native override contract.
- `handleStart()` currently sends only duration. Make applying the selected saved scenario/controller/seed part of a reliable start flow, or block start with an unambiguous unapplied-changes state. Never start a previous scenario under a new selection's label.
- Add fixed-time plus explicit compatible registered models. Do not use bare `rl` as a model choice.
- Add a reproducible seed and persist it with the run. Show scenario, duration, seed, actual controller/model and selected junction.
- Fixed-time runs must use all saved signal plans and offsets without enabling RL. All-way-stop junctions should remain visibly distinct.
- Preserve safety clearances, pedestrian protection and emergency priority for every compared controller. Explain the baseline as fixed-time with shared safety/priority rules; those rules can alter a nominal schedule.
- Check configured-versus-running state: `TrafficEngine.configure()` updates config but signal objects are rebuilt on start. Before start, show the saved plan; do not present stale signal objects as the new active configuration.
- Prove repeatability across live/headless paths using the same demand schedule, seed and model/engine/network versions. Rerunning after configuration changes is a different experiment.

### 4.4 Display actual controllers and affected roads

Main files: `services/render_frame_service.py`, `src/simulation/frame-types.ts`, `src/api/simulation.ts`, `src/simulation/SimulationScene3D.tsx`, `src/components/simulation-canvas-2d.tsx`, dashboard components.

The engine now emits `junction_controls` and `visual.slow_lanes`. The render serializer already has native closure/speed serialization, but TypeScript frame types and renderers still need to consume it. Inspect both live frames and dashboard-generated fallback frames.

- Carry `closed_lanes`, `slow_lanes` and per-junction control data through serialization and UI types without dropping them.
- Show a textual list of affected roads with lane/direction, closure status or speed percentage. Resolve labels from network-derived options.
- Highlight the corresponding road/lane geometry in 3D and the 2D fallback. Reopening and restoration to 100% must remove the indicator.
- Show a legend and use text in addition to color. Verify IDs match the directed lanes, not just an entire road with two directions.
- Show actual controller per junction: fixed-time, all-way-stop, or the selected RL algorithm/model. “Selected for RL” is a configuration candidate and does not prove RL is currently active.
- If using WebSocket frames, keep controller/road-state information aligned with that frame's simulation time. Avoid pairing a newer status poll with an older rendered frame without explanation.
- Verify recorded playback preserves the same information before claiming the replay path complete.

### 4.5 Close traffic/routing test gaps

Use the existing synthetic cross and diamond graphs in `tests/test_native_traffic_contract.py`.

- The anti-churn test currently patches `_travel_costs`. Keep it for the threshold/cooldown rule, then add a separate case where actual queued vehicles change engine costs and cause a beneficial detour.
- The pedestrian/emergency test finishes with `vehicle.position > 0`, even though the vehicle started near the stop line. Replace or supplement that with a meaningful assertion that the emergency vehicle crosses or completes after the pedestrian clears.
- Test no-route behavior for vehicles already in the network and demand waiting to enter. Preserve counts and explain waiting rather than deleting demand.
- Check initial speed factor `1` as well as a scheduled restoration; visual activity should mean a real restriction exists.
- For closures during junction traversal, define safe semantics: prevent new entry without teleporting/removing a vehicle already traversing a reserved connector.
- Test event times exactly at zero and later tick boundaries, stable ordering for simultaneous events, and reset/repeat behavior.
- Check eventual progress where routes and downstream storage allow it. Distinguish genuine oversaturation from a permanently stuck reservation or stale controller request.

## 5. Complete 31-task implementation backlog

The numbers below match the advisory list given to the owner. “Existing” means source is present; it does not mean the complete workflow is verified. Suggested owners identify responsibilities, not assigned people. One implementer can cover several roles.

### 1. Traffic engine correctness

**Existing:** native motion, gap rules, queues, junction reservations and regression tests. **Owner:** engine.

Implement/finalize: define and enforce minimum bumper gaps, admission storage, stop-line behavior, connector ownership and vehicle lifecycle accounting. Exercise mixed sizes and dense queues. Avoid broad rewrites unless a demonstrated failure requires them.

**Done when:** representative congested runs maintain safety/accounting invariants and progress whenever downstream capacity and valid routes permit. Tests identify the engine's simplified scope. Dependencies: shared network and signal semantics.

### 2. Signal safety

**Existing:** protected service requests, green limits and transition stages. **Owner:** engine/ML.

Implement/finalize: reject unsafe or out-of-scope actions; preserve yellow/all-red timing, pedestrian clearance and minimum/maximum green constraints under fixed-time, RL and emergency requests. Keep requested actions distinct from applied actions and safety overrides.

**Done when:** phase timelines and conflicting-demand tests prove clearance rules and no forbidden simultaneous service; the UI reports actual applied states. Dependencies: task 1.

### 3. Vehicle and pedestrian behavior

**Existing:** mixed dimensions, pedestrian crossing logic and emergency priority. **Owner:** engine/research.

Implement/finalize: verify spawn eligibility, following/stopping behavior by supported category, pedestrian entry/clearance, emergency requests and return to normal service. Record model assumptions and avoid implying unsupported lane changing or driver behavior.

**Done when:** reproducible cases prove safety and eventual service, with separate completed/unfinished vehicle and pedestrian counts. Field calibration is a later gate. Dependencies: tasks 1–2.

### 4. Synthetic testing scenarios

**Existing:** synthetic graph helpers and a peak/event JSON example. **Owner:** engine/test.

Implement/finalize: maintain a compact suite for empty/single/ordinary/peak demand, asymmetric queues, pedestrian-heavy traffic, emergencies, blocked exits, closure/detour and recovery. Keep stable seeds, expected behavioral outcomes and synthetic provenance.

**Done when:** scenarios can be run repeatedly from commands and, where appropriate, selected through the app. Do not create many redundant fixtures with no distinct acceptance purpose.

### 5. Dependable fixed-time baseline

**Existing:** fixed schedules and offsets; partial repeatability coverage. **Owner:** engine/frontend/research.

Implement/finalize: expose saved timing plans and seed, keep RL disabled, preserve common safety rules and record the exact baseline inputs. Verify reset/repeat and saved-run identity.

**Done when:** two runs using the same frozen inputs reproduce demand and results within declared precision; the selected baseline is the actual controller. Dependencies: tasks 2, 7, 9, 16 and 20.

### 6. Adaptive routing

**Existing:** directed routing, dynamic travel costs, closure detours and reroute thresholds. **Owner:** engine.

Implement/finalize: validate connected permitted turns, compare path costs, respect cooldown/minimum-benefit rules, respond to closures and recover from temporary no-route conditions. Avoid changing the already traversed path segment.

**Done when:** real congestion, closure, recovery and anti-oscillation tests pass with conservation intact. Dependencies: tasks 1 and 4.

### 7. Complete scenario editing

**Existing:** API persistence and newly added native editor controls. **Owner:** frontend/API.

Implement/finalize: create/edit/duplicate if supported/reload/run without losing nested configuration; distinguish omitted fields from explicit resets; surface atomic validation errors. Resolve legacy presets deliberately and require an explicit choice before replacing unsupported settings.

**Done when:** a scenario containing plans, events, restrictions and routing options survives a full browser round trip unchanged and executes those settings. Dependencies: native configuration contract.

### 8. Scheduled disruption controls

**Existing:** engine events and new editor fields; rendering incomplete. **Owner:** frontend/engine.

Implement/finalize: lane/direction selection, timed close/open, speed factor and restoration, readable summaries and meaningful invalid-input feedback. Demonstrate actual detours and recovery.

**Done when:** saved event times match engine transitions and affected-road displays; detouring vehicles avoid restricted entry. Dependencies: tasks 6–7 and 17.

### 9. Configurable junctions and signal plans

**Existing:** per-junction native plans, selected junction, new controls. **Owner:** engine/frontend/ML.

Implement/finalize: derive choices from the network; configure phase order, green bounds, clearance and offset; retain stop-controlled alternatives. Ensure training and inference use the selected junction and compatible model metadata.

**Done when:** plans persist, the chosen controller operates that junction, and all others are correctly identified. Dependencies: tasks 2, 7, 12 and 17. Network-wide coordinated RL is a separate decision.

### 10. Complete RL training workflow

**Existing:** CLI learners and newly rewritten, unverified job service; frontend currently broken. **Owner:** ML/API/frontend.

Implement/finalize: execute sections 4.1–4.2. Use saved scenario snapshots, validated settings, honest progress, cancellation, checkpoint resume and actionable errors. Keep one owned process-local training queue until measured needs justify more.

**Done when:** actual API/browser jobs finish, cancel, resume and fail correctly without losing provenance or leaving a permanently busy worker. Dependencies: tasks 7, 9, 11–12 and 20.

### 11. Actual synthetic RL training

**Existing:** QL, DQL and PPO learners and short learning-function smoke tests. **Owner:** ML.

Implement/finalize: run every required algorithm with enough steps for actual parameter updates; save metadata and reload for inference. Observe reward/action traces and valid-action handling. Separate pipeline smoke runs from longer training experiments.

**Done when:** saved policies execute in the same native engine and have finite observations/rewards, correct dimensions and auditable training inputs. A trained artifact alone is not an improvement result. Dependencies: tasks 1–5 and 9–10.

### 12. Reliable trained-model selection

**Existing:** registered controller resolver, version checks and new catalog fields. **Owner:** ML/API/frontend.

Implement/finalize: explicit algorithm/model identity, compatible junction/network/observation/action versions, timing consistency and clear incompatibility reasons. Eliminate fallback to the first or latest model when the user's selection is missing.

**Done when:** selected model ID/hash appears in a real run and changes applied policy actions; invalid selections are rejected before replacing runtime state. Dependencies: tasks 9–11 and 20.

### 13. Evaluation pipeline

**Existing:** controller evaluation CLI and saved summaries. **Owner:** ML/research/API.

Implement/finalize: match graph, demand arrivals, duration, warmup, seed and safety rules across controllers; preserve per-run outcomes and failures. Separate training and held-out evaluation conditions. Ensure partial/failed batches are not ranked as successful complete comparisons.

**Done when:** a repeatable command/job produces complete, traceable per-controller/per-seed results with unfinished demand and appropriate uncertainty for the eventual study. Dependencies: tasks 5, 11–12, 15 and 20.

### 14. Separate routing and signal comparisons

**Existing:** static/adaptive routing and multiple signal controllers. **Owner:** research/engine.

Implement/finalize: compare static versus adaptive routes under a fixed signal strategy, then signal strategies with routing held constant; optionally use a clearly defined factorial study. Avoid attributing a routing change to RL signal control.

**Done when:** comparison inputs identify the changed factor and every other relevant input is matched. Dependencies: tasks 6, 13 and 19. Final study design needs adviser agreement.

### 15. Metric correctness

**Existing:** waits, queues, speed, throughput, travel time, pedestrian delay and conservation. **Owner:** engine/research.

Implement/finalize: specify units, denominators, queue thresholds and measurement windows; hand-calculate small runs. Define treatment of warmup, rejected/pending arrivals and trips still unfinished at the horizon. Do not hide unfinished demand through completed-trip-only averages.

**Done when:** live, saved, replayed and exported values agree under the same definitions, including zero-demand and saturated cases. Dependencies: task 1 and recording/report boundaries.

### 16. Live simulation controls

**Existing:** lifecycle API and React dashboard. **Owner:** frontend/API.

Implement/finalize: reliable scenario application, start/pause/resume/reset/stop, bounded speed controls, seed and controller selection. Preserve state on invalid requests. Show a visible connection/error state instead of pretending the last frame is live.

**Done when:** the user can complete the lifecycle without stale scenario labels or state divergence. Dependencies: tasks 5, 7, 9, 12 and 25.

### 17. Faithful 3D visualization

**Existing:** procedural roads, vehicles, signals and cameras. **Owner:** frontend/engine.

Implement/finalize: consume authoritative positions, connectors, signals and road restrictions; check supported vehicle dimensions, pedestrians and emergency markings. Disclose render caps separately from simulation counts. Keep the 2D fallback semantically consistent.

**Done when:** selected synthetic cases visibly match engine state, including closure/reopening and actual controller identity. Decorative scenery is lower priority. Dependencies: tasks 1–3, 8–9 and frame serialization.

### 18. Recording and replay

**Existing:** native JSONL/gzip recording and strict playback validation. **Owner:** API/frontend.

Implement/finalize: save complete versioned frames/manifests, surface recording failures, load compatible runs, seek/pause/replay and preserve controller/road-state information. Reject corruption before disrupting a currently usable runtime.

**Done when:** replayed events, positions and metrics agree with the recorded run and the workflow works in the current browser build. Dependencies: tasks 15–17 and 20.

### 19. Comparison and reports

**Existing:** run/report/compare pages, APIs and reporting helpers. **Owner:** frontend/API/research.

Implement/finalize: select compatible runs, distinguish unmatched inputs, label algorithms/models and export actual data with provenance. Verify chart values and export totals, not only successful file download.

**Done when:** a reviewer can trace a chart or exported result back to its inputs/run, including incomplete trips and limitations. Dependencies: tasks 13–15, 18 and 20.

### 20. Experiment traceability

**Existing:** engine/network compatibility, demand fingerprints and new job snapshots. **Owner:** API/engine/research.

Implement/finalize: preserve scenario snapshot, network hash, engine version, seed set, actual model ID/hash, relevant timings, provenance and execution status. Verify the same information survives training, live runs, saved results and exports.

**Done when:** later scenario/map edits cannot silently change an old experiment's meaning and another teammate can reproduce it. Do not use file modification dates as substitutes for collection/run dates.

### 21. Network replacement workflow

**Existing:** OSM importer, derived study-network builder and graph validation. **Owner:** engine/data.

Implement/finalize: import a bounded network, validate directed connectivity/turns/IDs, display assumptions and switch through an explicit configuration boundary. Keep the old snapshot recoverable and invalidate incompatible artifacts.

**Done when:** a second small test network can be validated and loaded without editing road IDs throughout the UI. Extending trained-policy support beyond the currently versioned default network needs an explicit compatibility design. Final Tagum geometry still requires verification.

### 22. Data import and validation

**Existing:** explicit trips, demand windows and headless trip-CSV support. **Owner:** data/API/research.

Implement/finalize: settle supported schemas for counts/turns/pedestrians/trips, units and time bins. Map observations to network IDs, validate totals/connectivity and retain source/date/provenance. Aggregate counts cannot be treated as exact trips without documenting the conversion method.

**Done when:** sample valid files import predictably and invalid files produce row/field-specific errors without partial mutation. Use synthetic samples until observations exist. Dependencies: tasks 7, 20–21 and 31.

### 23. Authentication and permissions

**Existing:** accounts, roles, sessions and API permission checks. **Owner:** API/deployment.

Implement/finalize: compare the UI's available actions with server authorization for simulation, expensive training, reports and administration. Verify logout, session expiry and unauthorized direct API calls. Review training routes currently using view permission before hosting.

**Done when:** each agreed role can perform its intended workflow and cannot bypass restrictions through direct requests. Use existing conventions; avoid a wholesale identity-system replacement.

### 24. Shared-session behavior

**Existing:** one process-local live simulation and one process-local training worker. **Owner:** API/frontend.

Implement/finalize: define operator/owner/viewer behavior, expose the active owner/run and reject conflicting mutations. Test two users trying to configure/start/stop the same runtime. Distinguish a viewed historical training job from the active job.

**Done when:** concurrent users cannot unknowingly overwrite one another's work. Multiple independent simulations or multi-worker deployment are separate scope changes triggered by a real requirement. Dependencies: tasks 16 and 23.

### 25. Failure recovery

**Existing:** some runtime error handling and startup reconciliation; worker cancellation recently rewritten. **Owner:** API/ML/frontend.

Implement/finalize: handle disconnect/reconnect, invalid frames, subprocess crashes, API restarts, failed recording and interrupted training. Reconcile persisted statuses and keep valid partial artifacts available.

**Done when:** failures produce accurate states and a subsequent valid operation succeeds without deleting evidence or manually resetting a global flag. Do not promise exact mid-simulation recovery unless implemented. Dependencies: tasks 10, 16, 18 and 20.

### 26. Backup and restore

**Existing:** backup/restore UI and API routes. **Owner:** API/deployment.

Implement/finalize: back up a coherent database plus referenced models, networks, scenarios, recordings and manifests. Use SQLite-safe backup practices. Restore to a separate location, resolve artifact references and verify permissions.

**Done when:** the restored app can load scenarios/models and replay a known run. A database-only export is not a full artifact backup. Dependencies: tasks 18, 20 and 25.

### 27. Performance measurement

**Existing:** bounded native runtime and render limits; no final capacity certification. **Owner:** engine/frontend/deployment.

Implement/finalize: measure increasing synthetic traffic on target hardware, including step/frame cost, simulation-to-wall-time ratio, memory, browser frame rate and recording size. Identify whether CPU, rendering or storage is the limiting factor.

**Done when:** declared operating limits are backed by measurements and overload is explicit. Optimize measured bottlenecks while preserving demand/metric semantics; do not drop agents silently. Dependencies: tasks 16–18.

### 28. Complete application verification

**Existing:** unit/integration suites and historical browser checks. **Owner:** implementation/test.

Implement/finalize: execute the current browser journey from login and scenario editing through baseline, training, model selection, comparison, saving, replay and export. Include representative failure and permission paths.

**Done when:** the current build, tests and observed browser behavior prove the workflow, with evidence tied to source/configuration. Old passes and screenshots are not substitutes. Dependencies: preceding features used by the journey.

### 29. Standalone SmartFlow readiness

**Existing:** independent Git repository, own runtime/dependencies and copied research sources. **Owner:** project/deployment.

Implement/finalize: audit absolute paths and parent imports, preserve ignored/untracked artifacts, rebuild environments and test a separate location. Follow the archive's relocation checklist. Do not move/delete the original folder without the owner's instruction.

**Done when:** SmartFlow works without the parent Dash codebase and retained evidence remains accessible. Dependencies: task 26 and a working application checkpoint.

### 30. Deployment preparation

**Existing:** local web/API startup, configurable environment and storage paths. **Owner:** deployment/API.

Implement/finalize: prepare production secrets, allowed origins, HTTPS termination assumptions, persistent storage, resource bounds, restart procedures and a local demonstration fallback. Keep heavy training offline unless a measured, budgeted hosted requirement justifies it.

**Done when:** a reproducible deployment package and operating checklist fit measured requirements. Selecting/paying for a provider or publishing externally requires the owner's deployment scope; do not infer it from this handoff. Dependencies: tasks 23–29.

### 31. Research preparation

**Existing:** chapter archive, scope map and architecture decisions. **Owner:** research/project.

Implement/finalize: agree metric definitions, data-collection procedure, observation forms, calibration approach, evaluation design and objective-to-feature mapping. Draft the native-engine/SUMO-removal explanation and distinguish routing from signal learning. Obtain decisions on study intersections and required RL coverage.

**Done when:** the methodology is ready to accept real observations and supports honest interpretation of later experiments. Final results, calibrated timings and Tagum improvement claims remain blocked on actual data/evaluation.

## 6. Architecture contracts to preserve

### Engine and rendering

- Python is authoritative for motion, queues, signal transitions, routing, demand and metrics.
- React/Three.js renders/interpolates state and issues commands. Do not implement a second traffic model in the browser to hide engine defects.
- Keep core simulation independent of FastAPI, database sessions and rendering. The same engine must support live use, learning, headless evaluation and recording.
- Version behavior/observation/action/network contracts when compatibility changes require it. Do not bump versions merely to hide an unrelated regression.

### Scenario and event contract

The native configuration is stored under `engine_config`. Important fields include `controlled_junction`, `signal_plans`, `closed_lanes`, `slow_lanes`, `events`, `routing_mode`, `reroute_interval`, `reroute_improvement` and demand provenance. Preserve additional existing fields when editing a subset.

An event identifies `time` and `lane_id`, with `closed` and/or `speed_factor`. `closed: false` means reopen. `speed_factor: 1` means restore normal speed. The two changes are independent: reopening need not silently remove a separately configured slowdown. Validate against actual lane IDs and simulation tick boundaries.

The present validator requires a complete permitted phase order including pedestrian service, bounded green/clearance timings and valid control modes. Read `simulation/scenario_config.py` instead of duplicating guessed rules in the UI.

### RL and model contract

- `SmartFlowRLEnv` currently supplies a 30-value observation and five protected service actions.
- Policy requests are subject to engine safety rules. Requested action, applied result and any override must remain distinguishable.
- Bind a registered model to its algorithm, compatible engine/network/action/observation contract, trained junction and control timing.
- Freeze the full scenario for a queued training/evaluation job. A mutable scenario ID is a reference, not an immutable experimental input.
- Separate job status, per-algorithm status and model/checkpoint availability. A partial model can be useful even when the job is interrupted.
- Treat successful loading or low training loss as execution evidence, not proof of traffic improvement.

### Data and operations

- Retain existing SQLite conventions; use explicit migrations only when required. The latest checkpoint-list additions reuse existing tables.
- Use trusted registered artifact references. Keep model deserialization out of untrusted upload paths.
- Preserve source data, models, logs and failed experimental results. Do not make the worktree appear clean by deleting evidence.
- Keep the initial operational boundary small: one live runtime and one training worker per application process. Do not deploy multiple workers that accidentally create independent conflicting “singletons.”

## 7. Delivery slices and suggested ownership

| Slice | Deliverable | Owner | Dependencies | Acceptance |
| --- | --- | --- | --- | --- |
| A | Repair training page and establish worker tests | Frontend/API/ML | Current unfinished files | TypeScript passes; invalid jobs rejected; one real QL job completes and a failed job stays failed. |
| B | Finish saved scenario, signal and disruption configuration | Frontend/engine | A contracts; existing editor | Create/edit/reload preserves settings; chosen junction and exact event times appear in actual runtime. |
| C | Repeatable baseline plus visible control/road state | Engine/frontend | B | Same-seed baseline repeats; no stale scenario start; affected roads and per-junction controller identity are accurate. |
| D | Complete training, cancellation, checkpoints and model application | ML/API/frontend | A–C | Real QL/DQL/PPO smoke runs, safe cancel, registered checkpoint resume, selected policy inference and usable failures. |
| E | Evaluation, metrics, recording and evidence journey | Research/API/frontend | C–D | Matched comparisons and hand-checked metrics survive save/replay/export with provenance. |
| F | Bounded release and relocation readiness | API/deployment/project | E | Permissions, conflict handling, load limits, recovery, backup restoration and separate-location startup verified. |
| G | Final site/data study | Research/engine/ML | Confirmed intersections and observations | Calibrated scenarios, credible timings, held-out evaluation and manuscript claims supported by actual evidence. |

Slices A–D close the immediate six-item request; they also overlap the broader backlog. Slice E is the recommended next complete-product milestone. Preserve time for corrections and defense rehearsal after confirming the actual deadline.

## 8. Verification and safe execution instructions

### Local commands

Run from the SmartFlow root. Prefer the existing project environment; do not reinstall or upgrade dependencies without a demonstrated need.

```powershell
git status --short
git diff --stat
.\node_modules\.bin\tsc.cmd --noEmit -p tsconfig.app.json --incremental false
.\.venv\Scripts\python.exe -m unittest tests.test_native_traffic_contract -v
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
npm.cmd run check:api
npm.cmd run build
npm.cmd run lint
```

The first TypeScript command is expected to fail at this handoff until task A is implemented. Run targeted checks during repairs and the complete relevant suite after integration. Investigate existing versus introduced lint failures rather than suppressing them indiscriminately. A build warning about bundle size is different from a type error.

Development startup is `npm.cmd run api` and `npm.cmd run dev` in separate terminals. Restart the API after Python changes if auto-reload is disabled. Ensure a previously running server is not serving stale code.

### Isolate test data and child processes

- Use `tempfile.TemporaryDirectory` for test databases/artifacts and patch `config.DB_PATH` plus `services.rl_training_service.LOG_DIR` for worker tests.
- The new worker passes `config.DB_PATH` into its child environment. Verify that behavior so a subprocess cannot accidentally write to `data/smartflow.db` during a test.
- For browser acceptance, use a distinct verification database and distinct ports, with unmistakably named synthetic scenarios. Preserve the owner's real database.
- Join workers or wait for a verified terminal state before cleaning temporary directories. A missing response or observation timeout is not proof that a process has stopped.
- Verify the resolved directory is inside the intended test/workspace boundary before recursive cleanup. Do not use broad process-kill or filesystem-delete commands.
- Do not publish or upload artifacts as part of local verification.

### Minimum browser acceptance script for the six areas

1. Log in to the isolated verification instance.
2. Create a synthetic scenario with a named controlled junction, non-default signal plan, initial restriction and close/reopen/speed-restoration events.
3. Save, close, reopen and compare every setting. Submit an invalid value and confirm the valid saved scenario is preserved.
4. Select fixed-time and a known seed. Start without relying on stale applied settings. Inspect queues, turns, crossings and the controller display.
5. Observe the closure, detour and recovery at the configured times; check the affected-road list and both visualization modes if supported.
6. Repeat the baseline and compare demand and result fingerprints/metrics.
7. Open training, select the same saved scenario, apply short smoke settings and run QL/DQL/PPO. Confirm real output, compatible models/checkpoints and evaluation results.
8. Edit the saved scenario after queuing a separate job; confirm that job still uses its original snapshot.
9. Cancel a sufficiently long synthetic job after a checkpoint exists. Confirm a responsive cancellation request, terminal interrupted state, retained artifact and a successful subsequent job.
10. Resume the chosen compatible checkpoint; verify additional learning and accurate timing/provenance. Reject a mismatched model/junction/checkpoint with a useful error.
11. Apply a saved model in simulation. Confirm model identity and actual policy inference at the selected junction, with other junctions using their saved controllers.
12. Exercise a process/evaluation failure through a controlled test; confirm it is never reported as a successful completed job.

Capture results with source revision/worktree description, command or UI action, scenario/seed/model IDs, actual outcome and any limitation. Screenshots supplement behavior checks; they do not establish engine correctness by themselves.

## 9. Risks and deferred decisions

| Risk / decision | Mitigation now | Revisit trigger / owner |
| --- | --- | --- |
| Half-migrated frontend contract | Repair against current API types; no type casts or obsolete fields to conceal missing integration. | Immediate / frontend. |
| New worker looks correct but fails in subprocess execution | Isolated real jobs plus lifecycle/failure tests. | Immediate / API/ML. |
| Custom engine underestimates real intersection capacity | Keep simplified assumptions explicit; verify software behavior now and calibrate later. | Field observations or research plausibility failure / engine/research. |
| Final junctions change model compatibility | Derive UI choices from network; preserve versioned inputs; retrain as needed. | Site selection / engine/ML. |
| Required RL scope exceeds one selected junction | Obtain adviser decision; assess independent versus coordinated control explicitly. | Academic confirmation / project/research. |
| Checkpoint “resume” overstates continuity | Explain retained weights/state and missing replay/RNG state; test actual semantics. | Before presenting resume as a feature / ML. |
| Baseline, routing and RL changes are confounded | Match exogenous demand and isolate experimental factors. | Evaluation design / research. |
| Synthetic results are presented as observed Tagum performance | Label provenance at scenario, run and report boundaries. | Every result / research. |
| Hosting disrupts process-local ownership or loses artifacts | Single-process bounded trial, persistent storage and tested recovery before expansion. | Hosting decision / deployment. |
| Broad backlog consumes defense time | Finish the six approved areas and one complete evidence journey first. | Confirmed deadline / project lead. |

Deferred unless explicitly required: desktop installer, arbitrary city/network editor, distributed training, multiple independent live runtimes, alternative database/queue infrastructure, decorative 3D scenery and production deployment provider. Their absence does not block the immediate six-area scope.

## 10. Suggested opening message for the new chat

Copy or adapt this after selecting GPT-6 SOL with High reasoning:

> Start with `AGENTS.md`, `README.md`, `IMPLEMENTATION_HANDOFF.md` sections 1–4 and 11, and `docs/PROJECT_OVERVIEW.md`. Read other documentation as needed. Inspect the current worktree and the relevant code/tests before relying on previous status; do not read the entire repository or full manuscript appendices upfront. Continue implementation inside SmartFlow only. First repair the unfinished six-area work recorded in sections 2–4, including the RL page's current TypeScript errors and the unverified training-worker rewrite. Preserve existing uncommitted/untracked work and use isolated databases for tests. Finish and verify complete workflows; do not just add placeholders or make the build pass. Use the 31-task backlog for the next delivery slices, clearly distinguishing software verification from field calibration. Ask only questions that materially change the implementation scope. Report what changed, actual verification results and remaining work. Do not deploy, relocate folders or discard historical evidence without my instruction.

When finishing a slice, update the existing progress record with fresh evidence and the exact next action. Do not mark the full project or the six-task effort complete until their acceptance conditions have actually been exercised.

## 11. Codebase orientation without reading the whole repository

Added during the SmartFlow-only context audit on September 23. This is a map of the inspected source, not a claim that its unfinished connections work. Use it to locate the few modules that own the requested behavior, then inspect their callers, data contracts and relevant tests. Documentation cannot replace reading the code being changed.

### 11.1 Entry points and execution paths

| Workflow | Source path to follow | What to understand |
| --- | --- | --- |
| Frontend startup and navigation | `src/main.tsx` → `src/App.tsx` → page component under `src/components/` | App restores the authenticated user and selects pages through React state. Start here before assuming a separate URL router or modifying navigation. |
| HTTP and WebSocket connection | `src/api/client.ts`, `src/hooks/useSimulationSocket.ts` | API base URL, credentials, error decoding and frame connection/reconnection. Check the client contract before blaming server responses. |
| Python startup | `package.json` → `scripts/python-runner.mjs` → `run_api.py` → `backend/main.py` | Commands run from SmartFlow and prefer its virtual environment. Startup initializes/seeds the database and reconciles incomplete runs/jobs. |
| Save/edit a scenario | `scenarios-page.tsx` + `native-scenario-controls.tsx` → `src/api/scenarios.ts` / `native-scenario.ts` → scenario routes in `backend/main.py` → `database.py` | Native settings, legacy fields, normalization, validation and JSON persistence. Read `backend/schemas.py` and `simulation/scenario_config.py` alongside the form. |
| Configure and run live | `dashboard-page.tsx` → `src/api/simulation.ts` → lifecycle routes → `backend/simulation_runtime.py` → `simulation/traffic_engine.py` | Runtime owns the live engine and step loop. Follow `configure`, `start`, `_run_step_loop` and controller resolution; the UI must not start its own physics. |
| Stream and render | Engine `to_dict()` → `services/render_frame_service.py` → `/ws/simulation` → `useSimulationSocket.ts` → dashboard → 3D/2D renderer | A compact frame differs from full API state. Dashboard also refreshes full state and builds fallback frames, so new fields must survive both paths. |
| Train from the UI | `rl-training-page.tsx` → `src/api/rl.ts` → RL routes → `services/training_settings.py` / `rl_training_service.py` → CLI subprocess | This is the currently broken/unfinished integration. Follow the scenario snapshot, active job, model/checkpoint references and terminal status. |
| Learn in Python | `tools/train_ql.py`, `train_dql.py`, `train_ppo.py` → corresponding training module → `simulation/rl_env.py` → native engine | The RL environment supplies reset/step, observations, reward and safe service requests. Training is headless. |
| Apply a saved policy | `services/native_controller.py` → `simulation/rl_policy_runtime.py` + `model_contract.py` → engine `set_runtime_policy` | Registered identity, compatibility, trained junction/timing, actual inference and safety application. Do not treat a label as proof of inference. |
| Record and replay | Timeline routes → `services/timeline_generator.py` → native engine/manifest; playback routes → runtime → `simulation/timeline_engine.py` | A recording stores evidence; playback reads it. Inspect both sides when adding a state field or changing compatibility. |
| Compare and export | `runs-reports-page.tsx`, `compare-runs-page.tsx` → `src/api/runs.ts` / `compare.ts` → routes/report helpers | Trace metrics, compatibility keys and provenance through database rows and exported data. Do not substitute historical Dash helpers based on their filenames. |

Page filenames in this table without a directory prefix are under `src/components/`. The actual API routes are grouped in `backend/main.py`; schemas are in `backend/schemas.py`, authentication/permission helpers in `backend/security.py` and `auth.py`.

### 11.2 Engine ownership and ordering

Read these modules together for traffic work:

- `simulation/road_network.py`: road/lane graph, geometry sampling, connectors, routes and network fingerprint. Default inputs are `data/networks/tagum_network.json` and its retained OSM source.
- `simulation/scenario_config.py`: defaults, supported fields, numeric/ID validation, demand/plan/event rules and trip CSV parsing.
- `simulation/demand.py`: deterministic exogenous arrival schedules and demand fingerprint.
- `simulation/traffic_engine.py`: active `Signal`, vehicle/pedestrian state, lifecycle, movement, routing, metrics and RL application.
- `simulation/rl_state.py` / `rl_reward.py`: learning observations/action masks and reward, when the task affects RL.

`TrafficEngine.step()` currently applies due events, handles control requests, advances signal stages, advances pedestrians, moves vehicles front-first, advances simulation time, applies newly due events before arrivals, spawns demand, updates metrics and ends at the duration limit. An apparently harmless change to that order can alter closure timing, safety, reproducibility and observations. Read the actual function and boundary tests before changing it.

Useful engine locations by responsibility:

| Concern | Functions/classes to inspect |
| --- | --- |
| Configuration/start/reset | `configure`, `configure_from_scenario`, `start`, `_reset_state`, `reset` |
| Following and intersection entry | `_move_vehicle`, `_exit_has_space`, `_stop_priority`, junction reservations |
| Routes and disruptions | `close_lane`, `_travel_costs`, `_reroute`, `_apply_scheduled_events` |
| Signals and priority | `Signal.request`, `Signal.step`, `_control_signals`, `_request_safety_service`, `_crossing_occupied`, `_step_pedestrians` |
| Learning and inference | `configure_rl_control`, `apply_rl_action`, `set_runtime_policy`, `disable_rl_control` |
| Metrics and provenance | `_lane_queues`, `_refresh_metrics`, `reset_metrics`, `experiment_metadata`, `junction_controls`, `to_dict` |

Units are metres and seconds; the engine step is 0.1 seconds. The five RL action names are `SERVE_NORTH`, `SERVE_EAST`, `SERVE_SOUTH`, `SERVE_WEST` and `SERVE_PEDESTRIAN`. These are service requests, not arbitrary direct writes to signal lamps.

### 11.3 Contract and persistence map

| Domain | Main routes | Persistent/serialized data |
| --- | --- | --- |
| Scenario/options | `/api/scenarios`, `/api/scenarios/{id}`, `/api/scenarios/{id}/native-config`, `/api/simulation/options` | `scenarios`, native `engine_config`, legacy fields, network-derived lane/junction choices. `engine_config` is added through `_migrate_scenarios`; the original CREATE TABLE text alone is not the complete current schema. |
| Simulation | `/api/simulation/configure`, `/start`, `/pause`, `/resume`, `/stop`, `/reset`, `/step`, `/state`; `/ws/simulation`; `/api/visual-network` | `simulation_runs`, `run_metrics`, full state versus compact `RenderFrame`. Lifecycle suffixes here are under `/api/simulation`. |
| Learning | `/api/rl/jobs`, `/api/rl/status`, `/api/rl/jobs/{id}/stop`, `/api/rl/models`, `/api/rl/evaluate` | `rl_training_jobs`, `rl_training_job_items`, `rl_models`, `rl_checkpoints`, scenario snapshots, progress logs and saved artifacts. |
| Evidence | `/api/simulation/timelines`, `/api/simulation/playback/*`, `/api/runs/*`, `/api/compare/*`, `/api/reports/export` | Run metrics, timeline/manifest files, compatibility and evaluation summaries. |
| Accounts/operations | `/api/auth/*`, `/api/admin/*` | Users, roles, permissions, sessions, audits and backup records. Read authorization helpers, not only the visible button state. |

For a field change, trace **editor → TypeScript API type → request schema → validation → database representation → runtime/worker → state/frame → renderer/report**. Not every feature crosses every boundary, but skipping a consumer is how configuration gets lost. Current examples are the unmigrated training page and missing renderer consumption of road/control fields.

### 11.4 Test map and limited reading sets

| Change | Start with | Nearby tests |
| --- | --- | --- |
| Vehicle, signals, routing, events | Engine + graph + scenario validator | `test_native_engine.py`, `test_native_experiments.py`, `test_native_regressions.py`, `test_native_traffic_contract.py` |
| Scenario persistence or live commands | Relevant React page/API type + route/schema + runtime/database | `test_native_integration.py`, relevant regressions, then browser round trip |
| Training UI/job lifecycle | RL page/API type + schemas/routes + training settings/worker | `test_native_learning.py` is only a starting point; worker lifecycle/API tests are still required |
| Model/junction binding | Native controller + policy runtime/model contract + RL environment | Learning and integration tests, plus an actual selected-model run |
| Road/controller visualization | Engine snapshot + frame serializer + frame types/socket/dashboard + renderer | Frame regression/integration tests and observed browser behavior |
| Recording/comparison | Timeline generator/playback + relevant routes/API/page | Integration replay/compatibility tests and manual value/export checks |

Test files in this table are under `tests/`. Add meaningful coverage where the existing test only checks a narrower layer. Do not claim that a learning-function smoke test verifies cancellation or the browser training form.

### 11.5 What to defer reading, and what must stay local

- Do not start by reading `node_modules`, `.venv`, `dist`, generated logs/models/recordings, every skill copy or both full manuscript appendices. Inspect a generated artifact only when it is relevant evidence.
- `simulation/engine.py`, `simulation/sumo_engine.py`, `simulation/sumo_config.py`, `simulation/sumo_state.py`, `services/simulation_service.py` and `sumo/` contain historical material. Confirm imports before touching anything that appears obsolete. In contrast, `services/simulation_flow.py` is still imported by the active runtime despite its older-looking name.
- The copied source PDFs and all current context links are inside SmartFlow. The archive is sufficient for orientation to Trapik2; detailed investigation of an old implementation could still require the old source later. That is not necessary to resume the present six areas.
- `.agents/skills/shadcn/SKILL.md` exists within SmartFlow. Use the applicable local copy rather than depending on the parent workspace's copy; do not read all skill folders as project requirements.
- Keep database/artifact backups when actually relocating. Opening a new chat at the same SmartFlow directory is different from moving it or cloning it. No fresh-location runtime test was performed by this documentation audit.

The audit found the existing context sufficient after fixing navigation and stale checkpoint labels; it did not justify another large general-purpose Markdown file. Maintain this reading map when entry points change and update the evidence ledger after implementation so future chats need targeted verification rather than a complete rediscovery.
