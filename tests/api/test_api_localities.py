"""Pruebas de /api/localities y del lugar de la noticia.

Lo que más importa aquí es el roll-up: el cliente etiqueta una nota en el
municipio donde ocurrió, y espera que cuente igual al mirar la provincia, la
región o el país. Si eso se rompe, el reporte miente sin dar error.

SQLite en memoria vía `api_client`/`sqlite_sessionmaker` (ver conftest.py).
"""
from __future__ import annotations

from datetime import datetime

import pytest

import odin.db.localities as loc_store
from odin.core.auth import create_token
from odin.db.models import Article, ArticleLocality


def _auth_headers():
    token, _ = create_token("tester")
    return {"Authorization": f"Bearer {token}"}


def _make_article(session, url: str, **overrides) -> Article:
    defaults = dict(
        source="listin_diario",
        url=url,
        title="Título de prueba",
        body="cuerpo",
        published_at=datetime(2026, 8, 1),
    )
    defaults.update(overrides)
    article = Article(**defaults)
    session.add(article)
    session.commit()
    return article


@pytest.fixture
def seeded(sqlite_sessionmaker):
    """Catálogo cargado. El `api_client` no dispara el lifespan (ver conftest),
    así que la semilla que en producción corre al arrancar se aplica aquí."""
    session = sqlite_sessionmaker()
    try:
        loc_store.seed_localities(session)
    finally:
        session.close()


def _locality_id(sqlite_sessionmaker, name: str, level: str | None = None) -> int:
    session = sqlite_sessionmaker()
    try:
        return loc_store.resolve(session, name, level=level).id
    finally:
        session.close()


class TestTree:
    def test_returns_country_as_single_root(self, api_client, seeded):
        resp = api_client.get("/api/localities/tree")

        assert resp.status_code == 200
        roots = resp.json()
        assert len(roots) == 1
        assert roots[0]["name"] == "República Dominicana"
        assert roots[0]["level"] == "PAIS"

    def test_carries_aliases_for_client_side_search(self, api_client, seeded):
        """El buscador del frontend filtra en memoria mientras se teclea, así
        que los alias tienen que viajar con el árbol: sin ellos, escribir
        "Navarrete" no encontraría Villa Bisonó sin ir al servidor."""
        roots = api_client.get("/api/localities/tree").json()

        found: list[str] = []

        def walk(node):
            if node["name"] == "Villa Bisonó":
                found.extend(node["aliases"])
            for child in node["children"]:
                walk(child)

        walk(roots[0])
        assert "Navarrete" in found

    def test_nests_five_levels_deep(self, api_client, seeded):
        roots = api_client.get("/api/localities/tree").json()

        levels = []
        node = roots[0]
        while node:
            levels.append(node["level"])
            node = node["children"][0] if node["children"] else None

        assert levels == ["PAIS", "MACRORREGION", "REGION", "PROVINCIA", "MUNICIPIO"]


class TestSearch:
    def test_finds_by_partial_accentless_name(self, api_client, seeded):
        resp = api_client.get("/api/localities", params={"q": "samana"})

        assert resp.status_code == 200
        assert any(r["name"] == "Samaná" for r in resp.json())

    def test_filters_by_level(self, api_client, seeded):
        resp = api_client.get("/api/localities", params={"level": "PROVINCIA", "limit": 500})

        assert resp.status_code == 200
        assert len(resp.json()) == 32  # 31 provincias + Distrito Nacional


class TestCatalogAdministration:
    def test_creating_a_municipality_requires_auth(self, api_client, seeded, sqlite_sessionmaker):
        parent = _locality_id(sqlite_sessionmaker, "Santiago", "PROVINCIA")

        resp = api_client.post(
            "/api/localities", json={"name": "Nuevo Municipio", "level": "MUNICIPIO", "parent_id": parent}
        )

        assert resp.status_code in (401, 403)

    def test_creates_municipality_with_path_under_parent(
        self, api_client, seeded, sqlite_sessionmaker
    ):
        """El caso real: el Congreso crea un municipio y el cliente lo agrega
        sin esperar un deploy."""
        parent = _locality_id(sqlite_sessionmaker, "Santiago", "PROVINCIA")

        resp = api_client.post(
            "/api/localities",
            json={"name": "Villa Nueva", "level": "MUNICIPIO", "parent_id": parent},
            headers=_auth_headers(),
        )

        assert resp.status_code == 201
        body = resp.json()
        assert body["path"].endswith(f"/{body['id']}/")
        assert body["path"].startswith(f"/{_locality_id(sqlite_sessionmaker, 'República Dominicana')}/")

    def test_rejects_duplicate_name_under_same_parent(
        self, api_client, seeded, sqlite_sessionmaker
    ):
        parent = _locality_id(sqlite_sessionmaker, "Santiago", "PROVINCIA")

        resp = api_client.post(
            "/api/localities",
            json={"name": "Tamboril", "level": "MUNICIPIO", "parent_id": parent},
            headers=_auth_headers(),
        )

        assert resp.status_code == 409

    def test_rejects_unknown_level(self, api_client, seeded, sqlite_sessionmaker):
        parent = _locality_id(sqlite_sessionmaker, "Santiago", "PROVINCIA")

        resp = api_client.post(
            "/api/localities",
            json={"name": "X", "level": "BARRIO", "parent_id": parent},
            headers=_auth_headers(),
        )

        assert resp.status_code == 422


