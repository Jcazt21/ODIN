# Requerimientos del cliente vs. Odin actual — análisis de brecha y fases

> **Estado: borrador para evaluación.** Nada de esto está implementado ni
> decidido. El propósito es que puedas leerlo, tachar lo que no aplica,
> corregir lo que malinterpreté de la entrevista y ordenar las fases.
>
> Fuente: notas de entrevista con el cliente (sin fecha, desordenadas por
> ser tomadas en vivo). Contraste contra el código en `dev` al 2026-08-21.
>
> **Re-verificado el 2026-08-22** contra el árbol de entonces: 8 tablas, cero
> endpoints de agregación, cero export, sin tabla de usuarios,
> `source`/`section`/`authors` como texto libre. Solo se corrigieron las
> rutas de archivo, porque el código se movió de la raíz a `src/odin/`.
>
> **Re-verificado el 2026-09-02** contra `dev`: esta vez sí cambió bastante.
> Entraron enteras la dimensión geográfica (R2), los usuarios documentalistas
> con su formulario manual (R18, R19) y el export a Word (R22); avanzaron a
> medias la ficha de actor (R1), el cruce medio × actor (R3) y el KPI (R20).
> §3 y §4 quedaron reescritas con eso; §7 sigue describiendo las fases como se
> planificaron, con una nota de qué quedó hecho en cada una.

---

## 1. Cómo leer este documento

- **§2** normaliza las notas en requerimientos numerados (`R1`…`R22`). Si
  interpreté algo mal, es aquí donde hay que corregirlo — todo lo demás
  cuelga de esta lista.
- **§3** dice qué tiene Odin hoy, sin optimismo.
- **§4** es la tabla de brecha: requerimiento por requerimiento.
- **§5** es el hallazgo de fondo, y la razón por la que propongo fases en
  este orden y no en el orden en que el cliente las mencionó.
- **§6** son las decisiones que necesito de ti (o del cliente) antes de
  poder planificar en serio. Varias son bloqueantes.
- **§7** son las fases propuestas.
- **§8** es lo que recomiendo **no** construir.

---

## 2. Los requerimientos, normalizados

| # | Requerimiento | Cita/origen en las notas |
|---|---|---|
| **R1** | Ficha de seguimiento por actor e institución (ej. Luis Abinader / Presidencia) | "Seguimiento Actores Institucion" |
| **R2** | Lugar geográfico donde ocurre la noticia | "y Lugar geografico", "en q lugar" |
| **R3** | Cómo se comporta cada medio hacia cada actor/institución | "q comportamiento le dan los medios a los autores institucion" |
| **R4** | Catálogo administrable de temas | "Lista de temas" |
| **R5** | Clasificación automática de la noticia contra ese catálogo al ingresarla | "cuando traiga la noticia a la db el procesamiento identifique cuales temas participa" |
| **R6** | Subtemas jerárquicos bajo cada tema | "SUBTEMAS (acueducto → tema agua, subtema infraestructura)" |
| **R7** | Frecuencia de cada tema por día | "Tema - Frecuencia del dIa" |
| **R8** | Vinculación tema ↔ actor ↔ institución ↔ lugar ↔ tono, como unidad consultable | "VINCULACION - Tema agua potable tono negativo" |
| **R9** | Quién habla de un actor, qué dice, con qué sentimiento — **y quién no habla** | "quienes hablan de el q hablan de el, el sentimiento quien no habla de el" |
| **R10** | Relación explícita institución ↔ actor | "relacion institucion con actor" |
| **R11** | Sección normalizada de la noticia (política, deportes…) | "Secciones q tipo de noticia es de que seccion" |
| **R12** | Prominencia ALTO / MEDIO / BAJO: importancia que el medio le dio a la noticia | "antes se media en q pagina del peridico lo ponian tamaño" |
| **R13** | Ante-títulos | "ante-titulos" |
| **R14** | Medio de comunicación como dimensión (no solo filtro) | "filtrar por medio de comunicacion (listin diario, diario libre)" |
| **R15** | Periodista como dimensión | "agregar periodista" |
| **R16** | Rol del actor en la nota: **emisor** (declara) vs **referido** (hablan de él) | "IMPORTANTE… luis abinader se compromete = emisor; un empresario dice 'Luis se comprometió' = referido" |
| **R17** | **Hechos**: agrupar noticias en torno a un suceso, y ver por hecho qué actores participaron y cómo los trataron los medios | "accidente de camión en el malecón… toda la info relacionada se vincula al hecho" |
| **R18** | Dos modos de trabajo: automático (modelo) y manual (documentalista) | "2 formas de trabaja" |
| **R19** | Documentalistas: usuarios con formulario propio, capaces de operar **si el modelo se cae** | "Documentalista (otro formulario)… trabajar si el modelo se cae" |
| **R20** | KPI de calidad del trabajo del documentalista | "para verificar si realmente verificaron las noticias" |
| **R21** | Consumo desde Power BI | "se usa powerbi" |
| **R22** | Exportar a `.doc` | "Exporto en .doc" |

