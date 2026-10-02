# 3. Field observations and SmartFlow integration plan

Prepared **2026-10-02, Asia/Singapore**. This document describes the agreed direction and a future implementation sequence; the proposed software changes below have **not** been implemented by preparing this document.

Read with [Field recording protocol](FIELD_RECORDING_PROTOCOL.md), [Video observation tool plan](VIDEO_OBSERVATION_TOOL_PLAN.md) and the existing [Research method](RESEARCH_METHOD.md). The recording protocol governs roadside phone collection; the observation tool plan governs extracting and reviewing evidence. This document governs its use in SmartFlow.

## 1. Purpose and boundaries

The intended chain is **phone recordings → reviewed observations → field-checked network and control model → calibrated simulator → held-out validation → RL training and controller comparisons**. Videos provide measurements of actual operation. They are not direct RL training episodes, and automated detections are preliminary observations until reviewed.

The current direction is a separate offline Python observation tool at `tools/field_observer/`, using its own environment and writing artifacts under `data/generated/field_observer/`. Keep computer-vision dependencies and raw-video processing separate from SmartFlow's authoritative native simulation and learning environment. This documentation task does not install dependencies, download models or create tool code.

The team will use **one camera**. Each fixed take measures one site/view during its own period. Prioritize validation against those actual measurement locations and periods. A network scenario assembled from sequential site observations is constructed from observations and explicit assumptions, not a simultaneously observed network dataset. No graphics or 3D-model changes are included in this documentation task.

The team expects field collection at selected Tagum intersections. Their exact identities, connected study boundary, physical controls, safe camera locations, recording dates and adviser-approved sample size still need to be recorded. The required RL coverage is tentatively per intersection; independent single-junction controllers versus coordinated control remains an adviser decision. No deadline, traffic-model fit tolerance or calibrated parameter is assumed here. The sibling protocol's proposed counting-tool QA and survey defaults are separate from traffic-model validation criteria.

### First decision: one pilot site and its required model behavior

Before developing a bundle-import interface or changing simulator contracts, complete one 10-minute stationary-phone pilot, a manually reconciled reference and the recording protocol's per-measurement coverage table. This first-site pilot is a delivery sequence, not an automatic reduction of the final capstone study area or required RL coverage.

Record the actual approaches/turns/crossings, signal movement groups and timing, lanes/storage, visible arrival/discharge locations, queue observations and missing coverage. Select the intended primary outcome and supporting measures. Compare each required behavior and measurement with the existing engine and identify the smallest necessary changes, the observations needed to verify them and any unsupported research claim. A required inflow or control gap needs further evidence, an explicitly justified estimate with bounded claims, or an agreed scope change; a missing-data label alone cannot validate the baseline.

Accurate counts are one input to a credible study. The fixed baseline must also reproduce the site's relevant service pattern and capacity before an RL comparison can support field claims. Freeze this site/model decision before choosing the implementation slice below. Finalize collection dates/repetitions, independent held-out periods and simulator-fit criteria with the adviser before full collection.

## 2. What the current software can and cannot represent

These findings come from the current source and regression tests, rather than the visual appearance of the application.

| Current behavior | Consequence for field evidence |
| --- | --- |
| CSV imports accept `trips`, `od_counts`, `turn_counts` and `pedestrian_counts`. Trip rows preserve explicit entry times and supported vehicle classes. | The existing importer can carry a carefully derived subset of reviewed observations. It does not interpret videos or rich event tables. |
| Aggregate vehicle count imports create `car` trips at evenly spaced times within each bin. | A count of 20 mixed vehicles does not become 20 measured vehicle arrivals. Local class mix and platooning are lost. Preserve the original counts and the conversion assumptions. |
| Vehicle demand requires connected boundary source/destination IDs. Turn rows must lie on the supplied boundary OD route; later adaptive routing can change that route. | A local turn observation is not a measured origin-to-destination trip across the connected study network. Do not invent a known OD pair or feed the same vehicle as new demand at every junction. |
| `pedestrian_counts` becomes evenly spaced pedestrian arrivals by junction. Individual `pedestrian_trips` contains only time and junction. | Crossing completions, crossing starts and arrival at the curb mean different things. The import loses crossing side/direction and actual individual waiting times. |
| A signal plan has one shared green duration, a sequence of individual cardinal approaches plus pedestrian service, common yellow/all-red and an offset. | It cannot faithfully express unequal phase greens, simultaneous opposing approaches, movement-specific arrow phases or crosswalk-specific permissions. There is no recorded signal-event CSV import. |
| A whole-junction reservation permits only one vehicle at a time; pedestrian occupancy blocks the whole junction. Roads produce one modeled lane per permitted direction. | Adding a simultaneous phase label alone will not reproduce observed capacity. Parallel streams, turn-lane storage and local pedestrian conflicts need representation or an explicit reduced scope. |
| Simulation throughput counts trips finishing at a modeled boundary; vehicle wait counts stopped time; queues use a speed threshold and lane-based aggregation. | Field stop-line counts, queue snapshots and curb waiting cannot be compared blindly with similarly named dashboard metrics. Match measurement locations, definitions and time windows first. |

