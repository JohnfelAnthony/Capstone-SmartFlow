# Route Planner: whole-site closure and route previews

## 1. The owner's problem

The current closure and adaptive-routing interface is difficult to understand visually. In New Scenario, the owner can select a road direction to close and choose how traffic should respond, but cannot see the whole network and where the affected vehicles could go. A small junction drawing and a "has a detour" badge do not explain the actual detour, whether the original destination remains reachable, or what happens when no route exists.

The shared-road option is also unclear. The owner drew a green path from the west approach into the open upper half of an eastern road whose lower half was closed. The question was whether "Share the other side" means allocating part of the opposite pavement to the closed direction. The interface needs to show both temporary travel directions, the closed pavement and the transitions, rather than leaving the owner to infer these from signal arrows.

The owner also finds the **"Closes at (s)" and "Reopens at (s)" inputs unnecessary**. They should be removed from the New Scenario closure form in a future implementation and must not be added to the new Route Planner page. A newly selected closure should apply for the whole run.

The agreed direction is a **separate Route Planner page**, using the same Canvas 2D map rendering as the Dashboard, without running a simulation. Users can inspect a saved scenario or try temporary closures without creating or changing a scenario. Apart from the requested removal of closure timing inputs, the Scenarios page keeps its existing workflow.

## 2. Status and decisions

- Date: **2026-11-10**, Asia/Singapore.
- Status: **reviewed design only; implementation pending**. Creating or revising these documents does not implement the page or remove any form controls. The concrete tasks, contracts and test names are in the [companion build plan](2026-11-10-route-planner-implementation.md).
- Source reviewed: local `main` at `725da90` in `C:/Users/jhepo/Desktop/trapik2/SmartFlow`.
- Intended audience: LGU traffic/planning reviewers, capstone researchers and demonstration users.
- Primary goal: answer **"If this direction is closed, where can traffic go, and does it still reach its intended destination?"**
- No simulation start, recording, model training or traffic generation is part of this page.
- No time slider, closure schedule editor, "Closes at" input or "Reopens at" input is part of this page.
- Route previews use the existing backend routing and shared-road rules. This work must not alter traffic behaviour, RL observations, rewards or model compatibility.
- Review accepted: extract shared route-decision policy for vehicle entry and rerouting; show only the original route and one selected route; restrict entries to generated-demand boundaries; reuse `scenarios:view` without a permission migration.
- A static preview says **"Route under these conditions"**, not "the route every vehicle will take". Engine parity means identical decisions for identical inputs, not a prediction of future congestion.
- Desktop integration remains on the desktop branch in a later delivery step. This plan does not authorize a desktop build or merging desktop-specific code into `main`.

## 3. Current implementation to reuse

| Existing source | Relevant behaviour |
| --- | --- |
| [Closure picker](../../../src/components/closure-picker.tsx) | Junction selection, directional closure toggles and response choices; currently contains the two timing inputs to remove. |
| [Closure form helpers](../../../src/lib/closures.ts) | Reads and preserves saved closure schedules, response selections and unrelated settings. |
| [Native scenario API](../../../src/api/native-scenario.ts) | Scenario/network options, closure checks and the frontend configuration contract. |
| [Closure check service](../../../services/closure_check.py) | Existing response eligibility and route-availability summaries. It does not currently return full route geometry. |
| [Closure responses](../../../simulation/closure_responses.py) | Detour, adaptive detour, shared pavement, alternative exit and entry waiting rules. |
| [Road network](../../../simulation/road_network.py) | Directed routes, permitted turns, class restrictions and main-road preference. |
| [Contraflow geometry](../../../simulation/contraflow.py) | Generates the temporary shared pavement and the two direction paths from the base network. |
| [2D canvas](../../../src/components/simulation-canvas-2d.tsx) | Existing renderer and camera interactions. Reuse its static rendering capabilities rather than mounting the live Dashboard. |
| [Compare map](../../../src/components/compare-map.tsx) | An example of reusing the renderer outside the Dashboard. |
| [Scene summary](../../../src/simulation/scene-summary.ts) | Existing road labels and shared-road presentation helpers. Its pre-run shared strips are approximate; use backend-derived geometry for the planner. |
| [Application shell](../../../src/App.tsx) and [sidebar](../../../src/components/app-sidebar.tsx) | Page registration, lazy loading and permission-aware navigation. |

