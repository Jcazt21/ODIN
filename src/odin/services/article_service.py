"""Lógica de negocio de artículos guardados: listado con filtros, detalle,
rectificación (§8.2), borrado y guardado del resultado de /api/analyze (§9.2
de task.md). Los handlers HTTP (`api/routers/articles.py`) solo traducen
request/response; las queries SQLAlchemy viven aquí.
"""
from __future__ import annotations

from datetime import UTC, datetime, timedelta

from fastapi import HTTPException
from sqlalchemy import ColumnElement, and_, func, or_, select
from sqlalchemy.orm import selectinload

import odin.db.canonical_entities as canonical_entity_store
from odin.analysis.base import ANALYSIS_SCHEMA_VERSION
from odin.analysis.canonicalize import (
    canonicalize_entities,
    invalidate_person_map,
    match_actor_name,
)
from odin.analysis.text_norm import accent_insensitive_regex as _accent_insensitive_regex
from odin.analysis.text_norm import norm_key as _norm_key
from odin.api import deps
from odin.api.deps import log
from odin.api.schemas import (
    FRAMING_VALUES,
    HEADLINE_INTENT_VALUES,
    LEAD_ORIENTATION_VALUES,
    SENTIMENT_VALUES,
    SOURCE_QUALITY_VALUES,
    ArticleDetail,
    ArticleFiltersResponse,
    ArticleListResponse,
    ArticleSummary,
    DocumentalistOption,
    EntityMention,
    SaveArticleRequest,
    SourceOption,
)
from odin.db.models import Article, ArticleLocality, CanonicalEntity, Entity, Locality, User
from odin.scrapers import SCRAPERS, source_name
from odin.scrapers.base import _parse_date
from odin.services.analyzer_registry import analyzer
from odin.services.locality_service import validate_link_payloads

_ACTOR_FIELDS = {
    "dominant_actor": "dominant_actor_id",
    "blamed_actor": "blamed_actor_id",
    "credited_actor": "credited_actor_id",
}


def _documentalist_id_for(session, username: str | None) -> int | None:
    """Traduce el usuario del token a un id de `users`.

    Devuelve `None` si no hay usuario o si ya no existe (un JWT válido de
    alguien dado de baja): perder la atribución es aceptable, tumbar el guardado
    del documentalista no.
    """
    if not username:
        return None
    import odin.db.users as user_store

    user = user_store.get_by_username(session, username)
    return user.id if user else None


def accent_insensitive_contains(column, value: str) -> ColumnElement[bool]:
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
    locality: int | None = None,
    documentalist: int | None = None,
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
                accent_insensitive_contains(Article.title, q),
                accent_insensitive_contains(Article.main_topic, q),
                accent_insensitive_contains(Article.topic_keywords, q),
            )
        )
    if entity:
        stmt = stmt.join(Entity, Entity.article_id == Article.id).where(
            accent_insensitive_contains(Entity.name, entity)
        )
    if documentalist is not None:
        conditions.append(Article.documentalist_id == documentalist)
    if locality is not None:
        # Filtrar por un lugar incluye lo que cuelga de él: pedir "Santiago"
        # trae también las notas marcadas en Tamboril. La relación
        # ancestro/descendiente ya está materializada en `path`, así que basta
        # comparar prefijos — sin CTE recursivo, que además no se escribe igual
        # en los tres motores objetivo (PostgreSQL, SQLite y SQL Server).
        target_path = select(Locality.path).where(Locality.id == locality).scalar_subquery()
        stmt = (
            stmt.join(ArticleLocality, ArticleLocality.article_id == Article.id)
            .join(Locality, Locality.id == ArticleLocality.locality_id)
            .where(Locality.path.like(target_path + "%"))
        )
    if conditions:
        stmt = stmt.where(and_(*conditions))
    return stmt


# Columnas por las que se puede ordenar el listado. Lista blanca explícita y no
# un getattr(Article, sort): eso dejaría ordenar por cualquier columna de la
# tabla, `password_hash` de un futuro join incluido, con el nombre viajando
# desde el query string.
SORTABLE_COLUMNS = {
    "published_at": Article.published_at,
    "source": Article.source,
    "analyzed_on": Article.analyzed_on,
}

# Alias del contrato anterior, donde `sort` mezclaba campo y dirección. Se
# mantienen para no romper enlaces guardados.
_SORT_ALIASES = {
    "recent": ("published_at", "desc"),
    "oldest": ("published_at", "asc"),
}