Verified paths: [observation importer](../services/observed_data_import.py), [scenario validation](../simulation/scenario_config.py), [road network](../simulation/road_network.py), [signal, movement and metrics runtime](../simulation/traffic_engine.py). Existing [import tests](../tests/test_shared_session_and_import.py) confirm uniform count conversion and retained source bytes; [traffic contract tests](../tests/test_native_traffic_contract.py) confirm current clearance, reservation and pedestrian behavior. These tests establish software behavior, not field realism.

## 3. Preserve observations before converting them

### Motorcycles, trucks and Tagum passenger tricycles

The survey starts with seven ordinary categories: car, motorcycle, tricycle, jeepney, bus, truck and bicycle. The current engine supports `car`, `motorcycle`, `tricycle`, `bus`, `truck` and special `emergency`. Jeepney and bicycle are additional field categories whose simulation behavior needs implementation or an explicit justified mapping. An unknown subtype does not authorize dropping a vehicle or relabeling it as car.

The owner's pictured green/yellow three-wheel passenger vehicle belongs to `tricycle`, distinct from two-wheel `motorcycle`. Retain `vehicle_subtype=tagum_passenger_tricycle` in reviewed data and conversion records; use existing `vehicle_type=tricycle` in supported trip input. This is one road vehicle regardless of passenger count. Color/body style is a data subtype, not a separate demand class. No new vehicle graphics or 3D assets are requested by this plan.

Existing provisional dimensions and speed factors are car **4.5 m × 1.8 m / 1.0**, motorcycle **2.0 m × 0.8 m / 1.0**, tricycle **3.0 m × 1.4 m / 0.75**, bus **10.0 m × 2.5 m / 0.85**, truck **8.0 m × 2.5 m / 0.8**, emergency **5.0 m × 2.0 m / 1.0**. These are source defaults, not measured Tagum values. Verify representative dimensions, arrival share, discharge and stopping behavior from evidence before proposing changes to physics.

Preserve class proportions by period and movement, with original event timing where visible. Today's `trips` schema can already retain a reviewed tricycle's class. Aggregate-count imports still create cars: future bundle conversion must preserve tricycle/motorcycle/truck counts and label generated timing. Changing rendered color alone cannot repair lost demand classes. Do not count a tricycle's motorcycle component separately.

Keep the original videos, reviewed event tables, aggregate tables, signal observations, geometry notes and reference metrics as distinct evidence. An arrival is an input; a served count or measured wait is a reference outcome. Using only departures as arrivals can hide unmet demand behind a red signal or a long queue.

- Vehicle events should retain local track/event identity, observed class, incoming approach, outgoing approach if actually visible, boundary-entry time where measurable, stop-line passage time, and completeness/uncertainty flags. Preserve the field classes in the recording protocol, including jeepney, bicycle, confirmed emergency and unknown. An unsupported simulator class needs an explicit justified mapping or an unresolved input; never silently map it to car. A detector's track ID is local to its camera, not a reliable corridor-wide vehicle identity.
- Pedestrian events should distinguish curb arrival, crossing start and crossing finish, with crossing ID/direction and flags for already waiting at clip start or still waiting/crossing at its end. Exclude sidewalk passers and riders from pedestrian crossing demand. If curb arrival is hidden, keep it unknown; crossing start is not a substitute for arrival time.
- Signal observations should retain timestamped indications by movement/signal head and pedestrian indication, including arrows, uncertainty, visibility gaps and multiple measured cycles. Red duration must identify the relevant movement; it is not interchangeable with junction all-red clearance.
- Preserve local entry→exit movement observations even when connected-network OD is unknown. Obtain or estimate network OD separately, documenting the method, constraints and uncertainty. A short local recording cannot reveal a vehicle's unobserved journey across several junctions.
- Preserve initial queues/waiting pedestrians and users remaining at the end as censored observations. Do not drop them to improve average delay, and do not silently replace missing observations with zero.

