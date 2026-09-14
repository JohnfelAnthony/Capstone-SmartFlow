# SMARTFLOW Dash to React Migration Plan

## 1. Migration Goal

The goal is not to throw away the existing `trapik2` work. The goal is to move the user-facing application from a Dash-centered interface to a React/Vite interface that can render simulation visuals more smoothly, while keeping the Python simulation, RL, database, training, evaluation, and artifact systems that already work.

The current Dash app is valuable as the working reference implementation. It already proves the system flow: login, scenario selection, SUMO execution, RL training, evaluation, runs, reports, and comparison. The React app should replace Dash gradually, page by page, using new API boundaries instead of copying Dash callbacks directly.

The recommended final direction is:

- React/Vite/TypeScript for the browser UI.
- Three.js for the live 3D simulation view.
- FastAPI for HTTP APIs and WebSocket simulation streaming.
- Python/SUMO/TraCI as the simulation source of truth.
- Existing RL scripts and Python modules for QL, DQL, PPO, evaluation, and model persistence.
- SQLite as the existing local persistence layer.

## 2. Current Architecture

The current root project is mainly a Python/Dash application.

Important current areas:

- `app.py`: Dash app creation, routing, Flask routes, security headers, `/api/render-stream`, and `/api/visual-network`.
- `callbacks.py`: Dash callback layer for dashboard state, simulation controls, charts, render bridge updates, and visualization toggles.
- `pages/`: Dash page layouts and page-specific callbacks.
- `components/`: Dash sidebar/header/common layout components.
- `services/`: Python service layer for simulation lifecycle, scenario loading, timeline generation, RL training, RL reporting, metrics, and visual network loading.
- `simulation/`: SUMO runtime, RL environment, RL state/reward, policy runtime, training logic, and older legacy simulation references.
- `database.py`: SQLite schema, CRUD functions, seed data, sessions, users, roles, scenarios, runs, metrics, RL models, training jobs, and checkpoints.
- `tools/`: CLI workflows for RL training, evaluation, and SUMO visual network export.
- `sumo/`: SUMO network, route, additional, and config files for the intersections.
- `assets/`: Dash CSS, JavaScript render bridges, model assets, generated timelines, textures, and static resources.
- `SmartFlow/`: New React/Vite application.

## 3. Important Clarification: `sumo_engine.py` Is Reusable

`simulation/sumo_engine.py` was used by Dash, but it is not truly Dash-specific.

It does not depend on Dash components like `dcc`, `html`, callbacks, or Dash stores. Its job is to:

- Start and stop SUMO through TraCI.
- Step the simulation.
- Apply fixed-time or RL traffic signal control.
- Spawn pedestrians.
- Track vehicles, pedestrians, traffic lights, phases, events, and metrics.
- Return runtime state through plain Python dictionaries.
- Expose RL runtime state for the RL environment and policy adapters.

That means React should not rewrite it and should not copy it into TypeScript. React cannot run this Python code directly. Instead, a FastAPI backend should wrap it and stream its output to React.

Target runtime flow:

```text
React + Three.js
       |
       | HTTP / WebSocket
       v
FastAPI Backend
       |
       | Python calls
       v
SumoSimulationEngine + RL + Database
       |
       | TraCI
       v
SUMO
```

The Dash-specific layer is mostly outside `sumo_engine.py`:

- Dash layouts in `pages/`.
- Dash callbacks in `callbacks.py`.
- Dash stores and intervals in `app.py`.
- Dash renderer bridge integration through `assets/three-bridge.mjs` and `assets/traffic-canvas.mjs`.

## 4. What To Reuse

These should be kept and reused behind the new FastAPI backend:

