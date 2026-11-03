# SmartFlow Road Editor — implementation plan

Date: November 2, 2026. Status: **partially implemented; not ready for network activation.** The local editor can open and edit a draft, save a project and download an explicitly unvalidated JSON draft. Native structural preview is available, but physical-clearance validation, the authenticated installation workflow and other tasks below remain open. See `tools/road_editor/README.md` and the current handoff for the precise scope and verification.

## 1. Outcome and architecture

Build a local companion tool, similar to Field Observer, for editing the actual SmartFlow road network. A researcher can open Site A or Site B, drag road geometry, change carriageway width, add roads and connections, inspect the resulting native lanes, and apply a reviewed revision to SmartFlow. The interface should use ordinary traffic language and metres.

Use plain HTML, CSS and JavaScript modules with an SVG editor canvas. Use a small Python standard-library HTTP server on `127.0.0.1`, reusing the repository Python environment and the native `RoadNetwork` parser. No React, Three.js, new web framework, CDN, npm build step, separate ML environment or internet connection is required for the editor. The existing main application remains responsible for authenticated activation.

The Python side owns authoritative validation, native lane/connector preview and fingerprint calculation. JavaScript owns editing, selection, camera controls and draft history. Do not port native junction clipping or lane offsets into a second JavaScript physics model.

Package under `tools/road_editor/` with a root `Start Road Editor.cmd`, a Python module entry point, static HTML/CSS/JS, tests and a README. Normal launch opens a browser; `--no-browser`, `--port` and `--data-dir` support testing. Select an available local port and use `webbrowser.open`; do not leave a visible command window solely to host the server. Show startup failures with a readable message and log path.

## 2. User workflow and interface

1. Open a registered network or import an existing native network JSON.
2. Save an editable project copy. Source files remain untouched while editing.
3. Edit the network in the map; inspect numeric properties and native preview.
4. Resolve validation errors. Save drafts at any time, including temporarily invalid edits.
5. Export a validated candidate JSON, its validation report and a visual overview.
6. In SmartFlow, an administrator imports the candidate, reviews the change summary and explicitly applies it. Existing scenarios are not silently rewritten.

Layout: top file/history/validation toolbar; left tool palette; large SVG map; right selected-object inspector; bottom status line showing coordinates, distance and draft status. Include Fit network, Fit selection, zoom, pan, grid, north arrow and a scale bar. Use a restrained light theme and visible selection/error outlines. The editor must work at 1280×720 and above; touch editing is out of scope for v1.

### Editing tools

- **Select/move:** select roads, nodes, vertices or islands; drag vertices and nodes, with numeric coordinate entry. Moving a node updates all incident road endpoints in the same undoable action. Internal road vertices remain fixed unless explicitly selected.
- **Road shape:** insert and remove intermediate vertices. Keep at least two points and preserve endpoint attachment. Dragging an endpoint requires an explicit reconnect operation; it must not silently detach from its node.
- **Road properties:** name, one-way/two-way, lanes per direction, carriageway width per direction and speed in km/h. Convert speed to the engine's m/s. Show both the per-direction and total paved width so two-way width is not mistaken for total width.
- **Add road:** click existing nodes or create endpoint nodes, then draw the intervening polyline. Offer one-way and two-way roads; default new roads to one lane per direction, 3.3 m per direction, 30 km/h and provisional geometry.
- **Reverse direction:** for a one-way road, swap source/target and reverse the shape. Preview affected turn restrictions before committing the edit. Reject the operation if a restriction cannot be remapped unambiguously.
- **Split/connect:** insert a junction by splitting a road at a selected point. A visual crossing alone does not create connectivity. Connecting crossing roads must explicitly split both at a common node. Native clearance may make short segments invalid; display the affected segments rather than silently extending them.
- **Delete:** show incident roads and turn restrictions before deleting a connected node or road. Remove references only as part of the confirmed, undoable edit. Never silently repair broken topology on export.
- **Junction properties:** distinguish boundary nodes, study junction and neighboring no-signal junctions. Preserve Site B's `tagum_site_b_j` study identity. All added neighboring junctions default to `first_come`, including their visual no-signal state. A separate explicit action changes the study junction; for Site B v1 this action is disabled to preserve the owner's scope.
- **Turn restrictions:** list allowed/disallowed movements using the native incoming/outgoing lane IDs and preview their connectors. Do not add U-turn support or infer legal movements from road appearance.
- **Island outlines:** draw and edit raised-island polygons, mark planted/paved, and label them. Show that current island rendering support does not itself enforce collision avoidance. Route/island validation is required before activation.
- **History:** undo/redo for every geometry/property edit; one drag is one operation. Keep 100 operations in memory. Save changes explicitly and autosave a recovery copy after 2 seconds of inactivity. Offer recovery on restart; never replace the last explicit save without informing the user.

