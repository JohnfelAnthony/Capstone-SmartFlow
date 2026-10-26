# Traffic engine fix plan

Planned: **2026-10-25** (Asia/Singapore). Status: **P0-1, P1-2 step 1, P1-4 and the P1-3 pedestrian rule implemented 2026-10-25; the per-junction stopped-seconds counter (step 5), the `native-5` bump (step 6), P1-6 (raw DQL/PPO action in the app) and P1-5 (`reward_v3`) implemented 2026-10-26** (P1-3 fixed-time timing from field observation still open) (the engine version stayed `native-4` until the step 6 bump; see progress for evidence). Remaining fixes proposed and reviewed, not implemented. P1-2 deviation: the exit check became a lane-storage rule (everything on or committed to the exit lane must fit end to end), because the P0-1 "tail must already be clear" rule capped discharge at about 3.5 s per vehicle. P1-4 deviation: when `maximum_red_seconds` is not set, the cap defaults to 120 s or the plan's own fixed-time red, whichever is longer, instead of rejecting long fixed-time plans. Scope: critical and high findings from the October 25 engine review (`simulation/traffic_engine.py`, RL modules).

Navigation: [Start here](../README.md) · [Progress and handoff](PROGRESS_AND_HANDOFF.md) · [Architecture and plan](ARCHITECTURE_AND_PLAN.md) · [Research method](RESEARCH_METHOD.md)

## Why

The engine follows the current contracts: `native-4`, 22-value observation, five classes plus pedestrians, one RL junction, no emergency support. The review nevertheless found it is not yet fit for RL training or for comparisons that resemble real traffic.

**Re-measured during the plan review:**

- **Permanent lock-up on both networks.** Medium demand, seed 101.
  - **Default 5-junction network:** completed trips freeze at 47 from t≈900 s to 1800 s while pending demand rises to 329. All five junctions are held by stopped cars 1.41–3.85 m past the junction.
  - **Provisional 2-junction network:** completed trips freeze at 52 from t≈600 s and pending demand reaches 394. Each junction is held by a car stopped 3.75 m into Osmeña Street, one in each direction, so each blocks the other.
- **Junction capacity.** A saturated approach discharges one vehicle per **7.9 s (≈456 veh/h/lane)**: cars 7.9 s, turning cars 8.1 s, motorcycles 7.1 s, buses 9.6 s. Raising the approach speed limit from 30 to 50 km/h changes nothing, so the junction itself is the bottleneck.

**From the review, not re-measured:** the reward barely separates policies (always-NORTH −1.051 against always-PED −1.059), and an always-same-action policy left two approaches without green for 305 s.

## What it costs to change versions (checked against the data)

- **Trained models: nothing usable is lost.**
  - `data/models` holds 24 files, which make up 13 models and 6 checkpoints.
  - All of them were trained in June 2026 under `obs_v1` / `reward_v1` / `action_v1` and carry **no native contract**. `validate_metadata` (`simulation/model_contract.py`) already refuses them today.
  - The 18 rows in the `rl_models` table point at the same old artifacts.
  - So a retrain is required whatever this plan does. Any model trained on the provisional 2-junction network will need retraining again on the final study network, because models are tied to the network fingerprint.
- **Saved runs.**
  - Only **3 completed fixed-time runs** were recorded on `native-4`; there are **0 calibration records**.
  - After the bump, the metric gates (`src/lib/metrics.ts`, `services/metric_definitions.py`) show those 3 runs as unavailable.
  - Older runs that carry no `engine_version` are *not* gated. The dashboard's fixed-time baseline lookup should therefore explicitly require the current engine version, or it may compare against a pre-native run.
- **Recordings.** `simulation/timeline_engine.py:50` refuses any recording whose engine version or network fingerprint differs. The 21 runs with recordings cannot be replayed after the bump and must be regenerated if needed.
- **Version strings a bump touches:**
  - `simulation/traffic_engine.py` (`ENGINE_VERSION`)
  - `simulation/model_contract.py` (observation and action strings)
  - `simulation/metric_definitions.json`
  - `services/metric_definitions.py` (message text)
  - `simulation/dql_training.py` and `simulation/ppo_training.py` (`OBSERVATION_VERSION`, `REWARD_VERSION`)
  - `tools/train_ql.py`
  - `database.py` (column defaults)
  - `tests/test_native_cleanup.py:101-103`
  - `AGENTS.md`, `README.md`, and the architecture, progress, research-method and field-data docs that name `native-4` / `native-local-22-v2`.

