"""Entidades canónicas (dimensión + fusión)."""
from __future__ import annotations

from fastapi import APIRouter, Depends, Query

from odin.core import auth
from odin.api.schemas import (
    CanonicalEntityDetailResponse,
    CanonicalEntityListResponse,
    CanonicalEntityMergePayload,
    CanonicalEntityResponse,
    CanonicalEntityUpdatePayload,
)
from odin.services import canonical_entity_service

router = APIRouter(tags=["canonical-entities"])


@router.get("/api/canonical-entities", response_model=CanonicalEntityListResponse)
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
    return canonical_entity_service.list_canonical_entities(q, type_, limit, offset)


@router.get("/api/canonical-entities/{entity_id}", response_model=CanonicalEntityDetailResponse)
def get_canonical_entity(entity_id: int):
    """Detalle de una entidad canónica: sus datos y los artículos donde
    aparece vinculada (vía Entity.canonical_entity_id), más recientes primero.
    Esta es la respuesta confiable a "¿cuántos artículos hablan de esta
    persona?" — agrupa por identidad real, no por string de nombre."""
    return canonical_entity_service.get_canonical_entity(entity_id)


@router.put(
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
    return canonical_entity_service.update_canonical_entity(entity_id, payload)


@router.post(
    "/api/canonical-entities/{entity_id}/merge",
    dependencies=[Depends(auth.require_auth)],
    response_model=CanonicalEntityResponse,
)
def merge_canonical_entities(entity_id: int, payload: CanonicalEntityMergePayload):
    """Fusiona `source_id` DENTRO de `entity_id`: reasigna todas las menciones
    (pasadas) que apuntaban a `source_id` y la borra. Es la corrección manual
    que el pipeline no puede inferir solo (dos nombres que en realidad son la
    misma figura, creados como filas separadas)."""
    return canonical_entity_service.merge_canonical_entities(entity_id, payload)
