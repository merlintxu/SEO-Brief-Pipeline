# Rearchitecture Execution Plan

This document converts the redesign into an executable backlog for maintainers and agents.

## Scope

- Rework the pipeline by stages with typed contracts and quality gates.
- Improve provider resilience, prompt quality, persistence, and operations.
- Add an operator frontend for run lifecycle and diagnostics.
- Redesign the operator UX/UI so setup, configuration, execution and review work as one product flow.
- Keep current public flow (`POST /briefing`, `GET /briefing/{run_id}`, `/outputs/...`) backward compatible during migration.

## Delivery Rules

1. Medium PRs only.
2. Each PR must include:
   - tests,
   - docs updates (`AGENTS.md` + at least one `docs/*` file),
   - explicit rollout notes.
3. No real credentials or secrets in docs, logs, tests, fixtures.
4. API compatibility is required unless explicitly versioned.

## Epic A - Stage Contracts And Quality Gates

### Goal
Make every pipeline stage explicit, typed, and measurable.

### PR A1 - Stage I/O contracts

- Add typed models for stage boundaries in `seo_pipeline/models.py`:
  - `PipelineInput`,
  - `KeywordSet`,
  - `CompetitorSet`,
  - `EnrichmentSet`,
  - `BriefingPlan`.
- Wire `run_full_pipeline()` to move typed payloads, not ad hoc dicts.

Acceptance:

- No untyped stage handoff for core path.
- Unit tests for model validation and coercion.

### PR A2 - Quality gate engine

- Add `seo_pipeline/quality_gates.py` with stage gate rules:
  - required fields,
  - minimum SERP and competitor coverage,
  - fail/continue policy.
- Persist gate results in `run_metrics.json`.

Acceptance:

- Failed gates mark run as failed with explicit `error_category=validation`.
- Tests for pass/fail gate matrix.

## Epic B - Provider Reinforcement Layer

### Goal
Improve data completeness and reduce provider-specific failures.

### PR B1 - Provider capability matrix + flags

- Add provider capability registry in `seo_pipeline/vendors/capabilities.py`.
- Add feature flags for provider activation order in config.

Acceptance:

- Provider selection is data-driven, not hardcoded.
- Tests cover provider selection + fallback order.

### PR B2 - Quorum and partial-data policy

- Add quorum evaluator: do not continue to final generation if critical fields are missing.
- Persist partial-data reasons in metrics and status.

Acceptance:

- Runs with insufficient data fail early with actionable messages.
- Integration tests for degraded-provider scenarios.

## Epic C - Prompt And Model Pipeline

### Goal
Increase briefing quality with multi-step generation and validation.

### PR C1 - Prompt versioning and registry

- Create prompt registry:
  - `intent_classifier`,
  - `content_planner`,
  - `brief_generator`,
  - `quality_reviewer`.
- Add `prompt_version` tracking in run metrics.

Acceptance:

- Prompt versions persisted for each run.
- Tests verify prompt resolution and fallback.

### PR C2 - Two-step LLM orchestration

- Split generation:
  1. planner step -> structured plan,
  2. writer step -> final briefing.
- Add reviewer pass for consistency checks.

Acceptance:

- Planner and writer artifacts are saved for debugging.
- Tests validate schema and consistency checks.

### PR C3 - LLM gateway

- Route structured briefing generation through `seo_pipeline/llm/`.
- Keep OpenAI as the default adapter.
- Persist provider/model metadata in `prompt_run`.

Acceptance:

- Current OpenAI behavior remains compatible.
- Gateway tests cover provider routing and unsupported providers.

### PR C4 - Ollama/local adapter

- Add `LLM_PROVIDER=ollama` support through the LLM gateway.
- Validate local model JSON responses against `SEOBriefing`.

Acceptance:

- Tests mock Ollama HTTP responses.
- CI does not require a local model server.

### PR C5 - Anthropic adapter

- Add `LLM_PROVIDER=anthropic` support through the LLM gateway.
- Validate Anthropic JSON text responses against `SEOBriefing`.

Acceptance:

- Tests mock Anthropic HTTP responses.
- CI does not call external model providers.

## Epic D - Persistence Upgrade (Operational DB)

### Goal
Move from SQLite-only ops metadata to production-ready persistence.

### PR D1 - DB abstraction and migrations

- Introduce DB backend abstraction for JobStore.
- Keep SQLite backend for local/dev.
- Add PostgreSQL backend for production.

Acceptance:

- Same API behavior across backends.
- Migration scripts and rollback notes documented.

### PR D2 - Events and stage metrics tables

- Add tables for:
  - `job_events` (implemented),
  - `job_stage_metrics` (implemented),
  - `provider_calls` (implemented),
  - `prompt_runs` (implemented).
- Store retries, latency, cost, and error categories.

Acceptance:

- `run_id` lifecycle timeline query is available through `/jobs/{run_id}/events`.
- `run_id` metrics timeline query is available through `/jobs/{run_id}/metrics`.
- Stage metrics, provider call estimates and prompt runs are indexed from `run_metrics.json` in SQLite.
- Tests validate writes and reads for each table.

### PR D4 - DB-first final output store

- Persist final briefing output metadata in SQLite:
  - `job_outputs`,
  - `job_artifacts`,
  - `briefing_records`.
- Keep generated files as downloadable artifacts.

