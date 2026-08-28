"""Pruebas del CRUD de documentalistas."""
from __future__ import annotations

import pytest

from odin.core import auth
from odin.core.auth import create_token
from odin.db.models import User


def _headers(username: str = "jefe"):
    token, _ = create_token(username)
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def people(sqlite_sessionmaker):
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
    session.close()


class TestList:
    def test_lists_documentalists(self, api_client, people):
        resp = api_client.get("/api/documentalists", headers=_headers())

        assert resp.status_code == 200
        assert {a["username"] for a in resp.json()} == {"jefe", "jperez"}

    def test_never_exposes_password_hashes(self, api_client, people):
        """Un hash filtrado es un ataque offline servido en bandeja."""
        body = api_client.get("/api/documentalists", headers=_headers()).text

        assert "password_hash" not in body
        assert "pbkdf2" not in body


class TestCreate:
    def test_admin_creates_an_documentalist(self, api_client, people):
        resp = api_client.post(
            "/api/documentalists",
            json={
                "first_name": "María",
                "last_name": "Gómez",
                "role": "documentalista",
            },
            headers=_headers(),
        )

        assert resp.status_code == 201
        # El usuario se deriva del nombre; la regla vive en
        # test_username_generation.py y test_api_user_autoname.py.
        assert resp.json()["username"] == "mgome"

    def test_the_new_documentalist_can_log_in_with_the_pin(self, api_client, people):
        """El alta ya no recibe contraseña: devuelve un PIN de primer acceso.
        Las reglas de ese PIN viven en test_api_user_pin.py."""
        created = api_client.post(
            "/api/documentalists",
            json={
                "first_name": "María",
                "last_name": "Gómez",
                "role": "documentalista",
            },
            headers=_headers(),
        )

        login = api_client.post(
            "/api/auth/login",
            json={"username": created.json()["username"], "password": created.json()["pin"]},
        )

        assert login.status_code == 200

    def test_a_plain_documentalist_cannot_create_documentalists(self, api_client, people):
        resp = api_client.post(
            "/api/documentalists",
            json={"first_name": "Otro", "last_name": "Distinto", "role": "documentalista"},
            headers=_headers("jperez"),
        )

        assert resp.status_code == 403

    def test_a_repeated_name_gets_a_numbered_username(self, api_client, people):
        """Ya no hay 409 por usuario repetido: como el usuario se autogenera,
        rechazar el alta dejaría al admin sin salida. Ver
        test_api_user_autoname.py para el detalle del sufijo."""
        resp = api_client.post(
            "/api/documentalists",
            json={"first_name": "Otro", "last_name": "Perez", "role": "documentalista"},
            headers=_headers(),
        )

        assert resp.status_code == 201
        assert resp.json()["username"] == "opere"

    def test_rejects_an_unknown_role(self, api_client, people):
        resp = api_client.post(
            "/api/documentalists",
            json={"first_name": "Otro", "last_name": "Distinto", "role": "superusuario"},
            headers=_headers(),
        )

        assert resp.status_code == 422


class TestUpdate:
    def test_deactivates_an_documentalist(self, api_client, people, sqlite_sessionmaker):
        import odin.db.users as user_store

        session = sqlite_sessionmaker()
        target = user_store.get_by_username(session, "jperez").id
        session.close()

        resp = api_client.put(
            f"/api/documentalists/{target}", json={"is_active": False}, headers=_headers()
        )

        assert resp.status_code == 200
        assert resp.json()["is_active"] is False

    def test_resets_a_password(self, api_client, people, sqlite_sessionmaker):
        import odin.db.users as user_store

        session = sqlite_sessionmaker()
        target = user_store.get_by_username(session, "jperez").id
        session.close()

        api_client.put(
            f"/api/documentalists/{target}", json={"password": "clave-nueva"}, headers=_headers()
        )
        login = api_client.post(
            "/api/auth/login", json={"username": "jperez", "password": "clave-nueva"}
        )

        assert login.status_code == 200


class TestLastAdminGuard:
    """`seed_operator` (db/users.py) solo siembra al primer admin cuando la
    tabla `users` está VACÍA: si una edición deja la tabla poblada pero sin
    ningún admin activo, nadie puede volver a administrar documentalistas, ni
    reiniciando el servicio. Estas pruebas confirman que `update_documentalist`
    corta esa operación en vez de dejar el sistema en ese estado."""

    def test_the_last_active_admin_cannot_be_demoted(self, api_client, people, sqlite_sessionmaker):
        import odin.db.users as user_store

        session = sqlite_sessionmaker()
        target = user_store.get_by_username(session, "jefe").id
        session.close()

        resp = api_client.put(
            f"/api/documentalists/{target}", json={"role": "documentalista"}, headers=_headers()
        )

        assert resp.status_code == 409

    def test_the_last_active_admin_cannot_be_deactivated(
        self, api_client, people, sqlite_sessionmaker
    ):
        import odin.db.users as user_store

        session = sqlite_sessionmaker()
        target = user_store.get_by_username(session, "jefe").id
        session.close()

        resp = api_client.put(
            f"/api/documentalists/{target}", json={"is_active": False}, headers=_headers()
        )

        assert resp.status_code == 409

    def test_an_admin_can_be_demoted_when_another_admin_remains(
        self, api_client, people, sqlite_sessionmaker
    ):
        import odin.db.users as user_store

        session = sqlite_sessionmaker()
        session.add(
            User(
                username="segunda",
                username_key="segunda",
                display_name="Segunda Admin",
                password_hash=auth.hash_password("x", iterations=1000),
                role="admin",
            )
        )
        session.commit()
        target = user_store.get_by_username(session, "jefe").id
        session.close()

        resp = api_client.put(
            f"/api/documentalists/{target}", json={"role": "documentalista"}, headers=_headers()
        )

        assert resp.status_code == 200
        assert resp.json()["role"] == "documentalista"

    def test_demoting_a_regular_documentalist_still_works(self, api_client, people, sqlite_sessionmaker):
        import odin.db.users as user_store

        session = sqlite_sessionmaker()
        target = user_store.get_by_username(session, "jperez").id
        session.close()

        resp = api_client.put(
            f"/api/documentalists/{target}", json={"role": "documentalista"}, headers=_headers()
        )

        assert resp.status_code == 200
