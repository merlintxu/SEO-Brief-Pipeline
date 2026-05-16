"""Gradio operator UI for DB-first SEO briefing runs."""
from __future__ import annotations

import os
from datetime import datetime
from pathlib import Path
from typing import Callable

from api.job_lifecycle import JobLifecycleService
from api.job_store import JobStore
from seo_pipeline.artifacts import RUN_METRICS_JSON
from seo_pipeline.config import ClientConfig, ProjectConfig, ProjectRuntimeConfig, RuntimeSettings, get_config
from seo_pipeline.integration_checks import checks_to_markdown, run_connection_checks
from seo_pipeline.options import (
    ANTHROPIC_MODEL_OPTIONS,
    DEFAULT_LLM_MODEL,
    DEFAULT_LLM_PROVIDER,
    DEFAULT_OLLAMA_BASE_URL,
    GOOGLE_GL_OPTIONS,
    GOOGLE_HL_OPTIONS,
    LLM_PROVIDER_OPTIONS,
    OLLAMA_MODEL_OPTIONS,
    OPENAI_MODEL_OPTIONS,
    PROJECT_TYPE_OPTIONS,
    SEMRUSH_DATABASES,
    llm_models_for_provider,
)
from seo_pipeline.operator_ui import (
    active_context_markdown,
    cancel_run,
    checks_markdown,
    cleanup_runs,
    client_dropdown_choices,
    clients_table_data,
    config_preflight_results,
    delete_run,
    duplicate_project,
    effective_config_markdown,
    launch_preview_markdown,
    project_dropdown_choices,
    projects_table_data,
    run_detail_markdown,
    runs_table_html,
    set_active_context,
    setup_health_markdown,
    validate_launch_request,
)
from seo_pipeline.pipeline import run_full_pipeline
from seo_pipeline.utils.io import ensure_dir, load_json
from seo_pipeline.vendors.drive_io import list_spreadsheets


DEFAULT_STORE = JobStore((Path("outputs") / "jobs.db").resolve())
BRIEF_TYPES = {
    "new_page": "New page",
    "existing_page": "Existing page",
}
APP_CSS = """
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');

.gradio-container { max-width: 1440px !important; font-family: 'Inter', sans-serif !important; }
.status-panel { border-left: 4px solid #6366F1; padding-left: 12px; background: rgba(31, 41, 55, 0.5); border-radius: 8px; padding: 16px; margin-bottom: 16px; border: 1px solid #374151; }
.danger-action button { border-color: #EF4444 !important; color: #EF4444 !important; }
.btn-primary { background: linear-gradient(135deg, #6366F1 0%, #A855F7 100%) !important; border: none !important; color: white !important; font-weight: 600 !important; }
.sidebar-panel { background: #111827; border-radius: 12px; padding: 20px; border: 1px solid #374151; height: 100%; min-height: 800px; }
.main-panel { background: #1F2937; border-radius: 12px; padding: 24px; border: 1px solid #374151; min-height: 800px; }
"""


def runtime_settings_markdown() -> str:
    settings = get_config().runtime_settings
    rows = ["| Setting | Configured |", "|---|---|"]
    for name in (
        "semrush_token",
        "serpapi_key",
        "openai_key",
        "anthropic_key",
        "llm_base_url",
        "dataforseo_login",
        "dataforseo_password",
    ):
        rows.append(f"| {name} | {_yes_no(getattr(settings, name))} |")
    return "\n".join(rows)


def save_runtime_settings_callback(
    semrush_token: str,
    serpapi_key: str,
    openai_key: str,
    anthropic_key: str,
    llm_base_url: str,
    dataforseo_login: str,
    dataforseo_password: str,
) -> str:
    cfg = get_config()
    current = cfg.runtime_settings
    cfg.runtime_settings = RuntimeSettings(
        semrush_token=_keep_or_none(semrush_token, current.semrush_token),
        serpapi_key=_keep_or_none(serpapi_key, current.serpapi_key),
        openai_key=_keep_or_none(openai_key, current.openai_key),
        anthropic_key=_keep_or_none(anthropic_key, current.anthropic_key),
        llm_base_url=_keep_or_none(llm_base_url, current.llm_base_url) or DEFAULT_OLLAMA_BASE_URL,
        dataforseo_login=_keep_or_none(dataforseo_login, current.dataforseo_login),
        dataforseo_password=_keep_or_none(dataforseo_password, current.dataforseo_password),
    )
    cfg.save_runtime_settings()
    return "Global runtime settings saved in ignored local config."


def list_clients_markdown() -> str:
    cfg = get_config()
    if not cfg.clients:
        return "No clients configured."
    rows = ["| Client ID | Name | Default domain | Database | gl | hl | GSC | Sheets |", "|---|---|---|---|---|---|---|---|"]
    for client in sorted(cfg.clients.values(), key=lambda item: item.client_id):
        rows.append(
            "| "
            f"`{client.client_id}` | {client.name} | {client.default_base_domain or '-'} | "
            f"{client.default_database} | {client.default_gl} | {client.default_hl} | "
            f"{_yes_no(client.gsc_sa_path)} | {_yes_no(client.sheets_sa_path)} |"
        )
    return "\n".join(rows)


def client_choices() -> list[str]:
    return sorted(get_config().clients)


def _gr_update(**kwargs):
    try:
        import gradio as gr
    except ModuleNotFoundError:
        return kwargs
    return gr.update(**kwargs)


def refresh_clients_callback():
    choices = client_choices()
    return _gr_update(choices=choices, value=choices[0] if choices else None), list_clients_markdown()