Acceptance:

- API-triggered successful runs persist briefing JSON, row24-equivalent data and artifact paths.
- Tests validate idempotent writes and cleanup/delete behavior.

## Epic E - Admin API V2 (Non-breaking Extension)

### Goal
Support operator workflows with stronger lifecycle control.

### PR E1 - State machine enforcement

- Add explicit state transitions in JobStore/service layer:
  - `queued -> running -> done|failed` (implemented),
  - cancellation and retry constraints (implemented),
  - lifecycle service wrapper for queue-backend readiness (implemented).

Acceptance:

- Invalid transitions return `409`.
- Unit/API tests for transition matrix.

### PR E2 - Enhanced list/filter API

- Extend `/jobs` filters:
  - by date range,
  - provider,
  - error_category.
- Keep current fields compatible.

Acceptance:

- Response contract remains stable.
- OpenAPI + contract tests updated.

## Epic F - Frontend Operator Console

### Goal
Provide a practical operational UI, not a marketing site.

### PR F1 - Dashboard and run list

- Add frontend app (Next.js + TypeScript) with:
  - run list,
  - status chips,
  - duration/cost/error summary.

Acceptance:

- Can inspect recent runs and filter by status/error.

### PR F2 - Run detail and controls

- Run detail timeline with stage metrics and artifacts.
- Actions: retry, cancel, cleanup.

Acceptance:

- Run detail includes persisted stage metrics, provider calls and prompt metadata.
- All admin actions available from UI with clear success/error feedback.

### PR F3 - Gradio DB-first ops UI

- Add `apps/gradio_app.py` for local operator workflows.
- Support model provider selection for `openai`, `ollama` and `anthropic`.
- Read jobs, metrics and final outputs from SQLite.

Acceptance:

- Callback tests run without launching a Gradio server.
- Gradio UI defaults to no Sheets upload.

## Epic H - Operator UX/UI Redesign

### Goal
Turn the current Gradio baseline into a usable local operator console from first
run through output review.

Detailed source of truth:

- `docs/UX_UI_REDESIGN_PLAN.md`

### PR UX1 - Product shell and navigation

- Add Home, setup checklist, active client/project context and recent run summary.
- Replace duplicate client/project entry points with shared context state.

Acceptance:

- A clean local app shows the next setup action.
- Selected context is reused by checks and launch.

### PR UX2 - Guided first-run setup

- Add provider credential status, default LLM setup, first client and first project flow.
- Keep secrets write-only and show configured/not configured status only.

Acceptance:

- A new operator can configure the minimum viable system without editing JSON.

### PR UX3 - Client and project workspaces

- Replace markdown listings with structured selectable lists.
- Add project effective configuration preview and inheritance visibility.

Acceptance:

- Existing clients/projects can be edited without manually typing IDs.

### PR UX4 - Integrations and preflight center

- Show live and config-only checks for SEMrush, SERP, GSC, GA4, Sheets and LLM.
- Display latest preflight state on the launch screen.

Acceptance:

- Operators can validate readiness for the active project before launching a run.

### PR UX5 - Briefing launcher redesign

- Split new-page and existing-page launch modes.
- Add run preview, mode-specific validation and explicit export intent.

Acceptance:

- Invalid runs fail before creating jobs.

### PR UX6 - Runs workspace and output review

- Add filterable run table, detail panels, metrics, costs, artifacts and safe admin actions.

Acceptance:

- Failed and completed runs can be diagnosed from the UI without opening files manually.

### PR UX7 - UI service layer

- Extract orchestration out of `apps/gradio_app.py` into reusable service modules.

Acceptance:

- Gradio callbacks are thin and core UI behavior is testable without importing Gradio.

### PR UX8 - Documentation and release readiness

- Add first-run tutorial, smoke checklist and final docs alignment.

Acceptance:

- README, runtime operations, troubleshooting, project map and AGENTS agree on the primary operator workflow.

## Epic G - Cost, Performance, And SLO

### Goal
Control runtime cost and latency while preserving quality.

### PR G1 - Cost tracking

- Persist per-run token and provider call cost estimates.
- Expose totals in metrics and `/jobs/{run_id}` detail.

Acceptance:

- Cost fields available for every completed run.

### PR G2 - SLO and alerts

- Define SLOs:
  - success rate,
  - p95 run duration,
  - retry spike thresholds.
- Add alert hooks/documented runbooks.

Acceptance:

- SLO definitions documented and testable against metrics shape.

## Proposed Sequence

1. A1, A2 (typed stages + gates)
2. B1, B2 (provider resilience)
3. C1, C2 (prompt/model quality)
4. E1 (state machine hardening)
5. D1, D2 (DB upgrade and observability depth)
6. E2 (admin filters)
7. F1, F2 (operator frontend)
8. UX1 through UX8 (operator UX/UI redesign)
9. G1, G2 (cost/SLO optimization)

## Immediate Next PR (Recommended)

`PR-next: UX polish and local smoke hardening`

- Run the integrated UX baseline against a clean local setup.
- Tighten labels, spacing and validation messages based on real usage.
- Add smoke coverage for app construction and the first-run path.
- Update `AGENTS.md`, `docs/GRADIO_OPERATOR_WORKFLOWS.md`, `docs/RUNTIME_OPERATIONS.md`.
