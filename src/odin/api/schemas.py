"""Schemas Pydantic de la API — requests y respuestas.

Separado de las rutas (tarea 24 de task.md, §9.2): antes vivían todos
mezclados con los handlers en `api.py`, un archivo de 1700+ líneas. Los
`response_model=` interpuestos entre los modelos ORM (`db/models.py`) y las
rutas usan `from_attributes=True` para leer directo de objetos SQLAlchemy —
ver `_ResponseModel` — y `scripts/generate_openapi.py` + `openapi-typescript`
generan los tipos TS del frontend a partir de ellos (tarea 25 de task.md).
"""
from __future__ import annotations

from datetime import date, datetime
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


class ArticleLocalityPayload(BaseModel):
    """Alta de un vínculo artículo↔lugar.

    `locality_id` a secas, sin país/región/provincia/municipio por separado: el
    "Todas" del formulario del cliente solo indica hasta qué nivel bajó el
    documentalista, y eso ya queda dicho por CUÁL nodo eligió. Guardar los
    cuatro campos obligaría a que cada reporte filtrara centinelas.
    """

    locality_id: int
    kind: str = "HECHO"
    origin: str = "MANUAL"
    confidence: float | None = None


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
    # Lugares de la noticia, para el alta manual. Van en el mismo cuerpo y no
    # en una segunda llamada para que artículo y vínculos entren o fallen
    # juntos. Default vacío: el flujo de /api/analyze no manda el campo.
    localities: list[ArticleLocalityPayload] = []


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
    """Una mención de entidad de un artículo YA guardado: `id` es siempre la
    fila real de `Entity` (nunca preview). Ver `AnalyzePreviewEntity` para la
    vista previa sin guardar de POST /api/analyze."""

    id: int
    name: str
    type: str
    mentions_count: int
    sentiment_toward: str | None = None
    sentiment_score: float | None = None
    context: str | None = None
    extraction_confidence: float
    canonical_entity_id: int | None = None


class ArticleDetail(_ResponseModel):
    """Reporte completo YA guardado, con sus entidades: respuesta de
    POST /api/articles y GET/PUT /api/articles/{id}. Distinto del schema de
    vista previa de POST /api/analyze (`AnalyzeResult`, más abajo): acá `id` y
    `body` son siempre reales, nunca `null` (esquema separado por caso de uso
    en vez de una sola clase compartida con campos opcionales según quién
    llame)."""

    id: int
    source: str
    # Nombre legible del medio, derivado del slug de arriba (`odin.scrapers.
    # source_name`). Va aquí y no se resuelve en el frontend para que el
    # detalle no dependa de haber cargado antes las facetas.
    source_name: str = ""
    url: str
    title: str
    authors: str | None = None
    section: str | None = None
    published_at: datetime | None = None
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
    # Nombre para mostrar del documentalista que dejó guardado el reporte. `None` en
    # lo que entró por el rastreo masivo o antes de que existiera la columna.
    documentalist: str | None = None
    # Fecha del análisis, sin hora. No confundir con `published_at` (cuándo lo
    # publicó el medio): una nota de la semana pasada puede analizarse hoy.
    analyzed_on: date | None = None
    entities: list[EntityMention] = []


# ── Vista previa de POST /api/analyze ────────────────────────────────────────
# Esquema separado de ArticleDetail/EntityMention (caso de uso distinto): acá
# el artículo puede no estar guardado todavía, así que `id`/`body` sí son
# legítimamente opcionales — si se comparte esa opcionalidad con el schema de
# /api/articles, ese termina con campos "opcionales" que en realidad siempre
# vienen presentes ahí.


class AnalyzePreviewEntity(_ResponseModel):
    """Mención detectada en la vista previa: `id`/`canonical_entity_id` son
    `null` mientras el artículo no se guarde; si la URL ya estaba guardada
    (`AnalyzeResult.already_saved=True`), son los reales de esa fila."""

    id: int | None = None
    name: str
    type: str
    mentions_count: int
    sentiment_toward: str | None = None
    sentiment_score: float | None = None
    context: str | None = None
    extraction_confidence: float
    canonical_entity_id: int | None = None


class AnalyzeResult(_ResponseModel):
    """Respuesta de POST /api/analyze y del `result` de GET /api/jobs/{id}:
    o bien una vista previa recién analizada y sin guardar
    (`already_saved=False`, `id` `null`), o el artículo ya existente que se
    devuelve tal cual en vez de re-analizar (`already_saved=True`, `id` real)."""

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
    sentiment_basis: str | None = None
    facts_sentiment: str | None = None
    quoted_sentiment: str | None = None
    media_stance: str | None = None
    media_stance_evidence: str | None = None
    overall_sentiment_reason: str | None = None
    content_flags: str | None = None
    analyzer_name: str | None = None
    analyzer_model: str | None = None
    analyzer_version: str | None = None
    analysis_schema_version: int | None = None
    analyzed_at: datetime | None = None
    entities: list[AnalyzePreviewEntity] = []


class ArticleSummary(_ResponseModel):
    """Fila de GET /api/articles: sin cuerpo ni entidades detalladas."""

    id: int
    source: str
    # Nombre legible del medio, derivado del slug de arriba (`odin.scrapers.
    # source_name`). Va aquí y no se resuelve en el frontend para que el
    # detalle no dependa de haber cargado antes las facetas.
    source_name: str = ""
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
    # Nombre para mostrar del documentalista que dejó guardado el reporte. `None` en
    # lo que entró por el rastreo masivo o antes de que existiera la columna.
    documentalist: str | None = None
    # Fecha del análisis, sin hora. No confundir con `published_at` (cuándo lo
    # publicó el medio): una nota de la semana pasada puede analizarse hoy.
    analyzed_on: date | None = None
    entity_count: int = 0


