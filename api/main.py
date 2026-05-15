# api/main.py
"""
API REST FastAPI para el SEO Briefing Pipeline 2025
Endpoints:
  POST /briefing → lanza un briefing completo (rate limited)
  GET  /health   → chequeo rápido
  GET  /outputs/{run_id}/{filename} → descarga archivos (con protección)
"""
from __future__ import annotations

import os
from pathlib import Path
from datetime import datetime
from contextlib import asynccontextmanager
import sentry_sdk
from sentry_sdk.integrations.fastapi import FastApiIntegration
from sentry_sdk.integrations.starlette import StarletteIntegration

from fastapi import (
    FastAPI,
    HTTPException,
    BackgroundTasks,
    Security,
    status,
    Depends,
    Request,
    Query,
)
from fastapi.responses import JSONResponse, FileResponse, RedirectResponse
from fastapi.security.api_key import APIKeyHeader
from fastapi.middleware.cors import CORSMiddleware
import uvicorn

from api.rate_limiter import RateLimitMiddleware
from api.job_lifecycle import JobLifecycleService
from api.job_store import InvalidJobTransitionError, JobStore

from seo_pipeline.config import get_config
from seo_pipeline.pipeline import run_full_pipeline
from seo_pipeline.artifacts import DOWNLOADABLE_ARTIFACTS, RUN_METRICS_JSON
from api.schemas import (
    BriefingRequest,
    BriefingResponse,
    JobCancelResponse,
    JobDeleteResponse,
    JobDetailResponse,
    JobEventsListResponse,
    JobMetricsResponse,
    JobRetryResponse,
    JobsCleanupRequest,
    JobsCleanupResponse,
    JobsListResponse,
    OperatorAuditEventRequest,
    OperatorAuditEventResponse,
    OperatorAuditEventsListResponse,
    OpsSloResponse,
)
from seo_pipeline.slo import evaluate_slo_window
from seo_pipeline.utils.io import ensure_dir, load_json
from seo_pipeline.llm.config import get_llm_settings
from seo_pipeline.runtime_validation import RuntimeValidationError, validate_runtime_requirements

# ============================================================================
# SECURITY & CONFIGURATION
# ============================================================================

# CRITICAL: API_KEY must be set as environment variable - no hardcoded defaults!
API_KEY = os.getenv("API_KEY")
if not API_KEY or len(API_KEY) < 20:
    raise RuntimeError(
        "SECURITY ERROR: API_KEY environment variable must be set and >= 20 chars. "
        "Generate with: python -c \"import secrets; print(secrets.token_urlsafe(32))\""
    )

API_KEY_NAME = "X-API-Key"
api_key_header = APIKeyHeader(name=API_KEY_NAME, auto_error=False)

# Allowed output files (whitelist to prevent path traversal)
ALLOWED_FILES = DOWNLOADABLE_ARTIFACTS


def _get_job_retention_days() -> int:
    raw = os.getenv("JOB_STORE_RETENTION_DAYS", "30").strip()
    try:
        value = int(raw)
    except ValueError as exc:
        raise RuntimeError("JOB_STORE_RETENTION_DAYS must be an integer >= 1") from exc
    if value < 1:
        raise RuntimeError("JOB_STORE_RETENTION_DAYS must be >= 1")
    return value

