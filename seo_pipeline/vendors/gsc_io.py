# seo_pipeline/vendors/gsc_io.py
"""
Integración Google Search Console (Service Account preferido).
- Cannibalización con posición ponderada por impresiones (2025 standard)
- Agregación robusta y filtrado por mínimo impresiones
"""
from __future__ import annotations

from typing import List, Dict, Optional
from collections import defaultdict
import logging

from seo_pipeline.models import GscPage, GscQueryCannibal, GscCannibalization

log = logging.getLogger("gsc_io")

try:
    from google.oauth2.service_account import Credentials
    from googleapiclient.discovery import build
    from googleapiclient.errors import HttpError
    GSC_LIBS_OK = True
except ImportError as e:
    GSC_LIBS_OK = False
    log.warning("Librerías Google GSC no disponibles: %s", e)

SCOPES = ["https://www.googleapis.com/auth/webmasters.readonly"]


def build_service(sa_json_path: str, subject: Optional[str] = None):
    if not GSC_LIBS_OK:
        raise RuntimeError("Faltan librerías google-auth / google-api-client")
    try:
        creds = Credentials.from_service_account_file(sa_json_path, scopes=SCOPES)
    except FileNotFoundError as e:
        raise RuntimeError(f"Archivo de credenciales GSC no encontrado: {sa_json_path}") from e
    if subject:
        creds = creds.with_subject(subject)
    return build("searchconsole", "v1", credentials=creds, cache_discovery=False)


def fetch_cannibalization(
    site_url: str,
    start_date: str,
    end_date: str,
    sa_json_path: str,
    subject: Optional[str] = None,
    min_impressions: int = 15
) -> GscCannibalization:
    """
    Detecta queries con múltiples URLs rankeando (cannibalización).
    Posición = promedio ponderado por impresiones.
    """
    service = build_service(sa_json_path, subject)

    body = {
        "startDate": start_date,
        "endDate": end_date,
        "dimensions": ["query", "page"],
        "rowLimit": 25000
    }

    try:
        response = service.searchanalytics().query(siteUrl=site_url, body=body).execute()
        rows = response.get("rows", [])
    except HttpError as e:
        log.error("GSC API error: %s", e)
        raise RuntimeError("Error calling GSC API") from e

    # Agregación por query → page
    aggregation: Dict[str, Dict[str, dict]] = defaultdict(lambda: defaultdict(lambda: {
        "clicks": 0.0, "impressions": 0.0, "pos_sum": 0.0, "weight": 0.0
    }))

    for row in rows:
        keys = row.get("keys", [])
        if len(keys) != 2:
            continue
        query, page = keys
        data = aggregation[query][page]
        data["clicks"] += float(row.get("clicks", 0))
        impr = float(row.get("impressions", 0))
        data["impressions"] += impr
        pos = float(row.get("position", 0))
        data["pos_sum"] += pos * impr
        data["weight"] += impr

    # Construcción del reporte final
    items: List[GscQueryCannibal] = []
    for query, pages in aggregation.items():
        page_list: List[GscPage] = []
        for page, stats in pages.items():
            if stats["impressions"] < min_impressions:
                continue
            weighted_pos = stats["pos_sum"] / stats["weight"] if stats["weight"] > 0 else 99.0
            page_list.append(GscPage(
                url=page,
                clickable=stats["clicks"],
                impressions=stats["impressions"],
                position=round(weighted_pos, 2)
            ))

        if len(page_list) > 1:
            page_list.sort(key=lambda x: (x.position, -x.clicks))
            items.append(GscQueryCannibal(query=query, pages=page_list))

    items.sort(key=lambda x: -sum(p.impressions for p in x.pages))

    return GscCannibalization(
        site_url=site_url,
        start_date=start_date,
        end_date=end_date,
        items=items[:100]  # límite razonable
    )