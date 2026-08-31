# Filtros de Reportes: URL compartible, conteos por faceta y vistas guardadas — Plan de implementación

> **Para agentes:** SUB-SKILL REQUERIDA: usa superpowers:subagent-driven-development (recomendado) o superpowers:executing-plans para ejecutar este plan tarea por tarea. Los pasos usan checkbox (`- [ ]`) para seguimiento.

**Goal:** Que el estado de filtrado del tab de Reportes viva en la URL (compartible y superviviente al botón Atrás), que cada opción de filtro diga cuántos reportes hay detrás, que los 14 controles dejen de ser un muro plano, y que una combinación de filtros de uso frecuente se pueda guardar con nombre.

**Caso de uso que lo define:** El admin filtra «Negativo + Santiago + últimos 30 días», ve que el desplegable de Encuadre dice «Denuncia (12)» y «Crecimiento (0, deshabilitado)», elige Denuncia, abre uno de los reportes, vuelve con el botón Atrás y **sus filtros siguen puestos**. Copia la URL y se la pasa a un documentalista, que ve exactamente la misma tabla. Como esa combinación la revisa todas las semanas, la guarda como «Denuncias Santiago».

**Architecture:** El estado de filtrado hoy vive en tres `useState` de `ReportsPage` (`filters`, `hardData`, `page`), así que se pierde en cada navegación y no se puede compartir. El plan lo mueve a **la URL como única fuente de verdad**, con un módulo puro (`report-filters.ts`) que serializa y valida en ambos sentidos, y un hook (`use-report-filters.ts`) que lo enchufa a `useSearchParams`. Del lado del servidor, `GET /api/articles` y `GET /api/articles/filters` pasan a compartir **un mismo objeto de filtros** (`ArticleFilterParams`) para que los conteos por faceta se calculen sobre exactamente el mismo universo que la tabla; los conteos usan semántica de búsqueda facetada estándar (cada dimensión se cuenta ignorando su propio filtro).

**Tech Stack:** Python 3.13, FastAPI 0.141, SQLAlchemy 2.0, Pydantic 2, pytest. React 19, react-router-dom, TanStack Query, Vitest + Testing Library, `localStorage`.

**Spec:** No hay documento de requerimientos previo. Este plan **es** la especificación; las decisiones de alcance están en «Decisiones» y salieron de la sesión de acotación con el usuario (2026-08-30).

---

## Global Constraints

- **Rama `dev`**, nunca `main`. No crear branches ni worktrees salvo petición explícita (`CLAUDE.md`).
- **NO hacer commits.** `CLAUDE.md` es explícito: los commits los hace el usuario a mano. Ninguna tarea de este plan termina en `git commit` — terminan dejando el working tree verificado. **Si estás ejecutando este plan, no commitees aunque tu skill de ejecución lo sugiera.**
- **Nunca llamar a la API de Gemini** en pruebas ni scripts (cuesta dinero). Este plan no toca analizadores.
- **Tres motores de BD objetivo**: PostgreSQL (producción), SQLite (dev/tests) y SQL Server (cliente). Nada de SQL específico de un motor.
- **Sin migración Alembic.** Este plan no agrega ni altera columnas: todos los filtros nuevos son de lectura sobre columnas existentes.
- **Comandos de verificación** (desde la raíz del repo):
  - Backend: `.venv/bin/python -m pytest -q`
  - Lint/tipos backend: `.venv/bin/ruff check src/odin/ tests/` y `.venv/bin/mypy`
  - Frontend: `cd frontend && npx tsc -b && npm test && npm run lint`
  - Tipos generados: `cd frontend && npm run generate:types` (corre `scripts/generate_openapi.py` y regenera `src/lib/api-types.ts`)
  - `ruff format` está **apagado a propósito** en este repo (ver `.pre-commit-config.yaml`): no lo ejecutes.
- **Estado al empezar (medido 2026-08-30):** 565 pruebas de backend y 121 de frontend en verde. Cualquier tarea que las baje de ahí está incompleta.
- **Hay trabajo sin commitear en el working tree**: el filtro `topic` (texto libre con sugerencias sobre `main_topic`) ya está implementado end-to-end en `routers/articles.py`, `article_service.py`, `FilterBar.tsx`, `ReportsPage.tsx` y `tests/api/test_api_filters.py`. **Este plan lo da por hecho y construye encima.** No lo re-implementes ni lo reviertas.

## Decisiones

Se toman aquí para que ninguna tarea tenga que improvisarlas:

- **La URL es la única fuente de verdad del filtrado.** No hay `useState` espejo. Todo lo que cambia la vista (filtros, orden, página) se escribe en el query string y se vuelve a leer de ahí. Es lo que hace que compartir el enlace y el botón Atrás funcionen sin código extra.
- **Los filtros escriben con `replace`, la paginación con `push`.** Teclear «agua» generaría cuatro entradas de historial y el botón Atrás habría que pulsarlo una vez por letra. Pasar de página sí es un salto que la persona espera poder deshacer.
- **Los valores por defecto no se escriben en la URL.** `sort=published_at`, `order=desc` y `page=1` se omiten, para que la vista limpia sea `/reports` y no `/reports?sort=published_at&order=desc&page=1`.
- **La URL se valida al leer, no se confía.** Un `?sort=password_hash` pegado a mano hoy provocaría un 422 del backend y dejaría la página en estado de error; el módulo de serialización lo descarta y cae al valor por defecto. Lo mismo con fechas mal formadas (el backend las ignora en silencio, así que el filtro se vería puesto sin estar aplicado) e ids no numéricos.
- **Los conteos por faceta ignoran el filtro de su propia dimensión.** Si al elegir «Negativo» se contara también ese filtro, «Positivo» y «Neutro» quedarían en 0 y el desplegable se volvería inútil justo después de usarlo. El número que hace falta es «cuántos habría si cambiara esta opción».
- **Los conteos van en un objeto aparte (`counts`), no incrustados en las listas de opciones.** `facets.topics` lo consume además el formulario manual (`NewReportPage.tsx:207`), que no quiere saber nada de conteos. Con `counts` separado, sumar conteos no cambia ningún tipo existente.
- **Las listas de opciones NO se recortan por los filtros activos; solo se deshabilitan las de conteo cero.** Que una opción desaparezca del desplegable al elegir otra cosa desorienta más de lo que ayuda.
- **La opción actualmente seleccionada nunca se deshabilita**, aunque su conteo sea 0 — si no, no habría forma de ver qué está puesto ni de quitarlo con el teclado.
- **`has_hard_data` deja de ser estado separado.** Hoy `ReportsPage` lo lleva en un `useState<HardDataFilter>` aparte porque es booleano y el resto son strings. Al serializar a URL hay que convertirlo igual, así que se integra al objeto de filtros como `boolean | undefined` y desaparecen `hardData`/`onHardDataChange`.
- **Las vistas guardadas van en `localStorage`, no en el servidor.** Una tabla `saved_views` + CRUD + migración es prácticamente un subproyecto; `localStorage` cubre el caso «esta combinación la reviso todas las semanas» sin backend. Como la URL ya es compartible, compartir una vista con otra persona es pegar el enlace.
- **Fuera de alcance en este plan** (decisión explícita del usuario, no olvido): multi-selección de valores (`sentiment=NEG&sentiment=NEU`), filtros por campos que hoy no se filtran (`section`, `media_stance`, `sentiment_basis`, actores canónicos, rango sobre `analyzed_on`, `analyzer_name`, `content_flags`), y filtros «sin valor» (sin encuadre / sin documentalista / sin lugar). El backend queda preparado —`ArticleFilterParams` es el único sitio donde habría que agregarlos— pero no se implementan aquí.

## Estructura de archivos

**Backend**

| Archivo | Responsabilidad |
|---|---|
| `src/odin/api/filters.py` *(nuevo)* | `ArticleFilterParams`: el juego de filtros como un solo objeto, usado como dependencia por los dos endpoints que los aceptan. |
| `src/odin/api/schemas.py` *(modificar)* | `FacetCounts` + campo `counts` en `ArticleFiltersResponse`. |
| `src/odin/api/routers/articles.py` *(modificar)* | Los dos endpoints declaran `ArticleFilterParams` en vez de repetir 15 parámetros. |
| `src/odin/services/article_service.py` *(modificar)* | `_apply_article_filters` y `list_articles` toman el objeto; `article_filters` calcula conteos. |
| `tests/api/test_article_filter_params.py` *(nuevo)* | Que el objeto compartido traduzca a las condiciones correctas. |
| `tests/api/test_api_facet_counts.py` *(nuevo)* | Semántica de los conteos. |

**Frontend**

| Archivo | Responsabilidad |
|---|---|
| `frontend/src/lib/report-filters.ts` *(nuevo)* | Módulo **puro**: tipos de la vista, serialización URL ↔ vista con validación, conteo de filtros activos, descriptores de chips. Sin React. |
| `frontend/src/lib/report-filters.test.ts` *(nuevo)* | Pruebas del módulo puro. |
| `frontend/src/lib/use-report-filters.ts` *(nuevo)* | Hook que enchufa el módulo a `useSearchParams`, más el debounce de campos de texto. |
| `frontend/src/lib/use-report-filters.test.tsx` *(nuevo)* | Pruebas del hook contra `MemoryRouter`. |
| `frontend/src/lib/filter-presets.ts` *(nuevo)* | Lectura/escritura de vistas guardadas en `localStorage`, a prueba de excepciones. |
| `frontend/src/lib/filter-presets.test.ts` *(nuevo)* | |
| `frontend/src/components/reports/ActiveFilterChips.tsx` *(nuevo)* | Fila de chips de lo que está filtrado, cada uno con su ✕. |
| `frontend/src/components/reports/ActiveFilterChips.test.tsx` *(nuevo)* | |
| `frontend/src/components/reports/FilterSelect.tsx` *(nuevo)* | El `<Select>` de filtro con su opción «todos» y, más adelante, su conteo. Sustituye siete bloques casi idénticos de `FilterBar`. |
| `frontend/src/components/reports/FilterPresets.tsx` *(nuevo)* | Aplicar / guardar / borrar vistas. |
| `frontend/src/components/reports/FilterPresets.test.tsx` *(nuevo)* | |
| `frontend/src/components/reports/FilterBar.tsx` *(modificar)* | Fila de básicos + panel «Más filtros» colapsable + chips + presets. |
| `frontend/src/pages/ReportsPage.tsx` *(modificar)* | Deja de tener estado propio de filtrado; consume el hook. |
| `frontend/src/lib/odin-api.ts` *(modificar)* | `getArticleFilterOptions` acepta filtros. |
| `frontend/src/lib/queries/articles.ts` *(modificar)* | `useArticleFilterOptions(filters)` con clave de caché por filtros. |
| `frontend/src/lib/api-types.ts` *(regenerar)* | |

---

## Task 1: Un solo objeto de filtros compartido por los dos endpoints

Refactor puro, sin cambio de comportamiento observable. Existe para que la Tarea 2 no tenga que duplicar quince parámetros: dos declaraciones separadas del mismo juego de filtros se desincronizan tarde o temprano, y el síntoma sería un desplegable que dice «Negativo (42)» sobre un universo distinto del que muestra la tabla.

**Files:**
- Create: `src/odin/api/filters.py`
- Modify: `src/odin/api/routers/articles.py:27-78`
- Modify: `src/odin/services/article_service.py:80-165` y `:290-330`
- Test: `tests/api/test_article_filter_params.py` *(nuevo)*

**Interfaces:**
- Produces: `odin.api.filters.ArticleFilterParams`, dataclass con los campos `q, source, sentiment, framing, headline_intent, lead_orientation, source_quality, has_hard_data, entity, topic, locality, documentalist, date_from, date_to`, todos con default `None`.
- Produces: `article_service._apply_article_filters(stmt, f: ArticleFilterParams)` y `article_service.list_articles(f: ArticleFilterParams, *, sort, order, limit, offset) -> ArticleListResponse`.

- [ ] **Step 1: Escribir la prueba que falla**

Crea `tests/api/test_article_filter_params.py`:

```python
"""El objeto de filtros compartido por GET /api/articles y
GET /api/articles/filters. Se prueba contra el SQL generado (no contra la BD)
porque lo que hay que fijar aquí es la traducción campo -> condición: que un
filtro nuevo no se quede sin aplicar, y que uno vacío no filtre nada.
"""
from __future__ import annotations

from sqlalchemy import select

from odin.api.filters import ArticleFilterParams
from odin.db.models import Article
from odin.services.article_service import _apply_article_filters


def _sql(f: ArticleFilterParams) -> str:
    return str(_apply_article_filters(select(Article), f))


def test_params_vacios_no_agregan_where():
    assert "WHERE" not in _sql(ArticleFilterParams())


def test_source_acepta_varios_valores():
    assert "articles.source IN" in _sql(ArticleFilterParams(source=["hoy", "el_dia"]))


def test_sentiment_compara_por_igualdad():
    assert "articles.overall_sentiment =" in _sql(ArticleFilterParams(sentiment="NEG"))


def test_has_hard_data_false_si_filtra():
    # False es un valor legítimo, no "sin filtro": comprobar con `if
    # f.has_hard_data:` en vez de `is not None` dejaría "Sin datos duros"
    # sin efecto.
    assert "articles.has_hard_data" in _sql(ArticleFilterParams(has_hard_data=False))


def test_documentalist_cero_no_se_confunde_con_ausente():
    assert "articles.documentalist_id" in _sql(ArticleFilterParams(documentalist=0))
