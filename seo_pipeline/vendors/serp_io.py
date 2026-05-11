# seo_pipeline/vendors/serp_io.py
"""
Cliente SerpAPI optimizado para Google SERP en 2025.
- Soporte completo para AI Overview (citas y fuentes)
- Extracción robusta de URLs orgánicas + dominios competidores
- Caché opcional y logging detallado
- Manejo graceful de fallos y límites de cuota
"""
from __future__ import annotations

from pathlib import Path
from typing import Dict, List, Optional, Any
from urllib.parse import urlparse
import logging
import requests

from seo_pipeline.utils.io import save_json, load_json
from seo_pipeline.utils.text import uniq_preserve
from seo_pipeline.config import get_config
from pydantic import ValidationError
from seo_pipeline.models import SerpRawPayload, SerpSnapshot
from seo_pipeline.utils.logging import logger

# La librería oficial es 'google-search-results' → expone serpapi
try:
    from serpapi import GoogleSearch
    SERPAPI_AVAILABLE = True
except ImportError as e:
    GoogleSearch = None  # type: ignore
    SERPAPI_AVAILABLE = False
    logger.warning(f"SerpAPI no disponible (pip install google-search-results): {e}")


def _ensure_serpapi() -> None:
    if not SERPAPI_AVAILABLE or GoogleSearch is None:
        raise RuntimeError(
            "Librería SerpAPI no instalada. Ejecuta: pip install google-search-results"
        )


def normalize_domain(value: Optional[str]) -> str:
    """Return a comparable hostname without scheme, path, port, or leading www."""
    if not value:
        return ""
    raw = value.strip().lower()
    parsed = urlparse(raw if "://" in raw else f"//{raw}")
    host = parsed.hostname or raw.split("/", 1)[0].split(":", 1)[0]
    return host[4:] if host.startswith("www.") else host


def search_raw(
    query: str,
    api_key: str = None,
    gl: str = "es",
    hl: str = "es-es",
    num: int = 12,
    include_ai_overview: bool = True,
    timeout: int = 30,
    use_dataforseo_fallback: bool = True,
    force_disable_serpapi: bool = False,
) -> Dict:
    cfg = get_config()
    client = cfg.active_client

    # 1. Intentar SerpAPI (principal)
    if not force_disable_serpapi and (api_key or (client and client.serpapi_key)):
        params = {
            "engine": "google",
            "q": query,
            "api_key": api_key or client.serpapi_key,
            "gl": gl,
            "hl": hl,
            "num": num,
        }
        if include_ai_overview:
            params["include_ai_overview"] = "true"

        try:
            search = GoogleSearch(params)
            result = search.get_dict()  # timeout is not a valid parameter
            if "error" not in result:
                logger.info(f"SERP obtenida vía SerpAPI para: {query}")
                return result
            else:
                logger.warning(f"SerpAPI error: {result['error']} → intentando DataForSEO")
        except requests.exceptions.RequestException as e:
            logger.warning(f"SerpAPI falló por error de red: {e} → intentando DataForSEO")
        except Exception as e:
            # Otros errores (p.ej. fallo interno del cliente serpapi)
            logger.warning(f"SerpAPI falló: {e} → intentando DataForSEO")

    # 2. Fallback a DataForSEO
    has_dataforseo_credentials = bool(
        client
        and getattr(client, "dataforseo_login", None)
        and getattr(client, "dataforseo_password", None)
    )
    if use_dataforseo_fallback and has_dataforseo_credentials:
        logger.info(f"Usando DataForSEO como fallback para: {query}")
        from .dataforseo_serp import fetch_serp_dataforseo
        fallback = fetch_serp_dataforseo(
            keyword=query,
            language_code=hl,
            cache_dir=cfg.cache_dir
        )
        if fallback:
            return fallback

    raise RuntimeError("Todos los proveedores SERP fallaron (SerpAPI + DataForSEO)")

