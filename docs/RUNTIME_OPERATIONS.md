# Runtime Operations

## Local Setup

Install for development:

```bash
python -m pip install -e ".[test]"
```

Install developer tooling (pre-commit and lint/format hooks):

```bash
python -m pip install -e ".[dev]"
pre-commit install
```

Install runtime dependencies only:

```bash
python -m pip install -r requirements.txt
```

Create local environment:

```bash
cp .env.example .env
```

Do not commit `.env`.

## Required Environment

Minimum API runtime:

```env
API_KEY=replace_with_strong_api_key_at_least_20_chars
```

Pipeline runtime normally also needs:

```env
SEMRUSH_TOKEN=replace_with_semrush_token
SERPAPI_KEY=replace_with_serpapi_key
OPENAI_API_KEY=replace_with_openai_key
```

Optional:

```env
DFSP_USERNAME=replace_with_dataforseo_login
DFSP_PASSWORD=replace_with_dataforseo_password
SENTRY_DSN=
SENTRY_ENVIRONMENT=development
SENTRY_RELEASE=2025.11.18
PIPELINE_ROOT=
JOB_STORE_RETENTION_DAYS=30
QUALITY_GATES_STRICT=0
SERP_ENABLE_SERPAPI=1
SERP_ENABLE_DATAFORSEO=1
SERP_PROVIDER_ORDER=serpapi,dataforseo
QUORUM_ENFORCE=0
QUORUM_MIN_RELATED_KEYWORDS=1
QUORUM_MIN_TOP_URLS=3
QUORUM_MIN_COMPETITOR_DOMAINS=2
QUORUM_MIN_AUDIT_ENTRIES=1
BRIEFING_PROMPT_VERSION=v1
JOB_STORE_BACKEND=sqlite
# JOB_STORE_POSTGRES_DSN=postgresql://user:pass@host:5432/dbname  # scaffold only, not enabled yet
```

## Client And Project Config

The pipeline loads:

- `data/clients.json`
- `data/projects.json`

Client config holds credentials and provider defaults.

Project config holds domain, GSC property, Sheets id and output path.

Use the CLI for interactive management:

```bash
python client_manager.py
```

## Running The API

PowerShell:

```powershell
$env:API_KEY = "replace_with_strong_api_key_at_least_20_chars"
uvicorn api.main:app --reload
```

Bash:

```bash
export API_KEY="replace_with_strong_api_key_at_least_20_chars"
uvicorn api.main:app --reload
```

Health:

```bash
curl http://localhost:8000/health
```

Docs:

```text
http://localhost:8000/docs
```

Ops dashboard (static file):

```text
public/dashboard.html
```

Open it in a browser and configure `API Base URL` + `X-API-Key` for authenticated operations.
Current UX behaviors:
- after creating a briefing run, dashboard polls `/briefing/{run_id}` until terminal status.
- destructive actions (`cancel`, `delete`, `cleanup`) request operator confirmation.
- HTTP errors are normalized into operator-friendly messages.
- API also serves the same dashboard at:
  - `GET /ops`
- API key persistence policy in UI:
  - default: session storage (clears when browser session ends)
  - optional "remember" mode persists key in local storage
  - explicit "Borrar Key" action wipes both stores.
- Operator audit trail in UI:
  - panel "Trail Operativo" logs operator actions and outcomes.
  - logs include confirmation decisions for destructive actions.
  - latest 50 events are shown in the UI.
  - events are persisted best-effort through the protected append-only API.
  - "Limpiar Vista" clears the local dashboard view only; persisted audit events remain.

OpenAPI contract export:

```bash
python tools/export_openapi.py
```

Contract file path:

```text
docs/contracts/openapi.json
```

## Request Lifecycle

