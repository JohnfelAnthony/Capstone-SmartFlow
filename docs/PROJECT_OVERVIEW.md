# Project purpose and scope

> **Scope update — October 24, 2026:** Emergency vehicles, emergency priority, emergency metrics and emergency RL features are excluded from SmartFlow by the owner’s decision. Any earlier descriptions below are historical and do not define current functionality. Current simulation classes are car, motorcycle, tricycle, bus and truck. Original manuscripts and research artifacts are preserved. See the October 24 scope decision in the architecture document.


Reviewed: **2026-10-23** (Asia/Singapore). Applies to the React/Python application inside `SmartFlow`; application verification remains dated separately in progress.

Navigation: [Start here](../README.md) · [Architecture and plan](ARCHITECTURE_AND_PLAN.md) · [Progress and handoff](PROGRESS_AND_HANDOFF.md)

For current status and dated evidence, see [Progress and handoff](PROGRESS_AND_HANDOFF.md). [IMPLEMENTATION_HANDOFF.md](../IMPLEMENTATION_HANDOFF.md) preserves the resolved September 23 interruption and original scope; section 11 provides the maintained source-reading map. This overview explains purpose and research scope; earlier verification mentions below describe their own checkpoints.

**Planning context:** the owner reported approximately 35 days remaining in the September 22 discussion, giving a provisional deadline around October 27, 2026. This is the original planning anchor, not a new countdown or a confirmed submission date. The exact date and whether RL must control one junction, every junction independently, or coordinate the network remain unconfirmed in the repository. The current single-junction environment is an implementation fact, not proof of academic acceptance. The [technical-lead review](ARCHITECTURE_AND_PLAN.md) retains the original schedule and decision gates as history.

**Current software and research distinction:** scenario editing, live runs, RL jobs, replay/reporting, research comparisons and interactive 2D views are implemented with dated synthetic verification. The offline [Field Observer](../tools/field_observer/README.md) provides provisional proposals and reviewed exports; [Calibration & Validation](RESEARCH_WORKSPACE.md) stores baseline-fit and independent-validation records. Neither tool establishes audited field accuracy or a validated baseline. Final site mapping, field audit/conversion, model fidelity and final comparative results remain research work.

**November 1 scope decision:** the delivered application uses Canvas 2D only. Historical 3D descriptions below record earlier milestones. Removing a presentation mode does not change simulation, calibration or validation requirements.

## Purpose

SmartFlow is a capstone project for studying traffic signal optimization and adaptive routing in Tagum City through simulation. Its purpose is to let researchers configure a connected road network, represent traffic conditions, run controlled experiments, and compare results before recommending changes.

The revised Chapters 1 and 2 reviewed earlier use the title **“SMARTFLOW: A Simulation-Based Approach to Traffic Signal Optimization and Adaptive Routing Using Reinforcement Learning.”** The project owner has since directed the implementation away from SUMO. The owner also permits routing to use a separate algorithm rather than requiring reinforcement learning to choose every route.

The intended contribution is a reproducible traffic experimentation and decision-support system with an understandable visual display. A moving 3D scene alone does not establish valid traffic behavior or an effective controller. The engine, input data, comparison method and documented assumptions are central to the capstone.

## Research basis and dates

The review covered the original `SMARTFLOW_CHAP1_AND 2.docx.pdf` and revised `FINAL_SIGURO_CHAPTER1_AND_2.docx.pdf`. Exact copies now live in `docs/research_sources/` so they remain available after relocating SmartFlow. The [project history and chapter archive](../PROJECT_HISTORY_AND_MIGRATION.md) includes the comparison, dates, source hashes and complete extracted text of both manuscripts. Their parent-folder originals remain unchanged. The revised manuscript is the research basis where it differs from the original. Later explicit project decisions govern the software direction and need to be reflected in the eventual manuscript revision.

The manuscript cover date, filesystem modification date, OSM retrieval date, experiment date and documentation review date describe different events. They must not be treated as interchangeable evidence of freshness. This set records the documentation review date and the map retrieval timestamp; new field observations and experimental results must record their own collection/run dates.

The requirements below summarize the chapters and discussions already reviewed. They are a working requirements map, not a claim that every panel recommendation has been independently implemented or that the manuscript has already been updated for the new engine.

## Intended users and workflows

| User or stakeholder | Need |
| --- | --- |
| Capstone researchers | Configure inputs, test assumptions, train controllers and reproduce experiments. |
| Traffic/planning reviewers | Inspect signal and route behavior, compare scenarios and understand limitations. |
| Panel members and evaluators | Trace objectives to implementation and distinguish measured evidence from assumptions. |
| Application administrators | Manage accounts, permissions, audit records and backups. |

These are product audiences. The current account/permission system is separate; this table does not assert that every audience has a dedicated implemented role.

The intended experiment workflow is:

1. Choose and verify a small connected Tagum road network.
2. Supply observed or explicitly synthetic traffic demand, pedestrian demand, vehicle mix and signal plans.
3. Define an ordinary period, peak period, holiday/event assumption or a timed road disruption.
4. Run a fixed-time baseline and candidate RL signal controllers under matched inputs.
5. Observe traffic and inspect queues, delays, routes, signal phases and completion counts.
6. Save or replay the run, compare metrics and export evidence for the study.
7. Explain assumptions, incomplete trips, uncertainty and practical limits alongside the result.

## Requirements carried forward from the chapters