class ArticleListResponse(BaseModel):
    total: int
    limit: int
    offset: int
    items: list[ArticleSummary]


class SourceOption(_ResponseModel):
    """Un medio tal como lo consume el selector de filtros.

    `value` es lo que se guarda y por lo que se filtra; `label` es solo para
    pintar. Separarlos evita que renombrar un medio en pantalla invalide los
    filtros guardados o los reportes ya escritos."""

    value: str
    label: str


class DocumentalistOption(_ResponseModel):
    """Un documentalista tal como lo consume el selector de filtros."""

    id: int
    display_name: str


class ArticleFiltersResponse(BaseModel):
    sources: list[SourceOption]
    sections: list[str]
    # Temas ya usados, para sugerir en el formulario manual mientras no
    # exista el catálogo administrable (R4). Texto libre, no enumeración.
    topics: list[str] = []
    sentiments: list[str]
    framing: list[str]
    headline_intent: list[str]
    lead_orientation: list[str]
    source_quality: list[str]
    documentalists: list[DocumentalistOption] = []


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
    sentiment_score: float | None = None
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
    stage: str | None = None  # fetching | analyzing | canonicalizing — solo con status=running
    error: str | None = None
    result: AnalyzeResult | None = None


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


# --- Lugar de la noticia -----------------------------------------------------
# Valores permitidos, espejo de los del modelo (db/models.py). Se repiten aquí
# porque la capa HTTP valida antes de tocar la BD: un `kind` inválido debe dar
# 422 en el borde, no un IntegrityError a mitad del guardado.
LOCALITY_LEVEL_VALUES = ("PAIS", "MACRORREGION", "REGION", "PROVINCIA", "MUNICIPIO")
LOCALITY_KIND_VALUES = ("HECHO", "MENCIONADO")
LOCALITY_ORIGIN_VALUES = ("MANUAL", "AUTO")


class LocalityResponse(_ResponseModel):
    id: int
    name: str
    level: str
    parent_id: int | None = None
    path: str
    is_active: bool


class LocalityNode(_ResponseModel):
    """Nodo del árbol con sus hijos: lo que consume el selector en cascada del
    frontend, que necesita el árbol entero de una vez para no pedir un fetch
    por cada desplegable que el documentalista abre."""

    id: int
    name: str
    level: str
    parent_id: int | None = None
    # Los alias viajan con el árbol para que el buscador del frontend pueda
    # filtrar en memoria mientras se teclea: sin ellos, escribir "Navarrete"
    # no encontraría Villa Bisonó sin ir al servidor en cada pulsación.
    aliases: list[str] = []
    children: list[LocalityNode] = []


class LocalityBreadcrumb(_ResponseModel):
    """El camino del país hasta el nodo elegido.

    Es lo que permite mostrar "República Dominicana › Cibao › Santiago ›
    Tamboril" sin que el frontend tenga que recorrer el árbol hacia arriba.
    """

    id: int
    name: str
    level: str


class ArticleLocalityResponse(_ResponseModel):
    id: int
    locality_id: int
    name: str
    level: str
    kind: str
    origin: str
    confidence: float | None = None
    # Camino completo hasta el nodo, del país hacia abajo, incluyéndolo.
    breadcrumb: list[LocalityBreadcrumb] = []


class LocalityPayload(BaseModel):
    """Alta de un lugar en el catálogo (municipio creado por ley, etc.)."""

    name: str
    level: str
    parent_id: int | None = None


class LocalityUpdatePayload(BaseModel):
    name: str | None = None
    is_active: bool | None = None


# --- Documentalistas ---------------------------------------------------------------
# Espejo de USER_ROLES en db/models.py. Se repite porque la capa HTTP valida en
# el borde: un rol inválido debe dar 422, no un dato inconsistente en la tabla.
DOCUMENTALIST_ROLE_VALUES = ("admin", "documentalista")


class DocumentalistResponse(_ResponseModel):
    """Nunca incluye `password_hash`: exponerlo convertiría un listado de
    lectura en un ataque offline contra las contraseñas."""

    id: int
    username: str
    display_name: str
    first_name: str = ""
    last_name: str = ""
    role: str
    is_active: bool
    created_at: datetime


class DocumentalistPayload(BaseModel):
    """Alta de un usuario.

    Sin contraseña: el servidor genera un PIN de 4 dígitos y la persona elige
    su clave al entrar. Sin `username` tampoco: se deriva del nombre (inicial +
    4 primeras del apellido), y ante un choque recibe un número.
    """

    first_name: str
    last_name: str
    role: str = "documentalista"


class DocumentalistCreated(DocumentalistResponse):
    """Respuesta del alta. Es la ÚNICA vez que el PIN viaja en claro: no se
    guarda descifrable en ninguna parte, así que si se pierde hay que
    regenerarlo."""

    pin: str


class DocumentalistUpdatePayload(BaseModel):
    display_name: str | None = None
    password: str | None = None
    role: str | None = None
    is_active: bool | None = None


class ExportRequest(BaseModel):
    """Reportes a incluir en el documento, en el orden en que se envían."""

    article_ids: list[int]


class DocumentalistKpiRow(_ResponseModel):
    """Trabajo de un documentalista en el rango consultado.

    Mide volumen, no calidad: la «tasa de corrección sobre lo que propuso el
    modelo» que pide R20 necesita auditoría campo a campo, y hoy re-analizar
    sobrescribe la fila del artículo sin dejar rastro.
    """

    documentalist_id: int
    display_name: str
    articles: int
    # Fechas sin hora, como `articles.analyzed_on`.
    first_on: date | None = None
    last_on: date | None = None
    # Días DISTINTOS con al menos un reporte: tres reportes en un día son un día
    # de trabajo, no tres.
    active_days: int