def _order_by(sort: str | None, order: str | None):
    """Cláusula ORDER BY a partir del campo y la dirección pedidos."""
    field, direction = _SORT_ALIASES.get(sort or "", (sort or "published_at", order or "desc"))
    if order and sort not in _SORT_ALIASES:
        direction = order

    column = SORTABLE_COLUMNS.get(field)
    if column is None:
        raise HTTPException(
            status_code=422,
            detail=f"No se puede ordenar por '{field}'. Válidos: {', '.join(SORTABLE_COLUMNS)}.",
        )
    if direction not in ("asc", "desc"):
        raise HTTPException(
            status_code=422, detail=f"Dirección inválida: '{direction}'. Válidas: asc, desc."
        )

    clause = column.asc() if direction == "asc" else column.desc()
    # Los nulos siempre al final: `analyzed_on` está vacío en lo que nadie
    # trabajó, y en descendente esos vacíos coparían la primera pantalla.
    # Segundo criterio por id para que el orden sea estable entre páginas
    # cuando varias filas empatan.
    return [column.is_(None).asc(), clause, Article.id.desc()]


def serialize_summary(article: Article) -> ArticleSummary:
    return ArticleSummary(
        id=article.id,
        source=article.source,
        source_name=source_name(article.source),
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
        documentalist=article.documentalist.display_name if article.documentalist else None,
        analyzed_on=article.analyzed_on,
        entity_count=len(article.entities),
    )


def serialize_article(article: Article) -> ArticleDetail:
    return ArticleDetail(
        id=article.id,
        source=article.source,
        source_name=source_name(article.source),
        url=article.url,
        title=article.title,
        authors=article.authors,
        section=article.section,
        published_at=article.published_at,
        body=article.body or "",
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
        documentalist=article.documentalist.display_name if article.documentalist else None,
        analyzed_on=article.analyzed_on,
        entities=[EntityMention.model_validate(e) for e in article.entities],
    )


def list_articles(
    *,
    q: str | None,
    source: list[str] | None,
    sentiment: str | None,
    framing: str | None,
    headline_intent: str | None,
    lead_orientation: str | None,
    source_quality: str | None,
    has_hard_data: bool | None,
    entity: str | None,
    locality: int | None,
    documentalist: int | None,
    date_from: str | None,
    date_to: str | None,
    sort: str | None,
    order: str | None,
    limit: int,
    offset: int,
) -> ArticleListResponse:
    limit = max(1, min(limit, 100))
    offset = max(0, offset)

    session = deps.get_session()
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
            locality=locality,
            documentalist=documentalist,
        )
        if entity or locality is not None:
            # El join a menciones/lugares multiplica filas por artículo.
            base = base.distinct()

        total = session.scalar(select(func.count()).select_from(base.subquery())) or 0

        order_clauses = _order_by(sort, order)
        # selectinload: una query con IN(...) por relación para toda la página,
        # en vez de lazy-load por artículo (N+1) al pedir `len(article.entities)`,
        # `article.dominant_actor.name` (+blamed/credited) y `article.documentalist.
        # display_name` en serialize_summary.
        rows = session.scalars(
            base.options(
                selectinload(Article.entities),
                selectinload(Article.dominant_actor),
                selectinload(Article.blamed_actor),
                selectinload(Article.credited_actor),
                selectinload(Article.documentalist),
            )
            .order_by(*order_clauses)
            .limit(limit)
            .offset(offset)
        ).all()

        return ArticleListResponse(
            total=total,
            limit=limit,
            offset=offset,
            items=[serialize_summary(a) for a in rows],
        )
    finally:
        session.close()


def source_catalog() -> list[SourceOption]:
    """Todos los medios del registro de scrapers, con su nombre legible.

    No sale de `DISTINCT articles.source` como las facetas del filtro: esas
    listan lo ya guardado, y el formulario de captura necesita poder dar de
    alta el PRIMER reporte de un medio, que por definición todavía no aparece
    ahí.
    """
    return sorted(
        (SourceOption(value=slug, label=source_name(slug)) for slug in SCRAPERS),
        key=lambda o: o.label,
    )


