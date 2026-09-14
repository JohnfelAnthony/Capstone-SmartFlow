# SMARTFLOW - Codebase Status

**Generated:** 2026-05-30  
**Last Updated:** 2026-06-04  
**Project:** SMARTFLOW - AI-Driven Traffic Simulation and Signal Control Dashboard  
**Workspace:** `C:\Users\jhepo\Desktop\trapik2`

---

## 1. Executive Summary

SMARTFLOW is now a **Dash + SUMO + TraCI traffic simulation and RL evaluation platform**.

The project has moved beyond a fixed-time-only dashboard. It now includes:

- Dash web app with authentication, admin tools, scenario management, reports, compare, and RL training pages
- SQLite persistence for users, roles, scenarios, simulation runs, metrics, RL models, and RL training jobs
- SUMO/TraCI runtime as the active traffic simulation source of truth
- 3D Three.js and 2D Canvas visualization paths
- Pre-recorded timeline generation and replay
- Offline RL training for QL, DQL, and PPO
- Controller evaluation workflow for Fixed-Time, QL, DQL, and PPO
- Compare Runs workflow for synchronized prerecorded playback and KPI comparison

The current research path is:

1. Train QL, DQL, or PPO offline.
2. Save model artifacts and metadata.
3. Evaluate controllers under the same scenario, seed, duration, density, and intersection.
4. Record replay timelines.
5. Compare compatible runs in the Compare Runs page.

---

## 2. Current Architecture

### 2.1 Canonical Runtime Path

The active traffic runtime is SUMO-backed.

1. SUMO network/config lives under `sumo/Tagum_1/` and `sumo/Tagum_2/`.
2. `simulation/sumo_engine.py` starts and steps SUMO through TraCI.
3. `services/simulation_service.py` manages the shared runtime engine for Dash.
4. `callbacks.py` updates dashboard state, KPIs, charts, and visualization payloads.
5. `tools/export_sumo_visual_network.py` exports SUMO geometry into renderer-ready JSON.
6. Renderers consume the same runtime/geometry payloads:
   - `assets/three-bridge.mjs`
   - `assets/traffic-canvas.mjs`
   - `assets/compare-canvas.mjs`

### 2.2 State Machine Flow

The simulation workflow uses a state-machine style flow:

- `IDLE`
- `SCENARIO_SELECTED`
- `LIVE_RUNNING`
- `GENERATING`
- `READY_TO_PLAY`
- `PLAYING_BACK`
- `PAUSED`
- `COMPLETED`

Main branches:

1. **Live simulation:** starts SUMO and updates the dashboard in real time.
2. **Pre-record generation:** runs SUMO headlessly and writes timeline artifacts.
3. **Playback:** reads saved `.jsonl` or `.jsonl.gz` timeline files.
4. **Compare playback:** loads two prerecorded runs and scrubs them together.

### 2.3 Active vs Legacy Simulation Code

Active path:

- `simulation/sumo_engine.py`
- `simulation/sumo_state.py`
- `simulation/sumo_config.py`
- `simulation/timeline_engine.py`
- `services/simulation_service.py`
- `services/timeline_generator.py`

Legacy/reference path:

- `simulation/engine.py`
- `simulation/network.py`
- `simulation/vehicles.py`
- `simulation/pedestrians.py`
- `simulation/traffic_light.py`
- `simulation/controllers.py`
- `simulation/metrics.py`

The legacy engine remains useful for tests/reference, but RL and live runtime work should target the SUMO path.

---

## 3. Working Application Areas

### 3.1 Authentication and Admin

Implemented and usable:

- Login and registration
- Session handling
- Password hashing
- First-login password change
- Role-based access control
- Admin user management
- Role and permission matrix
- Audit logs
- Backup/restore page

Primary files:

- `auth.py`
- `database.py`
- `pages/login.py`
- `pages/register.py`
- `pages/change_password.py`
- `pages/admin_users.py`
- `pages/admin_roles.py`
- `pages/admin_audit.py`
- `pages/admin_backups.py`

### 3.2 Navigation and Pages

Current visible sidebar is intentionally simplified:

- Main:
  - Dashboard
  - Scenarios
  - RL Training
  - Runs & Reports
  - Compare Runs
- System:
  - Settings
  - Help
- Admin:
  - User Management
  - Role & Access Control
  - Audit Logs
  - Backup & Restore

