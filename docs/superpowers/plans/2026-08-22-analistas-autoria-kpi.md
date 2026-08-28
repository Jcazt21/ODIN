# Analistas: autoría, filtro y exportación a Word — Plan de implementación

> **Para agentes:** SUB-SKILL REQUERIDA: usa superpowers:subagent-driven-development (recomendado) o superpowers:executing-plans para ejecutar este plan tarea por tarea. Los pasos usan checkbox (`- [ ]`) para seguimiento.

**Goal:** Que cada reporte guarde qué persona lo analizó y en qué fecha, que un admin pueda filtrar los reportes de un analista, y que pueda seleccionar los que quiera y exportarlos a Word.

**Caso de uso que lo define:** Juan (analista) analizó 7 reportes. El admin entra en Reportes, filtra por «Juan Pérez», ve sus 7 con la fecha de análisis de cada uno, marca los que necesita y los descarga en un documento.

**Architecture:** Hoy `core/auth.py` valida contra **una sola credencial del entorno** y firma todos los tokens con `settings.auth_username`, así que atribuir reportes sin tocar el login daría un único analista y un KPI de una fila. Por eso el plan empieza por una tabla `users` y mueve el login contra ella (el operador del `.env` se siembra como primer admin para no perder el acceso), y solo después agrega la columna de autoría, el filtro y el KPI.

**Tech Stack:** Python 3.13, FastAPI, SQLAlchemy 2.0, Alembic, PostgreSQL/SQLite/SQL Server, PyJWT, PBKDF2 de la stdlib (ya implementado), `python-docx` (dependencia nueva; su única dependencia es `lxml`, ya presente), React 19 + TanStack Query, Vitest + Testing Library.

**Spec:** [`docs/planning/2026-08-21-requerimientos-cliente-gap.md`](../../planning/2026-08-21-requerimientos-cliente-gap.md) — requerimientos **R19** (usuarios documentalistas), **R20** (KPI) y **R22** (exportar a `.doc`), fase **F5**. Las decisiones de diseño propias de este plan están en «Decisiones» más abajo.

---

## Global Constraints

- **Rama `dev`**, nunca `main`. No crear branches ni worktrees salvo petición explícita (`CLAUDE.md`).
- **NO hacer commits.** `CLAUDE.md` es explícito: los commits los hace el usuario a mano. Por eso ninguna tarea de este plan termina en `git commit` — terminan dejando el working tree limpio y verificado. **Si estás ejecutando este plan, no commitees aunque tu skill de ejecución lo sugiera.**
- **Nunca llamar a la API de Gemini** en pruebas ni scripts de verificación (cuesta dinero). Este plan no toca analizadores, así que no debería surgir.
- **Tres motores de BD objetivo**: PostgreSQL (producción), SQLite (dev/tests) y SQL Server (cliente). Usar tipos genéricos del ORM; nada de SQL específico de un motor. Las migraciones que alteren tablas existentes usan `op.batch_alter_table` (SQLite no soporta `ALTER TABLE ADD CONSTRAINT`).
- **Alembic head actual: `a7c3e5f01b92`**. La primera migración de este plan encadena desde ahí.
- **Comandos de verificación** (desde la raíz del repo):
  - Backend: `.venv/bin/python -m pytest -q`
  - Lint/tipos: `.venv/bin/ruff check src/odin/ tests/` y `.venv/bin/mypy`
  - Frontend: `cd frontend && npx tsc -b && npm test && npm run lint`
  - `ruff format` está **apagado a propósito** en este repo (ver `.pre-commit-config.yaml`): no lo ejecutes.
- **Estado al empezar**: 335 pruebas de backend y 31 de frontend en verde. Cualquier tarea que las baje de ahí está incompleta.

## Decisiones

Se toman aquí para que ninguna tarea tenga que improvisarlas:

- **`analyst_id` (persona) NO es `analyzer_name` (motor).** `articles.analyzer_name`/`analyzed_at` ya existen y describen *qué modelo* produjo el análisis (`local`, `groq`, `gemini`). La columna nueva describe *qué persona* lo revisó y guardó. Nombres deliberadamente distintos; ambos conviven.
- **`analyst_id` es nullable.** Los artículos que entran por el rastreo masivo (`scrape_jobs`) no tienen persona detrás, y los ~existentes tampoco. NULL significa «automático / sin analista», y se muestra así.
- **`ON DELETE SET NULL`** desde `articles` hacia `users`: dar de baja a un analista no puede borrar reportes. Para retirar a alguien se usa `is_active`, no el borrado.
- **El KPI de esta entrega cuenta trabajo, no calidad.** Artículos guardados por analista, primer y último guardado, días activos. La «tasa de corrección sobre lo que propuso el modelo» que pide R20 necesita auditoría campo a campo (hoy re-analizar **sobrescribe** la fila) — eso es un plan aparte, y se documenta como pendiente en la Tarea 6.
- **El filtro por analista es para todos; el KPI es solo para admin.** Cualquier
  usuario con sesión puede filtrar reportes por quién los analizó (sirve para
  encontrar el trabajo propio). El KPI comparativo entre personas exige rol
  `admin`: es un dato de evaluación, no de operación.
- **`GET /api/articles` y `/api/articles/filters` pasan a exigir sesión.** Hoy
  responden `200` sin token (comprobado contra el contenedor). Añadirles la
  dimensión de analista sin cerrarlos publicaría los nombres del personal y
  quién hizo qué a cualquiera que alcance la API. Cerrarlos es de bajo riesgo:
  el frontend ya adjunta el token en cada petición (`request()` en
  `odin-api.ts`) y todas las pantallas viven detrás del login.
- **`GET /api/auth/me` devuelve también el rol**, para que el frontend pueda
  ocultar lo que es solo de admin. Sin eso la UI tendría que adivinarlo.
- **El operador del `.env` se migra, no se rompe.** Al arrancar, si la tabla `users` está vacía se siembra `settings.auth_username` con su hash actual y rol `admin`. Quien hoy entra, sigue entrando igual.

## Estructura de archivos

| Archivo | Responsabilidad |
|---|---|
| `src/odin/db/models.py` (modificar) | Modelo `User` + columna `articles.analyst_id` |
| `alembic/versions/b2d41f7a9c03_*.py` (crear) | Tabla `users` |
| `alembic/versions/c9e8b3d5107f_*.py` (crear) | `articles.analyst_id` |
| `src/odin/db/users.py` (crear) | Alta/consulta de usuarios y siembra del operador del entorno |
| `src/odin/core/auth.py` (modificar) | Login contra la tabla; `require_admin` |
| `src/odin/services/user_service.py` (crear) | CRUD de analistas (lógica de negocio) |
| `src/odin/api/routers/users.py` (crear) | `/api/analysts` y `/api/analysts/kpi` |
| `src/odin/services/article_service.py` (modificar) | Registrar autoría; filtro `analyst`; faceta |
| `src/odin/services/analyst_kpi_service.py` (crear) | Agregación del KPI |
| `frontend/src/lib/queries/analysts.ts` (crear) | Hooks de analistas y KPI |
| `frontend/src/components/reports/FilterBar.tsx` (modificar) | Selector de analista |
| `frontend/src/pages/AnalystsPage.tsx` (crear) | Administración de analistas + KPI |

---

### Task 1: Tabla `users` y siembra del operador

**Files:**
- Modify: `src/odin/db/models.py` (añadir al final, junto a los demás modelos)
- Create: `alembic/versions/b2d41f7a9c03_users_tabla_de_analistas.py`
- Create: `src/odin/db/users.py`
- Modify: `src/odin/api/__init__.py:102-125` (siembra en el `lifespan`)
- Test: `tests/db/test_users.py`

**Interfaces:**
- Produces:
  - `odin.db.models.User` con columnas `id: int`, `username: str`, `display_name: str`, `password_hash: str`, `role: str`, `is_active: bool`, `created_at`, `updated_at`
  - `odin.db.models.USER_ROLES: tuple[str, ...] = ("admin", "analista")`
  - `odin.db.users.get_by_username(session, username: str) -> User | None`
  - `odin.db.users.seed_operator(session) -> bool` — devuelve `True` si sembró

- [ ] **Step 1: Escribir la prueba que falla**

Crear `tests/db/test_users.py`:

```python
"""Pruebas de la tabla de analistas y de la siembra del operador del entorno.

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
                role="analista",
            )
        )
        db_session.commit()

        assert user_store.get_by_username(db_session, "jperez").display_name == "Juan Pérez"

    def test_is_case_insensitive(self, db_session):
        """Quien teclea "JPerez" al entrar es la misma persona que "jperez"."""
        db_session.add(
            User(username="jperez", display_name="Juan Pérez", password_hash="x", role="analista")
        )
        db_session.commit()

        assert user_store.get_by_username(db_session, "JPerez") is not None

    def test_returns_none_when_missing(self, db_session):
        assert user_store.get_by_username(db_session, "nadie") is None


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
```

**Aviso sobre `settings`:** `odin.core.config.Settings` es un
`@dataclass(frozen=True)`. `monkeypatch.setattr(settings, "auth_username", ...)`
lanza `FrozenInstanceError` — comprobado. Hay que sustituir el objeto completo
con `dataclasses.replace(...)` sobre la referencia que importó `db/users.py`,
que es justo lo que hace el helper `_with_settings` de arriba. No lo simplifiques
a un setattr directo.

- [ ] **Step 2: Correr la prueba y verificar que falla**

Run: `.venv/bin/python -m pytest tests/db/test_users.py -q`
Expected: FAIL con `ModuleNotFoundError: No module named 'odin.db.users'`

- [ ] **Step 3: Añadir el modelo `User`**

Al final de `src/odin/db/models.py`:

```python
# Roles del sistema. `analista` es quien captura y revisa reportes; `admin`
# además administra el catálogo de analistas.
USER_ROLES = ("admin", "analista")


class User(Base):
    """Una persona que usa Odin.

    Hasta ahora la autenticación era un operador único contra credenciales del
    entorno (ver `core/auth.py`). Esa forma hacía imposible el KPI que pide el
    cliente: si todos entran con la misma credencial, todos los reportes se
    atribuyen al mismo nombre y medir el trabajo por analista no significa nada.

    El operador del `.env` no desaparece: al arrancar se siembra como primer
    usuario con rol `admin` (`db/users.seed_operator`), así que quien hoy entra
    sigue entrando igual.
    """

    __tablename__ = "users"
    __table_args__ = (UniqueConstraint("username_key", name="uq_user_username"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

    username: Mapped[str] = mapped_column(String(80))          # "jperez", como se muestra
    # Clave de comparación en minúsculas: quien teclea "JPerez" al entrar es la
    # misma persona que "jperez", y el UNIQUE debe impedir ambas variantes.
    username_key: Mapped[str] = mapped_column(String(80), index=True)
    display_name: Mapped[str] = mapped_column(String(160))     # "Juan Pérez"
    password_hash: Mapped[str] = mapped_column(String(255))    # formato de core/auth.py
    role: Mapped[str] = mapped_column(String(20), default="analista")  # ver USER_ROLES

    # Dar de baja sin borrar: los reportes que firmó siguen atribuidos a él.
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, onupdate=_utcnow
    )

    def __repr__(self) -> str:  # pragma: no cover
        return f"<User {self.username} ({self.role})>"
```

- [ ] **Step 4: Crear el almacén de usuarios**

Crear `src/odin/db/users.py`:

```python
"""Consultas y siembra de la tabla de analistas.

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
        User(
            username=settings.auth_username,
            username_key=username_key(settings.auth_username),
            display_name=settings.auth_username,
            password_hash=stored,
            role="admin",
            is_active=True,
        )
    )
    session.commit()
    return True
```

- [ ] **Step 5: Correr las pruebas del almacén**

Run: `.venv/bin/python -m pytest tests/db/test_users.py -q`
Expected: PASS (8 pruebas)

- [ ] **Step 6: Escribir la migración**

Crear `alembic/versions/b2d41f7a9c03_users_tabla_de_analistas.py`:

```python
"""users: tabla de analistas

Sustituye al operador unico contra credenciales del entorno. El operador
existente no se pierde: `db/users.seed_operator()` lo inserta como primer
usuario admin en el arranque de la API.

Revision ID: b2d41f7a9c03
Revises: a7c3e5f01b92
Create Date: 2026-08-22 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'b2d41f7a9c03'
down_revision: Union[str, Sequence[str], None] = 'a7c3e5f01b92'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        'users',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('username', sa.String(length=80), nullable=False),
        sa.Column('username_key', sa.String(length=80), nullable=False),
        sa.Column('display_name', sa.String(length=160), nullable=False),
        sa.Column('password_hash', sa.String(length=255), nullable=False),
        sa.Column('role', sa.String(length=20), nullable=False, server_default='analista'),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('username_key', name='uq_user_username'),
    )
    op.create_index(op.f('ix_users_username_key'), 'users', ['username_key'], unique=False)


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(op.f('ix_users_username_key'), table_name='users')
    op.drop_table('users')
```

- [ ] **Step 7: Sembrar al arrancar**

En `src/odin/api/__init__.py`, junto al bloque que siembra las localidades (busca `seed_localities_failed`), añadir **después** de ese bloque:

```python
    # El operador del entorno se convierte en el primer analista admin. Va en su
    # propio try y con exception(): si esto falla en una base vacía, NADIE puede
    # entrar, y el traceback es lo único que lo explica.
    try:
        session = get_session()
        try:
            if user_store.seed_operator(session):
                log.info("seed_operator_created", username=settings.auth_username)
        finally:
            session.close()
    except Exception:
        log.exception("seed_operator_failed")
```

