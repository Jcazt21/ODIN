"""API REST de Odin (FastAPI).

Flujo en dos pasos:
  1. POST /api/analyze   — descarga la URL (trafilatura) y la analiza (tema,
     sentimiento, entidades). NO guarda: es una vista previa para revisar/
     corregir en el frontend antes de persistir. Si la URL ya estaba
     guardada, devuelve directamente ese registro (already_saved=true).
  2. POST /api/articles  — recibe el resultado (posiblemente editado por el
     usuario) y lo guarda.

CRUD de siglas: GET/POST /api/aliases, PUT/DELETE /api/aliases/{id}.

Uso:
  uvicorn api:app --reload --port 8000
"""
from __future__ import annotations

import logging
import os
from contextlib import asynccontextmanager
from datetime import timedelta

import trafilatura
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from sqlalchemy import and_, func, or_, select

from analysis import LocalAnalyzer
from analysis.canonicalize import canonicalize_entities, canonicalize_result, match_actor_name
from analysis.gemini_analyzer import GeminiAnalyzer
from analysis.local_analyzer import sentence_mentions_venue_word
import db.aliases as alias_store
from db.models import Article, Entity, EntityAlias
from db.session import get_session, init_db
from scrapers.base import BaseScraper, _parse_date

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

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Carga perezosa: los modelos se inicializan aquí.
if os.getenv("GEMINI_API_KEY"):
    log.info("Iniciando API con GeminiAnalyzer")
    _analyzer = GeminiAnalyzer()
else:
    log.info("Iniciando API con LocalAnalyzer (spaCy + pysentimiento)")
    _analyzer = LocalAnalyzer()
_IS_GEMINI_ANALYZER = isinstance(_analyzer, GeminiAnalyzer)
_extractor = BaseScraper()


class AnalyzeRequest(BaseModel):
    url: str


class EntityPayload(BaseModel):
    name: str
    type: str
    mentions_count: int = 1
    sentiment_toward: str | None = None
    sentiment_score: float | None = None
    context: str | None = None


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


def _fetch_and_extract(url: str):
    html = _extractor.fetch(url)
    if not html:
        raise HTTPException(status_code=422, detail="No se pudo descargar la URL.")

    import json

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


@app.post("/api/analyze")
def analyze(req: AnalyzeRequest):
    """Descarga y analiza la URL. NO guarda — es una vista previa para que el
    usuario revise/corrija en el frontend antes de POST /api/articles."""
    url = req.url.strip()
    if not url.startswith(("http://", "https://")):
        raise HTTPException(status_code=422, detail="URL inválida.")

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
    conditions = []
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
        like = f"%{q}%"
        conditions.append(
            or_(
                Article.title.ilike(like),
                Article.main_topic.ilike(like),
                Article.topic_keywords.ilike(like),
            )
        )
    if entity:
        stmt = stmt.join(Entity, Entity.article_id == Article.id).where(
            Entity.name.ilike(f"%{entity}%")
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
        rows = session.scalars(
            base.order_by(order_col, Article.id.desc()).limit(limit).offset(offset)
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


# ── CRUD de siglas ─────────────────────────────────────────────────────────────


@app.get("/api/aliases")
def list_aliases(q: str | None = None):
    """Devuelve todos los alias activos e inactivos.  Filtrado opcional por ?q=."""
    session = get_session()
    try:
        stmt = select(EntityAlias).order_by(EntityAlias.alias)
        rows = session.scalars(stmt).all()
        if q:
            ql = q.lower()
            rows = [r for r in rows if ql in r.alias.lower() or ql in r.canonical_name.lower()]
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


@app.post("/api/aliases", status_code=201)
def create_alias(payload: AliasPayload):
    """Crea un nuevo alias. Devuelve 409 si la sigla ya existe (mismo tipo)."""
    alias_key = payload.alias.strip().lower()
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
        raise HTTPException(status_code=500, detail="Error interno creando el alias.")
    finally:
        session.close()


@app.put("/api/aliases/{alias_id}")
def update_alias(alias_id: int, payload: AliasUpdatePayload):
    """Actualiza parcialmente un alias (nombre canónico, estado activo/inactivo...)."""
    session = get_session()
    try:
        row = session.scalar(select(EntityAlias).where(EntityAlias.id == alias_id))
        if not row:
            raise HTTPException(status_code=404, detail="Alias no encontrado.")
        if payload.alias is not None:
            row.alias = payload.alias.strip()
            row.alias_key = payload.alias.strip().lower()
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
        raise HTTPException(status_code=500, detail="Error interno actualizando el alias.")
    finally:
        session.close()


@app.delete("/api/aliases/{alias_id}", status_code=204)
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
        raise HTTPException(status_code=500, detail="Error interno eliminando el alias.")
    finally:
        session.close()


@app.post("/api/articles")
def save_article(req: SaveArticleRequest):
    """Persiste el resultado de /api/analyze, ya revisado/corregido."""
    url = req.url.strip()

    session = get_session()
    try:
        init_db()

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
            article.entities.append(
                Entity(
                    name=e.name,
                    type=e.type,
                    mentions_count=e.mentions_count,
                    sentiment_toward=e.sentiment_toward,
                    sentiment_score=e.sentiment_score,
                    context=e.context,
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
        raise HTTPException(status_code=500, detail="Error interno guardando el artículo.")
    finally:
        session.close()


    return list(merged.values())


def _analyze_safely(title: str, body: str):
    try:
        return _analyzer.analyze(title, body)
    except RuntimeError as exc:
        raise HTTPException(status_code=500, detail=str(exc))


def _gemini_key_configured() -> bool:
    return bool(os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY"))


def _arbitrate_ambiguous_persons(result) -> None:
    """Segundo filtro (pagado, opcional) solo para PERSON cuya oración de
    contexto menciona una palabra de lugar en algún punto — la heurística
    local ya descartó los casos claros; esto cubre lo que queda ambiguo. Se
    salta por completo si no hay GEMINI_API_KEY configurada (sin costo por
    defecto) o si el análisis principal ya lo hizo GeminiAnalyzer (su prompt
    ya excluye lugares/homenajes; repetirlo sería pagar dos veces). Solo se
    llama desde /api/analyze, nunca desde el crawl (main.py/pipeline.py).

    Todos los casos ambiguos del artículo van en UNA sola llamada a Gemini."""
    if _IS_GEMINI_ANALYZER or not _gemini_key_configured():
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
    dropped = {id(e) for e, keep in zip(ambiguous, verdicts) if not keep}
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
                "name": e.name,
                "type": e.type,
                "mentions_count": e.mentions_count,
                "sentiment_toward": e.sentiment_toward,
                "sentiment_score": e.sentiment_score,
                "context": e.context,
            }
            for e in article.entities
        ],
    }


@app.get("/api/health")
def health():
    return {"status": "ok"}
