"""Pruebas del resumen de trabajo por documentalista.

Es material de evaluación, así que está restringido a rol admin: un documentalista no
tiene por qué ver los números de sus compañeros.
"""
from __future__ import annotations

from datetime import date, datetime

import pytest

from odin.core import auth
from odin.core.auth import create_token
from odin.db.models import Article, User


def _headers(username: str = "jefe"):
    token, _ = create_token(username)
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def team(sqlite_sessionmaker):
    session = sqlite_sessionmaker()
    session.add_all(
        [
            User(
                username="jefe",
                username_key="jefe",
                display_name="La Jefa",
                password_hash=auth.hash_password("x", iterations=1000),
                role="admin",
            ),
            User(
                username="jperez",
                username_key="jperez",
                display_name="Juan Pérez",
                password_hash=auth.hash_password("x", iterations=1000),
                role="documentalista",
            ),
        ]
    )
    session.commit()
    juan = session.query(User).filter_by(username="jperez").one().id

    for n, day in enumerate([18, 18, 20], start=1):
        session.add(
            Article(
                source="listin_diario",
                url=f"https://listindiario.com/k{n}",
                title=f"Nota {n}",
                body="x",
                published_at=datetime(2026, 8, day),
                documentalist_id=juan,
                analyzed_on=date(2026, 8, day),
            )
        )
    # Sin documentalista: entró por el rastreo masivo.
    session.add(
        Article(
            source="diario_libre",
            url="https://diariolibre.com/auto",
            title="Automática",
            body="x",
            published_at=datetime(2026, 8, 1),
        )
    )
    session.commit()
    session.close()
    return juan


class TestKpi:
    def test_counts_articles_per_documentalist(self, api_client, team):
        rows = api_client.get("/api/documentalists/kpi", headers=_headers()).json()

        juan = [r for r in rows if r["display_name"] == "Juan Pérez"][0]
        assert juan["articles"] == 3

    def test_counts_distinct_active_days(self, api_client, team):
        """Tres reportes en dos días son dos días de trabajo, no tres."""
        rows = api_client.get("/api/documentalists/kpi", headers=_headers()).json()

        juan = [r for r in rows if r["display_name"] == "Juan Pérez"][0]
        assert juan["active_days"] == 2

    def test_reports_dates_without_a_time(self, api_client, team):
        rows = api_client.get("/api/documentalists/kpi", headers=_headers()).json()

        juan = [r for r in rows if r["display_name"] == "Juan Pérez"][0]
        assert juan["first_on"] == "2026-08-18"
        assert juan["last_on"] == "2026-08-20"

    def test_ignores_articles_without_an_documentalist(self, api_client, team):
        rows = api_client.get("/api/documentalists/kpi", headers=_headers()).json()

        assert sum(r["articles"] for r in rows) == 3

    def test_date_range_narrows_the_count(self, api_client, team):
        rows = api_client.get(
            "/api/documentalists/kpi", params={"date_from": "2026-08-20"}, headers=_headers()
        ).json()

        juan = [r for r in rows if r["display_name"] == "Juan Pérez"][0]
        assert juan["articles"] == 1

    def test_a_plain_documentalist_cannot_see_it(self, api_client, team):
        """Los números de productividad no son para los compañeros."""
        resp = api_client.get("/api/documentalists/kpi", headers=_headers("jperez"))

        assert resp.status_code == 403

    def test_requires_authentication(self, api_client, team):
        assert api_client.get("/api/documentalists/kpi").status_code in (401, 403)


class TestMeCarriesTheRole:
    def test_me_reports_the_role(self, api_client, team):
        """El frontend necesita el rol para ocultar lo que es solo de admin."""
        resp = api_client.get("/api/auth/me", headers=_headers())

        assert resp.status_code == 200
        assert resp.json()["role"] == "admin"

    def test_an_unknown_user_reports_no_role(self, api_client, team):
        resp = api_client.get("/api/auth/me", headers=_headers("fantasma"))

        assert resp.status_code == 200
        assert resp.json()["role"] is None
