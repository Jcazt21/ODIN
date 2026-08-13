"""CRUD de siglas."""
from __future__ import annotations

from fastapi import APIRouter, Depends

from odin.core import auth
from api.schemas import AliasPayload, AliasUpdatePayload, EntityAliasResponse
from services import alias_service

router = APIRouter(tags=["aliases"])


@router.get("/api/aliases", response_model=list[EntityAliasResponse])
def list_aliases(q: str | None = None, limit: int = 500, offset: int = 0):
    return alias_service.list_aliases(q, limit, offset)


@router.post(
    "/api/aliases",
    status_code=201,
    dependencies=[Depends(auth.require_auth)],
    response_model=EntityAliasResponse,
)
def create_alias(payload: AliasPayload):
    """Crea un nuevo alias. Devuelve 409 si la sigla ya existe (mismo tipo)."""
    return alias_service.create_alias(payload)


@router.put(
    "/api/aliases/{alias_id}",
    dependencies=[Depends(auth.require_auth)],
    response_model=EntityAliasResponse,
)
def update_alias(alias_id: int, payload: AliasUpdatePayload):
    """Actualiza parcialmente un alias (nombre canónico, estado activo/inactivo...)."""
    return alias_service.update_alias(alias_id, payload)


@router.delete(
    "/api/aliases/{alias_id}", status_code=204, dependencies=[Depends(auth.require_auth)]
)
def delete_alias(alias_id: int):
    """Elimina permanentemente un alias."""
    alias_service.delete_alias(alias_id)
