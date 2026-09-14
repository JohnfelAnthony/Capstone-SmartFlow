# SMARTFLOW Flow Implementation Guide
## Live Scenario, Pre-record Timeline, and Playback Flow

### 1. Purpose

This document defines the target user flow for SMARTFLOW’s simulation system. The goal is to support two main run modes:

1. **Live Scenario Mode** The user starts a scenario live, SUMO/TraCI runs in real time, and the dashboard updates continuously.

2. **Pre-record Timeline Mode** The user selects a scenario, SMARTFLOW runs the scenario in the background without rendering, shows a loading state from 0 to 100%, saves the full timeline to JSON, and then enables playback in the dashboard.

This flow keeps SMARTFLOW useful as both an interactive simulation dashboard and a research-friendly playback tool.

---

### 2. Flow Overview

The recommended high-level system flow is:

1. Login.
2. Validate session and role.
3. Redirect to Dashboard or Admin page based on role or last-used module.
4. Show an idle dashboard with scenario controls and run mode selection.
5. User selects one of two modes:
   - Live Scenario.
   - Pre-record Timeline.
6. If Live Scenario is selected:
   - Launch SUMO/TraCI on demand.
   - Stream live state to the dashboard.
   - Stop automatically when the duration limit is reached.
   - Save run metrics and logs.
7. If Pre-record Timeline is selected:
   - Run SUMO in the background without rendering.
   - Show loading/progress from 0 to 100%.
   - Save the full timeline to JSON.
   - Reveal a Play button when ready.
8. Playback the recorded scenario in the dashboard.
9. Allow export and replay actions.
10. End session with logout and clean state reset.

---

### 3. Login and Routing Flow

#### 3.1 Login entry

After login:
- Validate username/password.
- Check account status and role.
- Create session token.
- Store session metadata and last visited module.

#### 3.2 Redirect logic

After a successful login:
- Admin users can go to Admin Dashboard or main Dashboard.
- Researcher/User accounts go to Dashboard by default.
- If the user previously left off in another module, restore that module when appropriate.

#### 3.3 Session guards

Every protected page must:
- Reject unauthenticated access.
- Reject expired sessions.
- Reject disabled or unauthorized roles.
- Redirect safely to login when access is invalid.

---

### 4. Idle Dashboard State

The dashboard must load in an idle state first.

#### 4.1 What the idle dashboard should show
- Static 2D preview or placeholder map.
- Scenario selector.
- Run mode selector.
- Duration selector: 300, 600, or 900 seconds.
- Control mode selector: Live Scenario or Pre-record Timeline.
- Disabled Play/Start buttons until the correct state is ready.
- Status panel showing: Ready, No simulation running, or Waiting for scenario.

#### 4.2 What the idle dashboard should not do
- It must not auto-start SUMO.
- It must not consume CPU in a continuous loop.
- It must not render fake live movement unless playback or live mode is active.

---

### 5. Live Scenario Flow

This is the real-time simulation mode.

#### 5.1 User action
The user chooses Live Scenario and clicks Start.

#### 5.2 Backend action
- Load the selected SUMO configuration.
- Start TraCI.
- Initialize runtime state.
- Begin stepping the simulation.
- Stream state updates to the dashboard.
- Track elapsed simulation time.

#### 5.3 Stop condition
- Automatically stop when the time limit is reached.
- Stop when the user clicks Stop.
- Stop on backend failure or invalid runtime state.

#### 5.4 After stop
- Save run metadata.
- Save performance metrics.
- Save audit log entry.
- Show summary cards and charts.
- Enable replay/export actions if data was captured.

---

### 6. Pre-record Timeline Flow

This is the recommended flow for playback generation.

#### 6.1 User action
The user selects Pre-record Timeline and then chooses a scenario.

#### 6.2 Loading state
Immediately after selection:
- Show a progress state from 0 to 100%.
- Display a status message such as:
  - Preparing scenario.
  - Running background simulation.
  - Recording vehicle timelines.
  - Finalizing playback file.
- Disable Play until the recording is complete.

