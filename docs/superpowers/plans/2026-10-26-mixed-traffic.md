# Mixed Traffic Engine Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make SmartFlow's native engine simulate Tagum mixed traffic — real road widths, vehicles side by side, motorcycles filtering to the stop line, varied drivers and a Tagum vehicle mix — released as engine `native-6`.

**Architecture:**
- **Lanes and vehicles:** each road direction keeps one `Lane` object, which now carries a width and a lane count. Each vehicle gains a sideways position.
- **One overlap rule everywhere:** following, spawning, junction passage and sideways gap seeking all use the same sideways-overlap rule, on the same body that is drawn. Exit storage keeps the `native-5` end-to-end rule.
- **New modules:** parameters and pure geometry live in two small modules, `simulation/mixed_traffic.py` and `simulation/footprints.py`.
- **Unchanged structure:** the engine keeps its deterministic tick loop and per-tick search index.
- **Measurement:** a report tool records safety, behaviour and speed on `native-5` first, then checks `native-6` against it.

**Tech Stack:** Python 3.13 (standard library only in the engine), pytest/unittest, React + TypeScript + Vite, Vitest, Three.js.

**Spec:** `docs/superpowers/specs/2026-10-26-mixed-traffic-design.md` (approved 2026-10-26; revised during planning and after the 2026-10-27 review — see its header).

## Global Constraints

- **Commands:**
  - Python: `.venv/Scripts/python.exe`.
  - Backend tests: `.venv/Scripts/python.exe -m pytest <tests> -q -p no:cacheprovider --basetemp "$PYTEST_TMP"`, with `PYTEST_TMP` a scratch folder outside the repository.
  - Frontend: `npx vitest run`, `npx tsc -b`, `npx eslint <changed files>`.
- **No new Python or npm dependencies.**
- **Branch and commits:** work on branch `feat/mixed-traffic` from `main`. One commit per task; each message ends with `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`.
- **Units:** metres and seconds; the engine step is 0.1 s.
- **Sign convention:** `lateral` is a vehicle centre's sideways offset from its lane's centre line, in metres. It is **positive toward the right-hand kerb**, the same sign as `road_network.offset()`. The right normal of heading `h` is `(sin h, −cos h)`.
- **Determinism:** the same seed gives the same run. New randomness comes only from `self.driver_random = random.Random(seed ^ 0x445256)`. New features never draw from `self.random`, `self.pedestrian_random` or `build_schedule`'s generator.
- **Engine version:** `ENGINE_VERSION` stays `"native-5"` until Task 12, which sets `"native-6"`. The `engine_config` scenario contract gets **no new settings**.
- **Provisional values (exact):**
  - Lanes and clearances: `LANE_WIDTH_M` 3.3; `SIDE_CLEARANCE_M` 0.3; `EDGE_CLEARANCE_M` 0.1; lateral grid 0.25 m.
  - Sideways decisions: every 5 ticks; move gain threshold 2.0 m; move cost 1.0 per m; keeping weight 2.0 per m; turn-side weight 2.0 per m within 30 m of the stop line; cooldown 2.0 s; room horizon 50 m.
  - Body angle: at most 10°. Cars, tricycles, buses and trucks move sideways at most `speed · tan 10°`; motorcycles also up to 0.3 m/s when slow or stopped. Both stay within the class lateral speed.
  - Class driving table (time headway s, minimum gap m, maximum acceleration m/s², lateral speed m/s):

    | Class | Time headway | Minimum gap | Max acceleration | Lateral speed |
    |---|---|---|---|---|
    | car | 1.2 | 2.0 | 1.5 | 0.5 |
    | motorcycle | 0.8 | 1.0 | 2.0 | 1.0 |
    | tricycle | 1.2 | 1.5 | 1.0 | 0.6 |
    | bus | 1.5 | 2.5 | 0.8 | 0.3 |
    | truck | 1.5 | 2.5 | 0.8 | 0.3 |

  - Driver variation: speed multiplier N(1, 0.08) clipped to [0.8, 1.2]; headway multiplier N(1, 0.15) clipped to [0.7, 1.4].
  - Tagum mix: motorcycle 0.55, tricycle 0.25, car 0.15, truck 0.03, bus 0.02.
- **Safety invariants every task keeps green:**
  - approach-scoped junction occupancy;
  - the P0-1 release guarantee;
  - maximum red and the pedestrian rule;
  - `stuck_junction_vehicles`, `gridlock_seconds` and `vehicle_conservation_error` equal 0 in regression runs;
  - `tests/test_engine_search_index.py` equivalence.
- **Data:** saved scenarios are never rewritten automatically. `data/smartflow.db` is written only in Task 12, after the owner approves.
- **Performance budget (checked in Task 11, timed with the overlap and fingerprint checks off):**
  - a cars-only medium 900 s run on the 5-junction network takes ≤ 1.5× the Task 1 baseline;
  - RL environment decisions per second with the Tagum mix stay ≥ 70% of the Task 1 baseline.

## Review Focus

1. **Saved scenario with an older or hand-entered mix** (for example weights `{"car": 65, "motorcycle": 15, "tricycle": 10, "bus": 5, "truck": 5}`) opened in the scenario editor. It must show "Custom (saved)" and keep its mix until the user picks a preset. Covered in Task 2 (`matchingMixPreset` test and an editor check).
2. **OSM `lanes` tags that aren't a plain integer** (`"2;3"`, `""`, `"abc"`, `"1.5"`, `"0"`, `" 4 "`) and an out-of-range `width_per_direction_m`. They must fall back to one lane per direction, or be rejected with a message naming the field. They must never crash or produce a zero width. Covered in Task 3.
3. **An all-way-stop junction whose front row holds two vehicles side by side.** It must still admit one vehicle at a time, with no overlap. Covered in Task 7.
4. **A lane closure that starts while vehicles are moving sideways or filtering.** No overlap, and accounting stays balanced. Covered in Task 9.
5. **Very high demand at the vehicle cap.** No overlap and no stuck vehicles while saturated. Covered in Task 9.

---

### Task 1: Footprint checks, report tool and the `native-5` baseline

**Files:**
- Create: `simulation/footprints.py`
- Create: `tools/mixed_traffic_report.py`
- Create: `tests/test_footprints.py`, `tests/test_mixed_traffic_report.py`
- Create (generated): `docs/reports/mixed-traffic-baseline-native-5.json`

**Interfaces:**
- Produces:
  - `rectangle(x: float, y: float, heading: float, length: float, width: float) -> list[tuple[float, float]]` — heading in radians (x east, y north); four corners.
  - `rectangles_overlap(a: list[tuple[float, float]], b: list[tuple[float, float]], tolerance: float = 1e-6) -> bool` — separating-axis test. Touching, or separated within the tolerance, means no overlap.
  - `record_rectangle(record: dict) -> list[tuple[float, float]]` — from a `vehicle_records()` entry, where `angle == (90 - degrees(heading)) % 360`.
  - `overlapping_pairs(records: list[dict]) -> list[tuple[str, str]]` — sorted pairs of IDs. It sweeps the records sorted by their leftmost x and tests only pairs whose x-ranges meet, so it is fast enough to run at every tick.
  - `longitudinal_digest(engine, seconds: float, sample_every_ticks: int = 50) -> str` — steps a started engine until `simulation_time >= seconds` or it stops running, sampling every `sample_every_ticks` ticks and once more at the end. It hashes `(id, tuple(route), repr(position), repr(speed), repr(wait), connector is not None, repr(connector_position), reserved_junction)` for every vehicle at each sample. Lateral state is deliberately excluded: this digest compares against `native-5` behaviour (Task 5).
  - `state_digest(engine, seconds: float, sample_every_ticks: int = 50) -> str` — the same sampling, hashing the longitudinal tuple plus `repr(getattr(vehicle, name, None))` for `lateral`, `lateral_speed`, `lateral_target`, `lateral_cooldown_until`, `yaw`, `connector_entry_lateral` and `connector_exit_lateral`, and per sample `sorted((node, sorted(ids)) for node, ids in engine.reservations.items())` and `sorted(engine.reservation_approach.items())`. `getattr` lets it run on `native-5`. This is the same-seed determinism fingerprint.
  - CLI: `tools/mixed_traffic_report.py --out PATH [--seconds 1800] [--seeds 101,102] [--quick]`. It writes `{"engine_version": str, "cases": {"<case>@<seed>": {...}}, "benchmarks": {...}}`, running every case once per seed.

- [ ] **Step 0: Create the branch and commit the design and this plan**

```bash
git switch -c feat/mixed-traffic
git add docs/superpowers/specs/2026-10-26-mixed-traffic-design.md docs/superpowers/plans/2026-10-26-mixed-traffic.md
git commit -m "Add the mixed-traffic design and implementation plan"
```

- [ ] **Step 1: Write the failing tests** in `tests/test_footprints.py`

