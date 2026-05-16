# Gradio Operator Workflows

This document describes the local Gradio app used by operators to configure clients,
projects, provider connections and briefing jobs.

The current implementation follows the integrated UX redesign baseline tracked
in `docs/UX_UI_REDESIGN_PLAN.md`.

Launch:

```powershell
.\.venv\Scripts\python -m apps.gradio_app
```

Alternative:

```powershell
$env:PYTHONPATH='.'
python .\apps\gradio_app.py
```

## Information Model

The Gradio app follows the operational hierarchy:

```text
Client
  -> Project
      -> Runtime defaults
      -> Provider connection checks
      -> Briefing jobs
          -> Keyword
          -> Target URL optional for new pages, required for existing pages
          -> Outputs and metrics
```

Configuration is still stored in:

- `data/clients.json`
- `data/projects.json`
- `config/runtime_settings.json` for local global provider credentials and base URLs.

`config/runtime_settings.json` is ignored by Git and may contain local secrets.
The UI writes through `seo_pipeline.config` models, so the JSON files remain the
source of truth for local operation.

## Console Structure

The app is organized around operator tasks:

- **Home**: setup checklist, active client/project context, clients, projects and recent runs.
- **Settings**: global provider credentials and model references.
- **Clients**: client list plus editor.
- **Projects**: project list, editor, effective config preview, duplication and Drive discovery.
- **Preflight**: config-only and live provider checks for the selected project.
- **Launch**: new-page/existing-page run preview and validated launch.
- **Runs**: filterable run table, details, metrics, artifacts and safe admin actions.

The preferred workflow is:

1. Start at **Home** and confirm the next setup action.
2. Configure providers in **Settings**.
3. Create or load a client in **Clients**.
4. Create or load a project in **Projects** and review the effective configuration.
5. Run **Preflight** checks.
6. Preview and launch from **Launch**.
7. Review results in **Runs**.

## Global Settings Tab

Use this tab for provider settings shared by all clients:

- SEMrush token.
- SerpAPI key.
- OpenAI key.
- Anthropic key.
- LLM base URL, normally `http://localhost:11434`.
- DataForSEO login/password.

Client-specific credentials can still exist for backwards compatibility, but new
local operation should prefer global settings plus client/project non-secret
defaults.

## Clients Tab

Use this tab to create or update client-level configuration.

Editing flow:

1. Click **Refresh clients** to reload the client dropdown from `data/clients.json`.
2. Select an existing client in **Existing client**.
3. Click **Load selected client**. The form is populated with the stored values.
4. Edit the fields and click **Save client**.

Saving with the same `client_id` updates that client. Changing `client_id`
creates a separate client entry; it does not rename existing project references.

Client fields:

- `client_id`: stable identifier used by jobs and projects.
- `name`: human-readable client name.
- default base domain inherited by projects.
- GSC service account path.
- Sheets service account path.
- Default SEMrush database and Google locale settings.

SEMrush database, Google `gl` and Google `hl` are dropdowns backed by
`seo_pipeline/options.py`; operators cannot type arbitrary unsupported values.

## Projects Tab

Use this tab to create or update projects under a client.

Editing flow:

1. Optionally enter a `client_id` to filter the project list by client.
2. Click **Refresh projects** to reload the dropdown from `data/projects.json`.
3. Select an existing project in **Existing project**.
4. Click **Load selected project**. The form is populated with the stored values.
5. Edit the fields and click **Save project**.

Saving with the same `project_id` updates that project. Changing `project_id`
creates a separate project entry. If `client_id` is changed, the project moves
under the new client ID and inherits that client's defaults where project fields
are left blank.

Project fields:

- `project_id`: stable identifier used by jobs.
- `client_id`: parent client.
- optional `base_domain` override. If blank, the client default base domain is used.
- optional SEMrush database, Google `gl` and Google `hl` overrides.
- `gsc_property`: Search Console property, when available.
- `ga4_property_id`: GA4 property ID, when available.
- `project_type`: vertical mode used by Google AI Search readiness checks.
- `sheets_id`: optional Google Sheets ID or URL.
- `output_dir`: project output directory for non-API runs.
- default LLM provider/model/base URL/prompt version.
- SERP providers selected with checkboxes instead of comma-separated text.

