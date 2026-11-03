# SmartFlow Windows desktop implementation guide

Date: 2026-11-01 (Asia/Singapore)
Status (2026-11-04): development prototype integrated with main `1f3e6a5` (native-8). Source desktop suite 101 passed; frozen worker/backend/restore tests 7 passed on `desktop-shell-experiment-2e58fd33cde4`. NOT done: native-window acceptance, installer build, clean-profile install/offline/update/uninstall. Not LGU-ready. Unchecked boxes are unverified or open.
Branch: `codex/desktop-version`
Starting revision: `5de043a86781f7a94e77b946ea6f5996dc7af553`

Implementation requirements clarified November 2: collect the initial administrator credentials in a private native setup step before the normal backend starts; provide desktop workflows for reviewed-observation import and independent validation, after reconciling the stable study branch; verify a backup before stopping owned workloads and activating a restored data root, with restart and rollback on failure; and persist desktop preferences outside origin-scoped local storage so they survive port changes. These are required implementation and acceptance items, not completed features.

## 1. Goal and scope

Deliver an installable Windows application that opens the existing SmartFlow interface in its own window, starts its local Python backend automatically, and keeps user data across restarts and upgrades. The receiving PC must not need Git, Node, a separately installed Python interpreter, or developer commands.

Keep one codebase for browser and desktop use. React and the 2D canvas handle presentation; FastAPI and the native engine own simulation and learning. The owner removed 3D rendering from the current application. Packaging does not establish field validity or complete the two-site study.

This is a separate workstream while another agent implements and tests the study plan. Do not switch branches, install dependencies, build, stop servers, or edit files in that agent's checkout.

### Proposed first release defaults

- Windows 11 x64 is the initial acceptance target. Treat any Windows 10 support as a separately tested target; do not promise compatibility from framework support alone.
- One Windows user profile owns one local data directory.
- One application instance per data directory and one API worker.
- CPU-only QL/DQL/PPO dependencies for the initial full package. Existing study gates remain mandatory. GPU/CUDA distribution is deferred.
- Retain scenarios, simulation, recording/replay, comparisons, reports, accounts, roles and backups.
- Field Observer stays a separate installation initially. Accept its reviewed exports through SmartFlow's supported import workflow.
- Offline operation after installation for bundled assets and supported local workflows.
- No cloud hosting, LAN service, public port, automatic updater, new vehicle classes, or sidebar redesign in this task.
- Build a small simulation-only proof first; it is not the final full-feature package.

These defaults are implementation assumptions, not claims of stakeholder approval. Clarify only if a requirement changes installer scope, storage ownership, GPU support, or distribution.

## 2. Recommended architecture

Prototype pywebview with the EdgeChromium/WebView2 renderer, PyInstaller one-folder packaging, then an Inno Setup installer. Pin tested versions in the desktop build environment. Switch to Tauri only if the prototype demonstrates a concrete blocker; avoid maintaining two desktop shells.

Proposed process structure:

```text
SmartFlow.exe                        desktop supervisor + WebView2 window
  |
  +-- SmartFlowWorker.exe serve      one local FastAPI/Uvicorn process
         |
         +-- SmartFlowWorker.exe train-ql / train-dql / train-ppo / evaluate
```

These executable names and modes are proposed interfaces, not existing commands.

The server supplies the compiled React site and existing API/WebSocket routes from the same loopback origin. Never load the application from file:// and assume HTTP authentication will work unchanged. Keep the UI on the main GUI thread; launch and monitor backend processes separately.

Bind only to 127.0.0.1. Have the server bind a free port itself, then communicate its actual address and a launch identity through private IPC. Do not find a free port, release it, and assume it remains available. A readiness handshake must identify this backend instance, not merely accept any service returning HTTP 200.

The desktop UI needs no general-purpose JavaScript-to-Python bridge. If a narrow bridge becomes necessary for file dialogs, expose only explicit operations to the trusted local application.

