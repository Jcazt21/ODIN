"""Alta manual de un reporte: artículo y lugares en una sola escritura.

El formulario del documentalista es un solo acto ("Guardar reporte"), así que
por dentro tiene que ser una sola transacción. La prueba que sostiene ese
diseño es `test_invalid_locality_leaves_no_article`: si los lugares se
guardaran en una segunda llamada, ese caso dejaría un reporte huérfano.
"""
from __future__ import annotations

import pytest

import odin.db.localities as loc_store
from odin.core.auth import create_token
from odin.db.models import Article, ArticleLocality


def _auth_headers():
    token, _ = create_token("tester")
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def seeded(sqlite_sessionmaker):
    session = sqlite_sessionmaker()
    try:
        loc_store.seed_localities(session)
    finally:
        session.close()


def _locality_id(sqlite_sessionmaker, name: str) -> int:
    session = sqlite_sessionmaker()
    try:
        return loc_store.resolve(session, name).id
    finally:
        session.close()


def _payload(**overrides) -> dict:
    body = dict(
        source="listin_diario",
        url="https://listindiario.com/nueva",
        title="Reporte capturado a mano",
        body="Cuerpo de la nota.",
        main_topic="agua potable",
    )
    body.update(overrides)
    return body


def _count(sqlite_sessionmaker, model) -> int:
    session = sqlite_sessionmaker()
    try:
        return session.query(model).count()
    finally:
        session.close()


class TestSaveWithLocalities:
    def test_creates_article_and_links_together(self, api_client, sqlite_sessionmaker, seeded):
        santiago = _locality_id(sqlite_sessionmaker, "Santiago")

        resp = api_client.post(
            "/api/articles",
            json=_payload(localities=[{"locality_id": santiago, "kind": "HECHO"}]),
            headers=_auth_headers(),
        )

        assert resp.status_code == 201
        article_id = resp.json()["id"]
        links = api_client.get(f"/api/articles/{article_id}/localities").json()
        assert [link["locality_id"] for link in links] == [santiago]

    def test_invalid_locality_leaves_no_article(self, api_client, sqlite_sessionmaker, seeded):
        """Un lugar inexistente aborta el alta entera: nada de reporte huérfano."""
        resp = api_client.post(
            "/api/articles",
            json=_payload(localities=[{"locality_id": 999_999, "kind": "HECHO"}]),
            headers=_auth_headers(),
        )

        assert resp.status_code == 404
        assert _count(sqlite_sessionmaker, Article) == 0
        assert _count(sqlite_sessionmaker, ArticleLocality) == 0

    def test_invalid_kind_leaves_no_article(self, api_client, sqlite_sessionmaker, seeded):
        santiago = _locality_id(sqlite_sessionmaker, "Santiago")

        resp = api_client.post(
            "/api/articles",
            json=_payload(localities=[{"locality_id": santiago, "kind": "INVENTADO"}]),
            headers=_auth_headers(),
        )

        assert resp.status_code == 422
        assert _count(sqlite_sessionmaker, Article) == 0

    def test_repeated_place_with_same_role_is_rejected(self, api_client, sqlite_sessionmaker, seeded):
        santiago = _locality_id(sqlite_sessionmaker, "Santiago")

        resp = api_client.post(
            "/api/articles",
            json=_payload(localities=[
                {"locality_id": santiago, "kind": "HECHO"},
                {"locality_id": santiago, "kind": "HECHO"},
            ]),
            headers=_auth_headers(),
        )

        assert resp.status_code == 422
        assert _count(sqlite_sessionmaker, Article) == 0

    def test_same_place_with_different_roles_is_allowed(self, api_client, sqlite_sessionmaker, seeded):
        """Una nota puede ocurrir en Santiago y además mencionar a Santiago."""
        santiago = _locality_id(sqlite_sessionmaker, "Santiago")

        resp = api_client.post(
            "/api/articles",
            json=_payload(localities=[
                {"locality_id": santiago, "kind": "HECHO"},
                {"locality_id": santiago, "kind": "MENCIONADO"},
            ]),
            headers=_auth_headers(),
        )

        assert resp.status_code == 201
        links = api_client.get(f"/api/articles/{resp.json()['id']}/localities").json()
        assert sorted(link["kind"] for link in links) == ["HECHO", "MENCIONADO"]


class TestCreatedVersusExisting:
    def test_new_url_returns_201(self, api_client):
        resp = api_client.post("/api/articles", json=_payload(), headers=_auth_headers())

        assert resp.status_code == 201

    def test_known_url_returns_200_with_the_existing_report(self, api_client, sqlite_sessionmaker):
        first = api_client.post("/api/articles", json=_payload(), headers=_auth_headers())

        second = api_client.post(
            "/api/articles",
            json=_payload(title="Otro título para la misma URL"),
            headers=_auth_headers(),
        )

        assert second.status_code == 200
        assert second.json()["id"] == first.json()["id"]
        assert second.json()["title"] == "Reporte capturado a mano"
        assert _count(sqlite_sessionmaker, Article) == 1

    def test_saving_without_localities_still_works(self, api_client, sqlite_sessionmaker):
        """El flujo de AnalyzePage no manda el campo: tiene que seguir igual."""
        resp = api_client.post("/api/articles", json=_payload(), headers=_auth_headers())

        assert resp.status_code == 201
        assert _count(sqlite_sessionmaker, ArticleLocality) == 0
