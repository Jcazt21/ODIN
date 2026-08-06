"""Schemas Pydantic de la API — requests y respuestas.

Separado de las rutas (tarea 24 de task.md, §9.2): antes vivían todos
mezclados con los handlers en `api.py`, un archivo de 1700+ líneas. Los
`response_model=` interpuestos entre los modelos ORM (`db/models.py`) y las
rutas usan `from_attributes=True` para leer directo de objetos SQLAlchemy —
ver `_ResponseModel` — y `scripts/generate_openapi.py` + `openapi-typescript`
generan los tipos TS del frontend a partir de ellos (tarea 25 de task.md).
"""
from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

# ── Análisis ──────────────────────────────────────────────────────────────────


class AnalyzeRequest(BaseModel):
    url: str = Field(min_length=1, max_length=2048)


class EntityPayload(BaseModel):
    name: str
    type: str
    mentions_count: int = 1
    sentiment_toward: str | None = None
    sentiment_score: float | None = None
    context: str | None = None
    extraction_confidence: float = 1.0


class SaveArticleRequest(BaseModel):
    source: str
    url: str
    title: str
    authors: str | None = None
    section: str | None = None
    published_at: str | None = None
    body: str
    main_topic: str | None = None
    topic_keywords: str | None = None
    overall_sentiment: str | None = None
    sentiment_score: float | None = None
    framing: str | None = None
    headline_intent: str | None = None
    lead_orientation: str | None = None
    dominant_actor: str | None = None
    source_quality: str | None = None
    has_hard_data: bool | None = None
    blamed_actor: str | None = None
    credited_actor: str | None = None
    sentiment_basis: str | None = None
    facts_sentiment: str | None = None
    quoted_sentiment: str | None = None
    media_stance: str | None = None
    media_stance_evidence: str | None = None
    overall_sentiment_reason: str | None = None
    content_flags: str | None = None
    entities: list[EntityPayload] = []


# ── Schemas de siglas ─────────────────────────────────────────────────────────


class AliasPayload(BaseModel):
    alias: str = Field(min_length=1, max_length=100)
    canonical_name: str = Field(min_length=1, max_length=300)
    type: str = Field(default="ORG", pattern="^(ORG|PERSON)$")
    is_active: bool = True


class AliasUpdatePayload(BaseModel):
    alias: str | None = Field(default=None, min_length=1, max_length=100)
    canonical_name: str | None = Field(default=None, min_length=1, max_length=300)
    type: str | None = Field(default=None, pattern="^(ORG|PERSON)$")
    is_active: bool | None = None


# ── Schemas de entidades canónicas ───────────────────────────────────────────


class CanonicalEntityUpdatePayload(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=300)
    description: str | None = Field(default=None, max_length=300)


class CanonicalEntityMergePayload(BaseModel):
    source_id: int = Field(description="Se funde DENTRO del {id} de la URL; la fuente se borra.")


# ── Schemas de rectificación de artículos y menciones (§8.2) ─────────────────


class ArticleUpdatePayload(BaseModel):
    """Corrige el análisis (no el contenido escrapeado) de un artículo ya
    guardado: solo los campos que produce el analizador, nunca `title`/`body`/
    `url` (eso es lo que decía la fuente, no un juicio del sistema)."""

    main_topic: str | None = None
    topic_keywords: str | None = None
    overall_sentiment: str | None = None
    sentiment_score: float | None = Field(default=None, ge=0, le=1)
    framing: str | None = None
    headline_intent: str | None = None
    lead_orientation: str | None = None
    dominant_actor: str | None = None
    source_quality: str | None = None
    has_hard_data: bool | None = None
    blamed_actor: str | None = None
    credited_actor: str | None = None


class EntityUpdatePayload(BaseModel):
    """Corrige una mención puntual (nombre mal extraído, sentimiento mal
    inferido...) sin tener que borrar y re-analizar todo el artículo."""

    name: str | None = Field(default=None, min_length=1, max_length=300)
    type: str | None = Field(default=None, pattern="^(PERSON|ORG)$")
    sentiment_toward: str | None = None
    sentiment_score: float | None = Field(default=None, ge=0, le=1)
    context: str | None = None


