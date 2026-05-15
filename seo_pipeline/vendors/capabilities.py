from __future__ import annotations

import os
from dataclasses import dataclass

from seo_pipeline.config import ClientConfig, ProjectConfig


def _env_bool(name: str, default: bool) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


@dataclass(frozen=True)
class SerpProviderPlan:
    provider_order: tuple[str, ...]
    use_serpapi: bool
    use_dataforseo: bool


def resolve_serp_provider_plan(
    client: ClientConfig | None,
    project: ProjectConfig | None = None,
) -> SerpProviderPlan:
    # Defaults keep existing behavior: SerpAPI primary, DataForSEO fallback.
    enable_serpapi = _env_bool("SERP_ENABLE_SERPAPI", True)
    enable_dataforseo = _env_bool("SERP_ENABLE_DATAFORSEO", True)
    if project:
        requested = tuple(project.runtime.providers.serp.provider_order)
    else:
        order_raw = os.getenv("SERP_PROVIDER_ORDER", "serpapi,dataforseo")
        requested = tuple(item.strip().lower() for item in order_raw.split(",") if item.strip())

    has_serpapi_key = bool(client and client.serpapi_key)
    has_dfso_creds = bool(client and client.dataforseo_login and client.dataforseo_password)

    allowed: list[str] = []
    for name in requested:
        if name not in {"serpapi", "dataforseo"}:
            continue
        if name == "serpapi" and enable_serpapi and has_serpapi_key:
            allowed.append(name)
        if name == "dataforseo" and enable_dataforseo and has_dfso_creds:
            allowed.append(name)

    # Environment fallback preserves legacy behavior. Project runtime order is
    # explicit, so missing credentials should surface as an empty plan.
    if not allowed and project is None:
        if enable_serpapi and has_serpapi_key:
            allowed.append("serpapi")
        if enable_dataforseo and has_dfso_creds:
            allowed.append("dataforseo")

    return SerpProviderPlan(
        provider_order=tuple(allowed),
        use_serpapi="serpapi" in allowed,
        use_dataforseo="dataforseo" in allowed,
    )
