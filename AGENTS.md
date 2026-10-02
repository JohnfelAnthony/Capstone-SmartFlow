# SmartFlow agent entry point

This folder is the independent SmartFlow repository. Work from this root, even if it is still nested inside `trapik2`. The parent Dash/SUMO application is historical context and is not needed for ordinary implementation here.

## Read progressively

1. [README.md](README.md): startup, repository orientation and documentation index.
2. [IMPLEMENTATION_HANDOFF.md](IMPLEMENTATION_HANDOFF.md), sections **1–4**: latest captured implementation state, approved six-area scope, unfinished edits and first repairs. Section **11** maps tasks to the exact code paths to read.
3. [Project overview](docs/PROJECT_OVERVIEW.md): capstone purpose, revised-chapter requirements and research limits.
4. Read the relevant source, API types and tests for the requested task. Follow its callers and consumers; do not read the entire repository indiscriminately.

Consult handoff sections 5–9 for the 31-task backlog, contracts, delivery slices and verification. Consult [architecture](docs/ARCHITECTURE_AND_PLAN.md) for design rationale and [progress](docs/PROGRESS_AND_HANDOFF.md) for dated evidence. The [history archive](PROJECT_HISTORY_AND_MIGRATION.md) sections 1–9 explain both codebases and manuscript changes; its long appendices and PDFs are reference material to read only when the task requires their exact wording or figures.

The latest source and fresh verification establish current software behavior. Older “40 tests passed” records describe an earlier checkpoint, not the interrupted worktree. Do not assume `dist/`, running servers or model files match current source. Recheck the handoff's known failures after changing relevant code.

## Architecture boundaries

- React/TypeScript/Vite and Three.js provide interaction and rendering. Python/FastAPI owns simulation and learning.
- The active engine is `simulation/traffic_engine.py`; do not substitute similarly named legacy engines or reconnect SUMO/TraCI.
- `engine_config` is the native scenario contract. Preserve complete saved settings through editing, running, training and evaluation.
- RL currently controls one selected junction; routing is separate. Final study intersections and field calibration are not established. Label synthetic evidence honestly.
- This application currently uses process-local live/training runtimes. Do not assume multiple API workers share that state.

## Work and verification conventions

- Inspect `git status --short` and preserve existing modifications, untracked files and ignored research artifacts. Do not reset unrelated work.
- Use descriptive names, existing patterns and named booleans for complex conditions.
- Reuse existing UI components. The project-local shadcn instructions are at `.agents/skills/shadcn/SKILL.md` when applicable.
- Use [package.json](package.json) for commands and `.venv/Scripts/python.exe` on this Windows workspace. Use isolated databases/artifact directories for integration and subprocess tests.
- Follow handoff section 8 for targeted checks, full acceptance and browser verification. Passing syntax/build checks alone does not prove traffic, training or research correctness.
- Update current status/evidence after verified implementation. Keep original manuscript copies unchanged and put durable architecture decisions in the architecture document.
