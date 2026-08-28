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
| `documentalist_id` | FK → `users.id`, `ON DELETE SET NULL`, índice | sí | usuario (login) | **quién** revisó y dejó guardado el reporte — no confundir con `analyzer_name`/`analyzed_at` de arriba, que dicen qué motor lo produjo y cuándo corrió, no qué persona lo firmó. `NULL` en los artículos que entran por el rastreo masivo (no hay persona detrás) y en los guardados antes de esta columna |
| `analyzed_on` | Date, índice | sí | usuario (login) | **cuándo** lo trabajó el documentalista, solo día/mes/año — distinto de `analyzed_at`, que es el timestamp completo de cuándo corrió el motor de análisis. Es `Date` y no `DateTime` a propósito: el dato que pidió el cliente es la fecha sin hora, y el tipo lo deja dicho en el esquema en vez de depender de que cada consulta recuerde recortarla; además hace trivial agrupar por día para el KPI |
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

## `localities`

Catálogo geográfico jerárquico: el lugar de la noticia. Una sola tabla
autorreferencial para los cinco niveles (`PAIS`, `MACRORREGION`, `REGION`,
`PROVINCIA`, `MUNICIPIO`).

Contenido: 31 provincias + el Distrito Nacional y 158 municipios, agrupados en
las 3 macrorregiones y las 10 regiones de planificación del **Decreto 710-04**.
Incluye los municipios creados por ley en 2024 (La Victoria, Ley 15-24, vigente
desde el 2026-01-01; y La Caleta, Ley 39-24).

| Columna | Tipo | Null | Significado |
|---|---|---|---|
| `id` | Integer PK | no | — |
| `name` | String(160), índice | no | nombre para mostrar ("Santiago de los Caballeros") |
| `norm_key` | String(160), índice | no | forma normalizada (`norm_key`), para buscar sin acentos |
| `level` | String(20), índice | no | `PAIS` \| `MACRORREGION` \| `REGION` \| `PROVINCIA` \| `MUNICIPIO` |
| `parent_id` | FK → `localities.id`, `ON DELETE CASCADE` | sí | nulo solo en el país |
| `path` | String(255), índice | no | ruta de ids materializada (`/1/2/6/19/`) |
| `is_active` | Boolean, default `True` | no | desactivar sin borrar, para no huerfanar artículos ya etiquetados |
| `created_at` / `updated_at` | DateTime(tz) | no | — |

Restricción: `UNIQUE(parent_id, norm_key)` — dos hermanos no pueden llamarse
igual, pero el mismo nombre sí puede repetirse bajo padres distintos
("Santiago" es provincia y también municipio dentro de esa provincia).

**Por qué `path`**: la consulta caliente es "todo lo que cuelga del Cibao", que
con solo `parent_id` exigiría un CTE recursivo — cuya sintaxis difiere entre
PostgreSQL, SQLite y SQL Server. Con la ruta materializada el mismo filtro es
un `LIKE '/1/2/%'`: una pasada, indexable e idéntico en los tres motores. El
precio es mantener `path` al mover un nodo, y por eso `update_locality` no
permite cambiar de padre.

Semilla en `db/seeds/localities_rd.json`, cargada de forma idempotente por
`db/localities.seed_localities()` en el `lifespan` de la API — mismo patrón que
`entity_aliases`. Es tabla y no constante en el código porque el catálogo
cambia por ley (Baitoa pasó a municipio en 2013).

## `locality_aliases`

Otros nombres por los que la prensa cita un lugar.

| Columna | Tipo | Null | Significado |
|---|---|---|---|
| `id` | Integer PK | no | — |
| `locality_id` | FK → `localities.id`, `ON DELETE CASCADE`, índice | no | — |
| `alias` | String(160) | no | forma tal como aparece en texto ("Navarrete") |
| `alias_key` | String(160), índice | no | forma normalizada, para el lookup |

