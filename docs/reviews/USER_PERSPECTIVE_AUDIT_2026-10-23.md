# SmartFlow user-perspective audit and recommended next work

Date: **October 23, 2026 (Asia/Singapore)**.

Scope: the independent SmartFlow repository. This audit considers the needs of capstone researchers and traffic reviewers, based on source inspection, project documentation, and targeted tests. It does not include a fresh browser usability session, full application acceptance, or field validation. Recommendations below are proposed work, not implemented changes or adviser-approved study requirements.

Navigation: [README](../../README.md) · [Current progress](../PROGRESS_AND_HANDOFF.md) · [Project overview](../PROJECT_OVERVIEW.md) · [Field integration plan](../FIELD_DATA_SMARTFLOW_INTEGRATION.md)

## Main recommendation

The next milestone should be a complete, defensible research experiment:

**Reviewed field data → credible baseline → fair controller comparison → understandable report.**

SmartFlow already has much of the software needed, but users still have to connect those steps manually. From a researcher's or traffic reviewer's perspective, the central question is:

> What change should we consider at this intersection, and what evidence supports it?

The system should make that answer traceable. Scenario editing, replay, registered-model selection, permissions, backups, and calibration records already provide useful foundations. New work should extend those workflows.

## 1. Concrete issues to address first

### 1.1 Controller ranking can imply a broader improvement than it establishes

The [ranking implementation](../../services/rl_reporting_service.py) sorts primarily by average waiting time; throughput only breaks ties. Unfinished demand and pedestrian delay do not affect the rank. The primary evaluation score is negative mean vehicle waiting time.

A direct call to `build_combined_ranking` with deliberately constructed inputs produced this result:

| Controller | Average wait | Completed trips | Unfinished vehicles | Pedestrian delay | Assigned rank |
| --- | ---: | ---: | ---: | ---: | ---: |
| Fixed-time | 20 s | 90 | 10 | 10 s | 2 |
| PPO | 19 s | 10 | 90 | 100 s | 1 |

Both inputs declared 100 requested vehicles and zero dropped vehicles. This is a **function-level demonstration using fabricated summary values, not an actual PPO experiment**. It shows that `traffic_performance_rank` currently represents a narrower criterion than its name may suggest. The evaluator does retain other metrics in its summary; the problem is their absence from the ranking decision.

Recommended action:

- Label the current ordering explicitly as a waiting-time ranking.
- Show throughput, unfinished demand, pedestrian service, and other relevant tradeoffs alongside it.
- Agree acceptance criteria for those outcomes before presenting an overall recommendation.
- Avoid replacing the current rule with an arbitrary weighted score.

Acceptance: a controller with a lower mean wait but materially worse completion or pedestrian outcomes must not be presented as an unqualified overall improvement. Any ranking must state its criterion and limitations.

### 1.2 In-app help does not consistently describe the implemented metrics

The [Help page](../../src/components/help-about-page.tsx) describes waiting time as delay before crossing an intersection and average queue length as a cycle-based measure. The [engine](../../simulation/traffic_engine.py), particularly `_refresh_metrics`, calculates different populations and aggregations:

- Average vehicle wait uses accumulated stopped time for completed and active admitted vehicles, divided by their count. Pending arrivals are excluded; boundary waiting is tracked separately.
- Average queue is a time average per incoming signal lane, rather than a controlled-junction cycle average.
- Help lists an emissions estimate, but source inspection and a short engine run found no corresponding calculation in the active engine.

Recommended action: align Help, dashboard labels, and exports with one metric definition source. Include units, measurement window, included population, and exclusions. Remove or clearly mark unsupported metrics.

Acceptance: each displayed metric can be traced to its actual calculation and uses consistent definitions across Help, live views, saved results, and exported reports. Emissions must not be presented as an available result without an implemented and documented model.

## 2. What intended users would want

