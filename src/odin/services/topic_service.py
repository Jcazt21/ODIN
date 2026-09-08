"""Lógica de negocio del catálogo administrable de temas y de la clasificación
de la noticia contra él.

Mismo reparto que `locality_service.py` / `alias_service.py`: los handlers HTTP
(`api/routers/topics.py`) solo traducen request/response, las queries viven aquí,
sesión por función, `HTTPException` en el borde y `topic_store.invalidate_cache()`
tras cada mutación (para que el `resolve()`/`get_catalog()` y el matcher del
clasificador reflejen el cambio en el siguiente request).
"""
from __future__ import annotations

from datetime import timedelta

from fastapi import HTTPException
from sqlalchemy import func, select

from odin.analysis.text_norm import norm_key
from odin.api import deps
from odin.api.deps import log
from odin.api.schemas import (
    ArticleSummary,
    ArticleTopicResponse,
    TopicAliasPayload,
    TopicAliasResponse,
    TopicFrequencyRow,
    TopicNode,
    TopicPayload,
    TopicResponse,
    TopicUpdatePayload,
)
from odin.db import topics as topic_store
from odin.db.models import Article, ArticleTopic, Topic, TopicAlias
from odin.scrapers.base import _parse_date


# ── Catálogo ─────────────────────────────────────────────────────────────────

def list_topics(
    q: str | None,
    parent_id: int | None,
    include_inactive: bool,
    limit: int,
    offset: int,
) -> list[TopicResponse]:
    """Busca temas por nombre (sin acentos) y/o tema padre."""
    limit = max(1, min(limit, 500))
    offset = max(0, offset)
    session = deps.get_session()
    try:
        stmt = select(Topic)
        if not include_inactive:
            stmt = stmt.where(Topic.is_active.is_(True))
        if q:
            # norm_key ya está guardado sin acentos ni mayúsculas: un LIKE sobre
            # esa columna basta y aprovecha su índice (igual que localities).
            stmt = stmt.where(Topic.norm_key.like(f"%{norm_key(q)}%"))
        if parent_id is not None:
            stmt = stmt.where(Topic.parent_id == parent_id)
        rows = session.scalars(
            stmt.order_by(Topic.display_order, Topic.name).limit(limit).offset(offset)
        ).all()
        return [TopicResponse.model_validate(r) for r in rows]
    finally:
        session.close()


def get_tree(*, include_inactive: bool = False) -> list[TopicNode]:
    """El catálogo entero como árbol, con alias, para el administrador de temas
    del frontend. Una sola query + los alias en lote (mismo criterio que el
    árbol de localidades: evitar el N+1 al abrir cada rama)."""
    session = deps.get_session()
    try:
        stmt = select(Topic)
        if not include_inactive:
            stmt = stmt.where(Topic.is_active.is_(True))
        rows = session.scalars(stmt.order_by(Topic.display_order, Topic.name)).all()

        aliases: dict[int, list[str]] = {}
        for a in session.scalars(select(TopicAlias)).all():
            aliases.setdefault(a.topic_id, []).append(a.alias)

        nodes = {
            r.id: TopicNode(
                id=r.id,
                name=r.name,
                slug=r.slug,
                parent_id=r.parent_id,
                aliases=aliases.get(r.id, []),
                children=[],
            )
            for r in rows
        }
        roots: list[TopicNode] = []
        for r in rows:
            node = nodes[r.id]
            parent = nodes.get(r.parent_id) if r.parent_id else None
            # Un nodo cuyo padre está inactivo (o filtrado) se muestra suelto en
            # vez de desaparecer sin explicación, igual que en localities.
            if parent is None:
                roots.append(node)
            else:
                parent.children.append(node)
        return roots
    finally:
        session.close()


def create_topic(payload: TopicPayload) -> TopicResponse:
    name = payload.name.strip()
    if not name:
        raise HTTPException(status_code=422, detail="El nombre no puede estar vacío.")
    nkey = norm_key(name)
    slug = payload.slug.strip()
    session = deps.get_session()
    try:
        parent = session.get(Topic, payload.parent_id) if payload.parent_id else None
        if payload.parent_id and not parent:
            raise HTTPException(status_code=404, detail="El tema padre no existe.")
        clash = session.scalar(
            select(Topic).where(
                Topic.parent_id == payload.parent_id, Topic.norm_key == nkey
            )
        )
        if clash:
            raise HTTPException(
                status_code=409, detail=f"'{name}' ya existe bajo ese tema padre."
            )
        slug_clash = session.scalar(select(Topic).where(Topic.slug == slug))
        if slug_clash:
            raise HTTPException(
                status_code=409, detail=f"El slug '{slug}' ya está en uso."
            )
        row = Topic(
            name=name,
            norm_key=nkey,
            slug=slug,
            description=payload.description,
            parent_id=payload.parent_id,
            display_order=payload.display_order,
            path="",
        )
        session.add(row)
        session.flush()  # necesitamos el id para armar el path
        row.path = f"{(parent.path if parent else '/')}{row.id}/"
        session.commit()
        topic_store.invalidate_cache()
        return TopicResponse.model_validate(row)
    except HTTPException:
        raise
    except Exception:
        session.rollback()
        log.exception("topic_creation_failed")
        raise HTTPException(status_code=500, detail="Error interno creando el tema.") from None
    finally:
        session.close()


