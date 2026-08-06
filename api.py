"""API REST de Odin (FastAPI).

Flujo en dos pasos:
  1. POST /api/analyze   — si la URL ya estaba guardada, devuelve `200` con
     ese registro directamente (already_saved=true). Si es nueva, encola el
     trabajo (descarga con trafilatura + NLP, §3.1 de task.md) y devuelve
     `202` + `job_id`; GET /api/jobs/{job_id} da el estado/resultado. NO
     guarda: es una vista previa para revisar/corregir en el frontend antes
     de persistir.
  2. POST /api/articles  — recibe el resultado (posiblemente editado por el
     usuario) y lo guarda.

CRUD de siglas: GET/POST /api/aliases, PUT/DELETE /api/aliases/{id}.

Rectificación/borrado (§8.2 de task.md — datos personales y perfilado):
  PUT/DELETE /api/articles/{id}, PUT/DELETE /api/entities/{id}.

Uso:
  uvicorn api:app --reload --port 8000
"""
from __future__ import annotations

import json
import math
import time
import uuid
from contextlib import asynccontextmanager
from datetime import UTC, datetime, timedelta
from typing import Literal

import requests
import trafilatura
from fastapi import BackgroundTasks, Depends, FastAPI, HTTPException, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response
from prometheus_client import CONTENT_TYPE_LATEST, generate_latest
from pydantic import BaseModel, ConfigDict, Field, ValidationError
from sqlalchemy import ColumnElement, and_, func, or_, select, text
from sqlalchemy.orm import selectinload

import auth
import db.aliases as alias_store
import db.canonical_entities as canonical_entity_store
import url_guard
from analysis import LocalAnalyzer
from analysis.base import ANALYSIS_SCHEMA_VERSION, Analyzer
from analysis.canonicalize import canonicalize_entities, canonicalize_result, match_actor_name
from analysis.local_analyzer import sentence_mentions_venue_word
from analysis.text_norm import accent_insensitive_regex as _accent_insensitive_regex
from analysis.text_norm import norm_key as _norm_key
from config import settings
from db.models import AnalyzeJob, Article, CanonicalEntity, CrawlRun, Entity, EntityAlias, ScrapeJob
from db.session import get_session, init_db
from observability import (
    HTTP_REQUEST_DURATION_SECONDS,
    HTTP_REQUESTS_TOTAL,
    configure_logging,
    correlation_scope,
    get_logger,
    init_sentry,
)
from observability import (
    registry as metrics_registry,
)
from scrape_jobs import has_active_scrape_job, run_scrape_job
from scrapers.base import BaseScraper, _parse_date
from url_guard import UrlNotAllowed

configure_logging()
init_sentry()
log = get_logger("odin.api")


@asynccontextmanager
async def _lifespan(app: FastAPI):
    """Crea tablas y carga el catálogo semilla al arrancar."""
    try:
        init_db()
        n = alias_store.load_seed()
        if n:
            log.info("seed_catalog_loaded", aliases=n)
    except Exception as exc:
        log.warning("seed_catalog_load_failed", error=str(exc))
    yield


app = FastAPI(title="Odin API", lifespan=_lifespan)

app.include_router(auth.router)


# Rutas parametrizadas (`/api/articles/{article_id}`) colapsan a su plantilla
# para que las métricas no exploten en cardinalidad por cada ID distinto.
def _route_template(request: Request) -> str:
    route = request.scope.get("route")
    return route.path if route is not None else request.url.path


@app.middleware("http")
async def _observability_middleware(request: Request, call_next):
    """Correlation ID + logs estructurados + métricas de latencia/error por
    endpoint (§7.1 de task.md)."""
    with correlation_scope(request.headers.get("x-correlation-id")) as correlation_id:
        started = time.perf_counter()
        try:
            response = await call_next(request)
        except Exception:
            duration = time.perf_counter() - started
            path = _route_template(request)
            HTTP_REQUEST_DURATION_SECONDS.labels(method=request.method, path=path).observe(
                duration
            )
            HTTP_REQUESTS_TOTAL.labels(
                method=request.method, path=path, status_code="500"
            ).inc()
            log.exception(
                "http_request_failed",
                method=request.method,
                path=path,
                duration_seconds=round(duration, 4),
            )
            raise
        duration = time.perf_counter() - started
        path = _route_template(request)
        HTTP_REQUEST_DURATION_SECONDS.labels(method=request.method, path=path).observe(duration)
        HTTP_REQUESTS_TOTAL.labels(
            method=request.method, path=path, status_code=str(response.status_code)
        ).inc()
        log.info(
            "http_request_finished",
            method=request.method,
            path=path,
            status_code=response.status_code,
            duration_seconds=round(duration, 4),
        )
        response.headers["X-Correlation-ID"] = correlation_id
        return response

# Orígenes explícitos (ODIN_CORS_ORIGINS). Nada de "*": la API acepta escrituras
# autenticadas y no tiene por qué ser invocable desde cualquier página.
app.add_middleware(
    CORSMiddleware,
    allow_origins=list(settings.cors_origins),
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type"],
)

# El motor lo decide ODIN_ANALYZER, NUNCA la presencia de GEMINI_API_KEY: tener
# la llave en el .env no es lo mismo que querer pagar por cada análisis. Mismo
# criterio que el CLI (main.py --analyzer). Ver CLAUDE.md.
_IS_GEMINI_ANALYZER = settings.analyzer == "gemini"

# Carga perezosa: los modelos se inicializan aquí. El tipo declarado es el
# puerto (`Analyzer`), no la implementación: es lo que permite intercambiarlas.
_analyzer: Analyzer
if _IS_GEMINI_ANALYZER:
    # Import perezoso: sin esto, correr en modo local exigiría google-genai.
    from analysis.gemini_analyzer import GeminiAnalyzer

    log.warning(
        "ODIN_ANALYZER=gemini — cada análisis es una llamada FACTURADA a la API "
        "de Gemini. Usa ODIN_ANALYZER=local para el motor gratuito."
    )
    _analyzer = GeminiAnalyzer()
elif settings.analyzer == "groq+gemini":
    from analysis.fallback_analyzer import GroqWithGeminiFallback

    log.warning(
        "ODIN_ANALYZER=groq+gemini — GroqAnalyzer (gratis) primero; si falla "
        "(rate limit, respuesta truncada, error de red) reintenta con Gemini, "
        "que es una llamada FACTURADA. El linaje guardado dice cuál respondió."
    )
    _analyzer = GroqWithGeminiFallback()
