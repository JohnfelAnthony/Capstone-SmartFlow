# Peak-traffic video counts in Scenarios

Date: 2026-11-13. Status: **approved by the owner and built** (decision D49). Two details changed while building; they are marked *Built:* below.

## Why

The adviser wants the study-site comparisons (no signal against fixed-time, QL, DQL) to run on traffic the team measured, not only on density presets. The team has one peak-traffic video count per site. Today, counts enter a scenario only through two file importers ("Traffic counts CSV" and "Import counts from Field Observer"). The team does not use them, and the counts they have fit neither format. So the owner wants the counts built in. A person making a scenario picks "peak traffic" and sees what the data holds and what it will produce, instead of attaching files.

## Goals

- **Traffic choice.** The New/Edit Scenario form's Traffic section offers two choices: **Peak traffic (video count)** or **Density preset** (today's Low/Medium/High/Very High).
- **Summary card.** Picking peak traffic shows one summary card of the site's data (the owner chose "version A"). It also shows how many vehicles enter in 5, 10 and 15 minutes of a run.
- **Demand.** The counts become scenario demand by the route rule below.
- **Removals.** "Traffic counts CSV" and "Import counts from Field Observer" are removed from the form, the server and the tests. Scenarios already saved with imported counts still load, run and edit.

## Non-goals

- Calibration or validation. Results stay "scenario-based, not calibrated or validated".
- Variation within the 16 minutes: the counts are a steady rate, as with field counts today (D38).
- Reviewing Site B's detector proposals, or measuring turns.
- Any change to traffic behaviour, the engine version, RL contracts or models.

## Anti-goals (a failure even if it works)

- An assumed origin, route, rate or vehicle type shown as measured.
- A counted vehicle silently dropped or added.
- A preset scenario, saved scenario or recording that runs differently from before.

## The data (decided by the owner)

Both counts are labelled **"Peak traffic"**. The time of day is not shown.

**Site A: manual count, video `IMG_2511.MOV`, 16 min 44 s (1,004.12 s).** Vehicles were counted as they **left** by each road:

| Exit road | Car | Motorcycle | Tricycle | Bus | Truck | Total |
|---|---|---|---|---|---|---|
| North (Dalisay Gante) | 32 | 105 | 48 | 0 | 5 | 190 |
| South (Dalisay Gante) | 72 | 157 | 85 | 0 | 2 | 316 |
| West (Capitol Circumferential) | 79 | 125 | 80 | 7 | 6 | 297 |
| East (Capitol Circumferential) | 73 | 94 | 64 | 8 | 10 | 249 |
| **All** | 256 | 481 | 277 | 15 | 23 | **1,052** |

There are also 15 pedestrians for the whole video (about 54 an hour).

**Site B: automatic detector, video 16 min 8 s (968 s).** There are 650 arrival proposals, none of them reviewed. Vehicles were counted as they **arrived**:

| Video line | Simulation road | Car | Motorcycle | Tricycle | Bus | Truck | Total |
|---|---|---|---|---|---|---|---|
| W | National Highway, west end | 222 | 104 | 0 | 8 | 67 | 401 |
| E | National Highway, east end | 122 | 42 | 0 | 2 | 33 | 199 |
| N | Sobrecarey Street | 30 | 3 | **17** | 0 | 0 | 50 |
| (none) | Dao Street | 30 | 3 | 17 | 0 | 0 | 50, **assumed** |

The owner made three decisions about this data:

- **Sobrecarey's 17 heavy vehicles:** the 15 trucks and 2 buses detected on the N line count as **tricycles**. Buses and trucks are banned on Sobrecarey Street (D42), and the detector has no tricycle class.
- **Dao Street:** Dao Street was not counted. It gets **Sobrecarey's rate and mix**, labelled as an assumption.
- **Pedestrians:** none were counted. Site B keeps the pedestrian density choice.

The video-line-to-road mapping above is my call. The video's West and East lines are the highway ends; the North line is Sobrecarey Street.

## Routes: equal shares among legal routes (owner)

A **legal** movement is from one road to a different road (no U-turn) for which the network has a route for that vehicle type through the study junction (`RoadNetwork.route(..., vehicle_type=...)`). The counted numbers are kept; only the unmeasured side is shared out.

