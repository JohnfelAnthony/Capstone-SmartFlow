# Settings, search and research comparisons

Implemented October 4, 2026. The sidebar clock and its decorative traffic-light indicator have been removed.

**October 24 scope:** current metric and calibration choices cover the ordinary five-class simulation and pedestrians. Retired vehicle-category outcomes are absent from current definitions and exports. Historical raw records retain their original provenance and frozen definitions; dormant database defaults are not measured outcomes. Current engine `native-4` uses revised RL observation/reward contracts; old models require retraining and incompatible recordings require regeneration. See the [scope decision](ARCHITECTURE_AND_PLAN.md#october-24-scope-decision-ordinary-traffic-only).

## Settings

Settings shows the signed-in account, role and status, and opens the existing change-password workflow. Account identity remains administrator-managed. Theme and default 2D/3D visualization can be saved; the default view is restored on session restoration or sign-in. Theme is browser-wide, while the default view is keyed by user ID on that browser. Saving the standard theme clears a randomized palette. These preferences do not change simulation inputs.

## Search

Search finds accessible workspace pages, scenario names/descriptions, run IDs/control/status/notes, model names/algorithms, and comparison-record names/sites/purposes. Opening a record selects its scenario details, run, model or research record. Search performs a literal substring query: `%` and `_` are text. Each record category returns at most 25 matches; refine the query when more exist. Video contents and raw artifact files are not searched. Results are filtered by the same view permissions as their destination.

## Calibration & Validation

This workspace records **numerical baseline-fit checks**. Researchers supply reviewed reference values; no detector, automatic calibration optimizer, or independent field-certification service is invoked.

1. Save complete scenario inputs and finish a fixed-time baseline, normally using **Scenarios → Record**. Headless runs with saved current-native metrics are also supported.
2. Open **Calibration & Validation → New comparison**, select Calibration, and enter a stable site identifier, reference source and offset-aware collection timestamps. Label invented references Synthetic fixture. The collection start marks simulation t=0; the recording must cover the run's warmup plus measured duration.
3. Select the baseline. Its measurement window and automatic simulated values come from saved metrics. Enter reference values using matching populations, locations, units and definitions; set absolute or percentage tolerances. Local/custom comparisons require a manually extracted simulated value and its extraction method/source.
4. Document parameter changes, rationale and reference-quality notes. Confirm measurement matching and save. To tune, edit the scenario in Scenarios, record another baseline and save another calibration iteration. Saved records are append-only, retaining full run metrics and experiment settings, network identity/hash, seed, source declarations and reviewer identity.
5. Open a calibration record and choose **Validate on independent reference**. Enter a different source and nonoverlapping collection period. Select a baseline retaining the calibrated network, control, routing, disruption and behavior settings. Demand counts, arrivals, mixture and provenance may change for the independent period. Measurement definitions, tolerances, warmup and measurement duration remain frozen.
6. Review the comparison history and export a record as CSV or JSON. Search opens older records outside the latest-200 history list. Both exports retain the complete frozen record; CSV also exposes each comparison as a row and protects formula-like text cells.

### Matching metrics

The [shared native metric catalog](../simulation/metric_definitions.json), also available at authenticated `/api/metrics/definitions`, supplies the current definitions returned to this workspace. New records identify its version; old records retain their frozen text, inputs and tolerances. Whole-network values use the shared availability checks: empty/unrecorded populations are not zero averages, queue measures need recorded ticks, and rates need positive measured time. A different recorded historical engine is not silently assigned native definitions. This does not change parameter-fitting or source-verification capabilities.

| Measure | Required reference meaning |
| --- | --- |
| Completed network trips | Trips completing at network boundaries in the saved measurement window; not a local stop-line count. |
| Mean stopped vehicle wait | Stopped wait for completed and active admitted vehicles divided by their count; pending arrivals are excluded. |
| Mean incoming-lane queue | Time average per incoming modeled-junction lane, including stop-controlled junctions, for vehicles moving at at most 0.1 m/s; excludes connectors. A single queue snapshot does not match this measure. |
| Completed-trip travel time | Full travel time for trips completing during the measurement window; unfinished trips are excluded. |
| Mean pedestrian wait | Wait for completed and active pedestrians divided by their count; crossing time is separate. |
| Local/custom observation | Same stop line, approach, sampling times, definition and units in the field reference and manually extracted simulation value. Cite the extraction. |

The backend rejects average-wait/travel metrics with an empty measured population, manual overrides of automatic metrics, invalid units/windows, non-finite values, unfinished/non-fixed-time runs, missing current-native provenance and conservation errors. Percentage error is undefined when the reference is zero; an absolute tolerance is generally more informative for that case. A percentage tolerance against zero permits only zero error.

Validation rejects reuse of a declared calibration source/hash and overlapping calibration periods at the same site, network and source kind, including other saved calibration iterations. These checks depend on researcher-supplied identities; they cannot authenticate recordings, infer field truth, or guarantee independence beyond supplied provenance. The workspace does not connect field-observer exports automatically or mark a scenario/model field-validated. Numerical thresholds do not replace the collection, audit and analysis protocol in [Research preparation](RESEARCH_METHOD.md).

### Permissions and retention

Viewing requires both `scenarios:view` and `runs-reports:view`. Saving additionally requires `scenarios:edit`; exporting requires `runs-reports:export`. Administrators retain their existing bypass. Search itself is available to authenticated users and reveals only authorized categories. Existing role permissions apply without adding or regranting permissions during migration.

`calibration_records` is created additively by database initialization. Records survive scenario edits and run deletion because their evidence snapshot is stored independently. SQLite backups and staged restores preserve the records. Reference videos/sheets are cited, not uploaded or copied into the bundle by this workspace; retain those original files separately. Frozen metadata remains reviewable after deletion, but reproducing a simulation still requires its original network/input artifacts.