### Storage layout

Use a writable, user-specific location such as:

```text
%LOCALAPPDATA%/SmartFlow/
  config/
  data/
    smartflow.db
    networks/
    sites/                 mappings, criteria and ledgers
    imports/
    models/
    recordings/
    jobs/
    reports/               immutable validation/research evidence
    backups/
  logs/
  webview/
```

Finalize paths against existing artifact consumers before implementing them. Prefer a coherent data root beneath the database's parent so backup containment remains understandable. Do not add a parallel layout without updating all consumers.

Installation resources are read-only. Never write user records beside the executable, inside Program Files, or into PyInstaller's extraction directory. Copy seed resources only on first use; never overwrite edited networks, criteria, ledgers or existing evidence on startup.

A package installs a fresh database by default. Moving the owner's existing research database is a separate explicit backup/import operation, never an automatic copy from the development checkout.

## 3. Source-specific issues already identified

Recheck these at the chosen implementation revision because the other agent is changing the project.

| Area | Current dependency to address |
| --- | --- |
| `src/api/client.ts` | HTTP pages default to port 8000. Desktop same-origin requests must use the actual bound port. Keep browser-development defaults working. |
| `run_api.py` | Development startup supplies a default secret and admin password. Do not invoke this bootstrap unchanged in a distributed desktop app. |
| `config.py` | Database defaults are relative to source; production expects HTTPS. Introduce a deliberate desktop-loopback profile without weakening hosted production checks. |
| `backend/main.py` | Needs desktop-specific static frontend serving with API and WebSocket routing preserved. |
| `services/rl_training_service.py` | Launches .venv/python or sys.executable with script paths and repository cwd. A frozen executable is not a Python interpreter. |
| `simulation/road_network.py`, `simulation/network_registry.py` | Default network paths depend on repository layout. |
| `services/study_gate.py` | Study-site detection depends on mapping-file presence; omitted package resources must not make a study site appear unrestricted. |
| `services/site_validation.py` | Engine identity scans simulation source files; revision lookup calls Git. Freezing must not create an empty-source digest or silently lose provenance. |
| `services/backup_bundle.py`, `database.py` | Source roots, artifact locations, persisted paths and restore rewriting must work outside the checkout. |
| Imports, training tools, report generators | Audit every output path and subprocess, not only DB_PATH. |
| Frontend exports and backups | Browser downloads and WebSockets must work inside WebView2, not merely in Chrome. |

Current contract in AGENTS.md: native-7, native-local-20-v4, phase-service-5-v2, and recorded phase_plan. Reconcile against current source before coding. Keep legacy artifacts as history and preserve incompatibility errors.

## 4. Branch isolation and later synchronization

The desktop worktree starts from a committed snapshot. It does not contain the other agent's uncommitted changes, ignored data, dependencies or later commits.

Before each work session:

```powershell
git status --short --branch
git branch --show-current
git log -5 --oneline
```

Work only when the checkout is the intended desktop worktree and its branch is codex/desktop-version. Keep dependencies, temporary test data, logs and build output in this worktree or its dedicated scratch directories.

After the study agent reaches a stable, committed, verified checkpoint:
1. Review the incoming commits and their updated contracts.
2. Commit the desktop work in small, coherent commits.
3. Merge the explicitly chosen study commit into this branch; do not follow a moving main blindly.
4. Resolve conflicts by preserving study behavior and the thin desktop adapters.
5. Rerun the affected source tests and packaged smoke checks.
6. Record the integrated source revision and evidence.

Do not cherry-pick every study commit individually or make another copy of the engine. Do not modify the other agent's branch or working files. Push, merge back to main, public distribution and signing-key use are separate actions, not part of writing this guide.

## 5. Implementation tasks and acceptance

All tasks below are initially unchecked. Implement in dependency order and record actual results, not expected counts.

### D1 — Freeze a packaging baseline and build environment

