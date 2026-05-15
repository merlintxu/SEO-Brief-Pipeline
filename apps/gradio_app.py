"""Gradio operator UI for DB-first SEO briefing runs."""
from __future__ import annotations

import os
from datetime import datetime
from pathlib import Path
from typing import Callable

from api.job_lifecycle import JobLifecycleService
from api.job_store import JobStore
from seo_pipeline.artifacts import RUN_METRICS_JSON
from seo_pipeline.config import ProjectRuntimeConfig, get_config
from seo_pipeline.pipeline import run_full_pipeline
from seo_pipeline.utils.io import ensure_dir, load_json


DEFAULT_STORE = JobStore(Path("outputs") / "jobs.db")


def list_jobs_markdown(limit: int = 20, *, store: JobStore = DEFAULT_STORE) -> str:
    jobs = store.list_jobs(limit=max(1, min(int(limit), 200)))
    if not jobs:
        return "No jobs found."
    rows = ["| Run ID | Keyword | Status | Step | Updated |", "|---|---|---|---|---|"]
    for job in jobs:
        rows.append(f"| `{job.run_id}` | {job.keyword} | {job.status} | {job.step} | {job.updated_at} |")
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
    *,
    store: JobStore = DEFAULT_STORE,
    pipeline_func: Callable[..., dict] = run_full_pipeline,
) -> str:
    keyword = keyword.strip()
    if not keyword:
        return "Keyword is required."
    run_id = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
    run_dir = Path("outputs") / run_id
    ensure_dir(run_dir)
    status_path = run_dir / "status.json"
    lifecycle = JobLifecycleService(store)
    lifecycle.enqueue(run_id=run_id, keyword=keyword, output_dir=run_dir, status_path=status_path)
    if not lifecycle.start(run_id):
        return f"Run {run_id} could not start."

    old_env = {key: os.environ.get(key) for key in ("LLM_PROVIDER", "LLM_MODEL", "OLLAMA_MODEL", "OLLAMA_BASE_URL", "ANTHROPIC_MODEL")}
    cfg = get_config()
    old_runtime = cfg.active_project.runtime if cfg.active_project else None
    try:
        _set_model_env(provider, model, ollama_base_url)
        _set_active_project_runtime(provider, model, ollama_base_url)
        result = pipeline_func(
            keyword=keyword,
            target_url=target_url.strip() or None,
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


def build_app():
    import gradio as gr

    with gr.Blocks(title="SEO Brief Pipeline Ops") as app:
        gr.Markdown("# SEO Brief Pipeline Ops")
        with gr.Tab("Run"):
            keyword = gr.Textbox(label="Keyword")
            target_url = gr.Textbox(label="Target URL")
            provider = gr.Dropdown(["openai", "ollama", "anthropic"], value="openai", label="LLM Provider")
            model = gr.Textbox(label="Model override")
            ollama_base_url = gr.Textbox(value="http://localhost:11434", label="Ollama Base URL")
            upload = gr.Checkbox(value=False, label="Upload to Google Sheets")
            run_button = gr.Button("Run briefing", variant="primary")
            run_output = gr.Markdown()
            run_button.click(
                launch_briefing_callback,
                inputs=[keyword, target_url, provider, model, ollama_base_url, upload],
                outputs=run_output,
            )
        with gr.Tab("Jobs"):
            limit = gr.Number(value=20, label="Limit", precision=0)
            refresh = gr.Button("Refresh")
            jobs = gr.Markdown()
            refresh.click(list_jobs_markdown, inputs=limit, outputs=jobs)
        with gr.Tab("Detail"):
            run_id = gr.Textbox(label="Run ID")
            detail_button = gr.Button("Load detail")
            detail = gr.Markdown()
            detail_button.click(job_detail_markdown, inputs=run_id, outputs=detail)
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
        if key in {"json", "markdown", "csv", "xlsx", "metrics_path", "serp_raw_path", "audit_path"}
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


if __name__ == "__main__":
    build_app().launch()
