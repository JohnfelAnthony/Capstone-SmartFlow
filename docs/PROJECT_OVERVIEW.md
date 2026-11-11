# Project purpose and scope

> **Scope update — October 24, 2026:** Emergency vehicles, emergency priority, emergency metrics and emergency RL features are excluded from SmartFlow by the owner’s decision. Any earlier descriptions below are historical and do not define current functionality. Current simulation classes are car, motorcycle, tricycle, bus and truck. Original manuscripts and research artifacts are preserved. See the October 24 scope decision in the architecture document.


Reviewed **2026-11-10** (Asia/Singapore). Applies to the React and Python application inside SmartFlow.

Navigation: [Start here](../README.md) · [Architecture and plan](ARCHITECTURE_AND_PLAN.md) · [Progress and handoff](PROGRESS_AND_HANDOFF.md)

For current status and dated evidence, see [Progress and handoff](PROGRESS_AND_HANDOFF.md). [IMPLEMENTATION_HANDOFF.md](../IMPLEMENTATION_HANDOFF.md) preserves the resolved September 23 interruption and original scope; section 11 provides the maintained source-reading map. This overview explains purpose and research scope; earlier verification mentions below describe their own checkpoints.

**Planning context:** the owner reported approximately 35 days remaining in the September 22 discussion, giving a provisional deadline around October 27, 2026. This is the original planning anchor, not a new countdown or a confirmed submission date. The exact date and whether RL must control one junction, every junction independently, or coordinate the network remain unconfirmed in the repository. The current single-junction environment is an implementation fact, not proof of academic acceptance. The [technical-lead review](ARCHITECTURE_AND_PLAN.md) retains the original schedule and decision gates as history.

**Current scope.** SmartFlow supports scenario editing, live runs, selected-junction RL, replay, reports and comparisons using Canvas 2D. The two provisional Tagum study networks are Site A and Site B. Reviewed Field Observer exports supply vehicle counts and turns for scenario demand. The study uses one 16-minute midday recording per site and follows D38's scenario-based scope without calibration or independent validation. [Research method](RESEARCH_METHOD.md) · [Counts import](RESEARCH_WORKSPACE.md#counts-from-field-observer)

**November 1 scope decision.** The delivered interface uses Canvas 2D. Earlier 3D milestones are documented in the progress log.

## Purpose

SmartFlow is a capstone project for studying traffic signal optimization and adaptive routing in Tagum City through simulation. Its purpose is to let researchers configure a connected road network, represent traffic conditions, run controlled experiments, and compare results before recommending changes.

The revised Chapters 1 and 2 reviewed earlier use the title **“SMARTFLOW: A Simulation-Based Approach to Traffic Signal Optimization and Adaptive Routing Using Reinforcement Learning.”** The project owner has since directed the implementation away from SUMO. The owner also permits routing to use a separate algorithm rather than requiring reinforcement learning to choose every route.

The intended contribution is a reproducible way to compare traffic scenarios. The engine, demand inputs, comparison method and stated assumptions determine how to interpret the results.

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
| Use one React interface for browser and desktop operation. | React handles interaction and Canvas 2D rendering. FastAPI and Python own simulation. A Windows development installer is maintained on the desktop branch. |
| Obtain road geometry from available map data, initially OpenStreetMap. | Automate import and retain bends/connectivity/source metadata; avoid manually drawing the whole study network. |
| Use two separate study networks. | Site A has 13 modeled junctions and Site B has 10. Each has one study junction where proposed signal controllers can be tested. |
| Use Canvas 2D for the simulation. | The map displays authoritative engine frames for live runs and replay. Buildings and other scene decorations provide visual context. |
| Separate adaptive routing from RL signal control. | A travel-time graph algorithm handles routes; RL chooses safe signal service requests. |
| Prioritize traffic correctness and reproducible experiments. | Freeze experiment inputs and preserve the evidence for each comparison. |
| Consolidate documentation, then resume the Python engine at the owner's request. | The September 23 `native-3` checkpoint passed 40 Python tests; research and application release gates remain. |
| Preserve both codebases' history and both manuscripts before relocating SmartFlow. | Keep the self-contained chapter/history archive and source PDFs inside SmartFlow; preserve uncommitted work and ignored research artifacts separately. |

## Meaning of “dynamic” in this project

The intended network consists of connected road segments rather than isolated intersection animations. Vehicles travel across several intersections, respond to signals and queues, and may change route when conditions change. The display follows the engine's actual state.

The current map pipeline derives a bounded cached network. A browser feature that selects any city area and automatically produces a calibrated traffic model is **not complete**. Map import supplies geometry; it does not supply observed congestion, traffic counts or validated signal plans.

## Current research boundaries

- The initial study is a small connected network, not a complete Tagum city model.
- The mixed-traffic engine models side-by-side movement and motorcycle filtering within the road geometry. Vehicle mix and behavior parameters are provisional.
- Junction behavior depends on the configured control mode and movement conflicts. The fixed-time and RL plans are proposed controls for the comparison.
- Simulated pedestrians and ordinary vehicles follow traffic logic; the primary RL agent is the signal controller.
- QL, DQL and PPO control one selected junction per run. Other junctions follow their configured rules.
- Model the unsignalized condition with first-come rules, then compare it with proposed fixed-time and RL control. First-come behavior and signal timing are scenario assumptions.
- There is no current requirement for live CCTV/GPS/IoT ingestion or physical traffic-signal actuation.
- A hosting direction has been chosen, but no provider, budget, public release or concurrent-user deployment has been verified.

## What completion must mean

Software completion requires consistent scenario configuration, safe and repeatable engine behavior, real policy inference when a run is labeled RL, persistent experiment provenance, trustworthy metrics, usable visualization and verified save/replay/compare/report workflows.

Capstone evidence requires traceable demand inputs, matched comparisons, held-out evaluation, documented limitations and manuscript alignment. Report outcomes for the simulated conditions. The study does not establish field performance or an optimal real-world signal arrangement.

## Inputs still needed from the research team

Confirm the modeled boundaries and legal movements. Preserve each recording, its collection period, coverage, reviewed counts and turns, and any gaps in the source evidence.

The team also needs to settle the final evaluation protocol with its adviser/panel: baseline plans, training versus held-out periods/seeds, scenario durations, warmup, number of repetitions and report format. These research inputs are not blockers to documenting or validating basic engine behavior, but they are prerequisites for credible final conclusions.
