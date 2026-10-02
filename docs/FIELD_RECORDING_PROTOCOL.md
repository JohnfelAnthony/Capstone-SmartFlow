# 1. Field recording and observation protocol

Prepared: **2026-10-02**. Status: **agreed project direction and proposed survey procedure; no field observations or accuracy results have been produced**.

Read next: [Video observation tool plan](VIDEO_OBSERVATION_TOOL_PLAN.md) and [Field data integration with SmartFlow](FIELD_DATA_SMARTFLOW_INTEGRATION.md). The existing [research preparation protocol](RESEARCH_METHOD.md) provides the research and import context.

## Purpose and decisions

The team will use **one mobile-phone camera**, recording selected Tagum intersections sequentially from a stationary roadside position. Each take measures one fixed view during its own dated period. Original videos will provide the field record. An offline Python tool will assist with vehicle and pedestrian observations; reviewers will correct its results and record visible signal transitions. SmartFlow will use reviewed observations to build and validate the existing-conditions model before training and comparing controllers. This update changes documentation only; vehicle graphics and application code are outside this task.

The owner reports that intersections have been selected, but their names, boundaries, physical layouts and identifiers have not yet been supplied in this plan. The supplied software `tagum_network` must not be assumed to match them. Record the actual sites before preparing a full survey.

The observation tool will initially live in `tools/field_observer/` inside SmartFlow. Its local generated artifacts will live in `data/generated/field_observer/`; large original videos will be kept in designated research storage rather than committed to Git. This document specifies collection work; it does not implement the tool.

The first deliverable is one **10-minute roadside pilot, a manual reference count and a coverage/model-gap decision**. Use ordinary video playback and structured observation tables for this first pass; a custom counting or review application is not a prerequisite. Full collection follows the site-coverage decision and a predeclared sampling schedule. Automated output alone is not verified field evidence.

## What the team must observe

| Observation | Record | Meaning and limits |
| --- | --- | --- |
| Geometry | Approach/outbound IDs, lane count and use, legal turns, stop lines, crossings, road boundary, dated sketch/photos | Check map geometry against the site; a map supplies neither demand nor signal timings. |
| Vehicle arrival | Time crossing a defined approach arrival line, class and direction | Arrival at that line; if queues extend beyond it, actual demand is only partly visible. |
| Vehicle movement | Entry approach, exit approach, stop-line crossing time and vehicle class | Local movement and discharge; this does not reveal the full boundary-to-boundary trip. |
| Pedestrian arrival | Time entering a defined crossing waiting area and intended crossing when identifiable | Crossing demand; pedestrians already waiting at video start have unknown earlier arrival. |
| Pedestrian crossing | Crossing ID, direction, start and completion time when visible | A crossing event; completed crossings alone omit people still waiting. |
| Signal state | Signal-head ID, controlled movements, observed color/arrow and transition times | Actual control during the recorded period; one visible head does not establish all other heads' states. |
| Queue | Approach/lane, timestamp, stopped-vehicle count or visible minimum, observation method | Performance reference; record whether the tail is outside the frame. |
| Travel-time sample | Defined segment with entry and exit visible in the same fixed take, event times and match method | Only the measured segment; the phone cannot establish travel time along an unseen route. |
| Conditions | Weather, lighting, obstruction, unusual event and its time | Explain variation, coverage failures and periods unsuitable for particular measurements. |

Use vehicle classes `car`, `motorcycle`, `tricycle`, `jeepney`, `bus`, `truck`, `bicycle`, `emergency_confirmed`, `other` and `unknown` in the original observation tables. Agree category examples during the pilot. Preserve jeepneys and bicycles as separate field classes even if SmartFlow needs an explicit later mapping. Do not infer emergency priority from a detector label alone; record the observable basis for an emergency classification.

### Vehicle categories and the pictured Tagum passenger tricycle

Use **seven ordinary field categories** initially. Count pedestrians in separate crossing tables; retain `other`, `unknown` and confirmed emergency observations as additional labels rather than forcing every road user into a known category.

