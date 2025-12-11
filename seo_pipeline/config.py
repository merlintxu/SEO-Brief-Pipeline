# seo_pipeline/config.py
"""
Gestión centralizada de configuración, clientes, proyectos y rutas.
Elimina por completo las variables globales dispersas del notebook original.
Utiliza singleton pattern para acceso global seguro (get_config()).
"""
from __future__ import annotations

import os
import json
from pathlib import Path
from typing import Dict, Any, Optional
from pydantic import BaseModel, Field, ValidationError
from dotenv import load_dotenv

# Cargar variables de entorno (.env o Colab secrets)
load_dotenv()

class ClientConfig(BaseModel):
    client_id: str
    name: str
    semrush_token: Optional[str] = None
    serpapi_key: Optional[str] = None
    openai_key: Optional[str] = None
    piloterr_key: Optional[str] = None      # ← NUEVO
    dataforseo_login: Optional[str] = None  # ← NUEVO (DFSP_USERNAME)
    dataforseo_password: Optional[str] = None  # ← NUEVO (DFSP_PASSWORD)
    gsc_sa_path: Optional[str] = None
    sheets_sa_path: Optional[str] = None
    default_database: str = "es"
    default_gl: str = "es"
    default_hl: str = "es-es"

class ProjectConfig(BaseModel):
    project_id: str
    client_id: str
    name: str
    base_domain: str
    gsc_property: str  # URL completa de la propiedad GSC[](https://example.com/)
    sheets_id: str     # ID o URL de la hoja de cálculo principal
    output_dir: str = "outputs"

class PipelineConfig:
    _instance: Optional["PipelineConfig"] = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return

        # Rutas base
        self.root_dir = Path(os.getenv("PIPELINE_ROOT", Path.cwd()))
        self.data_dir = self.root_dir / "data"
        self.cache_dir = self.data_dir / "cache"
        self.runs_dir = self.data_dir / "runs"
        self.clients_file = self.data_dir / "clients.json"
        self.projects_file = self.data_dir / "projects.json"

        # Crear carpetas si no existen
        for d in (self.data_dir, self.cache_dir, self.runs_dir):
            d.mkdir(parents=True, exist_ok=True)

        # Estado activo
        self.active_client: Optional[ClientConfig] = None
        self.active_project: Optional[ProjectConfig] = None

        # Cargar clientes y proyectos
        self.clients: Dict[str, ClientConfig] = self._load_clients()
        self.projects: Dict[str, ProjectConfig] = self._load_projects()

        self._initialized = True

    # ===================================================================
    # Carga y guardado persistente
    # ===================================================================
    def _load_clients(self) -> Dict[str, ClientConfig]:
        if not self.clients_file.exists():
            return {}
        try:
            raw = json.loads(self.clients_file.read_text(encoding="utf-8"))
            return {c["client_id"]: ClientConfig(**c) for c in raw}
        except (OSError, json.JSONDecodeError) as e:
            from seo_pipeline.utils.logging import logger
            logger.error("Error cargando clientes: %s", e)
            return {}

    def _load_projects(self) -> Dict[str, ProjectConfig]:
        if not self.projects_file.exists():
            return {}
        try:
            raw = json.loads(self.projects_file.read_text(encoding="utf-8"))
            return {p["project_id"]: ProjectConfig(**p) for p in raw}
        except (OSError, json.JSONDecodeError) as e:
            from seo_pipeline.utils.logging import logger
            logger.error("Error cargando proyectos: %s", e)
            return {}

    def save_clients(self):
        data = [c.model_dump() for c in self.clients.values()]
        self.clients_file.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

    def save_projects(self):
        data = [p.model_dump() for p in self.projects.values()]
        self.projects_file.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

    # ===================================================================
    # Gestión de cliente/proyecto activo
    # ===================================================================
    def set_active_client(self, client_id: str) -> bool:
        if client_id not in self.clients:
            return False
        self.active_client = self.clients[client_id]
        # Reset proyecto si no pertenece al cliente
        if self.active_project and self.active_project.client_id != client_id:
            self.active_project = None
        return True

    def set_active_project(self, project_id: str) -> bool:
        if project_id not in self.projects:
            return False
        proj = self.projects[project_id]
        if not self.active_client or proj.client_id != self.active_client.client_id:
            self.set_active_client(proj.client_id)
        self.active_project = proj
        return True

    # ===================================================================
    # Helpers de rutas dinámicas
    # ===================================================================
    def get_output_dir(self) -> Path:
        if not self.active_project:
            raise RuntimeError("No hay proyecto activo")
        path = self.root_dir / self.active_project.output_dir / self.active_project.project_id
        path.mkdir(parents=True, exist_ok=True)
        return path

    def get_current_run_dir(self, run_id: Optional[str] = None) -> Path:
        run_id = run_id or Path().stem  # fallback simple
        run_dir = self.runs_dir / run_id
        run_dir.mkdir(parents=True, exist_ok=True)
        return run_dir

# =======================================================================
# Singleton accessor (uso recomendado en todo el código)
# =======================================================================
def get_config() -> PipelineConfig:
    return PipelineConfig()