def load_client_callback(selected_client_id: str):
    client = get_config().clients.get((selected_client_id or "").strip())
    if client is None:
        return ("", "", "", "", "", "es", "es", "es-es", "Client not found.")
    return (
        client.client_id,
        client.name,
        client.default_base_domain or "",
        client.gsc_sa_path or "",
        client.sheets_sa_path or "",
        client.default_database,
        client.default_gl,
        client.default_hl,
        f"Loaded client `{client.client_id}`.",
    )


def save_client_callback(
    client_id: str,
    name: str,
    default_base_domain: str,
    gsc_sa_path: str,
    sheets_sa_path: str,
    default_database: str,
    default_gl: str,
    default_hl: str,
) -> str:
    cfg = get_config()
    client_id = _slug(client_id)
    if not client_id:
        return "Client ID is required."
    if not name.strip():
        return "Client name is required."
    existing = cfg.clients.get(client_id)
    client = ClientConfig(
        client_id=client_id,
        name=name.strip(),
        default_base_domain=_optional(default_base_domain),
        semrush_token=existing.semrush_token if existing else None,
        serpapi_key=existing.serpapi_key if existing else None,
        openai_key=existing.openai_key if existing else None,
        piloterr_key=existing.piloterr_key if existing else None,
        dataforseo_login=existing.dataforseo_login if existing else None,
        dataforseo_password=existing.dataforseo_password if existing else None,
        gsc_sa_path=_optional(gsc_sa_path),
        sheets_sa_path=_optional(sheets_sa_path),
        default_database=default_database.strip() or "es",
        default_gl=default_gl.strip() or "es",
        default_hl=default_hl.strip() or "es-es",
    )
    cfg.clients[client_id] = client
    cfg.save_clients()
    return f"Client `{client_id}` saved. Secrets were not displayed."


def list_projects_markdown(client_id: str = "") -> str:
    cfg = get_config()
    projects = list(cfg.projects.values())
    if client_id.strip():
        projects = [project for project in projects if project.client_id == client_id.strip()]
    if not projects:
        return "No projects configured."
    rows = [
        "| Project ID | Client | Domain | GSC | GA4 | LLM | SERP order |",
        "|---|---|---|---|---|---|---|",
    ]
    for project in sorted(projects, key=lambda item: item.project_id):
        rows.append(
            "| "
            f"`{project.project_id}` | `{project.client_id}` | {cfg.resolve_project_base_domain(project) or '-'} | {_yes_no(project.gsc_property)} | "
            f"{_yes_no(project.ga4_property_id)} | {project.runtime.llm.provider}/{project.runtime.llm.model or '-'} | "
            f"{', '.join(project.runtime.providers.serp.provider_order)} |"
        )
    return "\n".join(rows)


def project_choices(client_id: str = "") -> list[str]:
    cfg = get_config()
    projects = list(cfg.projects.values())
    if client_id.strip():
        projects = [project for project in projects if project.client_id == client_id.strip()]
    return [project.project_id for project in sorted(projects, key=lambda item: item.project_id)]


def refresh_projects_callback(client_id: str = ""):
    choices = project_choices(client_id)
    return _gr_update(choices=choices, value=choices[0] if choices else None), list_projects_markdown(client_id)


def load_project_callback(selected_project_id: str):
    cfg = get_config()
    project = cfg.projects.get((selected_project_id or "").strip())
    if project is None:
        return (
            "",
            "",
            "",
            "",
            None,
            None,
            None,
            "",
            "",
            "",
            "content",
            "runs",
            DEFAULT_LLM_PROVIDER,
            _gr_update(choices=OLLAMA_MODEL_OPTIONS, value=DEFAULT_LLM_MODEL),
            DEFAULT_OLLAMA_BASE_URL,
            True,
            True,
            "Project not found.",
        )
    provider = project.runtime.llm.provider
    model_choices = llm_models_for_provider(provider)
    model = project.runtime.llm.model or (DEFAULT_LLM_MODEL if provider == "ollama" else model_choices[0])
    if model not in model_choices:
        model_choices = [model, *model_choices]
    serp_order = project.runtime.providers.serp.provider_order
    return (
        project.project_id,
        project.client_id,
        project.name,
        project.base_domain or "",
        project.semrush_database,
        project.google_gl,
        project.google_hl,
        project.gsc_property or "",
        project.ga4_property_id or "",
        project.sheets_id or "",
        project.project_type,
        project.output_dir or "runs",
        provider,
        _gr_update(choices=model_choices, value=model),
        project.runtime.llm.base_url or DEFAULT_OLLAMA_BASE_URL,
        "serpapi" in serp_order,
        "dataforseo" in serp_order,
        f"Loaded project `{project.project_id}`.",
    )


