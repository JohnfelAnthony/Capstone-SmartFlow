# Mixed traffic: side-by-side vehicles and motorcycle filtering — design

Date: **2026-10-26** (Asia/Singapore). Status: **approved by the owner on 2026-10-26**, revised during planning (2026-10-26) and after an external review (2026-10-27). Nothing described here is implemented yet.

The owner chose **option 2, the "mixed-traffic engine"**: real road width, vehicles side by side, motorcycles filtering to the stop line, and varied drivers. The cheap visible parts come first. Calls marked **(my call)** were made by the assistant after the owner handed those decisions over; everything else follows the owner's choice or the existing project rules.

**Revised during implementation planning (2026-10-26):** with the first clearance values, a motorcycle could not fit beside a car on a 3.3 m lane and a tricycle never could, so filtering would almost never happen on the 2-junction network.

- The edge clearance is now **0.1 m**.
- Cars, buses and trucks keep to the centre-line side of their lane portion; tricycles keep to the kerb; motorcycles go anywhere.
- Spawn positions follow a fixed rule instead of a random draw.
- The junction method is settled in 6.4.

All of these are marked **(my call)**.

**Revised after an external review (2026-10-27, approved by the owner):** the review found that the first version could undo the junction-capacity repair, make vehicles jump or lock up inside the junction, check a different body shape from the one drawn, and accept results it had forced.

- **Exit space (6.5):** the sideways-band reservation is dropped. It allowed only one committed car per exit lane and brought back the old "tail must be clear" condition. The `native-5` end-to-end storage rule stays, counting each vehicle's own minimum gap.
- **Junction (6.4):** a vehicle enters its connector at its real sideways position. Vehicles that would merge or cross follow a fixed order, so two vehicles can never wait for each other inside the junction.
- **Sideways movement (6.3, 6.9):** cars, tricycles, buses and trucks move sideways only while moving forward. The drawn angle is capped, and the engine checks the same turned body that is drawn.
- **Acceptance (8):** overlap is checked at every tick, the determinism fingerprint covers sideways state and reservations, safety runs last 1800 s, and speed is timed in separate runs. Behaviour checks compare filtering on and off with everything else equal; wider comparisons are reported, not required.

## 1. Why

The team recorded two Tagum intersections on 10 September 2026 (`D:\intersection\IMG_2511.MOV`, `IMG_2516.MOV`, 1080p, about 16 minutes each). The footage shows what Tagum traffic looks like:

- most vehicles are **motorcycles and green passenger tricycles**;
- vehicles travel and queue **side by side**, not in neat single file;
- at a red light, **motorcycles squeeze through the gaps to the stop line** and leave first on green;
- vehicles sit **loosely across the road** and at small angles, not on one centre line.

The simulation today does none of this:

- each road direction is **one 3.3 m lane**, and every vehicle drives **exactly on its centre line** in single file;
- saved scenarios and the default configuration use **cars only** (`vehicle_mix: {"car": 1.0}`);
- motorcycles, when present, behave like short cars waiting in line;
- all drivers of a class behave identically.

This matters for more than looks. Queue lengths, how fast a queue empties on green, and delay are what the RL controller is trained on and judged by. In a single-file, cars-only model these numbers come from traffic that does not exist in Tagum, and they cannot later be matched against field counts from the Field Observer.

**What success looks like:**

1. Someone comparing the simulation with the two videos recognises the behaviour: mostly two- and three-wheelers, vehicles side by side, motorcycles crowding at the stop line and leaving first.
2. The numbers (queues, discharge, delay) come from that behaviour and can later be compared with Field Observer measurements.
3. Every existing safety guarantee still holds: no conflicting approaches inside a junction, no deadlock, maximum red, the pedestrian rule, and zero on the fault checks.

## 2. Goals

