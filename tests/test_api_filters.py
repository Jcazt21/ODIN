"""Pruebas de los filtros combinables de GET /api/articles (api.py).

Usan SQLite en memoria vía el fixture `api_client` (ver conftest.py) — nunca
la `DATABASE_URL` real, y sin disparar el `lifespan` de la app (no se llama
`init_db()` contra Postgres). Ningún test aquí toca `/api/analyze`: ese
endpoint cargaría spaCy/pysentimiento (o Gemini, prohibido por CLAUDE.md), y
no hace falta para probar filtros de lectura sobre datos ya guardados.
"""
from __future__ import annotations

from datetime import datetime

from db.models import Article, Entity


def _make_article(**overrides) -> Article:
    defaults = dict(
        source="diario_libre",
        url=f"https://diariolibre.com/{overrides.get('title', 'articulo')}-{id(overrides)}",
        title="Título de prueba",
        body="cuerpo",
        main_topic="tema",
        topic_keywords="clave1, clave2",
        overall_sentiment="NEU",
        sentiment_score=0.5,
        published_at=datetime(2026, 1, 1),
    )
    defaults.update(overrides)
    return Article(**defaults)


class TestSourceFilter:
    def test_filters_by_single_source(self, api_client, sqlite_sessionmaker):
        session = sqlite_sessionmaker()
        session.add_all([
            _make_article(source="diario_libre", url="https://diariolibre.com/a"),
            _make_article(source="listin_diario", url="https://listindiario.com/b"),
        ])
        session.commit()
        session.close()

        resp = api_client.get("/api/articles", params={"source": ["diario_libre"]})
        assert resp.status_code == 200
        body = resp.json()
        assert body["total"] == 1
        assert body["items"][0]["source"] == "diario_libre"

    def test_multiple_sources_are_ored(self, api_client, sqlite_sessionmaker):
        session = sqlite_sessionmaker()
        session.add_all([
            _make_article(source="diario_libre", url="https://diariolibre.com/a"),
            _make_article(source="listin_diario", url="https://listindiario.com/b"),
            _make_article(source="hoy", url="https://hoy.com.do/c"),
        ])
        session.commit()
        session.close()

        resp = api_client.get(
            "/api/articles", params={"source": ["diario_libre", "hoy"]}
        )
        assert resp.json()["total"] == 2


class TestSentimentAndFramingFilters:
    def test_filters_by_sentiment(self, api_client, sqlite_sessionmaker):
        session = sqlite_sessionmaker()
        session.add_all([
            _make_article(url="https://diariolibre.com/pos", overall_sentiment="POS"),
            _make_article(url="https://diariolibre.com/neg", overall_sentiment="NEG"),
        ])
        session.commit()
        session.close()

        resp = api_client.get("/api/articles", params={"sentiment": "POS"})
        body = resp.json()
        assert body["total"] == 1
        assert body["items"][0]["overall_sentiment"] == "POS"

    def test_filters_by_framing(self, api_client, sqlite_sessionmaker):
        session = sqlite_sessionmaker()
        session.add_all([
            _make_article(url="https://diariolibre.com/f1", framing="crisis_conflicto"),
            _make_article(url="https://diariolibre.com/f2", framing="logro_institucional"),
        ])
        session.commit()
        session.close()

        resp = api_client.get("/api/articles", params={"framing": "crisis_conflicto"})
        body = resp.json()
        assert body["total"] == 1
        assert body["items"][0]["framing"] == "crisis_conflicto"


class TestHasHardDataFilter:
    def test_null_never_matches_true_or_false(self, api_client, sqlite_sessionmaker):
        session = sqlite_sessionmaker()
        session.add_all([
            _make_article(url="https://diariolibre.com/t", has_hard_data=True),
            _make_article(url="https://diariolibre.com/f", has_hard_data=False),
            _make_article(url="https://diariolibre.com/n", has_hard_data=None),
        ])
        session.commit()
        session.close()

        resp_true = api_client.get("/api/articles", params={"has_hard_data": "true"})
        resp_false = api_client.get("/api/articles", params={"has_hard_data": "false"})
        assert resp_true.json()["total"] == 1
        assert resp_false.json()["total"] == 1


class TestDateRangeFilter:
    def test_range_is_inclusive_of_both_endpoints(self, api_client, sqlite_sessionmaker):
        session = sqlite_sessionmaker()
        session.add_all([
            _make_article(url="https://diariolibre.com/d9", published_at=datetime(2026, 1, 9)),
            _make_article(url="https://diariolibre.com/d10", published_at=datetime(2026, 1, 10)),
            _make_article(
                url="https://diariolibre.com/d12",
                published_at=datetime(2026, 1, 12, 23, 0),
            ),
            _make_article(url="https://diariolibre.com/d13", published_at=datetime(2026, 1, 13)),
        ])
        session.commit()
        session.close()

        resp = api_client.get(
            "/api/articles", params={"date_from": "2026-01-10", "date_to": "2026-01-12"}
        )
        body = resp.json()
        assert body["total"] == 2
        urls = {item["url"] for item in api_client.get(
            "/api/articles", params={"date_from": "2026-01-10", "date_to": "2026-01-12", "limit": 100}
        ).json()["items"]}
        assert urls == {"https://diariolibre.com/d10", "https://diariolibre.com/d12"}