**Dudas de interpretación** (§6 las retoma):

- R3 y R9 pueden ser el mismo reporte visto desde dos ángulos. Los dejo
  separados hasta confirmar.
- "Actores" en las notas a veces significa *figura pública seguida* y a
  veces *cualquier entidad mencionada*. Asumo lo primero (una **watchlist**
  del cliente); si no, el costo del pipeline cambia mucho.
- R12 mezcla dos cosas: la **medición** de prominencia y la **escala**
  ALTO/MEDIO/BAJO. La escala es fácil; la medición es el problema (§7, F4).

---

## 3. Qué tiene Odin hoy

Inventario honesto, no aspiracional.

### Datos

| Tabla | Qué guarda | Nivel de madurez |
|---|---|---|
| `articles` | url, título, `authors` (texto libre), `section` (texto libre de trafilatura), `published_at`, `body`, `source` (slug string) | maduro |
| `articles` (análisis) | `main_topic` (texto libre), `topic_keywords`, `overall_sentiment` POS/NEG/NEU + score | maduro |
| `articles` (encuadre, **solo LLM**) | `framing`, `headline_intent`, `lead_orientation`, `source_quality`, `has_hard_data` | maduro |
| `articles` (capas de sentimiento, **solo LLM**) | `sentiment_basis`, `facts_sentiment`, `quoted_sentiment`, `media_stance`, `media_stance_evidence`, `content_flags` | maduro |
| `articles` (actores de encuadre, **solo LLM**) | `dominant_actor_id`, `blamed_actor_id`, `credited_actor_id` → FK a `canonical_entities` | maduro |
| `entities` | una mención por artículo: nombre, tipo `PERSON`\|`ORG`, conteo, `sentiment_toward`, `context`, `extraction_confidence` | maduro |
| `canonical_entities` | dimensión de persona/organización, con merge y renombrado | maduro |
| `entity_aliases` | siglas → nombre canónico, administrable desde el frontend | maduro |
| `analyze_jobs`, `scrape_jobs`, `crawl_runs` | cola y trazabilidad de corridas | maduro |
| `runtime_settings` | fila única: motor de análisis | maduro |
| `localities` | árbol geográfico en una sola tabla (país → macrorregión → región de planificación → provincia → municipio), con `path` materializado y baja lógica | maduro |
| `locality_aliases` | nombres alternos por los que la prensa cita un lugar ("Navarrete", "Salcedo") | maduro |
| `article_localities` | N:M artículo ↔ lugar, con `kind` HECHO/MENCIONADO, `origin` MANUAL/AUTO y confianza | maduro |
| `users` | documentalistas y admins: rol, baja lógica, PIN provisional de un solo uso | maduro |
| `articles` (autoría del reporte) | `documentalist_id` → FK a `users`, `analyzed_on` (día trabajado) | maduro |

### Capacidades

- **Análisis a demanda**: pegas una URL → `POST /api/analyze` → revisas →
  guardas. Es el flujo principal y está sólido.
- **Rastreo masivo** de 9 medios dominicanos, opcional y manual
  (`scrape_jobs` + `politics_filter`).
