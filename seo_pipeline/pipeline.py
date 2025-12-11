# seo_pipeline/pipeline.py
"""
Orquestador principal del pipeline SEO 2025.
Una única función `run_full_pipeline()` ejecuta todo el flujo de forma secuencial,
robusta y con logging completo. Ideal para notebooks, scripts o futura CLI.
"""
from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Optional

from seo_pipeline.config import get_config
from seo_pipeline.constants import (
    DEFAULT_RELATED_LIMIT,
    DEFAULT_SERP_NUM,
    DEFAULT_TOP_COMPETITORS,
)
from seo_pipeline.vendors.semrush_io import SemrushClient
from seo_pipeline.vendors.serp_io import search_raw, extract_top_urls, extract_competitor_domains
from seo_pipeline.audit.content_audit import audit_urls
from seo_pipeline.anchors import generate_anchors
from seo_pipeline.blueprint import generate_briefing
from seo_pipeline.row24 import build_row24
from seo_pipeline.exporter import export_all_formats
from seo_pipeline.vendors.gsc_io import fetch_cannibalization
from seo_pipeline.vendors.sheets_io import upsert_to_sheet
from seo_pipeline.constants import HEADERS_24, SHEET_ROW_KEYCOLS
from seo_pipeline.utils.logging import logger
from time import sleep
from datetime import timedelta
from seo_pipeline.utils.io import save_json


