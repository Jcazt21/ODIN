"""Pruebas de la autoría del reporte.

`documentalist` (persona) y `analyzer_name` (motor) son cosas distintas y ambas se
guardan: quién lo revisó, y qué modelo lo produjo.
"""
from __future__ import annotations

import pytest

from odin.core import auth
from odin.core.auth import create_token
from odin.db.models import User


def _headers(username: str = "jperez"):
    token, _ = create_token(username)
    return {"Authorization": f"Bearer {token}"}


def _payload(url: str = "https://listindiario.com/n1") -> dict:
    return {
        "source": "listin_diario",
        "url": url,
        "title": "Título de prueba",
        "body": "cuerpo",
        "main_topic": "agua potable",
        "overall_sentiment": "NEU",
    }


@pytest.fixture
def documentalist(sqlite_sessionmaker):
    session = sqlite_sessionmaker()
    session.add(
        User(
            username="jperez",
            username_key="jperez",
            display_name="Juan Pérez",
            password_hash=auth.hash_password("x", iterations=1000),
            role="documentalista",
        )
    )
    session.commit()
    session.close()


class TestSaveRecordsAuthorship:
    def test_saving_records_who_did_it(self, api_client, documentalist):
        resp = api_client.post("/api/articles", json=_payload(), headers=_headers())

        assert resp.status_code == 201  # alta: ver test_api_save_with_localities.py
        assert resp.json()["documentalist"] == "Juan Pérez"

    def test_authorship_survives_in_the_listing(self, api_client, documentalist):
        api_client.post("/api/articles", json=_payload(), headers=_headers())

        items = api_client.get("/api/articles", headers=_headers()).json()["items"]

        assert items[0]["documentalist"] == "Juan Pérez"

    def test_listing_does_not_query_once_per_documentalist(self, api_client, documentalist, sqlite_sessionmaker):
        """El listado carga el documentalista en bloque, no una consulta por fila: son
        20 artículos por página y sería 20 viajes extra a la BD.

        Usa un documentalista DISTINTO por artículo a propósito: si los tres
        compartieran uno solo, el `get()` por identity map que SQLAlchemy usa
        para relaciones many-to-one encontraría al segundo y al tercero ya
        cargados en sesión y la prueba pasaría igual sin `selectinload`,
        sin haber probado nada. Con tres documentalistas distintos, cada acceso
        lazy SÍ dispara una consulta nueva si no hay carga en bloque."""
        session = sqlite_sessionmaker()
        for n in range(1, 3):
            session.add(
                User(
                    username=f"documentalista{n}",
                    username_key=f"documentalista{n}",
                    display_name=f"Documentalista {n}",
                    password_hash=auth.hash_password("x", iterations=1000),
                    role="documentalista",
                )
            )
        session.commit()
        session.close()

        api_client.post(
            "/api/articles", json=_payload("https://listindiario.com/n1-0"), headers=_headers("jperez")
        )
        api_client.post(
            "/api/articles", json=_payload("https://listindiario.com/n1-1"), headers=_headers("documentalista1")
        )
        api_client.post(
            "/api/articles", json=_payload("https://listindiario.com/n1-2"), headers=_headers("documentalista2")
        )

        from sqlalchemy import event

        engine = sqlite_sessionmaker.kw["bind"]
        queries: list[str] = []

        def _count(conn, cursor, statement, params, context, executemany):
            queries.append(statement)

        event.listen(engine, "before_cursor_execute", _count)
        try:
            resp = api_client.get("/api/articles", headers=_headers())
        finally:
            event.remove(engine, "before_cursor_execute", _count)

        assert resp.json()["total"] == 3
        user_queries = [q for q in queries if "FROM users" in q]
        assert len(user_queries) <= 1, (
            f"se esperaba una sola consulta a users, hubo {len(user_queries)}: {user_queries}"
        )

    def test_articles_without_a_person_report_no_documentalist(
        self, api_client, documentalist, sqlite_sessionmaker
    ):
        """Lo que entra por el rastreo masivo no tiene persona detrás."""
        from datetime import datetime

        from odin.db.models import Article

        session = sqlite_sessionmaker()
        session.add(
            Article(
                source="diario_libre",
                url="https://diariolibre.com/auto",
                title="Automático",
                body="x",
                published_at=datetime(2026, 8, 1),
            )
        )
        session.commit()
        session.close()

        items = api_client.get("/api/articles", headers=_headers()).json()["items"]
        automatic = [i for i in items if i["url"].endswith("/auto")][0]

        assert automatic["documentalist"] is None

    def test_rectifying_reassigns_authorship_to_whoever_corrected_it(
        self, api_client, documentalist, sqlite_sessionmaker
    ):
        """Si otra persona corrige el análisis, el reporte pasa a ser suyo: el
        KPI mide quién dejó el dato como está, no quién lo tocó primero."""
        session = sqlite_sessionmaker()
        session.add(
            User(
                username="mgomez",
                username_key="mgomez",
                display_name="María Gómez",
                password_hash=auth.hash_password("x", iterations=1000),
                role="documentalista",
            )
        )
        session.commit()
        session.close()

        created = api_client.post("/api/articles", json=_payload(), headers=_headers()).json()
        updated = api_client.put(
            f"/api/articles/{created['id']}",
            json={"main_topic": "energía eléctrica"},
            headers=_headers("mgomez"),
        )

        assert updated.status_code == 200
        assert updated.json()["documentalist"] == "María Gómez"

    def test_an_unknown_username_leaves_no_documentalist_instead_of_failing(
        self, api_client, documentalist
    ):
        """Un token válido de alguien ya borrado no puede tumbar el guardado."""
        resp = api_client.post("/api/articles", json=_payload(), headers=_headers("fantasma"))

        assert resp.status_code == 201  # alta: ver test_api_save_with_localities.py
        assert resp.json()["documentalist"] is None


