# Progress and handoff

Updated: **2026-09-23** (Asia/Singapore). Scope: `SmartFlow` only.

Navigation: [Start here](../README.md) · [Purpose and scope](PROJECT_OVERVIEW.md) · [Architecture and plan](ARCHITECTURE_AND_PLAN.md) · [History and full chapter archive](../PROJECT_HISTORY_AND_MIGRATION.md)

## Current checkpoint

**The `native-3` Python checkpoint passed all 40 tests. The capstone is not yet a verified release.** After the documentation/planning pause, the owner requested continued engine work. The current changes address demonstrated configuration, runtime, event-timing, controller and playback failures. The owner then requested a portable record of both codebases and both manuscripts before moving SmartFlow. That record and exact source PDF copies are now inside this folder; no folder move or deployment was performed.

The direction remains custom Python traffic logic, React/Three.js, a bounded connected Tagum study network and routing separate from RL signal control. The [delivery plan](ARCHITECTURE_AND_PLAN.md) retains the owner's roughly 35-day estimate from September 22, provisionally ending October 27 with five days reserved for corrections. The exact deadline, mandatory algorithms and required RL junction coverage still need adviser confirmation.

## What is present in the current source

| Area | Present implementation | Qualification |
| --- | --- | --- |
| Application shell | React pages for live simulation, scenarios, training, runs/reports, comparison, accounts/roles, audits and backups, with corresponding API routes. | Current end-to-end browser acceptance remains. |
| Native network | Cached OSM extract; five junctions, twelve roads, twenty-four directed lanes; validation, geometry, connectors and turn restrictions. | Field verification of lanes, turns, signals and demand remains. |
| Traffic engine | `native-3`; deterministic stepping, gaps, reservations, signal clearances, pedestrians, emergency priority, closures and rerouting. | One modeled lane per direction and conservative one-vehicle whole-junction reservations limit realism/capacity. |
| Extended scenarios | Strict native configuration, demand windows, explicit trips/CSV, mixed vehicle dimensions, signal plans and all-way-stop control. | Detailed legacy disruption JSON is explicitly rejected rather than silently ignored; use native fields. |
| Metrics | Waiting, queues, throughput, travel time, pedestrian delay, unfinished demand, lane/junction diagnostics and conservation counters. | Hand-checked research definitions and final report/export acceptance remain. |
| API persistence | Saved `engine_config`; omitted update fields preserve stored values; explicit empty values can reset them; invalid configuration/start errors leave runtime state intact. | React still needs complete native configuration controls/types and browser round-trip acceptance. |
| RL | QL/DQL/PPO adapters, 30-value observations, safe service requests, artifact compatibility checks and real runtime inference. | One selected junction. Short successful training is not evidence of controller quality. |
| Recording/comparison | Native JSONL/gzip recordings, experiment provenance, input compatibility, strict playback validation and comparison signatures. | Historical artifacts can be incompatible; complete UI/export comparisons remain to be accepted. |
| Headless experiments | Scenario-based runner, synthetic peak/disruption example, saved-scenario training/evaluation support. | Three-seed command verified; actual-data calibration and held-out research evaluation remain. |
| 3D | Procedural roads, vehicles, signals and camera controls consuming native frames. | No new frontend build/browser inspection in this engine/archive checkpoint. Earlier checks predate recent source edits. |

## Changes in this engine checkpoint

- **Configuration and demand:** validate nested objects and integer seeds; bound explicit-trip materialization; preserve advanced scenario settings on partial updates; validate a candidate before mutating the active run.
- **Traffic/control timing:** apply timed constraints before arrivals at the event boundary, account for initial signal offsets, respect configured green limits, and prevent requests from changing a junction outside the selected RL scope. Stop-control priority now considers eligible outgoing movements.
- **Runtime lifecycle:** reject incompatible live-start changes, finish/persist terminal manual-step runs, report errors consistently, validate replay before interrupting a current run, and include computation time in the runner's tick budget.
- **Evidence and replay:** retain controller/model identity and hashes, policy-decision and safety-override diagnostics, experiment metadata and native lane-closure details. Validate playback manifest/frame continuity and final timing; protect stored frames from caller mutation; persist recording failures.
- **Tools and compatibility:** evaluation uses the same runtime policy path as live execution; validate finite durations; report unfinished demand and conservation. The engine contract is now `native-3`, requiring compatible models and recordings.

