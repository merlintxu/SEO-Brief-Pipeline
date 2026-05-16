# Agent Guide

This file is the entrypoint for coding agents working in this repository.

## Current State

- Main branch is expected to be green in GitHub Actions.
- `.env` is local-only and ignored. Never print, stage, commit or summarize its values.
- Generated artifacts are ignored: `outputs/`, `runs/`, `logs/`, caches, credentials and bytecode.
- Tests are under `tests/` and should be run with `pytest -q`.
- Current execution is aligned to `docs/REARCHITECTURE_EXECUTION_PLAN.md`; latest local work implements the integrated UX/UI redesign baseline from `docs/UX_UI_REDESIGN_PLAN.md`.

## Documented Changes (Recent)

- Pipeline observability baseline is active:
  - structured stage metrics in `run_metrics.json` with `provider`, `status`, `retries`, `items_processed`, `error_category`.
  - failed runs persist `error_category` in `status.json` and metrics.
- Runtime contracts and artifact naming are centralized:
  - canonical artifact names in `seo_pipeline/artifacts.py`.
  - API download whitelist aligned to those names.
- SERP normalization was migrated to `SerpSnapshot` for downstream usage.
- Runtime preflight checks are centralized in `seo_pipeline/runtime_validation.py`.
- Added centralized runtime input validation in `seo_pipeline/input_validation.py`:
  - validates `keyword`, `target_url`, `related_limit`, `serp_num`, `top_competitors_count`, `gsc_months_back`.
- Added typed SERP raw payload models in `seo_pipeline/models.py` and typed coercion in `seo_pipeline/vendors/serp_io.py`.
- Added SQLite job-store spike and partial API integration:
  - store module: `api/job_store.py`.
  - API writes/updates job status in SQLite while keeping `status.json` compatibility.
  - `GET /briefing/{run_id}` falls back to job store if status file is missing.
- API run id now includes microseconds to avoid collision under burst requests.
- Docs updated: `docs/RUNTIME_OPERATIONS.md`, `docs/IMMEDIATE_ACTION_PLAN.md`, `TROUBLESHOOTING.md`.
- Test coverage added/updated for input validation, typed SERP normalization, API smoke/job-store flows.
- Added run metrics contract tests to lock backward-compatible root keys and stage observability shape.
- Added human-readable log correlation in pipeline text logs with `run_id` and `stage` prefixes.
- Added job-store retention helpers:
  - `delete_job(run_id)`
  - `cleanup_old_jobs(max_age_days, statuses)`
- Added API startup retention cleanup path:
  - env config `JOB_STORE_RETENTION_DAYS` (default `30`)
  - retention cleanup executes on API startup and does not block service boot if cleanup fails.
- Added protected operational jobs endpoint:
  - `GET /jobs?limit=N` returns recent job metadata from SQLite `JobStore`.
  - endpoint is API-key protected and intended for ops/debug workflows.
- Added `/jobs` limit validation coverage:
  - `limit` supports `1..200`.
  - invalid limits return `422` via FastAPI validation.
- Added jobs administration suite (authenticated):
  - `GET /jobs` supports limit/cursor/status/search.
  - `GET /jobs/{run_id}` returns job detail and optional status snapshot.
  - `DELETE /jobs/{run_id}` deletes metadata only.
  - `POST /jobs/cleanup` runs bounded terminal-state cleanup.
  - `POST /jobs/{run_id}/retry` requeues failed jobs as new runs.
  - `POST /jobs/{run_id}/cancel` performs logical cancellation for queued/running jobs.
- Added OpenAPI contract export flow:
  - source of truth file: `docs/contracts/openapi.json`
  - exporter command: `python tools/export_openapi.py`
  - test coverage validates contract JSON and required API paths.
- Added pre-commit baseline:
  - `.pre-commit-config.yaml` with formatting, YAML/JSON checks, private-key detection and local repo guards.
  - local hooks: `tools/check_repo_guard.py` and `tools/check_markdown.py`.