| Priority | User expectation | Current position | Next useful functionality |
| --- | --- | --- | --- |
| Essential | Show me exactly what location and conditions this experiment represents. | A provisional network and scenario configuration exist. | A study summary showing named junctions, observed lanes/turns/signals, collection periods, verified details, and remaining assumptions. |
| Essential | Let me use reviewed observations without silently changing their meaning. | CSV import and Field Observer exist separately. | A reproducible conversion process with approach mapping, count reconciliation, source identity, and clear measured/estimated/missing labels. |
| Essential | Demonstrate that the baseline resembles this site. | Calibration records exist; structural fidelity remains unresolved. | Observed-versus-simulated plots at matching locations and times, plus discharge, queue, and signal-service checks. |
| High | Guide me through a valid experiment. | Scenario, calibration, training, and comparison pages are separate. | A study checklist linking each stage to its evidence and next action, while keeping synthetic demonstration runs available. |
| High | Compare controllers fairly across repeated runs. | Multi-seed evaluation exists in Python; the comparison page focuses on pairs of recordings. | An experiment workspace selecting scenarios, registered models, repetitions, and measurement settings, with per-run results and uncertainty summaries. |
| High | Explain who benefits and who becomes worse off. | Aggregate KPIs and local telemetry exist. | Results by junction/approach, pedestrian outcomes, unfinished demand, and separate signal-control versus routing comparisons. |
| High | Give me a report I can defend. | CSV/JSON exports and provenance exist. | A readable study report containing the question, inputs, baseline-fit evidence, comparison charts, limitations, and reproducibility references. |

The [research workspace documentation](../RESEARCH_WORKSPACE.md) explicitly distinguishes stored numerical-fit records from authenticated field evidence. It also identifies manual local-metric extraction and the absence of automatic Field Observer integration. These are workflow gaps to resolve progressively, not evidence that the existing research workspace is absent.

## 3. Biggest research dependency: baseline fidelity

The current engine permits one vehicle at a time through a junction and uses a single green-duration setting within each junction's signal plan. These are substantial simplifications if the chosen site has simultaneous compatible movements, unequal phase durations, multiple lanes, or important motorcycle interactions.

Relevant source: the `Signal` class and `_move_vehicle` in [traffic_engine.py](../../simulation/traffic_engine.py).

First record one representative pilot period and compare the actual service pattern with these assumptions. Implement the geometry, movement, timing, and capacity changes that the selected site requires. A mismatch cannot be resolved merely by adjusting demand until queues look plausible.