| Requirement | Software interpretation | Evidence still needed for the study |
| --- | --- | --- |
| Tagum road maps and geographic information | Import/cache map geometry and use connected roads and intersections. | Verify the selected roads, allowed turns, widths, lane counts and actual signal locations. |
| Actual traffic data | Accept time-dependent demand and boundary-to-boundary trips with provenance. | Collect or obtain dated vehicle counts, turning movements and pedestrian observations. |
| Configurable traffic and signals | Adjust demand, vehicle mix, signal phases/timing and modeled control at a junction. | Define realistic parameter ranges and explain the selected plans. |
| Road closures, changes and rerouting | Model entry closures, speed restrictions, alternate routes and supplied network variants. | Validate detour connectivity and relate each scenario to a real or clearly hypothetical situation. |
| Event-based scenarios | Represent peak/ordinary windows, temporary events and disruption/recovery periods. | Provide defensible event timings and demand multipliers or observed counts. |
| RL signal optimization | Train/evaluate Q-learning, DQL and PPO signal policies against a fixed-time baseline. | Demonstrate performance with held-out scenarios/seeds; successful training execution is insufficient. |
| Signal arrangement recommendations | Compare explicitly configured signalized and unsignalized alternatives. | Evaluate candidate arrangements; no automatic optimal signal-placement result is established. |
| Metrics and reporting | Record waiting, queues, throughput, travel time, pedestrian delay, speed/density and unfinished demand. | Check definitions, measurement windows and report consistency. |

The native engine supports five vehicle categories: car, motorcycle, tricycle, bus and truck. Emergency-vehicle demand, priority, outcomes and RL features were removed by the owner on October 24, 2026. Ordinary vehicle behavior and parameters still need evaluation before being presented as calibrated Tagum behavior.

## Decisions already made

| Decision | Consequence |
| --- | --- |
| Replace SUMO with a custom Python traffic engine. | Live simulation, recordings and training should use the same native engine; do not reintroduce TraCI into the active path. |
| Use the React web application as the primary interface. | Keep the browser responsible for interaction and rendering; run traffic logic on Python. A separate desktop application is not the current implementation direction. |
| Obtain road geometry from available map data, initially OpenStreetMap. | Automate import and retain bends/connectivity/source metadata; avoid manually drawing the whole study network. |
| Begin with roughly four to six connected junctions. | The current supplied study network has five junctions. Larger coverage follows demonstrated correctness and measured performance. |
| Begin with a minimal 3D scene, then add faithful presentation. | The October 10–12 implementation supplies shared native 2D/3D geometry, five vehicle appearances, inspection, follow and analytical overlays. Illustrative context supplies no field evidence; traffic remains authoritative in Python. |
| Separate adaptive routing from RL signal control. | A travel-time graph algorithm handles routes; RL chooses safe signal service requests. |
| Prioritize traffic correctness and reproducible experiments. | Keep presentation separate from traffic behavior; subsequent visual work does not settle baseline fidelity, calibration or research conclusions. |
| Consolidate documentation, then resume the Python engine at the owner's request. | The September 23 `native-3` checkpoint passed 40 Python tests; research and application release gates remain. |
| Preserve both codebases' history and both manuscripts before relocating SmartFlow. | Keep the self-contained chapter/history archive and source PDFs inside SmartFlow; preserve uncommitted work and ignored research artifacts separately. |

## Meaning of “dynamic” in this project

The intended network consists of connected road segments rather than isolated intersection animations. Vehicles travel across several intersections, respond to signals and queues, and may change route when conditions change. The display follows the engine's actual state.

The current map pipeline derives a bounded cached network. A browser feature that selects any city area and automatically produces a calibrated traffic model is **not complete**. Map import supplies geometry; it does not supply observed congestion, traffic counts or validated signal plans.

## Current research boundaries

- The initial study is a small connected network, not a complete Tagum city model.
- The present lane model uses one modeled lane per permitted direction. Mixed vehicle lengths/speeds do not imply lane changing, overtaking or motorcycle filtering.
- Junction occupancy is approach-scoped (since October 25, 2026): only vehicles from the approach with green share a junction, and turns are slower than through movements. Synthetic discharge is about 1,480 veh/h/lane straight through; field calibration of discharge headways is still required and must be stated in comparisons.
- Simulated pedestrians and ordinary vehicles follow traffic logic; the primary RL agent is the signal controller.
- The current RL environment controls one selected junction. It does not establish coordinated multi-agent optimization across all five junctions.
- Signal placement and timing in the supplied network are experimental assumptions. All-way-stop comparison is one modeled alternative, not a comprehensive model of local unsignalized driving behavior. Since the two-site study (October 31, 2026) the engine also models an unsignalized junction where vehicles enter by arrival order (`first_come`, run control `no-signal`). That is a hypothesis about the two study sites, to be tested against reviewed video by the validation gate, not an established description of local driving.
- There is no current requirement for live CCTV/GPS/IoT ingestion or physical traffic-signal actuation.
- A hosting direction has been chosen, but no provider, budget, public release or concurrent-user deployment has been verified.

## What completion must mean

Software completion requires consistent scenario configuration, safe and repeatable engine behavior, real policy inference when a run is labeled RL, persistent experiment provenance, trustworthy metrics, usable visualization and verified save/replay/compare/report workflows.

Capstone validation additionally requires field data, calibrated assumptions, fair baseline comparisons, held-out evaluation, documented limitations and manuscript alignment. These are separate from passing software tests. The project must not claim a real-world traffic improvement percentage or optimal signal arrangement until experiments actually support it.

## Inputs still needed from the research team

Record the final study boundary and junction selection; dated road/signal observations; vehicle and pedestrian counts by time and direction; turning proportions or OD estimates; and observed queue/travel-time samples. Record the source, collection method, units and any missing values.

The team also needs to settle the final evaluation protocol with its adviser/panel: baseline plans, training versus held-out periods/seeds, scenario durations, warmup, number of repetitions and report format. These research inputs are not blockers to documenting or validating basic engine behavior, but they are prerequisites for credible final conclusions.
