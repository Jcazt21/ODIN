"""Pruebas del login contra la tabla de documentalistas.

Antes se validaba contra una credencial del entorno; ahora contra `users`. Lo
que no puede cambiar es el contrato hacia afuera: el token sigue llevando el
username en `sub`, para que los endpoints que ya usan `require_auth` no se
enteren.
"""
from __future__ import annotations

import pytest

import odin.db.users as user_store
from odin.core import auth
from odin.db.models import User


@pytest.fixture
def documentalist(sqlite_sessionmaker):
    session = sqlite_sessionmaker()
    session.add(
        User(
            username="jperez",
            username_key="jperez",
            display_name="Juan Pérez",
            password_hash=auth.hash_password("clave-buena", iterations=1000),
            role="documentalista",
            is_active=True,
        )
    )
    session.commit()
    session.close()


class TestLogin:
    def test_accepts_a_registered_documentalist(self, api_client, documentalist):
        resp = api_client.post(
            "/api/auth/login", json={"username": "jperez", "password": "clave-buena"}
        )

        assert resp.status_code == 200
        assert resp.json()["username"] == "jperez"

    def test_rejects_a_wrong_password(self, api_client, documentalist):
        resp = api_client.post(
            "/api/auth/login", json={"username": "jperez", "password": "clave-mala"}
        )

        assert resp.status_code == 401

    def test_rejects_an_unknown_user(self, api_client, documentalist):
        resp = api_client.post(
            "/api/auth/login", json={"username": "nadie", "password": "clave-buena"}
        )

        assert resp.status_code == 401

    def test_rejects_a_deactivated_documentalist(self, api_client, documentalist, sqlite_sessionmaker):
        """Dar de baja tiene que cerrar el acceso de inmediato, sin borrar a la
        persona ni desatribuir lo que ya firmó."""
        session = sqlite_sessionmaker()
        user_store.get_by_username(session, "jperez").is_active = False
        session.commit()
        session.close()

        resp = api_client.post(
            "/api/auth/login", json={"username": "jperez", "password": "clave-buena"}
        )

        assert resp.status_code == 401

    def test_token_carries_the_username_so_existing_endpoints_keep_working(
        self, api_client, documentalist
    ):
        token = api_client.post(
            "/api/auth/login", json={"username": "jperez", "password": "clave-buena"}
        ).json()["access_token"]

        me = api_client.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"})

        assert me.status_code == 200
        assert me.json()["username"] == "jperez"


class TestAuthenticate:
    def test_returns_the_user_row(self, api_client, documentalist):
        found = auth.authenticate("jperez", "clave-buena")

        assert found is not None
        assert found.display_name == "Juan Pérez"

    def test_returns_none_on_bad_password(self, api_client, documentalist):
        assert auth.authenticate("jperez", "clave-mala") is None
