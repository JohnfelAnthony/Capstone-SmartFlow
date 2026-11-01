# Manuscript revision guide: the two-site study (October 31, 2026)

Scope: Chapters 1–2 of the capstone manuscript. This guide lists what the software and study design now say, so the text can be revised to match. It describes software capability and study design only. **No field result, calibration or validation exists yet**, and nothing below may be written as a finding.

## 1. What changed in the study

| Topic | Earlier wording to replace | What is now true |
| --- | --- | --- |
| Study area | A five-junction Tagum network with signals | Two single-junction study sites, each its own network: **Site A** (Capitol Circumferential Road × Dalisay Gante Road) and **Site B** (Davao–Agusan National Highway × Sobrecarey Street / Dao Street). Neither has a traffic signal; drivers proceed first come, first served with no enforcer. The five- and two-junction networks remain as software test networks. |
| Geometry | Hand-drawn study network | OpenStreetMap geometry (ODbL), built into one-junction networks, **unverified in the field**. Site B's split carriageway and median are modelled as one junction under an explicit assumption that must be checked on site. |
| Conditions compared | Fixed-time versus RL | **Three** conditions on matched demand, seeds and settings: today's **no-signal** operation; a **proposed traditional (pre-timed, fixed-time) signal**; and a **proposed RL signal**. |
| What can be validated | Fixed-time baseline against video | Only the **no-signal** condition exists in the field, so only it can be validated against video. The two signals are proposals, evaluated in simulation. |
| Simulator | SUMO / TraCI | The **native SmartFlow engine** (Python/FastAPI, 0.1 s steps, mixed-traffic sub-lane model). SUMO is no longer in the active system. |
| Vehicle classes | Included an emergency class | Car, motorcycle, tricycle, bus and truck, plus pedestrians. **Emergency vehicles are outside the study.** Pedicabs and other classes need an explicit team decision (map to tricycle, exclude and report the count, or request a new class). |
| RL control | One of the five junctions | RL serves **phase groups** of the single site junction through a new observation/action contract (`native-7`). Models trained under earlier contracts are refused, not reused. |

## 2. Definitions to use

- **Unsignalized intersection:** a junction with no traffic signal and no enforcer, where drivers decide whom to let go. In the model, vehicles enter in order of arrival at a short approach zone, subject to a clear exit and a path clear of vehicles already inside. This is a **hypothesis** about the sites, testable against video.
- **Fixed-time (pre-timed, traditional) signal:** a repeating cycle of phases with fixed green, yellow and all-red times, independent of traffic. Here, phases may group approaches that share a green (for example north and south together, then east and west, then pedestrians), and a provisional Webster calculation proposes the greens from approach flows.
- **Validation versus evaluation:** *validation* checks that the no-signal simulation reproduces the reviewed video on measures fixed in advance; *evaluation* compares the three conditions once a site has passed validation.

## 3. Method statements the text may make now

1. The video evidence is collected with a stationary phone camera and organized with a separate offline tool that proposes events and requires manual review; reviewed bins with incomplete coverage are never turned into zero demand.
2. Vehicle demand enters the simulation at its boundary, earlier than its counting-line crossing by an estimated per-class travel time, and the simulation starts from a documented empty state.
3. Validation criteria are written and frozen **before** any held-out outcome is inspected; a second, untouched recording is used for the independent check; a failed or stale validation cannot be overridden.
4. Reinforcement learning is trained and evaluated for a site only after that site's no-signal model passes validation. Final results use protected seeds and at least three independently trained models per algorithm per site, with the spread reported.
5. Waiting time alone does not establish that one condition is better: completion, queues, pedestrian delay and unfinished demand are reported together.

## 4. Statements the text must not make

- That the sites are validated, that the first-come hypothesis holds, or that any signal or RL result applies to the real intersections.
- That the OpenStreetMap geometry, class mapping, approach speeds, passenger-car equivalents, saturation flows or any threshold is measured; they are provisional placeholders until sourced.
- That RL controls a coordinated network. It controls one junction.
- That synthetic software tests are study evidence.

## 5. Evidence to cite once it exists

The team's reviewed observations, the frozen criteria file and its commit, the study ledger, the immutable validation reports (`docs/reports/site-validation-*.json`), and the final results report. Until then, cite the design (`docs/superpowers/plans/2026-10-31-two-site-study.md`) and decision D30 in the architecture document for what the software does.