- `simulation/sumo_engine.py`
- `simulation/sumo_state.py`
- `simulation/sumo_config.py`
- `simulation/timeline_engine.py`
- `simulation/rl_env.py`
- `simulation/rl_state.py`
- `simulation/rl_reward.py`
- `simulation/rl_policy_runtime.py`
- `simulation/ql_agent.py`
- `simulation/ql_training.py`
- `simulation/dql_training.py`
- `simulation/ppo_training.py`
- `services/scenario_service.py`
- `services/visual_network_service.py`
- `services/render_frame_service.py`
- `services/rl_training_service.py`
- `services/rl_reporting_service.py`
- `tools/train_ql.py`
- `tools/train_dql.py`
- `tools/train_ppo.py`
- `tools/evaluate_controllers.py`
- `tools/export_sumo_visual_network.py`
- `database.py`
- `sumo/`
- `data/models/`
- `data/generated/`
- `assets/generated/timelines/`
- `assets/models/`
- `assets/textures/`

The most important idea: reuse the Python system as a backend/domain layer, not as frontend code.

## 5. What To Replace

These should eventually be replaced by React/FastAPI equivalents:

- Dash page layout functions in `pages/`.
- Dash callback graph in `callbacks.py`.
- Dash `dcc.Interval` polling for simulation visuals.
- Dash `dcc.Store` state passing for runtime UI state.
- Dash-specific routing in `app.py`.
- Dash-specific auth pages once React auth is ready.
- Dash-specific renderer bridge scripts once React owns the Three.js scene.

Replacement does not need to happen all at once. Dash should stay usable until React has feature parity for the important pages.

## 6. Target Architecture

Recommended new structure:

```text
trapik2/
  backend/
    main.py
    schemas.py
    auth_api.py
    scenario_api.py
    simulation_api.py
    simulation_runtime.py
    rl_api.py
    runs_api.py
    compare_api.py
  SmartFlow/
    src/
      api/
      components/
      pages/
      simulation/
      hooks/
      lib/
  simulation/
  services/
  tools/
  sumo/
  data/
  database.py
```

Backend responsibilities:

- Validate sessions and permissions.
- Start, step, pause, stop, and reset SUMO.
- Stream compact simulation frames over WebSocket.
- Read and write SQLite through the existing `database.py`.
- Launch RL training/evaluation scripts through existing Python services.
- Serve scenario, run, model, evaluation, and timeline metadata.

Frontend responsibilities:

- Render the application shell, sidebar, pages, forms, charts, and tables.
- Render the simulation scene using Three.js.
- Connect to HTTP APIs and WebSocket streams.
- Smooth/interpolate vehicle movement client-side.
- Show RL training progress and model evaluation results.

## 7. Step-by-Step Migration

### Step 1: Freeze Dash As The Reference

Before replacing behavior, treat Dash as the working reference.

Actions:

- Keep the current Dash app runnable.
- Record the expected flows:
  - Login.
  - Dashboard simulation start/pause/stop/reset.
  - Scenario selection.
  - RL training queue.
  - Model evaluation.
  - Runs and reports.
  - Compare runs.
- Use current Python tests as the baseline.
- Avoid deleting Dash files until the matching React page is complete.

Success criteria:

- Dash remains available as fallback.
- Any React behavior can be compared against existing Dash behavior.

### Step 2: Add FastAPI Beside Dash

Create a new backend package without removing Dash.

Recommended files:

- `backend/main.py`
- `backend/schemas.py`
- `backend/auth_api.py`
- `backend/scenario_api.py`
- `backend/simulation_api.py`
- `backend/simulation_runtime.py`
- `backend/rl_api.py`

Recommended command later:

```powershell
.venv\Scripts\uvicorn.exe backend.main:app --host 127.0.0.1 --port 8000 --reload
```

If `uvicorn` is not installed yet, add FastAPI and Uvicorn to requirements later.

Success criteria:

- `GET /api/health` returns a simple healthy response.
- The Dash app still runs independently.
- React can call the FastAPI server.

### Step 3: Add React-Compatible Auth Early

Because the user wants React auth early, the first backend feature should reuse the existing SQLite users, roles, permissions, and session records.

Endpoints:

- `POST /api/auth/login`
- `GET /api/auth/me`
- `POST /api/auth/logout`
- `POST /api/auth/change-password`

Implementation rules:

- Reuse `auth.hash_password()` and `auth.verify_password()` behavior where practical.
- Reuse `database.py` user/session functions.
- Store session token in an HTTP-only cookie.
- Return current user, role, permissions, and `must_change_password`.
- Keep Dash session handling separate until cutover.

Success criteria:

- React can log in.
- React can refresh and still know the current user.
- Logout invalidates the server-side session.

### Step 4: Expose Scenario APIs

React needs real scenario data before live simulation controls are meaningful.

Endpoints:

- `GET /api/scenarios`
- `GET /api/scenarios/{id}`
- `POST /api/scenarios`
- `PUT /api/scenarios/{id}`
- `POST /api/scenarios/{id}/archive`
- `POST /api/scenarios/{id}/restore`

Start with read-only endpoints if needed.

Implementation rules:

- Reuse `database.get_scenarios()`.
- Reuse `database.get_scenario_by_id()`.
- Keep scenario JSON fields validated the same way as Dash.
- Preserve `intersection_id`, traffic density, pedestrian density, emergency mode, and road constraints.

Success criteria:

- React scenario dropdown is populated from SQLite.
- React dashboard can select a real scenario by ID.

### Step 5: Expose Visual Network API

React/Three needs SUMO geometry.

Endpoint:

- `GET /api/visual-network?intersection_id=tagum_1`

Implementation rules:

- Reuse `services.visual_network_service.load_client_visual_network()`.
- Keep the existing payload sanitation.
- Do not parse SUMO XML in React.
- React receives renderer-ready geometry.

Success criteria:

- React can load Tagum intersection geometry.
- Three.js can draw roads/lanes/crossings from the payload.

### Step 6: Build FastAPI Simulation Runtime Wrapper

Create a new runtime wrapper around `SumoSimulationEngine`.

Recommended file:

- `backend/simulation_runtime.py`

Responsibilities:

- Hold one active engine instance.
- Guard access with a lock.
- Configure the engine from selected scenario/settings.
- Start SUMO.
- Step SUMO in a background loop.
- Stop and clean up the TraCI connection.
- Return current state snapshots.
- Save run metadata and metrics using `database.py`.

Important: do not import Dash or Flask session logic here.

The wrapper should call:

```python
engine = SumoSimulationEngine(seed=seed)
engine.configure_from_scenario(scenario)
engine.start(duration_limit=duration_seconds)
engine.step(num_ticks=1)
state = engine.to_dict()
```

Success criteria:

- FastAPI can start and stop a SUMO run without Dash.
- The engine state can be read as a plain dictionary.

### Step 7: Add Simulation HTTP Controls

Endpoints:

- `GET /api/simulation/state`
- `POST /api/simulation/configure`
- `POST /api/simulation/start`
- `POST /api/simulation/pause`
- `POST /api/simulation/resume`
- `POST /api/simulation/stop`
- `POST /api/simulation/reset`

Suggested request shape for configure/start:

```json
{
  "scenario_id": 1,
  "intersection_id": "tagum_1",
  "traffic_density": "low",
  "pedestrian_density": "medium",
  "emergency_mode": "disabled",
  "road_constraint": "None",
  "duration_seconds": 300,
  "seed": 11,
  "control_mode": "fixed-time"
}
```

Success criteria:

- React buttons can control the Python simulation through FastAPI.
- The same state machine ideas from Dash remain: idle, ready, running, paused, completed, error.

### Step 8: Add WebSocket Render Stream

Endpoint:

- `WS /ws/simulation`

Implementation rules:

- Backend uses `services.render_frame_service.build_render_frame()`.
- Send compact JSON frames.
- Do not send full dashboard state if the renderer only needs positions/signals.
- Use a stable update rate such as 10 frames per second from backend.
- Let Three.js render at browser frame rate.