elif settings.analyzer == "groq":
    # Import perezoso: sin esto, correr en modo local exigiría el paquete groq.
    from analysis.groq_analyzer import GroqAnalyzer

    log.info("ODIN_ANALYZER=groq — GroqAnalyzer (free tier, rate-limited)")
    _analyzer = GroqAnalyzer()
elif settings.analyzer == "hybrid":
    from analysis.groq_analyzer import HybridAnalyzer

    log.info(
        "ODIN_ANALYZER=hybrid — LocalAnalyzer (spaCy + pysentimiento) + Groq "
        "solo para el encuadre (free tier, rate-limited)"
    )
    _analyzer = HybridAnalyzer()
else:
    log.info("ODIN_ANALYZER=local — LocalAnalyzer (spaCy + pysentimiento), sin costo")
    _analyzer = LocalAnalyzer()

if settings.gemini_arbiter and not _IS_GEMINI_ANALYZER:
    log.warning(
        "ODIN_GEMINI_ARBITER activo — se hará una llamada FACTURADA extra a "
        "Gemini en los análisis con personas ambiguas."
    )
_extractor = BaseScraper()


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


def _fetch_and_extract(url: str):
    # La URL viene del usuario: se descarga con las protecciones de url_guard
    # (allowlist de dominios, bloqueo de IPs internas, tope de tamaño), no con
    # el fetch del scraper, que confía en las URLs de sus propios sitemaps.
    try:
        html = url_guard.fetch_html(url, session=_extractor.session)
    except UrlNotAllowed as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except requests.RequestException as exc:
        log.warning("fetch_failed", url=url, error=str(exc))
        raise HTTPException(status_code=422, detail="No se pudo descargar la URL.") from exc

    if not html:
        raise HTTPException(status_code=422, detail="No se pudo descargar la URL.")

    data = trafilatura.extract(
        html,
        output_format="json",
        with_metadata=True,
        include_comments=False,
        url=url,
    )
    if not data:
        raise HTTPException(status_code=422, detail="No se pudo extraer el artículo de esa URL.")

    meta = json.loads(data)
    body = (meta.get("text") or "").strip()
    title = (meta.get("title") or "").strip()
    if not body or not title:
        raise HTTPException(status_code=422, detail="La página no parece un artículo (falta título o cuerpo).")

    authors = meta.get("author") or None
    section = None
    cats = meta.get("categories")
    if cats:
        section = cats[0] if isinstance(cats, list) else str(cats)
    published_at = _parse_date(meta.get("date"))

    return {
        "title": title,
        "body": body,
        "authors": authors,
        "section": section,
        "published_at": published_at,
        "sitename": meta.get("sitename"),
    }


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


def _run_analyze_job(job_id: str, url: str) -> None:
    """Cuerpo del trabajo encolado por POST /api/analyze: descarga, analiza y
    guarda el resultado en la fila `AnalyzeJob`. Corre en el threadpool de
    `BackgroundTasks`, fuera del ciclo request/response — cualquier excepción
    de aquí NUNCA debe propagarse (no hay a quién devolvérsela), se guarda
    como `error` en el job para que el polling la muestre."""
    session = get_session()
    try:
        job = session.get(AnalyzeJob, job_id)
        if job is None:  # no debería pasar
            return
        job.status = "running"
        job.started_at = datetime.now(UTC)
        session.commit()

        try:
            extracted = _fetch_and_extract(url)
            result = _analyze_safely(extracted["title"], extracted["body"])
            _arbitrate_ambiguous_persons(result)
            canonicalize_result(result)

            detail = ArticleDetail(
                already_saved=False,
                source=extracted.get("sitename") or "manual",
                url=url,
                title=extracted["title"],
                authors=extracted["authors"],
                section=extracted["section"],
                published_at=extracted["published_at"],
                body=extracted["body"],
                main_topic=result.main_topic,
                topic_keywords=", ".join(result.topic_keywords) or None,
                overall_sentiment=result.overall_sentiment,
                sentiment_score=result.sentiment_score,
                framing=result.framing,
                headline_intent=result.headline_intent,
                lead_orientation=result.lead_orientation,
                dominant_actor=result.dominant_actor,
                source_quality=result.source_quality,
                has_hard_data=result.has_hard_data,
                blamed_actor=result.blamed_actor,
                credited_actor=result.credited_actor,
                sentiment_basis=result.sentiment_basis,
                facts_sentiment=result.facts_sentiment,
                quoted_sentiment=result.quoted_sentiment,
                media_stance=result.media_stance,
                media_stance_evidence=result.media_stance_evidence,
                overall_sentiment_reason=result.overall_sentiment_reason,
                content_flags=", ".join(result.content_flags) or None,
                analyzer_name=_analyzer.name,
                analyzer_model=_analyzer.model,
                analyzer_version=_analyzer.version,
                analysis_schema_version=ANALYSIS_SCHEMA_VERSION,
                analyzed_at=datetime.now(UTC),
                entities=[EntityMention.model_validate(e) for e in result.entities],
            )
            job.status = "done"
            job.result_json = detail.model_dump_json()
        except HTTPException as exc:
            job.status = "failed"
            job.error = str(exc.detail)
        except Exception as exc:
            log.exception("analyze_job_failed", job_id=job_id, url=url)
            job.status = "failed"
            job.error = str(exc)
        job.finished_at = datetime.now(UTC)
        session.commit()
    finally:
        session.close()


@app.post(
    "/api/analyze",
    dependencies=[Depends(auth.require_auth)],
    response_model=ArticleDetail | AnalyzeAccepted,
    status_code=200,
    responses={202: {"model": AnalyzeAccepted}},
)
def analyze(req: AnalyzeRequest, background_tasks: BackgroundTasks, response: Response):
    """Encola el análisis de la URL (§3.1 de task.md): la descarga y el NLP
    corren en segundo plano en vez de bloquear el request hasta 60s. Si la
    URL ya estaba guardada, devuelve `200` con el registro directamente (no
    hay nada que encolar). Si es nueva, devuelve `202` + `job_id`; el cliente
    consulta el resultado con GET /api/jobs/{job_id}."""
    # Se valida antes de tocar la BD: una URL que no pasa el guard no debe
    # producir ninguna respuesta distinguible según lo que haya guardado.
    try:
        url = url_guard.validate_url(req.url)
    except UrlNotAllowed as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    session = get_session()
    try:
        existing = session.scalar(select(Article).where(Article.url == url))
        if existing:
            return _serialize(existing, already_saved=True)

        job = AnalyzeJob(id=str(uuid.uuid4()), url=url)
        session.add(job)
        session.commit()
        job_id = job.id
    finally:
        session.close()

    background_tasks.add_task(_run_analyze_job, job_id, url)
    response.status_code = 202
    return AnalyzeAccepted(job_id=job_id)