Y añadir el import junto a los otros `import odin.db.*`:

```python
import odin.db.users as user_store
```

Si `settings` no está importado en ese módulo, añadir también `from odin.core.config import settings`. Comprobar con:

```bash
grep -n "^from odin.core.config import settings\|^import odin.db" src/odin/api/__init__.py
```

- [ ] **Step 8: Verificar la migración contra una base limpia**

```bash
SC=/tmp/odin-plan && rm -f $SC.db
DATABASE_URL="sqlite:///$SC.db" .venv/bin/python -m alembic upgrade head
DATABASE_URL="sqlite:///$SC.db" .venv/bin/python -c "
import sqlite3; c=sqlite3.connect('$SC.db')
print([r[0] for r in c.execute(\"select name from sqlite_master where type='table' and name='users'\")])"
DATABASE_URL="sqlite:///$SC.db" .venv/bin/python -m alembic downgrade -1
```
Expected: `upgrade` sin error, imprime `['users']`, `downgrade` sin error.

- [ ] **Step 9: Verificar el conjunto**

Run: `.venv/bin/python -m pytest -q && .venv/bin/ruff check src/odin/ tests/ && .venv/bin/mypy`
Expected: 343 passed (335 + 8), ruff «All checks passed!», mypy «Success».

**NO commitear** — dejar los cambios en el working tree (ver Global Constraints).

---

### Task 2: Login contra la tabla

**Files:**
- Modify: `src/odin/core/auth.py:189-232` (`_credentials_ok`, `login`) y añadir `require_admin`
- Test: `tests/api/test_api_auth_users.py`

**Interfaces:**
- Consumes: `odin.db.users.get_by_username`, `odin.db.models.User` (Tarea 1)
- Produces:
  - `odin.core.auth.authenticate(username: str, password: str) -> User | None`
  - `odin.core.auth.require_admin(username: str = Depends(require_auth)) -> str` — 403 si el usuario no es admin
  - El claim `sub` del JWT sigue siendo el **username**, así que todos los endpoints existentes que usan `require_auth` no cambian.

- [ ] **Step 1: Escribir la prueba que falla**

Crear `tests/api/test_api_auth_users.py`:

```python
"""Pruebas del login contra la tabla de analistas.

Antes se validaba contra una credencial del entorno; ahora contra `users`. Lo
que no puede cambiar es el contrato hacia afuera: el token sigue llevando el
username en `sub`, para que los endpoints que ya usan `require_auth` no se
enteren.
"""
from __future__ import annotations

import pytest

import odin.db.users as user_store
from odin.core import auth
from odin.db.models import User


@pytest.fixture
def analyst(sqlite_sessionmaker):
    session = sqlite_sessionmaker()
    session.add(
        User(
            username="jperez",
            username_key="jperez",
            display_name="Juan Pérez",
            password_hash=auth.hash_password("clave-buena", iterations=1000),
            role="analista",
            is_active=True,
        )
    )
    session.commit()
    session.close()


class TestLogin:
    def test_accepts_a_registered_analyst(self, api_client, analyst):
        resp = api_client.post(
            "/api/auth/login", json={"username": "jperez", "password": "clave-buena"}
        )

        assert resp.status_code == 200
        assert resp.json()["username"] == "jperez"

    def test_rejects_a_wrong_password(self, api_client, analyst):
        resp = api_client.post(
            "/api/auth/login", json={"username": "jperez", "password": "clave-mala"}
        )

        assert resp.status_code == 401

    def test_rejects_an_unknown_user(self, api_client, analyst):
        resp = api_client.post(
            "/api/auth/login", json={"username": "nadie", "password": "clave-buena"}
        )

        assert resp.status_code == 401

    def test_rejects_a_deactivated_analyst(self, api_client, analyst, sqlite_sessionmaker):
        """Dar de baja tiene que cerrar el acceso de inmediato, sin borrar a la
        persona ni desatribuir lo que ya firmó."""
        session = sqlite_sessionmaker()
        user_store.get_by_username(session, "jperez").is_active = False
        session.commit()
        session.close()

        resp = api_client.post(
            "/api/auth/login", json={"username": "jperez", "password": "clave-buena"}
        )

        assert resp.status_code == 401

    def test_token_carries_the_username_so_existing_endpoints_keep_working(
        self, api_client, analyst
    ):
        token = api_client.post(
            "/api/auth/login", json={"username": "jperez", "password": "clave-buena"}
        ).json()["access_token"]

        me = api_client.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"})

        assert me.status_code == 200
        assert me.json()["username"] == "jperez"


class TestAuthenticate:
    def test_returns_the_user_row(self, api_client, analyst):
        found = auth.authenticate("jperez", "clave-buena")

        assert found is not None
        assert found.display_name == "Juan Pérez"

    def test_returns_none_on_bad_password(self, api_client, analyst):
        assert auth.authenticate("jperez", "clave-mala") is None
```

- [ ] **Step 2: Correr la prueba y verificar que falla**

Run: `.venv/bin/python -m pytest tests/api/test_api_auth_users.py -q`
Expected: FAIL — `AttributeError: module 'odin.core.auth' has no attribute 'authenticate'`, y los login fallan con 401 porque aún se comparan contra el entorno.

- [ ] **Step 3: Reemplazar la validación de credenciales**

En `src/odin/core/auth.py`, sustituir `_credentials_ok` (líneas 189-202) por:

```python
# Hash de descarte con el mismo coste que uno real. Se verifica contra él
# cuando el usuario no existe, para que "usuario inexistente" y "contraseña
# incorrecta" tarden lo mismo y el login no sea un oráculo de qué cuentas hay.
_DUMMY_HASH = hash_password("contraseña-que-nadie-usa")


def authenticate(username: str, password: str) -> "User | None":
    """Devuelve el usuario si las credenciales son válidas y está activo."""
    # Import local: `db.users` importa de este módulo (hash_password), así que
    # importarlo arriba cerraría el ciclo.
    import odin.db.users as user_store
    from odin.api import deps

    session = deps.get_session()
    try:
        user = user_store.get_by_username(session, username)
        stored = user.password_hash if user else _DUMMY_HASH
        password_ok = verify_password(password, stored)

        if not user or not password_ok or not user.is_active:
            return None
        # Se desprende de la sesión para poder leer sus atributos después de
        # cerrarla (el sessionmaker del proyecto usa expire_on_commit=False,
        # pero expunge lo hace explícito y no depende de esa configuración).
        session.expunge(user)
        return user
    finally:
        session.close()
```

Añadir el import de tipo al principio del módulo, bajo el `from __future__`:

```python
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from odin.db.models import User
```

- [ ] **Step 4: Usar `authenticate` en el login**

En la función `login` de `src/odin/core/auth.py`, reemplazar el bloque que va desde `if not _credentials_ok(...)` hasta el `return TokenResponse(...)` por:

```python
    user = authenticate(req.username.strip(), req.password)
    if user is None:
        _record_failure(ip)
        log.warning("login fallido para '%s' desde %s", req.username, ip)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Usuario o contraseña incorrectos.",
        )

    _failures.pop(ip, None)
    token, expires_in = create_token(user.username)
    log.info("login correcto de '%s' desde %s", user.username, ip)
    return TokenResponse(access_token=token, expires_in=expires_in, username=user.username)
```

- [ ] **Step 5: Añadir `require_admin`**

Justo debajo de `require_auth` en `src/odin/core/auth.py`:

```python
def require_admin(username: str = Depends(require_auth)) -> str:
    """Exige que el usuario del token tenga rol `admin`.

    El rol se lee de la BD en cada request y no del token: así, quitarle el rol
    a alguien surte efecto de inmediato en vez de esperar a que su JWT venza.
    """
    import odin.db.users as user_store
    from odin.api import deps

    session = deps.get_session()
    try:
        user = user_store.get_by_username(session, username)
        if user is None or not user.is_active or user.role != "admin":
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Se requiere rol de administrador.",
            )
        return username
    finally:
        session.close()
```

- [ ] **Step 6: Correr las pruebas del login**

Run: `.venv/bin/python -m pytest tests/api/test_api_auth_users.py -q`
Expected: PASS (7 pruebas)

- [ ] **Step 7: Verificar que no se rompió el login existente**

Run: `.venv/bin/python -m pytest -q`
Expected: todo verde. Si alguna prueba antigua asumía credenciales del entorno, **arreglar la prueba** creando el usuario en la BD, no revertir el login.

- [ ] **Step 8: Actualizar el docstring del módulo**

En `src/odin/core/auth.py`, sustituir el primer párrafo (líneas 1-15) por uno que diga la verdad nueva:

```python
"""Autenticación de Odin — login contra la tabla `users`, que devuelve un JWT
firmado (HS256).

Hasta la Tarea 2 de este plan había un único operador contra credenciales del
entorno. Ahora cada analista es una fila de `users`, porque atribuir reportes y
medir trabajo por persona exige que las personas existan.

Las credenciales del entorno siguen usándose, pero solo para SEMBRAR al primer
administrador cuando la tabla está vacía (ver `db/users.seed_operator`):

    ODIN_AUTH_USER            usuario del operador inicial (por defecto "admin")
    ODIN_AUTH_PASSWORD_HASH   hash PBKDF2 generado con scripts/hash_password.py
    ODIN_AUTH_PASSWORD        alternativa en claro (solo desarrollo)
    ODIN_JWT_SECRET           clave para firmar los tokens
    ODIN_JWT_TTL_HOURS        vigencia del token (por defecto 12)

Sin contraseña configurada no se siembra nada y nadie puede entrar: el sistema
queda cerrado por defecto en vez de abierto.
"""
```

- [ ] **Step 9: Verificar el conjunto**

Run: `.venv/bin/python -m pytest -q && .venv/bin/ruff check src/odin/ tests/ && .venv/bin/mypy`
Expected: 350 passed, ruff y mypy limpios. **NO commitear.**

---

### Task 3: Administración de analistas (API)

**Files:**
- Create: `src/odin/services/user_service.py`
- Create: `src/odin/api/routers/users.py`
- Modify: `src/odin/api/schemas.py` (añadir al final)
- Modify: `src/odin/api/__init__.py` (registrar el router)
- Test: `tests/api/test_api_analysts.py`

**Interfaces:**
- Consumes: `odin.db.users.get_by_username`, `odin.db.models.User`, `odin.core.auth.require_admin`, `odin.core.auth.hash_password`
- Produces:
  - `GET /api/analysts` → `list[AnalystResponse]`
  - `POST /api/analysts` (admin) → `AnalystResponse`, 201
  - `PUT /api/analysts/{analyst_id}` (admin) → `AnalystResponse`
  - Schemas `AnalystResponse{id, username, display_name, role, is_active, created_at}`, `AnalystPayload{username, display_name, password, role}`, `AnalystUpdatePayload{display_name?, password?, role?, is_active?}`

- [ ] **Step 1: Escribir la prueba que falla**

Crear `tests/api/test_api_analysts.py`:

```python
"""Pruebas del CRUD de analistas."""
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
                role="analista",
            ),
        ]
    )
    session.commit()
    session.close()


class TestList:
    def test_lists_analysts(self, api_client, people):
        resp = api_client.get("/api/analysts", headers=_headers())

        assert resp.status_code == 200
        assert {a["username"] for a in resp.json()} == {"jefe", "jperez"}

    def test_never_exposes_password_hashes(self, api_client, people):
        """Un hash filtrado es un ataque offline servido en bandeja."""
        body = api_client.get("/api/analysts", headers=_headers()).text

        assert "password_hash" not in body
        assert "pbkdf2" not in body


class TestCreate:
    def test_admin_creates_an_analyst(self, api_client, people):
        resp = api_client.post(
            "/api/analysts",
            json={
                "username": "mgomez",
                "display_name": "María Gómez",
                "password": "clave-inicial",
                "role": "analista",
            },
            headers=_headers(),
        )

        assert resp.status_code == 201
        assert resp.json()["username"] == "mgomez"

    def test_the_new_analyst_can_log_in(self, api_client, people):
        api_client.post(
            "/api/analysts",
            json={
                "username": "mgomez",
                "display_name": "María Gómez",
                "password": "clave-inicial",
                "role": "analista",
            },
            headers=_headers(),
        )

        login = api_client.post(
            "/api/auth/login", json={"username": "mgomez", "password": "clave-inicial"}
        )

        assert login.status_code == 200

    def test_a_plain_analyst_cannot_create_analysts(self, api_client, people):
        resp = api_client.post(
            "/api/analysts",
            json={
                "username": "otro",
                "display_name": "Otro",
                "password": "x",
                "role": "analista",
            },
            headers=_headers("jperez"),
        )

        assert resp.status_code == 403

    def test_rejects_a_duplicate_username(self, api_client, people):
        resp = api_client.post(
            "/api/analysts",
            json={
                "username": "JPerez",
                "display_name": "Otro Juan",
                "password": "x",
                "role": "analista",
            },
            headers=_headers(),
        )

        assert resp.status_code == 409

    def test_rejects_an_unknown_role(self, api_client, people):
        resp = api_client.post(
            "/api/analysts",
            json={
                "username": "otro",
                "display_name": "Otro",
                "password": "x",
                "role": "superusuario",
            },
            headers=_headers(),
        )

        assert resp.status_code == 422


class TestUpdate:
    def test_deactivates_an_analyst(self, api_client, people, sqlite_sessionmaker):
        import odin.db.users as user_store

        session = sqlite_sessionmaker()
        target = user_store.get_by_username(session, "jperez").id
        session.close()

        resp = api_client.put(
            f"/api/analysts/{target}", json={"is_active": False}, headers=_headers()
        )

        assert resp.status_code == 200
        assert resp.json()["is_active"] is False

    def test_resets_a_password(self, api_client, people, sqlite_sessionmaker):
        import odin.db.users as user_store

        session = sqlite_sessionmaker()
        target = user_store.get_by_username(session, "jperez").id
        session.close()

        api_client.put(
            f"/api/analysts/{target}", json={"password": "clave-nueva"}, headers=_headers()
        )
        login = api_client.post(
            "/api/auth/login", json={"username": "jperez", "password": "clave-nueva"}
        )

        assert login.status_code == 200
```