class TestFilterByDocumentalist:
    def _two_documentalists_one_article_each(self, api_client, sqlite_sessionmaker):
        session = sqlite_sessionmaker()
        session.add(
            User(
                username="mgomez",
                username_key="mgomez",
                display_name="María Gómez",
                password_hash=auth.hash_password("x", iterations=1000),
                role="documentalista",
            )
        )
        session.commit()
        ids = {u.username: u.id for u in session.query(User).all()}
        session.close()

        api_client.post(
            "/api/articles",
            json=_payload("https://listindiario.com/de-juan"),
            headers=_headers("jperez"),
        )
        api_client.post(
            "/api/articles",
            json=_payload("https://listindiario.com/de-maria"),
            headers=_headers("mgomez"),
        )
        return ids

    def test_filters_to_a_single_documentalist(self, api_client, documentalist, sqlite_sessionmaker):
        ids = self._two_documentalists_one_article_each(api_client, sqlite_sessionmaker)

        resp = api_client.get(
            "/api/articles", params={"documentalist": ids["jperez"]}, headers=_headers()
        )

        assert resp.json()["total"] == 1
        assert resp.json()["items"][0]["url"].endswith("/de-juan")

    def test_without_the_filter_everything_shows(self, api_client, documentalist, sqlite_sessionmaker):
        self._two_documentalists_one_article_each(api_client, sqlite_sessionmaker)

        assert api_client.get("/api/articles", headers=_headers()).json()["total"] == 2

    def test_filter_options_list_the_documentalists(self, api_client, documentalist, sqlite_sessionmaker):
        self._two_documentalists_one_article_each(api_client, sqlite_sessionmaker)

        facets = api_client.get("/api/articles/filters", headers=_headers()).json()

        assert {a["display_name"] for a in facets["documentalists"]} == {"Juan Pérez", "María Gómez"}


class TestListingRequiresAuth:
    def test_listing_rejects_anonymous_requests(self, api_client):
        """La atribución por documentalista son nombres de personal: el listado no
        puede seguir respondiendo sin credenciales."""
        assert api_client.get("/api/articles").status_code in (401, 403)

    def test_filter_options_reject_anonymous_requests(self, api_client):
        assert api_client.get("/api/articles/filters").status_code in (401, 403)

    def test_listing_works_with_a_token(self, api_client, documentalist):
        assert api_client.get("/api/articles", headers=_headers()).status_code == 200
