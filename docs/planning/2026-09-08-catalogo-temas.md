# Catálogo administrable de temas + clasificación al ingresar — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Dar a Odin un catálogo de temas administrable (CRUD) contra el cual cada análisis (LocalAnalyzer o LLM) resuelve a qué tema(s) pertenece un reporte al ingresarlo, dejando en una cola "sin clasificar" lo que no mapee para revisión humana.

**Architecture:** Tres tablas nuevas calcadas del triángulo ya probado `localities` + `locality_aliases` + `article_localities`: `topics` (jerárquico en una sola tabla con `parent_id`/`path`), `topic_aliases` (términos alternos → tema) y `article_topics` (N:M artículo↔tema con `origin` AUTO/MANUAL, `score`, `evidence`). Un clasificador **puro por reglas** (`topic_classifier.py`, sin LLM, sin sesión) compila una regex de alternación sobre nombres + alias del catálogo y corre en los tres puntos donde un análisis se vuelve filas: vista previa de `/api/analyze` (como sugerencia), guardado manual y rastreo masivo. `Article.main_topic` (texto libre del analizador) no se toca: el catálogo es una capa nueva encima y `main_topic` es una señal de entrada más para el clasificador.

**Tech Stack:** Python 3.13, FastAPI, SQLAlchemy 2 + Alembic, Pydantic v2, pytest. Sin dependencias nuevas. Sin spaCy/LLM en el clasificador.

**Spec:** `docs/planning/2026-08-21-requerimientos-cliente-gap.md` §2 (R4, R5, R6, R7) y §F1 ("Temas y subtemas"). Este plan implementa una **primera versión experimental** de R4 + R5 + R7, con `parent_id` en el modelo para no cerrarle la puerta a R6 (subtemas) pero sin UI/lógica específica de subtemas todavía.

## Global Constraints

- **Sin commits.** `CLAUDE.md`: el usuario commitea manualmente. Cada tarea termina dejando el cambio **en el working tree**, nunca con `git commit`. Donde este plan dice "deja el cambio listo", significa: archivos guardados, tests en verde, nada commiteado.
- **Branch:** trabajar sobre `dev` (`CLAUDE.md`). No crear worktree salvo que el usuario lo pida.
- **Nunca llamar a la API de Gemini** en tests ni verificación (`CLAUDE.md`, costo). El clasificador es local; los tests usan `LocalAnalyzer` o stubs.
- **Compatibilidad de motores:** el SQL nuevo debe funcionar en PostgreSQL, SQLite y SQL Server. Nada de CTE recursivo: la jerarquía se consulta por prefijo de `path` con `LIKE`, igual que `localities`.
- **`ANALYSIS_SCHEMA_VERSION` no se toca** (`src/odin/analysis/base.py:17`): los temas son dimensión de BD, no salida del `AnalysisResult`.
- **`norm_key`** para toda clave de comparación: `from odin.analysis.text_norm import norm_key` (sin acentos, minúsculas, espacios colapsados, guiones→espacio, puntos fuera).
- **Umbral de clasificación por defecto:** `TOPIC_MIN_SCORE = 0.5`. Matches por debajo no se persisten como AUTO.
- **Frontend fuera de alcance.** Este plan es backend + API. Ver "Follow-up".

---

## Registro de implementación