Frame flow:

```python
state = runtime.get_state()
frame = build_render_frame(state)
await websocket.send_json(frame)
```

Success criteria:

- React receives continuous simulation frames.
- WebSocket closes cleanly when the simulation stops or the page unloads.

### Step 9: Build React Simulation Client

Recommended frontend files:

- `SmartFlow/src/api/client.ts`
- `SmartFlow/src/api/simulation.ts`
- `SmartFlow/src/hooks/useSimulationSocket.ts`
- `SmartFlow/src/simulation/SimulationScene.tsx`
- `SmartFlow/src/simulation/frame-types.ts`
- `SmartFlow/src/simulation/interpolation.ts`

Implementation rules:

- Keep API types explicit.
- Keep WebSocket frame data outside normal React state as much as possible.
- Store latest frames in refs.
- Let Three.js update object positions imperatively inside the animation loop.
- Update React KPIs at a slower UI interval.

Success criteria:

- React dashboard can connect to the backend stream.
- Vehicles/pedestrians/signals update without Dash.

### Step 10: Build Smooth Three.js Rendering

Rendering rules:

- Use one persistent Three.js scene.
- Do not recreate the scene on every frame.
- Reuse meshes for vehicles and pedestrians when possible.
- Interpolate positions between backend frames.
- Keep camera, lights, road geometry, and vehicle models separate.
- Load static visual network geometry once per intersection.
- Load dynamic vehicle positions from WebSocket.

Smoothness target:

- Backend can stream around 10Hz.
- Browser renders around 60fps.
- Vehicle motion should appear smooth because the client interpolates between backend frames.

Success criteria:

- Live simulation is visually smoother than Dash polling.
- React state updates do not cause large UI stutters.

### Step 11: Move Dashboard KPIs, Charts, and Events

React should display dashboard information from the same backend state.

Data sources:

- `state.metrics`
- `state.charts`
- `state.events`
- `state.dashboard`
- `state.phase`
- `state.phase_remaining`
- `state.scenario`

Implementation rules:

- KPIs can update every WebSocket frame or every few frames.
- Charts should update less frequently than the render scene.
- Events should append from backend event IDs.
- Do not use Plotly/Dash charts in React.
- Use the existing React chart stack already present in `SmartFlow` where practical.

Success criteria:

- React dashboard shows real wait time, queue length, throughput, pedestrian count, emergency count, phase, and events.

### Step 12: Migrate RL Training Page

Do not rewrite QL, DQL, or PPO in React.

React should call backend endpoints that reuse the existing training services and scripts.

Endpoints:

- `GET /api/rl/models`
- `GET /api/rl/training/jobs`
- `POST /api/rl/training/jobs`
- `GET /api/rl/training/jobs/{id}`
- `POST /api/rl/training/jobs/{id}/stop`
- `POST /api/rl/models/{id}/evaluate`

Backend reuse:

- `services.rl_training_service`
- `services.rl_reporting_service`
- `tools/train_ql.py`
- `tools/train_dql.py`
- `tools/train_ppo.py`
- `tools/evaluate_controllers.py`

Success criteria:

- React can launch QL/DQL/PPO training sequentially.
- React can show live console/progress.
- React can list trained models from SQLite.
- React can evaluate selected models.

### Step 13: Migrate Runs and Reports

React should read the same run and metric records.

Endpoints:

- `GET /api/runs`
- `GET /api/runs/{id}`
- `GET /api/runs/{id}/metrics`
- `GET /api/runs/{id}/timeline`
- `POST /api/runs/{id}/favorite`
- `DELETE /api/runs/{id}`
- `GET /api/reports/export`

Success criteria:

- React shows saved runs.
- React can filter by scenario, controller, seed, status, and run mode.
- React can open replayable timeline runs.

### Step 14: Migrate Compare Runs

Compare Runs should remain prerecorded playback first, not dual live.

Endpoints:

- `GET /api/compare/runs`
- `GET /api/compare/compatible-runs?left_run_id=123`
- `GET /api/compare/pair?left_run_id=123&right_run_id=124`

Rules:

- Left run is selected first.
- Right dropdown only shows compatible runs.
- Compatibility should match scenario, intersection, seed, duration, and comparable timeline availability.
- Timeline playback should not require live SUMO.

Success criteria:

- React can load two timeline artifacts.
- React can play/pause/scrub them together.
- KPI comparison matches saved run metrics.

### Step 15: Migrate Admin Pages

Move admin pages after simulation, RL, runs, and compare are stable.

Admin endpoints:

- `GET /api/admin/users`
- `POST /api/admin/users`
- `PUT /api/admin/users/{id}`
- `POST /api/admin/users/{id}/reset-password`
- `GET /api/admin/roles`
- `PUT /api/admin/roles/{id}/permissions`
- `GET /api/admin/audit-logs`
- `POST /api/admin/backups`
- `GET /api/admin/backups`

Success criteria:

- Admin can manage users and roles in React.
- Permission behavior matches Dash.
- Audit logs and backups remain functional.

### Step 16: Cut Over From Dash

Only remove Dash after React has feature parity for the required capstone workflow.

Minimum cutover checklist:

- React login works.
- React dashboard can run SUMO.
- React simulation is smoother than Dash.
- React scenarios work.
- React RL training works.
- React model list/evaluation works.
- React runs/reports work.
- React compare runs work.
- React admin basics work.
- Existing Python tests still pass or have React/FastAPI replacements.
- Dash fallback is no longer needed.

## 8. Backend API Summary

### Auth

- `POST /api/auth/login`
- `GET /api/auth/me`
- `POST /api/auth/logout`
- `POST /api/auth/change-password`

### Scenarios

- `GET /api/scenarios`
- `GET /api/scenarios/{id}`
- `POST /api/scenarios`
- `PUT /api/scenarios/{id}`
- `POST /api/scenarios/{id}/archive`
- `POST /api/scenarios/{id}/restore`

### Simulation

- `GET /api/visual-network`
- `GET /api/simulation/state`
- `POST /api/simulation/configure`
- `POST /api/simulation/start`
- `POST /api/simulation/pause`
- `POST /api/simulation/resume`
- `POST /api/simulation/stop`
- `POST /api/simulation/reset`
- `WS /ws/simulation`

### RL

- `GET /api/rl/models`
- `GET /api/rl/training/jobs`
- `POST /api/rl/training/jobs`
- `GET /api/rl/training/jobs/{id}`
- `POST /api/rl/training/jobs/{id}/stop`
- `POST /api/rl/models/{id}/evaluate`

### Runs and Compare

- `GET /api/runs`
- `GET /api/runs/{id}`
- `GET /api/runs/{id}/metrics`
- `GET /api/runs/{id}/timeline`
- `GET /api/compare/runs`
- `GET /api/compare/compatible-runs`
- `GET /api/compare/pair`

## 9. Simulation Smoothness Rules

The reason to move from Dash to React is not just visual preference. It is about avoiding the bottlenecks caused by server-driven UI updates.

Rules for the new renderer:

- Use WebSocket instead of Dash polling for live frames.
- Keep SUMO stepping in Python.
- Keep rendering in the browser GPU through Three.js.
- Send compact frame payloads.
- Do not update React state for every vehicle on every animation frame.
- Use `requestAnimationFrame` for visual updates.
- Interpolate vehicle and pedestrian positions client-side.
- Load static road geometry once.
- Stream only dynamic runtime state after the scene is loaded.
- Keep charts and KPIs separate from the high-frequency render loop.

Recommended timing:

- SUMO step length: existing `0.1s`.
- Backend stream rate: around `10Hz` to start.
- Browser render loop: normal `requestAnimationFrame`, ideally near `60fps`.
- UI KPI/chart update: throttled if needed.

## 10. RL Migration Rules

