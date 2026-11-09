# RL Training Clean-up and Compare Runs Two Maps Implementation Plan

> **Original implementation plan.** The live feature includes later changes to PDF reporting and playback startup. Use [progress](../../PROGRESS_AND_HANDOFF.md) for the implementation and verification record.

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the RL Training page consistent, then rebuild Compare Runs around two recorded simulations playing side by side with one shared player.

**Architecture:** Part 2 of the spec (RL clean-up) comes first: pure helpers in `src/lib` carry the testable logic and the page uses them. Part 1 adds one backend endpoint that returns windows of render frames for a validated pair, pure frontend helpers for deltas, playback time and windows, a slim `CompareMap` around the existing `SimulationCanvas2D`, and a rewritten `compare-runs-page.tsx`.

**Tech Stack:** React + TypeScript + Vite, shadcn components, Recharts, Vitest (node environment, `src/**/*.test.ts` only); FastAPI + pytest.

**Spec:** `docs/superpowers/specs/2026-11-08-compare-runs-two-maps-design.md`

## Global Constraints

- No change to which runs may be paired: `compare_kind` and the compatibility key stay the authority; no engine change, no new recording format, no new metrics.
- Keep every pair warning visible when a pair loads (safety failures, unfinished vehicles, "synthetic or field-count demand, not calibrated or validated").
- Unavailable values show "—", never zero; KPI direction is neutral when a value is unavailable or the metric has no direction (`lowerIsBetter === null`).
- No overall winner or single score.
- Both maps always show the same simulation time.
- Permission for new endpoints: `compare:view`.
- Backend tests: `.venv/Scripts/python.exe -m pytest <files> -q --basetemp "$TEMP/<dir>"`, isolated database via `patch.object(config, "DB_PATH", ...)` as in `tests/test_shared_session_and_import.py`.
- Frontend tests are pure functions in `src/lib/*.test.ts` (Vitest runs in node, no DOM). Component behaviour is checked in the browser step of each UI task.
- Frontend checks before every commit: `npx tsc -b --noEmit`, `npx eslint src`, `npx vitest run`.
- Commit messages end with `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`. Commit only the files the task names; the main checkout may hold another tool's uncommitted work.

## Review Focus

- A pair whose recordings share only some frame times: maps and chart show shared times only, never a frame from one run beside a different time from the other (Task 4 test).
- Seeking far ahead of or behind the loaded frames: the player fetches the window that holds the new time and never draws a stale frame (Task 5 test of `frameWindow` and `frameAtTime`).
- A KPI with an unavailable value on one side: "—" and a neutral tone, not a zero difference (Task 5 test of `kpiChange`).
- A long recording: the frames endpoint refuses a window longer than the limit, and the page asks in windows (Task 4 test).
- Changing the baseline while a pair plays: playback stops and both maps clear before the new pair loads (Task 8 browser step).

---

## Part 2: RL Training clean-up

### Task 1: Server dates, empty values and reward series helpers

**Files:**
- Create: `src/lib/display-format.ts`, `src/lib/display-format.test.ts`
- Create: `src/lib/reward-series.ts`, `src/lib/reward-series.test.ts`

**Interfaces:**
- Produces: `parseServerTimestamp(value: string | null | undefined): Date | null`, `formatServerDate(value: string | null | undefined, now?: Date): string`, `EMPTY_VALUE = "—"`, `rewardSeries(points: Array<{ algorithm: string; episode: number; reward: number }>): { data: Array<Record<string, number>>; algorithms: string[] }`.

- [ ] **Step 1: Write the failing tests**

```ts
// display-format.test.ts
expect(parseServerTimestamp("2026-11-06 10:04:00")?.toISOString()).toBe("2026-11-06T10:04:00.000Z") // SQLite UTC without zone
expect(parseServerTimestamp("2026-06-03T02:45:00+00:00")?.toISOString()).toBe("2026-06-03T02:45:00.000Z")
expect(parseServerTimestamp("not a date")).toBeNull()
expect(parseServerTimestamp(null)).toBeNull()
expect(formatServerDate("2026-06-03T02:45:00+00:00", new Date("2026-11-08T00:00:00Z"))).not.toMatch(/2026/) // same year: no year
expect(formatServerDate("2025-06-03T02:45:00+00:00", new Date("2026-11-08T00:00:00Z"))).toMatch(/2025/)
expect(formatServerDate(null)).toBe("Never")
// reward-series.test.ts
const series = rewardSeries([{ algorithm: "QL", episode: 1, reward: -5 }, { algorithm: "PPO", episode: 1, reward: -3 }, { algorithm: "QL", episode: 2, reward: -4 }])
expect(series.algorithms).toEqual(["QL", "PPO"])
expect(series.data).toEqual([{ episode: 1, QL: -5, PPO: -3 }, { episode: 2, QL: -4 }])
expect(rewardSeries([])).toEqual({ data: [], algorithms: [] })
```

