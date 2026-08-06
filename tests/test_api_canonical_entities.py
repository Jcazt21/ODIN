"""Pruebas de /api/canonical-entities (api.py): listado con conteos, detalle,
renombrado y fusión. SQLite en memoria vía `api_client`/`sqlite_sessionmaker`
(ver conftest.py), nunca la DATABASE_URL real."""
from __future__ import annotations

from datetime import datetime

from analysis.base import ANALYSIS_SCHEMA_VERSION
from auth import create_token
from db.models import Article, CanonicalEntity, Entity


def _make_article(**overrides) -> Article:
    defaults = dict(
        source="diario_libre",
        url=f"https://diariolibre.com/{overrides.get('url_suffix', id(overrides))}",
        title="Título de prueba",
        body="cuerpo",
        published_at=datetime(2026, 1, 1),
    )
    defaults.pop("url_suffix", None)
    defaults.update({k: v for k, v in overrides.items() if k != "url_suffix"})
    return Article(**defaults)


def _auth_headers():
    token, _ = create_token("tester")
    return {"Authorization": f"Bearer {token}"}


class TestListCanonicalEntities:
    def test_counts_articles_and_mentions_across_multiple_articles(
        self, api_client, sqlite_sessionmaker
    ):
        session = sqlite_sessionmaker()
        canonical = CanonicalEntity(name="Luis Abinader", type="PERSON")
        session.add(canonical)
        session.commit()

        a1 = _make_article(url="https://diariolibre.com/a1")
        a1.entities.append(
            Entity(name="Luis Abinader", type="PERSON", mentions_count=3, canonical_entity_id=canonical.id)
        )
        a2 = _make_article(url="https://diariolibre.com/a2")
        a2.entities.append(
            Entity(name="Abinader", type="PERSON", mentions_count=2, canonical_entity_id=canonical.id)
        )
        session.add_all([a1, a2])
        session.commit()
        session.close()

        resp = api_client.get("/api/canonical-entities")
        assert resp.status_code == 200
        body = resp.json()
        assert body["total"] == 1
        item = body["items"][0]
        assert item["name"] == "Luis Abinader"
        assert item["article_count"] == 2
        assert item["total_mentions"] == 5

    def test_filters_by_type_and_search(self, api_client, sqlite_sessionmaker):
        session = sqlite_sessionmaker()
        session.add_all([
            CanonicalEntity(name="Luis Abinader", type="PERSON"),
            CanonicalEntity(name="MINERD", type="ORG"),
        ])
        session.commit()
        session.close()

        resp = api_client.get("/api/canonical-entities", params={"type": "ORG"})
        body = resp.json()
        assert body["total"] == 1
        assert body["items"][0]["name"] == "MINERD"

        resp2 = api_client.get("/api/canonical-entities", params={"q": "abinader"})
        assert resp2.json()["total"] == 1

    def test_entity_with_no_mentions_shows_zero_counts(self, api_client, sqlite_sessionmaker):
        session = sqlite_sessionmaker()
        session.add(CanonicalEntity(name="Nadie Menciona", type="PERSON"))
        session.commit()
        session.close()

        resp = api_client.get("/api/canonical-entities")
        item = resp.json()["items"][0]
        assert item["article_count"] == 0
        assert item["total_mentions"] == 0


class TestGetCanonicalEntity:
    def test_returns_linked_articles(self, api_client, sqlite_sessionmaker):
        session = sqlite_sessionmaker()
        canonical = CanonicalEntity(name="Luis Abinader", type="PERSON")
        session.add(canonical)
        session.commit()
        article = _make_article(url="https://diariolibre.com/detalle", title="Un artículo")
        article.entities.append(
            Entity(
                name="Luis Abinader", type="PERSON", mentions_count=4,
                sentiment_toward="POS", canonical_entity_id=canonical.id,
            )
        )
        session.add(article)
        session.commit()
        entity_id = canonical.id
        session.close()

        resp = api_client.get(f"/api/canonical-entities/{entity_id}")
        assert resp.status_code == 200
        body = resp.json()
        assert body["article_count"] == 1
        assert len(body["articles"]) == 1
        assert body["articles"][0]["title"] == "Un artículo"
        assert body["articles"][0]["sentiment_toward"] == "POS"

    def test_404_when_missing(self, api_client):
        resp = api_client.get("/api/canonical-entities/99999")
        assert resp.status_code == 404


