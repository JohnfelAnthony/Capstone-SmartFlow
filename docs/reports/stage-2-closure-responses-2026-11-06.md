# Stage 2: clickable junction, closure responses and the narrower routing rule (D35), 6 November 2026

**Evidence kind: synthetic demand only.** Seeded demand with the provisional Tagum vehicle mix on provisional OpenStreetMap geometry; no field counts, no calibration. Development seeds 101-105 only. Engine `native-10` (no new bump: stage 2 adds the nearest-exit diversion and a setting, and the version change for the whole piece of work is already `native-10`).

Screenshots (scratch database, built-in browser): [`stage2-2026-11-06/picker-site-a-west-piece-closed.jpg`](stage2-2026-11-06/picker-site-a-west-piece-closed.jpg) and [`stage2-2026-11-06/picker-site-b-entry-road-closed-wait.jpg`](stage2-2026-11-06/picker-site-b-entry-road-closed-wait.jpg). Runs: [`stage2-2026-11-06/product-path-overlap-runs.jsonl`](stage2-2026-11-06/product-path-overlap-runs.jsonl).

## What changed

**A. Clickable junction** (`src/components/closure-picker.tsx`, `JunctionMiniMap` in `src/simulation/junction-details.tsx`). The checkbox list is gone. The picker draws the real mini-intersection, the same component the dashboard uses in Signal phases (shared, not copied), from the site's visual network, before any run and with no render frame.
- One click closes a road direction, another reopens it; clicking both directions closes the road both ways. A closed direction turns red and the turns it removes are dashed.
- A switcher reaches every junction: Site A J1-J3 (the side street is at J2 and J3), Site B J1-J2. **Every road that can be closed today is reachable:** Site A 14 of 14 and Site B 14 of 14, counted in the browser (J1 shows 8 road directions at Site A, J2 and J3 6 each).
- Beside the drawing, in plain words for each closed direction: the street, the side of the site, the direction, how far from the junction ("west, 0-226 m out · eastbound"), what the closure means for drivers, whether a detour exists, its start and end times, and "How should traffic respond?". No lane ids.
- Each road direction is a button (`role="button"`, `tabindex`, `aria-pressed`, an `aria-label` that says open or closed); Enter or Space closes or reopens it (Enter checked in the browser). The words panel carries everything the drawing shows, and the drawing sits above it.
- Editing a saved scenario with closures shows them, with their recorded responses (checked in the browser). The refusal of a selection that leaves no legal movement is unchanged.

**B. Responses** (`simulation/closure_responses.py`; stored per closed lane in `engine_config.closure_responses`):

| response | when it is offered |
|---|---|
| Use the side street | the piece is not an entry road and every trip that normally uses it still has a route |
| Use the side street and avoid jams (adaptive) | same as above |
| Send to the nearest open exit | the piece is not an entry road |
| Vehicles wait until it reopens | an entry road (nothing has entered yet) |
| Share the other side | stage 3 |

The availability comes from the real routing check, not a list. Results: Site A's west and north pieces next to the loop get the two side-street choices plus the nearest exit; pieces with no detour (the east exit, the stubs) get the nearest exit only; a closed entry road gets waiting only; **Site B has no detour anywhere, so it never offers avoiding jams** (tested for every lane). Closing a road in both directions keeps the side street where a detour exists (it only loses sharing, in stage 3). The first available response is preselected. `validate_config` refuses, in plain words, a response that is unknown, set for a road that is never closed, or not available for it ("'Use the side street' does not work for this closed road (road3f); choose one of: send to the nearest open exit."). The response shows on the scenario card line and in the details, as "Capitol Circumferential Road · west, 0-226 m out · eastbound — whole run — Use the side street and avoid jams (adaptive)".

**Decisions I made:**
1. **Avoid jams is network-wide, so mixing is refused.** Choosing it for one closure and the plain side street for another is refused ("Avoiding jams applies to the whole scenario: choose 'Use the side street and avoid jams' for every closure that uses a side street, or for none"). The form enforces it by moving every side-street closure together when one is changed; a nearest-exit or waiting closure is independent. The form says so in the response hint ("This applies to the whole scenario, not only this road.").
2. **A recorded response that stops working is replaced by the default, visibly.** When a later closure removes the detour a recorded response relied on, the form replaces it by the first available response (seen in the browser: closing a second road changed two side-street closures to "nearest open exit"). Without this the server would refuse the save with no way to recover.
3. **Saved scenarios with closures and no recorded choice behave as today.** No response is written for them; the form shows the default selected and says "This scenario was saved without a choice; traffic behaves as it always did until you pick one."
4. **Site validation is always static.** `validation_engine` validates an "avoid jams" closure as the plain side street. Training and evaluation follow the saved choice, so they see the same traffic (tested through `SmartFlowRLEnv`).
5. **Reference recordings follow the scenario** (not forced static). You asked for them to stay static; a scenario without a closure records static, but one that chose to avoid jams would otherwise be compared against a reference with different traffic. If you want references forced static even then, it is one line in the recording tool; say so.

