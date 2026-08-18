# Toggle de motor de análisis en Ajustes — Plan de implementación

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Agregar a la pestaña "Ajustes" del frontend un selector con dos opciones — "Cascada (Groq → Gemini → Local)" o "Solo Local" — que decide qué motor usa la función "Analizar URL" (`POST /api/analyze` y el guardado de artículos), sin reiniciar el proceso.

**Architecture:** Una tabla nueva de una sola fila (`runtime_settings`) guarda la preferencia. `services/settings_service.py` la lee/escribe. `services/analyzer_registry.py` gana una función `get_analyzer()` que, en cada llamada, consulta esa preferencia: si hay una fila guardada, arma el motor "Cascada" (Groq → Gemini → un `LocalAnalyzer` compartido, motor nuevo `CascadeAnalyzer`) o "Solo Local"; si NO hay fila (nadie tocó el toggle todavía), devuelve el analizador que ya construye `ODIN_ANALYZER` hoy — el comportamiento actual queda intacto por defecto. `analyze_service.py` y `article_service.py` pasan de importar un analizador fijo por nombre a pedirlo vía `get_analyzer()` en cada job. Un router nuevo (`GET`/`PUT /api/settings/analyzer`) expone la preferencia; el frontend agrega una fila más a la tarjeta de Ajustes ya preparada para crecer.

**Tech Stack:** FastAPI + Pydantic + SQLAlchemy 2.0 + Alembic (backend), React + TanStack Query + Vite/Vitest (frontend). Sin dependencias nuevas.

**Spec:** No hay spec separada — el alcance se acordó con el usuario durante la sesión de planificación (ver Contexto y Decisiones de alcance abajo). Este plan es la única referencia que viaja con la implementación.

## Contexto

Hoy el motor de análisis (`LocalAnalyzer` / `GroqAnalyzer` / `GeminiAnalyzer` / `HybridAnalyzer` / `GroqWithGeminiFallback`) lo elige **una sola vez, al arrancar el proceso**, la variable de entorno `ODIN_ANALYZER` (`src/odin/core/config.py:84-86`, consumida por `src/odin/services/analyzer_registry.py:19-81`). Cambiarlo hoy exige editar `.env` y reiniciar la API — no hay forma de alternarlo desde la UI. El usuario quiere poder elegir, desde la pestaña "Ajustes" del frontend, entre usar la cadena paga con red de seguridad (Groq → Gemini → Local) o quedarse exclusivamente con el motor local gratuito, y que el cambio aplique al siguiente análisis sin tocar el servidor.

### Decisiones de alcance (confirmadas con el usuario)

1. **Qué toca el toggle:** solo la función "Analizar URL" del frontend — `POST /api/analyze` (`services/analyze_service.py`) y el guardado del resultado (`services/article_service.py:save_article`). El scraper batch (`ScrapeJob`, que ya tiene su propio selector `local`/`groq`/`hybrid` por request en `scrape_job_service.py`) y el CLI (`main.py --analyzer`, gobernado por `ODIN_ANALYZER`) **no se tocan**.
2. **Compatibilidad con `ODIN_ANALYZER`:** hasta que alguien use el toggle por primera vez, `/api/analyze` sigue exactamente el comportamiento de hoy (incluidos los valores puros `gemini`/`groq`/`hybrid`, no solo `local`/`groq+gemini`). Recién cuando se guarda una preferencia explícita en Ajustes, esa preferencia manda — y de ahí en adelante ignora `ODIN_ANALYZER` para este único endpoint.

### Por qué una tabla nueva y no reusar `Settings` (`core/config.py`)

`Settings` es un `@dataclass(frozen=True)` leído una sola vez de variables de entorno al importar el módulo (`config.py:165`) — no está pensado para cambiar en caliente. La preferencia del toggle necesita persistir entre reinicios (si no, cada deploy la resetea) y ser mutable en runtime, así que va en una tabla (`runtime_settings`, una sola fila) igual que cualquier otro dato de negocio, no en el `.env`.

### Por qué un motor `CascadeAnalyzer` nuevo y no reusar `GroqWithGeminiFallback` tal cual

`GroqWithGeminiFallback` (`analysis/fallback_analyzer.py:60-168`) ya hace Groq → Gemini free → Gemini pago, pero si el último eslabón de Gemini también falla, **propaga la excepción** (`_run_gemini_chain`, línea 160-161: `if i == len(chain) - 1: raise`) — el análisis se pierde. La opción "Cascada" del toggle promete explícitamente "Groq/Gemini/Local", así que necesita un cuarto eslabón que nunca falla. `CascadeAnalyzer` envuelve `GroqWithGeminiFallback` sin tocarlo (sus tests y su uso desde `ODIN_ANALYZER=groq+gemini` siguen intactos) y agrega `LocalAnalyzer` como red de seguridad final.

### Corrección de paso: el árbitro pagado de entidades ambiguas

`arbitrate_ambiguous_persons` (`analyze_service.py:138-173`) decide si vale la pena una llamada extra a Gemini mirando un flag fijo (`ANALYZER_READS_WHOLE_ARTICLE`, calculado una sola vez de `ODIN_ANALYZER` en `analyzer_registry.py:28`). Con `CascadeAnalyzer` cayendo a Local silenciosamente en medio de un análisis, ese flag fijo mentiría (diría "un LLM ya lo leyó" cuando en realidad respondió Local). Este plan lo reemplaza por un chequeo posterior al análisis, basado en qué motor **realmente** respondió esa llamada (`active.name != "local"`) — más preciso que el comportamiento de hoy, no solo equivalente.

## Global Constraints

- Trabajar sobre `dev`. **No hacer commits** — dejar el working tree listo sin commitear; el usuario decide cuándo y qué commitear (ver `CLAUDE.md`).
- No ejecutar pruebas ni llamadas reales contra Groq/Gemini (`GROQ_API_KEY`/`GEMINI_API_KEY` reales) — todos los tests usan dobles/mocks, nunca la red.
- Todas las pruebas de BD/API usan SQLite en memoria vía las fixtures de `tests/conftest.py` (`api_client`, `sqlite_sessionmaker`, `db_session`), nunca la `DATABASE_URL` real.
- Las migraciones de Alembic se generan con `alembic revision -m "..."` (nunca a mano un `revision id`) y se revisan/editan antes de aplicarlas — ver `docs/adr/0002-alembic-sobre-migraciones-caseras.md`.

---

## Task 1: Tabla `runtime_settings`

**Files:**
- Modify: `src/odin/db/models.py`
- Create: `alembic/versions/<generado>_runtime_settings_ajustes_configurables.py`
- Test: `tests/db/test_runtime_settings_model.py`

**Interfaces:**
- Produce: `RuntimeSettings` (clase SQLAlchemy, `src/odin/db/models.py`) — columnas `id: int` (PK, siempre `1`), `analyzer_mode: str`, `updated_at: datetime`. La consume Task 2 (`settings_service.py`).

- [ ] **Step 1: Escribir el test que falla**

Crear `tests/db/test_runtime_settings_model.py` (si `tests/db/` no existe, crearlo con un `__init__.py` vacío — revisar primero con `ls tests/` si ya hay un paquete `tests/db/`; si no existe, crear también `tests/db/__init__.py` vacío):

