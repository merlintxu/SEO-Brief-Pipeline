from pathlib import Path

from api.job_store import JobStore
from seo_pipeline.config import ClientConfig, ProjectConfig, get_config
from apps.gradio_app import (
    activate_project_callback,
    guarded_launch_briefing_callback,
    home_refresh_callback,
    launch_preview_callback,
    connection_checks_callback,
    job_detail_markdown,
    launch_briefing_callback,
    load_client_callback,
    load_project_callback,
    list_jobs_markdown,
    refresh_clients_callback,
    refresh_projects_callback,
    save_client_callback,
    save_project_callback,
)


def test_gradio_list_and_detail_callbacks(tmp_path: Path):
    store = JobStore(tmp_path / "jobs.db")
    store.create_job("run1", "kw one", "outputs/run1")
    store.update_status("run1", status="done", step="done", message="ok")
    store.persist_job_output(
        "run1",
        keyword="kw one",
        briefing={"h1": "H1", "meta_title": "Title", "meta_description": "Desc"},
        row24={"Keyword": "kw one"},
        artifacts={"json": "outputs/run1/briefing.json"},
        provider="openai",
        model="gpt-4o",
    )

    listing = list_jobs_markdown(store=store)
    detail = job_detail_markdown("run1", store=store)

    assert "run1" in listing
    assert "kw one" in listing
    assert "H1" in detail
    assert "openai / gpt-4o" in detail


def test_gradio_launch_callback_runs_pipeline_and_persists_output(tmp_path: Path, monkeypatch):
    store = JobStore(tmp_path / "jobs.db")

    def fake_pipeline(**kwargs):
        output_dir = Path(kwargs["output_dir"])
        output_dir.mkdir(parents=True, exist_ok=True)
        status_path = Path(kwargs["status_path"])
        status_path.write_text('{"status":"done","step":"done","message":"ok"}', encoding="utf-8")
        metrics_path = output_dir / "run_metrics.json"
        metrics_path.write_text('{"status":"done","stages":{}}', encoding="utf-8")
        return {
            "briefing": {"h1": "Generated", "meta_title": "Meta", "meta_description": "Desc"},
            "row24": {"Keyword": kwargs["keyword"]},
            "json": output_dir / "briefing.json",
            "metrics_path": metrics_path,
            "prompt_run": {"provider": "ollama", "model": "llama3.1"},
        }

    monkeypatch.chdir(tmp_path)

    message = launch_briefing_callback(
        "kw",
        "",
        "ollama",
        "llama3.1",
        "http://localhost:11434",
        False,
        store=store,
        pipeline_func=fake_pipeline,
    )

    jobs = store.list_jobs(limit=10)
    assert "completed" in message
    assert len(jobs) == 1
    assert jobs[0].status == "done"
    output = store.get_job_output(jobs[0].run_id)
    assert output.briefing_json["h1"] == "Generated"
    assert store.get_briefing_record(jobs[0].run_id).provider == "ollama"


def test_gradio_client_project_callbacks_persist_config(tmp_path: Path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    cfg = get_config()
    cfg.clients = {}
    cfg.projects = {}
    cfg.clients_file = tmp_path / "clients.json"
    cfg.projects_file = tmp_path / "projects.json"

    client_message = save_client_callback(
        "Client A",
        "Client A",
        "https://example.com",
        "credentials/gsc.json",
        "credentials/sheets.json",
        "es",
        "es",
        "es-es",
    )
    project_message = save_project_callback(
        "Project A",
        "Client_A",
        "Project A",
        "",
        None,
        None,
        None,
        "https://example.com/",
        "123456",
        "",
        "content",
        "runs",
        "openai",
        "gpt-4o",
        "",
        True,
        True,
    )
    active_message = activate_project_callback("Client_A", "Project_A")

    assert "saved" in client_message
    assert "saved" in project_message
    assert "Client_A" in active_message
    assert cfg.clients["Client_A"].gsc_sa_path == "credentials/gsc.json"
    assert cfg.clients["Client_A"].default_base_domain == "https://example.com"
    assert cfg.projects["Project_A"].ga4_property_id == "123456"

    loaded_client = load_client_callback("Client_A")
    loaded_project = load_project_callback("Project_A")

    assert loaded_client[0] == "Client_A"
    assert loaded_client[2] == "https://example.com"
    assert loaded_project[0] == "Project_A"
    assert loaded_project[1] == "Client_A"
    assert loaded_project[8] == "123456"


def test_gradio_refresh_callbacks_return_choices(tmp_path: Path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    cfg = get_config()
    cfg.clients = {"c1": ClientConfig(client_id="c1", name="Client")}
    cfg.projects = {
        "p1": ProjectConfig(
            project_id="p1",
            client_id="c1",
            name="Project",
            base_domain="https://example.com",
            gsc_property="",
            sheets_id="",
        )
    }

    client_update, clients_listing = refresh_clients_callback()
    project_update, projects_listing = refresh_projects_callback("c1")

    assert "c1" in client_update["choices"]
    assert "p1" in project_update["choices"]
    assert "Client" in clients_listing
    assert "p1" in projects_listing


def test_gradio_connection_checks_callback_uses_selected_context(tmp_path: Path, monkeypatch):
    cfg = get_config()
    cfg.clients = {
        "c1": ClientConfig(client_id="c1", name="Client", semrush_token=None, serpapi_key=None, openai_key=None)
    }
    cfg.projects = {
        "p1": ProjectConfig(
            project_id="p1",
            client_id="c1",
            name="Project",
            base_domain="https://example.com",
            gsc_property="",
            sheets_id="",
        )
    }
    monkeypatch.setattr(
        "apps.gradio_app.run_connection_checks",
        lambda client, project, keyword: [],
    )

    message = connection_checks_callback("c1", "p1", "test")

    assert "Service" in message


def test_gradio_home_and_launch_preview_callbacks(tmp_path: Path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    cfg = get_config()
    cfg.clients = {"c1": ClientConfig(client_id="c1", name="Client", default_base_domain="https://example.com")}
    cfg.projects = {
        "p1": ProjectConfig(
            project_id="p1",
            client_id="c1",
            name="Project",
            gsc_property="",
            sheets_id="",
        )
    }

    home_status, client_update, project_update, context, clients, projects = home_refresh_callback()
    preview = launch_preview_callback("c1", "p1", "new_page", "keyword", "", False)

    assert "Home" in home_status
    assert ("Client (c1)", "c1") in client_update["choices"]
    assert ("Project (p1)", "p1") in project_update["choices"]
    assert "Client" in context
    assert clients[0][0] == "c1"
    assert projects[0][0] == "p1"
    assert "Run Preview" in preview


def test_gradio_guarded_launch_blocks_invalid_existing_page(tmp_path: Path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    cfg = get_config()
    cfg.clients = {"c1": ClientConfig(client_id="c1", name="Client", default_base_domain="https://example.com")}
    cfg.projects = {
        "p1": ProjectConfig(
            project_id="p1",
            client_id="c1",
            name="Project",
            gsc_property="",
            sheets_id="",
        )
    }

    message = guarded_launch_briefing_callback(
        "c1",
        "p1",
        "existing_page",
        "keyword",
        "",
        "ollama",
        "gemma4:26b",
        "http://localhost:11434",
        False,
        store=JobStore(tmp_path / "jobs.db"),
        pipeline_func=lambda **kwargs: {},
    )

    assert "Cannot launch" in message
    assert "Target URL is required" in message
