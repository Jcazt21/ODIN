"""API REST de Odin (FastAPI).

Flujo en dos pasos:
  1. POST /api/analyze   — descarga la URL (trafilatura) y la analiza (tema,
     sentimiento, entidades). NO guarda: es una vista previa para revisar/
     corregir en el frontend antes de persistir. Si la URL ya estaba
     guardada, devuelve directamente ese registro (already_saved=true).
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
import logging
from contextlib import asynccontextmanager
from datetime import timedelta

import requests
import trafilatura
from fastapi import Depends, FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from sqlalchemy import ColumnElement, and_, func, or_, select, text
from sqlalchemy.orm import selectinload

import auth
import db.aliases as alias_store
import db.canonical_entities as canonical_entity_store
import url_guard
from analysis import LocalAnalyzer
from analysis.base import Analyzer
from analysis.canonicalize import canonicalize_entities, canonicalize_result, match_actor_name
from analysis.local_analyzer import sentence_mentions_venue_word
from config import settings
from db.models import Article, CanonicalEntity, Entity, EntityAlias
from db.session import get_session, init_db
from scrapers.base import BaseScraper, _parse_date
from url_guard import UrlNotAllowed

log = logging.getLogger("odin.api")


@asynccontextmanager
async def _lifespan(app: FastAPI):
    """Crea tablas y carga el catálogo semilla al arrancar."""
    try:
        init_db()
        n = alias_store.load_seed()
        if n:
            log.info("Catálogo semilla: %d siglas cargadas", n)
    except Exception as exc:
        log.warning("No se pudo cargar el catálogo semilla: %s", exc)
    yield


app = FastAPI(title="Odin API", lifespan=_lifespan)

app.include_router(auth.router)

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


def _fetch_and_extract(url: str):
    # La URL viene del usuario: se descarga con las protecciones de url_guard
    # (allowlist de dominios, bloqueo de IPs internas, tope de tamaño), no con
    # el fetch del scraper, que confía en las URLs de sus propios sitemaps.
    try:
        html = url_guard.fetch_html(url, session=_extractor.session)
    except UrlNotAllowed as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except requests.RequestException as exc:
        log.warning("fetch falló (%s): %s", url, exc)
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


@app.post("/api/analyze", dependencies=[Depends(auth.require_auth)])
def analyze(req: AnalyzeRequest):
    """Descarga y analiza la URL. NO guarda — es una vista previa para que el
    usuario revise/corrija en el frontend antes de POST /api/articles."""
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
    finally:
        session.close()

    extracted = _fetch_and_extract(url)
    result = _analyze_safely(extracted["title"], extracted["body"])
    _arbitrate_ambiguous_persons(result)
    canonicalize_result(result)

    return {
        "already_saved": False,
        "id": None,
        "source": extracted.get("sitename") or "manual",
        "url": url,
        "title": extracted["title"],
        "authors": extracted["authors"],
        "section": extracted["section"],
        "published_at": extracted["published_at"],
        "body": extracted["body"],
        "main_topic": result.main_topic,
        "topic_keywords": ", ".join(result.topic_keywords) or None,
        "overall_sentiment": result.overall_sentiment,
        "sentiment_score": result.sentiment_score,
        "framing": result.framing,
        "headline_intent": result.headline_intent,
        "lead_orientation": result.lead_orientation,
        "dominant_actor": result.dominant_actor,
        "source_quality": result.source_quality,
        "has_hard_data": result.has_hard_data,
        "blamed_actor": result.blamed_actor,
        "credited_actor": result.credited_actor,
        "entities": [
            {
                "name": e.name,
                "type": e.type,
                "mentions_count": e.mentions_count,
                "sentiment_toward": e.sentiment_toward,
                "sentiment_score": e.sentiment_score,
                "context": e.context,
                "extraction_confidence": e.extraction_confidence,
            }
            for e in result.entities
        ],
    }


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


def _escape_like(value: str) -> str:
    """Escapa los comodines de LIKE/ILIKE (`%`, `_`) y el propio carácter de
    escape, para que el texto que busca el usuario se trate literalmente. Sin
    esto, buscar "50%" o "foo_bar" hace que `%`/`_` actúen como comodín en vez
    de como el carácter literal que el usuario escribió."""
    return value.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


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
        like = f"%{_escape_like(q)}%"
        conditions.append(
            or_(
                Article.title.ilike(like, escape="\\"),
                Article.main_topic.ilike(like, escape="\\"),
                Article.topic_keywords.ilike(like, escape="\\"),
            )
        )
    if entity:
        stmt = stmt.join(Entity, Entity.article_id == Article.id).where(
            Entity.name.ilike(f"%{_escape_like(entity)}%", escape="\\")
        )
    if conditions:
        stmt = stmt.where(and_(*conditions))
    return stmt


def _serialize_summary(article: Article) -> dict:
    return {
        "id": article.id,
        "source": article.source,
        "url": article.url,
        "title": article.title,
        "section": article.section,
        "published_at": article.published_at,
        "scraped_at": article.scraped_at,
        "main_topic": article.main_topic,
        "overall_sentiment": article.overall_sentiment,
        "sentiment_score": article.sentiment_score,
        "framing": article.framing,
        "headline_intent": article.headline_intent,
        "lead_orientation": article.lead_orientation,
        "source_quality": article.source_quality,
        "has_hard_data": article.has_hard_data,
        "dominant_actor": article.dominant_actor,
        "blamed_actor": article.blamed_actor,
        "credited_actor": article.credited_actor,
        "entity_count": len(article.entities),
    }


@app.get("/api/articles")
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
        # selectinload: una segunda query con IN(...) para todas las entidades
        # de la página, en vez de una lazy-load por artículo (N+1) al pedir
        # `len(article.entities)` en _serialize_summary.
        rows = session.scalars(
            base.options(selectinload(Article.entities))
            .order_by(order_col, Article.id.desc())
            .limit(limit)
            .offset(offset)
        ).all()

        return {
            "total": total,
            "limit": limit,
            "offset": offset,
            "items": [_serialize_summary(a) for a in rows],
        }
    finally:
        session.close()


@app.get("/api/articles/filters")
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
        return {
            "sources": sources,
            "sections": sections,
            "sentiments": list(SENTIMENT_VALUES),
            "framing": list(FRAMING_VALUES),
            "headline_intent": list(HEADLINE_INTENT_VALUES),
            "lead_orientation": list(LEAD_ORIENTATION_VALUES),
            "source_quality": list(SOURCE_QUALITY_VALUES),
        }
    finally:
        session.close()


@app.get("/api/articles/{article_id}")
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


@app.put("/api/articles/{article_id}", dependencies=[Depends(auth.require_auth)])
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
            setattr(article, field, value)
        session.commit()
        return _serialize(article, already_saved=True)
    except HTTPException:
        raise
    except Exception:
        session.rollback()
        log.exception("error rectificando artículo %d", article_id)
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
        log.exception("error borrando artículo %d", article_id)
        raise HTTPException(status_code=500, detail="Error interno borrando el artículo.") from None
    finally:
        session.close()


# ── Menciones de entidad (por artículo) ──────────────────────────────────────


@app.put("/api/entities/{entity_id}", dependencies=[Depends(auth.require_auth)])
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
        return {
            "id": entity.id,
            "name": entity.name,
            "type": entity.type,
            "mentions_count": entity.mentions_count,
            "sentiment_toward": entity.sentiment_toward,
            "sentiment_score": entity.sentiment_score,
            "context": entity.context,
            "extraction_confidence": entity.extraction_confidence,
            "canonical_entity_id": entity.canonical_entity_id,
        }
    except HTTPException:
        raise
    except Exception:
        session.rollback()
        log.exception("error rectificando mención %d", entity_id)
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
        log.exception("error borrando mención %d", entity_id)
        raise HTTPException(status_code=500, detail="Error interno borrando la mención.") from None
    finally:
        session.close()


# ── CRUD de siglas ─────────────────────────────────────────────────────────────


@app.get("/api/aliases")
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
            like = f"%{_escape_like(q)}%"
            stmt = stmt.where(
                or_(
                    EntityAlias.alias.ilike(like, escape="\\"),
                    EntityAlias.canonical_name.ilike(like, escape="\\"),
                )
            )
        rows = session.scalars(
            stmt.order_by(EntityAlias.alias).limit(limit).offset(offset)
        ).all()
        return [
            {
                "id": r.id,
                "alias": r.alias,
                "canonical_name": r.canonical_name,
                "type": r.type,
                "is_active": r.is_active,
                "created_at": r.created_at,
                "updated_at": r.updated_at,
            }
            for r in rows
        ]
    finally:
        session.close()


@app.post("/api/aliases", status_code=201, dependencies=[Depends(auth.require_auth)])
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
        return {
            "id": row.id,
            "alias": row.alias,
            "canonical_name": row.canonical_name,
            "type": row.type,
            "is_active": row.is_active,
            "created_at": row.created_at,
            "updated_at": row.updated_at,
        }
    except HTTPException:
        raise
    except Exception:
        session.rollback()
        log.exception("error creando alias")
        raise HTTPException(status_code=500, detail="Error interno creando el alias.") from None
    finally:
        session.close()


@app.put("/api/aliases/{alias_id}", dependencies=[Depends(auth.require_auth)])
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
        return {
            "id": row.id,
            "alias": row.alias,
            "canonical_name": row.canonical_name,
            "type": row.type,
            "is_active": row.is_active,
            "created_at": row.created_at,
            "updated_at": row.updated_at,
        }
    except HTTPException:
        raise
    except Exception:
        session.rollback()
        log.exception("error actualizando alias %d", alias_id)
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
        log.exception("error eliminando alias %d", alias_id)
        raise HTTPException(status_code=500, detail="Error interno eliminando el alias.") from None
    finally:
        session.close()


# ── Entidades canónicas (dimensión + fusión) ─────────────────────────────────


def _serialize_canonical_entity(row: CanonicalEntity, article_count: int, total_mentions: int) -> dict:
    return {
        "id": row.id,
        "name": row.name,
        "type": row.type,
        "description": row.description,
        "created_at": row.created_at,
        "updated_at": row.updated_at,
        "article_count": article_count,
        "total_mentions": total_mentions,
    }


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


@app.get("/api/canonical-entities")
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
            stmt = stmt.where(CanonicalEntity.name.ilike(f"%{_escape_like(q)}%", escape="\\"))

        total = session.scalar(select(func.count()).select_from(stmt.subquery())) or 0

        rows = session.execute(
            stmt.order_by(article_count_col.desc(), CanonicalEntity.name)
            .limit(limit)
            .offset(offset)
        ).all()

        return {
            "total": total,
            "limit": limit,
            "offset": offset,
            "items": [
                _serialize_canonical_entity(row, article_count, total_mentions)
                for row, article_count, total_mentions in rows
            ],
        }
    finally:
        session.close()


@app.get("/api/canonical-entities/{entity_id}")
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

        return {
            **_serialize_canonical_entity(row, article_count, total_mentions),
            "articles": [
                {
                    "article_id": article.id,
                    "title": article.title,
                    "url": article.url,
                    "source": article.source,
                    "published_at": article.published_at,
                    "sentiment_toward": mention.sentiment_toward,
                    "mentions_count": mention.mentions_count,
                }
                for mention, article in mention_rows
            ],
        }
    except HTTPException:
        raise
    finally:
        session.close()


@app.put(
    "/api/canonical-entities/{entity_id}", dependencies=[Depends(auth.require_auth)]
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
        log.exception("error actualizando entidad canónica %d", entity_id)
        raise HTTPException(
            status_code=500, detail="Error interno actualizando la entidad canónica."
        ) from None
    finally:
        session.close()


@app.post(
    "/api/canonical-entities/{entity_id}/merge",
    dependencies=[Depends(auth.require_auth)],
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
            "error fusionando entidades canónicas %d <- %d", entity_id, payload.source_id
        )
        raise HTTPException(status_code=500, detail="Error interno fusionando entidades.") from None
    finally:
        session.close()


@app.post("/api/articles", dependencies=[Depends(auth.require_auth)])
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
            dominant_actor=match_actor_name(req.dominant_actor, entities),
            source_quality=req.source_quality,
            has_hard_data=req.has_hard_data,
            blamed_actor=match_actor_name(req.blamed_actor, entities),
            credited_actor=match_actor_name(req.credited_actor, entities),
        )
        for e in entities:
            canonical = canonical_entity_store.get_or_create(session, e.name, e.type)
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
        session.add(article)
        session.commit()
        return _serialize(article, already_saved=False)
    except HTTPException:
        raise
    except Exception:
        session.rollback()
        log.exception("error guardando %s", url)
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


def _serialize(article: Article, already_saved: bool) -> dict:
    return {
        "already_saved": already_saved,
        "id": article.id,
        "source": article.source,
        "url": article.url,
        "title": article.title,
        "authors": article.authors,
        "section": article.section,
        "published_at": article.published_at,
        "body": article.body,
        "main_topic": article.main_topic,
        "topic_keywords": article.topic_keywords,
        "overall_sentiment": article.overall_sentiment,
        "sentiment_score": article.sentiment_score,
        "framing": article.framing,
        "headline_intent": article.headline_intent,
        "lead_orientation": article.lead_orientation,
        "dominant_actor": article.dominant_actor,
        "source_quality": article.source_quality,
        "has_hard_data": article.has_hard_data,
        "blamed_actor": article.blamed_actor,
        "credited_actor": article.credited_actor,
        "entities": [
            {
                "id": e.id,
                "name": e.name,
                "type": e.type,
                "mentions_count": e.mentions_count,
                "sentiment_toward": e.sentiment_toward,
                "sentiment_score": e.sentiment_score,
                "context": e.context,
                "extraction_confidence": e.extraction_confidence,
                "canonical_entity_id": e.canonical_entity_id,
            }
            for e in article.entities
        ],
    }


@app.get("/api/health")
def health():
    """Chequeo real: si la BD no responde, `status` refleja el problema en
    vez de devolver "ok" incondicionalmente (antes lo hacía sin tocar la
    BD; un orquestador lo daría por sano mientras todo falla)."""
    session = get_session()
    try:
        session.execute(text("SELECT 1"))
    except Exception as exc:
        log.warning("health check: BD no responde: %s", exc)
        raise HTTPException(status_code=503, detail="La base de datos no responde.") from exc
    finally:
        session.close()
    return {"status": "ok"}
