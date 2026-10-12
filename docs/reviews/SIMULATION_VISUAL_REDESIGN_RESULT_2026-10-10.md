# Simulation visual redesign — implementation and verification

Date: **2026-10-10**, Asia/Singapore. Scope: the independent SmartFlow repository.

Implemented the [agreed plan](../SIMULATION_VISUAL_REDESIGN_PLAN.md) through slices A–F. Software verification includes geometry regressions, native engine equivalence, backend tests, final frontend checks, actual native browser workflows, controlled presentation/failure fixtures and two production rendering measurements. This result does **not** establish field calibration, real Tagum geography, realistic 300-vehicle road capacity or learned-policy effectiveness.

Evidence directory: **`tmp/visual-redesign-20261010/`**, relative to the SmartFlow root. Keep this ignored directory; screenshots, logs, fixtures and isolated database artifacts are not automatically preserved by a source-only Git checkout. The worktree remains dirty; no commit, unrelated reset or research-data deletion was performed.

## Delivered behavior, by slice

| Slice | Implemented behavior | Verification |
| --- | --- | --- |
| A — shared foundation | One network loader and normalized geometry for both renderers/minimap/picking. Exact supplied lane endpoints, centered engine footprints, native heading conversion and unlit all-way-stop lamps. | Original extrapolation, footprint and off-lamp checks failed 3/3; corrected helpers passed 3/3. Geometry/coordinate regressions and seeded engine comparison passed. |
| B — architectural 3D | Junction opening with 20% padded approach bounds; pavement, curbs, markings, three-position signals, engine-derived pedestrian paths and sparse illustrative context. Distinct car, motorcycle, covered green three-wheel tricycle, bus, truck and ambulance appearance for the native emergency class. | Imported GLBs inspected and normalized; fleet/assets/camera regressions passed. Actual native mixed-fleet run and all-six-class scene close-up captured. |
| C — analytical 2D/navigation | Cached static map; dynamic actors/signals/restrictions, pan/zoom/reset, shared selection, junction/network/follow controls, minimap, fullscreen and inspector. Lane queues and optional heatmap/arrows/connectors use complete metrics. | Final browser exercised all four selection kinds, mode switching, minimap/picker, fullscreen, 2D navigation and a 430-pixel-wide collapsible inspector with no horizontal overflow. |
| D — truthful telemetry/replay | Complete lane/junction metrics, waits, controller/stage/timing/pending request and timestamped latest policy/safety events. Fixed-stage, minimum-hold and clearance labels have different meanings. All-way-stop is explicitly unsignalized. Older missing telemetry is unavailable. | Python/HTTP frame parity, optional-field clearing and timing tests; native recording/replay/backward seek; old-recording fixture; actual compatible QL inference plus separately labeled manual hold/clearance/pedestrian-service fixtures. |
| E — performance/failures | Class/material instancing, shared resources, Laptop default, optional Enhanced shadows, timing-based bounded interpolation, resource cleanup and visible asset/WebGL/stream fallback. | Ten mode switches retained one loop with stable resource counts. Six injected failure checks passed. Two 60-second Laptop measurements passed the numerical target below. |
| F — evidence/handoff | Final source checks, screenshots, reproducible browser scripts, preservation evidence and current architecture/status/index updates. | This result, linked logs/JSON and source/build hashes establish the scope of the claims. Remaining limits are listed below. |

Buildings, greenery and crossing-path styling remain illustrative. Native Python positions, speeds, vehicle sizes, signal decisions, demand, routing, closures and RL actions remain authoritative. The redesign introduces no replacement engine, SUMO/TraCI connection or new driving lanes.

## Contracts and compatibility

