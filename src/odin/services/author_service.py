"""Autores agrupados a partir de `articles.authors`.

La columna guarda los autores de cada nota separados por ", ". No hay tabla de
autores (decisión: agrupar en Python), así que el listado lee solo las tres
columnas necesarias y agrega en memoria.
"""
from __future__ import annotations

from collections import Counter
from datetime import datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from odin.analysis.text_norm import norm_key
from odin.api.schemas import AuthorListResponse, AuthorSummary
from odin.db.models import Article
from odin.scrapers.base import _parse_date

AUTHOR_SORTS = ("articles", "name")


def split_authors(text: str | None) -> list[str]:
    """Separa el texto de autores; descarta vacíos y variantes repetidas
    (mismo `norm_key`), conservando la primera grafía."""
    if not text:
        return []
    out: list[str] = []
    seen: set[str] = set()
    for part in text.split(","):
        name = part.strip()
        key = norm_key(name)
        if not key or key in seen:
            continue
        seen.add(key)
        out.append(name)
    return out


def list_authors(
    session: Session,
    *,
    q: str | None = None,
    source: str | None = None,
    date_from: str | None = None,
    date_to: str | None = None,
    sort: str = "articles",
    limit: int = 50,
    offset: int = 0,
) -> AuthorListResponse:
    limit = max(1, min(limit, 200))
    offset = max(0, offset)

    stmt = select(Article.authors, Article.source, Article.published_at).where(
        Article.authors.is_not(None)
    )
    if source:
        stmt = stmt.where(Article.source == source)
    if date_from and (parsed := _parse_date(date_from)):
        stmt = stmt.where(Article.published_at >= parsed)
    if date_to and (parsed := _parse_date(date_to)):
        stmt = stmt.where(Article.published_at < parsed + timedelta(days=1))

    variants: dict[str, Counter[str]] = {}
    sources: dict[str, set[str]] = {}
    counts: Counter[str] = Counter()
    last: dict[str, datetime] = {}
    for authors, src, published in session.execute(stmt):
        for name in split_authors(authors):
            key = norm_key(name)
            variants.setdefault(key, Counter())[name] += 1
            sources.setdefault(key, set()).add(src)
            counts[key] += 1
            if published is not None and (key not in last or published > last[key]):
                last[key] = published

    needle = norm_key(q) if q else ""
    items: list[AuthorSummary] = []
    for key, n in counts.items():
        if needle and needle not in key:
            continue
        # Variante más frecuente; en empate, la primera alfabéticamente.
        display = min(variants[key].items(), key=lambda kv: (-kv[1], kv[0]))[0]
        items.append(
            AuthorSummary(
                name=display,
                article_count=n,
                sources=sorted(sources[key]),
                last_published_at=last.get(key),
            )
        )

    if sort == "name":
        items.sort(key=lambda a: norm_key(a.name))
    else:
        items.sort(key=lambda a: (-a.article_count, norm_key(a.name)))
    return AuthorListResponse(items=items[offset : offset + limit], total=len(items))
