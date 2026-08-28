"""Resumen de trabajo por documentalista.

Se apoya en `articles.analyzed_on` — la fecha en que la persona lo trabajó — y
no en `published_at`, que es cuándo lo publicó el medio: una nota del mes pasado
revisada hoy es trabajo de hoy.

Como `analyzed_on` ya es una fecha sin hora, agrupar por día es contar valores
distintos de la columna; no hace falta truncar nada en SQL.
"""
from __future__ import annotations

from datetime import date

from fastapi import HTTPException
from sqlalchemy import func, select

from odin.api import deps
from odin.api.schemas import DocumentalistKpiRow
from odin.db.models import Article, User


def _parse_day(value: str | None) -> date | None:
    """Acepta "AAAA-MM-DD"; cualquier otra cosa es un 422, no un filtro que se
    ignora en silencio y devuelve números que nadie sabe interpretar."""
    if not value:
        return None
    try:
        return date.fromisoformat(value)
    except ValueError:
        raise HTTPException(
            status_code=422, detail=f"Fecha inválida: '{value}'. Formato: AAAA-MM-DD."
        ) from None


def documentalist_kpi(date_from: str | None, date_to: str | None) -> list[DocumentalistKpiRow]:
    since = _parse_day(date_from)
    until = _parse_day(date_to)

    session = deps.get_session()
    try:
        stmt = (
            select(
                User.id,
                User.display_name,
                func.count(Article.id).label("articles"),
                func.min(Article.analyzed_on).label("first_on"),
                func.max(Article.analyzed_on).label("last_on"),
                func.count(func.distinct(Article.analyzed_on)).label("active_days"),
            )
            .select_from(Article)
            .join(User, User.id == Article.documentalist_id)
            .group_by(User.id, User.display_name)
            .order_by(func.count(Article.id).desc())
        )
        if since:
            stmt = stmt.where(Article.analyzed_on >= since)
        if until:
            # Inclusivo: `until` es un día completo, no un instante.
            stmt = stmt.where(Article.analyzed_on <= until)

        return [
            DocumentalistKpiRow(
                documentalist_id=row.id,
                display_name=row.display_name,
                articles=row.articles,
                first_on=row.first_on,
                last_on=row.last_on,
                active_days=row.active_days,
            )
            for row in session.execute(stmt).all()
        ]
    finally:
        session.close()