- Stable distributed rendering limits are **300 vehicles / 128 pedestrians**, in live and replay. Above-limit selection is spread across native lanes/junction groups, rather than taking the first population prefix. Total/displayed counts and the reason for limiting are shown.
- Complete research metrics are serialized independently of the displayed population. The above-limit fixture retains metrics for **500 vehicles / 160 pedestrians** while showing 300/128.
- The actual compact UTF-8 WebSocket encoding has a **262,144-byte** ceiling. Entity trimming preserves required metadata and sampling distribution. Oversized metadata emits an explicit error; stale scene entities/details are cleared. HTTP state and action responses carry the same server-authored compact frame and error contract.
- New recordings retain additive telemetry. Older recordings omit unsupported waits, metrics, controller events or paths; the UI does not fabricate zeros or inherit prior frames. Their frozen experiment configuration supplies controlled-junction focus when available.
- Selection survives compatible 2D/3D switches and static-object replay seeks. New run/network/reset boundaries clear incompatible state. Pause and seeks snap to authoritative positions; ordinary frame gaps finish interpolation and freeze without extrapolation.
- The native scenario, `native-3`, observation/action/model and permission boundaries remain intact. RL still controls one selected junction. Generic training progress/exploration bars were replaced by a truthful runtime explanation and actual controller/runtime values.

The seeded comparison in [engine-invariance.json](../../tmp/visual-redesign-20261010/engine-invariance.json) matched **186 snapshots across six cases**, seed 17, for actors, signals, completions, metrics and RL state. Only additive presentation fields were excluded. This is synthetic regression evidence.

## Automated verification

Commands ran from the SmartFlow root using its `.venv/Scripts/python.exe` and package scripts.

| Check | Actual result | Evidence |
| --- | --- | --- |
| `python -m unittest discover -s tests -v` | **133 passed**, 277.772 s | [full backend log](../../tmp/visual-redesign-20261010/full-backend-tests.log) |
| Final backend display-label addition: presentation/native regression/shared-session/traffic-contract/cleanup modules | **47 passed**, 16.711 s; includes geometry unchanged after removing additive display labels | [focused final backend log](../../tmp/visual-redesign-20261010/backend-label-tests.log) |
| `npm.cmd run check:api` | Passed | [API compilation](../../tmp/visual-redesign-20261010/check-api-final.log) |
| `npm.cmd run test:visualization` | **84 passed**, six files, 760 ms | [final frontend tests](../../tmp/visual-redesign-20261010/frontend-tests-final.log) |
| `npm.cmd run build` | TypeScript and production build passed | [final build](../../tmp/visual-redesign-20261010/build-final.log) |
| `npm.cmd run lint` | Passed, zero lint issues | [final lint](../../tmp/visual-redesign-20261010/lint-final.log) |
| `git diff --check` | No whitespace errors; existing Windows line-ending notices | [diff check](../../tmp/visual-redesign-20261010/git-diff-check.log) |

The full backend suite preceded the final pure display-label helper; its final focused suite and compilation cover that addition. These counts are overlapping checks, not additive totals. Browser and performance measurements used the final production source. The existing large JavaScript chunk warning remains: approximately **1.765 MB minified / 501 KB gzip**. No broad dependency audit fix was applied.

The measured production build, configured for isolated API port 18029, is preserved in **`tmp/visual-redesign-20261010/production-build/`**. After verification, root `dist/` was rebuilt using the normal repository API defaults; it does not retain the temporary verification-port override. Owned verification servers were stopped. Current source hashes and build/evidence checks are in [verification-summary.json](../../tmp/visual-redesign-20261010/verification-summary.json).

## Browser evidence

Used the real production app on **127.0.0.1:15190**, single-worker native API on **18029**, and an isolated **`tmp/visual-redesign-20261010/browser.db`** with its own artifact directory. Existing owner servers, primary database and original model/recording paths were not used for test mutations.

Actual native workflows:

- Seed 17 mixed-fleet fixed-time run advanced to **24.3 simulated seconds**, paused with directed closure `road0f` and slowdown `road4f`, then resumed past 41 seconds and verified both restrictions cleared. Pause held simulation time constant. Matching 2D/3D views were captured from the paused snapshot.
- A native **20-second, 201-frame** recording completed; backward seek preserved a selected lane. Playback play/pause/stop succeeded.
- A short **two-episode QL** job completed in the isolated database and produced a compatible model. An actual `ql:1` run recorded policy requests and safety events; final-source inference screenshots were captured. This proves software integration, not model quality.

[native-final.json](../../tmp/visual-redesign-20261010/native-final.json) and [native-workflows.json](../../tmp/visual-redesign-20261010/native-workflows.json) retain those snapshots and job/artifact references.