- [ ] **Step 2: Correr la prueba y verificar que falla**

Run: `.venv/bin/python -m pytest tests/api/test_api_analysts.py -q`
Expected: FAIL con 404 en todas las rutas (el router no existe).

- [ ] **Step 3: Añadir los schemas**

Al final de `src/odin/api/schemas.py`:

```python
# --- Analistas ---------------------------------------------------------------
# Espejo de USER_ROLES en db/models.py. Se repite porque la capa HTTP valida en
# el borde: un rol inválido debe dar 422, no un dato inconsistente en la tabla.
ANALYST_ROLE_VALUES = ("admin", "analista")


class AnalystResponse(_ResponseModel):
    """Nunca incluye `password_hash`: exponerlo convertiría un listado de
    lectura en un ataque offline contra las contraseñas."""

    id: int
    username: str
    display_name: str
    role: str
    is_active: bool
    created_at: datetime


class AnalystPayload(BaseModel):
    username: str
    display_name: str
    password: str
    role: str = "analista"


class AnalystUpdatePayload(BaseModel):
    display_name: str | None = None
    password: str | None = None
    role: str | None = None
    is_active: bool | None = None
```

- [ ] **Step 4: Escribir el servicio**

Crear `src/odin/services/user_service.py`:

```python
"""Lógica de negocio del catálogo de analistas."""
from __future__ import annotations

from fastapi import HTTPException
from sqlalchemy import select

import odin.db.users as user_store
from odin.api import deps
from odin.api.deps import log
from odin.api.schemas import (
    ANALYST_ROLE_VALUES,
    AnalystPayload,
    AnalystResponse,
    AnalystUpdatePayload,
)
from odin.core.auth import hash_password
from odin.db.models import User


def _check_role(role: str) -> None:
    if role not in ANALYST_ROLE_VALUES:
        raise HTTPException(
            status_code=422,
            detail=f"Rol inválido: '{role}'. Válidos: {', '.join(ANALYST_ROLE_VALUES)}.",
        )


def list_analysts(include_inactive: bool = True) -> list[AnalystResponse]:
    session = deps.get_session()
    try:
        stmt = select(User)
        if not include_inactive:
            stmt = stmt.where(User.is_active.is_(True))
        rows = session.scalars(stmt.order_by(User.display_name)).all()
        return [AnalystResponse.model_validate(r) for r in rows]
    finally:
        session.close()


def create_analyst(payload: AnalystPayload) -> AnalystResponse:
    _check_role(payload.role)
    username = payload.username.strip()
    if not username or not payload.password:
        raise HTTPException(status_code=422, detail="Usuario y contraseña son obligatorios.")

    session = deps.get_session()
    try:
        if user_store.get_by_username(session, username):
            raise HTTPException(status_code=409, detail=f"El usuario '{username}' ya existe.")

        row = User(
            username=username,
            username_key=user_store.username_key(username),
            display_name=payload.display_name.strip() or username,
            password_hash=hash_password(payload.password),
            role=payload.role,
            is_active=True,
        )
        session.add(row)
        session.commit()
        return AnalystResponse.model_validate(row)
    except HTTPException:
        raise
    except Exception:
        session.rollback()
        log.exception("analyst_creation_failed")
        raise HTTPException(status_code=500, detail="Error interno creando el analista.") from None
    finally:
        session.close()


def update_analyst(analyst_id: int, payload: AnalystUpdatePayload) -> AnalystResponse:
    """Renombra, cambia el rol, resetea la contraseña o da de baja.

    No permite cambiar el `username`: es la identidad con la que se firmaron los
    reportes ya guardados y aparece en los KPI históricos.
    """
    if payload.role is not None:
        _check_role(payload.role)

    session = deps.get_session()
    try:
        row = session.get(User, analyst_id)
        if not row:
            raise HTTPException(status_code=404, detail="Analista no encontrado.")

        if payload.display_name is not None:
            row.display_name = payload.display_name.strip() or row.username
        if payload.role is not None:
            row.role = payload.role
        if payload.is_active is not None:
            row.is_active = payload.is_active
        if payload.password:
            row.password_hash = hash_password(payload.password)

        session.commit()
        return AnalystResponse.model_validate(row)
    except HTTPException:
        raise
    except Exception:
        session.rollback()
        log.exception("analyst_update_failed", analyst_id=analyst_id)
        raise HTTPException(
            status_code=500, detail="Error interno actualizando el analista."
        ) from None
    finally:
        session.close()
```

- [ ] **Step 5: Escribir el router**

Crear `src/odin/api/routers/users.py`:

```python
"""Catálogo de analistas y su KPI."""
from __future__ import annotations

from fastapi import APIRouter, Depends

from odin.api.schemas import AnalystPayload, AnalystResponse, AnalystUpdatePayload
from odin.core import auth
from odin.services import user_service

router = APIRouter(tags=["analysts"])


@router.get(
    "/api/analysts",
    dependencies=[Depends(auth.require_auth)],
    response_model=list[AnalystResponse],
)
def list_analysts(include_inactive: bool = True):
    """Analistas registrados. Cualquier usuario autenticado puede verlos: son
    los valores del filtro de reportes."""
    return user_service.list_analysts(include_inactive)


@router.post(
    "/api/analysts",
    status_code=201,
    dependencies=[Depends(auth.require_admin)],
    response_model=AnalystResponse,
)
def create_analyst(payload: AnalystPayload):
    """Da de alta a un analista con su contraseña inicial."""
    return user_service.create_analyst(payload)


@router.put(
    "/api/analysts/{analyst_id}",
    dependencies=[Depends(auth.require_admin)],
    response_model=AnalystResponse,
)
def update_analyst(analyst_id: int, payload: AnalystUpdatePayload):
    """Renombra, cambia el rol, resetea la contraseña o da de baja."""
    return user_service.update_analyst(analyst_id, payload)
```

- [ ] **Step 6: Registrar el router**

En `src/odin/api/__init__.py`, añadir `users` a la lista de imports de `odin.api.routers` (está en orden alfabético) y registrar:

```python
app.include_router(users.router)
```

- [ ] **Step 7: Correr las pruebas**

Run: `.venv/bin/python -m pytest tests/api/test_api_analysts.py -q`
Expected: PASS (9 pruebas)

- [ ] **Step 8: Verificar el conjunto**

Run: `.venv/bin/python -m pytest -q && .venv/bin/ruff check src/odin/ tests/ && .venv/bin/mypy`
Expected: 359 passed, limpio. **NO commitear.**

---

### Task 4: Autoría y fecha de análisis

**Files:**
- Modify: `src/odin/db/models.py` (columna en `Article`, junto a `analyzer_name`)
- Create: `alembic/versions/c9e8b3d5107f_articles_analista_que_lo_guardo.py`
- Modify: `src/odin/services/article_service.py:369` (`save_article`) y `:319` (`update_article`)
- Modify: `src/odin/api/routers/articles.py:96-105`
- Modify: `src/odin/api/schemas.py` (`ArticleSummary`, `ArticleDetail`)
- Test: `tests/api/test_api_article_authorship.py`

**Interfaces:**
- Consumes: `odin.db.models.User` (Tarea 1)
- Produces:
  - `articles.analyst_id: int | None` FK → `users.id` `ON DELETE SET NULL`
  - `articles.analyzed_on: date | None` — día/mes/año, **sin hora**
  - `article_service.save_article(req, analyst_username: str | None = None)`
  - `article_service.update_article(article_id, payload, analyst_username: str | None = None)`
  - `ArticleSummary.analyst` y `ArticleDetail.analyst`: `str | None` (nombre para mostrar)
  - `ArticleSummary.analyzed_on` y `ArticleDetail.analyzed_on`: `date | None`

- [ ] **Step 1: Escribir la prueba que falla**

Crear `tests/api/test_api_article_authorship.py`:

```python
"""Pruebas de la autoría del reporte.

`analyst` (persona) y `analyzer_name` (motor) son cosas distintas y ambas se
guardan: quién lo revisó, y qué modelo lo produjo.
"""
from __future__ import annotations

import pytest

from odin.core import auth
from odin.core.auth import create_token
from odin.db.models import User


def _headers(username: str = "jperez"):
    token, _ = create_token(username)
    return {"Authorization": f"Bearer {token}"}


def _payload(url: str = "https://listindiario.com/n1") -> dict:
    return {
        "source": "listin_diario",
        "url": url,
        "title": "Título de prueba",
        "body": "cuerpo",
        "main_topic": "agua potable",
        "overall_sentiment": "NEU",
    }


@pytest.fixture
def analyst(sqlite_sessionmaker):
    session = sqlite_sessionmaker()
    session.add(
        User(
            username="jperez",
            username_key="jperez",
            display_name="Juan Pérez",
            password_hash=auth.hash_password("x", iterations=1000),
            role="analista",
        )
    )
    session.commit()
    session.close()


class TestSaveRecordsAuthorship:
    def test_saving_records_who_did_it(self, api_client, analyst):
        resp = api_client.post("/api/articles", json=_payload(), headers=_headers())

        assert resp.status_code == 200
        assert resp.json()["analyst"] == "Juan Pérez"

    def test_authorship_survives_in_the_listing(self, api_client, analyst):
        api_client.post("/api/articles", json=_payload(), headers=_headers())

        items = api_client.get("/api/articles").json()["items"]

        assert items[0]["analyst"] == "Juan Pérez"

    def test_articles_without_a_person_report_no_analyst(
        self, api_client, analyst, sqlite_sessionmaker
    ):
        """Lo que entra por el rastreo masivo no tiene persona detrás."""
        from datetime import datetime

        from odin.db.models import Article

        session = sqlite_sessionmaker()
        session.add(
            Article(
                source="diario_libre",
                url="https://diariolibre.com/auto",
                title="Automático",
                body="x",
                published_at=datetime(2026, 8, 1),
            )
        )
        session.commit()
        session.close()

        items = api_client.get("/api/articles").json()["items"]
        automatic = [i for i in items if i["url"].endswith("/auto")][0]

        assert automatic["analyst"] is None

    def test_rectifying_reassigns_authorship_to_whoever_corrected_it(
        self, api_client, analyst, sqlite_sessionmaker
    ):
        """Si otra persona corrige el análisis, el reporte pasa a ser suyo: el
        KPI mide quién dejó el dato como está, no quién lo tocó primero."""
        session = sqlite_sessionmaker()
        session.add(
            User(
                username="mgomez",
                username_key="mgomez",
                display_name="María Gómez",
                password_hash=auth.hash_password("x", iterations=1000),
                role="analista",
            )
        )
        session.commit()
        session.close()

        created = api_client.post("/api/articles", json=_payload(), headers=_headers()).json()
        updated = api_client.put(
            f"/api/articles/{created['id']}",
            json={"main_topic": "energía eléctrica"},
            headers=_headers("mgomez"),
        )

        assert updated.status_code == 200
        assert updated.json()["analyst"] == "María Gómez"

    def test_an_unknown_username_leaves_no_analyst_instead_of_failing(
        self, api_client, analyst
    ):
        """Un token válido de alguien ya borrado no puede tumbar el guardado."""
        resp = api_client.post("/api/articles", json=_payload(), headers=_headers("fantasma"))

        assert resp.status_code == 200
        assert resp.json()["analyst"] is None
```

- [ ] **Step 2: Correr la prueba y verificar que falla**

Run: `.venv/bin/python -m pytest tests/api/test_api_article_authorship.py -q`
Expected: FAIL con `KeyError: 'analyst'`

- [ ] **Step 3: Añadir la columna al modelo**

En `src/odin/db/models.py`, dentro de `Article`, inmediatamente **después** del bloque de linaje del análisis (`analyzed_at`), añadir:

```python
    # --- Autoría humana (≠ linaje del análisis) ---
    # OJO: `analyzer_name`/`analyzed_at` de arriba dicen QUÉ MODELO produjo el
    # análisis. Esto dice QUÉ PERSONA lo revisó y lo dejó guardado. Son datos
    # distintos y ambos hacen falta: el primero explica un resultado, el segundo
    # sostiene el KPI por analista que pidió el cliente.
    #
    # Nulo a propósito en dos casos: los artículos que entran por el rastreo
    # masivo (no hay persona detrás) y los guardados antes de esta columna.
    # SET NULL y no CASCADE: dar de baja a un analista jamás puede borrar
    # reportes.
    analyst_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), index=True, nullable=True
    )
    # Fecha en que el analista lo trabajó: día, mes y año. `Date` y no
    # `DateTime` a propósito — el cliente pidió la fecha sin hora, y guardarla
    # como fecha lo deja dicho en el esquema, en vez de depender de que toda
    # consulta y toda pantalla se acuerden de recortar la hora. Además hace
    # trivial agrupar por día, que es la unidad del KPI.
    analyzed_on: Mapped[date | None] = mapped_column(Date, index=True, nullable=True)
```

