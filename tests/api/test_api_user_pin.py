"""Alta con PIN de 4 dígitos y cambio obligatorio de contraseña.

El PIN es una credencial de un solo uso: sirve para el primer login y muere
ahí. Cuatro dígitos son 10.000 combinaciones, así que lo que lo hace aceptable
es justamente que no sobreviva a ese primer uso — las pruebas de reuso son las
que sostienen el diseño, no un detalle.
"""
from __future__ import annotations

import re

from odin.core import auth
from odin.core.auth import create_token
from odin.db.models import User


def _admin(sqlite_sessionmaker, username: str = "jefa") -> None:
    session = sqlite_sessionmaker()
    session.add(
        User(
            username=username,
            display_name="La Jefa",
            password_hash=auth.hash_password("x", iterations=1000),
            role="admin",
        )
    )
    session.commit()
    session.close()


def _headers(username: str = "jefa"):
    token, _ = create_token(username)
    return {"Authorization": f"Bearer {token}"}


def _create(api_client, first: str = "Nueva", last: str = "Persona") -> dict:
    """El usuario se autogenera del nombre: "Nueva Persona" -> "npers".
    Las reglas de esa derivación viven en test_api_user_autoname.py."""
    resp = api_client.post(
        "/api/documentalists",
        json={"first_name": first, "last_name": last, "role": "documentalista"},
        headers=_headers(),
    )
    assert resp.status_code == 201, resp.text
    return resp.json()


class TestPinCreation:
    def test_creating_a_user_returns_a_four_digit_pin(self, api_client, sqlite_sessionmaker):
        _admin(sqlite_sessionmaker)

        body = _create(api_client)

        assert re.fullmatch(r"\d{4}", body["pin"]), body.get("pin")

    def test_the_pin_is_not_stored_in_clear_text(self, api_client, sqlite_sessionmaker):
        _admin(sqlite_sessionmaker)
        body = _create(api_client)

        session = sqlite_sessionmaker()
        row = session.query(User).filter_by(username="npers").one()
        stored = row.password_hash
        session.close()

        assert body["pin"] not in stored
        assert stored.startswith("pbkdf2_sha256$")

    def test_creation_no_longer_accepts_a_chosen_password(self, api_client, sqlite_sessionmaker):
        """La contraseña la elige la persona al entrar, no quien la da de alta."""
        _admin(sqlite_sessionmaker)

        resp = api_client.post(
            "/api/documentalists",
            json={
                "first_name": "Otro",
                "last_name": "Distinto",
                "role": "documentalista",
                "password": "elegida-por-el-admin",
            },
            headers=_headers(),
        )

        assert resp.status_code == 201
        login = api_client.post(
            "/api/auth/login", json={"username": "odist", "password": "elegida-por-el-admin"}
        )
        assert login.status_code == 401

    def test_only_admins_can_create(self, api_client, sqlite_sessionmaker):
        session = sqlite_sessionmaker()
        session.add(
            User(
                username="pepe",
                display_name="Pepe",
                password_hash=auth.hash_password("x", iterations=1000),
                role="documentalista",
            )
        )
        session.commit()
        session.close()

        resp = api_client.post(
            "/api/documentalists",
            json={"first_name": "Colado", "last_name": "Intruso", "role": "documentalista"},
            headers=_headers("pepe"),
        )

        assert resp.status_code == 403


class TestPinIsSingleUse:
    def test_the_pin_works_once(self, api_client, sqlite_sessionmaker):
        _admin(sqlite_sessionmaker)
        pin = _create(api_client)["pin"]

        first = api_client.post("/api/auth/login", json={"username": "npers", "password": pin})

        assert first.status_code == 200

    def test_the_pin_is_refused_the_second_time(self, api_client, sqlite_sessionmaker):
        _admin(sqlite_sessionmaker)
        pin = _create(api_client)["pin"]
        api_client.post("/api/auth/login", json={"username": "npers", "password": pin})

        second = api_client.post("/api/auth/login", json={"username": "npers", "password": pin})

        assert second.status_code == 401

    def test_regenerating_gives_a_new_working_pin(self, api_client, sqlite_sessionmaker):
        """Rescata a quien entró con el PIN y cerró antes de cambiar la clave."""
        _admin(sqlite_sessionmaker)
        created = _create(api_client)
        api_client.post("/api/auth/login", json={"username": "npers", "password": created["pin"]})

        resp = api_client.post(
            f"/api/documentalists/{created['id']}/pin", headers=_headers()
        )

        assert resp.status_code == 200
        nuevo_pin = resp.json()["pin"]
        assert re.fullmatch(r"\d{4}", nuevo_pin)
        assert (
            api_client.post(
                "/api/auth/login", json={"username": "npers", "password": nuevo_pin}
            ).status_code
            == 200
        )