```python
"""RuntimeSettings: fila única de preferencias configurables desde Ajustes
(hoy: el motor de análisis de POST /api/analyze), sin pasar por variables de
entorno ni reiniciar el proceso."""
from __future__ import annotations

from odin.db.models import RuntimeSettings


def test_persists_and_reads_back(db_session):
    db_session.add(RuntimeSettings(id=1, analyzer_mode="cascade"))
    db_session.commit()

    row = db_session.get(RuntimeSettings, 1)
    assert row.analyzer_mode == "cascade"
    assert row.updated_at is not None
```

- [ ] **Step 2: Confirmar que falla**

Run: `pytest tests/db/test_runtime_settings_model.py -v`
Expected: FAIL — `ImportError: cannot import name 'RuntimeSettings'`.

- [ ] **Step 3: Agregar el modelo**

En `src/odin/db/models.py`, después de la clase `EntityAlias` (línea 380), agregar:

```python
class RuntimeSettings(Base):
    """Fila única (id=1) de preferencias configurables desde Ajustes, sin
    pasar por variables de entorno (ver core/config.py) ni reiniciar el
    proceso.

    Hoy solo `analyzer_mode` (motor de POST /api/analyze: "cascade" o
    "local", ver services/analyzer_registry.py). Sin fila, ese servicio
    sigue el comportamiento de ODIN_ANALYZER de siempre — esta tabla es un
    override explícito, no un default duplicado.
    """

    __tablename__ = "runtime_settings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    analyzer_mode: Mapped[str] = mapped_column(String(20))

    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, onupdate=_utcnow
    )

    def __repr__(self) -> str:  # pragma: no cover
        return f"<RuntimeSettings analyzer_mode={self.analyzer_mode!r}>"
```

(`Integer`, `String`, `DateTime`, `Mapped`, `mapped_column`, `_utcnow`, `Base` ya están importados/definidos en ese archivo — es el mismo patrón que `EntityAlias`.)

- [ ] **Step 4: Confirmar que pasa**

Run: `pytest tests/db/test_runtime_settings_model.py -v`
Expected: PASS.

- [ ] **Step 5: Generar y editar la migración**

Run: `alembic revision -m "runtime settings: ajustes configurables sin variables de entorno"`

Esto crea `alembic/versions/<hash>_runtime_settings_ajustes_configurables_sin_.py` con `revision`/`down_revision` ya completados por la herramienta (el `down_revision` debe quedar en `c4d7b91f0a35`, la cabeza actual — confirmarlo abriendo el archivo generado). Reemplazar el cuerpo de `upgrade()`/`downgrade()` por:

```python
def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "runtime_settings",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("analyzer_mode", sa.String(length=20), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_table("runtime_settings")
```

- [ ] **Step 6: Aplicar la migración**

Run: `alembic upgrade head`
Expected: corre sin error contra la `DATABASE_URL` del `.env` (o `DATABASE_URL="sqlite:///odin.db" alembic upgrade head` si no hay Postgres local corriendo).

- [ ] **Step 7: Dejar el working tree listo (sin commit)**

No commitear — el usuario decide cuándo.

---

## Task 2: `settings_service.py`

**Files:**
- Create: `src/odin/services/settings_service.py`
- Test: `tests/api/test_api_settings.py` (cubre este servicio a través del router — ver Task 7; no hace falta un test de servicio aislado porque `alias_service.py`, el paralelo más cercano, tampoco lo tiene)

Esta tarea deja el servicio implementado; el test que lo ejerce se escribe recién en Task 7 junto con el router (así el test cubre el flujo completo HTTP → servicio → BD de una sola vez, igual que el resto de la API). Sin test propio en esta tarea, el "Step 1/2" de TDD se hace en Task 7.

**Interfaces:**
- Consume: `RuntimeSettings` (Task 1), `odin.api.deps.get_session` (ya existe).
- Produce: `get_analyzer_mode() -> str | None` y `set_analyzer_mode(mode: str) -> str`, ambos en `src/odin/services/settings_service.py` — los consume Task 4 (`analyzer_registry.get_analyzer()`) y Task 7 (router).

- [ ] **Step 1: Escribir el servicio**

Crear `src/odin/services/settings_service.py`:

```python
"""Preferencias configurables desde Ajustes sin variables de entorno (hoy:
el motor de análisis de POST /api/analyze — ver services/analyzer_registry.py).

Una sola fila (id=1): no hay multiusuario que justifique una tabla
clave-valor genérica (ver core/auth.py, "usuario único"). Sin fila, quien la
consulta debe asumir que nadie tocó el toggle todavía —
services/analyzer_registry.py interpreta eso como "seguir con
ODIN_ANALYZER", el comportamiento de antes de este archivo.
"""
from __future__ import annotations

from fastapi import HTTPException

from odin.api import deps
from odin.api.deps import log
from odin.db.models import RuntimeSettings

_ROW_ID = 1


def get_analyzer_mode() -> str | None:
    """`None` si nadie guardó una preferencia todavía."""
    session = deps.get_session()
    try:
        row = session.get(RuntimeSettings, _ROW_ID)
        return row.analyzer_mode if row is not None else None
    finally:
        session.close()


def set_analyzer_mode(mode: str) -> str:
    """Guarda (o reemplaza) la preferencia. `mode` ya viene validado por el
    `Literal["cascade", "local"]` del schema Pydantic del router — ver
    api/schemas.py:AnalyzerSettingsUpdatePayload."""
    session = deps.get_session()
    try:
        row = session.get(RuntimeSettings, _ROW_ID)
        if row is None:
            row = RuntimeSettings(id=_ROW_ID, analyzer_mode=mode)
            session.add(row)
        else:
            row.analyzer_mode = mode
        session.commit()
        return row.analyzer_mode
    except Exception:
        session.rollback()
        log.exception("settings_analyzer_mode_update_failed")
        raise HTTPException(
            status_code=500, detail="Error interno guardando la preferencia."
        ) from None
    finally:
        session.close()
```

- [ ] **Step 2: Verificar que importa sin error**

Run: `python -c "from odin.services import settings_service"`
Expected: sin salida (sin excepción).

- [ ] **Step 3: Dejar el working tree listo (sin commit)**

---

## Task 3: `CascadeAnalyzer` (Groq → Gemini → Local)

**Files:**
- Modify: `src/odin/analysis/fallback_analyzer.py`
- Test: `tests/analysis/test_cascade_analyzer.py`

**Interfaces:**
- Consume: `GroqWithGeminiFallback` (ya existe en el mismo archivo, sin cambios), `Analyzer`/`AnalysisResult` (`odin.analysis.base`).
- Produce: `CascadeAnalyzer(local: Analyzer)` (clase, `src/odin/analysis/fallback_analyzer.py`) — atributos `name`/`version`/`model` (properties) y método `analyze(title, body) -> AnalysisResult`. La consume Task 4 (`analyzer_registry._cascade_analyzer()`).

- [ ] **Step 1: Escribir el test que falla**

Crear `tests/analysis/test_cascade_analyzer.py`:

```python
"""CascadeAnalyzer: Groq → Gemini (GroqWithGeminiFallback, sin tocar) →
LocalAnalyzer si ambos fallan — a diferencia de GroqWithGeminiFallback, esta
nunca deja al usuario sin análisis. Sin red: ambos motores externos son
dobles."""
from __future__ import annotations

from odin.analysis.base import AnalysisResult
from odin.analysis.fallback_analyzer import CascadeAnalyzer
from odin.analysis.local_analyzer import LocalAnalyzer


class _FakeGroqGemini:
    name = "groq"
    model = "groq-model"
    version = "v1"

    def __init__(self, *, fails: bool = False) -> None:
        self._fails = fails

    def analyze(self, title: str, body: str) -> AnalysisResult:
        if self._fails:
            raise RuntimeError("saturado")
        return AnalysisResult(main_topic="groq-result")


class _FakeLocal:
    name = "local"
    model = "local-model"
    version = "1"

    def analyze(self, title: str, body: str) -> AnalysisResult:
        return AnalysisResult(main_topic="local-result")


def test_uses_groq_gemini_when_it_succeeds():
    cascade = CascadeAnalyzer(local=_FakeLocal())
    cascade._groq_gemini = _FakeGroqGemini(fails=False)

    result = cascade.analyze("t", "b")

    assert result.main_topic == "groq-result"
    assert cascade.name == "groq"
    assert cascade.model == "groq-model"
    assert cascade.version == "v1"


def test_falls_back_to_local_when_groq_gemini_fails():
    cascade = CascadeAnalyzer(local=_FakeLocal())
    cascade._groq_gemini = _FakeGroqGemini(fails=True)

    result = cascade.analyze("t", "b")

    assert result.main_topic == "local-result"
    assert cascade.name == "local"
    assert cascade.model == "local-model"


def test_constructs_with_a_real_local_analyzer_without_touching_the_network():
    # Solo construcción: LocalAnalyzer carga spaCy de forma perezosa (nunca
    # en __init__), así que esto no toca disco ni red.
    cascade = CascadeAnalyzer(local=LocalAnalyzer())
    assert cascade.name == "groq"  # antes del primer analyze(), asume Groq
```

- [ ] **Step 2: Confirmar que falla**

Run: `pytest tests/analysis/test_cascade_analyzer.py -v`
Expected: FAIL — `ImportError: cannot import name 'CascadeAnalyzer'`.

- [ ] **Step 3: Implementar `CascadeAnalyzer`**

En `src/odin/analysis/fallback_analyzer.py`, agregar al final del archivo (después de `GroqWithGeminiFallback`), y cambiar el import de la línea 37 de:

```python
from odin.analysis.base import AnalysisResult
```

a:

```python
from odin.analysis.base import AnalysisResult, Analyzer
```

Luego agregar al final del archivo:

```python
class CascadeAnalyzer:
    """Groq → Gemini (ver GroqWithGeminiFallback arriba) → LocalAnalyzer si
    ambos fallan.

    GroqWithGeminiFallback PROPAGA si el último eslabón de Gemini también
    falla (ver `_run_gemini_chain` arriba) — correcto para
    `ODIN_ANALYZER=groq+gemini`, donde el usuario pidió explícitamente esos
    dos motores y nada más. La opción "Cascada" del toggle de Ajustes
    promete "Groq/Gemini/Local" sin excepción: esta clase envuelve
    GroqWithGeminiFallback sin tocarlo y agrega Local como red de seguridad
    final, para que un análisis nunca se pierda del todo.

    `name`/`version`/`model` son propiedades que reflejan el motor que
    respondió el ÚLTIMO analyze() de este hilo — igual razón que en
    GroqWithGeminiFallback (linaje por hilo, ver ese docstring).
    """

    def __init__(self, local: Analyzer) -> None:
        self._groq_gemini = GroqWithGeminiFallback()
        self._local = local
        self._state = threading.local()

    @property
    def _last(self):
        return getattr(self._state, "engine", None) or self._groq_gemini

    @property
    def name(self) -> str:
        return self._last.name

    @property
    def version(self) -> str:
        return self._last.version

    @property
    def model(self) -> str:
        return self._last.model

    def analyze(self, title: str, body: str) -> AnalysisResult:
        try:
            result = self._groq_gemini.analyze(title, body)
        except Exception as exc:
            log.warning(
                "cascada_groq_gemini_fallo_usando_local error=%s: %s",
                type(exc).__name__,
                exc,
            )
            result = self._local.analyze(title, body)
            self._state.engine = self._local
        else:
            self._state.engine = self._groq_gemini
        return result
```

- [ ] **Step 4: Confirmar que pasa**

Run: `pytest tests/analysis/test_cascade_analyzer.py -v`
Expected: PASS (3 tests).

- [ ] **Step 5: Dejar el working tree listo (sin commit)**

---

## Task 4: `analyzer_registry.get_analyzer()`

**Files:**
- Modify: `src/odin/services/analyzer_registry.py`
- Test: `tests/services/test_analyzer_registry.py`

**Interfaces:**
- Consume: `settings_service.get_analyzer_mode()` (Task 2), `CascadeAnalyzer` (Task 3), `LocalAnalyzer` (ya existe), el `analyzer` module-level singleton (ya existe, sin tocar su construcción).
- Produce: `get_analyzer() -> Analyzer` y `local_analyzer() -> LocalAnalyzer` (funciones nuevas, `src/odin/services/analyzer_registry.py`) — las consumen Task 5 (`analyze_service.py`), Task 6 (`article_service.py`) y Task 7 (warm-up en `api/__init__.py`).

- [ ] **Step 1: Escribir el test que falla**

Crear `tests/services/test_analyzer_registry.py`:

```python
"""get_analyzer(): elige entre el analizador fijado por ODIN_ANALYZER
(comportamiento de siempre, cuando nadie tocó el toggle) y el override
guardado en Ajustes (cascada Groq→Gemini→Local, o solo Local) — ver
services/settings_service.py. Sin red: la construcción de
GroqAnalyzer/GeminiAnalyzer no llama a ninguna API, solo guarda config."""
from __future__ import annotations

import pytest

from odin.analysis.fallback_analyzer import CascadeAnalyzer
from odin.analysis.local_analyzer import LocalAnalyzer
from odin.services import analyzer_registry, settings_service


@pytest.fixture(autouse=True)
def _reset_analyzer_registry_cache():
    """`_local`/`_cascade` son cachés de proceso (ver Step 3): sin esto, un
    test que las llena decide lo que ve el siguiente."""
    analyzer_registry._local = None
    analyzer_registry._cascade = None
    yield
    analyzer_registry._local = None
    analyzer_registry._cascade = None


class TestGetAnalyzer:
    def test_returns_configured_analyzer_when_nothing_saved(self, monkeypatch):
        monkeypatch.setattr(settings_service, "get_analyzer_mode", lambda: None)
        assert analyzer_registry.get_analyzer() is analyzer_registry.analyzer

    def test_local_mode_returns_a_local_analyzer(self, monkeypatch):
        monkeypatch.setattr(settings_service, "get_analyzer_mode", lambda: "local")
        assert isinstance(analyzer_registry.get_analyzer(), LocalAnalyzer)

    def test_local_mode_reuses_the_same_instance_across_calls(self, monkeypatch):
        monkeypatch.setattr(settings_service, "get_analyzer_mode", lambda: "local")
        first = analyzer_registry.get_analyzer()
        second = analyzer_registry.get_analyzer()
        assert first is second

    def test_cascade_mode_returns_a_cascade_analyzer(self, monkeypatch):
        monkeypatch.setattr(settings_service, "get_analyzer_mode", lambda: "cascade")
        assert isinstance(analyzer_registry.get_analyzer(), CascadeAnalyzer)

    def test_cascade_mode_reuses_the_same_instance_across_calls(self, monkeypatch):
        monkeypatch.setattr(settings_service, "get_analyzer_mode", lambda: "cascade")
        first = analyzer_registry.get_analyzer()
        second = analyzer_registry.get_analyzer()
        assert first is second


class TestLocalAnalyzerHelper:
    def test_returns_the_configured_instance_when_odin_analyzer_is_local(self, monkeypatch):
        monkeypatch.setattr(analyzer_registry, "analyzer", LocalAnalyzer())
        assert analyzer_registry.local_analyzer() is analyzer_registry.analyzer

    def test_builds_a_separate_instance_when_odin_analyzer_is_not_local(self, monkeypatch):
        class _FakeGemini:
            name = "gemini"

        monkeypatch.setattr(analyzer_registry, "analyzer", _FakeGemini())
        local = analyzer_registry.local_analyzer()
        assert isinstance(local, LocalAnalyzer)
        assert local is not analyzer_registry.analyzer
```

