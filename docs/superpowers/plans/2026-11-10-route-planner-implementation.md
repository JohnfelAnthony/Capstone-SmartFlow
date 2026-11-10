# Route Planner implementation steps

**Status: pending implementation.** Revised 2026-11-10, Asia/Singapore, against local `main` at `725da90`. This document and its [design](2026-11-10-route-planner.md) are documentation only. The design starts with the owner's original problem and records the accepted scope.

**Goal:** add a static whole-site Route Planner that compares an original route with one route under a proposed closure arrangement. Support saved-scenario inspection and temporary arrangements, all existing eligible closure responses, vehicle-class restrictions and exact shared-pavement geometry. Remove the closure timing inputs from New/Edit Scenario while preserving historical schedules.

**First-version constraints:** no multiple-alternative search; no traffic generation, playback or live queues; no schedule controls; no scenario writes; no new permission or role migration; no changed engine behaviour or RL contract. Keep desktop work separate. Do not commit, push, merge or build an installer merely because this plan contains a delivery checkpoint; follow the owner's authorization at implementation time.

## 1. Engine arrival route contract (owner decision, option B)

Expose `TrafficEngine.arrival_route(self, source, destination, *, vehicle_type, costs) -> tuple[list[str], bool]`. It returns the lane sequence and whether the vehicle is diverting. Move only the inline decision from `_spawn_vehicles_and_pedestrians`: the nearest-exit cut check on the usual route, routing around closures and falling back to `_best_open_exit`. Call the method in place with the same inputs and order. Keep admission, pending demand, vehicle creation, destination updates, counters and random draws at the call site.

Leave `_reroute`, `_best_open_exit` and `_travel_costs` in place and unchanged. Do not create `simulation/routing_policy.py`. Live lane draining, reservations and network swaps stay in the engine.

For the original and selected routes, construct independent `TrafficEngine` instances and never start or step them. The original uses the base network with no closures. The selected route uses the validated initial arrangement and responses. For established sharing, derive the effective network with `contraflow.shared_network` and remove shared directions from the set closed to traversal. Keep the base fingerprint. Static arrivals use existing default costs. Adaptive arrivals use the disposable engine's `_travel_costs()`, which is queue-free because it has no vehicles.

Verify seeded runs before and after the extraction. Independently verify the preview against an actual disposable engine arrival under matching inputs.

## 2. API contract

Create `services/route_preview.py`, request/response models in `backend/schemas.py`, endpoints in `backend/main.py`, and matching client types in `src/api/routes.ts`.

Both endpoints require `require_current_user` and `require_permission(user, "scenarios", "view")`. Respect existing access to the referenced scenario. Previewing needs no create/edit/run permission. No permission catalog or database migration is required.

### Shared request types

```ts
type RouteSource =
  | { kind: "scenario"; scenario_id: number }
  | { kind: "network"; network_id: string }

type RouteVehicleClass = "car" | "motorcycle" | "tricycle" | "bus" | "truck"
type ClosureResponse = "side_street" | "side_street_adaptive" | "share" | "nearest_exit" | "wait"

type ClosureOverride = {
  closed_lanes: string[]
  closure_responses: Record<string, ClosureResponse>
}

type RouteContextRequest = { source: RouteSource; vehicle_type: RouteVehicleClass }
type RoutePreviewRequest = RouteContextRequest & {
  expected_network_sha256: string
  entry_id: string
  destination_id: string
  closure_override?: ClosureOverride
}
```

`closure_override` is a complete replacement of the initial closure arrangement, not an event schedule or patch. Omitted means use the source's initial arrangement. `{closed_lanes: [], closure_responses: {}}` explicitly previews all directions open. Reject null, duplicate/unknown lanes, orphan response keys and unsupported response values. Do not accept arbitrary `engine_config`, costs, simulation time or client-supplied geometry.

### `POST /api/routes/context`

Resolve the source without configuring/starting the live runtime. Return:

```ts
type RouteContext = {
  source: RouteSource
  source_label: string
  network_id: string
  network_sha256: string
  network_binding: "saved_fingerprint" | "current_unpinned" | "current_network"
  geometry: VisualNetwork                // existing visual-network payload type
  entries: Array<{ id: string; label: string; lane_ids: string[] }>
  destinations: Array<{ id: string; label: string }>
  eligible_pairs: Array<{ entry_id: string; destination_id: string }>
  initial_closures: ClosureOverride
  roads: Array<{ lane_id: string; road_id: string; label: string; direction: string }>
  basis: "initial_arrangement_zero_queue"
  has_later_closure_changes: boolean
  notices: Array<{ code: string; message: string }>
}
```

Use the existing `VisualNetwork` shape or its actual exported type name; do not invent a second map schema. `entries` uses `network.demand_boundaries` and lanes leaving those boundary nodes into the network. Filter class-inaccessible entries. Keep otherwise eligible entries visible when temporarily closed so the user can inspect the waiting outcome.

Normal destinations also follow generated-demand boundary/pair rules. Exclude the same source/destination and `side_street_only_pairs`, and reject class-prohibited pairs. Build eligibility without the proposed closures so closing a road does not remove the very trip being inspected. Physical non-generating exits remain available to `best_open_exit` and may be returned as substituted destinations.

### `POST /api/routes/preview`

Re-resolve the source on the server; require the expected fingerprint to match the base network. Recheck the scenario's own saved fingerprint as well. Return lightweight paths and settings, not the full network again:

```ts
type RoutePath = {
  lane_ids: string[]
  destination_id: string
  destination_label: string
  segments: Array<{
    kind: "lane" | "connector"
    lane_id?: string
    from_lane_id?: string
    to_lane_id?: string
    points: Array<{ x: number; y: number }>
  }>
}

type RoutePreview = {
  network_id: string
  network_sha256: string                 // always base, never derived contraflow
  basis: "initial_arrangement_zero_queue"
  routing_mode: "static" | "adaptive"
  arrangement_valid: boolean
  effective_closures: ClosureOverride
  effective_closed_lanes: string[]       // shared directions can remain drivable
  response_options: Record<string, Array<{
    value: ClosureResponse
    enabled: boolean
    reason: string | null
  }>>
  original: RoutePath | null
  selected: RoutePath | null
  outcome: "unchanged" | "detour" | "alternative_exit" | "waiting_entry" | "no_route" | "invalid_arrangement"
  reason: string
  intended_destination_id: string
  actual_destination_id: string | null
  shared_roads: SharedRoad[]             // existing shared-road visual contract
  uses_shared_pavement: boolean          // independent of route outcome
  notices: Array<{ code: string; message: string }>
}
```

There is no `alternatives` field. Identical lane IDs on shifted shared geometry must still draw different paths; `uses_shared_pavement` explains the change even when the topological outcome is `unchanged`.

### Resolution and decision rules

1. Resolve the network/config/fingerprint with existing validation conventions. Inspect `simulation/network_registry.py::engine_for_scenario`; extract its pure network/config resolution if needed rather than involving the live runtime. Do not update a missing fingerprint in the database. Label a legacy unpinned scenario `current_unpinned` and bind this preview to the returned current fingerprint.
2. Preserve the complete source configuration. Create an isolated initial snapshot by applying normalized zero-time closure and speed events in the same order as the engine. Report later closure events as not represented. Do not union future closures or apply hidden warm-up.
3. Apply any complete closure override to that snapshot, then validate responses using existing rules. Do not silently settle incompatible choices in a saved scenario. Return reasons and let the user explicitly select a valid arrangement.
4. Obtain the effective network for the assumed established sharing arrangement from `contraflow.shared_network`. Remove established shared directions from the set closed to traversal. Keep the base network immutable and keep its fingerprint in the API.
5. Calculate `original` on the base network with closures/sharing removed, retaining the applicable initial speed settings. Calculate `selected` by calling `arrival_route` on a disposable engine built on the effective network. Static arrivals use the existing default route costs; adaptive arrivals receive that engine's queue-free `_travel_costs()`. Do not inject fictional queues.
6. For a closed entry, use the engine's entry-availability semantics to return `waiting_entry`. Congestion/vehicle-footprint admission is not predicted. If useful, extract the existing topology/class entry predicate for reuse rather than broadening it.
7. Use `TrafficEngine.arrival_route` for forced-exit and unreachable-destination handling, even when a detour to the original destination exists. Preserve actual destination separately from requested destination.
8. Build each path from lane polylines plus `RoadNetwork.connector` using the corresponding base/derived network. Verify permitted connections before drawing. These are centreline route illustrations, not swept-body clearance certification. Do not replace missing connections with straight lines through islands.
9. All-roads-closed or response-incompatible arrangements with otherwise valid identifiers return `arrangement_valid=false`, reasons, disabled response options and no asserted selected route. Do not coerce them into a runnable configuration.

