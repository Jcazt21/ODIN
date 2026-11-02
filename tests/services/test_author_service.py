from __future__ import annotations

from datetime import datetime

from odin.db.models import Article
from odin.services.author_service import list_authors, split_authors


def _art(n, authors, source="diario_libre", day=1):
    return Article(
        source=source, url=f"https://x/{n}", title=f"t{n}", body="b",
        authors=authors, published_at=datetime(2026, 1, day, 12),
    )


def test_split_two_authors():
    assert split_authors("Ana Pérez, Luis Soto") == ["Ana Pérez", "Luis Soto"]


def test_split_empty_values():
    assert split_authors(None) == []
    assert split_authors("") == []
    assert split_authors("  ") == []


def test_split_dedupes_variants():
    assert split_authors("ANA PEREZ, Ana Pérez") == ["ANA PEREZ"]


def test_aggregates_counts_sources_last(db_session):
    db_session.add_all([
        _art(1, "Ana Pérez", "diario_libre", 1),
        _art(2, "ana perez", "listin", 5),
        _art(3, "Ana Pérez, Luis Soto", "diario_libre", 3),
    ])
    db_session.commit()
    res = list_authors(db_session)
    by = {a.name: a for a in res.items}
    ana = by["Ana Pérez"]  # variante más frecuente
    assert ana.article_count == 3
    assert ana.sources == ["diario_libre", "listin"]
    assert ana.last_published_at == datetime(2026, 1, 5, 12)
    assert by["Luis Soto"].article_count == 1
    assert res.total == 2


def test_filters_q_source_dates(db_session):
    db_session.add_all([
        _art(1, "Ana Pérez", "diario_libre", 1),
        _art(2, "Ana Pérez", "listin", 10),
        _art(3, "Mariano Gómez", "listin", 10),
    ])
    db_session.commit()
    assert [a.name for a in list_authors(db_session, q="perez").items] == ["Ana Pérez"]
    assert list_authors(db_session, source="listin").total == 2
    ana = [a for a in list_authors(db_session, source="listin").items if a.name == "Ana Pérez"][0]
    assert ana.article_count == 1
    res = list_authors(db_session, date_from="2026-01-05", date_to="2026-01-10")
    assert {a.name for a in res.items} == {"Ana Pérez", "Mariano Gómez"}
    assert next(a for a in res.items if a.name == "Ana Pérez").article_count == 1


def test_sort_and_pagination(db_session):
    db_session.add_all([
        _art(1, "Zeta"), _art(2, "Beta"), _art(3, "Beta"), _art(4, "Alfa"),
    ])
    db_session.commit()
    assert [a.name for a in list_authors(db_session).items] == ["Beta", "Alfa", "Zeta"]
    assert [a.name for a in list_authors(db_session, sort="name").items] == ["Alfa", "Beta", "Zeta"]
    page = list_authors(db_session, sort="name", limit=1, offset=1)
    assert [a.name for a in page.items] == ["Beta"]
    assert page.total == 3
