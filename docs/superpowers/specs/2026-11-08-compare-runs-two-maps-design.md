# Compare Runs: two maps side by side (and RL Training clean-up)

Date: 2026-11-08. Status: design for owner approval. Part 1 is a project; Part 2 is a small, separate clean-up.

## Part 1: Compare Runs

### Why

The owner wants Compare Runs to "focus on showing the 2 simulations and comparing them". Today the page never shows a simulation. It shows a stat strip, two cards of run identifiers (seeds, SHA-256 hashes), two "frame" cards with queue bars, three line charts and a KPI table. A viewer cannot *see* how an RL signal and the no-signal or fixed-time baseline behave differently, which is the point of the capstone's three-way comparison. Recorded timelines already store full engine state per frame (vehicles, pedestrians, signals), so the maps can be shown.

### Goals

1. Two maps play the paired recordings side by side, in step, as the main view of the page.
2. A viewer can tell at a glance which run is which (by controller, not "Left/Right") and which is better on each metric, and by how much.
3. One shared player: play/pause, speed, and a time scrubber in seconds.
4. The metric charts follow the playback position.
5. Run identifiers (hashes, seeds, demand source) stay available for checking, but out of the way.

### Non-goals

- No change to which runs may be paired. `compare_kind` and the compatibility key stay the authority (same network, demand, seed and duration; signal controller or routing changes, not both; D39 warm-up pairing).
- No overall winner or single score. The page keeps showing per-metric trade-offs, as today.
- No live (unrecorded) comparison; only completed pre-record runs, as today.
- No new metrics, no new recording format, no engine change.

### Anti-goals (a failure even if it works)

- Hiding the existing warnings: safety-check failures (stalls, overlaps), unfinished vehicles, and the "synthetic or field-count demand, not calibrated or validated" notice must stay visible when a pair loads.
- Maps drifting out of step: both maps must always show the same simulation time.
- Loading so much data that the page stalls on a normal recording.
- Making the RL run look better through presentation, for example a colour or ordering that implies a winner on metrics where it loses.

### Constraints

- Frontend: React/TypeScript, the existing 2D map component `SimulationCanvas2D` (`src/components/simulation-canvas-2d.tsx`, props `frame`, `geometry`, `presentation`), `normalizeSceneGeometry` for the network, existing shadcn components and Recharts.
- Backend: FastAPI. Recorded frames are read the way `read_compare_frames` already reads them (`backend/main.py`, JSON lines, optionally gzip, cached by file mtime and size). Render payloads are built with `build_render_frame` (`services/render_frame_service.py`), which already enforces a per-frame byte budget.
- Pairing and alignment: frames are matched on shared simulation times, as `compare_pair_response` already does.
- Permission: `compare:view`, as the existing endpoints.
- Both runs are on the same network (guaranteed by pairing), so one network geometry serves both maps.

### The page, top to bottom (owner asked for this focus; layout details are my call)

1. **Header.** Title and a one-line description. The Refresh button stays.
2. **Picker bar.** One row: "Baseline" run select, a swap button, "Compare with" select (compatible runs only, as now), and a chip saying what matches (scenario, seed, duration) and what differs (signal controller or routing). The pair loads automatically when both are chosen; the "Load Pair" button goes away. Run labels in the selects lead with the controller name.
3. **Warnings.** The pair's warnings from the API, shown as alerts directly under the picker (safety failures as destructive alerts). Before a pair loads, an empty state explains what to pick.
4. **Two maps.** Equal width side by side on desktop, stacked on narrow screens. Each map's header names its controller ("No signal", "Fixed-time", "RL: PPO #12"; use the existing `controlLabel`/`runModeLabel`). A small overlay on each map shows the current phase, vehicles in the network and the queue at the study junction for that frame (my call: the sum of the four approach queues the condensed frames already carry).
5. **Player.** Directly under the maps: play/pause, speed 1×, 2×, 4×, a scrubber labelled in simulation seconds ("85 s / 300 s"), and keyboard support (space to play/pause, arrows to step). Playback speed follows simulation time, not a fixed delay per frame.
6. **What changed.** One card per KPI already in `kpiRows` (wait, queue, max queue, throughput, travel time, pedestrian delay, and the others listed): baseline value → compared value, the difference, and an arrow coloured by whether the change is better for that metric (`lowerIsBetter`), neutral when the metric has no direction or a value is unavailable. Unavailable stays "—", never zero. `MetricDefinitions` stays.
7. **Chart.** One chart with tabs (wait, queue, throughput), both runs as two lines, and a vertical line at the current playback time. Clicking the chart seeks the player.
8. **Run details.** A closed disclosure ("Run details") with the current identifiers for both runs: run id, scenario, controller, model id and SHA-256, demand source and SHA-256, network SHA-256, seed, duration, step.

