# Remove remaining SUMO/Dash implementation safely

> **Scope update — October 24, 2026:** Emergency vehicles, emergency priority, emergency metrics and emergency RL features are excluded from SmartFlow by the owner’s decision. Any earlier descriptions below are historical and do not define current functionality. Current simulation classes are car, motorcycle, tricycle, bus and truck. Original manuscripts and research artifacts are preserved. See the October 24 scope decision in the architecture document.


Audit and revision date: **2026-10-09** (Asia/Singapore). Intended implementation handoff: **GPT-6.1 SOL**.

Status: **Implemented; completion evidence finalized on 2026-10-10.** The [implementation result](SUMO_DASH_CLEANUP_RESULT_2026-10-09.md), [exact cleanup manifest](SUMO_DASH_CLEANUP_MANIFEST_2026-10-09.json) and [primary migration report](NATIVE_SCENARIO_MIGRATION_2026-10-09.json) record the completed work and recovery procedure. The original audit findings and proposed actions below remain the October 9 baseline; consult the result for current behavior and verification.

## 1. Direction, history and boundaries

Work from the independent **SmartFlow repository root**. Follow [AGENTS.md](../../AGENTS.md), [README](../../README.md), and the current [progress record](../PROGRESS_AND_HANDOFF.md). The September [implementation handoff](../../IMPLEMENTATION_HANDOFF.md) is a historical repair map; do not assume its old failures remain unresolved.

The [project history](../../PROJECT_HISTORY_AND_MIGRATION.md), sections 1–9, distinguishes:

1. The parent `trapik2` application: Dash/Flask, SUMO/TraCI, SQLite and older models/recordings.
2. The revised manuscript: stronger field-data, signal-planning and routing requirements, still specifying SUMO/TraCI.
3. The owner's later software decision: React/TypeScript/Vite, Three.js, FastAPI and the native Python `simulation/traffic_engine.py`.

Continue the native stack. Remove obsolete implementation without changing traffic behavior, RL observation/action semantics or research evidence. This cleanup is not a return to SUMO, an engine rewrite or proof of field validity. Keep the parent project and original manuscripts as history; no parent-directory cleanup is included.

Retain legacy SQLite columns and historical recording locations. Do not change 3D models, Field Observer functionality, study geography or RL scope. Current RL controls one selected junction; routing is separate. Manuscript alignment and field validation remain subsequent research work.

## 2. Verified audit baseline

The main database was inspected read-only. Static imports were followed from the native API, headless, training and evaluation entry points, with source/reference checks. “Unused” below means no active callers were found in those inspected paths; recheck callers before deletion.

| Material | Verified finding | Planned action |
| --- | --- | --- |
| Active simulation | `backend/simulation_runtime.py` imports native `TrafficEngine` | Preserve |
| SUMO implementation | Five obsolete files listed in section 5; imports remain within the legacy cluster | Archive and remove |
| SUMO networks | **19 files** under `sumo/` | Archive and remove |
| Earlier generic engine | **Nine modules**, plus two unused services | Archive and remove |
| Old static assets | **199 files; 58,804,742 bytes**, excluding `assets/auth.css` and `assets/generated/**` | Archive and remove only the manifested files |
| Generated SUMO geometry | **Three files, two unique contents**, listed in section 5 | Archive and remove all three |
| Active compatibility code | Legacy aliases/fields, optional Flask imports, unused TraCI branches in `simulation/rl_state.py`, obsolete configuration | Refactor with regression checks |
| Historical recordings | **21 registered paths** under `assets/generated/timelines/`; all files and manifests exist | Preserve files, manifests and registered paths |
| Scenario storage | **12 rows**, **10 legacy aliases**; `engine_config` column exists but every row contains `{}`; no canonical `network_id` column | Migrate and update fresh-database seeds |

The seven rejected scenarios are IDs **22, 23, 24, 25, 26, 27 and 31**. Each has nonempty legacy disruption objects containing `{"enabled": false}`. Calling the current `TrafficEngine.configure_from_scenario` rejects them; the other five rows resolve. An empty native configuration is not itself a failure: those five currently derive settings from legacy columns/defaults.

