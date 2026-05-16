from pathlib import Path

from api.job_store import JobStore
from seo_pipeline.config import ClientConfig, ProjectConfig, RuntimeSettings, get_config
from seo_pipeline.operator_ui import (
    cleanup_runs,
    config_preflight_results,
    duplicate_project,
    effective_config_markdown,
    get_effective_project_config,
    get_setup_health,
    launch_preview_markdown,
    run_detail_markdown,
    runs_table_data,
    set_active_context,
    validate_launch_request,
)


def _reset_config(tmp_path: Path):
    cfg = get_config()
    cfg.clients = {}
    cfg.projects = {}
    cfg.active_client = None
    cfg.active_project = None
    cfg.clients_file = tmp_path / "clients.json"
    cfg.projects_file = tmp_path / "projects.json"
    cfg.runtime_settings_file = tmp_path / "runtime_settings.json"
    cfg.runtime_settings = RuntimeSettings(
        semrush_token="semrush",
        serpapi_key="serp",
        openai_key="openai",
        llm_base_url="http://localhost:11434",
    )
    return cfg


def test_setup_health_and_active_context(tmp_path: Path):
    cfg = _reset_config(tmp_path)
    cfg.clients["c1"] = ClientConfig(client_id="c1", name="Client", default_base_domain="https://example.com")
    cfg.projects["p1"] = ProjectConfig(
        project_id="p1",
        client_id="c1",
        name="Project",
        gsc_property="",
        sheets_id="",
    )

    message = set_active_context("c1", "p1")
    health = get_setup_health()

    assert "Client" in message
    assert health.ready_for_first_run
    assert health.active_client_id == "c1"
    assert health.active_project_id == "p1"


def test_effective_project_config_marks_inherited_and_overridden_values(tmp_path: Path):
    cfg = _reset_config(tmp_path)
    cfg.clients["c1"] = ClientConfig(
        client_id="c1",
        name="Client",
        default_base_domain="https://client.example",
        default_database="es",
        default_gl="es",
        default_hl="es-es",
    )
    cfg.projects["p1"] = ProjectConfig(
        project_id="p1",
        client_id="c1",
        name="Project",
        base_domain="https://project.example",
        gsc_property="https://project.example/",
        sheets_id="sheet-id",
        google_gl="us",
    )

    effective = get_effective_project_config("p1")
    markdown = effective_config_markdown("p1")

    assert effective.domain == "https://project.example"
    assert effective.domain_source == "project override"
    assert effective.google_gl == "us"
    assert effective.google_gl_source == "project override"
    assert effective.google_hl == "es-es"
    assert effective.google_hl_source == "client default"
    assert "Effective Project Configuration" in markdown


def test_config_preflight_and_launch_validation(tmp_path: Path):
    cfg = _reset_config(tmp_path)
    cfg.clients["c1"] = ClientConfig(client_id="c1", name="Client", default_base_domain="https://example.com")
    cfg.projects["p1"] = ProjectConfig(
        project_id="p1",
        client_id="c1",
        name="Project",
        gsc_property="",
        sheets_id="",
    )

    checks = config_preflight_results("c1", "p1")
    errors = validate_launch_request(
        client_id="c1",
        project_id="p1",
        brief_type="existing_page",
        keyword="keyword",
        target_url="",
    )
    preview = launch_preview_markdown(
        client_id="c1",
        project_id="p1",
        brief_type="existing_page",
        keyword="keyword",
        target_url="",
        upload_to_sheets=False,
    )

    assert {check.service for check in checks} >= {"context", "domain", "semrush", "serp", "llm"}
    assert any("Target URL is required" in error for error in errors)
    assert "Blocking Issues" in preview


def test_runs_workspace_services(tmp_path: Path):
    store = JobStore(tmp_path / "jobs.db")
    store.create_job("run1", "keyword", "outputs/run1", client_id="c1", project_id="p1", brief_type="new_page")
    store.update_status("run1", status="running", step="start", message="running")
    store.update_status("run1", status="done", step="done", message="done")
    store.persist_run_metrics("run1", {"stages": {"semrush": {"status": "ok", "provider": "semrush", "retries": 0}}})
    store.persist_job_output(
        "run1",
        keyword="keyword",
        briefing={"h1": "H1", "meta_title": "Title", "meta_description": "Desc"},
        row24={"Keyword": "keyword"},
        artifacts={"json": "outputs/run1/briefing.json"},
        provider="openai",
        model="gpt-4o",
    )

    rows = runs_table_data(store, limit=10)
    detail = run_detail_markdown("run1", store)
    cleanup_message = cleanup_runs(store, max_age_days=1)

    assert rows[0][0] == "run1"
    assert "Stage Metrics" in detail
    assert "H1" in detail
    assert "Cleanup deleted" in cleanup_message


def test_duplicate_project(tmp_path: Path):
    cfg = _reset_config(tmp_path)
    cfg.clients["c1"] = ClientConfig(client_id="c1", name="Client", default_base_domain="https://example.com")
    cfg.projects["p1"] = ProjectConfig(
        project_id="p1",
        client_id="c1",
        name="Project",
        gsc_property="",
        sheets_id="",
    )

    message = duplicate_project("p1", "p2", "Project Copy")

    assert "duplicated" in message
    assert cfg.projects["p2"].name == "Project Copy"