FHWA distinguishes geometry, control and demand inputs from contemporaneous performance observations; it also cautions that congested counts can measure capacity rather than demand. It recommends timestamps for controls and reconciliation of simultaneous counts where feasible. These principles support the collection and conversion separation above; they do not certify this project's eventual sample size. [FHWA data collection guidance](https://ops.fhwa.dot.gov/publications/fhwahop18036/chapter2.htm).

### Reviewed observation bundle

The planned integration unit consumes the offline tool's neutral `schema_version: 1` package: `manifest.json`, reviewed events/bins, camera configuration, signal changes, queue samples, review log and quality report. Do not create competing event schemas. Retain this package unchanged and add a separate SmartFlow conversion record for network mapping, input derivation and scenario identity. Raw video remains separately retained evidence rather than an API upload requirement. Together, the package and conversion record must carry:

- Site/take identity, collection start/end with UTC offsets, timezone, single camera `PHONE_01`, take/view segment, video-to-clock offset and uncertainty, collection method, coverage/missing intervals, unusual conditions and reviewer/version identity.
- Original video hashes and retained locations, hashes of reviewed tables, tool/detector versions and settings, counting-zone version, and a correction/review record. Reconcile duplicate events across verified file splits of one take; keep sequential site/view periods separate.
- A mapping from observed approaches, movements and crossings to the frozen network, plus network fingerprint. Keep observation identities independent of a later mapping change.
- For each derived input, its source table, transformation version, interpretation, and whether timing/OD/class/initial state was measured, inferred or unobserved. Keep the observed source identity separate from the generated schedule fingerprint.
- A split-group identity covering the complete collection take and its derived tables/file splits; reviewed status and unresolved items. Related takes from the same site/day block stay together where independence would otherwise be overstated. An incomplete view cannot be presented as a completely measured junction.

For the first supported experiment, retain the complete reviewed evidence package and use a **deterministic conversion script plus a versioned mapping/provenance record** with the existing CSV importer where its semantics fit. Existing `trips` input can retain supported vehicle classes and explicit arrival times when the required boundary mapping is measured or explicitly derived. Keep estimated OD/timing labeled as estimated; stop-line discharge cannot be silently substituted for boundary arrivals. Crossing-specific pedestrian or unsupported signal observations still require the necessary model/import work, or an explicitly narrower study claim. Do not flatten them merely to produce an accepted CSV.

A structured bundle-import interface with coverage/mapping preview and integrated save is a later convenience when the simpler path becomes inadequate. The same validation is required for either path: reconcile counts/classes/times, preserve source and conversion identity, reject invalid/oversized inputs before applying them, and report table/row errors without leaving partial scenarios. Treat manifest paths as references, not permission for the API to read arbitrary local files.

Maintain compatibility with the four existing CSV schemas; do not reinterpret old count bins as exact observed events. Preserve explicit arrival/class information through supported trip conversion or a necessary adapter extension; legacy bins remain documented approximations. Preserve source bytes and mappings through edit, run, training, reporting and restore. Retain an observation-coverage summary and measured/inferred labels with each experiment; a companion evidence record is acceptable before an integrated report interface exists.

Plan for survey size explicitly. Current CSV limits are **1,000,000 UTF-8 bytes, 5,000 rows and 100,000 expanded arrivals per import**; the serialized scenario JSON field limit defaults to **2 MiB**, and expanded schedules count toward it. An hour-scale recording may exceed the practical stored-scenario limit well before the arrival limit. Keep full reviewed evidence in immutable artifacts and reject an over-limit derived scenario with its size and reason; never truncate it silently. Use deliberately defined compatible periods when justified, keeping session lineage and initial-state requirements intact. Add referenced/lazy schedule support only if measured full-survey size requires it, with equivalent run/training/restore identity checks; splitting one session does not create independent held-out data.

## 4. Site-dependent implementation order

These are future changes selected after the pilot/site decision, not a requirement to build a general-purpose observation platform before the first experiment. The pilot determines the necessary fidelity work; there is no automatic assumption that the supplied graph describes the selected intersections. Defer interface convenience, not changes essential to valid site behavior or measurements.