def search_and_cache(
    label: str,
    queries: Dict[str, str],
    api_key: str,
    output_dir: Path,
    gl: str = "es",
    hl: str = "es-es",
    num: int = 12
) -> Dict[str, Path]:
    """
    Ejecuta múltiples búsquedas y guarda resultados raw en disco.
    Devuelve mapping {query_key → Path}.
    """
    output_dir.mkdir(parents=True, exist_ok=True)
    results: Dict[str, Path] = {}

    for key, query in queries.items():
        safe_key = "".join(c if c.isalnum() or c in "-_" else "_" for c in key)
        filepath = output_dir / f"serp_{label}_{safe_key}.json"

        try:
            raw = search_raw(query, api_key, gl=gl, hl=hl, num=num)
            save_json(filepath, raw)
            results[key] = filepath
            logger.info(f"SERP guardada: {query[:60]} → {filepath.name}")
        except (RuntimeError, requests.exceptions.RequestException) as e:
            logger.error(f"Fallo SERP para '{query[:60]}': {e}")
        except Exception:
            # Re-raise errores inesperados para no silenciar fallos graves
            raise

    return results


def _coerce_serp_payload(serp_data: Dict[str, Any]) -> SerpRawPayload:
    try:
        return SerpRawPayload.model_validate(serp_data or {})
    except ValidationError:
        return SerpRawPayload()


def extract_top_urls(serp_data: Dict, max_urls: int = 12, include_ai_citations: bool = True) -> List[str]:
    """
    Extrae URLs orgánicas + citas del AI Overview (si existen).
    Preserva orden y elimina duplicados.
    """
    payload = _coerce_serp_payload(serp_data)
    urls: List[str] = []

    # 1. Resultados orgánicos
    for item in payload.organic_results:
        link = item.link
        if link:
            urls.append(link)

    # 2. AI Overview citations (estructura variable según año/mes)
    if include_ai_citations:
        aio = payload.ai_overview
        if aio is None:
            return uniq_preserve(urls)[:max_urls]
        for container in (aio.sources, aio.citations):
            for cite in container:
                link = cite.link or cite.source or cite.url
                if link:
                    urls.append(link)

    return uniq_preserve(urls)[:max_urls]


def normalize_serp_snapshot(serp_data: Dict, provider: str = "unknown") -> SerpSnapshot:
    """Build a provider-neutral summary for metrics and downstream contracts."""
    payload = _coerce_serp_payload(serp_data)
    params = payload.search_parameters
    return SerpSnapshot(
        provider=provider,
        query=params.q,
        gl=params.gl,
        hl=params.hl,
        organic_results_count=len(payload.organic_results),
        top_urls=extract_top_urls(serp_data, max_urls=12),
        people_also_ask_count=len(payload.people_also_ask),
        related_searches_count=len(payload.related_searches),
        ai_overview_present=payload.ai_overview is not None,
        knowledge_graph_present=payload.knowledge_graph is not None,
    )


def extract_competitor_domains(
    serp_data: Dict,
    exclude_domain: Optional[str] = None,
    max_domains: int = 3
) -> List[str]:
    """
    Extrae dominios únicos de los top resultados.
    Opcionalmente excluye el dominio propio.
    """
    urls = extract_top_urls(serp_data, max_urls=50, include_ai_citations=True)
    domains: List[str] = []
    seen: set[str] = set()
    excluded = normalize_domain(exclude_domain)

    for url in urls:
        try:
            domain = normalize_domain(url)
            if not domain:
                continue
            if excluded and (domain == excluded or domain.endswith(f".{excluded}")):
                continue
            if domain not in seen:
                seen.add(domain)
                domains.append(domain)
                if len(domains) >= max_domains:
                    break
        except (ValueError, AttributeError):
            continue

    return domains


def load_serp(filepath: Path) -> Dict:
    """Carga segura de un JSON SERP desde disco."""
    data = load_json(filepath, default={})
    if not data:
        logger.warning(f"SERP JSON vacío o corrupto: {filepath}")
    return data
