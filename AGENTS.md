# Agent Guide

This file is the entrypoint for coding agents working in this repository.

## Current State

- Main branch is expected to be green in GitHub Actions.
- `.env` is local-only and ignored. Never print, stage, commit or summarize its values.
- Generated artifacts are ignored: `outputs/`, `runs/`, `logs/`, caches, credentials and bytecode.
- Tests are under `tests/` and should be run with `pytest -q`.
- Recent work is being shipped through PR #18 (`codex/jobs-admin-suite`).

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

## Next Actions (Post-PR)

1. Merge PR #18 after CI is green and re-check `main` CI.
2. Wire complete `JobStore` lifecycle in API:
   - retention policy is present at store/startup level;
   - admin endpoints are present (`list/detail/delete/cleanup/retry/cancel`);
   - next step is optional queue backend upgrade (SQLite -> Redis) if concurrency grows.
3. Continue normalization contracts:
   - move additional consumers away from raw SERP dicts to typed models;
   - keep raw payload persisted for debugging only.
4. Improve observability operations:
   - add alerting for retry spikes and repeated provider `error_category`.
5. Contract hardening:
   - extend snapshot/contract tests for exports and metrics evolution.
6. Controlled UTF-8 cleanup:
   - docs first, then user-facing strings; avoid mixing with behavior changes.

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
git ls-files '.env' '*__pycache__*' '*.pyc'
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
- `docs/IMMEDIATE_ACTION_PLAN.md`: immediate operational plan and acceptance criteria.
- `docs/IMPROVEMENT_ROADMAP.md`: prioritized improvement backlog.

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