- **Corrección humana**: el resultado se puede editar antes de guardar, y
  `PUT /api/articles/{id}` rectifica un análisis ya guardado.
- **Administración de identidad**: fusionar entidades duplicadas,
  administrar siglas.
- **Filtros** sobre artículos guardados: fuente, sección, sentimiento,
  campos de encuadre, entidad, tema (texto libre sobre `main_topic`), lugar
  (con subárbol), documentalista, rango de fechas, orden por columna.
- **Tres motores**: `local` (spaCy + pysentimiento, gratis), `groq`
  (gratis con límites), `gemini` (de pago, vedado para volumen por
  `CLAUDE.md`), más `hybrid`.
- **Alta manual sin modelo**: `NewReportPage` → `POST /api/articles`. El
  documentalista transcribe la nota, elige medio, sección, tema y lugares, y
  guarda sin pasar por el análisis.
- **Dimensión geográfica completa**: catálogo administrable desde el frontend,
  sugerencia automática de lugares a partir de las entidades `LOC` de spaCy
  (`local_analyzer._places` + `locality_service.suggest_from_places`) que una
  persona acepta o descarta, y `GET /api/localities/frequency` con roll-up.
- **Usuarios por persona**: login individual, roles `admin`/`documentalista`,
  alta con PIN de un solo uso y cambio de contraseña forzado.
- **Export a Word**: `POST /api/articles/export` arma un `.docx` a partir de
  una plantilla, con una ficha por reporte.
- **KPI de volumen por documentalista**: `GET /api/documentalists/kpi`
  (reportes, primer y último día, días activos).

### Lo que NO existe

- **Casi ninguna agregación en el backend.** `GET /api/localities/frequency`
  es el único endpoint que devuelve un conteo agregado. La ficha de entidad
  se agrega **en el navegador** sobre las ≤200 menciones más recientes que
  devuelve `GET /api/canonical-entities/{id}`, sin ventana de tiempo: sirve
  para entidades con poco volumen y empieza a mentir en silencio cuando una
  pasa las 200 menciones.
- **Ninguna dimensión más allá de persona/organización y lugar.** Medio,
  periodista, sección, tema y hecho siguen siendo texto libre, catálogo en
  código, o directamente no existen.
- **Ninguna auditoría.** El diccionario de datos lo dice explícitamente: si
  se re-analiza un artículo, la fila se sobrescribe. Sabemos **quién** dejó
  guardado el reporte (`documentalist_id`), pero no **qué cambió** respecto de
  lo que propuso el modelo.
- **Ninguna vista para Power BI.**

---

## 4. Tabla de brecha

Leyenda: ✅ existe · 🟡 existe a medias · ❌ no existe · ⬆️ avanzó desde la
revisión del 2026-08-22