def save_project_callback(
    project_id: str,
    client_id: str,
    name: str,
    base_domain: str,
    semrush_database: str,
    google_gl: str,
    google_hl: str,
    gsc_property: str,
    ga4_property_id: str,
    sheets_id: str,
    project_type: str,
    output_dir: str,
    llm_provider: str,
    llm_model: str,
    llm_base_url: str,
    serpapi_enabled: bool,
    dataforseo_enabled: bool,
) -> str:
    cfg = get_config()
    project_id = _slug(project_id)
    client_id = client_id.strip()
    if not project_id:
        return "Project ID is required."
    if client_id not in cfg.clients:
        return "Client does not exist."
    if not name.strip():
        return "Project name is required."
    inherited_domain = cfg.clients[client_id].default_base_domain
    if not base_domain.strip() and not inherited_domain:
        return "Base domain is required when the client has no default base domain."
    provider_order = []
    if serpapi_enabled:
        provider_order.append("serpapi")
    if dataforseo_enabled:
        provider_order.append("dataforseo")
    if not provider_order:
        return "Select at least one SERP provider."
    if llm_model not in llm_models_for_provider(llm_provider):
        return "Selected model is not valid for the selected LLM provider."
    try:
        runtime = ProjectRuntimeConfig(
            llm={
                "provider": llm_provider,
                "model": _optional(llm_model) or DEFAULT_LLM_MODEL,
                "base_url": _optional(llm_base_url) or DEFAULT_OLLAMA_BASE_URL,
                "prompt_version": "v1",
            },
            providers={"serp": {"provider_order": provider_order}},
        )
        project = ProjectConfig(
            project_id=project_id,
            client_id=client_id,
            name=name.strip(),
            base_domain=_optional(base_domain),
            gsc_property=gsc_property.strip(),
            ga4_property_id=_optional(ga4_property_id),
            project_type=project_type or "content",
            semrush_database=_optional(semrush_database),
            google_gl=_optional(google_gl),
            google_hl=_optional(google_hl),
            sheets_id=sheets_id.strip(),
            output_dir=output_dir.strip() or "runs",
            runtime=runtime,
        )
    except ValueError as exc:
        return f"Invalid project configuration: {exc}"
    cfg.projects[project_id] = project
    cfg.save_projects()
    return f"Project `{project_id}` saved for client `{client_id}`."


def activate_project_callback(client_id: str, project_id: str) -> str:
    cfg = get_config()
    if not cfg.set_active_client(client_id.strip()):
        return "Client not found."
    if not cfg.set_active_project(project_id.strip()):
        return "Project not found for active client."
    return f"Active context: `{cfg.active_client.client_id}` / `{cfg.active_project.project_id}`."


def connection_checks_callback(client_id: str, project_id: str, keyword: str = "test") -> str:
    cfg = get_config()
    client = cfg.clients.get(client_id.strip())
    project = cfg.projects.get(project_id.strip())
    if client is None:
        return "Client not found."
    if project is None:
        return "Project not found."
    if project.client_id != client.client_id:
        return "Project does not belong to client."
    results = run_connection_checks(client, project, keyword=keyword.strip() or "test")
    return checks_to_markdown(results)


def discover_sheets_callback(client_id: str, query: str = "") -> str:
    cfg = get_config()
    client = cfg.clients.get(client_id.strip())
    if client is None:
        return "Client not found."
    if not client.sheets_sa_path:
        return "Client has no Sheets/Drive service account path configured."
    try:
        sheets = list_spreadsheets(sa_json_path=client.sheets_sa_path, query=query.strip(), limit=20)
    except Exception as exc:
        return f"Could not list Google Sheets: {exc}"
    if not sheets:
        return "No spreadsheets found for this service account."
    rows = ["| Name | Spreadsheet ID | URL |", "|---|---|---|"]
    for sheet in sheets:
        rows.append(f"| {sheet.name} | `{sheet.spreadsheet_id}` | {sheet.web_url or '-'} |")
    return "\n".join(rows)


def model_choices_markdown() -> str:
    return "\n".join(
        [
            "### OpenAI",
            ", ".join(OPENAI_MODEL_OPTIONS),
            "",
            "### Anthropic",
            ", ".join(ANTHROPIC_MODEL_OPTIONS),
            "",
            "### Ollama",
            ", ".join(OLLAMA_MODEL_OPTIONS),
        ]
    )


def model_options_callback(provider: str):
    choices = llm_models_for_provider(provider)
    default = DEFAULT_LLM_MODEL if provider == "ollama" else choices[0]
    return _gr_update(choices=choices, value=default)


def home_refresh_callback():
    client_choices = client_dropdown_choices()
    selected_client = client_choices[0][1] if client_choices else None
    project_choices = project_dropdown_choices(selected_client or "")
    selected_project = project_choices[0][1] if project_choices else None
    if selected_client:
        set_active_context(selected_client, selected_project or "")
    return (
        setup_health_markdown(),
        _gr_update(choices=client_choices, value=selected_client),
        _gr_update(choices=project_choices, value=selected_project),
        active_context_markdown(),
        clients_table_data(),
        projects_table_data(selected_client or ""),
    )


def context_client_changed_callback(client_id: str):
    choices = project_dropdown_choices(client_id or "")
    selected_project = choices[0][1] if choices else None
    return (
        _gr_update(choices=choices, value=selected_project),
        projects_table_data(client_id or ""),
        effective_config_markdown(selected_project or ""),
    )


def set_context_callback(client_id: str, project_id: str):
    return (
        set_active_context(client_id, project_id),
        setup_health_markdown(),
        effective_config_markdown(project_id),
    )


def set_context_home_callback(client_id: str, project_id: str):
    return set_active_context(client_id, project_id), setup_health_markdown()


def preflight_config_callback(client_id: str, project_id: str) -> str:
    return checks_markdown(config_preflight_results(client_id, project_id))


def preflight_live_callback(client_id: str, project_id: str, keyword: str = "test") -> str:
    config_results = config_preflight_results(client_id, project_id)
    hard_failures = [result for result in config_results if result.status == "failed"]
    if hard_failures:
        return checks_markdown(config_results)
    return connection_checks_callback(client_id, project_id, keyword)


def launch_preview_callback(
    client_id: str,
    project_id: str,
    brief_type: str,
    keyword: str,
    target_url: str,
    upload_to_sheets: bool,
) -> str:
    return launch_preview_markdown(
        client_id=client_id,
        project_id=project_id,
        brief_type=brief_type,
        keyword=keyword,
        target_url=target_url,
        upload_to_sheets=upload_to_sheets,
    )