Read the callers and tests of these files before implementation. Recheck current branch changes instead of assuming this checkpoint is still current.

## 4. User workflows

### A. Explore a saved scenario

1. Open **Route Planner**, placed in the sidebar's Operate group beside Scenarios.
2. Choose a saved scenario. Load its own network, fingerprint, closure choices and relevant routing settings.
3. If it has no closures, display **"No roads are closed"** and allow a normal route to be inspected.
4. Choose an entry, intended destination and vehicle class. Entry choices come from the network's `demand_boundaries` with an incoming-to-network direction, filtered by class access; do not offer every boundary as an entry.
5. Show the original route and the route available under the closure arrangement.
6. Allow temporary closure/response edits in local page state. Display **"Temporary changes — saved scenario unchanged"** when the preview differs from the saved scenario.
7. Provide **Reset to saved scenario**. Never autosave these changes.

### B. Try closures without a scenario

1. Choose **Temporary arrangement** and select Site A or Site B.
2. Click a road direction to close it; click again to reopen it. Each direction is separate.
3. Choose an eligible traffic response for that direction.
4. Choose a supported demand entry, destination and vehicle class, then compare the original route with the single selected route under these conditions.
5. Provide **Clear temporary closures**. No scenario, run or recording is created.

Changing site clears site-specific selections. Switching scenario replaces the temporary preview with that scenario's settings. The page must make its temporary nature visible; persistence and "Save as scenario" are outside the initial scope.

Normal destinations follow generated-demand destination and pair rules, including `side_street_only_pairs`. A boundary that does not generate traffic can still appear as the resulting alternative exit when the engine selects it. Derive these roles from the network rather than road-name assumptions. These controls inspect an eligible trip; they do not assert that the scenario has demand for every selectable pair. Arbitrary mid-road origins and bespoke scripted-trip origins are outside the first version.

## 5. Page layout and visual language

Use a large map as the primary surface, with a compact panel beside it. Stack the panel below the map on narrow screens.

```text
Route Planner             [Saved scenario / Temporary arrangement]
[Scenario or site]        [Entry] [Destination] [Vehicle class]

+----------------------------------+----------------------------+
|                                  | Selected road direction    |
| Whole-site Canvas 2D map         | Closed / open              |
|                                  | How should traffic respond?|
| Original and available routes    | Eligible response choices  |
|                                  | Route result and explanation|
| [Zoom] [Fit network] [Fit routes] | [Reset temporary changes]  |
+----------------------------------+----------------------------+
Legend and a short statement of preview limitations
```

| Appearance | Meaning |
| --- | --- |
| Red hatching with a closed label | Closed direction/pavement. |
| Grey dashed arrows | Original route without the proposed closures. |
| Green directional arrows | One selected route, labelled "Route under these conditions". |
| Amber pavement with arrows in both directions | Temporary shared pavement, labelled hypothetical. |

- Green means **route availability**, not a green traffic signal. Do not display active signal phases on this static page.
- Use arrows, labels and different line patterns as well as colour.
- Draw one selected trip clearly by default. Avoid overlaying every origin/destination combination at once.
- Version one shows at most two route lines: the original and the selected route. There is no top-three search, alternate-route picker or blue alternatives layer. A different destination selected by diversion is still reported explicitly.
- Provide pan, zoom, Fit network and Fit affected routes. Keep the view stable when the response panel changes.
- Give roads readable names, direction and location descriptions. Unnamed roads need a useful location description rather than a raw lane ID.
- Provide keyboard-accessible road selection through a companion list or equivalent control; canvas clicks cannot be the only interaction.
- Show loading/error/empty states beside the relevant control. Do not fill the page with repeated warning banners.

## 6. What the preview must explain

### Route result

Return and display distinct results for:

- **Unchanged route:** the closure does not alter this trip's selected route.
- **Detour available:** another route reaches the original destination.
- **Alternative exit:** traffic is directed to a different boundary; show the intended and actual destination separately.
- **Waiting outside the network:** the selected entry is closed and its response is to wait.
- **No route:** no legal path is available for this trip and class under the selected arrangement.
- **Shared pavement:** the route uses a supported temporary shared section.

The original route must also respect vehicle access and turn rules. If a bus has no legal original route, explain that rather than blaming the closure. Do not count origin/destination combinations as vehicle counts.

### Response choices

| Response | Planner explanation |
| --- | --- |
| Use the side street | A permitted detour retains the intended destination where reachable. |
| Use the side street and avoid jams | The simulation may change routes as congestion changes; this page previews routes without simulated congestion. |
| Share the other side | Both directions use separate parts of the remaining pavement, one lane each way. |
| Send to the nearest open exit | The destination changes to an exit selected by the engine's routing costs; do not describe it as the geographically nearest exit. |
| Vehicles wait until it reopens | The entry is unavailable. For a whole-run closure there is no scheduled reopening, so these arrivals remain outside the network for the run. |

Display the response set, but disable unsupported options with an explanation. Enforce the same choices on the server. Preserve the existing rule that adaptive side-street routing is a scenario-wide choice; explain any coordinated response changes visibly.

### Adaptive-routing limits

- No live traffic means there are no measured queues or congestion costs for this preview.
- The selected route uses stated static assumptions and the existing route policy. The first version shows one selected route only. It cannot predict the future queues, reroute timing or position of every vehicle.
- Keep the current main-road rule: a route to a specified destination uses main roads whenever they remain reachable. Side streets are used as permitted detours, not as unrestricted shortcuts.
- RL controls signal phases. The route preview is not a learned RL route recommendation.
- Do not display predicted wait reductions, queue lengths, throughput gains or guaranteed travel-time savings.
- If distance is shown, label it as modelled route distance and calculate it consistently for every route.

## 7. Shared-pavement presentation

Use `simulation/contraflow.py` to derive the geometry for the complete supported set of shared roads. Show both temporary directions, the original closed half and transition paths. Do not turn the owner's hand-drawn curve into an invented legal movement.

Sharing is not two opposing streams using the same single lane simultaneously. The implemented model allocates a lane in each direction within the remaining pavement. Alternating traffic through one lane total is outside this plan.

Use the backend's eligibility checks, including the opposite direction remaining available, road width and supported topology. Do not introduce crossovers through Site B's highway median or remove the Sobrecarey bus/truck restriction.

The planner displays the **assumed established sharing arrangement**. An optional explanatory illustration may show that actual runs clear the road before changing layout. It must not invent a clearing duration, claim that clearance has occurred, or present transition stages as a running simulation.

The engine arrival decision does not perform a lane swap. Clearing occupied lanes, reservations, timers and applying the derived network belong to the live engine. The preview calls the existing geometry derivation on an isolated arrangement and builds a disposable engine on that effective network.

## 8. Closure timing: revised owner decision

This section supersedes the earlier suggestion to add a time selector.

### Route Planner

- No "Closes at" or "Reopens at" fields.
- No editable closure timeline or scheduling controls.
- Newly chosen temporary closures apply throughout the hypothetical arrangement.
- No moving vehicle overlay or playback controls.

### New Scenario and the shared closure form

- Remove both timing inputs and their unused input handlers from `closure-picker.tsx`.
- Keep directional closing/reopening, the response selector and existing validity checks.
- Keep the new-closure default `{ start: 0, end: null }`, persisted through the existing whole-run closure representation.
- Explain once that newly selected closures apply for the whole run.
- The component is reused by Edit Scenario. Remove the timing editors there too, while preserving saved schedules and showing their existing description read-only.
- Preserve non-closure events and complete saved `engine_config`. Do not remove backend schedule support or rewrite old scenarios, recordings, models or research artifacts.
- Removing and re-adding a simple saved closure explicitly creates a new whole-run closure. Do not silently convert it merely because the form is opened or another setting changes.

### Older scenarios with scheduled closures

There is no unique time-independent arrangement for a schedule. For the initial Route Planner implementation, preview **the saved start-of-run arrangement at engine time zero**, including events effective at zero, and clearly state that later scheduled changes are not represented. This is not the post-warm-up visible starting frame.