**Recommendation:** batch every engine-behaviour change into **one** bump to `native-5`, then retrain once on the provisional network.

## Prioritised fixes

### P0-1 — Junction reservation deadlock (critical)

- **Problem (verified in source).** A vehicle's position is its centre. On leaving a connector it is placed at the lane start (`traffic_engine.py:504`).
  - **Entry check:** a car may enter when the downstream tail's rear is ≥ L/2 + MIN_GAP + 1 = **5.25 m** (`:467-468`).
  - **Release:** the reservation is released only when the car's centre reaches L/2 + MIN_GAP = **4.25 m** (`:509`).
  - **Following:** car following lets its front come no closer than MIN_GAP to the leader's rear (`:514`, `:537`), so behind a stopped car whose rear is at 5.25 m it can only reach a centre of **1.0 m**.

  It never releases while the downstream queue is still. Two queued junctions then block each other permanently. The same holds for every class; a bus can reach a centre of 1.0 m but needs 8.0 m.
- **Fix:** make entry guarantee release.
  - Release when the vehicle has fully left the junction: rear ≥ 0, i.e. centre ≥ L/2.
  - Allow entry only when the downstream tail's rear is ≥ **L + MIN_GAP + 1 m**. Keep the 1 m margin, because the car-following model creeps towards its standstill gap without ever reaching it exactly.
  - Add two reported metrics that should always read 0: **vehicles stopped inside a junction for longer than 30 s**, and a **gridlock detector** (no vehicle moved for 60 s while vehicles are present).
- **What P0-1 does not do:**
  - It removes the reservation deadlock, not physical gridlock. A loop of full lanes can still jam, as in real traffic; the detector makes that visible instead of silent. Loops exist on the 5-junction network. On the 2-junction network, boundary-to-boundary routes do not revisit a junction.
  - It barely changes capacity, roughly 0.5 s per vehicle.
- **Verify:**
  - A property test over every vehicle class pair (entering × leader): the standstill position allowed by the entry check is past the release threshold.
  - A regression test reproducing the two-junction mutual block.
  - Medium and high demand for 1800 s on both networks: completions keep increasing after t=900 s, both new metrics stay 0, conservation counters unchanged.
  - The existing `test_blocked_downstream_storage_prevents_junction_entry` still passes.
- **Engine version:** `native-5`.
- **Manuscript:** no medium/high-demand result from `native-4` may be cited.
- **Size:** small.

### P1-2 — Junction capacity far below real traffic (high)

- **Problem (verified):**
  - Only one vehicle may occupy a junction (`reservations` keyed by junction).
  - Vehicles may reserve only within 1 m of the stop line, so every vehicle brakes towards the line even on green (`:519-529`).
  - Connector speed is capped at 4 m/s (`:501`, `:531-532`).
  - Vehicles on a connector have **no car following**: today only one can be there.
  - The exit-space check ignores vehicles still on connectors (`:468`).