| # | Estado | Qué hay | Qué falta exactamente |
|---|:--:|---|---|
| R1 | 🟡 ⬆️ | La ficha existe en `CanonicalEntityManager`: composición de sentimiento, **trato por medio** y artículos agrupados por medio, sobre `GET /api/canonical-entities/{id}` | Falta serie temporal, temas, lugares, secciones y periodistas que lo cubren. Y el corte estructural: se agrega en el navegador sobre las ≤200 menciones más recientes (`canonical_entity_service.py:111`), sin filtro de fechas — el mismo número cambia de significado cuando la entidad cruza ese tope |
| R2 | ✅ ⬆️ | Dimensión geográfica entera: `localities` (31 provincias + DN + 158 municipios en 3 macrorregiones y 10 regiones), `locality_aliases`, `article_localities` con `kind` HECHO/MENCIONADO, ABM desde el frontend, `LocalityPicker` en el alta y en el detalle, sugerencia automática desde las entidades `LOC` de spaCy, y `GET /api/localities/frequency` con roll-up | Nada bloqueante. Pendiente menor: `origin=AUTO` solo se escribe cuando **una persona acepta** la sugerencia — no hay etiquetado desatendido, y fue decisión deliberada. El comentario de `db/models.py:557` ("`AUTO` todavía no lo escribe nadie") quedó desactualizado |
| R3 | 🟡 ⬆️ | `SourceSentimentBreakdown` responde "qué trato le da cada medio a este actor", con marca de muestra baja | Es un cálculo de frontend sobre la misma lista de ≤200 menciones: sin ventana de tiempo, sin poder comparar dos períodos, y no consultable desde Power BI ni desde un export. Falta el cruce **medio × entidad × ventana** en el backend |
| R4 | ❌ | `main_topic` sigue siendo texto libre (`_main_topic`, `src/odin/analysis/local_analyzer.py:667`). Se agregó `?topic=` en `GET /api/articles`, pero es un `contains` sobre ese texto libre (`article_service.py:130`) | No hay catálogo de temas, ni tabla, ni administración. El filtro nuevo alivia la consulta; no crea la dimensión |
| R5 | ❌ | — | Depende de R4. Hoy el tema se *infiere* por frecuencia, no se *clasifica* contra nada |
| R6 | ❌ | — | Depende de R4. Requiere jerarquía padre-hijo (el patrón ya está probado en `localities`: una tabla, `parent_id` y `path`) |
| R7 | ❌ | — | Depende de R4. El endpoint es barato una vez que exista `article_topics`: `GET /api/localities/frequency` es el molde |
| R8 | ❌ | Ya están actor, sentimiento y **lugar**; falta tema | Falta la fila consultable que une tema+actor+institución+lugar+tono |
| R9 | ❌ | — | "Quién habla" es agregación (factible, y ahora media más cerca: el desglose por medio ya está calculado, falta subirlo al backend). **"Quién NO habla" sigue siendo el requerimiento más difícil del documento** → **decisión D1**, aún abierta |
| R10 | ❌ | — | No hay tabla de relaciones entre entidades canónicas |
| R11 | 🟡 | `articles.section` existe, es filtrable y el alta manual lo pide | Sigue siendo texto libre, tal como lo dé cada medio. Falta catálogo normalizado y mapeo por medio |
| R12 | ❌ | — | Sin cambios. La señal original (página, tamaño en papel) no existe en web, y los scrapers usan sitemaps/RSS por [ADR-001](../adr/0001-trafilatura-y-sitemaps-sobre-selectores.md) → **decisión D5** |
| R13 | ❌ | — | trafilatura no extrae ante-título; requiere selector por medio |
| R14 | 🟡 | `articles.source` es slug filtrable, y `scrapers.source_name()` le da nombre legible, que ya viaja en las respuestas (`source_name` en la ficha de entidad) | Sigue sin ser dimensión: el catálogo de medios es el **registro de scrapers en código** (`article_service.source_catalog`), no una tabla. Agregar un medio exige tocar código, y no hay dónde guardar tipo, alcance ni línea editorial |
| R15 | 🟡 | `articles.authors`, texto libre separado por `", "` | Sin cambios. Sin normalizar, sin dimensión, sin canonicalización: "J. Pérez" y "Juan Pérez" siguen siendo dos periodistas |
| R16 | ❌ | Sigue existiendo solo lo **vecino pero distinto**: `dominant/blamed/credited_actor` | Emisor vs referido es un **rol de la mención**. `entities` todavía no tiene esa columna |
| R17 | ❌ | — | El concepto de hecho/evento no existe en ningún nivel |
| R18 | ✅ ⬆️ | Los dos modos funcionan: el automático de siempre, y `NewReportPage` → `POST /api/articles` para captura manual completa sin pasar por el modelo, con medio, sección, tema, cuerpo y lugares en una sola transacción | El formulario **sigue exigiendo URL** (`REQUIRED` en `NewReportPage.tsx:36`). Para una nota de papel o de radio no hay URL que poner. Decidir si se vuelve opcional o se acepta un identificador sustituto |
| R19 | ✅ ⬆️ | `users` con roles `admin`/`documentalista`, login por persona, alta con PIN de 4 dígitos de un solo uso, cambio de contraseña forzado, baja lógica que preserva la atribución, y `db/users.seed_operator` para que el operador del `.env` siga entrando igual | El modelo de roles es de dos niveles: no hay figura de **supervisor** ni reglas sobre si un documentalista puede editar lo de otro → **decisión D6**, todavía sin responder |
| R20 | 🟡 ⬆️ | `GET /api/documentalists/kpi`: reportes por documentalista, primer y último día, días activos distintos, filtrable por rango | **Mide volumen, no calidad** — y el requerimiento del cliente era "verificar si realmente verificaron". La tasa de corrección sobre lo que propuso el modelo exige auditoría campo a campo, y re-analizar sigue sobrescribiendo la fila sin dejar rastro |
| R21 | 🟡 | Postgres soportado; y ahora hay más que agregar contra: `localities`, `article_localities`, `users` | Sin cambios de fondo: faltan vistas SQL estables y un usuario de solo lectura → **decisión D4** |
| R22 | ✅ ⬆️ | `POST /api/articles/export` devuelve un `.docx` armado sobre plantilla (`src/odin/exports/reportes-odin-template.docx` — la de `docs/export 4/` es la copia de diseño, no la que se usa), una ficha por reporte, con portada, período, medios y entidades | Es `.docx`, no el `.doc` literal de las notas — asumo que el cliente decía "Word". **Conviene confirmarlo**: si alguien depende de un flujo con `.doc` binario de verdad, esto no le sirve |