- [ ] **Step 2: Confirmar que falla**

Run: `pytest tests/services/test_analyzer_registry.py -v`
Expected: FAIL — `AttributeError: module 'odin.services.analyzer_registry' has no attribute 'get_analyzer'`.

- [ ] **Step 3: Implementar `get_analyzer()`/`local_analyzer()`**

En `src/odin/services/analyzer_registry.py`, agregar al final del archivo (después del bloque `if settings.gemini_arbiter:` existente, sin tocar nada de lo anterior):

```python
# ── Override de Ajustes (independiente de ODIN_ANALYZER) ────────────────────
#
# Lo de arriba (`analyzer`, `ANALYZER_READS_WHOLE_ARTICLE`) elige el motor UNA
# SOLA VEZ al arrancar el proceso, vía ODIN_ANALYZER — sigue intacto y sigue
# gobernando el CLI (main.py --analyzer) y cualquier consumidor que importe
# `analyzer` directo. Lo de abajo es el override que puede guardar la
# pestaña Ajustes (services/settings_service.py) para SOLO POST /api/analyze
# (analyze_service.py, article_service.py): consulta la preferencia en CADA
# llamada, así un cambio en la UI aplica al siguiente análisis sin reiniciar
# el proceso. Sin preferencia guardada, `get_analyzer()` devuelve el mismo
# `analyzer` de arriba — el comportamiento de antes de que existiera este
# toggle.

_local: LocalAnalyzer | None = None
_cascade: Analyzer | None = None


def local_analyzer() -> LocalAnalyzer:
    """Instancia compartida de LocalAnalyzer para los modos "local" y
    "cascade" del toggle: si ODIN_ANALYZER ya construyó una arriba (`analyzer`
    ya es un LocalAnalyzer), la reusa en vez de cargar spaCy/pysentimiento
    una segunda vez."""
    global _local
    if isinstance(analyzer, LocalAnalyzer):
        return analyzer
    if _local is None:
        _local = LocalAnalyzer()
    return _local


def _cascade_analyzer() -> Analyzer:
    global _cascade
    if _cascade is None:
        from odin.analysis.fallback_analyzer import CascadeAnalyzer

        _cascade = CascadeAnalyzer(local=local_analyzer())
    return _cascade


def get_analyzer() -> Analyzer:
    """Analizador para EL PRÓXIMO análisis de /api/analyze. Ver el docstring
    de esta sección para el porqué de la prioridad."""
    from odin.services import settings_service

    mode = settings_service.get_analyzer_mode()
    if mode == "local":
        return local_analyzer()
    if mode == "cascade":
        return _cascade_analyzer()
    return analyzer
```

- [ ] **Step 4: Confirmar que pasa**

Run: `pytest tests/services/test_analyzer_registry.py -v`
Expected: PASS (7 tests).

- [ ] **Step 5: Dejar el working tree listo (sin commit)**

---

## Task 5: Conectar `analyze_service.py`

**Files:**
- Modify: `src/odin/services/analyze_service.py`
- Modify: `tests/services/test_analyze_arbiter_guard.py` (firma nueva de `arbitrate_ambiguous_persons`)
- Modify: `tests/api/test_api_analyze_jobs.py` (firma nueva de `analyze_safely`/`arbitrate_ambiguous_persons`)

**Interfaces:**
- Consume: `analyzer_registry.get_analyzer()` (Task 4).
- Produce: `analyze_safely(active, title, body)` y `arbitrate_ambiguous_persons(result, *, reads_whole_article: bool)` (firmas nuevas, `src/odin/services/analyze_service.py`) — los consumen los tests modificados en esta tarea y, indirectamente, `run_analyze_job` (mismo archivo).

- [ ] **Step 1: Actualizar los tests existentes a la firma nueva (deben fallar primero)**

En `tests/services/test_analyze_arbiter_guard.py`, reemplazar la función helper `_enable_arbiter` y los cuatro tests que llaman `analyze_service.arbitrate_ambiguous_persons(result)` para que pasen `reads_whole_article` explícito en vez de monkeypatchear `ANALYZER_READS_WHOLE_ARTICLE`:

```python
def _enable_arbiter(monkeypatch) -> None:
    monkeypatch.setattr(
        analyze_service,
        "settings",
        dataclasses.replace(analyze_service.settings, gemini_arbiter=True),
    )


class TestArbiterIsSkipped:
    def test_when_disabled(self, monkeypatch, arbiter_calls):
        monkeypatch.setattr(
            analyze_service,
            "settings",
            dataclasses.replace(analyze_service.settings, gemini_arbiter=False),
        )

        result = _result_with_venue_person()
        analyze_service.arbitrate_ambiguous_persons(result, reads_whole_article=False)

        assert arbiter_calls == []
        assert len(result.entities) == 1

    def test_with_any_llm_analyzer_even_if_enabled(self, monkeypatch, arbiter_calls):
        """El guard miraba solo `ODIN_ANALYZER=gemini`, así que con groq/hybrid/
        groq+gemini se pagaba un segundo chequeo de algo que el prompt de esos
        motores ya resuelve."""
        _enable_arbiter(monkeypatch)

        result = _result_with_venue_person()
        analyze_service.arbitrate_ambiguous_persons(result, reads_whole_article=True)

        assert arbiter_calls == []
        assert len(result.entities) == 1

    def test_when_no_entity_is_ambiguous(self, monkeypatch, arbiter_calls):
        _enable_arbiter(monkeypatch)

        result = AnalysisResult(
            entities=[
                EntityResult(name="Luis Abinader", type="PERSON", context="Abinader anunció el plan.")
            ]
        )
        analyze_service.arbitrate_ambiguous_persons(result, reads_whole_article=False)

        assert arbiter_calls == []
        assert len(result.entities) == 1


class TestArbiterRuns:
    def test_with_the_local_analyzer_and_an_ambiguous_person(self, monkeypatch, arbiter_calls):
        _enable_arbiter(monkeypatch)

        result = _result_with_venue_person()
        analyze_service.arbitrate_ambiguous_persons(result, reads_whole_article=False)

        assert len(arbiter_calls) == 1  # UNA sola llamada para todo el artículo
        assert result.entities == []  # el doble respondió "no es una mención real"
```

En `tests/api/test_api_analyze_jobs.py`, cambiar las cuatro líneas de `monkeypatch.setattr`:

- Línea 82: `monkeypatch.setattr(analyze_service, "analyze_safely", lambda title, body: _fake_analysis_result())` → `monkeypatch.setattr(analyze_service, "analyze_safely", lambda active, title, body: _fake_analysis_result())`
- Línea 83: `monkeypatch.setattr(analyze_service, "arbitrate_ambiguous_persons", lambda result: None)` → `monkeypatch.setattr(analyze_service, "arbitrate_ambiguous_persons", lambda result, **kwargs: None)`
- Línea 209: `monkeypatch.setattr(analyze_service, "analyze_safely", _analyze)` — revisar la firma de `_analyze` definida arriba en ese mismo test (línea ~200) y agregarle el parámetro `active` como primero.
- Línea 210: `monkeypatch.setattr(analyze_service, "arbitrate_ambiguous_persons", lambda result: None)` → `monkeypatch.setattr(analyze_service, "arbitrate_ambiguous_persons", lambda result, **kwargs: None)`