Errors: unauthenticated `401`; insufficient permission `403`; missing scenario/network `404`; changed/stale fingerprint `409` with a string explaining reload/recreate; malformed identifiers, unsupported class or invalid trip selection `422`. Keep `detail` human-readable for the existing API client. Do not change existing endpoints' error behaviour as part of this work.

## 3. Build tasks

All tasks are unchecked. Paths below are relative to the repository root. New file names are proposed implementation targets, not files claimed to exist today.

### Task 1 — Remove closure timing editors independently

**Modify:** `src/components/closure-picker.tsx`. **Read:** `src/lib/closures.ts`, `src/lib/closures.test.ts`, `src/components/scenarios-page.tsx`.

1. [ ] Remove the two timing inputs, `Input` import, `setTime` handler and render-only validation references made unused by their removal.
2. [ ] Keep new closure defaults `{start: 0, end: null}` and add one short whole-run explanation. Keep response options, reopen controls and read-only saved timing descriptions.
3. [ ] Preserve existing schedule helpers, backend validation, non-closure events and complex locked schedules. Removing the input widgets is not permission to delete historical event support.
4. [ ] Run `npx vitest run src/lib/closures.test.ts`, `npx tsc -b` and `npx eslint src/components/closure-picker.tsx`.
5. [ ] Browser-check New Scenario, Edit Scenario, reopen and response changes with disposable scenarios. Verify a new closure is whole-run and that editing an unrelated field in a scheduled scenario preserves event values. Reuse existing coverage; do not add a test that only searches source text for removed labels.

**Checkpoint:** this small change can be delivered separately. No routing refactor is needed for it.

### Task 2 — Characterize and expose the engine arrival route

**Create:** `tests/test_engine_arrival_route.py`. **Modify:** `simulation/traffic_engine.py` only at the inline entry-route decision and its new method. **Read:** `simulation/road_network.py`, `simulation/closure_responses.py`.

1. [ ] Record seeded synthetic results before the engine change on both sites with seeds 101 and 102. Cover no closure, detour, adaptive, nearest exit and sharing. Document the configuration and reproduction commands.
2. [ ] Write and run the following tests. Confirm each fails because the arrival method is missing:
   - `test_arrival_keeps_main_route_when_reachable`
   - `test_arrival_nearest_exit_overrides_available_detour`
   - `test_unreachable_destination_uses_non_generating_exit`
   - `test_vehicle_class_and_turn_rules_are_respected`
   - `test_arrival_does_not_mutate_network_or_inputs`
3. [ ] Extract only the entry decision into `arrival_route(self, source, destination, *, vehicle_type, costs) -> tuple[list[str], bool]` and replace it with the method call. Leave `_reroute`, `_best_open_exit` and `_travel_costs` untouched.
4. [ ] Rerun the tests and the focused engine regression command in section 4. Repeat the seeded runs and compare routes, destinations, diversion and reroute counts, conservation and state digests.
5. [ ] Any difference blocks the task. Never update expected digests to make tests pass. Stop and report if parity cannot be established.

**Checkpoint:** arrival behaviour is unchanged. Keep the engine version and model contract.

### Task 3 — Build source context and static preview service

**Create:** `services/route_preview.py`, `tests/test_route_preview.py`, `tests/test_route_preview_parity.py`. **Modify if needed for pure reuse:** `simulation/network_registry.py`. **Read:** `simulation/scenario_config.py`, `services/native_scenario_service.py`, `services/visual_network_service.py`, `simulation/contraflow.py`.

