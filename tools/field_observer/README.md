# Field observer — single-phone recording tool

Version **0.3.0**, October 3, 2026. A separate local tool for **one stationary phone recording per take**. It registers a video, indexes decoded presentation timestamps, provides a local graphical workspace with video upload, counting lines, live detection previews, annotated playback, event review and provisional exports. It does not import SmartFlow's API, database, traffic engine or training runtime.

**Current scope.** Manually review every proposed observation. The detector suggests six traffic and person categories. Reviewers identify local tricycles and jeepneys and add missed vehicles. GUI review includes vehicle exits, counting lines and queue samples. Exports remain provisional, and automatic acceptance is unavailable. For vehicle demand, import the reviewed bundle through Scenarios in SmartFlow. [Counts workflow](../../docs/RESEARCH_WORKSPACE.md#counts-from-field-observer)

Use the [recording protocol](../../docs/FIELD_RECORDING_PROTOCOL.md), [complete tool plan](../../docs/VIDEO_OBSERVATION_TOOL_PLAN.md) and [integration plan](../../docs/FIELD_DATA_SMARTFLOW_INTEGRATION.md) for the research procedure and remaining work. A five-minute recording can be manually reviewed; it does not satisfy the proposed three disjoint two-minute automatic-audit windows.

## Start the GUI (recommended)

On this computer the environment and detector weights are already installed. Double-click **`Start Field Observer.cmd` in the SmartFlow root** (or the launcher in this tool folder). It opens the app in your default browser. Keep the helper window open; you do not need to type commands or start SmartFlow's main web application.

**GPU (October 26, 2026).** The launcher uses the optional GPU environment `.venv-gpu` when it exists, and the CPU environment `.venv` otherwise. Analysis then runs on the NVIDIA GPU when PyTorch can reach it (`auto`), and on the CPU when it cannot; `run.json` records the device actually used. **`Start Field Observer (CPU).cmd`** in this folder is the fallback: it uses `.venv` and forces the CPU. Setting `FIELD_OBSERVER_DEVICE=cpu` or `cuda` overrides `auto` in either environment. On this laptop, `.venv-gpu` is a junction to `D:ield_observer_gpu`, because drive C: has little free space.

Measured here on 60 frames of each 10 Sept 2026 recording (1080p): CPU **1.13–1.15 s per frame** (about 9.5 h for a 16.7-minute, 30,113-frame video) and GeForce MX350 **0.74–0.78 s per frame** (about 6.3 h). Detections were identical on both. The detector itself takes about 0.71 s of each GPU frame; the MX350 is an entry-level GPU, so a stronger NVIDIA GPU is needed for a large speed-up.

1. Click **Choose File**, select the phone video, enter the survey/intersection IDs and researcher name, then click **Load video**. Choose actual field or synthetic/test source honestly. The app copies the file into its local workspace and indexes the original timestamps; the input file stays unchanged.
2. Set the phone rotation before drawing. Click two endpoints on the frame, choose the observation and direction, and click **Add line**. Use separate lines for arrivals, discharges and pedestrian stages. Changing rotation clears existing lines.
3. Click **Start analysis**. The local CPU detector processes the recording. The screen updates with boxes, original detected classes, track IDs and proposed counts. **Stop** cancels after the current frame/model load; interrupted runs cannot become reviewed exports.
4. When processing finishes, use the video player's play/pause/seek controls. The annotated derivative keeps source-relative timestamps; displayed counts follow playback time. The original remains authoritative and is available through **Open original video**. Some original phone/container codecs may require your normal video player; the annotated MP4 is the browser-compatible review copy.
5. Click **Review** on an event to jump to its time. Choose the reviewed class, decision, reviewer and note. For a three-wheeler, choose a **Tricycle subtype**: **Bao-bao (motorized)** or **Pedicab (pedal)**; this sets the class to `tricycle`. A subtype with any other class is rejected. Use **Add missed event at playhead** for omissions and reject false/duplicate events. Related stages can share an episode ID; unrelated vehicles must not. Review the full recording, including objects absent from proposals.
6. If the vehicle's exit is visible, associate it with a configured discharge line placed at that exit; leave it unobserved otherwise. This assignment records the reviewed exit identity, not its crossing time; retain and review a corresponding exit event when timing is required. Use **Queue samples** to record a count at a video time: select complete, lower bound, or unknown visibility. An unknown count remains blank.
7. Expand **Coverage and provisional export**. Save each counting line's actual reviewed time interval and visibility. Complete coverage requires explicitly confirming the full pass. Enter an export note and click **Check and export**; address any reported issues, then **Download reviewed ZIP**. The GUI export includes its checked counting-line configuration. Unresolved/incomplete bins remain blank, not zero.

**No recording yet?** Click **Try demo**, then **Start analysis**. It displays moving boxes, track IDs and two vehicle-arrival / one pedestrian-start proposals. The demo uses explicitly scripted detections, not AI inference, and all its records are labeled synthetic. Actual uploads use RF-DETR regardless of whether you label their source observed or synthetic.

The GUI stores source copies, per-take evidence, annotated derivatives and revisions under `data/generated/field_observer_gui/`. Use **Saved recordings → Open recording** to return to a completed review after restarting. The folder shown in the interface identifies that take's files. Back it up separately; the main SmartFlow backup does not include these recordings. A recording with an existing review draft cannot be reanalyzed in place; preserve that work and create a new take for changed counting lines/settings.

GUI counts are automatic **proposals**, grouped by line, event type and detected class. Arrival, discharge, crossing-start and crossing-completion counters represent different events and must not be summed into unique road users. Corrections and manually entered queue samples are retained separately and enter the provisional reviewed export. Signal changes still use the separate draft table described below. To include checked counting lines in a CLI export, provide `--analysis` with the completed analysis folder; older manual exports without it have no `lines.json`. There is no automatic tricycle model or completed independent accuracy audit.

A developer can start the same interface with `.venv/Scripts/python.exe -m field_observer gui`. `--no-browser`, `--port` and `--data-dir` support isolated verification. The server binds to loopback only, runs one job at a time and uses a per-launch token for changes. No extra web-framework dependency or cloud account is required.

## Manual lane-by-lane count (one approach per pass)

For hand counting without the detector, open the **Manual count** tab (top of the GUI). The page has no sidebar: a slim bar on top loads the recording, the **raw** video (no boxes) plays on the left, and the site map, vehicle buttons, tallies and passes are on the right. It writes the same reviewed-revision format as the detector workflow, so SmartFlow's **Import counts from Field Observer** accepts the export unchanged.

0. In the bar, choose the **study site** and the **raw video** file, then click **Load video** (or reopen a saved recording from the same bar). No name, recording type, survey/intersection ID or clock is asked for: the recording is registered as actual field footage, the survey ID comes from the file name (letters, digits, `_`, `-`), the intersection ID is the site (`tagum_site_a` / `tagum_site_b`), and the collection clock stays unknown (relative video time only).
1. The study site (A or B) is the one chosen in the bar. Its approach names (`north`, `south`, `west`, `east`, the engine's own words) and street names are copied into `field_observer/manual_count.py`; the tool never imports SmartFlow. The map is a schematic four-leg junction, not the surveyed geometry. The site cannot change once a click exists.
2. Click an approach on the **mini intersection** (or press `1`–`4`). One pass counts only vehicles coming **in** on that approach.
3. Play the video (0.25×–2×) and click one button per vehicle. The grid is **5 vehicle types (Car, Motorcycle, Tricycle, Bus, Truck) × the three other legs**, so every click records both the type and the street the vehicle leaves by. A vehicle cannot leave by the leg it entered on, so U-turns have no button and are not recorded; jeepneys and pedicabs have none either (the team must decide how to count them: SmartFlow's importer maps jeepney to bus and pedicab to tricycle, pending that decision).
4. Keyboard: the grid keys follow the button layout (`Q W E R T` / `A S D F G` / `Z X C V B` for the first, second and third exit row), `Space` play/pause, `Backspace` or `Ctrl+Z` undo the last click of the pass, `←`/`→` seek 2 s.
5. Each click is stamped with **video time** (so pause, seeking and slow playback are fine) and saved at once to `manual_count/pass_<approach>.json` inside the recording's folder. Reload the page or restart the tool and the passes are exactly as left.
6. A pass is **complete** only when the playback you actually watched covers the whole video (intervals are recorded while the video plays; a gap over 1 s breaks it) and you press **Mark complete**, confirming you counted every vehicle on that approach. No name is asked for: the revision format requires a reviewer, so every reviewer field in a manual-count export (events, coverage, `review_record.json`) reads the fixed label **manual count**; the export note is optional and defaults to a one-line description of the method. Incomplete passes are listed by approach and block the export; nothing is filled with zero.
7. When all four passes are complete, **Export merged revision** writes the usual revision folder (`manifest.json` with `artifact_sha256`, `events.csv`, `coverage.csv`, `reviewed_bins.csv`, `lines.json`, quality and review records) under `revisions/` through `export_revision`, plus a ZIP. Each click becomes an accepted `vehicle_arrival` at `<approach>_arrival` and a matching `vehicle_discharge` at `<exit>_exit` sharing an `episode_id`; all rows have `review_method=manual_count`. The exit time equals the click time (the counter did not observe a crossing time), and `lines.json` marks its line geometry `nominal_not_drawn` with `counting_method: manual_click`. Bins use the tool's default 900 s grid, identical for every line.

A recording that already has a detector review draft cannot take manual counts (and vice versa for new detector analysis), so the two workflows never double count one take. Tests: `tests/test_manual_count.py` here, and `tests/test_field_observer_manual_count.py` in SmartFlow, which builds a four-pass export with this tool's code and imports it for both study sites.

## Setup on another computer

The tool has its own environment. **PyAV 19.0.1** provides original timestamps. The optional CV stack is **RF-DETR 1.11.1, Supervision 0.30.6, trackers 2.6.1 and Pillow 12.3.0**. The local target is Windows/Python **3.13.3**. Model weights and package caches belong to this tool, separate from SmartFlow's RL models. A first installation/model preparation needs internet access and can take several minutes.

From the SmartFlow root, using its existing Python interpreter to create a separate environment:

```powershell
.venv/Scripts/python.exe -m venv tools/field_observer/.venv
tools/field_observer/.venv/Scripts/python.exe -m pip install --require-hashes --only-binary=:all: -r tools/field_observer/requirements.txt
tools/field_observer/.venv/Scripts/python.exe -m pip install --require-hashes --only-binary=:all: -r tools/field_observer/requirements-cv-lock.txt
cd tools/field_observer
.venv/Scripts/python.exe -m field_observer --help
.venv/Scripts/python.exe -m field_observer prepare-model
.venv/Scripts/python.exe -m unittest discover -s tests -v
```

Optional GPU environment (needs an NVIDIA GPU; about 5 GB):

```powershell
.venv/Scripts/python.exe -m venv tools/field_observer/.venv-gpu
tools/field_observer/.venv-gpu/Scripts/python.exe -m pip install --no-cache-dir -r tools/field_observer/requirements.txt -r tools/field_observer/requirements-cv-gpu.txt --extra-index-url https://download.pytorch.org/whl/cu126
```

Run the remaining examples **from `tools/field_observer`**. Original videos may stay in a designated research folder. The generated take directory belongs under SmartFlow's ignored `data/generated/field_observer/` directory. Videos, environments and generated data must not be committed as application source.

## 1. Register one original recording

Example placeholders below require actual site, clock and file information:

```powershell
.venv/Scripts/python.exe -m field_observer register "C:/Research/J01_take01.mp4" "../../data/generated/field_observer/SURVEY_01/PHONE_01/J01_TAKE_01" --survey-id SURVEY_01 --intersection-id J01 --take-id J01_TAKE_01 --start "2026-10-03T07:00:00+08:00" --collector "Researcher A" --clock-note "Describe the actual phone-clock check here" --source-kind observed
```

Choose `--source-kind synthetic` for invented fixtures; there is no default that could accidentally label them observed. If supplied, `--start` describes the wall-clock time of the **first decoded video frame** and must include a UTC offset. Omit it when unknown and explain the limitation in `--clock-note`; relative video observations remain usable, with an explicit unknown collection clock. The tool does not infer a reliable collection time from filenames or file modification times. Resolve unknown alignment before linking companion logs or claiming time-aligned field evidence.

Registration decodes the entire video to index actual `PTS × time_base`, hashes the original before and after the scan and rejects missing or repeated/backward timestamps. It never edits the original. An existing destination is rejected. Audio, GPS, road geometry and unseen approaches are not inferred.

The resulting directory contains:

```text
manifest.json         Source path/hash, site/take/clock, media details and source kind
frames.csv            Source frame index, PTS, time base and seconds from video start
draft/
  coverage.csv        Measurement scope, time interval and visible/manual-reviewed coverage
  events.csv          Individual vehicle/pedestrian observations
  signal_changes.csv  Manually recorded visible states or clock-aligned observer notes
  queue_samples.csv   Manual complete/lower-bound/unknown queue observations
revisions/            New export directories; earlier revisions are never overwritten
```

This version handles **one source file per stationary take**. Do not register phone-generated file splits as independent observations and then add their totals; continuous multi-file take reconciliation is still pending. Moving the camera starts a different take. Review unusually large timestamp gaps or frozen frames manually and describe partial/unseen intervals in coverage.

## 2. Enter manual observations

Watch the original using an ordinary local video player. Edit the UTF-8 CSV files in `draft/` using their generated headers. For CSV edits, keep IDs as text and retain the exact column order. Each row includes the five identity fields from `manifest.json`: `survey_id`, `intersection_id`, `camera_id=PHONE_01`, `take_id` and `view_segment_id`. Those fields prevent accidental mixing of sites or sequential takes.

Use the frame command to obtain an exact source timestamp near an observed event:

```powershell
.venv/Scripts/python.exe -m field_observer frame "../../data/generated/field_observer/SURVEY_01/PHONE_01/J01_TAKE_01" --time 12.4
```

Copy its returned `time_s` and `frame_pts` together into a video-derived row. They must match `frames.csv`; frame number divided by nominal FPS is not an accepted substitute. The frame command returns timing information; it does not display the image. Recordings with rotation metadata should be reviewed in a player that displays their intended orientation; no polygon coordinates are produced in this stage.

### Coverage

For each event type and location, enter nonoverlapping half-open intervals `[start_s,end_s)`, visibility (`complete`, `partial`, `unseen`), a manual review method and reviewer. `complete` attests that the reviewer inspected the full stated measurement/category coverage for that interval, including objects that no detector would have proposed. A bare empty event table does not establish zero traffic.

Use separate location IDs for counting lines and turning movements. Example: `N_ARRIVAL` for an approach arrival, `N_STOP` for stop-line discharge, and `N_TO_W` for a fully observed turn. The same physical vehicle can generate different event types; **never add arrival, discharge and movement totals as if they were different vehicles**.

### Events

Each event needs a unique `event_id`, a stable `episode_id`, type, location, source time, class and review information. Reuse an episode ID for stages of the same vehicle traversal or pedestrian crossing. A later distinct traversal/crossing gets a new episode ID.

| Event type | Required additional identity for accepted records |
| --- | --- |
| `vehicle_arrival` | Incoming `approach_id`; an observed arrival-line passage |
| `vehicle_discharge` | Incoming `approach_id`; a stop-line passage |
| `vehicle_movement` | `approach_id` and visibly known `exit_id` |
| `pedestrian_arrival` | `crossing_id`; arrival at the crossing waiting area |
| `pedestrian_start` | `crossing_id`; crossing starts |
| `pedestrian_complete` | `crossing_id`; crossing completes |

Vehicle classes are `car`, `motorcycle`, `tricycle`, `jeepney`, `bus`, `truck`, `bicycle`, `other`, `unknown`; pedestrian events use `person`. Three-wheelers use `tricycle` with subtype `bao_bao` (motorized) or `pedicab` (pedal; the green vehicle in the owner's 2 October picture). The detector has no such classes, so set them in review. Count the complete three-wheel unit once. Do not count riders/occupants as crossing pedestrians.

**October 24 scope:** special-response events are outside the study taxonomy. Record their effect in recording context or coverage notes and flag affected intervals; do not relabel them as ordinary demand. Original footage and historical observation revisions remain unchanged. Drafts using the retired category fail current validation/export and need an explicit review against the revised study scope.

Statuses are `proposed`, `accepted`, `corrected`, `rejected`, `uncertain`. Accepted/corrected rows need a reviewer; corrections need a note. Supported manual review methods are `manual_count`, `individual_review`, `corrected`. `automatic_proposal` is allowed only for unaccepted rows; it cannot become an accepted observation without explicit manual review. Keep hidden exits uncertain, retain incomplete pedestrian stages, and explain censored or obscured events in `note`. The tool checks stage order but does not invent missing stages or compute complete waiting times from partial episodes.

### Signals and queues

Signal rows identify the head, controlled movement group, indication and source (`video` or `observer_log`). A log-derived timestamp needs a note identifying the independently retained, clock-aligned log. A video-derived timestamp needs its real frame PTS. Supported indications include colors, color arrows, `walk`, `dont_walk`, `flashing`, and `unknown`; no full-junction phase or safe simultaneous movement is inferred from one lamp.

Queue rows identify the approach and a nonnegative integer count for `complete` or `lower_bound` visibility. For `unknown`, leave the count blank: zero would assert that no vehicles were queued. The tool retains samples without treating their average as SmartFlow's current queue metric.

## 3. Check and export a provisional revision

```powershell
.venv/Scripts/python.exe -m field_observer check "../../data/generated/field_observer/SURVEY_01/PHONE_01/J01_TAKE_01"
.venv/Scripts/python.exe -m field_observer export "../../data/generated/field_observer/SURVEY_01/PHONE_01/J01_TAKE_01" --reviewer "Researcher B" --note "Describe the actual review and unresolved limitations" --bin-seconds 900
```

Checks re-hash the source, verify take identities/frame times, reject duplicate accepted episodes, impossible pedestrian ordering and overlapping coverage, and prevent automatic-accuracy claims. They validate record consistency, not whether a researcher has correctly observed the footage.

Each successful export creates a new directory such as `revisions/r000001/`, containing the observation tables, `reviewed_bins.csv`, `quality_report.json`, `review_record.json` and a manifest with artifact hashes. Prior revisions retain the before/after table evidence and reviewer/reason; the tool detects changes to the previous revision's hashed artifacts before appending another. Invalid drafts produce no completed revision.

Count bins use only accepted/corrected events. They preserve class/subtype and keep event types separate. `count` is blank for incomplete coverage or unresolved events; `observed_count` retains the number of accepted events seen within that interval. A complete manually reviewed interval with no events may have zero. A 10-minute clip remains a 10-minute observation even when the requested bin size is 15 minutes; its final bin ends at the decoded recording end and is never scaled to an observed hour.

Exports are **provisional**. Gate A automatic acceptance and Gate B independent field recount remain outside the current workflow. Use the reviewed bundle for vehicle counts and turns through Scenarios, and back up the original recordings separately. [Counts workflow](../../docs/RESEARCH_WORKSPACE.md#counts-from-field-observer)

## Detector-assisted workflow

After `register`, use the following commands from this tool folder. Replace `TAKE` with the registered take directory and `RUN` with a **new** analysis directory under the take. Paths below are placeholders, not existing field recordings.

```powershell
.venv/Scripts/python.exe -m field_observer setup "TAKE" "TAKE/setup.html" --time 0 --rotation 0
# Open setup.html in a browser. Click two endpoints, check the arrow and add a line.
# Download lines.json and save it as TAKE/lines.json.
.venv/Scripts/python.exe -m field_observer analyze "TAKE" "TAKE/lines.json" "RUN"
.venv/Scripts/python.exe -m field_observer use-proposals "TAKE" "RUN"
```

The editor is a self-contained local HTML file; it uploads nothing and needs no server. If downloads are blocked by an embedded browser, expand **Configuration text / alternate save** and copy the complete JSON into `lines.json`. This alternate output was verified through the browser and Python validator; the embedded browser did not report a completed download during testing. The chosen frame is embedded in the HTML, so treat that file as research footage. If the frame is sideways, regenerate to a new HTML filename with `--rotation 90`, `180` or `270`. Explicit clockwise rotation is applied identically to setup and analysis; phone rotation metadata is not silently applied. Lines cannot transfer across takes, source hashes or rotations.

Supported lines propose **vehicle arrival**, **vehicle discharge**, **pedestrian crossing start** or **pedestrian crossing completion**. Use arrival lines upstream of queues when genuinely visible; stop-line discharge is constrained by signals and must not be substituted for arrivals. A person merely crossing the drawn line is a candidate, not proof of a road crossing. Waiting-area arrivals, actual turns, signals and queue samples remain manual.

Each object's bottom-centre point must cross the finite line segment in the selected direction, beyond a four-pixel deadband by default, within a maximum 0.5-second gap. Each track is counted once per line per run. These are provisional settings, not calibrated Tagum thresholds. ID switches can still duplicate counts and occlusion can hide vehicles. Event time is the first stable source frame beyond the line; refine it against the original video when necessary. ByteTrack receives actual source timestamps, including variable frame intervals. No advertised-FPS timing or frame skipping is used.

Analysis produces:

- `run.json`: completion/failure status, source/model hashes, settings and library versions.
- `lines.json`: the exact line configuration for this run.
- `tracks.csv`: per-frame traffic/person detections with original class, confidence, box and assigned track ID (blank for untracked detections).
- `proposals.csv`: untouched event candidates with detected classes and source timestamps.
- `events_for_review.csv`: candidates using the manual table schema. Vehicle `reviewed_class` starts as `unknown`; it is never silently set to the model's suggestion.

`use-proposals` verifies a complete run and artifact hashes, then seeds an **empty** `draft/events.csv`. It refuses existing draft events. Review the entire video, add missed events, merge fragmented track episodes where justified, exclude riders/sidewalk traffic and correct classes. For three-wheelers use `tricycle` with `vehicle_subtype` `bao_bao` (motorized) or `pedicab` (pedal, such as the green vehicle in the owner's 2 October picture); two-wheel motorcycles remain `motorcycle`, and trucks remain `truck`. Set `review_method=individual_review`, `review_status=accepted` or `corrected`, reviewer and correction notes. Add honest coverage rows before `check` and `export`.

Never edit the raw analysis artifacts to match corrections. Keep them beside the take for comparison with each reviewed revision. A failure or Ctrl+C leaves a failed/interrupted run that cannot seed review. Use a new output directory for a retry. CPU processing is slow (see the measured speeds above). `--device` defaults to `auto`; `cuda` requires a CUDA build of PyTorch, as installed in `.venv-gpu`.

## Next stages

1. Test the first real roadside pilot; measure tricycle/pedestrian misses, occlusion and correction effort.
2. Add independent audit records and Gate A/B enforcement before sampled automatic acceptance.
3. For the study's two midday takes, prepare reviewed exports with mapped arrivals and exits and follow the current counts workflow. [Counts workflow](../../docs/RESEARCH_WORKSPACE.md#counts-from-field-observer)
4. Use the saved queue samples as observation records. Automatic recognition of signal phases is outside the counts import.
