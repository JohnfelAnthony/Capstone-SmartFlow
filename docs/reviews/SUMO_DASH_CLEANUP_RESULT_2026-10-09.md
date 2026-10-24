# SUMO/Dash cleanup implementation result

> **Scope update — October 24, 2026:** Emergency vehicles, emergency priority, emergency metrics and emergency RL features are excluded from SmartFlow by the owner’s decision. Any earlier descriptions below are historical and do not define current functionality. Current simulation classes are car, motorcycle, tricycle, bus and truck. Original manuscripts and research artifacts are preserved. See the October 24 scope decision in the architecture document.


Implementation began **2026-10-09**; completion evidence finalized **2026-10-10** (Asia/Singapore). Scope: the independent **SmartFlow** repository. Implementation follows the [revised cleanup plan](SUMO_DASH_CLEANUP_PLAN_2026-10-09.md).

The inactive implementation has been archived and removed. The primary database's **12 scenarios migrated successfully**, with **zero blocked rows**. Active scenario APIs now use canonical `network_id` and complete native `engine_config`. Legacy SQLite columns, research references, original manuscripts and historical artifacts remain preserved.

## Removed inventory and recovery

| Material | Removed files |
| --- | ---: |
| SUMO engine/config/state, obsolete simulation service and exporter | 5 |
| Earlier generic engine modules and two unused services | 11 |
| Historical `sumo/` network/configuration files | 19 |
| Unused static assets | 199 |
| Generated SUMO geometry exports | 3 |
| **Authored source/assets total** | **237** |
| Separately archived obsolete Python bytecode | 16 |

The 237 files contain **59,493,047 logical bytes**; the obsolete bytecode contains **186,390 bytes**. These are file sizes, not measured physical disk-space recovery. **24 empty directories** belonging to the manifested removal paths were also removed. Every deletion was restricted to verified workspace paths; files changed after the checkpoint would have prevented deletion.

The [exact manifest](SUMO_DASH_CLEANUP_MANIFEST_2026-10-09.json) records removed paths, sizes, SHA-256 hashes, changed-source hashes, protected-file hashes and recovery archive hashes. Keep the ignored recovery directory **`tmp/cleanup-20261009/`**; it is evidence and rollback material, not disposable build output.

| Recovery item | Contents |
| --- | --- |
| `tmp/cleanup-20261009/recovery.zip` | 597 source/asset files from the starting worktree, including pre-existing edits and authored untracked files; coherent SQLite snapshot; original scenarios; Git status/diff; checkpoint manifest |
| `tmp/cleanup-20261009/obsolete-cache-recovery.zip` | The 16 removed compiled files |
| `tmp/cleanup-20261009/database-pre-apply.db` | A second coherent primary-database snapshot immediately before applying migration |

Both ZIPs passed archive integrity checks and content/hash verification. The original recovery ZIP SHA-256 is **`3c33093a8b7af675c75bd87565667a4c5ed97eede4f338f3abf8a9bab848f9eb`**. Its starting source contains the owner's existing modifications; restoring from Git alone would lose those edits.

The final October 10 integrity pass rechecked all **597 archived source files**, both ZIPs, all **261 protected files**, the original history archive and the absence of all manifested removals. `final-integrity.json` records this pass. The final manifest distinguishes **44 changed pre-existing files** and **six newly created runtime/test/report files**, excluding the manifest itself.

`assets/auth.css`, all registered recording paths under `assets/generated/`, the native network and current renderers remain. The parent repository, Field Observer source/environments/weights and original manuscript copies were outside the removal scope. The **261-file protected manifest** still matches its original hashes. The original history archive also remains unchanged.

## Scenario migration and contract

[The per-scenario report](NATIVE_SCENARIO_MIGRATION_2026-10-09.json) retains each original row, resolved configuration, network fingerprint, warnings and migration status. IDs **22–33** were preserved, as were ownership, names, descriptions, flags and references.

Ten older aliases were mapped to the configured connected `tagum_network`; no alias is automatically mapped to a replacement network. Seven scenarios with explicitly boolean-disabled disruption objects now resolve. The other five retain their effective settings. Missing controlled-junction settings retain the engine's existing default and receive a warning; migration does not identify the correct physical study intersection or calibrate historical demand.

