# Oportunidades de mejora del pipeline de análisis — hallazgos medidos

> **Estado: documento vivo.** Se va llenando a medida que aparecen hallazgos
> revisando análisis reales. Nada de lo que está aquí está implementado ni
> aprobado: es el inventario del que se eligen los trabajos, no el plan de
> ninguno de ellos. Cada oportunidad que se apruebe sale de aquí hacia su
> propio plan en `docs/superpowers/plans/`.
>
> **Regla de este documento:** ninguna oportunidad entra sin evidencia
> medida contra la BD. Nada de "esto probablemente pasa seguido". Las
> consultas que produjeron cada número están en §6 para poder re-medirlas
> cuando el corpus crezca.
>
> **Base de la medición:** corpus de **62 artículos** (36 analizados por
> LLM, 4 por `local`, 22 sin linaje registrado) y **200 entidades
> canónicas**, medido el **2026-08-29** contra la BD Postgres de
> `docker-compose`.

---

## 1. Cómo leer y cómo actualizar

- **§2** es el caso que originó la revisión, con su rastro en la BD.
- **§3** son las oportunidades, una por sección, cada una con síntoma →
  evidencia → causa → qué ya existe → propuesta.
- **§4** es la tabla de prioridad, y es lo único que hay que mirar para
  decidir qué se hace después.
- **§5** son las decisiones que dependen de ti o del cliente.
- **§6** son las consultas de verificación.
- **§7** es el registro de cambios.

Al agregar una oportunidad: número siguiente, misma estructura, y su fila
en §4. Al cerrarla: se marca en §4 y se enlaza el plan que la ejecutó; la
sección de §3 **no se borra** — el hallazgo y su medición son el
antecedente que explica por qué el código quedó como quedó.

---

## 2. El caso que originó esto

Artículo **67** — *"Área de Salud Mental del hospital Jaime Mota opera con
deficiencias de climatización y seguridad"*, Diario Libre, Omar Medina,
publicado 2026-08-29, guardado por el documentalista 10.

- `analyze_jobs.id` = `96c4ba02-e9b7-49c9-8bfe-d0d87a51ad56` (`done`, 5,4 s)
- Motor: `groq` / `openai/gpt-oss-120b` / prompt v6 / schema v2
- Resultado: `NEG`, `crisis_conflicto`, `informativo`, `tecnico`,
  `citas_directas`, `has_hard_data=true`, `media_stance=neutra_transmisiva`,
  `facts`/`quoted` ambos `NEG`, `blamed_actor` **NULL**
- Entidades 418–421: Cordero Moquete (PERSON, 6), Hospital Regional
  Universitario Jaime Mota (ORG, 2), Servicio Nacional de Salud (ORG, 1),
  Jenny Olivero (PERSON, 1) — **las cuatro `NEU`**

El análisis en sí es correcto. Lo que la revisión encontró no son errores
del modelo sobre esta nota: son huecos del pipeline alrededor de ella, y
todos se repiten en el resto del corpus. De ahí salió §3.

---

## 3. Oportunidades

### O1 · Detectar canónicas duplicadas 🔴