- [ ] **Step 2: Confirmar que los tests existentes ahora fallan por la firma vieja**

Run: `pytest tests/services/test_analyze_arbiter_guard.py tests/api/test_api_analyze_jobs.py -v`
Expected: FAIL — `TypeError: arbitrate_ambiguous_persons() got an unexpected keyword argument 'reads_whole_article'` (la implementación todavía no cambió).

- [ ] **Step 3: Actualizar `analyze_service.py`**

Cambiar el import de la línea 37, de:

```python
from odin.services.analyzer_registry import ANALYZER_READS_WHOLE_ARTICLE, analyzer
```

a:

```python
from odin.services import analyzer_registry
```

Cambiar `analyze_safely` (línea 112):

```python
def analyze_safely(active, title: str, body: str):
    """Ejecuta `active` (el analizador elegido para ESTE job, ver
    `analyzer_registry.get_analyzer()`) traduciendo cualquier fallo a un
    mensaje presentable.

    `RuntimeError` es el error "esperado" —los analizadores lo usan para lo que
    el usuario sí puede entender: "el servicio de IA está saturado", "no se
    pudo parsear la respuesta"— y su texto va tal cual al UI. Lo que no lo es
    (un error del SDK de Groq/Gemini, un timeout de httpx, un fallo de
    validación) antes también terminaba en pantalla como `str(exc)`: jerga
    inútil para quien pegó un link, y detalle interno de más. Se registra
    completo en el log y al usuario le llega una frase que puede accionar.
    """
    try:
        return active.analyze(title, body)
    except HTTPException:
        raise
    except RuntimeError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    except Exception as exc:
        log.exception("analyzer_failed", analyzer=active.name)
        raise HTTPException(
            status_code=502,
            detail="El servicio de análisis no está disponible en este momento. Intenta de nuevo.",
        ) from exc
```

Cambiar `arbitrate_ambiguous_persons` (línea 138): agregar el parámetro y reemplazar la condición de salida. La firma pasa de `def arbitrate_ambiguous_persons(result) -> None:` a `def arbitrate_ambiguous_persons(result, *, reads_whole_article: bool) -> None:`, agregando este párrafo al docstring existente (después del que empieza "Se salta con CUALQUIER motor LLM..."):

```
    `reads_whole_article` refleja el motor que REALMENTE respondió ESTA
    llamada (ver CascadeAnalyzer/GroqWithGeminiFallback, cuyo `.name` cambia
    según quién contestó al final), no el modo elegido en Ajustes: si la
    cadena Groq→Gemini falló y "Cascada" cayó a LocalAnalyzer, el árbitro
    debe correr igual que si el modo elegido fuera "Solo Local".
```

y cambiar la primera línea del cuerpo de:

```python
    if ANALYZER_READS_WHOLE_ARTICLE or not settings.gemini_arbiter:
        return
```

a:

```python
    if reads_whole_article or not settings.gemini_arbiter:
        return
```

(el resto del cuerpo de la función queda igual).

Por último, en `run_analyze_job` (línea 176), dentro del bloque `try` interno (línea 198), cambiar:

```python
            extracted = fetch_and_extract(url)

            job.stage = "analyzing"
            session.commit()
            result = analyze_safely(extracted["title"], extracted["body"])
            arbitrate_ambiguous_persons(result)
```

a:

```python
            extracted = fetch_and_extract(url)

            job.stage = "analyzing"
            session.commit()
            active = analyzer_registry.get_analyzer()
            result = analyze_safely(active, extracted["title"], extracted["body"])
            arbitrate_ambiguous_persons(result, reads_whole_article=active.name != "local")
```

Y más abajo, dentro de la construcción de `AnalyzeResult` (líneas 238-240), cambiar:

```python
                analyzer_name=analyzer.name,
                analyzer_model=analyzer.model,
                analyzer_version=analyzer.version,
```

a:

```python
                analyzer_name=active.name,
                analyzer_model=active.model,
                analyzer_version=active.version,
```

- [ ] **Step 4: Confirmar que todo pasa**

Run: `pytest tests/services/test_analyze_arbiter_guard.py tests/api/test_api_analyze_jobs.py -v`
Expected: PASS (todos los tests de ambos archivos).

- [ ] **Step 5: Dejar el working tree listo (sin commit)**

---

## Task 6: Conectar `article_service.py`

**Files:**
- Modify: `src/odin/services/article_service.py`
- Modify: `tests/api/test_api_canonical_entities.py` (el test `test_stamps_analyzer_lineage` monkeypatchea el nombre viejo)

**Interfaces:**
- Consume: `analyzer_registry.get_analyzer()` (Task 4).

- [ ] **Step 1: Actualizar el test existente a la firma nueva (debe fallar primero)**

En `tests/api/test_api_canonical_entities.py`, dentro de `test_stamps_analyzer_lineage` (línea 302), cambiar la línea:

```python
        monkeypatch.setattr(article_service, "analyzer", _FakeAnalyzer())
```

a:

```python
        monkeypatch.setattr(article_service.analyzer_registry, "get_analyzer", lambda: _FakeAnalyzer())
```

Y actualizar el comentario de las líneas 315-322 (que explica por qué se fija el analizador a un valor conocido) para que hable de `get_analyzer()` en vez del `analyzer` importado por valor:

```python
        # `article_service.analyzer_registry.get_analyzer()` decide el motor
        # activo — ver services/analyzer_registry.py. Sin preferencia
        # guardada en Ajustes, cae al `analyzer` fijado por ODIN_ANALYZER,
        # que en la máquina de un desarrollador puede no ser "local" (p.ej.
        # "hybrid" en .env para uso manual). Este test solo verifica que el
        # linaje se graba con lo que devuelva `get_analyzer()`, no cuál es,
        # así que se fija a un valor conocido en vez de asumir el default.
```

- [ ] **Step 2: Confirmar que falla**

Run: `pytest tests/api/test_api_canonical_entities.py::TestCanonicalization::test_stamps_analyzer_lineage -v`
Expected: FAIL — `AttributeError: <module 'odin.services.article_service'> does not have the attribute 'analyzer_registry'` (todavía no se importó así).

(Si el nombre exacto de la clase contenedora difiere, ejecutar `pytest tests/api/test_api_canonical_entities.py -k test_stamps_analyzer_lineage -v` para ubicarlo.)

- [ ] **Step 3: Actualizar `article_service.py`**

Cambiar el import de la línea 40, de:

```python
from odin.services.analyzer_registry import analyzer
```

a:

```python
from odin.services import analyzer_registry
```

Dentro de `save_article` (línea 353), justo después de la línea `entities = canonicalize_entities(list(req.entities))` (línea 368), agregar:

```python
        active = analyzer_registry.get_analyzer()
```

Y cambiar las tres líneas de linaje dentro de la construcción de `Article(...)` (líneas 393-395), de:

```python
            analyzer_name=analyzer.name,
            analyzer_model=analyzer.model,
            analyzer_version=analyzer.version,
```

a:

```python
            analyzer_name=active.name,
            analyzer_model=active.model,
            analyzer_version=active.version,
```

- [ ] **Step 4: Confirmar que pasa**