Añadir los imports que falten en la cabecera de `src/odin/db/models.py`:

```python
from datetime import UTC, date, datetime   # `date` es nuevo
from sqlalchemy import Date                # junto a Boolean, DateTime, Float...
```

Y junto a las demás relaciones de `Article`:

```python
    analyst: Mapped[User | None] = relationship(foreign_keys=[analyst_id])
```

- [ ] **Step 4: Escribir la migración**

Crear `alembic/versions/c9e8b3d5107f_articles_analista_que_lo_guardo.py`:

```python
"""articles: analista y fecha de analisis

Autoria humana, distinta del linaje del analisis (`analyzer_name`, que dice que
MODELO lo produjo). Nulo en lo ya guardado y en lo que entra por el rastreo
masivo: no hay forma de reconstruir retroactivamente quien reviso que.

Revision ID: c9e8b3d5107f
Revises: b2d41f7a9c03
Create Date: 2026-08-22 12:30:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'c9e8b3d5107f'
down_revision: Union[str, Sequence[str], None] = 'b2d41f7a9c03'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # batch_alter_table: SQLite no soporta ALTER TABLE ADD CONSTRAINT directo;
    # en Postgres y SQL Server emite el mismo ALTER nativo sin cambios.
    with op.batch_alter_table('articles', schema=None) as batch_op:
        batch_op.add_column(sa.Column('analyst_id', sa.Integer(), nullable=True))
        # Date y no DateTime: el requisito es dia/mes/anio sin hora.
        batch_op.add_column(sa.Column('analyzed_on', sa.Date(), nullable=True))
        batch_op.create_index(
            batch_op.f('ix_articles_analyst_id'), ['analyst_id'], unique=False
        )
        batch_op.create_index(
            batch_op.f('ix_articles_analyzed_on'), ['analyzed_on'], unique=False
        )
        batch_op.create_foreign_key(
            'fk_articles_analyst_id_users', 'users', ['analyst_id'], ['id'], ondelete='SET NULL'
        )


def downgrade() -> None:
    """Downgrade schema."""
    with op.batch_alter_table('articles', schema=None) as batch_op:
        batch_op.drop_constraint('fk_articles_analyst_id_users', type_='foreignkey')
        batch_op.drop_index(batch_op.f('ix_articles_analyzed_on'))
        batch_op.drop_index(batch_op.f('ix_articles_analyst_id'))
        batch_op.drop_column('analyzed_on')
        batch_op.drop_column('analyst_id')
```

- [ ] **Step 5: Exponer el analista en los schemas**

En `src/odin/api/schemas.py`, añadir el campo a `ArticleSummary` y a `ArticleDetail` (buscar `class ArticleSummary` y `class ArticleDetail`):

```python
    # Nombre para mostrar del analista que dejó guardado el reporte. `None` en
    # lo que entró por el rastreo masivo o antes de que existiera la columna.
    analyst: str | None = None
    # Fecha del análisis, sin hora. No confundir con `published_at` (cuándo lo
    # publicó el medio): una nota de la semana pasada puede analizarse hoy.
    analyzed_on: date | None = None
```

Si `date` no está importado en `schemas.py`, añadirlo: `from datetime import date, datetime`.

- [ ] **Step 6: Registrar la autoría al guardar y al rectificar**

En `src/odin/services/article_service.py`:

a) Añadir el helper cerca de la cabecera del módulo, tras los imports:

```python
def _analyst_id_for(session, username: str | None) -> int | None:
    """Traduce el usuario del token a un id de `users`.

    Devuelve `None` si no hay usuario o si ya no existe (un JWT válido de
    alguien dado de baja): perder la atribución es aceptable, tumbar el guardado
    del analista no.
    """
    if not username:
        return None
    import odin.db.users as user_store

    user = user_store.get_by_username(session, username)
    return user.id if user else None
```

b) Cambiar la firma de `save_article` (línea 369) a:

```python
def save_article(req: SaveArticleRequest, analyst_username: str | None = None) -> ArticleDetail:
```

y añadir dentro del constructor de `Article(...)`, junto a los demás campos:

```python
            analyst_id=_analyst_id_for(session, analyst_username),
            analyzed_on=datetime.now(UTC).date(),
```

c) Cambiar la firma de `update_article` (línea 319) a:

```python
def update_article(article_id: int, payload, analyst_username: str | None = None) -> ArticleDetail:
```

y, justo antes del `session.commit()` de esa función, añadir:

```python
        # La rectificación reasigna la autoría: el KPI mide quién dejó el dato
        # como está, no quién lo tocó primero.
        rectifier = _analyst_id_for(session, analyst_username)
        if rectifier is not None:
            article.analyst_id = rectifier
            article.analyzed_on = datetime.now(UTC).date()
```

d) En `serialize_summary` y en `serialize_article`, añadir al constructor de la respuesta:

```python
        analyst=article.analyst.display_name if article.analyst else None,
        analyzed_on=article.analyzed_on,
```

- [ ] **Step 7: Pasar el usuario desde el router**

En `src/odin/api/routers/articles.py`, cambiar las dos rutas de escritura para que **reciban** el usuario en vez de solo exigirlo:

```python
@router.put("/api/articles/{article_id}", response_model=ArticleDetail)
def update_article(
    article_id: int,
    payload: ArticleUpdatePayload,
    analyst: str = Depends(auth.require_auth),
):
    """Rectifica el análisis de un artículo ya guardado (§8.2): tema, encuadre,
    sentimiento, actores señalados... Solo toca los campos enviados. No permite
    corregir `title`/`body`/`url` porque eso es lo que decía la fuente, no un
    juicio del sistema — si el scrape en sí está mal, hay que borrar y volver a
    analizar.

    Rectificar reasigna la autoría a quien corrige."""
    return article_service.update_article(article_id, payload, analyst_username=analyst)


@router.post("/api/articles", response_model=ArticleDetail)
def save_article(req: SaveArticleRequest, analyst: str = Depends(auth.require_auth)):
    """Persiste el resultado de /api/analyze, ya revisado/corregido, y registra
    qué analista lo dejó guardado."""
    return article_service.save_article(req, analyst_username=analyst)
```

**Importante:** se elimina `dependencies=[Depends(auth.require_auth)]` del decorador porque la dependencia pasa a ser un parámetro; la protección es la misma. `delete_article` no cambia.

- [ ] **Step 8: Correr las pruebas**

Run: `.venv/bin/python -m pytest tests/api/test_api_article_authorship.py -q`
Expected: PASS (5 pruebas)

- [ ] **Step 9: Verificar la migración y el conjunto**

```bash
SC=/tmp/odin-plan && rm -f $SC.db
DATABASE_URL="sqlite:///$SC.db" .venv/bin/python -m alembic upgrade head
DATABASE_URL="sqlite:///$SC.db" .venv/bin/python -m alembic downgrade -1
.venv/bin/python -m pytest -q && .venv/bin/ruff check src/odin/ tests/ && .venv/bin/mypy
```
Expected: migración sube y baja sin error; 364 passed; limpio. **NO commitear.**

---

### Task 5: Filtro por analista (y cierre del listado)

**Files:**
- Modify: `src/odin/services/article_service.py:62-115` (`_apply_article_filters`), `:180-244` (`list_articles`), `:247` (`article_filters`)
- Modify: `src/odin/api/routers/articles.py:20-64` (parámetro `analyst` **y** `require_auth` en las dos rutas GET)
- Modify: `src/odin/api/schemas.py` (`ArticleFiltersResponse`)
- Modify: `tests/test_quick_wins.py`, `tests/api/test_api_filters.py`, `tests/api/test_api_localities.py` (20 llamadas que hoy no envían token)
- Test: `tests/api/test_api_article_authorship.py` (añadir clase)

**Interfaces:**
- Consumes: `articles.analyst_id` (Tarea 4)
- Produces:
  - `GET /api/articles?analyst=<id>` filtra por analista, **ahora tras `require_auth`**
  - `GET /api/articles/filters` también tras `require_auth`
  - `ArticleFiltersResponse.analysts: list[AnalystOption]` con `AnalystOption{id, display_name}`

- [ ] **Step 1: Escribir la prueba que falla**

Añadir al final de `tests/api/test_api_article_authorship.py`:

```python
class TestFilterByAnalyst:
    def _two_analysts_one_article_each(self, api_client, sqlite_sessionmaker):
        session = sqlite_sessionmaker()
        session.add(
            User(
                username="mgomez",
                username_key="mgomez",
                display_name="María Gómez",
                password_hash=auth.hash_password("x", iterations=1000),
                role="analista",
            )
        )
        session.commit()
        ids = {u.username: u.id for u in session.query(User).all()}
        session.close()

        api_client.post(
            "/api/articles",
            json=_payload("https://listindiario.com/de-juan"),
            headers=_headers("jperez"),
        )
        api_client.post(
            "/api/articles",
            json=_payload("https://listindiario.com/de-maria"),
            headers=_headers("mgomez"),
        )
        return ids

    def test_filters_to_a_single_analyst(self, api_client, analyst, sqlite_sessionmaker):
        ids = self._two_analysts_one_article_each(api_client, sqlite_sessionmaker)

        resp = api_client.get("/api/articles", params={"analyst": ids["jperez"]})

        assert resp.json()["total"] == 1
        assert resp.json()["items"][0]["url"].endswith("/de-juan")

    def test_without_the_filter_everything_shows(self, api_client, analyst, sqlite_sessionmaker):
        self._two_analysts_one_article_each(api_client, sqlite_sessionmaker)

        assert api_client.get("/api/articles").json()["total"] == 2

    def test_filter_options_list_the_analysts(self, api_client, analyst, sqlite_sessionmaker):
        self._two_analysts_one_article_each(api_client, sqlite_sessionmaker)

        facets = api_client.get("/api/articles/filters").json()

        assert {a["display_name"] for a in facets["analysts"]} == {"Juan Pérez", "María Gómez"}
```

- [ ] **Step 2: Correr la prueba y verificar que falla**

Run: `.venv/bin/python -m pytest tests/api/test_api_article_authorship.py::TestFilterByAnalyst -q`
Expected: FAIL — el filtro se ignora (`total == 2`) y `KeyError: 'analysts'`

- [ ] **Step 3: Añadir el schema de la faceta**

En `src/odin/api/schemas.py`, antes de `class ArticleFiltersResponse`:

```python
class AnalystOption(_ResponseModel):
    """Un analista tal como lo consume el selector de filtros."""

    id: int
    display_name: str
```

y dentro de `ArticleFiltersResponse`:

```python
    analysts: list[AnalystOption] = []
```

- [ ] **Step 4: Implementar el filtro**

En `src/odin/services/article_service.py`:

a) Añadir el parámetro a `_apply_article_filters`, junto a `locality`:

```python
    analyst: int | None = None,
```

b) Dentro de esa función, junto al bloque de `locality`:

```python
    if analyst is not None:
        conditions.append(Article.analyst_id == analyst)
```

c) Añadir `analyst: int | None,` a la firma de `list_articles` y pasarlo en la llamada a `_apply_article_filters`:

```python
            analyst=analyst,
```

d) En `article_filters()`, antes del `return`, añadir la lista de analistas y devolverla:

```python
        analysts = [
            AnalystOption(id=u.id, display_name=u.display_name)
            for u in session.scalars(
                select(User)
                .join(Article, Article.analyst_id == User.id)
                .distinct()
                .order_by(User.display_name)
            ).all()
        ]
```

Añadir `analysts=analysts` al constructor de `ArticleFiltersResponse`, e importar `AnalystOption` y `User`:

```python
from odin.api.schemas import AnalystOption  # junto a los demás schemas
from odin.db.models import Article, ArticleLocality, CanonicalEntity, Entity, Locality, User
```

- [ ] **Step 5: Exponer el parámetro en el router**

En `src/odin/api/routers/articles.py`, añadir a `list_articles` junto a `locality`:

```python
    analyst: int | None = None,
```

y en la llamada al servicio:

```python
        analyst=analyst,
```

Ampliar el docstring:

```
    `analyst` es el id del analista que dejó guardado el reporte.
```

- [ ] **Step 6: Correr las pruebas del filtro**

Run: `.venv/bin/python -m pytest tests/api/test_api_article_authorship.py -q`
Expected: PASS (8 pruebas). Las pruebas de esta clase ya envían token porque
guardan artículos; el cierre del listado del paso siguiente no las afecta.

- [ ] **Step 7: Escribir la prueba de que el listado exige sesión**

Añadir al final de `tests/api/test_api_article_authorship.py`:

```python
class TestListingRequiresAuth:
    def test_listing_rejects_anonymous_requests(self, api_client):
        """La atribución por analista son nombres de personal: el listado no
        puede seguir respondiendo sin credenciales."""
        assert api_client.get("/api/articles").status_code in (401, 403)

    def test_filter_options_reject_anonymous_requests(self, api_client):
        assert api_client.get("/api/articles/filters").status_code in (401, 403)

    def test_listing_works_with_a_token(self, api_client, analyst):
        assert api_client.get("/api/articles", headers=_headers()).status_code == 200
```

- [ ] **Step 8: Correr la prueba y verificar que falla**

Run: `.venv/bin/python -m pytest tests/api/test_api_article_authorship.py::TestListingRequiresAuth -q`
Expected: FAIL — las dos primeras devuelven 200 en vez de 401.