Temporarily hidden from sidebar, but not deleted:

- Simulation Control
- Performance
- AI Agent (RL)

### 3.3 Scenario Management

Implemented:

- Scenario listing
- Card and table modes
- Scenario create/edit/detail flows
- Official/user/archived states
- Scenario loading into runtime
- Multi-intersection direction through `tagum_1` and `tagum_2`

Primary files:

- `pages/scenarios.py`
- `services/scenario_service.py`
- `simulation/sumo_config.py`
- `tools/export_sumo_visual_network.py`

### 3.4 Dashboard and Visualization

Implemented:

- Dashboard shell and KPIs
- Runtime state payloads
- 3D renderer bridge
- 2D canvas renderer
- Render safety checks
- Visual network export and cached generated assets
- Streaming/render timing controls

Primary files:

- `pages/dashboard.py`
- `callbacks.py`
- `assets/three-bridge.mjs`
- `assets/traffic-canvas.mjs`
- `assets/render-safety.mjs`
- `services/render_frame_service.py`
- `services/visual_network_service.py`

---

## 4. RL System Status

### 4.1 RL Contract

The RL contract exists and is the source of truth for algorithm comparisons:

- `docs/SMARTFLOW_RL_Contract.md`

Locked first-pass versions:

- Observation contract: `obs_v1`
- Reward contract: `reward_v1`
- Action contract: `action_v1`
- Episode policy: `episode_v1`
- Comparison protocol: `compare_v1`

Controllers:

- `fixed-time`
- `ql`
- `dql`
- `ppo`

### 4.2 RL Environment

Implemented:

- Gym-style SMARTFLOW RL environment wrapper
- Runtime observation extraction
- Shared reward calculation
- Discrete action space for signal service requests
- Minimum green hold handling
- Episode warmup/evaluation windows

Primary files:

- `simulation/rl_env.py`
- `simulation/rl_state.py`
- `simulation/rl_reward.py`

### 4.3 Training Algorithms

Implemented:

- QL tabular baseline
- DQL neural discrete baseline using Stable-Baselines3 DQN/PyTorch stack
- PPO modern policy-gradient baseline using Stable-Baselines3/PyTorch stack

Primary files:

- `simulation/ql_agent.py`
- `simulation/ql_training.py`
- `simulation/dql_training.py`
- `simulation/ppo_training.py`
- `tools/train_ql.py`
- `tools/train_dql.py`
- `tools/train_ppo.py`

Current training behavior:

- Training is offline, outside the normal live dashboard loop.
- Web-launched training runs scripts in background subprocesses.
- QL supports partial saves/checkpoints/resume.
- DQL and PPO save SB3 zip artifacts plus metadata.
- Training output is streamed to the RL Training page using unbuffered Python mode.

### 4.4 Runtime Policy Loading

Implemented:

- QL model artifact loading
- DQL model artifact loading
- PPO model artifact loading
- Deterministic inference for evaluation/runtime adapters
- Controller labels use the contract values: `ql`, `dql`, `ppo`

Primary file:

- `simulation/rl_policy_runtime.py`

### 4.5 Model Metadata and Persistence

Implemented direction:

- RL model records in DB
- Checkpoint paths
- Training metadata
- Observation/reward/action version fields
- Training jobs and job items for web UI queue tracking
- RL training logs under generated data

Primary files:

- `database.py`
- `services/rl_training_service.py`
- `services/rl_reporting_service.py`

Generated runtime directories:

- `data/models/ql/`
- `data/models/dql/`
- `data/models/ppo/`
- `data/generated/rl_training_logs/`
- `data/generated/evaluations/`

---

## 5. Evaluation and Comparison

### 5.1 Controller Evaluation

Implemented:

- CLI evaluator for Fixed-Time, QL, DQL, and PPO
- Fixed scenario/seed/duration/intersection comparison protocol
- Evaluation metric summary JSON output
- Optional prerecorded timeline generation for selected seed
- Auto-detection of latest model artifacts, with explicit model flags available

Primary file:

- `tools/evaluate_controllers.py`

Typical evaluated metrics:

- average waiting time
- average queue length
- maximum queue length
- throughput
- average pedestrian delay

### 5.2 Runs and Reports

Implemented:

- Runs table
- Filtering
- CSV/Excel/PDF direction
- Replay run support
- Report generation direction tied to saved simulation runs

