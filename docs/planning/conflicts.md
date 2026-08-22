# Conflictos de diseño

Bitácora de tensiones arquitectónicas de Odin: decisiones que hoy funcionan
pero que chocan entre sí, tienen un techo cercano o no se pueden verificar. No
es una lista de bugs (esos se arreglan y se cierran) ni un backlog de features
— es el registro de "esto va a doler cuando crezca, y por qué".

Cada entrada anota el conflicto, la **evidencia medida** (no la impresión), la
solución propuesta y su estado. Se actualiza cuando la evidencia cambia, no
cuando cambia la opinión.

## Estado actual

| # | Conflicto | Estado | Bloquea |
|---|---|---|---|
| 1 | El esquema no cabe en el free tier de Groq (92% del TPM) | mitigado; solución propuesta sin implementar | añadir campos nuevos |
| 2 | Los dos motores no leen el mismo artículo (16.000 vs 4.000 chars) | abierto — decisión de producto | consistencia del corpus |
| 3 | Modelo de entidades plano vs. relaciones fuente→objetivo | pospuesto a propósito | atribución de críticas |
| 4 | **Se cambió el prompt sin poder medir el efecto** | abierto | **la validación de 1, 2 y 3** |

Orden recomendado: **4 → deuda menor → 2 → 1 → 3** (ver el final del
documento).

---

## 2026-08-05 — Enriquecer el análisis choca con el presupuesto de tokens y con la falta de medición

**Contexto.** Ese día el esquema de análisis pasó de v1 a v2: se reordenaron
los campos de evidencia→conclusión y se añadieron siete señales nuevas
(`sentiment_basis`, `facts_sentiment`, `quoted_sentiment`, `media_stance`,
`media_stance_evidence`, `overall_sentiment_reason`, `content_flags`), más el
fallback Groq→Gemini. Todo eso funciona y está probado. Lo que sigue es lo que
**no** quedó resuelto.

### Conflicto 1 — El esquema ya no cabe en el free tier de Groq

Groq (`openai/gpt-oss-120b`, plan `on_demand`) limita a **8.000 tokens por
request**, y ese límite cuenta `prompt + max_completion_tokens` — el cupo de
salida se **reserva**, no es un simple tope de lo generado (esto costó dos
fallos: primero `413 rate_limit_exceeded`, después `finish_reason=length`).

Medición al cierre del día:

| Concepto | Tokens |
|---|---|
| System prompt (`_SYSTEM`) | ~1.460 |
| **Esquema JSON (`_Analysis`)** | **~1.689** |
| Sobrecarga fija por request | **~3.149** |
| Cuerpo del artículo (`_MAX_BODY_CHARS=4.000`) | ~1.000 |
| Cupo de salida reservado | 3.200 |
| **Total peor caso** | **~7.350 / 8.000 (92%)** |

El esquema por sí solo consume más que el artículo. **No queda margen para
añadir campos**: cada señal nueva hay que pagarla recortando texto del
artículo, y ese recorte ya demostró costar información real — en la nota
"Danilo Medina rechaza versión de Abinader sobre deuda" el cuestionamiento al
Gobierno aparece en el último tercio, justo la zona que Groq no llega a ver.

#### De qué está hecho el schema (medido)

| | Tokens | |
|---|---|---|
| Estructura JSON (`type`, `title`, `$defs`, `anyOf`…) | ~757 | andamiaje, no instrucciones |
| Descripciones de campos | ~931 | **55% del schema** |

Los campos más caros en descripción: `framing` (96), `entity.confidence` (62),
`content_flags` (61), `media_stance` (59), `source_quality` (47).

**Trampa a evitar:** mover descripciones al system prompt **no ahorra nada** —
los dos viajan en cada llamada. El único ahorro real viene de *eliminar la
duplicación* entre ambos, no de reubicarla.

#### Descartado: cambiar de modelo (verificado 2026-08-05)

Sondeo de la cuenta actual leyendo `x-ratelimit-limit-tokens`:

| Modelo | TPM | ¿`json_schema`? |
|---|---|---|
| `openai/gpt-oss-120b` (actual) | 8.000 | sí |
| `openai/gpt-oss-20b` | 8.000 | sí |
| `llama-3.3-70b-versatile` | **12.000** | **no** (400) |
| `qwen/qwen3.6-27b`, `llama-3.1-8b-instant` | — | no (400) |