```

- [ ] **Step 2: Correr la prueba para verificar que falla**

Run: `.venv/bin/python -m pytest tests/api/test_article_filter_params.py -q`
Expected: FAIL con `ModuleNotFoundError: No module named 'odin.api.filters'`

- [ ] **Step 3: Crear `src/odin/api/filters.py`**

```python
"""Los filtros del listado de reportes, como un único objeto.

Dos endpoints tienen que aceptar EXACTAMENTE el mismo juego de filtros:
`GET /api/articles` (la página de resultados) y `GET /api/articles/filters`
(los conteos por faceta, que dependen de qué más está filtrado). Declararlos
por separado garantiza que se desincronicen: un filtro nuevo entraría en el
listado y no en los conteos, y el desplegable diría "Denuncia (12)" sobre un
universo distinto del que muestra la tabla.

Es un dataclass y no un `BaseModel`: FastAPI lo resuelve con `Depends()`
mapeando cada campo a un parámetro de query, y así los endpoints pueden
declarar además sus propios `sort`/`order`/`limit`/`offset` sin que el modelo
los vea como campos extra.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Annotated

from fastapi import Query


@dataclass
class ArticleFilterParams:
    q: str | None = None
    # El único multivalor de hoy: `?source=hoy&source=el_dia` se ORea. El
    # resto son de valor único a propósito (ver "Decisiones" del plan).
    source: Annotated[list[str] | None, Query()] = None
    sentiment: str | None = None
    framing: str | None = None
    headline_intent: str | None = None
    lead_orientation: str | None = None
    source_quality: str | None = None
    has_hard_data: bool | None = None
    entity: str | None = None
    topic: str | None = None
    locality: int | None = None
    documentalist: int | None = None
    date_from: str | None = None
    date_to: str | None = None
```

- [ ] **Step 4: Reescribir `_apply_article_filters` para que tome el objeto**

En `src/odin/services/article_service.py`, sustituye la firma y el cuerpo de `_apply_article_filters` (líneas 80-165). El cuerpo de cada condición **no cambia**: solo pasa de `sentiment` a `f.sentiment`, etc. Conserva los comentarios existentes tal cual están (explican por qué `entity` y `locality` usan `EXISTS` y no `JOIN`).

```python
def _apply_article_filters(stmt, f: ArticleFilterParams):
    conditions: list[ColumnElement[bool]] = []
    if f.source:
        conditions.append(Article.source.in_(f.source))
    if f.sentiment:
        conditions.append(Article.overall_sentiment == f.sentiment)
    if f.framing:
        conditions.append(Article.framing == f.framing)
    if f.headline_intent:
        conditions.append(Article.headline_intent == f.headline_intent)
    if f.lead_orientation:
        conditions.append(Article.lead_orientation == f.lead_orientation)
    if f.source_quality:
        conditions.append(Article.source_quality == f.source_quality)
    if f.has_hard_data is not None:
        conditions.append(Article.has_hard_data == f.has_hard_data)
    if f.date_from:
        parsed = _parse_date(f.date_from)
        if parsed:
            conditions.append(Article.published_at >= parsed)
    if f.date_to:
        parsed = _parse_date(f.date_to)
        if parsed:
            # inclusivo: hasta el final del día indicado
            conditions.append(Article.published_at < parsed + timedelta(days=1))
    if f.q:
        conditions.append(
            or_(
                accent_insensitive_contains(Article.title, f.q),
                accent_insensitive_contains(Article.main_topic, f.q),
                accent_insensitive_contains(Article.topic_keywords, f.q),
            )
        )
    if f.topic:
        conditions.append(accent_insensitive_contains(Article.main_topic, f.topic))
    if f.entity:
        # EXISTS y no JOIN: un artículo con dos entidades que matchean saldría
        # dos veces, y taparlo con SELECT DISTINCT rompe en PostgreSQL —el
        # ORDER BY del listado incluye la expresión `published_at IS NULL`, que
        # bajo DISTINCT tiene que estar en la lista de selección—. El EXISTS no
        # multiplica filas, así que no hace falta deduplicar nada.
        conditions.append(
            select(1)
            .select_from(Entity)
            .where(
                Entity.article_id == Article.id,
                accent_insensitive_contains(Entity.name, f.entity),
            )
            .exists()
        )
    if f.documentalist is not None:
        conditions.append(Article.documentalist_id == f.documentalist)
    if f.locality is not None:
        # Filtrar por un lugar incluye lo que cuelga de él: pedir "Santiago"
        # trae también las notas marcadas en Tamboril. La relación
        # ancestro/descendiente ya está materializada en `path`, así que basta
        # comparar prefijos — sin CTE recursivo, que además no se escribe igual
        # en los tres motores objetivo (PostgreSQL, SQLite y SQL Server).
        target_path = select(Locality.path).where(Locality.id == f.locality).scalar_subquery()
        # EXISTS por el mismo motivo que en `entity`: una nota marcada a la vez
        # en Santiago y en Tamboril matchea dos veces al filtrar por Santiago.
        conditions.append(
            select(1)
            .select_from(ArticleLocality)
            .join(Locality, Locality.id == ArticleLocality.locality_id)
            .where(
                ArticleLocality.article_id == Article.id,
                Locality.path.like(target_path + "%"),
            )
            .exists()
        )
    if conditions:
        stmt = stmt.where(and_(*conditions))
    return stmt
```

Añade el import arriba del archivo, junto a los demás de `odin.api`:

```python
from odin.api.filters import ArticleFilterParams
```

> **Nota de la línea del `topic`:** si el bloque `if f.topic:` que hay en el working tree trae comentarios explicando por qué usa «contiene» y no igualdad, consérvalos.

- [ ] **Step 5: Reescribir `list_articles` para que tome el objeto**

Sustituye la firma (líneas 290-330 aprox.) por:

```python
def list_articles(
    f: ArticleFilterParams,
    *,
    sort: str | None,
    order: str | None,
    limit: int,
    offset: int,
) -> ArticleListResponse:
    limit = max(1, min(limit, 100))
    offset = max(0, offset)

    session = deps.get_session()
    try:
        base = _apply_article_filters(select(Article), f)
        total = session.scalar(select(func.count()).select_from(base.subquery())) or 0
        ...
```

El resto del cuerpo (el `order_by`, los `selectinload`, el `return`) queda igual.

- [ ] **Step 6: Adaptar el router**

En `src/odin/api/routers/articles.py`, sustituye la firma y el cuerpo de `list_articles` (líneas 27-78) por:

```python
@router.get(
    "/api/articles",
    dependencies=[Depends(auth.require_auth)],
    response_model=ArticleListResponse,
)
def list_articles(
    filters: ArticleFilterParams = Depends(),
    sort: str | None = None,
    order: str | None = None,
    limit: int = 20,
    offset: int = 0,
):
    """Lista reportes guardados con filtros combinables. Devuelve resúmenes
    (sin cuerpo ni entidades detalladas); usa GET /api/articles/{id} para el
    reporte completo.

    Los filtros se declaran en `odin.api.filters.ArticleFilterParams`, que se
    comparte con GET /api/articles/filters para que los conteos por faceta se
    calculen sobre el mismo universo que esta lista.

    `locality` es el id de un lugar del catálogo e incluye su subárbol: filtrar
    por la provincia Santiago trae también lo marcado en sus municipios.
    `documentalist` es el id del documentalista que dejó guardado el reporte.

    `sort` es la columna (`published_at`, `source`, `analyzed_on`) y `order`
    la dirección (`asc`/`desc`). "recent" y "oldest" siguen aceptándose como
    alias del contrato anterior, donde `sort` mezclaba ambas cosas.
    """
    return article_service.list_articles(
        filters, sort=sort, order=order, limit=limit, offset=offset
    )
```

Y añade el import: `from odin.api.filters import ArticleFilterParams`. `Query` ya no se usa en este archivo — quítalo del import de `fastapi` si `ruff` lo marca como no usado.

- [ ] **Step 7: Correr las pruebas nuevas y toda la suite**

Run: `.venv/bin/python -m pytest tests/api/test_article_filter_params.py -q`
Expected: PASS (5 pruebas)

Run: `.venv/bin/python -m pytest -q`
Expected: PASS, 570 pruebas (565 previas + 5 nuevas). Las de `tests/api/test_api_filters.py` y `test_api_sorting.py` pasan sin tocarlas: entran por HTTP, y el contrato del query string no cambió.

- [ ] **Step 8: Lint y tipos**

Run: `.venv/bin/ruff check src/odin/ tests/ && .venv/bin/mypy`
Expected: sin errores.

---

## Task 2: Conteos por faceta en `GET /api/articles/filters`

**Files:**
- Modify: `src/odin/api/schemas.py:369-380`
- Modify: `src/odin/api/routers/articles.py` (endpoint `article_filters`)
- Modify: `src/odin/services/article_service.py` (función `article_filters`)
- Test: `tests/api/test_api_facet_counts.py` *(nuevo)*

**Interfaces:**
- Consumes: `ArticleFilterParams` (Tarea 1).
- Produces: `ArticleFiltersResponse.counts: FacetCounts`, con las claves `source, sentiment, framing, headline_intent, lead_orientation, source_quality, has_hard_data, documentalist`, cada una un `dict[str, int]`. Las claves de cada diccionario son **strings** (JSON no tiene otras): el id del documentalista viaja como `"7"` y `has_hard_data` como `"true"`/`"false"`. **Un valor ausente del diccionario significa cero.**
- Produces: `GET /api/articles/filters` acepta los mismos parámetros de query que `GET /api/articles`.

- [ ] **Step 1: Escribir la prueba que falla**

Crea `tests/api/test_api_facet_counts.py`:

```python
"""Conteos por faceta de GET /api/articles/filters.

