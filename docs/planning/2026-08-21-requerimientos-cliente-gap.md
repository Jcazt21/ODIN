# Requerimientos del cliente vs. Odin actual — análisis de brecha y fases

> **Estado: borrador para evaluación.** Nada de esto está implementado ni
> decidido. El propósito es que puedas leerlo, tachar lo que no aplica,
> corregir lo que malinterpreté de la entrevista y ordenar las fases.
>
> Fuente: notas de entrevista con el cliente (sin fecha, desordenadas por
> ser tomadas en vivo). Contraste contra el código en `dev` al 2026-08-21.
>
> **Re-verificado el 2026-08-22** contra el árbol actual (`src/odin/`): el
> inventario de §3 y la tabla de §4 siguen siendo exactos — 8 tablas, cero
> endpoints de agregación, cero export, sin tabla de usuarios,
> `source`/`section`/`authors` como texto libre. Solo se corrigieron las
> rutas de archivo, porque el código se movió de la raíz a `src/odin/`.

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
  campos de encuadre, entidad, rango de fechas.
- **Tres motores**: `local` (spaCy + pysentimiento, gratis), `groq`
  (gratis con límites), `gemini` (de pago, vedado para volumen por
  `CLAUDE.md`), más `hybrid`.

### Lo que NO existe

- **Ninguna agregación.** No hay un solo endpoint que devuelva "tono de
  Listín hacia Abinader en agosto". Todo es listar artículos.
- **Ninguna dimensión más allá de persona/organización.** Medio, periodista,
  sección, tema, lugar y hecho son texto libre o directamente no existen.
- **Ningún concepto de usuario.** `src/odin/core/auth.py` es un operador único
  contra credenciales del entorno; no hay tabla de usuarios.
- **Ninguna auditoría.** El diccionario de datos lo dice explícitamente: si
  se re-analiza un artículo, la fila se sobrescribe. No hay historial de
  quién cambió qué.
- **Ningún export.**

---

## 4. Tabla de brecha

Leyenda: ✅ existe · 🟡 existe a medias · ❌ no existe

| # | Estado | Qué hay | Qué falta exactamente |
|---|:--:|---|---|
| R1 | 🟡 | `canonical_entities` como dimensión, con merge/rename. `GET /api/articles?entity=` filtra | No hay **ficha**: ninguna agregación por entidad (serie temporal, tono por medio, temas, lugares). `EntitiesPage` administra entidades, no las monitorea |
| R2 | ❌ | — | El tipo `LOCATION` no existe. Peor: spaCy **sí** detecta lugares, pero `_WANTED_ENT` (`src/odin/analysis/local_analyzer.py:150`) solo acepta `PER`/`ORG` y los descarta; y `_DOMINICAN_PROVINCES` (línea 139) **elimina activamente** las 31 provincias porque spaCy las confunde con personas. La señal está a mano y hoy se tira |
| R3 | 🟡 | `entities.sentiment_toward` por mención y `media_stance` por artículo | Falta el cruce agregado **medio × entidad × ventana de tiempo** |
| R4 | ❌ | `main_topic` es texto libre: la frase nominal más frecuente (`_main_topic`, `src/odin/analysis/local_analyzer.py:667`) | No hay catálogo de temas, ni tabla, ni administración |
| R5 | ❌ | — | Depende de R4. Hoy el tema se *infiere* por frecuencia, no se *clasifica* contra nada |
| R6 | ❌ | — | Depende de R4. Requiere jerarquía padre-hijo |
| R7 | ❌ | — | Depende de R4 + un endpoint de agregación temporal |
| R8 | ❌ | Las piezas sueltas existen (entidad, sentimiento); tema y lugar no | Falta la fila consultable que une tema+actor+institución+lugar+tono |
| R9 | ❌ | — | "Quién habla" es agregación (factible). **"Quién NO habla" es el requerimiento más difícil del documento**: medir ausencia exige saber qué publicó cada medio, no solo qué guardamos. Choca de frente con el diseño a demanda → **decisión D1** |
| R10 | ❌ | — | No hay tabla de relaciones entre entidades canónicas |
| R11 | 🟡 | `articles.section` existe y es filtrable | Es texto libre, tal como lo dé cada medio. Falta catálogo normalizado y mapeo por medio |
| R12 | ❌ | — | Nada. Y la señal original (página, tamaño en papel) **no existe en web**. Además los scrapers usan sitemaps/RSS por [ADR-001](../adr/0001-trafilatura-y-sitemaps-sobre-selectores.md), que no dan posición en portada → hay que cambiar la estrategia de captura, no agregar un campo → **decisión D5** |
| R13 | ❌ | — | trafilatura no extrae ante-título; requiere selector por medio |
| R14 | 🟡 | `articles.source` es slug y es filtrable | No es dimensión: sin tabla de medios, sin metadatos (tipo, alcance, línea editorial), sin poder agregar un medio sin tocar código |
| R15 | 🟡 | `articles.authors`, texto libre separado por `", "` | Sin normalizar, sin dimensión, sin canonicalización. Hoy "J. Pérez" y "Juan Pérez" son dos periodistas distintos |
| R16 | ❌ | Existe algo **vecino pero distinto**: `dominant/blamed/credited_actor` (quién protagoniza, a quién se culpa, a quién se acredita) | Emisor vs referido es un **rol de la mención**, no un campo del artículo. Un artículo tiene N emisores y N referidos a la vez |
| R17 | ❌ | — | El concepto de hecho/evento no existe en ningún nivel. Es la pieza más grande y más incierta del documento |
| R18 | 🟡 | `POST /api/articles` guarda un análisis ya revisado; `PUT` rectifica | No hay captura desde cero sin URL y sin modelo. `SaveArticleRequest` exige `source`, `url`, `title`, `body` |
| R19 | ❌ | Auth de operador único, sin tabla de usuarios | **Bloqueante para R19 y R20.** Hay que construir usuarios, roles y sesión por persona |
| R20 | ❌ | — | Depende de R19 + auditoría campo a campo. Hoy re-analizar **sobrescribe** la fila: no queda rastro de qué corrigió quién |
| R21 | 🟡 | Postgres está soportado, así que Power BI podría conectar hoy mismo | Conectaría contra un esquema normalizado para la app, no para BI. Faltan vistas estables y un usuario de solo lectura → **decisión D4** |
| R22 | ❌ | — | Ningún export en el código |

**Resumen: 3 requerimientos a medias en lo importante, 6 parciales, 13
inexistentes.** Ninguno está completo.

---

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