#### 6.3 Background processing
- Run SUMO without rendering.
- Advance simulation as fast as possible.
- Capture exact vehicle, pedestrian, and signal state.
- Record per-step timeline snapshots.
- Serialize the result into a JSON timeline file.

#### 6.4 Completion state
When the process reaches 100%:
- Mark the scenario as ready.
- Enable a **Play Recorded Scenario** button.
- Optionally show file size, duration, and generation timestamp.

---

### 7. Playback Flow

Playback should use the recorded JSON timeline.

#### 7.1 Start playback
- Load the saved JSON timeline.
- Initialize the renderer.
- Seek to the beginning of the scenario.
- Start animation playback on user action.

#### 7.2 During playback
- Move vehicles using recorded positions.
- Update signal states from the recorded timeline.
- Keep lane geometry and visual state synchronized.
- Allow pause, resume, scrub, and replay.

#### 7.3 Playback constraints
- Playback must not require live SUMO.
- Playback must not drift away from the recorded state.
- Playback must remain smooth and deterministic.

---

### 8. Data Persistence

SMARTFLOW should persist the following data:
- Run metadata.
- Scenario ID.
- Mode used: Live or Pre-record.
- Duration.
- Controller type.
- Summary metrics.
- Timeline JSON file path.
- Audit events.
- Errors and recovery notes.

Suggested tables or records:
- `simulation_runs`
- `run_metrics`
- `timelines`
- `audit_logs`
- `scenario_records`

---

### 9. State Machine

The system should behave like a simple state machine:

- `IDLE`
- `SCENARIO_SELECTED`
- `GENERATING`
- `READY_TO_PLAY`
- `LIVE_RUNNING`
- `PLAYING_BACK`
- `PAUSED`
- `COMPLETED`
- `ERROR`
- `LOGGED_OUT`

This prevents flow confusion and makes the UI easier to maintain.

---

### 10. Key UI Rules

#### 10.1 Buttons
- Disable buttons when their action is not valid.
- Use different labels for Live Start and Playback Play.
- Keep the primary action obvious.

#### 10.2 Progress handling
- Pre-record mode must always show progress.
- Progress must move from 0 to 100 in a believable way.
- Do not leave the user waiting without feedback.

#### 10.3 Status feedback
- Always show a visible status label.
- Distinguish idle, generating, ready, running, playing, and completed states.

---

### 11. Suggested File Responsibilities

The implementation should be split clearly.

#### Auth and routing
- `app.py`
- `auth.py`
- `callbacks.py`

#### Simulation runtime
- `services/simulation_service.py`
- `simulation/sumo_engine.py`
- `simulation/sumo_state.py`

#### Scenario and persistence
- `database.py`
- `pages/scenarios.py`
- `pages/runs_reports.py`

#### Visualization
- `assets/three-bridge.mjs`
- `assets/generated/visual_network.json`
- 2D renderer module if separate

#### Playback and record logic
- A dedicated recorder module.
- A playback loader module.
- A progress/status controller.

---

### 12. Implementation Order

1. Add state machine support.
2. Add run mode selection.
3. Implement Live Scenario start/stop flow.
4. Implement Pre-record generation flow.
5. Add 0–100% loading UI.
6. Save JSON timeline files.
7. Add Play Recorded Scenario button after completion.
8. Add playback loading and scrubbing.
9. Add persistence and audit logging.

---

### 13. Acceptance Criteria

The flow is complete when:
- Login redirects correctly.
- Dashboard starts idle.
- Live mode runs only on explicit start.
- Pre-record mode shows loading progress.
- JSON timeline is generated successfully.
- Playback can start only after recording finishes.
- Saved runs can be replayed later.
- Logout fully clears session and state.

---

### 14. Notes

The system should feel like a professional simulation platform, not a continuous sandbox.  
Pre-record mode should behave like a job queue or render job: select scenario, wait for completion, then play.  
Live mode should remain available for interactive debugging and real-time monitoring.

This dual-flow design gives SMARTFLOW both operational flexibility and polished presentation behavior.