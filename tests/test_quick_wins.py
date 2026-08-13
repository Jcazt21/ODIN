"""Pruebas de los quick wins de task.md §11 (#2, #3, #4, #5, #10):

  #2  init_db() ya no se llama en POST /api/articles (solo en el lifespan).
  #3  el listado no dispara N+1 al calcular entity_count.
  #4  list_aliases filtra en SQL (no en Python) y pagina.
  #5  '%' y '_' del usuario se tratan como texto literal en ILIKE.
  #10 /api/health refleja un fallo real de conexión a la BD.
"""
from __future__ import annotations

from sqlalchemy import event

import odin.analysis.canonicalize as canonicalize
import odin.db.session as db_session_module
from odin.core.auth import create_token
from odin.db.models import Article, Entity, EntityAlias


def _make_article(**overrides) -> Article:
    defaults = dict(
        source="diario_libre",
        url=f"https://diariolibre.com/{id(overrides)}",
        title="Título de prueba",
        body="cuerpo",
    )
    defaults.update(overrides)
    return Article(**defaults)


# ── #5: comodines de ILIKE escapados ─────────────────────────────────────────


class TestLikeEscaping:
    def test_percent_in_q_is_literal_not_wildcard(self, api_client, sqlite_sessionmaker):
        session = sqlite_sessionmaker()
        session.add_all([
            _make_article(url="https://diariolibre.com/pct", title="Aumento del 50% en ventas"),
            _make_article(url="https://diariolibre.com/other", title="Aumento del 50X en ventas"),
        ])
        session.commit()
        session.close()

        resp = api_client.get("/api/articles", params={"q": "50%"})
        body = resp.json()
        assert body["total"] == 1
        assert body["items"][0]["url"] == "https://diariolibre.com/pct"

    def test_underscore_in_entity_filter_is_literal(self, api_client, sqlite_sessionmaker):
        session = sqlite_sessionmaker()
        a = _make_article(url="https://diariolibre.com/us")
        a.entities.append(Entity(name="foo_bar", type="ORG", mentions_count=1))
        b = _make_article(url="https://diariolibre.com/us2")
        b.entities.append(Entity(name="fooXbar", type="ORG", mentions_count=1))
        session.add_all([a, b])
        session.commit()
        session.close()

        resp = api_client.get("/api/articles", params={"entity": "foo_bar"})
        body = resp.json()
        assert body["total"] == 1
        assert body["items"][0]["url"] == "https://diariolibre.com/us"


# ── #4: list_aliases filtra en SQL y pagina ──────────────────────────────────


class TestListAliases:
    def test_filters_in_sql_by_alias_or_canonical_name(self, api_client, sqlite_sessionmaker):
        session = sqlite_sessionmaker()
        session.add_all([
            EntityAlias(alias="MINERD", alias_key="minerd", canonical_name="Ministerio de Educación", type="ORG"),
            EntityAlias(alias="PRM", alias_key="prm", canonical_name="Partido Revolucionario Moderno", type="ORG"),
        ])
        session.commit()
        session.close()

        resp = api_client.get("/api/aliases", params={"q": "minerd"})
        body = resp.json()
        assert len(body) == 1
        assert body[0]["alias"] == "MINERD"

    def test_pagination_with_limit_and_offset(self, api_client, sqlite_sessionmaker):
        session = sqlite_sessionmaker()
        session.add_all([
            EntityAlias(alias=f"A{i}", alias_key=f"a{i}", canonical_name=f"Nombre {i}", type="ORG")
            for i in range(10)
        ])
        session.commit()
        session.close()

        page1 = api_client.get("/api/aliases", params={"limit": 3, "offset": 0}).json()
        page2 = api_client.get("/api/aliases", params={"limit": 3, "offset": 9}).json()
        assert len(page1) == 3
        assert len(page2) == 1


# ── #3: sin N+1 al listar artículos ──────────────────────────────────────────


class TestNoNPlusOne:
    def test_entity_count_does_not_trigger_one_query_per_article(self, api_client, sqlite_sessionmaker):
        session = sqlite_sessionmaker()
        for i in range(5):
            article = _make_article(url=f"https://diariolibre.com/nplus1-{i}")
            article.entities.append(Entity(name=f"Entidad {i}", type="ORG", mentions_count=1))
            article.entities.append(Entity(name=f"Otra {i}", type="PERSON", mentions_count=1))
            session.add(article)
        session.commit()
        engine = session.get_bind()
        session.close()

        statements: list[str] = []

        def _record(conn, cursor, statement, parameters, context, executemany):
            statements.append(statement)

        event.listen(engine, "before_cursor_execute", _record)
        try:
            resp = api_client.get("/api/articles", params={"limit": 100})
        finally:
            event.remove(engine, "before_cursor_execute", _record)

        body = resp.json()
        assert len(body["items"]) == 5
        assert all(item["entity_count"] == 2 for item in body["items"])
        # Sin selectinload esto sería count(1) + select(1) + 5 lazy-loads (7+).
        # Con selectinload debe quedarse en un puñado fijo de queries.
        assert len(statements) <= 4, statements


# ── #2: init_db() fuera del hot path de guardado ─────────────────────────────


class TestInitDbNotOnHotPath:
    def test_save_article_does_not_call_init_db(self, monkeypatch, api_client, sqlite_sessionmaker):
        import odin.api as api_module

        monkeypatch.setattr(db_session_module, "get_session", sqlite_sessionmaker)
        monkeypatch.setattr(canonicalize.alias_store, "resolve", lambda name: None)
        monkeypatch.setattr(canonicalize.alias_store, "all_canonicals", lambda: [])

        calls: list[int] = []
        monkeypatch.setattr(api_module, "init_db", lambda: calls.append(1))

        token, _ = create_token("tester")
        resp = api_client.post(
            "/api/articles",
            json={
                "source": "manual",
                "url": "https://diariolibre.com/nuevo-articulo",
                "title": "Título",
                "body": "cuerpo del artículo",
            },
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 200
        assert calls == []


# ── #10: /api/health refleja el estado real de la BD ─────────────────────────


class TestHealthCheck:
    def test_ok_when_db_reachable(self, api_client):
        resp = api_client.get("/api/health")
        assert resp.status_code == 200
        assert resp.json() == {"status": "ok"}

    def test_503_when_db_unreachable(self, monkeypatch):
        from fastapi.testclient import TestClient

        import odin.api as api_module
        import odin.api.deps as api_deps

        class _BrokenSession:
            def execute(self, *_args, **_kwargs):
                raise RuntimeError("sin conexión")

            def close(self):
                pass

        monkeypatch.setattr(api_deps, "get_session", lambda: _BrokenSession())
        client = TestClient(api_module.app)

        resp = client.get("/api/health")
        assert resp.status_code == 503
