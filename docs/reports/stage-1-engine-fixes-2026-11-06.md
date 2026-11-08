# Stage 1 engine fixes (engine `native-10`): evidence report, 6 November 2026

**Evidence kind: synthetic demand only.** Seeded demand with the provisional Tagum vehicle mix on provisional OpenStreetMap geometry; no field counts, no calibration. Nothing here is field validation or a claim about real traffic. Development seeds 101-108 only.

Machine-readable runs: [`stage1-2026-11-05/acceptance-runs-final.jsonl`](stage1-2026-11-05/acceptance-runs-final.jsonl) (111 runs, 1,800 s each). Earlier partial files stay beside it as the record of what was run: `acceptance-runs-part1.jsonl`, `...-part2-earlier-alarm.jsonl`, `...-part3-before-held-fix.jsonl`, `...-part4.jsonl`, `...-part5.jsonl`, `...-part6.jsonl`.

## What was wrong, what changed, and the test that failed first

| # | Cause | Change | Test that failed first |
|---|---|---|---|
| 1 | **Site B overlap** (seed 102, high traffic, fixed-time, 333.9 s; a truck and a motorcycle on `road2f`). The truck had committed to its left turn and was still driving up to the line. The motorcycle beside it, with its front ahead of the truck's, edged sideways into the swing of the truck's rear, because `_committed_sweeps` ignored every committed vehicle behind it on its own lane. | Only a committed vehicle behind it **in its own sideways band** is ignored (it is queued behind and cannot pass). One in another band is free to go, and its sweep is respected. | `test_a_motorcycle_does_not_drift_into_the_path_of_a_truck_already_committed_beside_it` (overlap at 3.1 s) |
| 2 | **Same-lane overlap on a bend** (the strict xfail `test_two_motorcycles_on_a_bend_keep_their_world_footprints_separate`). Spacing compares sideways bands measured along the lane, which is not enough where the lane turns. | On a bent lane (bodies swing more than 0.2 m sideways) a forward move is cut to the longest of travel, travel/2 ... travel/16 whose body clears every vehicle **ahead** of it on the lane. Only the vehicle behind is held, so no two wait for each other. The experimental guard (`tools/site_b_guard_prototype.py`), which held opposing cars against each other, stays an xfail. | the existing strict xfail, now an ordinary passing test |
| 3 | **Permanent deadlock at the Site A west stub** (seed 108, medium, no signal, side street closed 500-800 s; 958 s frozen). Three vehicles side by side at the line: the earliest was held by the last, which stood in its path; the last waited for the middle one's earlier place; the middle one waited for the earliest. `_must_wait_at_line` let a vehicle go first only when it stood in the earlier one's path directly (one hop). | It also lets a vehicle go first when the earlier one is held by **any** standing vehicle (`_sweep_blocked`). | `test_vehicles_side_by_side_at_the_stub_line_for_the_narrower_loop_all_get_through` (0 of 3 through in 120 s) |
| 4 | **The alarms missed it.** `stuck_junction_vehicles` needs a reservation and `gridlock_seconds` needs no movement anywhere. | New metric `stalled_vehicles` (see the alarm section). | `tests/test_stalled_vehicles.py` |
| 5 | **Stuck read vehicles that had only stood at a red** when a closure began (Site B road2 closed at 300 s read 2, cleared by 310 s). | A vehicle held at a closed exit counts as stuck only after it has been **held** for 30 s (`held_for`), not after standing for 30 s. | `test_a_vehicle_that_waited_at_a_red_before_its_exit_closed_is_not_stuck_the_moment_it_closes` |
| 6 | **One-tick overlap at the study junction** (Site A, medium, fixed-time, west and side street closed, seed 101, 1035.0 s; a bus in its turn and a motorcycle at the line). The commit test excused any committed stander on the vehicle's own approach as "about to drive off". The motorcycle was committed and moving when the bus committed (it was in the **other** sideways band: lateral 0.2 against the bus's -1.89), then sweeps ahead of it held it 3.6 m past its stop line, inside the swing of the bus's rear. | Only a committed stander in the vehicle's **own band** is excused. | `test_a_bus_does_not_start_its_turn_beside_a_committed_motorcycle_that_is_then_held_in_the_bus_path` (overlap at 6.3 s, with positions 48.72 / 49.67 against the traced 48.67 / 49.49; passes with the fix). My first version of this test held the motorcycle still from the start and did not reproduce the real case (the real motorcycle was moving at the moment of commit); it passed with a fix that changed nothing in the real run. It is replaced. |

The engine is `native-10` (see D34 in `docs/ARCHITECTURE_AND_PLAN.md`). The six closure-free digests in `tests/test_closure_free_digests.py` did not move, so none was re-pinned.