Removed: the stat strip (frames, synced duration, comparison type, network), the separate notice bar, the two "Frame" cards and the three-chart grid.

### Data the maps need (new endpoint)

Add an endpoint that returns render frames for a pair over a time window, for example `GET /api/compare/pair/frames?left_run_id=&right_run_id=&start=&end=`. It validates the pair exactly as `compare_pair_response` does, reads both recordings, keeps shared times only, and returns `{times, left: [RenderFrame], right: [RenderFrame]}` built with `build_render_frame`. The existing `/api/compare/pair` stays for metrics, warnings and the condensed frames that drive the chart. The page loads the network geometry once for the pair's network, through the existing `/api/visual-network?network_id=` endpoint.

Loading strategy is the builder's call within these limits: the first frames should appear within about two seconds for a five-minute recording on this machine, and the page must not request a whole long recording in one response. Fetching a window ahead of the playback position (and on seek) is the expected shape.

### Fixes to carry over (found in the current page)

- The right-side throughput line reads `interpreted_metrics.throughput` while the left reads `throughput`; both must read the same field.
- The chart text says recordings include warm-up; recordings made since D39 have none. My call: drop the sentence, and mention warm-up only if the pair's manifest records one.
- Playback advances one frame every 140 ms whatever the recording's step; speed must follow simulation time.

### Left to the builder

- Linked pan and zoom between the two maps (wanted; the map component keeps its camera internally, so the builder decides how to share it, or ships without linking and says so).
- Chunk size, prefetching and caching of render frames.
- Exact component split, file names and CSS.
- Whether the swap button also swaps the chart colours (keep the baseline colour on the baseline run either way). Pairing is symmetric, so swapping needs no new compatibility check.

### Done means

- With a paired no-signal and RL recording at Site A, both maps play in step at 1×, 2× and 4×, scrubbing and keyboard work, the chart cursor follows, and every KPI card matches the existing KPI table's numbers for the same pair.
- A pair whose run failed a safety check shows that warning above the maps.
- Backend tests cover the frames endpoint: pair validation (refuses incompatible pairs and the same run twice), shared-time alignment and windowing. Frontend tests cover the KPI direction colouring and "—" for unavailable values.
- Checked in the browser at desktop and phone width.

## Part 2: RL Training clean-up (small change, separate from Part 1)

Order (my call): Part 2 first, since it is small and independent; Part 1 after.

Found on `src/components/rl-training-page.tsx` and the owner's screenshot:

1. Button wording is mixed ("Start Queue", "Stop active job", "Start new training", "Resume Selected", "Evaluate Selected"). Use one style (sentence case, as most of the app). "Start new training" only clears the resume choice; rename it to what it does (for example "Clear resume selection").
2. "Resume Selected" stays enabled with nothing selected; disable it like "Evaluate Selected".
3. Reward Progress shows an empty dashed box with no message; show an empty state. With several algorithms queued, their rewards are drawn as one line; draw one line per algorithm.
4. Job #3 reads "Interrupted" while its PPO item reads "Error"; show the same word for the same outcome. "Completed" uses a grey badge; give success its own (green) style.
5. Dates have no year and SQLite UTC times are read as local time; show the year when it is not the current year and parse UTC (as Settings now does).
6. Empty values show "--"; use "—" as other pages do.
7. The "Recorded −wait (s)" header is unclear; name it plainly (for example "Mean stopped wait (s)", shown as a positive number) and shorten the Trained Models description.
8. The stat strips on Audit Logs, Compare Runs and RL Training are styled three different ways; RL Training should use the same strip as Audit Logs and Settings.

Done means: the page reads consistently, the existing RL tests pass, and the owner's screenshot cases (interrupted jobs, empty chart, no models) look right in the browser.
