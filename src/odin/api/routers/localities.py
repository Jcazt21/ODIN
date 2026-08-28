"""Catálogo geográfico y lugar de la noticia."""
from __future__ import annotations

from fastapi import APIRouter, Depends

from odin.api.schemas import (
    ArticleLocalityPayload,
    ArticleLocalityResponse,
    LocalityNode,
    LocalityPayload,
    LocalityResponse,
    LocalityUpdatePayload,
)
from odin.core import auth
from odin.services import locality_service

router = APIRouter(tags=["localities"])


@router.get("/api/localities/tree", response_model=list[LocalityNode])
def locality_tree(include_inactive: bool = False):
    """Árbol completo país→municipio, para el selector en cascada."""
    return locality_service.get_tree(include_inactive=include_inactive)


@router.get("/api/localities", response_model=list[LocalityResponse])
def list_localities(
    q: str | None = None,
    level: str | None = None,
    parent_id: int | None = None,
    limit: int = 200,
    offset: int = 0,
):
    """Busca lugares por nombre (sin importar acentos), nivel o lugar padre."""
    return locality_service.list_localities(q, level, parent_id, limit, offset)


@router.post(
    "/api/localities",
    status_code=201,
    dependencies=[Depends(auth.require_auth)],
    response_model=LocalityResponse,
)
def create_locality(payload: LocalityPayload):
    """Agrega un lugar al catálogo (p. ej. un municipio creado por ley)."""
    return locality_service.create_locality(payload)


@router.put(
    "/api/localities/{locality_id}",
    dependencies=[Depends(auth.require_auth)],
    response_model=LocalityResponse,
)
def update_locality(locality_id: int, payload: LocalityUpdatePayload):
    """Renombra o desactiva un lugar del catálogo."""
    return locality_service.update_locality(locality_id, payload)


@router.get("/api/localities/frequency")
def locality_frequency(
    level: str = "PROVINCIA",
    date_from: str | None = None,
    date_to: str | None = None,
    kind: str = "HECHO",
):
    """Noticias por lugar, agregadas al nivel pedido.

    Con roll-up: una nota marcada en un municipio cuenta también para su
    provincia, su región y el país.
    """
    return locality_service.frequency_by_locality(level, date_from, date_to, kind)


@router.get(
    "/api/articles/{article_id}/localities", response_model=list[ArticleLocalityResponse]
)
def list_article_localities(article_id: int):
    return locality_service.list_article_localities(article_id)


@router.post(
    "/api/articles/{article_id}/localities",
    status_code=201,
    dependencies=[Depends(auth.require_auth)],
    response_model=ArticleLocalityResponse,
)
def add_article_locality(article_id: int, payload: ArticleLocalityPayload):
    """Vincula un lugar al artículo (el botón "Agregar" del formulario)."""
    return locality_service.add_article_locality(article_id, payload)


@router.put(
    "/api/articles/{article_id}/localities",
    dependencies=[Depends(auth.require_auth)],
    response_model=list[ArticleLocalityResponse],
)
def replace_article_localities(article_id: int, payload: list[ArticleLocalityPayload]):
    """Deja el artículo exactamente con los lugares enviados."""
    return locality_service.replace_article_localities(article_id, payload)


@router.delete(
    "/api/articles/{article_id}/localities/{link_id}",
    status_code=204,
    dependencies=[Depends(auth.require_auth)],
)
def delete_article_locality(article_id: int, link_id: int):
    locality_service.delete_article_locality(article_id, link_id)
