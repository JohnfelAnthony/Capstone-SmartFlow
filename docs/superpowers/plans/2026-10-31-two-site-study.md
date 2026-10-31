# SmartFlow Two-Site Study Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** SmartFlow can simulate the two confirmed Tagum intersections, which have no traffic light, as separate sites. On the same demand and seeds, it compares three conditions: today's informal "first come, first served" operation, a proposed traditional fixed-time signal, and a proposed RL signal.

**Architecture:**
- **One network per site.** Each site is its own road-network file, registered by id. A scenario names its network, and every engine, recording, model and screen is built from that network.
- **Today's operation as a run setting.** A new junction mode, `first_come`, models today's operation. A run-level control mode, `no-signal`, applies it without changing the scenario, so all three conditions share one configuration and pair in Compare Runs.
- **Signals for the proposals.** Signals gain grouped phases and a green time per phase. A Webster tool designs the traditional plan from counts, and RL serves phase groups under a new contract (`native-7`).

**Tech Stack:**
- Python 3.13, FastAPI, unittest/pytest for the backend and engine.
- React 19, TypeScript, Vite and Vitest for the frontend. Tests cover pure helpers in `src/lib`; screen wiring is checked in the browser.
- Field Observer for the video counts: a separate Python tool with its own `.venv`.

**Spec:** Part 0 of this document. The design was confirmed with the owner on 2026-10-31.

