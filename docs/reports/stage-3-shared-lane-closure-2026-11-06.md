# Stage 3: shared-lane closure, "Share the other side" (D36), 6 November 2026

**Evidence kind: synthetic demand only.** Seeded demand with the provisional Tagum vehicle mix on provisional OpenStreetMap geometry; no field counts, no calibration. **The arrangement itself is hypothetical**: it assumes cones, signs and usually an enforcer, and neither study site has one. Every screen says so.

Screenshots (scratch database, built-in browser): [`stage3-2026-11-06/picker-site-a-share-the-other-side.jpg`](stage3-2026-11-06/picker-site-a-share-the-other-side.jpg) (the clickable junction with the new response) and [`stage3-2026-11-06/live-map-site-a-shared-lane.jpg`](stage3-2026-11-06/live-map-site-a-shared-lane.jpg) (a live run with the west piece of Capitol Circumferential shared, amber).

## Design and what changed

When one direction of a road is closed, its traffic can drive on half of the opposite direction's existing pavement. That pavement then carries one lane each way, and the direction that stays narrows to its own half.

- **A fifth response, `share`** ("Share the other side (hypothetical)"), stored in `engine_config.closure_responses` like the others (`simulation/closure_responses.py`, `simulation/scenario_config.py`). A shared direction is not counted as closed when the scenario is checked for a legal movement. It is offered only where the road is eligible and the opposite direction is not closed, so never when both directions are closed.
- **Eligibility** (`simulation/contraflow.py`): two-way, at least 6.0 m per direction, at least 60 m long, and the change must not move a junction's stop line. Today that is Site A: Capitol Circumferential Road (`road2`) and Dalisay Gante Road (`road1`, `road3`); Site B: Sobrecarey (`road1`). Not eligible: Dao, Acacia, Bonifacio, Site A's side street, and the **Site B National Highway**, which is **not built** (its carriageways are one-way pairs with a median that can be crossed only at openings, so there is no opposite pavement to borrow; the form does not offer sharing there and `validate_config` refuses it).
- **Derived at run time; no network file or fingerprint changes.** `contraflow.shared_network` builds a copy of the base network with the road's centreline shifted by half its width toward the kept pavement, both lanes half as wide and two lanes, a 25 m smoothstep taper at each end (at most 40% of the length), the same lane ids, nodes, topology and junction clearance. The engine keeps `base_network` for fingerprints, saved scenarios, validation and model checks, and swaps `network` only when the closure starts and ends.
- **Drain, then swap.** At the closure time the two lanes are closed to new entry like any closed lane. Vehicles that need them reroute, or are diverted to the nearest open exit and counted in `diverted_vehicles` (or held, counted in `closure_held_vehicles`). Vehicles already on the lanes leave, and when both lanes and the connectors into them are empty the network changes. The same on the way back. New metrics `shared_lane_roads` and `shared_lane_changing_roads`; the frame carries `visual.shared_roads` only while a road is shared.
- **Where it shows.** Main map: amber half-width bands and a "Shared lane (hypothetical)" label. Signal phases mini-map and the Scenarios clickable junction: the closed pavement is amber and dashed rather than red, its turns stay available, with a note. The form words explain the arrangement and that the lanes are emptied first.
- **Traffic with it off is identical.** The closure-free digests (`tests/test_closure_free_digests.py`) and the pinned native-6 runs pass unchanged; a closure with no `share` response behaves as before. **The RL contract is unchanged** (`native-local-20-v4`, `phase-service-5-v2`): a shared direction is not in the closed set, so the signal's `closed_approach` rule does not apply to it (it applies only while the two lanes are draining, as for any closed lane). `tests/test_rl_contract_v4.py` passes.