- [ ] Inventory resource files, external downloads, output paths, dynamic imports and all worker commands.
- [x] Record the chosen source SHA and whether tracked changes are present. _(verified 2026-11-04, see progress record)_
- [ ] Create a dedicated desktop virtual environment and pinned requirements; do not install into the other checkout's environment.
- [ ] Verify compatible Windows wheels for the selected Python version, ML stack, pywebview and PyInstaller.
- [ ] Use CPU-only PyTorch dependencies intentionally; do not silently pull a CUDA distribution.
- [ ] Inspect licensing/redistribution requirements for assets and dependencies.

Acceptance: a documented baseline, resource inventory and reproducible environment. Do not bundle the current data folder wholesale.

### D2 — Separate resources from writable data

Proposed module: `desktop/paths.py`; shared path helpers may live in services where appropriate.

- [x] Resolve application resources, persistent data and scratch files independently of cwd. _(verified 2026-11-04, see progress record)_
- [x] Apply startup configuration before importing modules that cache configuration at import time. _(verified 2026-11-04, see progress record)_
- [ ] Preserve existing web defaults unless the desktop launcher explicitly selects its profile.
- [x] Resolve database, imports, models, recordings, job logs, backups, network registry and study evidence consistently. _(verified 2026-11-04, see progress record)_
- [ ] Make fresh initialization idempotent and upgrades non-destructive.
- [ ] Prefer explicit desktop data-root selection for acceptance tests.

Acceptance: launch from a different directory and from a path containing spaces/non-ASCII characters; verify all writes stay within the test data root and installation resources remain unchanged.

### D3 — Preserve research identity and fail-closed gates

This is a release blocker, not optional documentation.

- [ ] Make study-site identity explicit and durable; missing mappings must block study work rather than reclassify the site.
- [ ] Resolve mappings, criteria, ledgers and reports from the desktop data/resource contract.
- [ ] Preserve engine-content identity. Initial conservative approach: bundle the exact engine source inputs used by the existing digest and verify a non-empty, complete inventory against a build manifest.
- [ ] Record source revision in build metadata so Git is not needed on the user's PC.
- [ ] Any future manifest-based identity replacement must preserve equivalence tests and detect altered/missing assets; do not return a constant hash or trust an unchecked manifest.
- [ ] Include the relevant evidence in backup/restore.
- [ ] Never enable --synthetic-smoke-test by default or expose it as a normal study bypass.

Acceptance: package with mappings absent, evidence missing, mismatched identity, changed phases or stale validation refuses study training/final evaluation. Source and frozen builds of the same approved revision compute the same intended engine identity. Synthetic fixtures remain visibly synthetic.

### D4 — Serve the frontend from the local backend

Proposed module: `desktop/server.py`.

- [x] Serve the built frontend and static assets using the same origin as API and WebSocket routes. _(verified 2026-11-04, see progress record)_
- [ ] Preserve API errors; SPA fallback must not turn /api or asset failures into index.html.
- [ ] Make API and WebSocket URL resolution support the runtime desktop origin while preserving Vite and hosted configurations.
- [ ] Keep normal authentication and permissions.
- [x] Add a desktop-only loopback profile with exact Host/Origin checks, bounded allowed origins and no wildcard CORS. _(verified 2026-11-04, see progress record)_
- [ ] Use a private launch handshake and authenticated application routes; guard state-changing endpoints against foreign web origins.
- [ ] Never expose a client-readable session secret or administrative token in bundled JavaScript.
- [ ] Keep remote production HTTPS requirements unchanged. Document and test cookie behavior for the loopback profile.

Acceptance: login, authenticated API requests and WebSockets work on a non-8000 port; foreign-origin state changes are rejected; hosted configuration tests remain valid.

### D5 — Build the shell and process lifecycle

Proposed modules: `desktop/launcher.py`, `desktop/lifecycle.py`.

