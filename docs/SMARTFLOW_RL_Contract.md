# SMARTFLOW RL Contract

This document defines the reinforcement learning contract for SMARTFLOW before any QL, DQL, or PPO implementation begins.

The goal is to make every controller compare against the same environment, the same action rules, and the same evaluation protocol.

This document is the locked `v1` contract for the first SMARTFLOW RL implementation pass.

## 1. Scope

RL in SMARTFLOW is a traffic-signal control module over the active SUMO runtime.

It is not a replacement for:
- the SUMO simulation backend
- the scenario system
- the dashboard playback system
- the reporting pipeline

The RL agent only decides signal control actions.

The active runtime to build on is:
- [simulation/sumo_engine.py](simulation/sumo_engine.py)
- [services/simulation_service.py](services/simulation_service.py)

The older lightweight engine in [simulation/engine.py](simulation/engine.py) is not the target runtime for RL rollout.

## 2. Target Algorithms

SMARTFLOW will compare these controllers:

1. Fixed-Time
2. QL
3. DQL
4. PPO

Implementation order:

1. QL
2. DQL
3. PPO

PPO is expected to be the strongest final candidate, but QL should be implemented first to validate the environment contract.

## 3. Supported Intersections

The RL contract must work against the same intersection registry already defined in:
- [simulation/sumo_config.py](simulation/sumo_config.py)

Initial rollout scope:

1. `tagum_1`
2. `tagum_2`

`tagum_3` should follow the same contract later without changing the RL API.

## 4. Control Granularity

The RL controller will act at a fixed decision interval, not every SUMO tick.

Locked `v1` values:

- SUMO step length: `0.1s`
- RL decision interval: `5.0s`
- Minimum green hold: `10.0s`

This means the simulator can keep stepping at `0.1s`, while the RL policy only chooses a new action every `5s`.

## 5. Action Space

Use one discrete action space shared by `tagum_1` and `tagum_2`.

Action meanings:

0. `SERVE_NORTH`
1. `SERVE_EAST`
2. `SERVE_SOUTH`
3. `SERVE_WEST`
4. `SERVE_PEDESTRIAN`

Interpretation:

- Each action requests the next service phase family.
- Yellow and all-red transition phases are not chosen directly by the agent.
- The environment is responsible for safely transitioning from the current phase to the requested target phase.

Action handling rules:

- If the requested service phase is already active, the environment keeps the current phase.
- If minimum green has not yet elapsed, the request is deferred until it becomes valid.
- If a pedestrian or emergency safety rule blocks the request, the environment applies the safe fallback and records that event.

This keeps the action space small enough for QL while still working for DQL and PPO.

## 6. Observation Space

The training observation must come from runtime state, not from rendered dashboard values.

Locked observation vector `obs_v1`:

1. Current service phase one-hot: `NORTH`, `EAST`, `SOUTH`, `WEST`, `PEDESTRIAN`
2. Normalized elapsed time in current phase
3. Normalized remaining time before a valid switch
4. Queue length by approach:
   - north
   - east
   - south
   - west
5. Waiting time by approach:
   - north
   - east
   - south
   - west
6. Active vehicle count by approach:
   - north
   - east
   - south
   - west
7. Pedestrian waiting count:
   - total
   - optional per crossing in a later version
8. Emergency presence flags by approach:
   - north
   - east
   - south
   - west
9. Emergency proximity by approach:
   - normalized distance-to-stop-line or time-to-junction
10. Intersection identifier one-hot:
   - `tagum_1`
   - `tagum_2`

Normalization rules for `obs_v1`:

- Queue counts are clipped to `30` and normalized to `[0, 1]`.
- Waiting times are clipped to `120s` and normalized to `[0, 1]`.
- Active vehicle counts are clipped to `30` and normalized to `[0, 1]`.
- Pedestrian waiting count is clipped to `20` and normalized to `[0, 1]`.
- Emergency proximity is represented as normalized closeness, clipped to `[0, 1]`, where `1.0` means the emergency vehicle is at or near the stop line.

