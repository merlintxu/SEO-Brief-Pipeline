# Runtime Operations

## Local Setup

Install for development:

```bash
python -m pip install -e ".[test]"
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

## Request Lifecycle

1. Client sends `POST /briefing` with `X-API-Key`.
2. API validates `BriefingRequest`.
3. API creates `run_id` and writes `outputs/{run_id}/status.json`.
4. API schedules a FastAPI background task.
5. Background task calls `run_full_pipeline()`.
6. Pipeline updates status as it moves through SEMrush, SERP, audit, GSC, anchors, OpenAI, export and optional Sheets.
7. Client polls `GET /briefing/{run_id}`.
8. Client downloads whitelisted files via `GET /outputs/{run_id}/{filename}`.

For API-triggered runs, status, final exports and `run_metrics.json` are written under the same `outputs/{run_id}` directory. CLI and notebook runs use the active project's configured output directory unless `output_dir` is passed explicitly.

Before any provider call, `run_full_pipeline()` validates runtime inputs through `seo_pipeline/input_validation.py` (keyword, URL and execution limits). Invalid values fail fast with a validation error.

## Status Values

Typical states:

- `queued`
- `running`
- `done`
- `failed`

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
```

For a real briefing, start with `upload_to_sheets=false` until provider credentials and output files are verified.