| Order | Addition | Acceptance before proceeding |
| --- | --- | --- |
| 1 | Complete the pilot/site decision; freeze the required study boundary, observed movements/crossings/control plan, measurement definitions and necessary model gaps. | Coverage is explicit for each required input/outcome; missing evidence and estimates have a decision; geometry/control and capacity requirements are known before integration development. |
| 2 | Add the smallest adequate reviewed-data conversion with immutable provenance, initially using supported CSV inputs and a mapping record; extend import only for required unsupported semantics. | Counts reconcile with reviewed events; supported observed times/classes survive round trips; unknown values remain unknown; conversion assumptions and retained source evidence are visible. |
| 3 | Implement the site-required geometry/lane/storage and signal/conflict/pedestrian changes, including per-phase timing and compatible movement groups wherever actual operation requires them. | The fixed baseline reproduces the observed service pattern and relevant capacity; incompatible movements remain protected. An inadequate baseline requires changes or an agreed narrower claim before field-effectiveness conclusions. |
| 4 | Add aligned observation-point outputs, initial-state handling where required, and calibration/validation reports. | Comparable flows, queues and delays use the same physical points, windows and definitions; initial/censored users and rejected/deferred demand remain visible. |
| 5 | Update RL observations/actions, training adapters, model compatibility, renderer/API types and replay/report metadata for the new control contract. | Old artifacts are rejected with a reason; new policies save/load/infer under the same safety behavior in headless and live runs. |
| 6 | Freeze the calibrated model and conduct independent validation before training/evaluating final policies. | Predeclared field-fit gates pass; final controller comparisons preserve matched exogenous inputs and report uncertainty and unfinished demand. |

Orders 3 and 5 form one coordinated control-contract release: build and verify the fixed baseline first, but do not expose new phase groups to an unchanged RL adapter. Do not make animation or additional algorithms the next priority while base-model fidelity remains unresolved.

An integrated bundle preview/save UI, polished video review, automatic signal recognition and custom detector training are later options. Required field coverage, trustworthy measurements, suitable baseline dynamics and independent validation remain acceptance requirements regardless of interface maturity.

### Control and capacity slice

Define stable phase IDs that serve explicit compatible vehicle movements and permitted crossings. Each phase needs its own measured green and relevant clearance settings; its order and start offset must be recorded. Preserve observed indication timelines as evidence. A fixed baseline may use a documented representative plan when operation varies, but must be labeled approximate; exact replay requires a separate explicit timeline mode, not an undocumented average.

Represent allowed simultaneous service and conflict relationships from verified site operation. Do not infer safe simultaneous turns merely from compass directions. Vehicle entry permissions, reservations and downstream storage checks must operate on movements/conflicts rather than allowing only one vehicle in the whole junction. The conservative existing behavior can remain an explicit legacy mode, but must not masquerade as calibrated parallel capacity. Assess whether turn lanes, multiple approach lanes or motorcycle filtering materially affect the selected site's fit; implement the necessary representation or narrow the study claim openly.

Associate pedestrians with actual crossings and their conflict sets. Capture when a new crossing may begin, when an existing crossing must clear and which vehicle movements can run concurrently. A green signal for one approach does not imply every adjacent pedestrian crossing is safe. Preserve minimum service, clearance, occupied-crossing protection, bounded-wait rules, emergency handling and blocked-exit checks. Test these rules under both fixed and learned requests.

Signal phase/movement structure belongs in the versioned scenario/network contracts and rendering frames. Treat changes to engine dynamics, observation encoding, action meaning or site movement mapping as model compatibility changes. Bump the relevant contract versions; keep old scenarios/artifacts inspectable, require explicit legacy handling/migration and retrain affected QL/DQL/PPO models rather than relabeling their old actions. Include the controlled junction, phase/action mapping and geometry/control fingerprints in new artifacts.

Current contract owners include [model compatibility](../simulation/model_contract.py), [RL snapshot/action mask](../simulation/rl_state.py), [RL environment](../simulation/rl_env.py) and [policy inference](../simulation/rl_policy_runtime.py). The current contract is `native-local-30-v1` with `protected-service-5-v1`; its equality check already prevents silently loading a different engine/network contract. A field phase-group extension must update every producer/consumer and regression fixture, not only the simulator's signal class.

## 5. Calibration and independent validation

Agree the analysis variables, field measurement definitions, traffic-model acceptance tolerances and sampling plan with the adviser before final alternative comparisons. No universal simulation-fit percentage or adviser-mandated recording duration is selected here; use the sibling protocol's proposed pilot/full-survey schedule as the collection starting point. Model tolerances should account for observation uncertainty and the decision the model will support.