@app.get(
    "/api/jobs/{job_id}",
    dependencies=[Depends(auth.require_auth)],
    response_model=JobResponse,
)
def get_job(job_id: str):
    """Estado/resultado de un job de POST /api/analyze."""
    session = get_session()
    try:
        job = session.get(AnalyzeJob, job_id)
        if job is None:
            raise HTTPException(status_code=404, detail="Job no encontrado.")
        result = ArticleDetail.model_validate_json(job.result_json) if job.result_json else None
        return JobResponse(job_id=job.id, status=job.status, error=job.error, result=result)
    finally:
        session.close()


# ── Listado y filtros de reportes ────────────────────────────────────────────

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


def _accent_insensitive_contains(column, value: str) -> ColumnElement[bool]:
    """Como `column.ilike(f"%{value}%")` pero sin importar acentos en NINGUNO
    de los dos lados: "matias" encuentra "Matías" y viceversa. Usa el operador
    `~*` (regex case-insensitive nativo de Postgres) con el patrón de
    `accent_insensitive_regex` — no requiere la extensión `unaccent` ni traer
    filas a Python para filtrarlas (ver analysis/text_norm.py). Se usa
    `regexp_match` (portable) en vez de `.op("~*")` directamente: SQLAlchemy
    lo traduce a `~*` en Postgres y a la función `REGEXP` en SQLite, que los
    tests registran en tests/conftest.py."""
    pattern = _accent_insensitive_regex(value)
    return column.regexp_match(pattern, flags="i")


def _apply_article_filters(
    stmt,
    *,
    source: list[str] | None,
    sentiment: str | None,
    framing: str | None,
    headline_intent: str | None,
    lead_orientation: str | None,
    source_quality: str | None,
    has_hard_data: bool | None,
    date_from: str | None,
    date_to: str | None,
    q: str | None,
    entity: str | None,
):
    conditions: list[ColumnElement[bool]] = []
    if source:
        conditions.append(Article.source.in_(source))
    if sentiment:
        conditions.append(Article.overall_sentiment == sentiment)
    if framing:
        conditions.append(Article.framing == framing)
    if headline_intent:
        conditions.append(Article.headline_intent == headline_intent)
    if lead_orientation:
        conditions.append(Article.lead_orientation == lead_orientation)
    if source_quality:
        conditions.append(Article.source_quality == source_quality)
    if has_hard_data is not None:
        conditions.append(Article.has_hard_data == has_hard_data)
    if date_from:
        parsed = _parse_date(date_from)
        if parsed:
            conditions.append(Article.published_at >= parsed)
    if date_to:
        parsed = _parse_date(date_to)
        if parsed:
            # inclusivo: hasta el final del día indicado
            conditions.append(Article.published_at < parsed + timedelta(days=1))
    if q:
        conditions.append(
            or_(
                _accent_insensitive_contains(Article.title, q),
                _accent_insensitive_contains(Article.main_topic, q),
                _accent_insensitive_contains(Article.topic_keywords, q),
            )
        )
    if entity:
        stmt = stmt.join(Entity, Entity.article_id == Article.id).where(
            _accent_insensitive_contains(Entity.name, entity)
        )
    if conditions:
        stmt = stmt.where(and_(*conditions))
    return stmt


def _serialize_summary(article: Article) -> ArticleSummary:
    return ArticleSummary(
        id=article.id,
        source=article.source,
        url=article.url,
        title=article.title,
        section=article.section,
        published_at=article.published_at,
        scraped_at=article.scraped_at,
        main_topic=article.main_topic,
        overall_sentiment=article.overall_sentiment,
        sentiment_score=article.sentiment_score,
        framing=article.framing,
        headline_intent=article.headline_intent,
        lead_orientation=article.lead_orientation,
        source_quality=article.source_quality,
        has_hard_data=article.has_hard_data,
        dominant_actor=article.dominant_actor.name if article.dominant_actor else None,
        blamed_actor=article.blamed_actor.name if article.blamed_actor else None,
        credited_actor=article.credited_actor.name if article.credited_actor else None,
        entity_count=len(article.entities),
    )


@app.get("/api/articles", response_model=ArticleListResponse)
def list_articles(
    q: str | None = None,
    source: list[str] | None = Query(None),
    sentiment: str | None = None,
    framing: str | None = None,
    headline_intent: str | None = None,
    lead_orientation: str | None = None,
    source_quality: str | None = None,
    has_hard_data: bool | None = None,
    entity: str | None = None,
    date_from: str | None = None,
    date_to: str | None = None,
    sort: str = "recent",
    limit: int = 20,
    offset: int = 0,
):
    """Lista reportes guardados con filtros combinables. Devuelve resúmenes
    (sin cuerpo ni entidades detalladas); usa GET /api/articles/{id} para el
    reporte completo."""
    limit = max(1, min(limit, 100))
    offset = max(0, offset)

    session = get_session()
    try:
        base = _apply_article_filters(
            select(Article),
            source=source,
            sentiment=sentiment,
            framing=framing,
            headline_intent=headline_intent,
            lead_orientation=lead_orientation,
            source_quality=source_quality,
            has_hard_data=has_hard_data,
            date_from=date_from,
            date_to=date_to,
            q=q,
            entity=entity,
        )
        if entity:
            base = base.distinct()

        total = session.scalar(select(func.count()).select_from(base.subquery())) or 0

        order_col = Article.published_at.asc() if sort == "oldest" else Article.published_at.desc()
        # selectinload: una query con IN(...) por relación para toda la página,
        # en vez de lazy-load por artículo (N+1) al pedir `len(article.entities)`
        # y `article.dominant_actor.name` (+blamed/credited) en _serialize_summary.
        rows = session.scalars(
            base.options(
                selectinload(Article.entities),
                selectinload(Article.dominant_actor),
                selectinload(Article.blamed_actor),
                selectinload(Article.credited_actor),
            )
            .order_by(order_col, Article.id.desc())
            .limit(limit)
            .offset(offset)
        ).all()

        return ArticleListResponse(
            total=total,
            limit=limit,
            offset=offset,
            items=[_serialize_summary(a) for a in rows],
        )
    finally:
        session.close()