1. [ ] Implement `route_context(source, vehicle_type)` and `preview_route(request)` using the section 2 contract. Keep endpoint/auth concerns outside the preview service.
2. [ ] Resolve initial source state without the live runtime, validate source fingerprints, and create class-aware demand-entry/destination choices. Obtain readable labels from existing helpers.
3. [ ] Implement complete closure override semantics, response explanations, derived shared geometry and two-route outcome classification.
4. [ ] Add these service cases in `tests/test_route_preview.py`:
   - `test_entries_use_demand_boundaries_and_class_access`
   - `test_closed_entry_remains_selectable_and_reports_waiting`
   - `test_non_generating_boundary_can_be_returned_as_diversion_exit`
   - `test_disallowed_generated_pair_is_rejected`
   - `test_initial_snapshot_applies_zero_time_events_only`
   - `test_empty_override_clears_initial_closures_without_mutating_schedule`
   - `test_shared_paths_match_derived_network_and_keep_base_fingerprint`
   - `test_no_route_and_invalid_arrangement_are_distinct`
   - `test_stale_saved_fingerprint_is_refused`
5. [ ] In `tests/test_route_preview_parity.py`, add `test_preview_matches_disposable_engine_vehicle_arrival` for static, adaptive zero-queue, forced exit, no-route and sharing cases, including allowed/restricted classes. Compare lane sequence, destination and diversion status against an actual disposable engine arrival path; do not compare two calls to the new helper alone.
6. [ ] Assert that the preview service itself never steps/configures a live runtime and does not modify input scenario dictionaries or base-network payloads.

**Run:** `& "C:/Users/jhepo/Desktop/trapik2/SmartFlow/.venv/Scripts/python.exe" -m pytest tests/test_engine_arrival_route.py tests/test_route_preview.py tests/test_route_preview_parity.py -q`.

### Task 4 — Add APIs using the existing permission

**Modify:** `backend/schemas.py`, `backend/main.py`. **Create:** `tests/test_route_preview_api.py`. **Read:** `tests/test_shared_session_and_import.py`, `tests/test_closure_check.py`, `auth.py`.

1. [ ] Define discriminated source models, enum restrictions, complete override semantics and typed responses. Enforce identifier validity and bounded request size using existing conventions.
2. [ ] Add the two POST endpoints and `scenarios:view` checks. Use disposable database fixtures for scenario loading tests; restore dependency overrides after every case.
3. [ ] Add these cases:
   - `test_view_only_user_can_preview_without_edit_or_run_permission`
   - `test_preview_requires_authentication_and_scenarios_view`
   - `test_context_and_preview_use_same_network_fingerprint`
   - `test_network_change_between_context_and_preview_returns_409`
   - `test_missing_source_and_invalid_trip_return_expected_errors`
   - `test_preview_with_disposable_arrival_engines_preserves_saved_data_and_live_runtime`
4. [ ] Snapshot relevant database rows and runtime state before/after preview requests, including when a disposable live run is already active. No new permission/role rows or research artifacts may appear.

**Run:** `& "C:/Users/jhepo/Desktop/trapik2/SmartFlow/.venv/Scripts/python.exe" -m pytest tests/test_route_preview_api.py tests/test_network_registry.py -q`.

### Task 5 — Add client contracts and temporary page state

**Create:** `src/api/routes.ts`, `src/lib/route-planner.ts`, `src/lib/route-planner.test.ts`, `src/api/routes.test.ts`. **Read:** `src/api/client.ts`, `src/api/scenarios.ts`, `src/api/visual-network.ts`, `src/lib/closures.ts`.

1. [ ] Implement typed `getRouteContext` and `previewRoute` wrappers. Use the existing `apiRequest` and its `AbortSignal` support; do not implement a second auth/session layer.
2. [ ] Define a small reducer/state model for source/class selection, current closures, response choice, trip selection, reset and request generation. Temporary state never calls scenario create/update APIs.
3. [ ] After a class change, reload eligible choices and clear an invalid trip. Do not issue a preview until the source fingerprint and trip are valid.
4. [ ] Debounce closure edits; abort or ignore stale responses by source/class/config generation. Retain the map during a lightweight update and show a nearby loading state.
5. [ ] Test reset-to-saved versus explicit-empty overrides, invalid trip clearing, unchanged source configuration, stale responses, `401` retry suppression and both API payload shapes. Use existing Vitest node/pure-helper patterns.
6. [ ] Extract or reuse response coordination rules so selecting adaptive routing remains consistent across relevant closures. Visibly explain any changed selections instead of silently coercing a source scenario.

