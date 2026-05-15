# External APIs

Do not place real tokens in this document. Use environment variables, ignored credentials files or deployment secrets.

## SEMrush

Code: `seo_pipeline/vendors/semrush_io.py`

Purpose:

- Fetch related keywords and search volume.
- Check API unit balance before fetching.

Endpoints:

- `https://www.semrush.com/users/countapiunits.html`
- `https://api.semrush.com`

Required credential:

- `SEMRUSH_TOKEN` or `ClientConfig.semrush_token`

Important params:

- `type=phrase_related`
- `phrase={keyword}`
- `database={default_database}`
- `display_limit={related_limit}`
- `export_columns=Ph,Nq`

Cache:

- CSV cache under `cfg.cache_dir`.
- Freshness controlled by `DEFAULT_CACHE_TTL_DAYS`.

Expected failures:

- invalid token: `ERROR 122`
- insufficient units
- network timeout
- empty response

## SerpAPI

Code: `seo_pipeline/vendors/serp_io.py`

Purpose:

- Fetch Google SERP.
- Include AI Overview sources when available.
- Provide organic results, PAA and related searches in raw provider response.

Required credential:

- `SERPAPI_KEY` or `ClientConfig.serpapi_key`

Important params:

- `engine=google`
- `q={keyword}`
- `gl={default_gl}`
- `hl={default_hl}`
- `num={serp_num}`
- `include_ai_overview=true`

Expected failures:

- missing/invalid key
- exhausted quota
- provider error field in response
- network failure

Fallback:

- DataForSEO is attempted only if both DataForSEO credentials are configured.

## DataForSEO

Code: `seo_pipeline/vendors/dataforseo_serp.py`

Purpose:

- Optional fallback for Google organic SERP.
- Normalizes results to a SerpAPI-like dictionary.

Endpoint:

- `https://api.dataforseo.com/v3/serp/google/organic/live/advanced`

Required credentials:

- `DFSP_USERNAME` / `ClientConfig.dataforseo_login`
- `DFSP_PASSWORD` / `ClientConfig.dataforseo_password`

Normalized output:

- `search_parameters`
- `organic_results`
- `ai_overview`
- `people_also_ask`
- `related_searches`

Expected failures:

- missing login or password
- non-200 HTTP status
- DataForSEO task status not `20000`
- malformed response

## OpenAI

Code: `seo_pipeline/blueprint.py`

Purpose:

- Generate final SEO briefing as a structured `SEOBriefing` Pydantic model.

Required credential:

- `OPENAI_API_KEY` or `ClientConfig.openai_key`

Current call:

```python
client.beta.chat.completions.parse(
    model="gpt-4o-2024-11-20",
    response_format=SEOBriefing,
)
```

Inputs:

- keyword
- search volume
- SEMrush keyword data
- raw SERP data
- audit report
- anchors
- optional cannibalization notes

Expected failures:

- invalid key
- quota/rate limit
- model access issue

## Ollama

Code: `seo_pipeline/llm/ollama_adapter.py`

Purpose:

- Run the structured briefing step against a local or cloud-hosted Ollama-compatible HTTP endpoint.

Configuration:

- `LLM_PROVIDER=ollama`
- `OLLAMA_BASE_URL` (default `http://localhost:11434`)
- `OLLAMA_MODEL`
- Preferred project runtime:
  - `data/projects.json` -> `runtime.llm.provider=ollama`
  - `data/projects.json` -> `runtime.llm.model`
  - optional `data/projects.json` -> `runtime.llm.base_url`

Operational notes:

- Ollama must return JSON that validates against `SEOBriefing`.
- Automated tests mock the HTTP API and do not require a local Ollama server.

## Anthropic

Code: `seo_pipeline/llm/anthropic_adapter.py`

Purpose:

- Run the structured briefing step through Anthropic Messages API while preserving the same `SEOBriefing` validation contract.

Configuration:

- `LLM_PROVIDER=anthropic`
- `ANTHROPIC_API_KEY`
- `ANTHROPIC_MODEL` (defaults to `claude-3-5-sonnet-latest` when not provided)
- `ANTHROPIC_BASE_URL` (optional, defaults to `https://api.anthropic.com`)
- Preferred project runtime:
  - `data/projects.json` -> `runtime.llm.provider=anthropic`
  - `data/projects.json` -> `runtime.llm.model`
  - optional `data/projects.json` -> `runtime.llm.base_url`

Operational notes:

- Anthropic responses must contain JSON text that validates against `SEOBriefing`.
- Automated tests mock HTTP calls and do not call Anthropic.
- structured output does not satisfy `SEOBriefing`

## Project Runtime Provider Order

Each project can define the provider/model defaults used before launching a
briefing:

```json
{
  "runtime": {
    "llm": {
      "provider": "openai",
      "model": "gpt-4o-2024-11-20",
      "prompt_version": "v1"
    },
    "providers": {
      "serp": {
        "provider_order": ["serpapi", "dataforseo"]
      }
    }
  }
}
```

This makes model choice and SERP API order explicit per project. Environment
variables still provide secrets and operational endpoints, but the active
project runtime is the default execution plan validated by the API preflight.

## Google Search Console

Code: `seo_pipeline/vendors/gsc_io.py`

Purpose:

- Detect keyword cannibalization by query and page.
- Compute weighted position by impressions.

Credential:

- Service account JSON path in `ClientConfig.gsc_sa_path`

Scope:

```text
https://www.googleapis.com/auth/webmasters.readonly
```

Inputs:

- `site_url`
- `start_date`
- `end_date`
- `sa_json_path`
- optional delegated `subject`

Expected failures:

- missing service account file
- service account not added to GSC property
- wrong `site_url`
- Search Console API disabled

Implementation note:

- Search Console `clicks` are mapped to the `GscPage.clicks` model field.

## Google Sheets

Code: `seo_pipeline/vendors/sheets_io.py`

Purpose:

- Upsert `SheetRow24` into a spreadsheet tab.

Credential:

- Service account JSON path in `ClientConfig.sheets_sa_path`

Operational status:

- Optional export only. DB-first mode does not require Google Sheets for normal operation.
- New API/Gradio runs default to `upload_to_sheets=false`.

Inputs:

- spreadsheet id
- tab name
- headers
- key columns
- row data

Behavior:

- Creates missing worksheet.
- Ensures headers.
- Finds by first key column.
- Updates matching composite key or appends a new row.

Expected failures:

- missing service account file
- sheet not shared with service account
- invalid spreadsheet id
- Google API quota or permission errors

## Sentry

Code: `api/main.py`

Purpose:

- Optional API monitoring for FastAPI/Starlette.

Activation:

- Set `SENTRY_DSN`.

Optional vars:

- `SENTRY_ENVIRONMENT`
- `SENTRY_RELEASE`

Default behavior:

- If `SENTRY_DSN` is empty, Sentry is not initialized.
