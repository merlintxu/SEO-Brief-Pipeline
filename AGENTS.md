# Agent Guide

This file is the entrypoint for coding agents working in this repository.

## Current State

- Main branch is expected to be green in GitHub Actions.
- `.env` is local-only and ignored. Never print, stage, commit or summarize its values.
- Generated artifacts are ignored: `outputs/`, `runs/`, `logs/`, caches, credentials and bytecode.
- Tests are under `tests/` and should be run with `pytest -q`.

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