def update_topic(topic_id: int, payload: TopicUpdatePayload) -> TopicResponse:
    """Renombra, redescribe, (des)activa o reordena un tema. No mueve nodos de
    padre: eso obligaría a reescribir el `path` del subárbol y no es un caso
    real del catálogo."""
    session = deps.get_session()
    try:
        row = session.get(Topic, topic_id)
        if not row:
            raise HTTPException(status_code=404, detail="Tema no encontrado.")
        if payload.name is not None:
            name = payload.name.strip()
            if not name:
                raise HTTPException(status_code=422, detail="El nombre no puede estar vacío.")
            nkey = norm_key(name)
            clash = session.scalar(
                select(Topic).where(
                    Topic.parent_id == row.parent_id,
                    Topic.norm_key == nkey,
                    Topic.id != row.id,
                )
            )
            if clash:
                raise HTTPException(
                    status_code=409, detail=f"'{name}' ya existe bajo ese tema padre."
                )
            row.name = name
            row.norm_key = nkey
        if payload.description is not None:
            row.description = payload.description
        if payload.is_active is not None:
            row.is_active = payload.is_active
        if payload.display_order is not None:
            row.display_order = payload.display_order
        session.commit()
        topic_store.invalidate_cache()
        return TopicResponse.model_validate(row)
    except HTTPException:
        raise
    except Exception:
        session.rollback()
        log.exception("topic_update_failed", topic_id=topic_id)
        raise HTTPException(
            status_code=500, detail="Error interno actualizando el tema."
        ) from None
    finally:
        session.close()


def delete_topic(topic_id: int) -> None:
    """Borra un tema. Baja lógica (`is_active=False`) si tiene artículos
    vinculados o subtemas — no romper el histórico ni dejar hijos huérfanos —;
    borrado duro solo si no cuelga nada."""
    session = deps.get_session()
    try:
        row = session.get(Topic, topic_id)
        if not row:
            raise HTTPException(status_code=404, detail="Tema no encontrado.")
        referenced = session.scalar(
            select(func.count()).select_from(ArticleTopic).where(
                ArticleTopic.topic_id == topic_id
            )
        )
        has_children = session.scalar(
            select(func.count()).select_from(Topic).where(Topic.parent_id == topic_id)
        )
        if referenced or has_children:
            row.is_active = False
        else:
            session.delete(row)
        session.commit()
        topic_store.invalidate_cache()
    except HTTPException:
        raise
    except Exception:
        session.rollback()
        log.exception("topic_deletion_failed", topic_id=topic_id)
        raise HTTPException(
            status_code=500, detail="Error interno eliminando el tema."
        ) from None
    finally:
        session.close()


# ── Alias ────────────────────────────────────────────────────────────────────

def add_alias(topic_id: int, payload: TopicAliasPayload) -> TopicAliasResponse:
    session = deps.get_session()
    try:
        if not session.get(Topic, topic_id):
            raise HTTPException(status_code=404, detail="Tema no encontrado.")
        key = norm_key(payload.alias)
        if not key:
            raise HTTPException(status_code=422, detail="El alias no puede estar vacío.")
        clash = session.scalar(
            select(TopicAlias).where(
                TopicAlias.topic_id == topic_id, TopicAlias.alias_key == key
            )
        )
        if clash:
            raise HTTPException(
                status_code=409,
                detail=f"El alias '{payload.alias}' ya existe para este tema.",
            )
        row = TopicAlias(
            topic_id=topic_id,
            alias=payload.alias.strip(),
            alias_key=key,
            is_active=payload.is_active,
        )
        session.add(row)
        session.commit()
        topic_store.invalidate_cache()
        return TopicAliasResponse.model_validate(row)
    except HTTPException:
        raise
    except Exception:
        session.rollback()
        log.exception("topic_alias_add_failed", topic_id=topic_id)
        raise HTTPException(status_code=500, detail="Error interno creando el alias.") from None
    finally:
        session.close()


def delete_alias(topic_id: int, alias_id: int) -> None:
    session = deps.get_session()
    try:
        row = session.scalar(
            select(TopicAlias).where(
                TopicAlias.id == alias_id, TopicAlias.topic_id == topic_id
            )
        )
        if not row:
            raise HTTPException(status_code=404, detail="Alias no encontrado.")
        session.delete(row)
        session.commit()
        topic_store.invalidate_cache()
    except HTTPException:
        raise
    except Exception:
        session.rollback()
        log.exception("topic_alias_delete_failed", alias_id=alias_id)
        raise HTTPException(
            status_code=500, detail="Error interno eliminando el alias."
        ) from None
    finally:
        session.close()


