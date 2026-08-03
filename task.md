# Odin — Auditoría técnica y backlog de madurez

> Revisión hecha el **2026-08-02** sobre el árbol de trabajo completo (backend,
> frontend, infra, docs, y el corpus real en `odin.db`).
> Perspectiva: ingeniería de software con foco en **pipelines de extracción de
> datos** (crawling, parsing, NLP, calidad de datos).
>
> Cada hallazgo trae **evidencia** (archivo:línea), **impacto** real y **acción**
> concreta. Al final hay un roadmap priorizado (P0/P1/P2).
>
> El análisis de producto y las preguntas al cliente que estaban antes en este
> archivo se conservan íntegros en el **Anexo A** (§15).

---

## 0. Veredicto ejecutivo

Odin es un **prototipo bien escrito** que ya hace end-to-end lo que promete:
descubre URLs de 8 medios dominicanos, extrae artículos, los analiza (NER +
sentimiento, local o LLM) y los persiste con una UI para revisar y corregir.
El código es legible, con docstrings de calidad inusual, separación de
responsabilidades razonable y una abstracción `Analyzer` genuinamente bien
puesta.

Pero **no es todavía un sistema de datos**: es un script con una API encima.
La distancia hasta "producto que un cliente puede usar en producción" no está
en features, está en fundamentos que hoy faltan por completo:

| Dimensión | Estado | Nota |
|---|---|---|
| Funcionalidad núcleo | 🟢 Funciona | Pipeline completo, 8 fuentes, UI |
| Calidad del código | 🟢 Buena | Legible, documentado, tipado parcial |
| **Control de versiones** | 🔴 **Inexistente** | **No hay repositorio git** |
| **Pruebas** | 🔴 **Inexistente** | 0 tests, 0 fixtures, 0 CI |
| **Evaluación del modelo** | 🔴 **Inexistente** | Precisión publicada sin evidencia |
| Seguridad | 🔴 Crítico | Sin auth, SSRF, CORS abierto, costo abusable |
| Arquitectura | 🟡 Frágil | Trabajo pesado síncrono, sin colas, sin estado |
| Modelo de datos | 🟡 Incompleto | Sin dimensión de entidad, sin linaje, sin índices |
| Observabilidad | 🔴 Inexistente | Sin métricas, sin trazas, sin dead-letter |
| Estructura / tooling | 🔴 Débil | Sin pyproject, sin lock, sin lint/format/types |
| Documentación | 🟡 Buena pero drift | Excelente prosa, ya desactualizada y sin ADRs |
| Legal / cumplimiento | 🔴 Sin abordar | Copyright, robots.txt, datos personales |

**Riesgo #1**: no hay git. Todo el trabajo vive en un solo directorio sin
historia, sin ramas y sin backup. Un `rm` mal puesto borra el proyecto entero.
Además bloquea CI, revisión de código y el cron de GitHub Actions que ya está
escrito en [deploy-test.md](deploy-test.md).

**Riesgo #2**: si esto se expone a internet tal como está (que es exactamente lo
que propone [deploy-test.md](deploy-test.md)), cualquiera puede borrar tu catálogo
de aliases, inyectar artículos falsos, usar tu servidor como proxy hacia redes
internas y quemar tu cuota de Gemini.

**Contexto que da urgencia a todo lo demás** — consulta directa a `odin.db`:

```
articles: 7   (diario_libre 5, manual 2)
entities: 82  (80 nombres distintos)
articles con framing != NULL: 0
entity_aliases: 119
```

El pipeline masivo **prácticamente no se ha ejercido**. Con 80 nombres distintos
en 82 menciones, la maquinaria de canonicalización y fusión —que es la parte más
sofisticada del código— nunca se ha enfrentado a volumen real. Y ningún registro
guardado tiene campos de encuadre, o sea que toda la ruta de `GeminiAnalyzer`
está construida pero no validada contra data persistida.

Traducción: **los problemas de este documento aún no han dolido porque no ha
habido carga.** Es el mejor momento posible para arreglarlos, y también el
momento en que más fácil es no hacerlo.

---

## 1. Lo que está bien hecho (para no romperlo)

Vale la pena nombrarlo porque son decisiones que hay que **preservar** en el
refactor:

- **`Analyzer` como Protocol** ([analysis/base.py:43](analysis/base.py#L43)) —
  la abstracción correcta en el lugar correcto. Cambiar local↔Gemini no toca
  scrapers, pipeline ni BD. Es lo que hace posible todo lo demás.
- **Descubrimiento por sitemap/RSS en lugar de selectores CSS**
  ([scrapers/base.py](scrapers/base.py)) — la decisión que hace que agregar un
  medio cueste 4 líneas ([scrapers/do_scrapers.py](scrapers/do_scrapers.py)) en
  vez de un día. Es la elección de alguien que ya sufrió scrapers frágiles.
- **`trafilatura` para extracción** — misma lógica: robustez sobre precisión
  quirúrgica.
- **Canonicalización en un solo módulo**
  ([analysis/canonicalize.py](analysis/canonicalize.py)), aplicada en los tres
  puntos de escritura (preview, guardado manual, crawl). La regla de
  desambiguación (solo apellidos únicos; los ambiguos se dejan quietos) es
  correcta y conservadora.
- **Control de costo del LLM explícito**: `thinking_budget=0`, todos los casos
  ambiguos en una sola llamada, tope de `max_output_tokens`, árbitro solo en el
  flujo manual. Alguien pensó en la factura.
- **Carga perezosa de modelos** — `main.py --list-sources` no carga 500 MB.
- **Cache de Docker por capas + BuildKit + volumen `hf_cache`** — bien pensado
  y bien documentado.

---

## 2. Ingeniería de datos y extracción (la lente principal)

La sección que más pesa: el producto **es** un pipeline de extracción, y es donde
faltan las piezas más caras de agregar después.

### 2.1 🔴 No hay linaje ni versionado del análisis

**Evidencia**: [db/models.py:36-72](db/models.py#L36) — `Article` guarda el
resultado del análisis pero no guarda **quién lo produjo**.

No hay ninguna columna que diga qué analizador corrió (`local` vs `gemini`), qué
modelo (`es_core_news_lg` 3.8.0, `gemini-3.5-flash`), qué versión del prompt,
cuándo se analizó, ni qué versión del esquema de salida.

**Impacto** (grave en extracción, no cosmético):
- No puedes responder "¿por qué esta fila dice NEG?" tres meses después.
- No puedes hacer **backfill selectivo**: si mejoras el prompt, no hay forma de
  saber qué filas están viejas y hay que re-analizar.
- No puedes comparar analizadores sobre el mismo corpus.
- Conviven en la misma tabla filas de `LocalAnalyzer` (con `framing=NULL`) y de
  `GeminiAnalyzer` (con framing) sin poder distinguirlas salvo por la ausencia
  de campos — heurística frágil que rompe cualquier agregación seria.

**Acción**: agregar a `articles`:
```
analyzer_name      VARCHAR(40)   -- "local" | "gemini"
analyzer_model     VARCHAR(80)   -- "es_core_news_lg-3.8.0" | "gemini-3.5-flash"
analyzer_version   VARCHAR(20)   -- versión del prompt/heurística
analysis_schema_v  INTEGER       -- versión de AnalysisResult
analyzed_at        TIMESTAMPTZ
```
y que `Analyzer` exponga esos metadatos como propiedades (`name`, `model`,
`version`) en vez de que el pipeline los adivine.

### 2.2 🔴 No se conserva el payload crudo

**Evidencia**: [scrapers/base.py:185-187](scrapers/base.py#L185) — el HTML se
descarga, se pasa a `trafilatura` y se descarta. `ScrapedArticle._raw` guarda el
JSON de trafilatura pero **tampoco se persiste**
([pipeline.py:37-57](pipeline.py#L37)).

**Impacto**: cada vez que mejores la extracción (o trafilatura saque una versión
mejor, o quieras un campo nuevo como "número de fotos" o "sección real del
breadcrumb"), hay que **volver a rastrear internet entero**. Y los artículos
viejos ya no están: los medios dominicanos rotan y borran. Estás perdiendo datos
irrecuperables en cada corrida.

Regla de oro en extracción: **guarda el crudo, deriva lo demás.** La extracción
es una transformación reproducible; el fetch no.

**Acción**: capa de almacenamiento crudo — tabla `raw_documents` o, mejor, object
storage (S3/GCS/R2) con la BD guardando la key, más
`url, fetched_at, http_status, etag, last_modified, content_hash, html_gzip`.
Con `content_hash` además resuelves la deduplicación real: hoy el mismo artículo
republicado en otra URL entra dos veces.

### 2.3 🔴 Los fallos de extracción se pierden en silencio

**Evidencia**:
- [scrapers/base.py:141-145](scrapers/base.py#L141) — fetch fallido → `log.warning` → `None`.
- [scrapers/base.py:150-152](scrapers/base.py#L150) — extracción vacía → `None`.
- [scrapers/base.py:199-204](scrapers/base.py#L199) — excepción → `log.exception` → `continue`.
- [pipeline.py:104-106](pipeline.py#L104) — error al persistir → rollback + log.

Ninguno deja rastro en la base de datos.

**Impacto**: no tienes **tasa de cobertura**. Si mañana Listín cambia su sitemap
y el 60% de las URLs empieza a fallar, el pipeline reporta alegremente
"12 artículos nuevos" y nadie se entera. Para un cliente que paga por monitoreo
de prensa, un silencio parcial es peor que una caída total: no se nota.

**Acción**: tabla `fetch_log` (`url, source, attempted_at, status, error_class,
error_detail, retry_count`) escrita **siempre**, éxito o fallo. De ahí salen las
métricas que importan —`discovered / fetched_ok / extracted_ok / analyzed_ok /
persisted` por fuente y por corrida— y una cola de reintentos (dead-letter) para
lo transitorio.

### 2.4 🔴 No existe conjunto de evaluación (golden set)

**Evidencia**: [README.md:258-266](README.md#L258) publica una tabla de precisión
— "Sentimiento global: ~75-85%", "Figuras y empresas: ~80%", "Opinión hacia una
figura concreta: ~60-70%".

**No existe ningún artefacto en el repo que respalde esos números.** Ni un CSV
etiquetado, ni un script de evaluación, ni un notebook.

**Impacto**: el hallazgo más serio desde el punto de vista de extracción de datos.
Sin golden set:
- Esos porcentajes son, en el mejor caso, una impresión; en el peor, una
  afirmación que un cliente puede tomar como compromiso contractual.
- No puedes saber si un cambio en las heurísticas de
  [local_analyzer.py](analysis/local_analyzer.py) —que ya tiene reglas muy
  específicas: `_VENUE_WORDS`, `_is_named_after_place`, `_preceded_by_venue_noun`—
  **mejora o empeora** el resultado. Estás optimizando a ciegas.
- No puedes justificar el costo de Gemini con datos. Es literalmente la
  pregunta 6 que le haces al cliente en el §15, y hoy no puedes responderla tú.

**Acción** (esto es P0, no P2):
1. Etiquetar a mano **150-300 artículos** reales. Por artículo: entidades
   correctas con su tipo, sentimiento global, sentimiento hacia cada entidad.
   Repartidos por fuente y por sección.
2. `tests/eval/` con el corpus versionado (JSONL) + `scripts/evaluate.py` que
   corra un analizador y saque **precision / recall / F1 por tipo de entidad**,
   matriz de confusión de sentimiento y accuracy de `sentiment_toward`.
3. Correrlo en cada cambio de heurística. Publicar el número real en el README
   con fecha y tamaño de muestra, reemplazando los rangos actuales.

### 2.5 🟠 No hay política de re-crawl ni detección de cambios

**Evidencia**: [pipeline.py:98](pipeline.py#L98) —
`if _already_stored(session, scraped.url): continue`. Una URL vista una vez no se
vuelve a mirar jamás.

**Impacto**: los medios **editan** artículos: corrigen titulares, agregan
párrafos, cambian el enfoque tras una aclaración. Precisamente los cambios de
titular son señal periodística valiosa para un producto de análisis de prensa, y
los estás descartando. Tampoco usas `ETag`/`Last-Modified`, así que ni siquiera
podrías re-verificar barato.

**Acción**: `content_hash` + revisita programada de artículos recientes (p. ej. a
las 6 h y 24 h) con `If-None-Match` / `If-Modified-Since`; si el hash cambia,
versionar en `article_revisions` en vez de sobrescribir.

### 2.6 🟠 La cortesía documentada no existe en el código

**Evidencia**:
- [README.md:276-277](README.md#L276): *"Se respeta un retardo entre peticiones (`REQUEST_DELAY`)"*.
- [scrapers/base.py:144](scrapers/base.py#L144): `REQUEST_DELAY` se usa
  **únicamente** dentro del `except`, como base del backoff exponencial.
- [scrapers/base.py:196-198](scrapers/base.py#L196): 4 workers concurrentes contra
  el mismo dominio, **sin ningún delay entre peticiones exitosas**.
- `robots.txt` no se lee en ninguna parte del código.

**Impacto**: el README afirma una conducta que el código no implementa. En el
camino feliz el crawler pega ~4 peticiones concurrentes seguidas al mismo host,
tan rápido como responda. Con sitemaps de ~180 URLs (hoy.com.do) eso es un patrón
que un WAF puede leer como abuso — y el `User-Agent` es identificable y lleva tu
email personal ([config.py:27](config.py#L27)), así que el bloqueo tendría nombre
y apellido.

**Acción**: throttle real **por dominio** (token bucket), no por
`ThreadPoolExecutor`; parsear y respetar `robots.txt` (`urllib.robotparser`)
incluido `Crawl-delay`; corregir el README; sustituir el email personal por uno
de proyecto.

### 2.7 🟠 Mezcla de datetimes naive y aware

**Evidencia**: [scrapers/base.py:51-66](scrapers/base.py#L51) — `_parse_date`
devuelve **aware** por la rama `fromisoformat` (con offset o `Z`) y **naive** por
la rama `strptime` (`%Y-%m-%d`, `%d/%m/%Y`). Ambos van a columnas
`DateTime(timezone=True)` ([db/models.py:47](db/models.py#L47)).

**Impacto**: Postgres interpreta el naive según el timezone del servidor; SQLite
lo guarda tal cual. El mismo dato produce resultados distintos según el motor y
según dónde corra. Los filtros de fecha de la API
([api.py:276-283](api.py#L276)) comparan contra un `_parse_date` que puede
devolver naive → comparaciones inconsistentes y artículos que se "pierden" en los
bordes del día. En un producto de monitoreo diario eso se nota rápido.

**Acción**: normalizar **todo** a UTC aware en el borde (`_parse_date` siempre
devuelve aware, asumiendo `America/Santo_Domingo` cuando la fuente no da offset)
y documentar la convención.

### 2.8 🟡 Truncados silenciosos

**Evidencia**: [local_analyzer.py:30-31](analysis/local_analyzer.py#L30) —
`_MAX_SENTENCES = 400`, `_MAX_SENT_CHARS = 500`;
[gemini_analyzer.py:29](analysis/gemini_analyzer.py#L29) — `_MAX_BODY_CHARS = 16_000`.
Un reportaje largo se analiza parcialmente y **nada en el registro lo indica**.

**Acción**: banderas `was_truncated` y `analyzed_chars` en el resultado y en la BD.

---

## 3. Arquitectura

### 3.1 🔴 Trabajo pesado y de red dentro del ciclo request/response

**Evidencia**: [api.py:166-220](api.py#L166) — `POST /api/analyze` hace,
síncronamente dentro del handler: fetch HTTP externo (hasta 3 intentos × 20 s de
timeout = **60 s** solo de red, [scrapers/base.py:137](scrapers/base.py#L137)),
extracción, inferencia de spaCy + pysentimiento sobre el artículo completo y,
opcionalmente, **una llamada a Gemini** ([api.py:641-666](api.py#L641)).

Además todos los endpoints son `def` (no `async def`), así que FastAPI los corre
en el threadpool (40 hilos por defecto) — y el analizador es una **instancia
global compartida** ([api.py:64-69](api.py#L64)) con modelos PyTorch/spaCy que no
están pensados para uso concurrente sin control.

**Impacto**: una petición puede tardar minutos, sin cancelación ni timeout; N
peticiones concurrentes multiplican la memoria de los modelos y saturan el
threadpool, bloqueando hasta `/api/health`. Cualquier proxy delante (nginx,
Cloud Run) cortará por timeout antes de que termine, dejando trabajo huérfano.

**Acción**: partir en dos. `POST /api/analyze` encola un job y devuelve `202` +
`job_id`; `GET /api/jobs/{id}` devuelve estado/resultado. Worker aparte (arq, RQ,
Celery — o para empezar barato, `BackgroundTasks` + tabla `jobs`). De paso, el
frontend gana progreso real.

### 3.2 🔴 El analizador se elige por presencia de una credencial

**Evidencia**: [api.py:64-70](api.py#L64):
```python
if os.getenv("GEMINI_API_KEY"):
    _analyzer = GeminiAnalyzer()
else:
    _analyzer = LocalAnalyzer()
```
Y [docker-compose.yml](docker-compose.yml) monta `env_file: .env` en `backend`,
donde `GEMINI_API_KEY` **está definida** (verificado).

**Impacto**: `docker compose up` arranca el backend en modo **de pago** sin que
nadie lo pida. Contradice directamente la política de costo de
[CLAUDE.md](CLAUDE.md). Y "tener la llave configurada" no es lo mismo que "quiero
pagar por cada análisis": la llave puede estar ahí solo para el árbitro puntual,
o para el CLI, o simplemente porque quedó en el `.env`.

**Acción**: variable explícita `ODIN_ANALYZER=local|gemini` (default `local`),
igual que ya hace bien el CLI ([main.py:35-40](main.py#L35)). La presencia de una
credencial nunca debe ser un interruptor de comportamiento facturable.

### 3.3 🟠 `init_db()` en el camino caliente

**Evidencia**: [api.py:573](api.py#L573) — `save_article` llama `init_db()` en
**cada request**, e `init_db` ejecuta `_add_missing_columns`, que hace
`inspect(engine)` con `get_columns()` sobre todas las tablas
([db/session.py:42-64](db/session.py#L42)) más un `create_all`.

**Impacto**: consultas de metadata y posible DDL en cada guardado — latencia
innecesaria y riesgo de contención de locks bajo concurrencia.

**Acción**: quitarlo; ya se ejecuta en el `lifespan` ([api.py:41-51](api.py#L41)).

### 3.4 🟠 Migraciones caseras en lugar de Alembic

**Evidencia**: [db/session.py:42-64](db/session.py#L42) — `_add_missing_columns`
construye DDL por interpolación de strings y **solo** agrega columnas nullables.

Es una solución honesta y bien comentada para un prototipo, pero: no renombra, no
borra, no cambia tipos, no hace backfill; no tiene versión (no puedes saber en qué
estado está una BD); no es reversible; y ejecuta DDL automáticamente al arrancar
la app, en producción, sin revisión.

**Impacto**: el primer cambio de esquema no trivial —que va a ser el de §4.1— no
lo puede hacer este mecanismo, y para entonces ya habrá datos del cliente.

**Acción**: Alembic ahora, mientras la BD tiene 7 filas. `alembic stamp head`
sobre el esquema actual y de ahí en adelante migraciones versionadas. Desactivar
el DDL automático al arrancar.

### 3.5 🟡 Configuración congelada en tiempo de import

**Evidencia**: [config.py:15-31](config.py#L15) — los defaults del dataclass se
evalúan **una vez, al importar el módulo**, y `settings` es un singleton inmutable.

**Impacto**: no puedes cambiar configuración en tests sin recargar módulos;
`Settings()` construido de nuevo no relee el entorno. Y no hay validación: un
`FETCH_WORKERS=abc` revienta con un `ValueError` críptico durante el import.

**Acción**: `pydantic-settings` (`BaseSettings`) con validación de rangos y un
`get_settings()` cacheado e invalidable.

### 3.6 🟡 El frontend asume que siempre hay un proxy

**Evidencia**: [frontend/src/lib/odin-api.ts:137](frontend/src/lib/odin-api.ts#L137)
— `const BASE = ""`.

Funciona en dev (proxy de Vite) y en Docker (nginx). **No funciona** en el
despliegue que propone [deploy-test.md](deploy-test.md) (frontend en Vercel,
backend en Cloud Run: orígenes distintos).

**Acción**: `BASE = import.meta.env.VITE_API_BASE ?? ""`.

---

## 4. Modelo de datos

### 4.1 🔴 No existe una dimensión canónica de entidad

**Evidencia**: [db/models.py:78-103](db/models.py#L78) — la tabla `entities` es en
realidad una tabla de **menciones** (`article_id` + `name` como string).
`entity_aliases` mapea sigla→string canónico, pero tampoco apunta a una entidad.

**Impacto**: toda la analítica que justifica el producto agrupa por **cadena de
texto**:
- [report.py:36-41](report.py#L36) hace `GROUP BY Entity.name, Entity.type`.
- Filtrar por entidad en la API es `ILIKE '%texto%'` ([api.py:293-296](api.py#L293)).

Consecuencias: "Luis Abinader" y "Presidente Abinader" son dos entidades distintas
en los reportes; el filtro `entity=Fernández` mezcla a Leonel, Omar y César; no
puedes adjuntar atributos a una entidad (partido, cargo, sector, si es figura
pública o privada); y todo el aparato de canonicalización —que es sofisticado y
está bien hecho— es un parche sobre un modelo que no tiene dónde guardar la
identidad.

Además esto bloquea directamente lo que el cliente probablemente va a pedir
(§15, pregunta 3): una **lista de entidades vigiladas** necesita que la entidad
sea una fila con identidad, no un string repetido en 500 menciones.

**Acción**: modelo estrella real.
```
entity          (id, canonical_name, type, slug, created_at, notes)   ← dimensión
entity_alias    (id, entity_id FK, alias, alias_key, is_active)       ← ya casi existe
entity_mention  (id, article_id FK, entity_id FK, surface_form,
                 mentions_count, sentiment_toward, sentiment_score, context)
```
`article.dominant_actor` / `blamed_actor` / `credited_actor` pasan a ser FKs a
`entity.id` en vez de strings sueltos — hoy son `String(300)` con un
`match_actor_name` que "reapunta" por comparación textual
([canonicalize.py:167-182](analysis/canonicalize.py#L167)).

Es **la** refactorización que hay que hacer antes de acumular volumen. Con 7
artículos cuesta una tarde; con 50.000 cuesta un proyecto.

### 4.2 🟠 Índices ausentes en las columnas que realmente se consultan

**Evidencia**: [db/models.py:36-67](db/models.py#L36) — hay índice en `source`,
`url` (unique) y `Entity.name`. **No hay índice** en:
- `published_at` — que es la columna de **ordenación por defecto** de
  `GET /api/articles` ([api.py:370](api.py#L370)) y la de los filtros de rango;
- `overall_sentiment`, `framing`, `headline_intent`, `lead_orientation`,
  `source_quality`, `has_hard_data` — todas expuestas como filtros
  ([api.py:245-299](api.py#L245));
- `scraped_at`.

Además la búsqueda de texto es `ILIKE '%q%'` sobre `title`, `main_topic` y
`topic_keywords` ([api.py:284-292](api.py#L284)): con comodín a la izquierda
**ningún índice B-tree puede usarse**, es seq scan siempre.

**Acción**: índice en `published_at` (desc), compuesto `(source, published_at)`,
e índices en los campos de encuadre. Para búsqueda: `tsvector` + GIN en Postgres
(aceptando que SQLite degrade a `LIKE`), o `pg_trgm` si quieres subcadena real.

### 4.3 🟠 N+1 garantizado en el listado

**Evidencia**: [api.py:322](api.py#L322) — `_serialize_summary` hace
`len(article.entities)`, que dispara una carga perezosa **por cada artículo** de
la página. Con `limit=100` son 101 queries.

**Acción**: subconsulta con `func.count` agrupada, `selectinload(Article.entities)`,
o mejor: columna denormalizada `entity_count` mantenida en la escritura.

### 4.4 🟡 `list_aliases` trae todo y filtra en Python

**Evidencia**: [api.py:436-456](api.py#L436) — carga **todas** las filas (ya son
119) y luego filtra con un `in` de Python. Sin paginación.

**Acción**: filtrar en SQL con `ILIKE` y paginar.

### 4.5 🟡 Normalización inconsistente entre módulos

**Evidencia**:
- [db/aliases.py:77](db/aliases.py#L77) — `resolve()` usa `name.strip().lower()`.
- [canonicalize.py:45-47](analysis/canonicalize.py#L45) — `_norm_key()` usa lower
  **+ quita acentos** + colapsa espacios.
- [local_analyzer.py:134-136](analysis/local_analyzer.py#L134) — otra copia de
  `_norm_key`, idéntica.

**Impacto**: un alias guardado como "Policía Nacional" **no resuelve** si el texto
trae "Policia Nacional" sin tilde — caso frecuente en teletipos y titulares en
mayúsculas. Y hay tres definiciones de "normalizar un nombre" en tres módulos,
dos de ellas duplicadas literalmente.

**Acción**: un único `analysis/normalize.py` con `norm_key()`, usado por todos
(incluido el cálculo de `alias_key` al insertar). Migración para recalcular
`alias_key` de las 119 filas existentes.

### 4.6 🟡 Sin retención ni ciclo de vida

`body` guarda el texto completo de cada artículo, indefinidamente, sin política de
retención, sin borrado, sin archivado. Ver también §8.

---

## 5. Seguridad

### 5.1 🔴 SSRF en `POST /api/analyze`

**Evidencia**: [api.py:166-182](api.py#L166) — la única validación de la URL que
suministra el usuario es:
```python
if not url.startswith(("http://", "https://")):
```
Luego [scrapers/base.py:137](scrapers/base.py#L137) hace
`self.session.get(url, timeout=20)` —con **redirecciones habilitadas**, el default
de `requests`— y el contenido extraído **se devuelve al llamante**
([api.py:187-220](api.py#L187)).

**Impacto**: el servidor es un proxy de lectura hacia cualquier cosa que él alcance
y tú no:
- `http://169.254.169.254/...` — metadata de GCP/AWS, y
  [deploy-test.md](deploy-test.md) propone **Cloud Run**, donde ese endpoint existe;
- `http://db:5432`, `http://localhost:8000`, cualquier host de la red interna de
  Docker o de la VPC;
- escaneo de puertos internos por diferencia de mensajes de error (422 "no se pudo
  descargar" vs 422 "no parece un artículo").

Y como no hay autenticación (§5.2), **cualquiera en internet** puede hacerlo.

**Acción**:
- Resolver el hostname **antes** de conectar y rechazar IPs privadas, loopback,
  link-local (169.254/16), CGNAT y multicast — revalidando en **cada salto de
  redirección** (o `allow_redirects=False` y seguirlas a mano).
- Allowlist de dominios: el producto solo necesita ~8 medios dominicanos. Una
  allowlist es defensa mucho más fuerte que una denylist de IPs y aquí encaja
  perfecto con el dominio del negocio.
- Limitar tamaño de respuesta (`stream=True` + corte a N MB) y `Content-Type`.

### 5.2 🔴 Cero autenticación y CORS totalmente abierto

**Evidencia**: [api.py:56-61](api.py#L56):
```python
allow_origins=["*"], allow_methods=["*"], allow_headers=["*"]
```
Ningún endpoint tiene dependencia de auth. Los que **escriben**:
`POST /api/articles`, `POST /api/aliases`, `PUT /api/aliases/{id}`,
`DELETE /api/aliases/{id}`.

**Impacto**: cualquiera que alcance la API puede borrar todo el catálogo de
aliases (119 entradas curadas a mano en
[db/seed_aliases.py](db/seed_aliases.py)), inyectar artículos falsos con el
sentimiento que quiera, o envenenar los reportes que el cliente va a leer. Para un
producto sobre reputación de figuras públicas, **inyección de datos es el peor
escenario posible**: no rompe el sistema, lo hace mentir.

**Acción**: API key o JWT en todos los endpoints de escritura y en `/api/analyze`
(el caro). CORS restringido al origen real del frontend, por variable de entorno.

### 5.3 🔴 Amplificación de costo hacia la API de pago

**Evidencia**: `POST /api/analyze` sin auth ni rate limit, que en el peor caso
(§3.2: backend arrancado con `GeminiAnalyzer` porque la llave está en `.env`) hace
**una llamada facturada por request**, más el árbitro
([api.py:641-666](api.py#L641)).

**Impacto**: un bucle trivial contra tu endpoint público vacía tu cuota de Gemini.
Es una denegación de servicio **con cargo a tu tarjeta**, y contradice frontalmente
la política de [CLAUDE.md](CLAUDE.md).

**Acción**: auth + rate limit por cliente + presupuesto diario con cortacircuito
(contador persistido; al superar N llamadas/día degrada a `LocalAnalyzer` y alerta).

### 5.4 🟠 Sin límites de entrada

- `SaveArticleRequest.body: str` ([api.py:96](api.py#L96)) — sin `max_length`.
  Nada impide un POST de 100 MB.
- `entities: list[EntityPayload]` ([api.py:107](api.py#L107)) — sin tope de elementos.
- `limit` de listado sí está acotado a 100 ([api.py:346](api.py#L346)) — bien hecho.
- Sin límite global de tamaño de request en uvicorn/nginx.

### 5.5 🟠 Contenedores como root, sin hardening

**Evidencia**: [Dockerfile.backend](Dockerfile.backend) no tiene `USER`; el proceso
corre como root. Tampoco hay `HEALTHCHECK` ni límites de recursos en
[docker-compose.yml](docker-compose.yml).
[frontend/nginx.conf](frontend/nginx.conf) no envía ninguna cabecera de seguridad
(`X-Content-Type-Options`, `X-Frame-Options`, `Referrer-Policy`, CSP) ni oculta
`Server`.

### 5.6 🟠 Dependencias sin fijar y sin escaneo

**Evidencia**: [requirements.txt](requirements.txt) usa solo `>=`. No hay
`requirements.lock`, ni `pyproject.toml`, ni hashes.

**Impacto**: dos builds del mismo código pueden instalar versiones distintas — el
clásico "en mi máquina funciona". Y sin lock no hay superficie sobre la que correr
`pip-audit` o Dependabot de forma significativa.

### 5.7 🟡 Filtrado de errores hacia el cliente

`_fetch_and_extract` distingue "no se pudo descargar" de "no parece un artículo"
([api.py:126-147](api.py#L126)); combinado con §5.1 es un oráculo para sondear la
red interna. Unificar el mensaje en el borde y dejar el detalle solo en los logs.

---

## 6. Calidad, pruebas y CI

### 6.1 🔴 Cero pruebas

No existe `tests/`, ni pytest, ni fixtures, ni un solo caso. Para **6.500 líneas**
con lógica no trivial, es el mayor riesgo de regresión del proyecto.

Lo que más duele que no esté probado, por densidad de reglas por línea:
- `analysis/canonicalize.py` — fusión, desambiguación por apellido único,
  `match_actor_name`. Lógica sutil, con casos límite explícitos en los docstrings
  que **son casos de prueba ya escritos en prosa** (solo falta transcribirlos).
- `local_analyzer._merge_aliases` y las heurísticas `_VENUE_WORDS` /
  `_is_named_after_place` / `_preceded_by_venue_noun`.
- `scrapers.base._parse_date` y `_urls_from_sitemap` — parsers puros,
  trivialmente testeables, hoy sin una sola aserción.
- Los filtros de `GET /api/articles` (11 parámetros combinables).
- `scripts/merge_duplicate_entities.py` — **modifica la BD en masa**; tiene
  `--dry-run` (bien) pero ninguna prueba.

**Acción**:
- `pytest` + `pytest-cov`; unitarias con HTML fijo en `tests/fixtures/`, nada de red.
- Tests de API con `TestClient` sobre SQLite en memoria.
- `responses`/`respx` para mockear HTTP. Ninguna prueba debe tocar internet, y
  **ninguna debe tocar Gemini** (regla de [CLAUDE.md](CLAUDE.md)): el cliente de
  `google.genai` se mockea siempre.
- Meta razonable: 70% en `analysis/`, `scrapers/`, `db/`.

### 6.2 🔴 Sin CI y sin control de versiones

**No hay repositorio git.** Consecuencias en cadena: sin historia, sin ramas, sin
revisión, sin `git bisect`, sin CI, sin el cron de GitHub Actions que propone
[deploy-test.md](deploy-test.md), sin backup fuera de este disco.

**Acción inmediata**, antes que cualquier otra cosa de este documento: `git init`,
verificar que [.gitignore](.gitignore) cubre `.env` y `*.db` (**sí lo hace**),
commit inicial, remoto privado. Después: CI con lint + types + tests en cada push.

### 6.3 🟠 Sin tooling de calidad en Python

No hay `pyproject.toml`, ni configuración de **ruff** (lint+format), ni
**mypy/pyright**, ni **pre-commit**. El frontend sí tiene `oxlint` y un protocolo
de validación en [.agents/AGENTS.md](.agents/AGENTS.md); el backend no tiene
equivalente.

El código ya usa `from __future__ import annotations` y anotaciones en casi todo:
activar mypy hoy es barato y solo se encarece con el tiempo.

### 6.4 🟠 Código muerto en producción

**Evidencia**: [api.py:627](api.py#L627) —
```python
    return list(merged.values())
```
Está **después** del `finally` de `save_article`, fuera de toda función alcanzable,
y `merged` ni siquiera existe en ese ámbito. Resto de un refactor. Inofensivo hoy,
pero es exactamente el tipo de cosa que un linter habría marcado el mismo día.

### 6.5 🟡 El frontend tampoco tiene pruebas

`App.tsx` (574 líneas) y `ReportsList.tsx` (666 líneas) concentran mucha lógica de
estado y formato sin un solo test. Sin Vitest ni Testing Library —y
[.agents/AGENTS.md](.agents/AGENTS.md) dice "corre los tests si están
configurados", que hoy es una rama que nunca se ejecuta.

---

## 7. Operación y observabilidad

### 7.1 🔴 No hay métricas de nada

Logging con `logging.basicConfig` en texto plano ([main.py:45](main.py#L45)); nada
más. No hay:
- métricas de pipeline (descubiertos / descargados / extraídos / analizados /
  guardados, por fuente y corrida) — **las métricas que definen si el producto
  funciona**;
- latencia ni tasa de error por endpoint;
- contador de llamadas y **gasto** de Gemini, crítico dado el modelo de costo;
- seguimiento de errores (Sentry o equivalente);
- logs estructurados (JSON) ni correlation ID por request/corrida.

**Acción**: `structlog` + `/metrics` (prometheus-client) + tabla `crawl_runs` con
el resumen de cada corrida — que ya se calcula en
[pipeline.py:107](pipeline.py#L107) y se **imprime por consola y se tira**.

### 7.2 🟠 Sin orquestación ni programación

El crawl solo existe como invocación manual del CLI. No hay cron, ni scheduler, ni
`.github/workflows/`. [docs/GUIA_DE_USO.md](docs/GUIA_DE_USO.md) menciona "corridas
periódicas" y [deploy-test.md](deploy-test.md) propone un cron de GitHub Actions,
pero **no está implementado en ninguna parte**. Tampoco hay protección contra
corridas solapadas: dos crawls simultáneos duplicarían trabajo, y el único guard
es la constraint única de `url`.

Es la explicación técnica de por qué `odin.db` tiene 7 artículos.

### 7.3 🟠 Sin healthcheck real ni readiness

[api.py:706-708](api.py#L706) — `/api/health` devuelve `{"status":"ok"}`
incondicionalmente: responde OK aunque la base de datos esté caída y aunque los
modelos no hayan cargado. Un orquestador lo daría por sano mientras todo falla.

**Acción**: `/api/health` (liveness, trivial) + `/api/ready` (verifica `SELECT 1` y
que los modelos estén cargados).

### 7.4 🟡 Sesión de BD de larga vida en el pipeline

[pipeline.py:88-109](pipeline.py#L88) abre **una** sesión para toda la corrida
(potencialmente ~1.500 artículos × 8 fuentes) y hace commit por artículo. Una
transacción fallida a mitad deja la sesión en estado dudoso; el `rollback` del
`except` ayuda, pero lo correcto es sesión por unidad de trabajo.

### 7.5 🟡 Sin backup ni recuperación

`odin.db` vive en el directorio de trabajo. El volumen `pgdata` de Docker no tiene
rutina de backup. No hay procedimiento de restauración documentado ni probado.

---

## 8. Legal, ético y cumplimiento

No es opcional en un producto que **almacena el texto íntegro de artículos con
copyright** y **emite juicios de valor sobre personas nombradas**.

### 8.1 🟠 Copyright y términos de uso

Se guarda `body` completo de 8 medios, indefinidamente, y la UI lo muestra
([api.py:680](api.py#L680) devuelve el cuerpo entero en `/api/articles/{id}`).
[README.md:278-279](README.md#L278) dice "revisa los términos de uso de cada sitio
antes de un despliegue a gran escala" — es decir, reconoce el problema y lo deja
sin resolver.

**Acción**: revisar ToS de los 8 medios y **documentar el resultado por medio**
(tabla en `docs/LEGAL.md`); decidir si el cuerpo completo es necesario o basta con
el análisis + un extracto; definir retención; respetar `robots.txt` (§2.6).

### 8.2 🟠 Datos personales y perfilado

El producto construye, de forma sistemática y automatizada, un **perfil de opinión
sobre personas identificadas** (`sentiment_toward` por `PERSON`, `blamed_actor`,
`credited_actor`). Eso es tratamiento de datos personales y, en la práctica,
perfilado reputacional. En RD aplica la **Ley 172-13**; si algún dato o usuario
toca la UE, aplica GDPR (art. 22 incluido).

Agravante técnico: el propio README admite que `sentiment_toward` acierta ~60-70%
([README.md:266](README.md#L266)). Es decir, **cerca de 1 de cada 3 juicios sobre
una persona nombrada es incorrecto**, y hoy se muestran en la UI sin ninguna marca
de confianza.

**Acción**:
- Mostrar siempre `sentiment_score` / nivel de confianza junto al veredicto, y un
  descargo explícito de que es una inferencia automática.
- Definir base legal, política de retención y procedimiento de
  rectificación/borrado — que hoy es **imposible**: no hay endpoint de borrado de
  artículos ni de entidades.
- `docs/LEGAL.md` + revisión con alguien de legal antes de entregar al cliente.

### 8.3 🟡 Sesgo y trazabilidad del análisis

Los campos de encuadre (`framing`, `headline_intent`, `lead_orientation`) son
**juicios editoriales** producidos por un LLM con un prompt concreto
([gemini_analyzer.py:104-136](analysis/gemini_analyzer.py#L104)). Sin versionado de
prompt (§2.1) no puedes explicar por qué el sistema clasificó una nota como
"sensacionalista" — y esa clasificación, sobre un medio identificado, es material
sensible.

---

## 9. Estructura del repositorio

### 9.1 Lo que falta

```
❌ .git/                    ← inexistente (bloquea CI, historia, backup)
❌ pyproject.toml           ← metadata, deps, config de ruff/mypy/pytest
❌ requirements.lock        ← builds reproducibles (pip-tools o uv)
❌ tests/                   ← unitarias, integración, fixtures HTML
❌ tests/eval/              ← golden set etiquetado + métricas
❌ .github/workflows/       ← CI (lint, types, tests) + cron del scraper
❌ .pre-commit-config.yaml
❌ alembic/                 ← migraciones versionadas
❌ LICENSE                  ← sin licencia = "todos los derechos reservados"
❌ CHANGELOG.md
❌ Makefile / justfile      ← comandos canónicos (setup, test, lint, run)
❌ docs/adr/                ← decisiones arquitectónicas
❌ .editorconfig
⚠️  odin.db en la raíz      ← ignorado por git, pero conviene moverlo a data/
⚠️  __pycache__/ en la raíz ← limpiar
```

### 9.2 Organización del código

- **`api.py` con 708 líneas** es el archivo más grande del backend y mezcla
  schemas Pydantic, lógica de negocio, acceso a datos, serialización y rutas.
  Partir en `api/routers/{articles,aliases,analyze}.py`, `api/schemas.py`,
  `api/deps.py`, y mover la lógica a `services/`.
- **Serialización triplicada**: `_serialize` ([api.py:669](api.py#L669)) y
  `_serialize_summary` ([api.py:302](api.py#L302)) repiten campo por campo lo que
  ya está en los modelos, y el frontend lo repite **otra vez** en TypeScript
  ([odin-api.ts:27-75](frontend/src/lib/odin-api.ts#L27)). Tres lugares que hay que
  cambiar de la mano cada vez que se agrega un campo — y ya se agregaron 8 (los de
  encuadre). Usar `response_model` de Pydantic y **generar los tipos TS desde el
  OpenAPI** (`openapi-typescript`).
- **Sin capa de servicio**: los handlers HTTP hablan SQLAlchemy directamente.
  Funciona a esta escala, pero impide reutilizar la lógica desde el CLI o desde un
  worker sin duplicarla.
- **`_norm_key` duplicado** en `canonicalize.py` y `local_analyzer.py` (§4.5).
- **`scripts/`** con un solo script que importa símbolos privados de otro módulo
  (`_norm_key`, `_NAME_PARTICLES`,
  [merge_duplicate_entities.py:26](scripts/merge_duplicate_entities.py#L26)) —
  señal de que esa API debería ser pública.
- **Frontend**: componentes de 574 y 666 líneas sin capa de data-fetching (nada de
  React Query/SWR: cada componente maneja loading/error a mano), sin error
  boundary, sin rutas (`react-router`).

---

## 10. Documentación

La documentación es, honestamente, **mejor que la de la mayoría de proyectos de
este tamaño**: [README.md](README.md), [docs/PROCESOS.md](docs/PROCESOS.md) (365
líneas con diagramas mermaid), [docs/GUIA_DE_USO.md](docs/GUIA_DE_USO.md),
[docs/docker.md](docs/docker.md),
[docs/scrapers_nuevas_fuentes.md](docs/scrapers_nuevas_fuentes.md). Los docstrings
explican el **porqué**, no el qué — eso es raro y valioso.

El problema no es la cantidad. Es el **drift** y las audiencias que faltan.

### 10.1 🟠 La documentación ya no describe el código

| Documento | Dice | Realidad |
|---|---|---|
| [README.md:3](README.md#L3) | "rastrea **Listín Diario** y **Diario Libre**" | Hay **8** scrapers registrados ([scrapers/\_\_init\_\_.py:14-23](scrapers/__init__.py#L14)) |
| [README.md:174-192](README.md#L174) | Árbol del código | Faltan `api.py`, `analysis/canonicalize.py`, `analysis/entity_arbiter.py`, `db/aliases.py`, `db/seed_aliases.py`, `scripts/` y **todo** `frontend/` |
| [README.md:276](README.md#L276) | "Se respeta un retardo entre peticiones" | `REQUEST_DELAY` solo se usa en el backoff de reintentos (§2.6) |
| [README.md:260-266](README.md#L260) | Tabla de precisión | Sin evidencia reproducible (§2.4) |
| [docs/PROCESOS.md](docs/PROCESOS.md) | Pipeline de 5 pasos | No cubre el flujo de la API (analizar→revisar→guardar), que es **el flujo principal del producto hoy** |
| [docs/scrapers_nuevas_fuentes.md](docs/scrapers_nuevas_fuentes.md) | El Caribe "en `_draft_do_scrapers.py`" | Ese archivo no existe; ya está en `do_scrapers.py` |

Que el README describa 2 fuentes cuando hay 8 es el síntoma clásico: la
documentación se escribió una vez y el código siguió. Necesita un dueño y un
checkpoint en el flujo de cambios, no más prosa.

### 10.2 🔴 Documentación que no existe y hace falta

**Para el equipo técnico**
- `docs/ARQUITECTURA.md` — diagrama C4 (contexto, contenedores, componentes). Hoy
  hay que leer el código para enterarse de que existe un frontend.
- `docs/adr/` — ADRs de las decisiones no obvias, que **ya se tomaron** y solo
  viven en comentarios: por qué trafilatura y no selectores; por qué sitemaps y no
  portadas; por qué `thinking_budget=0`; por qué migraciones caseras; por qué
  `predict()` por frase en vez de batch
  ([local_analyzer.py:216-224](analysis/local_analyzer.py#L216) — ese comentario
  **es** un ADR sin formato). Escribirlos hoy es barato; reconstruirlos en 6 meses,
  no.
- `docs/DATA_DICTIONARY.md` — cada columna: significado, dominio de valores, quién
  la produce (local vs Gemini), nullability, ejemplo. Imprescindible cuando el
  cliente conecte su BI a la BD.
- `docs/API.md` — hoy solo existe el `/docs` autogenerado: sin ejemplos, sin
  códigos de error, sin límites, sin versionado.

**Para operación**
- `docs/RUNBOOK.md` — qué hacer cuando una fuente deja de responder, cómo
  reintentar una corrida fallida, cómo restaurar un backup, cómo rotar la llave de
  Gemini, a quién escalar.
- `docs/DEPLOY.md` — [deploy-test.md](deploy-test.md) es un **plan**, no un
  procedimiento; está en la raíz (no en `docs/`) y su nombre sugiere borrador.

**Para producto / cliente**
- `docs/LEGAL.md` — ToS por medio, base legal del tratamiento, retención,
  procedimiento de rectificación (§8).
- `docs/PRECISION.md` — metodología de evaluación, tamaño de muestra, resultados
  fechados. Es lo que convierte la tabla del README en una afirmación defendible.

**Del repositorio**
- `LICENSE` — sin archivo de licencia el código es "todos los derechos reservados"
  por defecto. Decisión consciente pendiente.
- `CONTRIBUTING.md` con el flujo de trabajo (hoy inexistente porque no hay git).

### 10.3 🟡 Detalles

- Toda la documentación está en español y es coherente — **buena decisión**,
  mantenerla. Si el cliente o un dev externo necesita inglés, decidirlo
  explícitamente, no a medias.
- [.agents/AGENTS.md](.agents/AGENTS.md) cubre solo frontend; falta el protocolo
  equivalente para backend (ruff, mypy, pytest).
- El README no tiene badges de estado (CI, cobertura) porque no hay CI.

---

## 11. Bugs y quick wins concretos

Cosas puntuales, ya presentes, arreglables en menos de una hora cada una:

| # | Qué | Dónde |
|---|---|---|
| 1 | Código muerto tras el `finally` de `save_article` (`merged` ni existe) | [api.py:627](api.py#L627) |
| 2 | `init_db()` en cada request de guardado | [api.py:573](api.py#L573) |
| 3 | N+1 por `len(article.entities)` en el listado | [api.py:322](api.py#L322) |
| 4 | `list_aliases` filtra en Python en vez de SQL, sin paginación | [api.py:436](api.py#L436) |
| 5 | `%` y `_` del usuario no se escapan en los `ILIKE` de búsqueda | [api.py:285](api.py#L285) |
| 6 | `resolve()` no quita acentos → "Policia" no matchea "Policía" | [db/aliases.py:77](db/aliases.py#L77) |
| 7 | `_norm_key` duplicado en dos módulos | [canonicalize.py:45](analysis/canonicalize.py#L45), [local_analyzer.py:134](analysis/local_analyzer.py#L134) |
| 8 | `import json` dentro de la función en vez de arriba | [api.py:131](api.py#L131) |
| 9 | `if TYPE_CHECKING: pass` sin contenido | [db/aliases.py:29-30](db/aliases.py#L29) |
| 10 | `/api/health` responde OK con la BD caída | [api.py:706](api.py#L706) |
| 11 | Email personal en el `User-Agent` por defecto | [config.py:27](config.py#L27) |
| 12 | `person_map` se calcula una vez por fuente y no se refresca durante la corrida | [pipeline.py:95](pipeline.py#L95) |
| 13 | README dice 2 fuentes; hay 8 | [README.md:3](README.md#L3) |
| 14 | Referencia a `_draft_do_scrapers.py`, archivo inexistente | [docs/scrapers_nuevas_fuentes.md](docs/scrapers_nuevas_fuentes.md) |

---

## 12. Roadmap priorizado

Ordenado por **riesgo × costo de postergar**. Los P0 se encarecen cada día que pasan.

### P0 — Fundamentos (1-2 semanas)

| # | Tarea | Por qué ahora |
|---|---|---|
| 1 | **`git init`** + remoto privado + `.gitignore` verificado | Sin esto no hay red de seguridad ni nada de lo demás |
| 2 | Auth (API key/JWT) en escritura + `/api/analyze`; CORS al origen real | El sistema es escribible por cualquiera |
| 3 | Mitigar SSRF: allowlist de dominios + bloqueo de IPs privadas + límite de tamaño | Vector explotable el día que se despliegue |
| 4 | `ODIN_ANALYZER` explícito; nunca elegir motor de pago por presencia de llave | Cobros silenciosos; contradice CLAUDE.md |
| 5 | `pyproject.toml` + ruff + mypy + pre-commit + `requirements.lock` | Cada línea nueva sin esto es deuda |
| 6 | `pytest` + pruebas de `canonicalize`, `_parse_date`, `_urls_from_sitemap`, filtros de API | Refactorizar sin pruebas es apostar |
| 7 | **Golden set** (150-300 artículos) + `scripts/evaluate.py` | Sin esto no sabes si mejoras; hay números publicados sin respaldo |
| 8 | Alembic + `alembic stamp head`; quitar el DDL automático | La BD tiene 7 filas — la ventana se cierra sola |
| 9 | Quick wins #1-#5 y #10 de §11 | Horas de trabajo, riesgo real |

### P1 — Sistema de datos de verdad (3-5 semanas)

| # | Tarea |
|---|---|
| 10 | Linaje: `analyzer_name/model/version`, `analyzed_at`, `schema_version` (§2.1) |
| 11 | Almacenamiento crudo + `content_hash` + deduplicación real (§2.2) |
| 12 | `fetch_log` + dead-letter + métricas de cobertura por fuente (§2.3) |
| 13 | **Dimensión canónica de entidad** + tabla de menciones + FKs de actores (§4.1) |
| 14 | Índices + búsqueda full-text (§4.2) |
| 15 | Cola de trabajos: `/api/analyze` → `202` + `job_id` + worker (§3.1) |
| 16 | Throttle por dominio + `robots.txt` + corregir el README (§2.6) |
| 17 | Normalización de fechas a UTC aware (§2.7) |
| 18 | Logs estructurados + `/metrics` + tabla `crawl_runs` + Sentry (§7.1) |
| 19 | CI en GitHub Actions: lint + types + tests + `pip-audit` |
| 20 | Rate limiting + presupuesto de Gemini con cortacircuito (§5.3) |
| 21 | Endpoints de borrado/rectificación de artículos y entidades (§8.2) |

### P2 — Producto y escala (6+ semanas)

| # | Tarea |
|---|---|
| 22 | Scheduler real del crawl + protección contra corridas solapadas (§7.2) |
| 23 | Re-crawl con `ETag`/`If-Modified-Since` + `article_revisions` (§2.5) |
| 24 | Partir `api.py` en routers + capa de servicios (§9.2) |
| 25 | Generar tipos TS desde OpenAPI; eliminar la triple duplicación de esquema |
| 26 | Frontend: React Query, rutas, error boundary, Vitest, partir componentes grandes |
| 27 | Hardening de contenedores: `USER` no-root, healthchecks, cabeceras en nginx (§5.5) |
| 28 | Backups automáticos + procedimiento de restauración probado (§7.5) |
| 29 | Documentación faltante: ARQUITECTURA, ADRs, DATA_DICTIONARY, RUNBOOK, LEGAL, PRECISION, LICENSE (§10.2) |
| 30 | Actualizar README y PROCESOS al estado real; checkpoint de docs en el flujo de cambios (§10.1) |

> **Nota de secuenciación**: las respuestas del cliente (§15) pueden reordenar P1 y
> P2, pero **no P0**. Nada de lo que diga el cliente hace innecesario tener git,
> pruebas, autenticación o una forma de medir la precisión.

---

## 13. Definición de "listo para el cliente"

Checklist de salida. Mientras alguno esté sin marcar, no está listo:

- [ ] Código en git, con CI verde en cada push
- [ ] Cobertura ≥70% en `analysis/`, `scrapers/`, `db/`
- [ ] Golden set publicado + métricas de precisión reproducibles y fechadas
- [ ] Autenticación en todos los endpoints de escritura y en `/api/analyze`
- [ ] SSRF mitigado (allowlist + bloqueo de rangos privados), verificado con un test
- [ ] Rate limiting y presupuesto de Gemini con cortacircuito
- [ ] Migraciones versionadas con Alembic
- [ ] Linaje del análisis persistido (analizador, modelo, versión, fecha)
- [ ] `fetch_log` + métricas de cobertura por fuente, con alerta si cae
- [ ] Backup automático + restauración probada al menos una vez
- [ ] `robots.txt` respetado y throttle por dominio, coherente con el README
- [ ] `docs/LEGAL.md` revisado, con ToS por medio y política de retención
- [ ] La UI muestra confianza y descargo en cada juicio sobre una persona
- [ ] RUNBOOK escrito y probado por alguien que no escribió el código
- [ ] README que describe el sistema que existe hoy

---

## 14. Cierre

La calidad del pensamiento en Odin es alta: las abstracciones están donde deben,
las decisiones difíciles (sitemaps sobre selectores, trafilatura sobre parsing
propio, `Analyzer` como puerto) están bien tomadas y bien argumentadas en los
comentarios. Eso es lo caro, y ya está hecho.

Lo que falta es lo que separa un prototipo de un sistema: **git, pruebas,
evaluación medible, autenticación, linaje de datos y observabilidad**. Ninguna de
esas seis cosas es intelectualmente difícil; todas se encarecen cada semana que se
posponen, y tres de ellas (git, golden set, modelo de entidad) son
retroactivamente dolorosas — cuanto más código y más datos acumules, más cuesta
introducirlas.

El corpus de 7 artículos no es un problema: es la oportunidad. Todo lo estructural
de este documento cuesta hoy una fracción de lo que costará con 50.000 filas
dentro.

Si solo se puede hacer una cosa esta semana: **`git init`**.
Si se pueden hacer tres: git, autenticación, y las primeras 200 filas etiquetadas
del golden set.

---
---

# Anexo A — Estado del proyecto y preguntas al cliente

_Contenido previo de este archivo, conservado sin cambios. Es la lente de
**producto**; lo de arriba es la lente **técnica**. Se complementan: varias
preguntas de abajo (3, 6, 8) tienen respuestas técnicas que hoy no podemos dar —
ver §4.1, §2.4 y §5.2 respectivamente._

_Fecha: 2026-08-02_

## A.1 Dónde está el proyecto hoy

**Lo que ya funciona (construido y probado):**

| Pieza | Estado |
|---|---|
| Scrapers | 8 medios registrados: Listín, Diario Libre, El Nacional, Hoy, El Caribe, Al Momento, El Día, N Digital |
| Extracción | Título, autor, fecha, sección, cuerpo (trafilatura) — calidad alta |
| Análisis local (gratis) | Tema, palabras clave, sentimiento global, entidades (PERSON/ORG) + opinión hacia cada una |
| Análisis Gemini (pago) | Además: encuadre, intención del titular, actor dominante, culpado/acreditado, calidad de fuentes |
| Base de datos | 3 tablas (`articles`, `entities`, `entity_aliases`), portable SQLite / Postgres / SQL Server |
| API | 10 endpoints: analizar URL, guardar, listar con filtros, CRUD de siglas, health |
| Frontend | 3 pestañas: **Analizar** (pegar URL → revisar → guardar), **Reportes** (lista filtrable), **Siglas** (CRUD de alias) |
| Infra | Docker Compose completo (db + backend + frontend + scraper) y plan de deploy gratis documentado |

**Lo que revela la data real (`odin.db`):**

- Solo **7 artículos** guardados (5 Diario Libre, 2 manuales) y 82 entidades → el pipeline masivo **casi no se ha usado**; el uso real ha sido el flujo manual de una URL a la vez.
- **0 artículos con campos de encuadre** → todo el análisis avanzado de Gemini está construido pero nunca se ha ejercido sobre data guardada.
- 119 siglas sembradas → la normalización de nombres sí se trabajó a fondo.

**Huecos evidentes (aún no existe):**

- Sin agregados ni gráficas: los "Reportes" son una lista, no un tablero. No hay "¿cómo se habló de X esta semana?".
- Sin exportación (CSV/Excel/PDF) ni envío por correo.
- Sin ejecución automática programada (nadie corre el scraper solo).
- Sin usuarios, login ni roles.
- Sin lista de entidades vigiladas: Odin guarda *todo* lo que encuentra, no lo que al cliente le importa.

**Riesgo principal:** se ha invertido mucho en profundidad de análisis por artículo, y poco en la **agregación** — que es normalmente lo que un cliente compra. Las preguntas de abajo apuntan a confirmar o corregir eso antes de seguir construyendo.

## A.2 Preguntas al cliente

> 9 preguntas. Cortas, pero cada una decide qué se construye y qué se descarta.

**1. ¿Quién abre Odin cada mañana y qué decisión toma con lo que ve?**
_(Un nombre y un cargo real, no "el equipo".)_ Define si esto es monitoreo reputacional, inteligencia política, o investigación de medios.

**2. ¿Cuál es el entregable que le sirve: una pantalla web, un reporte diario por correo, o una alerta cuando pasa algo?**
Hoy tenemos pantalla. Si lo que quiere es un PDF a las 7 a.m., el foco cambia por completo.

**3. ¿Hay una lista concreta de personas/empresas/instituciones que le interesa vigilar? ¿Cuántas?**
Si son 20 nombres, Odin debe filtrar y priorizar. Si es "toda la prensa", debe agregar y descubrir. Son dos productos distintos.

**4. ¿Le basta la prensa escrita digital, o también necesita TV, radio y redes sociales?**
Tenemos 8 periódicos. Redes sociales sería un proyecto aparte — conviene saberlo ahora.

**5. ¿Cada cuánto necesita la información actualizada, y cuánto pasado necesita ver?**
_(¿Al instante, cada hora, una vez al día? ¿Historial de 1 mes, 1 año, 5 años?)_ Define la infraestructura y el costo de la primera carga.

**6. Cuando dice "hablan mal de X", ¿qué error es aceptable?**
Hoy: modelo gratis acierta ~60-70% en esa pregunta; con IA de pago sube fuerte pero cada artículo cuesta. ¿Prefiere barato y aproximado, o preciso y con costo mensual?

**7. ¿Alguien de su equipo va a revisar y corregir el análisis antes de darlo por bueno?**
Ya construimos ese flujo (revisar antes de guardar). Si nadie va a revisar, sobra y debe ser 100% automático.

**8. ¿Los datos son sensibles? ¿Necesita usuarios con contraseña, y la base en su servidor o en la nube?**
Hoy no hay login y todo está abierto. Cambiarlo después cuesta más.

**9. Si dentro de 30 días esto está funcionando, ¿qué tiene que poder hacer para que usted diga "sirve"?**
Una frase. Es el criterio de aceptación de la primera entrega.

## A.3 Cómo cambian las respuestas el plan

| Si el cliente dice… | Se quita | Se agrega |
|---|---|---|
| "Quiero vigilar 20 nombres" | Guardar todo indiscriminadamente | Lista de vigilancia + alertas por entidad |
| "Quiero un reporte diario" | Peso del frontend interactivo | Agregados, gráficas, export PDF/correo, cron |
| "Nadie va a revisar nada" | Flujo manual "Analizar → revisar → guardar" | Ejecución programada y automática |
| "Necesito precisión alta" | LocalAnalyzer como motor principal | Gemini + control de costo por artículo |
| "Es información sensible" | CORS abierto y API pública | Login, roles, despliegue en su infraestructura |
| "Solo periódicos, una vez al día" | — | Cerrar alcance: terminar los 8 medios y agregar tablero |
