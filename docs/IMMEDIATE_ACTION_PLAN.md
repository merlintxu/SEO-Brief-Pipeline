# Immediate Action Plan

This plan focuses on the next operational steps after the current hardening and documentation pass.

## Objective

Stabilize the SEO Brief Pipeline for reliable API execution, make future agent work safer, and prepare the project for production-oriented iteration without changing the public API unnecessarily.

## Current Baseline

- Tests pass locally with `pytest -q`.
- `.env` is ignored and must remain local-only.
- API-triggered runs write status, artifacts and `run_metrics.json` under the same run directory.
- Downloads are restricted by the API whitelist.
- Downloadable artifact names are centralized in `seo_pipeline/artifacts.py`.
- Required runtime providers are validated through `seo_pipeline/runtime_validation.py`.
- SERP responses have an initial provider-neutral `SerpSnapshot` summary for metrics and future contracts.
- Pipeline metrics include per-stage `provider`, `status`, `retries`, `items_processed` and `error_category`.
- Failed status payloads include `error_category` for faster diagnosis.
- GSC click totals map to `GscPage.clicks`.
- Google Sheets accepts either a raw spreadsheet id or a full Google Sheets URL.
- Documentation entrypoints exist for agents, project map, external APIs, runtime operations, pipeline deep dive and roadmap.

## Next 24 Hours

1. Publish the current branch through a PR.
2. Verify GitHub Actions passes on the PR.
3. Confirm the PR diff does not include `.env`, credentials, generated outputs, bytecode or local logs.
4. Smoke test the API locally:
   - start the API with a valid local `API_KEY`;
   - call `POST /briefing`;
   - poll `GET /briefing/{run_id}`;
   - download `run_metrics.json` through `GET /outputs/{run_id}/run_metrics.json`.
5. Review `docs/PIPELINE_DEEP_DIVE.md` and `docs/IMMEDIATE_ACTION_PLAN.md` as the source of truth for the next implementation cycle.

## Next 3-5 Days

1. Extend SERP normalization:
   - add SerpAPI and DataForSEO fixture tests;
   - move more downstream consumers from raw SERP JSON to `SerpSnapshot`;
   - enforce typed SERP payload parsing (`SerpRawPayload`) before normalization;
   - preserve raw provider payload for debugging.
2. Continue operational observability:
   - add log shipping/aggregation for structured events keyed by `run_id`;
   - add dashboards/alerts for `error_category` and retry spikes;
   - track rolling stage latency baselines from `run_metrics.json`.
3. Strengthen export contracts:
   - add snapshot tests for Markdown and CSV exports.
4. Finish controlled UTF-8 cleanup:
   - clean docs first;
   - clean user-facing strings second;
   - avoid mixing encoding cleanup with behavior changes.

## Next 2-4 Weeks

1. Replace in-process background tasks with durable job state using SQLite or Redis.
   - Current step: SQLite store module exists (`api/job_store.py`) with create/update/get/list.
   - Next step: wire create/update reads in `api/main.py` while keeping `status.json` backward compatible.
2. Add resumable batch keyword processing.
3. Add provider cache TTL and safe cache cleanup commands.
4. Add deployment smoke tests for auth, status polling and downloads.
5. Add briefing quality checks for minimum sections, FAQ coverage, unique angle and schema completeness.

## Acceptance Criteria

- CI passes on every PR.
- No tracked `.env`, bytecode, generated outputs or credential-like values.
- A full mocked pipeline run writes all expected artifacts and metrics.
- API status and download routes read from the same run directory.
- Provider failures are categorized without printing secret values.
- Future agents can start from `AGENTS.md` and `docs/PIPELINE_DEEP_DIVE.md` without rediscovering system structure.

## Commands Before Publishing

```bash
pytest -q
git diff --check
git ls-files '.env' '*__pycache__*' '*.pyc'
```

The last command must return no output.
