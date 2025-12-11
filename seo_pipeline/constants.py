# seo_pipeline/constants.py
"""
Constantes centrales del pipeline SEO.
Mantener todo en un único archivo facilita cambios futuros
y garantiza consistencia en todo el proyecto (Sheets, prompts, límites, etc.).
"""
from __future__ import annotations
from typing import Final, List

# ==============================
# Google Sheets — 24 columnas exactas
# ==============================
HEADERS_24: Final[List[str]] = [
    "kw_principal", "sv_principal", "kw_secundarias", "url_objetivo",
    "title", "h1", "meta_desc", "slugs_relacionados",
    "ai_overview_present", "paa_count", "related_count", "kg_present",
    "schema_article", "schema_product", "schema_breadcrumb", "schema_faq",
    "top_competitor_1", "top_competitor_2", "top_competitor_3",
    "anchor_primary", "anchor_secondary", "anchor_internal",
    "notes", "run_id"
]

# Columnas clave para upsert idempotente en Sheets
SHEET_ROW_KEYCOLS: Final[List[str]] = ["kw_principal", "url_objetivo"]

# ==============================
# Límites y configuraciones por defecto
# ==============================
DEFAULT_RELATED_LIMIT: Final[int] = 60          # Keywords relacionadas SEMrush
DEFAULT_SERP_NUM: Final[int] = 12              # Resultados orgánicos a analizar
DEFAULT_TOP_COMPETITORS: Final[int] = 3        # Hosts/dominios competidores a extraer
DEFAULT_CACHE_TTL_DAYS: Final[int] = 30         # Caché SEMrush / SERP
DEFAULT_UNITS_MIN_REQUIRED: Final[int] = 5     # Mínimo units SEMrush antes de llamar

# ==============================
# Prompts y configuraciones LLM (blueprint)
# ==============================
BRIEFING_SYSTEM_PROMPT: Final[str] = (
    "Eres un consultor SEO senior especializado en redacción de briefings de contenido "
    "optimizados para Google en 2025-2026. Tu objetivo es generar un briefing extremadamente "
    "detallado, accionable y orientado a resultados que supere a la competencia actual."
)

# ==============================
# Mensajes de diagnóstico
# ==============================
ERROR_MESSAGES: Final[dict[str, str]] = {
    "semrush_122": "SEMrush ERROR 122: API key inválida o sin permiso para el reporte solicitado.",
    "semrush_units": "SEMrush sin unidades suficientes para ejecutar la consulta.",
    "serpapi_limit": "Límite de consultas SerpAPI alcanzado o clave inválida.",
    "gsc_auth": "Fallo de autenticación Google Search Console (verifica SA o OAuth).",
}

# ==============================
# Versionado del pipeline
# ==============================
PIPELINE_VERSION: Final[str] = "2025.11.18"
