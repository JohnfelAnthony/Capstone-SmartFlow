# Research preparation protocol

Drafted 2026-09-27 for the native SmartFlow engine. This is a **collection and analysis plan**, not field observations, calibration or a final results chapter. The owner chose to leave final study intersections and one-versus-multiple-junction RL coverage open for now. The revised Chapters 1–2 in `research_sources/` remain unchanged; this draft records the later native-engine direction for an eventual manuscript revision.

**October 2 planning update:** The owner now reports selecting Tagum intersections and intends to collect roadside recordings using one mobile-phone camera. Each stationary take measures its own site/view and period; sequential takes do not establish simultaneous network observations. Exact site IDs, coverage, dated observations and the adviser-approved sampling schedule have not been supplied. The selected approach is offline computer-assisted extraction with manual verification. Read the [field recording procedure](FIELD_RECORDING_PROTOCOL.md), [video observation tool plan](VIDEO_OBSERVATION_TOOL_PLAN.md) and [SmartFlow integration plan](FIELD_DATA_SMARTFLOW_INTEGRATION.md) for the agreed direction and implementation sequence. These documents do not establish collected data, installed tools, calibration, vehicle graphics or verified field effectiveness.

## Decisions to record before field work and final evaluation

| Decision | Current working state | Approval needed |
| --- | --- | --- |
| Exact connected road boundary and study junction IDs | Owner reports selected Tagum sites; their IDs and boundary mapping are not recorded here. Supplied five-junction `tagum_network` remains a software test network. | Record the selected sites and confirm legal movements and physical signal/stop controls in the field. |
| RL control coverage | Current QL/DQL/PPO environment controls one selected junction; other junctions use saved plans. | Adviser/panel and project lead decide whether one, independent multiple, or coordinated control is required. |
| Mandatory controller comparisons | Fixed-time baseline and QL/DQL/PPO software paths exist. | Confirm required algorithms and whether unsignalized alternatives are in scope. |
| Observation periods and repetition count | Ordinary, peak and disruption/recovery are proposed conditions. | Agree days/times, survey permissions, replication and the final analysis plan before seeing outcome data. |
| Acceptance tolerances for calibration | No field-derived target or tolerance exists. | Set variable-specific thresholds with the adviser after inspecting data quality, before final alternative comparisons. |

## Collect and preserve evidence