```python
import itertools, math, random
from simulation.footprints import longitudinal_digest, overlapping_pairs, record_rectangle, rectangle, rectangles_overlap, state_digest

def test_side_by_side_rectangles_with_a_gap_do_not_overlap():
    assert not rectangles_overlap(rectangle(0, 0, 0.0, 4.5, 1.8), rectangle(0, -1.6, 0.0, 2.0, 0.8))

def test_rectangles_overlapping_by_ten_centimetres_are_detected():
    assert rectangles_overlap(rectangle(0, 0, 0.0, 4.5, 1.8), rectangle(4.4, 0, 0.0, 4.5, 1.8))

def test_rotated_rectangles_use_true_geometry():
    assert not rectangles_overlap(rectangle(0, 0, 0.0, 4.5, 1.8), rectangle(0, 3.35, math.pi / 2, 4.5, 1.8))

def test_overlapping_pairs_reads_engine_records():
    records = [{"id": "a", "x": 0, "y": 0, "angle": 90, "length": 4.5, "width": 1.8},
               {"id": "b", "x": 1, "y": 0, "angle": 90, "length": 4.5, "width": 1.8},
               {"id": "c", "x": 50, "y": 0, "angle": 90, "length": 4.5, "width": 1.8}]
    assert overlapping_pairs(records) == [("a", "b")]

def test_overlapping_pairs_matches_a_full_pairwise_check():
    # 200 records from random.Random(3): x, y in [0, 60), angle in [0, 360), length in [2, 10], width in [0.8, 2.5], ids "v0".."v199"
    assert overlapping_pairs(records) == sorted(tuple(sorted((a["id"], b["id"]))) for a, b in itertools.combinations(records, 2)
                                               if rectangles_overlap(record_rectangle(a), record_rectangle(b)))

def test_only_the_state_digest_sees_sideways_state():
    # two engines, same seed and settings, stepped 100 ticks; setattr(one vehicle of b, "lateral", 0.5); t = their current time, so only the final sample is taken
    assert state_digest(a, t) != state_digest(b, t) and longitudinal_digest(a, t) == longitudinal_digest(b, t)
```

- [ ] **Step 2: Run** `.venv/Scripts/python.exe -m pytest tests/test_footprints.py -q -p no:cacheprovider --basetemp "$PYTEST_TMP"`. Expected: FAIL, `ModuleNotFoundError: simulation.footprints`.

- [ ] **Step 3: Implement `simulation/footprints.py`** with the six functions above, using only `math` and `hashlib`.

- [ ] **Step 4: Run Step 2's command.** Expected: 6 passed.

- [ ] **Step 5: Implement `tools/mixed_traffic_report.py`.**
  - `run_case(network_name, density, mix, seconds, seed, *, events=None, all_way_stop=False, sideways_decisions=True) -> dict` runs one case. With `sideways_decisions=False` it uses a subclass of `TrafficEngine` whose `_decide_lateral` does nothing (on `native-5`, and before Task 9, that changes nothing).
    - Networks: `"5j"` is `data/networks/tagum_network.json`; `"2j"` is `data/networks/tagum_network_2j.json`.
    - Every case uses pedestrian density `"medium"`.
    - Mixes: `cars` = `{"car": 1.0}`; `tagum` = the Tagum mix from Global Constraints (defined in the tool for now).
  - Each case records:
    - `runtime_s` (with the checks running; informational only);
    - `max_overlapping_pairs` (every tick);
    - `max_stuck_junction_vehicles`, `max_gridlock_seconds`, `final_vehicle_conservation_error`, `completed`;
    - `queue_count_p95` and `active_count_p95`: 95th percentiles of per-approach stopped and present vehicles on the controlled junction's incoming lanes, sampled every 10 ticks;
    - `front_row_motorcycle_share`: motorcycles ÷ all stopped vehicles whose front is within 1.0 m of the stop line, summed over samples;
    - `queue_motorcycle_share`: the same over all stopped vehicles on those lanes;
    - both shares are `null` when fewer than 20 front-row vehicles were sampled;
    - `mean_discharge_first_10s`: the mean `lane_exits` increase on the green approach in the 100 ticks after each green onset.
  - Cases, as name: network, density, mix, extras:

    | Case | Network | Density | Mix | Extras |
    |---|---|---|---|---|
    | `5j-medium-cars` | 5j | medium | cars | |
    | `5j-low-tagum` | 5j | low | tagum | |
    | `5j-medium-tagum` | 5j | medium | tagum | |
    | `5j-high-tagum` | 5j | high | tagum | |
    | `2j-medium-tagum` | 2j | medium | tagum | |
    | `2j-medium-tagum-nofilter` | 2j | medium | tagum | `sideways_decisions=False` |
    | `2j-high-tagum` | 2j | high | tagum | |
    | `2j-veryhigh-tagum` | 2j | very high | tagum | |
    | `5j-closure-tagum` | 5j | medium | tagum | events close `network.incoming[controlled][0]` at 200 s and reopen it at 500 s |
    | `5j-allwaystop-tagum` | 5j | medium | tagum | every junction set to `{"mode": "all_way_stop"}` |

  - `benchmarks`, each run separately with no overlap or fingerprint checks:
    - `cars_only_5j_medium_900s_runtime_s`: a plain 900 s run, seed 101;
    - `rl_env_decisions_per_second`: one `SmartFlowRLEnv` episode with default warmup and episode length, scenario `{"traffic_density": "medium", "pedestrian_density": "medium", "vehicle_mix": tagum}`, and actions from `random.Random(1).randrange(5)`;
    - `determinism_digest_equal`: `state_digest` run twice on `2j`, medium, tagum, 300 s, seed 101.
  - `--quick`: 60 s, seed 101 only, only `2j-medium-tagum` and `5j-medium-cars`, and no benchmarks.

- [ ] **Step 6: Write `tests/test_mixed_traffic_report.py`.** Call the tool's `main(["--quick", "--out", str(tmp_path / "r.json")])`. Assert that the JSON has both quick cases and that every case has the fields above, with `max_overlapping_pairs` an `int`. Don't assert that it's 0: `native-5` can overlap vehicles of different movements inside a junction, and Task 7 fixes that.

- [ ] **Step 7: Run** `.venv/Scripts/python.exe -m pytest tests/test_footprints.py tests/test_mixed_traffic_report.py -q -p no:cacheprovider --basetemp "$PYTEST_TMP"`. Expected: all pass.

- [ ] **Step 8: Record the baseline** (about 30–60 min with every-tick checks; run it in the background):

```bash
.venv/Scripts/python.exe tools/mixed_traffic_report.py --out docs/reports/mixed-traffic-baseline-native-5.json
```

Expected: the file exists, `engine_version` is `"native-5"`, and it holds 10 cases × 2 seeds of 1800 s plus the benchmarks. The values are recorded as they are; thresholds apply only in Task 11.

- [ ] **Step 9: Commit**

```bash
git add simulation/footprints.py tools/mixed_traffic_report.py tests/test_footprints.py tests/test_mixed_traffic_report.py docs/reports/mixed-traffic-baseline-native-5.json
git commit -m "Add footprint checks and the mixed-traffic report with a native-5 baseline"
```

---

### Task 2: Tagum provisional vehicle mix

**Files:**
- Modify: `simulation/scenario_config.py:10-25` (presets and `DEFAULTS["vehicle_mix"]`)
- Modify: `services/native_scenario_service.py` (`configuration_options`)
- Modify: `tools/mixed_traffic_report.py` (import the preset instead of its own constant)
- Modify: `data/scenarios/tagum_peak_event.json` (`vehicle_mix`)
- Modify: `src/api/native-scenario.ts`, `src/components/native-scenario-controls.tsx`
- Create: `src/lib/vehicle-mix.ts`, `src/lib/vehicle-mix.test.ts`, `tests/test_vehicle_mix.py`

**Interfaces:**
- Produces (Python):
  - `TAGUM_PROVISIONAL_MIX = {"motorcycle": 0.55, "tricycle": 0.25, "car": 0.15, "truck": 0.03, "bus": 0.02}`;
  - `CARS_ONLY_MIX = {"car": 1.0}`;
  - `VEHICLE_MIX_PRESETS = {"tagum_provisional": {"label": "Tagum (provisional)", "mix": TAGUM_PROVISIONAL_MIX}, "cars_only": {"label": "Cars only", "mix": CARS_ONLY_MIX}}`;
  - `configuration_options()["vehicle_mix_presets"]`.
- Produces (TypeScript):
  - `type VehicleMixPreset = { label: string; mix: Record<string, number> }`;
  - `NativeScenarioOptions.vehicle_mix_presets: Record<string, VehicleMixPreset>`;
  - `NativeScenarioConfig.vehicle_mix?: Record<string, number>`;
  - `matchingMixPreset(mix: Record<string, number> | undefined, presets: Record<string, VehicleMixPreset>): string | null` — compares normalised proportions within 1e-6;
  - `mixShares(mix: Record<string, number>): Array<{ type: string; percent: number }>`, in descending percent.

- [ ] **Step 1: Write the failing tests** in `tests/test_vehicle_mix.py`