- [ ] **Step 2: Run** `npx vitest run src/lib/display-format.test.ts src/lib/reward-series.test.ts`. Expected: FAIL, modules not found.
- [ ] **Step 3: Implement both modules.** `parseServerTimestamp` appends `Z` (after replacing the space with `T`) only when the string has no zone; `formatServerDate` uses `Intl.DateTimeFormat("en", { month: "short", day: "numeric", hour: "numeric", minute: "2-digit" })` and adds `year: "numeric"` when the year differs from `now`. Algorithms keep first-seen order; rows are sorted by episode.
- [ ] **Step 4: Run the same command.** Expected: PASS.
- [ ] **Step 5: Commit** `feat: add server date, empty value and reward series helpers`.

### Task 2: Apply the RL Training clean-up

**Files:**
- Modify: `src/components/rl-training-page.tsx`, `src/styles/rl-training.css`
- Modify: `src/components/settings-page.tsx` (replace its local `createdDate` with `parseServerTimestamp`)

**Interfaces:**
- Consumes: Task 1 exports.

- [ ] **Step 1: Make the changes, each tied to the spec's Part 2 list**
  1. Button labels in sentence case: "Start queue", "Stop active job", "Resume selected", "Evaluate selected"; "Start new training" becomes "Clear resume selection".
  2. "Resume selected" gets `disabled={!canRunTraining || !selectedModel?.compatible || Boolean(serverActiveJobId) || pendingAction}`.
  3. Reward Progress: when `rewardSeries(...).data` is empty, render the existing `Empty` component ("No rewards yet. They appear here while a job trains.") instead of the chart; otherwise one `Line` per algorithm, colours `var(--chart-1)` … `var(--chart-5)` in order, with a `Legend`.
  4. Job Items: under each item's status badge, show `item.message` in muted small text when the status is `error` or `interrupted` (the two words come from different records: an item that failed before the job was marked interrupted on restart; the message explains which). `StatusBadge` gives `completed` its own success style (add a `.rl-status-badge.completed` rule using `--primary`), keeping destructive for `error`/`interrupted`.
  5. Every `formatDate(...)` call uses `formatServerDate`; remove the local `formatDate`.
  6. `"--"` becomes `EMPTY_VALUE` in `selectedAlgorithmLabel`, `compactNumber` and the artifact cell.
  7. The models column header becomes "Mean stopped wait (s)" and its cell shows `Math.abs(model.best_evaluation_score)`; the Trained Models description becomes: "Pick a model to resume or evaluate. Lower wait is better; it is not an overall recommendation."
  8. The page's stat strip uses the Audit Logs classes (`audit-metric-strip`, `audit-strip-metric`) with `import "@/styles/admin-user-management.css"`; delete the `.rl-metric-strip`/`.rl-strip-metric` rules.
- [ ] **Step 2: Run the frontend checks** (Global Constraints). Expected: all clean, all tests pass.
- [ ] **Step 3: Check in the browser** with a scratch app (never `data/smartflow.db`): an interrupted job, an empty reward chart, no trained models, desktop and phone width.
- [ ] **Step 4: Commit** `fix: make the RL Training page consistent`.

---

## Part 1: Compare Runs, two maps

### Task 3: Pair validation shared by both compare endpoints

**Files:**
- Modify: `backend/main.py` (`compare_pair_response`, around line 1405)
- Test: `tests/test_compare_pair_frames.py` (create)

**Interfaces:**
- Produces: `validated_compare_pair(left_run_id: int, right_run_id: int) -> tuple[CompareRunOption, CompareRunOption, str]` raising the same `HTTPException`s `compare_pair_response` raises today (422 same run, 422 incompatible); `compare_pair_response` calls it.
- Test fixture: `record_pair(self, *, extra_left_frames: int = 0) -> list[int]`, built like `test_comparison_and_csv_export_trace_saved_values` (a single-car `TrafficEngine(seed=42)` run written as JSON lines plus manifest, two pre-record runs), with `extra_left_frames` appending frames at later times only to the left file.