class TestArticleLocalities:
    def test_links_a_place_to_an_article(self, api_client, seeded, sqlite_sessionmaker):
        session = sqlite_sessionmaker()
        article = _make_article(session, "https://listindiario.com/a1")
        session.close()
        tamboril = _locality_id(sqlite_sessionmaker, "Tamboril")

        resp = api_client.post(
            f"/api/articles/{article.id}/localities",
            json={"locality_id": tamboril, "kind": "HECHO"},
            headers=_auth_headers(),
        )

        assert resp.status_code == 201
        body = resp.json()
        assert body["name"] == "Tamboril"
        assert body["origin"] == "MANUAL"

    def test_breadcrumb_goes_from_country_down_to_the_node(
        self, api_client, seeded, sqlite_sessionmaker
    ):
        """El frontend muestra "RD › Cibao › Santiago › Tamboril" sin tener que
        subir el árbol por su cuenta."""
        session = sqlite_sessionmaker()
        article = _make_article(session, "https://listindiario.com/a2")
        session.close()
        tamboril = _locality_id(sqlite_sessionmaker, "Tamboril")

        api_client.post(
            f"/api/articles/{article.id}/localities",
            json={"locality_id": tamboril},
            headers=_auth_headers(),
        )
        body = api_client.get(f"/api/articles/{article.id}/localities").json()

        crumb = [c["name"] for c in body[0]["breadcrumb"]]
        assert crumb[0] == "República Dominicana"
        assert crumb[-1] == "Tamboril"
        assert "Santiago" in crumb

    def test_national_scope_is_the_country_node(self, api_client, seeded, sqlite_sessionmaker):
        """"Todas" en el formulario del cliente = ámbito nacional, y eso se
        guarda apuntando al país, no con centinelas en cuatro columnas."""
        session = sqlite_sessionmaker()
        article = _make_article(session, "https://listindiario.com/a3")
        session.close()
        pais = _locality_id(sqlite_sessionmaker, "República Dominicana")

        resp = api_client.post(
            f"/api/articles/{article.id}/localities",
            json={"locality_id": pais},
            headers=_auth_headers(),
        )

        assert resp.status_code == 201
        assert resp.json()["level"] == "PAIS"

    def test_rejects_duplicate_link_with_same_role(self, api_client, seeded, sqlite_sessionmaker):
        session = sqlite_sessionmaker()
        article = _make_article(session, "https://listindiario.com/a4")
        session.close()
        bonao = _locality_id(sqlite_sessionmaker, "Bonao")

        payload = {"locality_id": bonao, "kind": "HECHO"}
        api_client.post(
            f"/api/articles/{article.id}/localities", json=payload, headers=_auth_headers()
        )
        second = api_client.post(
            f"/api/articles/{article.id}/localities", json=payload, headers=_auth_headers()
        )

        assert second.status_code == 409

    def test_same_place_allowed_twice_with_different_roles(
        self, api_client, seeded, sqlite_sessionmaker
    ):
        """Una nota puede ocurrir en Bonao y además mencionar a Bonao."""
        session = sqlite_sessionmaker()
        article = _make_article(session, "https://listindiario.com/a5")
        session.close()
        bonao = _locality_id(sqlite_sessionmaker, "Bonao")

        api_client.post(
            f"/api/articles/{article.id}/localities",
            json={"locality_id": bonao, "kind": "HECHO"},
            headers=_auth_headers(),
        )
        second = api_client.post(
            f"/api/articles/{article.id}/localities",
            json={"locality_id": bonao, "kind": "MENCIONADO"},
            headers=_auth_headers(),
        )

        assert second.status_code == 201

    def test_replace_leaves_exactly_the_places_sent(
        self, api_client, seeded, sqlite_sessionmaker
    ):
        session = sqlite_sessionmaker()
        article = _make_article(session, "https://listindiario.com/a6")
        session.close()
        bonao = _locality_id(sqlite_sessionmaker, "Bonao")
        nagua = _locality_id(sqlite_sessionmaker, "Nagua")

        api_client.post(
            f"/api/articles/{article.id}/localities",
            json={"locality_id": bonao},
            headers=_auth_headers(),
        )
        resp = api_client.put(
            f"/api/articles/{article.id}/localities",
            json=[{"locality_id": nagua, "kind": "HECHO"}],
            headers=_auth_headers(),
        )

        assert resp.status_code == 200
        assert [r["name"] for r in resp.json()] == ["Nagua"]

    def test_unlinks_a_place(self, api_client, seeded, sqlite_sessionmaker):
        session = sqlite_sessionmaker()
        article = _make_article(session, "https://listindiario.com/a7")
        session.close()
        bonao = _locality_id(sqlite_sessionmaker, "Bonao")

        link = api_client.post(
            f"/api/articles/{article.id}/localities",
            json={"locality_id": bonao},
            headers=_auth_headers(),
        ).json()
        resp = api_client.delete(
            f"/api/articles/{article.id}/localities/{link['id']}", headers=_auth_headers()
        )

        assert resp.status_code == 204
        assert api_client.get(f"/api/articles/{article.id}/localities").json() == []

    def test_rejects_unknown_locality(self, api_client, seeded, sqlite_sessionmaker):
        session = sqlite_sessionmaker()
        article = _make_article(session, "https://listindiario.com/a8")
        session.close()

        resp = api_client.post(
            f"/api/articles/{article.id}/localities",
            json={"locality_id": 999999},
            headers=_auth_headers(),
        )

        assert resp.status_code == 404


