"""Consultas y siembra de la tabla de documentalistas.

La siembra del operador del entorno vive aquí y no en `core/auth.py` para que
ese módulo no dependa de la BD más de lo imprescindible, y para poder probarla
contra SQLite sin levantar la API.
"""
from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from odin.core.auth import hash_password
from odin.core.config import settings
from odin.db.models import User


def username_key(username: str) -> str:
    """Clave de comparación: sin espacios sobrantes y en minúsculas."""
    return username.strip().lower()


def get_by_username(session: Session, username: str) -> User | None:
    return session.scalar(select(User).where(User.username_key == username_key(username)))


def seed_operator(session: Session) -> bool:
    """Convierte al operador del `.env` en el primer usuario (rol `admin`).

    Solo actúa si la tabla está VACÍA. Es deliberado: sembrar en cada arranque
    pisaría una contraseña ya cambiada desde la aplicación, y devolvería el
    acceso a una credencial del entorno que quizá se retiró a propósito.

    Sin contraseña configurada no siembra nada — el sistema queda cerrado por
    defecto, igual que hacía el login contra el entorno.
    """
    if session.scalar(select(func.count()).select_from(User)):
        return False

    stored = settings.auth_password_hash or (
        hash_password(settings.auth_password) if settings.auth_password else ""
    )
    if not stored:
        return False

    session.add(
        # `username_key` no se pasa: el validador `User._sync_username_key`
        # la deriva sola de `username` (ver `db/models.py`).
        User(
            username=settings.auth_username,
            display_name=settings.auth_username,
            password_hash=stored,
            role="admin",
            is_active=True,
        )
    )
    session.commit()
    return True
