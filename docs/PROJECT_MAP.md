# Project Map

## Top-Level Files

- `README.md`: user-facing overview, setup and API examples.
- `AGENTS.md`: instructions for agents and maintainers.
- `ARCHITECTURE.md`: architecture, runtime flow and current technical debt.
- `TROUBLESHOOTING.md`: operational diagnostics.
- `SECURITY.md`: credential management and incident response.
- `DEPLOYMENT.md`: deployment guidance.
- `Dockerfile`, `docker-compose.yml`, `deploy.sh`: container and deployment assets.
- `pyproject.toml`, `requirements.txt`: packaging and dependencies.
- `client_manager.py`: interactive local CLI.

## API Package

`api/main.py`

- Creates the FastAPI app.
- Validates `API_KEY` at import time.
- Initializes Sentry when `SENTRY_DSN` exists.
- Adds rate limiting and CORS middleware.
- Defines `/health`, `/briefing`, `/briefing/{run_id}` and `/outputs/{run_id}/{filename}`.

`api/schemas.py`

- `BriefingRequest`: keyword, target URL, Sheets flag, SEMrush related limit and SERP count.
- `BriefingResponse`: run id, keyword, output directory and file URLs.

`api/rate_limiter.py`

- `RateLimiter`: in-memory token bucket per IP.
- `RateLimitMiddleware`: Starlette middleware wrapper.

## Core Package

`seo_pipeline/pipeline.py`

- `run_full_pipeline()` is the central orchestrator.
- It pulls config, calls vendors, writes intermediate artifacts, builds the briefing and exports outputs.
- Uses `retry_call()` around SEMrush, SERP, audit and GSC calls.

`seo_pipeline/config.py`

- Defines `ClientConfig`, `ProjectConfig` and singleton `PipelineConfig`.
- Loads `data/clients.json` and `data/projects.json`.
- Uses `.env` via `load_dotenv()`.

`seo_pipeline/models.py`

- Pydantic contracts for vendor data, audit reports, GSC reports, anchors, briefing output and row24 export.

`seo_pipeline/constants.py`

- Default limits, cache TTL, spreadsheet headers, key columns and prompt constants.

`seo_pipeline/blueprint.py`

- `generate_briefing()` calls OpenAI structured output parsing into `SEOBriefing`.
- `save_briefing_markdown()` renders human-readable Markdown.

`seo_pipeline/row24.py`

- `build_row24()` maps briefing, SERP and anchors into the 24-column sheet model.

`seo_pipeline/exporter.py`

- `export_all_formats()` writes briefing JSON, briefing Markdown, row24 CSV and row24 XLSX.

`seo_pipeline/anchors.py`

- Extracts and scores phrases for primary, secondary and internal anchor suggestions.

## Audit Package

`seo_pipeline/audit/content_audit.py`

- `_fetch_html()` downloads competitor pages.
- `audit_single_url()` extracts page metadata.
- `audit_urls()` audits multiple URLs concurrently.

Data returned: `AuditReport` containing `AuditEntry` records with URL, status code, title, H1, meta description, word count, headings and schema signals.

## Vendor Package

`seo_pipeline/vendors/semrush_io.py`

- `SemrushClient`.
- Checks SEMrush units.
- Fetches related keywords with disk cache.
- Returns `SemrushResults`.

`seo_pipeline/vendors/serp_io.py`

- `search_raw()`: SerpAPI primary, DataForSEO fallback when credentials exist.
- `extract_top_urls()`: organic URLs plus AI Overview citations.
- `extract_competitor_domains()`: normalized domain extraction excluding own domain.
- `normalize_domain()`: removes scheme, path, port and leading `www`.

`seo_pipeline/vendors/dataforseo_serp.py`

- `fetch_serp_dataforseo()`: Google organic live advanced endpoint, normalized to SerpAPI-like shape.

`seo_pipeline/vendors/gsc_io.py`

- `build_service()`: builds Search Console service from service account.
- `fetch_cannibalization()`: aggregates query/page performance into cannibalization report.

`seo_pipeline/vendors/sheets_io.py`

- `SheetHandler`: opens spreadsheets, creates tabs, ensures headers and upserts rows.
- `upsert_to_sheet()`: high-level helper used by the pipeline.

`seo_pipeline/vendors/scrapers.py`

- Failover scraping helper placeholder.

## Utilities

`seo_pipeline/utils/io.py`

- `ensure_dir`, `save_json`, `load_json`, `save_text`.

`seo_pipeline/utils/text.py`

- Slugs, whitespace normalization, smart truncation, deduplication and n-grams.

`seo_pipeline/utils/retry.py`

- `retry_call()` with exponential backoff, jitter, injectable sleep and retry callback.

`seo_pipeline/utils/logging.py`

- Central logger setup.

## Data Flow And Artifacts

Input:

- API request or CLI call with `keyword`, optional `target_url`, limits and Sheets flag.

Intermediate:

- SEMrush results: in-memory `SemrushResults`.
- SERP raw JSON: `serp_raw.json`.
- Competitor audit: `audit_report.json`.
- Optional GSC cannibalization: in-memory and included in briefing context.
- Anchors: in-memory `AnchorSet`.

Final:

- Briefing model: `SEOBriefing`.
- Row model: `SheetRow24`.
- Files: JSON, Markdown, CSV, XLSX, `status.json` and `run_metrics.json`.
- Optional Sheets row in tab `Briefings 2025`.

## Tests

- `test_api_background.py`: API background pipeline behavior.
- `test_api_security.py`: API key, static mount absence and download guard.
- `test_rate_limiter.py`: request throttling.
- `test_serp_io.py`: domain normalization and fallback behavior.
- `test_retry_utils.py`: retry behavior and jitter.
- `test_pipeline_errors.py`: status writes on vendor failures.
- `test_exporter.py`, `test_models.py`, `test_utils_io.py`: contracts and utilities.
