"""Operator-facing connection checks for configured providers.

Checks return sanitized status objects. They must never expose credential values.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Callable

import requests

from seo_pipeline.config import ClientConfig, ProjectConfig, get_config
from seo_pipeline.llm.config import get_llm_settings
from seo_pipeline.vendors import gsc_io
from seo_pipeline.vendors.ga4_io import fetch_url_metrics
from seo_pipeline.vendors.sheets_io import SheetHandler
from seo_pipeline.vendors.semrush_io import SemrushClient
from seo_pipeline.vendors.serp_io import search_raw


@dataclass(frozen=True)
class IntegrationCheckResult:
    service: str
    status: str
    message: str

    @property
    def ok(self) -> bool:
        return self.status == "ok"


def run_connection_checks(
    client: ClientConfig,
    project: ProjectConfig,
    *,
    keyword: str = "test",
    semrush_factory: Callable[..., SemrushClient] = SemrushClient,
    serp_search: Callable[..., dict] = search_raw,
    gsc_service_builder: Callable[..., object] = gsc_io.build_service,
    sheets_handler_factory: Callable[..., SheetHandler] = SheetHandler,
    ga4_fetcher: Callable[..., object] = fetch_url_metrics,
) -> list[IntegrationCheckResult]:
    """Run configured provider checks for one client/project pair."""
    cfg = get_config()
    if project.client_id not in cfg.clients:
        cfg.clients[project.client_id] = client
    client = cfg.apply_effective_client_defaults(client)
    checks = [
        check_semrush(client, project, keyword=keyword, semrush_factory=semrush_factory),
        check_serp(client, project, keyword=keyword, serp_search=serp_search),
        check_gsc(client, project, gsc_service_builder=gsc_service_builder),
        check_ga4(client, project, ga4_fetcher=ga4_fetcher),
        check_sheets(client, project, sheets_handler_factory=sheets_handler_factory),
        check_llm(client, project),
    ]
    return checks


def check_semrush(
    client: ClientConfig,
    project: ProjectConfig,
    *,
    keyword: str = "test",
    semrush_factory: Callable[..., SemrushClient] = SemrushClient,
) -> IntegrationCheckResult:
    if not client.semrush_token:
        return IntegrationCheckResult("semrush", "skipped", "SEMrush token is not configured.")
    try:
        semrush_factory(client.semrush_token, Path("data") / "cache").fetch_related(
            keyword,
            database=get_config().resolve_project_database(project),
            limit=1,
        )
    except Exception as exc:
        return IntegrationCheckResult("semrush", "failed", _sanitize_error(exc))
    return IntegrationCheckResult("semrush", "ok", "SEMrush query succeeded.")


def check_serp(
    client: ClientConfig,
    project: ProjectConfig,
    *,
    keyword: str = "test",
    serp_search: Callable[..., dict] = search_raw,
) -> IntegrationCheckResult:
    if not client.serpapi_key and not (client.dataforseo_login and client.dataforseo_password):
        return IntegrationCheckResult("serp", "skipped", "No SERP provider credentials configured.")
    try:
        serp_search(
            keyword,
            api_key=client.serpapi_key,
            gl=get_config().resolve_project_gl(project),
            hl=get_config().resolve_project_hl(project),
            num=1,
            use_dataforseo_fallback="dataforseo" in project.runtime.providers.serp.provider_order,
            force_disable_serpapi="serpapi" not in project.runtime.providers.serp.provider_order,
        )
    except Exception as exc:
        return IntegrationCheckResult("serp", "failed", _sanitize_error(exc))
    return IntegrationCheckResult("serp", "ok", "SERP query succeeded.")


def check_gsc(
    client: ClientConfig,
    project: ProjectConfig,
    *,
    gsc_service_builder: Callable[..., object] = gsc_io.build_service,
) -> IntegrationCheckResult:
    if not client.gsc_sa_path or not project.gsc_property:
        return IntegrationCheckResult("gsc", "skipped", "GSC service account path or property is not configured.")
    try:
        service = gsc_service_builder(client.gsc_sa_path)
        service.sites().list().execute()
    except Exception as exc:
        return IntegrationCheckResult("gsc", "failed", _sanitize_error(exc))
    return IntegrationCheckResult("gsc", "ok", "GSC service account can access Search Console.")


def check_ga4(
    client: ClientConfig,
    project: ProjectConfig,
    *,
    ga4_fetcher: Callable[..., object] = fetch_url_metrics,
) -> IntegrationCheckResult:
    if not client.gsc_sa_path or not project.ga4_property_id:
        return IntegrationCheckResult("ga4", "skipped", "GA4 service account path or property ID is not configured.")
    try:
        ga4_fetcher(
            property_id=project.ga4_property_id,
            target_url=get_config().resolve_project_base_domain(project),
            sa_json_path=client.gsc_sa_path,
        )
    except Exception as exc:
        return IntegrationCheckResult("ga4", "failed", _sanitize_error(exc))
    return IntegrationCheckResult("ga4", "ok", "GA4 Data API query succeeded.")


def check_sheets(
    client: ClientConfig,
    project: ProjectConfig,
    *,
    sheets_handler_factory: Callable[..., SheetHandler] = SheetHandler,
) -> IntegrationCheckResult:
    if not client.sheets_sa_path or not project.sheets_id:
        return IntegrationCheckResult("sheets", "skipped", "Sheets service account path or spreadsheet ID is not configured.")
    try:
        sheets_handler_factory(project.sheets_id, client.sheets_sa_path)
    except Exception as exc:
        return IntegrationCheckResult("sheets", "failed", _sanitize_error(exc))
    return IntegrationCheckResult("sheets", "ok", "Google Sheets spreadsheet is accessible.")


def check_llm(client: ClientConfig, project: ProjectConfig) -> IntegrationCheckResult:
    settings = get_llm_settings(project)
    if settings.provider == "ollama":
        try:
            response = requests.get(f"{settings.base_url.rstrip('/')}/api/tags", timeout=5)
            response.raise_for_status()
        except Exception as exc:
            return IntegrationCheckResult("llm", "failed", _sanitize_error(exc))
        return IntegrationCheckResult("llm", "ok", f"Ollama is reachable; model={settings.model or '-'}")
    if settings.provider == "anthropic":
        if not settings.api_key:
            return IntegrationCheckResult("llm", "failed", "ANTHROPIC_API_KEY is not configured.")
        return IntegrationCheckResult("llm", "ok", f"Anthropic configuration is present; model={settings.model or '-'}")
    if not (settings.api_key or client.openai_key):
        return IntegrationCheckResult("llm", "failed", "OPENAI_API_KEY is not configured.")
    return IntegrationCheckResult("llm", "ok", f"OpenAI configuration is present; model={settings.model or '-'}")


def checks_to_markdown(results: list[IntegrationCheckResult]) -> str:
    rows = ["| Service | Status | Message |", "|---|---|---|"]
    for result in results:
        rows.append(f"| {result.service} | {result.status} | {result.message} |")
    return "\n".join(rows)


def _sanitize_error(exc: Exception) -> str:
    text = str(exc) or exc.__class__.__name__
    return text.replace("\n", " ")[:300]
