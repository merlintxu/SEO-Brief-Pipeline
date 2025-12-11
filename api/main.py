# api/main.py
"""
API REST FastAPI para el SEO Briefing Pipeline 2025
Endpoints:
  POST /briefing → lanza un briefing completo
  GET  /health   → chequeo rápido
"""
from __future__ import annotations

from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.responses import JSONResponse
import uvicorn
from pathlib import Path
from datetime import datetime
import os
from fastapi import FastAPI, HTTPException, BackgroundTasks, Security, status, Depends
from fastapi.security.api_key import APIKeyHeader

from seo_pipeline.config import get_config
from seo_pipeline.pipeline import run_full_pipeline
from api.schemas import BriefingRequest, BriefingResponse
from seo_pipeline.utils.io import save_json, ensure_dir, load_json
from pathlib import Path

app = FastAPI(
    title="SEO Briefing Pipeline API 2025",
    description="Generación automática de briefings SEO con SEMrush + SerpAPI + OpenAI + GSC",
    version="2025.11.18"
)

# Security
API_KEY_NAME = "X-API-Key"
API_KEY = os.getenv("API_KEY", "secret-token-2025") # Change this in production!

api_key_header = APIKeyHeader(name=API_KEY_NAME, auto_error=False)

async def get_api_key(api_key_header: str = Security(api_key_header)):
    if api_key_header == API_KEY:
        return api_key_header
    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail="Could not validate credentials",
    )

@app.on_event("startup")
async def startup_event():
    ensure_dir(Path("outputs"))

cfg = get_config()

@app.get("/health")
async def health_check():
    return {"status": "ok", "active_client": cfg.active_client.name if cfg.active_client else None}

@app.post("/briefing", response_model=BriefingResponse)
async def create_briefing(
    request: BriefingRequest, 
    background: BackgroundTasks,
    api_key: str = Depends(get_api_key)
):
    if not cfg.active_client or not cfg.active_project:
        raise HTTPException(status_code=400, detail="No hay cliente/proyecto activo configurado en el servidor")

    try:
        # Crear run_id y archivo de estado inicial
        run_id = datetime.now().strftime("%Y%m%d_%H%M%S")
        outputs_dir = Path("outputs")
        run_dir = outputs_dir / run_id
        ensure_dir(run_dir)
        status_path = run_dir / "status.json"
        save_json(status_path, {"status": "queued", "step": "queued", "message": "Tarea en cola"})

        def _bg_task(req: BriefingRequest, run_id: str, status_path: Path):
            try:
                run_full_pipeline(
                    keyword=req.keyword,
                    target_url=req.target_url,
                    upload_to_sheets=req.upload_to_sheets,
                    related_limit=req.related_limit,
                    serp_num=req.serp_num,
                    status_path=status_path,
                )
            except Exception as e:
                # status escrito por pipeline, pero reforzamos
                try:
                    save_json(status_path, {"status": "failed", "step": "error", "message": str(e)})
                except Exception:
                    pass

        background.add_task(_bg_task, request, run_id, status_path)

        # Devolver respuesta inmediata con run_id
        base_url = f"/outputs/{run_id}"
        files = {
            "status": f"{base_url}/status.json",
        }

        return BriefingResponse(
            run_id=run_id,
            keyword=request.keyword,
            output_dir=str(run_dir),
            files=files
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/briefing/{run_id}")
async def briefing_status(run_id: str):
    path = Path("outputs") / run_id / "status.json"
    if not path.exists():
        raise HTTPException(status_code=404, detail="Run_id no encontrado")
    data = load_json(path)
    return JSONResponse(content=data)

# Servidor estático para descargar archivos generados
from fastapi.staticfiles import StaticFiles
app.mount("/outputs", StaticFiles(directory="outputs"), name="outputs")

if __name__ == "__main__":
    uvicorn.run("api.main:app", host="0.0.0.0", port=8000, reload=False)