@app.get("/api/articles/filters", response_model=ArticleFiltersResponse)
def article_filters():
    """Valores disponibles para poblar los selectores de filtro del frontend.
    Fuentes y secciones son dinámicas (dependen de lo ya guardado); el resto
    de campos de encuadre son enumeraciones fijas del análisis."""
    session = get_session()
    try:
        sources = [
            s
            for s in session.scalars(select(Article.source).distinct().order_by(Article.source)).all()
            if s
        ]
        sections = [
            s
            for s in session.scalars(
                select(Article.section).distinct().where(Article.section.is_not(None)).order_by(Article.section)
            ).all()
            if s
        ]
        return ArticleFiltersResponse(
            sources=sources,
            sections=sections,
            sentiments=list(SENTIMENT_VALUES),
            framing=list(FRAMING_VALUES),
            headline_intent=list(HEADLINE_INTENT_VALUES),
            lead_orientation=list(LEAD_ORIENTATION_VALUES),
            source_quality=list(SOURCE_QUALITY_VALUES),
        )
    finally:
        session.close()


@app.get("/api/articles/{article_id}", response_model=ArticleDetail)
def get_article(article_id: int):
    """Reporte completo (con entidades) de un artículo ya guardado."""
    session = get_session()
    try:
        article = session.scalar(select(Article).where(Article.id == article_id))
        if not article:
            raise HTTPException(status_code=404, detail="Reporte no encontrado.")
        return _serialize(article, already_saved=True)
    except HTTPException:
        raise
    finally:
        session.close()


_ACTOR_FIELDS = {
    "dominant_actor": "dominant_actor_id",
    "blamed_actor": "blamed_actor_id",
    "credited_actor": "credited_actor_id",
}


def _resolve_actor_field(article: Article, name: str | None) -> int | None:
    """Resuelve el string de actor enviado en la rectificación a la
    `CanonicalEntity.id` de una mención YA vinculada a este artículo — igual
    criterio conservador que `resolve_actor_id` al guardar (§4.1): si el
    nombre no coincide con ninguna entidad del propio artículo, no se crea una
    fila nueva ni se adivina, queda en NULL."""
    if not name:
        return None
    nkey = _norm_key(name)
    for ent in article.entities:
        if ent.canonical_entity and _norm_key(ent.canonical_entity.name) == nkey:
            return ent.canonical_entity_id
        if _norm_key(ent.name) == nkey:
            return ent.canonical_entity_id
    return None


@app.put(
    "/api/articles/{article_id}",
    dependencies=[Depends(auth.require_auth)],
    response_model=ArticleDetail,
)
def update_article(article_id: int, payload: ArticleUpdatePayload):
    """Rectifica el análisis de un artículo ya guardado (§8.2): tema, encuadre,
    sentimiento, actores señalados... Solo toca los campos enviados. No permite
    corregir `title`/`body`/`url` porque eso es lo que decía la fuente, no un
    juicio del sistema — si el scrape en sí está mal, hay que borrar y volver a
    analizar."""
    session = get_session()
    try:
        article = session.scalar(select(Article).where(Article.id == article_id))
        if not article:
            raise HTTPException(status_code=404, detail="Reporte no encontrado.")
        data = payload.model_dump(exclude_unset=True)
        for field, value in data.items():
            if field in _ACTOR_FIELDS:
                setattr(article, _ACTOR_FIELDS[field], _resolve_actor_field(article, value))
            else:
                setattr(article, field, value)
        session.commit()
        return _serialize(article, already_saved=True)
    except HTTPException:
        raise
    except Exception:
        session.rollback()
        log.exception("article_rectification_failed", article_id=article_id)
        raise HTTPException(status_code=500, detail="Error interno rectificando el artículo.") from None
    finally:
        session.close()


@app.delete(
    "/api/articles/{article_id}", status_code=204, dependencies=[Depends(auth.require_auth)]
)
def delete_article(article_id: int):
    """Borra permanentemente un artículo y sus menciones (§8.2): no hay
    archivado ni papelera — es el procedimiento de borrado que el cliente
    puede exigir sobre su propio contenido o el de una persona nombrada."""
    session = get_session()
    try:
        article = session.scalar(select(Article).where(Article.id == article_id))
        if not article:
            raise HTTPException(status_code=404, detail="Reporte no encontrado.")
        session.delete(article)
        session.commit()
    except HTTPException:
        raise
    except Exception:
        session.rollback()
        log.exception("article_deletion_failed", article_id=article_id)
        raise HTTPException(status_code=500, detail="Error interno borrando el artículo.") from None
    finally:
        session.close()


# ── Menciones de entidad (por artículo) ──────────────────────────────────────


@app.put(
    "/api/entities/{entity_id}",
    dependencies=[Depends(auth.require_auth)],
    response_model=EntityMention,
)
def update_entity(entity_id: int, payload: EntityUpdatePayload):
    """Rectifica una mención puntual (§8.2): nombre mal extraído, sentimiento
    mal inferido... sin tener que borrar y re-analizar todo el artículo.
    Devuelve 409 si el cambio choca con otra mención ya existente en el mismo
    artículo (mismo nombre + tipo)."""
    session = get_session()
    try:
        entity = session.scalar(select(Entity).where(Entity.id == entity_id))
        if not entity:
            raise HTTPException(status_code=404, detail="Mención no encontrada.")
        data = payload.model_dump(exclude_unset=True)
        if data.get("name"):
            data["name"] = data["name"].strip()
        new_name = data.get("name", entity.name)
        new_type = data.get("type", entity.type)
        if (new_name, new_type) != (entity.name, entity.type):
            clash = session.scalar(
                select(Entity).where(
                    Entity.article_id == entity.article_id,
                    Entity.name == new_name,
                    Entity.type == new_type,
                    Entity.id != entity_id,
                )
            )
            if clash:
                raise HTTPException(
                    status_code=409,
                    detail=f"Ya hay una mención de '{new_name}' ({new_type}) en este artículo.",
                )
        for field, value in data.items():
            setattr(entity, field, value)
        session.commit()
        return EntityMention.model_validate(entity)
    except HTTPException:
        raise
    except Exception:
        session.rollback()
        log.exception("entity_rectification_failed", entity_id=entity_id)
        raise HTTPException(status_code=500, detail="Error interno rectificando la mención.") from None
    finally:
        session.close()