Primary file:

- `pages/runs_reports.py`

### 5.3 Compare Runs

Implemented:

- Dual prerecorded playback
- Static synchronized frame scrubber
- Left/right playback panels
- Queue bars
- KPI comparison table
- Wait/queue/throughput charts
- Learning summary cards for RL runs
- Canvas-based dual replay renderer
- Validation/warnings for mismatched protocol fields
- Guided dropdown flow:
  - choose left run first
  - right run unlocks only after left selection
  - right options are filtered to compatible runs with same scenario, intersection, seed, and duration

Primary files:

- `pages/compare.py`
- `assets/compare.css`
- `assets/compare-canvas.mjs`

---

## 6. RL Training Page

Implemented:

- Web page for queued RL training
- Algorithm selection for QL, DQL, and PPO
- Sequential queue execution
- Scenario and density settings
- Warmup/evaluation/seed/checkpoint settings
- Advanced algorithm settings
- Live console
- Reward progress chart
- Evaluation metrics chart
- Trained model table
- Resume selected model
- Evaluate selected model
- Link to Compare Runs

Primary files:

- `pages/rl_training.py`
- `assets/rl_training.css`
- `services/rl_training_service.py`

Important behavior:

- The page does not train inside the Dash callback itself.
- It launches the same CLI training scripts in background subprocesses.
- Reward chart updates after progress lines are produced by the script.
- Evaluation metrics appear after evaluation artifacts are created.

---

## 7. Current Limitations and Known Issues

### 7.1 RL Generalization

The system can train and evaluate QL/DQL/PPO, but final research-quality models still need broader training:

- more episodes
- more seeds
- low/medium/high traffic density runs
- low/medium/high pedestrian density runs
- separate evaluations per density
- repeated runs for consistency reporting

The current seed set `11,22,33,44,55` is mainly for fixed fair comparison. Training for broad generalization should use more randomized but recorded seeds/scenarios.

### 7.2 Live Dashboard RL Control

Offline RL training and evaluation exist. Full live dashboard selection of an RL controller as the active real-time controller is still a later integration step.

Current strongest path:

1. Train offline.
2. Evaluate offline.
3. Record timelines.
4. Compare replay artifacts.

### 7.3 CDN Browser Warnings

The app still loads some external CDN assets globally:

- Font Awesome CSS from cdnjs
- Three.js from cdnjs
- Google Fonts

Modern browsers may show tracking-prevention warnings for those URLs. They are usually harmless, but self-hosting those assets under `assets/` would reduce warnings and improve offline reliability.

### 7.4 Visual Fidelity

The renderers are functional and geometry-backed, but still not final presentation art.

Still open:

- richer 3D city context
- stronger 2D lane/road styling
- optional zoom/pan/selection interactions
- final asset strategy for custom low-poly or local resources

### 7.5 Repository Hygiene

The working tree currently includes many generated artifacts:

- model artifacts
- evaluation JSON files
- replay timelines
- DB files/backups
- Python `__pycache__`

Before final submission or version-control cleanup, decide which generated artifacts should be kept, ignored, or archived.

---

## 8. Tests and Validation

There are currently **30 Python test files** under `tests/`.

Key coverage areas:

| Area | Test Files |
|------|------------|
| Auth/admin/security | `test_auth_flow_guardrails.py`, `test_auth_page_design.py`, `test_admin_roles_helpers.py`, `test_security_hardening.py` |
| Dashboard/rendering | `test_callbacks_chart_layout.py`, `test_dashboard_visualization_cleanup.py`, `test_render_stream_timing.py`, `test_three_bridge_scene_style.py`, `test_traffic_canvas_renderer.py` |
| SUMO/runtime | `test_sumo_network_scope.py`, `test_sumo_simulation_service.py`, `test_sumo_state_payload.py`, `test_sumo_visual_network_export.py`, `test_multi_intersection_assets.py` |
| Legacy engine | `test_simulation_engine.py`, `test_simulation_vehicles.py` |
| Timeline/playback | `test_timeline_playback_engine.py` |
| RL contract/training | `test_rl_contract.py`, `test_ql_agent.py`, `test_dql_training.py`, `test_ppo_training.py`, `test_rl_policy_runtime.py` |
| RL web/reporting | `test_rl_training_service.py`, `test_rl_training_page.py`, `test_rl_training_integration.py`, `test_rl_reporting_service.py` |
| Evaluation/compare | `test_evaluate_controllers.py`, `test_compare_page.py` |
| Scenario page | `test_scenarios_callback_placeholders.py` |