- Added retry lineage persistence in job metadata:
  - `JobStore` now stores `source_run_id` for retried jobs.
  - `POST /jobs/{run_id}/retry` persists the parent run id in the new queued job.
  - `GET /jobs` and `GET /jobs/{run_id}` include `source_run_id` in the job payload.
- Updated GitHub Actions workflow to Node24-ready action versions:
  - `actions/checkout@v5`
  - `actions/setup-python@v5`
- Added explicit response contracts for jobs admin endpoints in `api/schemas.py`:
  - `JobsListResponse`, `JobDetailResponse`, `JobDeleteResponse`, `JobsCleanupResponse`, `JobRetryResponse`, `JobCancelResponse`.
  - FastAPI endpoints now declare `response_model` for stable OpenAPI output.
- Added job status transition hardening in `JobStore`:
  - allowed statuses: `queued`, `running`, `done`, `failed`.
  - allowed transitions:
    - `queued -> queued|running|failed`
    - `running -> running|done|failed`
    - `done -> done`
    - `failed -> failed`
  - invalid transitions raise `InvalidJobTransitionError`.
- Added stage contracts baseline (A1) in `seo_pipeline/models.py`:
  - `PipelineInput`, `KeywordSet`, `CompetitorSet`, `EnrichmentSet`, `BriefingPlan`.
  - initial contract tests in `tests/test_stage_contracts.py`.
- Wired A1 stage contracts into pipeline runtime:
  - `run_full_pipeline()` now builds typed stage snapshots and stores them in results for traceability.
  - added regression assertions in `tests/test_pipeline_full_mock.py`.
- Added A2 quality gate engine:
  - module: `seo_pipeline/quality_gates.py`.
  - gate outcomes persisted in `run_metrics.json` under `quality_gates`.
  - strict mode toggle: `QUALITY_GATES_STRICT=1` (fails run when coverage gates fail).
- Added B1 provider capability matrix baseline for SERP:
  - module: `seo_pipeline/vendors/capabilities.py`
  - env flags: `SERP_ENABLE_SERPAPI`, `SERP_ENABLE_DATAFORSEO`, `SERP_PROVIDER_ORDER`
  - runtime stores selected provider plan in pipeline results.
- Added B2 quorum / partial-data policy:
  - module: `seo_pipeline/quorum.py`
  - metrics contract: `quorum.decision`, `quorum.checks`, `quorum.failed_count`
  - defaults to continue with partial data, optional hard enforcement with `QUORUM_ENFORCE=1`
- Added C1 prompt registry baseline:
  - module: `seo_pipeline/prompt_registry.py`
  - prompt resolution by key/version (`brief_generator`, `v1`)
  - pipeline persists `prompt_run` (`key`, `version`, `model`, `temperature`) in metrics/results
- Added C2 planner/writer split baseline:
  - planner artifact builder: `build_briefing_plan_artifact()` in `seo_pipeline/blueprint.py`
  - writer step consumes planner artifact in `generate_briefing()`
  - `prompt_run` now tracks `planner_version` and `mode=planner_writer`
- Added D1 job-store backend abstraction scaffold:
  - `JobStore` now acts as a facade with backend selection via `JOB_STORE_BACKEND`.
  - operational backend: `SQLiteJobStoreBackend`.
  - scaffold backend: `PostgresJobStoreBackend` (explicitly not enabled yet).
- Added D2 SQLite job lifecycle events:
  - `job_events` table stores transition timeline per `run_id`.
  - events are appended on `create_job` and `update_status`.
  - `GET /jobs/{run_id}` now returns `events` in descending order.
  - `DELETE /jobs/{run_id}` also deletes related event metadata.
- Added D3 events pagination endpoint:
  - new endpoint `GET /jobs/{run_id}/events?limit=&cursor=` (API-key protected).
  - response contract: `items`, `count`, `next_cursor`.
  - bounded pagination (`limit` in `1..200`), newest-first ordering.