@app.delete(
    "/api/entities/{entity_id}", status_code=204, dependencies=[Depends(auth.require_auth)]
)
def delete_entity(entity_id: int):
    """Borra una mención puntual (§8.2): redacta el juicio sobre una persona en
    UN artículo sin borrar el artículo completo."""
    session = get_session()
    try:
        entity = session.scalar(select(Entity).where(Entity.id == entity_id))
        if not entity:
            raise HTTPException(status_code=404, detail="Mención no encontrada.")
        session.delete(entity)
        session.commit()
    except HTTPException:
        raise
    except Exception:
        session.rollback()
        log.exception("entity_deletion_failed", entity_id=entity_id)
        raise HTTPException(status_code=500, detail="Error interno borrando la mención.") from None
    finally:
        session.close()


# ── CRUD de siglas ─────────────────────────────────────────────────────────────


@app.get("/api/aliases", response_model=list[EntityAliasResponse])
def list_aliases(q: str | None = None, limit: int = 500, offset: int = 0):
    """Devuelve alias activos e inactivos, filtrados en SQL (?q=) y paginados.
    `limit` por defecto es generoso (500, tope 1000) para no cambiar el
    comportamiento actual del frontend, que espera la lista completa."""
    limit = max(1, min(limit, 1000))
    offset = max(0, offset)
    session = get_session()
    try:
        stmt = select(EntityAlias)
        if q:
            stmt = stmt.where(
                or_(
                    _accent_insensitive_contains(EntityAlias.alias, q),
                    _accent_insensitive_contains(EntityAlias.canonical_name, q),
                )
            )
        rows = session.scalars(
            stmt.order_by(EntityAlias.alias).limit(limit).offset(offset)
        ).all()
        return [EntityAliasResponse.model_validate(r) for r in rows]
    finally:
        session.close()


@app.post(
    "/api/aliases",
    status_code=201,
    dependencies=[Depends(auth.require_auth)],
    response_model=EntityAliasResponse,
)
def create_alias(payload: AliasPayload):
    """Crea un nuevo alias. Devuelve 409 si la sigla ya existe (mismo tipo)."""
    alias_key = alias_store.normalize_key(payload.alias)
    session = get_session()
    try:
        existing = session.scalar(
            select(EntityAlias).where(
                EntityAlias.alias_key == alias_key,
                EntityAlias.type == payload.type,
            )
        )
        if existing:
            raise HTTPException(
                status_code=409,
                detail=f"La sigla '{payload.alias}' ya existe para el tipo '{payload.type}'.",
            )
        row = EntityAlias(
            alias=payload.alias.strip(),
            alias_key=alias_key,
            canonical_name=payload.canonical_name.strip(),
            type=payload.type,
            is_active=payload.is_active,
        )
        session.add(row)
        session.commit()
        alias_store.invalidate_cache()
        return EntityAliasResponse.model_validate(row)
    except HTTPException:
        raise
    except Exception:
        session.rollback()
        log.exception("alias_creation_failed")
        raise HTTPException(status_code=500, detail="Error interno creando el alias.") from None
    finally:
        session.close()


@app.put(
    "/api/aliases/{alias_id}",
    dependencies=[Depends(auth.require_auth)],
    response_model=EntityAliasResponse,
)
def update_alias(alias_id: int, payload: AliasUpdatePayload):
    """Actualiza parcialmente un alias (nombre canónico, estado activo/inactivo...)."""
    session = get_session()
    try:
        row = session.scalar(select(EntityAlias).where(EntityAlias.id == alias_id))
        if not row:
            raise HTTPException(status_code=404, detail="Alias no encontrado.")
        if payload.alias is not None:
            row.alias = payload.alias.strip()
            row.alias_key = alias_store.normalize_key(payload.alias)
        if payload.canonical_name is not None:
            row.canonical_name = payload.canonical_name.strip()
        if payload.type is not None:
            row.type = payload.type
        if payload.is_active is not None:
            row.is_active = payload.is_active
        session.commit()
        alias_store.invalidate_cache()
        return EntityAliasResponse.model_validate(row)
    except HTTPException:
        raise
    except Exception:
        session.rollback()
        log.exception("alias_update_failed", alias_id=alias_id)
        raise HTTPException(status_code=500, detail="Error interno actualizando el alias.") from None
    finally:
        session.close()


@app.delete(
    "/api/aliases/{alias_id}", status_code=204, dependencies=[Depends(auth.require_auth)]
)
def delete_alias(alias_id: int):
    """Elimina permanentemente un alias."""
    session = get_session()
    try:
        row = session.scalar(select(EntityAlias).where(EntityAlias.id == alias_id))
        if not row:
            raise HTTPException(status_code=404, detail="Alias no encontrado.")
        session.delete(row)
        session.commit()
        alias_store.invalidate_cache()
    except HTTPException:
        raise
    except Exception:
        session.rollback()
        log.exception("alias_deletion_failed", alias_id=alias_id)
        raise HTTPException(status_code=500, detail="Error interno eliminando el alias.") from None
    finally:
        session.close()


# ── Entidades canónicas (dimensión + fusión) ─────────────────────────────────


def _serialize_canonical_entity(
    row: CanonicalEntity, article_count: int, total_mentions: int
) -> CanonicalEntityResponse:
    return CanonicalEntityResponse.model_validate(row).model_copy(
        update={"article_count": article_count, "total_mentions": total_mentions}
    )


def _canonical_entity_counts(session, entity_id: int) -> tuple[int, int]:
    article_count = session.scalar(
        select(func.count(func.distinct(Entity.article_id))).where(
            Entity.canonical_entity_id == entity_id
        )
    ) or 0
    total_mentions = session.scalar(
        select(func.coalesce(func.sum(Entity.mentions_count), 0)).where(
            Entity.canonical_entity_id == entity_id
        )
    ) or 0
    return article_count, total_mentions