Prompt version is not exposed in the UI. The current production prompt bundle is
`v1`; the field remains in JSON for future prompt migrations and traceability.

Default LLM provider/model:

- provider: `ollama`
- model: `gemma4:26b`
- base URL: `http://localhost:11434`

Model dropdowns are constrained by provider. Current options were refreshed on
2026-05-15 from the official OpenAI model documentation, Anthropic model
documentation and Ollama model library. At that point OpenAI listed `gpt-5.5`
as the recommended frontier starting point, Anthropic recommended Claude Sonnet
4.5 as the balanced default, and Ollama listed `gemma4:26b` plus related Gemma 4
tags.

The **Activate project** action sets the in-process active context used by legacy
pipeline entry points.

The effective configuration preview shows inherited client values versus project
overrides before any run is launched.

Supported project types:

- `content`
- `ecommerce`
- `local`
- `saas`
- `marketplace`

For ecommerce/marketplace projects, the pipeline expects product and merchant
facts in the final brief. For local projects, it expects local business facts.

The duplicate action creates a new project from an existing project and keeps the
same client relationship unless the copy is edited afterwards.

The **Discover Sheets from Drive** action lists Google Sheets visible to the
client's service account through the Google Drive API. This is service-account
based discovery; full end-user OAuth Drive browsing is not implemented in the
local Gradio app.

## Connections Tab

This section is now exposed as **Preflight** in the UI.

The Preflight tab runs sanitized provider checks for one client/project pair.

Checks:

- SEMrush: one small keyword query.
- SERP: SerpAPI/DataForSEO query according to the project provider order.
- GSC: service account can list Search Console sites.
- GA4: Data API query against the configured property.
- Sheets: spreadsheet can be opened with the configured service account.
- LLM: provider configuration or local Ollama availability.

Automated tests mock provider calls. CI must not call real vendor APIs.

## Run Tab

This section is now exposed as **Launch** in the UI.

Use the Launch tab to preview and launch one briefing job.

Required:

- client ID
- project ID
- briefing type
- keyword

Briefing types:

- `new_page`: keyword-first briefing for a page that does not exist yet. Target URL is optional.
- `existing_page`: optimization briefing for an existing URL. Target URL is required.

The preview step shows blocking validation errors before a job is created. This
prevents invalid existing-page runs from entering SQLite job history.

Each Gradio-created job persists the operator context in SQLite:

- `client_id`
- `project_id`
- `brief_type`
- `target_url`

This metadata is shown in job lists and details and is available through the API
job response schema.

## Jobs And Detail Tabs

This section is now exposed as **Runs** in the UI.

The Runs tab lists recent runs from SQLite. The detail panel shows:

- job status and operator context,
- DB-first briefing record,
- output path,
- persisted stage metrics,
- provider calls,
- prompt metadata,
- artifacts,
- lifecycle timeline.

Allowed admin actions from the UI:

- cancel queued/running runs,
- delete job metadata,
- cleanup old terminal job metadata.

Generated file artifacts remain on disk for compatibility with the existing API
download flow.

## GA4 Enrichment

GA4 is optional. When a briefing is launched for an existing page and the active
project has `ga4_property_id` plus a client service account path, the pipeline
queries GA4 URL metrics and persists them in:

- pipeline result key: `ga4_url_metrics`
- `run_metrics.json` stage: `ga4`

GA4 failures are non-blocking. The stage is marked failed with an error category,
and the briefing continues.

## Google AI Search Readiness

Every run now produces `ai_search_readiness.json`.

For `new_page` runs, the readiness stage generates publishing requirements for
the future URL:

- crawlable/indexable URL,
- original value and evidence,
- useful media,
- structured data where eligible,
- project-type specific requirements,
- unsupported AEO/GEO tactics to avoid.

For `existing_page` runs, the pipeline also writes `target_audit_report.json`
after auditing the target URL. The readiness report summarizes technical,
content, media, structured data and agent-friendly signals.

The generated briefing is reviewed after creation and `run_metrics.json` stores
`brief_quality_review` with quality and myth-guardrail findings.
