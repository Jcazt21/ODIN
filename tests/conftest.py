"""Fixtures compartidas.

Todas las pruebas de BD/API usan SQLite en memoria, nunca la `DATABASE_URL`
real del `.env` (que por defecto apunta a Postgres). Nada aquí toca la red ni
la API de Gemini (ver CLAUDE.md).
"""
from __future__ import annotations

import re

import pytest
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from odin.db.models import Base


def _sqlite_regexp_ci(pattern: str, value: str | None) -> bool:
    """Implementa el operador `~*` de Postgres sobre SQLite: el código de
    producción usa `column.op("~*")`, que en SQLite se traduce a la función
    `REGEXP` de dos argumentos. Se registra aquí (no en db/session.py) porque
    solo los tests corren contra SQLite; en Postgres esta función no existe y
    no hace falta."""
    if value is None:
        return False
    return re.search(pattern, value, re.IGNORECASE) is not None


@pytest.fixture
def sqlite_sessionmaker():
    """Sessionmaker ligado a una BD SQLite en memoria fresca, con el esquema
    ya creado. StaticPool: una sola conexión compartida, para que las tablas
    creadas sobrevivan entre sesiones dentro del mismo test."""
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )

    @event.listens_for(engine, "connect")
    def _register_regexp(dbapi_connection, connection_record):
        dbapi_connection.create_function("regexp", 2, _sqlite_regexp_ci)

    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine, expire_on_commit=False)
    try:
        yield Session
    finally:
        engine.dispose()


@pytest.fixture
def db_session(sqlite_sessionmaker):
    session = sqlite_sessionmaker()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture
def api_client(monkeypatch, sqlite_sessionmaker):
    """TestClient de la API con `get_session` apuntando a SQLite en memoria.

    Se instancia `TestClient` SIN usar `with`: eso evita disparar el
    `lifespan` de la app (que llama `init_db()` / `load_seed()` contra la
    `DATABASE_URL` real), algo que no queremos ni necesitamos para probar
    endpoints de solo lectura.

    Se parchea `api.deps.get_session` (no `db.session.get_session` directo):
    todos los routers y servicios importan `get_session` desde `api.deps` —
    ver el docstring de ese módulo —, así que parchear el nombre ahí cubre a
    todos sin tener que tocar cada `services/*.py` por separado.
    """
    from fastapi.testclient import TestClient

    import odin.api as api_module
    import odin.api.deps as api_deps

    monkeypatch.setattr(api_deps, "get_session", sqlite_sessionmaker)
    return TestClient(api_module.app)
