# Dashboard and simulation canvas redesign plan

Planned: **2026-10-25** (Asia/Singapore). Status: **implemented 2026-10-25** (see the progress entry for verification and the two small deviations: the controller is chosen only in the Signal control card, and Replay is chosen from the setup card rather than a Live/Replay switch in the bar). Scope: `SmartFlow` Dashboard (Live Simulation View) only.

Navigation: [Start here](../README.md) · [Progress and handoff](PROGRESS_AND_HANDOFF.md) · [Architecture and plan](ARCHITECTURE_AND_PLAN.md)

## Why

The October 24 dashboard (decision D24) put too much information on the simulation canvas: a toolbar row, junction picker, layers/inspector buttons, legend, footer counts and a floating minimap. The owner prefers the earlier canvas (commit `479358f`) for its clean look: a minimal map with three corner chips and good KPI boxes. The owner also wants the right-hand information column from the reference mock-up: a small network map, a selected-junction card with a picture, and three tabs (Signal Phases, Queue Info, Performance).

The target audience remains an LGU traffic administrator. Every change must stay accurate for the capstone: two provisional junctions, RL on one selected junction, synthetic demand, no emergency vehicles.

## Agreed layout

```
┌ KPI row: Average wait │ Average queue │ Throughput veh/h │ Average travel time   (each: % vs fixed-time) ┐
│┌──────────── Map (2D default / 3D) ─────────────┐┌ Right column ───────────────────────┐│
││ [Intersection name]                       (+ −) ││ 1. Small network map (J1 ─ J2)      ││
││          [J1 · Arellano × Osmeña]               ││ 2. Selected junction card + photo   ││
││                    [J2 · Mabini × Osmeña]        ││ 3. Tabs: Signal Phases │ Queue Info  ││
││ [Signal phase]                  [Phase timer]   ││          │ Performance               ││
│└─────────────────────────────────────────────────┘│ 4. Signal Control (Fixed/QL/DQL/PPO)││
│ Bar: Live|Replay ▶ ⏸ ■  1× ─ 02:15 / 05:00 ──●──  Layers  Expand  (Camera in 3D) └─────┘│
│ Trends over time (collapsed by default)                                                       │
└───────────────────────────────────────────────────────────────────────────────────────────────┘
```

## Decisions

| # | Decision |
| --- | --- |
| 1 | Use the reference mock-up's structure: KPI row on top, map centre-left, right information column, control bar under the map. The minimal style of the old canvas applies inside the map. |
| 2 | Map overlays are limited to three corner chips: **intersection name** (top-left), **signal phase** (bottom-left), **phase timer** (bottom-right), plus zoom icons and a one-line OpenStreetMap credit (licence requirement). Remove the toolbar row, legend line, footer counts and floating minimap. |
| 3 | Right column, top to bottom: small network map → selected-junction card with photo → three tabs → Signal Control card. |
| 4 | Junction photo: a free-licensed placeholder intersection photo from Wikimedia Commons at `public/assets/junctions/placeholder.jpg`, used for both junctions, captioned **"Placeholder photo — not the study site"** with its credit. Confirm file name, source and size with the owner before downloading. Dropping `J1.jpg` / `J2.jpg` into the same folder replaces it per junction. |
| 5 | Signal Control card lists Fixed-time / QL / DQL / PPO. A method is enabled only when a compatible trained model exists for the controlled junction. The card states which junction RL controls (e.g. "RL on J1; J2 runs fixed-time") and shows run status. |
| 6 | KPI cards: Average wait (s), Average queue (veh), Throughput (veh/h), **Average travel time (min)** (replaces Completed trips). Each shows % change against the latest completed fixed-time run of the same scenario and seed. No emergency KPI or setting. |
| 7 | Below the bar: only the existing "Trends over time" chart, **collapsed by default**. |
| 8 | Control bar: Live/Replay, Play/Pause, Stop, speed, elapsed clock with scrubber, Layers, Expand. **Camera** (Junction / Network view) appears only in 3D. |
| 9 | Placeholder photo approach as in decision 4 (owner request: "random intersection picture for now"). |
| 10 | **Signal Phases tab** shows the engine's real services, not the mock-up's turn movements: one card each for North, East, South, West and Pedestrian (only those the junction has), with arrow icons; the current service highlighted; "Current: South Green — 8 s / 14 s" with a progress bar; the plan's green / yellow / all-red seconds. |
| 11 | **Queue Info tab**: one bar per approach labelled by direction and street ("North · Osmeña St"), count plus band word (Clear 0, Low 1–4, Moderate 5–9, High 10+) coloured blue/amber/red; active closures or slowdowns on that junction's roads listed below. |
| 12 | **Performance tab** shows only measured per-junction values: queue now, vehicles passed since start, waiting pedestrians, mean speed on incoming lanes. No derived per-junction wait or throughput (the engine measures those network-wide only; they stay in the KPI row). |
| 13 | Sim clock shows elapsed / duration ("02:15 / 05:00"). No invented time of day. |
| 14 | When idle, a **centred setup card** over the map is the only place to choose scenario, controller, duration and seed (seed under "Advanced"). The Setup side sheet is removed. |
| 15 | Each junction gets a small clickable map tag ("J1 · Arellano × Osmeña"); the selected one is highlighted. |
| 16 | No "RL Control Ready" box in the left sidebar; the sidebar stays as is (Operate / Research / Admin, Randomize, Dark Mode). |
| 17 | Clicking a vehicle or road shows a map hover tooltip only. Remove the "Find a vehicle, lane or junction" picker and the vehicle/lane detail section. |
| 18 | The setup card has two tabs: **New run** (scenario, controller, duration, seed) and **Replay recording** (recording list + Load). The bar's Play/Pause and scrubber serve both. |
| 19 | Below ~1280 px wide, the right column stacks under the map. |
| 20 | 2D and 3D use the identical layout, chips, tags and right column; only the map drawing differs. |