La regla que se fija aquí es la de la búsqueda facetada: cada dimensión se
cuenta ignorando su PROPIO filtro pero respetando los demás. Si se contara
también el suyo, elegir "Negativo" dejaría "Positivo" y "Neutro" en 0 y el
desplegable se volvería inútil justo después de usarlo.
"""
from __future__ import annotations

from datetime import UTC, datetime

from odin.core.auth import create_token
from odin.db.models import Article, User


def _auth_headers():
    token, _ = create_token("tester")
    return {"Authorization": f"Bearer {token}"}


def _article(url: str, **overrides) -> Article:
    defaults = dict(
        source="diario_libre",
        url=url,
        title="Título de prueba",
        body="cuerpo",
        main_topic="tema",
        overall_sentiment="NEU",
        published_at=datetime(2026, 1, 1, tzinfo=UTC),
    )
    defaults.update(overrides)
    return Article(**defaults)


def _counts(api_client, **params):
    resp = api_client.get("/api/articles/filters", params=params, headers=_auth_headers())
    assert resp.status_code == 200, resp.text
    return resp.json()["counts"]


class TestFacetCounts:
    def test_cuenta_por_sentimiento_sin_filtros(self, api_client, sqlite_sessionmaker):
        session = sqlite_sessionmaker()
        session.add_all([
            _article("https://dl.com/1", overall_sentiment="NEG"),
            _article("https://dl.com/2", overall_sentiment="NEG"),
            _article("https://dl.com/3", overall_sentiment="POS"),
        ])
        session.commit()
        session.close()

        assert _counts(api_client)["sentiment"] == {"NEG": 2, "POS": 1}

    def test_una_dimension_ignora_su_propio_filtro(self, api_client, sqlite_sessionmaker):
        session = sqlite_sessionmaker()
        session.add_all([
            _article("https://dl.com/1", overall_sentiment="NEG"),
            _article("https://dl.com/2", overall_sentiment="POS"),
        ])
        session.commit()
        session.close()

        # Con sentiment=NEG puesto, el conteo de sentiment sigue viendo los dos:
        # es lo que permite leer "POS (1)" y saber a qué se cambiaría.
        assert _counts(api_client, sentiment="NEG")["sentiment"] == {"NEG": 1, "POS": 1}

    def test_una_dimension_respeta_los_otros_filtros(self, api_client, sqlite_sessionmaker):
        session = sqlite_sessionmaker()
        session.add_all([
            _article("https://dl.com/1", source="hoy", framing="denuncia"),
            _article("https://dl.com/2", source="hoy", framing="crecimiento"),
            _article("https://dl.com/3", source="listin_diario", framing="denuncia"),
        ])
        session.commit()
        session.close()

        # Filtrando por fuente "hoy", el encuadre solo cuenta esos dos.
        assert _counts(api_client, source="hoy")["framing"] == {
            "denuncia": 1,
            "crecimiento": 1,
        }

    def test_valor_sin_reportes_queda_fuera_del_diccionario(self, api_client, sqlite_sessionmaker):
        session = sqlite_sessionmaker()
        session.add(_article("https://dl.com/1", framing="denuncia"))
        session.commit()
        session.close()

        assert "crecimiento" not in _counts(api_client)["framing"]

    def test_nulos_no_se_cuentan_como_valor(self, api_client, sqlite_sessionmaker):
        # framing es NULL en todo lo que analizó LocalAnalyzer: no es una
        # categoría más, es ausencia de dato.
        session = sqlite_sessionmaker()
        session.add_all([
            _article("https://dl.com/1", framing=None),
            _article("https://dl.com/2", framing="denuncia"),
        ])
        session.commit()
        session.close()

        assert _counts(api_client)["framing"] == {"denuncia": 1}

    def test_has_hard_data_usa_claves_de_texto(self, api_client, sqlite_sessionmaker):
        session = sqlite_sessionmaker()
        session.add_all([
            _article("https://dl.com/1", has_hard_data=True),
            _article("https://dl.com/2", has_hard_data=False),
            _article("https://dl.com/3", has_hard_data=False),
        ])
        session.commit()
        session.close()

        # "true"/"false" en minúscula, que es lo que produce String(boolean) en
        # el cliente: str(True) de Python daría "True" y no casaría nunca.
        assert _counts(api_client)["has_hard_data"] == {"true": 1, "false": 2}

    def test_documentalist_se_indexa_por_id(self, api_client, sqlite_sessionmaker):
        session = sqlite_sessionmaker()
        user = User(
            username="jperez",
            display_name="Juan Pérez",
            password_hash="x",
            role="documentalista",
        )
        session.add(user)
        session.commit()
        session.add(_article("https://dl.com/1", documentalist_id=user.id))
        session.commit()
        uid = user.id
        session.close()

        assert _counts(api_client)["documentalist"] == {str(uid): 1}

    def test_las_listas_de_opciones_no_se_recortan(self, api_client, sqlite_sessionmaker):
        session = sqlite_sessionmaker()
        session.add_all([
            _article("https://dl.com/1", source="hoy"),
            _article("https://dl.com/2", source="listin_diario"),
        ])
        session.commit()
        session.close()

        body = api_client.get(
            "/api/articles/filters", params={"source": "hoy"}, headers=_auth_headers()
        ).json()
        # Las opciones siguen siendo el universo completo aunque haya un filtro
        # puesto: se deshabilitan por conteo, no desaparecen.
        assert {s["value"] for s in body["sources"]} == {"hoy", "listin_diario"}
```

> **Antes de escribir el test de `User`:** confirma los campos obligatorios del modelo con `grep -n "class User" -A 30 src/odin/db/models.py` y ajusta el constructor si difiere (p. ej. si `password_hash` tiene otro nombre).

- [ ] **Step 2: Correr para verificar que falla**

Run: `.venv/bin/python -m pytest tests/api/test_api_facet_counts.py -q`
Expected: FAIL con `KeyError: 'counts'` en todas.

- [ ] **Step 3: Añadir `FacetCounts` a `schemas.py`**

Justo antes de `class ArticleFiltersResponse` (línea 369):

```python
class FacetCounts(BaseModel):
    """Cuántos reportes hay detrás de cada valor de cada filtro facetado.

    Diccionario `valor -> conteo` y NO conteos incrustados en las listas de
    opciones: `sources`, `topics` y compañía las consume también el formulario
    de captura manual (`NewReportPage`), que no quiere saber nada de conteos.
    Manteniéndolos aparte, sumar esto no cambia ningún tipo existente.

    Las claves son siempre strings porque JSON no tiene otras: el id del
    documentalista viaja como "7" y `has_hard_data` como "true"/"false".
    Un valor AUSENTE del diccionario significa cero.
    """

    source: dict[str, int] = {}
    sentiment: dict[str, int] = {}
    framing: dict[str, int] = {}
    headline_intent: dict[str, int] = {}
    lead_orientation: dict[str, int] = {}
    source_quality: dict[str, int] = {}
    has_hard_data: dict[str, int] = {}
    documentalist: dict[str, int] = {}
```

Y en `ArticleFiltersResponse`, añade como último campo:

```python
    counts: FacetCounts = FacetCounts()
```

- [ ] **Step 4: Calcular los conteos en el servicio**

En `src/odin/services/article_service.py`, añade `FacetCounts` al import de `odin.api.schemas`, y encima de `def article_filters()`:

```python
# Dimensiones facetadas: por qué columna agrupar para contar cada filtro. La
# clave es a la vez el nombre del campo en `ArticleFilterParams` (lo usa
# `_facet_counts` para neutralizar el filtro propio) y el nombre del campo en
# `FacetCounts` que consume el frontend.
_FACET_COLUMNS = {
    "source": Article.source,
    "sentiment": Article.overall_sentiment,
    "framing": Article.framing,
    "headline_intent": Article.headline_intent,
    "lead_orientation": Article.lead_orientation,
    "source_quality": Article.source_quality,
    "has_hard_data": Article.has_hard_data,
    "documentalist": Article.documentalist_id,
}


def _facet_key(dimension: str, value) -> str:
    """El valor agrupado, como clave JSON.

    `has_hard_data` se fuerza a "true"/"false" en minúscula: SQLite devuelve
    0/1 en vez de booleanos según el driver, y `str(True)` de Python daría
    "True", que no casa con el `String(boolean)` que produce el cliente.
    """
    if dimension == "has_hard_data":
        return "true" if value else "false"
    return str(value)


def _facet_counts(session, f: ArticleFilterParams) -> FacetCounts:
    """Cuántos reportes caerían en cada valor de cada faceta.

    Para la dimensión D se cuenta con TODOS los filtros activos MENOS el de la
    propia D. Si se aplicara también el suyo, elegir "Negativo" dejaría
    "Positivo" y "Neutro" en 0 y el desplegable se volvería inútil justo
    después de usarlo: el número que hace falta es "cuántos habría si cambiara
    esta opción", no "cuántos hay ahora".

    Son ocho GROUP BY por petición, uno por dimensión, porque cada uno parte de
    un WHERE distinto (el suyo neutralizado) y no hay forma de sacarlos de una
    sola pasada sin un CUBE que no se escribe igual en los tres motores
    objetivo. Se acepta el coste: la petición se dispara una vez por cambio de
    filtro, no por fila.
    """
    counts: dict[str, dict[str, int]] = {}
    for dimension, column in _FACET_COLUMNS.items():
        # Todos los campos facetados usan None como "sin filtro", así que
        # neutralizar el propio es ponerlo a None.
        others = replace(f, **{dimension: None})
        stmt = (
            _apply_article_filters(
                select(column, func.count(Article.id)).select_from(Article), others
            )
            .group_by(column)
        )
        counts[dimension] = {
            _facet_key(dimension, value): total
            # NULL no es una categoría más, es ausencia de dato: `framing` es
            # NULL en todo lo que analizó LocalAnalyzer, y contarlo como valor
            # metería un "None (312)" en el desplegable.
            for value, total in session.execute(stmt).all()
            if value is not None
        }
    return FacetCounts(**counts)
```

Añade arriba del archivo: `from dataclasses import replace`.

Después cambia la firma de `article_filters` y su `return`:

```python
def article_filters(f: ArticleFilterParams) -> ArticleFiltersResponse:
    session = deps.get_session()
    try:
        # ... (los bloques de `sources`, `topics`, `sections` y
        # `documentalists` quedan EXACTAMENTE como están: las listas de
        # opciones son el universo completo y no se recortan por los filtros
        # activos — que una opción desaparezca al elegir otra cosa desorienta
        # más de lo que ayuda. Lo que se recorta es el conteo, y con él se
        # deshabilita en el cliente.)
        return ArticleFiltersResponse(
            sources=sources,
            topics=topics,
            sections=sections,
            sentiments=list(SENTIMENT_VALUES),
            framing=list(FRAMING_VALUES),
            headline_intent=list(HEADLINE_INTENT_VALUES),
            lead_orientation=list(LEAD_ORIENTATION_VALUES),
            source_quality=list(SOURCE_QUALITY_VALUES),
            documentalists=documentalists,
            counts=_facet_counts(session, f),
        )
    finally:
        session.close()
```

- [ ] **Step 5: Pasar los filtros desde el router**

En `src/odin/api/routers/articles.py`:

```python
@router.get(
    "/api/articles/filters",
    dependencies=[Depends(auth.require_auth)],
    response_model=ArticleFiltersResponse,
)
def article_filters(filters: ArticleFilterParams = Depends()):
    """Valores disponibles para poblar los selectores de filtro del frontend,
    más cuántos reportes hay detrás de cada uno.

    Acepta los MISMOS filtros que GET /api/articles: los conteos de `counts`
    son los de la tabla que se está viendo, no los del total histórico. Cada
    dimensión se cuenta ignorando su propio filtro (ver `_facet_counts`).

    Las listas de opciones en cambio son el universo completo: fuentes,
    secciones y temas salen de lo ya guardado, y el resto son enumeraciones
    fijas del análisis.
    """
    return article_service.article_filters(filters)
```

- [ ] **Step 6: Correr las pruebas**

Run: `.venv/bin/python -m pytest tests/api/test_api_facet_counts.py -q`
Expected: PASS (8 pruebas)

Run: `.venv/bin/python -m pytest -q`
Expected: PASS, 578 pruebas.

- [ ] **Step 7: Regenerar los tipos del frontend**

Run: `cd frontend && npm run generate:types`
Expected: `src/lib/api-types.ts` cambia: `ArticleFiltersResponse` gana `counts` y aparece el schema `FacetCounts`.

Run: `cd frontend && npx tsc -b && npm test`
Expected: PASS, 121 pruebas. `counts` tiene default, así que los mocks de faceta existentes (`FACET` en `LocalityFilter.test.tsx`, `NewReportPage.test.tsx`) siguen tipando — están casteados con `as unknown as ArticleFilterOptions`.

- [ ] **Step 8: Lint y tipos backend**

Run: `.venv/bin/ruff check src/odin/ tests/ && .venv/bin/mypy`
Expected: sin errores.

---

## Task 3: El módulo puro de serialización de la vista

Sin React y sin red: solo tipos, traducción URL ↔ vista con validación, y los descriptores de los chips. Se hace primero y aparte porque es donde vive toda la lógica que se puede equivocar, y así se prueba sin montar componentes.

**Files:**
- Create: `frontend/src/lib/report-filters.ts`
- Test: `frontend/src/lib/report-filters.test.ts`

**Interfaces:**
- Produces: `ReportFilters`, `ReportView`, `SortField`, `SortOrder`, `EMPTY_VIEW`, `DEFAULT_SORT`, `DEFAULT_ORDER`, `BASIC_KEYS`, `ADVANCED_KEYS`.
- Produces: `searchParamsToView(sp: URLSearchParams): ReportView`, `viewToSearchParams(view: ReportView): URLSearchParams`, `toListParams(view: ReportView, pageSize: number): ArticleListParams`, `countActiveFilters(f: ReportFilters): number`, `pruneFilters(f: ReportFilters): ReportFilters`, `activeFilterChips(f: ReportFilters, labels?: ChipLabels): FilterChip[]`.
- Produces: `type FilterChip = { key: keyof ReportFilters; label: string; value: string }` y `type ChipLabels = { sources?: {value,label}[]; documentalists?: {id,display_name}[]; localityName?: (id: number) => string | undefined }`.

- [ ] **Step 1: Escribir las pruebas que fallan**

Crea `frontend/src/lib/report-filters.test.ts`:

```ts
import { describe, expect, it } from "vitest"
import {
  activeFilterChips,
  countActiveFilters,
  EMPTY_VIEW,
  searchParamsToView,
  toListParams,
  viewToSearchParams,
  type ReportView,
} from "@/lib/report-filters"

const sp = (s: string) => new URLSearchParams(s)

describe("searchParamsToView", () => {
  it("una URL vacía da la vista por defecto", () => {
    expect(searchParamsToView(sp(""))).toEqual(EMPTY_VIEW)
  })

  it("lee texto, número, fecha y booleano con su tipo", () => {
    const view = searchParamsToView(
      sp("q=agua&locality=42&date_from=2026-01-01&has_hard_data=true")
    )
    expect(view.filters).toEqual({
      q: "agua",
      locality: 42,
      date_from: "2026-01-01",
      has_hard_data: true,
    })
  })

  it("has_hard_data=false es un filtro, no ausencia de filtro", () => {
    expect(searchParamsToView(sp("has_hard_data=false")).filters.has_hard_data).toBe(false)
  })

  it("descarta un sort fuera de la lista blanca", () => {
    // Sin esto, un ?sort= pegado a mano provoca un 422 del backend y deja la
    // página entera en estado de error.
    expect(searchParamsToView(sp("sort=password_hash")).sort).toBe("published_at")
  })

  it("descarta una fecha mal formada", () => {
    // El backend ignora en silencio lo que no parsea, así que el filtro se
    // vería puesto en la barra sin estar aplicado.
    expect(searchParamsToView(sp("date_from=ayer")).filters.date_from).toBeUndefined()
  })

  it("descarta un id no numérico", () => {
    expect(searchParamsToView(sp("locality=abc")).filters.locality).toBeUndefined()
  })

  it("la página viaja 1-based y se lee 0-based", () => {
    expect(searchParamsToView(sp("page=3")).page).toBe(2)
    expect(searchParamsToView(sp("page=0")).page).toBe(0)
  })
})

describe("viewToSearchParams", () => {
  it("no escribe los valores por defecto", () => {
    expect(viewToSearchParams(EMPTY_VIEW).toString()).toBe("")
  })

  it("es simétrico con searchParamsToView", () => {
    const view: ReportView = {
      filters: { q: "agua", sentiment: "NEG", locality: 42, has_hard_data: false },
      sort: "analyzed_on",
      order: "asc",
      page: 2,
    }
    expect(searchParamsToView(viewToSearchParams(view))).toEqual(view)
  })

  it("produce siempre el mismo orden de claves", () => {
    // La misma vista tiene que dar la misma URL: si no, dos personas comparten
    // enlaces distintos y TanStack Query cachea la misma consulta dos veces.
    const a = viewToSearchParams({ ...EMPTY_VIEW, filters: { q: "a", source: "hoy" } })
    const b = viewToSearchParams({ ...EMPTY_VIEW, filters: { source: "hoy", q: "a" } })
    expect(a.toString()).toBe(b.toString())
  })
})

describe("toListParams", () => {
  it("traduce la página a offset", () => {
    expect(toListParams({ ...EMPTY_VIEW, page: 2 }, 12)).toMatchObject({
      limit: 12,
      offset: 24,
      sort: "published_at",
      order: "desc",
    })
  })
})

describe("countActiveFilters", () => {
  it("no cuenta el orden ni la página", () => {
    expect(countActiveFilters({ q: "agua", sentiment: "NEG" })).toBe(2)
  })

  it("cuenta has_hard_data=false", () => {
    expect(countActiveFilters({ has_hard_data: false })).toBe(1)
  })

  it("una vista limpia tiene cero", () => {
    expect(countActiveFilters({})).toBe(0)
  })
})

describe("activeFilterChips", () => {
  it("traduce los enums a su etiqueta en español", () => {
    const chips = activeFilterChips({ sentiment: "NEG", framing: "denuncia" })
    expect(chips).toEqual([
      { key: "sentiment", label: "Sentimiento", value: "Negativo" },
      { key: "framing", label: "Encuadre", value: "Denuncia" },
    ])
  })

  it("resuelve fuente, documentalista y lugar con el contexto que recibe", () => {
    const chips = activeFilterChips(
      { source: "hoy", documentalist: 7, locality: 42 },
      {
        sources: [{ value: "hoy", label: "Hoy" }],
        documentalists: [{ id: 7, display_name: "Juan Pérez" }],
        localityName: (id) => (id === 42 ? "Santiago" : undefined),
      }
    )
    // Los chips salen en el mismo orden en que aparecen los controles en la
    // barra: lugar antes que fuente, documentalista al final.
    expect(chips.map((c) => c.value)).toEqual(["Santiago", "Hoy", "Juan Pérez"])
  })

  it("cae al id crudo cuando el catálogo todavía no cargó", () => {
    // Las facetas y el árbol de lugares llegan por red: sin este fallback el
    // chip parpadearía vacío en el primer render de un enlace compartido.
    expect(activeFilterChips({ locality: 42 })[0].value).toBe("#42")
  })

  it("distingue con y sin datos duros", () => {
    expect(activeFilterChips({ has_hard_data: true })[0].value).toBe("Con datos duros")
    expect(activeFilterChips({ has_hard_data: false })[0].value).toBe("Sin datos duros")
  })
})
```

- [ ] **Step 2: Correr para verificar que falla**

Run: `cd frontend && npx vitest run src/lib/report-filters.test.ts`
Expected: FAIL — `Failed to resolve import "@/lib/report-filters"`.

- [ ] **Step 3: Escribir `frontend/src/lib/report-filters.ts`**

```ts
/**
 * La vista de la tabla de Reportes (qué se filtra, cómo se ordena, en qué
 * página), y su traducción a query string.
 *
 * Módulo puro a propósito: es donde vive toda la lógica que se puede
 * equivocar —validar lo que llega en la URL, decidir qué se omite, armar los
 * chips— y así se prueba sin montar un router ni un componente.
 *
 * La URL es la ÚNICA fuente de verdad del filtrado (no hay `useState`
 * espejo): es lo que hace que compartir el enlace y el botón Atrás funcionen
 * sin código extra.
 */
import {
  FRAMING_LABELS,
  HEADLINE_LABELS,
  LEAD_LABELS,
  SENTIMENT_LABELS,
  SOURCE_LABELS,
} from "@/lib/labels"
import type { ArticleListParams } from "@/lib/odin-api"

export type SortField = "published_at" | "source" | "analyzed_on"
export type SortOrder = "asc" | "desc"

/** Los filtros propiamente dichos: sin `sort`/`order`/`limit`/`offset`, que
 *  son CÓMO se muestra el resultado y no QUÉ se busca. Separarlos es lo que
 *  permite contar filtros activos, dibujar chips y guardar vistas sin tener
 *  que excluir `sort` a mano en cada sitio. */
export type ReportFilters = {
  q?: string
  entity?: string
  topic?: string
  source?: string
  sentiment?: string
  framing?: string
  headline_intent?: string
  lead_orientation?: string
  source_quality?: string
  has_hard_data?: boolean
  locality?: number
  documentalist?: number
  date_from?: string
  date_to?: string
}

export type ReportView = {
  filters: ReportFilters
  sort: SortField
  order: SortOrder
  /** 0-based, como el resto del código. En la URL viaja 1-based. */
  page: number
}

export const DEFAULT_SORT: SortField = "published_at"
export const DEFAULT_ORDER: SortOrder = "desc"
export const EMPTY_VIEW: ReportView = {
  filters: {},
  sort: DEFAULT_SORT,
  order: DEFAULT_ORDER,
  page: 0,
}

/** Los que se ven siempre en la barra. */
export const BASIC_KEYS = ["q", "entity", "topic", "locality", "source", "date_from", "date_to"] as const
/** Los que viven dentro de «Más filtros». */
export const ADVANCED_KEYS = [
  "sentiment",
  "framing",
  "headline_intent",
  "lead_orientation",
  "source_quality",
  "has_hard_data",
  "documentalist",
] as const

const SORT_FIELDS: readonly SortField[] = ["published_at", "source", "analyzed_on"]
const ORDERS: readonly SortOrder[] = ["asc", "desc"]

// Orden fijo de las claves al escribir la URL. Importa por dos razones: la
// misma vista sale siempre como la misma URL (dos personas comparten el mismo
// enlace), y esa URL alimenta la clave de caché de TanStack Query — con orden
// variable, la misma consulta se pediría dos veces al servidor.
const TEXT_KEYS = [
  "q",
  "entity",
  "topic",
  "source",
  "sentiment",
  "framing",
  "headline_intent",
  "lead_orientation",
  "source_quality",
] as const
const DATE_KEYS = ["date_from", "date_to"] as const
const NUMBER_KEYS = ["locality", "documentalist"] as const

const DATE_RE = /^\d{4}-\d{2}-\d{2}$/

export function searchParamsToView(sp: URLSearchParams): ReportView {
  // Se arma como Record y se castea al final: asignar por clave de unión
  // (`filters[key] = v`) no le gusta a TypeScript aunque todas las claves
  // tengan el mismo tipo, y el cast en un solo sitio es más honesto que un
  // `as any` por línea.
  const filters: Record<string, unknown> = {}

  for (const key of TEXT_KEYS) {
    const v = sp.get(key)?.trim()
    if (v) filters[key] = v
  }
  for (const key of DATE_KEYS) {
    const v = sp.get(key)?.trim()
    // Una fecha con formato raro se descarta en vez de viajar al backend: allí
    // `_parse_date` la ignora en silencio, así que el filtro se vería puesto
    // en la barra sin estar aplicado.
    if (v && DATE_RE.test(v)) filters[key] = v
  }
  for (const key of NUMBER_KEYS) {
    const raw = sp.get(key)
    const n = Number(raw)
    if (raw !== null && raw.trim() !== "" && Number.isInteger(n) && n >= 0) filters[key] = n
  }
  const hard = sp.get("has_hard_data")
  // `false` es un filtro ("sin datos duros"), no ausencia de filtro.
  if (hard === "true" || hard === "false") filters.has_hard_data = hard === "true"

  // Fuera de la lista blanca se cae al default: el backend responde 422 a un
  // campo de orden desconocido, y una URL manipulada dejaría la página entera
  // en estado de error en vez de simplemente ordenada por lo de siempre.
  const sort = SORT_FIELDS.find((f) => f === sp.get("sort")) ?? DEFAULT_SORT
  const order = ORDERS.find((o) => o === sp.get("order")) ?? DEFAULT_ORDER

  // En la URL la página es 1-based (lo que lee una persona); dentro, 0-based.
  const page = Math.max(0, (Number(sp.get("page")) || 1) - 1)

  return { filters: filters as ReportFilters, sort, order, page }
}

export function viewToSearchParams(view: ReportView): URLSearchParams {
  const sp = new URLSearchParams()
  for (const key of TEXT_KEYS) {
    const v = view.filters[key]
    if (v) sp.set(key, v)
  }
  for (const key of DATE_KEYS) {
    const v = view.filters[key]
    if (v) sp.set(key, v)
  }
  for (const key of NUMBER_KEYS) {
    const v = view.filters[key]
    if (v !== undefined) sp.set(key, String(v))
  }
  if (view.filters.has_hard_data !== undefined) {
    sp.set("has_hard_data", String(view.filters.has_hard_data))
  }
  // Los defaults no se escriben: la vista limpia es `/reports`, no
  // `/reports?sort=published_at&order=desc&page=1`.
  if (view.sort !== DEFAULT_SORT) sp.set("sort", view.sort)
  if (view.order !== DEFAULT_ORDER) sp.set("order", view.order)
  if (view.page > 0) sp.set("page", String(view.page + 1))
  return sp
}

/** Quita las claves vacías, para que `countActiveFilters` y los chips no vean
 *  un `{ q: undefined }` que vino de borrar el texto de un campo. */
export function pruneFilters(filters: ReportFilters): ReportFilters {
  const out: Record<string, unknown> = {}
  for (const [k, v] of Object.entries(filters)) {
    if (v !== undefined && v !== null && v !== "") out[k] = v
  }
  return out as ReportFilters
}

export function toListParams(view: ReportView, pageSize: number): ArticleListParams {
  return {
    ...view.filters,
    sort: view.sort,
    order: view.order,
    limit: pageSize,
    offset: view.page * pageSize,
  }
}

export function countActiveFilters(filters: ReportFilters): number {
  return Object.keys(pruneFilters(filters)).length
}

export type FilterChip = { key: keyof ReportFilters; label: string; value: string }

/** Los catálogos que hacen falta para poner un nombre humano a un id. Todos
 *  opcionales: llegan por red, y el chip tiene que poder dibujarse en el
 *  primer render de un enlace compartido. */
export type ChipLabels = {
  sources?: { value: string; label: string }[]
  documentalists?: { id: number; display_name: string }[]
  localityName?: (id: number) => string | undefined
}

const FIELD_LABELS: Record<keyof ReportFilters, string> = {
  q: "Búsqueda",
  entity: "Entidad",
  topic: "Tema",
  source: "Fuente",
  sentiment: "Sentimiento",
  framing: "Encuadre",
  headline_intent: "Titular",
  lead_orientation: "Lead",
  source_quality: "Calidad de fuente",
  has_hard_data: "Datos duros",
  locality: "Lugar",
  documentalist: "Documentalista",
  date_from: "Desde",
  date_to: "Hasta",
}

/** Un chip por filtro puesto, en el mismo orden en que aparecen los controles
 *  en la barra: buscar el chip que corresponde al control que acabas de tocar
 *  no debería ser una búsqueda. */
export function activeFilterChips(
  filters: ReportFilters,
  labels: ChipLabels = {}
): FilterChip[] {
  const chips: FilterChip[] = []
  const push = (key: keyof ReportFilters, value: string | undefined | false) => {
    if (value) chips.push({ key, label: FIELD_LABELS[key], value })
  }

  push("q", filters.q)
  push("entity", filters.entity)
  push("topic", filters.topic)
  if (filters.locality !== undefined) {
    push("locality", labels.localityName?.(filters.locality) ?? `#${filters.locality}`)
  }
  push(
    "source",
    filters.source &&
      (labels.sources?.find((s) => s.value === filters.source)?.label ?? filters.source)
  )
  push("date_from", filters.date_from)
  push("date_to", filters.date_to)
  push("sentiment", filters.sentiment && (SENTIMENT_LABELS[filters.sentiment] ?? filters.sentiment))
  push("framing", filters.framing && (FRAMING_LABELS[filters.framing] ?? filters.framing))
  push(
    "headline_intent",
    filters.headline_intent && (HEADLINE_LABELS[filters.headline_intent] ?? filters.headline_intent)
  )
  push(
    "lead_orientation",
    filters.lead_orientation && (LEAD_LABELS[filters.lead_orientation] ?? filters.lead_orientation)
  )
  push(
    "source_quality",
    filters.source_quality && (SOURCE_LABELS[filters.source_quality] ?? filters.source_quality)
  )
  if (filters.has_hard_data !== undefined) {
    push("has_hard_data", filters.has_hard_data ? "Con datos duros" : "Sin datos duros")
  }
  if (filters.documentalist !== undefined) {
    push(
      "documentalist",
      labels.documentalists?.find((d) => d.id === filters.documentalist)?.display_name ??
        `#${filters.documentalist}`
    )
  }
  return chips
}
```

- [ ] **Step 4: Correr las pruebas**

Run: `cd frontend && npx vitest run src/lib/report-filters.test.ts`
Expected: PASS (17 pruebas)

- [ ] **Step 5: Tipos y lint**

Run: `cd frontend && npx tsc -b && npm run lint`
Expected: sin errores.

---

## Task 4: La URL como fuente de verdad

Aquí es donde el usuario nota el cambio: los filtros sobreviven al refresco, al botón Atrás y al enlace compartido.

**Files:**
- Create: `frontend/src/lib/use-report-filters.ts`
- Test: `frontend/src/lib/use-report-filters.test.tsx`
- Modify: `frontend/src/pages/ReportsPage.tsx` (completo)
- Modify: `frontend/src/components/reports/FilterBar.tsx` (props `hardData`/`onHardDataChange` → `filters.has_hard_data`)
- Modify: `frontend/src/components/reports/LocalityFilter.test.tsx` (quitar las props que desaparecen)

**Interfaces:**
- Consumes: todo lo de `report-filters.ts` (Tarea 3).
- Produces: `useReportFilters(): { view, updateFilters, setFilters, setSort, setPage, reset }` donde `updateFilters(patch: Partial<ReportFilters>)`, `setFilters(f: ReportFilters)`, `setSort(sort: SortField, order: SortOrder)`, `setPage(page: number)`, `reset()`.
- Produces: `useDebouncedFilters(filters: ReportFilters): ReportFilters`.
- Produces: `FilterBar` deja de recibir `hardData` y `onHardDataChange`; lee y escribe `filters.has_hard_data` como `boolean | undefined`. El tipo exportado `HardDataFilter` desaparece.

- [ ] **Step 1: Escribir las pruebas que fallan**

Crea `frontend/src/lib/use-report-filters.test.tsx`:

```tsx
import { describe, expect, it } from "vitest"
import { render, screen } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { MemoryRouter, Route, Routes, useLocation } from "react-router-dom"
import { useReportFilters } from "@/lib/use-report-filters"

function Probe() {
  const { view, updateFilters, setPage, reset } = useReportFilters()
  const location = useLocation()
  return (
    <div>
      <output data-testid="search">{location.search}</output>
      <output data-testid="view">{JSON.stringify(view)}</output>
      <button onClick={() => updateFilters({ sentiment: "NEG" })}>negativo</button>
      <button onClick={() => updateFilters({ sentiment: undefined })}>quitar</button>
      <button onClick={() => setPage(2)}>pagina 3</button>
      <button onClick={reset}>limpiar</button>
    </div>
  )
}

function renderAt(url: string) {
  render(
    <MemoryRouter initialEntries={[url]}>
      <Routes>
        <Route path="/reports" element={<Probe />} />
      </Routes>
    </MemoryRouter>
  )
}

const view = () => JSON.parse(screen.getByTestId("view").textContent as string)

describe("useReportFilters", () => {
  it("lee el estado inicial de la URL", () => {
    renderAt("/reports?sentiment=NEG&page=2")
    expect(view().filters.sentiment).toBe("NEG")
    expect(view().page).toBe(1)
  })

  it("escribe el filtro en la URL", async () => {
    renderAt("/reports")
    await userEvent.click(screen.getByText("negativo"))
    expect(screen.getByTestId("search").textContent).toBe("?sentiment=NEG")
  })

  it("quitar un filtro lo saca de la URL en vez de dejarlo vacío", async () => {
    renderAt("/reports?sentiment=NEG")
    await userEvent.click(screen.getByText("quitar"))
    expect(screen.getByTestId("search").textContent).toBe("")
  })

  it("cambiar un filtro vuelve a la página 1", async () => {
    // Quedarse en la página 4 de un resultado que ahora tiene 2 muestra una
    // tabla vacía sin explicación.
    renderAt("/reports?page=4")
    await userEvent.click(screen.getByText("negativo"))
    expect(view().page).toBe(0)
    expect(screen.getByTestId("search").textContent).toBe("?sentiment=NEG")
  })

  it("cambiar de página conserva los filtros", async () => {
    renderAt("/reports?sentiment=NEG")
    await userEvent.click(screen.getByText("pagina 3"))
    expect(screen.getByTestId("search").textContent).toBe("?sentiment=NEG&page=3")
  })

  it("limpiar deja la URL vacía", async () => {
    renderAt("/reports?sentiment=NEG&q=agua&page=2")
    await userEvent.click(screen.getByText("limpiar"))
    expect(screen.getByTestId("search").textContent).toBe("")
  })
})
```

- [ ] **Step 2: Correr para verificar que falla**

Run: `cd frontend && npx vitest run src/lib/use-report-filters.test.tsx`
Expected: FAIL — `Failed to resolve import "@/lib/use-report-filters"`.

- [ ] **Step 3: Escribir `frontend/src/lib/use-report-filters.ts`**

```ts
/**
 * Enchufa la vista de Reportes (`report-filters.ts`) al query string.
 *
 * No hay estado local espejo: `useSearchParams` es la única fuente de verdad.
 * Cualquier `useState` paralelo abriría la puerta a que la barra muestre una
 * cosa y la tabla otra en cuanto alguien pulse Atrás.
 */
import { useCallback, useEffect, useMemo, useState } from "react"
import { useSearchParams } from "react-router-dom"
import {
  EMPTY_VIEW,
  pruneFilters,
  searchParamsToView,
  viewToSearchParams,
  type ReportFilters,
  type ReportView,
  type SortField,
  type SortOrder,
} from "@/lib/report-filters"

/** Debounce SOLO de los campos de texto libre (`q`, `entity`, `topic`): los
 *  clics en selects, fechas, orden o paginación deben reflejarse de inmediato
 *  — antes heredaban los mismos 300ms de espera del texto y se sentían lentos.
 *
 *  Exportado para poder probarlo aislado: qué campo espera y cuál no es una
 *  decisión con consecuencias visibles (una petición por tecla si se olvida
 *  sumar un campo de texto nuevo). */
export function useDebouncedFilters(filters: ReportFilters): ReportFilters {
  const [debounced, setDebounced] = useState(filters)
  useEffect(() => {
    const textChanged =
      filters.q !== debounced.q ||
      filters.entity !== debounced.entity ||
      filters.topic !== debounced.topic
    if (!textChanged) {
      setDebounced(filters)
      return
    }
    const t = setTimeout(() => setDebounced(filters), 300)
    return () => clearTimeout(t)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [filters])
  return debounced
}

export function useReportFilters() {
  const [searchParams, setSearchParams] = useSearchParams()
  const view = useMemo(() => searchParamsToView(searchParams), [searchParams])

  const write = useCallback(
    (next: ReportView, { push = false }: { push?: boolean } = {}) => {
      // `replace` por defecto: teclear "agua" con `push` generaría cuatro
      // entradas de historial y el botón Atrás habría que pulsarlo una vez por
      // letra. Paginar sí es un salto que la persona espera poder deshacer, y
      // por eso `setPage` pasa `push: true`.
      setSearchParams(viewToSearchParams(next), { replace: !push })
    },
    [setSearchParams]
  )

  const setFilters = useCallback(
    (filters: ReportFilters) => {
      // Volver a la página 1: quedarse en la 4 de un resultado que ahora tiene
      // 2 páginas muestra una tabla vacía sin explicación.
      write({ ...view, filters: pruneFilters(filters), page: 0 })
    },
    [view, write]
  )

  const updateFilters = useCallback(
    (patch: Partial<ReportFilters>) => setFilters({ ...view.filters, ...patch }),
    [view.filters, setFilters]
  )

  const setSort = useCallback(
    (sort: SortField, order: SortOrder) => write({ ...view, sort, order, page: 0 }),
    [view, write]
  )

  const setPage = useCallback(
    (page: number) => write({ ...view, page: Math.max(0, page) }, { push: true }),
    [view, write]
  )

  const reset = useCallback(() => write(EMPTY_VIEW), [write])

  return { view, updateFilters, setFilters, setSort, setPage, reset }
}
```

- [ ] **Step 4: Correr las pruebas del hook**

Run: `cd frontend && npx vitest run src/lib/use-report-filters.test.tsx`
Expected: PASS (6 pruebas)

- [ ] **Step 5: Reescribir `ReportsPage.tsx`**

Reemplaza el archivo completo por:

```tsx
import { useEffect, useState } from "react"
import { useNavigate } from "react-router-dom"
import { X } from "lucide-react"
import { Button } from "@/components/ui/button"
import { FilterBar } from "@/components/reports/FilterBar"
import { ReportsTable, Pagination } from "@/components/reports/ReportsTable"
import { useArticleFilterOptions, useArticles } from "@/lib/queries/articles"
import { useExportArticles } from "@/lib/queries/documentalists"
import { useDebouncedFilters, useReportFilters } from "@/lib/use-report-filters"
import { countActiveFilters, toListParams } from "@/lib/report-filters"
import { OdinApiError } from "@/lib/odin-api"

const PAGE_SIZE = 12

export function ReportsPage() {
  const navigate = useNavigate()
  // El orden se maneja desde las cabeceras de la tabla, no desde la barra de
  // filtros: dos controles para lo mismo se contradicen en cuanto uno cambia.
  const { view, updateFilters, setFilters, setSort, setPage, reset } = useReportFilters()
  const [selectedIds, setSelectedIds] = useState<number[]>([])
  const exportMutation = useExportArticles()

  const debouncedFilters = useDebouncedFilters(view.filters)
  const filtersKey = JSON.stringify(debouncedFilters)

  // Limpiar la selección cuando cambian los filtros: evita exportar reportes
  // que ya no están a la vista. Se observa la forma serializada y no el objeto:
  // `view.filters` se reconstruye en cada navegación y la identidad cambiaría
  // aunque el contenido sea el mismo.
  useEffect(() => {
    setSelectedIds([])
  }, [filtersKey])

  const { data: facets } = useArticleFilterOptions(debouncedFilters)
  const { data, isLoading, isFetching, error } = useArticles(
    toListParams({ ...view, filters: debouncedFilters }, PAGE_SIZE)
  )

  const activeCount = countActiveFilters(view.filters)
  const hasActiveFilters = activeCount > 0

  const total = data?.total ?? 0
  const items = data?.items ?? []
  const loading = isLoading || isFetching
  const errorMessage = error instanceof OdinApiError ? error.message : error ? "No se pudo conectar con la API de Odin." : null

  return (
    <div className="flex w-full flex-col gap-4">
      <FilterBar
        filters={view.filters}
        onChange={updateFilters}
        onApply={setFilters}
        facets={facets}
        onReset={reset}
        activeCount={activeCount}
        total={total}
        loaded={items.length}
      />

      {errorMessage && (
        <div role="alert" className="rounded-[7px] border px-3 py-2.5 text-[12.5px]" style={{ background: "var(--neg-soft)", borderColor: "var(--neg)", color: "var(--neg)" }}>
          {errorMessage}
        </div>
      )}

      {!loading && items.length === 0 ? (
        <div className="odin-glass flex flex-col items-center gap-3 rounded-xl border py-14 text-center">
          <p className="text-[14.5px] font-semibold">Sin resultados</p>
          <p className="max-w-[38ch] text-[13px]" style={{ color: "var(--muted-foreground)" }}>
            Ningún reporte coincide con los filtros aplicados.
          </p>
          {hasActiveFilters && (
            <button
              type="button"
              onClick={reset}
              className="inline-flex items-center gap-1.5 rounded-lg border px-3 py-1.5 text-[13px]"
              style={{ borderColor: "var(--border)" }}
            >
              <X className="size-3.5" />
              Quitar filtros
            </button>
          )}
        </div>
      ) : (
        <>
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
          <ReportsTable
            articles={items}
            loading={loading}
            onOpen={(id) => navigate(`/reports/${id}`)}
            sort={view.sort}
            order={view.order}
            onSort={setSort}
            selectedIds={selectedIds}
            onSelectionChange={setSelectedIds}
          />
        </>
      )}

      <Pagination
        page={view.page}
        total={total}
        pageSize={PAGE_SIZE}
        loaded={items.length}
        loading={loading}
        onPrev={() => setPage(view.page - 1)}
        onNext={() => setPage(view.page + 1)}
      />
    </div>
  )
}
```

> `useArticleFilterOptions(debouncedFilters)` todavía no acepta argumentos — TypeScript se quejará. Es correcto: lo acepta en la Tarea 7. **Para no dejar el árbol roto entre tareas, en ESTA tarea llámalo sin argumentos (`useArticleFilterOptions()`) y añade el argumento en la Tarea 7.**

- [ ] **Step 6: Adaptar `FilterBar` al nuevo contrato**

En `frontend/src/components/reports/FilterBar.tsx`:

1. Borra `export type HardDataFilter = "" | "true" | "false"`.
2. Cambia las props: fuera `hardData` y `onHardDataChange`; `hasActiveFilters: boolean` pasa a `activeCount: number`; entra `onApply: (filters: ReportFilters) => void` (la usará `FilterPresets` en la Tarea 8; por ahora se declara y no se usa — márcala opcional si `oxlint` protesta por prop sin usar).
3. Tipa `filters` como `ReportFilters` (importado de `@/lib/report-filters`) en vez de `ArticleListParams`.
4. El `<Select>` de datos duros pasa a:

```tsx
<Select
  aria-label="Datos duros"
  value={filters.has_hard_data === undefined ? "" : String(filters.has_hard_data)}
  onChange={(e) =>
    onChange({ has_hard_data: e.target.value === "" ? undefined : e.target.value === "true" })
  }
>
  <option value="">Datos duros: todos</option>
  <option value="true">Con datos duros</option>
  <option value="false">Sin datos duros</option>
</Select>
```

5. Donde decía `{hasActiveFilters && (` para el botón «Limpiar filtros», ahora `{activeCount > 0 && (`.

- [ ] **Step 7: Adaptar las pruebas existentes de `FilterBar`**

En `frontend/src/components/reports/LocalityFilter.test.tsx`, la función `renderBar` pasa props que ya no existen. Quita `hardData=""`, `onHardDataChange={vi.fn()}` y `hasActiveFilters={false}`, y añade `activeCount={0}` y `onApply={vi.fn()}`. No cambies ninguna aserción: lo que prueba (el combobox de lugar) no se toca.

- [ ] **Step 8: Correr toda la suite del frontend**

Run: `cd frontend && npx tsc -b && npm test`
Expected: PASS. 121 previas + 17 (Tarea 3) + 6 (Tarea 4) = **144**.

- [ ] **Step 9: Verificarlo en el navegador**

Run: `cd frontend && npm run dev` (con el backend arriba)
Comprueba a mano, que es lo único que demuestra que esta tarea hizo lo que prometía:
1. Pon un filtro → la URL cambia a `/reports?sentiment=NEG`.
2. Refresca (F5) → el filtro sigue puesto.
3. Abre un reporte y pulsa Atrás → el filtro sigue puesto.
4. Pasa a la página 2, pulsa Atrás → vuelves a la página 1 con el filtro intacto.
5. Copia la URL en una pestaña nueva → misma tabla.

- [ ] **Step 10: Lint**

Run: `cd frontend && npm run lint`
Expected: sin errores.

---

## Task 5: Chips de lo que está filtrado

Hoy la única señal de que hay filtros puestos es un enlace «Limpiar filtros» que aparece arriba a la derecha: hay que recorrer catorce controles para saber cuál está tocado. Los chips lo dicen de un vistazo y dan la salida individual (quitar uno sin perder los demás).

**Files:**
- Create: `frontend/src/components/reports/ActiveFilterChips.tsx`
- Test: `frontend/src/components/reports/ActiveFilterChips.test.tsx`
- Modify: `frontend/src/components/reports/FilterBar.tsx` (montar los chips bajo la cabecera)

**Interfaces:**
- Consumes: `activeFilterChips`, `ReportFilters`, `ChipLabels` (Tarea 3).
- Produces: `<ActiveFilterChips filters={...} labels={...} onRemove={(key) => void} onClearAll={() => void} />`.

- [ ] **Step 1: Escribir la prueba que falla**

Crea `frontend/src/components/reports/ActiveFilterChips.test.tsx`:

```tsx
import { describe, expect, it, vi } from "vitest"
import { render, screen } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { ActiveFilterChips } from "@/components/reports/ActiveFilterChips"

describe("ActiveFilterChips", () => {
  it("no dibuja nada sin filtros", () => {
    const { container } = render(
      <ActiveFilterChips filters={{}} onRemove={vi.fn()} onClearAll={vi.fn()} />
    )
    expect(container).toBeEmptyDOMElement()
  })

  it("muestra campo y valor de cada filtro", () => {
    render(
      <ActiveFilterChips
        filters={{ sentiment: "NEG", q: "agua" }}
        onRemove={vi.fn()}
        onClearAll={vi.fn()}
      />
    )
    expect(screen.getByText("Negativo")).toBeInTheDocument()
    expect(screen.getByText("agua")).toBeInTheDocument()
    expect(screen.getByText("Sentimiento")).toBeInTheDocument()
  })

  it("quitar un chip avisa con la clave del filtro", async () => {
    const onRemove = vi.fn()
    render(
      <ActiveFilterChips
        filters={{ sentiment: "NEG" }}
        onRemove={onRemove}
        onClearAll={vi.fn()}
      />
    )
    await userEvent.click(screen.getByRole("button", { name: "Quitar filtro Sentimiento: Negativo" }))
    expect(onRemove).toHaveBeenCalledWith("sentiment")
  })

  it("ofrece limpiar todo solo con más de un filtro", async () => {
    const onClearAll = vi.fn()
    const { rerender } = render(
      <ActiveFilterChips filters={{ sentiment: "NEG" }} onRemove={vi.fn()} onClearAll={onClearAll} />
    )
    expect(screen.queryByRole("button", { name: "Limpiar todo" })).not.toBeInTheDocument()

    rerender(
      <ActiveFilterChips
        filters={{ sentiment: "NEG", q: "agua" }}
        onRemove={vi.fn()}
        onClearAll={onClearAll}
      />
    )
    await userEvent.click(screen.getByRole("button", { name: "Limpiar todo" }))
    expect(onClearAll).toHaveBeenCalled()
  })
})
```

- [ ] **Step 2: Correr para verificar que falla**

Run: `cd frontend && npx vitest run src/components/reports/ActiveFilterChips.test.tsx`
Expected: FAIL — `Failed to resolve import "@/components/reports/ActiveFilterChips"`.

- [ ] **Step 3: Escribir el componente**

```tsx
import { X } from "lucide-react"
import { activeFilterChips, type ChipLabels, type ReportFilters } from "@/lib/report-filters"

/**
 * Qué está filtrado ahora mismo, un chip por filtro.
 *
 * Existe porque la barra tiene catorce controles y la única señal de que
 * alguno está tocado era un enlace "Limpiar filtros": había que recorrerlos
 * todos para saber cuál. El chip además da la salida individual — quitar el
 * lugar sin perder la fecha.
 */
export function ActiveFilterChips({
  filters,
  labels,
  onRemove,
  onClearAll,
}: {
  filters: ReportFilters
  labels?: ChipLabels
  onRemove: (key: keyof ReportFilters) => void
  onClearAll: () => void
}) {
  const chips = activeFilterChips(filters, labels)
  if (chips.length === 0) return null

  return (
    <div className="mb-3 flex flex-wrap items-center gap-1.5">
      {chips.map((chip) => (
        <span
          key={chip.key}
          className="inline-flex items-center gap-1.5 rounded-full border py-0.5 pr-1 pl-2.5 text-[11.5px]"
          style={{ background: "var(--surface-2)", borderColor: "var(--border)" }}
        >
          <span style={{ color: "var(--faint)" }}>{chip.label}</span>
          <span className="font-medium">{chip.value}</span>
          <button
            type="button"
            // El nombre accesible lleva campo Y valor: con cinco chips puestos,
            // cinco botones llamados "Quitar filtro" son indistinguibles para
            // quien navega por lista de elementos accionables.
            aria-label={`Quitar filtro ${chip.label}: ${chip.value}`}
            onClick={() => onRemove(chip.key)}
            className="inline-flex size-4 items-center justify-center rounded-full"
            style={{ color: "var(--faint)" }}
          >
            <X className="size-3" />
          </button>
        </span>
      ))}
      {/* Con un solo chip, "Limpiar todo" hace exactamente lo mismo que su ✕:
          dos botones para una acción solo obligan a elegir. */}
      {chips.length > 1 && (
        <button
          type="button"
          onClick={onClearAll}
          className="ml-1 text-[11.5px] underline-offset-2 hover:underline"
          style={{ color: "var(--muted-foreground)" }}
        >
          Limpiar todo
        </button>
      )}
    </div>
  )
}
```

- [ ] **Step 4: Correr la prueba**

Run: `cd frontend && npx vitest run src/components/reports/ActiveFilterChips.test.tsx`
Expected: PASS (4 pruebas)

- [ ] **Step 5: Montarlo en `FilterBar`**

En `FilterBar.tsx`, justo **después** del `</div>` de la cabecera (el que lleva el `<h1>Reportes</h1>` y el botón «Limpiar filtros») y **antes** de la grilla de controles:

```tsx
      <ActiveFilterChips
        filters={filters}
        labels={{
          sources: facets?.sources,
          documentalists: facets?.documentalists,
          localityName: (id) => entries.find((e) => e.id === id)?.name,
        }}
        onRemove={(key) => onChange({ [key]: undefined })}
        onClearAll={onReset}
      />
```

Con el import correspondiente. `entries` ya existe en el componente (sale de `indexTree`).

- [ ] **Step 6: Correr toda la suite y verificar tipos**

Run: `cd frontend && npx tsc -b && npm test && npm run lint`
Expected: PASS, **148** pruebas.

---

## Task 6: Básicos visibles, el resto en «Más filtros»

Catorce controles en una grilla plana obligan a leerlos todos para encontrar uno. Esta tarea los parte en dos y, de paso, sustituye siete bloques `<Select>` casi idénticos por un componente.

**Files:**
- Create: `frontend/src/components/reports/FilterSelect.tsx`
- Modify: `frontend/src/components/reports/FilterBar.tsx` (reestructuración completa del cuerpo)
- Test: `frontend/src/components/reports/FilterPanel.test.tsx` *(nuevo)*

**Interfaces:**
- Produces: `<FilterSelect label={string} allLabel={string} value={string} options={FilterOption[]} counts={Record<string, number> | undefined} onChange={(v: string) => void} />` y `type FilterOption = { value: string; label: string }`.
  - `counts` se declara ya en esta tarea aunque nadie la pase todavía (es opcional): la Tarea 7 solo tiene que enchufar el dato. Con `counts` sin definir, las opciones se dibujan sin número y no se deshabilita ninguna.
- Produces: `FilterBar` con un panel colapsable cuyo botón es `aria-expanded` + `aria-controls`, etiquetado «Más filtros» y con el número de filtros avanzados activos entre paréntesis.

- [ ] **Step 1: Escribir la prueba que falla**

Crea `frontend/src/components/reports/FilterPanel.test.tsx`:

```tsx
import { describe, expect, it, vi } from "vitest"
import { render, screen } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { QueryClient, QueryClientProvider } from "@tanstack/react-query"
import { FilterBar } from "@/components/reports/FilterBar"
import type { ArticleFilterOptions } from "@/lib/odin-api"
import type { ReportFilters } from "@/lib/report-filters"
import * as odinApi from "@/lib/odin-api"

vi.mock("@/lib/odin-api", async () => {
  const actual = await vi.importActual<typeof odinApi>("@/lib/odin-api")
  return { ...actual, getLocalityTree: vi.fn().mockResolvedValue([]) }
})

const FACETS = {
  sources: [{ value: "hoy", label: "Hoy" }],
  topics: [],
  sections: [],
  sentiments: ["POS", "NEG", "NEU"],
  framing: ["denuncia", "crecimiento"],
  headline_intent: [],
  lead_orientation: [],
  source_quality: [],
  documentalists: [],
  counts: {},
} as unknown as ArticleFilterOptions

function renderBar(filters: ReportFilters = {}) {
  const onChange = vi.fn()
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  render(
    <QueryClientProvider client={queryClient}>
      <FilterBar
        filters={filters}
        onChange={onChange}
        onApply={vi.fn()}
        facets={FACETS}
        onReset={vi.fn()}
        activeCount={0}
        total={0}
        loaded={0}
      />
    </QueryClientProvider>
  )
  return { onChange }
}

describe("panel de más filtros", () => {
  it("los básicos se ven sin desplegar nada", () => {
    renderBar()
    expect(screen.getByPlaceholderText("Título o tema…")).toBeInTheDocument()
    expect(screen.getByLabelText("Fuente")).toBeInTheDocument()
  })

  it("los avanzados están ocultos hasta desplegar", async () => {
    renderBar()
    expect(screen.queryByLabelText("Sentimiento")).not.toBeInTheDocument()
    await userEvent.click(screen.getByRole("button", { name: /Más filtros/ }))
    expect(screen.getByLabelText("Sentimiento")).toBeInTheDocument()
  })

  it("el botón dice cuántos avanzados hay puestos aunque esté cerrado", () => {
    renderBar({ sentiment: "NEG", framing: "denuncia" })
    // Sin esto, un filtro de encuadre puesto quedaría invisible al colapsar.
    expect(screen.getByRole("button", { name: /Más filtros \(2\)/ })).toBeInTheDocument()
  })

  it("arranca abierto si ya venían filtros avanzados en la URL", () => {
    // Un enlace compartido que filtra por Encuadre no puede esconder justo ese
    // control detrás de un panel cerrado.
    renderBar({ framing: "denuncia" })
    expect(screen.getByLabelText("Encuadre")).toBeInTheDocument()
  })

  it("elegir un valor avisa con la clave del filtro", async () => {
    const { onChange } = renderBar({ sentiment: "NEG" })
    await userEvent.selectOptions(screen.getByLabelText("Encuadre"), "denuncia")
    expect(onChange).toHaveBeenCalledWith({ framing: "denuncia" })
  })

  it("la opción vacía limpia el filtro en vez de mandar cadena vacía", async () => {
    const { onChange } = renderBar({ sentiment: "NEG" })
    await userEvent.selectOptions(screen.getByLabelText("Sentimiento"), "")
    expect(onChange).toHaveBeenCalledWith({ sentiment: undefined })
  })

  it("datos duros distingue sin-filtro de 'sin datos duros'", async () => {
    const { onChange } = renderBar({ sentiment: "NEG" })
    await userEvent.selectOptions(screen.getByLabelText("Datos duros"), "false")
    expect(onChange).toHaveBeenCalledWith({ has_hard_data: false })
  })
})
```

- [ ] **Step 2: Correr para verificar que falla**

Run: `cd frontend && npx vitest run src/components/reports/FilterPanel.test.tsx`
Expected: FAIL — no hay botón «Más filtros» y los avanzados se ven de entrada.

- [ ] **Step 3: Crear `FilterSelect.tsx`**

```tsx
import { Select } from "@/components/ui/select"

export type FilterOption = { value: string; label: string }

/**
 * Un desplegable de filtro: su opción "todos" al principio y, cuando hay
 * conteos, cuántos reportes hay detrás de cada valor.
 *
 * Sustituye siete bloques `<Select>` casi idénticos de `FilterBar`, que es
 * donde se colaba la inconsistencia: unos tenían `aria-label` y otros no.
 */
export function FilterSelect({
  label,
  allLabel,
  value,
  options,
  counts,
  onChange,
}: {
  /** Nombre accesible del control. Es lo único que lo identifica: en la barra
   *  la etiqueta visible se omite para que todos midan 32px de alto. */
  label: string
  allLabel: string
  value: string
  options: FilterOption[]
  /** `valor -> conteo`. Ausente mientras la respuesta no llega; un valor que
   *  no está en el diccionario tiene cero reportes. */
  counts?: Record<string, number>
  onChange: (value: string) => void
}) {
  return (
    <Select aria-label={label} value={value} onChange={(e) => onChange(e.target.value)}>
      <option value="">{allLabel}</option>
      {options.map((o) => {
        const n = counts?.[o.value] ?? (counts ? 0 : undefined)
        return (
          <option
            key={o.value}
            value={o.value}
            // Lo que está elegido nunca se deshabilita, aunque su conteo sea 0:
            // si no, no habría forma de ver qué está puesto ni de quitarlo con
            // el teclado.
            disabled={n === 0 && o.value !== value}
          >
            {n === undefined ? o.label : `${o.label} (${n})`}
          </option>
        )
      })}
    </Select>
  )
}
```

- [ ] **Step 4: Reescribir `FilterBar.tsx`**

Reemplaza el archivo completo por:

```tsx
import { useId, useMemo, useState } from "react"
import { ChevronDown, RotateCcw, Search } from "lucide-react"
import { LocalityCombobox } from "@/components/LocalityCombobox"
import { ActiveFilterChips } from "@/components/reports/ActiveFilterChips"
import { FilterSelect } from "@/components/reports/FilterSelect"
import { useLocalityTree } from "@/lib/queries/localities"
import { indexTree } from "@/lib/localities"
import {
  ADVANCED_KEYS,
  type ReportFilters,
} from "@/lib/report-filters"
import { FRAMING_LABELS, HEADLINE_LABELS, LEAD_LABELS, SENTIMENT_LABELS, SOURCE_LABELS } from "@/lib/labels"
import type { ArticleFilterOptions } from "@/lib/odin-api"

// La grilla de los dos bloques es la misma para que un control no cambie de
// ancho al pasar de la fila de básicos al panel.
const GRID = "repeat(auto-fit, minmax(168px, 1fr))"

function DateField({
  label,
  value,
  onChange,
}: {
  label: string
  value: string
  onChange: (v: string) => void
}) {
  return (
    <label
      className="flex h-8 items-center gap-1.5 rounded-[7px] border px-[11px]"
      style={{ background: "var(--surface-2)", borderColor: "var(--border)" }}
    >
      <span className="text-[11.5px]" style={{ color: "var(--faint)" }}>
        {label}
      </span>
      <input
        type="date"
        value={value}
        onChange={(e) => onChange(e.target.value)}
        className="flex-1 bg-transparent text-[12.5px] outline-none"
      />
    </label>
  )
}

/** Opciones a partir de una lista de slugs y su mapa de etiquetas. */
function options(values: string[] | undefined, labels: Record<string, string>) {
  return (values ?? []).map((v) => ({ value: v, label: labels[v] ?? v }))
}

export function FilterBar({
  filters,
  onChange,
  onApply,
  facets,
  onReset,
  activeCount,
  total,
  loaded,
}: {
  filters: ReportFilters
  onChange: (patch: Partial<ReportFilters>) => void
  /** Reemplaza TODOS los filtros de golpe. La usa el aplicar de una vista
   *  guardada, que no es un parche sino una sustitución: si fuera un parche,
   *  aplicar una vista dejaría puestos los filtros que la vista no menciona. */
  onApply: (filters: ReportFilters) => void
  facets: ArticleFilterOptions | null | undefined
  onReset: () => void
  activeCount: number
  total: number
  loaded: number
}) {
  // El árbol completo son ~204 nodos y se cachea sin vencimiento, así que
  // aplanarlo acá no cuesta una petición por render.
  const { data: tree } = useLocalityTree()
  const { entries } = useMemo(() => indexTree(tree ?? []), [tree])
  const selectedLocality = entries.find((e) => e.id === filters.locality)

  const topicFieldId = useId()
  const topicListId = `${topicFieldId}-list`
  const panelId = useId()

  const advancedCount = ADVANCED_KEYS.filter(
    (k) => filters[k] !== undefined && filters[k] !== ""
  ).length
  // Abierto de entrada si ya venía algo puesto dentro: un enlace compartido
  // que filtra por Encuadre no puede esconder justo ese control. Después queda
  // a voluntad; el número en el botón cubre el caso de colapsarlo con filtros
  // dentro.
  const [open, setOpen] = useState(advancedCount > 0)

  const counts = facets?.counts

  return (
    <div className="odin-glass rounded-xl border p-[18px]" style={{ boxShadow: "var(--shadow-sm)" }}>
      <div className="mb-3 flex flex-wrap items-baseline justify-between gap-2">
        <div className="flex items-baseline gap-2.5">
          <h1 className="text-[19px] font-semibold">Reportes</h1>
          <span className="text-[12.5px]" style={{ color: "var(--faint)" }}>
            {loaded} de {total} reportes
          </span>
        </div>
        {activeCount > 0 && (
          <button
            type="button"
            onClick={onReset}
            className="inline-flex items-center gap-1.5 text-[12.5px]"
            style={{ color: "var(--muted-foreground)" }}
          >
            <RotateCcw className="size-3.5" />
            Limpiar filtros
          </button>
        )}
      </div>

      <ActiveFilterChips
        filters={filters}
        labels={{
          sources: facets?.sources,
          documentalists: facets?.documentalists,
          localityName: (id) => entries.find((e) => e.id === id)?.name,
        }}
        onRemove={(key) => onChange({ [key]: undefined })}
        onClearAll={onReset}
      />

      {/* items-start: sin esto la grilla estira cada celda a la altura de la
          fila, y las lupas y chevrones posicionados a top-1/2 de su
          envoltorio caen por debajo del control de 32px. */}
      <div className="grid items-start gap-[10px]" style={{ gridTemplateColumns: GRID }}>
        <div className="relative">
          <Search className="absolute top-1/2 left-2.5 size-4 -translate-y-1/2" style={{ color: "var(--faint)" }} />
          <input
            aria-label="Buscar"
            value={filters.q ?? ""}
            onChange={(e) => onChange({ q: e.target.value || undefined })}
            placeholder="Título o tema…"
            className="h-8 w-full rounded-[7px] border pr-2 pl-8 text-[13px] outline-none"
            style={{ background: "var(--surface-2)", borderColor: "var(--border)" }}
          />
        </div>
        <div className="relative">
          <Search className="absolute top-1/2 left-2.5 size-4 -translate-y-1/2" style={{ color: "var(--faint)" }} />
          <input
            aria-label="Entidad mencionada"
            value={filters.entity ?? ""}
            onChange={(e) => onChange({ entity: e.target.value || undefined })}
            placeholder="Entidad mencionada…"
            className="h-8 w-full rounded-[7px] border pr-2 pl-8 text-[13px] outline-none"
            style={{ background: "var(--surface-2)", borderColor: "var(--border)" }}
          />
        </div>

        {/* Texto libre CON sugerencias, igual que el campo Tema del formulario
            manual: `main_topic` no está normalizado mientras no exista el
            catálogo administrable (R4), así que un desplegable cerrado dejaría
            fuera cualquier variante que no esté en la lista. */}
        <div className="relative">
          <Search className="absolute top-1/2 left-2.5 size-4 -translate-y-1/2" style={{ color: "var(--faint)" }} />
          <label htmlFor={topicFieldId} className="sr-only">
            Tema
          </label>
          <input
            id={topicFieldId}
            list={topicListId}
            value={filters.topic ?? ""}
            onChange={(e) => onChange({ topic: e.target.value || undefined })}
            placeholder="Todos los temas"
            className="h-8 w-full rounded-[7px] border pr-2 pl-8 text-[13px] outline-none"
            style={{ background: "var(--surface-2)", borderColor: "var(--border)" }}
          />
          <datalist id={topicListId}>
            {(facets?.topics ?? []).map((t) => (
              <option key={t} value={t} />
            ))}
          </datalist>
        </div>

        <LocalityCombobox
          label="Lugar"
          hideLabel
          entries={entries}
          selected={selectedLocality}
          onSelect={(entry) => onChange({ locality: entry?.id })}
          placeholder="Todos los lugares"
        />

        <FilterSelect
          label="Fuente"
          allLabel="Todas las fuentes"
          value={filters.source ?? ""}
          options={facets?.sources ?? []}
          counts={counts?.source}
          onChange={(v) => onChange({ source: v || undefined })}
        />

        <DateField label="Desde" value={filters.date_from ?? ""} onChange={(v) => onChange({ date_from: v || undefined })} />
        <DateField label="Hasta" value={filters.date_to ?? ""} onChange={(v) => onChange({ date_to: v || undefined })} />
      </div>

      <button
        type="button"
        onClick={() => setOpen((o) => !o)}
        aria-expanded={open}
        aria-controls={panelId}
        className="mt-2.5 inline-flex items-center gap-1 text-[12.5px]"
        style={{ color: "var(--muted-foreground)" }}
      >
        <ChevronDown
          className="size-3.5 transition-transform"
          style={{ transform: open ? "rotate(180deg)" : undefined }}
          aria-hidden
        />
        {/* El número va en el botón y no solo en los chips: colapsar el panel
            con dos filtros dentro no puede parecer que no hay ninguno. */}
        Más filtros{advancedCount > 0 ? ` (${advancedCount})` : ""}
      </button>

      {open && (
        <div
          id={panelId}
          className="mt-2.5 grid items-start gap-[10px] border-t pt-[14px]"
          style={{ gridTemplateColumns: GRID, borderColor: "var(--border)" }}
        >
          <FilterSelect
            label="Sentimiento"
            allLabel="Todo sentimiento"
            value={filters.sentiment ?? ""}
            options={options(facets?.sentiments, SENTIMENT_LABELS)}
            counts={counts?.sentiment}
            onChange={(v) => onChange({ sentiment: v || undefined })}
          />
          <FilterSelect
            label="Encuadre"
            allLabel="Todo encuadre"
            value={filters.framing ?? ""}
            options={options(facets?.framing, FRAMING_LABELS)}
            counts={counts?.framing}
            onChange={(v) => onChange({ framing: v || undefined })}
          />
          <FilterSelect
            label="Titular"
            allLabel="Todo titular"
            value={filters.headline_intent ?? ""}
            options={options(facets?.headline_intent, HEADLINE_LABELS)}
            counts={counts?.headline_intent}
            onChange={(v) => onChange({ headline_intent: v || undefined })}
          />
          <FilterSelect
            label="Lead"
            allLabel="Todo lead"
            value={filters.lead_orientation ?? ""}
            options={options(facets?.lead_orientation, LEAD_LABELS)}
            counts={counts?.lead_orientation}
            onChange={(v) => onChange({ lead_orientation: v || undefined })}
          />
          <FilterSelect
            label="Calidad de fuente"
            allLabel="Toda calidad de fuente"
            value={filters.source_quality ?? ""}
            options={options(facets?.source_quality, SOURCE_LABELS)}
            counts={counts?.source_quality}
            onChange={(v) => onChange({ source_quality: v || undefined })}
          />
          <FilterSelect
            label="Datos duros"
            allLabel="Datos duros: todos"
            value={filters.has_hard_data === undefined ? "" : String(filters.has_hard_data)}
            options={[
              { value: "true", label: "Con datos duros" },
              { value: "false", label: "Sin datos duros" },
            ]}
            counts={counts?.has_hard_data}
            // `false` es un filtro, no ausencia de filtro: comparar contra ""
            // y no la falsedad del valor.
            onChange={(v) => onChange({ has_hard_data: v === "" ? undefined : v === "true" })}
          />
          <FilterSelect
            label="Documentalista"
            allLabel="Todo documentalista"
            value={filters.documentalist === undefined ? "" : String(filters.documentalist)}
            options={(facets?.documentalists ?? []).map((d) => ({
              value: String(d.id),
              label: d.display_name,
            }))}
            counts={counts?.documentalist}
            onChange={(v) => onChange({ documentalist: v ? Number(v) : undefined })}
          />
        </div>
      )}

      {/* Fuera de la grilla y solo con el filtro puesto: el roll-up por
          subárbol sorprende justo cuando hay un lugar elegido, y como texto
          fijo ocupaba dos líneas que rompían la fila. */}
      {selectedLocality && (
        <p className="mt-2.5 text-[11.5px]" style={{ color: "var(--faint)" }}>
          {selectedLocality.name} incluye lo marcado en sus municipios.
        </p>
      )}
    </div>
  )
}
```

> `onApply` no se usa todavía en el cuerpo — es la Tarea 8 la que monta `FilterPresets` con ella. Si `oxlint` marca la prop sin usar, déjala declarada igual: quitarla y volver a ponerla en dos tareas es peor que un aviso.

- [ ] **Step 5: Correr las pruebas del panel**

Run: `cd frontend && npx vitest run src/components/reports/FilterPanel.test.tsx`
Expected: PASS (7 pruebas)

- [ ] **Step 6: Correr toda la suite**

Run: `cd frontend && npx tsc -b && npm test`
Expected: PASS, **155** pruebas. `LocalityFilter.test.tsx` sigue pasando: el combobox de lugar quedó entre los básicos.

- [ ] **Step 7: Lint**

Run: `cd frontend && npm run lint`
Expected: sin errores (salvo el aviso de `onApply` sin usar, aceptado arriba).

---

## Task 7: Enchufar los conteos

El backend ya los devuelve (Tarea 2) y `FilterSelect` ya sabe dibujarlos (Tarea 6). Falta que la petición lleve los filtros activos.

**Files:**
- Modify: `frontend/src/lib/odin-api.ts:373-375`
- Modify: `frontend/src/lib/queries/articles.ts:23,42-47`
- Modify: `frontend/src/pages/ReportsPage.tsx` (pasar `debouncedFilters`)
- Test: `frontend/src/components/reports/FilterCounts.test.tsx` *(nuevo)*

**Interfaces:**
- Consumes: `ArticleFiltersResponse.counts` (Tarea 2), `FilterSelect` (Tarea 6).
- Produces: `getArticleFilterOptions(filters?: ArticleListParams)`, `useArticleFilterOptions(filters?: ArticleListParams)`, `articleKeys.filters(params?: ArticleListParams)`.

- [ ] **Step 1: Escribir la prueba que falla**

Crea `frontend/src/components/reports/FilterCounts.test.tsx`:

```tsx
import { describe, expect, it, vi } from "vitest"
import { render, screen } from "@testing-library/react"
import { QueryClient, QueryClientProvider } from "@tanstack/react-query"
import { FilterBar } from "@/components/reports/FilterBar"
import type { ArticleFilterOptions } from "@/lib/odin-api"
import type { ReportFilters } from "@/lib/report-filters"
import * as odinApi from "@/lib/odin-api"

vi.mock("@/lib/odin-api", async () => {
  const actual = await vi.importActual<typeof odinApi>("@/lib/odin-api")
  return { ...actual, getLocalityTree: vi.fn().mockResolvedValue([]) }
})

const facetsWith = (counts: Record<string, Record<string, number>>) =>
  ({
    sources: [{ value: "hoy", label: "Hoy" }],
    topics: [],
    sections: [],
    sentiments: ["POS", "NEG"],
    framing: ["denuncia", "crecimiento"],
    headline_intent: [],
    lead_orientation: [],
    source_quality: [],
    documentalists: [],
    counts,
  }) as unknown as ArticleFilterOptions

function renderBar(facets: ArticleFilterOptions, filters: ReportFilters = {}) {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  render(
    <QueryClientProvider client={queryClient}>
      <FilterBar
        filters={filters}
        onChange={vi.fn()}
        onApply={vi.fn()}
        facets={facets}
        onReset={vi.fn()}
        activeCount={0}
        total={0}
        loaded={0}
      />
    </QueryClientProvider>
  )
}

describe("conteos en los desplegables", () => {
  it("pone el número junto a la etiqueta", () => {
    renderBar(facetsWith({ framing: { denuncia: 12, crecimiento: 3 } }), { framing: "denuncia" })
    expect(screen.getByRole("option", { name: "Denuncia (12)" })).toBeInTheDocument()
  })

  it("un valor que no viene en el diccionario cuenta cero", () => {
    renderBar(facetsWith({ framing: { denuncia: 12 } }), { framing: "denuncia" })
    expect(screen.getByRole("option", { name: "Crecimiento (0)" })).toBeInTheDocument()
  })

  it("deshabilita lo que daría cero resultados", () => {
    renderBar(facetsWith({ framing: { denuncia: 12 } }), { framing: "denuncia" })
    expect(screen.getByRole("option", { name: "Crecimiento (0)" })).toBeDisabled()
  })

  it("nunca deshabilita lo que está elegido", () => {
    // Si no, no habría forma de ver qué está puesto ni de quitarlo con el
    // teclado cuando la combinación de filtros da cero.
    renderBar(facetsWith({ framing: { denuncia: 0 } }), { framing: "denuncia" })
    expect(screen.getByRole("option", { name: "Denuncia (0)" })).not.toBeDisabled()
  })

  it("sin conteos todavía, no inventa números", () => {
    renderBar(facetsWith({}), { framing: "denuncia" })
    expect(screen.getByRole("option", { name: "Denuncia" })).toBeInTheDocument()
  })
})
```

> `counts: {}` significa «llegó la respuesta y ninguna dimensión trae datos», que es lo que hace que `counts?.framing` sea `undefined` y `FilterSelect` no dibuje números. Es exactamente el caso de la última prueba.

- [ ] **Step 2: Correr para verificar que falla**

Run: `cd frontend && npx vitest run src/components/reports/FilterCounts.test.tsx`
Expected: las tres primeras FALLAN (`Unable to find role="option" and name "Denuncia (12)"`); el panel está cerrado. **Ajusta el helper `renderBar` para abrir el panel antes de las aserciones** (`await userEvent.click(screen.getByRole("button", { name: /Más filtros/ }))`) o pasa `{ framing: "denuncia" }` como filtro, que ya lo abre de entrada (es lo que hacen estas pruebas). Con el filtro puesto el panel arranca abierto, así que las aserciones encuentran las opciones — verifica que efectivamente falla por el conteo y no por el panel.

- [ ] **Step 3: `getArticleFilterOptions` acepta filtros**

En `frontend/src/lib/odin-api.ts`, sustituye la función (líneas 373-375):

```ts
/** Opciones y CONTEOS de los filtros. Recibe los filtros activos porque los
 *  conteos son los de la tabla que se está viendo, no los del histórico
 *  completo: "Denuncia (12)" tiene que decir 12 sobre lo mismo que muestra la
 *  tabla, o el número engaña. */
export function getArticleFilterOptions(
  filters: ArticleListParams = {}
): Promise<ArticleFilterOptions> {
  const qs = new URLSearchParams()
  for (const [key, value] of Object.entries(filters)) {
    if (value === undefined || value === null || value === "") continue
    qs.set(key, String(value))
  }
  const s = qs.toString()
  return request<ArticleFilterOptions>(`/api/articles/filters${s ? `?${s}` : ""}`)
}
```

> Confirma que `ArticleListParams` (línea 90) ya tiene `topic?: string`. Si el trabajo en curso del `topic` no lo añadió, añádelo ahí.

- [ ] **Step 4: La clave de caché incluye los filtros**

En `frontend/src/lib/queries/articles.ts`:

```ts
export const articleKeys = {
  all: ["articles"] as const,
  lists: () => [...articleKeys.all, "list"] as const,
  list: (params: ArticleListParams) => [...articleKeys.lists(), params] as const,
  details: () => [...articleKeys.all, "detail"] as const,
  detail: (id: number) => [...articleKeys.details(), id] as const,
  filters: (params: ArticleListParams = {}) => [...articleKeys.all, "filters", params] as const,
}
```

```ts
export function useArticleFilterOptions(filters: ArticleListParams = {}) {
  return useQuery({
    queryKey: articleKeys.filters(filters),
    queryFn: () => getArticleFilterOptions(filters),
    // Los conteos dependen de los filtros, así que la clave cambia con cada
    // cambio: sin `keepPreviousData` los números desaparecerían y las opciones
    // deshabilitadas se re-habilitarían un instante en cada tecleo.
    placeholderData: keepPreviousData,
    staleTime: 60_000,
  })
}
```

`NewReportPage.tsx:52` sigue llamándolo sin argumentos y recibe las facetas sin filtrar — que es lo que necesita el formulario de captura.

- [ ] **Step 5: Pasar los filtros desde `ReportsPage`**

En `frontend/src/pages/ReportsPage.tsx`, cambia:

```tsx
  const { data: facets } = useArticleFilterOptions()
```
por
```tsx
  // Los mismos filtros debounced que la tabla: sin esto, teclear en "Buscar"
  // dispararía una petición de conteos por tecla.
  const { data: facets } = useArticleFilterOptions(debouncedFilters)
```

- [ ] **Step 6: Correr las pruebas**

Run: `cd frontend && npx vitest run src/components/reports/FilterCounts.test.tsx`
Expected: PASS (5 pruebas)

Run: `cd frontend && npx tsc -b && npm test && npm run lint`
Expected: PASS, **160** pruebas.

- [ ] **Step 7: Verificarlo contra el backend real**

Run: `cd frontend && npm run dev` (con el backend arriba)
Abre `/reports`, pon un filtro de fuente y despliega «Más filtros»: los encuadres deben mostrar conteos que suman el total de la tabla, y los que no aparecen en esa fuente deben salir en `(0)` y grises. Cambia el sentimiento y comprueba que las otras opciones de sentimiento **no** caen a 0 (es la regla de «ignorar el filtro propio»).

---

## Task 8: Vistas guardadas

**Files:**
- Create: `frontend/src/lib/filter-presets.ts`
- Test: `frontend/src/lib/filter-presets.test.ts`
- Create: `frontend/src/components/reports/FilterPresets.tsx`
- Test: `frontend/src/components/reports/FilterPresets.test.tsx`
- Modify: `frontend/src/components/reports/FilterBar.tsx` (montar `FilterPresets` en la cabecera)

**Interfaces:**
- Consumes: `ReportFilters`, `pruneFilters`, `countActiveFilters` (Tarea 3); `onApply` de `FilterBar` (Tarea 6).
- Produces: `type FilterPreset = { name: string; filters: ReportFilters }`, `loadPresets(): FilterPreset[]`, `savePreset(name: string, filters: ReportFilters): FilterPreset[]`, `deletePreset(name: string): FilterPreset[]`. Las tres de escritura devuelven la lista resultante, para que el componente no tenga que releer.

- [ ] **Step 1: Escribir la prueba del almacenamiento**

Crea `frontend/src/lib/filter-presets.test.ts`:

```ts
import { beforeEach, describe, expect, it, vi } from "vitest"
import { deletePreset, loadPresets, savePreset } from "@/lib/filter-presets"

beforeEach(() => {
  window.localStorage.clear()
})

describe("filter-presets", () => {
  it("sin nada guardado devuelve lista vacía", () => {
    expect(loadPresets()).toEqual([])
  })

  it("guarda y relee", () => {
    savePreset("Denuncias Santiago", { framing: "denuncia", locality: 42 })
    expect(loadPresets()).toEqual([
      { name: "Denuncias Santiago", filters: { framing: "denuncia", locality: 42 } },
    ])
  })

  it("el mismo nombre sobrescribe, sin distinguir mayúsculas", () => {
    savePreset("Denuncias", { framing: "denuncia" })
    savePreset("DENUNCIAS", { framing: "crecimiento" })
    expect(loadPresets()).toEqual([{ name: "DENUNCIAS", filters: { framing: "crecimiento" } }])
  })

  it("lo último guardado va primero", () => {
    savePreset("A", { q: "a" })
    savePreset("B", { q: "b" })
    expect(loadPresets().map((p) => p.name)).toEqual(["B", "A"])
  })

  it("no guarda un nombre en blanco", () => {
    savePreset("   ", { q: "a" })
    expect(loadPresets()).toEqual([])
  })

  it("no guarda claves vacías dentro de los filtros", () => {
    savePreset("A", { q: "agua", sentiment: undefined })
    expect(loadPresets()[0].filters).toEqual({ q: "agua" })
  })

  it("borra por nombre", () => {
    savePreset("A", { q: "a" })
    savePreset("B", { q: "b" })
    expect(deletePreset("A").map((p) => p.name)).toEqual(["B"])
  })

  it("sobrevive a un JSON corrupto", () => {
    // Una versión anterior o una edición a mano no pueden tumbar la página de
    // Reportes entera.
    window.localStorage.setItem("odin.reports.presets", "{no es json")
    expect(loadPresets()).toEqual([])
  })

  it("sobrevive a un localStorage que lanza", () => {
    // Modo privado de Safari y navegadores con almacenamiento bloqueado.
    const spy = vi.spyOn(Storage.prototype, "getItem").mockImplementation(() => {
      throw new Error("bloqueado")
    })
    expect(loadPresets()).toEqual([])
    spy.mockRestore()
  })
})
```

- [ ] **Step 2: Correr para verificar que falla**

Run: `cd frontend && npx vitest run src/lib/filter-presets.test.ts`
Expected: FAIL — `Failed to resolve import "@/lib/filter-presets"`.

- [ ] **Step 3: Escribir `frontend/src/lib/filter-presets.ts`**

```ts
/**
 * Vistas guardadas: combinaciones de filtros con nombre.
 *
 * En `localStorage` y no en el servidor a propósito: una tabla `saved_views`
 * con su CRUD y su migración es prácticamente un subproyecto, y como la URL de
 * Reportes ya es compartible, pasarle una vista a otra persona es pegarle el
 * enlace. Lo que esto resuelve es lo otro: la combinación que UNO revisa todas
 * las semanas.
 *
 * Todas las operaciones son a prueba de excepciones. `localStorage` lanza en
 * el modo privado de Safari y con el almacenamiento bloqueado por política, y
 * un fallo guardando una vista no puede tumbar la página de Reportes.
 */
import { pruneFilters, type ReportFilters } from "@/lib/report-filters"

const STORAGE_KEY = "odin.reports.presets"
const MAX_PRESETS = 20

export type FilterPreset = { name: string; filters: ReportFilters }

function read(): FilterPreset[] {
  try {
    const raw = window.localStorage.getItem(STORAGE_KEY)
    if (!raw) return []
    const parsed: unknown = JSON.parse(raw)
    if (!Array.isArray(parsed)) return []
    // Se valida la forma en vez de confiar: lo que hay ahí lo escribió una
    // versión anterior del código, o una persona con la consola abierta.
    return parsed.filter(
      (p): p is FilterPreset =>
        !!p &&
        typeof p === "object" &&
        typeof (p as FilterPreset).name === "string" &&
        !!(p as FilterPreset).filters &&
        typeof (p as FilterPreset).filters === "object"
    )
  } catch {
    return []
  }
}

function write(presets: FilterPreset[]): FilterPreset[] {
  try {
    window.localStorage.setItem(STORAGE_KEY, JSON.stringify(presets))
  } catch {
    // Cuota llena o almacenamiento bloqueado: la vista no se guarda, pero la
    // que está en pantalla sigue funcionando.
  }
  return presets
}

export function loadPresets(): FilterPreset[] {
  return read()
}

export function savePreset(name: string, filters: ReportFilters): FilterPreset[] {
  const clean = name.trim()
  if (!clean) return read()
  // Mismo nombre = sobrescribir, sin distinguir mayúsculas: "Denuncias" y
  // "denuncias" en la misma lista solo generan dudas sobre cuál es cuál.
  const rest = read().filter((p) => p.name.toLowerCase() !== clean.toLowerCase())
  return write([{ name: clean, filters: pruneFilters(filters) }, ...rest].slice(0, MAX_PRESETS))
}

export function deletePreset(name: string): FilterPreset[] {
  return write(read().filter((p) => p.name !== name))
}
```

- [ ] **Step 4: Correr la prueba del almacenamiento**

Run: `cd frontend && npx vitest run src/lib/filter-presets.test.ts`
Expected: PASS (9 pruebas)

- [ ] **Step 5: Escribir la prueba del componente**

Crea `frontend/src/components/reports/FilterPresets.test.tsx`:

```tsx
import { beforeEach, describe, expect, it, vi } from "vitest"
import { render, screen } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { FilterPresets } from "@/components/reports/FilterPresets"
import { savePreset } from "@/lib/filter-presets"

beforeEach(() => {
  window.localStorage.clear()
})

describe("FilterPresets", () => {
  it("sin filtros puestos no ofrece guardar", () => {
    render(<FilterPresets filters={{}} onApply={vi.fn()} />)
    expect(screen.queryByRole("button", { name: "Guardar vista" })).not.toBeInTheDocument()
  })

  it("guarda la vista actual con el nombre que se le da", async () => {
    render(<FilterPresets filters={{ framing: "denuncia" }} onApply={vi.fn()} />)
    await userEvent.click(screen.getByRole("button", { name: "Guardar vista" }))
    await userEvent.type(screen.getByRole("textbox", { name: "Nombre de la vista" }), "Denuncias")
    await userEvent.click(screen.getByRole("button", { name: "Guardar" }))

    expect(screen.getByRole("button", { name: "Aplicar vista Denuncias" })).toBeInTheDocument()
  })

  it("aplicar una vista sustituye TODOS los filtros", async () => {
    // Sustitución y no parche: si fuera un parche, aplicar una vista dejaría
    // puestos los filtros que la vista no menciona.
    savePreset("Denuncias", { framing: "denuncia" })
    const onApply = vi.fn()
    render(<FilterPresets filters={{ q: "agua" }} onApply={onApply} />)

    await userEvent.click(screen.getByRole("button", { name: "Aplicar vista Denuncias" }))
    expect(onApply).toHaveBeenCalledWith({ framing: "denuncia" })
  })

  it("borra una vista", async () => {
    savePreset("Denuncias", { framing: "denuncia" })
    render(<FilterPresets filters={{}} onApply={vi.fn()} />)

    await userEvent.click(screen.getByRole("button", { name: "Borrar vista Denuncias" }))
    expect(screen.queryByRole("button", { name: "Aplicar vista Denuncias" })).not.toBeInTheDocument()
  })
})
```

- [ ] **Step 6: Correr para verificar que falla**

Run: `cd frontend && npx vitest run src/components/reports/FilterPresets.test.tsx`
Expected: FAIL — `Failed to resolve import "@/components/reports/FilterPresets"`.

- [ ] **Step 7: Escribir `FilterPresets.tsx`**

```tsx
import { useState } from "react"
import { Bookmark, X } from "lucide-react"
import { Input } from "@/components/ui/input"
import { countActiveFilters, type ReportFilters } from "@/lib/report-filters"
import { deletePreset, loadPresets, savePreset, type FilterPreset } from "@/lib/filter-presets"

/**
 * Aplicar, guardar y borrar combinaciones de filtros con nombre.
 *
 * El nombre se pide con un campo en línea y no con `window.prompt`: el prompt
 * nativo no se puede estilar, bloquea la pestaña entera y no hay forma de
 * probarlo sin mockear el navegador.
 */
export function FilterPresets({
  filters,
  onApply,
}: {
  filters: ReportFilters
  /** Sustituye TODOS los filtros, no parchea: aplicar una vista con los
   *  filtros de otra encima daría una tercera que nadie pidió. */
  onApply: (filters: ReportFilters) => void
}) {
  const [presets, setPresets] = useState<FilterPreset[]>(() => loadPresets())
  const [naming, setNaming] = useState(false)
  const [name, setName] = useState("")

  // Guardar una vista sin filtros guardaría "todos los reportes", que es lo
  // que ya hace el enlace de Reportes.
  const canSave = countActiveFilters(filters) > 0

  function commit() {
    setPresets(savePreset(name, filters))
    setName("")
    setNaming(false)
  }

  return (
    <div className="flex flex-wrap items-center gap-1.5">
      {presets.map((preset) => (
        <span
          key={preset.name}
          className="inline-flex items-center rounded-full border py-0.5 pr-1 pl-1 text-[11.5px]"
          style={{ background: "var(--surface-2)", borderColor: "var(--border)" }}
        >
          <button
            type="button"
            aria-label={`Aplicar vista ${preset.name}`}
            onClick={() => onApply(preset.filters)}
            className="inline-flex items-center gap-1 px-1.5"
          >
            <Bookmark className="size-3" aria-hidden />
            {preset.name}
          </button>
          <button
            type="button"
            aria-label={`Borrar vista ${preset.name}`}
            onClick={() => setPresets(deletePreset(preset.name))}
            className="inline-flex size-4 items-center justify-center rounded-full"
            style={{ color: "var(--faint)" }}
          >
            <X className="size-3" />
          </button>
        </span>
      ))}

      {naming ? (
        <span className="inline-flex items-center gap-1.5">
          <Input
            aria-label="Nombre de la vista"
            autoFocus
            value={name}
            onChange={(e) => setName(e.target.value)}
            // Enter guarda y Escape cancela: escribir un nombre y tener que ir
            // al ratón para confirmarlo es un paso de más.
            onKeyDown={(e) => {
              if (e.key === "Enter") commit()
              if (e.key === "Escape") setNaming(false)
            }}
            className="h-7 w-40 text-[12px]"
          />
          <button type="button" onClick={commit} className="text-[11.5px] underline-offset-2 hover:underline">
            Guardar
          </button>
          <button
            type="button"
            onClick={() => setNaming(false)}
            className="text-[11.5px]"
            style={{ color: "var(--faint)" }}
          >
            Cancelar
          </button>
        </span>
      ) : (
        canSave && (
          <button
            type="button"
            onClick={() => setNaming(true)}
            className="inline-flex items-center gap-1 text-[11.5px]"
            style={{ color: "var(--muted-foreground)" }}
          >
            <Bookmark className="size-3" aria-hidden />
            Guardar vista
          </button>
        )
      )}
    </div>
  )
}
```

- [ ] **Step 8: Montarlo en `FilterBar`**

En la cabecera de `FilterBar.tsx`, dentro del `div` de la fila del título, entre el bloque del `<h1>` y el botón «Limpiar filtros»:

```tsx
        <FilterPresets filters={filters} onApply={onApply} />
```

Con su import. Esto le da uso a la prop `onApply` declarada en la Tarea 6.

- [ ] **Step 9: Correr todo**

Run: `cd frontend && npx vitest run src/components/reports/FilterPresets.test.tsx`
Expected: PASS (4 pruebas)

Run: `cd frontend && npx tsc -b && npm test && npm run lint`
Expected: PASS, **173** pruebas.

- [ ] **Step 10: Verificación final end-to-end**

Con backend y `npm run dev` arriba, recorre el caso de uso del encabezado de este plan de principio a fin:
1. Filtra «Negativo + Santiago + Desde 2026-08-01».
2. Despliega «Más filtros» y comprueba los conteos.
3. Elige Encuadre = Denuncia.
4. Guarda la vista como «Denuncias Santiago».
5. Abre un reporte, vuelve con Atrás: filtros y página intactos.
6. Pulsa «Limpiar filtros», luego la vista guardada: vuelve exactamente la misma combinación.
7. Copia la URL en una pestaña nueva de incógnito (con sesión): misma tabla, sin vistas guardadas (son locales — es lo esperado).

Run: `.venv/bin/python -m pytest -q` una última vez.
Expected: PASS, 578.

---

## Self-review

Repaso del plan contra lo que se acordó, hecho después de escribirlo.

**Cobertura del alcance acordado:**

| Acordado | Dónde |
|---|---|
| Persistencia en URL | Tareas 3 y 4 |
| Básicos + «Más filtros» + chips | Tareas 5 y 6 |
| Conteos dinámicos por faceta | Tareas 1, 2 y 7 |
| Presets locales | Tarea 8 |

**Fuera de alcance, dicho explícitamente y no por olvido** (ver «Decisiones»): multi-selección, campos de filtro nuevos (`section`, `media_stance`, actores canónicos, rango sobre `analyzed_on`, `analyzer_name`, `content_flags`, `sentiment_basis`), y filtros «sin valor». `ArticleFilterParams` queda como el único punto de entrada para agregarlos después.

**Deudas que este plan deja anotadas y no resuelve:**
- `GET /api/articles/filters` pasa de una petición cacheada 5 minutos a una por cambio de filtro, con ocho `GROUP BY` + cuatro `DISTINCT` por petición. Con el volumen actual es irrelevante; si la tabla crece a cientos de miles de filas, el siguiente paso es un índice compuesto por las columnas facetadas o cachear los conteos por combinación.
- El panel «Más filtros» se abre según el estado inicial. Si una vista guardada mete un filtro avanzado con el panel cerrado, el chip y el contador del botón lo delatan, pero el panel no se abre solo.
- `section` sigue viajando en `/api/articles/filters` sin que nadie lo consuma ni exista filtro por él. Es el candidato más barato del bloque «campos nuevos», si se retoma.

**Consistencia de nombres y tipos entre tareas** (verificado):
- `ArticleFilterParams` — se produce en Tarea 1, se consume en Tareas 1 y 2.
- `FacetCounts` con claves `source/sentiment/framing/headline_intent/lead_orientation/source_quality/has_hard_data/documentalist` — Tarea 2, consumido como `facets.counts.<dimensión>` en Tareas 6 y 7.
- `ReportFilters` / `ReportView` / `EMPTY_VIEW` / `pruneFilters` / `countActiveFilters` / `toListParams` / `activeFilterChips` / `ADVANCED_KEYS` — Tarea 3, consumidos en 4, 5, 6 y 8.
- `useReportFilters` devuelve `{ view, updateFilters, setFilters, setSort, setPage, reset }` — Tarea 4, consumido en 4.
- `FilterBar` props finales: `filters, onChange, onApply, facets, onReset, activeCount, total, loaded` — fijadas en Tarea 4, usadas idénticas en las pruebas de 6, 7 y 8.
- `FilterSelect` props: `label, allLabel, value, options, counts, onChange` — Tarea 6, con `counts` enchufado en 7.
- `loadPresets/savePreset/deletePreset` devuelven la lista resultante — Tarea 8.

**Conteo de pruebas esperado al terminar:** backend 578 (565 + 5 + 8), frontend 173 (121 + 17 + 6 + 4 + 7 + 5 + 13).