- **Fix (step 1, matches the engine's exclusive per-approach phasing):**
  1. **Approach-scoped occupancy:** at a signalized junction, any number of vehicles from the approach that has green may be inside at once. Their movements diverge, so they do not conflict under exclusive phasing. Vehicles from another approach, and pedestrians, may start only when the junction is empty, which also gives safe clearance after yellow/all-red. All-way stops keep single occupancy.
  2. **Car following on connectors,** and across the connector-to-lane boundary.
  3. **Exit space counts vehicles on connectors** bound for the same outgoing lane.
  4. **Look-ahead permission:** a vehicle checks permission once it is within its stopping distance of the line, so a moving platoon does not brake to the stop line on green.
  5. **Speed by movement:** through movements at the approach speed, turns at a separate turning speed (a calibration parameter, start around 5–7 m/s).
- **Realistic target.** Steady-state capacity of the engine's own car-following settings (a = 1.5 m/s², T = 1.2 s, s0 = 2 m, car 4.5 m):
  - about **1,400 veh/h/lane at 30 km/h**;
  - about **1,740 at 50 km/h**;
  - about **1,100 at a 5 m/s turn**;
  - about **960 at today's 4 m/s cap**.

  Typical urban saturation flow is about 1,500–1,900. Getting there is therefore partly **calibration**: approach and turning speeds, time headway T, and per-class lengths, set against discharge headways measured at the Tagum sites. Field Observer crossing events give stop-line timestamps for this. The automated plausibility test should pin today's synthetic numbers and the calibrated values once known.
- **Tests to rewrite:** `tests/test_native_engine.py::test_heavy_traffic_preserves_gaps_and_junction_exclusivity` asserts one connector vehicle per junction. Replace it with the new invariants:
  - all occupants come from one approach;
  - no pedestrian crosses while vehicles are inside;
  - gaps hold on connectors too.
- **Step 2 (conflict-based reservations)** is only needed if phases start grouping non-conflicting approaches together (see P1-3).
- **Engine version:** `native-5`.
- **Manuscript:**
  - Describe junction occupancy as approach-scoped.
  - Report the synthetic saturation-flow check, and the field-calibrated headways when available.
  - **Fallback if time runs out:** narrow the claim. Results become relative comparisons under a capacity-limited junction model, not throughput predictions (`RESEARCH_METHOD.md`: "revise the model or narrow the claim").
- **Size:** medium.

### P1-3 — Fair fixed-time baseline (high)

- **Problem (verified):**
  - Every approach gets its own exclusive phase.
  - A pedestrian phase of `green_seconds` (14 s default) runs every cycle, even with no pedestrians (`:164`).
  - Validation *requires* the pedestrian phase in every `phase_order` (`scenario_config.py:137-140`).
  - RL is never forced to serve it unless a pedestrian waits 90 s (`pedestrian_max_wait`).

  The two controllers are therefore held to different pedestrian rules, which inflates any RL gain.
- **Correction to the first draft:** coordination offsets already exist (`offset_seconds` per signal plan, `traffic_engine.py:174`). Only the scenario defaults are 0, so J1/J2 offsets are a scenario choice, not code.
- **Fix:**
  - Apply **the same pedestrian rule to both controllers**. Either the pedestrian phase is on-call for both (skipped when nobody waits), or it is served every cycle by both. On-call needs a `Signal.step` change and relaxed validation.
  - Base the fixed-time plan on the **signal timing observed at the Tagum sites**, if possible.
  - Only when no field timing exists, derive green splits from demand (Webster-style). Do that *after* P1-2, since such derivations depend on capacity.
- **Engine version:** `native-5`.
- **Manuscript:**
  - State how the baseline plan was set, and that both controllers follow the same pedestrian rule.
  - Drop any improvement figure produced before this fix.
- **Size:** small (shared pedestrian rule) to medium (timing derivation).

### P1-4 — Maximum wait without green too long (high)

- **Problem (verified).** A demanded approach is forced to green only after `maximum_green × services` without one (`:413`).
  - The service count includes pedestrians, so the bound is 60 × 5 = **300 s**.
  - Plans may set `maximum_green` up to 180 s, which would allow up to **900 s**.
  - The guard runs for fixed-time junctions too.
- **Fix:**
  - Add `maximum_red_seconds` to the signal plan (default 120 s): the longest a demanded approach may wait for green, under any controller.
  - Validation rejects a fixed-time plan whose own cycle would exceed it, so a legal baseline never trips the guard.
  - The default plan's cycle is 4 × (14 + 3 + 1) + (14 + 1) = 87 s.
- **Engine version:** `native-5`.
- **Manuscript:** safety-constraints description — the engine, not the policy, guarantees green within the bound.
- **Size:** small.

### P1-5 — RL reward cannot tell good policies from bad (high)

- **Problem (verified):** `calculate_reward` (`rl_reward.py:24-40`) uses network-wide running values taken from `_last_metrics` (`traffic_engine.py:611`):
  - average wait over completed and active trips, capped at 120 s;
  - running mean queue over all junctions;
  - running maximum queue over all lanes, which never decreases;
  - completed trips, including trips that never pass the controlled junction.

  The observation's per-approach "wait" (`rl_state.py:119`) is each vehicle's **whole-trip** stopped time, so it includes waits at the other junction.
- **Fix (`reward_v3`):** add an engine counter of **stopped vehicle-seconds per junction approach**. The reward then uses only the controlled junction's per-interval terms:
  - change in stopped seconds;
  - current approach queue;
  - vehicles discharged (`vehicle_passages` delta);
  - waiting pedestrians;
  - switch penalty.

  Remove the running maximum queue. Take the normalisation constants from `rl_state.py`, not retyped literals.
- **Synergy:** the same counter gives a **per-junction delay** metric, so the evaluation can report J1, where RL acts, separately from the network-wide figures, where J2 dilutes the effect.
- **Verify:** always-NORTH, always-PED and round-robin must separate clearly in mean reward. A trained DQL must beat round-robin on the evaluation KPIs over a fixed seed set.
- **Version:**
  - the counter is part of `native-5`;
  - `reward_v3` in training metadata;
  - if the observation upgrades below are taken, a new observation version.
- **Manuscript:** rewrite the reward equation. State that the training reward is local and per-interval while the reported KPIs are network-wide plus J1-local.
- **Size:** medium.

### P1-6 — App behaviour differs from training (high, simpler than first drafted)

- **Corrected facts:**
  - **QL already** trains and runs with the action mask (`ql_training.py:59-83`).
  - **DQL and PPO** train with the raw action: the environment calls `apply_rl_action` with no mask (`rl_env.py:163-168`). In the app, DQL takes the **best allowed** action by Q-value (`rl_policy_runtime.py:155`), and PPO swaps a blocked action for the **first allowed** one (`:210-213`).
  - The swap matters because a request for the current approach clears any queued switch (`traffic_engine.py:65`).
  - Only the swapped action is recorded (`:740`).
  - `sb3-contrib` (maskable PPO) is **not installed**.
- **Fix:** for DQL and PPO, **apply the policy's own action in the app exactly as in training**. The engine already makes every request safe:
  - during minimum green it queues;
  - during clearance it is ignored;
  - for a missing approach it is refused.

  The recorded decision then holds the policy's own request plus the engine's applied/reason result, which meets the handoff rule "requested action, applied result and any override must remain distinguishable". This needs no new dependency, no retrain on its own, and no action-contract bump. QL stays masked in both training and the app.
- **Manuscript:** describe the engine-side safety layer (minimum green, clearance, maximum red), applied identically in training and deployment, and report safety-override counts.
- **Size:** small.

### P1-7 — RL training budget and conditions (high, new in review)

- **Problem:**
  - The default training is `episodes` 10 × (300 s ÷ 5 s) = **600 decisions** (`training_settings.py:46-47`, `dql_training.py:67`). DQL and PPO need on the order of 10⁵ decisions.
  - Each episode starts from an empty network with a 20 s warmup, so policies mostly see light traffic, while dashboard evaluations run 5–15 minutes into congestion.
- **Measured:** the environment runs at about **44 decisions/s** on the 2-junction network at medium demand. 100,000 decisions take about 40 minutes, more under heavier traffic.
- **Fix:**
  - Set realistic budgets (e.g. ≥ 100k decisions for DQL/PPO; QL as needed) and record them in the model metadata.
  - Use warmups long enough to reach the evaluated traffic state (e.g. 300 s).
  - Train on the scenarios and demand windows that will be evaluated.
  - Keep evaluation seeds separate from training seeds.
- **Manuscript:** report the training budget, warmup, seeds and learning curves, and distinguish training reward from evaluation results.
- **Size:** small code change; the cost is compute time.

## Order of work

1. **P0-1 deadlock** with its tests. Nothing else is trustworthy until it lands.
2. **P1-2 capacity, step 1**, with the rewritten occupancy tests and the synthetic saturation-flow test.
3. **P1-4 maximum red** and the plan validation.
4. **P1-3 shared pedestrian rule.** The fixed-time timing derivation follows once the capacity numbers are known.
5. **Engine counter for per-junction stopped seconds** (needed by P1-5 and the J1-local metric).
6. **Bump to `native-5`** across every version string listed above.
   - Make the dashboard baseline lookup require the current engine version.
   - Regenerate test fixtures.
   - Record fresh fixed-time baseline runs.
7. **P1-6 app/training parity.** It is independent of the version and can also land at any earlier point.
8. **P1-5 `reward_v3`**, plus the optional observation upgrades.
9. **P1-7 training settings**, then train QL, DQL and PPO on the provisional 2-junction network.
10. **Evaluate** fixed-time against each RL method on matched scenarios and held-out seeds. Report network-wide and J1-local results. Update progress, architecture (new decision record) and the manuscript sections named above.

## Impact summary

| Fix | Engine version | Model / training contract | Effect on existing artifacts | Manuscript |
| --- | --- | --- | --- | --- |
| P0-1 deadlock | `native-5` | engine field | 3 `native-4` runs become history; 21 recordings unplayable | no `native-4` medium/high results |
| P1-2 capacity | `native-5` | engine field | as above | junction model description; saturation-flow evidence or narrowed claim |
| P1-3 baseline | `native-5` | — (action set unchanged unless phases are grouped) | as above | baseline derivation; same pedestrian rule |
| P1-4 maximum red | `native-5` | engine field | as above | safety constraints |
| P1-5 reward | counter in `native-5` | `reward_v3` (+ observation version if upgraded) | none extra | reward equation; local reward vs reported KPIs |
| P1-6 parity | — | — | none | safety layer; override counts |
| P1-7 training | — | budget recorded in metadata | none | training budget, warmup, seeds, learning curves |

No trained model is lost by any of these: none of the existing 24 files is valid today.

## Optional items for the same retrain (medium)

- **Observation upgrades** (each changes the observation version, so take them in this retrain or not until the next):
  - elapsed green normalised by maximum green, not the 10 s minimum;
  - a yellow / all-red flag (today yellow looks the same as green, and all-red shows as all zeros);
  - a pending-request flag;
  - time since each approach last had green;
  - per-approach wait measured at this junction rather than over the whole trip.
- **Hidden boundary delay:** include vehicles waiting at the network edge in the reward's wait term, closing the possible spill-back exploit.
- **Yellow dilemma zone:** let a vehicle enter on yellow when it cannot stop comfortably. Today the travel clamp stops it with unlimited deceleration (`:537`).
- **Class-specific driving parameters** for motorcycles, buses and trucks (acceleration, headway). This is engine behaviour, so it goes in the same `native-5` bump.
- **Pedestrian start window:** allow a pedestrian to start at any point in the pedestrian green while enough clearance time remains, not only in the first 0.5 s (`:455`).

## Deadline note

The provisional deadline in the project overview is about **October 27, 2026** (unconfirmed). If it holds:

- **Do:** P0-1, P1-4, the shared pedestrian rule (P1-3), P1-6, P1-5, P1-7 and one retrain. Each is small or medium; training adds hours of compute.
- **Capacity (P1-2):** state the **narrowed-claim fallback** in the manuscript instead.
- **Never present RL improvement figures from the `native-4` build.** Label provisional-network results as pipeline evidence, to be repeated on the final study intersections.

## Review log

The first draft of this plan was checked against the source and data on 2026-10-25. Corrections:

- **Trained models.** The draft said all 24 model files would be invalidated by the bump. In fact none is valid today (June 2026, `obs_v1`, no native contract), so the bump costs no usable model.
- **P0-1.** The deadlock threshold arithmetic was confirmed and reproduced on both networks. Added: a 1 m margin; that P0-1 removes the reservation deadlock but not gridlock; the gridlock detector; and that P0-1 alone barely improves capacity.
- **P1-2.** Step 1 was redesigned around exclusive per-approach phasing (approach-scoped occupancy, connector car-following, exit space counting connector vehicles, look-ahead permission). The draft target was replaced by capacity values computed from the engine's car-following parameters, and calibration against field discharge headways was added. The occupancy test that will need rewriting is named.
- **P1-3.** Offsets already exist. The pedestrian phase is mandatory in validation. Reframed as "same pedestrian rule for both controllers", with field-observed timing preferred.
- **P1-4.** The bound counts the pedestrian service and can reach 900 s. The guard also affects fixed-time, so plan validation is added.
- **P1-5.** Confirmed. Added the per-junction stopped-seconds counter and the J1-local evaluation metric, and noted that the observation's "wait" is whole-trip.
- **P1-6.** Corrected: QL is already masked; DQL already uses the best allowed action; maskable PPO is not installed. The fix is now "apply the raw action in the app exactly as in training": small, with no dependency or contract change.
- **P1-7 (new).** The default training budget of 600 decisions is too small, and warmup starts from an empty network. Environment speed was measured at about 44 decisions/s.
- **Bump list.** The full list of version strings, the recording and baseline consequences, and the baseline-lookup filter were added.
