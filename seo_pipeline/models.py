# seo_pipeline/models.py
"""
Modelos de datos con Pydantic v2 (compatibilidad total v1 + fallback seguro).
Todos los contratos del pipeline están aquí centralizados.
"""
from __future__ import annotations

from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field, ConfigDict, field_validator

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
    keyword: str = Field(..., min_length=1, max_length=100, description="Keyword phrase")
    search_volume: int = Field(default=0, ge=0, le=999999999, description="Monthly search volume")


class SemrushResults(BaseModel):
    model_config = BaseConfig
    keyword_principal: SemrushKeyword
    keywords_secundarias: List[SemrushKeyword] = Field(default_factory=list, max_length=100)


# ==================== SERP ====================
class SerpSnapshot(BaseModel):
    model_config = BaseConfig
    provider: str = Field(default="unknown")
    query: str = Field(default="")
    gl: str = Field(default="")
    hl: str = Field(default="")
    organic_results_count: int = Field(default=0, ge=0)
    top_urls: List[str] = Field(default_factory=list)
    people_also_ask_count: int = Field(default=0, ge=0)
    related_searches_count: int = Field(default=0, ge=0)
    ai_overview_present: bool = False
    knowledge_graph_present: bool = False


class SerpSearchParameters(BaseModel):
    model_config = BaseConfig
    q: str = ""
    gl: str = ""
    hl: str = ""


class SerpOrganicResult(BaseModel):
    model_config = BaseConfig
    link: str = ""


class SerpPeopleAlsoAskItem(BaseModel):
    model_config = BaseConfig
    question: str = ""


class SerpRelatedSearchItem(BaseModel):
    model_config = BaseConfig
    query: str = ""


class SerpAiOverviewCitation(BaseModel):
    model_config = BaseConfig
    link: str = ""
    source: str = ""
    url: str = ""


class SerpAiOverview(BaseModel):
    model_config = BaseConfig
    sources: List[SerpAiOverviewCitation] = Field(default_factory=list)
    citations: List[SerpAiOverviewCitation] = Field(default_factory=list)


class SerpRawPayload(BaseModel):
    model_config = BaseConfig
    search_parameters: SerpSearchParameters = Field(default_factory=SerpSearchParameters)
    organic_results: List[SerpOrganicResult] = Field(default_factory=list)
    people_also_ask: List[SerpPeopleAlsoAskItem] = Field(default_factory=list)
    related_searches: List[SerpRelatedSearchItem] = Field(default_factory=list)
    ai_overview: Optional[SerpAiOverview] = None
    knowledge_graph: Optional[Dict[str, Any]] = None


# ==================== Stage Contracts (A1) ====================
class PipelineInput(BaseModel):
    model_config = BaseConfig
    keyword: str = Field(..., min_length=2, max_length=100)
    target_url: Optional[str] = Field(default=None, max_length=2048)
    related_limit: int = Field(default=30, ge=5, le=100)
    serp_num: int = Field(default=10, ge=1, le=50)
    top_competitors_count: int = Field(default=3, ge=1, le=20)
    gsc_months_back: int = Field(default=12, ge=1, le=36)
    upload_to_sheets: bool = True


class KeywordSet(BaseModel):
    model_config = BaseConfig
    principal: SemrushKeyword
    related: List[SemrushKeyword] = Field(default_factory=list, max_length=100)
    source: str = Field(default="semrush")


class CompetitorSet(BaseModel):
    model_config = BaseConfig
    top_urls: List[str] = Field(default_factory=list, max_length=50)
    domains: List[str] = Field(default_factory=list, max_length=50)
    source: str = Field(default="serp")


class EnrichmentSet(BaseModel):
    model_config = BaseConfig
    serp_snapshot: SerpSnapshot
    audit_report: "AuditReport"
    cannibalization: Optional["GscCannibalization"] = None
    anchors: Optional["AnchorSet"] = None


class BriefingPlan(BaseModel):
    model_config = BaseConfig
    keyword: str = Field(..., min_length=2, max_length=100)
    intent_summary: str = Field(default="", max_length=1000)
    required_sections: List[str] = Field(default_factory=list, max_length=30)
    evidence_points: List[str] = Field(default_factory=list, max_length=50)
    constraints: List[str] = Field(default_factory=list, max_length=30)
    prompt_version: str = Field(default="v1")


# ==================== Auditoría ====================
class SchemaSignals(BaseModel):
    model_config = BaseConfig
    has_article: bool = False
    has_product: bool = False
    has_breadcrumb: bool = False
    has_faq: bool = False
    schema_types: List[str] = Field(default_factory=list)  # Renamed from raw_types to avoid Pydantic conflict


