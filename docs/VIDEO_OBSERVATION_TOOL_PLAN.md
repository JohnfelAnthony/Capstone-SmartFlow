# 2. Phone-video observation tool: implementation plan

Prepared **2026-10-02, Asia/Singapore**. This is the agreed direction for a future implementation; no video-analysis software, model installation, field dataset or accuracy result is delivered by this document.

Read with [Field recording protocol](FIELD_RECORDING_PROTOCOL.md) for collection and [Field data and SmartFlow integration](FIELD_DATA_SMARTFLOW_INTEGRATION.md) for conversion, calibration, training and evaluation.

## 1. Decision and purpose

Build a small, local **offline Python observation utility**, temporarily inside `SmartFlow/tools/field_observer/`. Researchers record stable roadside phone videos, process them on a computer, correct the proposed observations, then export documented measurements. The utility can later move into a sibling repository because its exchange with SmartFlow is versioned files.

**Collection constraint: one phone camera only.** Process one stationary take at a time. The same phone may record different sites/angles sequentially, each with its own period and configuration; the tool must not combine those into simultaneous observations. Keep camera identity for provenance, with `PHONE_01` as the initial device. No multiple-camera synchronization or cross-camera tracking is part of the first release. This task updates the plan only and adds no vehicle models or application code.

The first release measures visible vehicle movements and classes, pedestrian crossing events, manually recorded signal changes and manual queue samples. Keep original videos as the evidence. Automated detections are proposals until reviewed; the exported tables retain what was corrected and what remains uncertain.

The utility does not promise to recognize every road user in the footage. Hidden objects, movements outside the frame and unreadable lights remain missing or uncertain. It does not operate physical signals, identify people, or train SmartFlow's RL policies directly from video pixels.

### Smallest capstone delivery

Start with the protocol's **10-minute pilot, manually reconciled reference and site-coverage decision** using ordinary video playback and structured tables. Collection-method testing must not wait for a custom review application. Preserve source timestamps, hashes, coverage, class definitions and corrections from this manual stage.

The first useful software slice is local batch video processing, a simple counting-zone configuration, timestamped vehicle/pedestrian proposals, editable observation tables, manual signal/queue records and repeatable exports. Review may initially use the original video plus CSV tables with retained before/after versions and a correction log. A polished Streamlit interface and integrated SmartFlow bundle-import UI are later conveniences. Keep custom detector training, automatic signal recognition and additional interfaces deferred until pilot evidence justifies their effort.

Measure machine processing time and human correction/checking time on the team's actual computer. One hour at 30 frames per second contains approximately 108,000 frames; CPU feasibility is an empirical pilot result, not implied by the detector's name or benchmark. Keep the manual workflow available when automation costs more effort or misses important road users.

## 2. Selected open-source components