- [ ] **Step 9: Cerrar las dos rutas GET**

En `src/odin/api/routers/articles.py`, añadir la dependencia a los dos
decoradores de lectura:

```python
@router.get(
    "/api/articles",
    dependencies=[Depends(auth.require_auth)],
    response_model=ArticleListResponse,
)
```

```python
@router.get(
    "/api/articles/filters",
    dependencies=[Depends(auth.require_auth)],
    response_model=ArticleFiltersResponse,
)
```

`GET /api/articles/{article_id}` (el detalle) se cierra igual, por coherencia:
un id adivinable no debe entregar el reporte completo sin sesión.

```python
@router.get(
    "/api/articles/{article_id}",
    dependencies=[Depends(auth.require_auth)],
    response_model=ArticleDetail,
)
```

- [ ] **Step 10: Arreglar las llamadas de prueba que no enviaban token**

Cerrar el listado rompe **20 llamadas** repartidas en tres archivos. No es un
fallo de esas pruebas: es que el endpoint cambió de contrato. Localizarlas:

```bash
grep -rn 'get("/api/articles' tests/ | grep -v "headers="
```

En cada archivo afectado (`tests/test_quick_wins.py`,
`tests/api/test_api_filters.py`, `tests/api/test_api_localities.py`), añadir el
helper si no existe:

```python
from odin.core.auth import create_token


def _auth_headers():
    token, _ = create_token("tester")
    return {"Authorization": f"Bearer {token}"}
```

y pasar `headers=_auth_headers()` en cada llamada afectada. `create_token` firma
un JWT sin consultar la BD, así que sirve aunque el usuario "tester" no exista:
`require_auth` solo valida la firma. (`require_admin` sí consulta la BD — por
eso las pruebas del KPI de la Tarea 6 necesitan un admin real.)

`tests/api/test_api_localities.py` ya tiene su propio `_auth_headers`; reusarlo.

- [ ] **Step 11: Verificar el conjunto**

Run: `.venv/bin/python -m pytest -q && .venv/bin/ruff check src/odin/ tests/ && .venv/bin/mypy`
Expected: 370 passed, limpio. Si queda alguna prueba en rojo por un 401, es una
llamada sin token que se escapó del paso 10. **NO commitear.**

---
### Task 6: Exportación a `.doc` de los reportes seleccionados

**Files:**
- Modify: `requirements.txt` (añadir `python-docx`)
- Create: `src/odin/services/export_service.py`
- Modify: `src/odin/api/routers/articles.py` (ruta de exportación)
- Modify: `src/odin/api/schemas.py` (payload de exportación)
- Test: `tests/api/test_api_export.py`

**Interfaces:**
- Consumes: `articles.analyst_id`, `articles.analyzed_on` (Tarea 4); `article_service.serialize_article`
- Produces:
  - `POST /api/articles/export` con cuerpo `ExportRequest{article_ids: list[int]}` → `.docx` binario
  - `export_service.build_document(articles) -> bytes`

**Por qué `.docx` y no un `.doc` de verdad:** el `.doc` binario de Word 97 no
tiene ninguna librería mantenida en Python, y el atajo habitual —servir HTML con
`Content-Type: application/msword`— produce un archivo que Word abre pero que no
es un documento real: se rompe al editarlo y algunas versiones avisan de que el
formato no coincide. `python-docx` genera un `.docx` legítimo, que es lo que
cualquier Word desde 2007 entiende por «documento de Word». Su única dependencia
es `lxml`, que **este proyecto ya usa** para el scraping, así que el peso añadido
es mínimo. Si el cliente exige literalmente la extensión `.doc`, es una decisión
suya que hay que tomar antes de construir: dilo y se cambia el enfoque.

- [ ] **Step 1: Añadir la dependencia**

En `requirements.txt`, al final, con su propia sección:

```
# --- Exportación de reportes ---
python-docx>=1.1         # genera .docx; su única dependencia es lxml, ya presente
```

Instalar:

```bash
.venv/bin/pip install "python-docx>=1.1"
.venv/bin/python -c "import docx; print(docx.__version__)"
```
Expected: imprime la versión sin error.

- [ ] **Step 2: Escribir la prueba que falla**

Crear `tests/api/test_api_export.py`:

```python
"""Pruebas de la exportación a Word.

El caso del cliente: el admin filtra los reportes de un analista, selecciona
los que quiere y los baja en un documento.
"""
from __future__ import annotations

import io
from datetime import date, datetime

import pytest
from docx import Document

from odin.core import auth
from odin.core.auth import create_token
from odin.db.models import Article, User


def _headers(username: str = "jperez"):
    token, _ = create_token(username)
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def reports(sqlite_sessionmaker):
    session = sqlite_sessionmaker()
    session.add(
        User(
            username="jperez",
            username_key="jperez",
            display_name="Juan Pérez",
            password_hash=auth.hash_password("x", iterations=1000),
            role="analista",
        )
    )
    session.commit()
    juan = session.query(User).filter_by(username="jperez").one().id

    ids = []
    for n in (1, 2):
        article = Article(
            source="listin_diario",
            url=f"https://listindiario.com/e{n}",
            title=f"Reporte número {n}",
            body="Cuerpo de la nota.",
            main_topic="agua potable",
            overall_sentiment="NEG",
            published_at=datetime(2026, 8, n),
            analyst_id=juan,
            analyzed_on=date(2026, 8, 20),
        )
        session.add(article)
        session.commit()
        ids.append(article.id)
    session.close()
    return ids


def _read(resp) -> Document:
    return Document(io.BytesIO(resp.content))


class TestExport:
    def test_returns_a_word_document(self, api_client, reports):
        resp = api_client.post(
            "/api/articles/export", json={"article_ids": reports}, headers=_headers()
        )

        assert resp.status_code == 200
        assert "wordprocessingml" in resp.headers["content-type"]
        assert ".docx" in resp.headers["content-disposition"]

    def test_includes_only_the_selected_reports(self, api_client, reports):
        resp = api_client.post(
            "/api/articles/export", json={"article_ids": [reports[0]]}, headers=_headers()
        )

        text = "\n".join(p.text for p in _read(resp).paragraphs)
        assert "Reporte número 1" in text
        assert "Reporte número 2" not in text

    def test_carries_the_analyst_and_the_analysis_date(self, api_client, reports):
        """Es el dato que hace útil el documento cuando se exporta el trabajo
        de una persona."""
        resp = api_client.post(
            "/api/articles/export", json={"article_ids": reports}, headers=_headers()
        )

        text = "\n".join(p.text for p in _read(resp).paragraphs)
        assert "Juan Pérez" in text
        assert "20/08/2026" in text

    def test_shows_the_date_without_a_time(self, api_client, reports):
        resp = api_client.post(
            "/api/articles/export", json={"article_ids": reports}, headers=_headers()
        )

        text = "\n".join(p.text for p in _read(resp).paragraphs)
        assert "00:00" not in text

    def test_rejects_an_empty_selection(self, api_client, reports):
        resp = api_client.post(
            "/api/articles/export", json={"article_ids": []}, headers=_headers()
        )

        assert resp.status_code == 422

    def test_ignores_ids_that_do_not_exist(self, api_client, reports):
        """Un id borrado entre que se listó y se exportó no puede tumbar la
        descarga entera."""
        resp = api_client.post(
            "/api/articles/export",
            json={"article_ids": [reports[0], 999999]},
            headers=_headers(),
        )

        assert resp.status_code == 200
        text = "\n".join(p.text for p in _read(resp).paragraphs)
        assert "Reporte número 1" in text

    def test_fails_when_nothing_selected_exists(self, api_client, reports):
        resp = api_client.post(
            "/api/articles/export", json={"article_ids": [999999]}, headers=_headers()
        )

        assert resp.status_code == 404

    def test_requires_authentication(self, api_client, reports):
        resp = api_client.post("/api/articles/export", json={"article_ids": reports})

        assert resp.status_code in (401, 403)
```

- [ ] **Step 3: Correr la prueba y verificar que falla**

Run: `.venv/bin/python -m pytest tests/api/test_api_export.py -q`
Expected: FAIL con 404 (la ruta no existe).

- [ ] **Step 4: Añadir el schema**

Al final de `src/odin/api/schemas.py`:

```python
class ExportRequest(BaseModel):
    """Reportes a incluir en el documento, en el orden en que se envían."""

    article_ids: list[int]
```

- [ ] **Step 5: Escribir el servicio de exportación**

Crear `src/odin/services/export_service.py`:

```python
"""Exportación de reportes a un documento de Word (.docx).

Se genera en memoria y se devuelve como bytes: los documentos son pequeños
(decenas de reportes) y así no hay archivos temporales que limpiar ni estado
compartido entre peticiones.
"""
from __future__ import annotations

import io
from datetime import date

from docx import Document
from docx.enum.text import WD_ALIGN_PARAGRAPH
from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from odin.api import deps
from odin.db.models import Article

# Etiquetas legibles para los códigos que guarda el análisis. El documento lo
# lee una persona, no un programa: "Negativo" dice más que "NEG".
_SENTIMENT_LABELS = {"POS": "Positivo", "NEG": "Negativo", "NEU": "Neutro"}


def _format_date(value: date | None) -> str:
    """Día/mes/año. Sin hora: es lo que pidió el cliente y lo que la columna
    `analyzed_on` guarda."""
    return value.strftime("%d/%m/%Y") if value else "—"


def _add_field(document: Document, label: str, value: str) -> None:
    paragraph = document.add_paragraph()
    run = paragraph.add_run(f"{label}: ")
    run.bold = True
    paragraph.add_run(value or "—")


def build_document(articles: list[Article]) -> bytes:
    """Arma el .docx con los reportes recibidos, en ese orden."""
    document = Document()

    heading = document.add_paragraph("Reportes de prensa")
    heading.alignment = WD_ALIGN_PARAGRAPH.CENTER
    heading.runs[0].bold = True
    heading.runs[0].font.size = None  # hereda el tamaño del estilo por defecto

    for index, article in enumerate(articles):
        if index:
            document.add_page_break()

        document.add_heading(article.title or "(sin título)", level=1)

        _add_field(document, "Medio", article.source)
        _add_field(document, "Sección", article.section or "—")
        _add_field(document, "Publicado", _format_date(
            article.published_at.date() if article.published_at else None
        ))
        _add_field(
            document,
            "Analista",
            article.analyst.display_name if article.analyst else "Automático",
        )
        _add_field(document, "Fecha de análisis", _format_date(article.analyzed_on))
        _add_field(document, "Tema", article.main_topic or "—")
        _add_field(
            document,
            "Sentimiento",
            _SENTIMENT_LABELS.get(article.overall_sentiment or "", "—"),
        )
        _add_field(document, "URL", article.url)

        if article.entities:
            _add_field(
                document,
                "Entidades",
                ", ".join(sorted({e.name for e in article.entities})),
            )

        if article.body:
            document.add_paragraph()
            document.add_paragraph(article.body)

    buffer = io.BytesIO()
    document.save(buffer)
    return buffer.getvalue()


def export_articles(article_ids: list[int]) -> bytes:
    """Busca los reportes pedidos y devuelve el documento.

    Los ids que ya no existen se ignoran en vez de fallar: entre que el usuario
    vio la lista y pulsó exportar, alguien pudo borrar uno, y perder la descarga
    entera por eso sería peor que entregar el resto. Solo se devuelve 404 si no
    queda ninguno.
    """
    if not article_ids:
        raise HTTPException(status_code=422, detail="No hay reportes seleccionados.")

    session = deps.get_session()
    try:
        rows = session.scalars(
            select(Article)
            .options(selectinload(Article.entities), selectinload(Article.analyst))
            .where(Article.id.in_(article_ids))
        ).all()
        if not rows:
            raise HTTPException(
                status_code=404, detail="Ninguno de los reportes seleccionados existe."
            )

        # Respetar el orden en que llegaron los ids: es el que el usuario ve en
        # pantalla, y `IN (...)` no garantiza ninguno.
        by_id = {row.id: row for row in rows}
        ordered = [by_id[i] for i in article_ids if i in by_id]
        return build_document(ordered)
    finally:
        session.close()
```

- [ ] **Step 6: Añadir la ruta**

En `src/odin/api/routers/articles.py`, añadir los imports:

```python
from fastapi import Response
from odin.api.schemas import ExportRequest
from odin.services import export_service
```

y la ruta. **Debe declararse ANTES de `GET /api/articles/{article_id}`** para
que `export` no se interprete como un id — aunque sean métodos distintos,
mantenerlas en ese orden evita sorpresas si mañana se añade un `GET`:

```python
@router.post("/api/articles/export", dependencies=[Depends(auth.require_auth)])
def export_articles(req: ExportRequest):
    """Devuelve un documento de Word con los reportes seleccionados.

    Es el cierre del flujo que pidió el cliente: filtrar por analista, elegir
    los reportes y bajarlos.
    """
    content = export_service.export_articles(req.article_ids)
    return Response(
        content=content,
        media_type=(
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
        ),
        headers={"Content-Disposition": 'attachment; filename="reportes-odin.docx"'},
    )
```

- [ ] **Step 7: Correr las pruebas**

Run: `.venv/bin/python -m pytest tests/api/test_api_export.py -q`
Expected: PASS (8 pruebas)

- [ ] **Step 8: Verificar el conjunto**

Run: `.venv/bin/python -m pytest -q && .venv/bin/ruff check src/odin/ tests/ && .venv/bin/mypy`
Expected: 378 passed, limpio.