- [ ] **Step 1: Write the failing test** `test_the_pair_refuses_the_same_run_and_an_incompatible_run` asserting `validated_compare_pair(a, a)` raises 422 and, after `database.update_run(b, seed=7)` (a different seed is never comparable), `validated_compare_pair(a, b)` raises 422.
- [ ] **Step 2: Run** `.venv/Scripts/python.exe -m pytest tests/test_compare_pair_frames.py -q --basetemp "$TEMP/cp1"`. Expected: FAIL, name not defined.
- [ ] **Step 3: Extract `validated_compare_pair`** from the first lines of `compare_pair_response` without changing behaviour.
- [ ] **Step 4: Run it and `tests/test_shared_session_and_import.py`.** Expected: PASS.
- [ ] **Step 5: Commit** `refactor: share compare pair validation`.

### Task 4: Render frames for a pair, by time window

**Files:**
- Modify: `backend/main.py`, `backend/schemas.py`
- Test: `tests/test_compare_pair_frames.py`

**Interfaces:**
- Consumes: `validated_compare_pair`, `build_render_frame` (`services/render_frame_service.py`).
- Produces: `GET /api/compare/pair/frames?left_run_id=&right_run_id=&start=&end=` returning `ComparePairFramesResponse { times: list[float]; left: list[dict]; right: list[dict]; duration: float }`; constant `COMPARE_RENDER_WINDOW_SECONDS = 60.0`.

- [ ] **Step 1: Write the failing tests**
  - `test_frames_cover_only_shared_times_in_the_window`: with `record_pair(extra_left_frames=5)`, a request for `start=0, end=1` returns equal-length `times`, `left`, `right`; every `left[i]["time"] == right[i]["time"] == times[i]`; no time from the extra left frames appears; `duration` equals the last shared time.
  - `test_frames_refuse_a_window_longer_than_the_limit`: `end - start = 61` returns 422; `end < start` returns 422.
  - `test_frames_refuse_the_same_run_twice`: the same run twice returns 422.
- [ ] **Step 2: Run** the test file. Expected: FAIL, 404 for the new route.
- [ ] **Step 3: Implement.** Read raw frames once per timeline file and cache the built render frames by `(resolved path, mtime_ns, size)` (an `functools.lru_cache(maxsize=4)` around a helper is enough); align on `round(time, 6)` exactly as `compare_pair_response` does; slice `start <= time <= end`; build each payload with `build_render_frame(raw, sequence=index)`. `Query(ge=0)` for `start` and `end`.
- [ ] **Step 4: Run** the test file and `tests/test_shared_session_and_import.py`. Expected: PASS.
- [ ] **Step 5: Commit** `feat: serve compare render frames by time window`.

### Task 5: Compare API client and pure comparison helpers

**Files:**
- Modify: `src/api/compare.ts`
- Create: `src/lib/compare-view.ts`, `src/lib/compare-view.test.ts`

**Interfaces:**
- Consumes: Task 4 response shape; `RenderFrame` from `src/simulation/frame-types.ts`.
- Produces:
  - `getComparePairFrames(leftRunId: number, rightRunId: number, start: number, end: number): Promise<ComparePairFramesResponse>` with `type ComparePairFramesResponse = { times: number[]; left: RenderFrame[]; right: RenderFrame[]; duration: number }`.
  - `kpiChange(left: number | null, right: number | null, lowerIsBetter: boolean | null): { delta: number | null; tone: "better" | "worse" | "neutral" }`.
  - `frameWindow(time: number, windowSeconds = 60): { start: number; end: number }` (window aligned to multiples of `windowSeconds`).
  - `frameAtTime(times: number[], time: number): number` (index of the last frame at or before `time`, `-1` if none).
  - `advancePlayback(time: number, elapsedMs: number, speed: 1 | 2 | 4, duration: number): { time: number; finished: boolean }`.
  - `studyQueue(queues: Record<string, number> | undefined): number`.

- [ ] **Step 1: Write the failing tests**

```ts
expect(kpiChange(10, 8, true)).toEqual({ delta: -2, tone: "better" })
expect(kpiChange(10, 12, true)).toEqual({ delta: 2, tone: "worse" })
expect(kpiChange(100, 120, false)).toEqual({ delta: 20, tone: "better" })
expect(kpiChange(null, 5, true)).toEqual({ delta: null, tone: "neutral" })
expect(kpiChange(3, 7, null)).toEqual({ delta: 4, tone: "neutral" })
expect(kpiChange(5, 5.00001, true).tone).toBe("neutral")
expect(frameWindow(0)).toEqual({ start: 0, end: 60 })
expect(frameWindow(135)).toEqual({ start: 120, end: 180 })
expect(frameAtTime([0, 0.5, 1], 0.7)).toBe(1)
expect(frameAtTime([10, 11], 5)).toBe(-1)
expect(advancePlayback(10, 500, 2, 300)).toEqual({ time: 11, finished: false })
expect(advancePlayback(299.5, 1000, 1, 300)).toEqual({ time: 300, finished: true })
expect(studyQueue({ north: 2, east: 0, south: 3, west: 1 })).toBe(6)
expect(studyQueue(undefined)).toBe(0)
```