Run: `pytest tests/api/test_api_canonical_entities.py -v`
Expected: PASS (todos los tests del archivo).

- [ ] **Step 5: Dejar el working tree listo (sin commit)**

---

## Task 7: Schemas + router `/api/settings/analyzer` + warm-up

**Files:**
- Modify: `src/odin/api/schemas.py`
- Create: `src/odin/api/routers/settings.py`
- Modify: `src/odin/api/__init__.py`
- Test: `tests/api/test_api_settings.py`

**Interfaces:**
- Consume: `settings_service.get_analyzer_mode()`/`set_analyzer_mode()` (Task 2), `analyzer_registry.analyzer`/`local_analyzer()` (Task 4), `odin.core.auth.require_auth` (ya existe), `odin.core.config.settings` (ya existe).
- Produce: `AnalyzerSettingsResponse`/`AnalyzerSettingsUpdatePayload` (Pydantic, `src/odin/api/schemas.py`) — los consume Task 8 (`openapi-typescript` genera `api-types.ts` a partir de ellos).

- [ ] **Step 1: Escribir el test que falla**

Crear `tests/api/test_api_settings.py`:

```python
"""GET/PUT /api/settings/analyzer: preferencia de motor para "Analizar URL"
(Cascada Groq→Gemini→Local vs. Solo Local), sin pasar por ODIN_ANALYZER ni
reiniciar el proceso — ver services/settings_service.py."""
from __future__ import annotations

import dataclasses

from odin.core.auth import create_token
from odin.db.models import RuntimeSettings


def _auth_headers() -> dict[str, str]:
    token, _ = create_token("tester")
    return {"Authorization": f"Bearer {token}"}


class TestGetAnalyzerSettings:
    def test_returns_null_mode_when_nothing_saved(self, api_client):
        resp = api_client.get("/api/settings/analyzer")
        assert resp.status_code == 200
        body = resp.json()
        assert body["mode"] is None
        assert body["default_mode"] in ("cascade", "local")

    def test_default_mode_is_local_when_odin_analyzer_is_local(self, api_client, monkeypatch):
        import odin.api.routers.settings as settings_router

        monkeypatch.setattr(
            settings_router,
            "settings",
            dataclasses.replace(settings_router.settings, analyzer="local"),
        )
        resp = api_client.get("/api/settings/analyzer")
        assert resp.json()["default_mode"] == "local"

    def test_default_mode_is_cascade_for_llm_engines(self, api_client, monkeypatch):
        import odin.api.routers.settings as settings_router

        monkeypatch.setattr(
            settings_router,
            "settings",
            dataclasses.replace(settings_router.settings, analyzer="groq"),
        )
        resp = api_client.get("/api/settings/analyzer")
        assert resp.json()["default_mode"] == "cascade"


class TestUpdateAnalyzerSettings:
    def test_requires_auth(self, api_client):
        resp = api_client.put("/api/settings/analyzer", json={"mode": "local"})
        assert resp.status_code == 401

    def test_saves_and_persists(self, api_client, sqlite_sessionmaker):
        resp = api_client.put(
            "/api/settings/analyzer", json={"mode": "local"}, headers=_auth_headers()
        )
        assert resp.status_code == 200
        assert resp.json()["mode"] == "local"

        session = sqlite_sessionmaker()
        row = session.get(RuntimeSettings, 1)
        assert row.analyzer_mode == "local"

        resp = api_client.get("/api/settings/analyzer")
        assert resp.json()["mode"] == "local"

    def test_rejects_invalid_mode(self, api_client):
        resp = api_client.put(
            "/api/settings/analyzer", json={"mode": "gemini"}, headers=_auth_headers()
        )
        assert resp.status_code == 422

    def test_overwrites_previous_choice(self, api_client, sqlite_sessionmaker):
        api_client.put("/api/settings/analyzer", json={"mode": "local"}, headers=_auth_headers())
        resp = api_client.put(
            "/api/settings/analyzer", json={"mode": "cascade"}, headers=_auth_headers()
        )
        assert resp.json()["mode"] == "cascade"

        session = sqlite_sessionmaker()
        assert session.query(RuntimeSettings).count() == 1
```

- [ ] **Step 2: Confirmar que falla**

Run: `pytest tests/api/test_api_settings.py -v`
Expected: FAIL — `404 Not Found` (la ruta todavía no existe) o `ModuleNotFoundError`.

- [ ] **Step 3: Agregar los schemas Pydantic**

En `src/odin/api/schemas.py`, después de la clase `AliasUpdatePayload` (línea 78), agregar:

```python
# ── Ajustes ───────────────────────────────────────────────────────────────


class AnalyzerSettingsResponse(BaseModel):
    """`mode=None` significa "nadie guardó una preferencia todavía": el
    frontend debe mostrar `default_mode` como seleccionado, pero no hay
    override guardado (ver services/analyzer_registry.get_analyzer())."""

    mode: Literal["cascade", "local"] | None
    default_mode: Literal["cascade", "local"]


class AnalyzerSettingsUpdatePayload(BaseModel):
    mode: Literal["cascade", "local"]
```

- [ ] **Step 4: Crear el router**

Crear `src/odin/api/routers/settings.py`:

```python
"""Ajustes configurables desde la UI sin variables de entorno (hoy: motor de
análisis de POST /api/analyze — ver services/settings_service.py)."""
from __future__ import annotations

from fastapi import APIRouter, Depends

from odin.api.schemas import AnalyzerSettingsResponse, AnalyzerSettingsUpdatePayload
from odin.core import auth
from odin.core.config import settings
from odin.services import settings_service

router = APIRouter(tags=["settings"])


def _default_mode() -> str:
    """Para mostrar algo razonable en la UI mientras nadie guardó una
    preferencia explícita: "local" si ODIN_ANALYZER=local, "cascade" para
    cualquier motor que pague (gemini/groq/hybrid/groq+gemini) — no es una
    preferencia guardada, solo lo que reflejaría el comportamiento actual."""
    return "local" if settings.analyzer == "local" else "cascade"


@router.get("/api/settings/analyzer", response_model=AnalyzerSettingsResponse)
def get_analyzer_settings():
    return AnalyzerSettingsResponse(
        mode=settings_service.get_analyzer_mode(), default_mode=_default_mode()
    )


@router.put(
    "/api/settings/analyzer",
    dependencies=[Depends(auth.require_auth)],
    response_model=AnalyzerSettingsResponse,
)
def update_analyzer_settings(payload: AnalyzerSettingsUpdatePayload):
    mode = settings_service.set_analyzer_mode(payload.mode)
    return AnalyzerSettingsResponse(mode=mode, default_mode=_default_mode())
```

- [ ] **Step 5: Registrar el router y actualizar el warm-up en `api/__init__.py`**

Cambiar el bloque de import de routers (líneas 39-47), de:

```python
from odin.api.routers import (
    aliases,
    analyze,
    articles,
    canonical_entities,
    entities,
    misc,
    scrape_jobs,
)
```

a:

```python
from odin.api.routers import (
    aliases,
    analyze,
    articles,
    canonical_entities,
    entities,
    misc,
    scrape_jobs,
    settings as settings_router,
)
```

(el alias `as settings_router` evita chocar con `from odin.core.config import settings`, ya importado más abajo en el mismo archivo, línea 49).

Cambiar la línea 60, de:

```python
from odin.services.analyzer_registry import analyzer
```

a:

```python
from odin.services import analyzer_registry
```

Reemplazar `_warm_up_analyzer` (líneas 67-93) completa por:

```python
def _warm_up_analyzer() -> None:
    """Carga los modelos locales antes del primer request.

    Calienta DOS candidatos, no solo el de `ODIN_ANALYZER`: desde que existe
    el override de Ajustes (`analyzer_registry.get_analyzer()`), el primer
    análisis tras un despliegue puede terminar usando
    `analyzer_registry.local_analyzer()` en vez del `analyzer` de abajo —
    alguien ya había elegido "Solo Local"/"Cascada" en una corrida anterior
    y esa preferencia sigue en la BD. Sin este segundo candidato, ESE primer
    análisis pagaría la carga de spaCy (~1.6s) y pysentimiento (~4.3s) que
    este warm-up existe para evitar. En el caso común (`ODIN_ANALYZER=local`
    o nadie tocó el toggle todavía) los dos candidatos son el MISMO objeto:
    calentarlo "dos veces" es gratis, la segunda ya está cargado.
    """
    candidates: list[LocalAnalyzer] = []
    configured_local = getattr(analyzer_registry.analyzer, "_local", analyzer_registry.analyzer)
    if isinstance(configured_local, LocalAnalyzer):
        candidates.append(configured_local)
    toggle_local = analyzer_registry.local_analyzer()
    if toggle_local not in candidates:
        candidates.append(toggle_local)
    if not candidates:
        return

    def _load() -> None:
        for local in candidates:
            try:
                local.nlp("Calentando el modelo.")
                local.sent  # noqa: B018 (la propiedad es la que carga el modelo)
                log.info("analyzer_warmed_up", analyzer=local.name)
            except Exception as exc:
                # Que falle el calentamiento no debe tumbar la API: el primer
                # análisis real volverá a intentarlo y reportará el error a quien
                # lo pidió.
                log.warning("analyzer_warmup_failed", error=str(exc))

    threading.Thread(target=_load, name="odin-warmup", daemon=True).start()
```

Por último, agregar el router a la lista de `app.include_router(...)` (líneas 119-126), después de `app.include_router(aliases.router)`:

```python
app.include_router(settings_router.router)
```

- [ ] **Step 6: Confirmar que pasa**

Run: `pytest tests/api/test_api_settings.py -v`
Expected: PASS (7 tests).

- [ ] **Step 7: Correr toda la suite de backend para descartar regresiones**

Run: `pytest tests/ -v`
Expected: PASS — sin fallas nuevas (comparar contra el estado antes de este plan si algo ya fallaba de antes).

- [ ] **Step 8: Dejar el working tree listo (sin commit)**

---

## Task 8: Cliente API del frontend

**Files:**
- Modify: `frontend/src/lib/odin-api.ts`
- Modify (generado): `frontend/src/lib/api-types.ts`

**Interfaces:**
- Consume: `AnalyzerSettingsResponse`/`AnalyzerSettingsUpdatePayload` (Task 7, vía OpenAPI generado).
- Produce: `getAnalyzerSettings()`, `updateAnalyzerMode(mode)`, tipos `AnalyzerSettings`/`AnalyzerMode` (`frontend/src/lib/odin-api.ts`) — los consume Task 9 (`AnalyzerModeSetting.tsx`).

- [ ] **Step 1: Regenerar los tipos desde el OpenAPI del backend**

Run (desde `frontend/`): `npm run generate:types`
Expected: `src/lib/api-types.ts` se reescribe e incluye `AnalyzerSettingsResponse`/`AnalyzerSettingsUpdatePayload` bajo `components["schemas"]`. Verificar con:

Run: `grep -n "AnalyzerSettingsResponse" frontend/src/lib/api-types.ts`
Expected: al menos una coincidencia.

(Este comando necesita el backend importable — corre `python scripts/generate_openapi.py` internamente sin levantar un servidor, así que no requiere Postgres/`DATABASE_URL` real; si falla por falta de dependencias Python del venv del backend, activarlo primero.)

- [ ] **Step 2: Agregar las funciones del cliente**

En `frontend/src/lib/odin-api.ts`, después de la sección `// ── Entidades canónicas ──...` (después de la línea 373, al final del archivo), agregar:

```ts
// ── Ajustes ─────────────────────────────────────────────────────────────────

export type AnalyzerMode = "cascade" | "local"

export type AnalyzerSettings = components["schemas"]["AnalyzerSettingsResponse"]

export function getAnalyzerSettings(): Promise<AnalyzerSettings> {
  return request<AnalyzerSettings>("/api/settings/analyzer")
}

export function updateAnalyzerMode(mode: AnalyzerMode): Promise<AnalyzerSettings> {
  return putJson("/api/settings/analyzer", { mode })
}
```

- [ ] **Step 3: Verificar que compila**

Run (desde `frontend/`): `npx tsc --noEmit`
Expected: sin errores de tipos.

- [ ] **Step 4: Dejar el working tree listo (sin commit)**

---

## Task 9: Componente `AnalyzerModeSetting`

**Files:**
- Create: `frontend/src/components/AnalyzerModeSetting.tsx`
- Test: `frontend/src/components/AnalyzerModeSetting.test.tsx`

**Interfaces:**
- Consume: `getAnalyzerSettings`/`updateAnalyzerMode`/`AnalyzerMode`/`AnalyzerSettings`/`OdinApiError` (Task 8), `Select` (`frontend/src/components/ui/select.tsx`, ya existe).
- Produce: `AnalyzerModeSetting` (componente, `frontend/src/components/AnalyzerModeSetting.tsx`) — lo consume Task 10 (`SettingsPage.tsx`).

- [ ] **Step 1: Escribir el test que falla**

Crear `frontend/src/components/AnalyzerModeSetting.test.tsx`:

```tsx
import { describe, expect, it, vi, beforeEach } from "vitest"
import { render, screen, waitFor } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { QueryClient, QueryClientProvider } from "@tanstack/react-query"
import { AnalyzerModeSetting } from "@/components/AnalyzerModeSetting"
import * as odinApi from "@/lib/odin-api"

vi.mock("@/lib/odin-api", async () => {
  const actual = await vi.importActual<typeof odinApi>("@/lib/odin-api")
  return {
    ...actual,
    getAnalyzerSettings: vi.fn(),
    updateAnalyzerMode: vi.fn(),
  }
})

const mockedGet = vi.mocked(odinApi.getAnalyzerSettings)
const mockedUpdate = vi.mocked(odinApi.updateAnalyzerMode)

function renderWithProviders() {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return render(
    <QueryClientProvider client={queryClient}>
      <AnalyzerModeSetting />
    </QueryClientProvider>
  )
}

describe("AnalyzerModeSetting", () => {
  beforeEach(() => {
    mockedGet.mockReset()
    mockedUpdate.mockReset()
  })

  it("shows the saved mode once loaded", async () => {
    mockedGet.mockResolvedValue({ mode: "local", default_mode: "cascade" })
    renderWithProviders()

    expect(
      await screen.findByRole("combobox", { name: "Motor de análisis" })
    ).toHaveValue("local")
  })

  it("falls back to default_mode when nothing was saved yet", async () => {
    mockedGet.mockResolvedValue({ mode: null, default_mode: "cascade" })
    renderWithProviders()

    expect(
      await screen.findByRole("combobox", { name: "Motor de análisis" })
    ).toHaveValue("cascade")
  })

  it("saves the new mode when changed", async () => {
    const user = userEvent.setup()
    mockedGet.mockResolvedValue({ mode: "cascade", default_mode: "cascade" })
    mockedUpdate.mockResolvedValue({ mode: "local", default_mode: "cascade" })
    renderWithProviders()

    const select = await screen.findByRole("combobox", { name: "Motor de análisis" })
    await user.selectOptions(select, "local")

    await waitFor(() => expect(mockedUpdate).toHaveBeenCalledWith("local"))
  })

  it("shows an error message when saving fails", async () => {
    const user = userEvent.setup()
    mockedGet.mockResolvedValue({ mode: "cascade", default_mode: "cascade" })
    mockedUpdate.mockRejectedValue(new odinApi.OdinApiError("No se pudo guardar."))
    renderWithProviders()

    const select = await screen.findByRole("combobox", { name: "Motor de análisis" })
    await user.selectOptions(select, "local")

    expect(await screen.findByText("No se pudo guardar.")).toBeInTheDocument()
  })
})
```

