---
name: traffic-engine-ops
description: Operational guide and validation rules for the SmartFlow native traffic simulation engine (simulation/traffic_engine.py). Use when modifying vehicle dynamics, car-following models, junction controllers, or signal phase transitions.
---

# Traffic Engine Operations (`traffic-engine-ops`)

Guidelines and best practices for developing, extending, and debugging the core traffic simulation engine in SmartFlow.

## Core Principles

1. **Native Simulation Authority**:
   - The primary simulation engine is [traffic_engine.py](file:///c:/Users/jhepo/Desktop/trapik2/SmartFlow/simulation/traffic_engine.py).
   - Do not re-introduce legacy SUMO/TraCI dependencies for the active runtime.

2. **State & Phase Consistency**:
   - When updating signal phases, ensure yellow transition intervals (`yellow_time`) are observed before red clearance or next green switch.
   - Junction vehicle queues and lane occupancy metrics must be recalculated deterministically per simulation step (`dt`).

3. **Collision & Distance Invariants**:
   - Vehicle following distances must respect minimum bumper-to-bumper headways (`min_gap`) and kinematic deceleration constraints.
   - Avoid instant teleportation or zero-time velocity shifts; apply acceleration clamping per vehicle profile.

## Verification Checklist

- Run engine unit tests using the project Python environment:
  ```powershell
  .venv\Scripts\python.exe -m pytest tests/test_traffic_engine.py
  ```
- Verify step loop execution doesn't produce negative delay or negative queue counts.