- Added E1 operational dashboard bootstrap:
  - `public/dashboard.html` now supports API URL + `X-API-Key` configuration.
  - includes `/briefing` launch, `/jobs` listing/filtering/pagination, job detail + events timeline.
  - includes admin actions: `retry`, `cancel`, `delete`, `cleanup`.
- Added E2 dashboard UX hardening:
  - polling de estado de runs tras `POST /briefing`.
  - confirmaciones explícitas para `cancel`, `delete` y `cleanup`.
  - mapeo de errores HTTP a mensajes operativos legibles.
- Added E3 dashboard serving + session baseline:
  - API now serves dashboard at `GET /ops` (single file route, no broad static mount).
  - dashboard auth UX now supports explicit key persistence policy:
    - session-only by default
    - optional remember mode in local storage
    - explicit key clear action.
- Added F1 lightweight operator audit trail in dashboard:
  - in-memory trail panel logs operator actions and outcomes.
  - captures confirmation decisions (`cancel`, `delete`, `cleanup`).
  - includes timestamp, action, result and metadata (`run_id` or error summary).
  - capped to latest 50 entries with manual clear action.
- Added F2 operator audit trail persistence:
  - SQLite append-only `operator_audit_events` table in `JobStore`.
  - protected `GET/POST /ops/audit-trail` endpoints with stable response contracts.
  - dashboard loads the latest persisted trail and writes operator actions best-effort.
- Added G1 cost tracking baseline:
  - `run_metrics.json` includes `costs` with USD totals, estimate rows and unknown provider count.
  - OpenAI briefing stage stores estimated input/output/total tokens and estimated cost.
  - `GET /jobs/{run_id}` exposes `cost_summary` from `run_metrics.json`.
- Added G2 SLO groundwork:
  - `seo_pipeline/slo.py` evaluates rolling windows of `run_metrics.json` payloads.
  - SLO checks cover success rate, p95 duration, retry rate and categorized failure rate.
  - operations docs include default thresholds and first-response runbook.
- Added cache management commands:
  - `tools/cache_admin.py inspect` reports configured cache size, file count and oldest/newest entries.
  - `tools/cache_admin.py clear --yes` removes files only after resolving the cache root safely.
- Added batch keyword runner:
  - `tools/batch_runner.py` accepts CSV or JSON keyword input.
  - each keyword gets an isolated run id and output directory.
  - failures continue by default unless `--stop-on-error` is set.
- Added resumable batch keyword runs:
  - `tools/batch_runner.py --resume` skips items already marked `done` in `batch_manifest.json`.
  - batch summaries now include `skipped`, per-item timestamps and `error_summary`.
- Added API job lifecycle service:
  - `api.job_lifecycle.JobLifecycleService` centralizes enqueue, start, fail, cancel and stale-running detection.
  - FastAPI still uses in-process `BackgroundTasks`; this is queue-backend preparation only.
- Added provider-aware retry policies:
  - `retry_call()` accepts a `should_retry` predicate.
  - SEMrush, SERP, audit and GSC calls retry transient provider failures and fail fast on auth/config/validation errors.
- Added DB-first final output indexes:
  - SQLite tables: `job_outputs`, `job_artifacts`, `briefing_records`.
  - API-triggered successful runs persist briefing JSON, row24-equivalent data and artifact paths.
  - file artifacts remain available for download compatibility.
- Added LLM gateway baseline:
  - `seo_pipeline/llm/` routes structured briefing generation through provider adapters.
  - OpenAI remains the default adapter and current structured-output behavior is preserved.
  - `prompt_run` now includes provider metadata.
- Added Ollama LLM adapter:
  - `LLM_PROVIDER=ollama`, `OLLAMA_BASE_URL`, `OLLAMA_MODEL`.
  - structured responses are validated against `SEOBriefing`.
  - CI uses mocks and does not require a local Ollama server.