def guarded_launch_briefing_callback(
    client_id: str,
    project_id: str,
    brief_type: str,
    keyword: str,
    target_url: str,
    provider: str,
    model: str,
    ollama_base_url: str,
    upload_to_sheets: bool,
    *,
    store: JobStore = DEFAULT_STORE,
    pipeline_func: Callable[..., dict] = run_full_pipeline,
) -> str:
    errors = validate_launch_request(
        client_id=client_id,
        project_id=project_id,
        brief_type=brief_type,
        keyword=keyword,
        target_url=target_url,
    )
    if errors:
        return "Cannot launch:\n" + "\n".join(f"- {error}" for error in errors)
    return launch_briefing_callback(
        keyword,
        target_url,
        provider,
        model,
        ollama_base_url,
        upload_to_sheets,
        client_id,
        project_id,
        brief_type,
        store=store,
        pipeline_func=pipeline_func,
    )


def refresh_runs_callback(limit: int, status: str, search: str):
    return runs_table_data(DEFAULT_STORE, limit=int(limit or 50), status=status or "", search=search or "")


def run_detail_callback(run_id: str) -> str:
    return run_detail_markdown(run_id, DEFAULT_STORE)


def cancel_run_callback(run_id: str) -> str:
    return cancel_run(run_id, DEFAULT_STORE)


def delete_run_callback(run_id: str) -> str:
    return delete_run(run_id, DEFAULT_STORE)


def cleanup_runs_callback(max_age_days: int) -> str:
    return cleanup_runs(DEFAULT_STORE, max_age_days=int(max_age_days or 30))


def duplicate_project_callback(source_project_id: str, new_project_id: str, new_name: str) -> str:
    return duplicate_project(source_project_id, new_project_id, new_name)


def list_jobs_markdown(limit: int = 20, *, store: JobStore = DEFAULT_STORE) -> str:
    jobs = store.list_jobs(limit=max(1, min(int(limit), 200)))
    if not jobs:
        return "No jobs found."
    rows = ["| Run ID | Client | Project | Type | Keyword | Status | Step | Updated |", "|---|---|---|---|---|---|---|---|"]
    for job in jobs:
        rows.append(
            f"| `{job.run_id}` | {job.client_id or '-'} | {job.project_id or '-'} | {job.brief_type or '-'} | "
            f"{job.keyword} | {job.status} | {job.step} | {job.updated_at} |"
        )
    return "\n".join(rows)


def job_detail_markdown(run_id: str, *, store: JobStore = DEFAULT_STORE) -> str:
    run_id = run_id.strip()
    if not run_id:
        return "Provide a run_id."
    job = store.get_job(run_id)
    if job is None:
        return "Job not found."
    output = store.get_job_output(run_id)
    briefing = store.get_briefing_record(run_id)
    metrics = store.list_stage_metrics(run_id)
    lines = [
        f"## {job.run_id}",
        f"- keyword: {job.keyword}",
        f"- status: {job.status}",
        f"- step: {job.step}",
        f"- message: {job.message}",
        f"- output_dir: `{job.output_dir}`",
        f"- client/project: {job.client_id or '-'} / {job.project_id or '-'}",
        f"- brief_type: {job.brief_type or '-'}",
        f"- target_url: {job.target_url or '-'}",
    ]
    if briefing:
        lines.extend(
            [
                "",
                "### Briefing",
                f"- H1: {briefing.h1 or '-'}",
                f"- meta_title: {briefing.meta_title or '-'}",
                f"- provider/model: {briefing.provider or '-'} / {briefing.model or '-'}",
            ]
        )
    if output:
        lines.append(f"- DB output updated: {output.updated_at}")
    if metrics:
        lines.append("")
        lines.append("### Stage Metrics")
        for metric in metrics:
            lines.append(
                f"- {metric.stage}: {metric.status or '-'} | provider={metric.provider or '-'} "
                f"| retries={metric.retries or 0} | duration={metric.duration_seconds or '-'}"
            )
    return "\n".join(lines)


def launch_briefing_callback(
    keyword: str,
    target_url: str,
    provider: str,
    model: str,
    ollama_base_url: str,
    upload_to_sheets: bool,
    client_id: str = "",
    project_id: str = "",
    brief_type: str = "new_page",
    *,
    store: JobStore = DEFAULT_STORE,
    pipeline_func: Callable[..., dict] = run_full_pipeline,
) -> str:
    keyword = keyword.strip()
    if not keyword:
        return "Keyword is required."
    target_url = target_url.strip()
    brief_type = _normalize_brief_type(brief_type)
    if brief_type == "existing_page" and not target_url:
        return "Target URL is required for existing-page briefings."
    context_message = _activate_context(client_id, project_id)
    if context_message:
        return context_message
    cfg = get_config()
    run_id = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
    run_dir = Path("outputs") / run_id
    ensure_dir(run_dir)
    status_path = run_dir / "status.json"
    lifecycle = JobLifecycleService(store)
    lifecycle.enqueue(
        run_id=run_id,
        keyword=keyword,
        output_dir=run_dir,
        status_path=status_path,
        client_id=cfg.active_client.client_id if cfg.active_client else None,
        project_id=cfg.active_project.project_id if cfg.active_project else None,
        brief_type=brief_type,
        target_url=target_url or None,
    )
    if not lifecycle.start(run_id):
        return f"Run {run_id} could not start."

    old_env = {key: os.environ.get(key) for key in ("LLM_PROVIDER", "LLM_MODEL", "OLLAMA_MODEL", "OLLAMA_BASE_URL", "ANTHROPIC_MODEL")}
    old_runtime = cfg.active_project.runtime if cfg.active_project else None
    try:
        _set_model_env(provider, model, ollama_base_url)
        _set_active_project_runtime(provider, model, ollama_base_url)
        result = pipeline_func(
            keyword=keyword,
            target_url=target_url or None,
            run_id=run_id,
            upload_to_sheets=upload_to_sheets,
            status_path=status_path,
            output_dir=run_dir,
        )
        metrics_path = run_dir / RUN_METRICS_JSON
        metrics_payload = load_json(metrics_path, default={}) if metrics_path.exists() else {}
        if isinstance(metrics_payload, dict) and metrics_payload:
            store.persist_run_metrics(run_id, metrics_payload)
        _persist_job_output_from_result(store, run_id, keyword, result)
        lifecycle.complete_from_status(run_id, status_path)
        return f"Run `{run_id}` completed. Output: `{run_dir}`"
    except Exception as exc:
        lifecycle.fail_from_exception(run_id, status_path, exc)
        return f"Run `{run_id}` failed: {exc}"
    finally:
        if cfg.active_project and old_runtime is not None:
            cfg.active_project.runtime = old_runtime
        _restore_env(old_env)


