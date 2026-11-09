# SmartFlow for Windows: operator instructions (development build)

Status: **development build, unsigned, not LGU-ready.** It has not passed clean-profile acceptance; see `docs/PROGRESS_AND_HANDOFF.md` for what was and was not tested. Data produced here is for software testing, not field evidence.

## Requirements
Windows 11 x64, about 2 GB free disk, and the Microsoft WebView2 runtime (included with Windows 11; the installer installs it only if it was built with the offline WebView2 installer). No Python, Node or Git is needed. Map tiles need internet; the simulator does not.

## Install
1. Run `SmartFlow-Setup-<version>.exe` as the normal user (no administrator needed). Windows SmartScreen will warn because the build is unsigned; that is expected for this build.
2. Choose Start menu shortcut (desktop shortcut optional). Finish.

## First run
1. Open SmartFlow from the Start menu. Read the development-build notice.
2. When asked, set the administrator password (twice). Weak passwords are refused; correct and retry.
3. Sign in. A second SmartFlow on the same Windows user is refused or focuses the first.

## Import trained models

In **RL Training → Import model**, choose a QL `.json` or select the DQL/PPO `.zip` and matching `.metadata.json` together. Confirm that you trust the files, then choose **Import model**. SmartFlow identifies the algorithm, checks the network and phase order, and registers compatible files under the active data folder. An administrator must perform this action. Use only neural archives you trust, because loading a DQL or PPO archive can execute code.

## Site A starter comparison

The next desktop build is configured to add the 455-episode QL model, the 325-episode DQL model, and their comparison library once per database on first startup. Open **Runs & Reports** or **Compare Runs** and look for **Site A starter comparison**. The 300-second replays use seed 101 and a 120-second warm-up. Fixed-time and DQL are the original web recordings #230 and #231. QL was recorded separately against the same inputs. These are synthetic simulations.

For the next build, keep the prepared `tmp/desktop-starter-content` directory available in this worktree. It contains only the selected models, recordings and their catalog, and is kept outside Git. To regenerate it from the original web data and the isolated QL recording, use a new empty output location:

```powershell
& .\.venv-desktop\Scripts\python.exe -m desktop.prepare_starter_content --web-root "C:\path\to\SmartFlow" --ql-database "tmp\starter-ql-recording\smartflow.db" --output "tmp\desktop-starter-content-new"
```

Pass the resulting directory as `-StarterContent` when building the installer. A full installer build requires the catalog. An existing desktop database receives the starter records additively. A custom Site A geometry with a different fingerprint keeps its own library and skips this starter content.

## Where things are
Data: `%LOCALAPPDATA%\SmartFlow` (database, models, recordings, evidence, logs, pre-start snapshots in `data\pre-start-snapshots`). Program: `%LOCALAPPDATA%\Programs\SmartFlow`. Logs for startup problems are in the data folder's `logs`.

## Backups
Backup & Restore (administrator): create and download a backup ZIP regularly and copy it off the PC. "Restore & restart" verifies the ZIP first, refuses while a simulation or training is running, and rolls back to the previous data if the restored copy does not start.

## Update
Close SmartFlow (setup refuses to run while it is open), then run the newer setup over the old one. Data and password are kept. Before every start the app saves a database snapshot (newest 10 kept). A database from a newer SmartFlow is refused rather than opened.

Version 0.2.0-dev moves unedited 0.1.x study networks to the current Site A and Site B revisions and keeps their old geometry in the network history. Custom or restored network selections are kept. Check the active network before running an older scenario or model. Compare Runs can continue to use compatible recordings tied to preserved geometry.

The Windows package uses the same reviewed-count import in Scenarios as the web app. Run Field Observer separately to create its five input files.

## If startup fails after an update
1. Close SmartFlow. 2. In PowerShell:
```powershell
& "$env:LOCALAPPDATA\Programs\SmartFlow\SmartFlowWorker.exe" recover
& "$env:LOCALAPPDATA\Programs\SmartFlow\SmartFlowWorker.exe" recover --snapshot <name from the list>
```
The first lists snapshots from the active data folder (including after a restore); the second restores one. The previous database and any WAL/SHM sidecars are kept together as `smartflow.db.replaced-<time>-<unique-id>` and matching sidecars. Keep all these files together. Recovery requires SmartFlow to be closed and prepares a verified replacement before switching. Then reinstall the previous setup. Restoring old program files alone does not roll back the database.

## Uninstall
Settings > Apps > SmartFlow > Uninstall. Your data folder is kept. To delete all records, delete `%LOCALAPPDATA%\SmartFlow` yourself.

## Troubleshooting
- Blank/refused window: WebView2 missing; install it from Microsoft (offline "Evergreen Standalone" installer).
- "Another instance": close it from the taskbar or Task Manager (SmartFlow.exe, SmartFlowWorker.exe).
- Close is refused during a run: stop the simulation/training first, then close.
- A saved scenario or model can require its original engine and network revision. Check the compatibility message before using older study artifacts.
