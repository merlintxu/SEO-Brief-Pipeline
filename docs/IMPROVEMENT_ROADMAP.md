# Improvement Roadmap

This roadmap is ordered by risk reduction and operational value.

Execution detail is now tracked in:

- `docs/REARCHITECTURE_EXECUTION_PLAN.md` (epics, PR slicing, acceptance and tests).
- `docs/UX_UI_REDESIGN_PLAN.md` (global operator UX/UI redesign across 8 PRs).
- `docs/GOOGLE_AI_SEARCH_SKILL_ANALYSIS.md` (Google AI Search skill analysis and AISEO backlog).

## P0 - Stabilization

### Fix GSC model mismatch

Status: implemented.

Problem: the GSC adapter previously used the wrong model field for click totals.

Acceptance:

- GSC cannibalization can build `GscPage` without validation errors.
- Add a unit test for `fetch_cannibalization()` with mocked service response.

### Unify API and pipeline output paths

Status: implemented for API-triggered runs.

Problem: API status used `outputs/{run_id}`, while pipeline artifacts used the project output path.

Acceptance:

- API response `output_dir` matches the actual artifact directory.
- Status endpoint and download endpoint read from the same run directory used by the pipeline.
- Existing tests cover queued, done, failed and downloads.

### Validate credentials before vendor execution

Status: implemented for required SEMrush, SERP and OpenAI execution.

Problem: missing credentials fail inside provider calls with inconsistent messages.

Acceptance:

- Preflight validation names missing credentials without printing values.
- API returns clear `failed` status for missing SEMrush, SERP or OpenAI credentials.
- Optional providers remain optional: GSC, Sheets and DataForSEO.

### Add run metrics per pipeline stage

Status: implemented.

Problem: status files only expose current state, not stage timing or operational context.

Acceptance:

- Each run writes `run_metrics.json`.
- Metrics include `run_id`, keyword, status, timestamps and per-stage duration.
- Download whitelist includes the metrics artifact.

### Controlled UTF-8 cleanup

Problem: mojibake exists in comments, docs and user-facing strings.

Acceptance:

- Docs render cleanly.
- User-facing Spanish messages are valid UTF-8.
- No behavior changes mixed into the cleanup PR.

## P1 - Reliability And Observability

Execution checkpoint:

- A2 quality gate engine added with metrics persistence and strict-mode toggle (`QUALITY_GATES_STRICT`).
- B1 baseline added for SERP capability matrix + feature flags (provider order and enable/disable toggles).
- B2 quorum policy added with explicit continue/fail semantics and metrics persistence.
- C1 prompt registry baseline added with prompt version persistence in run metrics.
- C2 planner/writer split baseline added with planner artifact traceability.
- D1 backend abstraction scaffold added for job store (SQLite operational, PostgreSQL scaffold).
- D2 lifecycle event persistence added in SQLite (`job_events`) and exposed in job detail payloads.
- D3 events pagination endpoint added (`GET /jobs/{run_id}/events`) with bounded limit/cursor.
- E1 baseline ops dashboard added at `public/dashboard.html` for authenticated jobs/admin workflows.
- E2 dashboard hardening added: run-status polling, destructive action confirmations, and error normalization.
- E3 dashboard serving/session baseline added: API route `/ops` plus session-default API-key persistence with optional remember mode.
- F1 lightweight operator audit trail added in dashboard UI (actions, confirmations, outcomes).
- F2 operator audit persistence added with append-only SQLite events and protected `GET/POST /ops/audit-trail`.
- G1 cost tracking baseline added in run metrics and job detail payloads.
- G2 SLO groundwork added with testable rolling-window evaluation for success rate, p95 duration, retry rate and categorized failure rate.
- SLO dashboard/API integration added with protected `GET /ops/slo` and dashboard summary.

### Structured run logging

Add `run_id`, `keyword`, `step`, duration and provider to log records.

Acceptance:

- Each pipeline stage emits start/end/failure events.
- Logs can be filtered by `run_id`.

### Stage timing metrics

Capture duration for SEMrush, SERP, audit, GSC, OpenAI, export and Sheets.

Acceptance:

- `status.json` or a companion metrics file includes stage timings.
- Slowest stage is visible after each run.

### Stronger vendor retry policies

Status: implemented.

Make retry exceptions provider-aware.

Acceptance:

- Retry transient network and rate-limit failures.
- Do not retry permanent credential/config errors.
- Tests cover both retryable and non-retryable cases.

### Integration pipeline test with real artifacts and mocked vendors

Acceptance:

- Full `run_full_pipeline()` writes JSON, Markdown, CSV, XLSX and status with all vendors mocked.
- No external network calls occur.

## P2 - Product And Scale

Execution checkpoint:

- A1 stage contracts baseline implemented in models (`PipelineInput`, `KeywordSet`, `CompetitorSet`, `EnrichmentSet`, `BriefingPlan`) with dedicated tests.
- A1 contracts wired into `run_full_pipeline()` handoff with backward-compatible outputs.
- Gradio operator workflow expanded for client/project management, provider connection checks and typed briefing launch context.
- GA4 existing-page enrichment baseline added as optional, non-blocking pipeline data.
- Global runtime settings added for shared provider credentials and LLM base URL in ignored local config.
- Client/project inheritance added for base domain, SEMrush database and Google locale.
- Gradio controls now use constrained dropdowns/checkboxes for supported markets, locales, models and SERP providers.
- Google Drive spreadsheet discovery added for service-account-visible Sheets.
- Gradio client/project edit UX added with dropdown refresh, load-selected and save-over-same-ID flows.
- UX/UI redesign plan added to make the operator console usable from first run through output review.