### Reference images

Allow local PNG/JPEG imports as a background layer. The user marks two image points and enters their real separation to set scale, then aligns an anchor and rotates the image to native north. Provide opacity, lock and hide controls. Store the image and transform in the editor project, never in the runtime network JSON. Label visually estimated scales separately from measured scales. Reject images over 20 MB or 40 million decoded pixels with a helpful message.

Do not depend on Google tiles or scrape map imagery. Cached OSM JSON continues to come through the existing importer/builder; the editor consumes native network JSON. Live OSM downloading and automatic tracing are later features.

## 3. Network contract and preservation rules

Keep the existing native payload (`id`, `version`, `source`, `nodes`, `roads`, optional `prohibited_turns` and `islands`). A project wrapper has its own version and stores the base network fingerprint, complete network payload, edit history summary, image transform and project metadata. The native network's `version` is not the editor-project schema version.

- Preserve unknown JSON fields and original OSM metadata on import/save/export. A no-op round trip must retain the original native fingerprint. Editor timestamps, camera state and selection must not change it.
- Preserve existing IDs. Allocate stable new IDs such as `edit_node_1` and `edit_road_1` with collision checks; never renumber the network to match array order. Keep the selected study junction first where the current engine relies on that default.
- Source/target endpoints must agree with node coordinates. Road shape coordinates remain native metres, x east and y north; browser y inversion is a presentation transform only.
- The current width override is `width_per_direction_m`, allowed from 2.5 to 15 m. The current engine reads lane count from `osm_tags.lanes`: for one-way roads store lanes per direction, and for two-way roads store twice that number. Make this conversion in a tested adapter. Preserve the original OSM tag in edit provenance when changing it. Do not silently truncate malformed tags or double-count width.
- Road width and lane count are independent settings. When editing the count, offer an explicit “Set width to lanes × 3.3 m” action; otherwise retain the saved width. Warn if width and lane count are inconsistent.
- A split keeps the original road ID on the source-side piece and allocates a new ID for the target-side piece. Remap endpoint turn restrictions directionally; do not copy restrictions onto both pieces. Report changed IDs in the export manifest for scenario review.
- Record changed geometry as a manual provisional edit unless the user supplies a measurement source. Preserve the original source attribution. Manual editing never marks a network calibrated or field-validated.
- Retain the full-JSON fingerprint convention already used by SmartFlow. Do not introduce a different hash that ignores width, restrictions, islands or control metadata.

## 4. Validation, preview and local endpoints

Provide two distinct render layers: editable source centerlines and the exact native preview returned by `RoadNetwork.visual()`. The latter shows lane footprints, directional arrows, junction outlines, clipped stop lines and connectors. For invalid drafts retain the source layer and mark any previous native preview stale. Never present the previous successful preview as the current geometry.

Local tool API:

| Endpoint | Purpose |
| --- | --- |
| `GET /api/networks` | List registered networks and current fingerprints, read-only |
| `GET /api/networks/{id}` | Load a registered payload by allowlisted ID |
| `GET/POST /api/projects` | List/create editor-owned projects |
| `GET/PUT /api/projects/{id}` | Read/save a project, with an expected revision to prevent lost saves |
| `POST /api/validate` | Validate the submitted draft and return issues, current fingerprint and native visual preview |
| `POST /api/export` | Validate again and return candidate JSON plus review report; no activation |