def article_filters() -> ArticleFiltersResponse:
    session = deps.get_session()
    try:
        # Se ordenan por etiqueta, no por slug: el desplegable lo lee una
        # persona, y "El Día" antes que "El Nacional" solo es evidente con el
        # nombre puesto.
        sources = sorted(
            (
                SourceOption(value=s, label=source_name(s))
                for s in session.scalars(select(Article.source).distinct()).all()
                if s
            ),
            key=lambda o: o.label,
        )
        topics = [
            t
            for t in session.scalars(
                select(Article.main_topic).distinct().order_by(Article.main_topic)
            ).all()
            if t
        ]
        sections = [
            s
            for s in session.scalars(
                select(Article.section).distinct().where(Article.section.is_not(None)).order_by(Article.section)
            ).all()
            if s
        ]
        documentalists = [
            DocumentalistOption(id=u.id, display_name=u.display_name)
            for u in session.scalars(
                select(User)
                .join(Article, Article.documentalist_id == User.id)
                .distinct()
                .order_by(User.display_name)
            ).all()
        ]
        return ArticleFiltersResponse(
            sources=sources,
            topics=topics,
            sections=sections,
            sentiments=list(SENTIMENT_VALUES),
            framing=list(FRAMING_VALUES),
            headline_intent=list(HEADLINE_INTENT_VALUES),
            lead_orientation=list(LEAD_ORIENTATION_VALUES),
            source_quality=list(SOURCE_QUALITY_VALUES),
            documentalists=documentalists,
        )
    finally:
        session.close()


def get_article(article_id: int) -> ArticleDetail:
    session = deps.get_session()
    try:
        article = session.scalar(select(Article).where(Article.id == article_id))
        if not article:
            raise HTTPException(status_code=404, detail="Reporte no encontrado.")
        return serialize_article(article)
    finally:
        session.close()


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


def update_article(article_id: int, payload, documentalist_username: str | None = None) -> ArticleDetail:
    """Rectifica el análisis de un artículo ya guardado (§8.2): tema, encuadre,
    sentimiento, actores señalados... Solo toca los campos enviados. No permite
    corregir `title`/`body`/`url` porque eso es lo que decía la fuente, no un
    juicio del sistema — si el scrape en sí está mal, hay que borrar y volver a
    analizar."""
    session = deps.get_session()
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
        # La rectificación reasigna la autoría: el KPI mide quién dejó el dato
        # como está, no quién lo tocó primero.
        rectifier = _documentalist_id_for(session, documentalist_username)
        if rectifier is not None:
            article.documentalist_id = rectifier
            article.analyzed_on = datetime.now(UTC).date()
        session.commit()
        return serialize_article(article)
    except HTTPException:
        raise
    except Exception:
        session.rollback()
        log.exception("article_rectification_failed", article_id=article_id)
        raise HTTPException(status_code=500, detail="Error interno rectificando el artículo.") from None
    finally:
        session.close()


def delete_article(article_id: int) -> None:
    """Borra permanentemente un artículo y sus menciones (§8.2): no hay
    archivado ni papelera — es el procedimiento de borrado que el cliente
    puede exigir sobre su propio contenido o el de una persona nombrada."""
    session = deps.get_session()
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


def save_article(
    req: SaveArticleRequest, documentalist_username: str | None = None
) -> tuple[ArticleDetail, bool]:
    """Persiste el resultado de /api/analyze, ya revisado/corregido.

    Devuelve el reporte y si hubo alta. El segundo valor existe para el
    formulario manual: ante una URL ya cargada esta función devuelve la
    existente, y sin esa señal el documentalista vería "guardado" tras
    llenar diez campos que no se guardaron en ninguna parte.
    """
    url = req.url.strip()

    session = deps.get_session()
    try:
        # Las tablas ya se crean en el lifespan de arranque (_lifespan); no
        # hace falta repetir init_db() (inspección de metadata + posible DDL)
        # en cada guardado.
        existing = session.scalar(select(Article).where(Article.url == url))
        if existing:
            return serialize_article(existing), False

        # Antes que nada, porque un lugar inválido tiene que abortar el alta
        # entera y no dejar un reporte sin los lugares que se le indicaron.
        locality_links = validate_link_payloads(session, list(req.localities))

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
            analyzer_name=analyzer.name,
            analyzer_model=analyzer.model,
            analyzer_version=analyzer.version,
            analysis_schema_version=ANALYSIS_SCHEMA_VERSION,
            analyzed_at=datetime.now(UTC),
            documentalist_id=_documentalist_id_for(session, documentalist_username),
            analyzed_on=datetime.now(UTC).date(),
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
        session.flush()  # necesita el id del artículo para los vínculos
        session.add_all([
            ArticleLocality(
                article_id=article.id,
                locality_id=link.locality_id,
                kind=link.kind,
                origin=link.origin,
                confidence=link.confidence,
            )
            for link in locality_links
        ])
        session.commit()
        # Los PERSON nuevos deben poder resolver un apellido suelto en el
        # siguiente análisis (ver known_person_fullname_map).
        invalidate_person_map()
        return serialize_article(article), True
    except HTTPException:
        raise
    except Exception:
        session.rollback()
        log.exception("article_save_failed", url=url)
        raise HTTPException(status_code=500, detail="Error interno guardando el artículo.") from None
    finally:
        session.close()