```python
def test_new_scenarios_default_to_the_tagum_provisional_mix():
    assert DEFAULTS["vehicle_mix"] == TAGUM_PROVISIONAL_MIX == {"motorcycle": .55, "tricycle": .25, "car": .15, "truck": .03, "bus": .02}

def test_mix_changes_classes_but_not_arrival_times_or_routes():
    # validate_config(DEFAULTS, {"traffic_density": "medium", "vehicle_mix": ...}, network) for each mix, 2j network, seed 101, 3600 s
    assert [(a.time, a.source, a.destination) for a in cars] == [(a.time, a.source, a.destination) for a in tagum]
    assert abs(sum(a.vehicle_type == "motorcycle" for a in tagum) / len(tagum) - 0.55) < 0.05

def test_options_offer_both_presets():
    presets = configuration_options()["vehicle_mix_presets"]
    assert presets["tagum_provisional"]["mix"] == TAGUM_PROVISIONAL_MIX and presets["cars_only"]["mix"] == CARS_ONLY_MIX

def test_a_saved_custom_mix_is_kept():
    engine.configure(vehicle_mix={"car": 65, "motorcycle": 15, "tricycle": 10, "bus": 5, "truck": 5})
    assert engine.config["vehicle_mix"] == {"car": 65.0, "motorcycle": 15.0, "tricycle": 10.0, "bus": 5.0, "truck": 5.0}
```

And in `src/lib/vehicle-mix.test.ts`:

```ts
expect(matchingMixPreset({ motorcycle: 55, tricycle: 25, car: 15, truck: 3, bus: 2 }, presets)).toBe("tagum_provisional")
expect(matchingMixPreset({ car: 1 }, presets)).toBe("cars_only")
expect(matchingMixPreset({ car: 65, motorcycle: 15, tricycle: 10, bus: 5, truck: 5 }, presets)).toBeNull()
expect(matchingMixPreset(undefined, presets)).toBeNull()
expect(mixShares({ car: 3, motorcycle: 1 })).toEqual([{ type: "car", percent: 75 }, { type: "motorcycle", percent: 25 }])
```

- [ ] **Step 2: Run both test files.** Expected: FAIL (missing names).

- [ ] **Step 3: Implement the presets and `DEFAULTS["vehicle_mix"] = dict(TAGUM_PROVISIONAL_MIX)`.** Add a comment: "Provisional: estimated by eye from the 10 Sept 2026 recordings, not counted; replace with Field Observer class shares." Then add `vehicle_mix_presets` to `configuration_options()`, and replace the report tool's own constant with the import.

- [ ] **Step 4: Implement `src/lib/vehicle-mix.ts` and the editor.**
  - In `NativeScenarioControls`, add a `FieldSet` with legend "Vehicle mix" before "Routing".
  - It holds a `NativeSelect` labelled "Vehicle mix". Its value is `matchingMixPreset(...) ?? "custom"`. Its options are the presets plus `{ value: "custom", label: "Custom (saved)", disabled: true }`.
  - On change it sets `vehicle_mix: { ...preset.mix }`.
  - A `FieldDescription` lists `mixShares` as "Motorcycle 55% · Tricycle 25% · …", followed by "Tagum shares are a provisional estimate, not a count."

- [ ] **Step 5: Update `data/scenarios/tagum_peak_event.json`.** Set `"vehicle_mix"` to the Tagum mix values.

- [ ] **Step 6: Run the full backend suite.** For each failure caused only by the new default mix, add `vehicle_mix=CARS_ONLY_MIX` to that test's `configure(...)` call, because its intent is car traffic. Known case: `tests/test_native_engine.py::test_heavy_traffic_preserves_gaps_and_approach_exclusivity`. Expected: all pass.

- [ ] **Step 7: Run the frontend checks:** `npx vitest run`, `npx tsc -b`, and `npx eslint src/lib/vehicle-mix.ts src/lib/vehicle-mix.test.ts src/components/native-scenario-controls.tsx src/api/native-scenario.ts`. Expected: pass.

- [ ] **Step 8: Browser check on an isolated scratch database.**
  - A new scenario shows "Tagum (provisional)".
  - A scenario saved with `{"car": 65, …}` shows "Custom (saved)" and keeps its mix after an unrelated edit and save.
  - Choosing "Cars only" and saving stores `{"car": 1.0}`.

- [ ] **Step 9: Commit**: "Default new scenarios to a provisional Tagum vehicle mix".

---

### Task 3: Lane width and lane count from map data

**Files:**
- Modify: `simulation/road_network.py` (constants, `Lane`, constructor pre-pass, `visual()`)
- Create: `tests/test_road_width.py`

**Interfaces:**
- Produces:
  - `LANE_WIDTH_M = 3.3`, `JUNCTION_CLEARANCE_M = 9.0`, `STOP_LINE_SETBACK_M = 1.5`;
  - `lanes_per_direction(road: dict) -> int`;
  - `width_per_direction(road: dict) -> float`;
  - `Lane.lane_count: int = 1` and `Lane.width: float = LANE_WIDTH_M`, appended after `approach`;
  - visual lane dicts and signal groups carry the real `"width"`; visual lane dicts gain `"lane_count"`.
- Rules:
  - `lanes_per_direction`: take the first `;`-separated part of `osm_tags.lanes`, stripped. If it's a positive integer string `n`, use `max(1, n // 2)` for two-way roads and `n` for one-way roads; otherwise use 1.
  - `width_per_direction`: use the road's `width_per_direction_m` if present. It must be a finite number in [2.5, 15.0], otherwise raise `ValueError("width_per_direction_m must be between 2.5 and 15 metres")`. If absent, use `lanes_per_direction(road) * LANE_WIDTH_M`.
  - Lane centre-line offset: `width / 2` for two-way roads, 0 for one-way roads.
  - Junction clearance at a node: `max(JUNCTION_CLEARANCE_M, max(total width of roads touching the node) / 2 + STOP_LINE_SETBACK_M)`, where total width is `width × (1 if oneway else 2)`. Use it in place of the fixed 9 at both lane ends.
  - In `visual()`: stop-line half-length is `lane.width / 2`; junction corners use `lane.width / 2 + 0.05`.

- [ ] **Step 1: Write the failing tests** in `tests/test_road_width.py`

```python
def test_lane_count_comes_from_the_osm_lanes_tag():
    assert (lanes_per_direction(road("4")), lanes_per_direction(road("2")), lanes_per_direction(road("2", oneway=True)), lanes_per_direction(road(None))) == (2, 1, 2, 1)

def test_unusual_lane_tags_fall_back_safely():
    assert [lanes_per_direction(road(tag)) for tag in ("2;3", "", "abc", "1.5", "0", " 4 ")] == [1, 1, 1, 1, 1, 2]

def test_width_is_lane_count_times_3_3_unless_a_field_width_is_given():
    assert width_per_direction(road("4")) == 6.6 and width_per_direction(road("2", width=5.0)) == 5.0

def test_out_of_range_field_width_is_rejected():
    for bad in (1.0, 20.0, "wide", float("nan")):
        with self.assertRaisesRegex(ValueError, "width_per_direction_m"): width_per_direction(road("2", width=bad))

def test_lane_centre_line_sits_half_the_width_from_the_road_centre():
    # synthetic two-way east-west road through a junction: lanes tag "4" -> forward lane y == -3.3; tag "2" -> y == -1.65

def test_wide_crossing_roads_push_the_stop_line_back():
    # cross network, north-south road width_per_direction_m=12: the west incoming lane ends 13.5 m before the node (x == -13.5 at its end)

def test_existing_networks_only_change_their_four_lane_roads():
    # 5-junction network: lanes from roads tagged "4" have width 6.6 and lane_count 2; every other lane has width 3.3, lane_count 1,
    # and a shape equal to offset(clip(shape, start, end), 1.65) with the old fixed 9 m clearance

def test_visual_payload_reports_real_width_and_stop_line_length():
    # every visual road lane has "width" == lane.width and "lane_count"; each signal group's stop_line endpoints are lane.width apart
```

- [ ] **Step 2: Run** `tests/test_road_width.py`. Expected: FAIL (missing names).

- [ ] **Step 3: Implement the rules above** in `simulation/road_network.py`.

- [ ] **Step 4: Run** `tests/test_road_width.py`, then the full backend suite. Expected: all pass. If a test encodes the old 3.3 m geometry of the two 4-lane roads, update only that expectation.

- [ ] **Step 5: Commit**: "Give each road direction its real width and lane count".

---

### Task 4: Draw roads at their real width with lane lines

**Files:**
- Modify: `src/api/visual-network.ts` (`VisualLane.lane_count?: number`)
- Modify: `src/simulation/scene-geometry.ts` (`SceneLane.laneCount`, two helpers)
- Modify: `src/simulation/__tests__/scene-geometry.test.ts`
- Modify: `src/components/simulation-canvas-2d.tsx`, `src/simulation/SimulationScene3D.tsx`

**Interfaces:**
- Consumes: visual lane `width` and `lane_count` (Task 3).
- Produces:
  - `SceneLane.laneCount: number` — 1 when missing or invalid;
  - `laneDividers(centerline: readonly VisualPoint[], width: number, laneCount: number): VisualPoint[][]` — polylines offset `-width/2 + k·width/laneCount` for `k = 1 … laneCount-1`, using the same normal as `lanePolygon`;
  - `dashedPieces(points: readonly VisualPoint[], dash: number, gap: number): VisualPoint[][]`.

- [ ] **Step 1: Write the failing tests** in `scene-geometry.test.ts`