# ── Schemas de respuesta (tarea 25 de task.md, §9.2) ─────────────────────────
# Interpuestos entre los modelos ORM (db/models.py) y las rutas vía
# `response_model=`, con `from_attributes=True` para leer directo de los
# objetos SQLAlchemy. Sustituyen a los serializadores mano a mano que había
# antes (_serialize/_serialize_summary/_serialize_canonical_entity) y a los
# dicts inline repetidos por ruta: esos campos ahora se declaran UNA vez, y
# `scripts/generate_openapi.py` + `openapi-typescript` generan los tipos TS
# del frontend a partir de ellos (ver frontend/src/lib/odin-api.ts), en vez
# de mantener una tercera copia a mano.


class _ResponseModel(BaseModel):
    """Base común: `from_attributes` para leer objetos SQLAlchemy directo, y
    `json_schema_serialization_defaults_required` para que los campos con
    default de Python (ej. `authors: str | None = None`, siempre presentes en
    la respuesta real) salgan como requeridos en el OpenAPI/TS generados —
    Pydantic los marca opcionales por defecto por tener un valor por omisión
    en el constructor, no porque la ruta pueda omitirlos."""

    model_config = ConfigDict(from_attributes=True, json_schema_serialization_defaults_required=True)


class EntityMention(_ResponseModel):
    """Una mención de entidad. `id` y `canonical_entity_id` son `null` en la
    vista previa de /api/analyze (el artículo aún no se guardó — `EntityResult`,
    la clase de esa vista previa, ni siquiera tiene esos dos atributos)."""

    id: int | None = None
    name: str
    type: str
    mentions_count: int
    sentiment_toward: str | None = None
    sentiment_score: float | None = None
    context: str | None = None
    extraction_confidence: float
    canonical_entity_id: int | None = None


class ArticleDetail(_ResponseModel):
    """Reporte completo con sus entidades: respuesta de /api/analyze,
    POST /api/articles y GET/PUT /api/articles/{id}."""

    already_saved: bool = False
    id: int | None = None
    source: str
    url: str
    title: str
    authors: str | None = None
    section: str | None = None
    published_at: datetime | None = None
    body: str | None = None
    main_topic: str | None = None
    topic_keywords: str | None = None
    overall_sentiment: str | None = None
    sentiment_score: float | None = None
    framing: str | None = None
    headline_intent: str | None = None
    lead_orientation: str | None = None
    dominant_actor: str | None = None
    source_quality: str | None = None
    has_hard_data: bool | None = None
    blamed_actor: str | None = None
    credited_actor: str | None = None
    # Capas de sentimiento: de quién es la carga (hechos reportados / discurso
    # citado / voz del medio) y por qué se etiquetó así. NULL con LocalAnalyzer.
    sentiment_basis: str | None = None
    facts_sentiment: str | None = None
    quoted_sentiment: str | None = None
    media_stance: str | None = None
    media_stance_evidence: str | None = None
    overall_sentiment_reason: str | None = None
    content_flags: str | None = None  # separados por ", " (igual que topic_keywords)
    analyzer_name: str | None = None
    analyzer_model: str | None = None
    analyzer_version: str | None = None
    analysis_schema_version: int | None = None
    analyzed_at: datetime | None = None
    entities: list[EntityMention] = []


class ArticleSummary(_ResponseModel):
    """Fila de GET /api/articles: sin cuerpo ni entidades detalladas."""

    id: int
    source: str
    url: str
    title: str
    section: str | None = None
    published_at: datetime | None = None
    scraped_at: datetime
    main_topic: str | None = None
    overall_sentiment: str | None = None
    sentiment_score: float | None = None
    framing: str | None = None
    headline_intent: str | None = None
    lead_orientation: str | None = None
    source_quality: str | None = None
    has_hard_data: bool | None = None
    dominant_actor: str | None = None
    blamed_actor: str | None = None
    credited_actor: str | None = None
    entity_count: int = 0


