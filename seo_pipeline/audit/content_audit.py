# seo_pipeline/audit/content_audit.py
"""
Auditoría técnica y de contenido para URLs (top-10 competidores + propia).
- Extracción de title, H1, meta description
- Conteo de palabras
- Análisis de headings (H1-H6)
- Detección de Schema.org básico
- Soporte para PDFs
"""
from __future__ import annotations

import logging
import time
from typing import List
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed

from bs4 import BeautifulSoup
from seo_pipeline.models import AuditEntry, AuditReport, SchemaSignals
from seo_pipeline.utils.text import normalize_ws

from seo_pipeline.vendors.scrapers import scrape_with_failover
from seo_pipeline.config import get_config
log = logging.getLogger("audit")


def audit_single_url(url: str) -> AuditEntry:
    """
    Audita una única URL extrayendo metadatos, headings y schema.

    Args:
        url (str): URL a auditar.

    Returns:
        AuditEntry: Objeto con los datos extraídos.
    """
    entry = AuditEntry(url=url)

    started = time.perf_counter()
    html = _fetch_html(url)
    if not html:
        entry.status_code = 0
        entry.elapsed_ms = round((time.perf_counter() - started) * 1000)
        entry.errors.append("No response")
        return entry

    soup = BeautifulSoup(html, "lxml")

    # Básicos
    title_tag = soup.find("title")
    entry.title = normalize_ws(title_tag.get_text()) if title_tag else ""
    entry.status_code = 200

    h1 = soup.find("h1")
    entry.h1 = normalize_ws(h1.get_text()) if h1 else ""

    meta_desc = soup.find("meta", attrs={"name": "description"})
    entry.meta_desc = meta_desc["content"] if meta_desc and meta_desc.get("content") else ""

    # Conteo de palabras
    text = soup.get_text(separator=" ")
    entry.word_count = len(normalize_ws(text).split())

    # Headings
    for level in range(1, 7):
        for tag in soup.find_all(f"h{level}"):
            text = normalize_ws(tag.get_text())
            if text:
                entry.headings.setdefault(f"H{level}", []).append(text)

    # Schema.org básico
    schema_tags = soup.find_all("script", type="application/ld+json")
    schema_types = []
    for tag in schema_tags:
        try:
            content = tag.string
            if "@type" in content:
                schema_types.append(content)
                if "Article" in content:
                    entry.schema_signals.has_article = True
                if "Product" in content:
                    entry.schema_signals.has_product = True
                if "BreadcrumbList" in content:
                    entry.schema_signals.has_breadcrumb = True
                if "FAQPage" in content:
                    entry.schema_signals.has_faq = True
        except (TypeError, ValueError, AttributeError):
            continue
    entry.schema_signals.schema_types = schema_types[:5]
    entry.elapsed_ms = round((time.perf_counter() - started) * 1000)

    return entry


def audit_urls(urls: List[str], max_workers: int = 5) -> AuditReport:
    """
    Audita una lista de URLs en paralelo.

    Args:
        urls (List[str]): Lista de URLs.
        max_workers (int): Número de hilos simultáneos.

    Returns:
        AuditReport: Reporte consolidado de todas las URLs.
    """
    entries: list[AuditEntry | None] = [None] * len(urls)

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {executor.submit(audit_single_url, url): index for index, url in enumerate(urls)}
        for future in as_completed(futures):
            index = futures[future]
            entry = future.result()
            entries[index] = entry

    return AuditReport(
        label="top10_audit",
        entries=[entry for entry in entries if entry is not None],
        generated_at=datetime.now().isoformat(timespec="seconds"),
    )

def _fetch_html(url: str, timeout: int = 20) -> str | None:
    cfg = get_config()
    client = cfg.active_client

    return scrape_with_failover(
        url=url,
        piloterr_key=getattr(client, "piloterr_key", None) if client else None,
        dataforseo_login=getattr(client, "dataforseo_login", None) if client else None,
        dataforseo_password=getattr(client, "dataforseo_password", None) if client else None,
        timeout=timeout
    )
