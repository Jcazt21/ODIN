"""Motor y sesión de SQLAlchemy.

Un solo punto de configuración de conexión. Cambiar de PostgreSQL a SQL Server
es cambiar DATABASE_URL en el .env; el resto del código no se toca.

El engine se crea de forma perezosa (lazy) para que importar los módulos que
tocan la BD no requiera tener el driver/servidor disponible (facilita tests y
scripts que no usan la BD).
"""
from __future__ import annotations

import logging
from functools import lru_cache
from typing import Any

from sqlalchemy import create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from odin.core.config import settings
from db.models import Base

log = logging.getLogger("odin.db")


@lru_cache(maxsize=1)
def get_engine() -> Engine:
    """Crea (una sola vez) el engine a partir de DATABASE_URL."""
    kwargs: dict[str, Any] = {"pool_pre_ping": True, "future": True}
    if not settings.database_url.startswith("sqlite"):
        # SQLite usa un pool propio (SingletonThreadPool) que no acepta estos
        # parámetros; solo aplican a Postgres/SQL Server (QueuePool).
        kwargs["pool_size"] = 5
        kwargs["max_overflow"] = 10
    return create_engine(settings.database_url, **kwargs)


@lru_cache(maxsize=1)
def _get_sessionmaker() -> sessionmaker:
    return sessionmaker(bind=get_engine(), class_=Session, expire_on_commit=False)


def init_db() -> None:
    """Crea las tablas que aún no existan (`create_all`, idempotente y sin
    riesgo: nunca altera una tabla existente). Da un mensaje claro si falla
    la conexión.

    Los cambios de esquema sobre una BD que YA tiene tablas (nueva columna,
    índice, etc.) van por Alembic (`alembic revision --autogenerate` +
    `alembic upgrade head`), no aquí: antes esta función también hacía
    `ALTER TABLE` automático y sin versionar en cada arranque (ver
    task.md §3.4); Alembic ya tiene el baseline (`alembic stamp head`,
    2026-08-03) y es reversible, versionado y revisable antes de aplicarse.
    """
    try:
        engine = get_engine()
        Base.metadata.create_all(engine)
    except Exception as exc:  # conexión/driver no disponible
        url = settings.database_url
        hint = ""
        if url.startswith("postgresql"):
            hint = (
                "\n  ¿Postgres no está corriendo? Para una prueba rápida sin instalar nada:\n"
                '    DATABASE_URL="sqlite:///odin.db" python main.py --limit 5'
            )
        raise RuntimeError(f"No se pudo inicializar la BD ({url}): {exc}{hint}") from exc


def get_session() -> Session:
    return _get_sessionmaker()()