- [x] Start the backend hidden, with reload disabled and exactly one worker. _(verified 2026-11-04, see progress record)_
- [ ] Wait for the authenticated readiness handshake with a bounded timeout.
- [ ] Open pywebview using EdgeChromium; do not fall back silently to the obsolete renderer.
- [ ] Detect missing WebView2 and show actionable installation guidance.
- [x] Use a per-data-root single-instance lock; a second launch should focus the existing instance or show a clear message. _(verified 2026-11-04, see progress record)_
- [ ] Handle startup failure, backend crash, stale locks and log location visibly.
- [ ] Opening external links must not navigate the privileged application window to untrusted sites.
- [ ] Closing during simulation/training offers a clear choice to continue or stop safely; bounded shutdown must stop only the app's own process tree.
- [x] Use a Windows job object or another tested lifecycle mechanism to prevent orphaned workers if the shell crashes. _(verified 2026-11-04, see progress record)_

Acceptance: startup, duplicate launch, crash recovery and closure leave no unwanted server/worker. Never kill arbitrary python.exe processes.

### D6 — First-run setup and durable user data

- [x] Generate a unique persistent installation secret. _(verified 2026-11-04, see progress record)_
- [ ] Provide first-run administrator setup without distributing the development password.
- [ ] Restrict setup to a private one-time bootstrap flow; never expose an unprotected general admin-creation endpoint.
- [ ] Decide and test persistent login/session behavior, especially across dynamic port changes.
- [ ] Keep account permissions and password rules.
- [ ] Label the application version, engine contract, data location and diagnostic-log location in an appropriate existing screen.

Acceptance: fresh install creates an account securely; second launch does not reset it; an update does not replace the secret or database.

### D7 — Freeze and test a minimal vertical slice

Proposed outputs: `desktop/SmartFlow.spec`, `desktop/worker_entry.py`.

- [ ] Build on Windows as a one-folder distribution first.
- [ ] Bundle compiled React, 2D assets, fonts, metric definitions, networks/registry and necessary study resources explicitly.
- [ ] Keep developer databases, credentials, raw field recordings, .git, node_modules, caches and unrelated test artifacts out.
- [ ] Install/run the folder on a clean Windows user profile without Python/Node/Git.
- [ ] Verify login, a clearly synthetic scenario, 2D simulation, saved recording and replay with internet disconnected.

Acceptance: record the source SHA, package hash, test environment, startup time and measured disk/RAM usage. This slice does not certify the full installer or ML functionality.

### D8 — Adapt training and evaluation workers

- [x] Introduce an allowlisted command factory for source and frozen execution. _(verified 2026-11-04, see progress record)_
- [ ] Dispatch named worker modes to the existing training/evaluation entry points. Do not execute arbitrary scripts passed from the UI.
- [ ] Preserve flags, scenario snapshots, cancellation, progress parsing, checkpoints, artifact registration and study gates.
- [x] Initialize multiprocessing.freeze_support early in frozen entry points and verify child processes do not recursively launch the desktop shell. _(verified 2026-11-04, see progress record)_
- [ ] Give worker processes console-capable stdout/stderr for log capture, while hiding their windows.
- [ ] Audit Python module discovery, Torch/SB3 dependencies, device selection and CPU checkpoint loading.
- [ ] Preserve one-compute-workload admission and state ownership.
- [ ] On a synthetic non-study fixture, run tiny QL, DQL and PPO jobs, load their models, evaluate, cancel and resume where supported.
- [x] Confirm unvalidated study jobs still fail through all packaged entry points. _(verified 2026-11-04, see progress record)_

Acceptance: real frozen worker paths pass, not just source-mode tests or mocked subprocess calls. Long training and final study evaluation are not needed for packaging acceptance.

### D9 — Files, exports and recovery

