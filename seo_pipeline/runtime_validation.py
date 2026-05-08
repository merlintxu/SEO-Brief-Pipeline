"""Runtime preflight validation for pipeline execution."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol


class _RuntimeConfig(Protocol):
    active_client: object | None
    active_project: object | None


@dataclass(frozen=True)
class RuntimeRequirements:
    """Resolved runtime capabilities used by the pipeline."""

    has_serpapi: bool
    has_dataforseo: bool
    can_run_gsc: bool
    can_upload_sheets: bool


class RuntimeValidationError(RuntimeError):
    """Raised when required runtime configuration is missing."""


def validate_runtime_requirements(
    cfg: _RuntimeConfig,
    *,
    require_semrush: bool = True,
    require_serp: bool = True,
    require_openai: bool = True,
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

    has_serpapi = bool(getattr(client, "serpapi_key", None))
    has_dataforseo = bool(
        getattr(client, "dataforseo_login", None)
        and getattr(client, "dataforseo_password", None)
    )

    if require_semrush and not getattr(client, "semrush_token", None):
        missing.append("SEMRUSH_TOKEN")
    if require_serp and not (has_serpapi or has_dataforseo):
        missing.append("SERPAPI_KEY o credenciales DataForSEO completas")
    if require_openai and not getattr(client, "openai_key", None):
        missing.append("OPENAI_API_KEY")
    if missing:
        raise RuntimeValidationError("Configuracion incompleta: falta " + ", ".join(missing))

    return RuntimeRequirements(
        has_serpapi=has_serpapi,
        has_dataforseo=has_dataforseo,
        can_run_gsc=bool(getattr(client, "gsc_sa_path", None) and getattr(project, "gsc_property", None)),
        can_upload_sheets=bool(getattr(client, "sheets_sa_path", None) and getattr(project, "sheets_id", None)),
    )