Primary changed areas: `simulation/scenario_config.py`, `demand.py`, `traffic_engine.py`, `model_contract.py`, `rl_policy_runtime.py`, `timeline_engine.py`; `backend/main.py`, `schemas.py`, `simulation_runtime.py`; `services/native_controller.py`, `render_frame_service.py`, `timeline_generator.py`; experiment/evaluation tools and integration/regression tests. The wider worktree also includes earlier native migration and frontend edits; not every Git modification originated in this checkpoint.

## Verification record

These are captured results for the **September 23 working tree**, not an immutable tagged release. Subsequent edits in this archive pass affect documentation/source copies only.

| Check | Captured result | Limits |
| --- | --- | --- |
| Baseline before current fixes | All 27 existing tests passed in 79.577 seconds. | Establishes the starting point; did not cover the subsequently demonstrated gaps. |
| Added targeted regressions | All seven new regression tests passed. | Behavioral cases, not performance or field validation. |
| Full suite after engine changes | `.venv/Scripts/python.exe -m unittest discover -s tests -v`: **40 passed in 72.961 seconds**. | Includes API, recording/playback and short real learning smoke tests. Does not certify the browser workflow or research validity. |
| API compilation | `npm run check:api`: passed. | Syntax compilation, not a hosted-service acceptance test. |
| Headless command | Three seeds completed; zero vehicle and pedestrian conservation errors in every run. | Explicitly synthetic, short experiment. |
| Whitespace check | `git diff --check -- backend simulation services tools tests`: passed. | Git emitted line-ending notices; no whitespace errors. |
| Frontend | Earlier production build/basic login, native scene, stream, follow-camera and pause were checked before later changes. | No current-source frontend build/browser acceptance captured in this checkpoint. |

Current suite:

| Test file | Passed | Coverage area |
| --- | ---: | --- |
| `tests/test_native_engine.py` | 7 | Network, lifecycle, motion, gaps/reservations, routing and signals. |
| `tests/test_native_experiments.py` | 12 | Configuration atomicity, reset/events, demand accounting, stop control, pedestrians/emergencies, warmup and CSV/headless execution. |
| `tests/test_native_integration.py` | 12 | API lifecycle, persistence, frames, recording/playback, controller binding and failure paths. |
| `tests/test_native_learning.py` | 2 | Gym/QL plus actual short DQL/PPO train/save/load/inference. |
| `tests/test_native_regressions.py` | 7 | New input, event-boundary, control/offset and playback regressions. |

Verified headless command:

```powershell
.venv/Scripts/python.exe -m tools.run_native_experiment --scenario data/scenarios/tagum_peak_event.json --duration 300 --warmup 20 --seeds 11 22 33 --output data/generated/experiments/native3_checkpoint_20260923.json
```

| Seed | Requested vehicles | Completed | Unfinished | Dropped | Vehicle/pedestrian conservation error |
| --- | ---: | ---: | ---: | ---: | --- |
| 11 | 100 | 20 | 80 | 0 | 0 / 0 |
| 22 | 108 | 23 | 85 | 0 | 0 / 0 |
| 33 | 117 | 28 | 89 | 0 | 0 / 0 |

The measurement window is 300 seconds after 20 seconds of warmup. Unfinished demand remains visible; completion of the command does not mean all trips finished or that traffic was uncongested. The output is under an ignored generated-artifact directory and must be copied explicitly if retained as evidence.

Historical context: earlier seven-test checks passed; an expanded run exposed playback-reset errors and a learning assertion incorrectly requiring an early phase switch. Those were corrected. The documentation pause left the final 27-test result unknown at that time. The captured baseline and 40-test run above now supersede that uncertainty; the old interrupted process itself was never used as proof.

The earlier technical-lead review was documentation-only: its structure/link checks passed and 133 source/dependency hashes were unchanged against its own baseline. That historical statement does not describe the later authorized engine changes.

## Important incomplete work and known limitations