- Added Anthropic LLM adapter:
  - `LLM_PROVIDER=anthropic`, `ANTHROPIC_API_KEY`, `ANTHROPIC_MODEL`.
  - Anthropic Messages API text is parsed as JSON and validated against `SEOBriefing`.
  - CI uses mocks and does not call Anthropic.
- Added Gradio ops UI:
  - `apps/gradio_app.py` starts DB-first local operator UI.
  - supports provider selection for OpenAI, Ollama and Anthropic.
  - lists jobs and reads persisted outputs/metrics from SQLite.
- Made DB-first no-Sheets mode explicit:
  - API and pipeline defaults now keep `upload_to_sheets=false`.
  - Google Sheets remains an optional export when explicitly enabled and configured.
  - README and operations docs describe the DB-first model/provider workflow.
- Added project runtime configuration:
  - `ProjectConfig.runtime.llm` defines per-project LLM provider, model, base URL and prompt version.
  - `ProjectConfig.runtime.providers.serp.provider_order` defines per-project SERP API order.
  - API preflight validates the active project runtime before queuing `/briefing`.
  - pipeline metrics retain the resolved LLM provider/model and SERP provider plan for each run.
- Added SLO dashboard/API integration:
  - protected `GET /ops/slo` evaluates recent job metrics with `seo_pipeline/slo.py`.
  - dashboard shows SLO status, run counts, p95 duration, retry rate and failed checks.
- Added extended jobs filters:
  - `GET /jobs` supports `created_from`, `created_to`, `error_category` and `provider`.
  - dashboard job list includes provider and error-category filters.
- Added persisted operational metrics indexes:
  - SQLite tables: `job_stage_metrics`, `provider_calls`, `prompt_runs`.
  - populated from `run_metrics.json` after API background runs finish and when existing job metrics are inspected.
  - `run_metrics.json` remains the artifact contract and source of truth.
- Added job metrics timeline API/dashboard integration:
  - protected `GET /jobs/{run_id}/metrics` returns stage metrics, provider calls, prompt run metadata and summary counts.
  - `/ops` job detail now renders persisted metrics alongside lifecycle events.
- Added Gradio client/project operator workflows:
  - tabs for client and project create/update backed by `data/clients.json` and `data/projects.json`.
  - project runtime editing includes LLM provider/model/base URL, prompt version and SERP provider order.
  - optional `ga4_property_id` is now part of `ProjectConfig`.
  - connection checks cover SEMrush, SERP, GSC, GA4, Sheets and LLM configuration.
  - Gradio-created jobs persist `client_id`, `project_id`, `brief_type` and `target_url`.
- Added GA4 existing-page enrichment baseline:
  - module: `seo_pipeline/vendors/ga4_io.py`.
  - pipeline writes optional `ga4_url_metrics` and a `ga4` stage in `run_metrics.json`.
  - GA4 failures are non-blocking and tests use mocked Google services only.
- Added global/local runtime settings and inherited client/project defaults:
  - ignored local settings file: `config/runtime_settings.json`.
  - shared SEMrush, SerpAPI, OpenAI, Anthropic, LLM base URL and DataForSEO settings are merged into active clients at runtime.
  - clients now define `default_base_domain`, `default_database`, `default_gl` and `default_hl`.
  - projects inherit client defaults and can override base domain, SEMrush database and Google locale.
  - project output paths now default to `{output_dir}/{client_id}/{project_id}/{run_id}` for direct runs.
- Added constrained operator options:
  - `seo_pipeline/options.py` centralizes selectable SEMrush databases, Google `gl`/`hl`, LLM providers/models and SERP providers.
  - Gradio uses dropdowns/checkboxes instead of arbitrary text for these fields.
  - default local LLM is now `ollama` with `gemma4:26b`.
- Added Google Drive spreadsheet discovery:
  - module: `seo_pipeline/vendors/drive_io.py`.
  - Gradio can list Sheets visible to the configured service account.