The RL system should remain Python.

Do not rewrite these in React:

- QL agent
- DQL training
- PPO training
- Gymnasium environment
- Reward function
- Observation extractor
- Controller evaluation
- Model persistence

React should only:

- Choose algorithms and settings.
- Start jobs.
- Display logs.
- Display episode progress and rewards.
- Display model table.
- Trigger evaluation.
- Navigate to compare runs.

The Python backend should own:

- Training subprocesses.
- Checkpoints.
- Model metadata.
- Evaluation summaries.
- Timeline generation.
- Database registration.

## 11. Recommended Migration Order

Recommended order:

1. FastAPI skeleton and health check.
2. React auth using existing SQLite sessions.
3. Scenario read APIs.
4. Visual network API.
5. FastAPI wrapper around `SumoSimulationEngine`.
6. WebSocket simulation stream.
7. React dashboard controls connected to backend.
8. React Three.js live renderer.
9. React KPIs, charts, and events.
10. React scenario management.
11. React RL training page.
12. React runs and reports.
13. React compare runs.
14. React admin pages.
15. Retire Dash.

The first serious milestone should be:

> A logged-in React user can select a real scenario, start a SUMO run through FastAPI, and watch smooth Three.js live movement through WebSocket frames.

## 12. Testing and Acceptance

Backend tests should cover:

- Login and logout.
- Session validation.
- Permission checks.
- Scenario list and scenario detail.
- Simulation configure/start/pause/resume/stop/reset.
- WebSocket frame emission.
- Visual network payload loading.
- RL training job creation.
- RL model listing.
- Evaluation command creation.

Frontend checks should cover:

- React build passes.
- Login page works.
- Dashboard loads only after auth.
- Scenario dropdown uses backend data.
- Simulation controls call backend APIs.
- WebSocket reconnects after disconnect.
- Three.js canvas is nonblank.
- Vehicles move smoothly.
- KPIs update from backend state.

Manual acceptance tests:

- Run a 300-second low-density simulation from React.
- Confirm SUMO starts only once.
- Confirm stop/reset closes TraCI cleanly.
- Confirm metrics save to the existing SQLite database.
- Train a short QL job from React.
- Evaluate a saved model from React.
- Compare two prerecorded runs in React.
- Confirm Dash still works until final cutover.

## 13. Risks and Mitigations

### Risk: Rewriting Too Much

Mitigation:

- Keep Python simulation/RL/database code.
- Build APIs around existing modules.
- Replace only the UI and streaming bridge first.

### Risk: SUMO Runtime Concurrency

Mitigation:

- Use one controlled runtime manager.
- Protect engine access with locks.
- Do not allow multiple live simulations unless explicitly designed later.
- Keep training/evaluation separate from the live runtime.

### Risk: React Re-render Lag

Mitigation:

- Keep vehicle motion out of normal React state.
- Use refs and Three.js imperative updates.
- Throttle charts and noncritical UI updates.

### Risk: Auth Duplication

Mitigation:

- Reuse the existing database tables.
- Keep one source of truth for users, roles, sessions, and permissions.
- Do not create a second user system for React.

### Risk: Dash and FastAPI Fighting Over State

Mitigation:

- During migration, avoid running both live simulation controllers at the same time.
- Use separate ports.
- Treat Dash as fallback/reference.
- Let FastAPI own React-triggered runtime sessions.

## 14. Final Recommendation

The best transition is a gradual replacement, not a hard rewrite.

Use React and Three.js for the smooth simulation UI. Use FastAPI and WebSockets as the new bridge. Keep Python as the owner of SUMO, RL, database, training, evaluation, and generated artifacts.

The first build target should be small but meaningful:

1. React login.
2. Scenario dropdown from SQLite.
3. Start SUMO through FastAPI.
4. Stream render frames through WebSocket.
5. Draw smooth live movement in Three.js.

Once that works, the rest of the pages can move over with much lower risk.
