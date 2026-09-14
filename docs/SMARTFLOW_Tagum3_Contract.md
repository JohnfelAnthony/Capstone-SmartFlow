# SMARTFLOW Tagum 3 Contract

This document locks the Tagum 3 placeholder contract so the third intersection can be added later without redesigning the multi-intersection stack.

Tagum 3 is intentionally a contract-only placeholder right now.

It should not be treated as a fully implemented runtime map until the actual SUMO assets are added.

## Canonical Intersection ID

- `tagum_3`

This value is the stable key used across:

- the scenario database
- the intersection asset registry
- visual-network resolution
- reports and replay metadata
- future RL and comparison flows

## Canonical Labels

- Scenario/UI label: `Tagum 3 (Bypass)`
- Viewport label: `Tagum City - J3 Bypass Intersection`
- Default scenario name: `Tagum City - J3 Bypass Intersection`

## Canonical SUMO Folder Contract

Tagum 3 must live under:

- [sumo/Tagum_3](sumo/Tagum_3)

Required canonical files:

1. `tagum3.sumocfg`
2. `tagum3.net.xml`
3. `tagum3.rou.xml`
4. `main_intersection_scope.json`

Required generated visual-network target:

- [data/generated/visual_networks/tagum_3.json](data/generated/visual_networks/tagum_3.json)

## Registry Contract

The Tagum 3 registry entry must continue to follow the same `IntersectionAssets` pattern as Tagum 1 and Tagum 2 in:

- [simulation/sumo_config.py](simulation/sumo_config.py)

Required stable fields:

1. `intersection_id`
2. `label`
3. `viewport_label`
4. `sumo_dir`
5. `sumo_config_path`
6. `sumo_net_path`
7. `sumo_route_path`
8. `sumo_scope_path`
9. `visual_network_path`
10. `controlled_tls_ids`
11. `phase_sequence`
12. `tls_state_map`
13. `approach_lanes`
14. `pedestrian_route_templates`
15. `default_scenario_name`

## TLS Contract

The canonical placeholder TLS ID for Tagum 3 is:

- `J3`

When the real SUMO assets are added, they should align to that ID unless there is a strong reason to change the UI/reporting contract too.

## Database Contract

No schema redesign is needed for Tagum 3.

The existing `scenarios.intersection_id` field is already the correct place to store it:

- `tagum_1`
- `tagum_2`
- `tagum_3`

## UI Contract

Tagum 3 must continue to reuse the same existing UI pattern already used for Tagum 1 and Tagum 2:

- scenario dropdowns
- scenario create/edit forms
- dashboard load flow
- live run flow
- pre-record flow
- playback flow
- runs and reports metadata

No intersection-specific dashboard redesign should be required.

## Non-Goals Right Now

This contract does not mean Tagum 3 is ready to run.

The following are still intentionally missing until later:

1. real SUMO files
2. real scope file
3. real visual-network export
4. real seeded scenarios
5. full runtime verification

## Ready-To-Implement Checklist For Later

When you are ready to add Tagum 3 for real, the work should be:

1. add the SUMO files into `sumo/Tagum_3`
2. export the visual network to `data/generated/visual_networks/tagum_3.json`
3. seed real Tagum 3 scenarios
4. verify live run
5. verify pre-record generation
6. verify playback
7. verify reports metadata

If those steps are followed, Tagum 3 should drop into the current architecture without another redesign.