class TestUpdateCanonicalEntity:
    def test_requires_auth(self, api_client, sqlite_sessionmaker):
        session = sqlite_sessionmaker()
        row = CanonicalEntity(name="Abinader", type="PERSON")
        session.add(row)
        session.commit()
        entity_id = row.id
        session.close()

        resp = api_client.put(f"/api/canonical-entities/{entity_id}", json={"name": "Luis Abinader"})
        assert resp.status_code == 401

    def test_renames_entity(self, api_client, sqlite_sessionmaker):
        session = sqlite_sessionmaker()
        row = CanonicalEntity(name="Abinader", type="PERSON")
        session.add(row)
        session.commit()
        entity_id = row.id
        session.close()

        resp = api_client.put(
            f"/api/canonical-entities/{entity_id}",
            json={"name": "Luis Abinader", "description": "Presidente de la RD"},
            headers=_auth_headers(),
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["name"] == "Luis Abinader"
        assert body["description"] == "Presidente de la RD"

    def test_409_when_new_name_collides_with_another_entity(self, api_client, sqlite_sessionmaker):
        session = sqlite_sessionmaker()
        session.add_all([
            CanonicalEntity(name="Abinader", type="PERSON"),
            CanonicalEntity(name="Luis Abinader", type="PERSON"),
        ])
        session.commit()
        short_id = session.query(CanonicalEntity).filter_by(name="Abinader").one().id
        session.close()

        resp = api_client.put(
            f"/api/canonical-entities/{short_id}",
            json={"name": "Luis Abinader"},
            headers=_auth_headers(),
        )
        assert resp.status_code == 409


class TestMergeCanonicalEntities:
    def test_merge_reassigns_mentions(self, api_client, sqlite_sessionmaker):
        session = sqlite_sessionmaker()
        short = CanonicalEntity(name="Abinader", type="PERSON")
        full = CanonicalEntity(name="Luis Abinader", type="PERSON")
        session.add_all([short, full])
        session.commit()
        article = _make_article(url="https://diariolibre.com/merge")
        article.entities.append(
            Entity(name="Abinader", type="PERSON", mentions_count=1, canonical_entity_id=short.id)
        )
        session.add(article)
        session.commit()
        short_id, full_id = short.id, full.id
        session.close()

        resp = api_client.post(
            f"/api/canonical-entities/{full_id}/merge",
            json={"source_id": short_id},
            headers=_auth_headers(),
        )
        assert resp.status_code == 200
        assert resp.json()["article_count"] == 1

        session = sqlite_sessionmaker()
        assert session.get(CanonicalEntity, short_id) is None
        mention = session.query(Entity).filter_by(name="Abinader").one()
        assert mention.canonical_entity_id == full_id

    def test_requires_auth(self, api_client, sqlite_sessionmaker):
        session = sqlite_sessionmaker()
        a = CanonicalEntity(name="A", type="PERSON")
        b = CanonicalEntity(name="B", type="PERSON")
        session.add_all([a, b])
        session.commit()
        a_id, b_id = a.id, b.id
        session.close()

        resp = api_client.post(f"/api/canonical-entities/{a_id}/merge", json={"source_id": b_id})
        assert resp.status_code == 401

    def test_400_on_type_mismatch(self, api_client, sqlite_sessionmaker):
        session = sqlite_sessionmaker()
        person = CanonicalEntity(name="Salud", type="PERSON")
        org = CanonicalEntity(name="Salud", type="ORG")
        session.add_all([person, org])
        session.commit()
        person_id, org_id = person.id, org.id
        session.close()

        resp = api_client.post(
            f"/api/canonical-entities/{org_id}/merge",
            json={"source_id": person_id},
            headers=_auth_headers(),
        )
        assert resp.status_code == 400

    def test_404_when_source_missing(self, api_client, sqlite_sessionmaker):
        session = sqlite_sessionmaker()
        row = CanonicalEntity(name="A", type="PERSON")
        session.add(row)
        session.commit()
        entity_id = row.id
        session.close()

        resp = api_client.post(
            f"/api/canonical-entities/{entity_id}/merge",
            json={"source_id": 99999},
            headers=_auth_headers(),
        )
        assert resp.status_code == 404


class TestSaveArticleLinksCanonicalEntity:
    def test_new_entity_gets_a_canonical_row(self, monkeypatch, api_client, sqlite_sessionmaker):
        import analysis.canonicalize as canonicalize
        import db.session as db_session_module

        monkeypatch.setattr(db_session_module, "get_session", sqlite_sessionmaker)
        monkeypatch.setattr(canonicalize.alias_store, "resolve", lambda name: None)
        monkeypatch.setattr(canonicalize.alias_store, "all_canonicals", lambda: [])

        resp = api_client.post(
            "/api/articles",
            json={
                "source": "manual",
                "url": "https://diariolibre.com/canon-nuevo",
                "title": "Título",
                "body": "cuerpo",
                "entities": [{"name": "Luis Abinader", "type": "PERSON", "mentions_count": 1}],
            },
            headers=_auth_headers(),
        )
        assert resp.status_code == 200

        session = sqlite_sessionmaker()
        entity = session.query(Entity).filter_by(name="Luis Abinader").one()
        assert entity.canonical_entity_id is not None
        canonical = session.get(CanonicalEntity, entity.canonical_entity_id)
        assert canonical.name == "Luis Abinader"
        assert canonical.type == "PERSON"

    def test_second_article_with_same_entity_reuses_canonical_row(
        self, monkeypatch, api_client, sqlite_sessionmaker
    ):
        import analysis.canonicalize as canonicalize
        import db.session as db_session_module

        monkeypatch.setattr(db_session_module, "get_session", sqlite_sessionmaker)
        monkeypatch.setattr(canonicalize.alias_store, "resolve", lambda name: None)
        monkeypatch.setattr(canonicalize.alias_store, "all_canonicals", lambda: [])

        payload = {
            "source": "manual",
            "title": "Título",
            "body": "cuerpo",
            "entities": [{"name": "Luis Abinader", "type": "PERSON", "mentions_count": 1}],
        }
        api_client.post(
            "/api/articles", json={**payload, "url": "https://diariolibre.com/canon-1"},
            headers=_auth_headers(),
        )
        api_client.post(
            "/api/articles", json={**payload, "url": "https://diariolibre.com/canon-2"},
            headers=_auth_headers(),
        )

        session = sqlite_sessionmaker()
        assert session.query(CanonicalEntity).filter_by(name="Luis Abinader").count() == 1
        mentions = session.query(Entity).filter_by(name="Luis Abinader").all()
        assert len(mentions) == 2
        assert mentions[0].canonical_entity_id == mentions[1].canonical_entity_id

    def test_stamps_analyzer_lineage(self, monkeypatch, api_client, sqlite_sessionmaker):
        import analysis.canonicalize as canonicalize
        import db.session as db_session_module
        import services.article_service as article_service

        class _FakeAnalyzer:
            name = "fake"
            model = "fake-model"
            version = "fake-version"

        monkeypatch.setattr(db_session_module, "get_session", sqlite_sessionmaker)
        monkeypatch.setattr(canonicalize.alias_store, "resolve", lambda name: None)
        monkeypatch.setattr(canonicalize.alias_store, "all_canonicals", lambda: [])
        # `article_service.analyzer` es el analizador activo del proceso,
        # importado por valor desde `services.analyzer_registry` (bindeado en
        # el momento del import, ver api/deps.py para el mismo gotcha con
        # `get_session`). Su identidad depende de ODIN_ANALYZER, que en la
        # máquina de un desarrollador puede no ser "local" (p.ej. "hybrid" en
        # .env para uso manual) — este test solo verifica que el linaje se
        # graba con el analizador activo, no cuál es, así que se fija a un
        # valor conocido en vez de asumir el default.
        monkeypatch.setattr(article_service, "analyzer", _FakeAnalyzer())

        resp = api_client.post(
            "/api/articles",
            json={
                "source": "manual",
                "url": "https://diariolibre.com/canon-lineage",
                "title": "Título",
                "body": "cuerpo",
            },
            headers=_auth_headers(),
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["analyzer_name"] == "fake"
        assert body["analyzer_model"] == "fake-model"
        assert body["analyzer_version"] == "fake-version"
        # Contra la constante, no contra un literal: lo que se prueba es que el
        # guardado ESTAMPA la versión del esquema, no cuál es su valor hoy —
        # con un literal, cada bump de ANALYSIS_SCHEMA_VERSION rompe el test
        # sin que haya nada roto (mismo criterio que tests/test_pipeline.py).
        assert body["analysis_schema_version"] == ANALYSIS_SCHEMA_VERSION
        assert body["analyzed_at"] is not None