Use structured issue objects with severity, code, message and affected road/node/island IDs so clicking an error focuses the relevant object. Run cheap browser checks while editing; debounce authoritative server validation by 300 ms after an operation. Attach a request revision and ignore late responses for older drafts. Keep saving drafts independent of server validation success.

Validation layers:

1. Validate JSON size (5 MB), finite numeric values, unique IDs, known endpoint references and collection shapes before constructing the native network. Normalize parser exceptions into actionable errors, not raw tracebacks.
2. Run `RoadNetwork` for actual widths, road-length/clearance requirements, connectivity, allowed turns and the maximum of four incoming approaches per physical junction.
3. Check polygon simplicity/nonzero area, duplicate consecutive road points, accidental self-crossings and road footprints touching or crossing raised islands. Reject an island crossing an active lane footprint. A connector's centerline alone is insufficient: inspect swept footprints for supported vehicle sizes and permitted lateral positions. Conservatively block activation where clearance cannot be established; allow saving the draft.
4. Check directed reachability between boundaries and the study junction. Flag unreachable incoming/outgoing boundaries and restrictions that make a usable road a dead end. Report disconnected components explicitly.
5. Show “structurally valid”, “clearance checked” and “traffic validation not run” independently. A green structural check must not imply zero collisions, field fidelity or successful RL experiments.

The editor must not resolve the existing Site B geometry problems by suppressing errors. If its current network fails clearance validation, load it with those errors visible and allow the user to repair it.

Server containment follows Field Observer's established pattern: loopback only, per-launch mutation token, same-origin checks, bounded request sizes and editor-owned directories. Serve only packaged assets. Do not accept arbitrary filesystem paths, execute imported content or run uploaded JavaScript. Render imported names using text content. Use project UUIDs and original filenames only as display metadata. Do not import ML training dependencies just to start the editor.

## 5. Applying a revision to SmartFlow

The editor exports candidates; activation belongs to the main application's authenticated admin flow. Add a small “Road networks” section to the existing administration/settings area, using current components. Provide candidate upload, old/new overview, changed-object counts, validation issues, affected scenario count and an explicit Apply button. A button to open the companion launcher may follow the existing admin-only Field Observer launcher pattern.

Add `POST /api/admin/networks/{id}/preview` and `POST /api/admin/networks/{id}/apply`. Apply accepts the candidate and expected current fingerprint, repeats validation on the server, and requires the existing admin permission. Do not trust the editor's exported verdict. For v1 activation supports registered Site A/B IDs only; adding new independent study sites is outside scope.

Apply must:

- Acquire the existing workload-admission exclusion so a run/training/recording cannot start during replacement. Refuse running or paused live simulation, playback and active training/evaluation/recording jobs with an actionable conflict message. Audit existing admission paths before implementation; do not invent a second unrelated lock.
- Compare the expected fingerprint with the installed network and return conflict on a stale candidate.
- Save an immutable revision named by network ID and hash beside the registry, then atomically replace the registry entry to reference it. Keep the previous registered file. A failed write must leave the old registry usable; unused revision files can be retained for recovery.
- Reload through the existing registry loader and clear/reset stale idle simulation and visual-network caches before releasing the exclusion. Verify that immutable filename changes bypass the loader's old cached file identity.
- Record the old/new hashes, administrator, date, changed objects and validation status in the audit log.
- Preserve old recordings with their embedded networks. Do not relabel old results, reuse field PASS records, or rewrite model contracts.
- Leave existing scenarios pinned to their original hash. List the affected scenarios and let the user create a reviewed copy on the revised network. Do not automatically remap deleted lane IDs, movements, schedules or signal plans.
- Include the active revision and referenced files in backup/restore. Rollback uses the same guarded apply workflow; it does not erase history or magically restore acceptance for changed scenario inputs.

Registering edited revisions must coexist with OSM generation: generators write candidate output, while the registry identifies the active installed revision. Explain this in the tool README so regenerating the canonical JSON cannot silently overwrite the user's active edits.

## 6. Ordered implementation and acceptance

Preserve current uncommitted work. Reconcile these tasks against the latest checkout before implementing; the Site B expansion and island-support changes may still be uncommitted. Use an existing suitable checkout and a `codex/road-editor` branch when safe; do not discard or accidentally commit unrelated work.