This follows the existing [field integration plan](../FIELD_DATA_SMARTFLOW_INTEGRATION.md). FHWA likewise treats calibration against observed conditions as necessary before using a microsimulation model to assess alternatives: [FHWA model calibration guidance](https://ops.fhwa.dot.gov/publications/fhwahop18036/chapter5.htm).

The pilot should establish:

- The study boundary and selected junctions.
- Observed lanes, permitted movements, crossings, and signal operation.
- Where and when each input and outcome is measured.
- Which inputs are observed, inferred, or unavailable.
- Which engine simplifications materially affect the intended conclusions.
- The required model changes or an explicitly agreed narrower study claim.

Selected-junction RL is the current implementation scope. Confirm the academic requirement before extending control to additional junctions or coordinated network control.

## 4. Recommended delivery order

### Step 1 — Correct interpretation immediately

Fix metric descriptions, unsupported emissions wording, and ranking labels/criteria.

Deliverable: consistent metric definitions and clearly qualified comparisons. The ranking reproduction above should become a regression case when the ranking behavior is changed.

### Step 2 — Freeze one pilot study definition

Identify the site, observed movements, signal operation, measurements, and required outcomes. Confirm selected-junction versus broader RL requirements with the adviser.

Deliverable: a recorded study definition, observation-coverage assessment, and site-specific model-gap list. Avoid developing a general-purpose observation platform before the pilot establishes what is necessary.

### Step 3 — Complete one reviewed-data-to-baseline workflow

Preserve original evidence, document conversion assumptions, reconcile counts, address required model gaps, then calibrate and independently validate.

Deliverable: a reproducible baseline with traceable input transformations and matching field/simulation measurement definitions. A deterministic conversion script and versioned mapping record are an appropriate first step where the existing CSV semantics fit; a full bundle-import UI can follow later.

### Step 4 — Expose repeatable experiments in the UI

Reuse the [evaluation runner](../../tools/evaluate_controllers.py). Add experiment grouping, matched-input checks, results across repetitions, and transparent tradeoffs. Keep signal-control comparisons separate from routing comparisons so changes remain interpretable.

Separate evaluation and multiple runs are also recommended by [Stable-Baselines3](https://stable-baselines3.readthedocs.io/en/master/guide/rl_tips.html). More random seeds do not create independent field observations; preserve collection-period and source lineage separately.

Deliverable: a researcher can configure and review repeated baseline/alternative evaluations without manually assembling unrelated run records. Reports retain every repetition and explain uncertainty using the agreed analysis plan.

### Step 5 — Produce a reviewer-facing report and rehearse the workflow

Create a readable report with the research question, source periods, scenario assumptions, baseline-fit evidence, alternative results, tradeoffs, limitations, and reproducibility references.

Deliverable: a teammate can reproduce an experiment from retained inputs and explain every reported metric without developer assistance.

## 5. User acceptance exercise

Ask a new researcher to perform these tasks using the application:

1. Create or select a scenario and identify the represented study site.
2. Explain which inputs are observed, estimated, or synthetic.
3. Locate the evidence supporting the fixed-time baseline.
4. Run the baseline and one alternative under matched conditions.
5. Explain the results, including outcomes that worsened and unfinished demand.
6. Export the evidence and identify what another researcher needs to reproduce it.

Record where the researcher needs help, encounters unclear terms, or cannot find the next action. Those observations should drive subsequent UI changes. This exercise is proposed; it was not performed during this audit.

## 6. Work to defer

Defer additional algorithms, citywide expansion, automatic signal placement, and further decorative visualization until the first research workflow is accepted. Revisit these only when they support the agreed study scope or a demonstrated user need.

## 7. Fresh verification and limits

The audit ran the following checks on October 23, 2026:

| Check | Result | Scope |
| --- | --- | --- |
| `npm.cmd run test:visualization` | 101 tests passed in eight suites. | Frontend visualization unit tests; not browser usability acceptance. |
| `.venv/Scripts/python.exe -m unittest discover -s tests -p test_native_traffic_contract.py -v` | 12 tests passed. | Synthetic traffic contracts, including movement, clearance, routing, and repeatability. |
| `.venv/Scripts/python.exe -m unittest discover -s tests -p test_research_workspace.py -v` | Eight tests passed. | Research records, validation rules, permissions, exports, and retained snapshots using isolated test storage. |
| Direct `build_combined_ranking` reproduction | Returned PPO rank 1 for the fabricated example in section 1.1. | Confirms the ranking rule's limitation; does not measure any trained controller. |
| Short native-engine metric inspection | No metric key containing `emission` or `co2`; source search found the Help claim without an active calculation. | Supports correcting the advertised metric; not a general environmental-model review. |

The initial frontend test attempt failed to load temporary Vite module-cache files in the sandbox. A rerun outside the sandbox passed all 101 tests. The initial failure is not evidence of a reproduced application defect.

These checks support the inspected software paths. They do not establish field validity, a complete backend-suite result, a fresh build, full browser acceptance, production readiness, or controller effectiveness.

No source or documentation files were changed during the audit. This Markdown record was subsequently created at the user's request. Existing modifications and untracked reports were preserved. The maintained [progress document](../PROGRESS_AND_HANDOFF.md) remains the current status pointer; this file records the dated audit and proposed priorities.