- [ ] Test CSV/JSON exports, backup downloads and save dialogs in WebView2.
- [ ] Test import file selection and browser permission/error flows.
- [ ] Verify manifest, model and recording paths survive installation-root changes.
- [x] Restore a backup into a separate desktop data root, then reopen scenarios, users, models, recordings and study evidence. _(verified 2026-11-04, see progress record)_
- [ ] Maintain version/network/phase compatibility checks and resource containment.
- [ ] Test insufficient disk, corrupt imports and interrupted writes without replacing existing research evidence.

Acceptance: restored workflows function and hashes/identities are preserved or an explicit incompatibility is reported. The production research database is never used as a scratch fixture.

### D10 — Build the installer

Proposed files: `desktop/installer/SmartFlow.iss`, `scripts/build-desktop.ps1`.

- [ ] Package the verified one-folder output into a Windows installer with Start menu and optional desktop shortcuts.
- [ ] Prefer a per-user installation and no administrator requirement for normal runtime.
- [ ] Detect WebView2. Support its standalone offline installer when offline installation is promised; a download-only bootstrapper does not satisfy that claim.
- [ ] Check other runtime prerequisites discovered by clean-machine tests.
- [ ] Prevent an update from replacing binaries while that installation is running.
- [x] Preserve data on uninstall by default; any data removal must be explicit and limited to the verified SmartFlow data root. _(silent uninstall kept user data, 2026-11-04; same profile)_
- [ ] Recheck installer tooling terms and include dependency/asset notices.
- [ ] Record whether the build is signed. Do not promise warning-free installation for an unsigned package.

Acceptance: install, first launch, update and uninstall on a clean target. No claim of an installer until its actual output has been tested.

### D11 — Upgrade and rollback

- [x] Back up before schema migrations; stage changes so an interruption cannot leave the only database copy unusable. _(verified 2026-11-04, see progress record)_
- [x] Reject incompatible downgrades clearly; restoring old binaries alone is not database rollback. _(verified 2026-11-04, see progress record)_
- [ ] Preserve edited networks and reports while versioning new bundled defaults.
- [ ] Reconcile orphaned jobs using existing recovery behavior.
- [ ] Test upgrade with populated synthetic records and restore to a compatible prior version.

Acceptance: an upgrade retains accounts, scenarios, models, recordings and evidence; a failed migration has a documented recovery path.

### D12 — Full acceptance, handoff and documentation

- [ ] Integrate the stable study checkpoint before final desktop acceptance.
- [ ] Run applicable backend tests, frontend tests, TypeScript, lint and build on the integrated source.
- [ ] Run desktop-specific lifecycle, path, security, worker, export, backup and upgrade tests.
- [ ] Run actual packaged UI acceptance on a clean Windows target, with network disconnected for promised offline workflows.
- [ ] Capture build manifest, dependency versions, hashes, known limitations and measured operating bounds.
- [ ] Update progress and architecture after verified implementation; this guide alone is not evidence.
- [ ] Provide installation, first-run, backup, update, troubleshooting and uninstall instructions for an LGU operator.

Acceptance: the checklist below is backed by dated results. Mark unavailable-machine checks as outstanding, not passed.

## 6. Suggested new files

These are proposed paths; none exists merely because it is listed here.

```text
desktop/
  __init__.py
  launcher.py
  server.py
  lifecycle.py
  paths.py
  worker_entry.py
  SmartFlow.spec
  installer/SmartFlow.iss
requirements-desktop.txt
requirements-desktop-build.txt
scripts/build-desktop.ps1
tests/test_desktop_paths.py
tests/test_desktop_lifecycle.py
tests/test_desktop_origin.py
tests/test_desktop_workers.py
tests/test_desktop_evidence.py
docs/DESKTOP_INSTALLATION.md
```

Keep generated package and build outputs ignored. Keep reusable source fixes in ordinary shared modules where appropriate. Before touching a shared file, inspect new work from the study branch and minimize overlapping edits.

## 7. Verification commands and release checklist

Use the desktop worktree's own dependencies. The following are existing source checks; they do not prove a frozen build works:

