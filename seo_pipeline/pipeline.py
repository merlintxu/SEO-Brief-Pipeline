# seo_pipeline/pipeline.py
"""
Orquestador principal del pipeline SEO 2025.
Una única función `run_full_pipeline()` ejecuta todo el flujo de forma secuencial,
robusta y con logging completo. Ideal para notebooks, scripts o futura CLI.
"""
from __future__ import annotations

from datetime import datetime
from pathlib import Path
import time
from typing import Optional

from seo_pipeline.config import get_config
from seo_pipeline.artifacts import AUDIT_REPORT_JSON, RUN_METRICS_JSON, SERP_RAW_JSON
from seo_pipeline.constants import (
    DEFAULT_RELATED_LIMIT,
    DEFAULT_SERP_NUM,
    DEFAULT_TOP_COMPETITORS,
)
from seo_pipeline.vendors.semrush_io import SemrushClient
from seo_pipeline.vendors.serp_io import (
    search_raw,
    extract_top_urls,
    extract_competitor_domains,
    normalize_serp_snapshot,
)
from seo_pipeline.audit.content_audit import audit_urls
from seo_pipeline.anchors import generate_anchors
from seo_pipeline.blueprint import generate_briefing
from seo_pipeline.row24 import build_row24
from seo_pipeline.exporter import export_all_formats
from seo_pipeline.vendors.gsc_io import fetch_cannibalization
from seo_pipeline.vendors.sheets_io import upsert_to_sheet
from seo_pipeline.constants import HEADERS_24, SHEET_ROW_KEYCOLS
from seo_pipeline.utils.logging import logger
from seo_pipeline.utils.retry import retry_call
from seo_pipeline.runtime_validation import validate_runtime_requirements
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
    output_dir: Optional[Path] = None,
    gsc_months_back: int = 11,
) -> dict:
    """
    Ejecuta el pipeline SEO completo y devuelve un diccionario con rutas a todos los artefactos generados.
    """
    cfg = get_config()
    runtime_requirements = validate_runtime_requirements(cfg)

    run_id = run_id or datetime.now().strftime("%Y%m%d_%H%M%S")
    output_dir = Path(output_dir) if output_dir else cfg.get_output_dir() / run_id
    output_dir.mkdir(parents=True, exist_ok=True)

    logger.info("=== INICIO PIPELINE SEO 2025 ===")
    logger.info(f"Keyword: {keyword} | Run ID: {run_id}")

    results = {"run_id": run_id, "keyword": keyword, "output_dir": str(output_dir)}
    metrics = {
        "run_id": run_id,
        "keyword": keyword,
        "started_at": datetime.now().isoformat(timespec="seconds"),
        "stages": {},
    }

    retry_attempts = 3
    retry_base_delay = 2

    try:
        def _write_status(step: str, message: str = "", percent: int | None = None, state: str = "running"):
            if status_path:
                payload = {"status": state, "step": step, "message": message, "percent": percent}
                try:
                    save_json(status_path, payload)
                except (OSError, TypeError, ValueError) as e:
                    logger.debug(f"No se pudo escribir status en {status_path}: {e}")

        def _log_retry_factory(fn_name: str, total_retries: int):
            def _log_retry(attempt: int, exc: Exception, delay: float) -> None:
                logger.warning(
                    f"Intento {attempt}/{total_retries} falló para {fn_name}: {exc} "
                    f"(reintentando en {delay:.2f}s)"
                )

            return _log_retry

        def _stage_start(stage: str) -> float:
            metrics["stages"][stage] = {"started_at": datetime.now().isoformat(timespec="seconds")}
            return time.perf_counter()

        def _stage_finish(stage: str, started: float, **extra) -> None:
            metrics["stages"][stage].update({
                "duration_seconds": round(time.perf_counter() - started, 3),
                **extra,
            })

        def _write_metrics(state: str) -> None:
            metrics["status"] = state
            metrics["finished_at"] = datetime.now().isoformat(timespec="seconds")
            save_json(output_dir / RUN_METRICS_JSON, metrics)

        _write_status(step="start", message="Pipeline iniciado", percent=0)

        # ===================================================================
        # 1. SEMrush – Volumen + keywords secundarias
        # ===================================================================
        logger.info("1/8 Obteniendo datos SEMrush...")
        _write_status(step="semrush", message="Obteniendo datos SEMrush", percent=5)
        stage_started = _stage_start("semrush")
        semrush_client = SemrushClient(
            token=cfg.active_client.semrush_token,
            cache_dir=cfg.cache_dir,
        )
        semrush_data = retry_call(
            semrush_client.fetch_related,
            keyword=keyword,
            database=cfg.active_client.default_database,
            limit=related_limit,
            retries=retry_attempts,
            base_delay=retry_base_delay,
            jitter=0.2,
            on_retry=_log_retry_factory("fetch_related", retry_attempts),
        )
        results["semrush"] = semrush_data
        _stage_finish(
            "semrush",
            stage_started,
            related_keywords=len(semrush_data.keywords_secundarias),
            search_volume=semrush_data.keyword_principal.search_volume,
        )

        # ===================================================================
        # 2. SERP Google (SerpAPI)
        # ===================================================================
        logger.info("2/8 Consultando SERP en tiempo real...")
        _write_status(step="serp", message="Consultando SERP en tiempo real", percent=20)
        stage_started = _stage_start("serp")
        serp_raw = retry_call(
            search_raw,
            query=keyword,
            api_key=cfg.active_client.serpapi_key,
            gl=cfg.active_client.default_gl,
            hl=cfg.active_client.default_hl,
            num=serp_num,
            retries=retry_attempts,
            base_delay=retry_base_delay,
            jitter=0.2,
            on_retry=_log_retry_factory("search_raw", retry_attempts),
        )
        serp_path = output_dir / SERP_RAW_JSON
        save_json(serp_path, serp_raw)
        results["serp_raw_path"] = str(serp_path)
        serp_snapshot = normalize_serp_snapshot(serp_raw, provider="serpapi_or_dataforseo")
        results["serp_snapshot"] = serp_snapshot.model_dump()

        top_urls = serp_snapshot.top_urls
        top_competitors = extract_competitor_domains(
            serp_raw,
            exclude_domain=cfg.active_project.base_domain,
            max_domains=top_competitors_count
        )
        results["top_competitors"] = top_competitors
        _stage_finish(
            "serp",
            stage_started,
            top_urls=len(top_urls),
            top_competitors=len(top_competitors),
            organic_results=serp_snapshot.organic_results_count,
            people_also_ask=serp_snapshot.people_also_ask_count,
            related_searches=serp_snapshot.related_searches_count,
            ai_overview_present=serp_snapshot.ai_overview_present,
        )

        # ===================================================================
        # 3. Auditoría de contenido Top-10
        # ===================================================================
        logger.info(f"3/8 Auditando contenido de la competencia ({len(top_urls)} URLs)...")
        _write_status(step="audit", message="Auditando contenido competitivo", percent=40)
        stage_started = _stage_start("audit")
        audit_report = retry_call(
            audit_urls,
            top_urls,
            retries=retry_attempts,
            base_delay=retry_base_delay,
            jitter=0.2,
            on_retry=_log_retry_factory("audit_urls", retry_attempts),
        )
        audit_path = output_dir / AUDIT_REPORT_JSON
        save_json(audit_path, audit_report.model_dump())
        results["audit_path"] = str(audit_path)
        _stage_finish("audit", stage_started, audited_urls=len(audit_report.entries))

        # ===================================================================
        # 4. Detección de canibalización (GSC)
        # ===================================================================
        cannibal_notes = ""
        if runtime_requirements.can_run_gsc:
            try:
                logger.info("4/8 Detectando canibalización en GSC...")
                _write_status(step="gsc", message="Detectando canibalización en GSC", percent=60)
                stage_started = _stage_start("gsc")
                start_date = (datetime.now() - timedelta(days=30 * gsc_months_back)).strftime("%Y-%m-%d")
                cannibal = retry_call(
                    fetch_cannibalization,
                    site_url=cfg.active_project.gsc_property,
                    start_date=start_date,
                    end_date=datetime.now().strftime("%Y-%m-%d"),
                    sa_json_path=cfg.active_client.gsc_sa_path,
                    retries=retry_attempts,
                    base_delay=retry_base_delay,
                    jitter=0.2,
                    on_retry=_log_retry_factory("fetch_cannibalization", retry_attempts),
                )
                if cannibal.items:
                    cannibal_notes = "\n\n## Canibalización detectada\n" + "\n".join([
                        f"- {item.query}: {len(item.pages)} URLs compitiendo"
                        for item in cannibal.items[:8]
                    ])
                results["cannibalization"] = cannibal.model_dump()
                _stage_finish("gsc", stage_started, cannibalization_items=len(cannibal.items))
            except RuntimeError as e:
                logger.warning(f"Canibalización no disponible: {e}")
                if "gsc" in metrics["stages"]:
                    _stage_finish("gsc", stage_started, error=str(e))
        else:
            logger.info("4/8 GSC no configurado → omitiendo canibalización")
            metrics["stages"]["gsc"] = {"skipped": True, "reason": "not_configured"}

        # ===================================================================
        # 5. Generación inteligente de anchors
        # ===================================================================
        logger.info("5/8 Generando anchor texts optimizados...")
        _write_status(step="anchors", message="Generando anchors", percent=70)
        stage_started = _stage_start("anchors")
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
        _stage_finish(
            "anchors",
            stage_started,
            primary=len(anchors.primary),
            secondary=len(anchors.secondary),
            internal=len(anchors.internal),
        )

        # ===================================================================
        # 6. Briefing con OpenAI + Instructor (structured output)
        # ===================================================================
        logger.info("6/8 Generando briefing con OpenAI (gpt-4o)...")
        _write_status(step="briefing", message="Generando briefing con OpenAI", percent=80)
        stage_started = _stage_start("briefing")
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
        _stage_finish("briefing", stage_started, headings=len(briefing.headings), faqs=len(briefing.faqs))

        # ===================================================================
        # 7. Construcción fila 24 columnas + exportación múltiple
        # ===================================================================
        logger.info("7/8 Construyendo fila 24 columnas y exportando...")
        _write_status(step="export", message="Construyendo fila y exportando", percent=90)
        stage_started = _stage_start("export")
        row24 = build_row24(
            kw=keyword,
            sv=semrush_data.keyword_principal.search_volume,
            secondary_kws=[k.keyword for k in semrush_data.keywords_secundarias[:20]],
            target_url=target_url or "",
            briefing=briefing,
            serp_snapshot=serp_snapshot,
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
        _stage_finish("export", stage_started, files=len(export_paths))

        # ===================================================================
        # 8. Subida automática a Google Sheets (opcional)
        # ===================================================================
        if upload_to_sheets and runtime_requirements.can_upload_sheets:
            logger.info("8/8 Subiendo fila 24 a Google Sheets...")
            _write_status(step="sheets", message="Subida a Google Sheets (opcional)", percent=95)
            stage_started = _stage_start("sheets")
            try:
                sheets_result = upsert_to_sheet(
                    spreadsheet_id=cfg.active_project.sheets_id,
                    tab_name="Briefings 2025",
                    headers=HEADERS_24,
                    key_columns=SHEET_ROW_KEYCOLS,
                    row=row24.to_row(),
                    sa_json_path=cfg.active_client.sheets_sa_path,
                )
                results["sheets"] = sheets_result
                _stage_finish("sheets", stage_started, **sheets_result)
                logger.info("Fila subida correctamente a Sheets")
            except Exception as e:
                results["sheets_error"] = str(e)
                _stage_finish("sheets", stage_started, error=str(e))
                logger.error(f"Error subiendo a Sheets: {e}")
        else:
            logger.info("8/8 Subida a Sheets desactivada o no configurada")
            metrics["stages"]["sheets"] = {"skipped": True, "reason": "disabled_or_not_configured"}

        logger.info("=== PIPELINE COMPLETADO CON ÉXITO ===\n")
        _write_metrics("done")
        results["metrics_path"] = str(output_dir / RUN_METRICS_JSON)
        _write_status(step="done", message="Pipeline completado", percent=100, state="done")
        return results

    except Exception as e:
        logger.error(f"Pipeline fallido para '{keyword}': {e}", exc_info=True)
        try:
            metrics["error"] = str(e)
            _write_metrics("failed")
        except Exception:
            pass
        if 'status_path' in locals() and status_path:
            try:
                save_json(status_path, {"status": "failed", "step": "error", "message": str(e)})
            except Exception:
                pass
        raise


# Alias rápido para notebooks
execute = run_full_pipeline