**Síntoma.** El mismo hospital vive en dos entidades canónicas:
`127 Hospital Jaime Mota` (artículo 45, *"La Fuerza del Pueblo denuncia
precariedades en los servicios de salud"*) y
`198 Hospital Regional Universitario Jaime Mota` (artículo 67). Las dos
notas son sobre las carencias del mismo centro; partidas en dos canónicas,
el conteo por entidad las cuenta como dos instituciones y se pierde
exactamente la corroboración cruzada que hace valioso el corpus.

**Evidencia.** Una detección por subconjunto de tokens (normalizando
acentos y descartando stopwords institucionales) da **13 pares candidatos**
sobre 200 canónicas:

| Duplicados reales | Falsos positivos |
|---|---|
| `2` / `140` Senado | **`7` PRM / `152` PRD** |
| `51` / `111` Congreso | `89` Gobierno RD / `92` Gobierno de Nicaragua |
| `8` / `88` / `89` Gobierno (tres filas) | `90` / `91` Min. RR.EE. RD vs Nicaragua |
| `33` / `34` Adora | |
| `57` Luis Henry Molina / `65` Luis H. Molina | |
| `127` / `198` Hospital Jaime Mota | |

Además, **175 de 200 canónicas aparecen en un solo artículo**. Parte es
corpus chico; parte es fragmentación real.

**Dos hallazgos de diseño que salieron de la medición:**

1. **Sugerir, nunca fusionar solo.** Fusionar PRM con PRD sería un desastre
   en cobertura política dominicana, y el patrón `RD vs Nicaragua` aparece
   dos veces. La detección propone; la persona decide.
2. **`LIKE '%…%'` no sirve.** No encuentra el caso `127`/`198`, porque
   `Hospital Jaime Mota` no es substring de `Hospital Regional
   Universitario Jaime Mota`. Hace falta comparación por tokens con lista
   de stopwords institucionales (`regional`, `universitario`, `nacional`,
   `de`, `la`…).

De paso, `34 Asociación de Radiodifusoras (Adora` — con paréntesis sin
cerrar — delata nombres truncados por el LLM; vale detectarlos aparte.

**Qué ya existe.** Toda la maquinaria de fusión:
`POST /api/canonical-entities/{id}/merge`
([canonical_entities.py:63](../../src/odin/api/routers/canonical_entities.py#L63)),
el botón "Fusionar" en
[CanonicalEntityManager.tsx:243](../../frontend/src/components/CanonicalEntityManager.tsx#L243),
el catálogo `entity_aliases` (el alias `SNS → Servicio Nacional de Salud`
funcionó en este mismo artículo) y `scripts/merge_duplicate_entities.py`
para el pase retroactivo. **Lo único que falta es encontrarlos**: nadie
revisa 200 canónicas a mano.

**Propuesta.** `GET /api/canonical-entities/duplicate-candidates` con la
comparación por tokens, y una sección de sugerencias en el manager que
reusa el merge que ya existe. Alcance acotado, sin tocar el pipeline de
análisis.

**Relación con el cliente:** R1 (ficha por actor e institución) y R10
(relación institución ↔ actor) no se sostienen sobre canónicas partidas.

---

### O2 · El reintento de Groq recorta el cuerpo sin dejar rastro 🔴

**Síntoma.** Cuando la salida del modelo se trunca,
[groq_analyzer.py:258-282](../../src/odin/analysis/groq_analyzer.py#L258-L282)
reintenta **una vez** con el cuerpo recortado de 7.000 a **3.000 chars** y
más cupo de salida. El reintento es correcto y deliberado — evita caer al
fallback pago de Gemini por un problema de reparto de tokens. El problema
es otro: **la fila guardada queda idéntica a una analizada completa**.
Mismo `analyzer_name`, mismo `analyzer_model`, mismo `analyzer_version`.
La única huella es un `log.warning` efímero.

**Evidencia.** Reproducido en vivo el 2026-08-29 sobre este mismo artículo:
un cuerpo de 5.499 chars disparó el reintento y el análisis salió sobre el
**54 % de la nota**, perdiendo el último tercio — donde aparece Jenny
Olivero, la directora que responde al señalamiento. En el corpus, **15
artículos caen en la banda 4.000–7.000 chars** y uno la supera (máx.
9.539, promedio 3.310). No es un caso teórico.

**Por qué importa aquí y no en otro proyecto.** Este repo ya construyó
linaje de análisis a propósito — `analyzer_name` / `analyzer_model` /
`analyzer_version` / `analysis_schema_version` existen justo para poder
responder *"¿por qué esta fila dice NEG?"* meses después y decidir
backfills selectivos. "Se analizó sobre la mitad del texto" es exactamente
esa clase de dato, y es el único que hoy no se guarda.

**Propuesta.** Registrar cuántos chars del cuerpo se analizaron (columna
propia o `content_flag`), y mostrarlo en la ficha del artículo. Barato, y
convierte un fallo silencioso en uno visible.

---

### O3 · Localidad: 58 de 62 artículos sin ella 🟡

**Síntoma.** El artículo 67 no tiene fila en `article_localities`, y no es
culpa del analizador: el texto **nunca nombra Barahona**. Pero la entidad
sí la implica — "Hospital Jaime Mota" ⇒ Barahona.

**Evidencia.** **58 de 62 artículos (94 %) sin localidad.** El filtro por
localidad del dashboard, recién construido, cubre hoy el 6 % del corpus.
`Barahona` sí está en el catálogo (`135` PROVINCIA, `136` Santa Cruz de
Barahona) y la tabla `locality_aliases` ya existe.

**Propuesta (a decidir, ver D1).** Un mapa entidad-canónica → localidad que
genere sugerencias con `origin=AUTO` para que el documentalista confirme.
El esquema ya distingue `MANUAL`/`AUTO` y `HECHO`/`MENCIONADO`, así que la
pieza que falta es la inferencia, no el modelo de datos.

**Relación con el cliente:** R2 (lugar geográfico del hecho), fase F2 del
documento de brecha. Ojo con la distinción que esa fase ya marca: el lugar
**donde ocurre el hecho** no es lo mismo que los lugares mencionados de
pasada.

---

### O4 · `blamed_actor` vacío justo en las denuncias 🟡

**Síntoma.** El artículo 67 es una denuncia sobre condiciones
hospitalarias y guardó `blamed_actor_id = NULL`.

**No es un bug.** La regla del prompt
([gemini_analyzer.py:295-297](../../src/odin/analysis/gemini_analyzer.py#L295-L297))
exige señalar solo a una entidad **ya listada** y marcada **explícitamente**
como causante, sin inferir por el cargo. La nota culpa a *"las autoridades
del centro hospitalario"* — genérico, no nombrado. El modelo obedeció.

**Evidencia.** Sobre los 36 artículos analizados por LLM:
`blamed_actor` en **10 (28 %)**, `credited_actor` en **20 (56 %)**,
`dominant_actor` en **36 (100 %)**.

**El efecto.** El campo "a quién se señala" se vacía precisamente en el
género de nota donde debería llenarse. Es una decisión editorial, no
técnica: o el KPI mide solo señalamientos nominales y se documenta así, o
el prompt admite señalados institucionales genéricos resueltos contra el
actor dominante. Ver D2.

---

### O5 · El sentimiento por entidad casi no discrimina 🟡

**Evidencia.** Distribución de `sentiment_toward` por motor:

| Motor | NEU | POS | NEG |
|---|---:|---:|---:|
| `groq` | 94 | 35 | 31 |
| `gemini` (tres variantes) | 30 | 10 | **0** |
| `local` | 34 | 18 | 15 |
| sin linaje | 105 | 19 | 18 |

**Gemini no produjo una sola etiqueta `NEG` en 40 menciones.** Nueve
artículos tienen todas sus entidades en `NEU`.

**Matiz importante.** En los motores LLM, `entities.sentiment_score` **no
es polaridad sino `sentiment_confidence`**
([gemini_analyzer.py:53-59](../../src/odin/analysis/gemini_analyzer.py#L53-L59)):
"qué tan marcada e inequívoca es la opinión". Las cuatro entidades del
artículo 67 en `NEU` con 0.8–0.9 significan *"el modelo está seguro de que
la nota no valora a nadie"*, lo cual es coherente con
`media_stance=neutra_transmisiva`. El conservadurismo puede ser correcto.

**El riesgo.** Si el entregable al cliente es "cómo trata la prensa a X",
una serie 60 % neutra que nunca baja de cero no sostiene una conclusión.
Además, con las cuatro entidades en `NEU`, el artículo 67 **no aporta nada
a la serie de sentimiento del Hospital Jaime Mota ni del SNS**: toda la
carga negativa vive en los campos de artículo (`framing`,
`facts_sentiment`), ninguna en los de entidad.

**Propuesta.** Medir contra un golden set **antes** de tocar el prompt.
`docs/PRECISION.md` y `scripts/evaluate.py` ya existen para eso. Sin esa
medición, cualquier ajuste es adivinar.

**Relación con el cliente:** R3 y R9 (comportamiento de los medios hacia
cada actor) se leen directamente de este campo.

---

### O6 · `sentiment_score` de artículo NULL en todo lo analizado por LLM 🟢

**Evidencia.** `articles.sentiment_score` es NULL en **36 de 40** filas con
linaje: las 30 de `groq` y las 6 de `gemini`. Solo las 4 de `local` lo
traen. Ningún analizador LLM emite ese número.

**Efecto.** El `SentimentBadge` de
[ReportsTable.tsx:167](../../frontend/src/components/reports/ReportsTable.tsx#L167)
y [AnalysisCard.tsx:94](../../frontend/src/components/AnalysisCard.tsx#L94)
queda sin confianza en la práctica totalidad del corpus. La agregación por
entidad **no sufre**: ahí Groq sí llena el score
([sentiment-aggregate.ts:34](../../frontend/src/lib/sentiment-aggregate.ts#L34)).

**Propuesta.** O se deriva de los campos que el LLM sí produce, o se quita
de la UI. Lo cosmético es decidir cuál; dejarlo NULL y seguir mostrando el
hueco no es una opción.

---

## 4. Prioridad

| # | Oportunidad | Evidencia | Esfuerzo | Estado |
|---|---|---|---|---|
| **O1** | Detectar canónicas duplicadas | 13 pares / 200 canónicas | Acotado | 🔴 propuesta |
| **O2** | Registrar el recorte del reintento | 15 artículos en la banda de riesgo | Chico | 🔴 propuesta |
| **O3** | Sugerir localidad | 58/62 sin localidad | Mediano · arquitectural | 🟡 requiere D1 |
| **O4** | `blamed_actor` en denuncias | 10/36 con señalado | Chico · decisión editorial | 🟡 requiere D2 |
| **O5** | Sentimiento por entidad | Gemini: 0 `NEG` en 40 | Mediano · medir primero | 🟡 propuesta |
| **O6** | `sentiment_score` de artículo | 36/40 NULL | Chico | 🟢 propuesta |

**Recomendación: O1 y O2, en ese orden.** Las dos son acotadas, las dos se
apoyan en piezas ya construidas (el merge existe; el linaje existe) y las
dos atacan datos que hoy están silenciosamente mal en la BD, no
funcionalidad ausente. **O3** es la de más valor para el cliente, pero es
arquitectural y merece su propio diseño.

---

## 5. Decisiones abiertas

### 🔴 D1 — ¿De dónde se infiere la localidad? (bloquea O3)

Tres caminos, no excluyentes: desde la **entidad canónica** (mapa
"Hospital Jaime Mota → Barahona"), desde el **texto** (NER de lugares +
`locality_aliases`), o desde la **fuente/sección**. El primero es el más
preciso y el más barato de mantener, pero exige poblar el mapa a mano. Sin
esta decisión, O3 no se puede planificar.

### 🔴 D2 — ¿`blamed_actor` admite señalados genéricos? (bloquea O4)

*"Las autoridades del centro hospitalario"* no es una entidad nombrada.
¿El campo mide solo señalamientos nominales (y se documenta que se vacía en
las denuncias institucionales), o se resuelve contra el actor dominante
cuando el señalado es genérico? Lo segundo llena el KPI pero mete
inferencia en un campo que hoy es literal.

### 🟡 D3 — ¿O1 va al manager o a la consola?

Sugerencias en `CanonicalEntityManager` (revisión continua por el
documentalista) o un pase tipo `merge_duplicate_entities.py` (limpieza
puntual del corpus). El manager es más trabajo y más valor sostenido.

### 🟡 D4 — ¿Se toca el prompt de sentimiento por entidad? (O5)

Solo después de medir contra el golden set. Si la medición dice que el
conservadurismo es correcto, la mejora es de **presentación** (explicar al
cliente que `NEU` domina a propósito), no de prompt.

---

## 6. Consultas de verificación

Para re-medir cuando crezca el corpus. Contra la BD de `docker-compose`:
`docker exec odin-db-1 psql -U odin -d odin -c "…"`.

```sql
-- O1 · fragmentación de canónicas
select count(*) as canonicas, count(*) filter (where n=1) as con_1_articulo
from (select ce.id, count(distinct e.article_id) n
      from canonical_entities ce
      left join entities e on e.canonical_entity_id = ce.id
      group by ce.id) t;

-- O2 · artículos en la banda de riesgo del reintento
select count(*) filter (where length(body) > 7000) as sobre_7000,
       count(*) filter (where length(body) between 4000 and 7000) as en_riesgo,
       round(avg(length(body))) as promedio, max(length(body)) as maximo
from articles where body is not null;

-- O3 · cobertura de localidad
select count(*) filter (where al.article_id is null) as sin_localidad,
       count(distinct a.id) as total
from articles a left join article_localities al on al.article_id = a.id;

-- O4 · cobertura de los actores del encuadre
select count(*) as total, count(blamed_actor_id) as con_blamed,
       count(credited_actor_id) as con_credited, count(dominant_actor_id) as con_dominant
from articles where analyzer_name is not null and analyzer_name <> 'local';

-- O5 · distribución de sentimiento por entidad y motor
select a.analyzer_name, e.sentiment_toward, count(*)
from entities e join articles a on a.id = e.article_id
group by 1, 2 order by 1, 3 desc;

-- O6 · sentiment_score de artículo por motor
select analyzer_name, count(*) total,
       count(*) filter (where sentiment_score is null) sin_score
from articles group by analyzer_name;
```

La detección de duplicados de O1 (subconjunto de tokens) no es una sola
consulta SQL; el prototipo que produjo la tabla de §3 fue un script
descartable en Python. Si O1 se aprueba, esa lógica se implementa en el
backend, no se rescata del scratchpad.

---

## 7. Registro de cambios

- **2026-08-29** — Documento creado. O1–O6 a partir de la revisión del
  artículo 67 (job `96c4ba02`), con medición contra un corpus de 62
  artículos y 200 canónicas.