- **G1 Tagum vehicle mix.** A provisional Tagum mix is available and used by default for new scenarios and the training environment.
- **G2 Real road width.** Each road direction has a width taken from the map's lane count, which can be overridden with a field-checked width. Every vehicle has a sideways (lateral) position within that width.
- **G3 Side by side.** A vehicle follows only the vehicle ahead that overlaps it sideways. Cars travel two abreast where the road is wide enough. Motorcycles and tricycles can travel beside a car even on a single-lane road when there is room.
- **G4 Gap seeking and filtering.** A blocked vehicle can move sideways into a gap that lets it advance. Narrow vehicles, mainly motorcycles, thereby work their way past stopped queues to the stop line. Vehicles stop at the line packed side by side.
- **G5 Front row leaves first.** On green, the vehicles at the line leave together within the junction rules, so motorcycles gathered at the front clear first.
- **G6 Driver variety.** Each vehicle gets its own seeded variation of desired speed, following time, minimum gap and acceleration, around class-specific base values.
- **G7 Drawing matches the engine.** The 2D and 3D views draw roads at their real width (with lane lines) and each vehicle at its real sideways position. A vehicle moving sideways is drawn turned slightly in that direction.
- **G8 Safe to ship.** Deterministic, tested, documented, released as engine version `native-6`.

## 3. Non-goals for this round

- **Fully lane-free movement (option 3).** No overtaking through the opposing direction, no wrong-way riding, and no free-form crowding inside the junction. Movements through the junction still follow their paths (now with a sideways offset).
- Red-light running, creeping past the stop line into the crosswalk, U-turns, jaywalking, or pedestrians walking among vehicles.
- **Tricycles stopping at the kerb** to pick up or drop off passengers, parked vehicles, and roadside activity. These are clearly visible in IMG_2511 and are a strong candidate for the next round, but they are out of scope here **(my call)**.
- Closing only some lanes of a road. Closures and speed restrictions still apply to a whole road direction.
- Pedestrian crossing length. It stays a scenario setting and is not derived from the new road widths.
- New vehicle classes such as jeepney or bicycle. Mapping those is a separate decision.
- **Calibration.** This round builds the behaviour with provisional values in one parameter table. Fitting them to Tagum uses Field Observer data after the study sites are confirmed (Section 9).
- Changing the RL scope: still one controlled junction and the same five service actions.

## 4. Anti-goals — failure even if it "works"

- Vehicles overlapping, jittering sideways every step, jumping, or leaving the road surface.
- Losing determinism. The same seed must give the same run, because recordings, baselines and training depend on it.
- Breaking a junction safety guarantee: two conflicting approaches inside a junction together, the P0-1 deadlock coming back, maximum red or the pedestrian rule not holding, or non-zero fault checks.
- Making the simulation much slower. Training already runs at about 5–8 decisions per second (Section 8 sets the budget).
- Presenting the provisional mix or parameters as measured Tagum facts.
- Drawing something the engine is not doing, such as showing vehicles side by side while the engine still treats them as single file. This is why option 2 was chosen over a visual-only change.

## 5. Constraints and current engine facts

**Project rules that apply:**

- The engine is `simulation/traffic_engine.py`, pure Python, run in one process. No SUMO/TraCI.
- `engine_config` is the scenario contract. Old saved scenarios must still load and run. A road with no width information behaves as today: one lane per direction, 3.3 m wide.
- Five vehicle classes (car, motorcycle, tricycle, bus, truck) plus pedestrians.
- RL controls one junction. Trained models are tied to the engine version and the network fingerprint.
- The hosted and local versions run the same engine code.

**How the engine works today (what the builder will change):**

