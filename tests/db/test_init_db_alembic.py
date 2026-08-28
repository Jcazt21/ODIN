"""Pruebas de la convivencia entre `init_db()` y Alembic.

El fallo que motivó esto: `init_db()` llamaba a `create_all()` en cada arranque,
que crea las tablas que falten SIN registrarlas en `alembic_version`. Cuando
después alguien corría `alembic upgrade head`, la migración intentaba crear una
tabla que ya existía y reventaba con `DuplicateTable`, dejando la base a medio
migrar y sin forma obvia de salir.

La regla que se prueba aquí:

* base **completamente vacía** -> `create_all()` y se sella (`stamp`) en head,
  para que Alembic sepa que ese esquema ya está al día.
* base **ya versionada** (tiene `alembic_version`) -> `init_db()` NO toca el
  esquema: es territorio de Alembic.
* base **con tablas pero sin versionar** -> tampoco se toca, y se avisa: es un
  estado ambiguo que solo una persona puede resolver.
"""
from __future__ import annotations

import pytest
from sqlalchemy import create_engine, inspect, text

from odin.db import session as db_session
from odin.db.models import Base


@pytest.fixture
def sqlite_file(tmp_path):
    """Una BD en archivo, no en memoria: `init_db()` abre su propia conexión a
    través de `get_engine()`, y con `:memory:` cada conexión vería una base
    distinta."""
    return f"sqlite:///{tmp_path / 'probe.db'}"


@pytest.fixture
def wired(monkeypatch, sqlite_file):
    """Apunta `get_engine()` a la BD de prueba, saltándose la caché del módulo."""
    engine = create_engine(sqlite_file)
    monkeypatch.setattr(db_session, "get_engine", lambda: engine)
    return engine


class TestEmptyDatabase:
    def test_creates_the_schema(self, wired):
        db_session.init_db()

        assert inspect(wired).has_table("articles")
        assert inspect(wired).has_table("users")

    def test_stamps_alembic_at_head(self, wired):
        """Sin esto, el siguiente `alembic upgrade head` intentaría crear tablas
        que acaban de crearse y fallaría con DuplicateTable."""
        db_session.init_db()

        with wired.connect() as conn:
            assert inspect(wired).has_table("alembic_version")
            stamped = conn.execute(text("select version_num from alembic_version")).scalar()

        assert stamped == db_session.alembic_head_revision()


class TestVersionedDatabase:
    def test_leaves_the_schema_alone(self, wired):
        """Una base ya versionada la migra Alembic, no el arranque: si faltan
        tablas es porque falta `alembic upgrade head`, y crearlas por detrás
        volvería a desincronizar el registro de versiones."""
        with wired.begin() as conn:
            conn.execute(text("create table alembic_version (version_num varchar(32) not null)"))
            conn.execute(text("insert into alembic_version values ('c4d7b91f0a35')"))

        db_session.init_db()

        assert not inspect(wired).has_table("articles")

    def test_does_not_move_the_stamp(self, wired):
        with wired.begin() as conn:
            conn.execute(text("create table alembic_version (version_num varchar(32) not null)"))
            conn.execute(text("insert into alembic_version values ('c4d7b91f0a35')"))

        db_session.init_db()

        with wired.connect() as conn:
            assert (
                conn.execute(text("select version_num from alembic_version")).scalar()
                == "c4d7b91f0a35"
            )


class TestUnversionedButPopulated:
    def test_leaves_the_schema_alone(self, wired):
        """Tablas sin `alembic_version` es un estado ambiguo (¿esquema viejo?
        ¿nuevo?). Sellarlo en head podría marcar como aplicadas migraciones que
        nunca corrieron, así que se avisa y no se toca."""
        Base.metadata.tables["articles"].create(wired)

        db_session.init_db()

        assert not inspect(wired).has_table("users")
        assert not inspect(wired).has_table("alembic_version")

    def test_warns_so_the_state_does_not_pass_unnoticed(self, wired, caplog):
        Base.metadata.tables["articles"].create(wired)

        db_session.init_db()

        assert any("alembic" in r.message.lower() for r in caplog.records)


class TestHeadRevision:
    def test_matches_the_migration_scripts(self):
        """Si esto devuelve None, el sellado silenciosamente no ocurre y el bug
        original vuelve."""
        head = db_session.alembic_head_revision()

        assert head is not None
        assert len(head) == 12  # formato de identificador de Alembic