- **Site A.** Each exit road's count per vehicle type is split equally among the legal origin roads for that type. The outbound totals stay exactly as counted. The arrivals on each road follow from the assumption: about North 287, South 245, West 252, East 268.
- **Site B.** Each road's arrival count per vehicle type is split equally among its legal exits for that type, so buses and trucks never go to Sobrecarey.
- **Rates.** Every (origin, exit, type) share becomes one steady stream: `vehicles_per_hour = share × 3600 / video_seconds`. It runs from time 0 to `STEADY_DEMAND_END_SECONDS`, like today's field-count windows. A run longer than the video keeps receiving vehicles.
- **Label.** The scenario's `demand_source` is `kind: "field_counts"`. Its description starts: **"Demand based on video counts with assumed routes"**. It names the site, the video, the counting method (manual or automatic detector, unreviewed), "peak traffic" and "not calibrated or validated". Its dataset entry records the SHA-256 of the counts file it came from. `traffic_density` becomes `"none"`, as the importers do today.

## Pedestrians (owner)

- **Site A peak traffic:** the pedestrians come from the count, 15 over 1,004.12 s, and the pedestrian choice is locked with a note.
- *Built:* a new pedestrian choice, `pedestrian_density: "counted"`, which requires `pedestrian_rate_per_hour`. The rate is kept only with that choice and dropped with any other, and it is not added to the defaults. Adding it to the defaults would have changed every saved configuration, and with it Compare Runs pairing of existing recordings. The builder check also noted that "observed" already names a demand source kind.
- **Originally planned: one new optional engine setting,** `pedestrian_rate_per_hour`. The density presets give 90, 252 and 540 an hour, and none of them is 54. With the setting at `null` (the default), pedestrians follow `pedestrian_density` exactly as now, so every existing run is unchanged. That is a hard requirement, checked by the pinned digest tests. When the setting has a number, pedestrians arrive at that rate (as the presets do: a random crossing among `network.pedestrian_junctions`, exponential gaps).
- **Site B peak traffic:** pedestrians follow the density choice, and the card says "Pedestrians were not counted at this site."

## Where the data lives (my call)

`data/generated/` is git-ignored local research evidence, so the server does not read it. A small script, `tools/build_peak_counts.py`, reads the copies in `data/generated/field_observations/` and writes two tracked files:

- `data/sites/tagum_site_a_peak_counts.json`
- `data/sites/tagum_site_b_peak_counts.json`

Each file holds:
- the counts by road and type, as counted, and for Site B also the detector's raw classes before the tricycle relabel;
- the video file name, length, take ID and source SHA-256;
- the counting method and review status;
- the line-to-road mapping, the pedestrian count, and any assumptions (Dao Street, the relabel).

The demand conversion reads only these files. Changing a count means rebuilding them with the script.

## Server

One endpoint replaces the two removed ones: `POST /api/scenarios/peak-counts` with `{network_id, engine_config}`. It returns `{engine_config, summary}`, the same shape the removed importers returned. It refuses a network that is not a study site, and any rate it cannot route legally.

The summary feeds the card. It also lets the card be redrawn when a saved peak-traffic scenario is opened: the scenario's dataset SHA-256 identifies the file. *Built:* the SHA-256 is taken over the file's text with LF line ends, so a Windows checkout gives the same value. A saved scenario whose SHA-256 differs from the current file shows the card with a note that the count changed, until Peak traffic is chosen again.

The summary holds:
- **Source:** the label, video, length, method and review status.
- **Counts:** the vehicles counted and the vehicles assumed (Dao Street); vehicles per hour; the vehicles entering in 5, 10 and 15 minutes.
- **By type:** counted per vehicle type.
- **By road:** counted and assumed, with directions and road names.
- **Pedestrians:** the count and the rate, or "not counted".
- **Notes:** the "What is assumed" list and the site's warnings.

## The Scenarios form

**Traffic choice.** A two-option toggle: **Peak traffic (video count)** and **Density preset**. Its sub-labels name the site and method, for example "Site A · manual count".