```ts
it("puts one divider on the centre line of a two-lane carriageway", () => {
  expect(laneDividers([{ x: 0, y: 0 }, { x: 10, y: 0 }], 6.6, 2)).toEqual([[{ x: 0, y: 0 }, { x: 10, y: 0 }]])
})
it("puts two dividers 1.65 m either side of a 9.9 m three-lane centre line", () => {
  const ys = laneDividers([{ x: 0, y: 0 }, { x: 10, y: 0 }], 9.9, 3).map((line) => Math.abs(line[0].y))
  expect(ys.map((y) => y.toFixed(2))).toEqual(["1.65", "1.65"])
})
it("draws no dividers for a single lane", () => expect(laneDividers([{ x: 0, y: 0 }, { x: 10, y: 0 }], 3.3, 1)).toEqual([]))
it("cuts a polyline into dashes", () => {
  expect(dashedPieces([{ x: 0, y: 0 }, { x: 12, y: 0 }], 3, 3)).toEqual([[{ x: 0, y: 0 }, { x: 3, y: 0 }], [{ x: 6, y: 0 }, { x: 9, y: 0 }]])
})
```

- [ ] **Step 2: Run** `npx vitest run src/simulation/__tests__/scene-geometry.test.ts`. Expected: FAIL.

- [ ] **Step 3: Implement the helpers and the drawing.**
  - 2D: for road lanes with `laneCount > 1`, draw each divider with `path(..., palette.markings, Math.max(1, transform.scale * .12), true)`.
  - 3D: push `ribbon(piece, 0.1, 0.035)` into `markingParts` for every `dashedPieces(divider, 3, 3)`.

- [ ] **Step 4: Run** `npx vitest run`, `npx tsc -b`, and `npx eslint` on the changed files. Expected: pass.

- [ ] **Step 5: Browser check.** On the 5-junction network, the two 4-lane roads are visibly wider, with a dashed divider in both 2D and 3D. Single-lane roads look unchanged.

- [ ] **Step 6: Commit**: "Draw roads at their real width with lane dividers".

---

### Task 5: Class driving parameters and per-vehicle driver variety

**Files:**
- Create: `simulation/mixed_traffic.py`
- Modify: `simulation/traffic_engine.py`
  - `Vehicle` dataclass;
  - `__init__` and `_reset_state`;
  - `add_vehicle`, and the `entry_possible` check in `_spawn_vehicles_and_pedestrians` (also restore the missing space in `single_demo = self…`);
  - `_advance`;
  - the stop-line obstacle in `_move_vehicle`.
- Modify: `tests/test_junction_capacity.py` (variation 0 in its helpers)
- Create: `tests/test_driver_variety.py`

**Interfaces:**
- Produces (`mixed_traffic.py`):
  - `DrivingParameters(time_headway: float, minimum_gap: float, max_acceleration: float, max_lateral_speed: float)` (frozen dataclass);
  - `CLASS_DRIVING: dict[str, DrivingParameters]`, holding the table from Global Constraints;
  - `DriverProfile(speed_multiplier, time_headway, minimum_gap, max_acceleration, max_lateral_speed)` (frozen);
  - `DRIVER_STREAM_SALT = 0x445256`, `SPEED_VARIATION_SD = 0.08`, `SPEED_MULTIPLIER_RANGE = (0.8, 1.2)`, `HEADWAY_VARIATION_SD = 0.15`, `HEADWAY_MULTIPLIER_RANGE = (0.7, 1.4)`;
  - `sample_driver(vehicle_type: str, rng: random.Random, variation_scale: float) -> DriverProfile`. It **always draws exactly two `rng.gauss` values** (speed, then headway) whatever the scale. Each multiplier is `clip(1 + scale·noise, range)`. Minimum gap, acceleration and lateral speed come from the class.
- Produces (engine):
  - `TrafficEngine.driver_variation_scale: float = 1.0`, set in `__init__` and kept across `configure`;
  - `self.driver_random`;
  - `Vehicle.time_headway = 1.2`, `Vehicle.minimum_gap = 2.0`, `Vehicle.max_acceleration = 1.5`, `Vehicle.max_lateral_speed = 0.5`.
- Rules:
  - `add_vehicle` samples a profile only after the entry check passes. It sets `speed_factor = spec["speed_factor"] * profile.speed_multiplier` and copies the other profile fields.
  - Spawn checks use `spec["length"] + CLASS_DRIVING[type].minimum_gap` instead of `MIN_GAP`.
  - `_advance` uses the vehicle's `minimum_gap`, `time_headway` and `max_acceleration`; `b` stays `COMFORTABLE_DECELERATION`.
  - The stop-line obstacle becomes `stop_position + vehicle.minimum_gap`.

- [ ] **Step 1: Record the pre-change digest** (one-off verification, not a test):

```bash
.venv/Scripts/python.exe -c "import json; from simulation.road_network import RoadNetwork; from simulation.traffic_engine import TrafficEngine; from simulation.footprints import longitudinal_digest; n=RoadNetwork(json.load(open('data/networks/tagum_network_2j.json',encoding='utf-8'))); e=TrafficEngine(seed=101,network=n); e.configure(traffic_density='medium',vehicle_mix={'car':1.0}); e.start(600); print(longitudinal_digest(e,600))"
```

Expected: one hex digest. Note it down.

- [ ] **Step 2: Write the failing tests** in `tests/test_driver_variety.py`

```python
def test_class_table_matches_the_design():
    assert CLASS_DRIVING["motorcycle"] == DrivingParameters(0.8, 1.0, 2.0, 1.0) and CLASS_DRIVING["bus"] == DrivingParameters(1.5, 2.5, 0.8, 0.3)  # and car, tricycle, truck

def test_scale_zero_gives_the_class_values():
    assert sample_driver("car", random.Random(1), 0.0) == DriverProfile(1.0, 1.2, 2.0, 1.5, 0.5)

def test_variation_stays_inside_its_bounds():
    profiles = [sample_driver("motorcycle", rng, 1.0) for _ in range(2000)]
    assert all(0.8 <= p.speed_multiplier <= 1.2 and 0.56 - 1e-9 <= p.time_headway <= 1.12 + 1e-9 for p in profiles)
    assert abs(statistics.fmean(p.speed_multiplier for p in profiles) - 1) < 0.01

def test_same_seed_gives_the_same_drivers():
    # two engines, seed 5, medium, Tagum mix, 600 ticks: [(id, speed_factor, time_headway)] equal

def test_driver_variety_does_not_touch_the_arrival_schedule():
    # same seed and settings, driver_variation_scale 0 vs 1: engine.demand_fingerprint and engine.arrivals equal

def test_motorcycles_stand_closer_than_cars():
    # cross network, red: five motorcycles queue with standstill gaps < 1.2 m; five cars with gaps > 1.9 m (variation 0)
```

- [ ] **Step 3: Run** them. Expected: FAIL (missing module).

- [ ] **Step 4: Implement `mixed_traffic.py` and the engine changes.** In `tests/test_junction_capacity.py`, set `engine.driver_variation_scale = 0` before `start` in `saturated_discharge` and wherever an engine is built.

- [ ] **Step 5: Run the new tests and the full backend suite.** Expected: all pass.

- [ ] **Step 6: Repeat Step 1's command,** with `e.driver_variation_scale = 0` added before `start`. Expected: **the same digest**, which shows variation off reproduces the cars-only `native-5` behaviour.

- [ ] **Step 7: Commit**: "Add class driving parameters and seeded per-vehicle driver variety". Include both digests in the commit message.

---

### Task 6: Vehicles side by side on lanes

**Files:**
- Modify: `simulation/mixed_traffic.py` (lateral helpers)
- Modify: `simulation/traffic_engine.py`
  - `Vehicle` dataclass;
  - `_pose` (new) and `vehicle_records`;
  - `_lane_obstacle` (new; replaces lines 673–681);
  - `_entry_lateral` and `_build_spawn_occupancy` (new);
  - `add_vehicle` and `_spawn_demand`;
  - connector entry.
- Create: `tests/mixed_traffic_helpers.py`, `tests/test_side_by_side.py`
- Modify:
  - `tests/test_native_traffic_contract.py` (`assert_bumper_gaps` body);
  - `tests/test_native_engine.py` (gap check in `test_heavy_traffic_preserves_gaps_and_approach_exclusivity`);
  - `tests/test_engine_search_index.py` (`FullScanEngine`).

**Interfaces:**
- Produces (`mixed_traffic.py`):
  - `SIDE_CLEARANCE_M = 0.3`, `EDGE_CLEARANCE_M = 0.1`, `LATERAL_GRID_M = 0.25`;
  - `LANE_KEEPING_CLASSES = frozenset({"car", "bus", "truck"})`, `KERB_KEEPING_CLASSES = frozenset({"tricycle"})`;
  - `lateral_bounds(lane_width: float, vehicle_width: float, edge_clearance: float = EDGE_CLEARANCE_M) -> tuple[float, float]` — `half = (lane_width - vehicle_width)/2 - edge_clearance`; returns `(0.0, 0.0)` if `half < 0`, else `(-half, half)`;
  - `bands_overlap(lateral_a: float, width_a: float, lateral_b: float, width_b: float, clearance: float = SIDE_CLEARANCE_M) -> bool` — `abs(a - b) < (width_a + width_b)/2 + clearance - 1e-9`;
  - `body_box(length: float, width: float, yaw: float) -> tuple[float, float]` — `(length·cos|yaw| + width·sin|yaw|, length·sin|yaw| + width·cos|yaw|)`: the along-road length and across-road width of the road-aligned box around a body turned by `yaw`;
  - `candidate_laterals(lane_width: float, vehicle_width: float) -> list[float]` — ascending from the low bound in 0.25 m steps, always including the high bound, rounded to 6 decimals;
  - `sub_lane_of(lateral: float, lane_width: float, lane_count: int) -> int`;
  - `keeping_position(vehicle_type: str, vehicle_width: float, lane_width: float, lane_count: int, sub_lane: int) -> float | None`:
    - lane keepers: `-lane_width/2 + sub_lane·(lane_width/lane_count) + EDGE_CLEARANCE_M + vehicle_width/2`, clamped to the bounds (a car on a 3.3 m lane: −0.65);
    - kerb keepers: the high bound;
    - motorcycles: `None`.
