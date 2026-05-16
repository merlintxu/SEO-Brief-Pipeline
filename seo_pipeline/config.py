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
from typing import Dict, Optional
from pydantic import BaseModel, Field, field_validator
from dotenv import load_dotenv

from seo_pipeline.options import (
    DEFAULT_LLM_MODEL,
    DEFAULT_LLM_PROVIDER,
    DEFAULT_OLLAMA_BASE_URL,
    GOOGLE_GL_OPTIONS,
    GOOGLE_HL_OPTIONS,
    LLM_PROVIDER_OPTIONS,
    SEMRUSH_DATABASES,
    validate_choice,
)

# Cargar variables de entorno (.env o Colab secrets)
load_dotenv()


class RuntimeSettings(BaseModel):
    semrush_token: Optional[str] = None
    serpapi_key: Optional[str] = None
    openai_key: Optional[str] = None
    anthropic_key: Optional[str] = None
    llm_base_url: Optional[str] = DEFAULT_OLLAMA_BASE_URL
    dataforseo_login: Optional[str] = None
    dataforseo_password: Optional[str] = None

    @field_validator("*", mode="before")
    @classmethod
    def normalize_optional_string(cls, value: object) -> object:
        if isinstance(value, str):
            stripped = value.strip()
            return stripped or None
        return value


class ClientConfig(BaseModel):
    client_id: str
    name: str
    default_base_domain: Optional[str] = None
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

    @field_validator("default_database")
    @classmethod
    def validate_default_database(cls, value: str) -> str:
        return validate_choice(value, SEMRUSH_DATABASES, "default_database")

    @field_validator("default_gl")
    @classmethod
    def validate_default_gl(cls, value: str) -> str:
        return validate_choice(value, GOOGLE_GL_OPTIONS, "default_gl")

    @field_validator("default_hl")
    @classmethod
    def validate_default_hl(cls, value: str) -> str:
        return validate_choice(value, GOOGLE_HL_OPTIONS, "default_hl")


