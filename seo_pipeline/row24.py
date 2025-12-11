# seo_pipeline/row24.py
"""
Construcción de la fila de 24 columnas para Google Sheets.
Centraliza toda la lógica de mapeo y transformación.
"""
from __future__ import annotations

from typing import List
from seo_pipeline.models import SheetRow24, AnchorSet
from seo_pipeline.constants import HEADERS_24
from seo_pipeline.utils.text import uniq_preserve

def build_row24(
    kw: str,
               sv: int,
               secondary_kws: List[str],
               target_url: str,
               briefing: dict,
               serp_data: dict,
               anchors: AnchorSet,
               top_competitors: List[str],
               run_id: str) -> SheetRow24:
    """
    Construye el objeto SheetRow24 listo para exportar a Google Sheets.
    """
    return SheetRow24(
        kw_principal=kw,
        sv_principal=sv,
        kw_secundarias=secondary_kws[:20],  # límite razonable
        url_objetivo=target_url,
        title=briefing.meta_title,
        h1=briefing.h1,
        meta_desc=briefing.meta_description,
        slugs_relacionados=[],  # opcional futuro
        ai_overview_present=bool(serp_data.get("ai_overview")),
        paa_count=len(serp_data.get("people_also_ask", [])),
        related_count=len(serp_data.get("related_searches", [])),
        kg_present=bool(serp_data.get("knowledge_graph")),
        schema_article=False,  # futuro: detectar en auditoría propia
        schema_product=False,
        schema_breadcrumb=False,
        schema_faq=False,
        top_competitor_1=top_competitors[0] if len(top_competitors) > 0 else "",
        top_competitor_2=top_competitors[1] if len(top_competitors) > 1 else "",
        top_competitor_3=top_competitors[2] if len(top_competitors) > 2 else "",
        anchor_primary=anchors.primary,
        anchor_secondary=anchors.secondary,
        anchor_internal=anchors.internal,
        notes=briefing.get("unique_angle", "")[:200],
        run_id=run_id
    )