- Produces (engine):
  - `Vehicle.lateral: float = 0.0`, `Vehicle.lateral_speed: float = 0.0`;
  - `Vehicle.yaw: float = 0.0` — the body's angle from its lane's direction in radians, positive when turned toward the right-hand kerb. It stays 0 until Task 9 and is always 0 on connectors;
  - `_box(vehicle) -> tuple[float, float]` — `body_box(vehicle.length, vehicle.width, vehicle.yaw)`;
  - `_pose(vehicle) -> tuple[float, float, float]` — x, y and the body heading (path heading − `yaw`), including the lateral offset, on a lane or a connector;
  - `_lane_obstacle(vehicle, lane) -> tuple[Vehicle | None, float, float]` — (leader, obstacle, leader_speed);
  - `_entry_lateral(lane_id: str, vehicle_type: str) -> float | None`;
  - `_build_spawn_occupancy() -> dict[str, list[tuple[float, float, float]]] | None` — lane → (rear, lateral, width) for vehicles on lanes;
  - vehicle records gain `"lateral"`.
- Rules:
  - **Body size:** every lane rule (leader, gaps, spawn, bounds) uses `_box(vehicle)` for a vehicle's length and width, so Task 9's turned bodies are checked as drawn.
  - **Leader:** the nearest vehicle ahead on the same lane whose band overlaps. Vehicles turning off this lane stay obstacles **regardless of lateral**, so junction entry is single file until Task 7.
  - **Spawn:** a position `c` is free when every on-lane vehicle whose band overlaps has `rear >= spec length + class minimum gap`.
    - Lane keepers try `keeping_position` for each sub-lane. Sub-lanes are ordered by most free room at the start (the smallest rear among overlapping vehicles, infinite if none), then by index. Lane keepers take no other position.
    - Tricycles and motorcycles try `candidate_laterals` from the kerb inward.
    - `None` means blocked.
  - **Spawn equivalence:** `add_vehicle` and the `entry_possible` pre-check use `_entry_lateral`; the occupancy cache, when present, must give the same answer as a full scan. `self._spawn_rears` is replaced by `self._spawn_occupancy`, filled by `_build_spawn_occupancy()` in `_spawn_demand`.
  - **Connector entry:** set `vehicle.lateral = 0.0` (Task 7 carries the offset).

- [ ] **Step 1: Create `tests/mixed_traffic_helpers.py`.**
  - `junction_network(width_per_direction_m=None, lanes_tag="2", arm_length=150.0) -> RoadNetwork` builds a cross with boundary arms `w`, `e`, `n`, `s` as two-way roads to junction `j`, at 8.33 m/s, with `osm_tags {"lanes": lanes_tag}`.
  - `started_engine(network, **config) -> TrafficEngine` uses seed 7, traffic none, pedestrians none, `driver_variation_scale = 0`, then `start(600)`.
  - `place(engine, route, vehicle_type, *, from_stop_line: float, lateral: float) -> Vehicle` adds the vehicle and sets `position = lane.length - length/2 - from_stop_line`.
  - `assert_never_overlap(test, engine, ticks, *, every=1, lanes_only=False)` asserts on every sample that `overlapping_pairs(...)` is empty and that each lane vehicle's body is on its road: `lower ≤ lateral ≤ upper` (± 1e-9) for `lateral_bounds(lane.width, vehicle.width)` when `yaw == 0`, and for `lateral_bounds(lane.width, engine._box(vehicle)[1], edge_clearance=0)` when turned.

- [ ] **Step 2: Write the failing tests** in `tests/test_side_by_side.py`

```python
def test_two_cars_stay_single_file_on_a_3_3_m_lane():
    # red at j; two cars spawn on w; after 30 s the rear car's front is behind the front car's rear (no side by side)
def test_two_cars_queue_abreast_on_a_6_6_m_carriageway():
    # lanes_tag "4"; cars placed 20 m back in sub-lanes 0 and 1; after 30 s of red both fronts within 1 m of the stop line
def test_motorcycle_on_the_kerb_side_reaches_the_stop_line_past_queued_cars():
    # 3.3 m; three cars queued at the line (lateral -0.65); motorcycle 40 m back at lateral +1.15; after 30 s its front is within 1 m of the stop line
def test_tricycle_holds_cars_behind_but_lets_motorcycles_pass():
    # red; tricycle at the line at the kerb (+0.85); motorcycle 20 m back at -1.15; car 40 m back at -0.65:
    # after 30 s the motorcycle's front is within 1 m of the line and the car's front is behind the tricycle's rear
def test_spawn_places_vehicles_abreast_when_the_lane_start_is_partly_occupied():
    # a car just spawned on w; a motorcycle spawned on the same tick gets a kerb-side lateral and is not blocked
def test_mixed_traffic_never_overlaps_on_lanes():
    # 2j network, Tagum mix, medium, 300 s: assert_never_overlap(..., every=1, lanes_only=True)
```

- [ ] **Step 3: Run** them. Expected: FAIL.

- [ ] **Step 4: Implement the helpers and the engine changes.** Also update the existing tests:
  - `assert_bumper_gaps` now calls `assert_never_overlap` for the current state with `lanes_only=True`. Keep the method name so its callers are unchanged.
  - The heavy-traffic gap loop becomes an overlap check of lane vehicles.
  - `FullScanEngine` gains `def _build_spawn_occupancy(self): return None`.

- [ ] **Step 5: Run the new tests, the full backend suite, and `tests/test_engine_search_index.py`.** Expected: all pass.

- [ ] **Step 6: Commit**: "Let vehicles travel and queue side by side on a lane".

---

### Task 7: Side by side through the junction

**Files:**
- Modify: `simulation/traffic_engine.py`
  - `Vehicle` connector laterals;
  - connector entry and exit;
  - `_turn_angle` (new; `_movement_speed` uses it);
  - `_progress`, `_exit_lateral`, `_paths_merge`, `_paths_cross` and `_must_wait_at_line` (new), and the proceed check;
  - `_connector_lateral`, `_junction_pool`, `_junction_gap` (replaces `_connector_gap`) and `_clear_travel`;
  - overlap for turning-off vehicles in `_lane_obstacle`.
- Create: `tests/test_junction_side_by_side.py`
- Modify:
  - `tests/mixed_traffic_helpers.py` (`junction_network` gains `arm_widths: dict[str, float] | None = None`, setting `width_per_direction_m` per arm);
  - `tests/test_side_by_side.py` (the overlap test now covers all vehicles);
  - `tests/test_junction_capacity.py` (backward check).

**Interfaces:**
- Consumes: `_pose`, `_box`, `bands_overlap`, `lateral_bounds`, `SIDE_CLEARANCE_M` (Task 6).
- Produces:
  - `Vehicle.connector_entry_lateral: float = 0.0`, `Vehicle.connector_exit_lateral: float = 0.0`;
  - `_turn_angle(incoming: str, outgoing: str) -> float` — the signed heading change in degrees, wrapped to (−180, 180], positive for a left (counter-clockwise) turn. `_movement_speed` uses its absolute value;
  - `_progress(vehicle) -> float` — `connector_position` on a connector, otherwise `position − lane.length`; larger is further along;
  - `_exit_lateral(vehicle) -> float` — `connector_exit_lateral` on a connector, otherwise `clamp(lateral, *lateral_bounds(exit lane width, width))`;
  - `_paths_merge(a, b) -> bool` — same `route[:2]` and `bands_overlap(_exit_lateral(a), a.width, _exit_lateral(b), b.width)`. Checking the exits is enough: clamping never moves two positions apart, so overlapping entries always give overlapping exits;
  - `_paths_cross(a, b) -> bool` — different `route[1]` and `(turn_a − turn_b)·(start_a − start_b) > 0`, where `turn = _turn_angle(route[0], route[1])` and `start` is `connector_entry_lateral` on a connector, otherwise `lateral`. A left turner starting to the right of a through vehicle crosses it;
  - `_must_wait_at_line(vehicle) -> bool` — true when another vehicle from the same incoming lane either:
    - is on a connector, `_paths_cross` with it, and is beside it: `abs(_progress(a) − _progress(b)) < (a.length + b.length)/2 + max(a.minimum_gap, b.minimum_gap)`; or
    - is also on the lane with `stop_arrival` set, `_paths_merge` or `_paths_cross` with it, and has `(other.stop_arrival, other.id) < (vehicle.stop_arrival, vehicle.id)`, the order `_stop_priority` already uses;
  - `_connector_lateral(vehicle, connector_length: float) -> float` — linear blend from entry to exit by `connector_position / connector_length`;
  - `_junction_pool(vehicle) -> list[Vehicle]` — `_candidates(*[("turning_off", lane) for lane in network.incoming[node]], ("on_lane", vehicle.route[1]))`, where `node` is the target of `route[0]`;
  - `_junction_gap(vehicle, connector_length: float) -> tuple[float, float]`;
  - `_clear_travel(vehicle, travel: float, connector_length: float) -> float` — tries `travel, travel/2, travel/4, travel/8, travel/16`, then 0, and returns the first travel whose rectangle at the new position overlaps no pool vehicle.
