"""Runtime preflight validation for pipeline execution."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from seo_pipeline.llm.config import LlmSettings


class _RuntimeConfig(Protocol):
    active_client: object | None
    active_project: object | None


@dataclass(frozen=True)
class RuntimeRequirements:
    """Resolved runtime capabilities used by the pipeline."""

    has_serpapi: bool
    has_dataforseo: bool
    can_run_gsc: bool
    can_run_ga4: bool
    can_upload_sheets: bool


class RuntimeValidationError(RuntimeError):
    """Raised when required runtime configuration is missing."""


def validate_runtime_requirements(
    cfg: _RuntimeConfig,
    *,
    require_semrush: bool = True,
    require_serp: bool = True,
    require_openai: bool = True,
    llm_settings: LlmSettings | None = None,
) -> RuntimeRequirements:
    """Validate required runtime capabilities without exposing secret values."""
    missing: list[str] = []

    client = cfg.active_client
    project = cfg.active_project

    if client is None:
        missing.append("active_client")
    if project is None:
        missing.append("active_project")
    if missing:
        raise RuntimeValidationError("Configuracion incompleta: falta " + ", ".join(missing))

    if hasattr(cfg, "apply_effective_client_defaults"):
        client = cfg.apply_effective_client_defaults(client)

    has_serpapi = bool(getattr(client, "serpapi_key", None))
    has_dataforseo = bool(
        getattr(client, "dataforseo_login", None)
        and getattr(client, "dataforseo_password", None)
    )

    if require_semrush and not getattr(client, "semrush_token", None):
        missing.append("SEMRUSH_TOKEN")
    project_runtime = getattr(project, "runtime", None)
    serp_order: list[str] = []
    if project_runtime is None:
        missing.append("project.runtime")
    else:
        llm_config = getattr(project_runtime, "llm", None)
        serp_config = getattr(getattr(project_runtime, "providers", None), "serp", None)
        if llm_config is None:
            missing.append("project.runtime.llm")
        if serp_config is None or not getattr(serp_config, "provider_order", None):
            missing.append("project.runtime.providers.serp.provider_order")
        else:
            serp_order = list(getattr(serp_config, "provider_order", []))

    if require_serp and not any(
        (provider == "serpapi" and has_serpapi)
        or (provider == "dataforseo" and has_dataforseo)
        for provider in serp_order
    ):
        missing.append("credentials for project.runtime.providers.serp.provider_order")

    active_llm = llm_settings
    if active_llm is not None and active_llm.provider not in {"openai", "ollama", "anthropic"}:
        missing.append("project.runtime.llm.provider")

    if require_openai and not (getattr(client, "openai_key", None) or (active_llm and active_llm.api_key)):
        missing.append("OPENAI_API_KEY")
    if active_llm and active_llm.provider == "anthropic" and not active_llm.api_key:
        missing.append("ANTHROPIC_API_KEY")
    if active_llm and active_llm.provider == "ollama" and not active_llm.model:
        missing.append("OLLAMA_MODEL o project.runtime.llm.model")
    if missing:
        raise RuntimeValidationError("Configuracion incompleta: falta " + ", ".join(missing))

    return RuntimeRequirements(
        has_serpapi=has_serpapi,
        has_dataforseo=has_dataforseo,
        can_run_gsc=bool(getattr(client, "gsc_sa_path", None) and getattr(project, "gsc_property", None)),
        can_run_ga4=bool(getattr(client, "gsc_sa_path", None) and getattr(project, "ga4_property_id", None)),
        can_upload_sheets=bool(getattr(client, "sheets_sa_path", None) and getattr(project, "sheets_id", None)),
    )