**No existe un cambio de modelo gratis:** los únicos que aceptan salida
estructurada topan en 8.000. El comentario en `groq_analyzer.py` sobre
llama-3.3 sigue siendo correcto.

#### Descartado: partir la llamada en dos

El TPM es un presupuesto **por minuto**, no por request (el error fue
`Limit 8000, Requested 10517`). Dos llamadas de ~4.500 dentro del mismo minuto
suman 9.000 y vuelven a chocar. Solo funcionaría espaciándolas ~60s, inviable
para un flujo de "pego un link y espero". Duplica complejidad sin levantar el
límite.

#### Solución propuesta

**1. Separar el esquema por caso de uso (recomendada).** El error de diseño no
es el tamaño del schema: es que **un mismo esquema sirve a dos casos con
economías opuestas**, y el barato le impone su límite al caro.

| | Pegar un link | Rastreo masivo |
|---|---|---|
| Volumen | 1 artículo, manual | cientos, automático |
| Costo por artículo | irrelevante | dominante |
| Prioridad | máxima calidad | cobertura |

- `/api/analyze` → Gemini, esquema completo, 16.000 chars, sin truncar.
- Crawl → Groq con un esquema magro (entidades + sentimiento global +
  encuadre, sin capas de atribución), que cabe holgado en 8.000.

Disuelve el conflicto en vez de administrarlo. No exige pipeline nuevo:
`_result_from_llm` ya está compartido; sería un segundo modelo Pydantic
reducido.

**2. Alternativa si se quiere análisis rico y gratis en Groq:** renunciar a
`json_schema` para poder usar `llama-3.3-70b-versatile` (12.000 TPM) y de paso
eliminar los ~757 tokens de andamiaje. El formato se describe a mano (más
compacto que el JSON Schema autogenerado) y **Pydantic valida**; si no valida,
el fallback a Gemini ya existente cubre. Estimado: ~9.200 de 12.000, es decir
**sin truncar el cuerpo**. Riesgos: más fallos de parseo, y calidad de
llama-3.3 en matiz político dominicano **sin medir** (ver Conflicto 4).

**3. Gratis, hágase lo que se haga:** deduplicar `_SYSTEM` (~1.460) contra las
descripciones (~931). Hay solapamiento real —las cuatro capas y las reglas de
entidades se explican en ambos sitios—; consolidar debería liberar 300-500
tokens sin perder ninguna indicación.

**No recortar campos por intuición.** Es tentador (`framing` cuesta 96 tokens),
pero no hay con qué decidir cuál aporta: es exactamente el Conflicto 4.

**Estado:** mitigado al 92% de uso. Bloquea cualquier campo nuevo. Solución 1
propuesta, sin implementar.

### Conflicto 2 — Los dos motores no leen el mismo artículo

`GroqAnalyzer` y `GeminiAnalyzer` comparten `_SYSTEM` y `_Analysis` (mismo
objeto en memoria, verificado con `is`), pero **no la misma entrada**:

| | Gemini | Groq |
|---|---|---|
| Cuerpo enviado | 16.000 chars | **4.000 chars** |
| Cupo de salida | 6.144 | 3.200 |

Con el fallback activo (`ODIN_ANALYZER=groq+gemini`), el mismo artículo puede
producir análisis distintos según quién respondió. Para un producto de
monitoreo de medios —donde el valor está en comparar cobertura a lo largo del
tiempo— eso genera un corpus heterogéneo. `analyzer_name`/`model`/`version`
registran quién respondió, pero **registrar la inconsistencia no la elimina**.

**Solución propuesta.** Decidir explícitamente qué se prioriza:

- Si pesa más la **consistencia**: Gemini como motor único de `/api/analyze`.
  Elimina el truncado asimétrico y el techo del Conflicto 1 de una vez.
- Si pesa más el **costo**: mantener el fallback, pero tratar los análisis de
  Groq y de Gemini como series comparables solo dentro de su propio motor al
  hacer estadísticas agregadas.

**Estado:** abierto. Decisión de producto, no técnica.

### Conflicto 3 — El modelo de entidades es plano; la metodología pide relaciones

Las cuatro capas añadidas (`facts_sentiment`, `quoted_sentiment`,
`media_stance`, más el `sentiment_toward` por entidad) son **a nivel
documento**. La entidad sigue siendo `entidad → un sentimiento hacia ella`.

