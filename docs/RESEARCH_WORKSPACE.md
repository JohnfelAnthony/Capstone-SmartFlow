# Settings, search and counts import

Implemented October 4, 2026. The sidebar clock and its decorative traffic-light indicator have been removed.

**October 24 scope:** current metric and calibration choices cover the ordinary five-class simulation and pedestrians. Retired vehicle-category outcomes are absent from current definitions and exports. Historical raw records retain their original provenance and frozen definitions; dormant database defaults are not measured outcomes. Current engine `native-4` uses revised RL observation/reward contracts; old models require retraining and incompatible recordings require regeneration. See the [scope decision](ARCHITECTURE_AND_PLAN.md#october-24-scope-decision-ordinary-traffic-only).

## Settings

Settings shows the signed-in account, role and status, and opens the existing change-password workflow. Account identity remains administrator-managed. Theme and default 2D/3D visualization can be saved; the default view is restored on session restoration or sign-in. Theme is browser-wide, while the default view is keyed by user ID on that browser. Saving the standard theme clears a randomized palette. These preferences do not change simulation inputs.

## Search

Search finds accessible workspace pages, scenario names/descriptions, run IDs/control/status/notes, and model names/algorithms. Opening a record selects its scenario details, run or model. Search performs a literal substring query: `%` and `_` are text. Each record category returns at most 25 matches; refine the query when more exist. Video contents and raw artifact files are not searched. Results are filtered by the same view permissions as their destination.

## Calibration & Validation (removed, November 6, 2026)

The Calibration & Validation page, its `/api/calibration` routes, the site-validation check, the study gate and the validation criteria and ledger templates were removed (decision D38): the study does not calibrate or validate the simulation. Records saved earlier stay in the `calibration_records` table, untouched but no longer reachable from the application. Results are described as **scenario-based, demand from field counts, not calibrated or validated**.

## Counts from Field Observer

In **Scenarios**, **Import counts from Field Observer** takes the five files of a reviewed revision (`manifest.json`, `events.csv`, `coverage.csv`, `reviewed_bins.csv`, `lines.json`), chosen together, and turns the accepted arrivals into the scenario's vehicle demand: one stream per time bin, class, approach and turn, at the bin's rate. It shows the totals per approach and class and the turns before anything is applied, and nothing is saved until the scenario is.

- The counting lines' `approach_id` must be the site's own approach names (south, north, east, west); arrival lines are `vehicle_arrival` lines and exits are lines with role `exit`.
- A blank reviewed bin, a coverage gap, a changed file, a U-turn or a vehicle with no reviewed exit stops the import with the reason. A vehicle seen in the last 60 s of the footage with no exit yet is left out and reported. Nothing is read as zero.
- Classes: car, motorcycle, tricycle (including bao-bao), bus and truck map directly. **Pedicab is simulated as a tricycle and jeepney as a bus; both are flagged as pending the team's decision.** Bicycle, other and unknown are listed as not simulated.
- Limits: 16 minutes of one day, midday; counts at the lines are used as boundary entry rates; simulation settings are not tuned to the site.