1. Reconcile reviewed observations, site geometry, visible movements, controls and clocks for each single-camera period. Mark missing approaches, unseen arrivals, unreadable signals and clipped queues explicitly. Any cross-site demand allocation from sequential periods is a documented estimate, not measured concurrency. A visibility gap is a data-quality issue, not a parameter-fitting opportunity.
2. Assign whole takes and related site/day-period blocks to calibration, model development and final held-out validation. All file splits and derivative tables from a take stay in the same split. Random frames, adjacent slices of one short clip, reformatted CSVs and different scenario names do not create independent evidence.
3. Calibrate the fixed baseline on designated data: check control/geometry and demand interpretation first, then adjust justified vehicle, following, discharge or pedestrian parameters. Record each parameter change, rationale, input subset and fit result. If the structural model cannot reproduce measured capacity, correct it or reduce the claim; do not lower demand just to remove queues.
4. Freeze the model and validate on independent observations without further fitting. Report residuals by site, movement, class and period where supported. If validation fails, record the failure, revise using development data and collect/reserve a new untouched validation set before final claims.
5. Keep detector/manual-count validation separate from simulator calibration. A simulator matching a wrong automated count is not field validation. Retain independently recounted samples, discrepancies and review coverage. Require the recording/tool plans' Gate A before accepting `sample_audited_auto` inputs; Gate B checks final corrected/manual data separately. Repaired audit samples cannot certify the unsampled footage. Failed automatic gates require fresh acceptance evidence or a complete manual pass for the affected measurement period.