| Field category | What to distinguish |
| --- | --- |
| `car` | Passenger cars, including sedans and SUVs; optional body subtypes instead of brand/model classes. Agree van/pickup boundaries in the pilot guide. |
| `motorcycle` | Two-wheel powered motorcycles and scooters, including those carrying passengers. |
| `tricycle` | Motorized three-wheel vehicles, specifically including the pictured green/yellow Tagum covered passenger tricycle. |
| `jeepney` | Jeepney public-transport vehicles; preserve their category rather than silently substituting car or bus. |
| `bus` | Buses, with optional size subtype if the surveyed fleet warrants it. |
| `truck` | Goods/freight trucks; light/heavy subtypes if consistently identifiable. |
| `bicycle` | Pedal bicycles, distinct from two-wheel motorcycles. |

The owner supplied an image of green/yellow covered passenger tricycles in this conversation as the body-style reference.

This image was supplied by the owner on October 2 as a **classification and visual reference**, not as collected intersection evidence. Use `vehicle_class=tricycle` and `vehicle_subtype=tagum_passenger_tricycle` for this body style. The subtype is not a legal-registration classification or an assertion that every Tagum tricycle has identical dimensions.

Count the complete motorcycle/cabin/sidecar unit as **one vehicle**. Do not count its motorcycle portion again under `motorcycle`, or its driver and seated passengers as pedestrians. A passenger who alights and crosses can subsequently produce a pedestrian crossing event. Classify by structure and visible movement; green paint alone does not establish the class.

Explicitly audit these tricycles against two-wheel motorcycles and cars. Preserve an unknown class/subtype if obstruction prevents identification. Document representative dimensions and behavior separately; this illustration does not calibrate size, speed, loading, stopping or filtering behavior.

Motorcycle riders and vehicle occupants are not pedestrian crossings. People merely walking along the sidewalk are excluded from crossing demand. Count a person's crossing once per actual crossing event, rather than once per detected frame. Record interrupted or abandoned crossings separately; never invent completion times.

## Team roles and equipment

For a small pilot, one person can record and later review, with a second reviewer reconciling the manual reference. For the full survey, assign site/coverage coordinator, the single phone operator, signal/queue observer and data reviewer; one person may hold more than one role if coverage remains workable. A companion observer may use a paper log; no second recording device is required.

Bring the one phone with sufficient storage and a charged battery, a stable support or tripod, a collection sheet, and a map/sketch. Test sustained recording and storage beforehand; use external power if needed. The phone records; inference runs later on a computer.

Choose a stationary location that the team may use and that does not obstruct the road or sidewalk. Do not move into the roadway to improve a view. Obtain access permission for an elevated private vantage if using one. Keep research copies access-controlled; public presentation clips should conceal identifiable faces or plates when those details are unnecessary.

## Pilot: one site before the full survey

1. Draw and label the intersection, including each approach, departure, stop line, crossing and signal head. Use provisional IDs if the final SmartFlow graph has not yet been prepared.
2. Set a stable roadside diagonal view. Start with landscape **1080p at 30 fps** as a practical recording default; inspect the video rather than assuming those settings guarantee visibility. Do not pan, zoom or change position during a take.
3. Record **10 minutes** as the pilot default, ideally enough to observe several full signal cycles. A shorter **5–10-minute exploratory clip** can check framing first. For automation acceptance, reserve three disjoint two-minute windows that have not been used to adjust the detector or counting rules. Extend recording or collect another take with the same phone if the pilot has already been used for development or cannot supply those fresh windows. This clip tests the method and is not the final representative traffic survey.
4. Inspect footage at normal speed and paused frames. Check motorcycles beside larger vehicles, turning paths, pedestrian waiting/crossing areas, queue tails and readable signal heads.
5. Manually count the visible movements/classes and pedestrian events using video playback, with source times and uncertainty recorded. Have a second reviewer reconcile the reference before comparing it with any automatic result. If a prototype is available, compare processing time, correction/checking effort and raw errors against this manual workflow; otherwise retain the reference for the later prototype.
6. Complete the per-measurement coverage decision below and the site/model-gap review in the integration plan. Identify required signal, capacity and pedestrian behavior before deciding which software additions are necessary. Set the survey schedule after this pilot review.

Choose the one fixed view that best covers the required movements and pedestrian crossing. If the whole junction cannot be measured from that position, define the observed subset and record the remainder as unavailable. If another angle is essential, stop the take before moving the same phone and record a new take with its actual time and new configuration. Those takes describe different periods; their totals cannot be added into a supposedly simultaneous intersection count.

## One-camera coverage and clock reference

