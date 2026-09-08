# Filtros probabilísticos en ODIN — evaluación y guía

> Nota de decisión. Responde a: *¿dónde en ODIN tiene sentido un Bloom filter
> (o Counting Bloom, Cuckoo, Quotient, Scalable Bloom, HyperLogLog), valen la
> pena, o conviene otra estructura?* Léela antes de introducir cualquiera de
> estas estructuras.

## Veredicto

**A la escala actual de ODIN, ninguno de esos filtros se justifica.** El
producto analiza artículos **de a uno y a demanda**; el corpus es de unos
cientos de artículos (grafo de ~3.130 nodos); el rastreo masivo es **manual y
opcional** y descubre cientos de URLs por corrida, no millones; el backend es
de **un solo worker** sobre SQLite/Postgres.

Todos los puntos donde ODIN hace una pregunta de *pertenencia* ("¿ya vi esta
URL?", "¿ya existe esta entidad?") o de *unicidad* ya están resueltos con un
`set` en memoria o con un índice `UNIQUE` en la base. A este tamaño esas
soluciones son **exactas, más simples y más rápidas** que un filtro
probabilístico — que además obligaría a mantener una estructura extra
sincronizada con la fuente de verdad y, ante un positivo, *igual* habría que
consultar la base para descartar el falso positivo.

La única técnica probabilística que sí aportaría valor a ODIN **no está en la
tabla**: **SimHash / MinHash + LSH** para detectar *near-duplicados de
contenido* (la misma nota de cable o comunicado republicada por varias
fuentes con URLs distintas). Es una mejora **futura** del golden set, no algo
para hoy.

| Estructura | Caso candidato en ODIN | Veredicto |
|---|---|---|
| **Bloom** | pre-filtro de "URL ya guardada" en el crawl | **No** — el `SELECT` por índice `UNIQUE` es de microsegundos y el crawl está limitado por la red, no por esa consulta |
| **Counting Bloom / Cuckoo** | lo mismo, con borrado (p. ej. `merge()` de entidades) | **No** — mismo motivo; no hay conjunto grande ni mutación de alta frecuencia |
| **Quotient** | dedup en estructura en disco tipo LSM-tree | **No** — ODIN no tiene un store en disco propio; la base ya indexa |
| **Scalable Bloom** | frontier de crawl de tamaño desconocido | **No hoy** — el frontier son cientos de URLs y cabe de sobra en un `set` |
| **HyperLogLog** | conteo aproximado de entidades / artículos únicos | **No** — los conteos son de cientos; `COUNT(DISTINCT ...)` es exacto e instantáneo |
| **SimHash / MinHash + LSH** *(fuera de la tabla)* | near-duplicados de contenido entre fuentes | **Único con valor real**, pero **futuro** y solo si el golden set lo pide |

## Puntos de inserción analizados

### 1. `_already_stored()` — no re-analizar un artículo ya guardado
`src/odin/core/pipeline.py:50`

Por cada URL descubierta en un crawl se hace
`SELECT Article.id WHERE url = ?`. `articles.url` es `UNIQUE` (índice B-tree).

Un Bloom filter delante de esa consulta solo ahorraría trabajo si "ya vista"
fuera el caso dominante sobre **millones** de URLs y la consulta fuera el
cuello de botella. Aquí son cientos de URLs por corrida y **cada una ya costó
un `requests.get` con `settings.request_delay` obligatorio** (segundos): el
`SELECT` indexado es ruido frente a eso. Además, un positivo del Bloom no
evita la consulta — hay que ir a la base igual para descartar el falso
positivo. Solo suma una estructura que mantener.

### 2. Dedup de URLs en el descubrimiento
`src/odin/scrapers/base.py:220` (`BaseScraper.discover_urls`, `seen: set[str]`)

Ya usa un `set` para deduplicar URLs dentro de una pasada de descubrimiento
(RSS + sitemaps). **`set` es la estructura correcta**: son cientos —a lo sumo
unos miles— de strings cortos; entra en RAM mil veces sobre, y es exacto. Un
Bloom solo tendría sentido si ese conjunto no cupiera en memoria, escenario
que no está en la trayectoria del proyecto.

### 3. `canonical_entities.get_or_create` — una fila por (nombre, tipo)
`src/odin/db/canonical_entities.py:24`

`SELECT ... WHERE name = ? AND type = ?` y `INSERT` si no existe.
`(name, type)` es `UNIQUE`. El techo realista es de miles de filas.

Un Counting Bloom o Cuckoo (harían falta *con borrado* por el `merge()` de
entidades canónicas en `canonical_entities.py:65`) no ahorra nada medible a
esta escala y añade una estructura que hay que mantener coherente con la base
en cada `INSERT` y cada `merge`.

### 4. Reuso de análisis reciente — evitar pagar dos veces el LLM
`src/odin/services/analyze_service.py:369-389`

Antes de encolar un análisis se busca si la misma URL ya tiene un `Article`
guardado o un `AnalyzeJob` `done` dentro de una ventana temporal
(`ix_analyze_jobs_url_created_at`). Aquí el motivo de costo **sí es real**
(dinero y rate limit de Gemini/Groq), pero:

- El lookup ya es exacto y barato (índice + ventana de minutos).
- Un Bloom introduce **falsos positivos**, y un falso positivo aquí significa
  "creer que existe un análisis que no existe" → servir un resultado
  inexistente o saltarse un análisis que el usuario pidió. Inaceptable para
  este caso de uso.

No aplica.

### 5. `_RobotsCache` / `_DomainThrottle`
`src/odin/scrapers/base.py:94` y `src/odin/scrapers/base.py:126`

Diccionarios indexados por dominio, con **9 dominios**. No hay nada que
optimizar.

### 6. `politics_filter.is_dominican_politics`
`src/odin/analysis/politics_filter.py:106`

Es **clasificación por palabras clave**, no una pregunta de pertenencia a un
conjunto. Los filtros de la tabla no aplican conceptualmente.

## Cuándo reconsiderar

Señales concretas que cambiarían el veredicto. Ninguna está en la trayectoria
actual (crawl manual, corpus de cientos, un worker):

- **Frontier de crawl > ~1–5 millones de URLs vivas por corrida**, o dedup de
  URLs movido fuera de una base compartida (workers sin acceso al índice
  `UNIQUE`) → **Bloom / Scalable Bloom** delante del store de URLs, con la
  base como verificación del positivo.
- **`canonical_entities` del orden de 10⁷ filas o más** con lookups en un
  camino caliente sin base local → **Cuckoo filter** (soporta el borrado que
  exige `merge()`).
- Necesidad de *"¿cuántos X únicos?"* sobre un flujo que no cabe en memoria ni
  en un `COUNT(DISTINCT)` razonable → **HyperLogLog**.

Regla práctica: un filtro probabilístico se paga solo cuando el conjunto no
cabe en RAM **y** la consulta exacta (índice o red) está en el camino
crítico. ODIN no cumple ninguna de las dos condiciones hoy.

## Alternativa fuera de la tabla: near-duplicados de contenido

El problema real de un corpus de prensa dominicana es la **misma nota
publicada por varias fuentes** (cable de EFE/AP, comunicado oficial,
teletipo) con URLs legítimamente distintas.

- `canonical_url()` (`src/odin/core/url_guard.py:165`) + `UNIQUE` en
  `articles.url` **no lo detecta**: las URLs son distintas de verdad.
- Bloom / Cuckoo **tampoco**: comparan igualdad exacta de una clave.

La herramienta correcta es una de similitud de contenido:

- **SimHash** — hash de 64 bits del cuerpo normalizado; dos artículos son
  casi iguales si la distancia de Hamming entre sus hashes es pequeña.
  Barato de calcular y comparar.
- **MinHash + LSH** — estima el índice de Jaccard sobre *shingles* de
  palabras; LSH agrupa candidatos sin comparar todos contra todos.

**Recomendación: no implementarlo ahora.** Anotarlo como candidato para
cuando el golden set crezca y la deduplicación de contenido sea un problema
medible. Encajaría en la etapa de filtrado de `pipeline.run()`, junto a
`politics_filter`, marcando (no borrando) los artículos sospechosos de ser
duplicados de uno ya guardado para que un documentalista decida.