Restricción: `UNIQUE(locality_id, alias_key)`. Hace falta más de lo que parece:
la provincia Hermanas Mirabal se llamó **Salcedo** hasta 2007 y los medios
siguen usando el nombre viejo; Villa Bisonó aparece casi siempre como
**Navarrete**; y el municipio cabecera suele nombrarse por su provincia
("Higüey" por "Salvaleón de Higüey").

## `article_localities`

Vínculo N:M artículo ↔ lugar. N:M y no una columna en `articles` porque una
noticia puede ocurrir en varios lugares.

| Columna | Tipo | Null | Significado |
|---|---|---|---|
| `id` | Integer PK | no | — |
| `article_id` | FK → `articles.id`, `ON DELETE CASCADE`, índice | no | — |
| `locality_id` | FK → `localities.id`, `ON DELETE CASCADE`, índice | no | — |
| `kind` | String(20), default `HECHO` | no | `HECHO` (dónde ocurrió) \| `MENCIONADO` (nombrado de pasada) |
| `origin` | String(20), default `MANUAL` | no | `MANUAL` \| `AUTO` — quién hizo el vínculo |
| `confidence` | Float | sí | confianza de la detección automática; `NULL` cuando lo puso una persona |
| `created_at` | DateTime(tz) | no | — |

Restricción: `UNIQUE(article_id, locality_id, kind)` — el mismo lugar puede
estar dos veces en una nota si juega dos papeles distintos, pero no dos veces
con el mismo papel.

**El nivel del nodo apuntado ES el alcance de la noticia**: apuntar al país
significa ámbito nacional, a una región significa regional, a un municipio
significa municipal. Por eso no hay cuatro columnas con centinelas "Todas" — el
"Todas" del formulario solo dice hasta dónde bajó el documentalista, y eso ya
queda registrado en cuál nodo se eligió.

`origin` y `confidence` existen desde la primera versión aunque hoy solo se
escriba `MANUAL`: la detección automática es la fase siguiente, y así no tendrá
que migrar datos ya guardados.

## `users`

Personas que usan Odin. Antes de esta tabla la autenticación era un operador
único contra credenciales del entorno (`ODIN_AUTH_*`): si todos entraban con
la misma credencial, todo reporte quedaba atribuido al mismo nombre y medir
el trabajo por documentalista no significaba nada. El operador del `.env` no
desaparece: al arrancar se siembra como primer usuario con rol `admin`
(`db/users.seed_operator`), así que quien hoy entra sigue entrando igual.

| Columna | Tipo | Null | Significado |
|---|---|---|---|
| `id` | Integer PK | no | — |
| `username` | String(80) | no | tal como se muestra y se teclea al entrar, p. ej. `jperez` |
| `username_key` | String(80), índice | no | `username` normalizado a minúsculas; se deriva solo en cada alta y edición (`@validates`), para que renombrar a alguien no deje una clave vieja que el login ya no encuentre |
| `display_name` | String(160) | no | nombre para mostrar en reportes y KPI, p. ej. "Juan Pérez" |
| `password_hash` | String(255) | no | formato de `core/auth.py` |
| `role` | String(20), default `documentalista` | no | `admin` \| `documentalista` (`USER_ROLES`) — `documentalista` captura y revisa reportes; `admin` además administra el catálogo de documentalistas |
| `is_active` | Boolean, default `True` | no | dar de baja sin borrar: los reportes que firmó siguen atribuidos a él |
| `created_at` / `updated_at` | DateTime(tz) | no | `updated_at` con `onupdate` automático |

Restricción: `UNIQUE(username_key)` (`uq_user_username`).

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
- **Tampoco hacia `users`**: `articles.documentalist_id` usa `ON DELETE SET NULL` —
  dar de baja a un documentalista (o borrarlo) jamás borra los reportes que firmó,
  solo los deja sin autor asignado.
- **Los vínculos de lugar sí van en cascada**: `article_localities` es una
  tabla de unión sin datos propios que valgan sin sus dos extremos, así que
  borrar el artículo o el lugar borra el vínculo (`ON DELETE CASCADE`). Para
  retirar un municipio de circulación sin perder el histórico se usa
  `localities.is_active`, no el borrado.