@app.get("/api/canonical-entities", response_model=CanonicalEntityListResponse)
def list_canonical_entities(
    q: str | None = None,
    type_: str | None = Query(None, alias="type", pattern="^(ORG|PERSON)$"),
    limit: int = 50,
    offset: int = 0,
):
    """Lista entidades canónicas (la dimensión "persona/organización real",
    no menciones por artículo) con cuántos artículos y menciones acumula cada
    una. Puede haber más de una fila para la misma figura real si se creó
    antes de que la heurística de nombre único las uniera ("Abinader" y
    "Luis Abinader" por separado) — usa POST .../merge para fusionarlas."""
    limit = max(1, min(limit, 200))
    offset = max(0, offset)
    session = get_session()
    try:
        article_count_col = func.count(func.distinct(Entity.article_id)).label("article_count")
        total_mentions_col = func.coalesce(func.sum(Entity.mentions_count), 0).label("total_mentions")

        stmt = (
            select(CanonicalEntity, article_count_col, total_mentions_col)
            .outerjoin(Entity, Entity.canonical_entity_id == CanonicalEntity.id)
            .group_by(CanonicalEntity.id)
        )
        if type_:
            stmt = stmt.where(CanonicalEntity.type == type_)
        if q:
            stmt = stmt.where(_accent_insensitive_contains(CanonicalEntity.name, q))

        total = session.scalar(select(func.count()).select_from(stmt.subquery())) or 0

        rows = session.execute(
            stmt.order_by(article_count_col.desc(), CanonicalEntity.name)
            .limit(limit)
            .offset(offset)
        ).all()

        return CanonicalEntityListResponse(
            total=total,
            limit=limit,
            offset=offset,
            items=[
                _serialize_canonical_entity(row, article_count, total_mentions)
                for row, article_count, total_mentions in rows
            ],
        )
    finally:
        session.close()


@app.get("/api/canonical-entities/{entity_id}", response_model=CanonicalEntityDetailResponse)
def get_canonical_entity(entity_id: int):
    """Detalle de una entidad canónica: sus datos y los artículos donde
    aparece vinculada (vía Entity.canonical_entity_id), más recientes primero.
    Esta es la respuesta confiable a "¿cuántos artículos hablan de esta
    persona?" — agrupa por identidad real, no por string de nombre."""
    session = get_session()
    try:
        row = session.scalar(select(CanonicalEntity).where(CanonicalEntity.id == entity_id))
        if not row:
            raise HTTPException(status_code=404, detail="Entidad canónica no encontrada.")

        mention_rows = session.execute(
            select(Entity, Article)
            .join(Article, Article.id == Entity.article_id)
            .where(Entity.canonical_entity_id == entity_id)
            .order_by(Article.published_at.desc(), Article.id.desc())
            .limit(200)
        ).all()
        article_count, total_mentions = _canonical_entity_counts(session, entity_id)
        summary = _serialize_canonical_entity(row, article_count, total_mentions)

        return CanonicalEntityDetailResponse(
            **summary.model_dump(),
            articles=[
                CanonicalEntityArticleMention(
                    article_id=article.id,
                    title=article.title,
                    url=article.url,
                    source=article.source,
                    published_at=article.published_at,
                    sentiment_toward=mention.sentiment_toward,
                    mentions_count=mention.mentions_count,
                )
                for mention, article in mention_rows
            ],
        )
    except HTTPException:
        raise
    finally:
        session.close()


@app.put(
    "/api/canonical-entities/{entity_id}",
    dependencies=[Depends(auth.require_auth)],
    response_model=CanonicalEntityResponse,
)
def update_canonical_entity(entity_id: int, payload: CanonicalEntityUpdatePayload):
    """Renombra y/o describe una entidad canónica. El nombre nuevo entra a
    `known_person_fullname_map()` en el siguiente análisis (ver
    analysis/canonicalize.py): la corrección se propaga hacia adelante, no
    solo en los reportes ya guardados. Devuelve 409 si el nombre nuevo choca
    con otra entidad canónica ya existente del mismo tipo — en ese caso hace
    falta fusionar (POST .../merge), no renombrar."""
    session = get_session()
    try:
        row = session.scalar(select(CanonicalEntity).where(CanonicalEntity.id == entity_id))
        if not row:
            raise HTTPException(status_code=404, detail="Entidad canónica no encontrada.")
        if payload.name is not None:
            new_name = payload.name.strip()
            clash = session.scalar(
                select(CanonicalEntity).where(
                    CanonicalEntity.name == new_name,
                    CanonicalEntity.type == row.type,
                    CanonicalEntity.id != entity_id,
                )
            )
            if clash:
                raise HTTPException(
                    status_code=409,
                    detail=(
                        f"Ya existe una entidad canónica '{new_name}' ({row.type}); "
                        "usa fusionar en vez de renombrar."
                    ),
                )
            row.name = new_name
        if payload.description is not None:
            row.description = payload.description.strip() or None
        session.commit()
        article_count, total_mentions = _canonical_entity_counts(session, entity_id)
        return _serialize_canonical_entity(row, article_count, total_mentions)
    except HTTPException:
        raise
    except Exception:
        session.rollback()
        log.exception("canonical_entity_update_failed", entity_id=entity_id)
        raise HTTPException(
            status_code=500, detail="Error interno actualizando la entidad canónica."
        ) from None
    finally:
        session.close()


@app.post(
    "/api/canonical-entities/{entity_id}/merge",
    dependencies=[Depends(auth.require_auth)],
    response_model=CanonicalEntityResponse,
)
def merge_canonical_entities(entity_id: int, payload: CanonicalEntityMergePayload):
    """Fusiona `source_id` DENTRO de `entity_id`: reasigna todas las menciones
    (pasadas) que apuntaban a `source_id` y la borra. Es la corrección manual
    que el pipeline no puede inferir solo (dos nombres que en realidad son la
    misma figura, creados como filas separadas)."""
    session = get_session()
    try:
        target = session.get(CanonicalEntity, entity_id)
        source = session.get(CanonicalEntity, payload.source_id)
        if not target or not source:
            raise HTTPException(status_code=404, detail="Entidad canónica no encontrada.")
        try:
            canonical_entity_store.merge(session, entity_id, payload.source_id)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        session.commit()
        article_count, total_mentions = _canonical_entity_counts(session, entity_id)
        return _serialize_canonical_entity(target, article_count, total_mentions)
    except HTTPException:
        raise
    except Exception:
        session.rollback()
        log.exception(
            "canonical_entity_merge_failed", entity_id=entity_id, source_id=payload.source_id
        )
        raise HTTPException(status_code=500, detail="Error interno fusionando entidades.") from None
    finally:
        session.close()