- Added Gradio client/project edit UX:
  - existing clients and projects can be refreshed into dropdowns, loaded into forms and saved back over the same ID.
  - tests cover load/refresh callbacks without launching a Gradio server.
- Added global UX/UI redesign plan:
  - source of truth: `docs/UX_UI_REDESIGN_PLAN.md`.
  - slices the operator console redesign into UX1 through UX8, covering first-run setup, shared context, workspaces, preflight, launch, runs, service extraction and release docs.
- Implemented integrated Gradio UX/UI baseline:
  - Home setup checklist and active client/project context.
  - Settings, Clients, Projects, Preflight, Launch and Runs task areas.
  - Project effective configuration preview and duplicate-project workflow.
  - Config preflight, guarded launch validation and richer run detail/actions.
  - New service layer: `seo_pipeline/operator_ui.py`.
- Added Google AI Search skill analysis:
  - source of truth: `docs/GOOGLE_AI_SEARCH_SKILL_ANALYSIS.md`.
  - proposes AISEO backlog for readiness contracts, target URL audit, prompt guardrails, quality review, vertical modes and agent-friendly audits.
- Implemented AISEO1-AISEO6 baseline:
  - `seo_pipeline/ai_search_readiness.py` adds readiness reports, target URL audit support, myth guardrails and brief quality review.
  - `ProjectConfig.project_type` supports `content`, `ecommerce`, `local`, `saas`, `marketplace`.
  - pipeline writes `ai_search_readiness.json` and, for existing pages, `target_audit_report.json`.
  - prompt context now includes readiness findings and anti-hack guardrails.
- Cleaned obsolete root-level manual scripts:
  - removed ad-hoc `test_*.py` pipeline smoke scripts now covered by `tests/`.
  - removed legacy `restart_pipeline.sh` launcher in favor of documented API/Gradio entrypoints.
  - removed hardcoded-key API smoke script and tightened local repo guard coverage for `*.egg-info`.
- Implemented Premium UX/UI V2 Redesign Baseline (UX9 and UX10):
  - injected modern Dark Mode theme, Google Fonts (Inter) and CSS styling (Glassmorphism, gradients) in `apps/gradio_app.py`.
  - replaced `gr.Tab` navigation with a structural Dashboard Sidebar (`gr.Row`/`gr.Column`) for active context visibility.
  - grouped views dynamically using `gr.Group` controlled by sidebar actions.
  - updated `docs/UX_UI_REDESIGN_PLAN.md` with the new V2 Premium roadmap.
- Implemented Premium UX/UI V2 Redesign Additions (UX11 and UX12):
  - wrapped advanced/secondary inputs in `gr.Accordion` components to streamline forms.
  - unified `Preflight` and `Launch` tabs into a single workflow.
  - replaced raw `gr.Dataframe` for Runs with custom `gr.HTML` rendering using `runs_table_html`, displaying visual status pills.

## Next Actions (Post-PR)

1. Execute `docs/REARCHITECTURE_EXECUTION_PLAN.md` in medium PRs.
2. Smoke test the integrated Gradio UX baseline with a clean local setup.
3. Harden AISEO baseline with richer ecommerce/local fixtures and one-pass target HTML reuse.
4. Decide whether global/client/project management should remain Gradio-only or be promoted to authenticated API endpoints.
5. Continue typed stage contracts and quality gates before adding new provider complexity.
6. Expand typed enrichment contracts for GA4/GSC/Drive before prompt tuning experiments.
7. Prepare DB abstraction (SQLite + PostgreSQL) before scaling admin operations/frontend.

## Documentation Discipline (Mandatory)

- Every functional code change must include:
  - `AGENTS.md` update (status + next actions).
  - at least one relevant docs update under `docs/` (operations/roadmap/architecture/troubleshooting).
- Every PR description must include:
  - summary of behavior changes,
  - test commands executed,
  - explicit note if no doc changes were needed (exception case).
- Work is not considered complete until docs + agent status are updated.

