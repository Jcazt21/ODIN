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
from pathlib import Path
from typing import Any

from sqlalchemy import create_engine, inspect
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from odin.core.config import settings
from odin.db.models import Base

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


def _alembic_config():
    """Localiza `alembic.ini` y devuelve su configuración, o `None`.

    Se busca en el directorio de trabajo (que es donde vive en la imagen de
    Docker, cuyo WORKDIR es la raíz del proyecto) y en la raíz del repositorio
    relativa a este archivo (que cubre la instalación editable de desarrollo).
    Devolver `None` en vez de reventar es deliberado: no poder sellar la base
    es un problema de despliegue, no una razón para impedir que la aplicación
    arranque.
    """
    from alembic.config import Config

    candidates = [
        Path.cwd() / "alembic.ini",
        Path(__file__).resolve().parents[3] / "alembic.ini",
    ]
    for ini in candidates:
        if ini.is_file():
            cfg = Config(str(ini))
            # script_location absoluto: en alembic.ini es relativo, y solo
            # resuelve bien si el proceso arrancó desde la raíz del proyecto.
            cfg.set_main_option("script_location", str(ini.parent / "alembic"))
            return cfg
    return None


def alembic_head_revision() -> str | None:
    """Identificador de la última migración disponible, o `None` si no se
    encuentra la configuración de Alembic."""
    from alembic.script import ScriptDirectory

    cfg = _alembic_config()
    if cfg is None:
        return None
    return ScriptDirectory.from_config(cfg).get_current_head()


def init_db() -> None:
    """Prepara el esquema **solo si la base está completamente vacía**.

    Antes esta función llamaba a `create_all()` en todo arranque. Parecía
    inofensivo ("nunca altera una tabla existente"), pero creaba las tablas
    nuevas SIN registrarlas en `alembic_version`: al correr después
    `alembic upgrade head`, la migración intentaba crear una tabla que ya
    existía, fallaba con `DuplicateTable` y dejaba la base a medio migrar. Pasó
    en producción con `runtime_settings`.

    De ahí las tres ramas:

    * **Base vacía** — se crea el esquema y se sella en head. Es la comodidad
      de "clonar y arrancar", y queda coherente con Alembic desde el minuto
      cero.
    * **Base ya versionada** — no se toca nada. El esquema es responsabilidad
      de Alembic; si falta una tabla es porque falta `alembic upgrade head`, y
      crearla por detrás es justo lo que rompía el registro de versiones.
    * **Base con tablas pero sin `alembic_version`** — tampoco se toca, y se
      avisa. Sellarla en head marcaría como aplicadas migraciones que quizá
      nunca corrieron; qué revisión le corresponde solo lo puede decidir una
      persona mirando el esquema.
    """
    try:
        engine = get_engine()
        inspector = inspect(engine)
        tables = set(inspector.get_table_names())

        if "alembic_version" in tables:
            log.debug("init_db: base ya versionada; el esquema lo gobierna Alembic")
            return

        if tables:
            log.warning(
                "init_db: la base tiene tablas pero no `alembic_version`. No se toca el "
                "esquema. Revisa qué revisión le corresponde y séllala con "
                "`alembic stamp <revision>`; después `alembic upgrade head`."
            )
            return

        Base.metadata.create_all(engine)

        cfg = _alembic_config()
        if cfg is None:
            log.warning(
                "init_db: esquema creado, pero no se encontró alembic.ini para sellarlo. "
                "Ejecuta `alembic stamp head` o el próximo `alembic upgrade head` fallará "
                "intentando crear tablas que ya existen."
            )
            return

        # Se sella sobre ESTA conexión, no con `alembic.command.stamp()`: ese
        # atajo deja que `env.py` abra su propia conexión desde la
        # configuración, que no tiene por qué ser la misma base que se acaba de
        # crear (en pruebas, desde luego, no lo es).
        from alembic.runtime.migration import MigrationContext
        from alembic.script import ScriptDirectory

        script = ScriptDirectory.from_config(cfg)
        with engine.begin() as conn:
            MigrationContext.configure(conn).stamp(script, "head")

        log.info("init_db: esquema creado y sellado en %s", alembic_head_revision())
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