# ============================================================================
# APP INITIALIZATION WITH LIFESPAN & MIDDLEWARE
# ============================================================================

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Modern lifespan manager (replaces @app.on_event)"""
    # Initialize Sentry if DSN is configured
    sentry_dsn = os.getenv("SENTRY_DSN")
    if sentry_dsn:
        sentry_sdk.init(
            dsn=sentry_dsn,
            integrations=[
                FastApiIntegration(transaction_style="endpoint"),
                StarletteIntegration(transaction_style="endpoint"),
            ],
            traces_sample_rate=0.1,  # 10% of transactions for performance monitoring
            environment=os.getenv("SENTRY_ENVIRONMENT", "production"),
            release=os.getenv("SENTRY_RELEASE", "2025.11.18"),
        )
    
    ensure_dir(Path("outputs"))
    try:
        retention_days = _get_job_retention_days()
        job_store.cleanup_old_jobs(max_age_days=retention_days)
    except Exception:
        # Startup must not fail if retention cleanup fails.
        pass
    yield


app = FastAPI(
    title="SEO Briefing Pipeline API",
    description="""
    ## Automated SEO Content Briefing Generation
    
    Generate comprehensive SEO content briefs using:
    - **SEMrush** - Keyword research and search volume data
    - **SerpAPI** - Real-time SERP analysis
    - **OpenAI GPT-4** - AI-powered content recommendations
    - **Google Search Console** - Cannibalization detection
    
    ### Features
    - Automated keyword research
    - Competitor content analysis
    - AI-generated briefings with structured headings
    - Google Sheets integration
    - Rate-limited API (10 requests/minute)
    
    ### Authentication
    All endpoints (except `/health`) require an `X-API-Key` header.
    
    ### Rate Limiting
    - **Limit**: 10 requests per minute per IP
    - **Exempt**: `/health`, `/docs`, `/openapi.json`
    """,
    version="2025.11.18",
    contact={
        "name": "SEO Pipeline Support",
        "url": "https://github.com/your-repo/seo-pipeline",
        "email": "support@example.com"
    },
    license_info={
        "name": "MIT",
        "url": "https://opensource.org/licenses/MIT"
    },
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_tags=[
        {
            "name": "briefing",
            "description": "SEO briefing generation endpoints"
        },
        {
            "name": "health",
            "description": "System health and status checks"
        },
        {
            "name": "files",
            "description": "Download generated briefing files"
        },
        {
            "name": "jobs",
            "description": "Operational job metadata endpoints"
        },
        {
            "name": "ops",
            "description": "Protected operator console and audit trail endpoints"
        }
    ]
)

# Add rate limiting middleware (10 requests per minute, exempt /health)
app.add_middleware(
    RateLimitMiddleware,
    rate=10,
    window=60,
    exempt_paths=["/health", "/docs", "/openapi.json", "/redoc"]
)

# CORS Protection: Allow only configured origins
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",      # React dev server
        "http://localhost:8000",      # Uvicorn dev server
        "http://localhost:8001",      # Alternate port
    ],
    allow_credentials=True,
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type", "X-API-Key"],
    max_age=3600,
)

# ============================================================================
# SECURITY: API KEY VALIDATION
# ============================================================================

async def get_api_key(api_key_header: str = Security(api_key_header)):
    """Validate API key from header"""
    if not api_key_header or api_key_header != API_KEY:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Invalid or missing X-API-Key header",
        )
    return api_key_header


# ============================================================================
# ENDPOINTS
# ============================================================================

cfg = get_config()
job_store = JobStore(Path("outputs") / "jobs.db")
job_lifecycle = JobLifecycleService(job_store)
JOB_STATUS_VALUES = {"queued", "running", "done", "failed"}


def _job_to_dict(job) -> dict:
    return {
        "run_id": job.run_id,
        "keyword": job.keyword,
        "status": job.status,
        "step": job.step,
        "message": job.message,
        "error_category": job.error_category,
        "output_dir": job.output_dir,
        "source_run_id": job.source_run_id,
        "created_at": job.created_at,
        "updated_at": job.updated_at,
    }


def _operator_audit_to_dict(event) -> dict:
    return {
        "id": event.id,
        "action": event.action,
        "result": event.result,
        "run_id": event.run_id,
        "metadata": event.metadata,
        "created_at": event.created_at,
    }


def _stage_metric_to_dict(metric) -> dict:
    return {
        "run_id": metric.run_id,
        "stage": metric.stage,
        "status": metric.status,
        "provider": metric.provider,
        "retries": metric.retries,
        "items_processed": metric.items_processed,
        "duration_seconds": metric.duration_seconds,
        "error_category": metric.error_category,
        "estimated_cost_usd": metric.estimated_cost_usd,
        "total_tokens_estimated": metric.total_tokens_estimated,
        "created_at": metric.created_at,
    }


def _provider_call_to_dict(call) -> dict:
    return {
        "id": call.id,
        "run_id": call.run_id,
        "provider": call.provider,
        "service": call.service,
        "calls": call.calls,
        "estimated_cost_usd": call.estimated_cost_usd,
        "total_tokens_estimated": call.total_tokens_estimated,
        "notes": call.notes,
        "created_at": call.created_at,
    }


def _prompt_run_to_dict(prompt_run) -> dict | None:
    if prompt_run is None:
        return None
    return {
        "run_id": prompt_run.run_id,
        "key": prompt_run.key,
        "version": prompt_run.version,
        "planner_version": prompt_run.planner_version,
        "mode": prompt_run.mode,
        "model": prompt_run.model,
        "temperature": prompt_run.temperature,
        "created_at": prompt_run.created_at,
    }


def _job_metrics_summary(stage_metrics, provider_calls) -> dict:
    total_retries = sum(metric.retries or 0 for metric in stage_metrics)
    failed_stages = [
        metric.stage
        for metric in stage_metrics
        if metric.status and metric.status not in {"ok", "done", "skipped"}
    ]
    total_duration = sum(metric.duration_seconds or 0 for metric in stage_metrics)
    total_estimated_cost = sum(call.estimated_cost_usd or 0 for call in provider_calls)
    return {
        "stage_count": len(stage_metrics),
        "provider_call_count": len(provider_calls),
        "failed_stages": failed_stages,
        "total_retries": total_retries,
        "total_duration_seconds": round(total_duration, 6),
        "total_estimated_cost_usd": round(total_estimated_cost, 6),
    }


def _sync_job_metrics_from_output(job) -> None:
    metrics_path = Path(job.output_dir) / RUN_METRICS_JSON
    if not metrics_path.exists():
        return
    payload = load_json(metrics_path, default={})
    if isinstance(payload, dict):
        job_store.persist_run_metrics(job.run_id, payload)


def _persist_job_output_from_result(run_id: str, keyword: str, result: dict) -> None:
    briefing = result.get("briefing")
    row24 = result.get("row24")
    briefing_payload = briefing.model_dump() if hasattr(briefing, "model_dump") else briefing
    row24_payload = row24.model_dump() if hasattr(row24, "model_dump") else row24
    artifacts = {
        key: str(value)
        for key, value in result.items()
        if key in {"json", "markdown", "csv", "xlsx", "metrics_path", "serp_raw_path", "audit_path"}
    }
    prompt_run = result.get("prompt_run") if isinstance(result.get("prompt_run"), dict) else {}
    job_store.persist_job_output(
        run_id,
        keyword=keyword,
        briefing=briefing_payload if isinstance(briefing_payload, dict) else None,
        row24=row24_payload if isinstance(row24_payload, dict) else None,
        artifacts=artifacts,
        provider="openai" if prompt_run else None,
        model=prompt_run.get("model"),
    )


def _job_metrics_has_provider(job, provider: str) -> bool:
    _sync_job_metrics_from_output(job)
    expected = provider.strip().lower()
    stage_metrics = job_store.list_stage_metrics(job.run_id)
    if any((metric.provider or "").lower() == expected for metric in stage_metrics):
        return True
    provider_calls = job_store.list_provider_calls(job.run_id)
    if any(call.provider.lower() == expected for call in provider_calls):
        return True

    metrics_path = Path(job.output_dir) / RUN_METRICS_JSON
    if not metrics_path.exists():
        return False
    payload = load_json(metrics_path, default={})
    if not isinstance(payload, dict):
        return False
    stages = payload.get("stages", {})
    if isinstance(stages, dict):
        for stage in stages.values():
            if isinstance(stage, dict) and str(stage.get("provider", "")).lower() == expected:
                return True
    costs = payload.get("costs", {})
    estimates = costs.get("estimates", []) if isinstance(costs, dict) else []
    return any(isinstance(item, dict) and str(item.get("provider", "")).lower() == expected for item in estimates)


def _queue_pipeline_run(
    *,
    background: BackgroundTasks,
    request: BriefingRequest,
    run_id: str,
    run_dir: Path,
    status_path: Path,
    initial_message: str = "Tarea en cola",
    source_run_id: str | None = None,
) -> None:
    job_lifecycle.enqueue(
        run_id=run_id,
        keyword=request.keyword,
        output_dir=run_dir,
        status_path=status_path,
        message=initial_message,
        source_run_id=source_run_id,
    )

    def _bg_task(req: BriefingRequest, current_run_id: str, current_status_path: Path, current_run_dir: Path):
        try:
            if not job_lifecycle.start(current_run_id):
                return
            result = run_full_pipeline(
                keyword=req.keyword,
                target_url=req.target_url,
                run_id=current_run_id,
                upload_to_sheets=req.upload_to_sheets,
                related_limit=req.related_limit,
                serp_num=req.serp_num,
                status_path=current_status_path,
                output_dir=current_run_dir,
            )
            _persist_job_output_from_result(current_run_id, req.keyword, result)
            metrics_path = current_run_dir / RUN_METRICS_JSON
            metrics_payload = load_json(metrics_path, default={}) if metrics_path.exists() else {}
            if isinstance(metrics_payload, dict) and metrics_payload:
                job_store.persist_run_metrics(current_run_id, metrics_payload)
            try:
                job_lifecycle.complete_from_status(current_run_id, current_status_path)
            except InvalidJobTransitionError:
                pass
        except Exception as e:
            try:
                try:
                    metrics_path = current_run_dir / RUN_METRICS_JSON
                    metrics_payload = load_json(metrics_path, default={}) if metrics_path.exists() else {}
                    if isinstance(metrics_payload, dict) and metrics_payload:
                        job_store.persist_run_metrics(current_run_id, metrics_payload)
                    job_lifecycle.fail_from_exception(current_run_id, current_status_path, e)
                except InvalidJobTransitionError:
                    pass
            except Exception:
                pass

    background.add_task(_bg_task, request, run_id, status_path, run_dir)


@app.get(
    "/health",
    tags=["health"],
    summary="Health Check",
    description="Check API health status and active configuration",
    response_description="System health status"
)
async def health_check():
    """Health check endpoint - no auth required"""
    return {
        "status": "ok",
        "active_client": cfg.active_client.name if cfg.active_client else None
    }


@app.get(
    "/ops",
    tags=["health"],
    summary="Ops Dashboard",
    description="Serve operational dashboard UI from tracked public file.",
)
async def ops_dashboard():
    dashboard_path = Path("public") / "dashboard.html"
    if not dashboard_path.exists():
        raise HTTPException(status_code=404, detail="Ops dashboard not found")
    return FileResponse(dashboard_path)


@app.get("/ops/", include_in_schema=False)
async def ops_dashboard_slash():
    return RedirectResponse(url="/ops")


@app.post(
    "/briefing",
    response_model=BriefingResponse,
    tags=["briefing"],
   summary="Create SEO Briefing",
    description="""
    Generate a comprehensive SEO content brief for a given keyword.
    
    This endpoint:
    1. Fetches keyword data from SEMrush
    2. Analyzes SERP results via SerpAPI
    3. Audits top competitor content
    4. Checks for keyword cannibalization (if GSC configured)
    5. Generates AI-powered content brief with OpenAI
    6. Exports results in multiple formats (JSON, Markdown, XLSX)
    7. Optionally uploads to Google Sheets
    
    **Note**: This is a long-running operation executed in the background.
    Use the `/briefing/{run_id}` endpoint to check status.
    """,
    responses={
        200: {
            "description": "Briefing creation initiated",
            "content": {
                "application/json": {
                    "example": {
                        "run_id": "20251125_120530",
                        "keyword": "content marketing",
                        "output_dir": "outputs/20251125_120530",
                        "files": {"status": "/outputs/20251125_120530/status.json"}
                    }
                }
            }
        },
        400: {"description": "No client/project configured"},
        403: {"description": "Invalid or missing API key"},
        429: {"description": "Rate limit exceeded"},
        500: {"description": "Internal server error"}
    }
)
async def create_briefing(
    request: BriefingRequest,
    background: BackgroundTasks,
    api_key: str = Depends(get_api_key)
):
    """
    Create a new SEO briefing (async, background task)
    Rate limited to 5 requests per minute per IP
    """
    if not cfg.active_client or not cfg.active_project:
        raise HTTPException(
            status_code=400,
            detail="No hay cliente/proyecto activo configurado en el servidor"
        )

    try:
        llm_settings = get_llm_settings(cfg.active_project)
        validate_runtime_requirements(
            cfg,
            require_openai=llm_settings.provider == "openai",
            llm_settings=llm_settings,
        )
        # Create run_id and initial status file
        run_id = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
        outputs_dir = Path("outputs")
        run_dir = outputs_dir / run_id
        ensure_dir(run_dir)
        status_path = run_dir / "status.json"
        _queue_pipeline_run(
            background=background,
            request=request,
            run_id=run_id,
            run_dir=run_dir,
            status_path=status_path,
            initial_message="Tarea en cola",
            source_run_id=None,
        )

        # Return immediate response with run_id
        base_url = f"/outputs/{run_id}"
        files = {"status": f"{base_url}/status.json"}

        return BriefingResponse(
            run_id=run_id,
            keyword=request.keyword,
            output_dir=str(run_dir),
            files=files
        )
    except RuntimeValidationError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get(
    "/briefing/{run_id}",
    tags=["briefing"],
    summary="Get Briefing Status",
    description="""
    Check the status of a running or completed briefing generation task.
    
    Poll this endpoint to track progress of the briefing generation.
    
    **Status values**:
    - `queued` - Task is waiting to start
    - `running` - Task is in progress
    - `done` - Task completed successfully
    - `failed` - Task encountered an error
    """,
    responses={
        200: {
            "description": "Status retrieved successfully",
            "content": {
                "application/json": {
                    "examples": {
                        "running": {
                            "value": {
                                "status": "running",
                                "step": "3/8 Auditando competidores...",
                                "message": "Processing"
                            }
                        },
                        "completed": {
                            "value": {
                                "status": "done",
                                "step": "completed",
                                "message": "Pipeline completado",
                                "files": {
                                    "json": "/outputs/20251125_120530/briefing.json",
                                    "markdown": "/outputs/20251125_120530/briefing.md"
                                }
                            }
                        }
                    }
                }
            }
        },
        404: {"description": "Run ID not found"}
    }
)
async def briefing_status(run_id: str):
    """Get status of a briefing run"""
    path = Path("outputs") / run_id / "status.json"
    if path.exists():
        data = load_json(path)
        return JSONResponse(content=data)

    job = job_store.get_job(run_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Run_id no encontrado")

    data = {
        "status": job.status,
        "step": job.step,
        "message": job.message,
        "error_category": job.error_category,
    }
    return JSONResponse(content=data)


@app.get(
    "/jobs",
    tags=["jobs"],
    response_model=JobsListResponse,
    summary="List Jobs",
    description="List recent job metadata from the SQLite job store (operational endpoint).",
)
async def list_jobs(
    limit: int = Query(default=20, ge=1, le=200),
    cursor: int = Query(default=0, ge=0),
    status_filter: str | None = Query(default=None, alias="status"),
    q: str | None = Query(default=None, min_length=1, max_length=100),
    error_category: str | None = Query(default=None, min_length=1, max_length=64),
    created_from: str | None = Query(default=None, min_length=10, max_length=32),
    created_to: str | None = Query(default=None, min_length=10, max_length=32),
    provider: str | None = Query(default=None, min_length=1, max_length=64),
    api_key: str = Depends(get_api_key),
):
    if status_filter and status_filter not in JOB_STATUS_VALUES:
        raise HTTPException(
            status_code=422,
            detail=f"Invalid status filter '{status_filter}'. Allowed: {', '.join(sorted(JOB_STATUS_VALUES))}",
        )
    records = job_store.list_jobs(
        limit=limit,
        offset=cursor,
        status=status_filter,
        search=q,
        error_category=error_category,
        created_from=created_from,
        created_to=created_to,
    )
    if provider:
        records = [job for job in records if _job_metrics_has_provider(job, provider)]
    payload = [_job_to_dict(job) for job in records]
    next_cursor = cursor + limit if len(payload) == limit else None
    return JSONResponse(content={"items": payload, "count": len(payload), "next_cursor": next_cursor})


@app.get(
    "/jobs/{run_id}",
    tags=["jobs"],
    response_model=JobDetailResponse,
    summary="Get Job Detail",
    description="Get job metadata and current status snapshot for a single run.",
)
async def get_job(run_id: str, api_key: str = Depends(get_api_key)):
    job = job_store.get_job(run_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Run_id no encontrado")
    status_path = Path(job.output_dir) / "status.json"
    status_payload = load_json(status_path, default={}) if status_path.exists() else None
    _sync_job_metrics_from_output(job)
    metrics_path = Path(job.output_dir) / RUN_METRICS_JSON
    metrics_payload = load_json(metrics_path, default={}) if metrics_path.exists() else {}
    cost_summary = metrics_payload.get("costs") if isinstance(metrics_payload, dict) else None
    events = [
        {
            "id": event.id,
            "run_id": event.run_id,
            "status": event.status,
            "step": event.step,
            "message": event.message,
            "error_category": event.error_category,
            "created_at": event.created_at,
        }
        for event in job_store.list_job_events(run_id, limit=200, offset=0)
    ]
    return JSONResponse(
        content={
            "job": _job_to_dict(job),
            "status_file": status_payload,
            "cost_summary": cost_summary,
            "events": events,
        }
    )


@app.get(
    "/jobs/{run_id}/events",
    tags=["jobs"],
    response_model=JobEventsListResponse,
    summary="List Job Events",
    description="List lifecycle events for a job, ordered by newest event first.",
)
async def list_job_events(
    run_id: str,
    limit: int = Query(default=50, ge=1, le=200),
    cursor: int = Query(default=0, ge=0),
    api_key: str = Depends(get_api_key),
):
    job = job_store.get_job(run_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Run_id no encontrado")
    events = [
        {
            "id": event.id,
            "run_id": event.run_id,
            "status": event.status,
            "step": event.step,
            "message": event.message,
            "error_category": event.error_category,
            "created_at": event.created_at,
        }
        for event in job_store.list_job_events(run_id, limit=limit, offset=cursor)
    ]
    next_cursor = cursor + limit if len(events) == limit else None
    return JSONResponse(content={"items": events, "count": len(events), "next_cursor": next_cursor})


@app.get(
    "/jobs/{run_id}/metrics",
    tags=["jobs"],
    response_model=JobMetricsResponse,
    summary="Get Job Metrics",
    description="Get persisted stage metrics, provider calls and prompt metadata for a single run.",
)
async def get_job_metrics(run_id: str, api_key: str = Depends(get_api_key)):
    job = job_store.get_job(run_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Run_id no encontrado")
    _sync_job_metrics_from_output(job)
    stage_metrics = job_store.list_stage_metrics(run_id)
    provider_calls = job_store.list_provider_calls(run_id)
    prompt_run = job_store.get_prompt_run(run_id)
    return JSONResponse(
        content={
            "run_id": run_id,
            "stage_metrics": [_stage_metric_to_dict(metric) for metric in stage_metrics],
            "provider_calls": [_provider_call_to_dict(call) for call in provider_calls],
            "prompt_run": _prompt_run_to_dict(prompt_run),
            "summary": _job_metrics_summary(stage_metrics, provider_calls),
        }
    )


@app.get(
    "/ops/audit-trail",
    tags=["ops"],
    response_model=OperatorAuditEventsListResponse,
    summary="List Operator Audit Trail",
    description="List persisted operator audit trail events, ordered newest first.",
)
async def list_operator_audit_trail(
    limit: int = Query(default=50, ge=1, le=200),
    cursor: int = Query(default=0, ge=0),
    api_key: str = Depends(get_api_key),
):
    events = [
        _operator_audit_to_dict(event)
        for event in job_store.list_operator_audit_events(limit=limit, offset=cursor)
    ]
    next_cursor = cursor + limit if len(events) == limit else None
    return JSONResponse(content={"items": events, "count": len(events), "next_cursor": next_cursor})


@app.post(
    "/ops/audit-trail",
    tags=["ops"],
    response_model=OperatorAuditEventResponse,
    summary="Append Operator Audit Trail Event",
    description="Append one operator audit event. This endpoint is append-only and API-key protected.",
)
async def append_operator_audit_trail(
    payload: OperatorAuditEventRequest,
    api_key: str = Depends(get_api_key),
):
    event = job_store.append_operator_audit_event(
        action=payload.action,
        result=payload.result,
        run_id=payload.run_id,
        metadata=payload.metadata,
    )
    return JSONResponse(content=_operator_audit_to_dict(event))


@app.get(
    "/ops/slo",
    tags=["ops"],
    response_model=OpsSloResponse,
    summary="Evaluate Operational SLO",
    description="Evaluate recent run_metrics.json payloads from the job store against default SLO thresholds.",
)
async def evaluate_operational_slo(
    limit: int = Query(default=50, ge=1, le=200),
    api_key: str = Depends(get_api_key),
):
    jobs = job_store.list_jobs(limit=limit, offset=0)
    metrics_payloads = []
    missing_metrics_count = 0
    for job in jobs:
        _sync_job_metrics_from_output(job)
        metrics_path = Path(job.output_dir) / RUN_METRICS_JSON
        if not metrics_path.exists():
            missing_metrics_count += 1
            continue
        payload = load_json(metrics_path, default={})
        if isinstance(payload, dict):
            metrics_payloads.append(payload)
        else:
            missing_metrics_count += 1

    evaluation = evaluate_slo_window(metrics_payloads)
    return JSONResponse(
        content={
            "evaluated_run_count": len(metrics_payloads),
            "missing_metrics_count": missing_metrics_count,
            **evaluation,
        }
    )


@app.delete(
    "/jobs/{run_id}",
    tags=["jobs"],
    response_model=JobDeleteResponse,
    summary="Delete Job Metadata",
    description="Delete job metadata from SQLite. Does not delete output artifacts.",
)
async def delete_job(run_id: str, api_key: str = Depends(get_api_key)):
    deleted = job_store.delete_job(run_id)
    if deleted == 0:
        raise HTTPException(status_code=404, detail="Run_id no encontrado")
    return JSONResponse(content={"deleted": True, "run_id": run_id})


@app.post(
    "/jobs/cleanup",
    tags=["jobs"],
    response_model=JobsCleanupResponse,
    summary="Run Job Cleanup",
    description="Run manual retention cleanup for terminal jobs.",
)
async def cleanup_jobs(payload: JobsCleanupRequest, api_key: str = Depends(get_api_key)):
    deleted = job_store.cleanup_old_jobs(
        max_age_days=payload.max_age_days,
        statuses=tuple(payload.statuses),
    )
    return JSONResponse(
        content={
            "deleted_count": deleted,
            "max_age_days": payload.max_age_days,
            "statuses": payload.statuses,
        }
    )


@app.post(
    "/jobs/{run_id}/retry",
    tags=["jobs"],
    response_model=JobRetryResponse,
    summary="Retry Failed Job",
    description="Requeue a failed job as a new run.",
)
async def retry_job(run_id: str, background: BackgroundTasks, api_key: str = Depends(get_api_key)):
    job = job_store.get_job(run_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Run_id no encontrado")
    if job.status != "failed":
        raise HTTPException(status_code=409, detail="Only failed jobs can be retried")

    new_run_id = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
    outputs_dir = Path("outputs")
    run_dir = outputs_dir / new_run_id
    ensure_dir(run_dir)
    status_path = run_dir / "status.json"
    retry_request = BriefingRequest(
        keyword=job.keyword,
        target_url=None,
        upload_to_sheets=False,
        related_limit=30,
        serp_num=10,
    )
    _queue_pipeline_run(
        background=background,
        request=retry_request,
        run_id=new_run_id,
        run_dir=run_dir,
        status_path=status_path,
        initial_message=f"Retry queued from run {run_id}",
        source_run_id=run_id,
    )
    return JSONResponse(content={"source_run_id": run_id, "run_id": new_run_id, "status": "queued"})


@app.post(
    "/jobs/{run_id}/cancel",
    tags=["jobs"],
    response_model=JobCancelResponse,
    summary="Cancel Job",
    description="Logical cancellation for queued/running jobs (no process hard-kill).",
)
async def cancel_job(run_id: str, api_key: str = Depends(get_api_key)):
    job = job_store.get_job(run_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Run_id no encontrado")

    try:
        job_lifecycle.cancel(job)
    except InvalidJobTransitionError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return JSONResponse(content={"run_id": run_id, "status": "failed", "step": "canceled"})


@app.get(
    "/outputs/{run_id}/{filename}",
    tags=["files"],
    summary="Download Briefing File",
    description="""
    Download a generated briefing file.
    
    **Allowed files**:
    - `briefing.json` - Complete briefing data
    - `briefing.md` - Markdown formatted brief
    - `row24.csv` / `row24.xlsx` - Spreadsheet export
    - `status.json` - Current status
    - `audit_report.json` - Competitor audit data
    - `serp_raw.json` - Raw SERP data
    
    **Security**: Path traversal protection is enabled.
    """,
    responses={
        200: {"description": "File downloaded successfully"},
        403: {"description": "File not allowed or path traversal detected"},
        404: {"description": "File not found"}
    }
)
async def download_file(run_id: str, filename: str):
    """
    Download output file with path traversal protection
    Only allows whitelisted filenames to prevent ../../.env attacks
    """
    # Whitelist check: only allow known output files
    if filename not in ALLOWED_FILES:
        raise HTTPException(
            status_code=403,
            detail=f"File '{filename}' not allowed. Allowed: {', '.join(ALLOWED_FILES)}"
        )

    # Path traversal protection: resolve and verify file is within outputs/
    outputs_dir = Path("outputs").resolve()
    file_path = (outputs_dir / run_id / filename).resolve()

    try:
        # Ensure file is within outputs directory
        file_path.relative_to(outputs_dir)
    except ValueError:
        raise HTTPException(
            status_code=403,
            detail="Path traversal attempt detected"
        )

    # Verify file exists
    if not file_path.exists() or not file_path.is_file():
        raise HTTPException(status_code=404, detail="File not found")

    return FileResponse(file_path, filename=filename)


ensure_dir(Path("outputs"))


if __name__ == "__main__":
    uvicorn.run("api.main:app", host="0.0.0.0", port=8000, reload=False)
