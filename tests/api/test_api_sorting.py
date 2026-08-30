"""Orden del listado de reportes por columna.

`sort` era campo y dirección en un mismo valor ("recent" = published_at desc).
Con tres columnas ordenables eso se vuelve un enum que crece por combinatoria,
así que se separó: `sort` es el campo y `order` la dirección. "recent" y
"oldest" siguen aceptándose para no romper enlaces guardados.
"""
from __future__ import annotations

from datetime import UTC, date, datetime

from odin.core.auth import create_token
from odin.db.models import Article


def _auth():
    token, _ = create_token("tester")
    return {"Authorization": f"Bearer {token}"}


def _seed(sqlite_sessionmaker):
    session = sqlite_sessionmaker()
    session.add_all([
        Article(
            source="listin_diario",
            url="https://listindiario.com/a",
            title="A",
            body="x",
            published_at=datetime(2026, 1, 3, tzinfo=UTC),
            analyzed_on=date(2026, 2, 1),
        ),
        Article(
            source="acento",
            url="https://acento.com.do/b",
            title="B",
            body="x",
            published_at=datetime(2026, 1, 1, tzinfo=UTC),
            analyzed_on=date(2026, 2, 5),
        ),
        Article(
            source="diario_libre",
            url="https://diariolibre.com/c",
            title="C",
            body="x",
            published_at=datetime(2026, 1, 2, tzinfo=UTC),
            analyzed_on=None,  # nadie lo trabajó todavía
        ),
    ])
    session.commit()
    session.close()


def _titles(api_client, **params) -> list[str]:
    resp = api_client.get("/api/articles", params=params, headers=_auth())
    assert resp.status_code == 200, resp.text
    return [i["title"] for i in resp.json()["items"]]


class TestBackwardCompatibility:
    def test_recent_still_means_newest_first(self, api_client, sqlite_sessionmaker):
        _seed(sqlite_sessionmaker)
        assert _titles(api_client, sort="recent") == ["A", "C", "B"]

    def test_oldest_still_means_oldest_first(self, api_client, sqlite_sessionmaker):
        _seed(sqlite_sessionmaker)
        assert _titles(api_client, sort="oldest") == ["B", "C", "A"]

    def test_no_sort_is_newest_first(self, api_client, sqlite_sessionmaker):
        _seed(sqlite_sessionmaker)
        assert _titles(api_client) == ["A", "C", "B"]


class TestSortBySource:
    def test_ascending(self, api_client, sqlite_sessionmaker):
        _seed(sqlite_sessionmaker)
        # acento < diario_libre < listin_diario
        assert _titles(api_client, sort="source", order="asc") == ["B", "C", "A"]

    def test_descending(self, api_client, sqlite_sessionmaker):
        _seed(sqlite_sessionmaker)
        assert _titles(api_client, sort="source", order="desc") == ["A", "C", "B"]


class TestSortByAnalyzedOn:
    def test_descending_puts_the_most_recently_worked_first(self, api_client, sqlite_sessionmaker):
        _seed(sqlite_sessionmaker)
        titles = _titles(api_client, sort="analyzed_on", order="desc")
        assert titles[:2] == ["B", "A"]

    def test_unworked_reports_go_last_in_both_directions(self, api_client, sqlite_sessionmaker):
        """C no tiene fecha de análisis. Sin esto, descendente lo pondría
        arriba y la primera pantalla serían reportes vacíos."""
        _seed(sqlite_sessionmaker)

        assert _titles(api_client, sort="analyzed_on", order="desc")[-1] == "C"
        assert _titles(api_client, sort="analyzed_on", order="asc")[-1] == "C"


class TestRejectsNonsense:
    def test_an_unknown_field_is_refused(self, api_client, sqlite_sessionmaker):
        _seed(sqlite_sessionmaker)
        resp = api_client.get(
            "/api/articles", params={"sort": "password_hash"}, headers=_auth()
        )
        assert resp.status_code == 422

    def test_an_unknown_direction_is_refused(self, api_client, sqlite_sessionmaker):
        _seed(sqlite_sessionmaker)
        resp = api_client.get(
            "/api/articles", params={"sort": "source", "order": "sideways"}, headers=_auth()
        )
        assert resp.status_code == 422
