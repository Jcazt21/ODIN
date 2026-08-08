# Diccionario de datos

> Fuente de verdad: [`db/models.py`](../db/models.py). Este documento describe
> el **significado** de cada columna; la definición autoritativa del tipo SQL
> vive en el código y en `alembic/versions/`. Si hay discrepancia, el código
> gana — actualiza este archivo, no al revés.

## `articles`

Un artículo de prensa, su cuerpo (si se conservó) y el resultado de su
análisis más reciente. **No hay versionado de análisis**: si se re-analiza un
artículo, la fila se sobrescribe (no existe `article_revisions`).

| Columna | Tipo | Null | Producida por | Significado |
|---|---|---|---|---|
| `id` | Integer PK | no | sistema | identificador interno |
| `source` | String(100), índice | no | scraper/usuario | slug de la fuente, p. ej. `listin_diario`, `manual` |
| `url` | String(1000), único | no | scraper/usuario | URL canónica del artículo; el unique es la deduplicación actual (no cubre republicación en otra URL) |
| `title` | String(600) | no | extracción (trafilatura) | titular tal como lo extrajo trafilatura |
| `authors` | String(500) | sí | extracción | autores separados por `", "`; texto libre, no normalizado |
| `section` | String(200) | sí | extracción | sección del medio si trafilatura la detecta |
| `published_at` | DateTime(tz) | sí | extracción | fecha de publicación declarada por el medio; puede venir naive si la fuente no da offset (ver `task.md` §2.7, no resuelto) |
| `scraped_at` | DateTime(tz) | no (default `now`) | sistema | momento en que Odin obtuvo el artículo |
| `body` | Text | sí | extracción | cuerpo completo del artículo; ver retención en [LEGAL.md](LEGAL.md) |
| `main_topic` | String(200) | sí | analyzer | tema principal inferido |
| `topic_keywords` | String(600) | sí | analyzer | palabras clave separadas por `", "` |
| `overall_sentiment` | String(10) | sí | analyzer | `POS` \| `NEG` \| `NEU` |
| `sentiment_score` | Float | sí | analyzer | confianza del sentimiento, rango 0–1 |
| `analyzer_name` | String(40) | sí | sistema | `local` \| `gemini` \| `groq` \| `hybrid` — qué motor produjo esta fila |
| `analyzer_model` | String(80) | sí | sistema | id exacto del modelo (p. ej. `es_core_news_lg-3.8.0`, `gemini-3.5-flash`) |
| `analyzer_version` | String(64) | sí | sistema | versión del prompt/heurística (linaje del análisis, `task.md` §2.1) |
| `analysis_schema_version` | Integer | sí | sistema | versión de `AnalysisResult` (`ANALYSIS_SCHEMA_VERSION` en `analysis/base.py`) usada al producir esta fila |
| `analyzed_at` | DateTime(tz) | sí | sistema | momento del análisis |
| `framing` | String(40) | sí | analyzer (**solo LLM**) | encuadre editorial inferido; `NULL` si el análisis fue con `LocalAnalyzer` |
| `headline_intent` | String(20) | sí | analyzer (**solo LLM**) | intención del titular |
| `lead_orientation` | String(20) | sí | analyzer (**solo LLM**) | orientación del primer párrafo |
| `source_quality` | String(30) | sí | analyzer (**solo LLM**) | juicio sobre la calidad/rigor del artículo |
| `has_hard_data` | Boolean | sí | analyzer (**solo LLM**) | si el artículo cita datos duros (cifras, documentos) |
| `dominant_actor_id` | FK → `canonical_entities.id`, `ON DELETE SET NULL`, índice | sí | analyzer (**solo LLM**) | actor protagonista del artículo |
| `blamed_actor_id` | FK ídem | sí | analyzer (**solo LLM**) | actor señalado/culpado |
| `credited_actor_id` | FK ídem | sí | analyzer (**solo LLM**) | actor reconocido/acreditado |

**`framing`/`headline_intent`/`lead_orientation`/`source_quality`/
`has_hard_data`/`*_actor_id` son juicios editoriales de un LLM**, no hechos
verificables — ver [PRECISION.md](PRECISION.md) y [LEGAL.md](LEGAL.md) antes
de tratarlos como verdad de terreno. Sus valores válidos están enumerados en
`api/schemas.py` (no como `CHECK` constraint en la BD).

## `entities`

Una mención de una entidad (persona/organización/lugar) dentro de un
artículo concreto. Distinta de `canonical_entities` (la dimensión).