### Task 1 — Local tool shell and read-only loading

- [ ] Implement launcher, standard-library server and static interface; open a registered site and draw native preview.
- [ ] Verify offline startup, no new package installation, no application/database mutation, Windows paths with spaces, port conflicts, token rejection and clean shutdown.

### Task 2 — Project storage and lossless round trips

- [ ] Implement project wrapper, explicit save, autosave recovery, revision conflicts and JSON import/export.
- [ ] Test unknown-field preservation, unchanged network fingerprints, damaged project recovery and interrupted writes. Use temporary directories and isolated registries.

### Task 3 — Geometry editing and inspector

- [ ] Implement selection, source/native layers, pan/zoom, node/vertex dragging, width/count/speed editing and undo/redo.
- [ ] Test a shared-node move, width-only hash change, correct one-way/two-way width interpretation, zero-length edits, and undo restoring the original fingerprint. Browser-check that widths and lane footprints agree with Python output.

### Task 4 — Topology operations

- [ ] Implement add, split, connect, reverse and delete with stable IDs and explicit affected-reference review.
- [ ] Test directed routing, false visual intersections, split restriction remapping in both travel directions, incident-road deletion and rejection of five incoming approaches. Neighboring Site B junctions must retain no-signal mode.

### Task 5 — Reference images and islands

- [ ] Implement scale/anchor/rotation calibration, opacity and image lock; island polygon editing and planting metadata.
- [ ] Verify a known 50 m reference segment, transform save/reload and north/y-axis consistency. Test island self-intersections and intrusion by a car, bus and truck footprint. Label unmeasured dimensions provisional.

### Task 6 — Authoritative validation and review exports

- [ ] Add structured issues, revision-aware debounced previews, reachability checks and conservative physical-clearance checks. Export JSON, validation report and SVG overview from the same draft revision.
- [ ] Test stale validation responses, invalid drafts retaining editable geometry, rejected activation-ready export with errors, and unchanged playback of old embedded networks without islands.

### Task 7 — Main application activation and recovery

- [ ] Implement admin preview/apply, workload exclusion, immutable revision installation, audit records, cache refresh and affected-scenario listing.
- [ ] Test non-admin rejection, stale hash rejection, run-start/apply races, paused-run refusal, write failure, rollback, backup/restore and old recording replay. No test uses the owner's database.

### Task 8 — End-to-end acceptance and documentation

- [ ] Open Site B; adjust one road width; move a vertex; add a connected one-way frontage road; create an island; undo/redo; save; close/reopen; validate and export.
- [ ] Apply through an isolated SmartFlow instance, confirm the native simulation uses the edited geometry and confirm the neighboring junction shows no traffic lights in idle/live/replay views.
- [ ] Demonstrate an invalid island/road intersection being highlighted and blocked from activation. Do not accept the editor merely because a screenshot looks correct.
- [ ] Verify at least 100 roads and 1,000 editable vertices: local drag updates target a median frame interval under 33 ms on the documented development machine; server validation runs after the operation, not on every pointer move. Record hardware and actual timings.
- [ ] Run new editor Python tests, meaningful pure-JS operation tests with the existing Node test runner, affected backend suites, main frontend tests, TypeScript, lint and build. Full backend acceptance is required if native engine behavior changes. Use workspace-local TEMP/TMP and isolated data directories on Windows.
- [ ] Update the README, handoff and architecture with launch instructions, supported operations, revision installation, recovery and validation limits. Record evidence and outstanding failures honestly.

## 7. Definition of done and exclusions

Done means the owner can edit a real registered network through the browser, recover a saved draft, export a validated revision, and deliberately install it into an idle SmartFlow instance with history and stale-input protection. Width changes and added roads must affect the actual native network, not merely the drawing.

The editor is an authoring tool. It does not complete the pending Site B frontage reconstruction automatically, confer field validation, optimize signal plans, train RL, determine legal turns, or guarantee traffic safety from geometry checks alone. Long-duration scenario acceptance remains necessary for each adopted study-network revision. Native physics changes required by an adopted layout must receive their own engine-version and compatibility review.
