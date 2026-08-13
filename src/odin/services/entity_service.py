"""Lógica de negocio de menciones de entidad individuales (§8.2 de task.md,
§9.2): rectificar o borrar una mención puntual sin re-analizar el artículo
completo."""
from __future__ import annotations

from fastapi import HTTPException
from sqlalchemy import select

from odin.analysis.canonicalize import invalidate_person_map
from odin.api import deps
from odin.api.deps import log
from odin.api.schemas import EntityMention, EntityUpdatePayload
from odin.db.models import Entity


def update_entity(entity_id: int, payload: EntityUpdatePayload) -> EntityMention:
    """Rectifica una mención puntual (§8.2): nombre mal extraído, sentimiento
    mal inferido... sin tener que borrar y re-analizar todo el artículo.
    Devuelve 409 si el cambio choca con otra mención ya existente en el mismo
    artículo (mismo nombre + tipo)."""
    session = deps.get_session()
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
        invalidate_person_map()  # el nombre corregido entra al mapa de apellidos
        return EntityMention.model_validate(entity)
    except HTTPException:
        raise
    except Exception:
        session.rollback()
        log.exception("entity_rectification_failed", entity_id=entity_id)
        raise HTTPException(status_code=500, detail="Error interno rectificando la mención.") from None
    finally:
        session.close()


def delete_entity(entity_id: int) -> None:
    """Borra una mención puntual (§8.2): redacta el juicio sobre una persona en
    UN artículo sin borrar el artículo completo."""
    session = deps.get_session()
    try:
        entity = session.scalar(select(Entity).where(Entity.id == entity_id))
        if not entity:
            raise HTTPException(status_code=404, detail="Mención no encontrada.")
        session.delete(entity)
        session.commit()
        invalidate_person_map()
    except HTTPException:
        raise
    except Exception:
        session.rollback()
        log.exception("entity_deletion_failed", entity_id=entity_id)
        raise HTTPException(status_code=500, detail="Error interno borrando la mención.") from None
    finally:
        session.close()