**Resumen: 4 completos (R2, R18, R19, R22), 7 parciales (R1, R3, R11, R14,
R15, R20, R21), 11 inexistentes.** Contra la revisión anterior —cero
completos— el avance real fue la fase F5 (documentalistas), la mitad
geográfica de F0/F2 y el export de F3.

**El patrón de lo que falta no cambió:** casi todo lo pendiente cuelga de dos
cosas que siguen sin construirse — el **catálogo de temas** (R4→R5, R6, R7, y
la mitad de R8) y las **dimensiones de medio y periodista** (R14, R15, y con
ellas el valor real de R1, R3 y R21). El trabajo hecho hasta ahora eligió, con
buen criterio, lo que se podía terminar de punta a punta; lo que queda es
justamente lo que §5 llama la fontanería dimensional.

## 5. El hallazgo de fondo

Odin hoy responde **"¿qué dice este artículo?"**. El cliente está pidiendo
un sistema que responda **"¿qué está pasando con este actor / este tema /
este hecho, según qué medios, dónde y con qué tono?"**.

Eso no es la misma aplicación con más campos. Es un cambio de forma:

```
HOY                          LO QUE PIDE EL CLIENTE

  articles (raíz)              dimensiones
     ├─ entities                 medio · periodista · sección
     └─ (todo lo demás           actor · institución · tema · subtema
         son columnas)           lugar · hecho
                                        │
  consulta:                             ▼
  "listar artículos            tabla de hechos: la cobertura
   con filtros"                (artículo × entidad × rol × tono)

                               consulta:
                               "agregar por cualquier dimensión"
```

Que el cliente use **Power BI** no es un detalle de entrega: es la
confirmación de que espera un modelo dimensional. Power BI trabaja bien
contra un esquema estrella y mal contra tablas con texto libre en las
columnas que uno quisiera usar como eje.

**Consecuencia práctica para el orden de las fases:** las dimensiones van
primero, aunque no sean lo más vistoso. Si construimos primero los temas
(R4-R7) sobre un `source` que es un string y un `authors` sin normalizar,
el cliente va a poder cruzar tema × sentimiento pero no tema × medio ×
periodista, que es justamente lo que quiere.

**Segunda consecuencia, sobre ingesta:** R7 (frecuencia del día), R9 (quién
no habla) y R20 (KPI) presuponen **censo** — capturar sistemáticamente lo
que publican los medios seguidos. Odin hoy es deliberadamente a demanda; el
README lo enfatiza y [LEGAL.md](../LEGAL.md) tiene los ToS de los 9 medios
en 🔴 pendiente y la retención de `body` sin política. Pasar a censo es una
decisión de producto **y legal**, no una tarea técnica → **D1**.

