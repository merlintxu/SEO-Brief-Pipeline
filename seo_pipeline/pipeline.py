# seo_pipeline/pipeline.py
"""
Orquestador principal del pipeline SEO 2025.
Una Ãºnica funciÃ³n `run_full_pipeline()` ejecuta todo el flujo de forma secuencial,
robusta y con logging completo. Ideal para notebooks, scripts o futura CLI.
"""
from __future__ import annotations

from datetime import datetime
from pathlib import Path
import time
from typing import Optional
import os

from seo_pipeline.config import get_config
from seo_pipeline.artifacts import AUDIT_REPORT_JSON, RUN_METRICS_JSON, SERP_RAW_JSON
from seo_pipeline.cost_tracking import estimate_openai_text_cost, provider_call_estimate, summarize_costs
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
from seo_pipeline.vendors.capabilities import resolve_serp_provider_plan
from seo_pipeline.vendors.retry_policy import provider_retry_policy
from seo_pipeline.audit.content_audit import audit_urls
from seo_pipeline.anchors import generate_anchors
from seo_pipeline.blueprint import build_briefing_plan_artifact, generate_briefing
from seo_pipeline.row24 import build_row24
from seo_pipeline.exporter import export_all_formats
from seo_pipeline.vendors.gsc_io import fetch_cannibalization
from seo_pipeline.vendors.sheets_io import upsert_to_sheet
from seo_pipeline.constants import HEADERS_24, SHEET_ROW_KEYCOLS
from seo_pipeline.utils.logging import logger, log_event
from seo_pipeline.utils.retry import retry_call
from seo_pipeline.runtime_validation import validate_runtime_requirements
from seo_pipeline.utils.errors import classify_error
from datetime import timedelta
from seo_pipeline.utils.io import save_json
from seo_pipeline.input_validation import PipelineInput
from seo_pipeline.models import (
    AuditReport,
    BriefingPlan,
    CompetitorSet,
    EnrichmentSet,
    KeywordSet,
    PipelineInput as PipelineInputContract,
)
from seo_pipeline.quality_gates import evaluate_quality_gates
from seo_pipeline.quorum import QuorumPolicy, evaluate_quorum
from seo_pipeline.prompt_registry import resolve_prompt_bundle


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
    validated = PipelineInput(
        keyword=keyword,
        target_url=target_url,
        related_limit=related_limit,
        serp_num=serp_num,
        top_competitors_count=top_competitors_count,
        gsc_months_back=gsc_months_back,
    )
    keyword = validated.keyword
    target_url = str(validated.target_url) if validated.target_url else None
    related_limit = validated.related_limit
    serp_num = validated.serp_num
    top_competitors_count = validated.top_competitors_count
    gsc_months_back = validated.gsc_months_back
    pipeline_input = PipelineInputContract(
        keyword=keyword,
        target_url=target_url,
        related_limit=related_limit,
        serp_num=serp_num,
        top_competitors_count=top_competitors_count,
        gsc_months_back=gsc_months_back,
        upload_to_sheets=upload_to_sheets,
    )

    cfg = get_config()
    runtime_requirements = validate_runtime_requirements(cfg)
    serp_provider_plan = resolve_serp_provider_plan(cfg.active_client)

    run_id = run_id or datetime.now().strftime("%Y%m%d_%H%M%S")
    output_dir = Path(output_dir) if output_dir else cfg.get_output_dir() / run_id
    output_dir.mkdir(parents=True, exist_ok=True)

    logger.info("=== INICIO PIPELINE SEO 2025 ===")
    logger.info(f"[run_id={run_id}] Keyword: {keyword}")
    log_event("info", "pipeline.start", run_id=run_id, keyword=keyword)

    results = {"run_id": run_id, "keyword": keyword, "output_dir": str(output_dir)}
    results["pipeline_input"] = pipeline_input.model_dump()
    results["provider_plan"] = {
        "serp": {
            "provider_order": list(serp_provider_plan.provider_order),
            "use_serpapi": serp_provider_plan.use_serpapi,
            "use_dataforseo": serp_provider_plan.use_dataforseo,
        }
    }
    metrics = {
        "run_id": run_id,
        "keyword": keyword,
        "started_at": datetime.now().isoformat(timespec="seconds"),
        "stages": {},
        "costs": {
            "currency": "USD",
            "total_estimated_cost_usd": 0.0,
            "unknown_cost_estimate_count": 0,
            "estimates": [],
        },
    }
    stage_retries: dict[str, int] = {}
    cost_estimates = []

    retry_attempts = 3
    retry_base_delay = 2
    pipeline_started = time.perf_counter()

    try:
        def _log(level: str, message: str, stage: str | None = None) -> None:
            prefix = f"[run_id={run_id}]"
            if stage:
                prefix = f"{prefix} [stage={stage}]"
            text = f"{prefix} {message}"
            if level == "warning":
                logger.warning(text)
            elif level == "error":
                logger.error(text)
            else:
                logger.info(text)

        def _write_status(
            step: str,
            message: str = "",
            percent: int | None = None,
            state: str = "running",
            error_category: str | None = None,
        ):
            if status_path:
                payload = {
                    "status": state,
                    "step": step,
                    "message": message,
                    "percent": percent,
                    "error_category": error_category,
                }
                try:
                    save_json(status_path, payload)
                except (OSError, TypeError, ValueError) as e:
                    logger.debug(f"No se pudo escribir status en {status_path}: {e}")

        def _log_retry_factory(fn_name: str, total_retries: int, stage: str, provider: str):
            def _log_retry(attempt: int, exc: Exception, delay: float) -> None:
                stage_retries[stage] = stage_retries.get(stage, 0) + 1
                _log(
                    "warning",
                    f"Intento {attempt}/{total_retries} fallÃ³ para {fn_name}: {exc} "
                    f"(reintentando en {delay:.2f}s)",
                    stage=stage,
                )
                log_event(
                    "warning",
                    "pipeline.retry",
                    run_id=run_id,
                    stage=stage,
                    provider=provider,
                    attempt=attempt,
                    max_retries=total_retries,
                    delay_seconds=round(delay, 3),
                    error_category=classify_error(exc),
                )

            return _log_retry

        def _stage_start(stage: str, provider: str) -> float:
            metrics["stages"][stage] = {
                "started_at": datetime.now().isoformat(timespec="seconds"),
                "provider": provider,
                "status": "running",
            }
            log_event("info", "pipeline.stage.start", run_id=run_id, stage=stage, provider=provider, status="running")
            return time.perf_counter()

        def _stage_finish(stage: str, started: float, status: str = "ok", **extra) -> None:
            metrics["stages"][stage].update({
                "duration_seconds": round(time.perf_counter() - started, 3),
                "status": status,
                "retries": stage_retries.get(stage, 0),
                **extra,
            })
            log_event(
                "info" if status == "ok" else "warning",
                "pipeline.stage.finish",
                run_id=run_id,
                stage=stage,
                status=status,
                duration_seconds=metrics["stages"][stage]["duration_seconds"],
                provider=metrics["stages"][stage].get("provider"),
                error_category=metrics["stages"][stage].get("error_category"),
                retries=metrics["stages"][stage].get("retries", 0),
            )

        def _write_metrics(state: str) -> None:
            metrics["status"] = state
            metrics["finished_at"] = datetime.now().isoformat(timespec="seconds")
            save_json(output_dir / RUN_METRICS_JSON, metrics)

        _write_status(step="start", message="Pipeline iniciado", percent=0)

        # ===================================================================
        # 1. SEMrush â€“ Volumen + keywords secundarias
        # ===================================================================
        _log("info", "1/8 Obteniendo datos SEMrush...", stage="semrush")
        _write_status(step="semrush", message="Obteniendo datos SEMrush", percent=5)
        stage_started = _stage_start("semrush", provider="semrush")
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
            should_retry=provider_retry_policy("semrush"),
            on_retry=_log_retry_factory("fetch_related", retry_attempts, stage="semrush", provider="semrush"),
        )
        results["semrush"] = semrush_data
        keyword_set = KeywordSet(
            principal=semrush_data.keyword_principal,
            related=semrush_data.keywords_secundarias,
            source="semrush",
        )
        results["keyword_set"] = keyword_set.model_dump()
        _stage_finish(
            "semrush",
            stage_started,
            provider="semrush",
            items_processed=len(semrush_data.keywords_secundarias) + 1,
            related_keywords=len(semrush_data.keywords_secundarias),
            search_volume=semrush_data.keyword_principal.search_volume,
        )
        cost_estimates.append(
            provider_call_estimate(
                provider="semrush",
                service="keyword_related",
                calls=1 + stage_retries.get("semrush", 0),
                notes="Provider unit pricing is account-specific; call count is persisted for cost reconciliation.",
            )
        )

        # ===================================================================
        # 2. SERP Google (SerpAPI)
        # ===================================================================
        _log("info", "2/8 Consultando SERP en tiempo real...", stage="serp")
        _write_status(step="serp", message="Consultando SERP en tiempo real", percent=20)
        stage_started = _stage_start("serp", provider="serpapi_or_dataforseo")
        serp_raw = retry_call(
            search_raw,
            query=keyword,
            api_key=cfg.active_client.serpapi_key,
            gl=cfg.active_client.default_gl,
            hl=cfg.active_client.default_hl,
            num=serp_num,
            use_dataforseo_fallback=serp_provider_plan.use_dataforseo,
            force_disable_serpapi=not serp_provider_plan.use_serpapi,
            retries=retry_attempts,
            base_delay=retry_base_delay,
            jitter=0.2,
            should_retry=provider_retry_policy("serp"),
            on_retry=_log_retry_factory("search_raw", retry_attempts, stage="serp", provider="serpapi_or_dataforseo"),
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
        competitor_set = CompetitorSet(
            top_urls=top_urls,
            domains=top_competitors,
            source=serp_snapshot.provider,
        )
        results["competitor_set"] = competitor_set.model_dump()
        _stage_finish(
            "serp",
            stage_started,
            provider=serp_snapshot.provider,
            items_processed=serp_snapshot.organic_results_count,
            top_urls=len(top_urls),
            top_competitors=len(top_competitors),
            organic_results=serp_snapshot.organic_results_count,
            people_also_ask=serp_snapshot.people_also_ask_count,
            related_searches=serp_snapshot.related_searches_count,
            ai_overview_present=serp_snapshot.ai_overview_present,
            provider_order=list(serp_provider_plan.provider_order),
        )
        cost_estimates.append(
            provider_call_estimate(
                provider=serp_snapshot.provider,
                service="serp_search",
                calls=1 + stage_retries.get("serp", 0),
                notes="SERP provider pricing varies by plan/provider; call count is persisted for reconciliation.",
            )
        )

        # ===================================================================
        # 3. AuditorÃ­a de contenido Top-10
        # ===================================================================
        _log("info", f"3/8 Auditando contenido de la competencia ({len(top_urls)} URLs)...", stage="audit")
        _write_status(step="audit", message="Auditando contenido competitivo", percent=40)
        stage_started = _stage_start("audit", provider="scrape_failover")
        audit_report = retry_call(
            audit_urls,
            top_urls,
            retries=retry_attempts,
            base_delay=retry_base_delay,
            jitter=0.2,
            should_retry=provider_retry_policy("scrape_failover"),
            on_retry=_log_retry_factory("audit_urls", retry_attempts, stage="audit", provider="scrape_failover"),
        )
        audit_path = output_dir / AUDIT_REPORT_JSON
        save_json(audit_path, audit_report.model_dump())
        results["audit_path"] = str(audit_path)
        slowest_entry = max(audit_report.entries, key=lambda entry: entry.elapsed_ms, default=None)
        failed_urls = sum(1 for entry in audit_report.entries if entry.status_code == 0)
        _stage_finish(
            "audit",
            stage_started,
            provider="scrape_failover",
            items_processed=len(audit_report.entries),
            audited_urls=len(audit_report.entries),
            failed_urls=failed_urls,
            slowest_item_url=slowest_entry.url if slowest_entry else "",
            slowest_item_ms=slowest_entry.elapsed_ms if slowest_entry else 0,
        )

        # ===================================================================
        # 4. DetecciÃ³n de canibalizaciÃ³n (GSC)
        # ===================================================================
        cannibal_notes = ""
        cannibal = None
        if runtime_requirements.can_run_gsc:
            try:
                _log("info", "4/8 Detectando canibalizaciÃ³n en GSC...", stage="gsc")
                _write_status(step="gsc", message="Detectando canibalizaciÃ³n en GSC", percent=60)
                stage_started = _stage_start("gsc", provider="gsc")
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
                    should_retry=provider_retry_policy("gsc"),
                    on_retry=_log_retry_factory("fetch_cannibalization", retry_attempts, stage="gsc", provider="gsc"),
                )
                if cannibal.items:
                    cannibal_notes = "\n\n## CanibalizaciÃ³n detectada\n" + "\n".join([
                        f"- {item.query}: {len(item.pages)} URLs compitiendo"
                        for item in cannibal.items[:8]
                    ])
                results["cannibalization"] = cannibal.model_dump()
                _stage_finish(
                    "gsc",
                    stage_started,
                    provider="gsc",
                    items_processed=len(cannibal.items),
                    cannibalization_items=len(cannibal.items),
                )
            except RuntimeError as e:
                error_category = classify_error(e)
                _log("warning", f"Canibalización no disponible: {e}", stage="gsc")
                if "gsc" in metrics["stages"]:
                    _stage_finish(
                        "gsc",
                        stage_started,
                        status="failed",
                        provider="gsc",
                        error=str(e),
                        error_category=error_category,
                    )
        else:
            _log("info", "4/8 GSC no configurado â†’ omitiendo canibalizaciÃ³n", stage="gsc")
            metrics["stages"]["gsc"] = {
                "skipped": True,
                "reason": "not_configured",
                "provider": "gsc",
                "status": "skipped",
                "retries": 0,
            }

        # ===================================================================
        # 5. GeneraciÃ³n inteligente de anchors
        # ===================================================================
        _log("info", "5/8 Generando anchor texts optimizados...", stage="anchors")
        _write_status(step="anchors", message="Generando anchors", percent=70)
        stage_started = _stage_start("anchors", provider="internal")
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
        if isinstance(audit_report, AuditReport):
            audit_report_contract = audit_report
        else:
            audit_report_contract = AuditReport(
                label=getattr(audit_report, "label", "top10_audit"),
                entries=getattr(audit_report, "entries", []),
                generated_at=getattr(
                    audit_report,
                    "generated_at",
                    datetime.now().isoformat(timespec="seconds"),
                ),
            )
        enrichment = EnrichmentSet(
            serp_snapshot=serp_snapshot,
            audit_report=audit_report_contract,
            cannibalization=cannibal,
            anchors=anchors,
        )
        results["enrichment_set"] = enrichment.model_dump()
        _stage_finish(
            "anchors",
            stage_started,
            provider="internal",
            items_processed=len(anchors.primary) + len(anchors.secondary) + len(anchors.internal),
            primary=len(anchors.primary),
            secondary=len(anchors.secondary),
            internal=len(anchors.internal),
        )

        # ===================================================================
        # A2. Quality gates (pre-briefing)
        # ===================================================================
        gate_eval = evaluate_quality_gates(
            keyword_set=keyword_set,
            competitor_set=competitor_set,
            audit_entries_count=len(enrichment.audit_report.entries),
            strict=os.getenv("QUALITY_GATES_STRICT", "0").strip().lower() in {"1", "true", "yes"},
        )
        metrics["quality_gates"] = {
            "passed": gate_eval.passed,
            "results": [
                {
                    "gate": item.gate,
                    "passed": item.passed,
                    "message": item.message,
                    "severity": item.severity,
                }
                for item in gate_eval.results
            ],
            "failed_count": len(gate_eval.failures),
        }
        if not gate_eval.passed:
            failed_summary = "; ".join(f"{item.gate}: {item.message}" for item in gate_eval.failures)
            raise RuntimeError(f"Quality gates failed: {failed_summary}")

        # ===================================================================
        # B2. Quorum / partial-data policy
        # ===================================================================
        quorum_policy = QuorumPolicy(
            min_related_keywords=max(0, int(os.getenv("QUORUM_MIN_RELATED_KEYWORDS", "1"))),
            min_top_urls=max(0, int(os.getenv("QUORUM_MIN_TOP_URLS", "3"))),
            min_competitor_domains=max(0, int(os.getenv("QUORUM_MIN_COMPETITOR_DOMAINS", "2"))),
            min_audit_entries=max(0, int(os.getenv("QUORUM_MIN_AUDIT_ENTRIES", "1"))),
            enforce=os.getenv("QUORUM_ENFORCE", "0").strip().lower() in {"1", "true", "yes"},
        )
        quorum_decision = evaluate_quorum(
            keyword_set=keyword_set,
            competitor_set=competitor_set,
            audit_entries_count=len(enrichment.audit_report.entries),
            policy=quorum_policy,
        )
        metrics["quorum"] = {
            "decision": quorum_decision.decision,
            "enforce": quorum_policy.enforce,
            "checks": [
                {
                    "rule": check.rule,
                    "passed": check.passed,
                    "observed": check.observed,
                    "required": check.required,
                    "message": check.message,
                }
                for check in quorum_decision.checks
            ],
            "failed_count": len(quorum_decision.failed_checks),
        }
        results["quorum"] = metrics["quorum"]

        if quorum_decision.failed_checks:
            failure_summary = "; ".join(
                f"{item.rule} ({item.observed}/{item.required})" for item in quorum_decision.failed_checks
            )
            if quorum_decision.decision == "fail":
                raise RuntimeError(f"Quorum policy failed: {failure_summary}")
            _log("warning", f"Quorum partial-data continue: {failure_summary}", stage="quorum")
            results["partial_data"] = True
        else:
            results["partial_data"] = False

        # ===================================================================
        # 6. Briefing con OpenAI + Instructor (structured output)
        # ===================================================================
        _log("info", "6/8 Generando briefing con OpenAI (gpt-4o)...", stage="briefing")
        _write_status(step="briefing", message="Generando briefing con OpenAI", percent=80)
        stage_started = _stage_start("briefing", provider="openai")
        prompt_version = os.getenv("BRIEFING_PROMPT_VERSION", "v1").strip() or "v1"
        prompt_bundle = resolve_prompt_bundle("brief_generator", prompt_version)
        briefing_plan = build_briefing_plan_artifact(
            keyword=keyword,
            serp_snapshot=serp_snapshot,
            audit_report=enrichment.audit_report.model_dump(),
            prompt_version=prompt_bundle.version,
        )
        results["briefing_plan"] = briefing_plan.model_dump()

        briefing = generate_briefing(
            keyword=keyword,
            search_volume=semrush_data.keyword_principal.search_volume,
            semrush_data=semrush_data.model_dump(),
            serp_snapshot=serp_snapshot,
            audit_report=enrichment.audit_report.model_dump(),
            anchors=anchors,
            cannibalization_notes=cannibal_notes,
            openai_api_key=cfg.active_client.openai_key,
            model=prompt_bundle.model,
            temperature=prompt_bundle.temperature,
            prompt_version=prompt_bundle.version,
            planner_artifact=briefing_plan.model_dump(),
        )
        results["prompt_run"] = {
            "key": prompt_bundle.key,
            "version": prompt_bundle.version,
            "model": prompt_bundle.model,
            "temperature": prompt_bundle.temperature,
            "planner_version": briefing_plan.planner_version,
            "mode": "planner_writer",
        }
        metrics["prompt_run"] = results["prompt_run"]
        results["briefing"] = briefing
        briefing_cost = estimate_openai_text_cost(
            model=prompt_bundle.model,
            input_payload={
                "system_prompt": prompt_bundle.system_prompt,
                "keyword": keyword,
                "semrush_data": semrush_data.model_dump(),
                "serp_snapshot": serp_snapshot.model_dump(),
                "audit_report": enrichment.audit_report.model_dump(),
                "anchors": anchors.model_dump(),
                "cannibalization_notes": cannibal_notes,
                "planner_artifact": briefing_plan.model_dump(),
            },
            output_payload=briefing.model_dump(),
        )
        cost_estimates.append(briefing_cost)
        _stage_finish(
            "briefing",
            stage_started,
            provider="openai",
            items_processed=len(briefing.headings) + len(briefing.faqs),
            headings=len(briefing.headings),
            faqs=len(briefing.faqs),
            prompt_version=prompt_bundle.version,
            model=prompt_bundle.model,
            input_tokens_estimated=briefing_cost.input_tokens_estimated,
            output_tokens_estimated=briefing_cost.output_tokens_estimated,
            total_tokens_estimated=briefing_cost.total_tokens_estimated,
            estimated_cost_usd=briefing_cost.estimated_cost_usd,
        )

        # ===================================================================
        # 7. ConstrucciÃ³n fila 24 columnas + exportaciÃ³n mÃºltiple
        # ===================================================================
        _log("info", "7/8 Construyendo fila 24 columnas y exportando...", stage="export")
        _write_status(step="export", message="Construyendo fila y exportando", percent=90)
        stage_started = _stage_start("export", provider="internal")
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
        _stage_finish(
            "export",
            stage_started,
            provider="internal",
            items_processed=len(export_paths),
            files=len(export_paths),
        )

        # ===================================================================
        # 8. Subida automÃ¡tica a Google Sheets (opcional)
        # ===================================================================
        if upload_to_sheets and runtime_requirements.can_upload_sheets:
            _log("info", "8/8 Subiendo fila 24 a Google Sheets...", stage="sheets")
            _write_status(step="sheets", message="Subida a Google Sheets (opcional)", percent=95)
            stage_started = _stage_start("sheets", provider="google_sheets")
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
                _stage_finish("sheets", stage_started, provider="google_sheets", items_processed=1, **sheets_result)
                cost_estimates.append(
                    provider_call_estimate(
                        provider="google_sheets",
                        service="row_upsert",
                        calls=1,
                        notes="Google Sheets API cost is not estimated; call count is persisted for reconciliation.",
                    )
                )
                _log("info", "Fila subida correctamente a Sheets", stage="sheets")
            except Exception as e:
                error_category = classify_error(e)
                results["sheets_error"] = str(e)
                _stage_finish(
                    "sheets",
                    stage_started,
                    status="failed",
                    provider="google_sheets",
                    items_processed=0,
                    error=str(e),
                    error_category=error_category,
                )
                _log("error", f"Error subiendo a Sheets: {e}", stage="sheets")
        else:
            _log("info", "8/8 Subida a Sheets desactivada o no configurada", stage="sheets")
            metrics["stages"]["sheets"] = {
                "skipped": True,
                "reason": "disabled_or_not_configured",
                "provider": "google_sheets",
                "status": "skipped",
                "retries": 0,
            }

        _log("info", "=== PIPELINE COMPLETADO CON Ã‰XITO ===")
        metrics["costs"] = summarize_costs(cost_estimates)
        results["costs"] = metrics["costs"]
        _write_metrics("done")
        results["metrics_path"] = str(output_dir / RUN_METRICS_JSON)
        _write_status(step="done", message="Pipeline completado", percent=100, state="done")
        log_event(
            "info",
            "pipeline.finish",
            run_id=run_id,
            status="done",
            duration_seconds=round(time.perf_counter() - pipeline_started, 3),
        )
        return results

    except Exception as e:
        error_category = classify_error(e)
        logger.error(f"[run_id={run_id}] [stage=error] Pipeline fallido para '{keyword}': {e}", exc_info=True)
        log_event("error", "pipeline.failed", run_id=run_id, stage="error", error_category=error_category, message=str(e))
        try:
            metrics["error"] = str(e)
            metrics["error_category"] = error_category
            _write_metrics("failed")
        except Exception:
            pass
        if 'status_path' in locals() and status_path:
            try:
                save_json(
                    status_path,
                    {"status": "failed", "step": "error", "message": str(e), "error_category": error_category},
                )
            except Exception:
                pass
        raise


# Alias rÃ¡pido para notebooks
execute = run_full_pipeline