All 21 historical recording manifests lack a matching `native-3` engine version. Preservation is not playback compatibility. Keep the current rejection of incompatible artifacts; never relabel them or rewrite hashes to force acceptance.

### Corrections to the earlier plan

- Count **three geometry files**, including the duplicate root export, rather than two.
- Include the bypassed TraCI access branches in the active RL observation module; deleting the SUMO files alone does not remove them.
- Update seeds, database helper defaults and import/restore handling, not only existing rows.
- The scenario editor **already blocks saving after failed native-setting resolution** using `editConfigReady` and displays the error. Preserve this behavior as a regression requirement, not an outstanding fallback repair.
- Keep the current calibration/validation workspace and its saved run snapshots working through the contract migration.

### Verification captured during the audit

- `node_modules/.bin/tsc.cmd --noEmit -p tsconfig.app.json --incremental false`: passed.
- `npm.cmd run lint`: zero errors, one unused ESLint directive warning in `tools/field_observer/.venv/Lib/site-packages/matplotlib/backends/web_backend/js/mpl.js`.
- Five targeted tests passed in **4.353 seconds**: `NativeIntegrationTests.test_native_scenario_persistence_and_atomic_config_validation`, `test_scenario_edit_preserves_omitted_native_settings_and_can_clear_explicitly`, `test_legacy_recording_rejected_and_invalid_generation_marks_error`, `test_rl_observation_masks_and_native_model_round_trip`, and `NativeRegressionTests.test_legacy_disruption_details_are_not_silently_ignored`.
- Full application tests, production build, standalone installation and browser acceptance were **not rerun for this audit**. They remain cleanup completion gates.

## 3. Implementation order and recovery checkpoint

Keep scenario migration, file removal and contract refactoring as reviewable changes. Prioritize the seven unusable scenarios; do not start with a broad folder deletion.

1. **Capture recovery evidence.** Inspect `git status --short`, record the revision and preserve modified, untracked and ignored research files. A Git patch alone omits untracked files. Existing unrelated changes include application work, new research pages, skills and Field Observer; do not reset them.
2. **Prepare and test migration first.** Produce a per-scenario dry run on a coherent database snapshot. Implement/test the resolver and migration against isolated copies before changing the working database or removing compatibility paths.
3. **Remove confirmed inactive files as a separate batch.** Verify the archive, remove only manifested files, and recheck imports/references. This batch should not change simulation results.
4. **Complete the native contract and compatibility refactor.** Update every consumer and fresh-database seeds together. Apply the verified migration before strict native-only readers handle old rows; unresolved rows remain visible and blocked with a reason.
5. **Complete acceptance and record delivery evidence.** Include a clean-install path and an existing-database upgrade path; one cannot substitute for the other.

Create a recovery ZIP with original repository-relative paths, byte sizes and SHA-256 hashes for removal candidates and changed source. Read back every archived member and verify its digest before deleting its original. Archive outputs must not recursively include themselves. Before any recursive removal, verify resolved absolute targets are within this workspace and not a protected directory; on Windows use one shell and literal paths.

Use the existing backup facilities or SQLite backup API for a **coherent database snapshot**, accounting for active WAL state. Do not rely on zipping only a live `.db` file. Coordinate with running writers without terminating unrelated processes. Preserve all database-referenced artifacts and the field-observation directories; the application's referenced-artifact bundle is not a complete Field Observer backup.

Retain recovery archives outside the removal set and document how to restore both matching source and data. Protect database records, models/checkpoints, recordings/manifests, calibration records, field videos/exports, manuscripts, skills and `data/networks/`. No research-artifact relocation is part of this change.

## 4. Scenario migration and authoritative native configuration

### Migration rules

