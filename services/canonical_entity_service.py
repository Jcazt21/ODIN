"""Lógica de negocio de entidades canónicas: dimensión "persona/organización
real" (no menciones por artículo), listado con conteos, detalle y fusión
(§9.2 de task.md)."""
from __future__ import annotations

from fastapi import HTTPException
from sqlalchemy import func, select

import db.canonical_entities as canonical_entity_store
from analysis.canonicalize import invalidate_person_map
from api import deps
from api.deps import log
from api.schemas import (
    CanonicalEntityArticleMention,
    CanonicalEntityDetailResponse,
    CanonicalEntityListResponse,
    CanonicalEntityMergePayload,
    CanonicalEntityResponse,
    CanonicalEntityUpdatePayload,
)
from db.models import Article, CanonicalEntity, Entity
from services.article_service import accent_insensitive_contains


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


def list_canonical_entities(
    q: str | None, type_: str | None, limit: int, offset: int
) -> CanonicalEntityListResponse:
    """Lista entidades canónicas (la dimensión "persona/organización real",
    no menciones por artículo) con cuántos artículos y menciones acumula cada
    una. Puede haber más de una fila para la misma figura real si se creó
    antes de que la heurística de nombre único las uniera ("Abinader" y
    "Luis Abinader" por separado) — usa merge_canonical_entities para
    fusionarlas."""
    limit = max(1, min(limit, 200))
    offset = max(0, offset)
    session = deps.get_session()
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
            stmt = stmt.where(accent_insensitive_contains(CanonicalEntity.name, q))

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


def get_canonical_entity(entity_id: int) -> CanonicalEntityDetailResponse:
    """Detalle de una entidad canónica: sus datos y los artículos donde
    aparece vinculada (vía Entity.canonical_entity_id), más recientes primero.
    Esta es la respuesta confiable a "¿cuántos artículos hablan de esta
    persona?" — agrupa por identidad real, no por string de nombre."""
    session = deps.get_session()
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
                    sentiment_score=mention.sentiment_score,
                    mentions_count=mention.mentions_count,
                )
                for mention, article in mention_rows
            ],
        )
    except HTTPException:
        raise
    finally:
        session.close()


def update_canonical_entity(
    entity_id: int, payload: CanonicalEntityUpdatePayload
) -> CanonicalEntityResponse:
    """Renombra y/o describe una entidad canónica. El nombre nuevo entra a
    `known_person_fullname_map()` en el siguiente análisis (ver
    analysis/canonicalize.py): la corrección se propaga hacia adelante, no
    solo en los reportes ya guardados. Devuelve 409 si el nombre nuevo choca
    con otra entidad canónica ya existente del mismo tipo — en ese caso hace
    falta fusionar (merge_canonical_entities), no renombrar."""
    session = deps.get_session()
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
        invalidate_person_map()  # un renombrado manual pesa en el próximo análisis
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


def merge_canonical_entities(
    entity_id: int, payload: CanonicalEntityMergePayload
) -> CanonicalEntityResponse:
    """Fusiona `source_id` DENTRO de `entity_id`: reasigna todas las menciones
    (pasadas) que apuntaban a `source_id` y la borra. Es la corrección manual
    que el pipeline no puede inferir solo (dos nombres que en realidad son la
    misma figura, creados como filas separadas)."""
    session = deps.get_session()
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
        invalidate_person_map()
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