- Rules:
  - **Connector entry:**
    - `entry = vehicle.lateral`: its real position, with no clamp, so nothing jumps at the stop line;
    - `exit = _exit_lateral(vehicle)`;
    - `vehicle.lateral` follows `_connector_lateral` each step;
    - on reaching the exit lane, `lateral = connector_exit_lateral`.
  - **Proceed:** a vehicle may not proceed into the junction while `_must_wait_at_line(vehicle)`. This adds to the signal, occupancy, exit-space and commit rules and replaces none of them.
  - **`_junction_gap`:**
    - For a pool vehicle on the **same movement** that `_paths_merge` with this one and is ahead along the path, use the existing along-the-path gap.
    - For any **other** pool vehicle, use the moving vehicle's frame: `lon = dx·cos h + dy·sin h` and `lat = dx·sin h − dy·cos h`. It's a leader if `lon > 0` and `|lat| < (w + w_o)/2 + SIDE_CLEARANCE_M`, with `gap = lon − (l + l_o)/2`.
    - Return the smallest gap and that leader's speed.
  - **Turning-off obstacles:** in `_lane_obstacle`, a turning-off vehicle counts when `bands_overlap` with it, or when `_paths_merge` with it.
  - **Why nothing locks up:**
    - merging vehicles go single file;
    - crossing vehicles are never beside each other inside the junction;
    - vehicles level at the line follow the fixed order;
    - a vehicle in the junction never waits for one that has not entered.

- [ ] **Step 1: Write the failing tests** in `tests/test_junction_side_by_side.py`

```python
def test_front_row_enters_the_junction_together():
    # car at -0.65 and motorcycle at +1.15 at the w stop line, both w->e, w green: both on connectors within 20 ticks; never overlap for 300 ticks; both reach the e lane
def test_crossing_movements_from_one_approach_never_overlap():
    # both stopped at the w line, the car first: car at +0.65 turning w->n (left), motorcycle at -1.15 going w->e:
    # assert_never_overlap 400 ticks; the motorcycle gets its connector only once the car is no longer beside it; both leave the junction
def test_offset_stays_inside_the_connector():
    # arm_widths {"w": 6.6}: during passage abs(lateral) <= (1-f)*lateral_bounds(6.6, width)[1] + f*lateral_bounds(3.3, width)[1] + 1e-9, f = connector_position / connector_length
def test_no_sideways_jump_entering_a_narrower_exit():
    # arm_widths {"w": 6.6}; a car at +1.0 at the w stop line goes w->e (3.3 m): every tick abs(Δlateral) <= 0.05 until it is on the e lane
def test_abreast_cars_merge_into_a_narrower_exit_one_after_the_other():
    # arm_widths {"w": 6.6}; cars at -2.3 and +1.0 stopped at the w line, the -2.3 car first, both w->e, green: never overlap (every tick);
    # the +1.0 car's front crosses the stop line only after the other car's rear has; both reach the e lane within 300 ticks
def test_all_way_stop_admits_one_vehicle_at_a_time_from_an_abreast_front_row():
    # j all_way_stop; car and motorcycle abreast at w line, car at n line: every tick len(reservations.get("j", ())) <= 1; never overlap; all three pass within 600 ticks
```

In `tests/test_junction_capacity.py`:

```python
def test_cars_only_single_lane_discharge_stays_within_ten_percent_of_native_5(self):
    _, headway = self.saturated_discharge("e")
    self.assertTrue(2.19 <= headway <= 2.67)  # native-5 measured 2.43 s
```

- [ ] **Step 2: Run** them. Expected: the side-by-side tests FAIL. The capacity test may already pass, which is fine: it guards against regressions.

- [ ] **Step 3: Implement the rules.** Change `test_mixed_traffic_never_overlaps_on_lanes` to `lanes_only=False` and rename it `test_mixed_traffic_never_overlaps`.

- [ ] **Step 4: Run the new tests, the full backend suite and the quick report** (`--quick`). Expected: all pass. The quick report shows `max_overlapping_pairs == 0`.

- [ ] **Step 5: Commit**: "Carry side-by-side vehicles through the junction without overlap".

---

### Task 8: Exit storage stays end to end (keeps the P0-1 guarantee)

The `native-5` storage rule already keeps the guarantee with vehicles side by side, and it doesn't limit how many followers can commit. This task proves both and makes the rule count each vehicle's own gap. The rejected sideways-band reservation is in spec 6.5.