Recent focused checks used during development include:

- `python -m unittest tests.test_compare_page`
- `python -m unittest tests.test_rl_training_service tests.test_rl_training_page`
- `python -m unittest tests.test_rl_training_integration tests.test_rl_training_service tests.test_rl_training_page tests.test_rl_contract tests.test_evaluate_controllers tests.test_rl_reporting_service tests.test_rl_policy_runtime tests.test_compare_page`

---

## 9. Active Source of Truth

### Core App

- `app.py`
- `auth.py`
- `database.py`
- `callbacks.py`
- `components/header.py`
- `components/sidebar.py`
- `assets/styles.css`

### Runtime and Simulation

- `simulation/sumo_engine.py`
- `simulation/sumo_state.py`
- `simulation/sumo_config.py`
- `simulation/timeline_engine.py`
- `services/simulation_service.py`
- `services/timeline_generator.py`
- `services/render_frame_service.py`

### RL

- `docs/SMARTFLOW_RL_Contract.md`
- `simulation/rl_env.py`
- `simulation/rl_state.py`
- `simulation/rl_reward.py`
- `simulation/ql_agent.py`
- `simulation/ql_training.py`
- `simulation/dql_training.py`
- `simulation/ppo_training.py`
- `simulation/rl_policy_runtime.py`
- `services/rl_training_service.py`
- `services/rl_reporting_service.py`
- `tools/train_ql.py`
- `tools/train_dql.py`
- `tools/train_ppo.py`
- `tools/evaluate_controllers.py`

### Pages

- `pages/dashboard.py`
- `pages/scenarios.py`
- `pages/rl_training.py`
- `pages/runs_reports.py`
- `pages/compare.py`
- `pages/profile_settings.py`
- `pages/help_about.py`
- `pages/admin_users.py`
- `pages/admin_roles.py`
- `pages/admin_audit.py`
- `pages/admin_backups.py`

### Renderers and Assets

- `assets/three-bridge.mjs`
- `assets/traffic-canvas.mjs`
- `assets/compare-canvas.mjs`
- `assets/render-safety.mjs`
- `assets/traffic-canvas.css`
- `assets/compare.css`
- `assets/rl_training.css`
- `data/generated/visual_network.json`
- `data/generated/visual_networks/tagum_1.json`
- `data/generated/visual_networks/tagum_2.json`

---

## 10. Recommended Next Work

### Priority 1: Research-Quality Training Runs

1. Train QL/DQL/PPO on low density with short laptop-safe runs.
2. Evaluate against Fixed-Time with the same seed/scenario protocol.
3. Repeat for medium density.
4. Keep high density as a stronger final stress test.
5. Record timelines for at least one representative seed per controller.

### Priority 2: RL Result Reporting

1. Summarize training reward curves per model.
2. Show best/final/last-10 reward in reports and compare cards.
3. Add evaluation summary tables for each density batch.
4. Export research-friendly PDF/Excel summaries.

### Priority 3: Live RL Controller Integration

1. Add runtime controller mode selection for saved QL/DQL/PPO models.
2. Load selected model into the SUMO runtime.
3. Use deterministic inference for live control.
4. Keep replay/evaluation as the official comparison path.

### Priority 4: Asset and Dependency Cleanup

1. Self-host Font Awesome and Three.js to remove CDN tracking warnings.
2. Decide which generated timelines/models belong in source control.
3. Clean or ignore `__pycache__`, DB backups, and temporary artifacts.

### Priority 5: Visual Polish

1. Improve 2D lane styling and labels.
2. Improve 3D framing and context.
3. Add optional user inspection tools like hover/click details.

---

## 11. Bottom Line

SMARTFLOW is now best described as:

> a working Dash + SUMO + TraCI traffic simulation platform with offline RL training for QL, DQL, and PPO, standardized controller evaluation, saved replay timelines, and a Compare Runs workflow for synchronized playback and KPI review.

It is no longer accurate to describe the project as merely "RL-ready." The RL pipeline exists.

What is still not complete:

- final research-scale training and evaluation results
- live dashboard control using a selected saved RL model
- final visual polish
- generated artifact cleanup
- self-hosted external frontend dependencies

