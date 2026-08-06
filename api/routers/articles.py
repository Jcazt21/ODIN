"""CRUD de reportes guardados: listado con filtros, detalle, rectificación y
borrado (§8.2 de task.md), y guardado del resultado de /api/analyze."""
from __future__ import annotations

from fastapi import APIRouter, Depends, Query

import auth
from api.schemas import (
    ArticleDetail,
    ArticleFiltersResponse,
    ArticleListResponse,
    ArticleUpdatePayload,
    SaveArticleRequest,
)
from services import article_service

router = APIRouter(tags=["articles"])


@router.get("/api/articles", response_model=ArticleListResponse)
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
    return article_service.list_articles(
        q=q,
        source=source,
        sentiment=sentiment,
        framing=framing,
        headline_intent=headline_intent,
        lead_orientation=lead_orientation,
        source_quality=source_quality,
        has_hard_data=has_hard_data,
        entity=entity,
        date_from=date_from,
        date_to=date_to,
        sort=sort,
        limit=limit,
        offset=offset,
    )


@router.get("/api/articles/filters", response_model=ArticleFiltersResponse)
def article_filters():
    """Valores disponibles para poblar los selectores de filtro del frontend.
    Fuentes y secciones son dinámicas (dependen de lo ya guardado); el resto
    de campos de encuadre son enumeraciones fijas del análisis."""
    return article_service.article_filters()


@router.get("/api/articles/{article_id}", response_model=ArticleDetail)
def get_article(article_id: int):
    """Reporte completo (con entidades) de un artículo ya guardado."""
    return article_service.get_article(article_id)


@router.put(
    "/api/articles/{article_id}",
    dependencies=[Depends(auth.require_auth)],
    response_model=ArticleDetail,
)
def update_article(article_id: int, payload: ArticleUpdatePayload):
    """Rectifica el análisis de un artículo ya guardado (§8.2): tema, encuadre,
    sentimiento, actores señalados... Solo toca los campos enviados. No permite
    corregir `title`/`body`/`url` porque eso es lo que decía la fuente, no un
    juicio del sistema — si el scrape en sí está mal, hay que borrar y volver a
    analizar."""
    return article_service.update_article(article_id, payload)


@router.delete(
    "/api/articles/{article_id}", status_code=204, dependencies=[Depends(auth.require_auth)]
)
def delete_article(article_id: int):
    """Borra permanentemente un artículo y sus menciones (§8.2): no hay
    archivado ni papelera — es el procedimiento de borrado que el cliente
    puede exigir sobre su propio contenido o el de una persona nombrada."""
    article_service.delete_article(article_id)


@router.post("/api/articles", dependencies=[Depends(auth.require_auth)], response_model=ArticleDetail)
def save_article(req: SaveArticleRequest):
    """Persiste el resultado de /api/analyze, ya revisado/corregido."""
    return article_service.save_article(req)
