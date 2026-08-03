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

from sqlalchemy import create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from config import settings
from db.models import Base

log = logging.getLogger("odin.db")


@lru_cache(maxsize=1)
def get_engine() -> Engine:
    """Crea (una sola vez) el engine a partir de DATABASE_URL."""
    kwargs = {"pool_pre_ping": True, "future": True}
    if not settings.database_url.startswith("sqlite"):
        # SQLite usa un pool propio (SingletonThreadPool) que no acepta estos
        # parámetros; solo aplican a Postgres/SQL Server (QueuePool).
        kwargs["pool_size"] = 5
        kwargs["max_overflow"] = 10
    return create_engine(settings.database_url, **kwargs)


@lru_cache(maxsize=1)
def _get_sessionmaker() -> sessionmaker:
    return sessionmaker(bind=get_engine(), class_=Session, expire_on_commit=False)


def _add_missing_columns(engine: Engine) -> None:
    """Migración mínima sin Alembic: añade a las tablas existentes las columnas
    que estén en los modelos pero falten en la BD (create_all crea tablas
    nuevas, pero nunca altera las existentes). Solo AÑADE columnas nullables;
    no renombra ni borra. El tipo se compila según el dialecto activo, así que
    funciona igual en SQLite, Postgres y SQL Server."""
    from sqlalchemy import inspect

    inspector = inspect(engine)
    with engine.begin() as conn:
        for table in Base.metadata.sorted_tables:
            if not inspector.has_table(table.name):
                continue  # create_all la creará completa
            existing = {c["name"] for c in inspector.get_columns(table.name)}
            for column in table.columns:
                if column.name in existing or not column.nullable:
                    continue
                ddl = (
                    f"ALTER TABLE {table.name} ADD COLUMN {column.name} "
                    f"{column.type.compile(dialect=engine.dialect)}"
                )
                log.info("migración: %s", ddl)
                conn.exec_driver_sql(ddl)


def init_db() -> None:
    """Crea las tablas si no existen (y añade columnas nuevas a las que ya
    existen). Da un mensaje claro si falla la conexión."""
    try:
        engine = get_engine()
        _add_missing_columns(engine)
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