- [ ] **Step 2: Confirmar que falla**

Run (desde `frontend/`): `npx vitest run src/components/AnalyzerModeSetting.test.tsx`
Expected: FAIL — no se puede resolver el módulo `@/components/AnalyzerModeSetting`.

- [ ] **Step 3: Implementar el componente**

Crear `frontend/src/components/AnalyzerModeSetting.tsx`:

```tsx
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { Select } from "@/components/ui/select"
import {
  OdinApiError,
  getAnalyzerSettings,
  updateAnalyzerMode,
  type AnalyzerMode,
} from "@/lib/odin-api"

const analyzerSettingsKey = ["settings", "analyzer"] as const

const MODE_LABELS: Record<AnalyzerMode, string> = {
  cascade: "Cascada (Groq → Gemini → Local)",
  local: "Solo Local",
}

export function AnalyzerModeSetting() {
  const queryClient = useQueryClient()
  const { data, isLoading, error } = useQuery({
    queryKey: analyzerSettingsKey,
    queryFn: getAnalyzerSettings,
  })

  const mutation = useMutation({
    mutationFn: (mode: AnalyzerMode) => updateAnalyzerMode(mode),
    onSuccess: (settings) => {
      queryClient.setQueryData(analyzerSettingsKey, settings)
    },
  })

  const selected = data ? data.mode ?? data.default_mode : null

  const errorMessage =
    error instanceof OdinApiError
      ? error.message
      : mutation.error instanceof OdinApiError
        ? mutation.error.message
        : mutation.error
          ? "No se pudo guardar la preferencia."
          : null

  return (
    <div className="flex items-center justify-between gap-4 p-4">
      <div>
        <div className="text-[14px] font-medium">Motor de análisis</div>
        <div className="mt-0.5 text-[12px]" style={{ color: "var(--faint)" }}>
          Qué servicio usa "Analizar URL" para leer cada artículo.
        </div>
        {errorMessage && (
          <div className="mt-1 text-[12px]" style={{ color: "var(--danger, #c0392b)" }}>
            {errorMessage}
          </div>
        )}
      </div>

      <div className="w-[260px]">
        <Select
          aria-label="Motor de análisis"
          disabled={isLoading || mutation.isPending}
          value={selected ?? ""}
          onChange={(e) => mutation.mutate(e.target.value as AnalyzerMode)}
        >
          {!selected && (
            <option value="" disabled>
              Cargando…
            </option>
          )}
          <option value="cascade">{MODE_LABELS.cascade}</option>
          <option value="local">{MODE_LABELS.local}</option>
        </Select>
      </div>
    </div>
  )
}
```

- [ ] **Step 4: Confirmar que pasa**

Run (desde `frontend/`): `npx vitest run src/components/AnalyzerModeSetting.test.tsx`
Expected: PASS (4 tests).

- [ ] **Step 5: Dejar el working tree listo (sin commit)**

---

## Task 10: Conectar la pestaña Ajustes

**Files:**
- Modify: `frontend/src/pages/SettingsPage.tsx`

**Interfaces:**
- Consume: `AnalyzerModeSetting` (Task 9).

- [ ] **Step 1: Agregar la fila a la tarjeta existente**

`SettingsPage.tsx` ya documenta que el layout de fila está pensado para crecer sin rediseñar la tarjeta (docstring, línea 6-8): agregar `AnalyzerModeSetting` como una segunda fila de la MISMA tarjeta, no una tarjeta nueva. Reemplazar el archivo completo por:

```tsx
import { useOutletContext } from "react-router-dom"
import { AnalyzerModeSetting } from "@/components/AnalyzerModeSetting"
import { SkyToggle } from "@/components/ui/sky-toggle"
import type { WorkspaceOutletContext } from "@/components/Layout"

/**
 * Ajustes del workspace: tema y motor de análisis. El layout de fila
 * (etiqueta + control a la derecha) está pensado para crecer con más filas de
 * preferencias sin rediseñar la tarjeta.
 */
export function SettingsPage() {
  const { theme, onToggleTheme } = useOutletContext<WorkspaceOutletContext>()

  return (
    <div>
      <header>
        <h1 className="text-[19px] font-semibold">Ajustes</h1>
        <p className="mt-0.5 text-[12.5px]" style={{ color: "var(--faint)" }}>
          Preferencias de la interfaz.
        </p>
      </header>

      <div className="odin-glass mt-4 rounded-xl border" style={{ boxShadow: "var(--shadow)" }}>
        <div className="flex items-center justify-between gap-4 p-4">
          <div>
            <div className="text-[14px] font-medium">Tema</div>
            <div className="mt-0.5 text-[12px]" style={{ color: "var(--faint)" }}>
              Apariencia clara u oscura de la aplicación.
            </div>
          </div>

          <SkyToggle
            checked={theme === "dark"}
            onChange={onToggleTheme}
            aria-label={theme === "dark" ? "Cambiar a tema claro" : "Cambiar a tema oscuro"}
          />
        </div>

        <div className="border-t" style={{ borderColor: "var(--border)" }}>
          <AnalyzerModeSetting />
        </div>
      </div>
    </div>
  )
}
```

- [ ] **Step 2: Verificar que compila**

Run (desde `frontend/`): `npx tsc --noEmit`
Expected: sin errores de tipos.

- [ ] **Step 3: Verificación manual en el navegador**

Run: levantar el backend (`uvicorn odin.api:app --reload --port 8000`) y el frontend (`npm run dev` en `frontend/`), iniciar sesión, ir a la pestaña "Ajustes".

Expected:
- Se ve una segunda fila "Motor de análisis" debajo de "Tema", separada por una línea.
- El selector muestra "Cascada (Groq → Gemini → Local)" o "Solo Local" ya cargado (no "Cargando…" indefinidamente).
- Cambiar la selección persiste: recargar la página muestra la última opción guardada.
- Ir a "Analizar URL" y analizar cualquier link permitido (ver `ODIN_ALLOWED_DOMAINS`) con "Solo Local" seleccionado: el resultado se guarda con `analyzer_name="local"` (visible en el detalle del artículo, si el frontend lo muestra) y NO dispara ninguna llamada de red a Groq/Gemini (confirmar en la pestaña Network del navegador o en los logs del backend — no debe verse `groq.com`/`generativelanguage.googleapis.com`).
- **No** cambiar a "Cascada" y analizar una URL real salvo que el usuario lo pida explícitamente — esa ruta sí puede facturar una llamada real a Groq/Gemini (ver `CLAUDE.md`).

- [ ] **Step 4: Correr toda la suite de frontend para descartar regresiones**

Run (desde `frontend/`): `npx vitest run`
Expected: PASS — sin fallas nuevas.

- [ ] **Step 5: Dejar el working tree listo (sin commit)**
