"""Service layer for the local operator UI.

The Gradio app should stay focused on layout and event wiring. This module owns
operator-facing state summaries, effective project previews and run diagnostics.
It intentionally returns plain Python structures/Markdown so it can be tested
without importing Gradio.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from api.job_lifecycle import JobLifecycleService
from api.job_store import JobRecord, JobStore
from seo_pipeline.config import ClientConfig, ProjectConfig, get_config
from seo_pipeline.integration_checks import IntegrationCheckResult


@dataclass(frozen=True)
class SetupHealth:
    has_global_serp: bool
    has_global_semrush: bool
    has_global_llm: bool
    client_count: int
    project_count: int
    active_client_id: str | None
    active_project_id: str | None
    next_action: str

    @property
    def ready_for_first_run(self) -> bool:
        return self.client_count > 0 and self.project_count > 0 and self.has_global_semrush and self.has_global_serp and self.has_global_llm


@dataclass(frozen=True)
class EffectiveProjectConfig:
    project_id: str
    client_id: str
    domain: str
    domain_source: str
    semrush_database: str
    semrush_database_source: str
    google_gl: str
    google_gl_source: str
    google_hl: str
    google_hl_source: str
    llm_provider: str
    llm_model: str
    llm_base_url: str
    serp_provider_order: list[str]
    gsc_property: str
    ga4_property_id: str
    sheets_id: str
    project_type: str


def get_setup_health() -> SetupHealth:
    cfg = get_config()
    settings = cfg.runtime_settings
    has_global_serp = bool(settings.serpapi_key or (settings.dataforseo_login and settings.dataforseo_password))
    has_global_llm = bool(settings.openai_key or settings.anthropic_key or settings.llm_base_url)
    next_action = "Ready to configure a run."
    if not settings.semrush_token:
        next_action = "Configure SEMrush token in Settings."
    elif not has_global_serp:
        next_action = "Configure at least one SERP provider in Settings."
    elif not has_global_llm:
        next_action = "Configure an LLM provider or local Ollama base URL."
    elif not cfg.clients:
        next_action = "Create the first client."
    elif not cfg.projects:
        next_action = "Create the first project."
    elif not cfg.active_client or not cfg.active_project:
        next_action = "Select an active client and project."

    return SetupHealth(
        has_global_serp=has_global_serp,
        has_global_semrush=bool(settings.semrush_token),
        has_global_llm=has_global_llm,
        client_count=len(cfg.clients),
        project_count=len(cfg.projects),
        active_client_id=cfg.active_client.client_id if cfg.active_client else None,
        active_project_id=cfg.active_project.project_id if cfg.active_project else None,
        next_action=next_action,
    )


def setup_health_markdown() -> str:
    health = get_setup_health()
    rows = [
        "## Home",
        "",
        "| Area | Status |",
        "|---|---|",
        f"| SEMrush | {_status_label(health.has_global_semrush)} |",
        f"| SERP provider | {_status_label(health.has_global_serp)} |",
        f"| LLM | {_status_label(health.has_global_llm)} |",
        f"| Clients | {health.client_count} |",
        f"| Projects | {health.project_count} |",
        f"| Active context | {health.active_client_id or '-'} / {health.active_project_id or '-'} |",
        "",
        f"**Next action:** {health.next_action}",
    ]
    return "\n".join(rows)


def client_dropdown_choices() -> list[tuple[str, str]]:
    cfg = get_config()
    return [(f"{client.name} ({client.client_id})", client.client_id) for client in sorted(cfg.clients.values(), key=lambda item: item.name.lower())]


def project_dropdown_choices(client_id: str = "") -> list[tuple[str, str]]:
    cfg = get_config()
    projects = list(cfg.projects.values())
    if client_id:
        projects = [project for project in projects if project.client_id == client_id]
    return [(f"{project.name} ({project.project_id})", project.project_id) for project in sorted(projects, key=lambda item: item.name.lower())]


def set_active_context(client_id: str, project_id: str) -> str:
    cfg = get_config()
    client_id = (client_id or "").strip()
    project_id = (project_id or "").strip()
    if not client_id:
        return "Select a client."
    if not cfg.set_active_client(client_id):
        return "Client not found."
    if project_id:
        if not cfg.set_active_project(project_id):
            return "Project not found."
        if cfg.active_project and cfg.active_project.client_id != client_id:
            return "Project does not belong to selected client."
    return active_context_markdown()


def active_context_markdown() -> str:
    cfg = get_config()
    if not cfg.active_client:
        return "No active client selected."
    if not cfg.active_project:
        return f"Active client: `{cfg.active_client.name}` (`{cfg.active_client.client_id}`). Select a project."
    effective = get_effective_project_config(cfg.active_project.project_id)
    if effective is None:
        return "Active project could not be resolved."
    return "\n".join(
        [
            f"Active context: **{cfg.active_client.name}** / **{cfg.active_project.name}**",
            "",
            f"- Domain: `{effective.domain or '-'}` ({effective.domain_source})",
            f"- Locale: `{effective.google_gl}` / `{effective.google_hl}`",
            f"- LLM: `{effective.llm_provider}` / `{effective.llm_model}`",
            f"- SERP: `{', '.join(effective.serp_provider_order)}`",
        ]
    )


def clients_table_data() -> list[list[str]]:
    cfg = get_config()
    rows: list[list[str]] = []
    for client in sorted(cfg.clients.values(), key=lambda item: item.name.lower()):
        projects = [project for project in cfg.projects.values() if project.client_id == client.client_id]
        rows.append(
            [
                client.client_id,
                client.name,
                client.default_base_domain or "",
                client.default_database,
                client.default_gl,
                client.default_hl,
                str(len(projects)),
                _yes_no(client.gsc_sa_path),
                _yes_no(client.sheets_sa_path),
            ]
        )
    return rows


def projects_table_data(client_id: str = "") -> list[list[str]]:
    cfg = get_config()
    rows: list[list[str]] = []
    projects = list(cfg.projects.values())
    if client_id:
        projects = [project for project in projects if project.client_id == client_id]
    for project in sorted(projects, key=lambda item: item.name.lower()):
        effective = get_effective_project_config(project.project_id)
        rows.append(
            [
                project.project_id,
                project.name,
                project.client_id,
                effective.domain if effective else "",
                _yes_no(project.gsc_property),
                _yes_no(project.ga4_property_id),
                project.project_type,
                f"{project.runtime.llm.provider}/{project.runtime.llm.model or '-'}",
                ", ".join(project.runtime.providers.serp.provider_order),
            ]
        )
    return rows


def get_effective_project_config(project_id: str) -> EffectiveProjectConfig | None:
    cfg = get_config()
    project = cfg.projects.get((project_id or "").strip())
    if project is None:
        return None
    client = cfg.clients.get(project.client_id)
    domain_source = "project override" if project.base_domain else "client default"
    database_source = "project override" if project.semrush_database else "client default"
    gl_source = "project override" if project.google_gl else "client default"
    hl_source = "project override" if project.google_hl else "client default"
    return EffectiveProjectConfig(
        project_id=project.project_id,
        client_id=project.client_id,
        domain=cfg.resolve_project_base_domain(project),
        domain_source=domain_source if client else "project",
        semrush_database=cfg.resolve_project_database(project),
        semrush_database_source=database_source if client else "project",
        google_gl=cfg.resolve_project_gl(project),
        google_gl_source=gl_source if client else "project",
        google_hl=cfg.resolve_project_hl(project),
        google_hl_source=hl_source if client else "project",
        llm_provider=project.runtime.llm.provider,
        llm_model=project.runtime.llm.model or "-",
        llm_base_url=project.runtime.llm.base_url or "-",
        serp_provider_order=project.runtime.providers.serp.provider_order,
        gsc_property=project.gsc_property or "",
        ga4_property_id=project.ga4_property_id or "",
        sheets_id=project.sheets_id or "",
        project_type=project.project_type,
    )


def effective_config_markdown(project_id: str) -> str:
    effective = get_effective_project_config(project_id)
    if effective is None:
        return "Select a project to preview its effective configuration."
    rows = [
        "## Effective Project Configuration",
        "",
        "| Setting | Value | Source |",
        "|---|---|---|",
        f"| Base domain | `{effective.domain or '-'}` | {effective.domain_source} |",
        f"| SEMrush database | `{effective.semrush_database}` | {effective.semrush_database_source} |",
        f"| Google gl | `{effective.google_gl}` | {effective.google_gl_source} |",
        f"| Google hl | `{effective.google_hl}` | {effective.google_hl_source} |",
        f"| LLM provider | `{effective.llm_provider}` | project runtime |",
        f"| LLM model | `{effective.llm_model}` | project runtime |",
        f"| LLM base URL | `{effective.llm_base_url}` | project runtime |",
        f"| SERP order | `{', '.join(effective.serp_provider_order)}` | project runtime |",
        f"| GSC property | `{effective.gsc_property or '-'}` | project |",
        f"| GA4 property ID | `{effective.ga4_property_id or '-'}` | project |",
        f"| Sheets ID/URL | `{effective.sheets_id or '-'}` | project |",
        f"| Project type | `{effective.project_type}` | project |",
    ]
    return "\n".join(rows)


def config_preflight_results(client_id: str, project_id: str) -> list[IntegrationCheckResult]:
    cfg = get_config()
    client = cfg.clients.get((client_id or "").strip())
    project = cfg.projects.get((project_id or "").strip())
    if client is None:
        return [IntegrationCheckResult("context", "failed", "Select an existing client.")]
    if project is None:
        return [IntegrationCheckResult("context", "failed", "Select an existing project.")]
    if project.client_id != client.client_id:
        return [IntegrationCheckResult("context", "failed", "Project does not belong to selected client.")]
    effective_client = cfg.apply_effective_client_defaults(client)
    checks = [
        IntegrationCheckResult("context", "ok", "Client and project relationship is valid."),
        IntegrationCheckResult("domain", "ok" if cfg.resolve_project_base_domain(project) else "failed", "Base domain is resolved." if cfg.resolve_project_base_domain(project) else "Base domain is missing."),
        IntegrationCheckResult("semrush", "ok" if effective_client.semrush_token else "failed", "SEMrush token is configured." if effective_client.semrush_token else "SEMrush token is missing."),
        IntegrationCheckResult(
            "serp",
            "ok" if effective_client.serpapi_key or (effective_client.dataforseo_login and effective_client.dataforseo_password) else "failed",
            "At least one SERP credential set is configured." if effective_client.serpapi_key or (effective_client.dataforseo_login and effective_client.dataforseo_password) else "SERP credentials are missing.",
        ),
        IntegrationCheckResult("llm", "ok" if project.runtime.llm.provider else "failed", f"LLM provider is {project.runtime.llm.provider}."),
        IntegrationCheckResult("gsc", "ok" if client.gsc_sa_path and project.gsc_property else "skipped", "GSC is configured." if client.gsc_sa_path and project.gsc_property else "GSC is optional and not fully configured."),
        IntegrationCheckResult("ga4", "ok" if client.gsc_sa_path and project.ga4_property_id else "skipped", "GA4 is configured." if client.gsc_sa_path and project.ga4_property_id else "GA4 is optional and not fully configured."),
        IntegrationCheckResult("sheets", "ok" if client.sheets_sa_path and project.sheets_id else "skipped", "Sheets export is configured." if client.sheets_sa_path and project.sheets_id else "Sheets export is optional and not fully configured."),
    ]
    return checks


def checks_markdown(results: list[IntegrationCheckResult]) -> str:
    rows = ["| Check | Status | Message |", "|---|---|---|"]
    for result in results:
        rows.append(f"| {result.service} | {result.status} | {result.message} |")
    return "\n".join(rows)


def validate_launch_request(*, client_id: str, project_id: str, brief_type: str, keyword: str, target_url: str) -> list[str]:
    errors: list[str] = []
    cfg = get_config()
    client = cfg.clients.get((client_id or "").strip())
    project = cfg.projects.get((project_id or "").strip())
    normalized_type = (brief_type or "new_page").strip()
    if client is None:
        errors.append("Select an existing client.")
    if project is None:
        errors.append("Select an existing project.")
    if client and project and project.client_id != client.client_id:
        errors.append("Project does not belong to selected client.")
    if not (keyword or "").strip():
        errors.append("Keyword is required.")
    if normalized_type == "existing_page" and not (target_url or "").strip():
        errors.append("Target URL is required for existing-page briefings.")
    if project and not cfg.resolve_project_base_domain(project):
        errors.append("Effective base domain is missing.")
    hard_preflight_failures = [result for result in config_preflight_results(client_id, project_id) if result.status == "failed"]
    errors.extend(result.message for result in hard_preflight_failures)
    return list(dict.fromkeys(errors))


def launch_preview_markdown(*, client_id: str, project_id: str, brief_type: str, keyword: str, target_url: str, upload_to_sheets: bool) -> str:
    errors = validate_launch_request(
        client_id=client_id,
        project_id=project_id,
        brief_type=brief_type,
        keyword=keyword,
        target_url=target_url,
    )
    effective = get_effective_project_config(project_id)
    rows = [
        "## Run Preview",
        "",
        f"- Client/project: `{client_id or '-'}` / `{project_id or '-'}`",
        f"- Brief type: `{brief_type or 'new_page'}`",
        f"- Keyword: `{(keyword or '').strip() or '-'}`",
        f"- Target URL: `{(target_url or '').strip() or '-'}`",
        f"- Export to Sheets: `{_yes_no(upload_to_sheets)}`",
    ]
    if effective:
        rows.extend(
            [
                f"- Domain: `{effective.domain or '-'}`",
                f"- LLM: `{effective.llm_provider}` / `{effective.llm_model}`",
                f"- SERP order: `{', '.join(effective.serp_provider_order)}`",
            ]
        )
    if errors:
        rows.extend(["", "### Blocking Issues", *[f"- {error}" for error in errors]])
    else:
        rows.append("")
        rows.append("Ready to launch.")
    return "\n".join(rows)


def runs_table_data(store: JobStore, *, limit: int = 50, status: str = "", search: str = "") -> list[list[str]]:
    jobs = store.list_jobs(
        limit=max(1, min(int(limit), 200)),
        status=status or None,
        search=search or None,
    )
    return [
        [
            job.run_id,
            job.status,
            job.client_id or "",
            job.project_id or "",
            job.brief_type or "",
            job.keyword,
            job.error_category or "",
            job.updated_at,
        ]
        for job in jobs
    ]


def run_detail_markdown(run_id: str, store: JobStore) -> str:
    run_id = (run_id or "").strip()
    if not run_id:
        return "Select or paste a run ID."
    job = store.get_job(run_id)
    if job is None:
        return "Job not found."
    events = store.list_job_events(run_id, limit=20)
    metrics = store.list_stage_metrics(run_id)
    providers = store.list_provider_calls(run_id)
    prompt = store.get_prompt_run(run_id)
    briefing = store.get_briefing_record(run_id)
    artifacts = store.list_job_artifacts(run_id)
    rows = [
        f"## Run `{job.run_id}`",
        "",
        f"- Status: `{job.status}`",
        f"- Step: `{job.step}`",
        f"- Keyword: `{job.keyword}`",
        f"- Client/project: `{job.client_id or '-'}` / `{job.project_id or '-'}`",
        f"- Type: `{job.brief_type or '-'}`",
        f"- Target URL: `{job.target_url or '-'}`",
        f"- Error category: `{job.error_category or '-'}`",
        f"- Output: `{job.output_dir}`",
    ]
    if briefing:
        rows.extend(["", "### Briefing", f"- H1: {briefing.h1 or '-'}", f"- Meta title: {briefing.meta_title or '-'}", f"- Provider/model: {briefing.provider or '-'} / {briefing.model or '-'}"])
    if prompt:
        rows.extend(["", "### Prompt", f"- Key/version: {prompt.key or '-'} / {prompt.version or '-'}", f"- Mode: {prompt.mode or '-'}", f"- Model: {prompt.model or '-'}"])
    if metrics:
        rows.extend(["", "### Stage Metrics"])
        for metric in metrics:
            rows.append(f"- {metric.stage}: {metric.status or '-'} | provider={metric.provider or '-'} | retries={metric.retries or 0} | duration={metric.duration_seconds or '-'}")
    if providers:
        rows.extend(["", "### Provider Calls"])
        for call in providers:
            rows.append(f"- {call.provider}/{call.service}: calls={call.calls or '-'} | cost={call.estimated_cost_usd if call.estimated_cost_usd is not None else '-'}")
    if artifacts:
        rows.extend(["", "### Artifacts"])
        for artifact in artifacts:
            rows.append(f"- {artifact.artifact_type}: `{artifact.path}`")
    if events:
        rows.extend(["", "### Timeline"])
        for event in events:
            rows.append(f"- {event.created_at}: {event.status}/{event.step} - {event.message}")
    return "\n".join(rows)


def cancel_run(run_id: str, store: JobStore) -> str:
    job = store.get_job((run_id or "").strip())
    if job is None:
        return "Job not found."
    try:
        JobLifecycleService(store).cancel(job)
    except Exception as exc:
        return f"Cancel failed: {exc}"
    return f"Run `{job.run_id}` canceled."


def delete_run(run_id: str, store: JobStore) -> str:
    run_id = (run_id or "").strip()
    if not run_id:
        return "Select a run ID."
    deleted = store.delete_job(run_id)
    return f"Deleted metadata for `{run_id}`." if deleted else "Job not found."


def cleanup_runs(store: JobStore, *, max_age_days: int = 30) -> str:
    deleted = store.cleanup_old_jobs(max_age_days=max_age_days, statuses=("done", "failed"))
    return f"Cleanup deleted {deleted} terminal job metadata rows."


def duplicate_project(source_project_id: str, new_project_id: str, new_name: str) -> str:
    cfg = get_config()
    source = cfg.projects.get((source_project_id or "").strip())
    if source is None:
        return "Source project not found."
    new_project_id = "_".join((new_project_id or "").strip().split())
    if not new_project_id:
        return "New project ID is required."
    if new_project_id in cfg.projects:
        return "New project ID already exists."
    payload = source.model_dump()
    payload["project_id"] = new_project_id
    payload["name"] = (new_name or "").strip() or f"{source.name} Copy"
    cfg.projects[new_project_id] = ProjectConfig(**payload)
    cfg.save_projects()
    return f"Project `{new_project_id}` duplicated from `{source.project_id}`."


def _status_label(ok: bool) -> str:
    return "ok" if ok else "missing"


def _yes_no(value: Any) -> str:
    return "yes" if value else "no"