1. **Complete the React scenario/model workflow.** Server updates now preserve omitted native settings, but the editor still needs native types/controls and a verified compatible model selector. A bare `rl` label is not a registered model choice.
2. **Accept the full evidence workflow.** Finish browser-based recording, replay, comparison and report/export checks; hand-check metric definitions and confirm labels/provenance match across views.
3. **Verify current 3D behavior.** Live frames now retain native closure IDs, total entity counts and render limits. Confirm the renderer uses these accurately. Mixed physics dimensions do not establish correctly sized visual assets. Native slow-zone detail still needs an explicit visual contract.
4. **Validate model fidelity.** The entire-junction reservation and single lane per direction can distort capacity. Mixed vehicle types do not imply lane changing, overtaking, motorcycle filtering or non-compliant pedestrians.
5. **Confirm academic scope and collect data.** The supplied map assumptions and demand are experimental/synthetic. Obtain dated Tagum observations, calibrate, then evaluate on held-out conditions; no RL improvement claim is established.
6. **Enforce bounded hosting.** One process-local live runtime is not a completed run-ownership or concurrent-operator design. Measure target-machine performance, authorization, backup/restore and failure recovery before deployment.
7. **Align the manuscript.** Both archived PDFs still specify SUMO/TraCI. Explain the native architecture, routing method, RL scope, study boundary, metrics, actual schema and limitations in the eventual submission.
8. **Audit historical modules before cleanup.** SUMO assets and old generic services remain. Do not reconnect them to active routes or delete unique evidence based only on matching filenames.

## Next delivery slices

| Order | Action | Completion evidence |
| --- | --- | --- |
| 1 | Preserve/verify the relocation checkpoint; confirm deadline and academic scope. | Complete source, manuscripts, required database/artifacts and agreed RL/data requirements. |
| 2 | Complete native settings and model selection in React. | Create/edit/reload/run preserves inputs and invokes the selected compatible model. |
| 3 | Accept save/replay/compare/export and current 3D. | Current build plus browser workflow, faithful state, consistent metrics and disclosed display limits. |
| 4 | Calibrate and conduct the required comparisons. | Dated data, credible baseline, matched inputs, held-out seeds, unfinished demand and uncertainty. |
| 5 | Complete release/recovery gates and manuscript alignment. | Measured operating bounds, fresh-location setup, restored backup and rehearsed defense workflow. |

Use [README](../README.md) for commands. Tests should use temporary databases. Existing API processes can still contain older Python code until deliberately restarted. Do not rerun training or broad tests solely because documentation changed; rerun appropriate checks after code/config changes or relocation.

## Files and artifacts to preserve

Preserve source and uncommitted/untracked changes, this folder's own `.git`, `data/networks/tagum_osm.json`, `data/networks/tagum_network.json`, scenario inputs and required database/models/recordings/reports. Git ignores several research-artifact locations; a fresh clone is not a complete data backup. Recreate `.venv` and Node dependencies at the destination.

Earlier SUMO or native smoke artifacts may be incompatible with `native-3`. Use the engine/network/model compatibility checks; do not bypass them based on familiar filenames. `data/native-verification.db` and smoke outputs are development evidence, not the canonical research dataset.

The [history and migration record](../PROJECT_HISTORY_AND_MIGRATION.md) contains a detailed move checklist, both codebases' inspected progress, every page of both manuscript text extracts, and links/hashes for exact PDFs in `docs/research_sources/`. It does not copy the entire old source or all its generated artifacts. Neither folder was moved and the parent project was not modified.

## Documentation maintenance and cleanup record

Keep four current working documents: `README.md`, `PROJECT_OVERVIEW.md`, `ARCHITECTURE_AND_PLAN.md` and this handoff. The owner's later request adds the separate historical archive `PROJECT_HISTORY_AND_MIGRATION.md`; it preserves a dated snapshot, rather than competing with this handoff for current status.

Earlier consolidation superseded `docs/ARCHITECTURE.md` and `docs/VALIDATION.md`. Earlier migration cleanup had removed the old master reference, Dash-to-React plan, standalone audit, initialization/flow guides and SUMO/RL status contracts inside SmartFlow. They are not restored. Parent documents remain historical evidence. `AGENTS.md` and skill/tool Markdown remain developer instructions.

Update the overview when purpose/scope changes, architecture when contracts/decisions change, this handoff after implementation/verification, and README for startup commands. Preserve the archived source chapters unchanged; write later manuscript revisions as separately identified versions.
