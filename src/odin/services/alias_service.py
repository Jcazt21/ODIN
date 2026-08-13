"""Lógica de negocio del CRUD de siglas (§9.2 de task.md)."""
from __future__ import annotations

from fastapi import HTTPException
from sqlalchemy import or_, select

import odin.db.aliases as alias_store
from odin.api import deps
from odin.api.deps import log
from odin.api.schemas import AliasPayload, AliasUpdatePayload, EntityAliasResponse
from odin.db.models import EntityAlias
from odin.services.article_service import accent_insensitive_contains


def list_aliases(q: str | None, limit: int, offset: int) -> list[EntityAliasResponse]:
    """Devuelve alias activos e inactivos, filtrados en SQL (?q=) y paginados.
    `limit` por defecto es generoso (500, tope 1000) para no cambiar el
    comportamiento actual del frontend, que espera la lista completa."""
    limit = max(1, min(limit, 1000))
    offset = max(0, offset)
    session = deps.get_session()
    try:
        stmt = select(EntityAlias)
        if q:
            stmt = stmt.where(
                or_(
                    accent_insensitive_contains(EntityAlias.alias, q),
                    accent_insensitive_contains(EntityAlias.canonical_name, q),
                )
            )
        rows = session.scalars(
            stmt.order_by(EntityAlias.alias).limit(limit).offset(offset)
        ).all()
        return [EntityAliasResponse.model_validate(r) for r in rows]
    finally:
        session.close()


def create_alias(payload: AliasPayload) -> EntityAliasResponse:
    """Crea un nuevo alias. Devuelve 409 si la sigla ya existe (mismo tipo)."""
    alias_key = alias_store.normalize_key(payload.alias)
    session = deps.get_session()
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


def update_alias(alias_id: int, payload: AliasUpdatePayload) -> EntityAliasResponse:
    """Actualiza parcialmente un alias (nombre canónico, estado activo/inactivo...)."""
    session = deps.get_session()
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


def delete_alias(alias_id: int) -> None:
    """Elimina permanentemente un alias."""
    session = deps.get_session()
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
