---
name: traffic-engine-ops
description: Operational guide and validation rules for the SmartFlow native traffic simulation engine (simulation/traffic_engine.py). Use when modifying vehicle dynamics, car-following, junction reservations, signal stages or engine metrics.
---

# Traffic Engine Operations (`traffic-engine-ops`)

Guidelines and best practices for developing, extending, and debugging the core traffic simulation engine in SmartFlow.

## Core Principles

1. **Native Simulation Authority**:
   - The active engine is `simulation/traffic_engine.py`. Do not substitute similarly named legacy engines.
   - Do not re-introduce legacy SUMO/TraCI dependencies for the active runtime.
   - Traffic logic stays in Python; the React/Three.js frontend only draws the engine's state.

2. **Signal Stages**:
   - `Signal` moves green → yellow (`yellow_seconds`) → all-red (`all_red_seconds`) → next green. A walk phase goes straight to all-red.
   - Green lasts at least `minimum_green` and at most `maximum_green`. `maximum_red` caps how long a demanded approach waits for green, under any controller.
   - Controllers, RL included, only request a service through `Signal.request`. The engine applies it after minimum green, ignores it during clearance and refuses a missing approach. Keep this safety layer in the engine.

3. **Spacing and Junctions**:
   - Travel never closes the gap to the vehicle ahead below `MIN_GAP`.
   - A vehicle enters a junction only when everything on or committed to its exit lane, itself included, fits end to end. It releases its junction reservation once its rear has left the junction. Loosening either rule can bring back the October 25 deadlock (P0-1 in `docs/ENGINE_FIX_PLAN_2026-10-25.md`).

4. **Engine Version**:
   - Any change to traffic behaviour bumps `ENGINE_VERSION` in `traffic_engine.py` and `engine_version` in `simulation/metric_definitions.json` together.
   - Trained models, recordings and saved metrics carry the version, so a bump makes them history. Group behaviour changes into one bump.

## Verification Checklist

- Run the engine tests using the project Python environment, with a scratch folder for temporary files and no `SMARTFLOW_*` environment overrides:
  ```powershell
  .venv\Scripts\python.exe -m pytest tests/test_native_engine.py tests/test_junction_deadlock.py tests/test_junction_capacity.py tests/test_engine_search_index.py -q -p no:cacheprovider --basetemp <scratch folder>
  ```
- Run the full backend suite (`tests/`, several minutes) before committing an engine change.
- In long runs, `stuck_junction_vehicles`, `gridlock_seconds` and `vehicle_conservation_error` must stay 0.
