# seo_pipeline/models.py
"""
Modelos de datos con Pydantic v2 (compatibilidad total v1 + fallback seguro).
Todos los contratos del pipeline están aquí centralizados.
"""
from __future__ import annotations

from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field, ConfigDict

# Compatibilidad automática pydantic v1/v2
try:
    from pydantic import PydanticDeprecatedSince20  # v2
    PYDANTIC_V2 = True
except Exception:  # noqa: S110
    PYDANTIC_V2 = False

# Configuración global para evitar conflictos con campos reservados
if PYDANTIC_V2:
    BaseConfig = ConfigDict(protected_namespaces=())
else:
    class BaseConfig:  # type: ignore
        arbitrary_types_allowed = True


# ==================== SEMrush ====================
class SemrushKeyword(BaseModel):
    model_config = BaseConfig
    keyword: str
    search_volume: int = 0


class SemrushResults(BaseModel):
    model_config = BaseConfig
    keyword_principal: SemrushKeyword
    keywords_secundarias: List[SemrushKeyword] = Field(default_factory=list)


# ==================== Auditoría ====================
class SchemaSignals(BaseModel):
    model_config = BaseConfig
    has_article: bool = False
    has_product: bool = False
    has_breadcrumb: bool = False
    has_faq: bool = False
    raw_types: List[str] = Field(default_factory=list)


class AuditEntry(BaseModel):
    if PYDANTIC_V2:
        model_config = ConfigDict(protected_namespaces=())  # ← Esta línea ya evita el warning

    url: str
    status_code: int = 0
    title: str = ""
    h1: str = ""
    meta_desc: str = ""
    word_count: int = 0
    headings: Dict[str, List[str]] = Field(default_factory=dict)
    schema_signals: SchemaSignals = Field(default_factory=SchemaSignals, alias="schema")  # ← Cambia nombre interno
    is_pdf: bool = False
    errors: List[str] = Field(default_factory=list)


class AuditReport(BaseModel):
    model_config = BaseConfig
    label: str
    entries: List[AuditEntry]
    generated_at: str


# ==================== GSC ====================
class GscPage(BaseModel):
    model_config = BaseConfig
    url: str
    clicks: float = 0.0
    impressions: float = 0.0
    position: float = 0.0  # promedio ponderado


class GscQueryCannibal(BaseModel):
    model_config = BaseConfig
    query: str
    pages: List[GscPage]


class GscCannibalization(BaseModel):
    model_config = BaseConfig
    site_url: str
    start_date: str
    end_date: str
    items: List[GscQueryCannibal]


# ==================== Anchors ====================
class AnchorSet(BaseModel):
    model_config = BaseConfig
    primary: List[str] = Field(default_factory=list, max_items=5)
    secondary: List[str] = Field(default_factory=list, max_items=8)
    internal: List[str] = Field(default_factory=list, max_items=10)


# ==================== Row 24 columnas ====================
from seo_pipeline.constants import HEADERS_24

class SheetRow24(BaseModel):
    model_config = BaseConfig

    kw_principal: str
    sv_principal: int = 0
    kw_secundarias: List[str] = Field(default_factory=list)
    url_objetivo: str = ""
    title: str = ""
    h1: str = ""
    meta_desc: str = ""
    slugs_relacionados: List[str] = Field(default_factory=list)
    ai_overview_present: bool = False
    paa_count: int = 0
    related_count: int = 0
    kg_present: bool = False
    schema_article: bool = False
    schema_product: bool = False
    schema_breadcrumb: bool = False
    schema_faq: bool = False
    top_competitor_1: str = ""
    top_competitor_2: str = ""
    top_competitor_3: str = ""
    anchor_primary: List[str] = Field(default_factory=list)
    anchor_secondary: List[str] = Field(default_factory=list)
    anchor_internal: List[str] = Field(default_factory=list)
    notes: str = ""
    run_id: str = ""

    def to_row(self) -> List[Any]:
        """Convierte el modelo a fila compatible con HEADERS_24."""
        data = self.model_dump()
        row = []
        for header in HEADERS_24:
            value = data.get(header)
            if isinstance(value, list):
                row.append(", ".join(map(str, value)))
            else:
                row.append(value if value is not None else "")
        return row