QL note:

- QL will use a discretized version of this observation space.
- DQL and PPO can use the continuous normalized vector.

QL discretization contract for `obs_v1`:

- queue features: `4` bins (`0`, `low`, `medium`, `high`)
- waiting features: `4` bins (`0`, `low`, `medium`, `high`)
- active vehicle count features: `4` bins
- pedestrian waiting feature: `3` bins (`0`, `some`, `many`)
- emergency presence: binary
- emergency proximity: `3` bins (`far`, `near`, `critical`)

## 7. State Features Required From Runtime

The active SUMO runtime already exposes some of the needed data:
- phase
- phase remaining
- queue information
- wait summaries
- throughput
- pedestrian counts
- emergency flags

Before training begins, the runtime must expose a clean RL-facing state extractor that can reliably provide:

1. per-approach queue length
2. per-approach waiting time
3. per-approach active vehicle count
4. pedestrian waiting count
5. emergency approach and distance/proximity
6. valid next-action mask if needed

This extractor should live near the active SUMO runtime, not in the dashboard callback layer.

## 8. Reward Function

Use one shared reward contract for QL, DQL, and PPO.

Locked reward formula `reward_v1`:

`reward = throughput_bonus - wait_penalty - queue_penalty - ped_penalty - emergency_penalty - switch_penalty`

Recommended term definitions:

- `throughput_bonus`
  - positive reward for vehicles completed since the last decision window
- `wait_penalty`
  - penalty proportional to average waiting time
- `queue_penalty`
  - penalty proportional to average queue length and maximum queue
- `ped_penalty`
  - penalty for pedestrian delay / waiting count
- `emergency_penalty`
  - strong penalty when an emergency vehicle is delayed near the junction
- `switch_penalty`
  - small penalty for unnecessary phase changes to prevent thrashing

Locked `reward_v1` weights:

- `+0.5 * throughput_delta_norm`
- `-1.0 * avg_wait_norm`
- `-0.8 * avg_queue_norm`
- `-0.4 * max_queue_norm`
- `-0.5 * pedestrian_wait_norm`
- `-1.5 * emergency_delay_norm`
- `-0.05 * switch_penalty`

Rules:

- Keep weights identical across QL, DQL, and PPO.
- Only tune weights after baseline evaluation shows a clear issue.
- Do not give one algorithm a custom reward formula.

## 9. Episode Definition

One episode equals one standardized scenario run.

Recommended episode structure:

1. Load one scenario
2. Apply one fixed seed
3. Reset the SUMO runtime
4. Run for a fixed duration
5. End and record metrics

Recommended initial values:

- warm-up: `20s`
- evaluation/control horizon: `300s`
- total training episode length: `320s`

Locked `episode_v1` policy:

- Decisions made during warm-up do not count toward reported evaluation metrics.
- Rewards may still be accumulated during warm-up for training stability.
- The official reported evaluation window is the final `300s`.

Episode termination conditions:

1. Fixed duration reached
2. SUMO runtime error
3. Invalid unrecoverable control state
4. Explicit early-stop safety condition if added later

## 10. Scenario and Seed Policy

All algorithm comparisons must be apples-to-apples.

Each evaluation batch must keep constant:

1. scenario
2. intersection
3. seed
4. duration
5. traffic density
6. pedestrian density
7. emergency mode
8. road-constraint settings

Only the controller may change.

Locked fixed comparison protocol `compare_v1`:

For every controller comparison batch:

1. use the same scenario
2. use the same intersection
3. use the same seed set
4. use the same duration
5. use the same density and disruption settings
6. only change the controller

Required seed set for `compare_v1`:

- `11`
- `22`
- `33`
- `44`
- `55`

Required reporting rule:

- report the mean
- report the minimum
- report the maximum
- report the standard deviation when available
- do not report only the single best run

Initial evaluation scope for `compare_v1`:

1. one completed scenario on `tagum_1`
2. one completed scenario on `tagum_2`
3. all four controllers run on both intersections using the same seed set