class TestTextSearchFilter:
    def test_q_matches_title_case_insensitively(self, api_client, sqlite_sessionmaker):
        session = sqlite_sessionmaker()
        session.add_all([
            _make_article(url="https://diariolibre.com/agua", title="Crisis del agua potable"),
            _make_article(url="https://diariolibre.com/luz", title="Apagones en el sistema eléctrico"),
        ])
        session.commit()
        session.close()

        resp = api_client.get("/api/articles", params={"q": "AGUA"})
        body = resp.json()
        assert body["total"] == 1
        assert "agua" in body["items"][0]["title"].lower()


class TestEntityFilter:
    def test_filters_articles_by_entity_name_substring(self, api_client, sqlite_sessionmaker):
        session = sqlite_sessionmaker()
        a = _make_article(url="https://diariolibre.com/a")
        a.entities.append(Entity(name="Luis Abinader", type="PERSON", mentions_count=1))
        b = _make_article(url="https://diariolibre.com/b")
        b.entities.append(Entity(name="Leonel Fernández", type="PERSON", mentions_count=1))
        session.add_all([a, b])
        session.commit()
        session.close()

        resp = api_client.get("/api/articles", params={"entity": "Abinader"})
        body = resp.json()
        assert body["total"] == 1
        assert body["items"][0]["url"] == "https://diariolibre.com/a"

    def test_article_with_two_matching_entities_is_not_duplicated(self, api_client, sqlite_sessionmaker):
        session = sqlite_sessionmaker()
        c = _make_article(url="https://diariolibre.com/c")
        c.entities.append(Entity(name="Partido X", type="ORG", mentions_count=1))
        c.entities.append(Entity(name="Partido Y", type="ORG", mentions_count=1))
        session.add(c)
        session.commit()
        session.close()

        resp = api_client.get("/api/articles", params={"entity": "Partido"})
        body = resp.json()
        assert body["total"] == 1
        assert len(body["items"]) == 1


class TestPaginationAndSort:
    def test_pagination_respects_limit_and_offset(self, api_client, sqlite_sessionmaker):
        session = sqlite_sessionmaker()
        session.add_all(
            [
                _make_article(
                    url=f"https://diariolibre.com/p{i}",
                    published_at=datetime(2026, 1, i + 1),
                )
                for i in range(5)
            ]
        )
        session.commit()
        session.close()

        page1 = api_client.get("/api/articles", params={"limit": 2, "offset": 0}).json()
        page2 = api_client.get("/api/articles", params={"limit": 2, "offset": 2}).json()
        assert page1["total"] == 5
        assert len(page1["items"]) == 2
        assert len(page2["items"]) == 2
        ids_page1 = {item["id"] for item in page1["items"]}
        ids_page2 = {item["id"] for item in page2["items"]}
        assert ids_page1.isdisjoint(ids_page2)

    def test_limit_is_capped_at_100(self, api_client, sqlite_sessionmaker):
        resp = api_client.get("/api/articles", params={"limit": 500})
        assert resp.json()["limit"] == 100

    def test_sort_recent_vs_oldest(self, api_client, sqlite_sessionmaker):
        session = sqlite_sessionmaker()
        session.add_all([
            _make_article(url="https://diariolibre.com/old", published_at=datetime(2026, 1, 1)),
            _make_article(url="https://diariolibre.com/new", published_at=datetime(2026, 1, 20)),
        ])
        session.commit()
        session.close()

        recent = api_client.get("/api/articles", params={"sort": "recent"}).json()
        oldest = api_client.get("/api/articles", params={"sort": "oldest"}).json()
        assert recent["items"][0]["url"] == "https://diariolibre.com/new"
        assert oldest["items"][0]["url"] == "https://diariolibre.com/old"


class TestCombinedFilters:
    def test_source_and_sentiment_combine_with_and(self, api_client, sqlite_sessionmaker):
        session = sqlite_sessionmaker()
        session.add_all([
            _make_article(url="https://diariolibre.com/1", source="diario_libre", overall_sentiment="POS"),
            _make_article(url="https://diariolibre.com/2", source="diario_libre", overall_sentiment="NEG"),
            _make_article(url="https://listindiario.com/3", source="listin_diario", overall_sentiment="POS"),
        ])
        session.commit()
        session.close()

        resp = api_client.get(
            "/api/articles",
            params={"source": ["diario_libre"], "sentiment": "POS"},
        )
        body = resp.json()
        assert body["total"] == 1
        assert body["items"][0]["url"] == "https://diariolibre.com/1"


class TestFiltersEndpoint:
    def test_returns_dynamic_sources_and_static_enums(self, api_client, sqlite_sessionmaker):
        session = sqlite_sessionmaker()
        session.add(_make_article(url="https://diariolibre.com/x", source="diario_libre", section="Política"))
        session.commit()
        session.close()

        resp = api_client.get("/api/articles/filters")
        body = resp.json()
        assert "diario_libre" in body["sources"]
        assert "Política" in body["sections"]
        assert "POS" in body["sentiments"]
        assert "crisis_conflicto" in body["framing"]