Files: `simulation/contraflow.py` (new), `simulation/traffic_engine.py`, `simulation/closure_responses.py`, `simulation/scenario_config.py`, `simulation/road_network.py` (keeps its `clearance`), `simulation/metric_definitions.json`, `services/render_frame_service.py`, `database.py`, `services/scenario_migration.py`, `services/study_gate.py`, `services/training_settings.py` (the saved network fingerprint is the base network's), `src/api/simulation.ts`, `src/simulation/` (`frame-types`, `render-frame-adapter`, `scene-summary`, `junction-details`), `src/components/` (`closure-picker`, `simulation-canvas-2d`), `src/lib/closures.ts`, `src/index.css`, `tools/shared_lane_matrix.py` (new), `docs/ARCHITECTURE_AND_PLAN.md` (D36), `AGENTS.md`, `docs/PROGRESS_AND_HANDOFF.md`.

## Defects found and fixed on the way (each reproduced first)

1. **A scenario saved with a shared closure from t = 0 recorded the wrong fingerprint** (found in the browser: live start refused with "Scenario settings do not match network 'tagum_site_a'"). Cause: the engine was already on the derived network when the scenario was saved. Fix: every fingerprint use takes `base_network`. Red test `test_a_scenario_saved_with_a_shared_closure_from_the_start_records_the_base_networks_fingerprint_and_runs_again` failed first on the fingerprint, then on validating "Share the other side" against the already narrowed road (`configure()` validated against the derived network); both fixed.
2. **The live frame dropped `shared_roads`** (found in the browser: the engine reported a shared road but the map showed no amber). Cause: `services/render_frame_service._serialize_visual_payload` copies only known fields. Red test `test_the_live_frame_sent_to_the_map_carries_the_shared_road_and_stays_unchanged_when_nothing_is_shared` failed with `KeyError: 'shared_roads'`.
3. **Waiting for the draining lanes jammed the junction under fixed-time control.** My first drain let vehicles wait at the stop line for the draining lanes. In the first matrix, three of three fixed-time seeds at Site A finished **27-36% fewer trips than the same seed with no closure** (250/392, 259/374, 258/341), the network held 197 vehicles at 1800 s, and the road stayed shared for 1160-1360 s of a 900 s closure. Cause (seed 102, vehicle dump at 1500 s): blocked heads at the stop lines of road0r, road1r and road3r (all wanting the draining road2f) held whole queues. Fix: lanes being emptied are treated as closed for routing like any closed lane. After the fix, the same seed finishes 383 trips (no closure: 341) with 100 vehicles in the network. The failing evidence is kept in `stage3-2026-11-06/superseded-wait-during-drain/`. **No unit test locks this; the fixed-time matrix runs are the evidence.** The trade-off is in "Decisions" below.

## Tests

New: `tests/test_contraflow.py` (10: eligibility, derived geometry, junction clearance unchanged, strip geometry, refusal of ineligible roads) and `tests/test_contraflow_engine.py` (9: both directions flow while shared, with 12 of 12 trips completed and none diverted or held; the road returns to normal; the road changes only once every vehicle on its two lanes has left; a closure from the start shares at once; no response keeps the old behaviour; two busy directions never overlap at medium density; the base network is untouched; the fingerprint test and the live-frame test above). `tests/test_closure_responses.py` was updated for the new response (Site B offers sharing only on Sobrecarey; refusal for a narrow road; a shared direction is not counted closed).

Totals on the final code: **full backend suite 779 passed, 1 skipped, 3 xfailed (the same three as before, including the known side-by-side freeze, whose filtering I did not change), 44 min**; frontend `tsc -b` clean, `eslint src` clean, `vitest` **150 passed**. (An earlier full run on the code before fix 3 and the render-frame fix: 777 passed, 1 skipped, 3 xfailed.)

## Overlap, stuck, stall and conservation checks with it on

`tools/shared_lane_matrix.py` builds each run from a scenario record through the product path (`engine_for_scenario`, `apply_controller`), medium traffic and pedestrians, a 900 s closure from 300 s to 1200 s, 1800 s runs, overlap checked at **every tick**. Then the same seed with nothing closed. Raw lines: `stage3-2026-11-06/shared-lane-runs-no-signal.jsonl` and `shared-lane-runs-fixed-time.jsonl`.

**25 runs: 0 overlapping pairs, 0 stalled vehicles, 0 stuck junction vehicles, conservation error 0 in every run.** Seeds 101-105 at Site A (no-signal), 101-103 at Site B (no-signal; the site is heavier and each run takes 30-60 min), and fixed-time at Site A road2r seeds 101-103 and Site B road1r seed 101 only (fewer seeds than asked for fixed-time).

| site | closed (shares) | control | seeds | closed direction: mean crossing-time ratio (range) | kept direction: mean ratio (range) | mean trips done, shared vs none | mean seconds shared (closure lasts 900 s) | max diverted |
|---|---|---|---|---|---|---|---|---|
| A | road1f | no-signal | 5 | 1.03 (0.95-1.11) | 1.03 (0.85-1.20) | 491 vs 490 | 914 | 6 |
| A | road2r | fixed-time | 3 | 0.72 (0.54-0.87) | 1.05 (1.02-1.07) | 411 vs 369 | 1146 | 6 |
| A | road2r | no-signal | 5 | 0.99 (0.72-1.16) | 1.04 (1.02-1.07) | 492 vs 490 | 917 | 4 |
| A | road3f | no-signal | 5 | 1.04 (1.02-1.05) | 1.00 (0.82-1.17) | 492 vs 490 | 887 | 30 |
| B | road1f | no-signal | 3 | 1.02 (1.01-1.02) | 1.17 (0.99-1.40) | 445 vs 442 | 919 | 18 |
| B | road1r | fixed-time | 1 | 0.84 (0.84-0.84) | 0.93 (0.93-0.93) | 281 vs 268 | 1353 | 77 |
| B | road1r | no-signal | 3 | 0.99 (0.97-1.04) | 1.01 (1.01-1.02) | 433 vs 442 | 902 | 15 |

"Crossing-time ratio" is the mean time vehicles that entered that lane during the closure took to cross it, divided by the same measure for the same seed with nothing closed. It is a noisy measure (30-75 vehicles per cell, about +/-15% per seed) and only counts vehicles that left the lane. **At medium demand the shared pavement costs no measurable slowdown at Site A under no-signal control** (ratios about 1.0 for both directions, trips completed within 1% of no closure), because the pieces are lightly loaded. I did not test a saturated road. Under fixed-time control the closed direction's ratio is below 1 (0.54-0.87): that comes from queue timing at the signal, not a faster road, and should not be read as a benefit.

Per run (shared run; "none" is the same seed with nothing closed):

| site | closed (shares) | control | seed | trips done shared / none | seconds shared | overlaps | stalled | stuck at junction | held (max) | diverted | conservation | crossing time vs none: closed dir (n) / kept dir (n) |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| A | road1f | no-signal | 101 | 495 / 492 | 938.4 | 0 | 0 | 0 | 6 | 2 | 0 | 1.08 (61) / 1.05 (68) |
| A | road1f | no-signal | 102 | 449 / 449 | 893.0 | 0 | 0 | 0 | 0 | 2 | 0 | 1.11 (58) / 0.85 (55) |
| A | road1f | no-signal | 103 | 473 / 473 | 917.7 | 0 | 0 | 0 | 5 | 6 | 0 | 0.95 (49) / 0.9 (51) |
| A | road1f | no-signal | 104 | 534 / 534 | 917.7 | 0 | 0 | 0 | 2 | 3 | 0 | 0.98 (66) / 1.17 (62) |
| A | road1f | no-signal | 105 | 503 / 503 | 902.1 | 0 | 0 | 0 | 0 | 0 | 0 | 1.05 (57) / 1.2 (66) |
| A | road2r | fixed-time | 101 | 424 / 374 | 1074.9 | 0 | 0 | 0 | 8 | 3 | 0 | 0.54 (51) / 1.05 (28) |
| A | road2r | fixed-time | 102 | 383 / 341 | 1354.5 | 0 | 0 | 0 | 7 | 0 | 0 | 0.76 (55) / 1.07 (37) |
| A | road2r | fixed-time | 103 | 426 / 392 | 1009.1 | 0 | 0 | 0 | 15 | 6 | 0 | 0.87 (39) / 1.02 (28) |
| A | road2r | no-signal | 101 | 496 / 492 | 914.7 | 0 | 0 | 0 | 3 | 2 | 0 | 1.16 (65) / 1.02 (58) |
| A | road2r | no-signal | 102 | 455 / 449 | 877.4 | 0 | 0 | 0 | 0 | 0 | 0 | 1.03 (61) / 1.07 (59) |
| A | road2r | no-signal | 103 | 473 / 473 | 884.7 | 0 | 0 | 0 | 4 | 2 | 0 | 0.72 (53) / 1.03 (57) |
| A | road2r | no-signal | 104 | 534 / 534 | 983.3 | 0 | 0 | 0 | 6 | 4 | 0 | 1.13 (73) / 1.04 (61) |
| A | road2r | no-signal | 105 | 503 / 503 | 923.3 | 0 | 0 | 0 | 1 | 2 | 0 | 0.93 (65) / 1.06 (75) |
| A | road3f | no-signal | 101 | 496 / 492 | 910.0 | 0 | 0 | 0 | 3 | 13 | 0 | 1.05 (54) / 1.02 (66) |
| A | road3f | no-signal | 102 | 455 / 449 | 838.1 | 0 | 0 | 0 | 2 | 10 | 0 | 1.04 (46) / 0.99 (65) |
| A | road3f | no-signal | 103 | 473 / 473 | 843.6 | 0 | 0 | 0 | 1 | 18 | 0 | 1.02 (47) / 0.82 (58) |
| A | road3f | no-signal | 104 | 534 / 534 | 950.4 | 0 | 0 | 0 | 6 | 30 | 0 | 1.04 (50) / 1.17 (69) |
| A | road3f | no-signal | 105 | 503 / 503 | 892.4 | 0 | 0 | 0 | 0 | 11 | 0 | 1.05 (63) / 0.99 (66) |
| B | road1f | no-signal | 101 | 446 / 448 | 963.3 | 0 | 0 | 0 | 2 | 18 | 0 | 1.01 (45) / 1.4 (44) |
| B | road1f | no-signal | 102 | 438 / 433 | 901.7 | 0 | 0 | 0 | 0 | 8 | 0 | 1.02 (31) / 1.12 (31) |
| B | road1f | no-signal | 103 | 450 / 444 | 891.2 | 0 | 0 | 0 | 1 | 15 | 0 | 1.02 (31) / 0.99 (36) |
| B | road1r | fixed-time | 101 | 281 / 268 | 1352.6 | 0 | 0 | 0 | 11 | 77 | 0 | 0.84 (44) / 0.93 (14) |
| B | road1r | no-signal | 101 | 426 / 448 | 916.0 | 0 | 0 | 0 | 2 | 15 | 0 | 1.04 (44) / 1.01 (47) |
| B | road1r | no-signal | 102 | 426 / 433 | 905.1 | 0 | 0 | 0 | 0 | 9 | 0 | 0.97 (31) / 1.02 (30) |
| B | road1r | no-signal | 103 | 447 / 444 | 885.4 | 0 | 0 | 0 | 1 | 14 | 0 | 0.97 (36) / 1.01 (32) |

## Decisions I made

1. **Derive at run time, swap the network.** No network file or fingerprint changes were needed, so I did not stop to ask.
2. **Site B National Highway is not built.** One-way carriageway pairs with a median crossed only at openings do not have an opposite pavement; sharing them would need a different arrangement. Sobrecarey (Site B `road1`) is eligible and tested.
3. **Draining lanes are closed for routing, so vehicles divert or are held (fix 3).** The cost: some trips end at a different exit while a road changes (up to 30 of about 534 trips per run at Site A no-signal, 77 in the one Site B fixed-time run, counted in `diverted_vehicles`; held vehicles up to 15). The alternative (waiting) keeps every trip but jammed the junction under fixed-time. A choice for you: wait under first-come control and divert under a signal.
4. **The shared direction is not "closed" for the signal** while the road is shared.
5. **Widths are provisional OpenStreetMap values**, so which roads are eligible may change with measured widths.

## Not fixed, not checked

- **A standing queue at the end of the closure drains slowly.** At Site A under fixed-time the road stayed shared 1009-1354 s of a 900 s closure (drain at the junction's discharge rate); under no-signal it drains in seconds to a minute.
- Fixed-time runs: only 3 seeds at Site A road2r and 1 at Site B road1r. Other roads under fixed-time, any trained-model control (QL/DQL/PPO) and saturated roads are untested.
- The amber strip drawn in the clickable junction before a run is an approximation (the engine's own geometry is used during runs). The live-map screenshot was taken before fix 3 (drawing is unaffected).
- Stages 4 and 5 not started.
