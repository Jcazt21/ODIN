"""El medio viaja con su nombre legible además del slug.

El slug (`listin_diario`) sigue siendo la clave de filtrado; `source_name` es
solo para pintar. Se prueba en la lista, en el detalle y en las facetas porque
cada una lo arma por su cuenta.
"""
from __future__ import annotations

from datetime import UTC, datetime

from odin.core.auth import create_token
from odin.db.models import Article


def _auth_headers():
    token, _ = create_token("tester")
    return {"Authorization": f"Bearer {token}"}


def _make_article(**overrides) -> Article:
    defaults = dict(
        source="listin_diario",
        url="https://listindiario.com/a",
        title="Título de prueba",
        body="cuerpo",
        overall_sentiment="NEU",
        published_at=datetime(2026, 1, 1, tzinfo=UTC),
    )
    defaults.update(overrides)
    return Article(**defaults)


class TestSourceNameInArticles:
    def test_list_rows_carry_the_display_name(self, api_client, sqlite_sessionmaker):
        session = sqlite_sessionmaker()
        session.add(_make_article())
        session.commit()
        session.close()

        resp = api_client.get("/api/articles", headers=_auth_headers())
        assert resp.status_code == 200
        row = resp.json()["items"][0]
        assert row["source"] == "listin_diario"
        assert row["source_name"] == "Listín Diario"

    def test_detail_carries_the_display_name(self, api_client, sqlite_sessionmaker):
        session = sqlite_sessionmaker()
        article = _make_article(source="el_dia", url="https://eldia.com.do/x")
        session.add(article)
        session.commit()
        article_id = article.id
        session.close()

        resp = api_client.get(f"/api/articles/{article_id}", headers=_auth_headers())
        assert resp.status_code == 200
        assert resp.json()["source_name"] == "El Día"


class TestSourceFacets:
    def test_facets_pair_each_slug_with_its_label(self, api_client, sqlite_sessionmaker):
        session = sqlite_sessionmaker()
        session.add_all([
            _make_article(source="listin_diario", url="https://listindiario.com/a"),
            _make_article(source="diario_libre", url="https://diariolibre.com/b"),
        ])
        session.commit()
        session.close()

        resp = api_client.get("/api/articles/filters", headers=_auth_headers())
        assert resp.status_code == 200
        sources = resp.json()["sources"]
        assert {s["value"]: s["label"] for s in sources} == {
            "diario_libre": "Diario Libre",
            "listin_diario": "Listín Diario",
        }

    def test_filtering_still_uses_the_slug(self, api_client, sqlite_sessionmaker):
        """La etiqueta es de presentación: el filtro sigue viajando con el slug."""
        session = sqlite_sessionmaker()
        session.add_all([
            _make_article(source="listin_diario", url="https://listindiario.com/a"),
            _make_article(source="diario_libre", url="https://diariolibre.com/b"),
        ])
        session.commit()
        session.close()

        resp = api_client.get(
            "/api/articles", params={"source": ["listin_diario"]}, headers=_auth_headers()
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["total"] == 1
        assert body["items"][0]["source_name"] == "Listín Diario"


class TestTopicFacet:
    def test_lists_distinct_topics_already_used(self, api_client, sqlite_sessionmaker):
        """Alimenta las sugerencias del campo Tema del formulario manual."""
        session = sqlite_sessionmaker()
        session.add_all([
            _make_article(url="https://listindiario.com/a", main_topic="agua potable"),
            _make_article(url="https://listindiario.com/b", main_topic="agua potable"),
            _make_article(url="https://listindiario.com/c", main_topic="energía"),
            _make_article(url="https://listindiario.com/d", main_topic=None),
        ])
        session.commit()
        session.close()

        resp = api_client.get("/api/articles/filters", headers=_auth_headers())

        assert resp.status_code == 200
        assert resp.json()["topics"] == ["agua potable", "energía"]