@app.post("/api/articles", dependencies=[Depends(auth.require_auth)], response_model=ArticleDetail)
def save_article(req: SaveArticleRequest):
    """Persiste el resultado de /api/analyze, ya revisado/corregido."""
    url = req.url.strip()

    session = get_session()
    try:
        # Las tablas ya se crean en el lifespan de arranque (_lifespan); no
        # hace falta repetir init_db() (inspección de metadata + posible DDL)
        # en cada guardado.
        existing = session.scalar(select(Article).where(Article.url == url))
        if existing:
            return _serialize(existing, already_saved=True)

        # Canonicaliza también al guardar: cubre ediciones manuales del
        # frontend y unifica contra lo ya conocido en la BD.
        entities = canonicalize_entities(list(req.entities))
        article = Article(
            source=req.source,
            url=url,
            title=req.title,
            authors=req.authors,
            section=req.section,
            published_at=_parse_date(req.published_at),
            body=req.body,
            main_topic=req.main_topic,
            topic_keywords=req.topic_keywords,
            overall_sentiment=req.overall_sentiment,
            sentiment_score=req.sentiment_score,
            framing=req.framing,
            headline_intent=req.headline_intent,
            lead_orientation=req.lead_orientation,
            source_quality=req.source_quality,
            has_hard_data=req.has_hard_data,
            sentiment_basis=req.sentiment_basis,
            facts_sentiment=req.facts_sentiment,
            quoted_sentiment=req.quoted_sentiment,
            media_stance=req.media_stance,
            media_stance_evidence=req.media_stance_evidence,
            overall_sentiment_reason=req.overall_sentiment_reason,
            content_flags=req.content_flags,
            analyzer_name=_analyzer.name,
            analyzer_model=_analyzer.model,
            analyzer_version=_analyzer.version,
            analysis_schema_version=ANALYSIS_SCHEMA_VERSION,
            analyzed_at=datetime.now(UTC),
        )
        canonical_by_name: dict[str, CanonicalEntity] = {}
        for e in entities:
            canonical = canonical_entity_store.get_or_create(session, e.name, e.type)
            canonical_by_name[e.name] = canonical
            article.entities.append(
                Entity(
                    name=e.name,
                    type=e.type,
                    mentions_count=e.mentions_count,
                    sentiment_toward=e.sentiment_toward,
                    sentiment_score=e.sentiment_score,
                    context=e.context,
                    extraction_confidence=e.extraction_confidence,
                    canonical_entity=canonical,
                )
            )
        article.dominant_actor_id = canonical_entity_store.resolve_actor_id(
            match_actor_name(req.dominant_actor, entities), canonical_by_name
        )
        article.blamed_actor_id = canonical_entity_store.resolve_actor_id(
            match_actor_name(req.blamed_actor, entities), canonical_by_name
        )
        article.credited_actor_id = canonical_entity_store.resolve_actor_id(
            match_actor_name(req.credited_actor, entities), canonical_by_name
        )
        session.add(article)
        session.commit()
        return _serialize(article, already_saved=False)
    except HTTPException:
        raise
    except Exception:
        session.rollback()
        log.exception("article_save_failed", url=url)
        raise HTTPException(status_code=500, detail="Error interno guardando el artículo.") from None
    finally:
        session.close()


def _analyze_safely(title: str, body: str):
    try:
        return _analyzer.analyze(title, body)
    except RuntimeError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


def _arbitrate_ambiguous_persons(result) -> None:
    """Segundo filtro (pagado, opcional) solo para PERSON cuya oración de
    contexto menciona una palabra de lugar en algún punto — la heurística
    local ya descartó los casos claros; esto cubre lo que queda ambiguo.

    Está APAGADO por defecto: se activa con `ODIN_GEMINI_ARBITER=1`, nunca por
    tener GEMINI_API_KEY en el entorno (antes bastaba con eso y se facturaba sin
    pedirlo). También se salta si el análisis principal ya lo hizo
    GeminiAnalyzer: su prompt ya excluye lugares/homenajes y repetirlo sería
    pagar dos veces. Solo se llama desde /api/analyze, nunca desde el crawl
    (main.py/pipeline.py).

    Todos los casos ambiguos del artículo van en UNA sola llamada a Gemini."""
    if _IS_GEMINI_ANALYZER or not settings.gemini_arbiter:
        return

    ambiguous = [
        e
        for e in result.entities
        if e.type == "PERSON" and e.context and sentence_mentions_venue_word(e.context)
    ]
    if not ambiguous:
        return

    from analysis.entity_arbiter import are_person_mentions

    verdicts = are_person_mentions([(e.name, e.context) for e in ambiguous])
    dropped = {id(e) for e, keep in zip(ambiguous, verdicts, strict=True) if not keep}
    result.entities = [e for e in result.entities if id(e) not in dropped]


def _serialize(article: Article, already_saved: bool) -> ArticleDetail:
    return ArticleDetail(
        already_saved=already_saved,
        id=article.id,
        source=article.source,
        url=article.url,
        title=article.title,
        authors=article.authors,
        section=article.section,
        published_at=article.published_at,
        body=article.body,
        main_topic=article.main_topic,
        topic_keywords=article.topic_keywords,
        overall_sentiment=article.overall_sentiment,
        sentiment_score=article.sentiment_score,
        framing=article.framing,
        headline_intent=article.headline_intent,
        lead_orientation=article.lead_orientation,
        dominant_actor=article.dominant_actor.name if article.dominant_actor else None,
        source_quality=article.source_quality,
        has_hard_data=article.has_hard_data,
        blamed_actor=article.blamed_actor.name if article.blamed_actor else None,
        credited_actor=article.credited_actor.name if article.credited_actor else None,
        sentiment_basis=article.sentiment_basis,
        facts_sentiment=article.facts_sentiment,
        quoted_sentiment=article.quoted_sentiment,
        media_stance=article.media_stance,
        media_stance_evidence=article.media_stance_evidence,
        overall_sentiment_reason=article.overall_sentiment_reason,
        content_flags=article.content_flags,
        analyzer_name=article.analyzer_name,
        analyzer_model=article.analyzer_model,
        analyzer_version=article.analyzer_version,
        analysis_schema_version=article.analysis_schema_version,
        analyzed_at=article.analyzed_at,
        entities=[EntityMention.model_validate(e) for e in article.entities],
    )