## 11. Baseline Comparison Contract

Every RL run must be comparable to Fixed-Time.

Required reported metrics:

1. average waiting time
2. average queue length
3. maximum queue length
4. throughput
5. average pedestrian delay
6. emergency clearance behavior
7. total phase switches
8. fairness across approaches

Recommended fairness metric:

- standard deviation of queue length or waiting time across approaches

Locked evaluation scorecard order:

1. average waiting time
2. average queue length
3. maximum queue length
4. throughput
5. average pedestrian delay
6. emergency clearance behavior
7. total phase switches
8. fairness across approaches

Primary success metric for controller ranking:

- lowest average waiting time, with throughput and emergency clearance used as tie-break context

## 12. Controller Provenance Labels

Every run must carry one clear provenance label.

Required values:

- `fixed-time`
- `ql`
- `dql`
- `ppo`
- `recorded-playback`

User-facing labels:

- `Fixed-Time`
- `Q-Learning`
- `Deep Q-Learning`
- `PPO`
- `Recorded Playback`

These labels must flow into:

1. run manifests
2. database records
3. reports
4. comparison views
5. replay metadata

## 13. Training Architecture

Training must happen offline, outside the main Dash request loop.

Recommended file layout:

1. `simulation/rl_env.py`
   - SMARTFLOW Gym-style environment wrapper over the active SUMO runtime
2. `simulation/rl_state.py`
   - RL observation extraction and normalization helpers
3. `simulation/rl_reward.py`
   - shared reward function
4. `simulation/rl_policy_runtime.py`
   - inference adapter used by dashboard/runtime mode later
5. `tools/train_ql.py`
6. `tools/train_dql.py`
7. `tools/train_ppo.py`

The Dash app should not train models inside normal page callbacks.

## 14. Inference Architecture

When RL is added to SMARTFLOW runtime, inference should plug into the active SUMO engine as a controller mode.

That integration point belongs near:
- [simulation/sumo_engine.py](simulation/sumo_engine.py)

The dashboard should only select the controller mode and display the results.

## 15. Model Persistence

The project already has direction for model/checkpoint persistence in the database layer.

Each trained model record should store:

1. algorithm
2. intersection support
3. training scenarios
4. reward version
5. observation version
6. action-space version
7. seed set
8. training date
9. checkpoint path
10. best evaluation score

Checkpoint storage should distinguish:

- QL table/policy artifacts
- DQL model weights
- PPO model weights

## 16. Comparison Page Contract

The future compare page should compare prerecorded runs first, not dual live runs.

Required compare inputs:

1. run A
2. run B

Validation rules:

- warn if scenario differs
- warn if intersection differs
- warn if seed differs
- warn if duration differs

Recommended initial compare targets:

1. Fixed-Time vs QL
2. Fixed-Time vs DQL
3. Fixed-Time vs PPO
4. QL vs DQL
5. QL vs PPO
6. DQL vs PPO

## 17. Versioning Rules

The RL contract must be versioned.

Initial versions:

- observation contract: `obs_v1`
- reward contract: `reward_v1`
- action contract: `action_v1`

These versions should be saved in:

1. trained model metadata
2. evaluation manifests
3. compare reports

## 18. Finalized Step 5 Summary

The following are now fixed for the first RL implementation pass:

1. observation space: `obs_v1`
2. action space: `action_v1`
3. reward formula: `reward_v1`
4. episode definition: `episode_v1`
5. evaluation metrics: locked scorecard order above
6. comparison protocol: `compare_v1`

## 19. Implementation Gate

Do not start QL, DQL, or PPO coding until these are confirmed:

1. observation fields are fully extractable from the active SUMO runtime
2. action application and safe phase-transition logic are defined
3. reward terms are finalized
4. standardized scenario/seed evaluation protocol is agreed

## 20. Immediate Next Step

The next implementation step after this contract is:

1. build the RL environment wrapper

After that:

2. implement QL
3. implement DQL
4. implement PPO