## Facts this plan relies on

Verified by reading the source on 2026-10-25.

- **Old canvas (`479358f:src/components/dashboard-page.tsx`).** The dark crossroad was a CSS placeholder shown only while idle, under the Setup card. While running, it switched to the real `SimulationCanvas2D` / `SimulationScene3D` with live vehicles. Phase and timer came from `state.phase` and `state.phase_remaining`. "Back to the old look" therefore means stripping chrome around the existing live renderer, not restoring a static picture.
- **Signal phases (`simulation/traffic_engine.py`).** Each junction cycles through its existing approaches `north, east, south, west`, then `pedestrian`. A plan's `phase_order` can override this. Stages are green, then yellow (vehicles only), then all-red. Defaults are green 14 s, yellow 3 s, all-red 1 s, minimum green 10 s and maximum green 60 s.
- **What `junction_controls()` already sends.** Its output includes `phase_order` and all durations. `src/simulation/frame-types.ts` `JunctionControl` does not declare them yet, so the type must be extended.
- **Per-junction telemetry.** `junction_metrics` has `queue`, `vehicle_passages`, `waiting_pedestrians` (plus `phase` and `mode`, which are untyped in TS). `lane_metrics` has `vehicles`, `queue`, `mean_speed_mps`, `density_vehicles_per_km`, `exits`, `closed` and `speed_factor`. Wait time and completed-trip throughput are network-wide only.
- **Street names.** These are not in the visual network. They reach the frontend through native-scenario options (`lanes[].road_name`, `services/native_scenario_service.py`), which can be joined to the signal group `lane_id`.
- **Travel time.** `avg_travel_time` is in live metrics (`traffic_engine.py`) and in `simulation/metric_definitions.json` ("Completed-trip travel time").
- **Junction photos.** The repository contains none.

## Implementation steps

1. **Types:** extend `JunctionControl` with `phase_order` and the plan durations, and `JunctionMetrics` with `phase` and `mode` (`src/simulation/frame-types.ts`).
2. **Map chrome:** in `src/simulation/simulation-visualization.tsx`:
   - Remove the toolbar row, legend, footer and floating minimap.
   - Add the three corner chips and the clickable J-tags (2D and 3D).
   - Keep zoom icons and the one-line OSM credit.
   - Move Junction/Network camera focus into the bar (3D only).
   - Lift the selected-junction state so the right column can read and set it.
3. **Right column** (new components beside `dashboard-page.tsx`, built from shadcn Card / Tabs / Progress / Badge / ToggleGroup):
   - `network-minimap` (reuse the existing `Minimap` SVG logic).
   - `junction-card` (photo with per-junction override, then placeholder, with caption and credit).
   - `junction-tabs`: Signal Phases / Queue Info / Performance. Reuse `approachDirection`, the queue bands and `timingLabel`.
   - `signal-control-card`: controller options from the existing model filter; RL junction statement.
4. **KPI row:** swap Completed trips for Average travel time (min) in `src/components/dashboard-kpis.tsx`.
5. **Control bar:** in `src/components/dashboard-controls.tsx`, remove the Setup sheet, add the elapsed/duration clock with scrubber, and add Layers / Expand / Camera (3D only).
6. **Idle setup card** with New run / Replay recording tabs, centred over the map.
7. **Trends:** collapsed by default (`src/components/dashboard-trends.tsx`).
8. **Responsive:** right column stacks under the map below ~1280 px.
9. **Placeholder photo:** confirm the Wikimedia Commons file and licence with the owner, then add it with its credit.
10. **Cleanup:** remove code and CSS orphaned by these removals (vehicle/lane detail section, object picker, toolbar, caption/footer styles).
11. **Docs:** record the decision in the architecture document (superseding D24's map chrome) and add a dated, verified entry to progress.

## Verification

- `npx vitest run`, `npx tsc -b`, `npm run lint`, `npm run check:api`, production build.
- Unit tests for any new pure logic, such as phase-card ordering from `phase_order` and approach/street labelling.
- Browser check on the provisional 2-junction network with an isolated scratch database:
  - idle setup card (both tabs);
  - a fixed-time run in 2D and 3D;
  - chips update with phase and timer;
  - J-tag and minimap selection drive the right column;
  - all three tabs;
  - Signal Control states with and without a trained model;
  - Replay with scrubber;
  - layouts at 1440 px and below 1280 px.
- Not provable in the browser without a trained model: the KPI % change against an RL run (the calculation is unit-tested).

## Out of scope

- Photorealistic 3D.
- A time-of-day clock.
- Per-junction wait or throughput metrics.
- Emergency vehicles.
- A separate operator role.
- Per-scenario network selection (the provisional network is still chosen with `SMARTFLOW_NETWORK_PATH`).