class TestRollUp:
    """El corazón del diseño: etiquetar en el municipio y consultar arriba."""

    def _article_in(self, api_client, sqlite_sessionmaker, url: str, place: str) -> Article:
        session = sqlite_sessionmaker()
        article = _make_article(session, url)
        link = ArticleLocality(
            article_id=article.id,
            locality_id=loc_store.resolve(session, place).id,
            kind="HECHO",
        )
        session.add(link)
        session.commit()
        session.close()
        return article

    def test_filtering_by_province_finds_articles_tagged_in_its_municipalities(
        self, api_client, seeded, sqlite_sessionmaker
    ):
        self._article_in(api_client, sqlite_sessionmaker, "https://listindiario.com/r1", "Tamboril")
        santiago = _locality_id(sqlite_sessionmaker, "Santiago", "PROVINCIA")

        resp = api_client.get(
            "/api/articles", params={"locality": santiago}, headers=_auth_headers()
        )

        assert resp.status_code == 200
        assert resp.json()["total"] == 1

    def test_filtering_by_province_excludes_other_provinces(
        self, api_client, seeded, sqlite_sessionmaker
    ):
        self._article_in(api_client, sqlite_sessionmaker, "https://listindiario.com/r2", "Bonao")
        santiago = _locality_id(sqlite_sessionmaker, "Santiago", "PROVINCIA")

        resp = api_client.get(
            "/api/articles", params={"locality": santiago}, headers=_auth_headers()
        )

        assert resp.json()["total"] == 0

    def test_country_filter_finds_everything_tagged_anywhere(
        self, api_client, seeded, sqlite_sessionmaker
    ):
        self._article_in(api_client, sqlite_sessionmaker, "https://listindiario.com/r3", "Tamboril")
        self._article_in(api_client, sqlite_sessionmaker, "https://listindiario.com/r4", "Bonao")
        pais = _locality_id(sqlite_sessionmaker, "República Dominicana")

        resp = api_client.get(
            "/api/articles", params={"locality": pais}, headers=_auth_headers()
        )

        assert resp.json()["total"] == 2

    def test_frequency_aggregates_municipalities_into_their_province(
        self, api_client, seeded, sqlite_sessionmaker
    ):
        self._article_in(api_client, sqlite_sessionmaker, "https://listindiario.com/r5", "Tamboril")
        self._article_in(api_client, sqlite_sessionmaker, "https://listindiario.com/r6", "Jánico")

        resp = api_client.get("/api/localities/frequency", params={"level": "PROVINCIA"})

        assert resp.status_code == 200
        by_name = {r["name"]: r["articles"] for r in resp.json()}
        assert by_name["Santiago"] == 2

    def test_frequency_at_region_level_rolls_up_further(
        self, api_client, seeded, sqlite_sessionmaker
    ):
        self._article_in(api_client, sqlite_sessionmaker, "https://listindiario.com/r7", "Tamboril")
        self._article_in(api_client, sqlite_sessionmaker, "https://listindiario.com/r8", "Bonao")

        resp = api_client.get("/api/localities/frequency", params={"level": "MACRORREGION"})

        by_name = {r["name"]: r["articles"] for r in resp.json()}
        # Santiago y Monseñor Nouel son provincias distintas, pero ambas del Cibao.
        assert by_name["Región Norte o Cibao"] == 2

    def test_article_counted_once_even_with_several_places(
        self, api_client, seeded, sqlite_sessionmaker
    ):
        """Dos municipios de la misma provincia no deben inflar el conteo."""
        session = sqlite_sessionmaker()
        article = _make_article(session, "https://listindiario.com/r9")
        for place in ("Tamboril", "Jánico"):
            session.add(
                ArticleLocality(
                    article_id=article.id,
                    locality_id=loc_store.resolve(session, place).id,
                    kind="HECHO",
                )
            )
        session.commit()
        session.close()

        resp = api_client.get("/api/localities/frequency", params={"level": "PROVINCIA"})

        by_name = {r["name"]: r["articles"] for r in resp.json()}
        assert by_name["Santiago"] == 1