```powershell
.venv/Scripts/python.exe -m pytest tests -q --basetemp tmp/desktop-acceptance
npx.cmd vitest run
npx.cmd tsc -b
npm.cmd run lint
npm.cmd run build
```

Use a new scratch location per run if prior artifacts need preserving. If sandbox temp errors occur, redirect TEMP/TMP to a dedicated writable worktree folder before launching the tests. Do not set a real research database as a suite-wide environment override.

The future build script must expose a documented command for a pinned CPU package, produce a manifest and return a nonzero exit code on failures. Do not publish a placeholder command as usable before the script exists.

Final acceptance matrix:

| Check | Required evidence |
| --- | --- |
| Fresh standard Windows user, no developer tools | Installer and first login succeed |
| Offline installed runtime | Site selection, 2D simulation, recording/replay and local exports work |
| WebView2 missing | Installation handles prerequisite or explains the blocking condition |
| API origin / WebSocket | Actual runtime port works; unrelated local/remote origins do not gain access |
| Duplicate launch / port conflict | No competing backend writes the same data |
| Worker smoke | QL/DQL/PPO launch, logs, cancellation and supported resume work frozen |
| Research protection | Missing/stale evidence blocks; original contracts and phase checks remain |
| Process failure | No orphan workers; interrupted state is reconciled truthfully |
| Backup/restore | Complete artifacts and evidence reopen in a new data location |
| Upgrade/uninstall | Existing data preserved; rollback procedure verified |
| Browser regression | Existing local-web and hosted configuration behavior stays supported |
| Performance | Startup, simulation rate, render behavior, memory and package size measured |

A desktop pass is software/distribution evidence only. It does not authorize final-seed evaluation, establish field accuracy, or establish suitability for controlling physical traffic signals.

## 8. What the owner needs to supply later

These do not block writing this guide or the first isolated prototype:
- Confirmation that an installable desktop package satisfies the adviser.
- A target LGU PC or clean test machine, Windows version and hardware.
- Whether deployment is per Windows user or requires a shared office database.
- Whether Field Observer must eventually ship in the same installer.
- Whether GPU support, public signing or remote updates are required.
- Explicit authorization for any migration of real research data or long training.

No timing promise is made before the minimal frozen slice and worker smoke tests. The heavy dependency and subprocess work determines the actual effort.

## 9. Official references

Checked 2026-11-01. Confirm versions again when implementation starts.

- [pywebview freezing](https://pywebview.flowrl.com/guide/freezing): Windows packaging and React build assets.
- [pywebview web engines](https://pywebview.flowrl.com/guide/web_engine): explicit EdgeChromium selection and runtime requirements.
- [PyInstaller runtime information](https://pyinstaller.org/en/stable/runtime-information.html): frozen resource paths and executable behavior.
- [PyInstaller common pitfalls](https://pyinstaller.org/en/stable/common-issues-and-pitfalls.html): multiprocessing and subprocess considerations.
- [PyInstaller specification files](https://pyinstaller.org/en/stable/spec-files.html): explicit bundle contents and build configuration.
- [Microsoft WebView2 distribution](https://learn.microsoft.com/en-us/microsoft-edge/webview2/concepts/distribution): runtime detection and offline deployment.
- [Inno Setup](https://jrsoftware.org/isinfo.php): installer tooling and current licensing information.

## 10. Handoff prompt

> Work only in the codex/desktop-version worktree. Read AGENTS.md, the current progress record and this guide. Re-audit the recorded source baseline and changes from the study implementation. Start with D1, then D2–D7 to prove an isolated desktop slice. Use synthetic data and separate dependencies. Keep study gates, compatibility checks, authentication and the browser app intact. Do not touch the other agent's checkout, production data or running jobs. Continue to workers, backups, installer and clean-machine acceptance in dependency order. Record actual results after each slice. Stop short of unsupported release claims when field evidence, target hardware or owner-authorized distribution is unavailable.