- [ ] **Step 2: Run** `npx vitest run src/lib/compare-view.test.ts`. Expected: FAIL.
- [ ] **Step 3: Implement.** Neutral tolerance is `1e-4`, matching the current KPI table.
- [ ] **Step 4: Run it.** Expected: PASS.
- [ ] **Step 5: Commit** `feat: add compare frames client and comparison helpers`.

### Task 6: One map for one run

**Files:**
- Create: `src/components/compare-map.tsx`

**Interfaces:**
- Consumes: `SimulationCanvas2D`, `createPresentationState`, `SceneGeometry`, `studyQueue`, `controlLabel`.
- Produces: `CompareMap({ geometry, frame, title, runKey }: { geometry: SceneGeometry; frame: RenderFrame | null; title: string; runKey: string }): JSX.Element`.

- [ ] **Step 1: Implement.** A card with `title` in its header, the canvas (`onSelect` a no-op, presentation from `createPresentationState(geometry)`), and an overlay showing phase, vehicle count and `studyQueue` for the frame, or "Loading…" when `frame` is null. Pan and zoom are not linked between the two maps (the spec leaves this to the builder); say so in the commit message.
- [ ] **Step 2: Run the frontend checks.** Expected: clean.
- [ ] **Step 3: Commit** `feat: add the compare map card`.

### Task 7: Rebuild the Compare Runs page

**Files:**
- Modify: `src/components/compare-runs-page.tsx`, `src/styles/compare-runs.css`

**Interfaces:**
- Consumes: Tasks 4–6.

- [ ] **Step 1: Restructure the page in the spec's order.** Load the network geometry once per pair with `getVisualNetwork(networkId)` and `normalizeSceneGeometry`, where `networkId` is the pair's recorded `experiment.network_id` (falling back to the left run's `timeline.intersection_id`, as `StatStrip` does today). Then: header with Refresh; picker bar (Baseline select, swap button, Compare with select, match chip from `comparison_type` and the two options' scenario, seed and duration); the pair loads when both selects hold a value (remove the Load Pair button); warnings as `Alert`s (destructive for safety failures); two `CompareMap`s titled with `controlLabel(run.control_mode)` plus `#model_id` for RL runs; the player (play/pause, speed 1×/2×/4×, scrubber in seconds "85 s / 300 s", Space and arrow keys) driven by `requestAnimationFrame` and `advancePlayback`; frames fetched with `getComparePairFrames` for `frameWindow(time)`, plus the next window when `time` is within 10 s of its end, kept in a map keyed by window start; KPI cards from `kpiRows` using `kpiChange` and `formatMetric`; one chart with tabs (wait, queue, throughput), a `ReferenceLine` at the current time, and click-to-seek; "Run details" as a closed `Collapsible` holding today's `RunMetaCard` fields.
- [ ] **Step 2: Fix the carried-over faults:** both throughput lines read `interpreted_metrics.throughput`; delete the "Saved timeline frames include warmup" sentence; remove the fixed 140 ms timer.
- [ ] **Step 3: Remove** `StatStrip`, the notice bar, `CurrentFrameCard`, the three-chart grid and the KPI table, with their now-unused CSS.
- [ ] **Step 4: Run the frontend checks.** Expected: clean.
- [ ] **Step 5: Commit** `feat: rebuild Compare Runs around two maps and one player`.

### Task 8: Browser acceptance and docs

**Files:**
- Modify: `docs/PROGRESS_AND_HANDOFF.md`, `docs/ARCHITECTURE_AND_PLAN.md` (one dated decision entry for the frames endpoint and window limit)

- [ ] **Step 1: In a scratch app with its own database,** record a no-signal and an RL (or fixed-time) run at Site A with the same scenario and seed, then check: both maps play in step at 1×, 2×, 4×; scrubbing and keys work; seeking past the loaded window loads the right frames; the chart cursor follows; each KPI card matches the old table's numbers for the same pair (note them before Task 7 or from the API); changing the baseline while playing stops playback and clears both maps; a pair with a safety warning shows it above the maps; desktop and phone width.
- [ ] **Step 2: Run the full backend suite** (`.venv/Scripts/python.exe -m pytest tests -q --basetemp "$TEMP/cpfull"`) and the frontend checks. Expected: no failures.
- [ ] **Step 3: Write the progress entry** (what changed, the checks and their results, labelled synthetic where the demand is synthetic) and the architecture entry.
- [ ] **Step 4: Commit** `docs: record the Compare Runs two-map view`.