# ── Vínculo artículo ↔ tema ──────────────────────────────────────────────────

def list_article_topics(article_id: int) -> list[ArticleTopicResponse]:
    session = deps.get_session()
    try:
        if not session.get(Article, article_id):
            raise HTTPException(status_code=404, detail="Reporte no encontrado.")
        links = session.scalars(
            select(ArticleTopic).where(ArticleTopic.article_id == article_id)
        ).all()
        names = (
            {
                t.id: t.name
                for t in session.scalars(
                    select(Topic).where(Topic.id.in_([link.topic_id for link in links]))
                ).all()
            }
            if links
            else {}
        )
        return [
            ArticleTopicResponse(
                id=link.id,
                topic_id=link.topic_id,
                name=names.get(link.topic_id, ""),
                origin=link.origin,
                score=link.score,
                evidence=link.evidence,
            )
            for link in links
        ]
    finally:
        session.close()


def replace_article_topics(
    article_id: int, topic_ids: list[int], documentalist_username: str | None = None
) -> list[ArticleTopicResponse]:
    """Deja el artículo exactamente con los temas indicados, todos `MANUAL`
    (un dato humano no tiene score estimado). Rectificar reasigna la autoría del
    reporte, igual que `update_article`."""
    session = deps.get_session()
    try:
        article = session.get(Article, article_id)
        if not article:
            raise HTTPException(status_code=404, detail="Reporte no encontrado.")
        valid = set(
            session.scalars(select(Topic.id).where(Topic.id.in_(topic_ids))).all()
        )
        missing = set(topic_ids) - valid
        if missing:
            raise HTTPException(
                status_code=422,
                detail=f"Temas inexistentes: {sorted(missing)}.",
            )
        session.query(ArticleTopic).filter(
            ArticleTopic.article_id == article_id
        ).delete()
        for tid in dict.fromkeys(topic_ids):
            session.add(
                ArticleTopic(
                    article_id=article_id,
                    topic_id=tid,
                    origin="MANUAL",
                    score=None,
                    evidence=None,
                )
            )
        from odin.services.article_service import _documentalist_id_for

        rectifier = _documentalist_id_for(session, documentalist_username)
        if rectifier is not None:
            article.documentalist_id = rectifier
        session.commit()
        return list_article_topics(article_id)
    except HTTPException:
        raise
    except Exception:
        session.rollback()
        log.exception("replace_article_topics_failed", article_id=article_id)
        raise HTTPException(
            status_code=500, detail="Error interno actualizando los temas."
        ) from None
    finally:
        session.close()


# ── Cola "sin clasificar" y frecuencia (R7) ──────────────────────────────────

def list_unclassified(limit: int = 20, offset: int = 0) -> list[ArticleSummary]:
    """Reportes sin ningún `article_topic`: lo que el clasificador no supo
    mapear y espera revisión humana."""
    limit = max(1, min(limit, 100))
    offset = max(0, offset)
    session = deps.get_session()
    try:
        no_topics = ~select(1).select_from(ArticleTopic).where(
            ArticleTopic.article_id == Article.id
        ).exists()
        rows = session.scalars(
            select(Article)
            .where(no_topics)
            .order_by(Article.scraped_at.desc())
            .limit(limit)
            .offset(offset)
        ).all()
        from odin.services.article_service import serialize_summary

        return [serialize_summary(a) for a in rows]
    finally:
        session.close()


def frequency_by_topic(
    date_from: str | None = None,
    date_to: str | None = None,
    parent_id: int | None = None,
) -> list[TopicFrequencyRow]:
    """Conteo de artículos por tema y día. Roll-up al padre: una nota en un
    subtema cuenta también para su tema raíz (join por prefijo de `path`, igual
    que `frequency_by_locality`)."""
    session = deps.get_session()
    try:
        anc = select(Topic.id, Topic.name, Topic.path).subquery()
        day = func.date(Article.published_at)
        stmt = (
            select(
                anc.c.id,
                anc.c.name,
                day.label("day"),
                func.count(func.distinct(Article.id)).label("count"),
            )
            .select_from(ArticleTopic)
            .join(Topic, Topic.id == ArticleTopic.topic_id)
            .join(anc, Topic.path.like(anc.c.path + "%"))
            .join(Article, Article.id == ArticleTopic.article_id)
            .group_by(anc.c.id, anc.c.name, day)
            .order_by(day, anc.c.name)
        )
        if parent_id is not None:
            stmt = stmt.where(anc.c.id == parent_id)
        if date_from and (parsed := _parse_date(date_from)):
            stmt = stmt.where(Article.published_at >= parsed)
        if date_to and (parsed := _parse_date(date_to)):
            stmt = stmt.where(Article.published_at < parsed + timedelta(days=1))
        return [
            TopicFrequencyRow(topic_id=r.id, name=r.name, day=str(r.day), count=r.count)
            for r in session.execute(stmt).all()
        ]
    finally:
        session.close()