Create a coverage table for each site before recording:

| View ID | Intended coverage | Authoritative measurements | Known missing coverage |
| --- | --- | --- | --- |
| `PHONE_01`, `J01_TAKE_01` | Illustrative fixed diagonal view | Only the named movements and crossings visible in this take | Example: far queue tail or opposite signal head obscured |

These IDs and descriptions are examples, not descriptions of a selected Tagum site. Use `PHONE_01` as the device ID and a distinct take/view-segment ID for every site, repositioning or restart. Maintain a list of complete, partial and unseen movements for each take. Phone-generated file splits at the same position may belong to one take only when their timing is verified.

Expand the view summary into a **measurement coverage decision** before full collection. Add a row for every required approach arrival line, turning movement, pedestrian waiting area/crossing, signal head and queue observation point:

| Required measurement and location ID | Required for which research outcome? | Coverage in this take | Method and supporting source | Decision and remaining limitation |
| --- | --- | --- | --- | --- |
| Illustrative `N_TO_W` turn | Movement flow | Complete / partial / unseen, to be checked | Video event times and reviewer | Retain only after confirming entry and exit visibility |
| Illustrative `HEAD_S` signal | Baseline signal timing | Unseen in proposed view | Same-clock paper log by companion observer, if feasible | Obtain verified timing or leave this baseline input unresolved |

These rows are templates, not site findings. For each gap, choose a workable one-camera position, a companion manual measurement, a separately dated take, or a documented narrower research claim. A separate take does not repair missing simultaneous observations. Distinguish estimated inputs from measured ones. A required inflow/control gap must be resolved or the affected claim narrowed before treating a whole-junction baseline as field-validated; labeling a gap alone does not make the baseline valid.

Check the phone against one reliable clock before and after the take. If a teammate logs signals or queues on paper, use that same clock and record its offset from video time. Keep timing uncertainty and any drift. When a signal is not readable in the one-camera view, use a timestamped manual observer log or appropriately dated verified agency records; otherwise preserve its state as unknown. Do not rotate the camera away from traffic during the take to inspect the light.

Record the actual wall-clock start/end with timezone **Asia/Manila, UTC+08:00**, plus clip duration and video timestamps. Displayed phone clocks and file modification times alone are insufficient to prove an accurate collection start. Preserve the clock-setting/check method.

With one camera, sites are surveyed sequentially. Collect comparable ordinary/peak windows on recorded dates and repeat them as the study requires. These support site-level observations and variation across periods. A connected-network scenario assembled from different site periods must be labeled a **constructed scenario** with documented allocation/estimation; it is not an observed simultaneous network snapshot. Start validation with the measured site/view; limit network-wide conclusions to the evidence actually available.

## Sampling schedule for the full survey

The working proposal is **60-minute analytical periods**, summarized in **15-minute count bins**, for ordinary and peak conditions repeated on distinct collection days. Choose actual dates, peak windows and repetition count from reconnaissance, pilot variability, study objectives and adviser requirements. These are proposed collection defaults, not an adviser mandate or proof of statistical adequacy. The final schedule and number of days remain to be established before the full survey.

Before full collection, record the agreed site/view list, calendar and repeated periods, calibration/development versus held-out periods, primary outcome and supporting measures, and proposed simulator-fit criteria with the adviser. Revise the schedule if the pilot exposes inadequate visibility or unacceptable review effort. The counting-tool error thresholds below are separate from simulator-fit criteria.

Record enough additional lead-in for the selected simulation warmup and enough follow-up to characterize queues remaining at the end. The survey should cover the full analytical period and, when congestion is relevant, its build-up and dissipation. If that exceeds one hour, extend collection or explicitly bound the question to the shorter observed period. Log storage/battery interruptions as missing intervals.

