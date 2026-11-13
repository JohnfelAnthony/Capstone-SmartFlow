# Realistic no-signal behaviour at the study junction

Date: 2026-11-12. Status: **design for adviser approval**. Nothing is built.

## Why

The adviser wants the no-signal condition in Compare Runs to look like the real junction. The team's 16:44 midday video shows these behaviours:

- Vehicles from different roads are in the middle of the junction at the same time, on crossing paths.
- Drivers do not stop at a line. They roll in slowly and sort it out inside the junction. Left-turners wait in the centre.
- Motorcycles take small gaps. Larger vehicles push through.

Today's no-signal rule ("first come, first served") does not show this. A vehicle waits at the stop line until every earlier vehicle whose path crosses its own has gone. It may commit only if its whole path through the junction avoids every path already committed (`_first_come_permission`, `_meets_committed_path` in `simulation/traffic_engine.py`). So crossing movements never share the middle, and the junction looks orderly.

## Decisions already made (owner, 2026-11-12)

1. **Only the study junction, only in no-signal runs.** The neighbouring junctions (12 at Site A, 9 at Site B) keep today's first-come rule. Fixed-time, QL, DQL and PPO runs are therefore unchanged, and **no RL model needs retraining**. The cost: the study junction behaves differently from its neighbours in no-signal runs. The documentation states this.
2. **The amount of traffic comes from the existing presets** (low, medium, high) now, and from the team's Field Observer manual counts later. That choice is separate from the behaviour below.
3. **Behaviour values are provisional.** They are taken from published studies and labelled provisional until the team measures them from the video.

## As built (2026-11-13): conservative entry, owner's decision

- **Who counts as crossing.** A vehicle that is not yet inside the junction (still at or before its line) counts as crossing *every* path, from the start of that path. Once inside, only paths its body really touches count. So vehicles inside share the middle and hold short of the real crossing points. A newcomer, though, gives way to every committed vehicle still at its line, and its gap check counts every approaching vehicle.
- **Why.** Counting only the paths a waiting vehicle really touches was tried. It locked the junction in 3 of 12 safety runs: a priority loop (one vehicle already past a shared point led one committed before it), and two bodies wedged together when the loop was broken. The owner chose the conservative rule. It is recorded in each run as `not_inside_crosses_all`.
- **Lock found and fixed.** The first vehicle's footprint check waited on the path of a later vehicle that was holding for it (Site A seed 102). Its footprint check now ignores vehicles holding for it, as the junction gap already did.
- **Speed.** The entry check stops at the first relevant crossing point instead of building whole tables, with byte-identical results. At Site A medium it takes 2.3 ms per step, against 6.3 ms for the first-come rule.
- **Not built:** rule 7 below (the 5 s deadlock guard). Releasing every vehicle inside at once wedged two bodies together. With the conservative rule, no run locked, so it is not needed.

## The new rule ("negotiated" no-signal)

This applies to the study junction only (`tagum_site_a_j`, `tagum_site_b_j`), and only while the run's controller is No signal.