**Run:** `npx vitest run src/lib/route-planner.test.ts src/api/routes.test.ts src/lib/closures.test.ts` and `npx tsc -b`.

### Task 6 — Add optional static overlays to the shared canvas

**Modify:** `src/components/simulation-canvas-2d.tsx`. **Create:** `src/simulation/route-planner-overlay.ts`, `src/simulation/__tests__/route-planner-overlay.test.ts`, `src/components/route-planner-map.tsx`. **Read:** `src/simulation/map-navigation.ts`, `src/simulation/scene-geometry.ts`, `src/components/compare-map.tsx`.

Proposed optional renderer input:

```ts
type PlannerOverlay = {
  original: RoutePath | null
  selected: RoutePath | null
  closedLaneIds: readonly string[]
  sharedRoads: readonly SharedRoad[]
  selectedLaneId: string | null
}
// Existing props remain valid; defaults preserve live/replay behaviour.
// staticMode?: boolean
// plannerOverlay?: PlannerOverlay
// onRoadDirectionSelect?: (laneId: string) => void
// fitRequest?: { revision: number; target: "network" | "routes" }
```

1. [ ] Use `frame=null` with explicit static mode. Do not fabricate a live RenderFrame or show live signal/vehicle/queue state.
2. [ ] Render grey original and green selected paths, arrows, red closure hatching and exact amber shared-road geometry in the same coordinate system/camera as the existing roads.
3. [ ] Implement road-direction picking and fit bounds in pure helpers. Do not recompute routes in TypeScript. Keep route-segment boundaries so drawing does not accidentally join discontinuous pieces.
4. [ ] Make the static map redraw only when its geometry, overlay, theme, viewport or camera changes. Optional props must not disable live interpolation or replay in existing callers.
5. [ ] Add helper tests for world/screen selection, opposing directions, shared-path bounds, no-route fit fallback, and identical lane IDs with different base/shared geometry.
6. [ ] Verify Dashboard and Compare Runs compile without new required props. Include live/replay/browser regression checks in Task 8 because unit tests cannot establish canvas appearance.

**Run:** `npx vitest run src/simulation/__tests__/route-planner-overlay.test.ts src/simulation/__tests__/map-navigation.test.ts` and `npx tsc -b`.

### Task 7 — Assemble the page and navigation

**Create:** `src/components/route-planner-page.tsx`, `src/lib/page-access.ts`, `src/lib/page-access.test.ts`. **Modify:** `src/App.tsx`, `src/components/app-sidebar.tsx`; use the existing stylesheet only if layout needs it.

1. [ ] Add a lazy-loaded Route Planner page. Provide source selector, trip/class controls, static map, road selection list, response panel, reset/clear controls, legend and one short assumptions notice.
2. [ ] Give the new navigation item its own identity, `route-planner`, but resolve its permission through a small shared helper: `permissionPageFor("route-planner") === "scenarios"`; all existing keys map to themselves. Use that helper for sidebar visibility and the application's page guard, preserving existing admin handling.
3. [ ] Gate rendering as well as navigation with `scenarios:view`. Do not modify role definitions, landing paths or permission records. Test authorized viewer, denied viewer and admin cases.
4. [ ] Render disabled response options with reasons, read-only legacy schedule notices, no-route/waiting/different-exit outcomes, and "Temporary changes — saved scenario unchanged".
5. [ ] Use "Route under these conditions" and show actual versus intended destination for diversions. Do not add alternative paths, a winner, delay savings or future congestion claims.
6. [ ] Use existing shadcn controls, keyboard labels and responsive layout. Provide selection outside the canvas for keyboard users. Include neither timing inputs nor a timeline.
7. [ ] Check source switching, cancellation, loading, refresh after a fingerprint conflict and session expiry. No stale response may redraw an old network.

**Run:** `npx vitest run src/lib/page-access.test.ts src/lib/route-planner.test.ts`, `npx tsc -b` and `npx eslint src`.

### Task 8 — Final verification and evidence

**Update after verification:** `docs/PROGRESS_AND_HANDOFF.md`, `docs/ARCHITECTURE_AND_PLAN.md`, `src/components/help-about-page.tsx`, and both Route Planner documents' task status.

