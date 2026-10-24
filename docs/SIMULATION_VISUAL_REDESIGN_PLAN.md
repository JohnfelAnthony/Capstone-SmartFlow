# SmartFlow: a clearer, more compelling simulation

Date: 2026-10-10  
Status: Implemented through slices A–F; verified evidence and remaining acceptance limits are in the [October 10 result](reviews/SIMULATION_VISUAL_REDESIGN_RESULT_2026-10-10.md).  
Intended implementer: GPT-6.1 working in the independent SmartFlow repository.

The first five sections preserve the agreed visual direction. The instructions below remain the original implementation specification; the dated result establishes what was implemented and verified. Proposed interfaces here should be read alongside the current source and that evidence.

## Recommendation

**Use an interactive architectural model of the road network:** clean streets, recognizable vehicles, restrained buildings, and clear traffic information. The current presentation undersells the simulation.

The source and saved screenshots show several concrete causes: overly distant camera framing, mostly identical box-shaped vehicles, missing street context, and 2D roads extending beyond their actual endpoints.

The chosen direction is **ordinary-laptop performance, opening at the selected RL junction with a network minimap**.

## Visual design and interaction

| View | Intended experience |
|---|---|
| **3D** | An attractive miniature street scene where researchers can watch vehicles queue, pedestrians cross, and signals change. |
| **2D** | A precise analysis map with clear directions, queues, restrictions, and controller labels. |

**3D scene**

- Use warm neutral ground, charcoal asphalt, clear markings, restrained building shapes, muted greenery, and subtle shadows.
- Give **cars, motorcycles, green Tagum tricycles, buses and trucks** distinct silhouettes. These five categories already exist in the engine.
- Include a recognizable three-wheeled passenger tricycle with its green body and covered cabin. Scale every model to its engine-defined dimensions.
- Keep buildings low and sparse so they cannot obscure traffic.
- Represent pedestrian waiting and crossing clearly. Crossing graphics must follow the modeled pedestrian paths; current paths are simplified and should remain identified as illustrative.

**2D map**

- Replace the saturated green background with a restrained palette matching the dashboard.
- Add readable junction names, direction arrows, distinct vehicle symbols, queue overlays, and closure markers.
- Support pan, zoom, and selection, with the same selected junction or vehicle retained when switching between 2D and 3D.

**Shared controls**

- Open at the configured RL junction; identify its actual controller during fixed-time runs too.
- Provide **Junction / Network / Follow selected vehicle** camera controls, a clickable minimap, fullscreen, and a compact legend.
- Clicking a junction, lane, vehicle, or pedestrian opens a small inspector with relevant measurements.

## Make the RL behavior understandable

Place a compact controller panel beside the scene showing:

- Which junction is controlled and which controller is active.
- Current signal phase and approach queues.
- The latest policy request, when it occurred, and any safety override.
- Pedestrians waiting and the actual signal state.

Expose existing engine telemetry through the shared render-frame contract for live simulation and replay. Add authoritative lane/junction metrics, entity waiting time, and available controller/timing metadata.

**Label timing accurately:** RL minimum-hold time is not a guaranteed countdown to the next green. Missing telemetry should display "Unavailable," rather than fabricated explanations or zero-valued learning statistics.

Queue overlays must use complete engine metrics. The current live display cap of 80 vehicles can conceal congestion; target displaying the full default 300-vehicle population after optimization, with explicit visible-versus-total counts whenever a limit remains.

## Assets and implementation order