| Component | Chosen responsibility | Source and reuse decision |
| --- | --- | --- |
| **RF-DETR Small**, general COCO detection checkpoint | Local vehicle/person detections | [RF-DETR official repository](https://github.com/roboflow/rf-detr). The Small detection model and open-source package are designated Apache 2.0. Use this specific family; Plus XL/2XL have a different license. |
| **Supervision**, including its ByteTrack implementation | Track association, line/zone logic and overlays | [Supervision](https://github.com/roboflow/supervision), [MIT license](https://github.com/roboflow/supervision/blob/develop/LICENSE.md). Adapt the minimal needed logic from its [traffic-analysis example](https://github.com/roboflow/supervision/tree/develop/examples/traffic_analysis). |
| **OpenCV**, ordinary desktop Python package | Reference-frame polygon/line editing and image operations | Use its [mouse callback API](https://docs.opencv.org/4.x/db/d5b/tutorial_py_mouse_handling.html). The zone editor needs desktop windows, so use one compatible `opencv-python` installation, not concurrent full/headless/contrib packages. |
| **PyAV** | Decode video with presentation timestamps | [Timestamp API](https://pyav.org/docs/stable/api/time.html), [official package](https://pypi.org/project/av/). Keep the source timeline authoritative even for variable frame rate. |
| **Streamlit**, subsequent review stage | Small local review interface once the batch/table workflow is useful | [Official project](https://github.com/streamlit/streamlit), Apache 2.0. Use [video playback](https://docs.streamlit.io/develop/api-reference/media/st.video) and [editable tables](https://docs.streamlit.io/develop/api-reference/data/st.data_editor). The manual pilot and first table exports do not depend on this UI. |

This combines libraries with distinct jobs, rather than combining multiple independent counting applications. The upstream traffic example already supports RF-DETR and ByteTrack, but it is a demonstration, not the required research collection system. Its sample viewpoint, zones, aggregate totals and class handling must be adapted.

Preserve **detector class**, **tracker identity** and **movement/zone identity** in separate fields. The example repurposes `class_id` for zone annotation; copying that behavior would lose vehicle-class evidence. Add timestamped events, review state and exports instead of retaining only cumulative screen totals.

Do not clone entire upstream repositories into SmartFlow or add nested Git repositories. Install published packages; adapt only the small example portions actually needed. At implementation, record the exact upstream commit, adapted files, retained notices and changes in `THIRD_PARTY_NOTICES.md`. Record the selected checkpoint download source, model name, license and SHA-256 independently of the Python package version.

YOLO is an available alternative supported by the example, but is not a second default detector. Evaluate another detector only if the pilot establishes a concrete performance or accuracy problem; replacing the detector must preserve the same event contract and repeat the pilot checks.

## 3. Environment and repository boundary

- Use a separate **Python 3.12, Windows x86-64** tool environment at `tools/field_observer/.venv/`. Preserve SmartFlow's existing API environment and requirements. CPU inference is the baseline; GPU acceleration is optional after a verified CPU run. Offline processing need not be real time.
- RF-DETR declares Python >=3.10, Streamlit includes Python 3.12, and PyAV publishes a Python 3.12-compatible Windows wheel. PyTorch provides Windows installation instructions. These are feasibility indicators, not a completed installation test. Verify the complete chosen combination on the team's actual machine before extending the tool. [RF-DETR package](https://pypi.org/project/rfdetr/), [Streamlit package](https://pypi.org/project/streamlit/), [PyAV Windows package](https://pypi.org/project/av/), [PyTorch installation](https://docs.pytorch.org/get-started/locally/).
- Create a tool-specific dependency input manifest and a lock of the **tested** exact versions and hashes, including transitive packages. Use published stable releases, not a moving `develop` dependency. Record Python, operating system, device and decoder versions in each processing run. No lock or Windows compatibility certification exists yet.
- Keep UI and CLI as consumers of the same Python ingestion, event, review and export services. SmartFlow's FastAPI process does not import detector dependencies or run a Streamlit session.
- Read recordings from a researcher-selected local directory. Initial installation/checkpoint downloads may require internet; analysis and review must work offline once prepared. Do not add cloud upload or API-key requirements.
- Store generated output under `data/generated/field_observer/<survey_id>/PHONE_01/<take_id>/`; processing revisions have distinct child directories. Separate takes never overwrite or merge each other's results. Store detector weights in a tool cache, separate from SmartFlow RL artifacts.
- Ignore the tool environment, cached weights, videos and generated artifacts in Git when implemented. Commit source, schemas, locks, notices, tests and small synthetic fixtures. Back up raw recordings and reviewed exports separately; existing SmartFlow backups must not silently omit them.

The target implementation contains a batch entry point, OpenCV zone editor, schemas, detector adapter, timestamp decoder, event logic and export services. Add the Streamlit review entry point after the minimal batch/table workflow proves useful. These modules remain inside the one tool folder; no new React video application is required.

## 4. User workflow

1. **Register the survey and local recordings.** Enter intersection, observation period, timezone, collector, camera/view ID and movement coverage. Hash every original file. Preview decoding, orientation, timebase and readable coverage before inference.
2. **Establish the take timeline.** Record actual wall-clock start/end and video-to-clock offset for the single phone, uncertainty and recording gaps. Align any manual signal/queue sheet to the same clock. File creation time is insufficient evidence of the recording start. Only verified file splits from the same take share its timeline; repositioning or another site creates a new take.
3. **Mark a reference frame.** In a small OpenCV window, click polygons/lines for approaches, exits, stop lines, pedestrian waiting/crossing areas and optional signal regions. Provide save, undo and clear controls; name each region. Save the frame hash, dimensions, coordinates and zone version.
4. **Run batch analysis.** Decode in source order, detect and track visible objects, generate proposed events and save an annotated review proxy. Show progress and write a completed/incomplete run status. A failure must leave the original untouched and incomplete outputs ineligible for publication.
5. **Review by video time.** Initially use source-video playback and editable tables with before/after snapshots and a correction log. Later, a local Streamlit interface can link an event to surrounding video and exact source frames. Approve, edit, reject or add events; changes require a reviewer, reason and durable revision. Include a full footage pass for measurements requiring manual review so objects with no detector proposal can be added.
6. **Enter signals and queues.** Use the video timeline and editable forms to record signal transitions, movement service groups and queue samples. Keep those observations separate from object detection confidence.
7. **Validate and publish.** Produce quality summaries, reviewed event tables and derived interval counts. Publication requires the coverage and review checks below; provisional output remains available for inspection but clearly labeled.

Future entry points, run from the tool folder using its environment:

```powershell
.venv/Scripts/python.exe -m field_observer ingest --survey survey.json
.venv/Scripts/python.exe -m field_observer zones --survey survey.json --take TAKE_ID
.venv/Scripts/python.exe -m field_observer analyze --survey survey.json --take TAKE_ID
.venv/Scripts/python.exe -m streamlit run review_app.py --server.address 127.0.0.1
.venv/Scripts/python.exe -m field_observer export --survey survey.json --revision REVIEW_REVISION
```

These commands describe interfaces to implement, not commands available in today's checkout. `survey.json` identifies the local package and input files; paths resolve relative to it. Export reads a selected durable review revision, so CLI and UI cannot produce different totals from the same revision.

The Streamlit command belongs to the subsequent review stage. The manual pilot can use ordinary playback and structured tables without any of these custom commands.

### Source time, clip splitting and coverage

Use decoded presentation time (`pts × time_base`, relative to the first valid video timestamp), never `frame_number / advertised_fps` as the authoritative measurement clock. Retain original frame PTS, clip ID and video-to-clock offset for each event. Decode timestamp order must be checked; absent or discontinuous timestamps create a flagged interval requiring manual resolution before time-dependent export.

Retain immutable originals and their hashes. An optional constant-frame-rate or browser-compatible review proxy is a derivative with a source-to-proxy time mapping. Measurements stay tied to the original; a proxy must not silently alter durations or precision. Frame stepping uses decoded source frames even if browser seeking is coarse.

Phones may split recordings into files. Declare each file's actual timeline position; do not concatenate them by filename and assume continuity. Reset tracker identities at clip breaks/gaps; mark border tracks for review so a vehicle spanning adjacent clips does not become two accepted movement events. Interrupted coverage is not a zero count. Camera movement starts a new view segment and requires the zone configuration to be checked again.

Define complete, partial and missing coverage for every movement/crossing in each single-camera take. Count an event once within that take, including when a phone-generated file split divides its track. Recordings made after moving the phone cover a different period; retain them separately. No cross-camera re-identification, overlapping-camera total or second-camera requirement belongs to this implementation.

## 5. Observation rules

### Vehicles

- Detect car, motorcycle, bus, truck, bicycle and person classes where supported. Preserve the model's original class and confidence. The reviewed vehicle taxonomy is `car`, `motorcycle`, `tricycle`, `jeepney`, `bus`, `truck`, `bicycle`, `emergency_confirmed`, `other` and `unknown`; emergency classification needs an observable basis and manual confirmation. COCO classification is not a reliable dedicated tricycle/jeepney classifier.
- Explicitly include the owner's pictured green/yellow Tagum passenger tricycle: reviewed class `tricycle`, optional `vehicle_subtype=tagum_passenger_tricycle`. Two-wheel motorcycles remain `motorcycle`; trucks remain `truck`. Count a complete three-wheel passenger unit once, not as both motorcycle and car. Preserve subtype through review/export and audit these cases separately. Green color alone is insufficient classification evidence. Initially correct tricycle proposals manually; custom training is a later option justified by pilot errors.
- Associate detections with ByteTrack IDs within a camera segment. A track is not a guaranteed persistent real-world identity; identity changes, merged objects and obstruction need review. Process all decoded frames initially. Any later frame sampling must be recorded and repeat the pilot verification.
- Count a vehicle movement once when the same reviewed track has a valid approach entry and outbound exit, using a configured directed line/zone sequence. Maintain one proposed event per completed traversal; repeated zone occupancy and boundary jitter must not increment it.
- Preserve partial entry-only, exit-only and ambiguous movements. Do not assign a missing exit or full network destination from a guess. A stop-line crossing is a discharge event; an upstream entry event can measure arrival only when that entry is visibly inside the defined survey coverage.
- Avoid automatic queue-length or meter-speed estimates in the first version. Pixel motion is not a meter scale; any future distance/speed measurement needs documented spatial calibration and a matching field validation procedure.

### Pedestrians

- Count crossing demand only for people visibly entering the relevant waiting/crossing area with crossing intent established by their subsequent visible behavior or manual review. Keep sidewalk passers, riders and ambiguous people separately; a detected person is not automatically a crossing request.
- Record separate proposed waiting-area arrival, crossing start and crossing completion events, with crossing ID and direction. One person can have one crossing episode represented by several event types; do not sum those as several pedestrians.
- Waiting time is crossing start minus the observed waiting-area arrival for the same episode. Existing waiters at clip start are left-censored; people still waiting at clip end are right-censored. Unknown arrival, obstruction or an unmatched identity means no complete waiting-time estimate.
- Completed-crossing counts can be published where visible even if waiting arrivals cannot. Preserve the distinction so completed service is never silently imported as arrival demand. Include unfinished/uncertain episodes alongside completed ones.

### Signals and queues

- **Manual signal timestamp editing comes first.** Identify the signal head, controlled movements and visible indication, then record each change. Preserve red, yellow, green, turn arrow and pedestrian indications as observed; unknown state remains unknown.
- Record which movements receive service simultaneously, not just one lamp's green length. Compute a duration only between consecutive verified transitions with adequate visibility. The first/last state interval and unreadable intervals may be censored.
- Only after the manual baseline works, add an optional color-region assistant that proposes state changes from a selected visible signal ROI. Never infer an unseen light from vehicles moving. Every assistant-proposed change remains reviewable; retain flashing/arrow/unknown cases.
- Enter queue snapshots by approach/lane in vehicles, provisionally every 30 seconds and at observed green onset/end where possible. Record visibility and whether the queue extends outside the view. A visible count is a lower bound when its tail is hidden. Define the stopped/queued rule in the survey protocol; compare matching simulated snapshots rather than treating the sample mean as today's engine `avg_queue` metric.

## 6. Files and minimum exchange contract

Use `schema_version: 1` in the package metadata. Every record has `survey_id`, `intersection_id`, `camera_id=PHONE_01`, `take_id` and `view_segment_id` where applicable. IDs are stable across review revisions; local tracker IDs are namespaced by processing run, take and view segment.

| File | Minimum content and purpose |
| --- | --- |
| `manifest.json` | Take period as offset-aware ISO 8601 timestamps, timezone, site ID, device `PHONE_01`, take/view IDs, collectors, source files/hashes, clock offsets/uncertainty, missing intervals, measured movement/crossing coverage, processing/review revisions and artifact hashes. Sequential takes retain separate periods. |
| `camera_config.json` | Reference frame/hash/dimensions, view segments, named directed lines/polygons, approach/exit/crossing/signal mapping, visible coverage and configuration version. |
| `tracks.jsonl.gz` | Clip/frame PTS and seconds, namespaced track ID, bounding box, detector class/confidence and relevant zone memberships. A machine proposal retained for audit, not the published count table. |
| `events.csv` | `event_id,episode_id,event_type,time_s,clip_id,frame_pts,track_id,approach_id,exit_id,crossing_id,direction,detected_class,reviewed_class,vehicle_subtype,confidence,review_status,review_method,uncertainty_s,censoring,note`. `episode_id` links arrival/start/end for one traversal or crossing. Fields absent for an event type remain empty. Common IDs also accompany each row. |
| `signal_changes.csv` | Common IDs, signal head, controlled movement group, video/survey time, indication, visibility, timing uncertainty, source and review status. Store transition records; derive complete durations. |
| `queue_samples.csv` | Common IDs, sample time, approach/lane, visible queue count, complete/lower-bound/unknown coverage, sampling definition and reviewer. |
| `review_log.jsonl` | Revision, record ID, old/new values, reviewer, edit time and correction reason. Additions and rejections are explicit; preserve original proposals. |
| `reviewed_bins.csv` | Interval start/end, intersection, take/view IDs, movement/crossing, reviewed class, optional vehicle subtype, measurement kind, count, coverage and review status. Vehicle arrivals, movements, discharges and pedestrian arrivals/starts/completions are separate kinds. Class totals include subtype rows once; never add class totals to their subtotals. |
| `quality_report.json` | Coverage/gaps, reviewed duration, development versus reserved audit windows, independent reference/version, raw and corrected counts/event errors, separate Gate A and Gate B results, categories/conditions eligible for sampled acceptance, timing checks, uncertain/censored cases, runtime, manual-review time, dependency/config/model/review hashes and publishability decision. |

`time_s` is seconds from the manifest's collection start, including any declared pre-measurement buffer. The field timezone defaults to **Asia/Manila, UTC+08:00**. Retain the original clip timestamp and clock mapping so a later simulation window can be rebased explicitly. Count intervals are half-open `[start_s,end_s)`; an event on the boundary belongs to the next bin. Incomplete intervals carry coverage rather than a fabricated full-period total.

Review statuses are `proposed`, `accepted`, `corrected`, `rejected` and `uncertain`. Corrected records must include the reviewer and source evidence. Derived publishable totals use accepted/corrected records within complete measured coverage; include uncertainty and excluded-event totals in the companion report. Detector confidence is not a measurement error bound or a reviewer confidence score.

Record review method as `manual_count`, `individual_review`, `corrected` or `sample_audited_auto`. Bulk acceptance requires **Gate A** below to pass on fresh independent reference windows for the frozen automatic procedure, category/view and conditions, plus checked coverage and resolution of flagged uncertain/local-class cases. Correcting the audit clips to pass **Gate B** cannot authorize unsampled automatic results. When Gate A fails, perform a complete manual video pass for the affected measurement period or revise the procedure and pass fresh windows. Keep sampled acceptance distinct from individual/manual review and record the decision and supporting audit in the durable log.

Export never overwrites previous published revisions. It checks source/config/review hashes, required IDs, take interval bounds, measured movement coverage and review state, then writes a package to a new revision directory. Exact event tables are retained even when 15-minute bins are exported. A changed zone/model/config requires a new processing revision and invalidates old quality evidence for the changed view.

The utility publishes a **neutral observation package**. SmartFlow's import/conversion adapter consumes its reviewed measurements through the process in [Field data and SmartFlow integration](FIELD_DATA_SMARTFLOW_INTEGRATION.md). It must not force local turns into full-network OD trips or delete road-user classes merely to fit today's importer.

## 7. Pilot, acceptance and implementation order

1. **Manual pilot and site decision:** ordinary playback, independently reconciled tables, clock/source records and the protocol's coverage matrix. Decide the required site/model changes and whether automated counting offers enough benefit before committing to further tooling.
2. **Minimal batch/table workflow:** timestamp decoding, take manifest, simple zone editor and RF-DETR Small + ByteTrack proposals with original class preservation. Support editable vehicle/pedestrian records, manual signal/queue tables, source references, durable corrections and repeatable exports. Measure runtime and correction effort; retain a manual fallback.
3. **Verify the measurement procedure:** check pedestrian arrival/start/end linkage, censoring, file splits and missing coverage. Apply Gates A and B separately to fresh reserved audit windows. Verify later takes/conditions and preserve their separate periods/configurations.
4. **Smallest adequate SmartFlow conversion:** retain the neutral evidence package and use a deterministic conversion plus existing supported CSV inputs where their semantics fit. Record mapping/provenance and reject unsupported observations; add only the engine/import changes required by the site decision. Follow the integration plan before claiming field validity.
5. **Later conveniences and optional automation:** Streamlit event-linked review and bundle-import UI when they save demonstrated effort; signal ROI assistance, a detector replacement or custom tricycle/jeepney training only when supported by pilot errors. These are not prerequisites for collecting reviewed observations.

### Provisional automation quality defaults

Use a **10-minute pilot** for feasibility and reserve three disjoint two-minute human-recount windows per view for automatic acceptance. Extend it or collect another same-phone take when development has already used those windows. Include difficult conditions and identify reserved windows before examining automatic errors. Reviewers establish the reference from original footage independently of automatic results; a second reviewer reconciles ambiguity. The survey protocol describes full-period collection and buffers.

- **Gate A — sampled automatic acceptance:** freeze the detector, zone/tracking/counting configuration and processing version. Compare its uncorrected output on fresh reserved windows against the independent reference. For each audited movement/class or pedestrian category, require count difference at most one for 1–19 reference events, at most 5% for >=20, and zero spurious events when the reference is zero. Apply the same allowed-error budget to missed, duplicated/spurious or wrongly assigned events, counting each discrepant event once within the audited category. Net totals cannot cancel event errors. This gate applies only to tested categories/views/conditions; unrepresented classes or materially different conditions require added audits or a complete manual pass.
- **Gate B — final reviewed-data quality:** independently recount samples of final corrected/manual data using the same count and event-error budgets. Report raw and final errors separately. A corrected sample passing this gate does not establish Gate A or validate unsampled automatic results.
- If Gate A fails, require a complete original-video pass for the affected measurement throughout the period, including objects absent from detector rows; label those results manual/individually reviewed. Alternatively revise the procedure, retain the failed evidence and pass new reserved windows. Reusing a corrected or tuned acceptance sample is not a fresh audit. If Gate B fails, correct/expand review and recount fresh samples.
- Report misses, duplicate counts, wrong movements, class errors and identity errors separately, with audit sample sizes and exclusions. Preserve all flagged ambiguous/local-class review decisions. The reference-zero check detects spurious events in that sample; it does not validate recognition of a class absent from the sample.
- For clearly visible signal changes, the provisional timing target is <=1 second difference against manually checked source timestamps. Unreadable states and larger timing uncertainty must be flagged, not rounded into a pass.
- Record human time for entirely manual recount and for AI correction plus checking, separately from machine runtime. Retain automation only when it produces useful reviewed measurements with reasonable effort. If correction is slower or unreliable, use the tool's manual workflow for that view and log the decision.
- These are **project automation QA defaults**, not adviser-approved traffic-model calibration tolerances, promised detector accuracy or a claim that a ten-minute pilot represents an hour/day of traffic.

### Meaningful acceptance checks

- Timestamp fixture with nonconstant frame intervals, nonzero first PTS, rotated video, split clips and a real gap: correct source time, declared gap, preserved originals and no extrapolated counts.
- Known short movement fixtures: zone occupancy/jitter does not duplicate a traversal; ambiguous exits remain unknown; file-split boundaries do not double count; sequential takes remain separate; detector class survives zone annotation.
- Pedestrian fixture: sidewalk passer and rider excluded; each crossing episode counted once; prior waiter and unfinished wait marked censored; complete wait computed only from matched visible events.
- Signal/queue fixture: simultaneous movement group retained; unreadable intervals stay unknown; final signal duration is censored; hidden queue tail yields a lower bound.
- Review/export checks: add/correct/reject survives reopening; stable event IDs and audit log; CLI/UI share the same totals; original hash mismatch and unreviewed/incomplete output prevent publishable export.
- Audit-gate check: a poor raw result repaired only in audit windows can pass Gate B but cannot unlock `sample_audited_auto`; changed processing requires fresh reserved windows. Verify that full manual review can add an object absent from all detector rows and retains its manual provenance.
- Offline Windows smoke: prepared checkpoint analyzes a short local clip without network access or API keys; local review opens, edits, saves, reopens and exports; cancellation/failure cannot mark partial output complete.
- Real roadside pilot: perform the recount/time checks above before expanding collection. Synthetic fixtures prove logic, not Tagum accuracy. Preserve failing clips and corrections for explaining limitations.

Completion means a repeatable local recording-to-reviewed-observation workflow with measured pilot performance and documented missing coverage. Research validity additionally requires the site survey, calibration, held-out validation and matched controller comparisons in the other two documents.