Controlled browser fixtures passed **12 checks**, with **zero page exceptions**: [browser-acceptance.json](../../tmp/visual-redesign-20261010/browser-acceptance.json). They cover above-limit congestion, clearing restrictions, all-way-stop, manual minimum-hold/clearance requests, native pedestrian service after a synthetic manual request, old optional telemetry, ten mode switches and narrow layout. These fixtures deliberately contain manually arranged positions and sometimes overlapping populations; they are rendering evidence, not generated traffic or learned-policy evidence.

Six failure checks passed with zero page exceptions: asset download aborts, unavailable WebGL, context loss, reconnect after stream interruption, authoritative HTTP fallback and metadata-budget rejection clearing stale actors: [browser-failures.json](../../tmp/visual-redesign-20261010/browser-failures.json). The browser fullscreen API's expanded-layout fallback is recorded separately in [fullscreen-fallback.json](../../tmp/visual-redesign-20261010/fullscreen-fallback.json).

Ten switches retained one active frame loop; the final stress samples held **70 geometries, four textures and 70 draw calls** with diagnostic overlays enabled. The whole sequence fetched **five local GLBs once** and the visual network once. No runtime external asset requests were required.

| Screenshot | Purpose |
| --- | --- |
| [Before 3D](../../tmp/visual-redesign-20261010/baseline-3d.png), [before 2D](../../tmp/visual-redesign-20261010/baseline-2d.png) | Captured original renderers |
| [Final native 3D](../../tmp/visual-redesign-20261010/native-final-3d.png), [final native 2D](../../tmp/visual-redesign-20261010/native-final-2d.png) | Matching authoritative paused native snapshot |
| [Six-class close-up](../../tmp/visual-redesign-20261010/mixed-fleet-closeup-3d.png), [tricycle follow](../../tmp/visual-redesign-20261010/tricycle-follow-closeup-3d.png) | Actual scene renderer, manually arranged synthetic appearance fixture |
| [Congestion/closure 3D](../../tmp/visual-redesign-20261010/congestion-closure-3d.png), [2D](../../tmp/visual-redesign-20261010/congestion-closure-2d.png) | Full metrics with limited display and directed restrictions |
| [Controller request](../../tmp/visual-redesign-20261010/controller-request-3d.png), [actual QL](../../tmp/visual-redesign-20261010/native-final-policy.png) | Separate manual rare-state and actual model evidence |
| [Pedestrian service 3D](../../tmp/visual-redesign-20261010/pedestrian-service-3d.png), [2D](../../tmp/visual-redesign-20261010/pedestrian-service-2d.png) | Native service state after explicitly synthetic manual request |
| [New replay](../../tmp/visual-redesign-20261010/native-final-replay.png), [old telemetry](../../tmp/visual-redesign-20261010/old-recording-unavailable.png) | Replay and missing-field compatibility |
| [Narrow layout](../../tmp/visual-redesign-20261010/narrow-viewport.png) | Inspector below viewport, collapsible, no horizontal overflow |

## Measured performance

Hardware: **Acer Aspire A514-54G laptop**, Windows 11 Home Single Language 64-bit, build 26300; **Intel i7-1165G7**, four cores/eight logical processors; **12.65 GB physical memory reported** (about 11.78 GiB). Installed graphics are Intel Iris Xe and NVIDIA MX350. Chrome actually used **Intel Iris Xe through ANGLE Direct3D11**, not the NVIDIA adapter or a software renderer.

Production **Chrome 154.0.8037.98, headless**, browser viewport **1366×768**, DPR **1**, Laptop preset. The ordinary dashboard canvas measured **532×420**; this is not a fullscreen benchmark. Signals, labels, queues and sparse context were enabled; heatmap/arrows/connectors were off. No unrelated training job was active. Assets warmed for ten seconds before each 60-second window.

Synthetic stress fixture: **300 stationary authoritative-position vehicles, 50 of each native class, plus 128 pedestrians**, generated with seed 42, 100 ms fixture delivery. Its browser envelope displayed a seed-17 metadata label; no browser-side demand generation occurred. The recorded frame/state hashes identify the actual seed-42 fixture. This isolates rendering load; it does not establish realistic demand, collision behavior or native engine capacity at that population.