Use one consistent asset family. Start with the CC0 [Kenney Car Kit](https://kenney.nl/assets/car-kit) and selected [City Kit road props](https://kenney.nl/assets/city-kit-roads), plus a matching lightweight Tagum tricycle. Generate road surfaces from SmartFlow's network geometry.

Implement in this order:

1. **Correct the foundation:** remove inappropriate road extrapolation, align vehicle models with engine coordinates, and correctly display signals that are off.
2. **Complete one representative junction:** final camera framing, pavement, markings, vehicle silhouettes, pedestrians, and restrained context.
3. **Add research interactions:** minimap, selection, inspectors, synchronized queues and controller information.
4. **Apply the reusable design across the network and optimize.**

Retain Three.js and the Python engine. Use locally bundled GLB assets, shared materials, static batching, and [instancing](https://threejs.org/docs/pages/InstancedMesh.html). Cache the static 2D map. Default to a **Laptop** quality preset; offer enhanced shadows separately.

## Acceptance and assumptions

- Both views depict identical road geometry, positions, signals, and selected objects.
- Researchers can quickly identify the controlled junction, longest queue, pedestrian activity, and current signal service.
- Vehicle categories remain distinguishable at the default camera distance.
- Verify normal traffic, congestion, closures, all-way-stop control, pedestrian service, and replay.
- Target at least **30 FPS on a documented ordinary laptop** under a representative 300-vehicle load; measure before claiming success.
- Confirm rendering changes preserve seeded engine outcomes and research metrics.
- Scenery remains illustrative until field geometry is verified. Visual improvements do not change vehicle behavior, road capacity, or the study's calibration status.

---

## 6. Instructions for GPT-6.1

### Objective and boundaries

Implement this redesign as a complete, usable 2D/3D visualization of the existing native simulation. Finish the ordered slices below, verifying each before moving on. A recolored map or a standalone model showcase does not satisfy the objective.

Work from the SmartFlow root. Read `AGENTS.md`, `README.md`, handoff sections 1–4 and 11, and the relevant source. Read the [cleanup result](reviews/SUMO_DASH_CLEANUP_RESULT_2026-10-09.md) so removed SUMO/Dash/Infinitown resources are not accidentally reinstated. Older handoff failures and test counts are historical: current source and fresh verification establish actual behavior.

Before implementation:

1. Inspect `git status --short` and preserve all existing edits, untracked files, research data, models, recordings, and cleanup recovery archives.
2. Capture baseline screenshots of both current renderers and baseline engine/render timings using synthetic fixtures and isolated artifacts.
3. Read the applicable Three.js, React, shadcn, FastAPI, debugging, browser-testing, and verification skills when working on those areas. Reuse existing controls and design tokens.
4. Track the six delivery slices in section 10. Continue through routine implementation decisions without repeatedly asking the owner to choose defaults already specified here.

Keep these boundaries:

- Python remains authoritative for positions, signals, arrivals, queues, pedestrian service, routing, safety, and RL. Browser animation only interpolates that state.
- Preserve `engine_config`, model compatibility, seeds, permissions, saved scenarios, recordings, and exports. No database migration or learning-algorithm redesign is required for this work.
- Read-only telemetry additions to engine snapshots are allowed. Changes to movement, collision rules, capacity, crossing behavior, or signal decisions are outside this visual redesign.
- Keep the current direct Three.js/WebGL integration. Do not introduce a React Three Fiber, WebGPU, game-engine, or SUMO migration.
- Exclude Field Observer changes, custom intersection editing, automatic map import, field calibration, network-wide RL, and full route/rerouting-history visualization. Those require separate work.
- Do not add fake traffic, implied extra driving lanes, scripted signal decisions, or decoration that appears to establish real Tagum geography.
- Saving this handoff does not itself mean implementation has begun. When implementation is requested, only report slices complete after their acceptance evidence exists.

### Completion standard

The final app must let a researcher open a scenario, immediately understand the selected junction, distinguish vehicle types, see queues and pedestrian activity, inspect actual controller behavior, switch between 2D/3D, and replay the same information. It must retain a usable 2D fallback and operate locally without runtime asset downloads.

## 7. Source map and confirmed starting points

Paths below are relative to the SmartFlow root and were inspected on 2026-10-10. Recheck before editing because another chat may have changed them.

| Area | Existing entry points | Implementation responsibility |
|---|---|---|
| Scene integration | `src/components/dashboard-page.tsx` | `SimulationView`, render-frame fallback/merge, phase cards, mode switch, inspector placement, performance readout |
| 3D | `src/simulation/SimulationScene3D.tsx` | Geometry, camera, models, lights, selection, interpolation, resource lifecycle |
| 2D | `src/components/simulation-canvas-2d.tsx` | Canonical geometry, static-map cache, dynamic drawing, pan/zoom, selection |
| Shared contracts | `src/simulation/frame-types.ts`, `src/api/simulation.ts`, `src/api/visual-network.ts` | Typed optional telemetry, network metadata, common semantics |
| Stream | `src/hooks/useSimulationSocket.ts`, `backend/main.py` | Live delivery, lifecycle, network endpoint, reconnect/fallback consistency |
| Serialization | `services/render_frame_service.py` | Entity limits, authoritative metrics, controller events, compact snapshots |
| Network presentation | `simulation/road_network.py`, `services/visual_network_service.py` | Actual lane/connector shapes, junction pavement, signal anchors, metadata |
| Engine truth | `simulation/traffic_engine.py`, `simulation/scenario_config.py` | Read-only snapshots, timing meanings, vehicle dimensions, pedestrian path, configured capacity |
| Replay | `services/timeline_generator.py`, `simulation/timeline_engine.py` | Preserve new telemetry in new recordings; tolerate missing fields in old recordings |
| Existing asset helper | `src/simulation/three-assets.ts` | Inspect reusable procedural pieces before duplicating them; it is not currently imported by the active scene and lacks a tricycle type |
| Styling | `src/index.css`, existing UI components | Align simulation toolbar, overlays, and inspector with the dashboard |
| Regression evidence | `tests/test_native_regressions.py`, `tests/test_shared_session_and_import.py`, `tests/test_native_traffic_contract.py`, `tests/test_native_cleanup.py` | Extend focused contracts and preserve native-only behavior |
| Capacity measurements | `tools/measure_native_capacity.py` | Existing backend/serialization benchmark; does not measure browser FPS |

Specific issues to address:

- `extrapolateLaneShape()` extends each flagged endpoint by 1,000 units. Native connected-network roads currently have both flags set. Use exact supplied lane shapes for this network; do not change engine geometry to compensate for a drawing bug.
- Current 3D car geometry extends behind its group origin while the native vehicle position represents its center. Verify all class bounds and heading conventions before swapping assets.
- The current 3D signal mapping treats the off state `o` as red. All-way-stop must appear as an unlit signal with its actual controller label.
- Native visual output currently has empty `crossings`, `walking_areas`, and `polygons`. Existing renderer support alone cannot supply these features.
- The live serializer limits display to 80 vehicles/32 pedestrians, other frames to 120/48; the dashboard fallback separately slices to 80/32. Update all paths together.
- The native default is 300 active vehicles, but configuration permits up to 2,000. The visualization target is not a promise of full-detail real-time rendering at every supported engine capacity.
- `MAX_RENDER_STATE_BYTES` is declared but the inspected WebSocket sender directly sends the frame. Do not mistake the constant for an enforced payload bound.
- The fallback has an obsolete `tagum_1` default. Resolve the active native network from actual metadata; do not revive an invalid network identifier.
- Do not keep the hard-coded five-junction scene title or always-red phase text. Derive labels, counts, and signal styling from the current network/frame.

## 8. Shared presentation architecture

### Ownership and module boundaries

Extract shared presentation logic from the renderers and dashboard into small modules under `src/simulation/`. Use these proposed responsibilities; equivalent descriptive filenames are acceptable if existing code already supplies the role:

- `scene-geometry.ts`: pure network-to-display geometry, coordinate conversion, bounds, and stable selection identities.
- `presentation-state.ts`: selection, camera focus, overlays, quality preference, and network-change/reset behavior.
- `render-frame-adapter.ts`: HTTP fallback normalization with the same semantics as the Python serializer.
- `vehicle-assets.ts`: canonical vehicle class mapping, loading, normalization, batching, fallback meshes, and disposal.
- A reusable toolbar/minimap/inspector component group: shared controls around either renderer, using the existing UI library.

Load and validate one visual network in the visualization host and pass it to both views and the minimap. Remove independent per-renderer requests once the host owns this data. Ignore late responses for a previously selected network. Renderers must not fetch on every simulation frame.

Keep per-frame transforms in refs/renderer-owned structures. Do not send every moving vehicle through React state updates at display refresh rate. React owns user interaction and compact informational UI.

### Shared state and navigation rules

- Selection is `{ kind: 'junction' | 'lane' | 'vehicle' | 'pedestrian', id: string } | null`. IDs come from the network or snapshot, never mesh array indices.
- Focus is `junction`, `network`, or `follow`. Start at the configured controlled junction; fall back to the first valid junction, then network bounds if none exists.
- Inspecting another junction does not change the scenario's controlled junction or issue a simulation command.
- Preserve selection, focus target, overlay toggles, and quality when switching views. Each renderer may retain its own zoom/orbit values.
- Follow applies to the selected vehicle. Disable it when no vehicle is selected. If that vehicle leaves, return to junction focus and announce that it left; do not silently follow another vehicle.
- On replay seek, stop interpolation across the jump and apply the requested frame immediately. On network change, clear incompatible selections and cached geometry.
- Pause freezes entity motion at the authoritative paused state while leaving camera controls usable. Stop/reset clears stale entity and controller details.
- Make the minimap an overview of the canonical network with the focused junction marked. Clicking a junction focuses it. Provide a labeled dropdown with the same action for keyboard users.
- Default overlays: signals, selected-junction label, and a compact selected-junction queue summary on; lane heatmap, direction arrows, and turning connectors off until enabled.
- Use a responsive side inspector on wide screens and a collapsible panel below the viewport on narrow screens. It must not cover the main junction.
- Provide labeled controls, visible focus, keyboard-accessible selection alternatives, non-color status cues, and reduced-motion camera transitions. Fullscreen must have a clear exit and a usable expanded-layout fallback when the browser API is unavailable.

### Geometry and visual identity

Use native lane centerlines, widths, junction polygons, and signal stop lines. Both renderers must consume the same normalized primitives and IDs. Merge road/junction appearance without adding navigable geometry. Turning connectors are optional analytical paths over junction pavement, not separate fully marked roads.

Normalize vehicle assets once to a centered ground-level origin, forward along local positive X. Convert native `(x, y)` into Three.js `(x, elevation, -y)` and test all cardinal headings. Apply the current native angle conversion consistently. Match the supplied length/width; keep plausible class height without inflating the traffic footprint.

Use these starting scene colors, isolated in a shared palette so final contrast adjustments remain consistent:

| Element | Starting value |
|---|---|
| Ground/background | `#E8ECE8` |
| Pavement | `#414852` |
| Markings | `#F3F2E9` |
| Curbs/context | `#B8C0BA` |
| Buildings | `#D6DAD3` |
| Vegetation | `#839A83` |
| Selected junction | Existing SmartFlow brand accent plus outline/label |
| Tagum tricycle | `#69B83F`, with dark cabin and contrasting trim |

Color is supplementary: closure barriers, direction arrows, signal lamp positions, legends, and text must remain meaningful without color alone. Use muted non-green colors for most ordinary cars so the green tricycle is recognizable.

Place any illustrative buildings/trees deterministically outside buffered road, junction, and pedestrian-path bounds. Do not call unseeded randomness during rendering or change context when switching views. Keep scenery sparse and lower than the view's critical sightlines; its initial toggle is on and can be disabled.

For pedestrian paths, add a read-only presentation path derived from the same junction coordinates, origin offset, and configured `crossing_length` used by the engine. Share that derivation with pedestrian position serialization without changing numerical behavior. Render a restrained dashed crossing corridor labeled illustrative. Do not invent real sidewalk connectivity or zebra crossings at unrelated positions. When an old recording lacks path geometry, show its recorded people without manufacturing a crossing.

## 9. Data contracts and accurate explanations

### Additive render-frame changes

Preserve the existing frame envelope and public routes. In particular, the existing `intersection_id` frame field currently carries network identity; do not rename it throughout unrelated APIs as part of this work. The visual-network request continues to use canonical `network_id`.

Add the following optional fields to the Python serializer and TypeScript contracts. Names below are the proposed implementation contract. All metrics must come from the same state snapshot as the entities and signals.

| Proposed field | Authoritative source and meaning |
|---|---|
| `vehicles[].wait_time`, `pedestrians[].wait_time` | Existing engine record field; seconds, not inferred from animation |
| `lane_metrics` | Map by lane ID with `vehicles`, `queue`, `mean_speed_mps`, `density_vehicles_per_km`, `exits`, `closed`, `speed_factor`, copied from `state.metrics.lanes` |
| `junction_metrics` | Map by junction ID with `queue`, `vehicle_passages`, `waiting_pedestrians`, from `state.metrics.junctions` |
| Extended `junction_controls[id]` | Preserve existing fields; add `stage`, `elapsed_seconds`, `remaining_seconds`, `timing_kind`, `pending_service`, and `external_control` |
| `controller_events` | Nullable `last_policy_decision` and `last_safety_override` copied from `state.experiment`; retain their simulation time, junction ID, action/service, and recorded result/reason |
| `visual.pedestrian_paths` | Optional array of `{ id, junction_id, shape, provenance: 'illustrative' }` describing actual modeled paths; omit when unavailable |
| `render_coverage` | `{ vehicles: { total, shown }, pedestrians: { total, shown }, limited, reason }`; totals remain authoritative; reason is `null`, `entity_limit`, or `byte_limit` |

Expose stage/elapsed/pending/external state through read-only `junction_controls()` metadata; do not change `Signal.step()` or `Signal.request()` to simplify the display. `timing_kind` is one of `fixed_stage`, `minimum_hold`, `clearance`, or `none`:

- All-way-stop: `none`, no countdown, unlit lamps, explicit all-way-stop label.
- RL/external green: `minimum_hold`; label "Minimum hold remaining." At zero, say "Minimum hold satisfied," not "Green ends now."
- Fixed-time green: `fixed_stage`; label "Scheduled green remaining." Safety can delay service, so do not promise an exact time until another approach turns green.
- Yellow/all-red: `clearance`; label "Clearance timer." At zero, actual signal state still governs movement.
- Show elapsed stage time separately. Do not animate a timer beyond paused/stale authoritative data.

Policy events are requests, not necessarily immediate phase changes. In the current engine, `applied: true` with `queued_safely` means the request was queued. Display "Requested east service" and the actual current phase independently. A historical safety override should carry its timestamp; do not label it currently active merely because it is the latest recorded event.

Do not infer "the AI chose this because traffic was heavy" from a queue measurement. Display the actual request and measurements without inventing an explanation of the policy's reasoning. Training episode/reward/epsilon widgets must use actual relevant job data or show unavailable/not training; inference is not ongoing learning.

### Network metadata and compatibility

Type the backend's existing `network_id`, `junctions`, and provenance metadata where the frontend currently omits them. Resolve human-readable labels using existing native configuration options/network metadata. Fall back to stable "Junction 1" style labels with the raw ID available in the inspector.

Do not broadly retype all metrics as numbers: the state now includes nested lane/junction maps. Define explicit nested types while preserving existing numeric dashboard KPI consumers.

Update `renderFrameFromSimulation`, `mergeRenderFrame`, API types, and socket consumers together. Missing optional data in historical recordings must clear the corresponding displayed information; never retain telemetry from a newer frame or another run. New recordings already serialize engine snapshots; verify additions survive playback rather than creating a second recording format.

Use paired Python/TypeScript fixtures to prove equivalent semantics across WebSocket, HTTP fallback, and replay. Do not add a second stream or poll separate metrics just to populate the inspector.

### Display limits and transport defaults

For this delivery, use a uniform ceiling of **300 vehicles and 128 pedestrians** in live, replay, and HTTP fallback presentation. These are display defaults, not changes to engine admission limits. Display all entities below those ceilings. A run with a larger population remains valid and visibly identifies its limited display.

When a ceiling is exceeded, allocate display slots deterministically across lanes/junctions rather than always taking the first entries in the global array. Use stable IDs to break ties. Metrics and total counts must still describe the complete simulation. Show "Showing X of Y vehicles" and the corresponding pedestrian count whenever limited.

Enforce the existing **262,144-byte** compact-frame budget against the actual JSON encoding used for transmission. Trim only display entities when necessary, using the same deterministic allocation; preserve authoritative aggregates and set `render_coverage.reason` accordingly. If metadata alone exceeds the bound, surface a clear stream error rather than silently dropping research telemetry. Add tests for the byte guard; a declared constant is not verification.

Laptop and Enhanced quality must receive the same state and population. Quality changes geometry/effects, not queue totals or which controller appears active. Larger-capacity engine runs are not grounds for quietly lowering experiment demand.

## 10. Ordered implementation slices

### Slice A — Repair geometry and establish shared state

1. Add regressions for connected-road endpoints, vehicle centering/headings, and off-signal handling before changing their implementation.
2. Introduce shared normalized geometry and host-owned network loading; remove native-lane extrapolation in 2D.
3. Correct 3D model origins, normal road/junction drawing, dynamic title, and phase colors.
4. Add junction/network camera presets, initial controlled-junction focus, and shared selection state. Fit the junction plus its immediate approaches with approximately 20% padding; do not default to the complete network bounds.

**Gate:** both views align with native lane endpoints and vehicle centers; selected-junction framing is readable; switching views does not reset the chosen junction; off signals are visibly unlit. No engine motion rules changed.

### Slice B — Build the reusable architectural scene and fleet

1. Implement the palette, coherent pavement/curbs, legible signal heads, minimal context, and illustrative pedestrian-path overlay.
2. Create an explicit asset registry for `car`, `motorcycle`, `tricycle`, `bus` and `truck`. The registry follows the five supported ordinary-traffic classes.
3. Curate only needed files from the Kenney sources linked above. Inspect their actual contents before claiming any category is supplied. Use locally authored lightweight assets for missing classes and the distinctive green Tagum tricycle; do not substitute a recolored car or motorcycle.
4. Normalize source assets to the shared origin/dimensions. Use GLTFLoader for GLB files; cache templates and batch repeated parts by geometry/material. Procedural geometry is acceptable for missing assets if the class silhouette is recognizably different and follows the same style.
5. Use opaque dark glass where possible, one simple material palette/atlas, and low polygon counts. Store runtime assets under `public/assets/simulation/`; add an asset manifest with source URL, author, license, modifications, orientation, and normalization notes. Keep original license notices.
6. On asset-load failure, show a distinct procedural class fallback and a non-blocking message; keep the simulation usable. No runtime dependency on external CDNs or removed cleanup assets.

**Gate:** one representative junction demonstrates the final visual language in the real simulation; all five supported classes are distinguishable, the tricycle has three wheels and a covered passenger cabin, assets remain aligned at stops/turns, and the same renderer can display other junctions without hand-placed per-junction traffic geometry.

### Slice C — Complete the analytical 2D view and navigation

1. Separate static-map drawing from moving entities, signals, and overlays. Resize canvas backing buffers only when dimensions/DPR change.
2. Implement bounded pan/zoom, reset, selection hit-testing, class symbols, and the shared minimap. Invalidate static caches on geometry, viewport, or palette changes; redraw dynamic restriction overlays when they change.
3. Add direction-arrow and turning-connector toggles, readable closure/slowdown markers, a common legend, fullscreen, and keyboard-accessible selection controls.
4. Keep 2D and 3D coordinate conversion and selection behavior consistent. Signals and queue labels must remain readable at the junction preset without requiring close manual zoom.

**Gate:** a researcher can navigate from overview to another junction, inspect a lane, select a vehicle, switch modes, and return to the configured junction without losing context.

### Slice D — Integrate truthful research overlays

1. Implement section 9 contracts end to end, including snapshot-only timing metadata and backward compatibility.
2. Build the controller panel and inspector: junction queue/waiting people/control, lane queue/speed/restrictions, vehicle class/speed/wait, and pedestrian wait/moving state. Display speeds as km/h with explicit units, converting engine m/s once; waiting/timing stays seconds.
3. Queue heatmap uses authoritative lane queue counts. Default scale: 0 clear, 1–4 low, 5–9 moderate, 10+ high; display the legend and raw count. These are display bands, not calibrated congestion thresholds.
4. Replace misleading hard-coded RL status values and generic phase/timer cards with truthful available telemetry for the selected junction. Do not let fixed-time runs inherit an RL-active label merely because `selected_for_rl` is true.
5. Implement consistent entity coverage disclosure and test parity across live/fallback/replay before removing old slicing paths.

**Gate:** the same snapshot yields the same counts, phases, requests, timing meaning, and selection details in both renderers; old recordings display unavailable information honestly; no stale event survives a run change or replay seek.

### Slice E — Optimize and handle failures

1. Instance or batch vehicles by class/material, plus repeatable static props. Preserve an instance-to-entity-ID map for picking. Pool objects and update transforms without rebuilding geometry on each frame.
2. Laptop preset: DPR cap 1.25, simple contact/blob shadows, one key light plus ambient light, no postprocessing, sparse context. Enhanced: DPR cap 1.5 and one bounded shadow-casting key light; no extra traffic detail semantics.
3. Cache shared resources and release them exactly once on scene replacement/unmount. Remove animation frames, event handlers, controls, observers, and obsolete async callbacks. Verify repeated mode switches do not duplicate loops or leak resources.
4. Interpolate using snapshot timing/step length, not a permanent assumed 100 ms interval. On frame gaps, freeze at the newest authoritative position once interpolation finishes; do not extrapolate vehicles through a stop line. Seek/reset/network changes snap immediately.
5. Handle WebGL initialization/context failure with a visible explanation and usable 2D fallback. Preserve selections and current state where compatible. Asset failure should not trigger full renderer failure.
6. Benchmark the actual production build and backend separately. Improve geometry, draw calls, caching, and effects before reducing any display limit or proposing engine changes.

**Gate:** the documented reference laptop meets the performance target in section 11, or the result clearly records the unmet target and measured bottleneck. A build passing is not performance acceptance.

### Slice F — Acceptance evidence and handoff

1. Run focused regressions, full appropriate backend checks, frontend tests/build/lint, then browser acceptance on the exact final source.
2. Capture matched 2D/3D screenshots, a mixed-fleet close-up, a congestion/closure view, controller inspection, replay, and Laptop performance evidence.
3. Save a dated result document under `docs/reviews/` with changed behavior, commands/results, hardware, screenshots, limitations, and remaining work. Record artifact paths in the document so evidence is discoverable.
4. Update `docs/PROGRESS_AND_HANDOFF.md` with verified status and `docs/ARCHITECTURE_AND_PLAN.md` with durable rendering/data decisions. Add the plan/result links to the documentation index. Preserve original manuscripts and cleanup evidence.

**Gate:** every acceptance item is supported by evidence or explicitly marked incomplete. Do not mark the redesign finished while merely demonstrating downloaded models in a showcase.

## 11. Tests and acceptance procedure

### Automated coverage

Add focused serializer tests in a new `tests/test_render_presentation.py` and extend existing regression tests where their contracts change. The existing renderer-cap test explicitly expects 80/32; replace those expectations with meaningful below-limit, at-limit, above-limit, and byte-budget cases rather than simply weakening the test.

For pure frontend presentation logic, add a small Vitest setup with a `test:visualization` script if no frontend test runner exists at implementation time. Keep it limited to deterministic geometry, mapping, selection, and normalization tests; do not add snapshots that merely mirror component markup.

| Case | Required assertion |
|---|---|
| Bent/connected road | Display endpoints equal native endpoints; no 1,000-unit extensions or extra road branches |
| Mixed fleet and headings | Model/symbol centers match frame coordinates, dimensions match the class contract, forward direction is correct at cardinal headings and through a connector |
| Signal states | Green/yellow/red/off remain distinct; all-way-stop has no red-light implication or countdown |
| Controller timing | Fixed-stage, minimum-hold, clearance, and unavailable timing are labeled correctly; queued request is not treated as immediate green |
| Full versus limited population | 300 vehicles are included under normal payload size; above-limit displays keep exact total counts/metrics and expose coverage; byte trimming is deterministic |
| HTTP/stream/replay parity | Paired fixtures normalize to the same metrics, events, units, controller identity, and coverage |
| Old recording | Missing fields produce unavailable values; no crash, invented event, or stale previous-frame telemetry |
| Lifecycle | Run change, network change, seek, departed selection, pause/resume, and stale network response follow section 8 rules |
| Engine invariance | Same seed/config produces matching vehicle paths, signal sequence, completions, and metrics before/after read-only metadata additions; ignore newly added presentation fields in equality checks |
| Permissions and native cleanup | Existing network/stream access rules remain effective; legacy query aliases and removed engine/assets are not restored |

Suggested commands from the SmartFlow root, after the new test module/script exist:

```powershell
.\.venv\Scripts\python.exe -m unittest tests.test_render_presentation tests.test_native_regressions tests.test_shared_session_and_import tests.test_native_traffic_contract tests.test_native_cleanup -v
npm.cmd run test:visualization
npm.cmd run check:api
npm.cmd run build
npm.cmd run lint
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
```

Use isolated test databases/artifact directories and existing test initialization patterns. For browser checks, use a distinct `SMARTFLOW_DB_PATH`, separate verified ports, and clearly named synthetic scenarios. Read the current startup instructions for secrets/bootstrap requirements; do not overwrite the owner's database or start duplicate servers on occupied ports.

### Browser acceptance sequence

1. Open a clearly synthetic mixed-fleet scenario; start fixed-time control. Confirm the default junction focus, minimap, all five supported class appearances, and accurate controller label.
2. Toggle 2D/3D, inspect each entity kind, pan/zoom, use the keyboard junction picker, enter/exit fullscreen, and return to default focus.
3. Run a congested case and inspect lane queues, total/displayed populations, and heatmap legend. Confirm the overlay follows complete metrics even in an above-limit case.
4. Apply configured lane closure and slowdown events. Confirm only their directed lanes are marked and reopening clears the visual state. Do not manufacture a route trail.
5. Exercise pedestrian service and all-way-stop. Confirm pedestrian graphics match the modeled path and unlit signals are understandable.
6. Use a compatible actual policy for an RL case. Observe a request during minimum hold/clearance and inspect any recorded safety event. Controlled test fixtures may cover rare states, but must be labeled synthetic rather than presented as learned policy evidence.
7. Pause/resume, stop/restart, replay a new recording, seek backward, and open a recording without new telemetry. Confirm stale values and interpolation do not cross these boundaries.
8. Test failed asset load, unavailable WebGL, and lost stream/reconnect. Confirm clear errors/fallback and coherent HTTP-derived presentation.
9. Inspect at 1366×768 and a narrower viewport; controls and the inspector must remain reachable without obscuring the junction.
10. Switch modes at least ten times and watch frame-loop count, draw calls, memory/resource trends, console errors, and network requests. Asset/network requests must not repeat on every frame.

### Performance measurement

Target the Laptop preset at a 1366×768 browser viewport. Record OS, CPU, GPU, RAM, browser/version, DPR, build revision/worktree evidence, scenario/seed, actual peak entities, and quality settings. Do not claim "ordinary laptop verified" based only on a powerful desktop.

Warm assets for 10 seconds, then measure 60 seconds at junction focus and network overview. Use a reproducible stress fixture containing **300 vehicles and 128 pedestrians** for rendering load, plus an actual native run for integration. Identify the stress fixture as synthetic rendering evidence; it cannot prove realistic traffic capacity. Disable unrelated training jobs during the baseline measurement and report backend step cost separately.

Acceptance target: average rendered FPS at least 30 and p95 frame interval at most 50 ms in the 60-second window, with no recurring long stalls or broken interaction. Record draw calls and resource trends as diagnostic evidence rather than claiming that a low draw-call count alone proves good performance. If target hardware is unavailable, report available-machine results and leave target-laptop acceptance pending.

Use the existing backend capacity tool separately, for example:

```powershell
.\.venv\Scripts\python.exe -m tools.measure_native_capacity --duration-seconds 60 --seed 42 --densities medium,high --output tmp/visual-redesign-verification/native-capacity.json
```

That command measures engine/serialization cost and actual generated demand; it does not guarantee a 300-vehicle population or browser performance. Store browser measurements and screenshots alongside it in a uniquely named verification directory.

### Final delivery checklist

- [ ] Shared geometry fixes and centered vehicle transforms verified.
- [ ] Junction-focused opening, minimap, inspection, and mode switching complete.
- [ ] Architectural scene and all five supported recognizable classes, including the green Tagum tricycle, complete.
- [ ] Analytical 2D map, accessibility controls, and 2D fallback complete.
- [ ] Same-snapshot metrics, accurate RL/fixed-time timing, event meanings, and coverage disclosure complete.
- [ ] New and older replay compatibility verified.
- [ ] Asset sources/licenses recorded; packaged app works without remote asset requests.
- [ ] Engine/configuration/model/permission contracts preserved.
- [ ] Automated checks and browser acceptance recorded against final source.
- [ ] Performance target verified on documented hardware, or remaining gap explicitly reported.
- [ ] Result document and current project status updated without rewriting historical evidence.

## 12. Suggested execution prompt

Copy this into the GPT-6.1 implementation chat when ready:

> Implement `docs/SIMULATION_VISUAL_REDESIGN_PLAN.md` in SmartFlow. Read the repository instructions and relevant current source first, preserve the dirty worktree and research artifacts, and execute slices A–F in order. Use the selected architectural-model style, ordinary-laptop default, and junction-focused opening with minimap. Include the distinctive green Tagum tricycle and all existing vehicle classes. Follow the document's shared geometry, telemetry, compatibility, performance, and verification contracts; keep Python authoritative and do not reintroduce SUMO or change traffic/RL behavior. Continue through implementation and verification rather than stopping at a scaffold. Record actual evidence and any unmet acceptance criteria in a dated result Markdown file. Do not call the redesign complete from build success alone.
