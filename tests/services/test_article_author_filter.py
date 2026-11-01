from __future__ import annotations

from sqlalchemy import select

import odin.api  # noqa: F401  (orden de import: evita el ciclo api <-> services)
from odin.db.models import Article
from odin.services.article_service import _apply_article_filters


def _ids(session, **kw):
    base = dict(source=None, sentiment=None, framing=None, headline_intent=None,
                lead_orientation=None, source_quality=None, has_hard_data=None,
                date_from=None, date_to=None, q=None, entity=None)
    base.update(kw)
    stmt = _apply_article_filters(select(Article.title), **base)
    return sorted(session.scalars(stmt).all())


def _seed(db_session):
    db_session.add_all([
        Article(source="a", url="https://x/1", title="uno", body="b", authors="Ana Pérez, Luis Soto"),
        Article(source="b", url="https://x/2", title="dos", body="b", authors="Mariana Gómez"),
        Article(source="a", url="https://x/3", title="tres", body="b", authors="Ana"),
    ])
    db_session.commit()


def test_author_is_token_not_substring(db_session):
    _seed(db_session)
    assert _ids(db_session, author="Ana") == ["tres"]


def test_author_in_list_accent_case_insensitive(db_session):
    _seed(db_session)
    assert _ids(db_session, author="luis soto") == ["uno"]
    assert _ids(db_session, author="ANA PEREZ") == ["uno"]


def test_author_combines_with_source(db_session):
    _seed(db_session)
    assert _ids(db_session, author="Luis Soto", source=["b"]) == []
    assert _ids(db_session, author="Luis Soto", source=["a"]) == ["uno"]