| Focus | Renderer window | Average FPS | p95 interval | Maximum interval | Draw calls | Geometries/textures | >100 ms stalls |
| --- | --- | --- | --- | --- | --- | --- | --- |
| Junction | 60.003 s | **60.01** | **20.20 ms** | 26.90 ms | 51 | 51 / 4 | 0 |
| Network | 60.001 s | **60.02** | **20.10 ms** | 24.50 ms | 62 | 62 / 4 | 0 |

Both windows meet **≥30 average FPS / ≤50 ms p95**, retaining all 300/128 displayed entities and one frame loop with stable resources. Enhanced's short semantic check retained the same population; it is not a 60-second Enhanced acceptance result.

[performance-benchmark.json](../../tmp/visual-redesign-20261010/performance-benchmark.json) includes raw intervals, samples, browser/GPU details and dirty source/build/fixture hashes; [hardware.json](../../tmp/visual-redesign-20261010/hardware.json) includes hardware inventory. Reproduce with `node tmp/visual-redesign-20261010/performance-benchmark.cjs` while the isolated API and preserved production build are served on ports 18029/15190. The scripts use the installed Chrome and bundled Playwright; refresh the isolated test login with `prepare-browser.cjs` when needed. Keep this benchmark build separate from the normal root `dist/`.

Backend measured separately with `python -m tools.measure_native_capacity --duration-seconds 60 --seed 42 --densities medium,high --output tmp/visual-redesign-20261010/native-capacity.json`: peak **12/32 vehicles and six pedestrians**, step p95 **0.321/0.472 ms**, compact serialization p95 **0.934/0.957 ms**, zero vehicle/pedestrian conservation error. [native-capacity.json](../../tmp/visual-redesign-20261010/native-capacity.json) is generated-demand software timing evidence; it is not a 300-vehicle engine test. Baseline renderer sampling used a different smaller native snapshot and a short window, so no controlled percentage speedup is claimed.

## Preservation and remaining limits

[research-preservation.json](../../tmp/visual-redesign-20261010/research-preservation.json) matched **all 261 protected files** against the original cleanup checkpoint, including 24 model files, 56 recording files and original PDFs. An additional 21 authored Field Observer files/launchers, the history archive, both recovery ZIPs, pre-migration database snapshot and 20 historical evidence artifacts matched. All 237 removed legacy paths remain absent. Original cleanup manifests were not rewritten. Ignored environment/cache/weight files and main SQLite contents are outside that hash inventory; no broader preservation claim is inferred from it.

The implementation and documented numerical laptop rendering gate are verified under the conditions above. The following remain outside or incomplete as broader acceptance:

- **Field/research validation remains open:** final study intersections, measured geography, calibration and controller effectiveness are not established. Scenery and pedestrian paths remain illustrative.
- **Human usability acceptance remains open:** screenshots and deterministic controls establish functionality; no independent researcher timed recognition of the longest queue, controller or six classes. Tiny classes require closer zoom/follow on narrow displays. Dense enabled 2D labels can overlap; turn off optional labels/connectors or zoom and inspect exact measurements.
- **Hardware/browser coverage is bounded:** headless Chrome on this specific laptop passed. Headed sustained/battery/thermal tests, other browsers, high-DPR displays, fullscreen stress and weaker laptops were not benchmarked. Ten switches establish the recorded resource trend, not an unlimited-duration memory proof.
- **Enhanced performance is not certified**, and the existing production bundle-size warning remains. The underlying process-local single-worker runtime architecture is unchanged.
- Early verification harness errors included incorrect native speed (10 instead of the supported maximum 4), an incorrect preview API environment variable, expired isolated login, SVG group click bounds and an overly narrow asset-interception glob. These were corrected; final results above come from successful reruns. Browser testing also found and repaired a canvas/minimap stacking defect and camera fitting that was too distant.

No requested implementation slice was left as a scaffold. Do not use this result as field validation or as a claim that every laptop/browser meets the measured target.