FHWA describes calibration against observed variation and predefined acceptability criteria, including bottleneck behavior and system performance. This supports checking more than whether traffic moves or an aggregate count matches. [FHWA model calibration guidance](https://ops.fhwa.dot.gov/publications/fhwahop18036/chapter5.htm).

### Reference metrics and comparable outputs

| Field reference | Comparison and required qualification |
| --- | --- |
| Vehicle entry count by boundary/approach, class and time bin | Compare scheduled/requested/admitted entries separately. Stop-line passage count is served flow, not boundary demand. Report missing coverage and unmet/deferred demand. |
| Served movement count at a specified stop line or exit | Add/use simulated counts at that same observation point. Whole-network completed-trip throughput is not the same measure. Reconcile local movements and connected-network flow without double counting. |
| Queue snapshots by lane/approach at declared times | The protocol proposes snapshots every 30 seconds and at green onset/end when possible. Compare simulated samples at those same times with the agreed stopped/queued criteria and aggregation. Record queues extending beyond view as censored/lower bounds. Current `avg_queue` is a time average per incoming lane, not the snapshot or network queue sum. |
| Vehicle stopped wait or bounded-segment travel time | Compare the same event/endpoints and sample population. Travel time is not stopped delay. Report users present at clip start/end and completion bias; current completed-trip travel time excludes unfinished trips. |
| Pedestrian curb wait, crossing duration and completion | Compare curb arrival→crossing start separately from crossing duration. Report waiting/crossing users at cutoff. Current `avg_ped_delay` combines completed and active pedestrians and cannot substitute for every field statistic. |
| Signal indication transitions and phase service | Compare phase IDs, per-phase durations, clearance and observed cycle variability. Explain representative-plan approximations and any safety overrides. |

Choose a primary controller outcome before final experiments, with throughput, pedestrian service and unfinished/rejected demand as guardrails. Report all relevant periods, failures and negative results; a better completed-only mean accompanied by more stranded users is not unqualified improvement.

## 6. RL experiments and reproducibility

RL interacts with the validated simulator: observations describe simulated queues/control state, actions request permitted phase service, and rewards derive from simulated outcomes. Field evidence informs arrivals, vehicle mix, geometry, controls and calibrated behavior; raw videos and detection boxes do not directly train the present QL/DQL/PPO policies.

Keep simulator calibration/base-model validation separate from policy development and final policy evaluation. Reserve independent field-informed periods for final assessment, and separate training/evaluation seeds for any generated demand realizations. Replaying the same deterministic measured schedule under new seeds does not produce independent field observations. SB3 recommends separate evaluation environments and evaluation across several runs/seeds. [SB3 evaluation guidance](https://stable-baselines3.readthedocs.io/en/master/guide/rl_tips.html).

For each paired fixed-time/RL comparison, freeze network, calibrated behavior, initial state, vehicle and pedestrian arrival schedules, class/OD allocation, routing mode, incidents, safety rules, warmup, measurement window and seed. Vary the controller only. Check actual exogenous schedule hashes, not merely matching seed labels. Keep controller-dependent queues, departures and delays as outputs; do not force them to match the field outcome. For routing comparisons, hold signal control fixed and vary routing separately.

The current [evaluation runner](../tools/evaluate_controllers.py) creates controller runs with saved scenario/settings/seeds. Extend its matching and reporting to the reviewed bundle, full pedestrian/initial-state inputs and new control contract. Pair outcomes by scenario/realization, preserve every repetition and use uncertainty summaries justified by the eventual analysis plan.

Retain raw-source identity, reviewed-table identity, mapping/network identity, conversion version, realized vehicle/pedestrian schedule fingerprints, calibration version, engine/RL contract, scenario snapshot, model/checkpoint identity, training split/seed lineage, controller and measurement window. These records must remain visible after scenario edits and through CSV/JSON exports and replay.

Existing [held-out guards](../services/observation_identity.py) reject duplicate raw/normalized observations, equivalent realized arrivals and overlapping declared collection periods; [resume identity checks](../services/scenario_identity.py) preserve original inputs while allowing checksum-verified relocation. Extend them to session lineage and all bundle tables; do not weaken these protections to make a comparison run. They verify supplied identity, not honest field collection or statistical independence.

The existing [backup bundle](../services/backup_bundle.py) preserves referenced source/model/network/recording artifacts and verifies staged restore. Extend it to reviewed bundles, mapping and calibration evidence. It does not automatically archive the team's raw phone videos. Preserve them separately with hashes and a verified evidence-copy location, and disclose what the software ZIP excludes. Any later raw-video inclusion needs an explicit storage/retention decision because of size. A relocated research package is complete only when required software artifacts and original evidence are recoverable.

## 7. Acceptance gates and meaningful checks

| Gate | Evidence required |
| --- | --- |
| Pilot/site decision recorded | One stationary-phone pilot and manual reference; coverage by required measurement; actual site behavior compared with the engine; necessary changes, unresolved evidence and intended outcomes recorded before integration development. |
| Collection usable | Agreed dated/repeated survey and held-out periods; legible one-camera recordings with known clocks and measurement definitions; Gate A for sampled automatic acceptance and separate Gate B for final reviewed quality; uncertainty/censoring preserved. Uncovered required movements need separately dated evidence, companion manual measurement or reduced claims. |
| Import trustworthy | Retained reviewed evidence package, deterministic conversion/mapping and byte hashes, using supported CSV input or a necessary adapter extension; events reconcile with counts; no accidental synthetic/observed relabeling; atomic rejection of invalid/oversized content. |
| Model structurally appropriate | Observed phase groups, lanes/storage, conflicts and pedestrian service represented; capacity and clearance checks pass; unsupported features explicitly resolved. |
| Field baseline validated | Predeclared fit tolerances pass on independent observations for selected local and network measures; failures and uncertainty retained. Software tests alone cannot satisfy this gate. |
| RL comparison fair | Compatible newly trained artifacts; matched exogenous inputs; untouched final assessment periods; paired outputs, safety events, uncertainty and unfinished demand reported. |
| Evidence portable | Scenario/bundle/model/result exports agree; staged restore and relocated replay/model loading work; required original evidence is recoverable by its verified hash. |

Implementation tests should cover exact class/time preservation; zero versus missing observations; duplicate events across file splits of one take; sequential takes retaining separate periods; partial tracks and end-of-clip censoring; wrong/changed mappings; overlapping session lineage; corrupt/missing source tables; and failed import leaving no partial scenario/artifacts. Add fixed-signal fixtures for unequal greens, compatible opposing movements, conflicting turns, yellow/all-red transitions, occupied crosswalks, blocked exits and finite service under sustained demand.

Use the same synthetic fixtures across headless, live and recording paths; assert conservation and reproducibility. Assert contract invalidation and refused old-model resume/load, then run real QL/DQL/PPO save/load/inference with the new phase mapping. Verify observation-point metric definitions against small hand-calculated trajectories. Exercise bundle save/edit/reopen, reports, isolated backup/restore and relocation. Existing tests are starting evidence, not substitutes for these new cases.

When implementation is authorized, follow [handoff verification](../IMPLEMENTATION_HANDOFF.md#8-verification-and-safe-execution-instructions): targeted tests first, full Python acceptance, API checks, lint/build and then browser import/run/replay/report checks using isolated artifacts. Archive actual results and source revision. This document introduces a plan only; the next decision gate is a pilot and an explicit site/model-gap review, not a claim that field collection or the proposed software work is complete.