def refresh_runs_html_callback(limit: float | int, status_filter: str, search_filter: str) -> str:
    return runs_table_html(DEFAULT_STORE, limit=int(limit), status=status_filter, search=search_filter)


def home_refresh_runs_html_callback() -> str:
    return runs_table_html(DEFAULT_STORE, limit=20)


def build_theme():
    import gradio as gr

    return gr.themes.Default(
        primary_hue="indigo",
        neutral_hue="slate",
        font=[gr.themes.GoogleFont("Inter"), "ui-sans-serif", "system-ui", "sans-serif"],
    )


def build_app():
    import gradio as gr

    with gr.Blocks(title="SEO Brief Pipeline Ops") as app:
        with gr.Row():
            # SIDEBAR
            with gr.Column(scale=1, elem_classes=["sidebar-panel"]):
                gr.Markdown("# SEO Ops")
                gr.Markdown("Premium Pipeline Console")

                nav_home = gr.Button("Home", variant="secondary")
                nav_settings = gr.Button("Settings", variant="secondary")
                nav_clients = gr.Button("Clients", variant="secondary")
                nav_projects = gr.Button("Projects", variant="secondary")
                nav_launch = gr.Button("Launch Briefing", variant="primary", elem_classes=["btn-primary"])
                nav_runs = gr.Button("Runs Workspace", variant="secondary")

                gr.Markdown("---")
                gr.Markdown("### Context")
                sidebar_context = gr.Markdown(active_context_markdown())

            # MAIN CONTENT
            with gr.Column(scale=4, elem_classes=["main-panel"]):

                # --- HOME ---
                with gr.Group(visible=True) as view_home:
                    gr.Markdown("## Dashboard Home")
                    with gr.Row():
                        home_status = gr.Markdown(setup_health_markdown(), elem_classes=["status-panel"])
                        active_context = gr.Markdown(active_context_markdown(), elem_classes=["status-panel"])
                    with gr.Row():
                        home_client = gr.Dropdown(client_dropdown_choices(), label="Active client")
                        home_project = gr.Dropdown(project_dropdown_choices(), label="Active project")
                        set_context = gr.Button("Set active context", variant="primary", elem_classes=["btn-primary"])
                        refresh_home = gr.Button("Refresh")
                    home_clients = gr.Dataframe(
                        headers=["Client ID", "Name", "Domain", "DB", "gl", "hl", "Projects", "GSC", "Sheets"],
                        value=clients_table_data(), interactive=False, label="Clients"
                    )
                    home_projects = gr.Dataframe(
                        headers=["Project ID", "Name", "Client", "Domain", "GSC", "GA4", "Type", "LLM", "SERP"],
                        value=projects_table_data(), interactive=False, label="Projects"
                    )
                    home_runs = gr.HTML(
                        value=runs_table_html(DEFAULT_STORE, limit=20), label="Recent runs"
                    )
                    home_client.change(
                        context_client_changed_callback,
                        inputs=home_client,
                        outputs=[home_project, home_projects, active_context]
                    )
                    set_context.click(
                        set_context_home_callback,
                        inputs=[home_client, home_project],
                        outputs=[active_context, home_status]
                    )
                    refresh_home.click(
                        home_refresh_callback,
                        outputs=[home_status, home_client, home_project, active_context, home_clients, home_projects]
                    ).then(
                        home_refresh_runs_html_callback,
                        outputs=[home_runs]
                    )

                # --- SETTINGS ---
                with gr.Group(visible=False) as view_settings:
                    gr.Markdown("## Global Providers")
                    with gr.Row():
                        global_semrush = gr.Textbox(label="SEMrush token", type="password")
                        global_serpapi = gr.Textbox(label="SerpAPI key", type="password")
                    with gr.Row():
                        global_openai = gr.Textbox(label="OpenAI key", type="password")
                        global_anthropic = gr.Textbox(label="Anthropic key", type="password")
                        global_llm_base_url = gr.Textbox(value=DEFAULT_OLLAMA_BASE_URL, label="LLM base URL")
                    with gr.Row():
                        global_dataforseo_login = gr.Textbox(label="DataForSEO login")
                        global_dataforseo_password = gr.Textbox(label="DataForSEO password", type="password")
                    save_global = gr.Button("Save settings", variant="primary", elem_classes=["btn-primary"])
                    global_message = gr.Markdown()
                    with gr.Row():
                        refresh_global = gr.Button("Refresh provider status")
                        global_status = gr.Markdown(runtime_settings_markdown())
                    gr.Markdown(model_choices_markdown())
                    save_global.click(
                        save_runtime_settings_callback,
                        inputs=[global_semrush, global_serpapi, global_openai, global_anthropic, global_llm_base_url, global_dataforseo_login, global_dataforseo_password],
                        outputs=global_message
                    )
                    refresh_global.click(runtime_settings_markdown, outputs=global_status)

                # --- CLIENTS ---
                with gr.Group(visible=False) as view_clients:
                    gr.Markdown("## Client Workspace")
                    selected_client = gr.Dropdown(client_choices(), label="Existing client")
                    with gr.Row():
                        refresh_clients = gr.Button("Refresh clients")
                        load_client = gr.Button("Load selected client", variant="primary", elem_classes=["btn-primary"])
                    clients_grid = gr.Dataframe(
                        headers=["Client ID", "Name", "Domain", "DB", "gl", "hl", "Projects", "GSC", "Sheets"],
                        value=clients_table_data(), interactive=False, label="Client list"
                    )
                    with gr.Accordion("Client Configuration", open=True):
                        with gr.Row():
                            client_id = gr.Textbox(label="Client ID")
                            client_name = gr.Textbox(label="Name")
                            default_base_domain = gr.Textbox(label="Default base domain")
                        with gr.Row():
                            gsc_sa_path = gr.Textbox(label="GSC/GA4 service account path")
                            sheets_sa_path = gr.Textbox(label="Sheets/Drive service account path")
                        with gr.Row():
                            default_database = gr.Dropdown(SEMRUSH_DATABASES, value="es", label="SEMrush database")
                            default_gl = gr.Dropdown(GOOGLE_GL_OPTIONS, value="es", label="Google gl")
                            default_hl = gr.Dropdown(GOOGLE_HL_OPTIONS, value="es-es", label="Google hl")
                        save_client = gr.Button("Save client", variant="primary", elem_classes=["btn-primary"])
                        client_message = gr.Markdown()
                    refresh_clients.click(refresh_clients_callback, outputs=[selected_client, client_message])
                    refresh_clients.click(clients_table_data, outputs=clients_grid)
                    load_client.click(
                        load_client_callback, inputs=selected_client,
                        outputs=[client_id, client_name, default_base_domain, gsc_sa_path, sheets_sa_path, default_database, default_gl, default_hl, client_message]
                    )
                    save_client.click(
                        save_client_callback,
                        inputs=[client_id, client_name, default_base_domain, gsc_sa_path, sheets_sa_path, default_database, default_gl, default_hl],
                        outputs=client_message
                    )

                # --- PROJECTS ---
                with gr.Group(visible=False) as view_projects:
                    gr.Markdown("## Project Workspace")
                    selected_project = gr.Dropdown(project_choices(), label="Existing project")
                    with gr.Row():
                        refresh_projects = gr.Button("Refresh projects")
                        load_project = gr.Button("Load selected project", variant="primary", elem_classes=["btn-primary"])
                    projects_grid = gr.Dataframe(
                        headers=["Project ID", "Name", "Client", "Domain", "GSC", "GA4", "Type", "LLM", "SERP"],
                        value=projects_table_data(), interactive=False, label="Project list"
                    )
                    effective_preview = gr.Markdown("Select a project to preview its effective configuration.", elem_classes=["status-panel"])
                    with gr.Accordion("Project Configuration", open=True):
                        with gr.Row():
                            project_id = gr.Textbox(label="Project ID")
                            project_client_id = gr.Textbox(label="Client ID")
                            project_name = gr.Textbox(label="Name")
                        with gr.Row():
                            base_domain = gr.Textbox(label="Base domain override")
                            project_database = gr.Dropdown([None, *SEMRUSH_DATABASES], value=None, label="SEMrush database override")
                            project_gl = gr.Dropdown([None, *GOOGLE_GL_OPTIONS], value=None, label="Google gl override")
                            project_hl = gr.Dropdown([None, *GOOGLE_HL_OPTIONS], value=None, label="Google hl override")
                        with gr.Row():
                            gsc_property = gr.Textbox(label="GSC property")
                            ga4_property_id = gr.Textbox(label="GA4 property ID")
                            sheets_id = gr.Textbox(label="Google Sheets ID or URL")
                            project_type = gr.Dropdown(PROJECT_TYPE_OPTIONS, value="content", label="Project type")
                            output_dir = gr.Textbox(value="runs", label="Output directory")
                        with gr.Row():
                            llm_provider = gr.Dropdown(LLM_PROVIDER_OPTIONS, value=DEFAULT_LLM_PROVIDER, label="Default LLM provider")
                            llm_model = gr.Dropdown(OLLAMA_MODEL_OPTIONS, value=DEFAULT_LLM_MODEL, label="Default model")
                            llm_base_url = gr.Textbox(value=DEFAULT_OLLAMA_BASE_URL, label="LLM base URL")
                        with gr.Row():
                            serpapi_enabled = gr.Checkbox(value=True, label="Use SerpAPI")
                            dataforseo_enabled = gr.Checkbox(value=True, label="Use DataForSEO fallback")
                        save_project = gr.Button("Save project", variant="primary", elem_classes=["btn-primary"])
                        project_message = gr.Markdown()
                    with gr.Row():
                        activate_project = gr.Button("Activate project")
                        active_message = gr.Markdown()
                    with gr.Accordion("Duplicate Project", open=False):
                        duplicate_source = gr.Textbox(label="Source project ID")
                        duplicate_target = gr.Textbox(label="New project ID")
                        duplicate_name = gr.Textbox(label="New project name")
                        duplicate_button = gr.Button("Duplicate project")
                        duplicate_message = gr.Markdown()
                    with gr.Accordion("Discover Sheets from Drive", open=False):
                        sheets_query = gr.Textbox(label="Search Google Sheets")
                        discover_sheets = gr.Button("Discover Sheets")
                        sheets_listing = gr.Markdown()

                    llm_provider.change(model_options_callback, inputs=llm_provider, outputs=llm_model)
                    selected_project.change(effective_config_markdown, inputs=selected_project, outputs=effective_preview)
                    refresh_projects.click(refresh_projects_callback, inputs=project_client_id, outputs=[selected_project, project_message])
                    refresh_projects.click(projects_table_data, inputs=project_client_id, outputs=projects_grid)
                    load_project.click(
                        load_project_callback, inputs=selected_project,
                        outputs=[project_id, project_client_id, project_name, base_domain, project_database, project_gl, project_hl, gsc_property, ga4_property_id, sheets_id, project_type, output_dir, llm_provider, llm_model, llm_base_url, serpapi_enabled, dataforseo_enabled, project_message]
                    )
                    load_project.click(effective_config_markdown, inputs=selected_project, outputs=effective_preview)
                    save_project.click(
                        save_project_callback,
                        inputs=[project_id, project_client_id, project_name, base_domain, project_database, project_gl, project_hl, gsc_property, ga4_property_id, sheets_id, project_type, output_dir, llm_provider, llm_model, llm_base_url, serpapi_enabled, dataforseo_enabled],
                        outputs=project_message
                    )
                    activate_project.click(activate_project_callback, inputs=[project_client_id, project_id], outputs=active_message)
                    discover_sheets.click(discover_sheets_callback, inputs=[project_client_id, sheets_query], outputs=sheets_listing)
                    duplicate_button.click(duplicate_project_callback, inputs=[duplicate_source, duplicate_target, duplicate_name], outputs=duplicate_message)

                # --- LAUNCH (Unified with Preflight) ---
                with gr.Group(visible=False) as view_launch:
                    gr.Markdown("## Briefing Launcher & Preflight")
                    with gr.Row():
                        run_client_id = gr.Dropdown(client_dropdown_choices(), label="Client")
                        run_project_id = gr.Dropdown(project_dropdown_choices(), label="Project")
                        brief_type = gr.Radio([("New page", "new_page"), ("Existing page", "existing_page")], value="new_page", label="Briefing type")
                    with gr.Row():
                        keyword = gr.Textbox(label="Keyword")
                        target_url = gr.Textbox(label="Target URL")
                    with gr.Accordion("Advanced Configuration", open=False):
                        with gr.Row():
                            provider = gr.Dropdown(LLM_PROVIDER_OPTIONS, value=DEFAULT_LLM_PROVIDER, label="LLM Provider override")
                            model = gr.Dropdown(OLLAMA_MODEL_OPTIONS, value=DEFAULT_LLM_MODEL, label="Model override")
                            ollama_base_url = gr.Textbox(value=DEFAULT_OLLAMA_BASE_URL, label="Ollama Base URL")
                            upload = gr.Checkbox(value=False, label="Export to Google Sheets")

                    with gr.Row():
                        preview_button = gr.Button("1. Analyze Readiness & Preview", variant="secondary")
                        run_live_checks = gr.Button("Run live provider checks", variant="secondary")
                        run_button = gr.Button("2. Launch Briefing", variant="primary", elem_classes=["btn-primary"])

                    checks_output = gr.Markdown()
                    run_preview = gr.Markdown(elem_classes=["status-panel"])
                    run_output = gr.Markdown()

                    run_projects_hidden = gr.Dataframe(visible=False)
                    run_client_id.change(context_client_changed_callback, inputs=run_client_id, outputs=[run_project_id, run_projects_hidden, run_preview])
                    provider.change(model_options_callback, inputs=provider, outputs=model)

                    preview_button.click(
                        preflight_config_callback, inputs=[run_client_id, run_project_id], outputs=checks_output
                    ).then(
                        launch_preview_callback,
                        inputs=[run_client_id, run_project_id, brief_type, keyword, target_url, upload],
                        outputs=run_preview
                    )
                    run_live_checks.click(preflight_live_callback, inputs=[run_client_id, run_project_id, keyword], outputs=checks_output)
                    run_button.click(
                        guarded_launch_briefing_callback,
                        inputs=[run_client_id, run_project_id, brief_type, keyword, target_url, provider, model, ollama_base_url, upload],
                        outputs=run_output
                    )

                # --- RUNS WORKSPACE ---
                with gr.Group(visible=False) as view_runs:
                    gr.Markdown("## Runs Workspace")
                    with gr.Row():
                        limit = gr.Number(value=50, label="Limit", precision=0)
                        status_filter = gr.Dropdown(["", "queued", "running", "done", "failed"], value="", label="Status")
                        search_filter = gr.Textbox(label="Search")
                        refresh = gr.Button("Refresh runs", variant="primary", elem_classes=["btn-primary"])
                    runs_grid = gr.HTML(
                        value=runs_table_html(DEFAULT_STORE, limit=50), label="Runs"
                    )
                    run_id = gr.Textbox(label="Run ID")
                    with gr.Row():
                        detail_button = gr.Button("Load detail")
                        cancel_button = gr.Button("Cancel run")
                        delete_button = gr.Button("Delete metadata", elem_classes=["danger-action"])
                    detail = gr.Markdown(elem_classes=["status-panel"])
                    with gr.Accordion("Cleanup terminal jobs", open=False):
                        cleanup_age = gr.Number(value=30, label="Max age days", precision=0)
                        cleanup_button = gr.Button("Cleanup done/failed metadata")
                        cleanup_message = gr.Markdown()
                    refresh.click(refresh_runs_html_callback, inputs=[limit, status_filter, search_filter], outputs=runs_grid)
                    detail_button.click(run_detail_callback, inputs=run_id, outputs=detail)
                    cancel_button.click(cancel_run_callback, inputs=run_id, outputs=detail)
                    delete_button.click(delete_run_callback, inputs=run_id, outputs=detail)
                    cleanup_button.click(cleanup_runs_callback, inputs=cleanup_age, outputs=cleanup_message)

        # Handle Navigation state
        def show_view(view_name):
            return [
                gr.update(visible=(view_name == "home")),
                gr.update(visible=(view_name == "settings")),
                gr.update(visible=(view_name == "clients")),
                gr.update(visible=(view_name == "projects")),
                gr.update(visible=(view_name == "launch")),
                gr.update(visible=(view_name == "runs")),
            ]

        # Use partials/lambdas to map clicks
        views = [view_home, view_settings, view_clients, view_projects, view_launch, view_runs]
        nav_home.click(lambda: show_view("home"), outputs=views)
        nav_settings.click(lambda: show_view("settings"), outputs=views)
        nav_clients.click(lambda: show_view("clients"), outputs=views)
        nav_projects.click(lambda: show_view("projects"), outputs=views)
        nav_launch.click(lambda: show_view("launch"), outputs=views)
        nav_runs.click(lambda: show_view("runs"), outputs=views)

        # Keep context panel updated when context changes
        set_context.click(lambda: active_context_markdown(), outputs=sidebar_context)
        activate_project.click(lambda: active_context_markdown(), outputs=sidebar_context)

    return app