| Check | Result |
| --- | --- |
| Original primary rows versus recovery checkpoint | Identical immediately before apply |
| Dry run | 12 ready, 0 blocked; input database not written |
| Transactional primary apply | 12 migrated, 0 blocked |
| Repeat dry run | 12 unchanged, 0 ready/blocked |
| Original metadata and legacy column values | Preserved |
| Existing rows in all other tables | Preserved; only the migration report setting was added |
| SQLite integrity / foreign-key evidence | Integrity `ok`; foreign-key results unchanged |
| Isolated failure injection | Schema/row changes rolled back together |

The public scenario contract removes duplicate top-level densities/emergency controls, old IDs/presets and legacy disruption objects. Unknown legacy request fields receive a validation error. Native controls remain inside the complete normalized configuration, including nested plans, routing, demand, restrictions, events and the selected RL junction. Saved editing, runtime configuration, training/evaluation snapshots, imports and current native headless inputs use this contract.

Enabled, ambiguous, malformed or unmapped historical restrictions remain blocked until an explicit native mapping exists. The UI shows the specific migration error, disables execution/save and does not offer a default reset for these rows. A browser fixture with an enabled historical closure retained its original stored values after inspection. Canonical inputs ignore retained legacy recovery values; later native edits are not overwritten by repeated migration.

Immutable recording/model/training/calibration snapshots retain their existing `intersection_id` envelope. Engine/observation/action versions remain **`native-3`**, **`native-local-30-v1`**, **`protected-service-5-v1`**. The 21 registered historical recordings and 18 older model records were preserved and remain subject to compatibility checks; migration does not relabel them as native artifacts.

## Other implementation changes

- Native RL reads native vehicle/pedestrian runtime state and lane lengths. Dead TraCI readers and the native engine's unused connection placeholder were removed.
- Unused Flask session helpers and request probing were removed. Werkzeug hashing, password validation, active FastAPI permissions, sessions, CSRF/origin checks and expiry behavior remain covered. Audit logging accepts optional explicit client context.
- Obsolete SUMO/export/Dash configuration, misleading UI descriptions and the renderer's `sumoDx`/`sumoDy`/`sumoLength` names were removed. Renderer geometry, encoding and original line endings were preserved.
- Replay requires an explicitly registered path; it no longer guesses an assets-directory location. Historical explicit paths remain valid locations, with manifest compatibility checked separately.
- Lint/compilation exclude nested dependency/cache environments while retaining authored tool source. Standalone copying includes the auth stylesheet and independent Field Observer launcher/source, without environments or model caches.
- ZIP and SQLite-only restore rehearsals migrate the staged database. A fresh deeply nested installation exposed a Windows path-length failure for restored imported CSVs. Compact restore directory aliases now preserve filenames, job subtrees, sidecar relationships and verified bytes. `restore_layout.json` records the relocation; original bundles and live artifact paths remain unchanged.

## Verification evidence

Evidence is retained under **`tmp/cleanup-20261009/`**.

| Verification | Evidence / result |
| --- | --- |
| Final complete main application suite | `tests-acceptance-final.log`: **120 tests, 318.677 s, OK** |
| Focused restore/import/training regression suite | `tests-restore-final.log`: **34 tests, 146.757 s, OK** |
| Migration edge cases | `tests-migration-edge.log`: **13 tests, OK** |
| API compilation | `check-api-final.log`: passed |
| Explicit frontend typecheck | `typescript-final.log`: passed |
| Full frontend lint | `lint-final.log`: zero errors/warnings |
| Production build | `build-final.log`: passed; existing large-chunk warning remains |
| Separate fresh dependency installation | `standalone-2.log`: `npm ci`, new venv and requirements install completed; initial restore failures recorded |
| Separate-location full suite after repair | `standalone-final.log`: **120 tests, 264.402 s, OK** |
| Separate-location final compilation/typecheck/lint/build/API smoke | `standalone-finish.log`: passed |
| Deterministic before/after native comparison | `baseline-verification.json`: **12 scenarios / 36 states**, actors, metrics, RL observations/masks and QL encoding equivalent |
| Primary migration/database preservation | `migration-primary*.json`, `database-verification.json` |

The deterministic comparison excludes only the removed no-op `experiment.config.road_constraint` serialization field; it does not exclude actor/metric/observation differences. The comparison uses seeds and three captured native states per scenario. The same native network fingerprint is retained: **`4b3c52533709121af916c7a3efc04ed1d44703295d095fe9ee53f461e19700cb`**.