## The `stalled_vehicles` alarm: the three questions

The metric counts a vehicle on a lane that has stood for more than 60 s with nothing that legitimately holds it: no vehicle or turning body ahead, no red or yellow for its approach, no closed or full exit, no reservation. Somebody inside the junction or pedestrians on the crossing only **pause** the count (it is not reset, so a deadlock that looks explained now and then still adds up). A wait behind a full or closed exit is explained only if that exit's own head will move.

1. **Does it still fire with the stub fix reverted?** Yes. The seed 108 case with the fix reverted: first stalled at 946 s, three vehicles stalled at 1,800 s (`stalled_at_end` 3), `gridlock_seconds` 0. With the fix: first and maximum 0. (While building the refinement a version that **reset** the count on an exit-hold explanation read 0 at the end of that same run, which is why the count now pauses instead.)
2. **Can the "explained by a full exit" chain loop back or never end?** It is followed. `_full_exit_clears` returns "does not clear" for a lane already on the chain (each exit full because of the next), and for a head at the end of the network with nothing holding it; it returns "clears" for a moving head, a closure, a red, a junction in use or a pedestrian crossing, or a full exit further on that clears in turn. `test_a_full_exit_whose_own_head_is_going_nowhere_does_not_explain_the_wait` covers the loop and the dead end.
3. **Site A seed 101 (high traffic, no signal, west closed): does the exit it waits on clear, and for how long?** The first run flagged one stalled vehicle: the head of the west stub, bound for the loop street. It was stopped **504 s** at the end of the run (since about 1,296 s). The loop street (`road6f`) held 52 vehicles over its 264 m, so its entry was full. Its head was a bus at the north loop junction, waiting its first-come turn behind earlier arrivals from the north stub (114 vehicles queued there); that junction was serving vehicles (one had stood only 19 s), so this is **saturation at the north loop junction, not a deadlock**. But a wait of over 8 minutes behind a full exit is a real jam, and the alarm deliberately calls it explained. At high traffic the loop street competes with a saturated first-come junction; that is a limit of the provisional loop, not something the engine fixes. In the final runs the same case reads `max_stalled_vehicles` 0 at seeds 101 and 102.

**Was an earlier "clean" run hiding a stall?** The seed 108 case on `main` was clean on every alarm that existed while a partial deadlock held the stub for 958 s; seeds 106 and 107 of that case ended with nothing waiting. Earlier acceptance reports (the 4 and 5 November Site A reports and `two-site-acceptance.json`) predate the alarm and were **not** re-checked with it; they are superseded for the Site A closure cases by the table below. High-traffic runs can hide a stall behind a long boundary wait only if the stalled vehicle has a leader or a full exit ahead, which the alarm resolves along the chain.

## Acceptance (111 runs, 1,800 s)

Targets: 0 overlaps, 0 stalled vehicles, 0 gridlock seconds, 0 conservation error, and 0 stuck vehicles except where the closure itself strands vehicles (a stuck count is excused only when the run also shows vehicles held at a closed exit; the stuck column shows the peak and the held column the peak held).

**One miss:** `siteA-static-medium-nosignal-road2-closed`, seed 105: **4 stalled vehicles** (two vehicles bound for the loop street, stopped 440 s from about 710 s). See "Unfixed". Every other run met every target.