**Baseline:** source as at commit `51880ab` (`feat/mixed-traffic`, PR #2). File:line references are to that commit. PR #2 was merged into `main` on 2026-10-31 (`3b1d7f6`); work happens on a branch from `main`.

**Revised 2026-10-31** after an outside review. The changes:
- a validation gate before RL training and final results;
- arrival order treated as a hypothesis to check;
- the phase order checked when a model is loaded;
- the signal-design contradictions fixed;
- video timing aligned with the network boundaries;
- separate development and final seeds;
- fingerprint-based matching;
- the full set of acceptance cases.

**Second review revision, 2026-10-31:** independent confirmation after a validation failure; separate simulation and measurement origins with observed lead-in demand; conflict- and eligibility-aware arrival-order measurement; and saved per-site calibration with validation evidence bound to the exact model. The affected interfaces, tests, field work and gates below are part of this revision.

The first milestone is now one site whose no-signal model passes validation (see "Order of work").

---

## Global Constraints

- **Engine version.** The engine stays `native-6` until Task 17, which makes the single bump to `native-7`, following architecture decision D26. Until then, existing behaviour is unchanged: every new mode and plan field is opt-in, and the 5- and 2-junction networks keep their current approach names and results.
- **Vehicle classes.** Car, motorcycle, tricycle, bus and truck, plus pedestrians. The retired emergency feature is not restored.
- **Scenarios.** `engine_config` is the scenario contract. Saved settings must survive editing, running, training and evaluation unchanged.
- **History.** Old networks, scenarios, models, recordings and reports are kept as history and never relabelled.
- **Provisional values.** Every new behaviour value carries a comment beginning `# Provisional:` that says what will calibrate it, following the `TAGUM_PROVISIONAL_MIX` comment at `simulation/scenario_config.py:17`. Values are never tuned to make a test pass.
- **Backend tests.** Run as `.venv/Scripts/python.exe -m pytest tests -q --basetemp "$TEMP/sf_<task>"`. Never set `SMARTFLOW_DB_PATH`, `SMARTFLOW_RL_JOB_DIR` or `SMARTFLOW_IMPORT_DIR` for suite runs. Integration tests use scratch databases, as `tests/test_record_baselines.py` does.
- **Frontend tests.** `npx vitest run`, `npx tsc -b`, `npm run lint`, `npm run build`.
- **Field Observer tests.** Run from `tools/field_observer`: `.venv/Scripts/python.exe -m unittest discover -s tests -v`.
- **Owner approval.** Downloading from Overpass, writing to `data/smartflow.db` and starting long RL training each need the owner's explicit approval at the time.
- **Seeds.** Three sets that never overlap:
  - **Training:** 11–55, as today (`services/training_settings.py:60-65`).
  - **Development:** 101–110. Used for calibration, acceptance, scale and bin decisions, browser checks and day-to-day evaluation.
  - **Final evaluation:** 201–220. Untouched until Task 29: no task before it runs, prints or tunes against them, and the ledger records their first use.
- **Validation gate.** No full RL training and no final comparison results (Task 29) until the site's no-signal model passes validation (§0.15).
- **Commits.** Messages are plain imperative sentences, like the repo's own history. Each ends with the line `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`. Never commit `.claude/`.
- **Labels.** User-facing text uses these exact labels:
  - **No signal (first come, first served)**
  - **Traditional signal (fixed-time)**
  - **SmartFlow RL (QL)**, **SmartFlow RL (DQL)** and **SmartFlow RL (PPO)**

## Review Focus

These are the seven failure modes most likely to hurt a user that the spec implies but no feature test would naturally hit. Each has a pinned test in the task that owns the code.

1. **A site network rebuilt after scenarios were saved on it**, even when every lane id survives (for example, after field widths are added). Running such a scenario must give a clear "network changed, migrate the scenario" message, not a crash or a silent run on different roads. *Task 6: `test_scenario_on_a_rebuilt_site_network_reports_a_clear_error` and `test_a_width_change_with_the_same_lane_ids_is_detected`.*
2. **Constant main-road flow in no-signal mode.** A side-road vehicle that reached the junction first must go before main-road vehicles that arrived later; it must not wait forever. *Task 10: `test_side_road_is_served_in_arrival_order_under_constant_main_road_flow`.*
3. **A future site whose junction has more than four legs.** It must be refused with a message naming the junction, not silently given two legs with the same name. *Task 3: `test_more_than_four_legs_is_refused`.*
4. **Field Observer bins with incomplete coverage or unfinished review.** They must never become zero demand. *Task 20: `test_incomplete_coverage_in_the_window_is_refused`.*
5. **Webster inputs whose total flow ratio is 1 or more** (oversaturated). They must be refused with a clear message, never turned into a negative or huge cycle. *Task 15: `test_oversaturated_demand_is_refused`.*
6. **No-signal mode when the earliest arrival cannot move** because its exit is full. Later conflicting vehicles whose exits are clear must still go; one stuck vehicle must not stop the junction. *Task 10: `test_an_earlier_vehicle_with_a_blocked_exit_does_not_hold_others`.*
7. **A model loaded on the same site with its phases reordered.** `SERVE_PHASE_1` would mean a different movement, so it must be refused, not run. *Task 17: `test_a_model_is_refused_when_the_phase_order_differs`.*

---

## Part 0 — Design (the spec)

### 0.1 Decisions (owner, 2026-10-31)

1. The study uses two confirmed intersections. **Neither has a traffic light.** Video shows informal "first come, first served" driving with no enforcer.
2. The sites are about 2.6 km apart. Each is its own network with its own scenarios and RL model. A scenario chooses its site. The corridor between the sites is **not** modelled.
3. **Three-way comparison** on matched scenario, demand and seeds:
   - **no signal**, today's condition and the only one validated against video;
   - **traditional signal (fixed-time)**, a proposal;
   - **SmartFlow RL**, a proposal.
4. Dashboard KPI changes are measured against the matching **no-signal** run.
5. The traditional plan is designed by a **built-in Webster tool** from counts.
6. Signals support **grouped phases**, where opposite approaches can go together. Otherwise one-approach-at-a-time signals would be unfairly slow against the no-signal case.
7. The existing video covers **midday only**. Peak conditions may be studied only as clearly labelled synthetic scaling until peak video exists.
8. **Validation comes first** (review, 2026-10-31). The first milestone is one reviewed site whose no-signal model passes tolerances fixed in advance (§0.15). Full RL training and the final comparison wait for that.

### 0.2 The sites (OpenStreetMap, looked up 2026-10-31; every fact must be checked in the field)

**Site A — Capitol Circumferential Road × Dalisay Gante Road.** The owner's pin is at 7.4617375, 125.8026196. The OSM junction node is 7.4617206, 125.8026721, 6 m away.

| Leg | Road | OSM way | Class / tags | Leg direction (from centre) | Name today |
|---|---|---|---|---|---|
| North | Dalisay Gante Road | 1225836056 | secondary, `lanes=4`, concrete, two-way | 0.3° | north |
| East | Capitol Circumferential Road | 841643191 | secondary, ref 908, `lanes=4`, `maxspeed=40` | 90.3° | east |
| South | Dalisay Gante Road | 180968793 | secondary, `lanes=4`, concrete | 180.4° | south |
| West | Capitol Circumferential Road | 1225667612 | secondary, ref 908, `lanes=4`, `maxspeed=40` | 273.6° | west |

- It is a regular cross, and the names are already distinct.
- OSM `lanes=4` on a two-way road means 2 lanes and 6.6 m per direction unless a field width is entered.
- Minor roads join close to the centre:
  - a service road 22 m along Dalisay Gante;
  - a residential street 48 m along Capitol Circumferential;
  - other service or unclassified roads at 61, 68 and 72 m.
- The first larger junctions are Gazmen Road (tertiary), about 225 m along Dalisay Gante, and a residential/unclassified junction about 226 m along Capitol Circumferential.

**Site B — Davao–Agusan National Highway × Sobrecarey Street / Dao Street.** The owner's pin is at 7.4382646, 125.8025576.

- **The highway is a dual carriageway.** It runs north-east to south-west (38° / 217°), as two one-way trunk roads with `lanes=3` and `width=9` each, ref 1, and `maxspeed=30` on part of it.
- **There are two junction points, 8.6 m apart**, joined by a median link (way 1113256997):
  - 7.4383355, 125.8025667 — the south-west-bound carriageway (ways 1144654452 in, 288252870 out), with Sobrecarey Street;
  - 7.4382877, 125.8026277 — the north-east-bound carriageway (ways 678794201 in, 1144654495 out), with Dao Street.
- **The cross streets:**
  - Sobrecarey Street: secondary, `lanes=4`, two-way, leaving at **354°**, about 45° off the highway.
  - Dao Street: tertiary, `lanes=2`, `maxspeed=40`, two-way, leaving at 128°, at right angles to the highway.
- **Approach-name clash.** Rounding each leg to the nearest compass point (`simulation/road_network.py:182`) names **both** Sobrecarey (354°) and the highway's north-east leg (38°) "north". The engine would give them green together and admit them together. Task 3 fixes this.
- **Nearby joins:** a residential road 23 m along Dao; a service road 30 m along Sobrecarey; residential roads 75–76 m along the highway; Bonifacio Street (tertiary) about 186 m along the highway; Osmeña Street about 377 m. Footways 15 m from the centre are likely crossings.

**Both sites lie outside the cached extract** `data/networks/tagum_osm.json` (bbox 7.443–7.451 N, 125.801–125.810 E). Its query (`tools/import_osm_network.py:21`) also leaves out `trunk` roads.

**Field checklist for each site** (Team F2):
- lanes and painted markings for each leg;
- carriageway width per direction;
- median opening width, whether U-turns happen there, and which turns are banned;
- **at Site B, whether vehicles cross the median opening in one movement or stop and wait inside it**, and how often (this decides §0.3's join);
- driveways and side streets within 100 m and roughly how busy they are;
- tricycle or jeepney stops and terminals within 50 m;
- crosswalk positions;
- the farthest midday queue on each approach, measured from the centre;
- camera positions;
- one upstream "arrival" counting line per approach and one "exit" line per exit, with each line's distance from the centre measured. Each arrival line must be upstream of the farthest midday queue on its approach (§0.11).

### 0.3 Site networks

- **Single junction.** A site network has exactly one non-boundary node at the site centre. The projection origin is the centre, so the junction sits at (0, 0).
- **Joined junction points.** Junction nodes within `join_radius_m = 25` of the centre where at least two **major** ways meet are merged into that one junction. Major classes are trunk, primary, secondary and tertiary, and their `_link` roads. Ways running only between merged nodes, such as Site B's median link, are dropped.
- **Site B's join is a modelling assumption,** not a fact. It holds only if the field check (F2) shows vehicles crossing the median opening in one movement.
  - The Site B network built in Task 4 is labelled **provisional** until then. Its `source.assumptions` gains "Median crossing modelled as one movement; pending field check".
  - If F2 shows vehicles regularly stopping inside the median, the engine cannot represent it: a 9 m link fails the junction-clearance rule ("Road … too short for junction clearance", `simulation/road_network.py:176-177`). The owner then decides whether Site B continues with that limitation stated in every Site B result, or is replaced. Task 28 records the decision.
- **Pass-through.** Each leg follows its OSM way chain outward. It passes through nodes where only minor ways join (residential, unclassified, living_street). Service roads are not downloaded at all.
- **Leg length.** A leg ends at the shorter of:
  - `approach_m`: 250 m by default, or a per-leg value keyed by the leg's first OSM way id;
  - the next junction where another **major** way joins, minus 10 m.

  A leg that would end up shorter than 30 m is refused, never silently dropped: `ValueError("Leg along <name> (way <id>) is only <x> m; raise --approach or check the map")`, with x to one decimal.
- **Ids and names.** Network ids are `tagum_site_a` and `tagum_site_b`, at most 24 characters (render frames cut the network id at 24, `services/render_frame_service.py:227-230`, and signal ids at 16, `:186`). Names are "Site A — Capitol Circumferential Rd × Dalisay Gante Rd" and "Site B — National Highway × Sobrecarey St / Dao St".
- **Recorded assumptions** in `source.assumptions`:
  - "Lane counts from OSM lanes tags; carriageway widths need field measurement"
  - "30 km/h study speed; not a verified posted limit"
  - "Driveways, service roads and minor side streets along approaches are not modelled"
  - "No traffic signal exists today; signal plans are proposals"
  - "Approach length N m per leg unless field queue reach needs more"
  - "Synthetic demand until Field Observer counts are imported"
- **Existing networks unchanged.** `tagum_network.json` and `tagum_network_2j.json` stay exactly as they are, with the same id and the same results.

### 0.4 Approach names

- If rounding gives every incoming leg of a junction a different compass name, those names stay.
- Otherwise the incoming legs are sorted by travel heading. Each candidate assignment gives the legs distinct names in the same circular order (west → south → east → north as the heading turns anticlockwise). The chosen assignment minimises the total angle between each leg's heading and its name's heading, with ties broken by lane id.
- A junction with more than four incoming legs raises `ValueError("Junction <id> has <n> approaches; SmartFlow supports at most four")`.
- The engine, RL and renderers keep using `north`/`east`/`south`/`west` internally. Screens show street names wherever a name exists.

### 0.5 Each scenario picks its network

- **Registry.** `data/networks/registry.json` lists site networks by id. The default id `tagum_network` always resolves to the active network (`NETWORK_PATH`, which respects `SMARTFLOW_NETWORK_PATH`), as today.
- **Scenarios.** The `scenarios.network_id` column (`database.py:138`) decides the network for every run, recording, training job, evaluation, option list, visual map, import and backup.
- **Recordings** already embed their network (`services/timeline_generator.py:102-103`). Playback checks the recording against that embedded network, not the active one.
- **Changed networks.** Saving a scenario stores its network's fingerprint in a new `scenarios.network_sha256` column. Configuring a scenario raises "Scenario settings do not match network '<id>'; the network changed since this scenario was saved — migrate the scenario." in either case:
  - the stored fingerprint differs from the network's current fingerprint (this catches width changes that keep every lane id);
  - the settings name lanes or junctions the network no longer has.

  Scenarios saved before this change have no stored fingerprint. They keep today's lane and junction check, and get a fingerprint the next time they are saved.
- **Matching runs.** Two runs are "the same experiment" only when their comparison key matches. That is the key `compare_key` already builds (`backend/main.py:1186-1198`): engine version, network fingerprint, seed, duration, measurement start, demand fingerprint, and the configuration apart from routing. A matching scenario id and seed is never enough, because a scenario can be edited between runs.

### 0.6 No signal: first come, first served (junction mode `first_come`)

1. **Arrival.** A vehicle *arrives* on the first tick its front is within `APPROACH_ZONE_M = 30.0` (provisional) of its stop line, on a lane into a `first_come` junction. Its `approach_arrival` time is kept until it enters the junction.
2. **Approach speed.** Inside that zone, an uncommitted vehicle's desired speed is capped at `FIRST_COME_APPROACH_SPEED_MPS = 4.0` (about 14 km/h, provisional).
3. **Commit.** At the usual commit point (`simulation/traffic_engine.py:1335-1343`) a vehicle may commit only when **all** of these hold:
   - its exit has space (`_exit_has_space`);
   - it is not held by the fixed order of its own approach (`_must_wait_at_line`);
   - its path would not hit a vehicle standing near a stop line (`_sweep_blocked`);
   - its path does not meet the remaining path of **any** committed vehicle at the junction, from any approach (`_meets_committed_path`, new);
   - no waiting vehicle on another approach that **arrived earlier, could go now and whose path crosses its own** (`_first_come_permission`, new; settled once per junction per tick, as `_stop_priority` is at `:1261-1276`).

     "Could go now" means its exit has space, it is not held by its own approach's order, and its path is clear of committed and standing vehicles. An earlier vehicle that cannot move, because its exit is full or a vehicle ahead of it holds it, does **not** hold anyone else. This is the same skip `_stop_priority` already applies to all-way stops.
4. **Shared junction.** Vehicles whose paths do not meet may be inside the junction together, from any approaches. The one-approach rule in `_junction_open_to` (`:704-708`) does not apply.
5. **No forced stop.** A vehicle stops only when it must wait.
6. **Pedestrians** cross only when no vehicle is in the crossing (the all-way-stop rule at `:619`).
7. **Display.** No signal heads, no phase, no timer. The controller label is "No signal (first come, first served)".
8. **RL** cannot control a `first_come` junction.
9. **Calibration from video** (Task 28, measured with the Task 26 tool) uses the pre-declared parameter set in §0.15.
10. **Arrival order is a hypothesis, not a fact.** Informal traffic does not show that drivers follow strict arrival order from 30 m away. The day-1 video tests it.
    - **Measure:** use the Task 26 eligible-pair definition: conflicting movements from different approaches, timed at the reviewed priority-zone boundaries, with observable readiness. Demand counting lines are not priority-arrival lines. Nonconflicting movements and an earlier vehicle that cannot proceed do not establish an order violation.
    - **Threshold:** the team freezes the acceptance share, pair rules and minimum evidence requirements in `data/sites/validation_criteria.json` before inspecting held-out outcomes (Team F6). Insufficient evidence is `INCONCLUSIVE`, not a pass or a rejection of the hypothesis.
    - **If a site falls below it,** first come, first served is rejected for that site. The no-signal model must be revised before validation can pass, for example to main-road priority with side-road gap acceptance (a new mode; a separate plan with the owner's approval). That site does not continue to Task 29 until a revised model passes.

### 0.7 Run-level control `no-signal`

- `control_mode="no-signal"` sets every junction of the run to `first_come`, whatever the scenario's signal plans say. It survives `start()`, which rebuilds signals (`simulation/traffic_engine.py:241-258, 361`).
- The engine sets these values, which the run record stores:

  | Field | Value |
  |---|---|
  | `controller_provenance` | `"no-signal"` |
  | `controller_type` | `"no_signal"` |
  | label | "No signal (first come, first served)" |
  | `experiment["control"]["junction_control"]` | `"first_come"` |

- `experiment["config"]` stays identical to the fixed-time and RL runs of the same scenario. Compare Runs therefore pairs all three as a `"signal"` comparison (`backend/main.py:1201-1225`).
- Choosing `fixed-time` or an RL model turns no-signal off.

### 0.8 Grouped phases and a green time per phase

- **Phase groups.** Each `phase_order` item is an approach name, `"pedestrian"`, or a list of two or more approach names (a group). Every available approach appears exactly once across the items, and `"pedestrian"` exactly once. Example: `[["north","south"],["east","west"],"pedestrian"]`. Plans with a plain list of strings load exactly as before.
- **In the engine** a group's key is its names joined with `+`, in plan order (`"north+south"`). `Signal.serves(approach)` is true for every approach in the current phase.
- **During a group's green**, vehicles from every approach in the group may enter. Movements in the group that conflict (for example, a left turn against oncoming through traffic) are kept apart by the §0.6 path rules (`_meets_committed_path`, `_sweep_blocked`). That makes the turns *permissive*. Protected turn phases are out of scope.
- **Per-phase greens.** `phase_greens` is optional: a list of numbers, one per `phase_order` item, each between `minimum_green` and `maximum_green`. Without it, every phase uses `green_seconds`, as today.
- **The walk phase stays required.** Every plan still has `"pedestrian"` exactly once, as `simulation/scenario_config.py:166-170` requires today.
- **Cycle and red.** Cycle = Σ (green_i + all_red + yellow, with no yellow for the pedestrian phase). A **vehicle** phase's fixed red = cycle − its green. `fixed_red_seconds` returns the largest **vehicle-phase** red, and the `maximum_red_seconds` check (a guard for vehicle approaches, `simulation/traffic_engine.py:75-76`) uses that.
- **The walk phase's own red** (cycle − walk green) is separate. It sets `walk_interval`, the longest RL may leave the walk unserved under `every_cycle` (`:79-80`). It never counts towards `maximum_red_seconds`.

### 0.9 Webster plans

**Inputs:**
- `phase_order`: vehicle phases, plus an optional `"pedestrian"`. The formula works with or without a walk phase. `plan_from_result` refuses a result without one, because every scenario plan needs a walk phase (§0.8): `ValueError("A scenario plan needs a walk phase; include 'pedestrian' in phase_order")`.
- design flow per approach in PCU/h;
- saturation flow per approach in PCU/h;
- `yellow_seconds` (3), `all_red_seconds` (1), `startup_lost_seconds` (2, provisional);
- `pedestrian_green_seconds`: default = ceil(`crossing_length` / `pedestrian_speed`), at least 7;
- green bounds and cycle limits (40–120 s, provisional).

**Formulas:**
- **Flow ratio** of a vehicle phase: y_i = max over its approaches of (q / s). Y = Σ y_i.
  - If **Y ≥ 1**, refuse with `ValueError(f"Total flow ratio Y must be below 1 for a fixed-time plan (Y={Y:.2f})")`.
  - If **Y = 0** (no vehicle demand on any phase), give every vehicle phase `minimum_green`, with the warning "No vehicle demand; every phase gets its minimum green". The cycle then follows from those greens.
- **Lost time:** L = Σ over vehicle phases (startup_lost + all_red), plus the pedestrian phase's green + all_red if the plan has one.
- **Optimum cycle:** C₀ = (1.5·L + 5) / (1 − Y), rounded up to a whole second and clamped to the cycle limits. Clamping is reported in `warnings` as "Cycle raised to the minimum cycle of 40 s (Webster gave N s)" or "Cycle lowered to the maximum cycle of 120 s (Webster gave N s)".
- **Greens:** effective green g_i = (C₀ − L) · y_i / Y. Displayed green = g_i + startup_lost − yellow, rounded to 0.1 s and clamped to the green bounds. Any clamp is reported in `warnings`.
- **Recheck after clamping.**
  - `cycle_seconds` is the cycle the final greens actually give: Σ (green + yellow + all_red over vehicle phases) + (walk green + all_red). `webster_cycle_seconds` keeps C₀ for the record.
  - If the actual cycle falls outside the cycle limits, a warning says so.
  - If the plan passed in has `maximum_red_seconds` and the largest vehicle-phase red now exceeds it, `plan_from_result` refuses with the scenario validation message, so an invalid plan is never saved.

**Provisional placeholders,** recorded in the result's `assumptions` until the team cites a source:
- PCU factors: car 1.0, motorcycle 0.5, tricycle 1.0, bus 2.0, truck 2.5;
- saturation flow: 1,800 PCU/h per 3.3 m of approach width.

**Worked example** (hand-calculated; becomes the test):
- Inputs: phases `[["north","south"],["east","west"]]`, all saturation flows 1,800; flows N 900, S 720, E 540, W 450.
- y₁ = 0.5, y₂ = 0.3, Y = 0.8.
- L = 2 × (2 + 1) = 6 s.
- C₀ = (9 + 5) / 0.2 = 70 s.
- g₁ = 64 × 0.5 / 0.8 = 40, g₂ = 24.
- **Displayed greens 39 s and 23 s**; check: (39+3+1) + (23+3+1) = 70.

**Worked example with a walk phase** (hand-calculated; becomes the plan test):
- Inputs: phases `[["north","south"],["east","west"],"pedestrian"]`, `pedestrian_green_seconds=10`, all saturation flows 1,800; flows N 540, S 450, E 360, W 270.
- y₁ = 0.3, y₂ = 0.2, Y = 0.5.
- L = 2 × (2 + 1) + (10 + 1) = 17 s.
- C₀ = (25.5 + 5) / 0.5 = 61 s.
- g₁ = 44 × 0.3 / 0.5 = 26.4, g₂ = 17.6.
- **Displayed greens 25.4 s and 16.6 s, walk 10 s**; check: (25.4+4) + (16.6+4) + (10+1) = 61.

### 0.10 RL for each site

- **Junction.** RL controls the one junction of the site network.
- **Actions:** `("SERVE_PHASE_1", "SERVE_PHASE_2", "SERVE_PHASE_3", "SERVE_PHASE_4", "SERVE_PEDESTRIAN")`. Phase *k* is the *k*-th vehicle item of `phase_order`; missing slots are masked. Contract name `"phase-service-5-v2"`.
- **Observation** `obs_v4`, contract name `"native-local-20-v4"`, 20 values:
  - phase one-hot by slot (5);
  - phase elapsed and remaining (2);
  - queue, wait and active vehicles per approach N/E/S/W (12);
  - pedestrians waiting (1).

  The two network flags (`simulation/rl_state.py:8-10, 77`) are removed. The contract's network fingerprint ties a model to its site.
- **Reward** formula unchanged: `reward_v4`. The scales stay at 70 unless Task 25 measures a site queue p95 above 62. In that case both scales become the next multiple of 10 above p95, and `REWARD_VERSION` becomes `reward_v5`.
- **Contract:** `native_contract(network)` → `{"engine": "native-7", "observation": "native-local-20-v4", "actions": "phase-service-5-v2", "network_sha256": network.fingerprint}`. `native-6` models are refused, with the existing "train a new model" message.
- **Phase plan.** The contract alone does not fix what an action means: `SERVE_PHASE_1` depends on the scenario's phase order.
  - Every model's metadata stores `phase_plan = {"junction": <controlled junction>, "phase_keys": [<vehicle phase keys in slot order>, "pedestrian"]}`, taken from the training scenario.
  - `set_runtime_policy` refuses a model whose `phase_plan` differs from the engine's controlled junction and current phase keys: `ValueError("Selected model was trained for phases <a> at junction <j>; this scenario uses <b> at <k>. Train a model for this phase plan.")`.
  - Green times may differ; only the junction and the order and grouping of phases must match.
- **Evaluation.**
  - It reports both references, no-signal and fixed-time.
  - Day-to-day evaluation uses the development seeds 101–110. Final results use 201–220, only in Task 29.
  - **Warm-up runs under each condition's own control.** A no-signal evaluation warms up with no signal, a fixed-time one under its plan, and an RL one under its policy. The experiment therefore measures sustained operation under each condition, not a switch from a common fixed-time start. Today's evaluation warms everything up under fixed-time (`tools/evaluate_controllers.py:259-260`, `simulation/rl_env.py:141-151`); Task 18 changes evaluation only. Training keeps its fixed-time warm-up.
  - **Every evaluation result records:** warm-up seconds, the measurement window, unfinished demand (vehicles still waiting to enter, and vehicles on the network at the end), the per-seed values, and the spread across seeds (mean, standard deviation, min and max). No significance claim is made unless a test is named in advance.
- **Training runs.** Final results (Task 29) use at least three independently trained models per algorithm per site, with different training seeds from 11–55. Each is evaluated, and the spread across models is reported.
- **Retraining** QL, DQL and PPO for each site happens **after** the site passes the validation gate (§0.15), with the owner's approval.

### 0.11 Field data into SmartFlow

**Pipeline:** reviewed Field Observer revision → `convert_revision` (Task 20) → the existing `trips` and `pedestrian_counts` CSV schemas → the existing `import_observations`. That import keeps validation, provenance, held-out identity and the 5,000-row and 100,000-arrival limits.

**Mapping file for each site** (`data/sites/<network_id>_mapping.json`):
- `network_id`;
- `locations`: `location_id → {"role": "arrival"|"priority"|"stopline"|"exit"|"crossing", "boundary": <boundary node id>, "approach_id": <Field Observer approach id>, "distance_from_junction_m": <measured along the road in F2>}`. Each approach has a demand arrival line, a priority-zone boundary and a stop-line line; each exit has an exit line; crossings map to the junction. Priority-zone distances equal the frozen per-site approach-zone length measured upstream from the stop line. Priority and stop-line records feed validation, not demand;
- `lead_out_s`: footage reviewed after the window ends, at least 120 s;
- `upstream_speed_mps_by_class`: positive per-approach, per-class estimates with measurement/source notes; `movement_conflicts`: reviewed symmetric movement-pair table with geometry/version identity. The mapping also names the hashed `priority_review.csv` and initialization evidence used by Task 26;
- `class_map`: explicit choices for classes and subtypes, such as `"tricycle/pedicab": "exclude"`.

**Default class map:**
- car → car, motorcycle → motorcycle, bus → bus, truck → truck;
- tricycle (no subtype) → tricycle, tricycle/bao_bao → tricycle.

`pedicab`, `jeepney`, `bicycle`, `other` and `unknown` have **no default**. Counted vehicles of an unmapped class stop the conversion until the team decides (Team F4). A class map value is either one of the five simulation classes or `"exclude"`. Excluded vehicles are left out of demand and counted by class in the conversion summary, so the exclusion is reported, never hidden.

**Pedicab caution.** A pedal pedicab is slower and accelerates differently from a motorized bao-bao. Mapping it to `tricycle` gives it motorized behaviour, so F4 must choose one of:
- **exclude it**, and report how many there were;
- **map it to `tricycle`**, and state the limitation in every result;
- **ask the owner for a sixth vehicle class**, which changes the five-class rule in Global Constraints and needs its own plan.

**Trips:**
- **Three times:** `origin_s` is the simulation origin in video seconds; `[start_s, end_s)` is the measurement window in video seconds; `measurement_start_s = start_s - origin_s` is the engine warm-up duration. Require `0 <= origin_s <= start_s < end_s`. All vehicle and pedestrian demand uses this single origin; measurement times do not reset demand timestamps.
- Include reviewed lead-in arrivals as well as measurement-period arrivals. For each arrival compute its estimated boundary-entry video time first, then include it when that time is in `[origin_s, demand_end_s)`, where `demand_end_s` covers the declared follow-up horizon as well as measurement. Include post-measurement arrival-line events when their shifted boundary-entry time is before `end_s`; otherwise late boundary demand would be silently truncated. Report counts separately for lead-in, measurement and post-window observations.
- The destination comes from the same `episode_id`'s accepted event at an exit line, or the `exit_id` of a `vehicle_movement` / `vehicle_discharge`. Exit events are searched up to `end_s + lead_out_s`, so vehicles that arrive late in the window still get their exits. If the coverage of an exit line stops before `end_s + lead_out_s`, the conversion refuses and names the line.
- **Time alignment.** A simulated vehicle starts at the network boundary, upstream of the demand counting line: `boundary_time_s = arrival - (approach length - distance_from_junction_m) / upstream_speed_mps`; `time_s = boundary_time_s - origin_s`. Record the positive per-class upstream speed estimate and its source in the mapping. A lane-speed fallback is provisional and must be checked against observed free-flow travel times; it must not silently assume that every class travels at the speed limit.
  - Arrival lines must lie within the modelled approach (`distance_from_junction_m` ≤ the leg length), or the conversion refuses.
  - Arrival lines must be upstream of the farthest midday queue (F2), so the free-flow assumption holds.
  - A boundary time before the **measurement** start is valid lead-in demand. Example: origin 0 s, measurement start 120 s, observed arrival 125 s and upstream travel 24 s give trip time 101 s, not -19 s. Import it and retain the vehicle through warm-up.
  - Do not clip, drop or pile negative trip times at zero. Choose an earlier origin with sufficient reviewed coverage, and document initialization. If vehicles already occupy the modelled approaches at the proposed origin, use an earlier observed initialization period or stop with `INSUFFICIENT_INITIAL_STATE`; an empty reset at measurement start is forbidden. F1 must establish a defensible initialization, not assume a fixed warm-up erases queues.
  - Run through `end_s + lead_out_s` when following the measurement cohort to exits, while queue and discharge measurement remains `[start_s, end_s)`. Preserve and report unfinished cohort vehicles; never compare only the fast completers without disclosing them. Continuing arrivals during follow-up can affect that cohort: import the observed follow-up demand with the required coverage, or mark travel-time follow-up insufficient. An artificial no-demand drain is not a substitute for observed traffic. Return a separate `demand_end_s` for this extended input horizon and preserve the original measurement end.
- Arrivals with no exit are counted and refused by number.

**Provenance.** The conversion summary and the imported dataset record:
- the survey, take and revision ids;
- the revision `manifest.json` SHA-256 and the `reviewed_bins.csv` SHA-256;
- `origin_s`, the measurement window, `measurement_start_s`, `demand_end_s`, `lead_out_s`, initialization evidence, upstream-time assumptions and the mapping file's SHA-256.

The import stores them in `engine_config.demand_source.datasets`, so every scenario traces back to the exact reviewed video.

**Coverage:** verify the full input interval, including lead-in and the arrival/exit coverage needed for shifted boundary entries and cohort follow-up. `lead_out_s` is at least 120 s and must also cover the largest boundary-to-line shift; extend it when needed to resolve exits. Blank bins or missing initialization coverage stop conversion and name the line and interval. Earlier footage is useful only when its demand is imported.

### 0.12 Validation and the three-way comparison

- **Calibration** records the no-signal run as the condition being validated. Validation uses a second, different midday recording (Team F3), as `backend/research_routes.py:224-252` requires. The pass/fail rules are in §0.15.
- **Dashboard:** the KPI reference is the newest completed no-signal run whose comparison key (§0.5 "Matching runs") equals the current run's. If none exists, it falls back to the matching fixed-time run, and the note names which reference it used.
- **Compare Runs, run lists and exports** name the condition with the labels in Global Constraints.
- **The baseline tool** records one no-signal and one fixed-time run per active scenario.

### 0.13 Acceptance thresholds for the site cases (Task 25)

- **Cases:** both sites × {no signal, traditional ungrouped, traditional grouped} × {medium, high} demand × development seeds 101 and 102, 1,800 s each. That is 12 named cases and 24 runs:
  - `siteA-medium-nosignal`, `siteA-medium-fixed`, `siteA-medium-grouped`, `siteA-high-nosignal`, `siteA-high-fixed`, `siteA-high-grouped`;
  - the same six for `siteB`.
- **Every case must show:**
  - `max_overlapping_pairs` 0;
  - `max_stuck_junction_vehicles` 0;
  - `max_gridlock_seconds` 0;
  - `final_vehicle_conservation_error` 0;
  - equal determinism digests.
- **Speed budgets unchanged:** cars-only 900 s run ≤ 18.0 s; RL environment ≥ 7.07 decisions/s.

### 0.14 Out of scope

- Joining the two sites or modelling the corridor.
- Protected turn phases.
- Live feeds or signal hardware.
- Automatic pedicab recognition.
- Peak-hour scenarios built from data, unless peak video is added.
- Any change to the behaviour of the 5- and 2-junction networks.

### 0.15 Validation gate and per-site calibration

**Pre-registration.** The team and adviser commit `data/sites/validation_criteria.json` before inspecting held-out traffic outcomes, computing held-out measures or using that recording to select parameters or criteria. Conversion date alone does not establish independence. Record the criteria commit/hash, nominated held-out recording identity, freeze time and first outcome-access time in the study ledger. If day 2 has already informed those choices, nominate another untouched recording. Day 1 remains development data.

For each site the criteria contain:
- absolute (`{"abs": x}`) or relative (`{"rel": r}`) tolerances for average queue per approach, discharge per approach per 15-minute bin, mean arrival-to-exit travel time and eligible arrival-order share;
- `arrival_order_share_min`, `pair_window_s`, `tie_tolerance_s`, `min_order_pairs`, minimum coverage/sample counts for each measure, and rules for censored or unobservable observations;
- at least five development seeds from 101–110, the initialization and measurement protocol, and a reviewed movement-conflict table and priority-line locations.

Compare the mean simulated value over the declared seeds with the observed value for each declared approach/bin. Relative error at observed zero uses the exact inequality `abs(sim - obs) <= r * abs(obs)`; specify an absolute tolerance in advance when a nonzero allowance is intended. Missing, non-finite or insufficient observations are `INCONCLUSIVE`, never silently omitted or replaced by zero. Zero overlaps, stuck vehicles, gridlock time and vehicle conservation error are also required. Safety failure is `FAIL`; lack of required evidence cannot yield `PASS`.

**Saved calibration.** Add optional `engine_config.site_calibration` with `schema_version`, `network_id`, `first_come_approach_speed_mps`, `approach_zone_m`, `turn_speed_mps` and `class_speed_factors` for all five supported classes. Task 26 implements finite positive validation and engine-instance resolution of these fields. Defaults remain the existing constants when this object is absent. Do not edit module constants or shared `VEHICLE_TYPES` to calibrate a site. Preserve the complete object through save/edit, recording, training, evaluation, import/export and backup/restore. Use the same frozen physical calibration for all three conditions; the first-come-only settings apply only in that mode.

Calibration uses day 1 only and may adjust only those four behaviour fields (including the class-factor mapping), with every before/after setting and reason recorded. Site A and Site B have separate saved objects. Changing Site B must not change Site A or the default networks. Changing the priority-zone length requires matching priority-line annotations and recomputed day-1 measures. Any wider change needs a documented model-design decision and new verification.

**Frozen evidence identity.** Every report records engine version and source revision/content hash, network hash, resolved calibration hash, mapping/conflict-table hash, criteria hash, exact source revision/artifact hashes, demand hash, seeds, initialization, measurement/follow-up windows, purpose and an immutable report id. Keep every attempt; filenames include the report id, not only the date. The calibration hash covers resolved values, including defaults.

Validation runs on the nominated untouched recording with the model and criteria frozen. `PASS` requires all declared measures, adequate evidence, the arrival-order hypothesis check and safety checks. `INCONCLUSIVE` requests additional independently collected evidence under the same predeclared rules; it does not open the training gate.

**If validation fails:** preserve the failed report and stop that site's gate. The team may revise and recalibrate using development data. Once the failure has informed a revision, that recording is development evidence for the revised model: a rerun may diagnose the fix but cannot grant independent validation. Freeze the revised model/protocol, nominate a fresh untouched recording (normally day 3), and validate there. If fresh evidence is unavailable, the site remains unvalidated; no owner override or limitation note converts it to `PASS`.

**Gate validity.** Task 29 verifies a passing independent report for the current site and its frozen physical model, rather than trusting a filename or a scenario-level flag. Any change to engine identity, network, calibration, measurement method or criteria makes the old pass stale. Retain it as history and recheck the applicable validation protocol; behaviour changes informed by held-out failure require fresh evidence. A non-behavioural version/build change still requires a documented compatibility check and rerun, not automatic carry-forward. Proposed signal plans and evaluation demand have their own recorded identities; changing only the intervention does not rewrite the validated no-signal evidence.

**Milestone 1** ends when one site passes with sufficient independent evidence. Site A is expected first because Site B also needs the median check. Full RL training and final results remain blocked for each site without a current pass.

---

## File map

| File | Responsibility | Tasks |
|---|---|---|
| `tools/import_osm_network.py` | Overpass download (adds trunk roads and per-site boxes) | 1 |
| `tools/build_study_network.py` | Network builder (adds the single-site mode) | 2 |
| `simulation/road_network.py` | Distinct approach names | 3 |
| `data/networks/osm_site_{a,b}.json`, `tagum_site_{a,b}.json`, `registry.json` | Site map data and networks | 4, 5 |
| `simulation/network_registry.py` (new) | Look up networks by id; build an engine for a scenario | 5 |
| `backend/simulation_runtime.py`, `services/timeline_generator.py`, `services/native_scenario_service.py`, `database.py`, `services/scenario_migration.py`, `services/observed_data_import.py`, `services/observation_templates.py`, `services/render_frame_service.py`, `simulation/timeline_engine.py`, `backend/main.py` | Use the scenario's network | 6, 8 |
| `simulation/model_contract.py`, `simulation/rl_env.py`, `services/training_settings.py`, `tools/train_{ql,dql,ppo}.py`, `tools/evaluate_controllers.py` | RL path per network | 7, 17, 18 |
| `services/visual_network_service.py`, `services/backup_bundle.py` | Maps and backups per network | 8 |
| `src/api/networks.ts` (new), `src/lib/sites.ts` (new), `src/api/native-scenario.ts`, `src/components/scenarios-page.tsx`, `junction-details.tsx`, `compare-runs-page.tsx` | Site picker and labels | 9 |
| `simulation/traffic_engine.py` | `first_come`, no-signal, groups, per-phase greens, RL slots, `native-7` | 10–14, 17 |
| `simulation/scenario_config.py`, `src/lib/signal-plan.ts` | Plan validation and cycle maths | 10, 13, 14 |
| `services/native_controller.py` | `no-signal` control mode | 11 |
| `src/lib/control-labels.ts` (new) | One place for the condition labels | 12, 16 |
| `simulation/signal_design.py` (new), `tools/design_signal_plan.py` (new), `src/api/signal-design.ts` (new) | Webster | 15, 16 |
| `src/components/native-scenario-controls.tsx` | Phase groups, per-phase greens, Webster button | 16 |
| `simulation/rl_state.py`, `simulation/rl_policy_runtime.py`, `simulation/{dql,ppo}_training.py`, `simulation/metric_definitions.json` | Contract v4 | 17 |
| `services/rl_training_service.py`, `services/rl_reporting_service.py` | No-signal reference in evaluation | 18 |
| `tools/field_observer/field_observer/{gui.py,gui.html,core.py}` | Queue samples, exits, line export | 19 |
| `services/field_observer_import.py` (new), `data/sites/*.json` (new) | Converter and mappings | 20 |
| `backend/research_routes.py`, `src/components/calibration-validation-page.tsx` | Calibration on the no-signal run | 21 |
| `src/lib/reference-run.ts` (new), `src/components/dashboard-page.tsx`, `dashboard-kpis.tsx` | KPI reference | 22 |
| `tools/record_fixed_time_baselines.py` | Records both conditions | 23 |
| `backend/main.py`, `src/components/runs-reports-page.tsx`, report export | Condition names | 24 |
| `tools/mixed_traffic_report.py`, `docs/reports/two-site-acceptance.json` (new) | Site acceptance | 25 |
| `services/site_validation.py` (new), `tools/validate_site.py` (new), `data/sites/validation_criteria.json` (new, written by the team) | Per-site calibration, observed vs simulated measures, immutable evidence and the validation gate | 26, 28 |
| `docs/…` | Decisions, status, field and research docs | 27 |
| `docs/reports/two-site-results.json` (new) | Final results | 29 |

## Order of work

Two milestones. The second starts only for a site that passed the validation gate (§0.15).

**Milestone 1: a validated no-signal model of one site.**

```
Part 1 (T1–T4) ──► Part 2 (T5–T9) ──┐
Part 3 (T10–T12) ───────────────────┼──► T21 ──► T26 ──► T28 (Site A first, then Site B)
Part 6 (T19, then T20 after T4) ────┘
Team: F1, F2, F3, F4, F6 (criteria frozen before held-out outcomes are inspected)
```

**Milestone 2: the proposals and the comparison.**

```
Part 4 (T13–T16) ──► Part 5 (T17–T18) ──► T22–T25 ──► T29 (per validated site)
T27 documentation: after each milestone
```

Parts 1, 3 and T19 touch different files and can be worked in parallel. Part 3 uses synthetic networks, so it does not wait for the site files. Milestone 2 code (Parts 4 and 5) may be written while the team collects data, but T29 runs only for a validated site.

---

## Part 1 — Site networks

### Task 1: Fetch trunk roads and a box around each site

**Files:**
- Modify: `tools/import_osm_network.py:12-39`
- Test: `tests/test_import_osm_network.py` (new)

**Interfaces:**
- Produces:
  - `ROAD_CLASSES = ("trunk", "trunk_link", "primary", "primary_link", "secondary", "secondary_link", "tertiary", "tertiary_link", "residential", "unclassified", "living_street")`
  - `overpass_query(bbox: str) -> str`, which matches `^(<ROAD_CLASSES joined by "|">)$`
  - `site_bbox(latitude: float, longitude: float, radius_m: float = 450.0) -> str` → `"south,west,north,east"` to 6 decimals. It raises the existing "at most 0.03 degrees per side" error.
  - `download_roads(bbox: str, output: Path) -> None`, with the signature unchanged.
  - CLI: `--site LAT,LON [--radius-m 450]` as an alternative to `--bbox`, and `--output` now **required**.

- [ ] **Step 1: Write the failing tests**

```python
from tools.import_osm_network import overpass_query, site_bbox, download_roads

class OsmDownloadTests(unittest.TestCase):
    def test_query_includes_trunk_roads(self):
        query = overpass_query("7.4577,125.7985,7.4658,125.8067")
        self.assertIn('"^(trunk|trunk_link|primary', query)
        self.assertIn("(7.4577,125.7985,7.4658,125.8067)", query)

    def test_site_box_is_centred_on_the_point(self):
        south, west, north, east = map(float, site_bbox(7.4617375, 125.8026196, 450).split(","))
        self.assertAlmostEqual((south + north) / 2, 7.4617375, places=5)
        self.assertAlmostEqual((west + east) / 2, 125.8026196, places=5)
        self.assertAlmostEqual(north - south, 2 * 450 / 111320, places=5)

    def test_a_box_over_the_size_limit_is_refused(self):
        with self.assertRaisesRegex(ValueError, "0.03 degrees"):
            site_bbox(7.46, 125.80, 2000)

    def test_download_keeps_attribution_and_query(self):
        # patch tools.import_osm_network.urlopen with a context manager returning one node element;
        # write to a temp file, then:
        self.assertEqual(saved["smartflow_source"]["license"], "ODbL-1.0")
        self.assertIn("trunk", saved["smartflow_source"]["query"])
```

- [ ] **Step 2: Run them; they should fail**

Run: `.venv/Scripts/python.exe -m pytest tests/test_import_osm_network.py -q --basetemp "$TEMP/sf_t1"`
Expected: FAIL — `ImportError: cannot import name 'overpass_query'`.

- [ ] **Step 3: Implement**

Write `overpass_query`, `site_bbox` and a shared `_check_bbox(south, west, north, east)`, and make `download_roads` use them. In `site_bbox`, the longitude half-width is `radius_m / (111320·cos(lat))`.

- [ ] **Step 4: Run them; they should pass**

Same command. Expected: 4 passed.

- [ ] **Step 5: Commit**

Commit: "Fetch trunk roads and per-site boxes from OpenStreetMap".

### Task 2: Build a single-site network

**Files:**
- Modify: `tools/build_study_network.py`. Add `build_site_network`. The CLI requires `--output` in both modes, because today it defaults to the active network at `:117`.
- Test: `tests/test_build_site_network.py` (new). It builds synthetic OSM payloads in the test file; there are no fixture files.

**Interfaces:**
- Consumes: the `ROAD_CLASSES` list from Task 1, so service roads are absent.
- Produces:
  - `MAJOR_CLASSES = frozenset({"trunk", "trunk_link", "primary", "primary_link", "secondary", "secondary_link", "tertiary", "tertiary_link"})`
  - `build_site_network(source_path: Path, centre: tuple[float, float], *, network_id: str, name: str, join_radius_m: float = 25.0, approach_m: float = 250.0, approach_overrides_m: dict[str, float] | None = None, extra_assumptions: list[str] | None = None) -> dict`, which returns a network payload that `RoadNetwork` accepts, built by the rules in §0.3. `extra_assumptions` are appended to `source.assumptions`.
  - CLI: `--site LAT,LON --network-id ID --name NAME --source PATH --output PATH [--approach-m 250] [--approach WAY_ID=METRES ...] [--assumption TEXT ...]`.

- [ ] **Step 1: Write the failing tests**

```python
def test_a_cross_with_a_side_street_keeps_all_four_legs(self):
    # secondary cross; 300 m arms; a residential street joins the north arm 48 m out
    payload = build_site_network(path, CENTRE, network_id="site_test", name="Test")
    network = RoadNetwork(payload)
    self.assertEqual(len(network.intersections), 1)
    self.assertEqual(len(network.incoming[network.intersections[0]]), 4)
    self.assertTrue(all(length(road["shape"]) >= 240 for road in payload["roads"]))

def test_split_highway_points_join_into_one_junction(self):
    # Site B shape: two one-way trunk carriageways 9 m apart, a 9 m median link,
    # a secondary street on one side and a tertiary street on the other
    network = RoadNetwork(build_site_network(path, CENTRE, network_id="site_b_test", name="Test"))
    self.assertEqual(len(network.intersections), 1)
    self.assertEqual(len(network.incoming[network.intersections[0]]), 4)
    self.assertEqual(len(network.payload["roads"]), 6)   # 2 per carriageway + 2 two-way streets

def test_a_leg_stops_10_m_before_the_next_major_junction(self):
    # a tertiary road crosses the east arm 120 m out
    east = next(r for r in payload["roads"] if r["osm_way_id"] == EAST_WAY)
    self.assertAlmostEqual(length(east["shape"]), 110.0, delta=0.5)

def test_a_leg_shorter_than_30_m_is_refused_by_name(self):
    with self.assertRaisesRegex(ValueError, "Dao Street.*way 732013634"):
        build_site_network(path, CENTRE, network_id="t", name="t", approach_overrides_m={"732013634": 20})

def test_the_network_has_the_requested_id_and_assumptions(self):
    self.assertEqual(payload["id"], "site_test")
    self.assertIn("No traffic signal exists today; signal plans are proposals", payload["source"]["assumptions"])

def test_output_is_required_on_the_command_line(self):
    result = subprocess.run([sys.executable, str(TOOL), "--site", "7.46,125.80", "--network-id", "x", "--name", "x",
                             "--source", str(path)], capture_output=True)
    self.assertEqual(result.returncode, 2)
```

- [ ] **Step 2: Run them; they should fail**

Run: `.venv/Scripts/python.exe -m pytest tests/test_build_site_network.py -q --basetemp "$TEMP/sf_t2"`
Expected: FAIL — `ImportError: cannot import name 'build_site_network'`.

- [ ] **Step 3: Implement `build_site_network`**

Reuse `clip` and `length` from `simulation.road_network` and the way-chain walk the existing builder uses (`:41-59`), with the stopping rule from §0.3. Give each boundary node the id `boundary_<n>`. Roads keep `osm_way_id`, `osm_node_ids`, `osm_tags`, `name` and `speed_mps` 8.33, as at `:104`. The node is `{"id": network_id + "_j", "x": 0, "y": 0, "lat", "lon"}` with no `signal_plan` key.

- [ ] **Step 4: Run them; they should pass**

Same command. Expected: 6 passed. Also run `tests/test_road_width.py` and `tests/test_native_cleanup.py`: still green.

- [ ] **Step 5: Commit**

Commit: "Build a single-junction site network from OpenStreetMap".

### Task 3: Give every leg of a junction its own approach name

**Files:**
- Modify: `simulation/road_network.py`. Add a pass after the lane loop in `RoadNetwork.__init__` (`:155-189`). `Lane` is frozen, so use `dataclasses.replace`.
- Test: `tests/test_approach_names.py` (new)

**Interfaces:**
- Produces: `assign_approach_names(headings: dict[str, float]) -> dict[str, str]`. It maps lane id → name from each incoming lane's travel heading at its end, in radians (as `sample` returns them; 0 = travelling east, which is the "west" approach), using the algorithm in §0.4.

- [ ] **Step 1: Write the failing tests**

```python
def star(bearings_deg):  # boundary arms at these compass bearings (clockwise from north), two-way, into junction "j"
    ...

def test_skewed_junction_gets_four_distinct_approaches(self):
    network = RoadNetwork(star([38, 128, 217, 354]))           # Site B's legs
    names = [network.lanes[l].approach for l in network.incoming["j"]]
    self.assertEqual(sorted(names), ["east", "north", "south", "west"])

def test_names_keep_the_circular_order_of_the_legs(self):
    network = RoadNetwork(star([38, 128, 217, 354]))
    by_bearing = [approach_of_arm(network, b) for b in (38, 128, 217, 354)]
    self.assertIn(tuple(by_bearing), {tuple(ROTATION[i:] + ROTATION[:i]) for i in range(4)})  # ROTATION = north,east,south,west

def test_more_than_four_legs_is_refused(self):
    with self.assertRaisesRegex(ValueError, "Junction j has 5 approaches; SmartFlow supports at most four"):
        RoadNetwork(star([0, 72, 144, 216, 288]))

def test_existing_networks_keep_their_approach_names(self):
    expected = {"tagum_network.json": {"1226402048": ["east", "north", "south", "west"], "1217544499": ["east", "north", "south"],
                                       "376306710": ["east", "north", "south", "west"], "1217544567": ["north", "south", "west"],
                                       "1217544575": ["north", "south", "west"]},
                "tagum_network_2j.json": {"1226402048": ["east", "north", "south", "west"], "1217544499": ["east", "north", "south"]}}
    # load each file; sorted incoming approach names per junction == expected

def test_a_regular_cross_is_unchanged(self):
    network = junction_network()                                # tests/mixed_traffic_helpers.py
    self.assertEqual({network.lanes[l].source: network.lanes[l].approach for l in network.incoming["j"]},
                     {"w": "west", "e": "east", "n": "north", "s": "south"})
```

- [ ] **Step 2: Run them; they should fail**

Run: `.venv/Scripts/python.exe -m pytest tests/test_approach_names.py -q --basetemp "$TEMP/sf_t3"`
Expected: FAIL. The skewed junction gives `['east', 'north', 'north', 'south']`, and the 5-leg star loads without error.

- [ ] **Step 3: Implement `assign_approach_names`**

Call it once per intersection. Raise the >4 error before naming. Keep the rounding result when it is already distinct.

- [ ] **Step 4: Run them; they should pass**

Same command. Expected: 5 passed. Then run the full backend suite. Expected: every existing test still passes, because the existing networks' names are unchanged.

- [ ] **Step 5: Commit**

Commit: "Give every leg of a junction a distinct approach name".

### Task 4: Build the two site networks

**Owner gate:** before Step 3, ask the owner to approve two Overpass downloads (endpoint `https://overpass-api.de/api/interpreter`, two boxes of about 900 m × 900 m).

**Files:**
- Create: `data/networks/osm_site_a.json`, `data/networks/osm_site_b.json` (downloads), `data/networks/tagum_site_a.json`, `data/networks/tagum_site_b.json`
- Test: `tests/test_site_networks.py` (new)

**Interfaces:**
- Produces: network ids `tagum_site_a` and `tagum_site_b`, each with one junction and four distinct approaches.

- [ ] **Step 1: Write the failing test**

```python
SITES = {"tagum_site_a.json": ("tagum_site_a", {"Capitol Circumferential Road", "Dalisay Gante Road"}),
         "tagum_site_b.json": ("tagum_site_b", {"Davao-Agusan National Highway", "Sobrecarey Street", "Dao Street"})}

def test_each_site_network_loads_as_one_junction_with_four_named_approaches(self):
    for file, (network_id, streets) in SITES.items():
        network = RoadNetwork(json.loads((NETWORKS / file).read_text(encoding="utf-8")))
        self.assertEqual(network.id, network_id)
        self.assertEqual(len(network.intersections), 1)
        self.assertEqual(sorted(network.lanes[l].approach for l in network.incoming[network.intersections[0]]),
                         ["east", "north", "south", "west"])
        self.assertEqual({road["name"] for road in network.payload["roads"]}, streets)
        self.assertEqual(network.payload["source"]["provider"], "OpenStreetMap")
```

- [ ] **Step 2: Run it; it should fail**

Run: `.venv/Scripts/python.exe -m pytest tests/test_site_networks.py -q --basetemp "$TEMP/sf_t4"`
Expected: FAIL — `FileNotFoundError`.

- [ ] **Step 3: Download (after approval)**

```bash
.venv/Scripts/python.exe tools/import_osm_network.py --site 7.4617375,125.8026196 --output data/networks/osm_site_a.json
.venv/Scripts/python.exe tools/import_osm_network.py --site 7.4382646,125.8025576 --output data/networks/osm_site_b.json
```

- [ ] **Step 4: Build**

```bash
.venv/Scripts/python.exe tools/build_study_network.py --site 7.4617375,125.8026196 --source data/networks/osm_site_a.json --network-id tagum_site_a --name "Site A — Capitol Circumferential Rd × Dalisay Gante Rd" --output data/networks/tagum_site_a.json
.venv/Scripts/python.exe tools/build_study_network.py --site 7.4382646,125.8025576 --source data/networks/osm_site_b.json --network-id tagum_site_b --name "Site B — National Highway × Sobrecarey St / Dao St" --output data/networks/tagum_site_b.json
```

Print each leg's length and approach name; they go into the field sheet (Team F2).

The Site B network is **provisional** until F2 confirms the median crossing (§0.3). Add "Median crossing modelled as one movement; pending field check" to its `source.assumptions` (the builder's `--assumption TEXT` option, repeatable, appends to the list). Add a test line: `self.assertIn("Median crossing modelled as one movement; pending field check", site_b.payload["source"]["assumptions"])`.

- [ ] **Step 5: Run the test; it should pass**

Expected: 1 passed.

- [ ] **Step 6: Commit**

Commit: "Add the Site A and Site B networks from OpenStreetMap".

---

## Part 2 — Each scenario picks its network

### Task 5: Network registry

**Files:**
- Create: `simulation/network_registry.py`, `data/networks/registry.json`
- Test: `tests/test_network_registry.py` (new)

**Interfaces:**
- Produces:
  - `REGISTRY_PATH: Path` (`data/networks/registry.json`). Its content is `{"networks": [{"id": "tagum_site_a", "file": "tagum_site_a.json"}, {"id": "tagum_site_b", "file": "tagum_site_b.json"}]}`.
  - `registered_networks(registry_path: Path = REGISTRY_PATH) -> list[dict]` → `[{"id", "name", "file", "sha256", "junctions"}]`, with the default network first.
  - `load_registered_network(network_id: str | None = None, *, registry_path: Path = REGISTRY_PATH) -> RoadNetwork`. `None` or `"tagum_network"` → `load_network()` (`NETWORK_PATH`). The result is cached by (path, mtime_ns, size). It raises `ValueError(f"Unknown network '{network_id}'")` for an unknown id, and `ValueError(f"Registry file {file} has id '{actual}', not '{network_id}'")` when the file's id differs.
  - `engine_for_scenario(scenario: dict, *, seed: int | None = 42, registry_path: Path = REGISTRY_PATH) -> TrafficEngine` → `TrafficEngine(seed, network=load_registered_network(scenario.get("network_id"), registry_path=registry_path))` followed by `configure_from_scenario(scenario)`.

- [ ] **Step 1: Write the failing tests**

```python
def test_default_id_loads_the_active_network(self):
    self.assertEqual(load_registered_network(None).fingerprint, load_network().fingerprint)
    self.assertEqual(load_registered_network("tagum_network").id, "tagum_network")

def test_site_ids_load_their_own_files(self):
    self.assertEqual(load_registered_network("tagum_site_a").id, "tagum_site_a")
    self.assertEqual(load_registered_network("tagum_site_b").id, "tagum_site_b")

def test_unknown_id_is_refused(self):
    with self.assertRaisesRegex(ValueError, "Unknown network 'nowhere'"):
        load_registered_network("nowhere")

def test_a_registry_entry_whose_file_has_another_id_is_refused(self):
    # temp registry pointing id "x" at tagum_site_a.json
    with self.assertRaisesRegex(ValueError, "Registry file .* has id 'tagum_site_a', not 'x'"):
        load_registered_network("x", registry_path=temp_registry)

def test_list_puts_the_default_first_and_reports_fingerprints(self):
    listed = registered_networks()
    self.assertEqual([n["id"] for n in listed], ["tagum_network", "tagum_site_a", "tagum_site_b"])
    self.assertEqual(listed[1]["sha256"], load_registered_network("tagum_site_a").fingerprint)

def test_engine_for_scenario_uses_the_scenario_network(self):
    engine = engine_for_scenario({"network_id": "tagum_site_a", "engine_config": {}}, seed=101)
    self.assertEqual(engine.network.id, "tagum_site_a")
```

- [ ] **Step 2: Run them; they should fail**

Run: `.venv/Scripts/python.exe -m pytest tests/test_network_registry.py -q --basetemp "$TEMP/sf_t5"`
Expected: FAIL — `ModuleNotFoundError: simulation.network_registry`.

- [ ] **Step 3: Implement the module and registry file**

`simulation.network_registry` imports `TrafficEngine` inside `engine_for_scenario`. `traffic_engine` must never import the registry.

- [ ] **Step 4: Run them; they should pass**

Expected: 6 passed.

- [ ] **Step 5: Commit**

Commit: "Register site networks by id".

### Task 6: Build every engine from the scenario's network

**Files:**
- Modify:
  - `backend/simulation_runtime.py:73, 317, 524`
  - `services/timeline_generator.py:161`
  - `services/native_scenario_service.py:20-45`: `configuration_options(network_id: str | None = None)`
  - `database.py:842-846`: `validated_native_scenario` builds the engine on `load_registered_network(network_id)` and returns `network_sha256` with the other fields
  - `database.py`: the schema at `:132-142` and the scenario migration at `:384-391` gain a `network_sha256 TEXT` column on `scenarios`; `create_scenario` / `update_scenario` store it
  - `backend/main.py:979`
  - `services/scenario_migration.py:20, 55, 106`: each scenario on its own network
  - `services/observed_data_import.py:79` and `services/observation_templates.py:12`: take the scenario's network
  - `services/render_frame_service.py:11`
  - `simulation/timeline_engine.py:47-53`: check the recording against `RoadNetwork(manifest["network"])`
  - `simulation/traffic_engine.py:330-336`: the clear mismatch error in §0.5. It raises when `scenario.get("network_sha256")` is set and differs from `self.network.fingerprint`, and when lane or junction validation fails for a scenario that names its network.
- Test: `tests/test_site_scenarios.py` (new)

**Interfaces:**
- Consumes: `load_registered_network` and `engine_for_scenario` from Task 5.
- Produces: `configuration_options(network_id: str | None = None) -> dict`, with the same keys as today.

- [ ] **Step 1: Write the failing tests**

Use a scratch database set up like `tests/test_record_baselines.py`.

```python
def test_a_site_scenario_runs_while_the_default_network_still_works(self):
    site = database.validated_native_scenario("tagum_site_a", {"traffic_density": "low"})
    self.assertEqual(site["network_id"], "tagum_site_a")
    engine = engine_for_scenario({"network_id": "tagum_site_a", "engine_config": json.loads(site["engine_config"])}, seed=101)
    engine.start(60); engine.step(600)
    self.assertGreater(engine.vehicle_serial, 0)
    default = engine_for_scenario({"network_id": "tagum_network", "engine_config": {}}, seed=101)
    self.assertEqual(default.network.id, "tagum_network")

def test_recording_embeds_the_site_network_and_plays_back(self):
    # create a scratch scenario on tagum_site_a, run generate_timeline(..., 30 s), join the worker
    self.assertEqual(manifest["network"]["id"], "tagum_site_a")
    self.assertEqual(manifest["experiment"]["network_sha256"], load_registered_network("tagum_site_a").fingerprint)
    # TimelinePlaybackEngine on that run loads with status != "error" while the default network is active

def test_scenario_on_a_rebuilt_site_network_reports_a_clear_error(self):
    # register a temp network with id "tagum_site_a" whose lane ids differ; scenario closes a lane id that no longer exists
    with self.assertRaisesRegex(ValueError, "network changed since this scenario was saved"):
        engine_for_scenario({"network_id": "tagum_site_a", "engine_config": {"closed_lanes": [OLD_LANE]}})

def test_a_width_change_with_the_same_lane_ids_is_detected(self):
    saved = database.validated_native_scenario("tagum_site_a", {})
    # register a temp copy of tagum_site_a whose first road gains width_per_direction_m (every lane id unchanged)
    with self.assertRaisesRegex(ValueError, "network changed since this scenario was saved"):
        engine_for_scenario({**saved, "engine_config": json.loads(saved["engine_config"])}, registry_path=temp_registry)

def test_scenarios_saved_before_the_fingerprint_column_still_run(self):
    engine = engine_for_scenario({"network_id": "tagum_network", "engine_config": {}})   # no network_sha256 key
    self.assertEqual(engine.network.id, "tagum_network")

def test_options_follow_the_requested_network(self):
    options = configuration_options("tagum_site_b")
    self.assertEqual(options["network_id"], "tagum_site_b")
    self.assertEqual(len(options["junctions"]), 1)
```

- [ ] **Step 2: Run them; they should fail**

Run: `.venv/Scripts/python.exe -m pytest tests/test_site_scenarios.py -q --basetemp "$TEMP/sf_t6"`
Expected: FAIL. `validated_native_scenario` raises "Scenario network is unresolved or differs…" for `tagum_site_a`.

- [ ] **Step 3: Implement**

Replace each bare `TrafficEngine()` / `load_network()` listed above with the scenario's network through the registry. Where there is no scenario, as at `simulation_runtime.py:317`, the default stays.

- [ ] **Step 4: Run them, then the full backend suite**

Expected: 6 passed; full suite green.

- [ ] **Step 5: Commit**

Commit: "Run every scenario on its own registered network".

### Task 7: Train and evaluate on the scenario's network

**Files:**
- Modify:
  - `simulation/model_contract.py:10-52`: `native_contract`, `validate_metadata`, `_read_metadata` (the cache key adds the network fingerprint), `artifact_metadata` and `training_junction` all take an optional network
  - `simulation/rl_policy_runtime.py`: `load_runtime_policy(algorithm, path, network=None)` validates against that network
  - `services/native_controller.py:16-17`: passes `engine.network` to `load_runtime_policy`
  - Model metadata writers record the **training** network's contract, `native_contract(engine.network)`, not the default: `simulation/ppo_training.py:187`, the matching line in `simulation/dql_training.py`, and `_build_metadata` in `tools/train_ql.py:150`
  - `simulation/traffic_engine.py:599-600`: replace the "only the versioned default study network" check with `policy.artifact_metadata["native_contract"] == native_contract(self.network)`, raising the `validate_metadata` message otherwise
  - `simulation/rl_env.py:109`: use `engine_for_scenario` when the scenario has a `network_id`
  - `services/training_settings.py:31, 40`
  - `tools/train_ql.py:65`, `tools/train_dql.py`, `tools/train_ppo.py`: `--intersection-id` must equal the scenario's `network_id`, else exit with an error
  - `tools/evaluate_controllers.py:249`
  - `backend/main.py:1175`: read `scenario.get("intersection_id") or scenario.get("network_id")`
- Test: `tests/test_site_rl_path.py` (new)

**Interfaces:**
- Produces:
  - `native_contract(network: RoadNetwork | None = None) -> dict` (`None` → the default network)
  - `validate_metadata(metadata: dict, network: RoadNetwork | None = None) -> None`
  - `artifact_metadata(algorithm: str, path, network: RoadNetwork | None = None) -> dict`
  - `training_junction(metadata: dict, network: RoadNetwork | None = None) -> str`
  - `load_runtime_policy(algorithm: str, path, network: RoadNetwork | None = None)`
  - `set_runtime_policy` checks against `native_contract(self.network)`

- [ ] **Step 1: Write the failing tests**

```python
def test_contract_pins_the_given_network(self):
    site = load_registered_network("tagum_site_a")
    self.assertEqual(native_contract(site)["network_sha256"], site.fingerprint)

def test_rl_environment_runs_on_a_site_scenario(self):
    env = SmartFlowRLEnv(scenario={"network_id": "tagum_site_a", "engine_config": {"traffic_density": "low"}}, seed=11)
    observation, _ = env.reset(seed=11)
    self.assertEqual(env.engine.network.id, "tagum_site_a")
    self.assertEqual(len(observation), 22)   # becomes 20 in Task 17

def test_a_model_for_site_a_is_refused_on_site_b(self):
    metadata = {"native_contract": native_contract(load_registered_network("tagum_site_a"))}
    engine = engine_for_scenario({"network_id": "tagum_site_b", "engine_config": {}})
    with self.assertRaisesRegex(ValueError, "not trained for the current Python engine and road network"):
        engine.set_runtime_policy(StubPolicy(metadata))

def test_a_model_trained_on_a_site_records_that_site(self):
    # a 2-episode QL training run on a scratch tagum_site_a scenario → metadata["native_contract"]["network_sha256"] == site A fingerprint

def test_compare_metadata_reads_the_recorded_network(self):
    meta = compare_timeline_meta(run, {"scenario": {"intersection_id": "tagum_site_a"}, "timeline": {}})
    self.assertEqual(meta.intersection_id, "tagum_site_a")
```

- [ ] **Step 2: Run them; they should fail**

Run: `.venv/Scripts/python.exe -m pytest tests/test_site_rl_path.py -q --basetemp "$TEMP/sf_t7"`
Expected: FAIL — `native_contract()` takes no arguments.

- [ ] **Step 3: Implement as listed under Files**

- [ ] **Step 4: Run them, then the full backend suite**

Expected: 5 passed; full suite green. Includes `tests/test_training_worker.py`: run it alone if it times out under a parallel suite, a known flake.

- [ ] **Step 5: Commit**

Commit: "Train and evaluate RL on the scenario's own network".

### Task 8: Network APIs and backups

**Files:**
- Modify:
  - `backend/main.py:1979-2004`: `GET /api/simulation/options?network_id=`; `/api/visual-network` from the registry; new `GET /api/networks`
  - `services/visual_network_service.py`: `load_registered_network(network_id)`
  - `services/backup_bundle.py:52, 113-134, 265-279`: bundle `registry.json` and every registered network file; restore them; migrate scenarios per network
- Test: `tests/test_site_api.py` (new). Use the client and login setup in `tests/test_native_integration.py`.

**Interfaces:**
- Produces: `GET /api/networks` → `[{"id", "name", "sha256", "junctions"}]`, which needs the same permissions as `/api/simulation/options`.

- [ ] **Step 1: Write the failing tests**

```python
def test_networks_endpoint_lists_the_default_and_both_sites(self):
    self.assertEqual([n["id"] for n in client.get("/api/networks").json()], ["tagum_network", "tagum_site_a", "tagum_site_b"])

def test_options_accept_a_site_network(self):
    self.assertEqual(client.get("/api/simulation/options?network_id=tagum_site_a").json()["network_id"], "tagum_site_a")

def test_visual_network_serves_a_site(self):
    self.assertEqual(client.get("/api/visual-network?network_id=tagum_site_b").json()["network_id"], "tagum_site_b")

def test_scenario_write_rejects_an_unknown_network(self):
    self.assertEqual(client.post("/api/scenarios", json={"name": "x", "network_id": "nowhere", "engine_config": {}}).status_code, 422)

def test_backup_contains_and_restores_every_registered_network(self):
    # create a bundle in a scratch data dir; member names include networks/tagum_site_a.json, networks/tagum_site_b.json,
    # networks/registry.json; restoring into an empty scratch dir recreates them byte for byte
```

- [ ] **Step 2: Run them; they should fail**

Run: `.venv/Scripts/python.exe -m pytest tests/test_site_api.py -q --basetemp "$TEMP/sf_t8"`
Expected: FAIL — 404 on `/api/networks`.

- [ ] **Step 3: Implement**

- [ ] **Step 4: Run them, then the full backend suite**

Expected: 5 passed; full suite green.

- [ ] **Step 5: Commit**

Commit: "Serve and back up every registered network".

### Task 9: Site picker in the scenario editor

**Files:**
- Create: `src/api/networks.ts`, `src/lib/sites.ts`, `src/lib/sites.test.ts`
- Modify:
  - `src/api/native-scenario.ts`: `getSimulationOptions(networkId?: string)`
  - `src/components/scenarios-page.tsx:291-296, 366, 750-764`: a site `NativeSelect` and options reload on change; replace the read-only network name
  - `src/components/junction-details.tsx:61`: labels and photos keyed by network id
  - `src/components/compare-runs-page.tsx:62`: approaches from the junction data, not a fixed N/E/S/W list

**Interfaces:**
- Produces:
  - `listNetworks(): Promise<NetworkSummary[]>`, where `type NetworkSummary = { id: string; name: string; sha256: string; junctions: number }`
  - `siteOptions(networks: NetworkSummary[]): { value: string; label: string }[]`: registry order. The `tagum_network` entry is labelled ``Provisional ${junctions}-junction network``; others keep their name.
  - `approachLabel(approach: string, streetByApproach?: Record<string, string>): string` → the street name when known, else `"North"`/`"East"`/…

- [ ] **Step 1: Write the failing tests**

```ts
test("site options keep registry order and label the provisional network", () => {
  expect(siteOptions([{ id: "tagum_network", name: "Tagum", sha256: "a", junctions: 5 },
                      { id: "tagum_site_a", name: "Site A — Capitol Circumferential Rd × Dalisay Gante Rd", sha256: "b", junctions: 1 }]))
    .toEqual([{ value: "tagum_network", label: "Provisional 5-junction network" },
              { value: "tagum_site_a", label: "Site A — Capitol Circumferential Rd × Dalisay Gante Rd" }])
})
test("approach label prefers the street name", () => {
  expect(approachLabel("north", { north: "Sobrecarey Street" })).toBe("Sobrecarey Street")
  expect(approachLabel("west")).toBe("West")
})
```

- [ ] **Step 2: Run them; they should fail**

Run: `npx vitest run src/lib/sites.test.ts`
Expected: FAIL — module not found.

- [ ] **Step 3: Implement the helpers and wire the screens**

- [ ] **Step 4: Run the checks**

Run: `npx vitest run`, `npx tsc -b` and `npm run lint`. Expected: all green.

Browser check on a scratch database: create a scenario on Site A, save it, reopen it, and confirm the site and settings are kept and the map shows Site A.

- [ ] **Step 5: Commit**

Commit: "Let a scenario choose its study site".

---

## Part 3 — No signal: first come, first served

### Task 10: Junction mode `first_come`

**Files:**
- Modify:
  - `simulation/traffic_engine.py`:
    - constants near `:44-52`;
    - a `Vehicle.approach_arrival` field;
    - `_junction_open_to` (`:704-708`);
    - the new `_meets_committed_path` (alongside `_meets_own_approach_path` at `:1190-1214`);
    - the new `_first_come_permission` (alongside `_stop_priority` at `:1261-1276`);
    - the permission, commit check and approach-speed cap in `_move_vehicle` (`:1323-1351`)
  - `simulation/scenario_config.py:162-163`: accept `"first_come"`
  - `src/api/native-scenario.ts:5`: add `"first_come"` to `SignalPlan["mode"]`
- Test: `tests/test_first_come.py` (new)

**Interfaces:**
- Produces:
  - `APPROACH_ZONE_M = 30.0` and `FIRST_COME_APPROACH_SPEED_MPS = 4.0`, both with `# Provisional:` comments
  - `TrafficEngine._meets_committed_path(vehicle) -> bool` (any approach, no exemptions), which Task 13 reuses
  - `TrafficEngine._first_come_permission(vehicle, node) -> bool`
  - Test helper `busy_engine(network, *, seed: int = 7, density: str = "high", **config) -> TrafficEngine` in `tests/mixed_traffic_helpers.py`. It configures `traffic_density=density`, `pedestrian_density="low"`, `vehicle_mix=TAGUM_PROVISIONAL_MIX` and `**config`, then starts 1,800 s. Task 13 reuses it.

- [ ] **Step 1: Write the failing tests**

```python
FIRST_COME = {"signal_plans": {"j": {"mode": "first_come"}}}

def test_a_lone_car_crosses_without_stopping(self):
    engine = started_engine(junction_network(), trips=[{"time": 0, "source": "w", "destination": "e", "vehicle_type": "car"}], **FIRST_COME)
    # after its first 5 s and until it completes: speed >= 0.5 * FIRST_COME_APPROACH_SPEED_MPS and stop_arrival is None

def test_opposite_through_cars_cross_together(self):
    engine = started_engine(junction_network(), trips=[{"time": 0, "source": "w", "destination": "e", "vehicle_type": "car"},
                                                       {"time": 0, "source": "e", "destination": "w", "vehicle_type": "car"}], **FIRST_COME)
    # some tick has both vehicles with reserved_junction == "j"

def test_side_road_is_served_in_arrival_order_under_constant_main_road_flow(self):
    main = [{"time": t, "source": s, "destination": d, "vehicle_type": "car"}
            for t in range(0, 121, 2) for s, d in (("w", "e"), ("e", "w"))]
    engine = started_engine(junction_network(), trips=main + [{"time": 30, "source": "n", "destination": "s", "vehicle_type": "car"}], **FIRST_COME)
    # record approach_arrival and the tick each vehicle reserves "j";
    # no east/west car whose approach_arrival is more than 2.0 s after the north car's reserves before it,
    # and the north car reserves within 15 s of its approach_arrival

def test_an_earlier_vehicle_with_a_blocked_exit_does_not_hold_others(self):
    # routing_mode "static"; car A n→e (a left turn across the s→n path) at t=0, its exit lane j→e closed
    # (engine.close_lane("er", True)); car B s→n at t=2 with its exit open
    engine = started_engine(junction_network(), routing_mode="static",
                            trips=[{"time": 0, "source": "n", "destination": "e", "vehicle_type": "car"},
                                   {"time": 2, "source": "s", "destination": "n", "vehicle_type": "car"}], **FIRST_COME)
    engine.close_lane("er", True)
    # step until B reserves "j": it does so within 10 s of B's approach_arrival, while A is still unreserved

def test_no_overlap_at_any_tick_at_high_demand(self):
    assert_never_overlap(self, busy_engine(junction_network(), **FIRST_COME), 6000)

def test_no_stuck_gridlock_or_lost_vehicles_over_1800_s(self):
    engine = busy_engine(junction_network(), **FIRST_COME); peak = {"stuck": 0, "gridlock": 0}
    # step 18000 ticks, sampling every 10: track max of _last_metrics stuck_junction_vehicles and gridlock_seconds
    self.assertEqual(peak, {"stuck": 0, "gridlock": 0})
    self.assertEqual(engine._last_metrics["vehicle_conservation_error"], 0)

def test_same_seed_same_result(self):
    self.assertEqual(state_digest(busy_engine(junction_network(), seed=101, density="medium", **FIRST_COME), 300),
                     state_digest(busy_engine(junction_network(), seed=101, density="medium", **FIRST_COME), 300))   # simulation/footprints.py:83

def test_signalized_and_all_way_stop_plans_are_unchanged(self):
    # tests/test_junction_deadlock.py and tests/test_junction_side_by_side.py stay green (run in Step 4)
```

- [ ] **Step 2: Run them; they should fail**

Run: `.venv/Scripts/python.exe -m pytest tests/test_first_come.py -q --basetemp "$TEMP/sf_t10"`
Expected: FAIL — "Signal mode must be signalized or all_way_stop".

- [ ] **Step 3: Implement the rules in §0.6**

`_first_come_permission` settles one order per junction per tick, from vehicles inside `APPROACH_ZONE_M`, sorted by `(approach_arrival, id)`, as `_stop_priority` does. A vehicle is held only by earlier vehicles on **other** approaches that **could go now** and whose recorded or prospective path crosses its own (`_hits_sweep` on their sweeps).

"Could go now" is the same test `_stop_priority` applies at `:1274-1275`: exit open and with space, not `_must_wait_at_line`, not `_sweep_blocked`, plus not `_meets_committed_path`.

- [ ] **Step 4: Run them, then the mixed-traffic tests and the full suite**

```bash
.venv/Scripts/python.exe -m pytest tests/test_first_come.py tests/test_junction_deadlock.py tests/test_junction_side_by_side.py tests/test_gap_seeking.py -q --basetemp "$TEMP/sf_t10b"
.venv/Scripts/python.exe -m pytest tests -q --basetemp "$TEMP/sf_t10c"
```

Expected: all green. `tools/mixed_traffic_report.py --quick` gives the same digests as before (`first_come` is opt-in).

- [ ] **Step 5: Commit**

Commit: "Add a first-come-first-served junction mode for unsignalized sites".

### Task 11: Run-level control mode `no-signal`

**Files:**
- Modify:
  - `simulation/traffic_engine.py`: a `no_signal_control` attribute set in `__init__` (`:184-206`) and kept across `configure`; in `_reset_state` (`:241-258`), `mode = "first_come" if self.no_signal_control else plan.get("mode", "signalized")`; new `enable_no_signal_control()` and `disable_no_signal_control()`; `configure_rl_control` (`:1577`) raises while no-signal is on; `experiment_metadata` (`:1680-1692`) adds `control.junction_control`
  - `services/native_controller.py:5-22`: `"no-signal"` → `engine.enable_no_signal_control()`. `fixed-time` and RL modes call `disable_no_signal_control()` first.
- Test: `tests/test_no_signal_mode.py` (new)

**Interfaces:**
- Consumes: `first_come` from Task 10.
- Produces: `TrafficEngine.enable_no_signal_control() -> None` and `disable_no_signal_control() -> None`. Run `control_mode` `"no-signal"`; `controller_provenance` `"no-signal"`; label constant `NO_SIGNAL_LABEL = "No signal (first come, first served)"`.

- [ ] **Step 1: Write the failing tests**

```python
def test_no_signal_survives_start(self):
    engine = TrafficEngine(seed=101, network=junction_network()); apply_controller(engine, "no-signal"); engine.start(60)
    self.assertEqual({s.mode for s in engine.signals.values()}, {"first_come"})

def test_config_matches_the_fixed_time_run_and_control_differs(self):
    a, b = engine_with("no-signal"), engine_with("fixed-time")
    self.assertEqual(a.experiment_metadata()["config"], b.experiment_metadata()["config"])
    self.assertEqual(a.experiment_metadata()["control"]["junction_control"], "first_come")
    self.assertIsNone(b.experiment_metadata()["control"]["junction_control"])

def test_compare_key_pairs_no_signal_with_fixed_time(self):
    # manifests built from the two engines' experiment_metadata(); backend.main.compare_key gives equal keys

def test_rl_cannot_be_enabled_while_no_signal_is_on(self):
    engine.enable_no_signal_control()
    with self.assertRaisesRegex(ValueError, "RL signal control requires a signalized controlled junction"):
        engine.configure_rl_control()

def test_fixed_time_turns_no_signal_off(self):
    apply_controller(engine, "no-signal"); apply_controller(engine, "fixed-time"); engine.start(60)
    self.assertEqual({s.mode for s in engine.signals.values()}, {"signalized"})

def test_a_recorded_run_stores_no_signal(self):
    # scratch DB; generate_timeline(scenario_id, 30, run_id, seed=101, control_mode="no-signal"); join
    self.assertEqual(database.get_run_by_id(run_id)["control_mode"], "no-signal")
```

- [ ] **Step 2: Run them; they should fail**

Run: `.venv/Scripts/python.exe -m pytest tests/test_no_signal_mode.py -q --basetemp "$TEMP/sf_t11"`
Expected: FAIL — "Use fixed-time or ql:<model_id>…".

- [ ] **Step 3: Implement**

- [ ] **Step 4: Run them, then the full suite**

Expected: 6 passed; full suite green.

- [ ] **Step 5: Commit**

Commit: "Add the no-signal control mode for today's condition".

### Task 12: Show the no-signal junction correctly

**Files:**
- Modify:
  - `simulation/traffic_engine.py`:
    - `:619`: pedestrians cross on gaps under `first_come`;
    - `:945-949`: `_may_proceed_now` true under `first_come`;
    - `:1436`: `_blocked_on_green` counts waiting `first_come` vehicles;
    - `:1572`: light state `"n"` (no signal head);
    - `:1661-1673`: `controller "no-signal"`, `remaining_seconds None`, `timing_kind "none"`
  - Frontend:
    - `src/simulation/render-frame-adapter.ts:97` and `src/simulation/scene-geometry.ts:304-320`: state `"n"` draws no head
    - `src/components/junction-details.tsx:91-123`: shows "No signal — first come, first served" with no phase chips or timer
    - `src/components/simulation-visualization.tsx:73-80`
- Create: `src/lib/control-labels.ts`, `src/lib/control-labels.test.ts`
- Test: additions to `tests/test_no_signal_mode.py` and `src/simulation/__tests__/render-frame-adapter.test.ts`

**Interfaces:**
- Produces: `controlLabel(mode: string): string`:
  - `"no-signal"` → `"No signal (first come, first served)"`;
  - `"fixed-time"` → `"Fixed-time"` (Task 16 changes this);
  - `"ql"`/`"ql:7"` → `"SmartFlow RL (QL)"`, and likewise for DQL and PPO.

- [ ] **Step 1: Write the failing tests**

```python
def test_lanes_into_a_no_signal_junction_have_no_signal_head(self):
    self.assertEqual({light["state"] for light in engine.to_dict()["traffic_lights"].values()}, {"n"})

def test_junction_control_reports_no_timer(self):
    control = engine.junction_controls()["j"]
    self.assertEqual((control["controller"], control["timing_kind"], control["remaining_seconds"]), ("no-signal", "none", None))

def test_gridlock_watchdog_counts_waiting_first_come_vehicles(self):
    # junction_network(), routing_mode "static", one car w→e, FIRST_COME plan; close its exit lane j→e
    # (engine.close_lane("er", True); lane ids are road id + "f"/"r"); after 61 s with nothing else moving,
    # _last_metrics["gridlock_seconds"] > 0
```

```ts
test("no-signal lanes draw no signal head", () => { /* adapter output for state "n" has no head */ })
test("control labels", () => {
  expect(controlLabel("no-signal")).toBe("No signal (first come, first served)")
  expect(controlLabel("ppo:12")).toBe("SmartFlow RL (PPO)")
})
```

- [ ] **Step 2: Run them; they should fail**

Run: the pytest file and `npx vitest run src/lib/control-labels.test.ts src/simulation/__tests__/render-frame-adapter.test.ts`
Expected: FAIL.

- [ ] **Step 3: Implement**

- [ ] **Step 4: Run them, then the full suites**

Run the full backend suite, `npx vitest run`, `npx tsc -b` and `npm run lint`. Expected: green.

Browser check on a scratch database: a no-signal run on Site A shows no lights in 2D and 3D, and the junction panel reads "No signal — first come, first served".

- [ ] **Step 5: Commit**

Commit: "Show no-signal junctions without lights or timers".

---

## Part 4 — Traditional signal

### Task 13: Grouped phases

**Files:**
- Modify:
  - `simulation/scenario_config.py:166-170`: `phase_order` items may be lists (§0.8)
  - `simulation/traffic_engine.py`:
    - `Signal` (`:60-120`): phase keys joined by `+`, and `serves(approach)`;
    - replace `signal.family == lane.approach` with `signal.serves(lane.approach)` at `:563, 949, 1329, 1435, 1572`;
    - `_junction_open_to` (`:704-708`): admit any approach of the reserved phase key;
    - at commit, refuse when `_meets_committed_path` (Task 10) for phases with two or more approaches
  - `src/api/native-scenario.ts`: `phase_order: (string | string[])[]`
- Test: `tests/test_grouped_phases.py` (new)

**Interfaces:**
- Consumes: `_meets_committed_path` (Task 10).
- Produces: `Signal.serves(approach: str) -> bool`. Phase keys like `"north+south"`; `phase` names like `"NORTH+SOUTH_GREEN"`. `phase_family_from_name` still returns the part before `_`.

- [ ] **Step 1: Write the failing tests**

```python
GROUPED = {"signal_plans": {"j": {"phase_order": [["north", "south"], ["east", "west"], "pedestrian"]}}}

def test_opposite_approaches_get_green_together(self):
    engine = started_engine(junction_network(), trips=[{"time": 0, "source": "n", "destination": "s", "vehicle_type": "car"},
                                                       {"time": 0, "source": "s", "destination": "n", "vehicle_type": "car"}], **GROUPED)
    # some tick has both reserved on "j" during phase NORTH+SOUTH_GREEN

def test_a_left_turn_waits_for_oncoming_through_traffic(self):
    # north car turning left (towards east) and a south through car, both arriving together:
    # the turning car never reserves while the through car's remaining path is recorded; no overlap at any tick

def test_no_overlap_with_grouped_phases_at_high_demand(self):
    assert_never_overlap(self, busy_engine(junction_network(), **GROUPED), 6000)

def test_each_approach_must_appear_exactly_once(self):
    with self.assertRaisesRegex(ValueError, "phase_order must contain every available approach and pedestrian exactly once"):
        validate_config(DEFAULTS, {"signal_plans": {"j": {"phase_order": [["north", "south"], ["north", "east"], "west", "pedestrian"]}}}, junction_network())

def test_plans_listing_single_approaches_load_unchanged(self):
    plan = {"phase_order": ["north", "east", "south", "west", "pedestrian"]}
    self.assertEqual(validate_config(DEFAULTS, {"signal_plans": {"j": plan}}, junction_network())["signal_plans"]["j"]["phase_order"], plan["phase_order"])
```

- [ ] **Step 2: Run them; they should fail**

Run: `.venv/Scripts/python.exe -m pytest tests/test_grouped_phases.py -q --basetemp "$TEMP/sf_t13"`
Expected: FAIL — the `phase_order` validation error on list items.

- [ ] **Step 3: Implement §0.8 (groups)**

- [ ] **Step 4: Run them, then the full suite and `tools/mixed_traffic_report.py --quick`**

Expected: green; quick digests unchanged for ungrouped plans.

- [ ] **Step 5: Commit**

Commit: "Let opposite approaches share a green phase".

### Task 14: A green time per phase

**Files:**
- Modify:
  - `simulation/scenario_config.py:38-50, 171-185`: `phase_greens` validation; `fixed_red_seconds(order, green, yellow, all_red, phase_greens=None)`; `effective_maximum_red` uses the largest red
  - `simulation/traffic_engine.py` `Signal`: field `phase_greens: list[float] | None = None` and property `current_green`, used in `remaining` (`:89-91`) and `step` (`:108`); `_reset_state` passes the plan's `phase_greens`
  - `src/lib/signal-plan.ts`, `src/api/native-scenario.ts` (`phase_greens?: number[]`)
- Test: `tests/test_phase_greens.py` (new), `src/lib/signal-plan.test.ts`

**Interfaces:**
- Produces:
  - `Signal.current_green -> float`;
  - `fixed_red_seconds(..., phase_greens: list[float] | None = None) -> float`: the largest **vehicle-phase** red (§0.8), never the walk phase's;
  - `walk_red_seconds(order, green, yellow, all_red, phase_greens=None) -> float`: cycle − walk green, used for `walk_interval` (`simulation/traffic_engine.py:251-253`);
  - TS `fixedTimeRed(plan)` honours `phase_greens` and returns the vehicle-phase red.

- [ ] **Step 1: Write the failing tests**

```python
def test_each_phase_uses_its_own_green(self):
    plan = {"phase_order": [["north", "south"], ["east", "west"], "pedestrian"], "phase_greens": [39, 23, 10],
            "pedestrian_phase": "every_cycle"}
    # step a no-demand engine for one cycle; green durations observed per phase == [39.0, 23.0, 10.0] (±0.1)

def test_fixed_red_uses_each_phase_green(self):
    # cycle = (39+1+3) + (23+1+3) = 70; vehicle reds are 70−39 = 31 and 70−23 = 47; the function returns the largest
    self.assertEqual(fixed_red_seconds([["north", "south"], ["east", "west"]], 14, 3, 1, phase_greens=[39, 23]), 47.0)

def test_plans_without_phase_greens_are_unchanged(self):
    # today's default: cycle 4×(14+1+3) + (14+1) = 87, red 87 − 14 = 73
    self.assertEqual(fixed_red_seconds(["north", "east", "south", "west", "pedestrian"], 14, 3, 1), 73.0)

def test_maximum_red_check_uses_the_longest_vehicle_red(self):
    # cycle 70 + (10 + 1) = 81; vehicle reds 81−39 = 42 and 81−23 = 58; the walk red 81−10 = 71 is not counted
    plan = {"phase_order": [["north", "south"], ["east", "west"], "pedestrian"], "phase_greens": [39, 23, 10]}
    self.assertEqual(fixed_red_seconds(plan["phase_order"], 14, 3, 1, phase_greens=plan["phase_greens"]), 58.0)
    validate_config(DEFAULTS, {"signal_plans": {"j": {**plan, "maximum_red_seconds": 60}}}, junction_network())   # 60 ≥ 58: valid
    with self.assertRaisesRegex(ValueError, "shorter than this plan's own fixed-time red"):
        validate_config(DEFAULTS, {"signal_plans": {"j": {**plan, "maximum_red_seconds": 50}}}, junction_network())

def test_walk_interval_is_the_walk_phase_red(self):
    self.assertEqual(walk_red_seconds([["north", "south"], ["east", "west"], "pedestrian"], 14, 3, 1, phase_greens=[39, 23, 10]), 71.0)
    # an engine configured with that plan and pedestrian_phase "every_cycle" has signal.walk_interval == 71.0
```

The 60 s case passes even though the walk red (71 s) is longer. That shows the walk red is excluded from the maximum-red check.

```ts
test("fixed-time red uses per-phase greens", () => {
  expect(fixedTimeRed({ phase_order: [["north", "south"], ["east", "west"]], green_seconds: 14, yellow_seconds: 3, all_red_seconds: 1, phase_greens: [39, 23] })).toBe(47)
})
```

- [ ] **Step 2: Run them; they should fail**

Expected: FAIL — unknown signal plan field `phase_greens`.

- [ ] **Step 3: Implement §0.8 (per-phase greens)**

- [ ] **Step 4: Run them, the full suite and Vitest**

Expected: green.

- [ ] **Step 5: Commit**

Commit: "Give each signal phase its own green time".

### Task 15: Webster tool

**Files:**
- Create: `simulation/signal_design.py`, `tools/design_signal_plan.py`; endpoint `POST /api/signal-design/webster` in `backend/main.py` with a request model in `backend/schemas.py`
- Test: `tests/test_signal_design.py` (new)

**Interfaces:**
- Produces:
  - `PCU_FACTORS_PROVISIONAL: dict[str, float]` and `SATURATION_PCU_PER_HOUR_PER_3_3_M = 1800.0`, both `# Provisional:`
  - `@dataclass(frozen=True) class WebsterResult`: `cycle_seconds: float` (the cycle the final greens give), `webster_cycle_seconds: float` (C₀ before clamping), `phase_order: list`, `phase_greens: list[float]` (one per `phase_order` item, the walk phase included), `flow_ratios: list[float]`, `total_flow_ratio: float`, `lost_time_seconds: float`, `warnings: list[str]`, `assumptions: dict`
  - Warning texts:
    - "Cycle raised to the minimum cycle of 40 s (Webster gave N s)"
    - "Cycle lowered to the maximum cycle of 120 s (Webster gave N s)"
    - "Phase k green raised to the minimum green of 10 s"
    - "Phase k green lowered to the maximum green of 60 s"
    - "Actual cycle N s is outside the cycle limits"
    - "No vehicle demand; every phase gets its minimum green"
  - `webster_plan(phase_order: list, flows_pcu_per_hour: dict[str, float], saturation_pcu_per_hour: dict[str, float], *, yellow_seconds: float = 3.0, all_red_seconds: float = 1.0, startup_lost_seconds: float = 2.0, pedestrian_green_seconds: float | None = None, minimum_green: float = 10.0, maximum_green: float = 60.0, cycle_limits: tuple[float, float] = (40.0, 120.0)) -> WebsterResult`
  - `flows_from_counts(vehicles_per_hour_by_class: dict[str, dict[str, float]], pcu: dict[str, float] = PCU_FACTORS_PROVISIONAL) -> dict[str, float]` (approach → PCU/h)
  - `saturation_from_network(network: RoadNetwork, junction: str) -> dict[str, float]` (approach → width/3.3 × 1,800)
  - `plan_from_result(result: WebsterResult, base_plan: dict) -> dict` (a `signal_plans` entry)
  - CLI: `tools/design_signal_plan.py --network-id ID --counts counts.json [--phase-order JSON]`, which prints the plan and assumptions as JSON

- [ ] **Step 1: Write the failing tests**

```python
def test_two_phase_hand_example(self):
    result = webster_plan([["north", "south"], ["east", "west"]], {"north": 900, "south": 720, "east": 540, "west": 450},
                          dict.fromkeys(("north", "south", "east", "west"), 1800))
    self.assertEqual(result.cycle_seconds, 70.0)
    self.assertEqual(result.phase_greens, [39.0, 23.0])
    self.assertAlmostEqual(result.total_flow_ratio, 0.8)
    self.assertEqual(result.lost_time_seconds, 6.0)

def test_oversaturated_demand_is_refused(self):
    with self.assertRaisesRegex(ValueError, r"Total flow ratio Y must be below 1 for a fixed-time plan \(Y=1.05\)"):
        webster_plan([["north", "south"], ["east", "west"]], {"north": 1170, "south": 0, "east": 720, "west": 0},
                     dict.fromkeys(("north", "south", "east", "west"), 1800))

def test_a_short_cycle_is_clamped_and_reported(self):
    result = webster_plan([["north", "south"], ["east", "west"]], dict.fromkeys(("north", "south", "east", "west"), 90),
                          dict.fromkeys(("north", "south", "east", "west"), 1800))
    self.assertEqual(result.cycle_seconds, 40.0)
    self.assertTrue(any("minimum cycle" in warning for warning in result.warnings))

WALK = [["north", "south"], ["east", "west"], "pedestrian"]
SAT = dict.fromkeys(("north", "south", "east", "west"), 1800)

def test_walk_phase_hand_example(self):                       # §0.9 second worked example
    result = webster_plan(WALK, {"north": 540, "south": 450, "east": 360, "west": 270}, SAT, pedestrian_green_seconds=10)
    self.assertEqual(result.lost_time_seconds, 17.0)          # 2 × (2 + 1) + (10 + 1)
    self.assertEqual(result.cycle_seconds, 61.0)
    self.assertEqual(result.phase_greens, [25.4, 16.6, 10.0])

def test_zero_demand_gives_minimum_greens(self):
    result = webster_plan(WALK, dict.fromkeys(("north", "south", "east", "west"), 0), SAT, pedestrian_green_seconds=10)
    self.assertEqual(result.phase_greens, [10.0, 10.0, 10.0])
    self.assertEqual(result.cycle_seconds, 39.0)              # (10+4) + (10+4) + (10+1)
    self.assertIn("No vehicle demand; every phase gets its minimum green", result.warnings)

def test_clamped_greens_recheck_the_cycle(self):
    # y = 0.8 and 0.05: C0 = 14 / 0.15 → 94 s; displayed greens 81.8 → 60 (max) and 4.2 → 10 (min)
    result = webster_plan([["north", "south"], ["east", "west"]], {"north": 1440, "south": 0, "east": 90, "west": 0}, SAT)
    self.assertEqual(result.webster_cycle_seconds, 94.0)
    self.assertEqual(result.phase_greens, [60.0, 10.0])
    self.assertEqual(result.cycle_seconds, 78.0)              # (60+4) + (10+4)
    self.assertIn("Phase 1 green lowered to the maximum green of 60 s", result.warnings)
    self.assertIn("Phase 2 green raised to the minimum green of 10 s", result.warnings)

def test_flows_from_counts_apply_the_recorded_factors(self):
    self.assertEqual(flows_from_counts({"north": {"car": 100, "motorcycle": 200, "bus": 10}}), {"north": 220.0})

def test_result_becomes_a_valid_signal_plan(self):
    result = webster_plan(WALK, {"north": 540, "south": 450, "east": 360, "west": 270}, SAT, pedestrian_green_seconds=10)
    plan = plan_from_result(result, {"yellow_seconds": 3, "all_red_seconds": 1})
    validate_config(DEFAULTS, {"signal_plans": {"j": plan}}, junction_network())     # no error
    self.assertEqual((plan["phase_order"], plan["phase_greens"]), (WALK, [25.4, 16.6, 10.0]))

def test_a_plan_without_a_walk_phase_is_refused(self):
    result = webster_plan([["north", "south"], ["east", "west"]], {"north": 900, "south": 720, "east": 540, "west": 450}, SAT)
    with self.assertRaisesRegex(ValueError, "A scenario plan needs a walk phase; include 'pedestrian' in phase_order"):
        plan_from_result(result, {"yellow_seconds": 3, "all_red_seconds": 1})

def test_a_plan_breaking_its_maximum_red_is_refused(self):
    result = webster_plan(WALK, {"north": 540, "south": 450, "east": 360, "west": 270}, SAT, pedestrian_green_seconds=10)
    # vehicle reds: 61 − 25.4 = 35.6 and 61 − 16.6 = 44.4
    with self.assertRaisesRegex(ValueError, "shorter than this plan's own fixed-time red"):
        plan_from_result(result, {"yellow_seconds": 3, "all_red_seconds": 1, "maximum_red_seconds": 40})
```

- [ ] **Step 2: Run them; they should fail**

Run: `.venv/Scripts/python.exe -m pytest tests/test_signal_design.py -q --basetemp "$TEMP/sf_t15"`
Expected: FAIL — module not found.

- [ ] **Step 3: Implement the formulas in §0.9**

The endpoint takes `{scenario_id or network_id, junction, phase_order, counts_per_hour_by_class}` and returns the plan, `warnings` and `assumptions`. It needs `require_permission(user, "scenarios", "edit")`. A `ValueError` becomes a 422, as `create_scenario` does at `backend/main.py:1414-1415`.

- [ ] **Step 4: Run them, then the full suite**

Expected: 10 passed; green.

- [ ] **Step 5: Commit**

Commit: "Design traditional signal plans with Webster's method".

### Task 16: Signal editor and the "Traditional signal (fixed-time)" label

**Files:**
- Modify:
  - `src/components/native-scenario-controls.tsx:82-133`: a phase-group editor (for each approach, which phase it belongs to), a per-phase green input, and a "Design with Webster" button calling `src/api/signal-design.ts` (new)
  - `src/lib/control-labels.ts`: `"fixed-time"` → `"Traditional signal (fixed-time)"`. Then replace the hard-coded fixed-time text in:
    - `dashboard-controls.tsx:28, 105, 146, 157`
    - `dashboard-page.tsx:370`
    - `dashboard-kpis.tsx:22-23`
    - `scenarios-page.tsx:834, 839`
    - `runs-reports-page.tsx:487, 546`
    - `compare-runs-page.tsx:85-87, 179`
    - `native-scenario-controls.tsx`
    - `calibration-validation-page.tsx:124, 136, 150-151`
    - `help-about-page.tsx:57, 105, 107`
    - `junction-details.tsx:91`
  - Backend: a `FIXED_TIME_LABEL = "Traditional signal (fixed-time)"` constant in `simulation/traffic_engine.py`, used at `:205, 1602`, and `backend/simulation_runtime.py:531-533`. The stored value stays `"fixed-time"`.
- Test: `src/lib/control-labels.test.ts`, `src/lib/signal-plan.test.ts`; a Python check that `TrafficEngine().control_mode_label == FIXED_TIME_LABEL`

**Interfaces:**
- Consumes: Tasks 13–15.
- Produces: `designWebster(request): Promise<{ plan: SignalPlan; warnings: string[]; assumptions: Record<string, unknown> }>`; `groupsFromAssignment(assignment: Record<string, number>): (string | string[])[]`, a pure helper in `src/lib/signal-plan.ts`.

- [ ] **Step 1: Write the failing tests**

```ts
test("fixed-time is labelled as a traditional signal", () => expect(controlLabel("fixed-time")).toBe("Traditional signal (fixed-time)"))
test("phase assignment becomes grouped phase order", () =>
  expect(groupsFromAssignment({ north: 1, south: 1, east: 2, west: 2 })).toEqual([["north", "south"], ["east", "west"]]))
```

- [ ] **Step 2: Run them; they should fail**

- [ ] **Step 3: Implement**

- [ ] **Step 4: Run the checks**

Run the full Vitest suite, `npx tsc -b`, `npm run lint`, `npm run build` and the full backend suite. Expected: green.

Browser check: on a Site A scenario, group N+S and E+W, press "Design with Webster" with typed counts, save, reload, and confirm the plan is kept.

- [ ] **Step 5: Commit**

Commit: "Edit grouped phases and label fixed-time as a traditional signal".

---

## Part 5 — RL for each site

### Task 17: RL contract v4 and the `native-7` engine

**Files:**
- Modify:
  - `simulation/traffic_engine.py:36-37`: `ENGINE_VERSION = "native-7"`; `RL_SERVICE_ACTIONS` per §0.10
  - `apply_rl_action` (`:1612-1631`) and `get_green_phase_for_action` (`:1608-1609`): map slot → phase key
  - `simulation/rl_state.py:6-12, 73-80, 137-155`: `OBSERVATION_VERSION = "obs_v4"`; one-hot by slot; remove `INTERSECTION_ORDER` and `_intersection_one_hot`; mask by slot
  - `simulation/model_contract.py:12`: observation `"native-local-20-v4"`, actions `"phase-service-5-v2"`
  - `simulation/rl_env.py:90`: `observation_size = 20`
  - `simulation/rl_policy_runtime.py:51-53`
  - `simulation/metric_definitions.json`: `"engine_version": "native-7"`
  - `tests/test_native_cleanup.py` (engine assertion); `tests/test_site_rl_path.py` (observation length 20, per the pre-flight ruling)
  - `AGENTS.md` (contract names)
  - Model metadata writers: `simulation/dql_training.py:183-190`, `simulation/ppo_training.py:180-186` and the QL metadata in `tools/train_ql.py`. Each adds `phase_plan` (§0.10).
  - `simulation/traffic_engine.py:594-606` (`set_runtime_policy`): refuses a mismatched `phase_plan`
- Test: `tests/test_rl_contract_v4.py` (new)

**Interfaces:**
- Consumes: Task 13 phase keys; Task 7 `native_contract(network)`.
- Produces:
  - `phase_slots(signal: Signal) -> list[str | None]` (4 vehicle slots, then `"pedestrian"`) in `simulation/traffic_engine.py`;
  - `phase_plan(engine: TrafficEngine) -> dict` → `{"junction": engine.controlled_junction, "phase_keys": [...]}` in `simulation/model_contract.py`.

- [ ] **Step 1: Write the failing tests**

```python
def test_observation_has_20_values(self):
    self.assertEqual(len(extract_rl_snapshot(engine).observation), 20)

def test_mask_follows_phase_slots(self):
    # Site A scenario with phase_order [["north","south"],["east","west"],"pedestrian"], RL enabled
    self.assertEqual(snapshot.valid_action_mask[2:4], (0, 0))
    self.assertEqual(snapshot.valid_action_mask[4], 1)

def test_serve_phase_2_requests_the_second_group(self):
    self.assertEqual(engine.apply_rl_action("SERVE_PHASE_2")["applied"], True)
    self.assertEqual(engine.signals[node].pending, "east+west")

def test_contract_names(self):
    self.assertEqual({k: v for k, v in native_contract(site).items() if k != "network_sha256"},
                     {"engine": "native-7", "observation": "native-local-20-v4", "actions": "phase-service-5-v2"})

def test_native_6_models_are_refused(self):
    with self.assertRaisesRegex(ValueError, "Train a new model"):
        validate_metadata({"native_contract": {"engine": "native-6", "observation": "native-local-22-v3", "actions": "protected-service-5-v1",
                                               "network_sha256": site.fingerprint}})

def test_a_model_is_refused_when_the_phase_order_differs(self):
    # model trained with [["north","south"],["east","west"],"pedestrian"]; same network, engine plan [["east","west"],["north","south"],"pedestrian"]
    with self.assertRaisesRegex(ValueError, "Selected model was trained for phases .* this scenario uses"):
        engine.set_runtime_policy(StubPolicy({"native_contract": native_contract(site), "phase_plan": trained_plan}))

def test_a_model_accepts_different_green_times_for_the_same_phases(self):
    # same phase order and junction, phase_greens changed → no error
    engine.set_runtime_policy(StubPolicy({"native_contract": native_contract(site), "phase_plan": trained_plan}))

def test_training_metadata_records_the_phase_plan(self):
    # a 2-episode QL training run on a scratch Site A scenario writes metadata["phase_plan"] == phase_plan(engine)
```

- [ ] **Step 2: Run them; they should fail**

Run: `.venv/Scripts/python.exe -m pytest tests/test_rl_contract_v4.py -q --basetemp "$TEMP/sf_t17"`
Expected: FAIL — observation length 22.

- [ ] **Step 3: Implement §0.10**

- [ ] **Step 4: Run the full suite, plus `tools/mixed_traffic_report.py --quick` and the RL benchmark**

The RL benchmark is `benchmark_rl_env()` in the report tool. Expected: green; RL ≥ 7.07 decisions/s; determinism equal.

- [ ] **Step 5: Commit**

Commit: "Serve phase groups in the RL contract and release native-7".

### Task 18: Evaluate against both references

**Files:**
- Modify:
  - `services/rl_training_service.py:153-156`: controllers `["no-signal", "fixed-time", …]`
  - `tools/evaluate_controllers.py`:
    - `:38-39`: `DEFAULT_SEEDS = (101, 102, 103, 104, 105)` (development seeds); `FINAL_EVALUATION_SEEDS = tuple(range(201, 221))`; `SUPPORTED_CONTROLLERS` adds `"no-signal"`.
    - Seeds 201–220 are refused unless `--final` is passed: `ValueError("Seeds 201–220 are reserved for the final evaluation (Task 29); pass --final to use them")`.
    - `:259-260`: **warm-up runs under the evaluated controller**, not fixed-time (§0.10).
    - The output JSON adds top-level `warmup_seconds`, `warmup_control: "evaluated controller"`, `measurement_window_seconds` and `final: bool`. Each result adds `pending_demand` and `unfinished_vehicles`, and each summary metric adds `std`, `min` and `max` across seeds beside the existing mean and counts.
  - `services/rl_reporting_service.py:250-306`: each row of `build_combined_ranking(summary, model_learning=None)` (keyed by `"controller"`) gains `comparison_to_no_signal` and `beats_no_signal`, built exactly like `comparison_to_fixed_time` and `beats_fixed_time` but against `summary["no-signal"]`. Both are omitted when the summary has no `"no-signal"` entry.
- Test: `tests/test_evaluation_references.py` (new)

- [ ] **Step 1: Write the failing tests**

```python
def test_evaluation_command_includes_both_references(self):
    command = build_evaluation_command(["ql"], settings, {"ql": "m.json"})
    self.assertEqual(command[command.index("--controllers") + 1].split(",")[:2], ["no-signal", "fixed-time"])

def test_evaluation_defaults_to_development_seeds(self):
    self.assertEqual(DEFAULT_SEEDS, (101, 102, 103, 104, 105))

def test_final_seeds_need_the_final_flag(self):
    with self.assertRaisesRegex(ValueError, "Seeds 201–220 are reserved for the final evaluation"):
        run_cli(["--controllers", "no-signal", "--seeds", "201", ...])          # pattern of tests/test_result_reporting_api.py:96-103

def test_each_controller_warms_up_under_its_own_control(self):
    # evaluate "no-signal" with 30 s warm-up on a scratch Site A scenario: during warm-up every signal mode is "first_come"
    # (record the modes via a patched engine.step), and the output has warmup_control == "evaluated controller"

def test_results_report_spread_and_unfinished_demand(self):
    # two seeds → summary["no-signal"]["avg_wait"] has std, min and max; each result has pending_demand and unfinished_vehicles

def test_ranking_compares_against_both_references(self):
    ranking = build_combined_ranking(summary)   # summary has "no-signal", "fixed-time" and "ql" entries, built as in
                                                # tests/test_result_reporting_api.py:96-110
    ql = next(row for row in ranking if row["controller"] == "ql")
    self.assertIn("beats_no_signal", ql)
    self.assertIn("comparison_to_no_signal", ql)
    self.assertIn("beats_fixed_time", ql)

def test_ranking_without_a_no_signal_run_is_unchanged(self):
    ranking = build_combined_ranking(summary_without_no_signal)
    self.assertNotIn("beats_no_signal", ranking[0])
```

- [ ] **Step 2: Run them; they should fail**

- [ ] **Step 3: Implement**

- [ ] **Step 4: Run them and the full suite**

Expected: green.

- [ ] **Step 5: Commit**

Commit: "Evaluate RL against the no-signal and traditional references".

---

## Part 6 — Field data into SmartFlow

### Task 19: Field Observer: queue samples, exits and counting lines in the export

**Files:**
- Modify:
  - `tools/field_observer/field_observer/gui.py`: a new `queue_sample(self, data)` method and `POST /api/queue` route beside `/api/coverage` (`:399-470`); `review(self, data)` (`:232-268`) accepts `exit_id` for vehicle events
  - `tools/field_observer/field_observer/gui.html`: queue form and exit selector
  - `tools/field_observer/field_observer/core.py:300-330`: `export_revision` writes `lines.json` (the take's saved counting lines) into the revision and its `artifact_sha256`
- Test: `tools/field_observer/tests/test_gui.py`, `tools/field_observer/tests/test_field_observer.py`

**Interfaces:**
- Produces:
  - `POST /api/queue {time_s, approach_id, queue_count, visibility: "complete"|"lower_bound"|"unknown", reviewer, note}` → a `queue_samples.csv` row
  - `POST /api/review` accepts `exit_id` (an identifier from the configured exit lines)
  - a revision contains `lines.json`

- [ ] **Step 1: Write the failing tests**

They follow `GUITests.run_demo()` (`tools/field_observer/tests/test_gui.py:55`).

```python
def test_queue_samples_are_saved_from_the_gui(self):
    self.post("/api/queue", {"time_s": 30, "approach_id": "north", "queue_count": 7, "visibility": "complete", "reviewer": "T"})
    # queue_samples.csv has one row with queue_count "7"

def test_review_records_the_exit_of_a_vehicle(self):
    self.post("/api/review", {..., "exit_id": "exit_east"})
    # the event row's exit_id == "exit_east"

def test_export_includes_the_counting_lines(self):
    # after export, revision/lines.json equals the configured lines and is listed in manifest artifact_sha256
```

- [ ] **Step 2: Run them; they should fail**

Run: `cd tools/field_observer && .venv/Scripts/python.exe -m unittest discover -s tests -v`
Expected: the three new tests FAIL (404 or missing file).

- [ ] **Step 3: Implement**

- [ ] **Step 4: Run them; all 41 should pass**

- [ ] **Step 5: Commit**

Commit: "Record queues, exits and counting lines in Field Observer".

### Task 20: Convert a reviewed Field Observer revision into scenario demand

**Files:**
- Create: `services/field_observer_import.py`; `data/sites/tagum_site_a_mapping.json` and `data/sites/tagum_site_b_mapping.json` (templates generated by `site_mapping_template`, with boundaries listed and locations left for the team to fill)
- Modify: `services/observed_data_import.py:22-27, 115-121`: `od_counts` and `turn_counts` accept an optional `vehicle_type` column (default `car`), so count imports keep the class
- Test: `tests/test_field_observer_import.py` (new). It builds a synthetic revision folder with `events.csv`, `coverage.csv`, `reviewed_bins.csv` and `lines.json`.

**Interfaces:**
- Consumes: Task 4 site boundary ids; Task 19 `exit_id` and `lines.json`.
- Produces:
  - `DEFAULT_CLASS_MAP = {"car": "car", "motorcycle": "motorcycle", "tricycle": "tricycle", "tricycle/bao_bao": "tricycle", "bus": "bus", "truck": "truck"}`
  - `site_mapping_template(network: RoadNetwork) -> dict`, which lists each boundary with its road name and road length so the team can fill `distance_from_junction_m`
  - `convert_revision(revision_dir: Path, mapping: dict, network: RoadNetwork, *, origin_s: float, start_s: float, end_s: float) -> dict` → `{"trips_csv": str, "pedestrian_counts_csv": str | None, "summary": {"trips": int, "by_class": dict, "by_movement": dict, "excluded_by_class": dict}, "timing": {"origin_s": float, "measurement_start_s": float, "measurement_duration_s": float, "demand_end_s": float}, "provenance": dict}`. It follows the rules in §0.11:
    - trip times use the separate origin and reviewed upstream-speed estimates in §0.11 and are rounded to 0.1 s; include lead-in demand and preserve state at measurement start; the "approach length" is road-shape distance;
    - exits are searched up to `end_s + lead_out_s`;
    - pedestrian counts use 60 s bins on the same simulation-origin time axis, including lead-in coverage.

- [ ] **Step 1: Write the failing tests**

```python
# Synthetic fixtures have a verified empty initial state. MAPPING puts every arrival line at its boundary, so the time shift is 0; real recordings require the §0.11 initialization check.
def test_accepted_movements_become_trips_with_class_and_boundaries(self):
    result = convert_revision(revision, MAPPING, network, origin_s=0, start_s=0, end_s=900)
    rows = list(csv.DictReader(io.StringIO(result["trips_csv"])))
    self.assertEqual(rows[0], {"time_s": "12.4", "source": "boundary_0", "destination": "boundary_2", "vehicle_type": "motorcycle"})

def test_arrival_times_move_back_by_the_boundary_to_line_travel_time(self):
    # arrival line 50 m from the junction on a 250 m approach at 8.33 m/s: shift 200 / 8.33 = 24.0 s; observed at 60.0 s
    result = convert_revision(revision, MAPPING_LINE_AT_50_M, network, origin_s=0, start_s=0, end_s=900)
    self.assertEqual(first_row(result)["time_s"], "36.0")

def test_early_measurement_arrival_is_imported_as_lead_in(self):
    # origin 0, measurement [120, 1020), observed arrival 125, upstream travel 24
    result = convert_revision(revision, MAPPING_LINE_AT_50_M, network, origin_s=0, start_s=120, end_s=1020)
    self.assertEqual(first_row(result)["time_s"], "101.0")
    self.assertEqual(result["timing"]["measurement_start_s"], 120.0)
    # integration: this vehicle remains in the engine across measurement start; no reset or re-spawn

def test_missing_initial_state_or_lead_in_coverage_is_refused(self):
    # A vehicle occupies the approach at origin and no initialization evidence exists.
    # Refuse with INSUFFICIENT_INITIAL_STATE; never drop it or move its timestamp to zero.
    ...

def test_shifted_post_window_arrival_is_kept_as_boundary_demand(self):
    # observed arrival 910, shift 24, measurement end 900 -> boundary time 886 is included
    ...

def test_vehicle_and_pedestrian_demand_share_the_origin(self):
    # origin 30 and measurement start 150: both demand streams use video time minus 30;
    # only [120, measure_end) engine time contributes to measurement
    ...

def test_an_arrival_line_outside_the_modelled_approach_is_refused(self):
    with self.assertRaisesRegex(ValueError, "arrival_north is 400 m from the junction; the modelled approach is 250 m"):
        convert_revision(revision, MAPPING_LINE_AT_400_M, network, origin_s=0, start_s=0, end_s=900)

def test_exits_after_the_window_are_found_in_the_lead_out(self):
    # arrival at 890 s, exit at 950 s, lead_out_s 120 → one trip, no "no exit" error
    self.assertEqual(convert_revision(revision, MAPPING, network, origin_s=0, start_s=0, end_s=900)["summary"]["trips"], 1)

def test_missing_lead_out_coverage_is_refused(self):
    # exit-line coverage ends at 900 s but lead_out_s is 120
    with self.assertRaisesRegex(ValueError, "exit_east coverage ends at 900 s; the lead-out needs it until 1020 s"):
        convert_revision(revision, MAPPING, network, origin_s=0, start_s=0, end_s=900)

def test_excluded_classes_are_reported_not_hidden(self):
    # class_map {"tricycle/pedicab": "exclude"} and two pedicab arrivals
    result = convert_revision(revision, MAPPING_EXCLUDING_PEDICABS, network, origin_s=0, start_s=0, end_s=900)
    self.assertEqual(result["summary"]["excluded_by_class"], {"tricycle/pedicab": 2})

def test_provenance_names_the_reviewed_video(self):
    provenance = convert_revision(revision, MAPPING, network, origin_s=0, start_s=0, end_s=900)["provenance"]
    self.assertEqual(set(provenance), {"survey_id", "take_id", "revision", "manifest_sha256", "reviewed_bins_sha256",
                                       "origin_s", "window", "measurement_start_s", "demand_end_s", "lead_out_s", "initialization", "upstream_time_assumptions", "mapping_sha256"})

def test_incomplete_coverage_in_the_window_is_refused(self):
    # reviewed_bins row for arrival_north 0–900 has count ""
    with self.assertRaisesRegex(ValueError, "arrival_north.*0–900 s.*incomplete"):
        convert_revision(revision, MAPPING, network, origin_s=0, start_s=0, end_s=900)

def test_an_unmapped_class_with_vehicles_is_refused(self):
    # one accepted tricycle/pedicab arrival and no class_map entry
    with self.assertRaisesRegex(ValueError, "tricycle/pedicab.*1 vehicle.*class_map"):
        convert_revision(revision, MAPPING, network, origin_s=0, start_s=0, end_s=900)

def test_arrivals_without_an_exit_are_refused_by_count(self):
    with self.assertRaisesRegex(ValueError, "3 arrivals have no exit"):
        convert_revision(revision, MAPPING, network, origin_s=0, start_s=0, end_s=900)

def test_result_imports_through_the_existing_importer(self):
    # import_observations(scenario on tagum_site_a, "trips", result["trips_csv"], period) succeeds;
    # engine_config["trips"] has the same count and vehicle types

def test_count_imports_keep_the_vehicle_type(self):
    # an od_counts CSV with vehicle_type "bus" → imported trips are all "bus"; without the column → "car" as before

def test_pedestrian_starts_become_60_s_pedestrian_counts(self):
    # three accepted pedestrian_start events at a crossing location at 10, 50 and 70 s
    rows = list(csv.DictReader(io.StringIO(result["pedestrian_counts_csv"])))
    self.assertEqual([(r["start_s"], r["end_s"], r["count"]) for r in rows], [("0", "60", "2"), ("60", "120", "1")])
```

- [ ] **Step 2: Run them; they should fail**

Run: `.venv/Scripts/python.exe -m pytest tests/test_field_observer_import.py -q --basetemp "$TEMP/sf_t20"`
Expected: FAIL — module not found.

- [ ] **Step 3: Implement**

The other test calls in this file pass `network` as the third argument too. `import_observations` records the conversion's `provenance` in `demand_source.datasets`, through a new optional `provenance: dict | None = None` argument stored with the dataset entry. Carry `timing` into the scenario/run measurement metadata and keep warm-up demand on its original engine timestamps. Task 26 consumes exactly this timing contract; do not infer the measurement start from the first trip.

- [ ] **Step 4: Run them, then the full suite**

Expected: all converter tests pass, including the four added origin/initialization cases; record the actual count.

- [ ] **Step 5: Commit**

Commit: "Convert reviewed Field Observer counts into scenario demand".

---

## Part 7 — Validation and the three-way comparison

### Task 21: Calibrate on the no-signal run

**Files:**
- Modify:
  - `backend/research_routes.py:151-156`: accept `control_mode in {"no-signal", "fixed-time"}`, with the message "Choose a completed no-signal or fixed-time run."
  - `src/components/calibration-validation-page.tsx:70, 124, 136, 150-151`: list both kinds (two `listRuns` calls, merged by id); card title "2. Simulated run of the measured condition"; description "For a site without a traffic light, choose its no-signal run."
- Test: `tests/test_research_workspace.py` (add tests)

- [ ] **Step 1: Write the failing tests**

```python
def test_calibration_accepts_a_completed_no_signal_run(self): ...   # baseline_snapshot(run_id) returns metrics
def test_calibration_refuses_an_rl_run(self):
    with self.assertRaisesRegex(ValueError, "Choose a completed no-signal or fixed-time run."): baseline_snapshot(rl_run_id)
```

- [ ] **Step 2: Run them; they should fail**

- [ ] **Step 3: Implement**

- [ ] **Step 4: Run them, the full suite and the frontend checks**

- [ ] **Step 5: Commit**

Commit: "Calibrate against the no-signal run of an unsignalized site".

### Task 22: Dashboard KPIs measured against today's condition

**Files:**
- Create: `src/lib/reference-run.ts`, `src/lib/reference-run.test.ts`
- Modify: `src/components/dashboard-page.tsx:272-288, 292, 374`; `src/components/dashboard-kpis.tsx:16-24`

**Interfaces:**
- Produces:
  - `comparisonKey(experiment: SavedExperiment): string`: the TypeScript twin of `compare_key` (`backend/main.py:1186-1198`). It is a JSON string of `engine_version`, `network_sha256`, `seed`, `duration_seconds`, `measurement_start`, `demand_sha256` and `config` without `routing_mode`, with object keys sorted.
  - `pickReferenceRun(runs: SimulationRunRecord[], current: { experiment: SavedExperiment; activeRunId: number | null }): { run: SimulationRunRecord; kind: "no-signal" | "fixed-time" } | null`. It considers only runs whose `comparisonKey(savedExperiment(run.metrics))` equals the current key, prefers the newest `no-signal` run, and falls back to `fixed-time`.
- `DashboardKpis` props become `{ metrics, reference, isReferenceRun }`. The note reads ``vs ${controlLabel(kind)} run #${id} (same settings, demand, seed and duration)``, or "No matching no-signal or fixed-time run yet (same settings, demand, seed and duration)". Recorded references are 300 s runs (Task 23), so a live run gets a reference only when it also runs 300 s; this is intended.

- [ ] **Step 1: Write the failing tests**

```ts
test("prefers the matching no-signal run", () => expect(pickReferenceRun([fixed(5), noSignal(4)], current)?.kind).toBe("no-signal"))
test("falls back to fixed-time", () => expect(pickReferenceRun([fixed(5)], current)?.run.id).toBe(5))
test("ignores another seed, network, engine or the active run", () =>
  expect(pickReferenceRun([noSignal(4, { seed: 2 }), noSignal(6, { network_sha256: "other" }), noSignal(7, {}, { id: 7, active: true })], current)).toBeNull())
test("ignores a run made before the scenario was edited", () =>
  expect(pickReferenceRun([noSignal(4, { demand_sha256: "before-edit" })], current)).toBeNull())
test("ignores a different measurement window or duration", () =>
  expect(pickReferenceRun([noSignal(4, { measurement_start: 60 }), noSignal(5, { duration_seconds: 600 })], current)).toBeNull())
test("routing mode alone does not break the match", () =>
  expect(pickReferenceRun([noSignal(4, { config: { ...config, routing_mode: "static" } })], current)?.run.id).toBe(4))
```

- [ ] **Step 2: Run them; they should fail**

- [ ] **Step 3: Implement**

- [ ] **Step 4: Run the checks**

Run the full Vitest suite, `npx tsc -b` and `npm run lint`. Browser check: a fixed-time run on Site A after a no-signal run shows changes "vs No signal (first come, first served) run #N".

- [ ] **Step 5: Commit**

Commit: "Measure dashboard KPIs against today's no-signal condition".

### Task 23: Record both reference conditions

**Files:**
- Modify: `tools/record_fixed_time_baselines.py:35-63`: `--conditions` (default `no-signal,fixed-time`); `record_baselines(seed, seconds, conditions)` records one run per scenario and condition
- Test: `tests/test_record_baselines.py:49-59`

**Owner gate:** running this on `data/smartflow.db` needs fresh approval.

- [ ] **Step 1: Change the test**

The test becomes `test_with_confirm_it_backs_up_and_records_both_conditions`: two runs whose control modes are `{"no-signal", "fixed-time"}`, both completed and on this engine.

- [ ] **Step 2: Run it; it should fail** (one run is recorded)

- [ ] **Step 3: Implement**

- [ ] **Step 4: Run it, then the full suite**

- [ ] **Step 5: Commit**

Commit: "Record no-signal and fixed-time references for each scenario".

### Task 24: Name the three conditions in comparisons and reports

**Files:**
- Modify:
  - `backend/main.py:1228-1232` (`compare_run_label`), which uses the provenance label already set by Tasks 11 and 16
  - `src/components/runs-reports-page.tsx:487, 546` and `compare-runs-page.tsx:85-87, 179` → `controlLabel`
  - The runs report export (`export_runs_report`, `backend/main.py:1645`; rows from `run_report_row`, used by `write_runs_csv` at `:1091-1099` and the JSON writer) adds a `condition` field from the provenance label.
- Test: `tests/test_result_reporting_api.py`, beside `test_actual_csv_and_json_exports_include_definitions_windows_and_unavailability` (`:80`)

- [ ] **Step 1: Write the failing test**

`test_export_names_the_condition`: exported rows for a no-signal run and a fixed-time run carry `condition` "No signal (first come, first served)" and "Traditional signal (fixed-time)".

- [ ] **Step 2: Run it; it should fail**

- [ ] **Step 3: Implement**

- [ ] **Step 4: Run the full suite and Vitest**

- [ ] **Step 5: Commit**

Commit: "Name the three study conditions in comparisons and exports".

---

## Part 8 — Acceptance, validation, final results and documentation

### Task 25: Site acceptance cases

**Files:**
- Modify: `tools/mixed_traffic_report.py:24-50, 150-160`:
  - `NETWORKS` adds `"siteA"` and `"siteB"`;
  - `CASES` adds all 12 cases listed in §0.13: for each of `siteA` and `siteB`, `-medium-nosignal`, `-medium-fixed`, `-medium-grouped`, `-high-nosignal`, `-high-fixed`, `-high-grouped`;
  - `case_options` adds `no_signal` and `grouped`:
    - `fixed` cases use the scenario's default ungrouped plan;
    - `grouped` cases use `[["north","south"],["east","west"],"pedestrian"]` with a Webster plan from the case's own synthetic per-approach demand;
  - the site cases run at the development seeds 101 and 102;
  - `--out` default unchanged.
- Create: `docs/reports/two-site-acceptance.json`
- Test: `tests/test_mixed_traffic_report.py`

- [ ] **Step 1: Write the failing test**

```python
def test_site_cases_use_their_networks_and_control():
    assert case_options("siteA-high-nosignal")[3]["no_signal"] is True
    assert CASES["siteB-high-grouped"][0] == "siteB"

def test_every_site_condition_and_demand_has_a_case():
    expected = {f"{site}-{density}-{control}" for site in ("siteA", "siteB") for density in ("medium", "high")
                for control in ("nosignal", "fixed", "grouped")}
    assert expected <= set(CASES)
    assert len(expected) == 12
```

- [ ] **Step 2: Run it; it should fail**

- [ ] **Step 3: Implement**

- [ ] **Step 4: Run the full report in the background**

```bash
.venv/Scripts/python.exe tools/mixed_traffic_report.py --out docs/reports/two-site-acceptance.json > "$TEMP/two-site-acceptance.log" 2>&1
```

Check every threshold in §0.13 against the JSON.

- **Scales:** if a site case's largest `queue_count_p95` is above 62, apply the scale rule in §0.10 with a test pinning the new scale.
- **QL bins:** record the per-approach queue distribution. If more than a quarter of non-zero samples at either site exceed 8 vehicles, add one `QUEUE_BIN_EDGES` edge at that site's p75, rounded to a whole vehicle, with a test that p50 and p90 fall in different bins.

- [ ] **Step 5: Commit**

Commit the report and any scale or bin change. Commit: "Record two-site acceptance results".

### Task 26: Per-site calibration, validation measures and the gate check

Implement §0.15 and one measurement definition shared by observed and simulated data.

**Files:**
- Create: `services/site_validation.py`, `tools/validate_site.py`, `tests/test_site_validation.py`.
- Modify: `simulation/scenario_config.py`, `simulation/traffic_engine.py` and scenario API types/round-trip consumers for `engine_config.site_calibration`.
- Modify: the Task 19 Field Observer review/export path to retain priority-line crossing times and episode-linked readiness annotations. Export a hashed `priority_review.csv` with episode/pair ids, movement ids, priority and entry times, readiness at the decision, blocked reason, visibility, reviewer and note. Use a reviewed `movement_conflicts` table in the site mapping; do not infer conflicts from compass labels alone.
- Update the Task 19 line-role configuration and UI to support the `priority` role, preserve these annotations in immutable exports, and add Field Observer tests for their save/reopen/export behaviour. Include the new calibration and evidence fields in frontend API types and saved-scenario round-trip tests.

**Interfaces and definitions:**
- Resolve calibration per engine instance. Reject the wrong site id, unknown classes, non-finite/nonpositive values and incomplete class-factor maps. Never mutate global defaults. Carry the resolved calibration hash in recordings, training metadata and validation reports.
- **Queue:** stopped vehicles on each approach, sampled at the same video-relative 30-second instants, with the stopped-speed definition recorded and complete visibility required.
- **Discharge:** crossings of the same mapped stop line per approach per 15-minute bin. Detect the physical mapped line in both sources; connector entry is equivalent only when verified to coincide with that line.
- **Travel time:** arrival-line to exit-line duration for the same arrival-window cohort, with follow-up and unfinished counts. Report mean, median and count; gate on the predeclared mean and coverage rules. Do not discard unfinished/occluded vehicles without reporting them.
- **Arrival-order share:** unique pairs on different approaches whose reviewed movements conflict and whose priority-zone entry times differ by more than `tie_tolerance_s` and no more than `pair_window_s`. Use the same frozen priority-zone boundaries in video and simulation, not the upstream demand lines. Both vehicles must be at the decision area before the first enters. At that decision the earlier vehicle must have exit space, be free of a vehicle ahead, and have a path clear of committed vehicles and standing vehicles. Nonconflicting, noncompeting, tied, blocked-earlier and unobservable pairs are excluded with separate counts; they are not violations. A later vehicle entering first is a violation only for an eligible pair. Record order from front-crossing times at the mapped stop lines; unresolved entry ties are excluded. Never infer readiness only from who entered first.
- Pair readiness must be independently reviewed in video and measured from the same physical predicates in simulation. Unknown readiness/occlusion stays unknown. If the eligible count is below `min_order_pairs`, return `INCONCLUSIVE`; do not declare first-come rejected or validated. Changing the priority-zone calibration requires matching annotations.
- `observed_measures(revision_dir, mapping, *, start_s, end_s, criteria)` and `simulated_measures(scenario, mapping, *, seeds, origin_s, start_s, end_s, criteria)` return the four measures, sample/coverage counts, unfinished cohort, eligible pair count and exclusion counts. Simulation also returns `per_seed`, safety and resolved model identity. It uses the Task 20 timing contract, imports lead-in demand, retains state across measurement start and runs no-signal control throughout.
- `check_validation(observed, simulated, criteria)` returns `status: PASS|FAIL|INCONCLUSIVE`, `passed`, `safety_ok`, `hypothesis_ok` (nullable when evidence is insufficient), reasons and per-measure comparisons. Missing required criteria, approaches or metrics cannot pass. Sufficient evidence with an observed eligible share below the hypothesis threshold fails even when simulation reproduces that share.
- `validation_gate(report, current_identity, ledger)` rejects stale identities, development-only reruns and missing independence evidence. Matching is against the validated physical model and protocol; intervention settings are recorded separately.
- CLI: `tools/validate_site.py --scenario-id N --revision DIR --mapping FILE --criteria FILE --purpose calibration|validation --origin-s O --start-s S --end-s E`. Read development seeds from criteria and reject others. Persist a new immutable `docs/reports/site-validation-<site>-<purpose>-<report_id>.json` for each invocation, with §0.15 evidence identity. Print the status and every measure/reason. Never overwrite earlier attempts on the same date.

- [ ] **Step 1: Write failing tests** covering:
  - synthetic queue, discharge and travel-time values at matching physical lines and sample times;
  - a vehicle from lead-in remaining queued at measurement start, with no reset;
  - eligible conflicting pairs: two respected out of three gives 2/3;
  - nonconflicting movements, blocked earlier vehicles, noncompeting arrivals, entry/arrival ties and unknown readiness excluded with reasons;
  - insufficient/zero eligible pairs, missing approaches, incomplete coverage, missing metrics and non-finite values never passing;
  - tolerance boundaries, observed zero, and a failed arrival-order hypothesis with sufficient evidence;
  - every safety failure rejecting the gate;
  - per-site calibration round-trip through saving, editing, recording, training, evaluation and backup/restore;
  - configuring Site B leaves Site A and existing default-network results unchanged;
  - engine, network-width, calibration, mapping or criteria changes making a previous pass stale;
  - a day-2-informed revision being refused independent validation on day 2, while a documented untouched recording can qualify;
  - immutable report files for two attempts on the same day;
  - CLI refusal of final seeds.
- [ ] **Step 2: Run the targeted tests; confirm they fail for the missing behaviour.**

Run: `.venv/Scripts/python.exe -m pytest tests/test_site_validation.py -q --basetemp "$TEMP/sf_t26"`.

- [ ] **Step 3: Implement the interfaces, calibration resolution and evidence checks.**
- [ ] **Field Observer verification:** run its unittest suite for the new priority role and review/export annotations; inspect one synthetic export for intact hashes and unresolved-readiness handling.
- [ ] **Step 4: Run the targeted tests, existing scenario/recording/training/backup tests, the full backend suite and TypeScript checks.** All must pass; record actual counts. Re-run default-network determinism checks to prove calibration did not alter shared defaults.
- [ ] **Step 5: Commit.**

Commit: "Save per-site calibration and validate against independent observations".

### Task 27: Documentation

**Files:**
- `docs/ARCHITECTURE_AND_PLAN.md`: D30, "two-site study: separate site networks, `first_come`, no-signal, grouped phases, Webster, contract v4, `native-7`", placed before D29
- `docs/PROGRESS_AND_HANDOFF.md`: a dated entry with the verification
- `docs/FIELD_DATA_SMARTFLOW_INTEGRATION.md`: the signal-specific rows marked "not applicable at unsignalized sites"; the converter path
- `docs/FIELD_RECORDING_PROTOCOL.md`: arrival and exit lines; queue samples; entry order
- `docs/RESEARCH_METHOD.md`: three-way design; validation vs evaluation
- `docs/PROJECT_OVERVIEW.md:95`: no-signal is now modelled
- `docs/VIDEO_OBSERVATION_TOOL_PLAN.md:87`: the retired `tagum_passenger_tricycle` replaced with `tricycle` / `bao_bao` / `pedicab`
- `AGENTS.md`: contract names
- `docs/reviews/MANUSCRIPT_REVISION_GUIDE_2026-10-31.md` (new): study area of two unsignalized sites; three-way comparison; validation (no signal vs video) separated from evaluation (proposals); definitions of *unsignalized intersection* and *fixed-time (pre-timed, traditional) signal*; SUMO → SmartFlow engine; emergency vehicles removed

- [ ] **Step 1: Write the updates**
- [ ] **Step 2: Check them**

Every local link resolves; `git diff --check` is clean.

- [ ] **Step 3: Commit**

Commit: "Document the two-site study design and results". Write a progress entry at the end of each milestone, and the rest when Milestone 2 ends.

### Task 28: Observed midday scenario, calibration and independent validation (Milestone 1 gate)

Run per site once F1–F4 and F6 exist, Site A first. Use a scratch database; using the owner's database remains subject to the existing approval requirement.

- [ ] **Step 1: Check independence and pre-registration.** Verify the criteria hash/commit, nominated recording identity and access ledger. Freeze criteria before inspecting held-out outcomes; an earlier conversion timestamp alone is insufficient. If day 2 has informed model/criteria choices, nominate another untouched recording.
- [ ] **Step 2: Complete mapping and initialization.** Record demand/priority/stop/exit lines, measured distances, movement conflicts, per-class upstream time assumptions, coverage, initialization evidence, origin, measurement window and follow-up. Obtain reviewed priority/readiness annotations. Reject insufficient initialization or missing evidence instead of silently assuming zero queues.
- [ ] **Step 3: Import day 1.** Supply `origin_s`, `start_s` and `end_s`, import observed lead-in demand, verify provenance and timing persist in the scratch scenario, and save its `site_calibration` object. Do not reset at measurement start.
- [ ] **Step 4: Test the hypothesis on day 1.** Run the calibration-purpose validator. With sufficient evidence, a share below the threshold rejects first-come for that site and requires a revised model design. `INCONCLUSIVE` instead requests additional reviewed observations; it cannot open the gate.
- [ ] **Step 5: Calibrate on development data.** Adjust only the saved per-site parameters in §0.15. Record each change and its measures. Re-annotate priority boundaries when zone length changes. Confirm the other site and default networks are unaffected. Freeze the final model, calibration, mapping, measurement method and criteria hashes.
- [ ] **Step 6: Site B median check.** Record the F2 finding and the modelling decision under §0.3. Stating a limitation does not waive the validation gate.
- [ ] **Step 7: Independently validate.** Convert the nominated untouched recording, import its own observed lead-in, and run the validation-purpose tool on the frozen model. Keep the immutable report and validation record.
  - `PASS`: retain the full identity and independence evidence.
  - `INCONCLUSIVE`: collect sufficient independent evidence under the declared protocol; keep the gate closed.
  - `FAIL`: preserve the failure and stop the gate. A revised model may be diagnosed on that recording, but independent confirmation requires a fresh untouched recording after the revised model/protocol is frozen. A day-2 retry cannot grant the revised model a pass. If new evidence is unavailable, report the site as unvalidated.
- [ ] **Step 8: Save the evidence.** Commit the mapping, criteria, access ledger, immutable reports and scenario export containing per-site calibration. Never commit tuned global constants as site calibration. Use a commit description matching the actual result; do not call an inconclusive/failed site validated.

Milestone 1 ends when one site has a current independent pass. Update Task 27 documentation with the exact evidence identity.

### Task 29: Final results for a validated site (Milestone 2)

This runs only for a site with a current independent pass from Task 28. It needs Parts 4, 5 and Tasks 22–25. Before training and before final evaluation, run the Task 26 gate against the current physical-model identity and ledger. Task 17 changes the engine identity after Milestone 1: require a documented compatibility check and no-signal revalidation under §0.15; never carry a native-6 pass automatically to native-7. Report-only repetition on unchanged held-out data must not inform tuning; a behaviour revision informed by failure requires fresh independent evidence.

- [ ] **Step 1: Design the traditional plan.**
  - Build per-approach, per-class flows per hour from the day-1 conversion summary and convert them with `flows_from_counts`.
  - Design the grouped plan with Webster (`tools/design_signal_plan.py`) and save it on the scenario, with its `assumptions` and `warnings` in the scenario description.
- [ ] **Step 2: Train, with the owner's approval.**
  - Ask the owner to approve the training time.
  - Train **three** models per algorithm (QL, DQL, PPO) on the site scenario with the training-seed sets {11–15}, {21–25} and {31–35}. Each model's metadata records its contract, `phase_plan` and seeds.
- [ ] **Step 3: Run the final evaluation, once.**
  - `tools/evaluate_controllers.py --final --seeds 201,…,220 --controllers no-signal,fixed-time,<each model>` on the site scenario.
  - Record the first use of seeds 201–220 in the ledger. The final seeds are never used to choose between models; every trained model is reported.
- [ ] **Step 4: Write the results report** `docs/reports/two-site-results.json`, plus a summary in the progress entry. For each condition it gives:
  - the mean, standard deviation, min and max over seeds;
  - per-seed values, and the spread across the three models per algorithm;
  - unfinished demand, the warm-up, and the measurement window.

  It also states the limits: midday only; provisional values; the pedicab decision; Site B's median, if applicable.
- [ ] **Step 5: Commit**

Commit: "Record final two-site results for <site>".

---

## Team field work (not code; starts now, runs alongside)

- **F1 — Count the midday video for each site with Field Observer:**
  - one arrival line per approach, upstream of its farthest midday queue;
  - one priority-zone boundary and one stop-line line per approach, plus reviewed movement/conflict and readiness evidence;
  - one exit line per exit;
  - full-pass coverage;
  - classes reviewed, including bao-bao / pedicab;
  - entry→exit recorded for each vehicle;
  - queue samples every 30 s;
  - pedestrian crossings.

  *Done when* each site has an exported revision with no blank bins in a continuous 60-minute window, plus reviewed lead-in demand and defensible initialization at the chosen simulation origin, and at least 120 s of follow-up (extended as needed under §0.11). All required priority pairs and exclusions are independently reviewable; insufficient visibility is recorded.
- **F2 — Field check each site** against the checklist in §0.2: measured widths, queue reach, and each counting line's distance from the centre. *Done when* every leg has a width and a queue reach, and Site B's median crossing is described (one movement, or stopping inside the median, and how often).
- **F3 — Reserve an independent midday recording** at each site, normally day 2. Record its identity and first outcome access in the ledger; freeze the model/criteria before inspecting its outcomes. After a failure-informed revision, reserve a fresh untouched recording (normally day 3). No fresh recording means the revised site remains unvalidated.
- **F4 — Decide the class mapping** for pedicab (pedal), jeepney and bicycle, with the adviser. Pedicab options are in §0.11. *Done when* each has a `class_map` entry (a class or `"exclude"`) and a one-line justification.
- **F5 — Adviser approval** of the three-way framing and the manuscript changes listed in Task 27. *Done when* the adviser's confirmation is recorded.
- **F6 — Pre-register criteria and evidence rules** with the adviser in `data/sites/validation_criteria.json` (§0.15): tolerances, arrival-order threshold, pair/tie rules, minimum evidence, seeds, initialization and measurement protocol. Commit before held-out outcome inspection; record the freeze and access ledger. The commit date alone is not proof that the data was untouched.

## Final acceptance

1. Full backend suite: `.venv/Scripts/python.exe -m pytest tests -q --basetemp "$TEMP/sf_final"`.
2. Frontend: `npx vitest run`, `npx tsc -b`, `npm run lint`, `npm run build`.
3. Field Observer suite.
4. `docs/reports/two-site-acceptance.json` meets §0.13 (all 24 runs), and the 5- and 2-junction quick digests are unchanged by Parts 1–4.
5. **Milestone 1:** a `site-validation-<site>-validation-*.json` report showing `PASS` for each site that enters Task 29, with sufficient observations, documented held-out independence and matching current physical-model/criteria hashes. Day-2-informed retries and stale reports cannot satisfy this gate.
6. **Milestone 2:** `docs/reports/two-site-results.json` made with `--final` on seeds 201–220, used once and recorded in the ledger.
7. Browser check on a scratch database:
   - choose Site A and Site B;
   - a no-signal run (no lights, free movement, no overlap);
   - a traditional grouped Webster plan;
   - a short RL trial;
   - Compare Runs pairing the three conditions;
   - dashboard changes measured against the no-signal run;
   - a backup and restore that keeps both sites.
8. The owner reviews the result before any merge to `main`.