def _persist_job_output_from_result(store: JobStore, run_id: str, keyword: str, result: dict) -> None:
    briefing = result.get("briefing")
    row24 = result.get("row24")
    briefing_payload = briefing.model_dump() if hasattr(briefing, "model_dump") else briefing
    row24_payload = row24.model_dump() if hasattr(row24, "model_dump") else row24
    prompt_run = result.get("prompt_run") if isinstance(result.get("prompt_run"), dict) else {}
    artifacts = {
        key: str(value)
        for key, value in result.items()
        if key in {
            "json",
            "markdown",
            "csv",
            "xlsx",
            "metrics_path",
            "serp_raw_path",
            "audit_path",
            "target_audit_path",
            "ai_search_readiness_path",
        }
    }
    store.persist_job_output(
        run_id,
        keyword=keyword,
        briefing=briefing_payload if isinstance(briefing_payload, dict) else None,
        row24=row24_payload if isinstance(row24_payload, dict) else None,
        artifacts=artifacts,
        provider=prompt_run.get("provider"),
        model=prompt_run.get("model"),
    )


def _set_model_env(provider: str, model: str, ollama_base_url: str) -> None:
    provider = (provider or "openai").strip().lower()
    os.environ["LLM_PROVIDER"] = provider
    if model.strip():
        os.environ["LLM_MODEL"] = model.strip()
        if provider == "ollama":
            os.environ["OLLAMA_MODEL"] = model.strip()
        if provider == "anthropic":
            os.environ["ANTHROPIC_MODEL"] = model.strip()
    if provider == "ollama" and ollama_base_url.strip():
        os.environ["OLLAMA_BASE_URL"] = ollama_base_url.strip()