- Add canonical scenario `network_id` storage while **retaining existing legacy SQLite columns**. Preserve row IDs, ownership, names, descriptions, official/archive flags and references from runs/research records.
- Use a shared deterministic resolver for migration/import/restore. Record migration version, source values, resolved network/configuration, warnings and per-row status (`ready`, `blocked`, `unchanged`) in the report. A dry run must not write to its input database.
- Build complete validated configurations from legacy settings plus explicit `engine_config`, with explicit native values taking precedence. Preserve nested plans, demand, vehicle mix, routing, timing, events, limits and controlled-junction selection. Resolve missing defaults against the configured network and record the assumptions.
- Map recognized `tagum_1`, `tagum_2`, `tagum_3` aliases only when the connected `tagum_network` is configured. Never map these automatically onto a replacement network. These aliases do not establish which physical junction should be RL-controlled; preserve an explicit selection or report the existing default. Software migration does not make historical demand calibrated to the new geography.
- Empty disruption objects and objects explicitly declaring boolean `enabled: false` are inactive; retain their originals in recovery evidence. Do not treat strings such as `"false"`, missing flags on nonempty objects, malformed JSON or unsupported enabled settings as safely disabled. Require explicit native lane/event mapping for enabled or ambiguous disruptions and block unresolved execution.
- Resolve legacy `road_constraint` presets deliberately into lane closures, speed restrictions or events. Do not invent a physical lane mapping or silently clear an existing native restriction. Any unresolved mapping must appear in the report.
- Use transactional writes and idempotence: a repeated migration must not duplicate scenarios, overwrite later native edits or change already resolved configurations. Demonstrate rollback after a simulated failure on an isolated copy. Never mark blocked rows successfully migrated or silently replace them with defaults.

### Active contract after migration

- Scenario API writes/responses use metadata, `network_id` and complete `engine_config`. Native settings are authoritative. Remove duplicate top-level density/emergency settings, `road_constraint` and the four legacy disruption objects from the active scenario contract; preserve density/emergency behavior inside `engine_config` and use explicit native disruptions.
- Update database creation/seeding and helper defaults alongside migrated rows. A fresh database must create canonical scenarios directly, not recreate empty native configurations. Restarting an upgraded database must not add duplicate official scenarios.
- Update scenario editing, dashboard configuration, native-options resolution, training/evaluation snapshots, CSV imports, headless/CLI inputs and reporting consumers together. Update tests that intentionally exercise the old API contract while retaining tests for supported migration boundaries.
- Restrict live configuration and geometry requests to canonical IDs. Reject unknown/legacy fields clearly rather than letting request-model defaults silently discard them. Keep legacy interpretation at explicit migration/import/restore boundaries.
- Preserve failed-resolution save blocking in `src/components/scenarios-page.tsx`. Test that an error leaves stored settings unchanged and cannot save a default replacement.
- Preserve immutable historical run/model/training/calibration snapshots and hashes. The new scenario API name does not require mechanically renaming `intersection_id` in old frame/model formats. Use an explicit boundary adapter where needed; do not casually change native contract versions or bypass compatibility checks.

## 5. Exact inactive-file removal scope

Create an explicit file manifest at implementation time. The following counts describe the audit checkpoint, not permission to delete new files that later appear in these folders.

**Five SUMO implementation files:**

```text
simulation/sumo_engine.py
simulation/sumo_config.py
simulation/sumo_state.py
services/simulation_service.py
tools/export_sumo_visual_network.py
```

**Nine earlier engine modules and two services:**

```text
simulation/engine.py
simulation/network.py
simulation/agents.py
simulation/constants.py
simulation/controllers.py
simulation/metrics.py
simulation/pedestrians.py
simulation/traffic_light.py
simulation/vehicles.py
services/scenario_service.py
services/metrics_service.py
```

Archive/remove the 19 inspected files under `sumo/` and the 199 inspected static files under `assets/`. **Retain `assets/auth.css`**, dynamically imported by `src/components/auth-pages.tsx`, and **everything under `assets/generated/`**. Do not remove the entire assets directory.

**Three generated SUMO geometry files:**

```text
data/generated/visual_network.json
data/generated/visual_networks/tagum_1.json
data/generated/visual_networks/tagum_2.json
```