---

## 6. Decisiones abiertas

Necesito estas respuestas para planificar en serio. Las marcadas 🔴 bloquean
fases enteras.

### 🔴 D1 — ¿Censo o a demanda?

R7, R9 y R20 no funcionan sobre una muestra elegida a mano. Pero el censo
multiplica el volumen de `body` guardado, justo cuando LEGAL.md tiene los
ToS sin revisar.

**Mi recomendación:** censo **de titulares** (URL, titular, ante-título,
sección, periodista, fecha, prominencia) para los medios seguidos, y
descarga de `body` únicamente para las notas que entran al análisis
profundo. Habilita medir silencio y frecuencia real, y *reduce* la
exposición de copyright respecto de guardar todos los cuerpos.

### 🔴 D2 — ¿Con qué motor se analizan las capas nuevas?

Emisor/referido (R16), clasificación temática (R5), lugar del hecho (R2) y
hechos (R17) exigen comprensión del texto. `LocalAnalyzer` no puede con
ellas. `gemini` está vedado para volumen por `CLAUDE.md`.

**Mi recomendación:** reglas locales como piso garantizado (para R16 hay
una heurística decente: verbos de habla + comillas + atribución) y `groq`
para lo semántico, midiendo contra el golden set que ya existe. Nunca
depender solo del LLM: el cliente pidió explícitamente poder trabajar "si
el modelo se cae" (R19).

### 🔴 D3 — ¿Watchlist o universo abierto?

¿El cliente sigue un set definido de actores e instituciones (Presidencia,
Abinader, ministerios…) o quiere análisis de todo lo que se publique?

**Mi recomendación:** watchlist. Hace viable "quién no habla de X" (necesita
un denominador acotado), acota el costo del pipeline y es como funcionan
los servicios de monitoreo de medios.

### 🟡 D4 — Power BI: ¿contra la BD o contra la API?

**Mi recomendación:** vistas SQL en Postgres, versionadas en Alembic, más un
usuario de solo lectura. Una API para BI es trabajo extra que Power BI no
agradece.

### 🟡 D5 — ¿Cómo se define la prominencia?

"Página y tamaño" no tiene equivalente en web. Los proxies posibles:
posición en portada, si es titular principal, permanencia en home, longitud,
presencia de multimedia, si se replicó en varias secciones.

**Esto hay que pactarlo con el cliente antes de construirlo**, porque si
después dice "no, así no se mide", el trabajo de scraping de portadas se
pierde entero. Sugiero llevarle 2 o 3 definiciones concretas y que elija.

### 🟡 D6 — ¿Cuántos documentalistas y con qué permisos?

¿Un documentalista puede editar lo de otro? ¿Hay figura de supervisor que
aprueba? Esto define el modelo de roles de F5.

### 🟡 D7 — ¿R3 y R9 son el mismo reporte?

Si lo son, F3 se simplifica bastante.

---

## 7. Fases propuestas

Cada fase entrega algo mostrable al cliente. El orden prioriza
**desbloquear** sobre **impresionar** — con una excepción deliberada, F3,
que existe para que el cliente vea producto antes de las fases caras.

---

### F0 · Fundación dimensional
**Entrega:** R14, R15, R11, R10, y la mitad de R2
**Bloquea a:** todas las demás fases
**Estado al 2026-09-02:** hecha la parte geográfica (y más allá de lo que
pedía esta fase: quedó completa, ver F2). `media_outlets`, `journalists`,
`sections` y `entity_relations` siguen sin construirse — es lo que hoy
bloquea al resto.

Convertir en dimensiones lo que hoy es texto libre:

- `media_outlets` — el medio como tabla (nombre, slug, tipo, alcance,
  metadatos), con `articles.source` migrado a FK.
- `journalists` + vínculo con artículo — canonicalizar `authors`, con el
  mismo patrón de alias/merge que ya funciona para `canonical_entities`.
- `sections` — catálogo normalizado, más mapeo de la sección cruda de cada
  medio hacia el catálogo.
