"""Pruebas de los endpoints de borrado/rectificación de artículos y menciones
de entidad (task.md #21, §8.2): hoy no existen, así que no hay forma de
atender un pedido de corrección o de borrado sobre una persona nombrada."""
from __future__ import annotations

from odin.core.auth import create_token
from db.models import Article, CanonicalEntity, Entity


def _auth_headers() -> dict[str, str]:
    token, _ = create_token("tester")
    return {"Authorization": f"Bearer {token}"}


def _seed_article(session, **overrides) -> Article:
    defaults = dict(
        source="diario_libre",
        url="https://diariolibre.com/articulo-1",
        title="Título original",
        body="cuerpo original",
        overall_sentiment="NEG",
        sentiment_score=0.6,
    )
    defaults.update(overrides)
    article = Article(**defaults)
    session.add(article)
    session.commit()
    session.refresh(article)
    return article


def _seed_entity(session, article: Article, **overrides) -> Entity:
    defaults = dict(
        article_id=article.id,
        name="Policia Nacional",
        type="ORG",
        mentions_count=1,
        sentiment_toward="NEG",
        sentiment_score=0.55,
        context="frase de ejemplo",
    )
    defaults.update(overrides)
    entity = Entity(**defaults)
    session.add(entity)
    session.commit()
    session.refresh(entity)
    return entity


class TestUpdateArticle:
    def test_rectifies_only_sent_fields(self, api_client, sqlite_sessionmaker):
        session = sqlite_sessionmaker()
        article = _seed_article(session)
        session.close()

        resp = api_client.put(
            f"/api/articles/{article.id}",
            json={"overall_sentiment": "POS", "sentiment_score": 0.9},
            headers=_auth_headers(),
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["overall_sentiment"] == "POS"
        assert body["sentiment_score"] == 0.9
        # lo no enviado no se toca
        assert body["title"] == "Título original"
        assert body["body"] == "cuerpo original"

    def test_requires_auth(self, api_client, sqlite_sessionmaker):
        session = sqlite_sessionmaker()
        article = _seed_article(session)
        session.close()

        resp = api_client.put(f"/api/articles/{article.id}", json={"overall_sentiment": "POS"})
        assert resp.status_code == 401

    def test_404_on_missing_article(self, api_client, sqlite_sessionmaker):
        resp = api_client.put(
            "/api/articles/999", json={"overall_sentiment": "POS"}, headers=_auth_headers()
        )
        assert resp.status_code == 404

    def test_sets_dominant_actor_to_an_existing_mention(self, api_client, sqlite_sessionmaker):
        session = sqlite_sessionmaker()
        article = _seed_article(session)
        canonical = CanonicalEntity(name="Luis Abinader", type="PERSON")
        session.add(canonical)
        session.commit()
        _seed_entity(
            session, article, name="Luis Abinader", type="PERSON",
            canonical_entity_id=canonical.id,
        )
        session.close()

        resp = api_client.put(
            f"/api/articles/{article.id}",
            json={"dominant_actor": "Luis Abinader"},
            headers=_auth_headers(),
        )
        assert resp.status_code == 200
        assert resp.json()["dominant_actor"] == "Luis Abinader"

        session = sqlite_sessionmaker()
        refreshed = session.get(Article, article.id)
        assert refreshed.dominant_actor_id == canonical.id

    def test_clears_dominant_actor_when_name_matches_no_mention(
        self, api_client, sqlite_sessionmaker
    ):
        session = sqlite_sessionmaker()
        article = _seed_article(session)
        session.close()

        resp = api_client.put(
            f"/api/articles/{article.id}",
            json={"dominant_actor": "Alguien Sin Mencion"},
            headers=_auth_headers(),
        )
        assert resp.status_code == 200
        assert resp.json()["dominant_actor"] is None


class TestDeleteArticle:
    def test_deletes_article_and_cascades_entities(self, api_client, sqlite_sessionmaker):
        session = sqlite_sessionmaker()
        article = _seed_article(session)
        _seed_entity(session, article)
        article_id = article.id
        session.close()

        resp = api_client.delete(f"/api/articles/{article_id}", headers=_auth_headers())
        assert resp.status_code == 204

        session = sqlite_sessionmaker()
        assert session.get(Article, article_id) is None
        assert session.query(Entity).filter_by(article_id=article_id).count() == 0
        session.close()

    def test_requires_auth(self, api_client, sqlite_sessionmaker):
        session = sqlite_sessionmaker()
        article = _seed_article(session)
        session.close()

        resp = api_client.delete(f"/api/articles/{article.id}")
        assert resp.status_code == 401

    def test_404_on_missing_article(self, api_client, sqlite_sessionmaker):
        resp = api_client.delete("/api/articles/999", headers=_auth_headers())
        assert resp.status_code == 404


class TestUpdateEntity:
    def test_rectifies_sentiment_and_context(self, api_client, sqlite_sessionmaker):
        session = sqlite_sessionmaker()
        article = _seed_article(session)
        entity = _seed_entity(session, article)
        session.close()

        resp = api_client.put(
            f"/api/entities/{entity.id}",
            json={"sentiment_toward": "NEU", "context": "contexto corregido"},
            headers=_auth_headers(),
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["sentiment_toward"] == "NEU"
        assert body["context"] == "contexto corregido"
        assert body["name"] == "Policia Nacional"

    def test_409_on_name_clash_within_same_article(self, api_client, sqlite_sessionmaker):
        session = sqlite_sessionmaker()
        article = _seed_article(session)
        _seed_entity(session, article, name="Policia Nacional", type="ORG")
        other = _seed_entity(session, article, name="Otra Entidad", type="ORG")
        session.close()

        resp = api_client.put(
            f"/api/entities/{other.id}",
            json={"name": "Policia Nacional"},
            headers=_auth_headers(),
        )
        assert resp.status_code == 409

    def test_requires_auth(self, api_client, sqlite_sessionmaker):
        session = sqlite_sessionmaker()
        article = _seed_article(session)
        entity = _seed_entity(session, article)
        session.close()

        resp = api_client.put(f"/api/entities/{entity.id}", json={"context": "x"})
        assert resp.status_code == 401

    def test_404_on_missing_entity(self, api_client, sqlite_sessionmaker):
        resp = api_client.put(
            "/api/entities/999", json={"context": "x"}, headers=_auth_headers()
        )
        assert resp.status_code == 404


class TestDeleteEntity:
    def test_deletes_single_mention_without_touching_article(self, api_client, sqlite_sessionmaker):
        session = sqlite_sessionmaker()
        article = _seed_article(session)
        entity = _seed_entity(session, article)
        other = _seed_entity(session, article, name="Otra Entidad", type="ORG")
        article_id = article.id
        session.close()

        resp = api_client.delete(f"/api/entities/{entity.id}", headers=_auth_headers())
        assert resp.status_code == 204

        session = sqlite_sessionmaker()
        assert session.get(Entity, entity.id) is None
        assert session.get(Article, article_id) is not None
        assert session.get(Entity, other.id) is not None
        session.close()

    def test_requires_auth(self, api_client, sqlite_sessionmaker):
        session = sqlite_sessionmaker()
        article = _seed_article(session)
        entity = _seed_entity(session, article)
        session.close()

        resp = api_client.delete(f"/api/entities/{entity.id}")
        assert resp.status_code == 401

    def test_404_on_missing_entity(self, api_client, sqlite_sessionmaker):
        resp = api_client.delete("/api/entities/999", headers=_auth_headers())
        assert resp.status_code == 404