- **Density preset:** the traffic density and pedestrian selects work as today.
- **Peak traffic:** the summary card is drawn as in the owner's chosen mockup:
  - the "Video counts, assumed routes" tag and the source line;
  - vehicles per hour in large type;
  - three chips for 5, 10 and 15 minutes;
  - a vehicle-mix bar with legend;
  - a road table: counted next to assumed;
  - the pedestrian line;
  - a "What is assumed" list.

  Site B's card adds three warnings:
  - its vehicle types are unreviewed detector guesses;
  - 17 detected buses and trucks on Sobrecarey Street count as tricycles;
  - Dao Street's rate is assumed.

**Counts in a run.** The 5/10/15-minute numbers are the vehicles **entering** the network in that much visible run time, after the hidden warm-up (steady demand keeps the default 120 s warm-up). The card says that how many finish depends on congestion and the controller.

**Saved scenarios with counts imported earlier** (CSV or Field Observer demand). The form shows "Counts imported earlier" with the saved description, read-only. Those counts stay unless the user picks one of the two choices.

**Removed from the form:**
- the CSV field and its help text;
- the `FieldCountsImport` component;
- `importMovementCounts` and `importFieldObserverCounts` in `src/api/native-scenario.ts`;
- the sheet description's "or attach a traffic counts CSV".

## Everything else the change touches

- **`backend/main.py`:** remove `/api/scenarios/movement-counts` and `/api/scenarios/field-observer-counts` and their request models; add the new endpoint.
- **`services/field_observer_counts.py`:** delete.
- **`services/movement_counts.py`:** remove `import_movement_counts`. `approach_boundaries` stays, because other tests and `tools/rehearse_workflow.py` use it.
- **`simulation/scenario_config.py` and `simulation/traffic_engine.py`:** add `pedestrian_rate_per_hour` (default `null`, bounds 0–2,000, kept through save, run, training and evaluation like every other setting).
- **Tests:**
  - delete `tests/test_field_observer_counts.py`;
  - delete the import half of `tests/test_field_observer_manual_count.py` (the Field Observer tool's own export tests stay);
  - keep the `approach_boundaries` tests from `tests/test_movement_counts.py` and drop the rest;
  - `tools/rehearse_workflow.py` uses the new endpoint instead of the Field Observer import.
- **Places that show the demand source** (Runs & Reports, Compare Runs, RL Training, the comparison PDF): no code change. They already show `field_counts` and its description, which now starts with the new label.
- **Docs:**
  - a new architecture decision;
  - `AGENTS.md`'s study-site paragraph: counts now come from the built-in peak-traffic video counts, not "Import counts from Field Observer";
  - `docs/RESEARCH_WORKSPACE.md` ("Counts from Field Observer");
  - the progress note;
  - the README in `data/generated/field_observations/`.

  Dated reports under `docs/reports/` are history and stay. Where current docs call these videos "midday", the wording changes to "peak traffic" (my reading of the owner's instruction).

## Checks before it is accepted

1. **Conversion tests, written first:**
   - At Site A, the demand reproduces each exit road's counted total per type over the video length.
   - At Site B, it reproduces each counted road's arrivals per type.
   - Dao Street equals Sobrecarey.
   - No bus or truck goes to Sobrecarey Street.
   - No U-turn and no illegal movement appears.
   - Every share for a road and type is equal.
   - The 5/10/15-minute numbers are about 314, 629 and 943 at Site A, and about 217, 434 and 651 at Site B including Dao Street.
2. **Unchanged:** the pinned digest tests pass untouched, which proves `pedestrian_rate_per_hour = null` changes nothing. A scenario saved with old imported counts still loads, runs and saves.
3. **Pedestrians:** a Site A peak run generates pedestrians at about 54 an hour over a long seeded run.
4. **API:** both sites return a summary; other networks are refused; the removed endpoints return 404.
5. **Frontend:** tests for the toggle, the card (both sites, with the Site B warnings), the locked pedestrian choice and the "imported earlier" state. `tsc` stays clean.
6. **Browser:** make, save, reopen and record a peak-traffic scenario at each site; a preset scenario still works.

## Left to the builder

Component and file names in the frontend, the card's exact copy beyond the labels above, the script's command-line form, and the decision number.
