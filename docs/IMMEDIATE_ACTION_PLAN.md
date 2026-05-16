# Immediate Action Plan

This plan focuses on the next operational steps after the current hardening and documentation pass.

## Objective

Stabilize the SEO Brief Pipeline for reliable API execution, make future agent work safer, and execute the UX/UI redesign described in `docs/UX_UI_REDESIGN_PLAN.md` without changing the public API unnecessarily.

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
- Gradio now supports local client/project management, provider connection checks and briefing launch context.
- Existing-page runs can optionally enrich output with GA4 URL metrics when project/client configuration is present.
- Global runtime settings can be stored in ignored `config/runtime_settings.json`.
- Projects inherit client base-domain and locale defaults unless they define overrides.
- Gradio can discover Google Sheets through Drive metadata for the configured service account.
- A global UX/UI redesign plan now exists in `docs/UX_UI_REDESIGN_PLAN.md`.
- Documentation entrypoints exist for agents, project map, external APIs, runtime operations, pipeline deep dive and roadmap.
- Documentation governance is mandatory: each functional change must update `AGENTS.md` plus relevant docs under `docs/`.
- Repository hygiene now rejects tracked `.env`, bytecode, Python cache files
  and `*.egg-info`; obsolete root-level manual smoke scripts were removed in
  favor of `tests/` and documented `tools/` commands.

## Next 24 Hours

1. Smoke test the integrated UX baseline from `docs/UX_UI_REDESIGN_PLAN.md`.
2. Review whether any UX1-UX8 slice should be split into separate GitHub PRs before merge.
3. Verify GitHub Actions passes on the PR.
4. Confirm the PR diff does not include `.env`, credentials, generated outputs, bytecode or local logs.
5. Smoke test the API locally:
   - start the API with a valid local `API_KEY`;
   - call `POST /briefing`;
   - poll `GET /briefing/{run_id}`;
   - download `run_metrics.json` through `GET /outputs/{run_id}/run_metrics.json`.
6. Smoke test the Gradio operator app:
   - launch `.\.venv\Scripts\python -m apps.gradio_app`;
   - create or update global settings, then a client/project with test-safe values;
   - run connection checks with mocks or local-safe credentials;
   - discover Sheets visible to the service account if Google credentials are available;
   - launch a `new_page` briefing and inspect job detail.
7. Review `docs/UX_UI_REDESIGN_PLAN.md`, `docs/PIPELINE_DEEP_DIVE.md`, `docs/GRADIO_OPERATOR_WORKFLOWS.md` and `docs/IMMEDIATE_ACTION_PLAN.md` as the source of truth for the next implementation cycle.

## Next 3-5 Days

1. Harden the integrated UX baseline:
   - verify Home setup checklist on a clean repo;
   - verify active context propagation;
   - verify preflight and launch validation against test-safe credentials.
2. Extend SERP normalization:
   - add SerpAPI and DataForSEO fixture tests;
   - move more downstream consumers from raw SERP JSON to `SerpSnapshot`;
   - enforce typed SERP payload parsing (`SerpRawPayload`) before normalization;
   - preserve raw provider payload for debugging.
3. Continue operational observability:
   - add log shipping/aggregation for structured events keyed by `run_id`;
   - add dashboards/alerts for `error_category` and retry spikes;
   - track rolling stage latency baselines from `run_metrics.json`.
4. Strengthen export contracts:
   - add snapshot tests for Markdown and CSV exports.
5. Finish controlled UTF-8 cleanup:
   - clean docs first;
   - clean user-facing strings second;
   - avoid mixing encoding cleanup with behavior changes.
6. Decide whether global/client/project management should remain Gradio-only or be promoted to authenticated API endpoints.

## Next 2-4 Weeks

1. Iterate on visual polish and operator ergonomics after real local usage.
2. Replace in-process background tasks with durable job state using SQLite or Redis.
   - Current step: SQLite store module exists (`api/job_store.py`) with create/update/get/list.
   - Next step: wire create/update reads in `api/main.py` while keeping `status.json` backward compatible.
3. Add typed contracts for GA4/GSC enrichment payloads if these signals become prompt inputs.
4. Add deployment smoke tests for auth, status polling, downloads and Gradio callback coverage.
5. Add briefing quality checks for minimum sections, FAQ coverage, unique angle and schema completeness.
6. Evaluate durable queue backend once Gradio/API operator usage exceeds local background execution.

## Acceptance Criteria

- CI passes on every PR.
- No tracked `.env`, bytecode, generated outputs or credential-like values.
- A full mocked pipeline run writes all expected artifacts and metrics.
- API status and download routes read from the same run directory.
- Provider failures are categorized without printing secret values.
- Future agents can start from `AGENTS.md` and `docs/PIPELINE_DEEP_DIVE.md` without rediscovering system structure.
- Every merged PR includes synchronized updates to status docs and `AGENTS.md`.
- The UX/UI redesign PRs leave the operator app usable after each merge.

## Commands Before Publishing

```bash
pytest -q
git diff --check
git ls-files '.env' '*__pycache__*' '*.pyc' '*.egg-info'
```

The last command must return no output.