FHWA recommends matching count duration to the proposed simulation analytical period, ideally using intervals no longer than 15 minutes, and covering congestion build-up/dissipation. It identifies geometry, controls and demand as inputs and recommends field checks of timestamped agency signal plans. Its preference for concurrent counts cannot be fulfilled across sites by the team's single camera; document that limitation. FHWA does not prescribe this team's one-hour default. [FHWA, Traffic Analysis Toolbox Volume III, Chapter 2](https://ops.fhwa.dot.gov/publications/fhwahop18036/chapter2.htm).

Before tuning, designate complete dated periods as calibration/training inputs and different complete periods as held-out validation/evaluation evidence. Do not randomly split frames or copy overlapping clips into both groups. A 5-minute pilot may guide tool development, but is not an independent final validation set.

Do not multiply a short clip's count to claim an observed hour. Any expanded or generated demand is an estimate, with its method and uncertainty recorded. A bin with no visible measurement is missing, not zero.

## Signal, queue and pedestrian observation procedure

**Signals:** begin with manually timestamped transitions from video or an observer sheet aligned to the phone's clock reference. Record the head controlling each movement; movement groups receiving green together; arrows; pedestrian indications; and color-change timestamps. Capture several complete cycles and any changes between cycles. A green interval is the difference between its observed start and the next transition, not a guessed countdown. Record all-red only when all relevant heads are visible or verified by a documented source. If a head is unreadable, its state is `unknown`.

If agency timing sheets are available, preserve the dated source and compare against observed operation. A fixed plan, actuated plan, flashing operation and an unsignalized site require different baseline representations. AI signal recognition is an optional later assistant for a clearly visible head; it does not decide new real-road timings.

**Queues:** for the pilot, make manually reviewed snapshots every **30 seconds** and at each observed green onset/end when possible. Use a consistent definition of a queued/stopped vehicle; record the approach/lane and whether the tail is visible. The 30-second interval is a proposed observation default, not the simulation's time-average metric. A clipped queue is a minimum visible queue, not its total length. Compare simulated snapshots using the same definition and sampling times.

**Pedestrians:** label each crossing and waiting area. Where visible, record arrival, crossing start and finish. At the initial frame, distinguish people already waiting; at the final frame, distinguish people still waiting/crossing. These incomplete events are censored. Waiting time is computed only for events whose arrival and crossing-start times are both observed. Keep counts of incomplete events beside delay summaries.

**Travel time:** initially measure only a defined segment whose entry and exit are both visible in the same continuous fixed take and whose vehicle identity can be reviewed. Recordings made after moving the phone cannot be paired as observations of the same trip. Any independently collected travel-time sample requires a documented separate method. Exclude ambiguous matches from precise travel-time claims; retain local turn counts independently of any later OD estimation.

## Evidence records and illustrative rows

Keep one collection form per take with `collection_id`, site/take/view IDs, collector, date, actual start/end, timezone, clock method/offset, source video name, frame rate/resolution, measured coverage, weather/events, missing intervals and notes. After copying, calculate a SHA-256 hash and preserve the original file. Work on copies; keep reviewed tables and correction logs versioned beside their processing configuration.

Each event needs a source reference: `collection_id`, `take_id`, `video_id`, video timestamp/frame, common observation time, location/movement/crossing ID, measured event, class where applicable, automated/manual method, visibility and reviewer status. Detector track IDs identify local tracks and do not guarantee unique identity across restarted clips or separate takes.

Illustrative rows below are **invented examples of the format**, not collected data:

| Video reference | Observation | Location | Class/value | Review note |
| --- | --- | --- | --- | --- |
| `J01_TAKE_01.mp4`, `00:01:12.400` | Stop-line discharge toward west | `N_TO_W` | `tricycle`, subtype `tagum_passenger_tricycle` | Class corrected from detector's motorcycle label |
| `J01_TAKE_01.mp4`, `00:02:03.200` | Arrival at crossing waiting area | `CROSS_W` | pedestrian event `P014` | Arrival fully visible |
| `J01_TAKE_01.mp4`, `00:02:19.700` | Crossing begins | `CROSS_W` | pedestrian event `P014` | Observed wait: 16.5 s |
| `J01_TAKE_01.mp4`, `00:03:00.000` | Green begins | `HEAD_N` | green | Visible signal or same-clock observer log, method recorded |

Retain both the raw automated event and its correction; do not overwrite its history. A vehicle obscured before its exit can be retained with `exit_unknown`, rather than assigned a guessed turn. Aggregate only eligible reviewed measurements, and attach coverage/missingness to the result.

## Manual audit and quality gates

Set these criteria before processing the full survey. The following are proposed project defaults to test during the pilot, not guarantees of detector performance or academic acceptance:

- Audit at least **three disjoint two-minute segments per view**, using longer/additional recording if needed: an initial usable interval, the busiest visible interval, and a later interval. Reserve acceptance windows before assessing detector results, keep them out of rule/model tuning, and include difficult conditions. For full surveys, retain these segment types and inspect additional flagged segments.
- A reviewer independently tallies each movement/class and pedestrian crossing from the original video; a second reviewer reconciles ambiguous events and the reference before seeing the automatic totals. Inspect the entire audit footage, including objects without detector boxes.
- **Gate A: eligibility for sampled automatic acceptance.** Freeze the detector, zones, tracking/counting rules and processing version. Compare its uncorrected output on fresh reserved windows against the independent manual reference. Per audited movement/class or pedestrian category, allow absolute count difference **no greater than one for 1–19 reference events**, **no greater than 5% for 20 or more**, and **zero spurious events for a zero reference**. Apply the same error budget to the number of missed, duplicated/spurious or wrongly assigned events, counting each discrepant event once within the audited category; cancelling errors cannot pass on net count alone. These are provisional project QA limits, not a claim of statistical accuracy.
- Gate A authorizes `sample_audited_auto` only for the tested measurement categories, view and conditions. An unrepresented class or materially different visibility condition needs added audit coverage or a complete manual pass. Record raw errors even when subsequent corrections remove them.
- **Gate B: final reviewed-data quality.** Independently recount samples of the corrected/manual result and apply the same count and event-error budgets. Preserve raw and final discrepancies separately. Passing Gate B after fixing audit samples does **not** satisfy Gate A or authorize automatic acceptance of unsampled footage.
- If automatic signal transitions are introduced, require each sampled transition within **one second** of the reconciled manual reference, or use the manual timestamp. Record video/synchronization uncertainty separately.
- Audit fragmented tracks, double counts, riders mistaken for pedestrians, tricycle/jeepney classes, dark/obscured objects and entry/exit assignments. Record missed, duplicate and misclassified events separately. Net count agreement can hide cancelling errors, so review individual crossing events in the audit segments too. Review all flagged ambiguous events and local-class cases before accepting them.
- If Gate A fails, either revise the procedure and pass new reserved audit windows, or manually inspect the **entire affected measurement period** and add/correct missed, duplicated and mislabeled events. Reviewing only existing detector rows cannot find omitted vehicles. Record this result as manual/individually reviewed, not `sample_audited_auto`. Correcting the failed sample and resubmitting it cannot establish automatic acceptance. If Gate B fails, correct/expand review and recount fresh samples. Do not mark unseen movements as accurate because other movements passed.

A passed sample audit supports only the tested coverage and conditions. Export whether each result is manually counted, automatically produced with sampled audit, individually corrected, or still unreviewed. Final research tables must include the audit evidence and remaining limitations; unresolved automated rows are not presented as verified measurements.

Keep the criteria and any adviser-approved replacement in a dated quality-plan record before full processing. Distinguish the counting tool's measurement quality from SmartFlow's later calibration/validation tolerances.

## Readiness gates and next actions

1. **Site register:** supply selected names/coordinates, approach/crossing IDs and intended connected boundary. Confirm whether existing controls are signalized and identify the physical movement groups.
2. **Pilot and site decision:** obtain one usable stationary clip from the single phone, a reconciled manual reference and a completed measurement coverage table. Decide which actual signal/capacity/pedestrian features the model must reproduce. No full-survey claim is made from this pilot.
3. **Measurement readiness:** retain a usable manual playback/table workflow; test the small offline pipeline when available. Apply Gates A and B separately, and measure whether automation saves total human effort. Manual signal/queue logs remain valid inputs to review.
4. **Survey readiness:** finalize dated/repeated collection periods, team ownership, storage/backup, warmup/follow-up coverage, outcome definitions, simulator-fit criteria and separate held-out periods with the adviser.
5. **Integration readiness:** map reviewed observations and measurement locations to the verified graph using the smallest adequate conversion path. Apply necessary site-specific engine/import changes in [the integration plan](FIELD_DATA_SMARTFLOW_INTEGRATION.md) before claiming a calibrated Tagum baseline; defer general-purpose interface work until needed.

The field team supplies observations and context; the tool organizes and assists their measurement; SmartFlow reproduces the baseline and evaluates controlled alternatives. A missing camera view, unknown signal state or unrepresentable real phase is a recorded limitation to resolve before relying on that part of the comparison.
