# Research preparation protocol

Updated **2026-11-10** for the two-site, scenario-based study. Site A and Site B are separate provisional road networks in Tagum City. Both are unsignalized in the study premise. Each has one junction where proposed signal controllers can be tested. D38 uses one 16-minute midday video per site for vehicle counts and turns. Calibration, independent validation and the software study gate were removed from this study. The original manuscript and dated study plan preserve the earlier design. [Counts workflow](RESEARCH_WORKSPACE.md#counts-from-field-observer) · [D38 evidence](reports/stage-4-counts-import-2026-11-06.md) · [Earlier study plan](superpowers/plans/2026-10-31-two-site-study.md)

## Study conditions and decisions

Compare modeled first-come operation (**No signal**), a proposed **fixed-time** plan and a proposed **RL** controller under matched inputs. First-come behavior and the proposed signal timings are modeling assumptions. Confirm the frozen network and legal movements, fixed-time plan, required RL algorithms, measurement duration and analysis plan with the team and adviser before final comparisons.

The learning contract is `native-14`, `native-local-20-v4`, `phase-service-5-v2`, plus the network fingerprint and recorded phase plan. The `reward_v4` reward is computed at the controlled junction over each decision interval. Training reward and network performance measures answer different questions. [Model contract](../simulation/model_contract.py) · [Reward implementation](../simulation/rl_reward.py)

## Collect and preserve evidence

Preserve the original clips and exports. Record site, recording date and time, approach coverage, reviewer, counting lines, and corrections. Manually review detections and exits in Field Observer. Keep the five export files together, including the manifest and hashes. Blank bins represent incomplete evidence. A reviewed zero represents a covered interval with no counted events.

In **Scenarios → Import counts from Field Observer**, select the five files, check the per-class and per-turn totals and mappings, then save the scenario. SmartFlow converts counts to steady hourly rates for each movement and class and uses them at the modeled boundaries. The source kind is `field_counts`. These rates represent the sampled midday window. They provide no independent measurements of daily traffic, travel time or simulation accuracy. [Field Observer](../tools/field_observer/README.md) · [Counts workspace](RESEARCH_WORKSPACE.md#counts-from-field-observer)

The four CSV formats below are separate scenario inputs. Their observed-data provenance checks can flag duplicate content and overlapping declared periods on the same network. For separate periods on the same day, provide offset-aware collection start and end timestamps. Retain the actual collection period and the original source files.

## CSV template and import guide

The Scenarios create/edit sheet downloads header-only templates and separate, explicitly synthetic one-row examples for all four supported schemas. Examples use connected boundary, junction and lane IDs from the **loaded network**, including a replacement network. Download a new example when changing networks. A blank template requires data rows before validation; missing observations must not be entered as zero.

| Schema | Required columns, in template order | Meaning |
| --- | --- | --- |
| Trips | `time_s,source,destination,vehicle_type` | One vehicle arrival per row; boundary origin/destination IDs and a supported vehicle class. |
| OD counts | `start_s,end_s,source,destination,count` | Boundary origin/destination count over a time bin. |
| Turn counts | `start_s,end_s,source,destination,junction,from_lane,to_lane,count` | Count for a permitted incoming/outgoing lane movement on a connected boundary OD route. |
| Pedestrian counts | `start_s,end_s,junction,count` | Crossing demand at a modeled junction over a time bin. |

Times are nonnegative seconds relative to collection/simulation start, including warmup; they are not clock times. Bin end must exceed start. Counts are nonnegative integers; zero means the interval was observed and had no arrivals. Vehicle classes are `car`, `motorcycle`, `tricycle`, `bus` and `truck`. Count-based vehicle imports currently generate cars with evenly spaced arrival times; they do not preserve an unrecorded vehicle mix. Use trips when individual class and arrival information is available. Turning counts need the stated OD allocation, so an approach-only survey must first be transformed using a documented allocation method.

Keep IDs as text when editing in a spreadsheet, preserve the exact column names and export UTF-8 CSV. Boundary, junction and lane IDs shown in the form belong to the current network. Provide a meaningful source description, collection date and source kind. For observed periods on the same day, provide both offset-aware collection start/end timestamps; all CSV times must fit within that interval. Preserve original observations separately from cleaned/imported versions. The importer reports row errors and validates before applying the result to the draft; save the scenario only after reviewing its demand and provenance. Downloading a synthetic example selects the synthetic source label; a later manual label change does not make the example field evidence.

CSV run reports expose seed, network and demand fingerprints, controller/model identity, measurement start/duration, unfinished demand, dataset provenance JSON and the full experiment JSON. Each imported dataset retains its observed or synthetic source kind. JSON reports retain the frozen experiment object. Interpret a report's saved experiment provenance rather than the scenario's subsequently edited settings; the source record remains authoritative for collection details.

## Freeze inputs and evaluate

1. Freeze the engine revision, network fingerprint, demand and its provenance, fixed-time plan, model artifacts, seed set, warm-up, measured duration and metric catalog. Keep synthetic test results separate from comparisons driven by reviewed counts.
2. Use development seeds 101–110 for development comparisons. The evaluator requires `--final` to use the reserved final seeds 201–220. Fix model selection and comparison rules before final runs. Preserve per-seed results and disclose invalid runs or exclusions.
3. Vary only the controller for signal comparisons. Hold demand, geometry, routing, disruptions, and measurement windows constant. Compare routing separately with the signal controller held fixed.
4. Report paired differences and uncertainty alongside throughput, incomplete demand, and pedestrian outcomes. Retain recordings and exports for traceability. [Evaluation tool](../tools/evaluate_controllers.py)

## Report metric definitions from current source

Use the versioned [metric catalog](../simulation/metric_definitions.json) for exact units, populations, time windows and unavailable values. Freeze the catalog version with the experiment.

| Output | Current computation and interpretation |
| --- | --- |
| `avg_wait` (s) | Cumulative stopped wait of completed **and active** vehicles divided by completed plus active vehicles. Pending arrivals are excluded. This is not completed-trip average delay. |
| `avg_queue` (vehicles) | Time average of the **per-incoming-modeled-junction-lane** stopped count, including stop-controlled junctions, at speed ≤0.1 m/s and excluding connectors. `max_queue` is the maximum individual modeled lane queue, including outgoing boundary lanes. Use the named field: a network queue sum or single snapshot has a different aggregation. |
| `throughput` | Vehicles completed within the measurement window. `throughput_per_hour` is that count divided by elapsed measurement hours; it is not an observed field volume. |
| `avg_travel_time` (s) | Mean travel time of completed vehicles only. Congested unfinished trips are censored by this measure; report unfinished and pending counts beside it. |
| `avg_ped_delay` (s) | Cumulative wait of completed and active pedestrians divided by completed plus active pedestrians. |
| `pending_demand`, `dropped_vehicles`, `unfinished_vehicles` | Requests waiting to enter, requests refused at the pending limit, and vehicles still active or pending at cutoff. Include requested, admitted and completed counts and the conservation check. |
| Speed/density | Instantaneous mean of active vehicle speeds and active vehicles per total modeled lane-km, respectively. State the network and sample time. |

The primary outcome should be chosen before running final comparisons (for example, paired vehicle wait with throughput and unfinished demand as guardrails). Report per-seed values and paired differences with uncertainty intervals; do not select only a favorable seed or infer success from training reward. Explain that model predictions are conditional on the frozen graph, demand and simplifying assumptions.

## Objective-to-evidence map for manuscript revision

| Revised objective | Feature and evidence to present | Limit to state |
| --- | --- | --- |
| Tagum road environment | Frozen connected graph, network validation, site/geometry form and field-checked control plan. | The supplied OSM graph is not field validation. |
| Traffic inputs | Reviewed counts and turns, preserved source files and the conversion to steady arrival rates. | One short midday sample per site informs demand. The simulation is uncalibrated and unvalidated. |
| Configurable study | Scenario editor, saved `engine_config`, seed, network/model fingerprints and repeatable run. | Complete settings must survive edits, training and evaluation. |
| Disruptions and rerouting | Matched closure/recovery scenarios and separate static-versus-adaptive comparison. | Routing uses graph travel-time logic, not RL. |
| Event scenarios | Period-specific demand/event definitions, provenance and observed-versus-hypothetical labels. | A synthetic holiday case is an assumption. |
| RL signals and recommendations | Matched fixed-time versus selected-junction QL/DQL/PPO evaluation on held-out inputs, safety overrides and junction identity. | Current RL is single-junction; no network-wide or real-world improvement is established. |

## Manuscript wording

SmartFlow uses a React and TypeScript interface with Canvas 2D visualization and a Python FastAPI backend. The native Python engine maintains the road, vehicle, pedestrian and control state. SQLite and saved artifacts preserve the inputs and results for live runs, recordings, training and evaluation. QL, DQL and PPO request signal service at one selected junction. A separate graph algorithm handles routing.

The comparison is scenario-based, with demand derived from reviewed vehicle counts and turns from one 16-minute midday recording per site. The engine models mixed traffic, including side-by-side vehicle movement and motorcycle filtering. Site geometry, model settings and proposed controller timings remain provisional. The simulation was neither calibrated nor independently validated. Report differences for the simulated conditions and separate the software verification from the traffic-performance comparison.