class AuditEntry(BaseModel):
    if PYDANTIC_V2:
        model_config = ConfigDict(protected_namespaces=())

    url: str = Field(..., min_length=1, max_length=2048, description="URL being audited")
    status_code: int = Field(default=0, ge=0, le=599, description="HTTP status code")
    elapsed_ms: int = Field(default=0, ge=0, le=120000, description="Fetch and parse elapsed time in milliseconds")
    title: str = Field(default="", max_length=100, description="Page title (max 100 chars)")
    h1: str = Field(default="", max_length=100, description="H1 tag content")
    meta_desc: str = Field(default="", max_length=200, description="Meta description")
    word_count: int = Field(default=0, ge=0, le=50000, description="Word count (max 50k)")
    headings: Dict[str, List[str]] = Field(default_factory=dict)
    schema_signals: SchemaSignals = Field(default_factory=SchemaSignals)
    is_pdf: bool = False
    errors: List[str] = Field(default_factory=list, max_length=50)

    @field_validator('url')
    @classmethod
    def validate_url(cls, v: str) -> str:
        """Ensure URL is not just whitespace."""
        if not v.strip():
            raise ValueError("URL cannot be empty or whitespace-only")
        return v.strip()


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
    primary: List[str] = Field(default_factory=list, max_length=5)
    secondary: List[str] = Field(default_factory=list, max_length=8)
    internal: List[str] = Field(default_factory=list, max_length=12)


# ==================== Briefing (Moved from blueprint.py) ====================
class BriefingSection(BaseModel):
    title: str = Field(..., description="Título de la sección (H2)")
    content: str = Field(..., description="Contenido completo y accionable de la sección")


class FAQItem(BaseModel):
    question: str
    answer: str


class InternalLink(BaseModel):
    anchor: str
    target_url: str
    reason: str = Field(..., description="Por qué este enlace mejora la arquitectura y el SEO")


class ExternalLink(BaseModel):
    url: str
    anchor: str
    authority: str = Field(..., description="DR, DA, tráfico orgánico estimado o motivo de autoridad")


class SEOBriefing(BaseModel):
    meta_title: str = Field(..., max_length=60)
    meta_description: str = Field(..., max_length=160)
    h1: str
    tone_style: str = Field(..., description="Ej: profesional y cercano, conversacional experto, etc.")
    unique_angle: str = Field(..., description="Diferenciador clave frente a la competencia actual")
    longitud_recomendada: str = Field(default="2500–3500 palabras")
    eeat_notas: str = Field(default="", description="Cómo demostrar Expertise, Experience, Authoritativeness y Trustworthiness")

    headings: List[BriefingSection] = Field(..., min_length=8, max_length=20)
    faqs: List[FAQItem] = Field(default_factory=list, max_length=12)
    internal_inbound: List[InternalLink] = Field(default_factory=list, description="Enlaces que deberían apuntar a esta URL")
    internal_outbound: List[InternalLink] = Field(default_factory=list, max_length=15)
    external_links: List[ExternalLink] = Field(default_factory=list, max_length=10)
    multimedia_suggestions: List[str] = Field(default_factory=list, description="Ideas concretas de imágenes, tablas, gráficos, vídeos incrustados...")


# ==================== Row 24 columnas ====================
from seo_pipeline.constants import HEADERS_24

class SheetRow24(BaseModel):
    model_config = BaseConfig

    kw_principal: str = Field(..., min_length=1, max_length=100, description="Primary keyword")
    sv_principal: int = Field(default=0, ge=0, le=9999999, description="Search volume")
    kw_secundarias: List[str] = Field(default_factory=list, max_length=20)
    url_objetivo: str = Field(default="", max_length=2048)
    title: str = Field(default="", max_length=100)
    h1: str = Field(default="", max_length=100)
    meta_desc: str = Field(default="", max_length=200)
    slugs_relacionados: List[str] = Field(default_factory=list, max_length=20)
    ai_overview_present: bool = False
    paa_count: int = Field(default=0, ge=0, le=100)
    related_count: int = Field(default=0, ge=0, le=1000)
    kg_present: bool = False
    schema_article: bool = False
    schema_product: bool = False
    schema_breadcrumb: bool = False
    schema_faq: bool = False
    top_competitor_1: str = Field(default="", max_length=2048)
    top_competitor_2: str = Field(default="", max_length=2048)
    top_competitor_3: str = Field(default="", max_length=2048)
    anchor_primary: List[str] = Field(default_factory=list, max_length=10)
    anchor_secondary: List[str] = Field(default_factory=list, max_length=15)
    anchor_internal: List[str] = Field(default_factory=list, max_length=20)
    notes: str = Field(default="", max_length=1000)
    run_id: str = Field(default="", max_length=50)

    @field_validator('kw_principal')
    @classmethod
    def validate_keyword(cls, v: str) -> str:
        """Ensure keyword is not just whitespace."""
        if not v.strip():
            raise ValueError("Keyword cannot be empty or whitespace-only")
        return v.strip()

    @field_validator('kw_secundarias')
    @classmethod
    def validate_keywords_list(cls, v: List[str]) -> List[str]:
        """Validate all keywords in list are non-empty and reasonable length."""
        for kw in v:
            if not kw.strip():
                raise ValueError("Keywords cannot be empty")
            if len(kw) > 100:
                raise ValueError(f"Keyword too long: {kw[:50]}...")
        return [kw.strip() for kw in v]

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
