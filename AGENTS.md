# SmartFlow agent entry point

This folder is the independent SmartFlow repository. Work from this root, even if it is still nested inside `trapik2`. The parent Dash/SUMO application is historical context and is not needed for ordinary implementation here.

## Read progressively

1. [README.md](README.md): startup, repository orientation and documentation index.
2. [Progress and handoff](docs/PROGRESS_AND_HANDOFF.md): current status pointer and dated verification. [IMPLEMENTATION_HANDOFF.md](IMPLEMENTATION_HANDOFF.md), sections **1–4**, preserve the September 23 scope and interruption; those repairs were subsequently completed. Section **11** is the maintained source-reading map.
3. [Project overview](docs/PROJECT_OVERVIEW.md): capstone purpose, revised-chapter requirements and research limits.
4. Read the relevant source, API types and tests for the requested task. Follow its callers and consumers; do not read the entire repository indiscriminately.

Consult handoff sections 5–9 for the historical 31-task backlog, contracts and acceptance criteria; reconcile each task with subsequent progress before treating it as unfinished. Consult [architecture](docs/ARCHITECTURE_AND_PLAN.md) for current boundaries and dated design decisions. The [history archive](PROJECT_HISTORY_AND_MIGRATION.md) sections 1–9 explain both codebases and manuscript changes; its long appendices and PDFs are reference material to read only when the task requires their exact wording or figures.

The latest source and fresh verification establish current software behavior. Older test results and the September interruption describe their own checkpoints. Do not assume `dist/`, running servers or model files match current source. Reproduce a suspected failure before treating an old repair item as a current defect.

## Architecture boundaries

- React/TypeScript/Vite and Canvas 2D provide interaction and rendering. Python/FastAPI owns simulation and learning.
- The active engine is `simulation/traffic_engine.py`; do not substitute similarly named legacy engines or reconnect SUMO/TraCI.
- `engine_config` is the native scenario contract. Preserve complete saved settings through editing, running, training and evaluation.
- RL currently controls one selected junction; routing is separate. The two study sites (`tagum_site_a`, `tagum_site_b`) are provisional OpenStreetMap networks and neither has a signal; the no-signal (`first_come`) model is a hypothesis until a site passes the independent validation gate (`services/study_gate.py`, `services/site_validation.py`). Study-site training and final evaluation need that gate; `--synthetic-smoke-test` is for code checks only. Field calibration is not established. Label synthetic evidence honestly.
- Supported simulation classes are car, motorcycle, tricycle, bus and truck, plus separate pedestrian support. The retired emergency feature must not be restored through legacy settings; models require the current contract: engine `native-7`, observation `native-local-20-v4`, actions `phase-service-5-v2` and the model's recorded `phase_plan`. `native-6` / `native-local-22-v3` models and recordings are history: refuse them, do not relabel them. Signalized and all-way-stop traffic is unchanged from `native-6` (pinned in `tests/test_native6_compat.py`).
- This application currently uses process-local live/training runtimes. Do not assume multiple API workers share that state.

## Work and verification conventions

- Inspect `git status --short` and preserve existing modifications, untracked files and ignored research artifacts. Do not reset unrelated work.
- Use descriptive names, existing patterns and named booleans for complex conditions.
- Reuse existing UI components. The project-local shadcn instructions are at `.agents/skills/shadcn/SKILL.md` when applicable.
- Use [package.json](package.json) for commands and `.venv/Scripts/python.exe` on this Windows workspace. Use isolated databases/artifact directories for integration and subprocess tests.
- Follow handoff section 8 for targeted checks, full acceptance and browser verification. Passing syntax/build checks alone does not prove traffic, training or research correctness.
- Update current status/evidence after verified implementation. Keep original manuscript copies unchanged and put durable architecture decisions in the architecture document.