Earlier failed runs are retained rather than presented as passes. They include the old API-fixture transition, sandbox restrictions, the Windows restore path failure, and an incorrect Windows command path in the temporary verification runner. Each was diagnosed; fixtures/restore layout/runner were corrected and relevant checks rerun. The fresh standalone environment installs the declared requirements independently; it does not borrow the application's existing venv.

The final source comparison matched **146 authored application/tool/test files** between this repository and the verified standalone installation, with **zero differences**. Documentation was finalized afterward. On October 10, the temporary verification ports had no listeners and the earlier verification tab was no longer present; the user's existing browser tab was preserved.

### Browser acceptance

An isolated upgraded database (`browser-upgrade.db`) and production preview/API ports **15179/18019** verified:

1. Login and the migrated 12-row library.
2. Edit/save/reopen of scenario #32: nested J1 green **22 s**, road0f closure at **10 s**, complete native settings retained.
3. Fixed-time live run #152, pause/stop, 2D and 3D rendering, one visible vehicle and the scheduled restriction.
4. Short QL job #4, compatible model #20, held-out scenario #24 and seed 101; evaluation runs #153/#154.
5. Explicit model selection and live QL run #155 at its selected junction.
6. A **20-second native recording #156**, 201 frames, explicit load/play and appearance in Runs & Reports.
7. A downloaded selected-run CSV (`browser-runs.csv`).
8. A saved/reopened **synthetic calibration record #1**, frozen native baseline/network fingerprint and honest zero-reference error handling.
9. Settings navigation and Search finding/opening that research record.
10. A deliberately unresolved historical closure: disabled Load/Live/Record/Save, specific mapping error, unchanged stored legacy values.

DOM evidence is in `browser-training.txt`, `browser-reports.txt`, `browser-calibration.txt` and `browser-blocked.txt`; screenshots include `browser-2d.jpg`, `browser-3d.jpg` and `browser-calibration.jpg`. Initial test-server/browser communication attempts failed during setup; the loopback production preview and subsequent workflows succeeded. Synthetic fixtures were added only to the copied database.

![Native 3D controller workflow](../../tmp/cleanup-20261009/browser-3d.jpg)

## Rollback procedure

No rollback is needed for the verified current state. If recovery becomes necessary:

1. Stop SmartFlow API/live/training/recording processes using the affected database. Preserve a **new coherent SQLite backup and current source diff** first; reverting the checkpoint would otherwise discard work created after October 9.
2. Verify the recovery ZIP against its SHA-256 in the manifest. Extract into a separate review directory first. Source paths are repository-relative; database/evidence entries are under `checkpoint/`. Verify extracted bytes against `checkpoint/manifest.json`.
3. Restore only the affected files listed by the cleanup manifest, using the archived starting-worktree versions. Do not reset unrelated user edits. The newly introduced runtime files are `services/scenario_migration.py` and `tools/migrate_native_scenarios.py`; remove them only as part of a reviewed source rollback. Added regression tests and result documents are separately identifiable.
4. Rehearse the archived source with **`checkpoint/database-before.db`** or `database-pre-apply.db` at an isolated path. Existing legacy columns are still present in the migrated primary, but changing source alone is not a complete database rollback.
5. Replace a live database only after confirming that subsequent scenario/run/research edits have been preserved. With all writers stopped, handle that database's WAL/SHM consistently; do not combine an old database file with newer WAL contents. Prefer coherent SQLite backup/restore APIs over copying an open database file.
6. Keep original recorded/model/manuscript artifacts unchanged. Removed source/static assets can be restored from the main ZIP; obsolete bytecode is separately recoverable but can normally be regenerated from source.
7. Run the relevant/full checks and isolated login/run/replay verification before returning to normal use. The migration CLI's dry run can inspect a restored database without starting the API.

The archived worktree includes pre-existing modifications and untracked source; a Git reset/recheckout is not a substitute for this recovery procedure.

## Remaining research work

This cleanup preserves native traffic behavior and software compatibility. Study intersection selection, representative demand, field calibration, independent validation, manuscript alignment and real-world controller effectiveness remain research work. RL still controls one selected junction; routing remains separate. The original manuscript PDFs/history were not rewritten.