- `LOCATION` como tipo de entidad canónica — y **dejar de descartar** lo que
  spaCy ya detecta (`_WANTED_ENT`), resolviendo aparte el falso positivo de
  provincias que hoy se maneja borrando.
- `entity_relations` — actor ↔ institución, con tipo de relación y vigencia
  ("Abinader — preside — Presidencia, desde 2020").

**Riesgo principal:** backfill. Hay artículos guardados con `source` y
`authors` como strings; migrarlos sin perder datos es la parte delicada.

**Criterio de aceptación:** se puede consultar "artículos de Listín Diario,
sección Política, firmados por tal periodista" y el resultado sale de FKs,
no de comparar strings.

---

### F1 · Temas y subtemas
**Entrega:** R4, R5, R6, R7
**Depende de:** F0 (parcialmente — se puede empezar en paralelo)

- `topics` con jerarquía padre-hijo (tema → subtema), administrable desde
  el frontend igual que los alias hoy.
- `article_topics` — relación N:M con score y evidencia textual, porque una
  nota participa de varios temas (el ejemplo del acueducto: agua +
  infraestructura).
- Clasificador en dos niveles: reglas/keywords sobre el catálogo (barato,
  funciona sin LLM, y le da al cliente control directo sobre qué cuenta como
  cada tema) y capa semántica encima para lo que las reglas no alcancen.
- Endpoint de frecuencia por tema y día (R7 sale casi gratis una vez que
  existe `article_topics`).

**Nota:** el `main_topic` actual **no se tira**. Sigue siendo útil como
descriptor libre; el catálogo es una capa nueva encima, no un reemplazo.

---

### F2 · Rol del actor y lugar del hecho
**Entrega:** R16, R2 completo
**Depende de:** F0
**Estado al 2026-09-02:** R2 entregado entero, incluida la distinción
HECHO/MENCIONADO que esta fase pedía. R16 (emisor/referido) sin empezar.

- `entities.role` — `emisor` \| `referido` \| `ambos`, con confianza. Va en
  la **mención**, no en el artículo: una nota tiene varios emisores y varios
  referidos simultáneamente.
- `articles.location_id` — dónde ocurre el hecho, que es distinto de los
  lugares mencionados de pasada.

Es la fase donde más se nota la diferencia entre lo que el cliente pide y
lo que Odin ya tiene: `dominant_actor`/`blamed_actor`/`credited_actor` se
parecen a esto, pero responden otra pregunta.

---

### F3 · Consultas de seguimiento y salida
**Entrega:** R1, R3, R9 (parcial), R14 completo, R21, R22
**Depende de:** F0, F1, F2
**Estado al 2026-09-02:** el export (R22) se adelantó y está entregado. R1 y
R3 tienen una primera versión que agrega en el navegador, útil para mostrar y
suficiente con el volumen actual — pero no es la fase: falta subir la
agregación al backend, con ventana de tiempo, y falta todo lo que depende de
dimensiones que aún no existen (temas, periodistas, medio como tabla).

La primera fase que el cliente puede *ver*:

- Endpoints de agregación: ficha de actor/institución (serie temporal de
  menciones, tono por medio, temas dominantes, lugares, secciones,
  periodistas que lo cubren).
- Cruce medio × actor (R3).
- "Quién habla de X" completo. **"Quién no habla" queda condicionado a D1.**
- Pantalla de Seguimiento en el frontend.
- Vistas SQL para Power BI + usuario read-only (D4).
- Export a `.doc`.

**Por qué aquí y no al final:** después de tres fases de fontanería, el
cliente necesita ver producto. Y los reportes de esta fase son los que van a
revelar si las dimensiones de F0-F2 quedaron bien definidas, mientras todavía
es barato corregirlas.

---

### F4 · Prominencia y ante-títulos
**Entrega:** R12, R13
**Depende de:** F0 · **Bloqueada por D5**

- Captura de portada por medio: posición, si es titular principal,
  multimedia, ante-título. Esto **cambia la estrategia de scraping** —
  sitemaps y RSS no dan posición, así que hay que revisar ADR-001.
