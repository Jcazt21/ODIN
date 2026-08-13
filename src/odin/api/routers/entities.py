"""Menciones de entidad individuales (por artículo): rectificación y borrado
(§8.2 de task.md)."""
from __future__ import annotations

from fastapi import APIRouter, Depends

from odin.core import auth
from odin.api.schemas import EntityMention, EntityUpdatePayload
from odin.services import entity_service

router = APIRouter(tags=["entities"])


@router.put(
    "/api/entities/{entity_id}",
    dependencies=[Depends(auth.require_auth)],
    response_model=EntityMention,
)
def update_entity(entity_id: int, payload: EntityUpdatePayload):
    """Rectifica una mención puntual (§8.2): nombre mal extraído, sentimiento
    mal inferido... sin tener que borrar y re-analizar todo el artículo.
    Devuelve 409 si el cambio choca con otra mención ya existente en el mismo
    artículo (mismo nombre + tipo)."""
    return entity_service.update_entity(entity_id, payload)


@router.delete(
    "/api/entities/{entity_id}", status_code=204, dependencies=[Depends(auth.require_auth)]
)
def delete_entity(entity_id: int):
    """Borra una mención puntual (§8.2): redacta el juicio sobre una persona en
    UN artículo sin borrar el artículo completo."""
    entity_service.delete_entity(entity_id)