| Columna | Tipo | Null | Significado |
|---|---|---|---|
| `id` | Integer PK | no | — |
| `article_id` | FK → `articles.id`, `ON DELETE CASCADE` | no | artículo donde aparece la mención |
| `name` | String(300), índice | no | nombre tal como aparece en el texto/salida del analyzer |
| `type` | String(20) | no | `PERSON` \| `ORG` \| ... (según el analyzer) |
| `mentions_count` | Integer, default 1 | no | veces que se menciona dentro del mismo artículo |
| `sentiment_toward` | String(10) | sí | sentimiento del artículo hacia esta entidad específica (`~60-70%` de precisión medida, ver PRECISION.md — no un hecho) |
| `sentiment_score` | Float | sí | confianza del `sentiment_toward` |
| `context` | Text | sí | fragmento de texto que sustenta la clasificación |
| `extraction_confidence` | Float, default 1.0 | no | confianza de que la entidad fue extraída correctamente |
| `canonical_entity_id` | FK → `canonical_entities.id`, `ON DELETE SET NULL` | sí | vínculo a la dimensión canónica; `NULL` en menciones antiguas no vinculadas |

Restricción: `UNIQUE(article_id, name, type)` — no puede haber dos menciones
idénticas del mismo nombre+tipo en el mismo artículo.

## `canonical_entities`

La dimensión de entidad: una fila por figura/empresa real, independiente de
cómo se la nombre en cada artículo (§4.1 de `task.md`, resuelto).

| Columna | Tipo | Null | Significado |
|---|---|---|---|
| `id` | Integer PK | no | — |
| `name` | String(300), índice | no | nombre canónico mostrado en reportes |
| `type` | String(20) | no | `PERSON` \| `ORG` \| ... |
| `description` | String(300) | sí | nota libre para desambiguar (p. ej. cargo) |
| `created_at` / `updated_at` | DateTime(tz) | no | `updated_at` con `onupdate` automático |

Restricción: `UNIQUE(name, type)`. Fusionar dos entidades (`POST
/api/canonical-entities/{id}/merge`) reasigna `Entity.canonical_entity_id` de
la fuente al destino y borra la fila fuente.

## `entity_aliases`