Consecuencia: **"Medina → Gobierno: negativo" no se puede representar**. Cuando
el objetivo de una crítica es implícito o cuando una fuente evalúa a otra
entidad, el pipeline lo pierde o lo aplana. `quoted_sentiment` mitiga el
síntoma (dice que la carga vive en el discurso citado) pero no la causa.

**Solución propuesta.** Migrar a tuplas fuente→objetivo
(`{fuente, objetivo, polaridad, evidencia}`). **No es un campo más**: exige
tabla de relaciones en la BD, cambios en `canonicalize.py` (hoy funde por
`(nombre, tipo)`, no por relación) y rediseño del panel de entidades. Es un
proyecto propio, no un incremento. **No abordarlo antes del Conflicto 4.**

**Estado:** abierto, deliberadamente pospuesto.

### Conflicto 4 — Se cambió el prompt sin poder medir el efecto (el más grave)

- El golden set (`tests/eval/golden_set.jsonl`) tiene **42 artículos** (6
  fuentes: `diario_libre` 5, `manual` 33, `acento` 1, `al_momento` 1,
  `el_dia` 1, `n_digital` 1).
- `scripts/evaluate.py` mide entidades (P/R/F1), matriz de confusión de
  `overall_sentiment`, accuracy de `sentiment_toward` **y ya puntúa los
  campos nuevos** (`framing`, `sentiment_basis`, `facts_sentiment`,
  `quoted_sentiment`, `media_stance`, `content_flags`) cuando el golden set
  los etiqueta.
- El prompt pasó de v5 a v6 con cambios sustanciales y, en su momento,
  **cero medición**.

En el momento en que se hizo el cambio v5→v6, lo único que se podía afirmar
era que el análisis era más rico conceptualmente y que no rompía nada. **No
que fuera más preciso.** Con apenas 7 artículos, ninguna diferencia de
métrica habría sido estadísticamente distinguible del ruido, así que las
decisiones de los conflictos 1-3 se estaban tomando a ciegas (ver **Estado**
más abajo: esto ya se corrigió con el golden set ampliado).

**Solución propuesta — y es la que debería ir primero:**

1. Ampliar el golden set a **30-50 artículos** reales etiquetados a mano, con
   variedad deliberada: notas de prensa partidarias, reportajes con datos
   duros, declaraciones cruzadas, y casos límite (negaciones, desmentidos,
   ironía).
2. Extender `scripts/evaluate.py` para cubrir las dimensiones nuevas: accuracy
   de `media_stance`, de `sentiment_basis`, y coherencia entre
   `facts_sentiment`/`quoted_sentiment`/`overall_sentiment`.
3. Fijar la medición de la v6 como línea base **antes** de tocar el prompt otra
   vez.

**Estado (2026-08-13):** el golden set creció de 7 a **42 artículos**
(6 fuentes: `diario_libre` 5, `manual` 33, `acento` 1, `al_momento` 1,
`el_dia` 1, `n_digital` 1) y `scripts/evaluate.py` ya puntúa los campos nuevos (`framing`,
`sentiment_basis`, `facts_sentiment`, `quoted_sentiment`, `media_stance`,
`content_flags`) cuando el golden set los etiqueta. Se fijó una línea base
**local** medida contra esos 42 artículos (F1 entidades 74.0%, accuracy
sentimiento global 59.5%, accuracy `sentiment_toward` 59.9% — ver
`docs/PRECISION.md` §4, `tests/eval/baselines/2026-08-13-local.json`). La
línea base de **Groq** se intentó el mismo día y quedó **bloqueada**: falla
determinística (`json_validate_failed`, ver deuda menor abajo) que tumba la
corrida completa sin reporte parcial. Sigue **bloqueando la validación de
1, 2 y 3** hasta que exista al menos una línea base LLM (Groq o Gemini)
medida.

**Actualización (2026-08-14) — 4 fixes de `LocalAnalyzer` medidos contra el
mismo golden set.** Plan
`docs/superpowers/plans/2026-08-14-local-analyzer-accuracy.md`, 4 tareas:
(1) dejar de filtrar "Gobierno" como ORG genérico, (2) preferir el nombre de
display más completo sobre el más frecuente al fusionar alias de una misma
entidad, (3) resolver siglas institucionales dominicanas conocidas (PLD,
ITLA, etc.) vía el catálogo estático `SEED_ALIASES` (ya existía para
`canonicalize.py`, pero `LocalAnalyzer` nunca lo consultaba), y (4) atenuar
hacia NEU el sentimiento de frases con negación/desmentido explícito.
Números reales, `local`, mismos 42 artículos (detalle y desglose por tipo en
`docs/PRECISION.md` §4, reportes completos en
`tests/eval/baselines/2026-08-13-local.json` y
`tests/eval/baselines/2026-08-14-local.json`):