### Operator UX/UI redesign

Status: implemented baseline.

The current Gradio app is functionally useful but still organized around
technical tabs. The redesign plan moves the product toward a single operator
console with first-run setup, active client/project context, project workspaces,
preflight checks, guided briefing launch, run monitoring and output review.

Execution source of truth:

- `docs/UX_UI_REDESIGN_PLAN.md`

Acceptance:

- UX1 through UX8 are represented in the local Gradio baseline.
- The local app remains runnable and documented.
- Operators can reach a first briefing without editing JSON manually.

### Batch keyword processing

Status: implemented; resumable mode added.

Add a batch runner for multiple keywords with isolated statuses.

Acceptance:

- Input can be CSV or JSON.
- Each keyword receives a separate run id.
- Failures do not stop the whole batch unless configured.
- `--resume` skips prior `done` items from `batch_manifest.json` and retries incomplete items.

### Persistent job store

Replace background-only state with SQLite or Redis.

Status: in progress (SQLite store implemented and wired into API create/status/admin flow with `status.json` fallback compatibility).

Progress update:

- retry lineage persisted via `source_run_id` in `JobStore` and jobs API payloads.
- lifecycle transitions are now guarded in `JobStore` with explicit state transition rules.
- lifecycle timeline is now persisted per run in `job_events` and returned by `GET /jobs/{run_id}`.

Acceptance:

- API restart does not lose queued/running/completed metadata.
- Admin surface exists: list/detail/delete/cleanup/retry/cancel.
- Remaining step: evaluate queue backend upgrade if workload exceeds in-process background task limits.

### Cache management commands

Status: implemented.

Add safe commands to inspect and clear provider caches.

Acceptance:

- Cache clear never deletes outside configured cache directories.
- CLI reports cache size and oldest/newest entries.

### Enhanced jobs filters

Status: implemented.

`GET /jobs` supports optional date, provider and error-category filters while preserving the existing list response shape.

### Client/project operator workbench

Status: implemented in Gradio baseline.

Local operators can manage global runtime settings, clients, projects, project runtime defaults, connection checks and briefing launch context from `apps/gradio_app.py`.

Acceptance:

- Client/project JSON remains the local source of truth.
- Existing clients and projects can be loaded into the form, edited and saved without manually editing JSON.
- Shared secrets are stored in ignored local `config/runtime_settings.json` and never displayed in lists/details.
- Client defaults are inherited by projects unless explicitly overridden.
- Gradio-created jobs persist `client_id`, `project_id`, `brief_type` and `target_url`.
- Tests cover callbacks without launching a Gradio server.

### Google Drive Sheets discovery

Status: implemented baseline.

Operators can list Google Sheets visible to the configured service account and copy the target spreadsheet ID/URL into a project.

Acceptance:

- Discovery uses Drive metadata scope only.
- CI tests use mocked Drive services only.
- Interactive end-user OAuth remains a future enhancement.

### GA4 existing-page enrichment

Status: implemented baseline.

Existing-page briefings can query GA4 URL metrics when the project has `ga4_property_id` and the client has a service account path.

Acceptance:

- GA4 is optional and non-blocking.
- `run_metrics.json` records a `ga4` stage.
- CI tests use mocked GA4 services only.

### Google AI Search readiness

Status: implemented baseline.

The attached `google-ai-search-optimization` skill was reviewed against the
current pipeline. The strongest opportunity is to turn Google AI Search guidance
into typed readiness signals, target URL audits, better prompt inputs and
post-generation quality review.

Execution source of truth:

- `docs/GOOGLE_AI_SEARCH_SKILL_ANALYSIS.md`

Implemented baseline:

- AISEO1: readiness contracts and deterministic checklist evaluator.
- AISEO2: target URL audit stage for existing-page runs.
- AISEO3: prompt upgrade with myth guardrails and readiness context.
- AISEO4: brief quality reviewer.
- AISEO5: project vertical modes.
- AISEO6: deterministic agent-friendly audit signals.

Next hardening:

- richer ecommerce/local fixtures.
- one-pass target HTML reuse.
- optional rendered DOM audit for JavaScript-heavy pages.

### OpenAPI contract export

Status: implemented.

Progress update:

- jobs admin endpoints now declare explicit response models to stabilize API contract evolution.

Acceptance:

- Generated OpenAPI JSON is versioned or published as an artifact.
- Request/response examples match current schemas.

## P3 - Developer Experience

### Pre-commit

Status: implemented (baseline).

Add local hooks for:

- secret scanning
- bytecode/output guard
- formatting/linting
- markdown checks

Acceptance:

- Hooks run locally and mirror CI where practical.
- CI workflow action versions are kept current to avoid Node runtime deprecation on GitHub runners.

### Notebook cleanup

Acceptance:

- Notebooks are clearly examples, not production entry points.
- Any required sample inputs are synthetic.

### Cost and quota guide

Acceptance:

- Provider cost assumptions documented.
- Recommended limits by daily keyword volume documented.

## Suggested Execution Order

1. GSC `clicks` bug and test.
2. Output path unification and API tests.
3. Credential preflight.
4. UTF-8 cleanup.
5. Structured logging and timing metrics.
6. Full mocked integration test.
7. Batch runner and persistent jobs.