def _login(api_client, username: str, password: str) -> str:
    resp = api_client.post("/api/auth/login", json={"username": username, "password": password})
    assert resp.status_code == 200, resp.text
    return resp.json()["access_token"]


def _bearer(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


class TestForcedChangeGate:
    def test_me_reports_that_the_password_must_change(self, api_client, sqlite_sessionmaker):
        _admin(sqlite_sessionmaker)
        pin = _create(api_client)["pin"]
        token = _login(api_client, "npers", pin)

        resp = api_client.get("/api/auth/me", headers=_bearer(token))

        assert resp.status_code == 200
        assert resp.json()["must_change_password"] is True

    def test_every_other_route_is_closed_until_it_changes(self, api_client, sqlite_sessionmaker):
        """El portón vive en la API, no solo en la pantalla: si estuviera solo
        en el frontend, bastaría una llamada directa para esquivarlo."""
        _admin(sqlite_sessionmaker)
        pin = _create(api_client)["pin"]
        token = _login(api_client, "npers", pin)

        resp = api_client.get("/api/articles", headers=_bearer(token))

        assert resp.status_code == 403

    def test_changing_the_password_opens_everything(self, api_client, sqlite_sessionmaker):
        _admin(sqlite_sessionmaker)
        pin = _create(api_client)["pin"]
        token = _login(api_client, "npers", pin)

        changed = api_client.post(
            "/api/auth/change-password",
            json={"new_password": "una-clave-decente"},
            headers=_bearer(token),
        )

        assert changed.status_code == 200
        nuevo_token = changed.json()["access_token"]
        assert api_client.get("/api/articles", headers=_bearer(nuevo_token)).status_code == 200

    def test_the_old_token_stops_demanding_a_change_only_after_reissue(
        self, api_client, sqlite_sessionmaker
    ):
        """El portón viaja en el token, así que el cambio DEBE emitir uno nuevo."""
        _admin(sqlite_sessionmaker)
        pin = _create(api_client)["pin"]
        token = _login(api_client, "npers", pin)
        api_client.post(
            "/api/auth/change-password",
            json={"new_password": "una-clave-decente"},
            headers=_bearer(token),
        )

        assert api_client.get("/api/articles", headers=_bearer(token)).status_code == 403

    def test_the_new_password_works_for_logging_in(self, api_client, sqlite_sessionmaker):
        _admin(sqlite_sessionmaker)
        pin = _create(api_client)["pin"]
        token = _login(api_client, "npers", pin)
        api_client.post(
            "/api/auth/change-password",
            json={"new_password": "una-clave-decente"},
            headers=_bearer(token),
        )

        assert _login(api_client, "npers", "una-clave-decente")


class TestNewPasswordRules:
    def test_rejects_a_password_shorter_than_eight(self, api_client, sqlite_sessionmaker):
        _admin(sqlite_sessionmaker)
        pin = _create(api_client)["pin"]
        token = _login(api_client, "npers", pin)

        resp = api_client.post(
            "/api/auth/change-password", json={"new_password": "corta12"}, headers=_bearer(token)
        )

        assert resp.status_code == 422

    def test_rejects_reusing_the_pin(self, api_client, sqlite_sessionmaker):
        """Repetir el PIN dejaría viva justo la credencial que se quiere retirar."""
        _admin(sqlite_sessionmaker)
        pin = _create(api_client)["pin"]
        token = _login(api_client, "npers", pin)

        resp = api_client.post(
            "/api/auth/change-password", json={"new_password": pin}, headers=_bearer(token)
        )

        assert resp.status_code == 422