Show a compact read-only notice when a scenario contains later closure changes. Never combine every closure from different times into one supposedly simultaneous arrangement. Preview edits remain temporary and cannot overwrite the stored schedule. A later schedule-exploration feature would require a separate scope decision.

## 9. Backend preview contract

Add authenticated, side-effect-free `POST /api/routes/context` and `POST /api/routes/preview` endpoints. The first supplies source-specific geometry, selection options and effective initial settings; the second returns the two-route comparison after edits. These are proposed APIs, not existing endpoints. Their schemas and error handling are specified in the [build plan](2026-11-10-route-planner-implementation.md#2-api-contract).

Request information:

- saved scenario reference or network ID;
- expected base-network fingerprint;
- explicit temporary closure and response overrides;
- entry, intended destination and vehicle class, validated against the permitted demand choices.

For scenario mode, the server loads the authorized scenario and resolves its settings. For temporary mode, it resolves current network defaults. An omitted override means use the saved value; an explicit empty closure list means clear closures in the preview.

Response information:

- base-network ID and fingerprint, preview basis and assumptions;
- effective closures and supported/disabled responses with reasons;
- original route and one selected route only;
- route outcome and intended/actual destination;
- directed lane paths and map-ready geometry, including junction connectors where supported;
- exact derived shared-road geometry;
- a concise explanation of restrictions or missing routes;
- whether historical scheduled changes are outside this static preview.

Implementation constraints:

1. Extract only the existing entry decision into `TrafficEngine.arrival_route`. Call it on an unstarted, unstepped disposable engine for each preview path. Reuse Dijkstra, turn/access restrictions and contraflow geometry. Leave in-network rerouting unchanged.
2. Do not call simulation start/configure endpoints, step a traffic engine or modify the process-local live runtime. Previewing must work while another user is running a simulation.
3. Do not write scenarios, models, runs or recordings. Reuse existing access/audit conventions without recording previews as research results.
4. Require the existing `scenarios:view` permission consistently for sidebar visibility, page access, both endpoints and source scenario access. Do not register a new permission, migrate roles or require create/edit/run access for temporary previews.
5. Reject stale scenario/network fingerprints with an actionable explanation. Never silently substitute a newer map or relabel an old artifact.
6. Return only the original and selected route. Do not add a new alternatives search. Respect approach-dependent turn restrictions and vehicle class throughout each path.
7. Prove agreement between the preview policy and engine decisions for an actual engine arrival with the same network, closures, response, vehicle class and costs. A legal but policy-disallowed minor-road shortcut must not appear as the selected route.
8. Do not approximate a junction connector with a straight line through islands. Reuse available path geometry; identify any schematic-only segment explicitly.
9. Invalid arrangements should return useful per-selection feedback, including all-roads-blocked cases, without mutating the scenario or claiming the arrangement is runnable.
10. Keep vehicle admission/collision checks, reroute timers, threshold behaviour, metrics and lane-clearing transitions unchanged. Compare seeded pre/post-refactor results as well as unit tests; unchanged engine behaviour is a requirement, not an assumption based on the word "refactor".

## 10. Frontend integration

- Add a lazy-loaded Route Planner page and sidebar entry mapped explicitly to `scenarios:view`, including the application-shell guard.
- Reuse the Canvas 2D renderer through a static mode or a reusable rendering layer. Do not mount Dashboard websocket subscriptions, simulation controls, vehicle interpolation or live KPI updates.
- Add route and closure overlays without changing Dashboard or replay rendering by default.
- Store temporary settings in page state. Cache immutable network geometry by fingerprint.
- Debounce changes and cancel or ignore stale preview responses. A slow answer for Site A must not replace a newer Site B preview.
- Request lightweight route results after edits; do not reload the entire network each time.
- Draw on changes to camera, geometry or selection. An idle static map should not run an unnecessary continuous animation loop.
- Handle authentication expiry through the existing client flow; stop automatic retries for authorization failures.
- Keep the original Scenarios workflow, with only the timing-control removal described above.

## 11. Delivery order

All implementation tasks are pending. Follow the [step-by-step build plan](2026-11-10-route-planner-implementation.md), which specifies files, function contracts, API shapes, named tests and verification commands.

1. Remove the scenario timing inputs as an independent small change, preserving saved schedules.
2. Record seeded engine behaviour, then expose only the arrival decision and verify parity.
3. Build read-only source resolution and preview services, then authenticated APIs using `scenarios:view`.
4. Add static Canvas 2D overlays and the standalone page with temporary state.
5. Complete backend, frontend, browser, engine-parity and idle-rendering checks, then update user documentation and evidence.

## 12. Acceptance checks

### Routing and API

- [ ] Both sites with no closure show normal routes without claiming an improvement.
- [ ] A closure with a valid detour reaches the same destination using permitted roads.
- [ ] A disconnected destination, different exit and closed entry produce distinct explanations.
- [ ] Multiple closures are evaluated together for the displayed arrangement.
- [ ] Buses/trucks never receive a Sobrecarey route; allowed classes remain selectable.
- [ ] Main-road preference, turn restrictions, one-way streets and excluded movements match the engine.
- [ ] Only supported generated-demand entries are selectable; non-generating boundaries can still be returned as valid alternative exits.
- [ ] A disposable engine's actual vehicle arrivals demonstrate preview parity under matched inputs; pre/post-refactor seeded results remain unchanged.
- [ ] Shared pavement is derived from the backend geometry and unsupported roads explain why sharing is unavailable.
- [ ] Adaptive previews do not invent congestion or guarantee a future route; no additional alternative paths are returned or drawn.
- [ ] Historic scheduled closures are not combined across time, modified or mistaken for whole-run closures.
- [ ] Stale fingerprints and unauthorized access are refused clearly.
- [ ] A user with `scenarios:view` can preview without create/edit/run rights; role/permission tables do not change.
- [ ] Preview requests leave the live runtime, saved configuration and artifact tables unchanged.

### UI and browser

- [ ] Open a saved scenario with closures and one without closures.
- [ ] Try temporary closures without creating a scenario.
- [ ] Select/reset roads and responses by mouse and keyboard.
- [ ] Switch sites/scenarios during a pending request; stale results never replace the current selection.
- [ ] Inspect both sites at multiple zoom levels and at desktop/narrow widths.
- [ ] Confirm the map draws no generated vehicles or active signal indications.
- [ ] Verify New/Edit Scenario have no timing inputs and a new closure applies to the whole run.
- [ ] Edit an unrelated setting in an older scheduled scenario and verify its stored schedule remains intact.
- [ ] Check Dashboard, replay and Compare Runs still render normally after any shared-renderer change.
- [ ] Measure preview response time and idle redraw behaviour on the target laptop; report measured values rather than promising instantaneous routing.

### Verification commands

Use the repository's Python environment and isolated database/artifact paths. Existing relevant checks include:

```powershell
.venv/Scripts/python.exe -m pytest tests/test_closure_check.py tests/test_closure_responses.py tests/test_contraflow.py tests/test_vehicle_access.py tests/test_study_site_static_routing.py
npm run test:visualization
npx tsc -b
npx eslint src
npm run build
```

Add the new preview-service/API tests to the backend command. Run the full backend suite for the completed feature before delivery, especially if shared routing or permission code changes. Record test counts and browser evidence from the actual implementation; this plan supplies no passing test claims.

## 13. Definition of done and limits

The feature is complete when a user can select a scenario or a site, choose temporary whole-run closures and responses, and clearly see where a selected vehicle class can travel using the current engine rules, without starting a simulation or changing saved work. The requested scenario timing fields are removed while existing historical schedules are preserved.

The page is a **scenario-planning preview**. Geometry is provisional; route availability is modelled, and shared pavement is hypothetical. It does not establish legal approval, physical traffic-control design, field validation or measured congestion benefits.

No engine/RL redesign, new path-search algorithm, multi-alternative routing, role migration, new network geometry, model retraining, new PDF report, schedule editor, scenario autosave, single-lane alternating traffic, desktop installer or live-vehicle tracking is part of this implementation scope. Sharing existing decision code is allowed only as a verified behaviour-preserving refactor.
