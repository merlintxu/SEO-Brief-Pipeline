# UX/UI Redesign Plan

Status: implemented as the first integrated Gradio redesign baseline.

This plan resets the operator experience around a single goal: a new operator
must be able to install, configure, validate, run and review a SEO briefing from
the UI without editing JSON or reading internal implementation details.

## Current Diagnosis

The current project has strong backend foundations, but the UI is still shaped
like engineering tabs:

- Configuration, context selection, connection checks, execution and results are
  separated into independent surfaces.
- The active client/project context is implicit and must be re-entered in several
  places.
- Markdown tables are useful for diagnostics, but they are not good enough as
  the main editing and selection mechanism.
- Global settings, client defaults and project overrides exist, but the UI does
  not show an effective configuration preview before a run.
- New-page and existing-page briefings share the same form even though they have
  different validation and data expectations.
- Jobs and details are read-only markdown blocks instead of an operational work
  surface with filters, status, outputs and next actions.
- The existing `/ops` dashboard and Gradio app overlap. Operators should not need
  to know which surface owns which workflow.
- Documentation explains the implementation, but it does not yet define the
  product workflow as the source of truth.

## Target Operator Model

The final system should expose one coherent local operator console with these
primary workflows:

1. First-run setup:
   - check local environment,
   - enter provider credentials without displaying stored secret values,
   - verify LLM provider availability,
   - create the first client and project.
2. Client workspace:
   - select or create a client,
   - edit inherited defaults,
   - see projects and recent runs for that client.
3. Project workspace:
   - select or create a project,
   - edit project overrides,
   - connect GSC, GA4 and Sheets,
   - preview effective runtime configuration.
4. Briefing launcher:
   - choose project and brief type,
   - enter keyword and optional or required target URL,
   - run preflight checks,
   - launch the pipeline.
5. Run monitor:
   - view current status, stage progress, provider calls, costs and errors,
   - inspect artifacts and DB-first briefing output,
   - retry, cancel or clean up when allowed.
6. Knowledge and troubleshooting:
   - inline status messages,
   - clear provider failure categories,
   - links from UI sections to the relevant docs.

## Information Architecture

The UI should move from technical tabs to task areas:

```text
Home
  Setup checklist
  Active client/project context
  Recent runs and blocking issues

Settings
  Global providers
  LLM defaults
  Secret status only, no secret display

Clients
  Client list
  Client editor
  Client defaults
  Projects under client

Projects
  Project list filtered by client
  Project editor
  Effective config preview
  Google integrations
  Runtime defaults

Launch
  Client/project picker
  Brief type selector
  Keyword and target URL form
  Preflight summary
  Run action

Runs
  Filterable run table
  Run detail
  Timeline, metrics, costs and artifacts
  Admin actions
```

Gradio can remain the local-first implementation target for now, but the UI
structure must be independent of Gradio internals so a future web frontend can
reuse the same service layer and contracts.

## Design Principles

- One selected context: the operator picks a client and project once, and the UI
  uses that context across checks, launch and results.
- No raw IDs as primary UX: IDs stay visible and copyable, but names and filtered
  pickers drive navigation.
- Show inherited values: project screens must show whether a value is inherited
  from the client or overridden by the project.
- Validate before run: operators should see provider readiness and required
  fields before launching a pipeline.
- Secrets are write-only: the UI only shows configured/not configured states.
- Prefer structured components over markdown tables for editing, filtering and
  selection.
- Keep DB-first as the default: Sheets remains an explicit export option.
- Every PR must leave the app usable. No PR should require operators to edit JSON
  to complete the main workflow.

## PR Plan

### PR UX1 - Product Shell And Navigation

Status: implemented.

Goal: make the app feel like one console instead of a set of unrelated tabs.

Scope:

- Add a Home area with setup checklist, active context and recent run summary.
- Introduce a shared context state for selected client and project.
- Replace duplicate client/project text inputs in launch/checks with context
  pickers.
- Add lightweight CSS for spacing, width, status chips and section hierarchy.

Acceptance:

- A user can see whether global settings, at least one client and at least one
  project exist from the first screen.
- Selecting a client/project updates the context used by checks and launch.
- Existing callback tests cover context selection and empty-state rendering.

Docs:

- Update `docs/GRADIO_OPERATOR_WORKFLOWS.md`.
- Add screenshots or textual walkthrough placeholders in `docs/RUNTIME_OPERATIONS.md`.

### PR UX2 - Guided First-Run Setup

Status: implemented baseline.

Goal: make the first 10 minutes productive without reading JSON docs.

Scope:

- Add a setup wizard-like flow for:
  - provider credential status,
  - default LLM provider/base URL,
  - first client,
  - first project.
- Add a sanitized setup health summary callback.
- Add copy-safe examples for client/project fields.

Acceptance:

- A clean repo with no clients/projects shows the next required setup action.
- Saving credentials never echoes secret values.
- Setup health tests run without external API calls.

Docs:

- Add a "From zero to first run" section to `docs/GRADIO_OPERATOR_WORKFLOWS.md`.
- Link the setup flow from `README.md`.

### PR UX3 - Client And Project Workspaces

Status: implemented baseline.

Goal: make client/project management usable for repeated work.

Scope:

- Replace markdown-only listings with structured `Dataframe` lists where
  selection loads the editor.
- Add client detail view with projects under that client.
- Add project detail view with effective config preview:
  - inherited domain/database/gl/hl,
  - project overrides,
  - selected LLM,
  - SERP provider order.
- Add duplicate/project-create-from-client-defaults action.

Acceptance:

- Operators can edit existing clients/projects without typing IDs manually.
- Effective config preview is available before connection checks.
- Tests cover inherited versus overridden values.