class ArticleListResponse(BaseModel):
    total: int
    limit: int
    offset: int
    items: list[ArticleSummary]


class ArticleFiltersResponse(BaseModel):
    sources: list[str]
    sections: list[str]
    sentiments: list[str]
    framing: list[str]
    headline_intent: list[str]
    lead_orientation: list[str]
    source_quality: list[str]


class EntityAliasResponse(_ResponseModel):
    id: int
    alias: str
    canonical_name: str
    type: str
    is_active: bool
    created_at: datetime
    updated_at: datetime


class CanonicalEntityResponse(_ResponseModel):
    id: int
    name: str
    type: str
    description: str | None = None
    created_at: datetime
    updated_at: datetime
    article_count: int = 0
    total_mentions: int = 0


class CanonicalEntityArticleMention(_ResponseModel):
    article_id: int
    title: str
    url: str
    source: str
    published_at: datetime | None = None
    sentiment_toward: str | None = None
    mentions_count: int


class CanonicalEntityDetailResponse(CanonicalEntityResponse):
    articles: list[CanonicalEntityArticleMention]


class CanonicalEntityListResponse(BaseModel):
    total: int
    limit: int
    offset: int
    items: list[CanonicalEntityResponse]


class HealthResponse(BaseModel):
    status: str


class AnalyzeAccepted(BaseModel):
    """Respuesta de POST /api/analyze cuando la URL es nueva: el trabajo
    pesado (descarga + NLP, hasta ~60s) corre en segundo plano (§3.1 de
    task.md) en vez de bloquear el request. El cliente hace polling de
    GET /api/jobs/{job_id} hasta que `status` sea `done` o `failed`."""

    job_id: str
    status: str = "pending"


class JobResponse(BaseModel):
    job_id: str
    status: str  # pending | running | done | failed
    error: str | None = None
    result: ArticleDetail | None = None


# ── Reportes: enumeraciones fijas de filtros ─────────────────────────────────

SENTIMENT_VALUES = ("POS", "NEG", "NEU")
FRAMING_VALUES = (
    "crisis_conflicto",
    "logro_institucional",
    "negligencia",
    "crecimiento",
    "denuncia",
    "neutro_informativo",
)
HEADLINE_INTENT_VALUES = ("informativo", "alarmista", "sensacionalista")
LEAD_ORIENTATION_VALUES = ("social", "oficialista", "tecnico")
SOURCE_QUALITY_VALUES = (
    "citas_directas",
    "testimonios_anonimos",
    "datos_duros",
    "mixtas",
    "sin_fuentes",
)


# ── Corridas del pipeline / scraper ──────────────────────────────────────────


class CrawlRunResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    correlation_id: str
    started_at: datetime
    finished_at: datetime | None
    status: str
    sources: str | None
    analyzer_name: str | None
    articles_discovered: int
    articles_saved: int
    articles_failed: int
    stats_by_source: str | None
    error: str | None


class ScrapeJobStartRequest(BaseModel):
    target: int = Field(default=250, gt=0, le=2000)
    per_source_cap: int | None = Field(default=None, gt=0)
    analyzer: Literal["local", "groq", "hybrid"] = "local"


class ScrapeJobAccepted(BaseModel):
    job_id: str
    status: str = "pending"


class ScrapeSourceProgress(BaseModel):
    source: str
    stage: str
    status: str
    detail: str
    updated_at: datetime | None = None


class ScrapeJobResponse(BaseModel):
    job_id: str
    status: str
    target: int
    per_source_cap: int
    analyzer: str
    created_at: datetime
    started_at: datetime | None
    finished_at: datetime | None
    progress: dict[str, ScrapeSourceProgress]
    crawl_run: CrawlRunResponse | None = None
    error: str | None = None
