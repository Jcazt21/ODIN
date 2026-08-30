"""Pruebas de la tabla de documentalistas y de la siembra del operador del entorno.

La siembra es lo delicado: si falla, el `.env` deja de dar acceso y nadie
puede entrar — el login pasa a validar contra esta tabla en la Tarea 2.
"""
from __future__ import annotations

from sqlalchemy import func, select

import odin.db.users as user_store
from odin.core.auth import verify_password
from odin.db.models import User


class TestGetByUsername:
    def test_finds_an_existing_user(self, db_session):
        db_session.add(
            User(
                username="jperez",
                display_name="Juan Pérez",
                password_hash="x",
                role="documentalista",
            )
        )
        db_session.commit()

        assert user_store.get_by_username(db_session, "jperez").display_name == "Juan Pérez"

    def test_is_case_insensitive(self, db_session):
        """Quien teclea "JPerez" al entrar es la misma persona que "jperez"."""
        db_session.add(
            User(username="jperez", display_name="Juan Pérez", password_hash="x", role="documentalista")
        )
        db_session.commit()

        assert user_store.get_by_username(db_session, "JPerez") is not None

    def test_returns_none_when_missing(self, db_session):
        assert user_store.get_by_username(db_session, "nadie") is None

    def test_username_key_stays_in_sync_after_a_rename(self, db_session):
        """Renombrar a alguien (Tarea 3: administración de documentalistas) no debe
        dejar `username_key` desincronizado — si el validador solo corriera en
        el alta, esta prueba fallaría en silencio: encontraría al usuario por
        el nombre viejo y no por el nuevo."""
        user = User(
            username="jperez", display_name="Juan Pérez", password_hash="x", role="documentalista"
        )
        db_session.add(user)
        db_session.commit()

        user.username = "jperez2"
        db_session.commit()

        assert user_store.get_by_username(db_session, "jperez2") is not None
        assert user_store.get_by_username(db_session, "jperez") is None


class TestSeedOperator:
    """`Settings` es un `@dataclass(frozen=True)`: sus campos NO se pueden
    mutar (`FrozenInstanceError`). Por eso estas pruebas sustituyen el objeto
    entero con `dataclasses.replace(...)` y parchean la referencia que
    `db/users.py` importó, en vez de tocar `settings.auth_username`.
    """

    def _with_settings(self, monkeypatch, **overrides):
        from dataclasses import replace

        from odin.core.config import settings

        monkeypatch.setattr(user_store, "settings", replace(settings, **overrides))

    def test_seeds_the_env_operator_as_admin(self, db_session, monkeypatch):
        """Quien hoy entra con las credenciales del .env tiene que seguir
        entrando: se convierte en el primer usuario, con rol admin."""
        self._with_settings(
            monkeypatch,
            auth_username="admin",
            auth_password="secreto",
            auth_password_hash="",
        )

        assert user_store.seed_operator(db_session) is True

        operator = user_store.get_by_username(db_session, "admin")
        assert operator.role == "admin"
        assert verify_password("secreto", operator.password_hash)

    def test_prefers_the_configured_hash_over_the_plaintext(self, db_session, monkeypatch):
        from odin.core import auth

        stored = auth.hash_password("desde-hash", iterations=1000)
        self._with_settings(
            monkeypatch,
            auth_username="admin",
            auth_password="en-claro",
            auth_password_hash=stored,
        )

        user_store.seed_operator(db_session)

        assert user_store.get_by_username(db_session, "admin").password_hash == stored

    def test_does_nothing_when_a_user_already_exists(self, db_session, monkeypatch):
        """Sembrar en cada arranque no debe pisar contraseñas ya cambiadas."""
        self._with_settings(
            monkeypatch,
            auth_username="admin",
            auth_password="secreto",
            auth_password_hash="",
        )

        assert user_store.seed_operator(db_session) is True
        assert user_store.seed_operator(db_session) is False
        assert db_session.scalar(select(func.count()).select_from(User)) == 1

    def test_does_nothing_without_a_configured_password(self, db_session, monkeypatch):
        """Sin contraseña el sistema queda cerrado, no con un admin sin clave."""
        self._with_settings(
            monkeypatch, auth_username="admin", auth_password="", auth_password_hash=""
        )

        assert user_store.seed_operator(db_session) is False
