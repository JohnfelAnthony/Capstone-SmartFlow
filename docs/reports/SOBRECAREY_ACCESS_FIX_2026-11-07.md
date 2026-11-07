# Sobrecarey bus/truck access — November 7, 2026

The owner confirmed that buses and trucks cannot use Sobrecarey Street in either direction. This applies only to Sobrecarey; it is owner-provided local knowledge, not independent verification of an ordinance or signage.

## Implementation

- Optional `lane_vehicle_restrictions` restricts Site B `road1f` and `road1r` to exclude bus/truck classes. Cars, motorcycles and tricycles retain access. Highway and Bonifacio access is unchanged.
- The reproducible Site B builder emits the restriction. No road dimensions or island polygons changed.
- Native routes, insertion, scheduled arrivals, closure diversions and shared-pavement geometry preserve the restrictions. Closure-blocked demand is counted by vehicle class.
- Default synthetic demand retains its sampled class and chooses a permitted origin/destination. Explicit trips and count streams with incompatible movements are refused with a review message; counts are not silently dropped or redirected.
- Engine and metric contract advance to `native-11`. Earlier artifacts retain their versions and are rejected by current compatibility checks. The restriction-only checkpoint was `404b45fab29f8f6e5caaf2dd15c51f8b5d9163b2d454fadca76a100a3c9e7227`; concurrent work subsequently changed Site B again. Resolve the current registered fingerprint rather than treating this checkpoint as the final combined network.
- Previous Site B geometry is preserved as `data/networks/tagum_site_b_pre_sobrecarey_access.json`, registered for backup history. Stale saved scenario fingerprints are refused. No saved database, model or research result was migrated or rewritten.

## Verification

- Ten initial access regressions failed before implementation and passed afterward.
- Focused access/geometry/contracts/unchanged historical traffic: **58 passed, 1 expected failure** (remaining Site B clearance limitation).
- Expanded access, imports and revision history: **39 passed, 8 subtests**. Includes shared-pavement retention, live heavy-vehicle closure traffic, conservation, backup inclusion and stale-scenario refusal.
- **154 frontend tests passed**, and the production build (including TypeScript) passed.
- A subsequent read found generator and registered network matching at `0652e5fb4d6ed8345002c1ecfe078f044bb4e837de06a9ecb48e001789cf6e31`, both retaining the Sobrecarey restrictions. Concurrent work is still active, so this is a point-in-time check.
- The permitted connector diagnostic now checks **324 sweeps**, versus 360 before restricting Sobrecarey. It finds **no Sobrecarey contact**. Bonifacio still has **two actual-size bus/truck contacts** and **one conservative-envelope car warning without actual-size contact**. Filtering the diagnostic follows enforced access, not a geometric clearance repair.

## Limits and concurrent work

The full backend suite was started but stopped while another active session changed shared routing/engine files. Repeat the full suite on a stable combined revision before release; the checks above are not full-system acceptance. No browser interaction or new 1,800-second matrix is claimed for this change. The existing map edit and concurrent minor-road/demand-boundary changes were preserved, not reverted or certified here.

Site A's known freeze, Bonifacio clearance, frontage traffic, field confirmation and final RL acceptance remain separate. Imported jeepneys currently map provisionally to the bus class, so conflicting Sobrecarey observations require an explicit class-mapping decision. Do not bypass the access error by silently changing observed counts.