**C. The routing rule.** A study-site run with no closure is static even if saved adaptive; adaptive happens only in a scenario with a closure whose response is "avoid jams" (`validate_config` sets `routing_mode` from the responses, so every path agrees). `routing_mode` stays in both comparison keys. `fixed_routing_mode` in the options is replaced by `routing_follows_closure_choice`, and the scenario summary says "Drivers are rerouted around closed roads only, not around congestion" or "Avoid jams (adaptive): drivers steer around congestion as well as closed roads, in this whole scenario." The closed-roads list is no longer repeated in the summary (the details card already lists it).

**Nearest exit really diverts even where the loop exists.** An east-to-north trip normally goes straight through the study junction (`road1f`). With `road1f` closed, the side-street response takes the loop (1 trip, 0 diverted, 1 loop exit); the nearest-exit response sends it to the nearest open exit instead (1 trip, 1 diverted, 0 loop exits), both when the road is closed from the start and when it closes after the vehicle is underway.

## Tests (failing first)

`tests/test_closure_responses.py` (new, 20 tests): availability per case, refusals, the routing rule, nearest exit, the closure-check payload, validation and training. Watched fail before the engine and report changes: both nearest-exit diversion tests, the closure-check payload test and the mixing refusal (which first failed with a different message because my chosen pair did not offer the side street). `src/lib/closures.test.ts` (+4): choosing, mixing, settling. Updated: `tests/test_closure_check.py`, `tests/test_study_site_static_routing.py`.

## Product-path overlap runs (replacing the "test harness only" adaptive runs)

`tools/loop_overlap_matrix.py` now builds every engine from a scenario record through `engine_for_scenario` and `apply_controller`, and sets nothing on the engine afterwards. Site A, medium traffic, the west piece (`road2r`) closed 300-1,200 s, 1,800 s, seeds 101-105, every tick, whole network:

| response | control | routing mode | overlap episodes | stalled | stuck | completed | loop exits | reroutes |
|---|---|---|---|---|---|---|---|---|
| side street | no signal | static | 0 | 0 | 0 | 449-534 | 60-79 | 0-1 |
| side street | fixed-time | static | 0 | 0 | 0 | 382-419 | 44-60 | 0-1 |
| side street, avoid jams | no signal | **adaptive** | 0 | 0 | 0 | 456-534 | 67-86 | 0-5 |
| side street, avoid jams | fixed-time | **adaptive** | 0 | 0 | 0 | 419-476 | 77-100 | 2-7 |
| nearest exit | no signal | static | 0 | 0 | 0 | 449-534 | 60-79 | 0-1 |
| nearest exit | fixed-time | static | 0 | 0 | 0 | 387-474 | 60-79 | 0-1 |

**Total: 30 runs, 0 overlap episodes, 0 stalled, 0 stuck, 0 held.** What changed in traffic: avoiding jams sends more traffic through the loop than the plain side street (fixed-time 77-100 against 44-60 loop exits). The nearest-exit response reports 60-79 diverted vehicles and the same number of loop exits at this closure, because the nearest open exit for traffic from the west is the north exit through the loop (the only way out of the west stub); the east-to-north test above is the case where it differs from the loop.

## Test totals

Backend suite: 757 passed, 1 skipped, 3 xfailed (the same three as stage 1). Frontend 150 tests, `tsc -b` and `eslint .` clean.

## Not done or not checked

- **Share the other side** is not built (stage 3); the form does not offer it.
- **A live run with each response** is part of the stage 5 rehearsal; this stage tested the engine behaviour and the form, not a dashboard run.
- The browser pane was about 800 px wide, so the New Scenario sheet was narrower than the 700 px target; the drawing stacked above the words and fitted. I did not test the wider sheet or a mobile width.
- Duplicate lines in the details were fixed during the check; the details still show the developer "Advanced JSON" block and raw ids elsewhere (stage 5 removes them).
- The Site B picker was checked with an entry-road closure (waiting offered) and a link closure (nearest exit only); adaptive was not offered there, as intended.
