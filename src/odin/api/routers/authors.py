"""Listado de autores agrupados (solo lectura)."""
from __future__ import annotations

from typing import Literal

from fastapi import APIRouter, Depends

from odin.api import deps
from odin.api.schemas import AuthorListResponse
from odin.core import auth
from odin.services import author_service

router = APIRouter(tags=["authors"])


@router.get(
    "/api/authors",
    dependencies=[Depends(auth.require_auth)],
    response_model=AuthorListResponse,
)
def list_authors(
    q: str | None = None,
    source: str | None = None,
    date_from: str | None = None,
    date_to: str | None = None,
    sort: Literal["articles", "name"] = "articles",
    limit: int = 50,
    offset: int = 0,
):
    session = deps.get_session()
    try:
        return author_service.list_authors(
            session, q=q, source=source, date_from=date_from, date_to=date_to,
            sort=sort, limit=limit, offset=offset,
        )
    finally:
        session.close()
