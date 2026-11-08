# Site A West → North loop and road closures: acceptance rerun, 5 November 2026

**Evidence kind: synthetic demand only.** Seeded demand with the provisional Tagum vehicle mix; no field counts. Site A's loop is provisional OpenStreetMap geometry, not field-checked, and its side streets start empty. Nothing here is field validation or a claim about real traffic.

This report **replaces** [`site-a-closure-acceptance-2026-11-04.md`](site-a-closure-acceptance-2026-11-04.md). That report's "zero overlaps" held only for the 16 runs it covered (seeds 101 and 102, static routing); an independent check found overlaps on the loop street at other seeds. Two defects were found and fixed, and the loop network changed (new fingerprint `91cf11fe…`), so the earlier numbers describe a network that is no longer installed.

- Engine `native-9`. Run on the code of the commit that adds this report.
- Machine-readable: [`site-a-closure-acceptance-2026-11-05.json`](site-a-closure-acceptance-2026-11-05.json) (40 runs), [`closures-2026-11-05/loop-overlap-matrix.jsonl`](closures-2026-11-05/loop-overlap-matrix.jsonl) (50 runs, final code), [`closures-2026-11-05/loop-overlap-matrix-bend-fix-only-30-runs.jsonl`](closures-2026-11-05/loop-overlap-matrix-bend-fix-only-30-runs.jsonl) (the first 30 runs of an earlier matrix, made before the second fix; kept because it shows one overlap).

## What was wrong

1. **Bodies swing off a bent lane (the overlaps on `road6`).** The engine models a vehicle as a straight rectangle centred on its lane and lets it sit as close as 0.1 m to the lane edge. On a bend its ends swing sideways by about length² / (8 × radius), so a bus, truck, car or tricycle on the inner lane pushed its ends into the opposing lane. The loop's bend was a quadratic Bézier with a radius of roughly 9–15 m. Two changes: the bend is now a **25 m circular arc** (`LOOP_BEND_RADIUS_M`), and a lane with a bend keeps bodies further from its edges (`TrafficEngine.lateral_limits`: each side gives up half of the longest body's swing, less the usual 0.1 m; lanes with no bend are unchanged). Neither change alone is enough: the engine rule on the old geometry still left 348 overlapping placements, and the arc alone left 1,206 (buses and trucks).
2. **A second defect, found by the first re-run: spawning behind a bus still in the junction.** The west stub `road4r` is only 14.9 m long. A bus was placed at its start while the bus ahead, already in the junction, still had its rear on the lane, because the entry check ignored vehicles on a connector. One overlap of 0.1 s at 200.3 s (seed 104, adaptive, medium fixed-time) in the first matrix. The entry check now counts a vehicle on a connector by its rear.

Failing tests, watched fail before the fixes (`tests/test_site_a_loop.py`): `test_opposing_bodies_never_overlap_anywhere_on_the_loop_street_bend` (1,460 overlapping placements before any fix) and `test_a_bus_entering_the_short_west_stub_waits_for_a_bus_still_leaving_it_through_the_junction`.

## Overlaps, every tick, all vehicles: seeds 101–105

`tools/loop_overlap_matrix.py` checks every 0.1 s tick for any two overlapping bodies anywhere on Site A: 50 runs on the final code. The study-junction-closed case is 600 s; the others are 1,800 s. **The adaptive column cannot be produced by the product** (see below): those runs set `engine.config["routing_mode"]` directly after the engine is built, to show how the loop fares if congestion rerouting were allowed.

| case | static: runs / overlap episodes | adaptive (test harness only): runs / overlap episodes |
|---|---|---|
| high fixed, no closure | 5 / 0 | 5 / 0 |
| medium no signal, west closed 300-1200 s | 5 / 0 | 5 / 0 |
| medium fixed, west closed 300-1200 s | 5 / 0 | 5 / 0 |
| high no signal, west closed 300-1200 s | 5 / 0 | 5 / 0 |
| medium no signal, study junction closed from 0 s | 5 / 0 | 5 / 0 |

**Total: 50 runs, 0 overlap episodes.** For comparison, the independent check before the fixes found overlaps in 9 of 15 runs. The first matrix (bend fix only; 30 of 50 runs finished before it was replaced) had 1 overlap episode, the stub case above.

## Acceptance targets: 8 cases × 5 seeds = 40 runs, 1,800 s, static routing

`tools/mixed_traffic_report.py --only siteA-static`. **Met in all 40 runs:** `max_overlapping_pairs` 0, `max_stuck_junction_vehicles` 0, `max_gridlock_seconds` 0, `final_vehicle_conservation_error` 0. Determinism: both builds of the two medium closure cases at seeds 101 and 102 gave equal state digests over 120 s and over the full 1,800 s.

Range over the five seeds (min–max):

| case | completed | unfinished | loop exits west→north | reroutes | max held at a closed exit |
|---|---|---|---|---|---|
| medium, no signal, no closure | 444–534 | 17–39 | 0 | 0 | 0 |
| medium, no signal, west piece closed 300–1,200 s | 444–504 | 17–98 | 57–69 | 0–1 | 0 |
| medium, fixed-time, no closure | 341–396 | 115–192 | 0 | 0 | 0 |
| medium, fixed-time, west piece closed 300–1,200 s | 382–419 | 91–169 | 44–60 | 0–1 | 0 |
| high, no signal, no closure | 579–622 | 508–602 | 0 | 0 | 0 |
| high, no signal, west piece closed 300–1,200 s | 585–657 | 522–596 | 11–39 | 0–2 | 0–1 |
| high, fixed-time, no closure | 402–442 | 726–785 | 0 | 0 | 0 |
| high, fixed-time, west piece closed 300–1,200 s | 386–422 | 743–789 | 28–48 | 0–5 | 0–3 |

- **The loop works as a detour:** with `road2r` closed, 11–69 trips per run used it; with nothing closed no trip used it (all 20 no-closure runs show 0 loop exits, as static routing should).
- **Reroutes are few** because most closure traffic is routed round the loop at spawn; the mid-run reroute tests on the real network cover the rest.
- **High traffic is above Site A's capacity** with or without a closure; hundreds of requests wait at the boundary either way.
- **`max_closure_held_vehicles` is non-zero in some high-traffic closure runs** (up to 3, seed 104, fixed-time). Stuck vehicles stayed 0, so none was held more than 30 s; these are vehicles on the west stub at the moment it closes, before their first reroute check.

## Static routing at the study sites

The same review found that with nothing closed, adaptive routing at seed 103 put 9–24% of completed trips on the side street. Every run at a study site is now static (`validate_config`), so this report's runs are the product's behaviour. At the study sites "adaptive" means reacting to closures only, not to congestion.

## Limits and not checked

- Synthetic demand, provisional geometry, no field calibration. The loop street is 275 m; the 346 m survey figure includes 47 m of Capitol Circumferential Road.
- The same-lane bend limit is **not** closed in general: `tests/test_site_b_overlap_regression.py` still pins an isolated two-motorcycle case on the old Site B OSM corridor as failing. On the loop it is avoided because a bent lane leaves too little sideways room for two bodies to sit side by side.
- The extra edge clearance is a conservative constant per lane (it applies along the whole lane, not only at the bend) sized for the longest modelled body; it is a modelling choice, not a measurement. The 25 m radius is provisional.
- The 600 s closure-effects table in the 4 November report was not rerun on the new geometry.
- Only the west inbound piece was run at 1,800 s. The other three directions have no loop.