- F1 entidades (overall): 74.0% → 80.4%.
- F1 ORG: 52.6% → 65.9% — sube con claridad, el objetivo directo de las
  Tareas 1-3.
- F1 PERSON: 94.9% → 94.9% (sin cambio neto), pero **no fue tan directo
  como parece**: la Tarea 2 introdujo una regresión real (94.1%,
  tp/fp/fn 119/11/4), encontrada precisamente por este proceso de
  re-medición contra el golden set completo. Se aisló a un solo caso
  (`odin-db-040`: el artículo escribe el nombre del gold, "Eduardo Sanz
  Lovatón", una vez con un apodo insertado entre guiones — "Eduardo -Yayo-
  Sanz Lovatón" — que la regla de "preferir más palabras" de la Tarea 2
  elegía como display name, rompiendo el emparejamiento por substring
  contiguo del evaluador contra el gold). Se corrigió `_best_display_name`
  con una guarda que excluye del conteo de palabras cualquier variante con
  un apodo insertado entre guiones/paréntesis/comillas, validado contra los
  42 artículos completos (no solo el caso que lo motivó) antes de darlo por
  bueno — el resultado final vuelve exactamente al valor de 2026-08-13
  (120/10/3).
- Accuracy `overall_sentiment`: 59.5% → 59.5%, sin cambio (misma matriz de
  confusión antes y después).
- Accuracy `sentiment_toward`: 59.9% → 59.5%.

**Dos cosas quedan explícitamente abiertas después de esta medición:**

1. **Los 2 artículos que motivaron la Tarea 4 (`odin-db-024`, `odin-db-025`)
   siguen prediciendo NEG con gold NEU** (0.4567 y 0.6221
   respectivamente), re-chequeado en esta misma medición. El plan documenta
   por qué (Tarea 4, "Estado real" bajo el Step 7): con el `factor=0.5`
   literal del plan —el valor finalmente shippeado, después de que una
   revisión rechazara un ajuste no validado (`factor=0.08`) curva-ajustado
   contra solo esos 2 artículos por ser riesgo no medido contra el resto del
   corpus— ninguno de los 2 casos llega a NEU. Arreglar esto sin volver a
   curva-ajustar contra 2 casos requiere más artículos con negación/desmentido
   en el golden set.
2. **El clúster más grande de errores de `overall_sentiment` sigue sin
   tocar**: 14 de los 17 artículos mal clasificados en la medición original
   (`overall_sentiment` POS/NEG del gold cae a NEU por dilución en artículos
   largos con mucho contenido administrativo/narrativo —
   `odin-db-002/003/014/019/027`, etc.). El plan lo dejó deliberadamente
   fuera de alcance (ver su sección "Fuera de alcance"): se investigó un
   filtro de "frases tabulares" por densidad de dígitos y se descartó tras
   medirlo contra el texto real (no discrimina de forma confiable), y
   rediseñar la agregación de sentimiento con solo 42 artículos de
   referencia es el mismo "ajuste a ciegas" que este documento ya advierte
   evitar. Necesita más artículos en el golden set antes de intentar un fix
   seguro.

#### Actualización 2026-08-20 — el punto 2 de arriba estaba mal diagnosticado

**La hipótesis de "dilución en artículos largos" quedó refutada al medirla.**
Los artículos mal clasificados son **más cortos** que los acertados (457 vs.
525 palabras de media). La longitud no explicaba el error, así que "necesita
más artículos en el golden set antes de intentar un fix seguro" tampoco era
cierto: el fix se podía identificar y validar con los 42 que ya había.

La causa real es un **sesgo de clase del modelo base**. `_aggregate` era una
media plana de probabilidades: pysentimiento deja ~50% de masa NEU por frase,
así que promediar converge a esa tasa base. El analizador emitía POS **solo 3
veces en 42 artículos cuando el gold trae 12**, con **cero** confusiones
POS↔NEG. Y la misma función servía a dos problemas opuestos —el artículo
(decenas de frases, hay que des-diluir) y la entidad (mediana de 1 frase, hay
que ser conservador)—, que era el defecto de raíz.