Create a read-only original for every source file or paper sheet. Record collector, collection date, local time and timezone, location/approach IDs, units, weather, unusual events, method, missing intervals and any corrections in a separate provenance log. Hash the digitized original; version each cleaned table and conversion script. Keep synthetic samples clearly labeled. FHWA identifies geometry, controls and demand as base-model inputs and calls for contemporaneous counts and performance observations during calibration ([FHWA data collection](https://ops.fhwa.dot.gov/publications/fhwahop18036/chapter2.htm), [calibration data](https://ops.fhwa.dot.gov/trafficanalysistools/tat_vol3/sect2.htm)).

Use these paper/digital form sections at each selected site; a blank row is missing data, not zero:

| Form section | Fields to capture | Check before entry |
| --- | --- | --- |
| Site and geometry | Site ID, GPS/map reference, approach and outbound IDs, permitted turns, lane count/width, lane use, crossing locations, photos and date. | Compare each mapped lane/turn with the frozen network; log discrepancies. |
| Control plan | Controller type, phase order, green/yellow/all-red duration, offsets, pedestrian service and observed change times. | Confirm actual operation for each surveyed period; do not infer timing from OSM. |
| Demand counts | Bin start/end, inbound approach, vehicle class, turn destination or boundary OD when observable, counts, pedestrian crossings/direction, collector. | Use a predeclared interval (15 minutes is a draft), complete all approaches, distinguish observed turn counts from estimated OD. |
| Performance | Same-bin queue observations by approach, travel-time route/start/end, stopped delay/speed method, number of samples, censoring and anomalies. | Collect alongside counts under comparable conditions; label measurement uncertainty. |
| Event/disruption | Road/lane ID, restriction type, start/end, observed or hypothetical source, detour changes, incident notes. | Do not present a proposed holiday/closure scenario as an observed event. |

The importer accepts trips, OD count bins, turning count bins and pedestrian count bins with source/date/hash metadata. It validates format and connectivity; it does **not** verify field truth or calibrate the network. Preserve the original table and document any transformation from counts to evenly spaced synthetic arrivals. For OD estimates, log the estimation method and check input/output flow balance. FHWA notes that route-choice analysis can need OD estimates and that turning counts alone do not uniquely determine them ([FHWA data collection](https://ops.fhwa.dot.gov/publications/fhwahop18036/chapter2.htm)).

The October 1 held-out guard rejects duplicated raw/normalized CSV content, equivalent realized observations, and overlapping declared collection periods on the same network for vehicles or pedestrians. It inspects observed datasets even when a scenario also contains synthetic demand. Without explicit start/end timestamps, the entire collection date is reserved. For separate periods on the same date, supply both ISO 8601 timestamps with UTC offsets, such as `2026-01-01T07:00:00+08:00` and `2026-01-01T08:00:00+08:00`; the start must match the collection date. CSV time zero corresponds to that collection start and simulation start, including warmup, and CSV times must fit inside the period. Declare the real periods; changing a date or scenario name does not turn copied observations into independent evidence. Missing legacy provenance may require re-import. Passing this guard is a software check of supplied inputs, not proof of field truth or study validity.

## CSV template and import guide

The Scenarios create/edit sheet downloads header-only templates and separate, explicitly synthetic one-row examples for all four supported schemas. Examples use connected boundary, junction and lane IDs from the **loaded network**, including a replacement network. Download a new example when changing networks. A blank template requires data rows before validation; missing observations must not be entered as zero.

| Schema | Required columns, in template order | Meaning |
| --- | --- | --- |
| Trips | `time_s,source,destination,vehicle_type` | One vehicle arrival per row; boundary origin/destination IDs and a supported vehicle class. |
| OD counts | `start_s,end_s,source,destination,count` | Boundary origin/destination count over a time bin. |
| Turn counts | `start_s,end_s,source,destination,junction,from_lane,to_lane,count` | Count for a permitted incoming/outgoing lane movement on a connected boundary OD route. |
| Pedestrian counts | `start_s,end_s,junction,count` | Crossing demand at a modeled junction over a time bin. |

Times are nonnegative seconds relative to collection/simulation start, including warmup; they are not clock times. Bin end must exceed start. Counts are nonnegative integers; zero means the interval was observed and had no arrivals. Vehicle classes are `car`, `motorcycle`, `tricycle`, `bus`, `truck` and `emergency`. Count-based vehicle imports currently generate cars with evenly spaced arrival times; they do not preserve an unrecorded vehicle mix. Use trips when individual class and arrival information is available. Turning counts need the stated OD allocation, so an approach-only survey must first be transformed using a documented allocation method.

Keep IDs as text when editing in a spreadsheet, preserve the exact column names and export UTF-8 CSV. Boundary, junction and lane IDs shown in the form belong to the current network. Provide a meaningful source description, collection date and source kind. For observed periods on the same day, provide both offset-aware collection start/end timestamps; all CSV times must fit within that interval. Preserve original observations separately from cleaned/imported versions. The importer reports row errors and validates before applying the result to the draft; save the scenario only after reviewing its demand and provenance. Downloading a synthetic example selects the synthetic source label; a later manual label change does not make the example field evidence.

CSV run reports expose seed, network and demand fingerprints, controller/model identity, measurement start/duration, unfinished demand, dataset provenance JSON and the full experiment JSON. Each imported dataset retains its observed or synthetic source kind. JSON reports retain the frozen experiment object. Interpret a report's saved experiment provenance rather than the scenario's subsequently edited settings; the source record remains authoritative for collection details.

## Freeze, calibrate, then evaluate

1. Freeze the selected graph version, allowed turns, controller plans, source records, units, time bins and metric definitions. Verify network connectivity and input count reconciliation; correct coding errors before fitting parameters.
2. Split dated observations by period/day into calibration and held-out validation sets **before** tuning. Keep any later RL evaluation set separate from model selection. Calibrate arrival/turn/OD inputs, demand timing, vehicle mix and the simplified junction capacity against observed flows, queues and travel times. Record each parameter change and fit metric. The current engine reserves a whole junction for one vehicle at a time; if it cannot reproduce observed capacity within agreed tolerance, revise the model or narrow the claim rather than adjusting only demand to hide the mismatch. FHWA treats a working but uncalibrated model as insufficient for predictive alternatives analysis ([FHWA calibration](https://ops.fhwa.dot.gov/publications/fhwahop18036/chapter5.htm)).
3. Validate the frozen base model on held-out observations. Show observed-versus-simulated counts, queue and travel-time plots/tables by site and period, including residuals, missing data and failed fits. Do not call the later policy comparison a Tagum result if base-model validation fails.
4. Freeze baseline and candidate model artifacts, train only on designated training inputs, and evaluate with a separate environment and held-out scenarios/seeds. Stable-Baselines3 guidance calls for a separate evaluation environment and notes seed variability ([SB3 RL tips](https://stable-baselines3.readthedocs.io/en/master/guide/rl_tips.html)). Start planning with at least five held-out demand seeds per condition, then choose final repetitions from observed variability and the adviser-approved analysis plan. Preserve all runs, including failures and negative outcomes.
5. For a signal-control comparison, keep graph, exogenous arrivals, routing mode, vehicle/pedestrian mix, disruptions, safety rules, warmup, duration and seed matched; vary only the controller. For routing, hold the signal controller fixed and vary only static versus adaptive routing. A factorial design is possible only if both effects and their interaction are reported separately.

## Report metric definitions from current source

These are the meanings in `simulation/traffic_engine.py` at this draft date. Freeze code revision with experiments and revise definitions only with a versioned analysis plan.

| Output | Current computation and interpretation |
| --- | --- |
| `avg_wait` (s) | Cumulative stopped wait of completed **and active** vehicles divided by completed plus active vehicles. Pending arrivals are excluded. This is not completed-trip average delay. |
| `avg_queue` (vehicles) | Time average of the **per-incoming-signal-lane** count of vehicles at speed ≤0.1 m/s, excluding connectors. `max_queue` is the maximum individual lane queue. The live chart's queue is the sum over all lane queues, so use the named report field consistently. |
| `throughput` | Vehicles completed within the measurement window. `throughput_per_hour` is that count divided by elapsed measurement hours; it is not an observed field volume. |
| `avg_travel_time` (s) | Mean travel time of completed vehicles only. Congested unfinished trips are censored by this measure; report unfinished and pending counts beside it. |
| `avg_ped_delay` (s) | Cumulative wait of completed and active pedestrians divided by completed plus active pedestrians. |
| `pending_demand`, `deferred_demand`, `unfinished_vehicles` | Pending arrivals at the boundary; deferred/dropped demand; active plus pending vehicles at cutoff. Report all three, plus requested/admitted/completed counts and conservation error. |
| Speed/density | Instantaneous mean of active vehicle speeds and active vehicles per total modeled lane-km, respectively. State the network and sample time. |

The primary outcome should be chosen before running final comparisons (for example, paired vehicle wait with throughput and unfinished demand as guardrails). Report per-seed values and paired differences with uncertainty intervals; do not select only a favorable seed or infer success from training reward. Explain that model predictions are conditional on the frozen graph, demand and simplifying assumptions.

## Objective-to-evidence map for manuscript revision

| Revised objective | Feature and evidence to present | Limit to state |
| --- | --- | --- |
| Tagum road environment | Frozen connected graph, network validation, site/geometry form and field-checked control plan. | The supplied OSM graph is not field validation. |
| Traffic inputs | Provenance-preserving imports, dated counts, count-to-arrival conversion, calibration/validation record. | Synthetic examples do not satisfy an actual-data objective. |
| Configurable study | Scenario editor, saved `engine_config`, seed, network/model fingerprints and repeatable run. | Complete settings must survive edits, training and evaluation. |
| Disruptions and rerouting | Matched closure/recovery scenarios and separate static-versus-adaptive comparison. | Routing uses graph travel-time logic, not RL. |
| Event scenarios | Period-specific demand/event definitions, provenance and observed-versus-hypothetical labels. | A synthetic holiday case is an assumption. |
| RL signals and recommendations | Matched fixed-time versus selected-junction QL/DQL/PPO evaluation on held-out inputs, safety overrides and junction identity. | Current RL is single-junction; no network-wide or real-world improvement is established. |

## Native-engine explanation for Chapter 2

The revised manuscript still describes SUMO/TraCI. The implemented application instead uses React/Three.js for interaction and display, FastAPI for authorized commands and streaming, and `simulation/traffic_engine.py` for the authoritative connected-road dynamics. Python runs the same scenario contract in live, headless, training and evaluation paths; SQLite and versioned artifacts preserve inputs and results. A graph travel-time algorithm handles adaptive routing while QL/DQL/PPO request signal service at one selected junction under shared safety rules. This architecture is a later project decision. Update diagrams, technology list, data flow, tests, limitations and title/objective wording in a new manuscript revision; retain archived source PDFs unchanged.

### Draft architecture wording for a new manuscript revision

SmartFlow is implemented as a web application with a React and TypeScript interface, Three.js and canvas visualizations, and a Python FastAPI backend. The native Python traffic engine maintains the authoritative road, vehicle, pedestrian and control state. The interface sends authorized configuration commands and receives state updates for visualization. SQLite stores scenarios, run records and model references, while saved artifacts retain imported inputs, recordings, policies and checkpoints. A common scenario configuration carries network settings, demand, control plans, disruptions and seed through execution, training, evaluation and replay. These records support inspection and reproduction of software experiments.

Adaptive routing uses graph travel-time logic. Q-learning, deep Q-learning and proximal policy optimization provide signal-control requests for one selected junction in the current prototype; the remaining junctions follow their saved control plans. Shared safety rules constrain the requested service. Signal-control and routing comparisons require matched exogenous inputs and separately identified experimental changes. Exported results retain the controller and model identity, input fingerprints, seed, measurement window and unfinished demand so that the conditions of each reported run can be examined.

### Draft scope and limitations wording

The current prototype supports software experiments on a connected test network. Final study intersections, field-checked geometry and control plans, collected demand, calibration tolerances and required reinforcement-learning coverage remain to be established with the study team and adviser. The supplied network and synthetic input examples therefore demonstrate application functionality rather than validated Tagum traffic conditions. Field collection, calibration and independent validation are required before interpreting model output as evidence for the selected sites. Software-quality assessment and traffic-performance assessment will be reported separately.

The traffic engine simplifies junction occupancy and vehicle interactions. Its ability to represent the selected sites must be assessed against contemporaneous flow, queue and travel-time observations using predeclared tolerances. Completed-trip travel time excludes unfinished trips, so unfinished and pending demand will accompany the reported performance measures. The application uses one API process for its live and training state, with admission for one active compute workload; deployment capacity requires verification on the eventual host. Synthetic test success and training reward do not establish controller effectiveness. These paragraphs describe the implementation as of October 2, 2026 and require revision when the study decisions and evidence change.