1. [ ] Run section 4's complete checks with disposable data and record commands/results. Do not mark a task complete merely because its source file exists.
2. [ ] Browser-test both sites: no closure; a valid detour; alternative exit; waiting entry; allowed shared pavement; prohibited sharing; class restriction; invalid arrangement; reset; saved scenario with later schedule; stale fingerprint.
3. [ ] Verify keyboard use, multiple zoom levels, desktop/narrow layouts, readable arrows and both directions of shared pavement. Capture representative screenshots.
4. [ ] Verify New/Edit Scenario timing fields are absent and existing schedules survive an unrelated edit. Verify Dashboard live motion, replay and Compare Runs still render and navigate correctly.
5. [ ] Inspect network calls: no simulation start, websocket, recording, scenario write or training request originates from Route Planner. Test session expiry without a retry loop.
6. [ ] Measure warm preview response latency and idle redraws on the target laptop for both sites. Separate cold geometry loading from subsequent route updates; record actual timing without claiming a budget was met unless measured.
7. [ ] Confirm network artifacts/fingerprints, engine declaration, metric catalog and model contracts did not change. Preserve research data and existing expected results.
8. [ ] Document only verified behaviour. Desktop integration and packaging are separate future work.

## 4. Verification commands and evidence rules

Run from the repository root using the main checkout's Python at `C:/Users/jhepo/Desktop/trapik2/SmartFlow/.venv/Scripts/python.exe`. Use existing pytest fixtures or an isolated test database; never point write-capable tests at the owner's working database. The new test files below exist only after their tasks are implemented.

```powershell
# Shared policy and existing behaviour
& "C:/Users/jhepo/Desktop/trapik2/SmartFlow/.venv/Scripts/python.exe" -m pytest tests/test_engine_arrival_route.py tests/test_closures.py tests/test_closure_check.py tests/test_closure_responses.py tests/test_contraflow.py tests/test_contraflow_engine.py tests/test_vehicle_access.py tests/test_study_site_static_routing.py tests/test_native6_compat.py tests/test_closure_free_digests.py -q

# New service, matched-input engine parity and API
& "C:/Users/jhepo/Desktop/trapik2/SmartFlow/.venv/Scripts/python.exe" -m pytest tests/test_route_preview.py tests/test_route_preview_parity.py tests/test_route_preview_api.py tests/test_network_registry.py -q

# Final backend suite
& "C:/Users/jhepo/Desktop/trapik2/SmartFlow/.venv/Scripts/python.exe" -m pytest tests -q --basetemp "$env:TEMP/sf-route-full"

# Frontend and production build
npm run test:visualization
npx tsc -b
npx eslint src
npm run build
git diff --check
```

Before extraction, collect the existing deterministic fixture outputs and run the corresponding existing regressions on that revision. After extraction, compare the same seeds, configurations and checkpoints. Keep any non-Git artifacts isolated and document how to reproduce the comparison. A newly added test that compares two wrappers around the same function is not sufficient evidence that the original engine behaviour was preserved.

Do not start long RL training or use reserved final seeds for verification. If a genuine engine defect prevents parity, report it separately instead of quietly fixing it inside this preview feature and declaring existing models compatible.

## 5. Completion checklist

- [ ] Original problem and all revised owner decisions are satisfied.
- [ ] At most two route paths are shown; all supported response choices remain available where eligible.
- [ ] Engine spawner and preview use the same arrival decision. Seeded engine results match and in-network rerouting is untouched.
- [ ] The static zero-queue assumption and historical schedule limitation are visible.
- [ ] Generated-demand entries and class/turn rules are enforced on the server.
- [ ] Existing `scenarios:view` controls access; no role migration occurred.
- [ ] Shared geometry is exact for the model; lane clearing remains a live-engine responsibility.
- [ ] Scenario timing editors are removed without rewriting saved schedules.
- [ ] No user scenario, research artifact, engine behaviour or RL contract changed as a side effect.
- [ ] Backend, frontend and browser evidence is recorded, including map regressions and preview performance.

Until those checks are verified, these files remain a design and build plan rather than a claim that the feature is implemented.