| Area | Today | Where |
|---|---|---|
| Lanes | One `Lane` per road direction, centre line offset **1.65 m** from the road centre (two-way) or on it (one-way). Width is not modelled in the engine. | `simulation/road_network.py`, `RoadNetwork.__init__`, `offset()` |
| Map data | Every road keeps its OSM tags. All roads have a `lanes` tag: in the 5-junction network, 10 roads say 2 (one per direction) and 2 roads say 4 (two per direction); in the provisional 2-junction network, all 6 say 2. No `width` tags. | `data/networks/*.json`, `osm_tags.lanes` |
| Vehicle sizes | car 4.5 × 1.8 m, motorcycle 2.0 × 0.8, tricycle 3.0 × 1.4, bus 10.0 × 2.5, truck 8.0 × 2.5, with class speed factors | `simulation/scenario_config.py`, `VEHICLE_TYPES` |
| Movement | Intelligent Driver Model (IDM) per vehicle, 0.1 s steps; shared constants `MIN_GAP` 2.0 m, `TIME_HEADWAY` 1.2 s, `COMFORTABLE_DECELERATION` 2.0 m/s². The leader is the nearest vehicle ahead on the same lane. | `TrafficEngine._move_vehicle`, `_advance` |
| Junctions | Only vehicles from the approach that has green may be inside (approach-scoped occupancy). A vehicle commits at its last comfortable stopping point. Exit storage rule: everything on or committed to the exit lane plus the entrant must fit end to end. Vehicles follow on connectors only behind the same movement. | `_move_vehicle`, `_exit_has_space`, `_connector_gap`, `_reserve` |
| Spawning | A vehicle enters at the lane start if the rear of the last vehicle is clear. | `add_vehicle`, `_spawn_demand` |
| Speed index | Each tick indexes vehicles by lane, by the lane they are turning off and by next lane. A test proves it equals a full scan. | `_build_tick_index`, `_candidates`, `tests/test_engine_search_index.py` |
| Randomness | Arrivals and their classes come from `build_schedule`'s own `random.Random(seed)`. The engine has separate `self.random` and `self.pedestrian_random` streams. | `simulation/demand.py`, `TrafficEngine._reset_state` |
| Output | Each vehicle record has `x`, `y`, `angle`, `width`, `length`, `visual_type` on the lane centre line. | `vehicle_records` |
| Drawing | The 2D canvas and the 3D scene draw roads using each lane's `width` from the network visual payload (currently a fixed 3.3). | `RoadNetwork.visual`, `src/components/simulation-canvas-2d.tsx`, `src/simulation/SimulationScene3D.tsx` |
| Safety checks | Fault checks for stuck vehicles and gridlock; P0-1 class-pair property test; capacity tests. | `tests/test_junction_deadlock.py`, `tests/test_junction_capacity.py` |

## 6. Design

### 6.1 Road width (G2)

- **One `Lane` object per road direction stays.** It gains `lanes_per_direction` and `width_m`. Lane IDs, approaches, closures, speed restrictions, metrics and the RL approach mapping keep working unchanged **(my call)**.
- `lanes_per_direction` = OSM `lanes` ÷ 2, rounded down, for two-way roads; the OSM `lanes` value for one-way roads; at least 1; 1 when the tag is missing.
- `width_m` = `lanes_per_direction` × 3.3 m by default. A road in the network file may set an optional field-checked width per direction (for example `width_per_direction_m`) that overrides this, including any shoulder that motorcycles use. Default shoulder: none **(my call)**.
- The lane's centre line (the path that position is measured along) is offset `width_m ÷ 2` from the road centre for two-way roads, instead of the fixed 1.65 m. For one-lane roads this is unchanged.
- The network visual payload reports the real width and lane count, so the 2D and 3D views draw wider roads with lane lines automatically.
- Lanes currently stop **9 m** short of a junction node. On wide crossing roads that may put the stop line inside the other road's pavement. The builder should make this clearance grow with the crossing roads' widths where needed, keeping 9 m as the minimum.
- Result for today's networks: the provisional 2-junction network stays one lane (3.3 m) per direction everywhere, so cars stay single file there. A motorcycle (0.8 m) fits beside a car (1.8 m) because cars keep to the centre-line side: 1.8 + 0.3 + 0.8 + 2 × 0.1 = 3.1 m. A tricycle (1.4 m) does not fit beside a car on 3.3 m; a motorcycle does fit beside a tricycle. The two 4-lane roads in the 5-junction network become 6.6 m per direction, so two cars fit side by side.

### 6.2 Sideways position and following (G3)