def _set_active_project_runtime(provider: str, model: str, ollama_base_url: str) -> None:
    cfg = get_config()
    if not cfg.active_project:
        return
    provider = (provider or "openai").strip().lower()
    current_serp = cfg.active_project.runtime.providers.serp.provider_order
    cfg.active_project.runtime = ProjectRuntimeConfig(
        llm={
            "provider": provider,
            "model": model.strip() or None,
            "base_url": ollama_base_url.strip() if provider == "ollama" and ollama_base_url.strip() else None,
            "prompt_version": cfg.active_project.runtime.llm.prompt_version,
        },
        providers={"serp": {"provider_order": current_serp}},
    )


def _restore_env(values: dict[str, str | None]) -> None:
    for key, value in values.items():
        if value is None:
            os.environ.pop(key, None)
        else:
            os.environ[key] = value


def _activate_context(client_id: str, project_id: str) -> str | None:
    client_id = client_id.strip()
    project_id = project_id.strip()
    if not client_id and not project_id:
        return None
    cfg = get_config()
    if client_id and not cfg.set_active_client(client_id):
        return "Client not found."
    if project_id and not cfg.set_active_project(project_id):
        return "Project not found."
    if project_id and client_id and cfg.active_project and cfg.active_project.client_id != client_id:
        return "Project does not belong to client."
    return None


def _normalize_brief_type(value: str) -> str:
    normalized = (value or "new_page").strip().lower()
    if normalized in {"new", "new page", "pagina nueva", "p\u00e1gina nueva"}:
        return "new_page"
    if normalized in {"existing", "existing page", "pagina existente", "p\u00e1gina existente"}:
        return "existing_page"
    return normalized if normalized in BRIEF_TYPES else "new_page"


def _slug(value: str) -> str:
    return "_".join(value.strip().split())


def _optional(value: object) -> str | None:
    if value is None:
        return None
    stripped = str(value).strip()
    return stripped or None


def _keep_or_none(value: str, current: str | None) -> str | None:
    stripped = value.strip()
    if stripped:
        return stripped
    return current


def _yes_no(value: object) -> str:
    return "yes" if value else "no"


if __name__ == "__main__":
    build_app().launch(theme=build_theme(), css=APP_CSS)