Se separó en `_aggregate_document` (log-pooling con corrección de prior, sin
umbral que tunear, prior medido sobre corpus aparte vía
`scripts/estimate_sentiment_prior.py` sobre 162 artículos scrapeados que
excluyen las URLs del golden set) y `_aggregate_entity` (gate de
corroboración). Resultado medido: `overall_sentiment` 59.5% → **73.8%**
(recall de POS 3/12 → 9/12), `sentiment_toward` 59.5% → **70.5%**, F1 de
entidades idéntico. El golden set no participa en calibrar el prior, así que
la cifra no es un ajuste al conjunto de prueba. Detalle completo en
`docs/PRECISION.md` §4.

**Dos cosas nuevas que este documento debe registrar:**

1. **El "59.9% → 59.5%" de la medición del 2026-08-14 nunca fue una
   regresión.** `sentiment_toward` solo se puntuaba sobre entidades
   emparejadas: 51 entidades etiquetadas (20.3%) quedaron fuera del
   denominador, y los 18 ORGs recién emparejados por los fixes de ORG
   diluyeron un numerador PERSON fijo. La nota de arriba que lo atribuye a "un
   efecto de segundo orden, probablemente por qué entidades terminan
   emparejadas" apuntaba en la dirección correcta pero se quedó corta: es
   aritmética del denominador, no ruido. `scripts/evaluate.py` ahora reporta
   también una accuracy **end-to-end** con denominador estable.
2. **`sentiment_toward` tiene un techo estructural, no un umbral mal puesto.**
   Responder siempre NEU acierta el **71.5%**; el 70.5% actual no le gana, y
   ninguna de las 12 reglas de gating probadas lo supera. La entidad hereda el
   sentimiento de toda la frase y un modelo de frase no puede decidir de quién
   es. Superarlo exige atribución por rol sintáctico o un LLM. **Ninguna cifra
   de `sentiment_toward` debería presentarse sin ese piso al lado.**

Sigue abierto el punto 1 (los 2 artículos con negación explícita): `odin-db-024`
y `odin-db-025` siguen prediciendo NEG con gold NEU. Además, re-medido en este
contexto, **`dampen_negated` ya no cambia ninguna de las tres métricas** — se
deja intacto por no ser un cambio medido fuera de estos 42 artículos, pero
queda como candidato a eliminación cuando el golden set crezca.

### Deuda menor asociada

- **El fallback no distingue "mal configurado" de "falló"**
  (`analysis/fallback_analyzer.py`): al faltar `GROQ_API_KEY`, degradó en
  silencio a Gemini facturado en cada análisis. Un error de configuración
  debería fallar ruidosamente al arrancar, no convertirse en gasto callado.
- **Campos nuevos invisibles**: el frontend no los muestra y
  `ArticleUpdatePayload` no permite corregirlos. Se calculan y se guardan sin
  que nadie pueda verlos ni rectificarlos.
- **Sin ruta de backfill**: conviven filas con `analysis_schema_version` 1 y 2,
  sin herramienta de re-análisis selectivo. La heterogeneidad crece con el
  corpus.
- **Cuerpos ya guardados con mojibake**: el arreglo de codificación
  (`url_guard._decode_html`) corrige los análisis nuevos, no reescribe los
  artículos viejos.
- **`groq_analyzer.py` solo reintenta el truncado, no otros fallos de la
  API**: su `_call_groq` solo reintenta `_TruncatedOutput`
  (`finish_reason=length`); cualquier otro `APIStatusError` (p. ej.
  `json_validate_failed`) se propaga como `RuntimeError` sin captura por
  artículo en `evaluate()`, así que un solo artículo con salida estructurada
  inválida tumba una corrida completa de N artículos sin reporte parcial —
  bloqueó la línea base de Groq del golden set ampliado (2026-08-13, ver
  `docs/PRECISION.md` §4).

### Orden recomendado

1. **Conflicto 4** (medir) — sin esto lo demás es opinión.
2. Deuda menor: fallback ruidoso + mostrar los campos en la UI.
3. **Conflicto 2** (decidir motor) con datos del punto 1.
4. **Conflicto 1** solo si el punto 3 se queda en Groq.
5. **Conflicto 3** al final, como proyecto propio.