- Each vehicle has a **lateral position** (its centre, in metres across its lane's width) and a **lateral speed**.
- **Leader rule:** the leader is the nearest vehicle ahead in the same lane whose sideways band overlaps the vehicle's own band, widened by a sideways clearance. Vehicles that don't overlap are ignored for following, which is what lets them stand side by side.
- **Clearances (provisional, my call):** 0.3 m between vehicles side by side, and 0.1 m from the road edge. Both live in the parameter table (Section 6.7).
- **Keeping positions (my call):** cars, buses and trucks keep to the centre-line side of the lane portion they use, which leaves the kerb side for two-wheelers. Tricycles keep to the kerb. Motorcycles have no keeping position.
- The stop-line rule, the commit rule and the IDM itself are unchanged; only which vehicle counts as "ahead" changes.
- Vehicles may never overlap: two footprints (length × width rectangles at their positions, turned as drawn, see 6.9) must never intersect on a lane or inside the junction.

### 6.3 Gap seeking and motorcycle filtering (G4, G5)

- **Periodic decision.** Every vehicle reconsiders its sideways position at a fixed interval (provisional 0.5 s, staggered by vehicle so the work is spread across ticks). The schedule depends only on the tick count, so runs stay deterministic.
- **Choice.** It compares candidate sideways positions on a fine grid across its lane (provisional 0.25 m) and picks the one with the most room to advance, minus a cost for how far it has to move.
  - Cars, buses, trucks and tricycles are pulled towards their keeping position (6.2), which gives weak lane discipline.
  - Motorcycles have no keeping position and readily use gaps and edges.
- **Safety.** A sideways move is only chosen if the target band is clear beside the vehicle (no vehicle within its length plus clearance) and stays inside the road edges. A vehicle near the start of a lane does not move into the path of a vehicle arriving from the junction.
- **Each step is checked again (revised 2026-10-27).** Turning swings the tail slightly toward the side being left, so during a move the turned body (6.9) may use the clearances, but it must never touch another vehicle or leave the road. A step that fails is shortened; if even a short step fails, the move stops.
- **Lateral speed limits (provisional):** motorcycle 1.0 m/s, tricycle 0.6, car 0.5, bus and truck 0.3.
- **Sideways only while moving forward (revised 2026-10-27, my call).** Cars, tricycles, buses and trucks move sideways at most at forward speed × tan 10°, so a stopped one cannot slide sideways. Motorcycles may also shuffle sideways at up to 0.3 m/s when slow or stopped, as riders do with their feet.
- **No jitter.** A move happens only when the gain passes a threshold, and a vehicle that just moved waits before deciding again.
- **Turn side (provisional, optional).** In the last stretch before the junction, vehicles prefer the side of the road matching their turn: left turners to the left, right turners to the right (traffic drives on the right). This reduces paths crossing inside the junction.
- **Stop line.** Vehicles stop with their front at the line wherever they are sideways. Because narrow vehicles keep finding gaps, motorcycles end up at the line beside and ahead of cars. On green, everything at the line is free to go, subject to the existing junction rules.

### 6.4 Through the junction (G5)

- **Approach-scoped occupancy is unchanged**: only vehicles from the approach that has green are inside together, so conflicting streams still never meet.
- A vehicle enters its connector at its **real sideways position** and blends smoothly to its exit position: its own position, limited to the exit lane's width. There is no jump at the stop line, even from a wide approach into a narrow exit (revised 2026-10-27).
- **Following inside the junction** must account for all vehicles from the same approach that could overlap, not only those on the same movement. Vehicles of one approach doing different movements must not intersect inside the junction.
- **Fixed order (revised 2026-10-27, my call).** Two vehicles of one approach must never wait for each other:
  - **Merging:** two vehicles bound for the same exit lane whose exit positions would come within the sideways clearance go single file. The later one follows the earlier along the path, waiting at the line if needed.
  - **Crossing:** a vehicle whose path crosses that of a vehicle beside it (for example a left turner on the kerb side of a through vehicle) does not enter the junction while that vehicle is beside it. Once that vehicle is fully ahead, the normal following rules apply. The turn-side preference (6.3) makes this rare.
  - **Level at the line:** when two such vehicles both stopped at the line, the one that stopped first goes first, then the lower vehicle ID (the order the all-way stop already uses).
- **Method (my call, settled during planning):**
  - Merging vehicles keep the existing along-the-path following.
  - Other vehicles in the junction and at the start of the exit lane are judged in the moving vehicle's own frame of reference.
  - A final footprint check shortens any step that would make two vehicles overlap.

### 6.5 Exit space and the deadlock guarantee

The P0-1 guarantee must survive: **every vehicle that commits to a junction must be able to leave it completely.**

- **Rule (revised 2026-10-27):** keep the `native-5` storage rule. Everything on or committed to the exit lane, plus the entrant, must fit end to end, each counted as its length plus its own minimum gap plus the existing margin.
- **Why it still holds side by side:** a vehicle stops only behind a leader or a stop line. Every vehicle in the chain of leaders in front of an entrant is already counted, whatever its sideways position, so that chain is never longer than the counted total, which leaves room for the entrant.
- **Why not count per sideways band:** on a wide road a motorcycle in the middle overlaps both sides, so a queue can zigzag across bands, and a per-band total undercounts it.
- **Rejected first version:** reserving a sideways band per committed vehicle allowed only one committed car per exit lane and brought back the old "tail must be clear" condition. It would have undone the junction-capacity repair (about 2.4 s per car).
- **Accepted limitation:** an exit road backed up with vehicles side by side counts as full sooner than it really is, so during spillback the upstream junction lets fewer vehicles in than real traffic would. A finer rule can follow calibration if field data show that spillback matters.
- **Proof:** extend the P0-1 property test to sideways positions (class pairs × sideways positions × road widths) and show that it fails for an area-only rule, which can strand a vehicle. Show that several following cars can be committed at once.

### 6.6 Spawning

- At a boundary, a new vehicle may enter in any sideways band with enough free space at the lane start. Several vehicles can enter side by side.
- **Starting position (my call, fixed rule rather than a random draw):**
  - Cars, buses and trucks take their keeping position in the lane portion with the most free room at the start.
  - Tricycles and motorcycles take the free position nearest the kerb.
- The spawn shortcut from the speed-up work (the per-lane rearmost position) becomes per band or per lane width; it must stay exactly equivalent to a full check.

### 6.7 Driver variety and class parameters (G6)

- Each vehicle draws its own multipliers when created, from a **new, separate seeded random stream**. This keeps the arrival schedule (times and classes) identical to `native-5` for the same seed, so comparisons isolate the behaviour change **(my call)**.
- **Provisional class base values (my call; all to be calibrated, in one table):**

| Class | Following time (s) | Minimum gap (m) | Max acceleration (m/s²) | Lateral speed (m/s) |
|---|---|---|---|---|
| car | 1.2 | 2.0 | 1.5 | 0.5 |
| motorcycle | 0.8 | 1.0 | 2.0 | 1.0 |
| tricycle | 1.2 | 1.5 | 1.0 | 0.6 |
| bus | 1.5 | 2.5 | 0.8 | 0.3 |
| truck | 1.5 | 2.5 | 0.8 | 0.3 |

- **Per-vehicle variation (provisional):** desired speed × N(1, 0.08) clipped to [0.8, 1.2]; following time × N(1, 0.15) clipped to [0.7, 1.4]. Class speed factors stay.
- The parameter table includes a **variation scale**, where 0 turns per-vehicle variation off. Tests use it to compare like with like, and calibration can use it to find the right spread.
- The values replace the shared `MIN_GAP`, `TIME_HEADWAY` and acceleration wherever a specific vehicle is involved. The comfortable deceleration used in the commit rule becomes per class if needed.

### 6.8 Vehicle mix (G1)

- Add a **"Tagum (provisional)" mix**: motorcycle 0.55, tricycle 0.25, car 0.15, truck 0.03, bus 0.02. This is an assumption drawn from looking at the two videos, not a count. It is replaced by Field Observer class shares when available **(my call)**.
- Make it the default for **new** scenarios and for the RL training environment's default scenario. Cars-only stays available in the scenario editor **(my call)**.
- **Saved scenarios are not changed automatically**: each stores its own mix. The scenario editor offers a one-click "Tagum mix (provisional)" preset. The shipped demo scenarios under `data/scenarios/` can be switched to it **(my call)**.
- Tests that assume cars only must set the mix explicitly.

### 6.9 Drawing (G7)

- `x`, `y` are computed from the lane centre line plus the lateral offset. `angle` combines forward and sideways speed, so a vehicle moving sideways is drawn turned slightly that way, by at most **10°** (provisional, my call).
- **One body shape (revised 2026-10-27):** the engine checks the same turned body that is drawn, using the road-aligned box around it for following, spacing, spawning and the road edges. The footprint check in the tests uses the drawn rectangle itself, so it cannot pass a drawing the engine did not check. On connectors, bodies follow the path direction.
- Because `x`, `y` and `angle` already carry the result, the renderers, replay format and interpolation need no new fields. Adding the raw lateral position to the vehicle record is optional, for tests and debugging.
- Roads draw at real width with lane lines from `lanes_per_direction`.
- **No purely cosmetic random wobble.** Every drawn position comes from the engine **(my call)**.

### 6.10 Metrics and RL

- **Existing metric definitions stay as they are** (counts of stopped vehicles per incoming lane, and so on), so results remain comparable in kind **(my call)**.
- **Add one per-approach measure:** *queue reach*, the distance from the stop line to the rearmost stopped vehicle, in metres. Side-by-side queues change this directly, and the queue tail is visible in field video **(my call)**. Add it to the metric catalogue with a definition.
- **RL normalisation:** check the observation and reward scales (`MAX_QUEUE_COUNT` and `MAX_ACTIVE_VEHICLES` = 30 per approach in `simulation/rl_state.py`) against medium and high Tagum-mix runs. If the 95th-percentile per-approach count exceeds them, raise them, bump the observation version (`native-local-22-v3`), and bump the reward version only if the reward formula's scaling changes. No extra cost, because models must be retrained for `native-6` anyway.

### 6.11 Versioning

- All behaviour changes ship together as **`native-6`**, as the earlier fixes did for `native-5`. Older recordings, baselines and models become history.
- After release: re-record the fixed-time baselines, and keep the full retrain on hold until the study sites are confirmed (existing owner decision).

## 7. Order of work

Each stage ends with tests passing and a short browser check.

1. **Tagum mix (days).** The provisional preset, the new defaults, the editor preset button and the demo scenarios. Check that motorcycles and tricycles are easy to tell apart in 2D and 3D. No engine behaviour change and no version bump. This is the first visible difference.
2. **Width and side by side.** Lane width and offset, the lateral position, the overlap leader rule, packing at the stop line, side-by-side spawning, and drawing at the real position and width. Vehicles keep their entry sideways position (no gap seeking yet).
3. **Gap seeking and filtering.** The periodic sideways decision, the safety check with the turned body, speed limits and anti-jitter, the turn-side preference, junction offsets, the fixed order and following, and the P0-1 property test extended to sideways positions (the exit-space rule itself is unchanged).
4. **Driver variety.** The class table and per-vehicle variation on the separate random stream.
5. **Release.** Metric additions, the RL normalisation check, the performance check, the `native-6` bump, fixtures and recorded baselines, and documentation: a new architecture decision, a progress entry, and manuscript notes describing the mixed-traffic model and its limits.
6. **Calibration (after field data).** Fit the parameter table to Field Observer measurements (Section 9).

## 8. Acceptance checks

**Safety and invariants (automated):**

- No footprint overlap between any two vehicles on lanes or inside the junction, **checked at every tick**. Check across both networks; low, medium and high demand; Tagum mix and cars only; closures; all-way stop; several seeds.
- No drawn body outside its road's width.
- Fault checks (stuck vehicles, gridlock) and the vehicle conservation error stay at 0 in **1800 s** runs on both networks (every case of the acceptance report).
- The P0-1 property test, extended to sideways positions, passes, and fails for an area-only exit rule.
- The speed-index equivalence test still passes.
- **Determinism:** the same seed gives an identical state fingerprint, including sideways positions, targets and speeds, junction entry and exit positions, and reservations. The arrival schedule is identical to `native-5` for the same seed.
- **Backward check:** a cars-only scenario on one-lane-per-direction roads stays single file. With variation scale 0, its saturated discharge headway stays within ±10% of `native-5` (about 2.4 s per car), and several following cars are committed at once. With variation on, report the value without a bound.

**Behaviour (synthetic, provisional values):**

- **Mechanism checks (pass/fail, small controlled scenes):**
  - On a two-lanes-per-direction road, a cars-only queue holds about two cars abreast, and its storage roughly doubles.
  - Filtering: with the same seeds, Tagum mix and arrivals at a red light, the front-row motorcycle share is higher with sideways decisions on than with them off.
  - No vehicle reverses its sideways direction more than twice in any 10 s, lateral speed limits are respected, and stopped cars, tricycles, buses and trucks never move sideways.
- **Reported, not required (revised 2026-10-27):** front-row composition and vehicles leaving in the first 10 s of green on the full networks, Tagum mix against cars only and filtering on against off. These depend on demand, turns and downstream queues, so a case with no improvement is a result to report, not a bug to tune away.
- **Provisional values are never tuned to make a check pass.** A failing mechanism check is investigated as a possible bug; if the mechanism is correct, the result is reported as it is.

**Performance:**

- With the same scenario settings and a cars-only mix, a medium-demand 900 s run on the 5-junction network takes no more than **1.5×** today's time (about 11 s). This isolates the cost of the new engine logic. Report the Tagum-mix time alongside it.
- The RL environment, at the same demand and with the Tagum mix, keeps at least **70%** of today's decisions per second.
- Speed is timed in separate runs with the overlap and fingerprint checks off, so the checks do not distort it.
- Use the fingerprint and benchmark scripts from the speed-up work as the harness.

**Visual (owner):**

- Screenshots of the simulation next to frames from IMG_2511 and IMG_2516, reviewed by the owner.

## 9. Calibration hooks (stage 6, needs field data)

| Parameter | Field Observer measurement |
|---|---|
| Vehicle mix | Class counts at arrival lines, with tricycles corrected by review |
| Discharge headway per class | Time between successive stop-line (discharge) events during green |
| Front-row composition | Manual queue snapshots at green onset |
| Queue reach | Queue samples (tail position) |
| Desired speeds | Travel-time samples on a visible segment |
| Sideways clearance and filtering | Front-row composition plus reviewer notes |

Calibration uses separate calibration and held-out periods, as the recording protocol requires.

## 10. Effects elsewhere

- **Recordings and baselines** from `native-5` become history; re-record after release.
- **RL:** retrain needed (already planned after the sites are confirmed). Doing this change **before** that retrain avoids training twice.
- **Metric catalogue:** the new queue-reach entry, plus `engine_version` `native-6`.
- **Hosted version:** same engine, no extra work.
- **Field Observer:** unchanged. It becomes the source for calibration.
- **Manuscript:** describe the mixed-traffic (sub-lane) model, the provisional parameters and the limits. Cite IDM plus verified sources on sub-lane and strip-based mixed-traffic models; the builder must verify each citation.

## 11. Left to the builder

- The exact sideways decision formula, weights, grid size and decision interval, within the stated rules.
- Data structures for lateral position and bands, and how the tick index is extended.
- The method for junction following with offsets, as long as the fixed order (6.4), the stated invariants and the tests hold. The exit-space rule is fixed (6.5).
- Performance tactics, test scaffolding and fixture updates.
- Updating existing tests whose single-file assumptions intentionally change, especially the capacity and connector-gap tests. Their safety intent must be kept.

## 12. Calls made by the assistant (owner to check)

1. A continuous sideways position with an overlap rule (a sub-lane model), rather than separate lanes plus a special motorcycle lane.
2. One `Lane` object per road direction stays; width comes from the OSM lane count, with an optional field-checked override; no shoulder by default.
3. Provisional clearances (0.3 m between vehicles, 0.1 m to the edge), keeping positions (cars, buses and trucks on the centre-line side, tricycles at the kerb), lateral speeds, and the class parameter table.
4. Driver variety on a separate random stream, so arrivals match `native-5` for the same seed.
5. Provisional Tagum mix 55/25/15/3/2 (motorcycle/tricycle/car/truck/bus) as the default for new scenarios and training. Saved scenarios unchanged; a preset button instead.
6. Tricycle kerbside stops, red-light running and other "messiness" are left for a later round.
7. Existing metric definitions kept; one new queue-reach metric added.
8. No cosmetic random wobble in the drawing.
9. One version bump, `native-6`, at the end; stage 1 (the mix) ships without one.
10. After the 2026-10-27 review: the `native-5` exit storage rule kept with per-vehicle gaps, accepting that fewer vehicles enter during spillback; a fixed order for merging and crossing in the junction; sideways movement only while moving forward, except a 0.3 m/s motorcycle shuffle; the drawn angle capped at 10° and checked as drawn.

**Effort:** about 1–2 weeks of focused work for stages 1–5. Stage 6 depends on field data.
