"""Alta con nombre y apellido: el usuario se autogenera y nunca choca."""
from __future__ import annotations

from odin.core import auth
from odin.core.auth import create_token
from odin.db.models import User


def _admin(sqlite_sessionmaker) -> None:
    session = sqlite_sessionmaker()
    session.add(
        User(
            username="jefa",
            display_name="La Jefa",
            first_name="La",
            last_name="Jefa",
            password_hash=auth.hash_password("x", iterations=1000),
            role="admin",
        )
    )
    session.commit()
    session.close()


def _headers():
    token, _ = create_token("jefa")
    return {"Authorization": f"Bearer {token}"}


def _create(api_client, first: str, last: str):
    return api_client.post(
        "/api/documentalists",
        json={"first_name": first, "last_name": last, "role": "documentalista"},
        headers=_headers(),
    )


class TestGeneratedUsername:
    def test_builds_the_username_from_the_name(self, api_client, sqlite_sessionmaker):
        _admin(sqlite_sessionmaker)

        resp = _create(api_client, "Yvan", "Mercado")

        assert resp.status_code == 201
        assert resp.json()["username"] == "ymerc"

    def test_keeps_name_and_surname_apart(self, api_client, sqlite_sessionmaker):
        _admin(sqlite_sessionmaker)

        body = _create(api_client, "Yvan", "Mercado").json()

        assert body["first_name"] == "Yvan"
        assert body["last_name"] == "Mercado"
        assert body["display_name"] == "Yvan Mercado"

    def test_the_username_is_usable_for_logging_in(self, api_client, sqlite_sessionmaker):
        _admin(sqlite_sessionmaker)
        created = _create(api_client, "Yvan", "Mercado").json()

        login = api_client.post(
            "/api/auth/login", json={"username": "ymerc", "password": created["pin"]}
        )

        assert login.status_code == 200

    def test_rejects_a_name_with_no_usable_letters(self, api_client, sqlite_sessionmaker):
        _admin(sqlite_sessionmaker)

        resp = _create(api_client, "", "Mercado")

        assert resp.status_code == 422


class TestCollisions:
    def test_the_second_same_username_gets_a_number(self, api_client, sqlite_sessionmaker):
        _admin(sqlite_sessionmaker)
        _create(api_client, "Juan", "Mercado")

        second = _create(api_client, "José", "Mercado")

        assert second.status_code == 201
        assert second.json()["username"] == "jmerc2"

    def test_it_keeps_counting_past_the_second(self, api_client, sqlite_sessionmaker):
        _admin(sqlite_sessionmaker)
        _create(api_client, "Juan", "Mercado")
        _create(api_client, "José", "Mercado")

        third = _create(api_client, "Julia", "Mercado")

        assert third.json()["username"] == "jmerc3"

    def test_each_collided_user_can_log_in_on_their_own(self, api_client, sqlite_sessionmaker):
        """Lo que importa del sufijo: que sean cuentas distintas de verdad."""
        _admin(sqlite_sessionmaker)
        first = _create(api_client, "Juan", "Mercado").json()
        second = _create(api_client, "José", "Mercado").json()

        for user, pin in ((first["username"], first["pin"]), (second["username"], second["pin"])):
            resp = api_client.post("/api/auth/login", json={"username": user, "password": pin})
            assert resp.status_code == 200, f"{user} no pudo entrar"

    def test_collision_check_ignores_capitalisation(self, api_client, sqlite_sessionmaker):
        """El login compara en minúsculas, así que el choque también."""
        session = sqlite_sessionmaker()
        session.add(
            User(
                username="JMERC",
                display_name="Ya Estaba",
                first_name="Ya",
                last_name="Estaba",
                password_hash=auth.hash_password("x", iterations=1000),
                role="documentalista",
            )
        )
        session.commit()
        session.close()
        _admin(sqlite_sessionmaker)

        resp = _create(api_client, "Juan", "Mercado")

        assert resp.json()["username"] == "jmerc2"