At audit time the first two share SHA-256 `cadc4cc8b840646403a20ca2e085155635c01ff1ce49c994170853b05072ae28`; `tagum_2.json` has `10651d66853882de3b940480c14c2ce6e059b781ca1e84fb335ffaf192f86472`. Recompute before archival. Active geometry is built from `simulation/road_network.py` through `services/visual_network_service.py`, not these exports. **Other `data/generated/` contents remain protected.**

## 6. Remove residual coupling without changing native behavior

- Preserve `simulation/traffic_engine.py`, native road/demand/signal logic, `services/simulation_flow.py`, render serializers, controller services, timeline generation, and both current renderers.
- Remove unused TraCI branches in `simulation/rl_state.py` and the corresponding `TrafficEngine.connection` placeholder after checking callers. Use native vehicle/pedestrian snapshots and lane lengths. Verify identical observations, QL state encoding, valid-action masks and emergency proximity for the same native states. Keep observation ordering, normalization, action ordering and `native_contract()` unchanged unless a separately justified behavior change is required.
- Preserve password hashing/verification, password-strength checks, route permissions and active API session/CSRF logic. Remove unused Flask session/authentication helpers only after checking actual callers. **Keep Werkzeug**, which still provides the active password hashing functions.
- Remove Flask request probing in `database.log_audit_event`; accept optional explicit IP/user-agent metadata while preserving current callers. HTTP handlers may supply request metadata; workers may omit it. Do not introduce new trust in arbitrary forwarded headers.
- Remove unused SUMO supervisor, visual-export and Dash configuration constants after a reference check. Preserve settings still consumed by FastAPI, including session timeout and secure-cookie configuration.
- Replace stale user-facing Dash descriptions and rename the 2D renderer's `sumoDx`, `sumoDy`, `sumoLength` variables without changing geometry. Preserve historical mentions and useful incompatible-artifact error messages; a zero-keyword search is not the acceptance criterion.
- Remove playback's implicit assets-directory search only after verifying every active caller provides a registered path. Missing paths must give a clear error. Explicit paths under `assets/generated/timelines/` remain valid file locations; compatibility still depends on the manifest/content.
- Scope lint ignores to generated/dependency directories, including the nested Field Observer `.venv`, rather than editing third-party JavaScript or excluding authored tool source indiscriminately.
- Check standalone packaging paths after removals; retain the required auth stylesheet and independent Field Observer source/launcher. Do not package dependency environments or model caches as application source.

## 7. Targeted source-reading map

Read applicable callers/consumers rather than the entire repository.

| Work | Current paths to inspect |
| --- | --- |
| Persistence, seeds and scenario API | `database.py`, `backend/main.py`, `backend/schemas.py`, `backend/security.py`, `services/scenario_storage.py` |
| Native resolution and network identity | `simulation/traffic_engine.py`, `simulation/scenario_config.py`, `simulation/road_network.py`, `services/native_scenario_service.py`, `services/visual_network_service.py`, `services/scenario_identity.py` |
| Frontend contracts and usage | `src/api/scenarios.ts`, `src/api/native-scenario.ts`, `src/api/simulation.ts`, `src/api/visual-network.ts`, `src/components/scenarios-page.tsx`, `dashboard-page.tsx`, `rl-training-page.tsx`, `native-scenario-controls.tsx` |
| Training/evaluation/headless | `services/training_settings.py`, `services/rl_training_service.py`, `services/rl_reporting_service.py`, `tools/training_inputs.py`, `tools/train_ql.py`, `tools/train_dql.py`, `tools/train_ppo.py`, `tools/evaluate_controllers.py`, `tools/run_native_experiment.py` |
| RL semantics and artifacts | `simulation/rl_state.py`, `simulation/rl_reward.py`, `simulation/rl_env.py`, `simulation/rl_policy_runtime.py`, `simulation/model_contract.py` |
| Sessions and audit | `auth.py`, `config.py`, `database.py`, `backend/security.py`, `backend/main.py` |
| Recording, restoration and research | `simulation/timeline_engine.py`, `services/timeline_generator.py`, `services/timeline_artifacts.py`, `services/backup_bundle.py`, `backend/research_routes.py`, `src/components/calibration-validation-page.tsx` |
| Packaging/current renderers | `tools/verify_standalone.py`, `eslint.config.js`, `src/components/auth-pages.tsx`, `src/components/simulation-canvas-2d.tsx`, `src/simulation/SimulationScene3D.tsx` |