## Safe Commands

```bash
git status --short --branch
python -m pip install -e ".[test]"
pytest -q
git diff --check
git ls-files '.env' '*__pycache__*' '*.pyc' '*.egg-info'
```

The `git ls-files` command should return no output.

## Repository Map

- `api/`: FastAPI API, schemas and rate limiting.
- `seo_pipeline/`: core pipeline package.
- `seo_pipeline/vendors/`: external vendor adapters.
- `seo_pipeline/audit/`: competitor content audit.
- `seo_pipeline/utils/`: IO, text, logging and retry helpers.
- `data/`: tracked sample client/project JSON config; no secrets.
- `docs/`: operational and system documentation.
- `tests/`: unit and integration-style tests with mocks.
- `notebooks/`: exploratory notebooks; do not treat as source of truth.

Key docs:

- `docs/PROJECT_MAP.md`: file, function and artifact map.
- `docs/PIPELINE_DEEP_DIVE.md`: stage-by-stage pipeline behavior, risks and improvements.
- `docs/EXTERNAL_APIS.md`: provider contracts, credentials and expected failures.
- `docs/RUNTIME_OPERATIONS.md`: local setup, API lifecycle, deployment and debugging.
- `docs/GRADIO_OPERATOR_WORKFLOWS.md`: local Gradio client/project, connection-check and briefing workflows.
- `docs/UX_UI_REDESIGN_PLAN.md`: global UX/UI redesign plan for the operator console.
- `docs/GOOGLE_AI_SEARCH_SKILL_ANALYSIS.md`: analysis of the attached Google AI Search optimization skill and proposed AISEO backlog.
- `docs/IMMEDIATE_ACTION_PLAN.md`: immediate operational plan and acceptance criteria.
- `docs/IMPROVEMENT_ROADMAP.md`: prioritized improvement backlog.
- `docs/REARCHITECTURE_EXECUTION_PLAN.md`: executable rearchitecture backlog with PR-level steps.

## Main Flow

```text
API/CLI
  -> run_full_pipeline()
  -> SEMrush keyword data
  -> SERP provider data
  -> competitor audit
  -> optional GSC cannibalization
  -> anchor generation
  -> OpenAI SEOBriefing
  -> row24
  -> JSON/Markdown/CSV/XLSX exports
  -> optional Google Sheets upsert
```

## Important Entry Points

- `api.main:create_briefing`: starts background briefing jobs.
- `api.main:briefing_status`: reads run status.
- `api.main:download_file`: whitelisted artifact download.
- `seo_pipeline.pipeline:run_full_pipeline`: orchestrates the full workflow.
- `seo_pipeline.blueprint:generate_briefing`: calls OpenAI structured outputs.
- `seo_pipeline.models`: Pydantic data contracts.
- `seo_pipeline.constants`: spreadsheet headers and prompts.

## External Services

- SEMrush: keyword data and unit balance.
- SerpAPI: primary SERP provider.
- DataForSEO: optional SERP fallback.
- OpenAI: structured briefing generation.
- Google Search Console: optional cannibalization detection.
- Google Sheets: optional row upsert.
- Sentry: optional API monitoring via `SENTRY_DSN`.

See `docs/EXTERNAL_APIS.md` for details.

## Rules For Agents

- Do not read or display `.env` unless explicitly necessary, and never reveal values.
- Do not commit generated outputs, credentials, caches or bytecode.
- Prefer local helpers and existing patterns over new abstractions.
- Keep public data contracts in `models.py` and API schemas in `api/schemas.py`.
- Use mocks in tests; do not hit real vendor APIs in automated tests.
- If changing API behavior, update README, Architecture, Runtime Operations and tests.

## Before Finishing Work

1. Run `pytest -q`.
2. Run `git diff --check`.
3. Confirm no forbidden files are tracked.
4. Confirm docs do not include real secrets.
5. Summarize any remaining risks or manual follow-up.