1. **Gap acceptance at the crossing point, not "whole path free".** The engine predicts when a waiting vehicle would reach the area where its path crosses another committed or inside vehicle's path. It also predicts when that vehicle will be in the area. The newcomer may enter if those times are at least its **critical gap** apart. So several crossing movements can be in the middle together, a few seconds apart. Vehicles on the same approach still enter one behind the other, as today.
2. **Rolling entry.** No full stop is required. Vehicles approach at the existing low approach speed (4.0 m/s, `first_come_approach_speed_mps`) and enter while rolling when the gap is acceptable.
3. **Waiting inside the junction.** Once inside, a vehicle gives way at a crossing point to a crossing vehicle that will reach it first. The engine already does this (`_junction_gap`, `_crossing_gap`). This is what makes left-turners wait in the middle.
4. **Critical gap by vehicle type, shrinking with waiting time (impatience).** Values are in the table below.
5. **Right of way.** A vehicle already inside always has priority over one that is still outside. Between two vehicles still waiting, the earlier arrival goes first (today's order), unless only the later one has an acceptable gap.
6. **Limit on vehicles inside.** At most **8** vehicles may be inside the study junction at once (provisional). This keeps a full middle from locking up. The team can check the number by counting vehicles in the middle on paused video frames.
7. **Deadlock guard.** Suppose every vehicle inside has been stopped for **5 s** because each is waiting for another. The vehicle that entered first may then move. The footprint check still stops it short of touching anyone. If a lock still lasts, it is reported by the existing `stalled_vehicles` alarm, never hidden.
8. **Pedestrians.** A waiting pedestrian starts to cross when no vehicle holds the junction (today's rule), or after waiting **20 s** (provisional; people step into gaps in the video). While anyone is crossing, no new vehicle enters (`_crossing_occupied`, unchanged). Vehicles already inside finish their movement.
9. **Never overlapping.** "Chaotic" means crowded and negotiated, never vehicles passing through each other. The existing footprint checks stay as they are.

### Provisional values

| Value | Motorcycle | Car, tricycle | Bus, truck | Basis |
|---|---|---|---|---|
| Critical gap, no wait | 2.0 s | 3.0 s | 3.5 s | Motorcycles 1.25 s [1] and 2.46 s [5], cars 3.21 s [5], at Vietnamese roundabouts. Accepted gaps about 3.1 s and lags about 2.0 s at peak at an unsignalized junction in Indonesia [2]. US stop-control values (4.1–7.1 s [3]) are set aside as too cautious for this site. |
| Shrinks while waiting | 0.1 s per second waited | same | same | The critical gap falls as waiting time rises [4] |
| Lowest it can shrink to | 50 % of the starting gap | same | same | Judgment, provisional |
| Most vehicles inside at once | 8 | | | Judgment; the team can count it on paused video frames |
| Pedestrian patience | 20 s | | | Judgment, provisional |

These live in the engine config next to `first_come_approach_speed_mps`, with bounds (`simulation/scenario_config.py`). Each saved run records them.

## Unchanged

- Fixed-time, QL, DQL and PPO runs: identical to the last bit. Proven by the pinned digest tests (`tests/test_native6_compat.py`, `tests/test_closure_free_digests.py`) plus a new digest check for one fixed-time run at each site.
- Neighbouring junctions in every run, and the study junction in every run with a signal.
- The engine version (`native-14`) and the RL contract, so saved models stay valid.
- Training, evaluation commands and the observation and reward.

## Keeping old and new apart

- Each recording stores `no_signal_behaviour: "negotiated-v1"` and the values above in its experiment record.
- Compare Runs includes this in the pairing key, so a no-signal run made under the old rule never silently pairs as a "repeat" of a new one. None exist today; the database has no no-signal recordings.
- Earlier evaluation files that report a no-signal reference (`data/generated/*-eval.json`) used the old rule. They are history; the new no-signal numbers come from new runs.
- The label changes from "No signal (first come, first served)" to "No signal (negotiated, provisional)" (`src/lib/control-labels.ts`).

## Checks before it is accepted

1. **New tests, written first:**
   - Two vehicles from crossing approaches are inside the junction at the same time.
   - A motorcycle takes a gap (for example 2.5 s) that a car refuses.
   - A long wait shrinks the gap a vehicle accepts.
   - No more than 8 vehicles are ever inside.
   - A pedestrian crosses after 20 s under steady traffic.
   - The deadlock guard frees a four-way wait.
   - Bodies never overlap at any tick.
2. **Unchanged runs:** the digest tests above pass unchanged.
3. **Safety matrix:** Site A and Site B; medium and high traffic; development seeds 101–103; 600 s; no closure, plus one closure case per site. Required in every run:
   - 0 overlaps;
   - 0 stalled vehicles (or each one reported and explained);
   - 0 vehicles lost or created;
   - same seed, same result.
4. **Speed:** at Site B, medium traffic, a step stays under 25 ms for the first 8 minutes, so 4× playback stays smooth.
5. **Look check:** a no-signal recording side by side with the video. Count the vehicles in the middle on several paused frames in each and report both numbers. This is a description, not a calibration.

All results stay labelled "scenario-based, not calibrated or validated". The no-signal model is a hypothesis with provisional values.

## Files expected to change

- `simulation/traffic_engine.py`: entry rule, impatience, limit on vehicles inside, deadlock guard and pedestrian patience, all for the study junction in no-signal mode.
- `simulation/scenario_config.py`: the new values and their bounds.
- The recording manifest and the Compare Runs pairing key (`services/timeline_generator.py`, `backend/main.py`).
- `src/lib/control-labels.ts`.
- New `tests/test_negotiated_no_signal.py`.
- A new decision entry in the architecture document, plus the progress notes.

## Questions for the adviser

1. Is a limit of **8 vehicles** inside the junction reasonable for the video, or should the team count it first?
2. Should the old orderly rule stay available as a second no-signal option ("No signal, orderly")? Recommendation: **no**. One no-signal condition keeps the comparison simple.
3. Are the provisional gap values acceptable until the team measures gaps from the video?

## Sources

1. [Trinh et al., mixed traffic at roundabouts, Journal of Traffic and Transportation Engineering (2021)](https://doaj.org/article/537a25a080be4fbe9565d4bfe3f97fec): two-wheeler critical gap 1.25 s, one case study in Ho Chi Minh City.
2. [Analysis of motorists' movement from drone images, University of Birmingham](https://research.birmingham.ac.uk/en/publications/mitigation-of-traffic-disaster-by-analyzing-motorists-movement-be): Padang, Indonesia; average gap 3.1 s and lag 2.0 s at peak.
3. [PTV Visum: two-way stop nodes (HCM method)](https://cgi.ptvgroup.com/vision-help/VISUM_2023_ENG/Content/1_Benutzermodell%20IV/1_5_Vorfahrtsgeregelte%20Knoten.htm): HCM base critical headways 4.1–7.1 s.
4. [Generalized gap acceptance models for unsignalized intersections (Abhishek, Boon, Mandjes)](https://arxiv.org/pdf/1802.04192): drivers grow impatient, and the critical gap falls with waiting time.
5. [Motorcycle gap acceptance at roundabouts near Hanoi, University of Leeds](https://eprints.whiterose.ac.uk/id/eprint/214941): critical gap 2.46 s for motorcycles and 3.21 s for cars.