class ProjectLlmConfig(BaseModel):
    provider: str = Field(default=DEFAULT_LLM_PROVIDER)
    model: Optional[str] = DEFAULT_LLM_MODEL
    base_url: Optional[str] = DEFAULT_OLLAMA_BASE_URL
    prompt_version: str = "v1"

    @field_validator("provider")
    @classmethod
    def validate_provider(cls, value: str) -> str:
        normalized = value.strip().lower()
        if normalized not in LLM_PROVIDER_OPTIONS:
            raise ValueError("llm.provider must be one of: openai, ollama, anthropic")
        return normalized

    @field_validator("model", "base_url", mode="before")
    @classmethod
    def normalize_optional_string(cls, value: object) -> object:
        if isinstance(value, str):
            value = value.strip()
            return value or None
        return value

    @field_validator("prompt_version")
    @classmethod
    def validate_prompt_version(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("llm.prompt_version must not be empty")
        return normalized


class ProjectSerpConfig(BaseModel):
    provider_order: list[str] = Field(default_factory=lambda: ["serpapi", "dataforseo"], min_length=1)

    @field_validator("provider_order")
    @classmethod
    def validate_provider_order(cls, value: list[str]) -> list[str]:
        normalized: list[str] = []
        for item in value:
            provider = item.strip().lower()
            if provider not in {"serpapi", "dataforseo"}:
                raise ValueError("serp.provider_order only supports: serpapi, dataforseo")
            if provider not in normalized:
                normalized.append(provider)
        if not normalized:
            raise ValueError("serp.provider_order must not be empty")
        return normalized


class ProjectProviderConfig(BaseModel):
    serp: ProjectSerpConfig = Field(default_factory=ProjectSerpConfig)


class ProjectRuntimeConfig(BaseModel):
    llm: ProjectLlmConfig = Field(default_factory=ProjectLlmConfig)
    providers: ProjectProviderConfig = Field(default_factory=ProjectProviderConfig)


class ProjectConfig(BaseModel):
    project_id: str
    client_id: str
    name: str
    base_domain: Optional[str] = None
    gsc_property: str  # URL completa de la propiedad GSC[](https://example.com/)
    sheets_id: str     # ID o URL de la hoja de cálculo principal
    ga4_property_id: Optional[str] = None
    project_type: str = "content"
    semrush_database: Optional[str] = None
    google_gl: Optional[str] = None
    google_hl: Optional[str] = None
    output_dir: str = "outputs"
    runtime: ProjectRuntimeConfig = Field(default_factory=ProjectRuntimeConfig)

    @field_validator("project_type")
    @classmethod
    def validate_project_type(cls, value: str) -> str:
        normalized = value.strip().lower()
        allowed = {"content", "ecommerce", "local", "saas", "marketplace"}
        if normalized not in allowed:
            raise ValueError("project_type must be one of: content, ecommerce, local, saas, marketplace")
        return normalized

    @field_validator("semrush_database")
    @classmethod
    def validate_semrush_database(cls, value: Optional[str]) -> Optional[str]:
        return validate_choice(value, SEMRUSH_DATABASES, "semrush_database") if value else None

    @field_validator("google_gl")
    @classmethod
    def validate_google_gl(cls, value: Optional[str]) -> Optional[str]:
        return validate_choice(value, GOOGLE_GL_OPTIONS, "google_gl") if value else None

    @field_validator("google_hl")
    @classmethod
    def validate_google_hl(cls, value: Optional[str]) -> Optional[str]:
        return validate_choice(value, GOOGLE_HL_OPTIONS, "google_hl") if value else None

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
        self.config_dir = self.root_dir / "config"
        self.clients_file = self.data_dir / "clients.json"
        self.projects_file = self.data_dir / "projects.json"
        self.runtime_settings_file = self.config_dir / "runtime_settings.json"

        # Crear carpetas si no existen
        for d in (self.data_dir, self.cache_dir, self.runs_dir, self.config_dir):
            d.mkdir(parents=True, exist_ok=True)

        # Estado activo
        self.active_client: Optional[ClientConfig] = None
        self.active_project: Optional[ProjectConfig] = None

        # Cargar clientes y proyectos
        self.runtime_settings: RuntimeSettings = self._load_runtime_settings()
        self.clients: Dict[str, ClientConfig] = self._load_clients()
        self.projects: Dict[str, ProjectConfig] = self._load_projects()

        self._initialized = True

    # ===================================================================
    # Carga y guardado persistente
    # ===================================================================
    def _load_runtime_settings(self) -> RuntimeSettings:
        raw: dict = {}
        if self.runtime_settings_file.exists():
            try:
                raw = json.loads(self.runtime_settings_file.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError) as e:
                from seo_pipeline.utils.logging import logger
                logger.error(f"Error cargando runtime settings: {e}")
                raw = {}
        return RuntimeSettings(
            semrush_token=raw.get("semrush_token") or os.getenv("SEMRUSH_TOKEN"),
            serpapi_key=raw.get("serpapi_key") or os.getenv("SERPAPI_KEY"),
            openai_key=raw.get("openai_key") or os.getenv("OPENAI_API_KEY"),
            anthropic_key=raw.get("anthropic_key") or os.getenv("ANTHROPIC_API_KEY"),
            llm_base_url=raw.get("llm_base_url") or os.getenv("OLLAMA_BASE_URL") or DEFAULT_OLLAMA_BASE_URL,
            dataforseo_login=raw.get("dataforseo_login") or os.getenv("DFSP_USERNAME"),
            dataforseo_password=raw.get("dataforseo_password") or os.getenv("DFSP_PASSWORD"),
        )

    def save_runtime_settings(self):
        self.runtime_settings_file.write_text(
            json.dumps(self.runtime_settings.model_dump(), ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    def _load_clients(self) -> Dict[str, ClientConfig]:
        if not self.clients_file.exists():
            return {}
        try:
            raw = json.loads(self.clients_file.read_text(encoding="utf-8"))
            return {c["client_id"]: ClientConfig(**c) for c in raw}
        except (OSError, json.JSONDecodeError) as e:
            from seo_pipeline.utils.logging import logger
            logger.error(f"Error cargando clientes: {e}")
            return {}

    def _load_projects(self) -> Dict[str, ProjectConfig]:
        if not self.projects_file.exists():
            return {}
        try:
            raw = json.loads(self.projects_file.read_text(encoding="utf-8"))
            return {p["project_id"]: ProjectConfig(**p) for p in raw}
        except (OSError, json.JSONDecodeError) as e:
            from seo_pipeline.utils.logging import logger
            logger.error(f"Pipeline fallido para 'projects': {e}", exc_info=True)
            return {}

    def save_clients(self):
        data = [c.model_dump() for c in self.clients.values()]
        self.clients_file.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

    def save_projects(self):
        data = [p.model_dump() for p in self.projects.values()]
        self.projects_file.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

    def apply_effective_client_defaults(self, client: ClientConfig) -> ClientConfig:
        """Merge global runtime credentials into a client without mutating stored JSON."""
        settings = self.runtime_settings
        payload = client.model_dump()
        payload["semrush_token"] = payload.get("semrush_token") or settings.semrush_token
        payload["serpapi_key"] = payload.get("serpapi_key") or settings.serpapi_key
        payload["openai_key"] = payload.get("openai_key") or settings.openai_key
        payload["dataforseo_login"] = payload.get("dataforseo_login") or settings.dataforseo_login
        payload["dataforseo_password"] = payload.get("dataforseo_password") or settings.dataforseo_password
        return ClientConfig(**payload)

    def resolve_project_base_domain(self, project: ProjectConfig) -> str:
        if project.base_domain:
            return project.base_domain
        client = self.clients.get(project.client_id)
        return client.default_base_domain if client and client.default_base_domain else ""

    def resolve_project_database(self, project: ProjectConfig) -> str:
        client = self.clients.get(project.client_id)
        return project.semrush_database or (client.default_database if client else "es")

    def resolve_project_gl(self, project: ProjectConfig) -> str:
        client = self.clients.get(project.client_id)
        return project.google_gl or (client.default_gl if client else "es")

    def resolve_project_hl(self, project: ProjectConfig) -> str:
        client = self.clients.get(project.client_id)
        return project.google_hl or (client.default_hl if client else "es-es")

    # ===================================================================
    # Gestión de cliente/proyecto activo
    # ===================================================================
    def set_active_client(self, client_id: str) -> bool:
        if client_id not in self.clients:
            return False
        self.active_client = self.apply_effective_client_defaults(self.clients[client_id])
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
        path = self.root_dir / self.active_project.output_dir / self.active_project.client_id / self.active_project.project_id
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