1. Client sends `POST /briefing` with `X-API-Key`.
2. API validates `BriefingRequest`.
3. API creates `run_id` and writes `outputs/{run_id}/status.json`.
4. API schedules a FastAPI background task.
5. Background task calls `run_full_pipeline()`.
6. Pipeline updates status as it moves through SEMrush, SERP, audit, GSC, anchors, OpenAI, export and optional Sheets.
7. Client polls `GET /briefing/{run_id}`.
8. Client downloads whitelisted files via `GET /outputs/{run_id}/{filename}`.
9. Operators can inspect and maintain job metadata:
   - `GET /jobs?limit=20&cursor=0&status=failed&q=keyword`
   - optional filters: `created_from`, `created_to`, `error_category`, `provider`
   - `GET /jobs/{run_id}`
   - `GET /jobs/{run_id}/events?limit=50&cursor=0`
   - `GET /jobs/{run_id}/metrics`
   - `DELETE /jobs/{run_id}` (metadata only)
   - `POST /jobs/cleanup`
   - `POST /jobs/{run_id}/retry`
   - `POST /jobs/{run_id}/cancel`
10. Operators can inspect and append the operator audit trail:
   - `GET /ops/audit-trail?limit=50&cursor=0`
   - `POST /ops/audit-trail`
   - payload: `action`, `result`, optional `run_id`, optional `metadata`
   - this log is append-only; there is no delete endpoint.
11. Retry lineage is persisted in `JobStore`:
   - retried jobs store `source_run_id` (parent failed run).
   - this enables operational traceability for repeated retries/chains.
12. Jobs admin endpoints expose explicit response contracts in OpenAPI:
   - list: `items`, `count`, `next_cursor`
   - detail: `job`, `status_file`, `events`
   - retry/cancel/delete/cleanup: stable typed payloads
13. Job lifecycle events are persisted in SQLite:
   - table: `job_events`
   - automatic writes on `create_job` and `update_status`
   - `GET /jobs/{run_id}` returns latest events first for operator traceability.
14. Run metrics are also indexed in SQLite for operational queries:
   - tables: `job_stage_metrics`, `provider_calls`, `prompt_runs`
   - source of truth remains `outputs/{run_id}/run_metrics.json`
   - the API syncs the index when a background run finishes or when an existing job with metrics is inspected.
15. Final outputs are indexed in SQLite for DB-first operation:
   - tables: `job_outputs`, `job_artifacts`, `briefing_records`
   - source artifacts remain on disk for download compatibility
   - API-triggered runs persist briefing JSON, row24-equivalent data and artifact paths after pipeline completion.

For API-triggered runs, status, final exports and `run_metrics.json` are written under the same `outputs/{run_id}` directory. CLI and notebook runs use the active project's configured output directory unless `output_dir` is passed explicitly.

Before any provider call, `run_full_pipeline()` validates runtime inputs through `seo_pipeline/input_validation.py` (keyword, URL and execution limits). Invalid values fail fast with a validation error.
The pipeline also builds typed internal stage contracts (`PipelineInput`, `KeywordSet`, `CompetitorSet`, `EnrichmentSet`, `BriefingPlan`) to keep stage handoff consistent.

## Status Values

Typical states:

- `queued`
- `running`
- `done`
- `failed`

Allowed transitions:

- `queued -> queued|running|failed`
- `running -> running|done|failed`
- `done -> done`
- `failed -> failed`

API lifecycle writes go through `api.job_lifecycle.JobLifecycleService`. The service keeps the current FastAPI background-task backend but centralizes enqueue, start, terminal failure, cancellation and stale-running detection so a future queue backend has one integration point.

The status payload includes:

- `status`
- `step`
- `message`
- `percent`
- `error_category` (only when failed)

## Generated Artifacts

Common files:

- `status.json`
- `run_metrics.json`
- `serp_raw.json`
- `audit_report.json`
- briefing JSON
- briefing Markdown
- row24 CSV
- row24 XLSX

`run_metrics.json` now includes per-stage observability fields:

- `provider`
- `status`
- `retries`
- `items_processed`
- `error_category` (when a stage fails)
- audit-specific fields: `slowest_item_url`, `slowest_item_ms`, `failed_urls`
- quality gates summary:
  - `quality_gates.passed`
  - `quality_gates.results[]` (`gate`, `passed`, `message`, `severity`)
  - `quality_gates.failed_count`
- quorum summary:
  - `quorum.decision` (`continue` or `fail`)
  - `quorum.enforce`
  - `quorum.checks[]` with observed/required counts
  - `quorum.failed_count`
- prompt run summary:
  - `prompt_run.key`
  - `prompt_run.version`
  - `prompt_run.model`
  - `prompt_run.temperature`
  - `prompt_run.planner_version`
  - `prompt_run.mode` (`planner_writer`)
- cost summary:
  - `costs.currency`
  - `costs.total_estimated_cost_usd`
  - `costs.unknown_cost_estimate_count`
  - `costs.estimates[]` with provider, service, calls, token estimates and estimated cost.
  - OpenAI estimates use serialized prompt/output token approximation and static model pricing; provider-specific SEMrush/SERP/Sheets prices are marked unknown unless reconciled externally.

`GET /jobs/{run_id}` also returns `cost_summary` when `run_metrics.json` exists for that run.
SQLite stores a queryable copy of stage metrics, provider call estimates and prompt run metadata so future admin endpoints can build timelines without changing the artifact contract.
`GET /jobs/{run_id}/metrics` returns that persisted timeline as `stage_metrics`, `provider_calls`, `prompt_run` and an aggregate `summary`.
SQLite also stores final briefing metadata and artifact references so operators can query completed work without relying on Google Sheets.

## SLO And Alert Groundwork

SLO evaluation is implemented in `seo_pipeline/slo.py` and operates on windows of `run_metrics.json` payloads. Default thresholds:

- success rate: `>= 95%`
- p95 run duration: `<= 900s`
- retry rate: `<= 20%` of runs with any retry
- categorized failure rate: `<= 10%`

First-response runbook:

1. Check `/jobs?limit=50&status=failed` for recent failures.
2. Inspect `GET /jobs/{run_id}` and `GET /jobs/{run_id}/events`.
3. Download `run_metrics.json` and compare slow stages, retries, `error_category`, `quality_gates`, `quorum` and `costs`.
4. If retry rate spikes, inspect provider-specific stages before changing prompt/model settings.
5. If p95 duration spikes, compare `duration_seconds` by stage and prioritize SEMrush, SERP, audit or OpenAI based on the slowest stage.

Provider retries use a shared policy in `seo_pipeline/vendors/retry_policy.py`: transient network, timeout, rate-limit and 5xx/provider-unavailable failures are retryable; auth, quota and validation/configuration failures are terminal and should fail fast with a categorized error.

## LLM Gateway

Briefing generation now goes through `seo_pipeline/llm/` instead of calling provider SDKs directly from the pipeline. The OpenAI adapter preserves current structured-output behavior and records provider/model metadata in `prompt_run`. Future adapters should implement the same structured generation contract and return a validated `SEOBriefing`.

Operational endpoint:

```bash
curl -H "X-API-Key: replace_with_api_key" "http://localhost:8000/ops/slo?limit=50"
```

The dashboard served at `/ops` also shows the latest SLO evaluation for the selected list limit.

## Cache Management

Provider cache files live under the configured `cfg.cache_dir` (`data/cache` by default). Inspect cache state:

```bash
python tools/cache_admin.py inspect
```

Clear cache files:

```bash
python tools/cache_admin.py clear --yes
```

The clear command resolves the cache root before deleting and refuses to operate on filesystem root. It removes cache files and empty subdirectories only inside the configured cache directory.

## Batch Keyword Runs

Run multiple keywords from CSV or JSON:

```bash
python tools/batch_runner.py data/batch_keywords.csv --batch-id manual_20260514
```

CSV input requires a `keyword` column and may include `target_url`, `upload_to_sheets`, `related_limit`, `serp_num`, `top_competitors_count` and `gsc_months_back`.

JSON input can be either a list of objects or an object with an `items` list:

```json
{
  "items": [
    {"keyword": "content marketing", "upload_to_sheets": false}
  ]
}
```

Each keyword receives an isolated run id under the batch output directory. Failures do not stop the batch by default; use `--stop-on-error` when the first failed keyword should halt execution. The runner writes `batch_summary.json` next to the per-keyword run directories.
Use `--resume` with the same `--batch-id` and output directory to skip items already marked `done` in `batch_manifest.json` and retry only incomplete items. The summary includes `done`, `failed`, `skipped`, per-item timestamps and `error_summary`.

Generated files are ignored by Git.

## Docker

Build:

```bash
docker build -t seo-brief-pipeline .
```

Run with env vars:

```bash
docker run --rm -p 8000:8000 \
  -e API_KEY="replace_with_strong_api_key_at_least_20_chars" \
  -e SEMRUSH_TOKEN="replace_with_semrush_token" \
  -e SERPAPI_KEY="replace_with_serpapi_key" \
  -e OPENAI_API_KEY="replace_with_openai_key" \
  seo-brief-pipeline
```

Use mounted volumes for `outputs/`, `data/` and `credentials/` when persistence is required.

## Debugging

Safe checks:

```bash
pytest -q
python -m json.tool data/projects.json
python -m json.tool data/clients.json
```

Inspect a run:

```bash
cat outputs/replace_with_run_id/status.json
```

Avoid:

- `cat .env`
- printing `os.environ`
- logging request headers containing API keys

## Operations Checklist

Before deploy:

```bash
python -m pip install -e ".[test]"
pytest -q
git diff --check
git ls-files '.env' '*__pycache__*' '*.pyc'
```

After deploy:

```bash
curl http://localhost:8000/health
curl -H "X-API-Key: replace_with_api_key" http://localhost:8000/docs
curl -H "X-API-Key: replace_with_api_key" "http://localhost:8000/jobs?limit=10"
curl -H "X-API-Key: replace_with_api_key" "http://localhost:8000/jobs/replace_with_run_id"
curl -H "X-API-Key: replace_with_api_key" "http://localhost:8000/jobs/replace_with_run_id/events?limit=20&cursor=0"
curl -X POST -H "X-API-Key: replace_with_api_key" -H "Content-Type: application/json" -d "{\"max_age_days\":30,\"statuses\":[\"done\",\"failed\"]}" http://localhost:8000/jobs/cleanup
```

For a real briefing, start with `upload_to_sheets=false` until provider credentials and output files are verified.

## Admin Jobs Operational Checklist

1. List recent jobs and filter failures:

```bash
curl -H "X-API-Key: replace_with_api_key" "http://localhost:8000/jobs?limit=50&status=failed"
```

2. Inspect a specific failed run (check `error_category`, `message`, `source_run_id`):

```bash
curl -H "X-API-Key: replace_with_api_key" "http://localhost:8000/jobs/replace_with_run_id"
```

3. Retry only failed runs and track lineage:

```bash
curl -X POST -H "X-API-Key: replace_with_api_key" "http://localhost:8000/jobs/replace_with_run_id/retry"
```

4. Cancel only queued/running runs:

```bash
curl -X POST -H "X-API-Key: replace_with_api_key" "http://localhost:8000/jobs/replace_with_run_id/cancel"
```

5. Run bounded retention cleanup for terminal states:

```bash
curl -X POST -H "X-API-Key: replace_with_api_key" -H "Content-Type: application/json" -d "{\"max_age_days\":30,\"statuses\":[\"done\",\"failed\"]}" http://localhost:8000/jobs/cleanup
```
