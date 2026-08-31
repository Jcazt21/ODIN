"""CRUD de reportes guardados: listado con filtros, detalle, rectificación y
borrado (§8.2 de task.md), y guardado del resultado de /api/analyze."""
from __future__ import annotations

from fastapi import APIRouter, Depends, Query, Response

from odin.api.schemas import (
    ArticleDetail,
    ArticleFiltersResponse,
    ArticleListResponse,
    ArticleUpdatePayload,
    ExportRequest,
    SaveArticleRequest,
    SourceOption,
)
from odin.core import auth
from odin.services import article_service, export_service

router = APIRouter(tags=["articles"])


@router.get(
    "/api/articles",
    dependencies=[Depends(auth.require_auth)],
    response_model=ArticleListResponse,
)
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
    topic: str | None = None,
    locality: int | None = None,
    documentalist: int | None = None,
    date_from: str | None = None,
    date_to: str | None = None,
    sort: str | None = None,
    order: str | None = None,
    limit: int = 20,
    offset: int = 0,
):
    """Lista reportes guardados con filtros combinables. Devuelve resúmenes
    (sin cuerpo ni entidades detalladas); usa GET /api/articles/{id} para el
    reporte completo.

    `locality` es el id de un lugar del catálogo e incluye su subárbol: filtrar
    por la provincia Santiago trae también lo marcado en sus municipios.
    `documentalist` es el id del documentalista que dejó guardado el reporte.

    `sort` es la columna (`published_at`, `source`, `analyzed_on`) y `order`
    la dirección (`asc`/`desc`). "recent" y "oldest" siguen aceptándose como
    alias del contrato anterior, donde `sort` mezclaba ambas cosas.
    """
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
        topic=topic,
        locality=locality,
        documentalist=documentalist,
        date_from=date_from,
        date_to=date_to,
        sort=sort,
        order=order,
        limit=limit,
        offset=offset,
    )


@router.get(
    "/api/articles/filters",
    dependencies=[Depends(auth.require_auth)],
    response_model=ArticleFiltersResponse,
)
def article_filters():
    """Valores disponibles para poblar los selectores de filtro del frontend.
    Fuentes y secciones son dinámicas (dependen de lo ya guardado); el resto
    de campos de encuadre son enumeraciones fijas del análisis."""
    return article_service.article_filters()


@router.get(
    "/api/sources",
    dependencies=[Depends(auth.require_auth)],
    response_model=list[SourceOption],
)
def list_sources():
    """Medios disponibles para el formulario de captura, desde el registro de
    scrapers. Ver `article_service.source_catalog` para por qué no reusa las
    facetas del filtro."""
    return article_service.source_catalog()


@router.post("/api/articles/export", dependencies=[Depends(auth.require_auth)])
def export_articles(req: ExportRequest):
    """Devuelve un documento de Word con los reportes seleccionados.

    Es el cierre del flujo que pidió el cliente: filtrar por documentalista, elegir
    los reportes y bajarlos.
    """
    content = export_service.export_articles(req.article_ids)
    return Response(
        content=content,
        media_type=(
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
        ),
        headers={"Content-Disposition": 'attachment; filename="reportes-odin.docx"'},
    )


# `export` va declarada antes de `GET /api/articles/{article_id}`: aunque hoy
# no colisionan porque son métodos distintos (POST vs GET), este orden evita
# que un futuro `GET /api/articles/export` caiga en la ruta paramétrica de abajo.
@router.get(
    "/api/articles/{article_id}",
    dependencies=[Depends(auth.require_auth)],
    response_model=ArticleDetail,
)
def get_article(article_id: int):
    """Reporte completo (con entidades) de un artículo ya guardado."""
    return article_service.get_article(article_id)


@router.put("/api/articles/{article_id}", response_model=ArticleDetail)
def update_article(
    article_id: int,
    payload: ArticleUpdatePayload,
    documentalist: str = Depends(auth.require_auth),
):
    """Rectifica el análisis de un artículo ya guardado (§8.2): tema, encuadre,
    sentimiento, actores señalados... Solo toca los campos enviados. No permite
    corregir `title`/`body`/`url` porque eso es lo que decía la fuente, no un
    juicio del sistema — si el scrape en sí está mal, hay que borrar y volver a
    analizar.

    Rectificar reasigna la autoría a quien corrige."""
    return article_service.update_article(article_id, payload, documentalist_username=documentalist)


@router.delete(
    "/api/articles/{article_id}", status_code=204, dependencies=[Depends(auth.require_auth)]
)
def delete_article(article_id: int):
    """Borra permanentemente un artículo y sus menciones (§8.2): no hay
    archivado ni papelera — es el procedimiento de borrado que el cliente
    puede exigir sobre su propio contenido o el de una persona nombrada."""
    article_service.delete_article(article_id)


@router.post("/api/articles", response_model=ArticleDetail, status_code=201)
def save_article(
    req: SaveArticleRequest,
    response: Response,
    documentalist: str = Depends(auth.require_auth),
):
    """Persiste el resultado de /api/analyze, ya revisado/corregido, y registra
    qué documentalista lo dejó guardado.

    201 si dio de alta el reporte, 200 si la URL ya estaba guardada y devuelve
    la existente. El formulario manual usa esa diferencia para avisar en vez de
    dar por bueno un guardado que no ocurrió.
    """
    detail, created = article_service.save_article(req, documentalist_username=documentalist)
    if not created:
        response.status_code = 200
    return detail