**El último paso de CADA tarea** (después de "dejar el cambio en el working
tree") es volver aquí, marcar `[x]` la fila y escribir **fecha y hora local** de
cuando quedó (tests en verde). Zona: República Dominicana (UTC-4). Formato:
`2026-09-08 · 15:40`.

| # | Tarea | Estado | Implementada (fecha · hora) |
|---|-------|--------|------------------------------|
| 1 | Modelo de datos + migración | [x] | 2026-09-08 · 16:14 |
| 2 | Store del catálogo + semilla | [x] | 2026-09-08 · 16:18 |
| 3 | Clasificador puro | [x] | 2026-09-08 · 16:23 |
| 4 | Schemas de la API | [x] | 2026-09-08 · 16:41 |
| 5 | Servicio + router CRUD de temas | [x] | 2026-09-08 · 16:59 |
| 6 | Sugerencias de tema en la vista previa | [~] | 2026-09-08 · 17:05 — código + test propio en verde; BLOQUEADO por regresión (ver abajo) |
| 7 | Persistir `article_topics` al guardar (manual) | [~] | 2026-09-08 · 17:05 — código + tests propios en verde; BLOQUEADO por regresión |
| 8 | Clasificación en el rastreo masivo (`pipeline._persist`) | [~] | 2026-09-08 · 17:05 — código + test propio en verde; BLOQUEADO por regresión |
| 9 | Filtro por tema del catálogo + faceta | [ ] | — (faceta ya hecha en Task 4) |
| 10 | Backfill de `main_topic` → `article_topics` | [ ] | — |
| 11 | Documentación | [ ] | — |

**Verificación end-to-end** (sección final): [ ] — corrida completa · —

> **BLOQUEO (Tasks 6–8) — 2026-09-08.** `analyze_service.run_analyze_job`,
> `article_service.save_article` y `pipeline._persist` llaman `get_catalog()` sin
> guardia. Con la caché de proceso fría eso va a `odin.db.session.get_session()`
> (Postgres real): en tests que no cablean `topic_store` (p. ej.
> `tests/api/test_api_save_with_localities.py`, `test_api_article_authorship.py`,
> `tests/core/test_pipeline.py`) el guardado tarda ~12 s y devuelve 500 — 13+
> tests existentes en rojo. La corrida "verde" previa de `tests/api tests/services`
> pasó por suerte de orden (otro test calentaba la caché primero). En prod, un
> bache de la BD durante un rastreo pararía cada artículo ~12 s.
>
> **Fix pendiente (recomendado):** (1) `get_catalog()`/`resolve()` con
> try/except → `[]`/`None` y log, igual que `db/aliases.py::all_canonicals`;
> (2) `conftest.py`: parchear `odin.db.session.get_session` en `api_client`/
> `db_session` y limpiar la caché de temas en el fixture autouse
> `_clear_process_caches`. No toca la API de Tasks 2/3. Código de Tasks 6–8
> queda en el working tree sin revertir.

---

## File Structure

**Nuevos:**
- `src/odin/db/models.py` — (modificado) 3 modelos: `Topic`, `TopicAlias`, `ArticleTopic` + relación `Article.topics` + tuplas de constantes `ARTICLE_TOPIC_ORIGINS`.
- `src/odin/db/topics.py` — store del catálogo: caché en memoria, `resolve()`, `get_catalog()`, `invalidate_cache()`, `load_seed()`. Molde: `src/odin/db/aliases.py`.
- `src/odin/db/seed_topics.py` — `SEED_TOPICS`: lista semilla (placeholder documentado hasta que el cliente entregue la suya). Molde: `src/odin/db/seed_aliases.py`.
- `src/odin/analysis/topic_classifier.py` — clasificador puro: `build_matcher()`, `classify()`, `TopicMatch`, caché de matcher + `invalidate_matcher()`. Molde conceptual: `src/odin/analysis/politics_filter.py`.
- `src/odin/services/topic_service.py` — lógica de negocio CRUD + frecuencia + cola + vínculos. Molde: `src/odin/services/locality_service.py`.
- `src/odin/api/routers/topics.py` — endpoints HTTP finos. Molde: `src/odin/api/routers/localities.py`.
- `scripts/backfill_article_topics.py` — backfill de `Article.main_topic` → `article_topics`. Molde: `scripts/merge_duplicate_entities.py`.
- `alembic/versions/<rev>_topics_catalogo_de_temas.py` — crea las 3 tablas. Molde: `alembic/versions/a7c3e5f01b92_localities_catalogo_geografico_y_vinculo.py`. `down_revision = 'e5b2c81d3f47'` (head actual).
- Tests: `tests/db/test_topics_store.py`, `tests/analysis/test_topic_classifier.py`, `tests/api/test_api_topics.py`, `tests/api/test_api_topics_wiring.py`.

**Modificados:**
- `src/odin/api/schemas.py` — schemas de tema + `topic_ids` en `SaveArticleRequest` + `suggested_topics` en `AnalyzeResult` + temas en `ArticleFiltersResponse`.
- `src/odin/api/__init__.py` — `include_router(topics.router)` + `topic_store.load_seed()` en `_lifespan`.
- `src/odin/services/analyze_service.py` — `suggested_topics` en la vista previa.
- `src/odin/services/article_service.py` — `save_article` inserta `article_topics`; `list_articles` acepta `topic_id`; faceta de filtros devuelve el catálogo.
- `src/odin/api/routers/articles.py` — parámetro `topic_id` en `list_articles`.
- `src/odin/core/pipeline.py` — `_persist` inserta `article_topics` con un matcher construido una vez por corrida.
- `docs/DATA_DICTIONARY.md` — documentar las 3 tablas.

---

## Task 1: Modelo de datos + migración

**Files:**
- Modify: `src/odin/db/models.py` (añadir tras `ArticleLocality`, ~línea 603; y `Article.topics` en la clase `Article`, ~línea 143)
- Create: `alembic/versions/2f9a1c7b4e10_topics_catalogo_de_temas.py`
- Test: `tests/db/test_topics_store.py` (solo la parte de modelo en esta tarea)

**Interfaces:**
- Produces:
  - `Topic(id, name, norm_key, slug, description, parent_id, path, is_active, display_order, created_at, updated_at)`; rel. `parent`/`children`/`aliases`.
  - `TopicAlias(id, topic_id, alias, alias_key, is_active)`.
  - `ArticleTopic(id, article_id, topic_id, score, origin, evidence, created_at)`; rel. `article`/`topic`.
  - `Article.topics: list[ArticleTopic]` (`cascade="all, delete-orphan"`).
  - `ARTICLE_TOPIC_ORIGINS = ("AUTO", "MANUAL")`.

- [ ] **Step 1: Escribir el test que falla**

```python
# tests/db/test_topics_store.py
from __future__ import annotations

from odin.db.models import Article, ArticleTopic, Topic, TopicAlias


def test_topic_hierarchy_and_unique_sibling(sqlite_sessionmaker):
    s = sqlite_sessionmaker()
    agua = Topic(name="Agua", norm_key="agua", slug="agua", path="")
    s.add(agua)
    s.flush()
    agua.path = f"/{agua.id}/"
    infra = Topic(name="Infraestructura", norm_key="infraestructura", slug="infra",
                  parent_id=agua.id, path=f"/{agua.id}/")
    s.add(infra)
    s.flush()
    infra.path = f"/{agua.id}/{infra.id}/"
    s.commit()
    assert [c.name for c in agua.children] == ["Infraestructura"]


def test_article_topics_cascade_delete(sqlite_sessionmaker):
    s = sqlite_sessionmaker()
    t = Topic(name="Energía", norm_key="energia", slug="energia", path="/1/")
    a = Article(source="diario_libre", url="https://x/1", title="t", body="b")
    s.add_all([t, a])
    s.flush()
    s.add(ArticleTopic(article_id=a.id, topic_id=t.id, score=0.9, origin="AUTO",
                       evidence="agua potable"))
    s.commit()
    s.delete(a)
    s.commit()
    assert s.query(ArticleTopic).count() == 0
```

- [ ] **Step 2: Correr el test y verlo fallar**

Run: `python -m pytest tests/db/test_topics_store.py -q`
Expected: FAIL con `ImportError: cannot import name 'Topic'`.

- [ ] **Step 3: Añadir los modelos**

En `src/odin/db/models.py`, tras la clase `ArticleLocality`:

```python
ARTICLE_TOPIC_ORIGINS = ("AUTO", "MANUAL")


class Topic(Base):
    """Un nodo del catálogo de temas. Jerárquico en UNA tabla (tema → subtema)
    con `parent_id` a sí misma y `path` materializado ("/1/4/"), igual que
    `Locality`: la consulta caliente es "todo lo que cuelga del tema Agua" y con
    `path` es un `LIKE '/1/%'` indexable, sin CTE recursivo (que no se escribe
    igual en Postgres, SQLite y SQL Server).

    El catálogo lo entrega el cliente y se administra desde la UI: por eso es una
    tabla con baja lógica (`is_active`) y no una constante en el código.
    """

    __tablename__ = "topics"
    __table_args__ = (
        UniqueConstraint("parent_id", "norm_key", name="uq_topic_sibling_name"),
        Index("ix_topics_path", "path"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(160), index=True)
    norm_key: Mapped[str] = mapped_column(String(160), index=True)
    slug: Mapped[str] = mapped_column(String(160))
    description: Mapped[str | None] = mapped_column(String(500))
    parent_id: Mapped[int | None] = mapped_column(
        ForeignKey("topics.id", ondelete="CASCADE"), index=True
    )
    path: Mapped[str] = mapped_column(String(255), default="")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    display_order: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, onupdate=_utcnow
    )

    parent: Mapped[Topic | None] = relationship(back_populates="children", remote_side=[id])
    children: Mapped[list[Topic]] = relationship(
        back_populates="parent", cascade="all, delete-orphan"
    )
    aliases: Mapped[list[TopicAlias]] = relationship(
        back_populates="topic", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:  # pragma: no cover
        return f"<Topic {self.name}>"


class TopicAlias(Base):
    """Otro término por el que la prensa nombra un tema: "acueducto",
    "suministro de agua", "escasez de agua" → tema *Agua*. Es lo que le da al
    cliente control directo sobre qué cuenta como cada tema, sin tocar código."""

    __tablename__ = "topic_aliases"
    __table_args__ = (
        UniqueConstraint("topic_id", "alias_key", name="uq_topic_alias"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    topic_id: Mapped[int] = mapped_column(
        ForeignKey("topics.id", ondelete="CASCADE"), index=True
    )
    alias: Mapped[str] = mapped_column(String(160))
    alias_key: Mapped[str] = mapped_column(String(160), index=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    topic: Mapped[Topic] = relationship(back_populates="aliases")


class ArticleTopic(Base):
    """Vínculo N:M artículo↔tema. N:M y no una columna en `articles` porque una
    nota participa de varios temas (el acueducto es agua + infraestructura).

    `origin`: AUTO lo propuso el clasificador; MANUAL lo puso/confirmó un
    documentalista. `score` es la confianza del match automático (NULL cuando es
    MANUAL: un dato humano tiene autoría, no confianza estimada). `evidence` es
    el término del catálogo que disparó el match, para poder explicar un match
    raro."""

    __tablename__ = "article_topics"
    __table_args__ = (
        UniqueConstraint("article_id", "topic_id", name="uq_article_topic"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    article_id: Mapped[int] = mapped_column(
        ForeignKey("articles.id", ondelete="CASCADE"), index=True
    )
    topic_id: Mapped[int] = mapped_column(
        ForeignKey("topics.id", ondelete="CASCADE"), index=True
    )
    score: Mapped[float | None] = mapped_column(Float)
    origin: Mapped[str] = mapped_column(String(20), default="AUTO")
    evidence: Mapped[str | None] = mapped_column(String(200))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)

    article: Mapped[Article] = relationship(back_populates="topics")
    topic: Mapped[Topic] = relationship()
```

En la clase `Article`, junto a `localities` (~línea 143):

```python
    topics: Mapped[list[ArticleTopic]] = relationship(
        back_populates="article",
        cascade="all, delete-orphan",
    )
```

- [ ] **Step 4: Crear la migración**

`alembic/versions/2f9a1c7b4e10_topics_catalogo_de_temas.py` — copiar la estructura de `a7c3e5f01b92_...localities...py`, con:

```python
revision = "2f9a1c7b4e10"
down_revision = "e5b2c81d3f47"
```

`upgrade()` crea `topics`, `topic_aliases`, `article_topics` con las mismas columnas/índices/constraints que los modelos de arriba (`server_default=sa.true()` para `is_active`, `server_default="0"` para `display_order`, `server_default=""` para `path`). `downgrade()` hace `op.drop_table` de las tres en orden inverso. NO siembra nada (igual que la de localities): la semilla la carga `db.topics.load_seed()` en el arranque.

- [ ] **Step 5: Aplicar y verificar la migración en SQLite**

Run: `python -m alembic upgrade head && python -m alembic downgrade -1 && python -m alembic upgrade head`
Expected: sin errores; `alembic heads` muestra `2f9a1c7b4e10 (head)`.

- [ ] **Step 6: Correr los tests**

Run: `python -m pytest tests/db/test_topics_store.py -q`
Expected: PASS.

- [ ] **Step 7: Dejar el cambio en el working tree** (sin commit — `CLAUDE.md`).

---

## Task 2: Store del catálogo + semilla

**Files:**
- Create: `src/odin/db/topics.py`
- Create: `src/odin/db/seed_topics.py`
- Modify: `src/odin/api/__init__.py` (`_lifespan`, tras `alias_store.load_seed()`)
- Test: `tests/db/test_topics_store.py` (añadir casos)

**Interfaces:**
- Consumes: `Topic`, `TopicAlias` (Task 1); `norm_key` (`odin.analysis.text_norm`).
- Produces:
  - `odin.db.topics.get_catalog() -> list[CatalogTopic]` donde `CatalogTopic` es un `dataclass(frozen=True)` con `id: int, name: str, norm_key: str, parent_id: int | None, path: str, aliases: tuple[str, ...]` (aliases ya normalizados con `norm_key`).
  - `odin.db.topics.resolve(text: str) -> int | None` — id del tema si `norm_key(text)` coincide exactamente con el `norm_key` de un tema activo o de un alias activo.
  - `odin.db.topics.invalidate_cache() -> None` — descarta la caché y llama a `topic_classifier.invalidate_matcher()`.
  - `odin.db.topics.load_seed() -> int` — inserta temas/alias de `SEED_TOPICS` que no existan (idempotente, insert-only); devuelve nº de temas insertados; llama `invalidate_cache()`.

- [ ] **Step 1: Escribir los tests que fallan**

```python
# añadir a tests/db/test_topics_store.py
from odin.db import topics as topic_store


def test_load_seed_idempotent_and_resolve(sqlite_sessionmaker):
    n1 = topic_store.load_seed()
    n2 = topic_store.load_seed()
    assert n1 > 0 and n2 == 0
    # por nombre y por alias, sin acentos ni mayúsculas
    agua_id = topic_store.resolve("Agua")
    assert agua_id is not None
    assert topic_store.resolve("ACUEDUCTO") == agua_id
    assert topic_store.resolve("no-existe-este-tema") is None


def test_get_catalog_shape(sqlite_sessionmaker):
    topic_store.load_seed()
    cat = topic_store.get_catalog()
    agua = next(t for t in cat if t.norm_key == "agua")
    assert "acueducto" in agua.aliases
    assert agua.path.endswith(f"/{agua.id}/")
```

(`conftest.py` ya aísla cada test con SQLite en memoria vía `sqlite_sessionmaker`/`api_client`; `load_seed()` usa `get_session()`, que en tests apunta a esa BD.)

- [ ] **Step 2: Correr y ver fallar**

Run: `python -m pytest tests/db/test_topics_store.py -q`
Expected: FAIL con `ModuleNotFoundError: odin.db.topics`.

- [ ] **Step 3: Escribir `src/odin/db/seed_topics.py`**

```python
"""Catálogo semilla de temas.

PLACEHOLDER: esta lista es un punto de partida plausible para prensa
dominicana. Reemplazar `SEED_TOPICS` por la lista real que entregue el cliente
antes de poner esto en producción. `load_seed()` es insert-only, así que
agregar entradas aquí y reiniciar la API las suma sin tocar las existentes;
quitar una de aquí NO la borra de la BD (eso es baja lógica desde la UI).

Formato: (name, slug, parent_slug|None, [aliases...]).
"""
from __future__ import annotations

SEED_TOPICS: list[tuple[str, str, str | None, list[str]]] = [
    ("Agua", "agua", None,
     ["agua potable", "acueducto", "suministro de agua", "escasez de agua",
      "INAPA", "CAASD", "corte de agua"]),
    ("Energía eléctrica", "energia-electrica", None,
     ["apagón", "apagones", "EDESUR", "EDENORTE", "EDEESTE", "factura eléctrica",
      "tarifa eléctrica", "servicio eléctrico"]),
    ("Seguridad ciudadana", "seguridad-ciudadana", None,
     ["delincuencia", "criminalidad", "Policía Nacional", "atraco", "homicidio",
      "inseguridad"]),
    ("Salud", "salud", None,
     ["hospital", "SNS", "Salud Pública", "dengue", "servicios de salud",
      "Ministerio de Salud"]),
    ("Educación", "educacion", None,
     ["MINERD", "escuela", "tanda extendida", "maestros", "ADP", "año escolar"]),
    ("Transporte", "transporte", None,
     ["OMSA", "INTRANT", "metro", "teleférico", "peaje", "transporte público"]),
    ("Corrupción", "corrupcion", None,
     ["PEPCA", "soborno", "lavado de activos", "Punta Catalina", "Odebrecht",
      "malversación"]),
]
```

- [ ] **Step 4: Escribir `src/odin/db/topics.py`**

Copiar la forma de `src/odin/db/aliases.py` (caché con `threading.Lock`, `_cache = None` = no cargado, `_build_cache`, `_get_cache`, `invalidate_cache`, `load_seed`). Diferencias:

```python
"""Store del catálogo de temas: caché en memoria + carga de la semilla.

Mismo diseño que `db/aliases.py`: la caché se llena en el primer `resolve()`/
`get_catalog()` y se descarta con `invalidate_cache()` desde los endpoints CRUD.
"""
from __future__ import annotations

import threading
from dataclasses import dataclass

from sqlalchemy import select

from odin.analysis.text_norm import norm_key
from odin.db.models import Topic, TopicAlias
from odin.db.session import get_session, init_db


@dataclass(frozen=True)
class CatalogTopic:
    id: int
    name: str
    norm_key: str
    parent_id: int | None
    path: str
    aliases: tuple[str, ...]  # ya normalizados con norm_key


_lock = threading.Lock()
_catalog: list[CatalogTopic] | None = None
_by_key: dict[str, int] | None = None  # norm_key (nombre o alias) -> topic_id


def _build() -> tuple[list[CatalogTopic], dict[str, int]]:
    session = get_session()
    try:
        topics = session.scalars(select(Topic).where(Topic.is_active.is_(True))).all()
        aliases = session.scalars(
            select(TopicAlias).where(TopicAlias.is_active.is_(True))
        ).all()
        by_topic_aliases: dict[int, list[str]] = {}
        key_map: dict[str, int] = {}
        for a in aliases:
            k = norm_key(a.alias)
            if not k:
                continue
            by_topic_aliases.setdefault(a.topic_id, []).append(k)
            key_map.setdefault(k, a.topic_id)
        catalog: list[CatalogTopic] = []
        for t in topics:
            k = norm_key(t.name)
            key_map.setdefault(k, t.id)
            catalog.append(CatalogTopic(
                id=t.id, name=t.name, norm_key=k, parent_id=t.parent_id,
                path=t.path, aliases=tuple(sorted(set(by_topic_aliases.get(t.id, [])))),
            ))
        return catalog, key_map
    finally:
        session.close()


def _load_cache() -> tuple[list[CatalogTopic], dict[str, int]]:
    global _catalog, _by_key
    with _lock:
        if _catalog is None or _by_key is None:
            _catalog, _by_key = _build()
        return _catalog, _by_key


def get_catalog() -> list[CatalogTopic]:
    return list(_load_cache()[0])


def resolve(text: str) -> int | None:
    key = norm_key(text)
    if not key:
        return None
    return _load_cache()[1].get(key)


def invalidate_cache() -> None:
    global _catalog, _by_key
    with _lock:
        _catalog = None
        _by_key = None
    # Import local para evitar ciclo (topic_classifier importa este módulo).
    from odin.analysis.topic_classifier import invalidate_matcher
    invalidate_matcher()


def load_seed() -> int:
    from odin.db.seed_topics import SEED_TOPICS

    init_db()
    session = get_session()
    inserted = 0
    try:
        existing_slugs = set(session.scalars(select(Topic.slug)).all())
        slug_to_id: dict[str, int] = {
            s: i for i, s in session.execute(select(Topic.id, Topic.slug)).all()
        }
        # 1ª pasada: temas raíz y luego hijos (la semilla lista los padres antes).
        for name, slug, parent_slug, _aliases in SEED_TOPICS:
            if slug in existing_slugs:
                continue
            parent_id = slug_to_id.get(parent_slug) if parent_slug else None
            row = Topic(
                name=name.strip(), norm_key=norm_key(name), slug=slug,
                parent_id=parent_id, path="",
            )
            session.add(row)
            session.flush()
            parent_path = "/"
            if parent_id is not None:
                parent_path = session.get(Topic, parent_id).path
            row.path = f"{parent_path}{row.id}/"
            slug_to_id[slug] = row.id
            existing_slugs.add(slug)
            inserted += 1
        # 2ª pasada: alias (todos los temas ya tienen id).
        existing_alias_keys = {
            (tid, k) for tid, k in session.execute(
                select(TopicAlias.topic_id, TopicAlias.alias_key)
            ).all()
        }
        for name, slug, _parent, aliases in SEED_TOPICS:
            tid = slug_to_id.get(slug)
            if tid is None:
                continue
            for alias in aliases:
                k = norm_key(alias)
                if not k or (tid, k) in existing_alias_keys:
                    continue
                session.add(TopicAlias(topic_id=tid, alias=alias.strip(), alias_key=k))
                existing_alias_keys.add((tid, k))
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
    invalidate_cache()
    return inserted
```

- [ ] **Step 5: Enganchar `load_seed()` en el arranque**

En `src/odin/api/__init__.py`, dentro de `_lifespan`, tras el bloque `alias_store.load_seed()` (~línea 108), en su propio `try` (como el de localities):

```python
    try:
        from odin.db import topics as topic_store
        k = topic_store.load_seed()
        if k:
            log.info("seed_topics_loaded", topics=k)
    except Exception:
        log.exception("seed_topics_failed")
```

- [ ] **Step 6: Correr los tests**

Run: `python -m pytest tests/db/test_topics_store.py -q`
Expected: PASS (los 4 tests).

- [ ] **Step 7: Dejar el cambio en el working tree.**

---

## Task 3: Clasificador puro

**Files:**
- Create: `src/odin/analysis/topic_classifier.py`
- Test: `tests/analysis/test_topic_classifier.py`

**Interfaces:**
- Consumes: `odin.db.topics.get_catalog()` / `CatalogTopic` (Task 2); `strip_accents` (`odin.analysis.text_norm`).
- Produces:
  - `TopicMatch = dataclass(topic_id: int, score: float, evidence: str)`.
  - `classify(title: str, body: str, keywords: str | None, main_topic: str | None, *, min_score: float = TOPIC_MIN_SCORE) -> list[TopicMatch]` — usa el matcher cacheado; roll-up al padre incluido; ordenado por score desc; sin duplicar topic_id.
  - `invalidate_matcher() -> None`.
  - `TOPIC_MIN_SCORE = 0.5`.

- [ ] **Step 1: Escribir el test que falla**

```python
# tests/analysis/test_topic_classifier.py
from __future__ import annotations

from odin.db import topics as topic_store
from odin.analysis import topic_classifier as tc


def _ids(matches):
    return {m.topic_id for m in matches}


def test_title_hit_scores_high(sqlite_sessionmaker):
    topic_store.load_seed()
    agua = topic_store.resolve("Agua")
    m = tc.classify(title="Protestan por la escasez de agua en Villa Altagracia",
                    body="Vecinos reclaman.", keywords=None, main_topic=None)
    assert agua in _ids(m)
    assert max(x.score for x in m if x.topic_id == agua) >= 0.85


def test_single_body_mention_below_threshold(sqlite_sessionmaker):
    topic_store.load_seed()
    agua = topic_store.resolve("Agua")
    m = tc.classify(title="Inauguran parque infantil",
                    body="Al acto asistió el director del acueducto local.",
                    keywords=None, main_topic=None)
    assert agua not in _ids(m)


def test_two_distinct_body_terms_match(sqlite_sessionmaker):
    topic_store.load_seed()
    energia = topic_store.resolve("Energía eléctrica")
    m = tc.classify(
        title="Comunidad en reclamo",
        body="El apagón lleva ocho horas. EDESUR no responde por la avería.",
        keywords=None, main_topic=None,
    )
    assert energia in _ids(m)


def test_main_topic_is_a_signal(sqlite_sessionmaker):
    topic_store.load_seed()
    salud = topic_store.resolve("Salud")
    m = tc.classify(title="Nota", body="Cuerpo sin señales.",
                    keywords="hospital, dengue", main_topic="servicios de salud")
    assert salud in _ids(m)
```

- [ ] **Step 2: Correr y ver fallar**

Run: `python -m pytest tests/analysis/test_topic_classifier.py -q`
Expected: FAIL con `ModuleNotFoundError: odin.analysis.topic_classifier`.

- [ ] **Step 3: Implementar el clasificador**

```python
"""Clasificador de temas por reglas sobre el catálogo. Puro: no toca la BD
(recibe el catálogo ya cargado vía `db.topics.get_catalog()`), no llama a ningún
LLM. Le da al cliente control directo — lo que cuenta como cada tema son los
nombres y alias que él administra.

Diseño calcado de `analysis/politics_filter.py`: una sola regex de alternación
compilada sobre los términos del catálogo, coincidencia por palabra completa
sobre texto sin acentos y en minúsculas. "Señal fuerte primero": un término en
el título / `main_topic` / `topic_keywords` pesa más que en el cuerpo.
"""
from __future__ import annotations

import re
import threading
from dataclasses import dataclass

from odin.analysis.text_norm import strip_accents

TOPIC_MIN_SCORE = 0.5

_TITLE_SCORE = 0.9
_BODY_MULTI_SCORE = 0.6
_BODY_SINGLE_SCORE = 0.35


@dataclass(frozen=True)
class TopicMatch:
    topic_id: int
    score: float
    evidence: str


class _Matcher:
    def __init__(self, pattern: re.Pattern[str], term_to_topic: dict[str, int],
                 parent_of: dict[int, int | None]):
        self.pattern = pattern
        self.term_to_topic = term_to_topic
        self.parent_of = parent_of


_lock = threading.Lock()
_matcher: _Matcher | None = None


def invalidate_matcher() -> None:
    global _matcher
    with _lock:
        _matcher = None


def build_matcher(catalog) -> _Matcher:
    term_to_topic: dict[str, int] = {}
    parent_of: dict[int, int | None] = {}
    for t in catalog:
        parent_of[t.id] = t.parent_id
        for term in (t.norm_key, *t.aliases):
            term = strip_accents(term).lower().strip()
            if term:
                term_to_topic.setdefault(term, t.id)
    if not term_to_topic:
        return _Matcher(re.compile(r"(?!x)x"), {}, parent_of)  # nunca matchea
    alternation = "|".join(
        re.escape(term) for term in sorted(term_to_topic, key=len, reverse=True)
    )
    pattern = re.compile(rf"\b(?:{alternation})\b")
    return _Matcher(pattern, term_to_topic, parent_of)


def _get_matcher() -> _Matcher:
    global _matcher
    with _lock:
        if _matcher is None:
            from odin.db.topics import get_catalog
            _matcher = build_matcher(get_catalog())
        return _matcher


def _hits(text: str, m: _Matcher) -> dict[int, set[str]]:
    """topic_id -> conjunto de términos distintos encontrados en `text`."""
    found: dict[int, set[str]] = {}
    for term in m.pattern.findall(strip_accents(text or "").lower()):
        tid = m.term_to_topic.get(term)
        if tid is not None:
            found.setdefault(tid, set()).add(term)
    return found


def classify(title: str, body: str, keywords: str | None, main_topic: str | None,
             *, min_score: float = TOPIC_MIN_SCORE) -> list[TopicMatch]:
    m = _get_matcher()
    strong_text = " . ".join(x for x in (title, main_topic, keywords) if x)
    strong = _hits(strong_text, m)
    weak = _hits(body, m)

    scored: dict[int, tuple[float, str]] = {}
    for tid, terms in strong.items():
        scored[tid] = (_TITLE_SCORE, sorted(terms)[0])
    for tid, terms in weak.items():
        if tid in scored:
            continue
        score = _BODY_MULTI_SCORE if len(terms) >= 2 else _BODY_SINGLE_SCORE
        scored[tid] = (score, sorted(terms)[0])

    # Roll-up: si matchea un subtema, el padre hereda el mismo score.
    for tid, (score, ev) in list(scored.items()):
        parent = m.parent_of.get(tid)
        if parent is not None and parent not in scored:
            scored[parent] = (score, ev)

    out = [
        TopicMatch(topic_id=tid, score=score, evidence=ev)
        for tid, (score, ev) in scored.items()
        if score >= min_score
    ]
    out.sort(key=lambda x: x.score, reverse=True)
    return out
```

- [ ] **Step 4: Correr los tests**

Run: `python -m pytest tests/analysis/test_topic_classifier.py -q`
Expected: PASS (4 tests).

- [ ] **Step 5: Dejar el cambio en el working tree.**

---

## Task 4: Schemas de la API

**Files:**
- Modify: `src/odin/api/schemas.py`
- Test: cubierto por Task 5 (`tests/api/test_api_topics.py`)

**Interfaces:**
- Produces: `TopicResponse`, `TopicNode`, `TopicPayload`, `TopicUpdatePayload`, `TopicAliasPayload`, `TopicAliasResponse`, `SuggestedTopic`, `ArticleTopicResponse`, `ArticleTopicPayload`, `TopicFrequencyRow`; `SaveArticleRequest.topic_ids: list[int]`; `AnalyzeResult.suggested_topics: list[SuggestedTopic]`; `ArticleFiltersResponse.topics: list[TopicResponse]`.

- [ ] **Step 1: Añadir los schemas** (junto a los de localidades, ~línea 610)

```python
ARTICLE_TOPIC_ORIGIN_VALUES = ("AUTO", "MANUAL")


class TopicResponse(_ResponseModel):
    id: int
    name: str
    slug: str
    description: str | None = None
    parent_id: int | None = None
    path: str
    is_active: bool
    display_order: int


class TopicNode(_ResponseModel):
    id: int
    name: str
    slug: str
    parent_id: int | None = None
    aliases: list[str] = []
    children: list[TopicNode] = []


class TopicPayload(BaseModel):
    name: str = Field(min_length=1, max_length=160)
    slug: str = Field(min_length=1, max_length=160)
    description: str | None = Field(default=None, max_length=500)
    parent_id: int | None = None
    display_order: int = 0


class TopicUpdatePayload(BaseModel):
    name: str | None = Field(default=None, max_length=160)
    description: str | None = Field(default=None, max_length=500)
    is_active: bool | None = None
    display_order: int | None = None


class TopicAliasPayload(BaseModel):
    alias: str = Field(min_length=1, max_length=160)
    is_active: bool = True


class TopicAliasResponse(_ResponseModel):
    id: int
    topic_id: int
    alias: str
    is_active: bool


class ArticleTopicResponse(_ResponseModel):
    id: int
    topic_id: int
    name: str
    origin: str
    score: float | None = None
    evidence: str | None = None


class ArticleTopicPayload(BaseModel):
    topic_id: int


class SuggestedTopic(_ResponseModel):
    """Tema propuesto por el clasificador en la vista previa, sin persistir.
    Si el documentalista lo deja, vuelve como `ArticleTopicPayload` y se guarda
    con origin="AUTO"; si lo quita, no queda rastro."""

    topic_id: int
    name: str
    path: str
    score: float
    evidence: str


class TopicFrequencyRow(_ResponseModel):
    topic_id: int
    name: str
    day: str  # ISO date
    count: int


TopicNode.model_rebuild()
```

- [ ] **Step 2: Extender `SaveArticleRequest`** (~línea 80, tras `localities`)

```python
    # Temas elegidos por el documentalista. Si viene no vacío, PISA lo que
    # propondría el clasificador (se guardan como origin="MANUAL").
    topic_ids: list[int] = []
```

- [ ] **Step 3: Extender `AnalyzeResult`** (~línea 307, tras `suggested_localities`)

```python
    suggested_topics: list[SuggestedTopic] = []
```

Y añadir `AnalyzeResult.model_rebuild()` tras la definición de `SuggestedTopic` (o mover la línea `model_rebuild` existente para que también resuelva la nueva referencia adelantada — `SuggestedTopic` no es forward-ref si se define antes de `AnalyzeResult`; colócala en el bloque de análisis, ~línea 240, para evitarlo).

- [ ] **Step 4: Extender `ArticleFiltersResponse`** (~línea 369)

```python
    topics: list[TopicResponse] = []
```

- [ ] **Step 5: Verificar que el módulo importa**

Run: `python -c "import odin.api.schemas"`
Expected: sin error.

- [ ] **Step 6: Dejar el cambio en el working tree.**

---

## Task 5: Servicio + router CRUD de temas

**Files:**
- Create: `src/odin/services/topic_service.py`
- Create: `src/odin/api/routers/topics.py`
- Modify: `src/odin/api/__init__.py` (`from odin.api.routers import (... topics ...)` línea 41; `app.include_router(topics.router)` tras localities línea 159)
- Test: `tests/api/test_api_topics.py`

**Interfaces:**
- Consumes: schemas (Task 4); `Topic`/`TopicAlias`/`ArticleTopic` (Task 1); `topic_store` (Task 2); `deps.get_session`; `auth.require_auth`; `norm_key`; `accent_insensitive_contains` (`odin.services.article_service`).
- Produces (llamadas por el router y por Tasks 6–10):
  - `list_topics(q, parent_id, include_inactive, limit, offset) -> list[TopicResponse]`
  - `get_tree(include_inactive: bool) -> list[TopicNode]`
  - `create_topic(payload: TopicPayload) -> TopicResponse`
  - `update_topic(topic_id: int, payload: TopicUpdatePayload) -> TopicResponse`
  - `delete_topic(topic_id: int) -> None`  (baja lógica si tiene `article_topics`; borrado duro solo si no está referenciado y no tiene hijos)
  - `add_alias(topic_id: int, payload: TopicAliasPayload) -> TopicAliasResponse`
  - `delete_alias(topic_id: int, alias_id: int) -> None`
  - `list_article_topics(article_id: int) -> list[ArticleTopicResponse]`
  - `replace_article_topics(article_id: int, topic_ids: list[int], documentalist_username: str | None) -> list[ArticleTopicResponse]`
  - `list_unclassified(limit, offset) -> list[ArticleSummary]`
  - `frequency_by_topic(date_from, date_to, parent_id) -> list[TopicFrequencyRow]`

- [ ] **Step 1: Escribir los tests que fallan**

```python
# tests/api/test_api_topics.py
from __future__ import annotations

from odin.core.auth import create_token


def _h():
    t, _ = create_token("tester")
    return {"Authorization": f"Bearer {t}"}


def test_crud_topic_and_alias(api_client):
    r = api_client.post("/api/topics", headers=_h(),
                        json={"name": "Vivienda", "slug": "vivienda"})
    assert r.status_code == 201, r.text
    tid = r.json()["id"]

    r = api_client.post(f"/api/topics/{tid}/aliases", headers=_h(),
                        json={"alias": "déficit habitacional"})
    assert r.status_code == 201

    r = api_client.get("/api/topics")
    assert any(t["slug"] == "vivienda" for t in r.json())

    r = api_client.put(f"/api/topics/{tid}", headers=_h(), json={"is_active": False})
    assert r.status_code == 200 and r.json()["is_active"] is False


def test_duplicate_sibling_slug_conflicts(api_client):
    api_client.post("/api/topics", headers=_h(), json={"name": "Agua", "slug": "agua-x"})
    r = api_client.post("/api/topics", headers=_h(), json={"name": "AGUA", "slug": "agua-y"})
    assert r.status_code == 409


def test_delete_topic_with_articles_is_soft(api_client, sqlite_sessionmaker):
    from odin.db.models import Article, ArticleTopic, Topic
    s = sqlite_sessionmaker()
    t = Topic(name="Deportes", norm_key="deportes", slug="deportes", path="/99/")
    a = Article(source="acento", url="https://x/dep", title="t", body="b")
    s.add_all([t, a]); s.flush()
    s.add(ArticleTopic(article_id=a.id, topic_id=t.id, score=0.9, origin="AUTO"))
    s.commit(); tid = t.id; s.close()

    r = api_client.delete(f"/api/topics/{tid}", headers=_h())
    assert r.status_code == 204
    s = sqlite_sessionmaker()
    assert s.get(Topic, tid).is_active is False  # no se borró
```

- [ ] **Step 2: Correr y ver fallar**

Run: `python -m pytest tests/api/test_api_topics.py -q`
Expected: FAIL (404 en los endpoints / `ModuleNotFoundError`).

- [ ] **Step 3: Implementar `src/odin/services/topic_service.py`**

Seguir 1:1 el estilo de `locality_service.py` (sesión por función, `HTTPException` en el borde, `try/except/rollback/finally`, `invalidate` tras cada mutación). Puntos clave:

```python
from odin.db import topics as topic_store
from odin.db.models import Article, ArticleTopic, Topic, TopicAlias
# ... imports schemas, deps, norm_key, accent_insensitive_contains, select/func/and_

def create_topic(payload):
    name = payload.name.strip()
    nkey = norm_key(name)
    session = deps.get_session()
    try:
        parent = session.get(Topic, payload.parent_id) if payload.parent_id else None
        if payload.parent_id and not parent:
            raise HTTPException(404, "El tema padre no existe.")
        clash = session.scalar(select(Topic).where(
            Topic.parent_id == payload.parent_id, Topic.norm_key == nkey))
        if clash:
            raise HTTPException(409, f"'{name}' ya existe bajo ese tema padre.")
        slug_clash = session.scalar(select(Topic).where(Topic.slug == payload.slug.strip()))
        if slug_clash:
            raise HTTPException(409, f"El slug '{payload.slug}' ya está en uso.")
        row = Topic(name=name, norm_key=nkey, slug=payload.slug.strip(),
                    description=payload.description, parent_id=payload.parent_id,
                    display_order=payload.display_order, path="")
        session.add(row); session.flush()
        row.path = f"{(parent.path if parent else '/')}{row.id}/"
        session.commit()
        topic_store.invalidate_cache()
        return TopicResponse.model_validate(row)
    except HTTPException:
        raise
    except Exception:
        session.rollback(); log.exception("topic_creation_failed")
        raise HTTPException(500, "Error interno creando el tema.") from None
    finally:
        session.close()


def delete_topic(topic_id):
    session = deps.get_session()
    try:
        row = session.get(Topic, topic_id)
        if not row:
            raise HTTPException(404, "Tema no encontrado.")
        referenced = session.scalar(
            select(func.count()).select_from(ArticleTopic).where(ArticleTopic.topic_id == topic_id)
        )
        has_children = session.scalar(
            select(func.count()).select_from(Topic).where(Topic.parent_id == topic_id)
        )
        if referenced or has_children:
            row.is_active = False          # baja lógica: no romper histórico
        else:
            session.delete(row)            # borrado duro solo si no cuelga nada
        session.commit()
        topic_store.invalidate_cache()
    except HTTPException:
        raise
    except Exception:
        session.rollback(); log.exception("topic_deletion_failed", topic_id=topic_id)
        raise HTTPException(500, "Error interno eliminando el tema.") from None
    finally:
        session.close()


def replace_article_topics(article_id, topic_ids, documentalist_username=None):
    session = deps.get_session()
    try:
        article = session.get(Article, article_id)
        if not article:
            raise HTTPException(404, "Reporte no encontrado.")
        valid = set(session.scalars(select(Topic.id).where(Topic.id.in_(topic_ids))).all())
        missing = set(topic_ids) - valid
        if missing:
            raise HTTPException(422, f"Temas inexistentes: {sorted(missing)}.")
        session.query(ArticleTopic).filter(ArticleTopic.article_id == article_id).delete()
        for tid in dict.fromkeys(topic_ids):
            session.add(ArticleTopic(article_id=article_id, topic_id=tid,
                                     origin="MANUAL", score=None, evidence=None))
        # rectificar reasigna autoría, como update_article
        from odin.services.article_service import _documentalist_id_for
        rectifier = _documentalist_id_for(session, documentalist_username)
        if rectifier is not None:
            article.documentalist_id = rectifier
        session.commit()
        return list_article_topics(article_id)
    except HTTPException:
        raise
    except Exception:
        session.rollback(); log.exception("replace_article_topics_failed", article_id=article_id)
        raise HTTPException(500, "Error interno actualizando los temas.") from None
    finally:
        session.close()


def list_unclassified(limit=20, offset=0):
    session = deps.get_session()
    try:
        no_topics = ~select(1).select_from(ArticleTopic).where(
            ArticleTopic.article_id == Article.id).exists()
        rows = session.scalars(
            select(Article).where(no_topics)
            .order_by(Article.scraped_at.desc()).limit(limit).offset(offset)
        ).all()
        from odin.services.article_service import _to_summary
        return [_to_summary(session, a) for a in rows]
    finally:
        session.close()


def frequency_by_topic(date_from=None, date_to=None, parent_id=None):
    """Conteo de artículos por tema y día. Roll-up al padre: una nota en un
    subtema cuenta también para su tema raíz (join por prefijo de `path`)."""
    session = deps.get_session()
    try:
        anc = select(Topic.id, Topic.name, Topic.path).subquery()
        day = func.date(Article.published_at)
        stmt = (
            select(anc.c.id, anc.c.name, day.label("day"),
                   func.count(func.distinct(Article.id)).label("count"))
            .select_from(ArticleTopic)
            .join(Topic, Topic.id == ArticleTopic.topic_id)
            .join(anc, Topic.path.like(anc.c.path + "%"))
            .join(Article, Article.id == ArticleTopic.article_id)
            .group_by(anc.c.id, anc.c.name, day)
            .order_by(day, anc.c.name)
        )
        if parent_id is not None:
            stmt = stmt.where(anc.c.id == parent_id)
        if date_from:
            stmt = stmt.where(Article.published_at >= _parse_date(date_from))
        if date_to:
            stmt = stmt.where(Article.published_at < _parse_date(date_to) + timedelta(days=1))
        return [
            TopicFrequencyRow(topic_id=r.id, name=r.name, day=str(r.day), count=r.count)
            for r in session.execute(stmt).all()
        ]
    finally:
        session.close()
```

`list_topics`, `get_tree`, `update_topic`, `add_alias`, `delete_alias`, `list_article_topics` siguen el molde exacto de sus equivalentes en `locality_service.py` / `alias_service.py` (`get_tree` = el de localities con `aliases` incluidos). Requisito nuevo en `article_service.py`: extraer un helper `_to_summary(session, article) -> ArticleSummary` a partir del código que hoy arma `ArticleSummary` dentro de `list_articles`, para reusarlo en `list_unclassified` (si ya existe un helper equivalente, usar ese).

- [ ] **Step 4: Implementar `src/odin/api/routers/topics.py`**

Molde exacto de `routers/localities.py` (`dependencies=[Depends(auth.require_auth)]` en cada mutación):

```python
"""Catálogo administrable de temas y clasificación de la noticia."""
from __future__ import annotations

from fastapi import APIRouter, Depends

from odin.api.schemas import (
    ArticleTopicPayload, ArticleTopicResponse, SuggestedTopic, TopicAliasPayload,
    TopicAliasResponse, TopicFrequencyRow, TopicNode, TopicPayload, TopicResponse,
    TopicUpdatePayload,
)
from odin.api.schemas import ArticleListResponse
from odin.core import auth
from odin.services import topic_service

router = APIRouter(tags=["topics"])


@router.get("/api/topics/tree", response_model=list[TopicNode])
def topic_tree(include_inactive: bool = False):
    return topic_service.get_tree(include_inactive=include_inactive)


@router.get("/api/topics", response_model=list[TopicResponse])
def list_topics(q: str | None = None, parent_id: int | None = None,
                include_inactive: bool = False, limit: int = 200, offset: int = 0):
    return topic_service.list_topics(q, parent_id, include_inactive, limit, offset)


@router.post("/api/topics", status_code=201,
             dependencies=[Depends(auth.require_auth)], response_model=TopicResponse)
def create_topic(payload: TopicPayload):
    return topic_service.create_topic(payload)


@router.put("/api/topics/{topic_id}", dependencies=[Depends(auth.require_auth)],
            response_model=TopicResponse)
def update_topic(topic_id: int, payload: TopicUpdatePayload):
    return topic_service.update_topic(topic_id, payload)


@router.delete("/api/topics/{topic_id}", status_code=204,
               dependencies=[Depends(auth.require_auth)])
def delete_topic(topic_id: int):
    topic_service.delete_topic(topic_id)


@router.post("/api/topics/{topic_id}/aliases", status_code=201,
             dependencies=[Depends(auth.require_auth)], response_model=TopicAliasResponse)
def add_alias(topic_id: int, payload: TopicAliasPayload):
    return topic_service.add_alias(topic_id, payload)


@router.delete("/api/topics/{topic_id}/aliases/{alias_id}", status_code=204,
               dependencies=[Depends(auth.require_auth)])
def delete_alias(topic_id: int, alias_id: int):
    topic_service.delete_alias(topic_id, alias_id)


@router.get("/api/topics/frequency", response_model=list[TopicFrequencyRow])
def topic_frequency(date_from: str | None = None, date_to: str | None = None,
                    parent_id: int | None = None):
    return topic_service.frequency_by_topic(date_from, date_to, parent_id)


@router.get("/api/topics/unclassified", response_model=ArticleListResponse)
def unclassified(limit: int = 20, offset: int = 0):
    return topic_service.list_unclassified(limit, offset)


@router.get("/api/articles/{article_id}/topics", response_model=list[ArticleTopicResponse])
def list_article_topics(article_id: int):
    return topic_service.list_article_topics(article_id)


@router.put("/api/articles/{article_id}/topics",
            dependencies=[Depends(auth.require_auth)], response_model=list[ArticleTopicResponse])
def replace_article_topics(article_id: int, payload: list[ArticleTopicPayload],
                           documentalist: str = Depends(auth.require_auth)):
    return topic_service.replace_article_topics(
        article_id, [p.topic_id for p in payload], documentalist_username=documentalist)
```

(Nota: `/api/topics/unclassified` y `/api/topics/frequency` van declarados ANTES de cualquier `/api/topics/{topic_id}` para que FastAPI no capture "unclassified" como `topic_id`. En este router `{topic_id}` es `int`, así que no colisiona, pero mantener el orden por claridad.)

- [ ] **Step 5: Registrar el router**

`src/odin/api/__init__.py`: añadir `topics` al import de `odin.api.routers` (línea 41) y `app.include_router(topics.router)` tras `localities` (línea 159).

- [ ] **Step 6: Correr los tests**

Run: `python -m pytest tests/api/test_api_topics.py -q`
Expected: PASS.

- [ ] **Step 7: Dejar el cambio en el working tree.**

---

## Task 6: Sugerencias de tema en la vista previa de `/api/analyze`

**Files:**
- Modify: `src/odin/services/analyze_service.py` (~línea 245–290, donde se arma `AnalyzeResult` con `suggested_localities`)
- Test: `tests/api/test_api_topics_wiring.py`

**Interfaces:**
- Consumes: `topic_classifier.classify` (Task 3); `topic_store.get_catalog` (Task 2); `SuggestedTopic` (Task 4).
- Produces: `AnalyzeResult.suggested_topics` poblado en la vista previa (no en la rama `already_saved`).

- [ ] **Step 1: Escribir el test que falla**

```python
# tests/api/test_api_topics_wiring.py
from __future__ import annotations

from unittest.mock import patch

from odin.analysis.base import AnalysisResult
from odin.core.auth import create_token
from odin.db import topics as topic_store


def _h():
    t, _ = create_token("tester")
    return {"Authorization": f"Bearer {t}"}


_FAKE = AnalysisResult(main_topic="escasez de agua", topic_keywords=["agua", "acueducto"],
                       overall_sentiment="NEG", sentiment_score=0.7, entities=[])


def test_preview_returns_suggested_topics(api_client, monkeypatch):
    topic_store.load_seed()
    monkeypatch.setattr("odin.services.analyze_service.fetch_html", lambda *a, **k: "<html>x</html>")
    with patch("odin.services.analyze_service._extract_article") as ex:
        ex.return_value = type("S", (), dict(
            source="acento", url="https://acento.com.do/x", title="Protesta por agua",
            authors=None, section=None, published_at=None, body="Vecinos reclaman agua.",
        ))()
        with patch("odin.services.analyze_service.analyzer") as an:
            an.analyze.return_value = _FAKE
            an.name, an.model, an.version = "local", "test", "t"
            r = api_client.post("/api/analyze", headers=_h(),
                                json={"url": "https://acento.com.do/x"})
    assert r.status_code == 200, r.text
    names = {s["name"] for s in r.json()["result"]["suggested_topics"]}
    assert "Agua" in names
```

(Ajustar los nombres de símbolos parcheados —`fetch_html`, `_extract_article`, `analyzer`— a los reales de `analyze_service.py`; el patrón exacto ya está en `tests/api/test_api_analyze*.py`, copiarlo.)

- [ ] **Step 2: Correr y ver fallar**

Run: `python -m pytest tests/api/test_api_topics_wiring.py::test_preview_returns_suggested_topics -q`
Expected: FAIL (`suggested_topics` vacío / KeyError).

- [ ] **Step 3: Implementar**

En `analyze_service.py`, junto al import diferido de `suggest_from_places` (~línea 250):

```python
        from odin.analysis.topic_classifier import classify as classify_topics
        from odin.db.topics import get_catalog as _topic_catalog

        _by_id = {t.id: t for t in _topic_catalog()}
        _topic_matches = classify_topics(
            result_source.title, result.? if False else scraped.body,  # usar título+cuerpo reales
            ", ".join(result.topic_keywords) or None, result.main_topic,
        )
        suggested_topics = [
            SuggestedTopic(topic_id=mt.topic_id, name=_by_id[mt.topic_id].name,
                           path=_by_id[mt.topic_id].path, score=round(mt.score, 2),
                           evidence=mt.evidence)
            for mt in _topic_matches if mt.topic_id in _by_id
        ]
```

y pasar `suggested_topics=suggested_topics` al construir el `AnalyzeResult` (línea ~289, junto a `suggested_localities=`). Usar el título y cuerpo del artículo scrapeado que ya están en scope en esa función (mismos que se pasan al analizador).

- [ ] **Step 4: Correr los tests**

Run: `python -m pytest tests/api/test_api_topics_wiring.py -q`
Expected: PASS.

- [ ] **Step 5: Dejar el cambio en el working tree.**

---

## Task 7: Persistir `article_topics` al guardar (manual)

**Files:**
- Modify: `src/odin/services/article_service.py::save_article` (~línea 604–616, tras `session.flush()` y el `add_all` de localities)
- Test: `tests/api/test_api_topics_wiring.py` (añadir casos)

**Interfaces:**
- Consumes: `req.topic_ids` (Task 4); `classify` + `get_catalog` (Tasks 2–3); `ArticleTopic` (Task 1).
- Produces: filas `article_topics` tras un alta manual — `MANUAL` si `req.topic_ids` no está vacío, si no `AUTO` desde el clasificador (≥ `TOPIC_MIN_SCORE`).

- [ ] **Step 1: Escribir los tests que fallan**

```python
def test_save_with_explicit_topic_ids_is_manual(api_client, sqlite_sessionmaker):
    topic_store.load_seed()
    agua = topic_store.resolve("Agua")
    body = dict(source="acento", url="https://acento.com.do/s1", title="t", body="cuerpo",
                entities=[], topic_ids=[agua])
    r = api_client.post("/api/articles", headers=_h(), json=body)
    assert r.status_code == 201, r.text
    from odin.db.models import ArticleTopic
    s = sqlite_sessionmaker()
    rows = s.query(ArticleTopic).all()
    assert [(x.topic_id, x.origin) for x in rows] == [(agua, "MANUAL")]


def test_save_without_topic_ids_runs_classifier(api_client, sqlite_sessionmaker):
    topic_store.load_seed()
    agua = topic_store.resolve("Agua")
    body = dict(source="acento", url="https://acento.com.do/s2",
                title="Reclaman por la escasez de agua", body="El acueducto no da servicio.",
                main_topic="escasez de agua", entities=[])
    r = api_client.post("/api/articles", headers=_h(), json=body)
    assert r.status_code == 201
    from odin.db.models import ArticleTopic
    s = sqlite_sessionmaker()
    rows = s.query(ArticleTopic).filter_by(origin="AUTO").all()
    assert agua in {x.topic_id for x in rows}
```

- [ ] **Step 2: Correr y ver fallar**

Run: `python -m pytest tests/api/test_api_topics_wiring.py -q -k save`
Expected: FAIL (no se crean `article_topics`).

- [ ] **Step 3: Implementar**

En `save_article`, tras el `session.add_all([...ArticleLocality...])` y antes de `session.commit()`:

```python
        from odin.analysis.topic_classifier import classify as classify_topics
        from odin.db.topics import get_catalog as _topic_catalog

        valid_topic_ids = {t.id for t in _topic_catalog()}
        if req.topic_ids:
            chosen = [(tid, "MANUAL", None, None)
                      for tid in dict.fromkeys(req.topic_ids) if tid in valid_topic_ids]
        else:
            chosen = [(m.topic_id, "AUTO", round(m.score, 3), m.evidence)
                      for m in classify_topics(req.title, req.body, req.topic_keywords,
                                               req.main_topic)
                      if m.topic_id in valid_topic_ids]
        session.add_all([
            ArticleTopic(article_id=article.id, topic_id=tid, origin=origin,
                         score=score, evidence=ev)
            for tid, origin, score, ev in chosen
        ])
```

(`ArticleTopic` ya importado en Task 1 vía `from odin.db.models import ...`; añadirlo al import existente de `article_service.py`.)

- [ ] **Step 4: Correr los tests**

Run: `python -m pytest tests/api/test_api_topics_wiring.py -q`
Expected: PASS.

- [ ] **Step 5: Dejar el cambio en el working tree.**

---

## Task 8: Clasificación en el rastreo masivo (`pipeline._persist`)

**Files:**
- Modify: `src/odin/core/pipeline.py` — `_persist` (línea 54) y `run` (construcción del matcher junto a `person_map`, línea 203; pasarlo por el árbol de llamadas `_process_source` → `_persist`)
- Test: `tests/test_pipeline_topics.py` (o el archivo de tests de pipeline existente)

**Interfaces:**
- Consumes: `topic_classifier.build_matcher` / `classify` con matcher explícito; `get_catalog`.
- Produces: filas `article_topics` `origin="AUTO"` para los artículos que entran por crawl y matchean ≥ umbral.

- [ ] **Step 1: Escribir el test que falla**

```python
# tests/test_pipeline_topics.py
from __future__ import annotations

from odin.analysis.base import AnalysisResult
from odin.core import pipeline
from odin.db import topics as topic_store
from odin.db.models import Article, ArticleTopic
from odin.scrapers.base import ScrapedArticle


def test_persist_creates_article_topics(sqlite_sessionmaker, monkeypatch):
    topic_store.load_seed()
    agua = topic_store.resolve("Agua")
    session = sqlite_sessionmaker()

    scraped = ScrapedArticle(source="acento", url="https://acento.com.do/p1",
                             title="Protesta por escasez de agua", body="El acueducto falla.")
    result = AnalysisResult(main_topic="escasez de agua", topic_keywords=["agua"],
                            overall_sentiment="NEG", sentiment_score=0.6, entities=[])

    class _A:
        name, model, version = "local", "test", "t"
    pipeline._persist(session, scraped, result, _A())

    rows = session.query(ArticleTopic).all()
    assert agua in {r.topic_id for r in rows}
    assert all(r.origin == "AUTO" for r in rows)
```

- [ ] **Step 2: Correr y ver fallar**

Run: `python -m pytest tests/test_pipeline_topics.py -q`
Expected: FAIL (no hay `article_topics`).

- [ ] **Step 3: Implementar**

En `_persist`, tras `session.add(article)` / `session.commit()` (o antes del commit, tras `session.flush()` para tener `article.id`):

```python
    from odin.analysis.topic_classifier import classify
    from odin.db.topics import get_catalog

    valid = {t.id for t in get_catalog()}
    for m in classify(scraped.title, scraped.body or "",
                      ", ".join(result.topic_keywords) or None, result.main_topic):
        if m.topic_id in valid:
            session.add(ArticleTopic(article_id=article.id, topic_id=m.topic_id,
                                     origin="AUTO", score=round(m.score, 3),
                                     evidence=m.evidence))
    session.commit()
```

`get_catalog()` y el matcher del clasificador están cacheados a nivel de módulo, así que llamarlos por artículo dentro de una corrida no re-consulta la BD (la caché se llena una vez y `invalidate_cache` solo la limpia ante un CRUD). No hace falta pasar el matcher explícito por el árbol de llamadas — la caché ya cumple ese rol. **Simplificación respecto al diseño inicial: no se toca `run()` ni `_process_source`.**

Importar `ArticleTopic` en `pipeline.py` (`from odin.db.models import Article, ArticleTopic, ...`).

- [ ] **Step 4: Correr los tests**

Run: `python -m pytest tests/test_pipeline_topics.py tests/ -q -k "pipeline"`
Expected: PASS; los tests de pipeline existentes siguen verdes.

- [ ] **Step 5: Dejar el cambio en el working tree.**

---

## Task 9: Filtro por tema del catálogo + faceta

**Files:**
- Modify: `src/odin/services/article_service.py` — `_build_conditions`/`list_articles` (bloque `locality`, ~línea 155–172; firma ~línea 302; faceta ~línea 398)
- Modify: `src/odin/api/routers/articles.py` — `list_articles` (añadir `topic_id: int | None = None`, pasarlo al servicio)
- Test: `tests/api/test_api_topics_wiring.py` (añadir casos) — y verificar que `tests/api/test_api_filters.py` sigue verde

**Interfaces:**
- Consumes: `Topic`, `ArticleTopic` (Task 1).
- Produces: `GET /api/articles?topic_id=<id>` filtra por `article_topics` incluyendo el subárbol (`Topic.path` prefijo); `GET /api/articles/filters` devuelve `topics` del catálogo. El parámetro `topic` (contains sobre `main_topic`) **se conserva** para no romper el frontend actual.

- [ ] **Step 1: Escribir el test que falla**

```python
def test_filter_by_topic_id_includes_subtree(api_client, sqlite_sessionmaker):
    from odin.db.models import Article, ArticleTopic, Topic
    s = sqlite_sessionmaker()
    agua = Topic(name="Agua", norm_key="agua", slug="agua", path="")
    s.add(agua); s.flush(); agua.path = f"/{agua.id}/"
    sub = Topic(name="Infra agua", norm_key="infra agua", slug="infra-agua",
                parent_id=agua.id, path=f"/{agua.id}/")
    s.add(sub); s.flush(); sub.path = f"/{agua.id}/{sub.id}/"
    a = Article(source="acento", url="https://x/f1", title="t", body="b")
    s.add(a); s.flush()
    s.add(ArticleTopic(article_id=a.id, topic_id=sub.id, score=0.9, origin="AUTO"))
    s.commit(); agua_id = agua.id; s.close()

    r = api_client.get(f"/api/articles?topic_id={agua_id}", headers=_h())
    assert r.status_code == 200
    assert r.json()["total"] == 1  # el artículo del subtema cuenta para el padre


def test_filters_facet_lists_catalog_topics(api_client):
    topic_store.load_seed()
    r = api_client.get("/api/articles/filters", headers=_h())
    slugs = {t["slug"] for t in r.json()["topics"]}
    assert "agua" in slugs
```

- [ ] **Step 2: Correr y ver fallar**

Run: `python -m pytest tests/api/test_api_topics_wiring.py -q -k "topic_id or facet"`
Expected: FAIL (`topic_id` no reconocido / `topics` ausente en la faceta).

- [ ] **Step 3: Implementar el filtro**

En `_build_conditions` (junto al bloque `locality`):

```python
    if topic_id is not None:
        target_path = select(Topic.path).where(Topic.id == topic_id).scalar_subquery()
        conditions.append(
            select(1).select_from(ArticleTopic)
            .join(Topic, Topic.id == ArticleTopic.topic_id)
            .where(ArticleTopic.article_id == Article.id,
                   Topic.path.like(target_path + "%"))
            .exists()
        )
```

Añadir `topic_id: int | None = None` a la firma de `list_articles` y `_build_conditions` y propagarlo (igual que `locality`). Importar `Topic, ArticleTopic` en `article_service.py`.

- [ ] **Step 4: Implementar la faceta**

En la función que arma `ArticleFiltersResponse` (~línea 398), reemplazar el `SELECT DISTINCT Article.section`… no — dejar `sections` como está; **añadir**:

```python
        from odin.db.models import Topic
        topic_rows = session.scalars(
            select(Topic).where(Topic.is_active.is_(True))
            .order_by(Topic.display_order, Topic.name)
        ).all()
        # ...
        return ArticleFiltersResponse(
            ...,
            topics=[TopicResponse.model_validate(t) for t in topic_rows],
        )
```

- [ ] **Step 5: Router**

`routers/articles.py::list_articles`: añadir `topic_id: int | None = None` a la firma y `topic_id=topic_id` a la llamada de `article_service.list_articles`.

- [ ] **Step 6: Correr los tests**

Run: `python -m pytest tests/api/test_api_topics_wiring.py tests/api/test_api_filters.py -q`
Expected: PASS (nuevos + los de filtros existentes).

- [ ] **Step 7: Dejar el cambio en el working tree.**

---

## Task 10: Backfill de `main_topic` → `article_topics`

**Files:**
- Create: `scripts/backfill_article_topics.py`
- Test: `tests/scripts/test_backfill_article_topics.py`

**Interfaces:**
- Consumes: `topic_store.resolve` / `classify`; `Article`, `ArticleTopic`.
- Produces: script CLI con `--dry-run`; para cada `Article` sin `article_topics`, primero intenta `topic_store.resolve(main_topic)`, si no `classify(title, body, topic_keywords, main_topic)`; inserta `AUTO` con `evidence`. Loguea `mapeados` / `sin_clasificar`.

- [ ] **Step 1: Escribir el test que falla**

```python
# tests/scripts/test_backfill_article_topics.py
from __future__ import annotations

from odin.db import topics as topic_store
from odin.db.models import Article, ArticleTopic
from scripts.backfill_article_topics import backfill


def test_backfill_maps_main_topic(sqlite_sessionmaker):
    topic_store.load_seed()
    agua = topic_store.resolve("Agua")
    s = sqlite_sessionmaker()
    s.add(Article(source="acento", url="https://x/b1", title="t", body="b",
                  main_topic="acueducto"))
    s.add(Article(source="acento", url="https://x/b2", title="t", body="b",
                  main_topic="tema totalmente ajeno"))
    s.commit(); s.close()

    stats = backfill(dry_run=False)
    assert stats["mapeados"] == 1
    assert stats["sin_clasificar"] == 1
    s = sqlite_sessionmaker()
    assert {r.topic_id for r in s.query(ArticleTopic).all()} == {agua}
```

- [ ] **Step 2: Correr y ver fallar**

Run: `python -m pytest tests/scripts/test_backfill_article_topics.py -q`
Expected: FAIL (`ModuleNotFoundError: scripts.backfill_article_topics`).

- [ ] **Step 3: Implementar** (molde: `scripts/merge_duplicate_entities.py`)

```python
"""Backfill de temas para artículos ya guardados: aplica el mismo clasificador
que ahora corre en cada análisis a las filas viejas, cuyo tema quedó solo como
texto libre en `Article.main_topic`.

100% local. `--dry-run` solo cuenta.

Uso:
  python scripts/backfill_article_topics.py --dry-run
  python scripts/backfill_article_topics.py
"""
from __future__ import annotations

import argparse

from sqlalchemy import select

from odin.analysis.topic_classifier import classify
from odin.db import topics as topic_store
from odin.db.models import Article, ArticleTopic
from odin.db.session import get_session, init_db


def backfill(*, dry_run: bool = False) -> dict[str, int]:
    init_db()
    topic_store.get_catalog()  # calienta la caché
    valid = {t.id for t in topic_store.get_catalog()}
    session = get_session()
    stats = {"mapeados": 0, "sin_clasificar": 0}
    try:
        has_topics = select(1).select_from(ArticleTopic).where(
            ArticleTopic.article_id == Article.id).exists()
        articles = session.scalars(select(Article).where(~has_topics)).all()
        for a in articles:
            tid = topic_store.resolve(a.main_topic or "")
            matches = []
            if tid in valid:
                matches = [(tid, 1.0, a.main_topic)]
            else:
                matches = [(m.topic_id, m.score, m.evidence)
                           for m in classify(a.title, a.body or "",
                                             a.topic_keywords, a.main_topic)
                           if m.topic_id in valid]
            if not matches:
                stats["sin_clasificar"] += 1
                continue
            stats["mapeados"] += 1
            if not dry_run:
                for mtid, score, ev in matches:
                    session.add(ArticleTopic(article_id=a.id, topic_id=mtid,
                                             origin="AUTO", score=round(float(score), 3),
                                             evidence=ev))
        if not dry_run:
            session.commit()
        return stats
    finally:
        session.close()


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--dry-run", action="store_true")
    args = p.parse_args()
    stats = backfill(dry_run=args.dry_run)
    print(f"mapeados={stats['mapeados']}  sin_clasificar={stats['sin_clasificar']}"
          + ("  (dry-run, nada se guardó)" if args.dry_run else ""))


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: Correr los tests**

Run: `python -m pytest tests/scripts/test_backfill_article_topics.py -q`
Expected: PASS.

- [ ] **Step 5: Dejar el cambio en el working tree.**

---

## Task 11: Documentación

**Files:**
- Modify: `docs/DATA_DICTIONARY.md` (añadir `topics`, `topic_aliases`, `article_topics`)
- Modify: `docs/planning/2026-08-21-requerimientos-cliente-gap.md` (marcar R4/R5/R7 con estado "primera versión" y apuntar a este trabajo)
- Create: `docs/superpowers/plans/2026-09-08-catalogo-temas.md` (copia de este plan, ubicación canónica del skill)

- [ ] **Step 1:** Documentar las 3 tablas en `DATA_DICTIONARY.md` con el mismo formato que las filas de `localities`/`article_localities` (columna, tipo, nullable, origen, descripción).

- [ ] **Step 2:** En el gap doc, en la tabla de estado (~línea 162), cambiar R4/R5/R7 de ❌ a "🟡 primera versión (catálogo + clasificador por reglas + cola sin clasificar)".

- [ ] **Step 3:** Guardar este plan en `docs/superpowers/plans/2026-09-08-catalogo-temas.md`.

- [ ] **Step 4: Dejar el cambio en el working tree.**

---

## Follow-up (fuera de alcance de este plan)

- **Frontend**: pantalla de administración del catálogo (molde: panel de `entity_aliases`), migrar el filtro `topic` de input libre a multiselect del catálogo, vista "sin clasificar", chips de tema en el detalle y en el form de guardado/preview (usando `suggested_topics`).
- **Capa semántica del clasificador** (§F1): para lo que las reglas no alcancen, un segundo nivel (embeddings o el propio LLM) — solo si el cliente reporta demasiados "sin clasificar".
- **Subtemas (R6)**: el modelo ya lo soporta; falta UI de árbol y una decisión de producto sobre cómo se navegan.
- **R11 secciones normalizadas**: misma maquinaria (`sections` + `section_aliases`), otra dimensión.

---

## Verification (end-to-end)

1. **Migración:** `python -m alembic upgrade head` limpio en SQLite; `alembic downgrade -1 && alembic upgrade head` reversible. En un Postgres de prueba (docker-compose `db`): `alembic upgrade head` sin error.
2. **Suite completa:** `python -m pytest -q` en verde — en especial `tests/api/test_api_filters.py`, `tests/api/test_api_analyze*.py`, `tests/test_pipeline*.py` (no regresiones) y los 5 archivos nuevos.
3. **Semilla y clasificación manual (servidor levantado con `uvicorn odin.api:app`):**
   - `POST /api/auth/login` → token.
   - `GET /api/topics` → devuelve la lista semilla (Agua, Energía eléctrica, …).
   - `POST /api/analyze` con la URL de una nota real de agua/apagón → `result.suggested_topics` trae el tema esperado con `score ≥ 0.6` y `evidence` con el término que disparó.
   - `POST /api/articles` con ese cuerpo (sin `topic_ids`) → `GET /api/articles/{id}/topics` muestra el vínculo `AUTO`.
   - `POST /api/articles` con `topic_ids: [<otro>]` → el vínculo es `MANUAL`, no corre el clasificador.
   - `PUT /api/articles/{id}/topics` con `[{topic_id: X}]` → reemplaza y queda `MANUAL`.
   - `GET /api/topics/unclassified` → lista los artículos sin ningún `article_topic`.
   - `GET /api/topics/frequency?date_from=2026-01-01&date_to=2026-12-31` → filas `{topic_id, name, day, count}`, con el conteo del subtema sumado al padre.
   - `GET /api/articles?topic_id=<raíz>` → incluye artículos etiquetados en sus subtemas.
4. **Backfill:** `python scripts/backfill_article_topics.py --dry-run` reporta `mapeados/sin_clasificar`; sin `--dry-run` crea los `article_topics` y una segunda corrida reporta `mapeados=0`.
5. **CRUD de catálogo:** crear un tema hijo, agregarle un alias, `POST /api/analyze` de una nota que use ese alias → aparece en `suggested_topics` (prueba de que `invalidate_cache` propagó al clasificador). Desactivar el tema → deja de sugerirse. Borrar un tema con artículos → 204 y el tema queda `is_active=false` (no se borró).
6. **Costo:** ningún test ni paso toca Gemini/Groq (`CLAUDE.md`). El clasificador es regex puro.
7. **Sin commits:** `git status` muestra los archivos nuevos/modificados sin commitear; el usuario decide.

---

## Self-Review

- **Cobertura del spec (§F1):** `topics` jerárquico ✔ (Task 1). `article_topics` N:M con score + evidencia ✔ (Task 1). Clasificador por reglas/keywords sobre el catálogo, sin LLM ✔ (Task 3). Endpoint de frecuencia por día (R7) ✔ (Task 5, `frequency_by_topic`). "`main_topic` no se tira" ✔ (no se toca; es input del clasificador y del backfill). Capa semántica → explícitamente Follow-up. Subtemas (R6) → modelo listo, UI en Follow-up.
- **Placeholders:** `SEED_TOPICS` es un placeholder **de datos** (marcado como tal, con contenido real funcional para tests/demo), no un placeholder de plan. Todo paso de código tiene el código. Los puntos "seguir el molde de X" apuntan a un archivo concreto y a funciones concretas ya leídas; las firmas nuevas están todas declaradas en los bloques **Interfaces**.
- **Consistencia de tipos:** `classify(title, body, keywords, main_topic)` — misma firma en Tasks 3, 6, 7, 8, 10. `TopicMatch(topic_id, score, evidence)` — usada igual en todos. `ArticleTopic(article_id, topic_id, score, origin, evidence)` — mismos campos en modelo (T1), save (T7), pipeline (T8), backfill (T10). `topic_store.resolve` / `get_catalog` / `invalidate_cache` — firmas fijadas en T2 y usadas sin variación. `CatalogTopic.path` se usa en T6 (SuggestedTopic.path) y T9 (filtro) — presente en el dataclass de T2.
- **Ajuste sobre el diseño inicial:** Task 8 NO propaga un matcher por el árbol de llamadas de `pipeline.run()` como decía el borrador; la caché de módulo del clasificador ya evita reconsultar la BD, así que `_persist` llama `classify()` directo. Menos superficie, mismo efecto.