Si mypy se queja de que a `docx` le faltan tipos, añadir en `pyproject.toml`,
dentro de la sección de `mypy`, junto a los demás módulos sin stubs:

```toml
[[tool.mypy.overrides]]
module = ["docx.*"]
ignore_missing_imports = true
```

**NO commitear.**

---

### Task 7: Resumen de trabajo por analista (solo admin)

**Files:**
- Create: `src/odin/services/analyst_kpi_service.py`
- Modify: `src/odin/api/routers/users.py`
- Modify: `src/odin/api/schemas.py`
- Modify: `src/odin/core/auth.py` (`MeResponse` con el rol)
- Test: `tests/api/test_api_analyst_kpi.py`

**Interfaces:**
- Consumes: `articles.analyst_id`, `articles.analyzed_on` (Tarea 4); `odin.core.auth.require_admin` (Tarea 2)
- Produces:
  - `GET /api/analysts/kpi?date_from=&date_to=` (**admin**) → `list[AnalystKpiRow]`
  - `AnalystKpiRow{analyst_id, display_name, articles, first_on, last_on, active_days}`
  - `MeResponse{username, role}` — para que el frontend sepa qué ocultar

**Alcance deliberadamente pequeño.** El conteo del ejemplo del cliente («Juan
hizo 7») ya sale del propio filtro: `GET /api/articles?analyst=<id>` devuelve
`total`. Este endpoint solo añade la vista comparativa entre personas, que es lo
único que el filtro no da. Mide volumen, no calidad: la «tasa de corrección
sobre lo que propuso el modelo» de R20 exige auditoría campo a campo, y hoy
re-analizar sobrescribe la fila sin dejar rastro.

- [ ] **Step 1: Escribir la prueba que falla**

Crear `tests/api/test_api_analyst_kpi.py`:

```python
"""Pruebas del resumen de trabajo por analista.

Es material de evaluación, así que está restringido a rol admin: un analista no
tiene por qué ver los números de sus compañeros.
"""
from __future__ import annotations

from datetime import date, datetime

import pytest

from odin.core import auth
from odin.core.auth import create_token
from odin.db.models import Article, User


def _headers(username: str = "jefe"):
    token, _ = create_token(username)
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def team(sqlite_sessionmaker):
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
                role="analista",
            ),
        ]
    )
    session.commit()
    juan = session.query(User).filter_by(username="jperez").one().id

    for n, day in enumerate([18, 18, 20], start=1):
        session.add(
            Article(
                source="listin_diario",
                url=f"https://listindiario.com/k{n}",
                title=f"Nota {n}",
                body="x",
                published_at=datetime(2026, 8, day),
                analyst_id=juan,
                analyzed_on=date(2026, 8, day),
            )
        )
    # Sin analista: entró por el rastreo masivo.
    session.add(
        Article(
            source="diario_libre",
            url="https://diariolibre.com/auto",
            title="Automática",
            body="x",
            published_at=datetime(2026, 8, 1),
        )
    )
    session.commit()
    session.close()
    return juan


class TestKpi:
    def test_counts_articles_per_analyst(self, api_client, team):
        rows = api_client.get("/api/analysts/kpi", headers=_headers()).json()

        juan = [r for r in rows if r["display_name"] == "Juan Pérez"][0]
        assert juan["articles"] == 3

    def test_counts_distinct_active_days(self, api_client, team):
        """Tres reportes en dos días son dos días de trabajo, no tres."""
        rows = api_client.get("/api/analysts/kpi", headers=_headers()).json()

        juan = [r for r in rows if r["display_name"] == "Juan Pérez"][0]
        assert juan["active_days"] == 2

    def test_reports_dates_without_a_time(self, api_client, team):
        rows = api_client.get("/api/analysts/kpi", headers=_headers()).json()

        juan = [r for r in rows if r["display_name"] == "Juan Pérez"][0]
        assert juan["first_on"] == "2026-08-18"
        assert juan["last_on"] == "2026-08-20"

    def test_ignores_articles_without_an_analyst(self, api_client, team):
        rows = api_client.get("/api/analysts/kpi", headers=_headers()).json()

        assert sum(r["articles"] for r in rows) == 3

    def test_date_range_narrows_the_count(self, api_client, team):
        rows = api_client.get(
            "/api/analysts/kpi", params={"date_from": "2026-08-20"}, headers=_headers()
        ).json()

        juan = [r for r in rows if r["display_name"] == "Juan Pérez"][0]
        assert juan["articles"] == 1

    def test_a_plain_analyst_cannot_see_it(self, api_client, team):
        """Los números de productividad no son para los compañeros."""
        resp = api_client.get("/api/analysts/kpi", headers=_headers("jperez"))

        assert resp.status_code == 403

    def test_requires_authentication(self, api_client, team):
        assert api_client.get("/api/analysts/kpi").status_code in (401, 403)


class TestMeCarriesTheRole:
    def test_me_reports_the_role(self, api_client, team):
        """El frontend necesita el rol para ocultar lo que es solo de admin."""
        resp = api_client.get("/api/auth/me", headers=_headers())

        assert resp.status_code == 200
        assert resp.json()["role"] == "admin"

    def test_an_unknown_user_reports_no_role(self, api_client, team):
        resp = api_client.get("/api/auth/me", headers=_headers("fantasma"))

        assert resp.status_code == 200
        assert resp.json()["role"] is None
```

- [ ] **Step 2: Correr la prueba y verificar que falla**

Run: `.venv/bin/python -m pytest tests/api/test_api_analyst_kpi.py -q`
Expected: FAIL con 404 en `/api/analysts/kpi` y `KeyError: 'role'` en `/me`.

- [ ] **Step 3: Añadir el rol a `/me`**

En `src/odin/core/auth.py`, cambiar `MeResponse` y el endpoint `me`:

```python
class MeResponse(BaseModel):
    username: str
    # El rol viaja aquí y no en el token: leerlo de la BD en cada arranque de la
    # aplicación hace que quitarle el rol a alguien surta efecto sin esperar a
    # que su JWT venza.
    role: str | None = None
```

```python
@router.get("/me", response_model=MeResponse)
def me(username: str = Depends(require_auth)):
    """Valida el token guardado en el navegador al abrir la aplicación, y
    devuelve el rol para que la interfaz sepa qué mostrar."""
    import odin.db.users as user_store
    from odin.api import deps

    session = deps.get_session()
    try:
        user = user_store.get_by_username(session, username)
        return MeResponse(username=username, role=user.role if user else None)
    finally:
        session.close()
```

- [ ] **Step 4: Añadir el schema del KPI**

Al final de `src/odin/api/schemas.py`:

```python
class AnalystKpiRow(_ResponseModel):
    """Trabajo de un analista en el rango consultado.

    Mide volumen, no calidad: la «tasa de corrección sobre lo que propuso el
    modelo» que pide R20 necesita auditoría campo a campo, y hoy re-analizar
    sobrescribe la fila del artículo sin dejar rastro.
    """

    analyst_id: int
    display_name: str
    articles: int
    # Fechas sin hora, como `articles.analyzed_on`.
    first_on: date | None = None
    last_on: date | None = None
    # Días DISTINTOS con al menos un reporte: tres reportes en un día son un día
    # de trabajo, no tres.
    active_days: int
```

- [ ] **Step 5: Escribir el servicio**

Crear `src/odin/services/analyst_kpi_service.py`:

```python
"""Resumen de trabajo por analista.

Se apoya en `articles.analyzed_on` — la fecha en que la persona lo trabajó — y
no en `published_at`, que es cuándo lo publicó el medio: una nota del mes pasado
revisada hoy es trabajo de hoy.

Como `analyzed_on` ya es una fecha sin hora, agrupar por día es contar valores
distintos de la columna; no hace falta truncar nada en SQL.
"""
from __future__ import annotations

from datetime import date, timedelta

from fastapi import HTTPException
from sqlalchemy import func, select

from odin.api import deps
from odin.api.schemas import AnalystKpiRow
from odin.db.models import Article, User


def _parse_day(value: str | None) -> date | None:
    """Acepta "AAAA-MM-DD"; cualquier otra cosa es un 422, no un filtro que se
    ignora en silencio y devuelve números que nadie sabe interpretar."""
    if not value:
        return None
    try:
        return date.fromisoformat(value)
    except ValueError:
        raise HTTPException(
            status_code=422, detail=f"Fecha inválida: '{value}'. Formato: AAAA-MM-DD."
        ) from None


def analyst_kpi(date_from: str | None, date_to: str | None) -> list[AnalystKpiRow]:
    since = _parse_day(date_from)
    until = _parse_day(date_to)

    session = deps.get_session()
    try:
        stmt = (
            select(
                User.id,
                User.display_name,
                func.count(Article.id).label("articles"),
                func.min(Article.analyzed_on).label("first_on"),
                func.max(Article.analyzed_on).label("last_on"),
                func.count(func.distinct(Article.analyzed_on)).label("active_days"),
            )
            .select_from(Article)
            .join(User, User.id == Article.analyst_id)
            .group_by(User.id, User.display_name)
            .order_by(func.count(Article.id).desc())
        )
        if since:
            stmt = stmt.where(Article.analyzed_on >= since)
        if until:
            # Inclusivo: `until` es un día completo, no un instante.
            stmt = stmt.where(Article.analyzed_on <= until)

        return [
            AnalystKpiRow(
                analyst_id=row.id,
                display_name=row.display_name,
                articles=row.articles,
                first_on=row.first_on,
                last_on=row.last_on,
                active_days=row.active_days,
            )
            for row in session.execute(stmt).all()
        ]
    finally:
        session.close()
```

Nota: `timedelta` no se usa aquí (el rango es inclusivo por fechas, no por
instantes); no lo importes.

- [ ] **Step 6: Añadir la ruta**

En `src/odin/api/routers/users.py`, importar y declarar. **Antes** de cualquier
`/api/analysts/{analyst_id}`, para que `kpi` no se lea como un id:

```python
from odin.api.schemas import AnalystKpiRow
from odin.services import analyst_kpi_service
```

```python
@router.get(
    "/api/analysts/kpi",
    dependencies=[Depends(auth.require_admin)],
    response_model=list[AnalystKpiRow],
)
def analyst_kpi(date_from: str | None = None, date_to: str | None = None):
    """Trabajo por analista en el rango indicado. Solo admin: son datos de
    evaluación, no de operación."""
    return analyst_kpi_service.analyst_kpi(date_from, date_to)
```

- [ ] **Step 7: Correr las pruebas**

Run: `.venv/bin/python -m pytest tests/api/test_api_analyst_kpi.py -q`
Expected: PASS (9 pruebas)

- [ ] **Step 8: Verificar el conjunto**

Run: `.venv/bin/python -m pytest -q && .venv/bin/ruff check src/odin/ tests/ && .venv/bin/mypy`
Expected: 387 passed, limpio. **NO commitear.**

---

### Task 8: Frontend — filtrar por analista, seleccionar y exportar

Es el flujo completo que describió el cliente, en pantalla.

**Files:**
- Modify: `frontend/src/lib/api-types.ts` (regenerado)
- Modify: `frontend/src/lib/odin-api.ts`
- Create: `frontend/src/lib/queries/analysts.ts`
- Modify: `frontend/src/lib/auth.ts` (guardar el rol)
- Modify: `frontend/src/components/reports/FilterBar.tsx`
- Modify: `frontend/src/components/reports/ReportsTable.tsx`
- Modify: `frontend/src/pages/ReportsPage.tsx`
- Test: `frontend/src/components/reports/ReportsTable.test.tsx`

**Interfaces:**
- Consumes: `GET /api/articles?analyst=`, `GET /api/articles/filters`, `POST /api/articles/export` (Tareas 5 y 6)
- Produces: `useAnalysts()`, `useAnalystKpi()`, `exportArticles(ids)`, selección de filas en la tabla

- [ ] **Step 1: Regenerar los tipos**

```bash
cd frontend
ODIN_ANALYZER=local PATH="/Users/jazar/Documents/Projects/Odin/.venv/bin:$PATH" npm run generate:types
grep -n "AnalystResponse:\|AnalystKpiRow:\|ExportRequest:" src/lib/api-types.ts
```
Expected: los tres aparecen. `ODIN_ANALYZER=local` es obligatorio: el script se
niega a cargar el motor de pago solo para volcar tipos.

- [ ] **Step 2: Escribir la prueba que falla**

Crear `frontend/src/components/reports/ReportsTable.test.tsx`:

```tsx
import { describe, expect, it, vi } from "vitest"
import { render, screen } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { MemoryRouter } from "react-router-dom"
import { ReportsTable } from "@/components/reports/ReportsTable"
import type { ArticleSummary } from "@/lib/odin-api"

const ROWS = [
  {
    id: 1,
    source: "listin_diario",
    url: "https://listindiario.com/a",
    title: "Reporte de Juan",
    analyst: "Juan Pérez",
    analyzed_on: "2026-08-20",
    overall_sentiment: "NEG",
  },
  {
    id: 2,
    source: "diario_libre",
    url: "https://diariolibre.com/b",
    title: "Reporte automático",
    analyst: null,
    analyzed_on: null,
    overall_sentiment: "NEU",
  },
] as unknown as ArticleSummary[]

function renderTable(props: Record<string, unknown> = {}) {
  const onSelectionChange = vi.fn()
  render(
    <MemoryRouter>
      <ReportsTable
        articles={ROWS}
        selectedIds={[]}
        onSelectionChange={onSelectionChange}
        {...props}
      />
    </MemoryRouter>
  )
  return onSelectionChange
}

describe("ReportsTable — analista y selección", () => {
  it("muestra el analista de cada reporte", () => {
    renderTable()

    expect(screen.getByText("Juan Pérez")).toBeTruthy()
  })

  it("muestra la fecha de análisis en día/mes/año", () => {
    renderTable()

    expect(screen.getByText("20/08/2026")).toBeTruthy()
  })

  it("marca como automático lo que no tiene analista", () => {
    renderTable()

    expect(screen.getByText("Automático")).toBeTruthy()
  })

  it("permite seleccionar un reporte", async () => {
    const onSelectionChange = renderTable()
    const user = userEvent.setup()

    await user.click(screen.getByLabelText("Seleccionar Reporte de Juan"))

    expect(onSelectionChange).toHaveBeenCalledWith([1])
  })

  it("selecciona y deselecciona todo de una vez", async () => {
    const onSelectionChange = renderTable()
    const user = userEvent.setup()

    await user.click(screen.getByLabelText("Seleccionar todos"))

    expect(onSelectionChange).toHaveBeenCalledWith([1, 2])
  })
})
```

- [ ] **Step 3: Correr la prueba y verificar que falla**

Run: `cd frontend && npm test -- ReportsTable`
Expected: FAIL — no encuentra la columna de analista ni las casillas.

- [ ] **Step 4: Añadir el cliente API**

Al final de `frontend/src/lib/odin-api.ts`:

```ts
// ── Analistas y exportación ──────────────────────────────────────────────────

export type Analyst = components["schemas"]["AnalystResponse"]
export type AnalystKpiRow = components["schemas"]["AnalystKpiRow"]
export type AnalystPayload = components["schemas"]["AnalystPayload"]
export type AnalystUpdatePayload = components["schemas"]["AnalystUpdatePayload"]

export function listAnalysts(): Promise<Analyst[]> {
  return request<Analyst[]>("/api/analysts")
}

export function getAnalystKpi(
  params: { date_from?: string; date_to?: string } = {}
): Promise<AnalystKpiRow[]> {
  const qs = new URLSearchParams()
  for (const [key, value] of Object.entries(params)) {
    if (value === undefined || value === null || value === "") continue
    qs.set(key, String(value))
  }
  const s = qs.toString()
  return request<AnalystKpiRow[]>(`/api/analysts/kpi${s ? `?${s}` : ""}`)
}

export function createAnalyst(payload: AnalystPayload): Promise<Analyst> {
  return postJson("/api/analysts", payload)
}

export function updateAnalyst(id: number, payload: AnalystUpdatePayload): Promise<Analyst> {
  return putJson(`/api/analysts/${id}`, payload)
}

/** Descarga el .docx de los reportes seleccionados.
 *
 *  No usa `request()` porque la respuesta es binaria, no JSON. La descarga se
 *  dispara con un enlace temporal sobre un blob: es lo único que funciona igual
 *  en todos los navegadores para un POST cuyo resultado es un archivo. */
export async function exportArticles(articleIds: number[]): Promise<void> {
  const headers = new Headers({ "Content-Type": "application/json" })
  const token = getToken()
  if (token) headers.set("Authorization", `Bearer ${token}`)

  const res = await fetch("/api/articles/export", {
    method: "POST",
    headers,
    body: JSON.stringify({ article_ids: articleIds }),
  })
  if (!res.ok) {
    const body = await res.json().catch(() => null)
    throw new OdinApiError(body?.detail ?? "No se pudo exportar.")
  }

  const blob = await res.blob()
  const url = URL.createObjectURL(blob)
  const link = document.createElement("a")
  link.href = url
  link.download = "reportes-odin.docx"
  document.body.appendChild(link)
  link.click()
  link.remove()
  // Liberar el objeto: sin esto el blob queda retenido hasta recargar.
  URL.revokeObjectURL(url)
}
```

Añadir `analyst?: number` a la interfaz `ArticleListParams`.

- [ ] **Step 5: Crear los hooks**

Crear `frontend/src/lib/queries/analysts.ts`:

```ts
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import {
  listAnalysts,
  getAnalystKpi,
  createAnalyst,
  updateAnalyst,
  exportArticles,
  type AnalystPayload,
  type AnalystUpdatePayload,
} from "@/lib/odin-api"

export const analystKeys = {
  all: ["analysts"] as const,
  list: () => [...analystKeys.all, "list"] as const,
  kpi: (from?: string, to?: string) => [...analystKeys.all, "kpi", from ?? "", to ?? ""] as const,
}

export function useAnalysts() {
  return useQuery({ queryKey: analystKeys.list(), queryFn: listAnalysts })
}

/** Solo lo consume la pantalla de admin: el backend responde 403 al resto. */
export function useAnalystKpi(dateFrom?: string, dateTo?: string, enabled = true) {
  return useQuery({
    queryKey: analystKeys.kpi(dateFrom, dateTo),
    queryFn: () => getAnalystKpi({ date_from: dateFrom, date_to: dateTo }),
    enabled,
  })
}

export function useCreateAnalyst() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (payload: AnalystPayload) => createAnalyst(payload),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: analystKeys.all }),
  })
}

export function useUpdateAnalyst() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: ({ id, payload }: { id: number; payload: AnalystUpdatePayload }) =>
      updateAnalyst(id, payload),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: analystKeys.all }),
  })
}

export function useExportArticles() {
  return useMutation({ mutationFn: (ids: number[]) => exportArticles(ids) })
}
```

- [ ] **Step 6: Guardar el rol en la sesión**

En `frontend/src/lib/auth.ts`, junto a `getUsername`/`setSession`, añadir el rol
usando el mismo mecanismo de almacenamiento que ya usa el username:

```ts
const ROLE_KEY = "odin:role"

export function getRole(): string | null {
  try {
    return localStorage.getItem(ROLE_KEY)
  } catch {
    // Modo privado o almacenamiento bloqueado: sin rol, la UI de admin
    // simplemente no se muestra. El backend sigue siendo quien decide.
    return null
  }
}

export function setRole(role: string | null): void {
  try {
    if (role) localStorage.setItem(ROLE_KEY, role)
    else localStorage.removeItem(ROLE_KEY)
  } catch {
    // ignorado a propósito: el rol es una conveniencia de la interfaz
  }
}

export function isAdmin(): boolean {
  return getRole() === "admin"
}
```

Y en `clearSession()`, borrar también `ROLE_KEY`. Donde la aplicación llama a
`getMe()` al arrancar (busca `getMe` en `src/lib/queries/auth.ts` o en
`App.tsx`), guardar el rol de la respuesta con `setRole(me.role)`.

**El rol en el navegador solo decide qué se dibuja.** Quien autoriza de verdad
es `require_admin` en el backend; manipular `localStorage` no da acceso a nada.

- [ ] **Step 7: Añadir el selector de analista al FilterBar**

En `frontend/src/components/reports/FilterBar.tsx`, junto a los demás selectores:

```tsx
<label className="flex flex-col gap-1">
  <span className="text-[11.5px]" style={{ color: "var(--faint)" }}>
    Analista
  </span>
  <Select
    aria-label="Analista"
    value={filters.analyst === undefined ? "" : String(filters.analyst)}
    onChange={(e) =>
      onChange({ analyst: e.target.value ? Number(e.target.value) : undefined })
    }
  >
    <option value="">Todos</option>
    {(facets?.analysts ?? []).map((a) => (
      <option key={a.id} value={String(a.id)}>
        {a.display_name}
      </option>
    ))}
  </Select>
</label>
```

- [ ] **Step 8: Añadir columnas y selección a la tabla**

En `frontend/src/components/reports/ReportsTable.tsx`, ampliar las props:

```tsx
  selectedIds: number[]
  onSelectionChange: (ids: number[]) => void
```

Casilla de «seleccionar todos» en la fila de encabezados, como primera columna:

```tsx
<th className="w-8 px-2 py-1.5">
  <input
    type="checkbox"
    aria-label="Seleccionar todos"
    checked={articles.length > 0 && selectedIds.length === articles.length}
    onChange={(e) =>
      onSelectionChange(e.target.checked ? articles.map((a) => a.id as number) : [])
    }
  />
</th>
```

Dos encabezados más, tras los existentes:

```tsx
<th className="px-2 py-1.5 text-left font-medium">Analista</th>
<th className="px-2 py-1.5 text-left font-medium">Analizado</th>
```

Y en cada fila, la casilla como primera celda y las dos columnas al final:

```tsx
<td className="px-2 py-1.5">
  <input
    type="checkbox"
    aria-label={`Seleccionar ${article.title}`}
    checked={selectedIds.includes(article.id as number)}
    onChange={(e) =>
      onSelectionChange(
        e.target.checked
          ? [...selectedIds, article.id as number]
          : selectedIds.filter((id) => id !== article.id)
      )
    }
  />
</td>
```

```tsx
<td className="px-2 py-1.5" style={{ color: "var(--faint)" }}>
  {article.analyst ?? "Automático"}
</td>
<td className="px-2 py-1.5 font-mono text-[11.5px]" style={{ color: "var(--faint)" }}>
  {formatDay(article.analyzed_on)}
</td>
```

`"Automático"` y no una celda vacía: un hueco parece un dato que falta, cuando
significa que la nota entró por el rastreo masivo.

Añadir el formateador en `frontend/src/lib/format.ts`:

```ts
/** "2026-08-20" -> "20/08/2026". La API entrega una fecha sin hora
 *  (`analyzed_on` es DATE), así que se parte el string en vez de construir un
 *  `Date`: `new Date("2026-08-20")` se interpreta como UTC y en husos al oeste
 *  muestra el día anterior. */
export function formatDay(value: string | null | undefined): string {
  if (!value) return "—"
  const [year, month, day] = value.slice(0, 10).split("-")
  return day && month && year ? `${day}/${month}/${year}` : "—"
}
```

- [ ] **Step 9: Añadir la barra de exportación a la página de reportes**

En `frontend/src/pages/ReportsPage.tsx`, mantener la selección y ofrecer la
descarga cuando haya algo elegido:

```tsx
const [selectedIds, setSelectedIds] = useState<number[]>([])
const exportMutation = useExportArticles()
```

Pasar `selectedIds` y `onSelectionChange={setSelectedIds}` a `<ReportsTable>`, y
sobre la tabla:

```tsx
{selectedIds.length > 0 && (
  <div
    className="mb-2 flex items-center gap-3 rounded-[7px] border px-3 py-2"
    style={{ background: "var(--surface-2)", borderColor: "var(--border)" }}
  >
    <span className="text-[12.5px]">
      {selectedIds.length} {selectedIds.length === 1 ? "reporte" : "reportes"} seleccionados
    </span>
    <Button
      type="button"
      onClick={() => exportMutation.mutate(selectedIds)}
      disabled={exportMutation.isPending}
    >
      {exportMutation.isPending ? "Exportando…" : "Exportar a Word"}
    </Button>
    <button
      type="button"
      onClick={() => setSelectedIds([])}
      className="text-[12px] underline-offset-2 hover:underline"
      style={{ color: "var(--faint)" }}
    >
      Limpiar selección
    </button>
    {exportMutation.error && (
      <span role="alert" className="text-[12px]" style={{ color: "var(--neg)" }}>
        No se pudo exportar.
      </span>
    )}
  </div>
)}
```

Limpiar la selección cuando cambian los filtros, para no exportar reportes que
ya no están a la vista:

```tsx
useEffect(() => {
  setSelectedIds([])
}, [filters])
```

- [ ] **Step 10: Correr las pruebas**

Run: `cd frontend && npx tsc -b && npm test && npm run lint`
Expected: tsc limpio; 36 pruebas en verde (31 + 5); lint sin advertencias nuevas
(las de `button`, `badge` y `dialog` son preexistentes).

**NO commitear.**

---

### Task 9: Frontend — pantalla de analistas (admin) y documentación

**Files:**
- Create: `frontend/src/pages/AnalystsPage.tsx`
- Modify: `frontend/src/App.tsx` (ruta)
- Modify: `frontend/src/components/Layout.tsx:9-13` (`NAV_ITEMS`)
- Modify: `docs/DATA_DICTIONARY.md`, `docs/ARQUITECTURA.md`, `README.md`
- Test: `frontend/src/pages/AnalystsPage.test.tsx`

**Interfaces:**
- Consumes: `useAnalysts`, `useAnalystKpi`, `useCreateAnalyst`, `useUpdateAnalyst`, `isAdmin` (Tarea 8)

- [ ] **Step 1: Escribir la prueba que falla**

Crear `frontend/src/pages/AnalystsPage.test.tsx`:

```tsx
import { describe, expect, it, vi, beforeEach } from "vitest"
import { render, screen, waitFor } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { QueryClient, QueryClientProvider } from "@tanstack/react-query"
import { AnalystsPage } from "@/pages/AnalystsPage"
import * as odinApi from "@/lib/odin-api"

vi.mock("@/lib/odin-api", async () => {
  const actual = await vi.importActual<typeof odinApi>("@/lib/odin-api")
  return {
    ...actual,
    listAnalysts: vi.fn(),
    getAnalystKpi: vi.fn(),
    createAnalyst: vi.fn(),
  }
})

const mockedList = vi.mocked(odinApi.listAnalysts)
const mockedKpi = vi.mocked(odinApi.getAnalystKpi)
const mockedCreate = vi.mocked(odinApi.createAnalyst)

function renderPage() {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  render(
    <QueryClientProvider client={queryClient}>
      <AnalystsPage />
    </QueryClientProvider>
  )
}

describe("AnalystsPage", () => {
  beforeEach(() => {
    localStorage.setItem("odin:role", "admin")
    mockedList.mockReset()
    mockedKpi.mockReset()
    mockedCreate.mockReset()
    mockedList.mockResolvedValue([
      {
        id: 1,
        username: "jperez",
        display_name: "Juan Pérez",
        role: "analista",
        is_active: true,
        created_at: "2026-08-01T00:00:00Z",
      },
    ] as never)
    mockedKpi.mockResolvedValue([
      {
        analyst_id: 1,
        display_name: "Juan Pérez",
        articles: 7,
        first_on: "2026-08-18",
        last_on: "2026-08-20",
        active_days: 2,
      },
    ] as never)
    mockedCreate.mockResolvedValue({} as never)
  })

  it("lista a los analistas", async () => {
    renderPage()

    expect(await screen.findByText("Juan Pérez")).toBeTruthy()
  })

  it("muestra cuántos reportes lleva cada uno", async () => {
    renderPage()

    await waitFor(() => expect(screen.getByText("7")).toBeTruthy())
  })

  it("da de alta a un analista", async () => {
    renderPage()
    const user = userEvent.setup()
    await screen.findByText("Juan Pérez")

    await user.type(screen.getByLabelText("Usuario"), "mgomez")
    await user.type(screen.getByLabelText("Nombre"), "María Gómez")
    await user.type(screen.getByLabelText("Contraseña inicial"), "clave-inicial")
    await user.click(screen.getByRole("button", { name: /agregar analista/i }))

    expect(mockedCreate).toHaveBeenCalledWith(
      expect.objectContaining({ username: "mgomez", display_name: "María Gómez" })
    )
  })

  it("no pide el KPI si el usuario no es admin", async () => {
    localStorage.setItem("odin:role", "analista")
    renderPage()
    await screen.findByText("Juan Pérez")

    expect(mockedKpi).not.toHaveBeenCalled()
  })
})
```

- [ ] **Step 2: Correr la prueba y verificar que falla**

Run: `cd frontend && npm test -- AnalystsPage`
Expected: FAIL — no se encuentra el módulo `@/pages/AnalystsPage`.

- [ ] **Step 3: Escribir la página**

Crear `frontend/src/pages/AnalystsPage.tsx`:

```tsx
import { useState } from "react"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Select } from "@/components/ui/select"
import { isAdmin } from "@/lib/auth"
import { formatDay } from "@/lib/format"
import { OdinApiError } from "@/lib/odin-api"
import {
  useAnalysts,
  useAnalystKpi,
  useCreateAnalyst,
  useUpdateAnalyst,
} from "@/lib/queries/analysts"

/**
 * Analistas y su trabajo.
 *
 * El resumen de volumen solo lo ve un admin: el backend responde 403 al resto,
 * y aquí ni siquiera se pide (`enabled`), para no provocar un error visible en
 * la consola de quien no tiene por qué verlo.
 */
export function AnalystsPage() {
  const admin = isAdmin()
  const { data: analysts } = useAnalysts()
  const { data: kpi } = useAnalystKpi(undefined, undefined, admin)
  const createMutation = useCreateAnalyst()
  const updateMutation = useUpdateAnalyst()

  const [form, setForm] = useState({
    username: "",
    display_name: "",
    password: "",
    role: "analista",
  })

  const workById = new Map((kpi ?? []).map((row) => [row.analyst_id, row]))
  const error = createMutation.error instanceof OdinApiError ? createMutation.error.message : null

  function submit() {
    if (!form.username || !form.password) return
    createMutation.mutate(
      { ...form, display_name: form.display_name || form.username },
      {
        onSuccess: () =>
          setForm({ username: "", display_name: "", password: "", role: "analista" }),
      }
    )
  }

  return (
    <div>
      <header>
        <h1 className="text-[19px] font-semibold">Analistas</h1>
        <p className="mt-0.5 text-[12.5px]" style={{ color: "var(--faint)" }}>
          Quién captura los reportes{admin ? " y cuánto lleva cada uno" : ""}.
        </p>
      </header>

      <div
        className="odin-glass mt-4 overflow-x-auto rounded-xl border"
        style={{ boxShadow: "var(--shadow)" }}
      >
        <table className="w-full text-[12.5px]">
          <thead>
            <tr style={{ color: "var(--faint)" }}>
              <th className="px-3 py-2 text-left font-medium">Nombre</th>
              <th className="px-3 py-2 text-left font-medium">Usuario</th>
              <th className="px-3 py-2 text-left font-medium">Rol</th>
              {admin && <th className="px-3 py-2 text-right font-medium">Reportes</th>}
              {admin && <th className="px-3 py-2 text-right font-medium">Días activos</th>}
              {admin && <th className="px-3 py-2 text-right font-medium">Último</th>}
              <th className="px-3 py-2 text-right font-medium">Estado</th>
            </tr>
          </thead>
          <tbody>
            {(analysts ?? []).map((a) => {
              const work = workById.get(a.id)
              return (
                <tr key={a.id} className="border-t" style={{ borderColor: "var(--border)" }}>
                  <td className="px-3 py-2">{a.display_name}</td>
                  <td className="px-3 py-2" style={{ color: "var(--faint)" }}>
                    {a.username}
                  </td>
                  <td className="px-3 py-2" style={{ color: "var(--faint)" }}>
                    {a.role}
                  </td>
                  {admin && (
                    <td className="px-3 py-2 text-right font-mono">{work?.articles ?? 0}</td>
                  )}
                  {admin && (
                    <td className="px-3 py-2 text-right font-mono">{work?.active_days ?? 0}</td>
                  )}
                  {admin && (
                    <td className="px-3 py-2 text-right font-mono">
                      {formatDay(work?.last_on)}
                    </td>
                  )}
                  <td className="px-3 py-2 text-right">
                    <button
                      type="button"
                      onClick={() =>
                        updateMutation.mutate({ id: a.id, payload: { is_active: !a.is_active } })
                      }
                      className="text-[12px] underline-offset-2 hover:underline"
                      style={{ color: a.is_active ? "var(--faint)" : "var(--neg)" }}
                    >
                      {a.is_active ? "Activo" : "Inactivo"}
                    </button>
                  </td>
                </tr>
              )
            })}
          </tbody>
        </table>
      </div>

      {admin && (
        <div className="odin-glass mt-4 rounded-xl border p-4" style={{ boxShadow: "var(--shadow)" }}>
          <div className="text-[14px] font-medium">Agregar analista</div>
          {error && (
            <p role="alert" className="mt-2 text-[12.5px]" style={{ color: "var(--neg)" }}>
              {error}
            </p>
          )}
          <div className="mt-3 grid gap-2 sm:grid-cols-2">
            <label className="flex flex-col gap-1">
              <span className="text-[11.5px]" style={{ color: "var(--faint)" }}>Usuario</span>
              <Input
                aria-label="Usuario"
                value={form.username}
                onChange={(e) => setForm({ ...form, username: e.target.value })}
              />
            </label>
            <label className="flex flex-col gap-1">
              <span className="text-[11.5px]" style={{ color: "var(--faint)" }}>Nombre</span>
              <Input
                aria-label="Nombre"
                value={form.display_name}
                onChange={(e) => setForm({ ...form, display_name: e.target.value })}
              />
            </label>
            <label className="flex flex-col gap-1">
              <span className="text-[11.5px]" style={{ color: "var(--faint)" }}>
                Contraseña inicial
              </span>
              <Input
                aria-label="Contraseña inicial"
                type="password"
                value={form.password}
                onChange={(e) => setForm({ ...form, password: e.target.value })}
              />
            </label>
            <label className="flex flex-col gap-1">
              <span className="text-[11.5px]" style={{ color: "var(--faint)" }}>Rol</span>
              <Select
                aria-label="Rol"
                value={form.role}
                onChange={(e) => setForm({ ...form, role: e.target.value })}
              >
                <option value="analista">Analista</option>
                <option value="admin">Administrador</option>
              </Select>
            </label>
          </div>
          <Button type="button" className="mt-3" onClick={submit} disabled={createMutation.isPending}>
            Agregar analista
          </Button>
        </div>
      )}
    </div>
  )
}
```

- [ ] **Step 4: Añadir la ruta y la navegación**

En `frontend/src/App.tsx`, junto a las demás rutas protegidas (están sobre la
línea 96; la comodín `path="*"` debe quedar la última):

```tsx
<Route path="/analysts" element={<AnalystsPage />} />
```

con su import.

`Nav.tsx` NO se toca: es presentacional y se alimenta de `items`. La navegación
se declara en `NAV_ITEMS` de `frontend/src/components/Layout.tsx` (líneas 9-13),
donde `tab` es la ruta. Añadir antes de «Ajustes»:

```tsx
  { label: "Analistas", tab: "/analysts" },
```

- [ ] **Step 5: Correr las pruebas del frontend**

Run: `cd frontend && npx tsc -b && npm test && npm run lint`
Expected: tsc limpio; 40 pruebas en verde (36 + 4); lint sin advertencias nuevas.

- [ ] **Step 6: Actualizar la documentación**

El hook `docs-freshness` avisa cuando se toca `db/models.py` o `api/schemas.py`
sin tocar docs. Actualizar:

- `docs/DATA_DICTIONARY.md`: añadir la sección `## users` (columnas de la Tarea
  1) y, en la tabla de `articles`, las filas `analyst_id` y `analyzed_on`,
  dejando explícito que **no** son lo mismo que `analyzer_name`/`analyzed_at`
  (motor y momento del análisis automático). Actualizar «Convenciones
  generales» con la regla de `ON DELETE SET NULL` hacia `users`.
- `docs/ARQUITECTURA.md`: añadir `users.py` a la lista de routers;
  `user_service.py`, `analyst_kpi_service.py` y `export_service.py` a la de
  servicios; `db/users.py` a la de `db/`; y actualizar «10 tablas» a «11
  tablas».
- `README.md`: en la sección de autenticación, decir que el login va contra la
  tabla `users` y que las variables `ODIN_AUTH_*` ahora solo siembran al primer
  administrador. Añadir la exportación a Word a la lista de capacidades.

- [ ] **Step 7: Verificación final completa**

```bash
.venv/bin/python -m pytest -q
.venv/bin/ruff check src/odin/ tests/
.venv/bin/mypy
cd frontend && npx tsc -b && npm test && npm run lint && npm run build
```
Expected: 387 backend + 40 frontend en verde, todo limpio, build sin errores.

Y una comprobación de extremo a extremo contra Docker, porque **es el entorno
donde salen los fallos de empaquetado y de dependencias que el árbol de fuentes
esconde** (así apareció el bug del JSON de localidades):

```bash
docker compose build backend && docker compose up -d backend
docker compose logs backend | grep -iE "seed_operator|seed_localities|error"
curl -s -X POST localhost:8000/api/auth/login \
  -H 'Content-Type: application/json' \
  -d '{"username":"admin","password":"<la del .env>"}'
```
Expected: el log muestra `seed_operator_created` en una base sin usuarios, no
hay errores de import de `docx`, y el login devuelve un token.

**NO commitear** — dejar todo verificado en el working tree para que el usuario
revise y commitee.

---

## Notas de revisión del plan

**Cobertura de lo que pidió el cliente.** «Que se guarde quién analizó/agregó
los reportes» → Tarea 4. «La fecha en que lo analizó, día/mes/año sin hora» →
Tarea 4, columna `analyzed_on` de tipo `Date`. «Poder filtrar los reportes por
quién los analizó» → Tarea 5 (API) y Tarea 8 (pantalla). «Seleccionar y exportar
en .doc» → Tarea 6 (backend) y Tarea 8 (selección y descarga). «Para temas de
KPI» → el conteo del ejemplo sale del propio filtro (`total`), y la Tarea 7
añade la comparativa entre analistas para el admin.

**El flujo del ejemplo, de punta a punta:** el admin entra en Reportes, elige
«Juan Pérez» en el selector de Analista, ve sus 7 reportes con la fecha de
análisis de cada uno, marca los que quiere y pulsa «Exportar a Word».

**Consistencia de tipos.** `analyst_id` es `int | None` en el modelo, el filtro
y el KPI. `analyst` en las respuestas de artículo es `str | None` (nombre para
mostrar), nunca un id. `analyzed_on` es `date` en todas partes —modelo, schema,
KPI— y se formatea a día/mes/año solo al pintarlo (`formatDay`). `AnalystOption`
(faceta del filtro, solo quienes tienen reportes) y `AnalystResponse` (catálogo
completo) son distintos a propósito.

**Lo que este plan NO hace, y conviene decirle al cliente:**
- El documento exportado es **`.docx`**, no el `.doc` binario de Word 97. Word
  lo abre desde 2007. Si el cliente exige la extensión literal, hay que decidirlo
  antes de construir la Tarea 6.
- El KPI mide **volumen**, no calidad. La tasa de corrección de R20 necesita
  auditoría campo a campo: plan aparte.
- No hay recuperación de contraseña; un admin la resetea desde la pantalla de
  analistas.
- Los artículos **ya guardados** quedan sin analista y sin fecha de análisis. No
  se inventa un backfill: no hay forma de saber quién revisó qué ni cuándo.
- La exportación no pagina: seleccionar varios cientos de reportes con cuerpo
  completo puede generar un documento pesado. Si el cliente exporta a esa
  escala, hay que añadir un tope y decirlo en pantalla.
