from pathlib import Path

from api.job_store import JobStore
from apps.gradio_app import job_detail_markdown, launch_briefing_callback, list_jobs_markdown


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