Docs:

- Document inheritance rules and rename/duplicate behavior.

### PR UX4 - Integrations And Preflight Center

Status: implemented baseline.

Goal: make provider readiness visible and actionable.

Scope:

- Create a dedicated Integrations/Preflight area for the active project.
- Show connection state for SEMrush, SERP, GSC, GA4, Sheets and LLM.
- Separate cheap config checks from live provider checks.
- Store the latest check results in SQLite or a local status artifact for display.

Acceptance:

- Operators can run checks for the active project without re-entering IDs.
- The launch screen displays the latest preflight result and blocks only hard
  failures.
- Tests mock all provider checks.

Docs:

- Update `docs/EXTERNAL_APIS.md` and `docs/RUNTIME_OPERATIONS.md` with check
  categories and failure messages.

### PR UX5 - Briefing Launcher Redesign

Status: implemented.

Goal: turn run creation into a guided, validated workflow.

Scope:

- Split the launch form into new-page and existing-page modes.
- Add mode-specific validation and helper text:
  - new page: target URL optional,
  - existing page: target URL required and GA4/GSC context highlighted.
- Add run preview with keyword, project, providers, model, output destination and
  estimated expensive stages.
- Keep `upload_to_sheets=false` by default and make export intent explicit.

Acceptance:

- Invalid mode/URL combinations fail before a job is created.
- The run preview matches the metadata persisted in `JobStore`.
- Tests cover both briefing modes.

Docs:

- Update operator workflow docs and API lifecycle docs.

### PR UX6 - Runs Workspace And Output Review

Status: implemented baseline.

Goal: make completed and failed jobs useful from the UI.

Scope:

- Replace markdown job list with a filterable runs table.
- Add run detail panels:
  - status and lifecycle events,
  - stage metrics,
  - provider calls and costs,
  - final briefing summary,
  - artifact paths.
- Add safe actions for retry, cancel and cleanup where allowed.

Acceptance:

- Operators can diagnose a failed run without opening files manually.
- Completed run details show briefing output and artifact references.
- Admin actions reflect allowed state transitions.

Docs:

- Update runtime operations and troubleshooting with UI-based diagnosis steps.

### PR UX7 - Backend Service Layer For UI Workflows

Status: implemented.

Goal: prevent the UI from becoming a large callback file.

Scope:

- Move client/project/runtime/check/run orchestration into service modules.
- Keep Gradio callbacks thin and testable.
- Add response DTOs for UI state, setup health, effective project config and run
  summaries.

Acceptance:

- `apps/gradio_app.py` contains layout and callback wiring, not business logic.
- Service tests cover the same behavior without importing Gradio.
- Future FastAPI endpoints can reuse the service layer.

Docs:

- Update `docs/PROJECT_MAP.md` and `ARCHITECTURE.md`.

### PR UX8 - Documentation, Smoke Tests And Release Readiness

Status: implemented baseline.

Goal: make the redesigned operator console the supported way to work from day
one.

Scope:

- Add a complete first-run tutorial.
- Add UI smoke tests for app construction and main callbacks.
- Add a manual QA checklist for local Windows PowerShell execution.
- Decide whether `/ops` dashboard remains admin-only, is merged conceptually, or
  is deprecated in favor of the Gradio operator console.

Acceptance:

- A new developer can run the app, configure a test client/project and launch a
  mocked-safe run using docs alone.
- All docs agree on the primary UI entrypoint.
- `pytest -q`, markdown guard, `git diff --check` and repo guard pass.

Docs:

- Update README, runtime operations, troubleshooting, project map and AGENTS.

## Execution Order

1. UX1 - shell, context and navigation.
2. UX2 - guided setup.
3. UX3 - client/project workspaces.
4. UX4 - integrations and preflight.
5. UX5 - launcher redesign.
6. UX6 - runs and output review.
7. UX7 - service layer extraction.
8. UX8 - docs, smoke tests and release readiness.

UX7 is intentionally late enough to avoid designing abstractions before the UI
shape stabilizes, but early enough that the final app is maintainable.

## Definition Of Done For The Redesign

- The app has a clear first screen and active client/project context.
- A clean local install can reach first briefing without manual JSON edits.
- Existing clients/projects can be edited, duplicated and used for runs.
- Provider checks and runtime configuration are visible before launch.
- New-page and existing-page runs have separate validation paths.
- Run results, metrics, costs and artifacts can be reviewed from the UI.
- Documentation describes the operator workflow first and internal details second.
- Automated tests cover UI state services and Gradio callback wiring.

## V2 Premium Redesign (Dashboard Sidebar)

Status: UX9 and UX10 implemented.

A new visual identity and sidebar-based layout have been integrated to improve the aesthetics and navigation of the Gradio application, shifting from a technical tool to a Premium Operator Console.

### PR UX9 - Theme, Typography, and Dark Mode
Status: implemented.
Goal: Apply a premium dark mode theme, Google Fonts (Inter), and CSS styling (Glassmorphism, Gradients).

### PR UX10 - Sidebar and Dashboard Layout
Status: implemented.
Goal: Replace `gr.Tab` with a `gr.Row`/`gr.Column` sidebar approach.
Scope:
- Sidebar contains navigation buttons and active context.
- Main panel contains conditionally visible Groups for each workspace.

### PR UX11 - Progressive Forms and Unified Preflight
Status: implemented.
Goal: Wrap secondary inputs in Accordions and merge Preflight checks into the Launch view.

### PR UX12 - Advanced Runs Rendering
Status: implemented.
Goal: Replace the raw Dataframe for Runs with a custom HTML rendering including status pills and icons.