@app.get("/api/health", response_model=HealthResponse)
def health():
    """Chequeo real: si la BD no responde, `status` refleja el problema en
    vez de devolver "ok" incondicionalmente (antes lo hacía sin tocar la
    BD; un orquestador lo daría por sano mientras todo falla)."""
    session = get_session()
    try:
        session.execute(text("SELECT 1"))
    except Exception as exc:
        log.warning("health_check_db_unreachable", error=str(exc))
        raise HTTPException(status_code=503, detail="La base de datos no responde.") from exc
    finally:
        session.close()
    return {"status": "ok"}


@app.get("/metrics")
def metrics():
    """Métricas en formato Prometheus (§7.1 de task.md): pipeline, latencia y
    tasa de error por endpoint, llamadas/gasto de Gemini."""
    return Response(generate_latest(metrics_registry), media_type=CONTENT_TYPE_LATEST)


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


@app.get(
    "/api/crawl-runs",
    response_model=list[CrawlRunResponse],
    dependencies=[Depends(auth.require_auth)],
)
def list_crawl_runs(limit: int = Query(20, ge=1, le=200)):
    """Historial de corridas del pipeline, más reciente primero."""
    session = get_session()
    try:
        runs = session.scalars(
            select(CrawlRun).order_by(CrawlRun.started_at.desc()).limit(limit)
        ).all()
        return runs
    finally:
        session.close()


# ── Scraper de política (tab "Scraper" del frontend) ─────────────────────────
#
# Arranca una corrida del scraper de política dominicana (pipeline.run() +
# analysis.politics_filter) en background y expone su avance para polling —
# mismo patrón que POST /api/analyze + GET /api/jobs/{id}, escalado a una
# corrida de varios minutos con 9 fuentes. El motor de análisis está
# restringido a local|groq|hybrid a nivel de schema (Literal): "gemini" ni
# siquiera es un valor aceptable acá, adrede — ver CLAUDE.md.


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


def _serialize_scrape_job(job: ScrapeJob) -> ScrapeJobResponse:
    progress_raw = json.loads(job.progress_json) if job.progress_json else {}
    progress: dict[str, ScrapeSourceProgress] = {}
    for k, v in progress_raw.items():
        try:
            progress[k] = ScrapeSourceProgress(**v)
        except ValidationError:
            # Fila de un formato de progress_json anterior (p. ej. de antes de
            # que "source" fuera requerido) — no tumbar el listado entero por
            # una entrada vieja, solo omitirla.
            log.warning("scrape_job_progress_entry_unparseable", job_id=job.id, key=k)
    return ScrapeJobResponse(
        job_id=job.id,
        status=job.status,
        target=job.target,
        per_source_cap=job.per_source_cap,
        analyzer=job.analyzer_name,
        created_at=job.created_at,
        started_at=job.started_at,
        finished_at=job.finished_at,
        progress=progress,
        crawl_run=CrawlRunResponse.model_validate(job.crawl_run) if job.crawl_run else None,
        error=job.error,
    )


@app.post(
    "/api/scrape-jobs",
    dependencies=[Depends(auth.require_auth)],
    response_model=ScrapeJobAccepted,
    status_code=202,
)
def start_scrape_job(req: ScrapeJobStartRequest, background_tasks: BackgroundTasks):
    """Encola una corrida del scraper de política sobre las 9 fuentes
    permitidas. Rechaza con 409 si ya hay una en curso — un backend de un
    solo worker no tiene por qué correr dos scrapes de 9 fuentes a la vez."""
    from scrapers import SCRAPERS

    per_source_cap = req.per_source_cap or math.ceil(req.target / len(SCRAPERS))
    session = get_session()
    try:
        if has_active_scrape_job(session):
            raise HTTPException(status_code=409, detail="Ya hay una corrida de scraping en curso.")
        job = ScrapeJob(
            id=str(uuid.uuid4()),
            target=req.target,
            per_source_cap=per_source_cap,
            analyzer_name=req.analyzer,
        )
        session.add(job)
        session.commit()
        job_id = job.id
    finally:
        session.close()

    background_tasks.add_task(run_scrape_job, job_id, req.target, per_source_cap, req.analyzer)
    return ScrapeJobAccepted(job_id=job_id)


@app.get(
    "/api/scrape-jobs/{job_id}",
    dependencies=[Depends(auth.require_auth)],
    response_model=ScrapeJobResponse,
)
def get_scrape_job(job_id: str):
    """Estado/avance de una corrida encolada por POST /api/scrape-jobs."""
    session = get_session()
    try:
        job = session.get(ScrapeJob, job_id)
        if job is None:
            raise HTTPException(status_code=404, detail="Job no encontrado.")
        return _serialize_scrape_job(job)
    finally:
        session.close()


@app.get(
    "/api/scrape-jobs",
    dependencies=[Depends(auth.require_auth)],
    response_model=list[ScrapeJobResponse],
)
def list_scrape_jobs(limit: int = Query(5, ge=1, le=50)):
    """Corridas recientes, más reciente primero — el frontend la usa al
    montar la tab para detectar un job pending/running y retomar el polling
    en vez de mostrar el formulario (p. ej. tras recargar la página)."""
    session = get_session()
    try:
        jobs = session.scalars(
            select(ScrapeJob).order_by(ScrapeJob.created_at.desc()).limit(limit)
        ).all()
        return [_serialize_scrape_job(j) for j in jobs]
    finally:
        session.close()


@app.post(
    "/api/scrape-jobs/{job_id}/cancel",
    dependencies=[Depends(auth.require_auth)],
    response_model=ScrapeJobResponse,
)
def cancel_scrape_job(job_id: str):
    """Pide cancelar una corrida en curso. Cooperativo, no instantáneo:
    pipeline.run() solo lo consulta entre fuentes y entre artículos, así que
    puede tardar hasta que termine de descargar la fuente actual."""
    session = get_session()
    try:
        job = session.get(ScrapeJob, job_id)
        if job is None:
            raise HTTPException(status_code=404, detail="Job no encontrado.")
        if job.status not in ("pending", "running"):
            raise HTTPException(
                status_code=409, detail=f"El job ya está en estado '{job.status}', no se puede cancelar."
            )
        job.cancel_requested = True
        session.commit()
        return _serialize_scrape_job(job)
    finally:
        session.close()