| case | seeds | completed | overlaps | stuck (held) | stalled | gridlock | conservation |
|---|---|---|---|---|---|---|---|
| Site A medium no signal | 101,102 | 449-492 | 0 | 0 (0) | 0 | 0 | 0 |
| Site A medium no signal, west closed 300-1,200 s | 101,102 | 449-496 | 0 | 0 (0) | 0 | 0 | 0 |
| Site A medium fixed-time | 101,102 | 341-374 | 0 | 0 (0) | 0 | 0 | 0 |
| Site A medium fixed-time, west closed | 101,102 | 382-393 | 0 | 0 (0) | 0 | 0 | 0 |
| Site A high no signal | 101,102 | 585-590 | 0 | 0 (0) | 0 | 0 | 0 |
| Site A high no signal, west closed | 101,102 | 611-618 | 0 | 0 (1) | 0 | 0 | 0 |
| Site A high fixed-time | 101,102 | 405-429 | 0 | 0 (0) | 0 | 0 | 0 |
| Site A high fixed-time, west closed | 101,102 | 388-392 | 0 | 0 (1) | 0 | 0 | 0 |
| Site A medium no signal, road1 closed both ways | 101-108 | 448-534 | 0 | 0 (2) | 0 | 0 | 0 |
| Site A medium fixed-time, road1 closed | 101-108 | 388-457 | 0 | 0 (11) | 0 | 0 | 0 |
| Site A medium no signal, road2 closed | 101-108 | 321-534 | 0 | 0 (2) | **4 (seed 105)** | 0 | 0 |
| Site A medium fixed-time, road2 closed | 101-108 | 393-444 | 0 | 0 (6) | 0 | 0 | 0 |
| Site A medium no signal, side street closed during the west closure | 101-108 | 449-534 | 0 | 1 (1) | 0 | 0 | 0 |
| Site A medium fixed-time, side street closed during the west closure | 101-108 | 372-430 | 0 | 2 (2) | 0 | 0 | 0 |
| Site B medium no signal | 101-103 | 421-448 | 0 | 0 (0) | 0 | 0 | 0 |
| Site B medium fixed-time | 101-103 | 261-287 | 0 | 0 (0) | 0 | 0 | 0 |
| Site B high no signal | 101-107 | 432-503 | 0 | 0 (0) | 0 | 0 | 0 |
| Site B high fixed-time | 101,102 | 263-308 | 0 | 0 (0) | 0 | 0 | 0 |
| Site B medium no signal, road1 closed | 101-108 | 410-462 | 0 | 0 (2) | 0 | 0 | 0 |
| Site B medium fixed-time, road1 closed | 101-108 | 323-371 | 0 | 0 (11) | 0 | 0 | 0 |
| Site B medium no signal, road2 closed | 101-108 | 387-448 | 0 | 0 (7) | 0 | 0 | 0 |
| Site B medium fixed-time, road2 closed | 101-108 | 338-409 | 0 | 0 (5) | 0 | 0 | 0 |

Site B road2 is a one-way carriageway, so "closed" there closes its one lane. The side-street cases close the loop street (500-800 s) inside the west closure, so the west stub has no open way out for that time: vehicles on it are held by the closure, and a stuck count of 1-2 there is those vehicles, not a fault.

**What changed in traffic (the fixes' own effect).** Site A, medium, seeds 101-102: no signal 449-492 completed against 444-496 in the 4 November report, fixed-time 341-374 against 351-374; high traffic no signal 585-590 against 579-612. These are within normal seed variation. I did not compare Site B with an earlier report (the earlier Site B figures are for a different engine build and geometry), so I cannot say how the fixes moved Site B completions.

**Which code produced which runs.** The runs were made over several hours while the engine was being corrected, so they did not all run on the final code. Parts 1-3 and the clean part 4 runs (78 runs) were made before fix 6 (the band-based exemption) and before the alarm's last change; fix 6 can only withhold a commit and the alarm change affects only what is measured, but those 78 runs are not on the final code. Part 6 (33 runs) is on the final code. The closure-free digests pass on the final code. I did **not** re-run the 78.

## Unfixed

**Two vehicles side by side at the line can each stand in the other's turning path by a few centimetres, and then neither can start.** Found by the alarm at Site A, medium, no signal, road2 closed, seed 105 (a bus at lateral 1.1, pos 44.47, and a motorcycle at lateral 2.8, pos 48.47, both bound for the loop street; the motorcycle's path touches the bus by 0.05 m at 0.55 m of its turn, the bus's path touches the motorcycle at 1.45 m). Reproduced in a minimal two-vehicle scene (recorded as a strict xfail, `test_a_bus_and_a_motorcycle_whose_turning_paths_barely_touch_do_not_freeze_the_line`). I tried a sideways move for the blocked vehicle and removed it: the engine moves a body sideways only while it moves forward (a motorcycle's shuffle aside), so a stopped bus cannot move, and the motorcycle's only free side is the bus. Options for the owner: (a) forbid a later vehicle from stopping inside the turning path of a waiting earlier one (this would change filtering behaviour and probably the pinned digests); (b) allow a stopped vehicle a slow sideways creep when blocked (a change to the sub-lane model); (c) accept it as a rare limit at stressed closure cases (1 of 8 seeds here) and rely on the alarm. I made no choice.

## Not checked

- The 78 runs above on the final code; seeds 103-108 for the standard (non-added) cases; Site B high-traffic no-signal at seeds 108 and beyond; Site B high fixed-time at seed 103 (it read 1 stalled under the earlier alarm and was not repeated on the final code).
- The remaining `main`-only claim about seed 108 is from this branch's code with the fix switched off in the probe, not from `main` itself.
- The site validation gate's safety fields are unchanged: adding `stalled_vehicles` there changes its criteria hash, which is an owner decision.
- The old OSM corridor (a history network with sharp bends) still shows overlaps that are not same-lane; the general bend problem is reduced, not solved.