**Files:**
- Modify: `simulation/traffic_engine.py` (`_exit_has_space`: each vehicle's own minimum gap, and the docstring)
- Modify: `tests/test_junction_deadlock.py`, `tests/test_junction_capacity.py`

**Interfaces:**
- Consumes: `lateral_bounds`, `SIDE_CLEARANCE_M` (Task 6); `Vehicle.minimum_gap` (Task 5); `EXIT_SPACE_MARGIN`.
- Produces: nothing new. `_exit_has_space(lane_id, entering) -> bool` keeps its signature and its callers (the commit check and `_stop_priority`). No sideways band is reserved, and `_reserve` is unchanged.
- **Rule:** everything on or committed to the exit lane, plus the entrant, must fit end to end, each counted as `length + minimum_gap + EXIT_SPACE_MARGIN`. The margin also covers the few centimetres a turned body adds to its length. The docstring says why the rule holds side by side: a vehicle stops only behind a leader or a stop line, and every leader in the chain ahead of an entrant is already counted, whatever its lateral.

- [ ] **Step 1: Write the tests** in `tests/test_junction_deadlock.py` and `tests/test_junction_capacity.py`
  - `two_junction_line(link_length=60, link_width=None)` sets the link's `width_per_direction_m` when given.
  - Extend `test_any_admitted_vehicle_clears_and_releases_behind_a_held_queue` with loops over `link_width in (None, 6.6)` and `queued_side in ("left", "kerb")`, placing queued vehicles at `lateral_bounds(...)[0 or 1]`. Its assertions stay the same, including `outcomes == {True, False}`.
  - Add the tests below.

```python
def test_area_only_rule_would_strand_a_vehicle(self):
    class AreaOnlyEngine(TrafficEngine):
        def _exit_has_space(self, lane_id, entering):  # footprint area only, no end-to-end check
            # the same occupying vehicles as TrafficEngine._exit_has_space, plus the entrant:
            # sum((v.length + v.minimum_gap) * (v.width + SIDE_CLEARANCE_M)) <= 0.8 * lane.length * lane.width
    # the extended loops with AreaOnlyEngine: some case enters j1 and never releases it
    self.assertTrue(any(stranded for each case), "the end-to-end rule must be what prevents stranding")

def test_motorcycles_count_with_their_own_minimum_gap(self):
    # link held at red at j2, a motorcycle added on w every 2 s for 120 s: the number on or committed to the link
    # stops at floor(link.length / (2.0 + 1.0 + EXIT_SPACE_MARGIN)); never overlap

# in tests/test_junction_capacity.py
def test_followers_commit_while_the_leader_is_still_crossing(self):
    # saturated cars-only discharge, variation 0: at some tick at least two cars hold reservations at the junction at once
```

- [ ] **Step 2: Run** `tests/test_junction_deadlock.py` and `tests/test_junction_capacity.py`. Expected: only `test_motorcycles_count_with_their_own_minimum_gap` FAILS, because the rule still counts `MIN_GAP` for every vehicle. The extended loops, the area-only check and the follower test pass already. They pin what this task keeps: no stranding side by side, and no limit on followers committing.

- [ ] **Step 3: Implement the rule** in `_exit_has_space`: count `vehicle.length + vehicle.minimum_gap + EXIT_SPACE_MARGIN`, and extend the docstring.

- [ ] **Step 4: Run the deadlock tests, the capacity tests and the full backend suite.** Expected: all pass.

- [ ] **Step 5: Commit**: "Keep end-to-end exit storage with each vehicle's own gap, proven side by side".

---

### Task 9: Gap seeking and motorcycle filtering

**Files:**
- Modify: `simulation/mixed_traffic.py` (decision constants)
- Modify: `simulation/traffic_engine.py`
  - `Vehicle` lateral state;
  - `_turn_side`, `_lateral_speed_limit`, `_lateral_room`, `_side_clear`, `_decide_lateral` and `_step_lateral` (new);
  - the call order in `_move_vehicle`;
  - `yaw`, which sets the record angle through `_pose`.
- Create: `tests/test_gap_seeking.py`

**Interfaces:**
- Consumes: `_box`, `body_box`, `lateral_bounds`, `bands_overlap`, `candidate_laterals`, `keeping_position`, `sub_lane_of` (Task 6); `_turn_angle`, `connector_exit_lateral` (Task 7).
- Produces (`mixed_traffic.py`): `LATERAL_DECISION_TICKS = 5`, `MOVE_GAIN_THRESHOLD_M = 2.0`, `MOVE_COST_PER_M = 1.0`, `KEEPING_WEIGHT_PER_M = 2.0`, `TURN_SIDE_WEIGHT_PER_M = 2.0`, `TURN_SIDE_DISTANCE_M = 30.0`, `MOVE_COOLDOWN_SECONDS = 2.0`, `ROOM_HORIZON_M = 50.0`, `MAX_YAW_DEGREES = 10.0`, `MOTORCYCLE_SHUFFLE_MPS = 0.3`.
  - The turn-side weight must exceed the move cost, or a turning vehicle never gains enough to change lane portion. A car moving 3.3 m to its turn side then gains 3.3 m, which passes the 2.0 m threshold.
- Produces (engine):
  - `Vehicle.lateral_target: float = 0.0`, `Vehicle.lateral_cooldown_until: float = 0.0`;
  - `_turn_side(incoming: str, outgoing: str) -> int` — from Task 7's `_turn_angle`: greater than `THROUGH_ANGLE_DEGREES` gives −1 (left turn, counter-clockwise); less than −`THROUGH_ANGLE_DEGREES` gives +1; otherwise 0;
  - `_lateral_speed_limit(vehicle) -> float` — `min(max_lateral_speed, max(speed·tan(MAX_YAW_DEGREES), MOTORCYCLE_SHUFFLE_MPS if motorcycle else 0.0))`. It is 0 for a stopped car, tricycle, bus or truck;
  - `_lateral_room(vehicle, lane, lateral: float) -> float` — `min(ROOM_HORIZON_M, distance from the vehicle's front to the nearest obstacle in that band)`. Obstacles are lane leaders and turning-off vehicles whose bands overlap, plus the stop line when the vehicle may not proceed now;
  - `_side_clear(vehicle, lane, start: float, end: float) -> bool` — the planning check, with straight bodies and full clearances: no lane vehicle with `|Δposition| < (l + l_o)/2 + 0.5` whose band (its `_box` width), widened by `SIDE_CLEARANCE_M`, meets the swept interval `[min(start, end) − w/2, max(start, end) + w/2]`. Each vehicle on a connector into this lane counts as a lane vehicle at `connector_position − connector_length` with lateral `connector_exit_lateral`, so no vehicle moves into the path of one arriving from the junction;
  - `_decide_lateral(vehicle, lane) -> None` — runs when `(self.ticks + serial) % LATERAL_DECISION_TICKS == 0`, `lateral == lateral_target`, the time is past `lateral_cooldown_until`, `_lateral_speed_limit(vehicle) > 0`, and the vehicle is not committed to `lane.target`. `serial` is the integer after the last `-` in `vehicle.id`. It scores each of `candidate_laterals` and sets `lateral_target` to the best one when that one is `_side_clear` and beats the current position by `MOVE_GAIN_THRESHOLD_M`;
  - `_step_lateral(vehicle, lane) -> None` — the per-tick check, with the turned body:
    - It tries steps of `_lateral_speed_limit(vehicle) · STEP_LENGTH` × 1, ½, ¼ and ⅛ toward the target, never past it.
    - A step `d` gives the trial yaw `copysign(min(atan2(|d| / STEP_LENGTH, speed), radians(MAX_YAW_DEGREES)), d)`, positive toward the kerb.
    - It takes the first step whose turned box (`body_box` at the trial yaw) stays on the road, meaning within `lateral_bounds(lane.width, across, edge_clearance=0)`. The box must also overlap no other vehicle's box: `bands_overlap(..., clearance=0)` for vehicles whose along-road extents meet, including the connector arrivals counted by `_side_clear`.
    - It then sets `lateral`, `lateral_speed = d / STEP_LENGTH` and `yaw`.
    - If no step fits, it sets `yaw = 0`, `lateral_speed = 0` and `lateral_target = lateral`, sets the cooldown and stops. On arrival it sets `yaw = 0` and `lateral_speed = 0`, then the cooldown. A vehicle that isn't moving sideways has `yaw == 0`.
  - **Score** of a candidate `c`:

    ```
    _lateral_room(c) − MOVE_COST_PER_M·|c − lateral| − KEEPING_WEIGHT_PER_M·|c − keep| − TURN_SIDE_WEIGHT_PER_M·|c − side_bound|
    ```

    - `keep` is `keeping_position` for the candidate's own sub-lane, `sub_lane_of(c, …)`. The term is skipped when `keep` is `None`.
    - The turn term applies only within `TURN_SIDE_DISTANCE_M` of the stop line when `_turn_side ≠ 0`. `side_bound` is the low bound for −1 and the high bound for +1.
  - **Call order** in the lane branch of `_move_vehicle`: after the release and reroute, before the leader search, call `_decide_lateral` and then `_step_lateral`. Neither runs on connectors.
  - **Record angle:** it comes from `_pose` (`heading − yaw`), so the drawn body is the one `_step_lateral` checked. There is no separate formula.

- [ ] **Step 1: Write the failing tests** in `tests/test_gap_seeking.py`

```python
def test_motorcycle_moves_aside_and_filters_to_the_stop_line():
    # 3.3 m, red, three cars queued at -0.65; motorcycle 40 m behind at lateral 0: within 60 s its front is within 1 m of the line; never overlap
def test_motorcycle_stays_behind_when_the_gap_is_too_narrow():
    # width_per_direction_m 2.8: after 60 s the motorcycle's front is still behind the last car's rear
def test_motorcycle_starts_a_move_from_the_kerb_edge():
    # 3.3 m, red; a tricycle stopped at the line at +0.85; a motorcycle stopped 4 m behind it at the kerb bound +1.15:
    # within 20 s its front is within 1 m of the line on the centre-line side; never overlap and never off the road (every tick)
def test_lateral_motion_respects_speed_limits_and_does_not_jitter():
    # 2j, Tagum, medium, 300 s: every tick abs(Δlateral) <= _lateral_speed_limit(vehicle) at the tick's start * 0.1 + 1e-9;
    # per vehicle at most 2 sign reversals of lateral_speed in any 10 s
def test_stopped_cars_tricycles_buses_and_trucks_never_move_sideways():
    # same run: a non-motorcycle whose speed was 0 at the tick's start keeps its lateral through that tick
def test_left_turners_wait_on_the_centre_line_side():
    # lanes_tag "4" (6.6 m), red; a car routed w->n placed 25 m from the line in the kerb-side lane portion (lateral +1.0): after 20 s its lateral < 0
def test_bus_and_truck_moving_beside_stopped_traffic_never_overlap():
    # lanes_tag "4", red; three cars stopped at the line in sub-lane 0; a bus routed w->n starts 60 m back in sub-lane 1,
    # so its left turn draws it toward the stopped cars: never overlap and never off the road (every tick) for 400 ticks; repeat with a truck
def test_vehicle_near_the_lane_start_does_not_move_into_an_arriving_vehicle():
    # a car 3 m from the end of its connector into e; a motorcycle 2 m into e would gain room at the car's exit lateral: they never overlap (every tick)
def test_filtering_raises_the_front_row_motorcycle_share():
    # 3.3 m, red for 90 s; seeds 1-5 each add a vehicle on w every 2.0 s, classes from random.Random(seed).choices with the Tagum weights.
    # Front row: stopped vehicles whose front is within 1.0 m of the line at the end of the red, pooled over the seeds.
    # Its motorcycle share is higher than with NoFilteringEngine (a test subclass whose _decide_lateral does nothing) on the same seeds
def test_closure_during_filtering_keeps_accounting_and_no_overlap():
    # 2j, Tagum, medium; events close incoming[controlled][0] at 60 s, reopen at 180 s; 240 s: never overlap (every tick), conservation 0, stuck 0
def test_very_high_demand_at_the_vehicle_cap_never_overlaps():
    # 2j, "very high", max_active_vehicles=120, 240 s: never overlap (every tick), stuck 0, gridlock 0
```

- [ ] **Step 2: Run** them. Expected: the filtering, kerb-edge, turn-side and front-row tests FAIL. The others may pass, which is fine: they guard against regressions. If a mechanism test still fails after Step 3, look for a bug; never tune the provisional values to make it pass.

- [ ] **Step 3: Implement the decision and step logic.**

- [ ] **Step 4: Run the new tests, the full backend suite and the quick report.** Expected: all pass. The quick report shows `max_overlapping_pairs == 0`.

- [ ] **Step 5: Commit**: "Let narrow vehicles seek gaps and filter to the stop line".

---

### Task 10: Queue reach metric

**Files:**
- Modify: `simulation/traffic_engine.py` (`_queue_reach`, `_refresh_metrics`)
- Modify: `simulation/metric_definitions.json` (new entry; `"version": "native-metric-interpretation-4"`)
- Create: `tests/test_queue_reach.py`
- Modify: any test asserting `native-metric-interpretation-3`

**Interfaces:**
- Produces:
  - `_queue_reach(lane_id: str) -> float` — the largest `lane.length − (position − length/2)` over stopped vehicles (speed ≤ 0.1, not on a connector) on that lane; 0.0 if none;
  - `_last_metrics["junctions"][node]["queue_reach_m"]` — approach → largest reach over that approach's incoming lanes;
  - `_last_metrics["max_queue_reach_m"]` — the largest reach over incoming lanes of every modeled junction.
- **Catalog entry, exact text:**
  - `key`: `"max_queue_reach_m"`; `label`: `"Longest current queue reach"`; `unit`: `"metres"`; `aliases`: `[]`;
  - `population`: `"Incoming lanes of all modeled junctions."`;
  - `definition`: `"Distance from a stop line to the rear of the farthest stopped vehicle (speed at most 0.1 m/s) on that incoming lane at the latest tick; the largest value over incoming lanes. Side-by-side queues reach less far than single-file queues of the same vehicles. Connector vehicles are excluded."`;
  - `population_keys`: `[]`; `requires_ticks`: `false`; `requires_elapsed`: `false`;
  - `zero`: `"Zero means no stopped vehicle on any incoming lane at the latest tick."`;
  - `unavailable`: `"Missing or non-finite values are unavailable."`.

- [ ] **Step 1: Write the failing tests** in `tests/test_queue_reach.py`

```python
def test_single_file_queue_reach_is_the_rear_of_the_last_car():
    # 3.3 m, red, two cars queued: reach == lane.length - (car2.position - car2.length / 2)
def test_side_by_side_queue_reaches_less_far():
    # four cars: 6.6 m two abreast vs 3.3 m single file; reach(6.6) < reach(3.3)
def test_metrics_report_reach_by_approach_and_network_maximum():
    # junctions["j"]["queue_reach_m"]["west"] == _queue_reach(west lane); max_queue_reach_m == max over incoming lanes
def test_catalog_defines_queue_reach():
    # entry exists with unit "metres" and requires_ticks False; catalog version "native-metric-interpretation-4"
```

- [ ] **Step 2: Run.** Expected: FAIL.

- [ ] **Step 3: Implement the metric and the catalog entry.**

- [ ] **Step 4: Run the new tests, the full backend suite and `npx vitest run`** (the frontend reads the catalog). Expected: pass.

- [ ] **Step 5: Commit**: "Add queue reach in metres per approach and for the network".

---

### Task 11: Acceptance run and RL scale check

**Files:**
- Create (generated): `docs/reports/mixed-traffic-acceptance.json`
- Modify only if Step 4 requires it: `simulation/rl_state.py`, `simulation/model_contract.py`, `simulation/rl_reward.py`, `simulation/dql_training.py`, `simulation/ppo_training.py`, `tools/train_ql.py`, and the tests asserting their version strings.

**Interfaces:**
- Consumes: the report tool (Task 1) and the baseline JSON.
- Produces, only if scales change:
  - `rl_state.OBSERVATION_VERSION`, defined once and imported by the three training modules instead of their `"obs_v2"` literals;
  - `"native-local-22-v3"` in `native_contract()`;
  - `REWARD_VERSION = "reward_v4"`.

- [ ] **Step 1: Run** `.venv/Scripts/python.exe tools/mixed_traffic_report.py --out docs/reports/mixed-traffic-acceptance.json` in the background (1800 s cases with every-tick checks, about 30–60 min). Expected: the file is written.

- [ ] **Step 2: Check the safety and speed thresholds** against the file and `docs/reports/mixed-traffic-baseline-native-5.json`:
  - every case: `max_overlapping_pairs == 0`, `max_stuck_junction_vehicles == 0`, `max_gridlock_seconds == 0` and `final_vehicle_conservation_error == 0`;
  - `benchmarks.determinism_digest_equal` is `true`;
  - `cars_only_5j_medium_900s_runtime_s` ≤ 1.5 × the baseline;
  - `rl_env_decisions_per_second` ≥ 0.7 × the baseline.

  If any of these fails, stop. Fix it in the owning task's code (overlap: Tasks 7 and 9; speed: profile `_move_vehicle`), then rerun Step 1.

- [ ] **Step 3: Record the behaviour comparisons as measured.** For every case, note `front_row_motorcycle_share`, `queue_motorcycle_share` and `mean_discharge_first_10s`. Compare `2j-medium-tagum` with `2j-medium-tagum-nofilter`, and `5j-medium-tagum` with `5j-medium-cars`. These are not thresholds:
  - they go into the progress entry (Task 12) as they come out, including cases with no improvement;
  - never change provisional values to improve them;
  - check a surprising result for a bug first; if the mechanism is correct, report it as it is.

- [ ] **Step 4: RL scales.** Let `p` be the largest `queue_count_p95` or `active_count_p95` over the `tagum` cases.
  - If `p ≤ 30`: change nothing and note `p` in the progress entry (Task 12).
  - If `p > 30`:
    1. Set `MAX_QUEUE_COUNT` and `MAX_ACTIVE_VEHICLES` to the next multiple of 10 above `p`.
    2. Move the observation version into `rl_state.OBSERVATION_VERSION = "obs_v3"` and import it in the three training modules.
    3. Set `native_contract()["observation"]` to `"native-local-22-v3"` and `REWARD_VERSION` to `"reward_v4"`, because the reward normalises by `MAX_QUEUE_COUNT`.
    4. Add `test_observation_scales_cover_tagum_queues`, which reads `docs/reports/mixed-traffic-acceptance.json` and asserts `MAX_QUEUE_COUNT >= p`.
    5. Update the tests asserting the old strings.

- [ ] **Step 5: Run the full backend suite.** Expected: all pass.

- [ ] **Step 6: Commit**: "Record mixed-traffic acceptance results" (plus "and widen RL scales" if Step 4 changed them).

---

### Task 12: Release `native-6`

**Files:**
- Modify:
  - `simulation/traffic_engine.py` (`ENGINE_VERSION = "native-6"`);
  - `simulation/metric_definitions.json` (`"engine_version": "native-6"`);
  - `tests/test_native_cleanup.py` (expected engine);
  - `AGENTS.md` (`native-5` → `native-6` in the models line).
- Modify docs:
  - `docs/ARCHITECTURE_AND_PLAN.md`: decision **D29 — mixed-traffic sub-lane model, `native-6`**, and the current-contract lines;
  - `docs/PROGRESS_AND_HANDOFF.md`: a dated entry with the acceptance numbers;
  - `docs/FIELD_DATA_SMARTFLOW_INTEGRATION.md`: the "one modeled lane per permitted direction" and occupancy rows;
  - `docs/RESEARCH_METHOD.md`: a dated model note.
- Create: `tools/record_fixed_time_baselines.py`, `tests/test_record_baselines.py`

**Interfaces:**
- Produces: `tools/record_fixed_time_baselines.py --seed 101 --seconds 300 --confirm`.
  - It reads `SMARTFLOW_DB_PATH` like the app.
  - It backs up the database to `data/backups/smartflow_backup_<YYYYmmdd_HHMMSS>_pre_<engine>_baselines.db` with SQLite's backup API.
  - It records one pre-recorded fixed-time run per active scenario through `services.timeline_generator.generate_timeline`, then prints the run IDs.
  - Without `--confirm` it exits with status 2 and changes nothing.

- [ ] **Step 1: Write the failing test** in `tests/test_record_baselines.py`. Use an isolated scratch database (`SMARTFLOW_DB_PATH`) holding one scenario.
  - Without `--confirm`: the exit status is 2.
  - With `--confirm --seconds 30`: a backup file exists, and a completed fixed-time run is saved whose raw metrics have `experiment.engine_version == ENGINE_VERSION`.

- [ ] **Step 2: Run.** Expected: FAIL (missing tool).

- [ ] **Step 3: Implement the tool, bump the version strings and update the docs listed above.**
  - The progress entry records Task 11's behaviour comparisons as measured.
  - It also notes a follow-up: the manuscript revision guide's engine facts need updating, since it still says one lane per direction.
  - D29 and the research-method note state the accepted limitation. Exit storage counts vehicles end to end, so a road backed up with vehicles side by side counts as full early.

- [ ] **Step 4: Run the full checks.**
  - Backend: the full suite.
  - Frontend: `npx vitest run`, `npx tsc -b`, and `npx eslint` on every frontend file changed on this branch.
  - Expected: all pass.

- [ ] **Step 5: Browser check on the isolated 2-junction database.** In a live Tagum-mix run, confirm in 2D and 3D that:
  - motorcycles stand beside cars and gather at the stop line;
  - vehicles never overlap;
  - wide roads show their dividers.

  Save screenshots next to the 60 s frames of IMG_2511 and IMG_2516 for the owner's review.

- [ ] **Step 6: Ask the owner** before writing to `data/smartflow.db`. On approval, run `.venv/Scripts/python.exe tools/record_fixed_time_baselines.py --seed 101 --seconds 300 --confirm` and record the run IDs in the progress entry.

- [ ] **Step 7: Commit**: "Release the mixed-traffic engine as native-6".

- [ ] **Step 8: Whole-branch review.** Run a fresh review of `main...feat/mixed-traffic` on the most capable model before merging.

---

**Not in this plan:** calibration against field data (design Section 9, stage 6). It waits for confirmed sites and reviewed Field Observer measurements, and fits the provisional values in `simulation/mixed_traffic.py` and `TAGUM_PROVISIONAL_MIX`.