def run_full_pipeline(
    keyword: str,
    target_url: Optional[str] = None,
    run_id: Optional[str] = None,
    related_limit: int = DEFAULT_RELATED_LIMIT,
    serp_num: int = DEFAULT_SERP_NUM,
    top_competitors_count: int = DEFAULT_TOP_COMPETITORS,
    upload_to_sheets: bool = True,
    status_path: Optional[Path] = None,
    gsc_months_back: int = 11,
) -> dict:
    """
    Ejecuta el pipeline SEO completo y devuelve un diccionario con rutas a todos los artefactos generados.
    """
    cfg = get_config()
    if not cfg.active_client or not cfg.active_project:
        raise RuntimeError("Cliente y proyecto deben estar configurados antes de ejecutar el pipeline.")

    run_id = run_id or datetime.now().strftime("%Y%m%d_%H%M%S")
    output_dir = cfg.get_output_dir() / run_id
    output_dir.mkdir(parents=True, exist_ok=True)

    logger.info("=== INICIO PIPELINE SEO 2025 ===")
    logger.info(f"Keyword: {keyword} | Run ID: {run_id}")

    results = {"run_id": run_id, "keyword": keyword, "output_dir": str(output_dir)}

    try:
        def _write_status(step: str, message: str = "", percent: int | None = None, state: str = "running"):
            if status_path:
                payload = {"status": state, "step": step, "message": message, "percent": percent}
                try:
                    save_json(status_path, payload)
                except (OSError, TypeError, ValueError) as e:
                    logger.debug(f"No se pudo escribir status en {status_path}: {e}")

        def _retry_call(fn, *a, retries=3, delay=2, **kw):
            last_exc = None
            for i in range(retries):
                try:
                    return fn(*a, **kw)
                except Exception as e:
                    last_exc = e
                    logger.warning(f"Intento {i+1}/{retries} fallo para {getattr(fn, '__name__', str(fn))}: {e}")
                    sleep(delay)
            raise last_exc

        _write_status(step="start", message="Pipeline iniciado", percent=0)

        # ===================================================================
        # 1. SEMrush – Volumen + keywords secundarias
        # ===================================================================
        logger.info("1/8 Obteniendo datos SEMrush...")
        _write_status(step="semrush", message="Obteniendo datos SEMrush", percent=5)
        semrush_client = SemrushClient(
            token=cfg.active_client.semrush_token,
            cache_dir=cfg.cache_dir,
        )
        semrush_data = _retry_call(
            semrush_client.fetch_related,
            keyword=keyword,
            database=cfg.active_client.default_database,
            limit=related_limit,
        )
        results["semrush"] = semrush_data

        # ===================================================================
        # 2. SERP Google (SerpAPI)
        # ===================================================================
        logger.info("2/8 Consultando SERP en tiempo real...")
        _write_status(step="serp", message="Consultando SERP en tiempo real", percent=20)
        serp_raw = _retry_call(
            search_raw,
            query=keyword,
            api_key=cfg.active_client.serpapi_key,
            gl=cfg.active_client.default_gl,
            hl=cfg.active_client.default_hl,
            num=serp_num,
        )
        serp_path = output_dir / "serp_raw.json"
        save_json(serp_path, serp_raw)
        results["serp_raw_path"] = str(serp_path)

        top_urls = extract_top_urls(serp_raw, max_urls=12)
        top_competitors = extract_competitor_domains(
            serp_raw,
            exclude_domain=cfg.active_project.base_domain,
            max_domains=top_competitors_count
        )
        results["top_competitors"] = top_competitors

        # ===================================================================
        # 3. Auditoría de contenido Top-10
        # ===================================================================
        logger.info(f"3/8 Auditando contenido de la competencia ({len(top_urls)} URLs)...")
        _write_status(step="audit", message="Auditando contenido competitivo", percent=40)
        audit_report = _retry_call(audit_urls, top_urls)
        audit_path = output_dir / "audit_report.json"
        save_json(audit_path, audit_report.model_dump())
        results["audit_path"] = str(audit_path)

        # ===================================================================
        # 4. Detección de canibalización (GSC)
        # ===================================================================
        cannibal_notes = ""
        if cfg.active_client.gsc_sa_path:
            try:
                logger.info("4/8 Detectando canibalización en GSC...")
                _write_status(step="gsc", message="Detectando canibalización en GSC", percent=60)
                start_date = (datetime.now() - timedelta(days=30 * gsc_months_back)).strftime("%Y-%m-%d")
                cannibal = _retry_call(
                    fetch_cannibalization,
                    site_url=cfg.active_project.gsc_property,
                    start_date=start_date,
                    end_date=datetime.now().strftime("%Y-%m-%d"),
                    sa_json_path=cfg.active_client.gsc_sa_path,
                )
                if cannibal.items:
                    cannibal_notes = "\n\n## Canibalización detectada\n" + "\n".join([
                        f"- {item.query}: {len(item.pages)} URLs compitiendo"
                        for item in cannibal.items[:8]
                    ])
                results["cannibalization"] = cannibal.model_dump()
            except RuntimeError as e:
                logger.warning(f"Canibalización no disponible: {e}")
        else:
            logger.info("4/8 GSC no configurado → omitiendo canibalización")

        # ===================================================================
        # 5. Generación inteligente de anchors
        # ===================================================================
        logger.info("5/8 Generando anchor texts optimizados...")
        _write_status(step="anchors", message="Generando anchors", percent=70)
        competitor_titles = [
            entry.title for entry in audit_report.entries if entry.title
        ][:8]

        anchors = generate_anchors(
            title=audit_report.entries[0].title if audit_report.entries else "",
            h1=audit_report.entries[0].h1 if audit_report.entries else "",
            h2_list=sum((entry.headings.get("H2", []) for entry in audit_report.entries), []),
            main_keyword=keyword,
            secondary_keywords=[k.keyword for k in semrush_data.keywords_secundarias[:20]],
            competitor_titles=competitor_titles,
        )
        results["anchors"] = anchors.model_dump()

        # ===================================================================
        # 6. Briefing con OpenAI + Instructor (structured output)
        # ===================================================================
        logger.info("6/8 Generando briefing con OpenAI (gpt-4o)...")
        _write_status(step="briefing", message="Generando briefing con OpenAI", percent=80)
        briefing = generate_briefing(
            keyword=keyword,
            search_volume=semrush_data.keyword_principal.search_volume,
            semrush_data=semrush_data.model_dump(),
            serp_raw=serp_raw,
            audit_report=audit_report.model_dump(),
            anchors=anchors,
            cannibalization_notes=cannibal_notes,
            openai_api_key=cfg.active_client.openai_key,
        )
        results["briefing"] = briefing

        # ===================================================================
        # 7. Construcción fila 24 columnas + exportación múltiple
        # ===================================================================
        logger.info("7/8 Construyendo fila 24 columnas y exportando...")
        _write_status(step="export", message="Construyendo fila y exportando", percent=90)
        row24 = build_row24(
            kw=keyword,
            sv=semrush_data.keyword_principal.search_volume,
            secondary_kws=[k.keyword for k in semrush_data.keywords_secundarias[:20]],
            target_url=target_url or "",
            briefing=briefing.model_dump(),
            serp_data=serp_raw,
            anchors=anchors,
            top_competitors=top_competitors,
            run_id=run_id,
        )

        export_paths = export_all_formats(
            run_id=run_id,
            keyword=keyword.replace(" ", "_"),
            row24=row24,
            briefing=briefing,
            output_dir=output_dir,
        )
        results.update(export_paths)

        # ===================================================================
        # 8. Subida automática a Google Sheets (opcional)
        # ===================================================================
        if upload_to_sheets and cfg.active_client.sheets_sa_path and cfg.active_project.sheets_id:
            logger.info("8/8 Subiendo fila 24 a Google Sheets...")
            _write_status(step="sheets", message="Subida a Google Sheets (opcional)", percent=95)
            try:
                upsert_to_sheet(
                    spreadsheet_id=cfg.active_project.sheets_id,
                    tab_name="Briefings 2025",
                    headers=HEADERS_24,
                    key_columns=SHEET_ROW_KEYCOLS,
                    row=row24.to_row(),
                    sa_json_path=cfg.active_client.sheets_sa_path,
                )
                logger.info("Fila subida correctamente a Sheets")
            except Exception as e:
                logger.error(f"Error subiendo a Sheets: {e}")
        else:
            logger.info("8/8 Subida a Sheets desactivada o no configurada")

        logger.info("=== PIPELINE COMPLETADO CON ÉXITO ===\n")
        _write_status(step="done", message="Pipeline completado", percent=100, state="done")
        return results

    except Exception as e:
        logger.error(f"Pipeline fallido para '{keyword}': {e}", exc_info=True)
        if 'status_path' in locals() and status_path:
            try:
                save_json(status_path, {"status": "failed", "step": "error", "message": str(e)})
            except Exception:
                pass
        raise


# Alias rápido para notebooks
execute = run_full_pipeline