- Índice de prominencia con los proxies pactados, y su corte en
  ALTO/MEDIO/BAJO.

**El requerimiento con más riesgo de decepcionar al cliente.** No vamos a
poder replicar la fidelidad de "qué página del periódico y qué tamaño".
Conviene decirlo antes de construir, no después.

---

### F5 · Documentalistas: usuarios, formulario y KPI
**Entrega:** R18, R19, R20
**Depende de:** nada de lo anterior — **se puede adelantar si el cliente lo prioriza**
**Estado al 2026-09-02:** se adelantó, como preveía esta nota, y está casi
entera: usuarios con roles, formulario manual y KPI de volumen. Falta lo que
depende de auditoría — la tasa de corrección de R20 — y la definición de roles
de D6.

- `users` con roles (documentalista / supervisor / admin), reemplazando el
  auth de operador único de `src/odin/core/auth.py`.
- Formulario de captura completa sin URL y sin modelo, para que el trabajo
  no se detenga si el análisis falla.
- **Auditoría campo a campo**: quién cambió qué, cuándo, valor anterior.
  Hoy re-analizar sobrescribe la fila y no queda rastro — sin esto, R20 es
  imposible.
- KPI: notas procesadas, tasa de corrección sobre lo que propuso el modelo,
  tiempo por nota, muestreo de calidad.

Es independiente del resto. La ubico en F5 porque las fases anteriores
definen *qué campos* llena el documentalista — construir el formulario antes
significa rehacerlo. Pero si el cliente tiene gente esperando para trabajar,
esta es la que se adelanta.

---

### F6 · Hechos (eventos)
**Entrega:** R17, R8 completo
**Depende de:** F0, F1, F2

- `events` + `article_events`: un hecho ("explosión de camión de gas en el
  malecón") con las notas que lo cubren.
- Agregación por hecho: actores e instituciones que participaron, y cómo
  trató cada medio a cada uno **dentro de ese hecho**.

**Va al final a propósito.** Agrupar notas por suceso es un problema de
clustering con criterio temporal, geográfico y de entidades — se apoya
directamente en que tema, lugar, actor y fecha ya estén normalizados. Hacerlo
antes es hacerlo dos veces. Es además la fase con mayor probabilidad de
necesitar revisión humana permanente: ningún sistema agrupa hechos bien solo.

---

### Mapa requerimiento → fase

| Fase | Requerimientos |
|---|---|
| F0 | R2 (parcial), R10, R11, R14, R15 |
| F1 | R4, R5, R6, R7 |
| F2 | R2 (completo), R16 |
| F3 | R1, R3, R9, R21, R22 |
| F4 | R12, R13 |
| F5 | R18, R19, R20 |
| F6 | R8, R17 |

---

## 8. Lo que recomiendo NO hacer

- **No reescribir `LocalAnalyzer`.** Está medido contra un golden set y
  funciona para lo suyo. Las capas nuevas se agregan al lado, no encima.
- **No perseguir paridad con el papel en prominencia.** Pactar una
  definición web honesta y decirle al cliente qué se pierde.
- **No construir hechos (F6) temprano** porque sea lo más llamativo de la
  entrevista. Sin temas, lugares y actores normalizados, el agrupamiento va
  a ser malo y va a quemar la confianza del cliente en la función.
- **No construir una API para Power BI.** Vistas SQL (D4).
- **No tocar `dominant/blamed/credited_actor`** para meter emisor/referido.
  Son preguntas distintas; mezclarlas pierde las dos.
- **No prometer "quién no habla de X" hasta resolver D1.** Es el
  requerimiento que más fácil se promete y más difícil se cumple.

---

## 9. Qué necesito de ti para seguir

1. Corregir §2 si malinterpreté algún requerimiento.
2. Responder D1, D2 y D3 (las 🔴) — o decirme cuáles hay que devolverle al
   cliente.
3. Confirmar o reordenar las fases. En particular: **¿F5 se adelanta?**
   Depende de si hay documentalistas esperando para trabajar.

Con eso escribo el spec de la primera fase y de ahí sale el plan de
implementación.
