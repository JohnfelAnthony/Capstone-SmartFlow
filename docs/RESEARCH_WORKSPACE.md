# Settings, search and counts import

This guide describes Settings, Search and the peak-traffic video counts on the web branch.

The metric catalog covers five simulated vehicle classes and pedestrians. Model compatibility follows the current engine, network fingerprint and phase plan. [Metric catalog](../simulation/metric_definitions.json) · [Current contracts](../AGENTS.md)

## Settings

Settings shows the signed-in account, role and status and opens the change-password workflow. Account identity is administrator-managed. The browser saves its theme preference. The simulation uses the Canvas 2D map.

## Search

Search finds accessible workspace pages, scenario names/descriptions, run IDs/control/status/notes, and model names/algorithms. Opening a record selects its scenario details, run or model. Search performs a literal substring query: `%` and `_` are text. Each record category returns at most 25 matches; refine the query when more exist. Video contents and raw artifact files are not searched. Results are filtered by the same view permissions as their destination.

## Calibration & Validation (removed, November 6, 2026)

The Calibration & Validation page, its `/api/calibration` routes, the site-validation check, the study gate and the validation criteria and ledger templates were removed (decision D38): the study does not calibrate or validate the simulation. Records saved earlier stay in the `calibration_records` table, untouched but no longer reachable from the application. Results are described as **scenario-based, demand from field counts, not calibrated or validated**.

## Peak-traffic video counts (D49)

In **Scenarios**, the Traffic section offers **Peak traffic** (the site's video count) or a **Density preset**. Peak traffic replaces the scenario's vehicle demand with the site's count and shows one card: the video and how it was counted, vehicles per hour, the vehicles entering in 5, 10 and 15 minutes of a run, the vehicle mix, counted against assumed numbers for each road, pedestrians and the assumptions. Nothing is saved until the scenario is.

- **Site A:** a manual count of vehicles leaving by each road. Each exit's vehicles are shared equally among the roads that can legally reach it. The 15 counted pedestrians set the pedestrian rate.
- **Site B:** unreviewed automatic detector arrivals on the two highway ends and Sobrecarey Street. Each road's vehicles are shared equally among the roads they can legally reach. Buses and trucks detected on Sobrecarey count as tricycles; Dao Street was not counted and gets Sobrecarey's rate (assumed). Pedestrians follow the chosen level.
- Each share is a steady rate for the whole run; variation within the video is not modelled. Results are scenario-based, demand from video counts with assumed routes, not calibrated or validated.
- The counts live in `data/sites/<site>_peak_counts.json`. After a recount, copy the new Field Observer files into `data/generated/field_observations/` and run `.venv/Scripts/python.exe tools/build_peak_counts.py`. A scenario saved before a recount says its count changed until Peak traffic is chosen again.

The CSV and Field Observer importers were removed; scenarios saved with imported counts keep them.