## 8. Acceptance and completion evidence

### Migration and behavior checks

- Test all 12 current rows on isolated database copies. The seven explicitly disabled cases must resolve after migration. The other five must retain equivalent effective native settings. Compare actual before/after resolved values, not merely successful HTTP responses.
- Include explicit native overrides, controlled-junction preservation, nested settings, disabled/enabled/ambiguous disruptions, malformed JSON, unknown aliases, a configured replacement network, repeated migration and transactional failure/rollback.
- Test fresh database seeds, restart without duplicates, and restoring/importing older data through the documented migration boundary. Unresolved scenarios remain understandable in the UI and unavailable for execution.
- Verify create/edit/reload, failed-resolution blocking, live runs, training snapshots, evaluation, imports and recording preserve complete native configuration. Compare deterministic same-seed native behavior across this cleanup.
- Verify native RL observations/masks and compatible model loading; retain clear rejection of incompatible models/recordings. Never use the 21 historical artifacts as expected-success native replay fixtures.
- Verify explicit registered recording paths, current native replay, artifact hashes, coherent backup/restore and calibration record exports/snapshots.
- Verify login/logout, password changes, permissions, session expiry, CSRF and audit logging. Neither removing Flask helpers nor renaming scenario fields may weaken access controls.

Existing coverage to extend: `tests/test_native_integration.py`, `test_native_regressions.py`, `test_native_experiments.py`, `test_training_worker.py`, `test_operations.py`, `test_portable_inputs.py`, `test_shared_session_and_import.py`, and `test_research_workspace.py`. Add focused migration and observation-equivalence regressions. Use isolated databases/artifact directories, including subprocesses.

### Full acceptance

Run from the SmartFlow root with the main application environment:

```powershell
.venv/Scripts/python.exe -m unittest discover -s tests -v
npm.cmd run check:api
node_modules/.bin/tsc.cmd --noEmit -p tsconfig.app.json --incremental false
npm.cmd run lint
npm.cmd run build
```

Then rehearse a standalone installation using `tools/verify_standalone.py` with a new nonexistent target directory. Audit/update its contract assumptions before using it. Follow with isolated browser verification: login, scenario edit/save/reopen/run, fixed-time and registered-model selection, short training/evaluation, native recording/replay, reports, calibration-record access and both 2D/3D renderers. Include an upgrade from a copied existing database; a clean installation alone does not prove migration.

Recheck imports/references after each removal batch. Active code must have no SUMO/TraCI/Dash/Flask runtime dependency, but historical documents and incompatibility messages may retain those names. Do not infer completion from syntax/build checks alone.

Completion requires a final inventory of removed paths and hashes, verified recovery archives, per-scenario migration results, preserved-artifact hash checks, targeted/full test outputs, browser/standalone evidence and a documented rollback procedure. Update current README/architecture/progress records with dated facts. Keep archived manuscripts/history intact; date any annotations instead of rewriting historical claims.

## 9. After cleanup

Return to capstone work: align the current manuscript and diagrams with the native architecture, finalize study intersections and RL coverage, collect the single-camera pilot, review counts/classes/signals/queues, and assess native traffic behavior against observations before larger training comparisons. This plan establishes software maintenance scope; it does not establish representative demand, calibrated junction capacity or real-world controller effectiveness.

Suggested prompt for the implementation chat:

> Implement `docs/reviews/SUMO_DASH_CLEANUP_PLAN_2026-10-09.md` from the SmartFlow root. Follow AGENTS.md, inspect the current working tree, and preserve unrelated changes. Start with recovery evidence and the scenario-migration dry run, then complete the documented removal/refactor stages and acceptance checks. Keep legacy SQLite columns, historical recording paths, manuscripts, field data and the native engine/model contracts. Report verified results, blocked legacy mappings and remaining limitations; do not label synthetic checks as field validation.