Catálogo de siglas/alias → nombre canónico, usado por `canonicalize.py` para
unificar menciones antes de guardar (p. ej. "PRM" → "Partido Revolucionario
Moderno").

| Columna | Tipo | Null | Significado |
|---|---|---|---|
| `id` | Integer PK | no | — |
| `alias` | String(100) | no | forma tal como aparece en texto |
| `alias_key` | String(100), índice | no | forma normalizada (`norm_key`, minúsculas + sin acentos) usada para el lookup |
| `canonical_name` | String(300) | no | nombre al que resuelve el alias |
| `type` | String(20), default `ORG` | no | tipo de la entidad resultante |
| `is_active` | Boolean, default `True` | no | permite desactivar un alias sin borrarlo |
| `created_at` / `updated_at` | DateTime(tz) | no | — |

Restricción: `UNIQUE(alias_key, type)`. Semilla inicial en
`db/seed_aliases.py`, cargada en el `lifespan` de la API.

## `analyze_jobs`

Cola de trabajos de `POST /api/analyze` (flujo a demanda, un job por URL
analizada).

| Columna | Tipo | Null | Significado |
|---|---|---|---|
| `id` | String(36) PK (UUID) | no | UUID, no autoincrement — evita revelar volumen total de análisis |
| `status` | String(20), default `pending` | no | `pending` \| `running` \| `done` \| `failed` |
| `stage` | String(20) | sí | paso del pipeline dentro de `status=running`: `fetching` \| `analyzing` \| `canonicalizing` (`ANALYZE_STAGES` en `services/analyze_service.py`); `NULL` fuera de `running`. Lo consume el polling del frontend para mostrar progreso, no solo "corriendo" |
| `url` | String(2048) | no | URL solicitada, ya canonicalizada (`url_guard.canonical_url`: sin `utm_*`, fragmento ni barra final) — es la clave con que se busca un análisis reciente o un job en curso de la misma nota |
| `created_at` / `started_at` / `finished_at` | DateTime(tz) | sí (excepto `created_at`) | timestamps del ciclo de vida |
| `result_json` | Text | sí | `AnalyzeResult` serializado (la vista previa sin guardar, no `ArticleDetail`), si terminó en `done` |
| `error` | Text | sí | mensaje de error, si terminó en `failed`. Siempre redactado para el usuario: el detalle de una excepción interna va al log, no aquí |

Índices: `(url, created_at)` para el reuso y el dedupe de jobs en curso;
`(status, created_at)` para el barrido de arranque.

No hay operación de reintento: un job fallido se reintenta creando uno nuevo
(`POST /api/analyze` de nuevo). Ver [RUNBOOK.md](RUNBOOK.md).

Las filas no son eternas: al arrancar, la API marca como `failed` los jobs que
quedaron colgados (`ODIN_ANALYZE_JOB_STALE_MINUTES`) y borra los terminados que
pasaron su TTL (`ODIN_ANALYZE_JOB_TTL_HOURS`).

## `crawl_runs`

Resumen agregado de una corrida del pipeline masivo (`pipeline.run()`), sea
disparada por `main.py` o por un `scrape_job`.

| Columna | Tipo | Null | Significado |
|---|---|---|---|
| `id` | Integer PK | no | — |
| `correlation_id` | String(32), único, índice | no | mismo id que aparece en los logs estructurados de la corrida |
| `started_at` / `finished_at` | DateTime(tz) | sí (`finished_at`) | — |
| `status` | String(20), default `running` | no | `running` \| `success` \| `failed` \| `cancelled` |
| `sources` | String(300) | sí | fuentes incluidas; `NULL` = todas |
| `analyzer_name` | String(40) | sí | motor usado en la corrida |
| `articles_discovered` / `articles_saved` / `articles_failed` | Integer, default 0 | no | contadores agregados |
| `stats_by_source` | Text (JSON) | sí | desglose por fuente |
| `error` | Text | sí | error a nivel de corrida, si aplica |

**No existe `fetch_log`** (tabla por-URL con éxito/fallo, `task.md` §2.3): la
cobertura solo se puede ver agregada por `crawl_run`, no por URL individual —
gap de observabilidad conocido, no resuelto por este diccionario.

## `scrape_jobs`

Un `scrape_job` es la unidad expuesta por la API para disparar una corrida
masiva (`POST /api/scrape-jobs`); internamente arranca un `pipeline.run()` y
produce un `crawl_run`.

| Columna | Tipo | Null | Significado |
|---|---|---|---|
| `id` | String(36) PK (UUID) | no | — |
| `status` | String(20), default `pending` | no | `pending` \| `running` \| `done` \| `failed` \| `cancelled` |
| `target` | Integer | sí | meta total de artículos de la corrida |
| `per_source_cap` | Integer | sí | tope por fuente, calculado como `ceil(target/len(SCRAPERS))` si no se especifica |
| `analyzer_name` | String(40) | sí | restringido a `local`\|`groq`\|`hybrid` — **nunca `gemini`**, para no facturar por volumen |
| `correlation_id` | String(32), índice | sí | comparte id con el `crawl_run` resultante |
| `crawl_run_id` | FK → `crawl_runs.id`, `ON DELETE SET NULL`, índice | sí | — |
| `progress_json` | Text (JSON) | sí | progreso por clave compuesta `"fuente:etapa"` |
| `cancel_requested` | Boolean, default `False` | no | cancelación cooperativa; el pipeline la consulta entre fuentes/artículos |
| `created_at` / `started_at` / `finished_at` | DateTime(tz) | sí (excepto `created_at`) | — |
| `error` | Text | sí | — |

Solo puede haber un `scrape_job` activo (`pending`/`running`) a la vez —
`POST /api/scrape-jobs` responde `409` si ya hay uno.

## Convenciones generales

- **Timestamps**: columnas `DateTime(timezone=True)`; el objetivo es siempre
  UTC-aware, pero `published_at` puede llegar naive desde la extracción si la
  fuente no da offset (`task.md` §2.7 — normalización pendiente).
- **Nombres de motor** (`analyzer_name`): `local` (spaCy + pysentimiento, sin
  costo), `gemini` (LLM, facturado, agrega campos de encuadre), `groq` (LLM
  alternativo), `hybrid` (local + Groq solo para encuadre).
- **IDs de job como UUID string** (`analyze_jobs.id`, `scrape_jobs.id`): a
  propósito, para no exponer volumen total vía IDs secuenciales adivinables.
- **Nada se borra en cascada hacia `canonical_entities`**: los FKs de actor y
  de mención usan `ON DELETE SET NULL`, nunca `CASCADE` — borrar una entidad
  canónica no borra artículos ni menciones, solo desvincula.
