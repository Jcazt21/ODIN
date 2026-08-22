# Precisión del análisis: metodología y resultados

> Este documento existe para que las cifras de precisión que se muestran a un
> cliente tengan una metodología reproducible detrás — reemplaza los rangos
> sin evidencia que hoy aparecen en el README (`task.md` §2.4, §10.2).
> **Estado actual: metodología lista, muestra insuficiente para publicar
> cifras como compromiso.** No repetir los porcentajes del README
> ("~75-85%", "~80%", "~60-70%") en material de cliente hasta que este
> documento tenga resultados con una muestra representativa.

## 1. Qué mide y cómo

**Golden set**: `tests/eval/golden_set.jsonl`, formato JSONL descrito en
`tests/eval/README.md`. Cada línea es un artículo real etiquetado a mano:
`id, source, url, title, body, overall_sentiment, entities_exhaustive,
entities[{name, type, sentiment_toward}], notes`.

`entities_exhaustive: false` marca artículos donde el etiquetado de
entidades es parcial (no se listaron todas) — el evaluador respeta esa
bandera para no contar falsos positivos sobre entidades que simplemente no se
etiquetaron.

**Evaluador**: `scripts/evaluate.py`. Corre un analizador (`--analyzer
{local,gemini,groq,hybrid}`) contra el golden set y calcula:

- **Precision / recall / F1 por tipo de entidad** (`PERSON`, `ORG`) y global
  (`EntityMetrics`). Emparejamiento por nombre normalizado con contención de
  substrings (`_names_match`), el mismo criterio que usa
  `analysis/canonicalize.py` en producción — para que la métrica refleje el
  mismo criterio de "es la misma entidad" que usa el sistema real.
- **Matriz de confusión de `overall_sentiment`** (`ConfusionMatrix`):
  POS/NEG/NEU predicho vs. etiquetado.
- **Accuracy de `sentiment_toward`** sobre las entidades que sí emparejaron
  correctamente (no tiene sentido medir sentimiento hacia una entidad que ni
  siquiera se detectó).

```bash
python scripts/evaluate.py --golden-set tests/eval/golden_set.jsonl \
    --analyzer local --out reporte.json
```

El CLI avisa con 5 segundos de margen antes de correr `--analyzer gemini`
(u otro motor facturado) por el costo — no correr esa opción sin que el
usuario lo pida explícitamente (ver `CLAUDE.md`).

Tests unitarios del evaluador: `tests/scripts/test_evaluate.py`.

## 2. Estado actual de la muestra

**42 artículos** en `tests/eval/golden_set.jsonl` a la fecha de este
documento, repartidos entre **6 fuentes** (`diario_libre` 5, `manual` 33,
`acento` 1, `al_momento` 1, `el_dia` 1, `n_digital` 1 — verificado contando
el campo `source` de cada fila). El objetivo fijado en `task.md` §2.4 es
**150-300 artículos**. Con 42 casos:

- Cualquier métrica calculada sigue teniendo un intervalo de confianza
  amplio (un puñado de artículos mal clasificados mueve el F1 varios
  puntos), aunque ya menos frágil que la muestra original de 7.
- La distribución por fuente es muy desigual (`manual` concentra 33 de 42),
  y no hay garantía de reparto uniforme por sección (política, economía,
  sucesos, etc.) — el rendimiento real puede variar mucho por sección
  (titulares de sucesos vs. columnas de opinión, por ejemplo).
- **No se debe publicar ningún número derivado de esta muestra como cifra de
  producto.** Sirve para verificar que el evaluador funciona end-to-end y
  para fijar una línea base de referencia entre corridas, no para reportar
  precisión de cara a cliente.

## 3. Cómo crecer el golden set

1. Etiquetar a mano 150-300 artículos reales, repartidos por fuente y
   sección (no solo los que ya están en `odin.db` — conseguir variedad
   deliberadamente).
2. Por artículo: entidades correctas con su tipo, sentimiento global,
   sentimiento hacia cada entidad (`task.md` §2.4, punto 1).
3. Agregar cada lote nuevo a `tests/eval/golden_set.jsonl` (formato en
   `tests/eval/README.md`), no reemplazar el archivo.
4. Correr `scripts/evaluate.py` en cada cambio de heurística de
   `local_analyzer.py` (`_VENUE_WORDS`, `_is_named_after_place`, etc.) para
   saber si el cambio mejora o empeora el resultado — hoy no hay forma de
   saberlo sin esto.

## 4. Historial de mediciones

| Fecha | Tamaño de muestra | Analizador | F1 entidades | Accuracy sentimiento global | Accuracy `sentiment_toward` | Publicable como cifra de producto |
|---|---|---|---|---|---|---|
| 2026-08-13 | 42 | `local` | 74.0% | 59.5% | 59.9% | **No** — muestra insuficiente (objetivo 150-300) |
| 2026-08-14 | 42 | `local` | 80.4% | 59.5% | 59.5% | **No** — muestra insuficiente (objetivo 150-300) |
| 2026-08-20 | 42 | `local` | **82.7%** | **73.8%** | 68.7% (**e2e 58.6%**) | **No** — muestra insuficiente (objetivo 150-300) |

Reporte completo: `tests/eval/baselines/2026-08-13-local.json` (2026-08-13),
`tests/eval/baselines/2026-08-14-local.json` (2026-08-14). Nota:
`LocalAnalyzer` no es un LLM y no llena de forma significativa los campos de
encuadre/atribución (`framing`, `sentiment_basis`, etc.) — sus accuracies
para esos campos, presentes en el JSON, no reflejan juicio real y no se
copian aquí.

**Medición 2026-08-14 — 4 fixes de extracción de entidades y sentimiento.**
Corrida contra el mismo golden set de 42 artículos, después de implementar
las 4 tareas de
`docs/superpowers/plans/2026-08-14-local-analyzer-accuracy.md`: dejar de
filtrar "Gobierno" como ORG genérico (Tarea 1), preferir el nombre de
display más completo sobre el más frecuente al fusionar alias de una misma
entidad (Tarea 2), resolver siglas institucionales dominicanas conocidas
(PLD, ITLA, etc.) vía el catálogo estático `SEED_ALIASES` (Tarea 3), y
atenuar hacia NEU el sentimiento de frases con negación/desmentido explícito
(Tarea 4). Desglose por tipo (no está en la tabla, que solo reporta F1
global de entidades):

| Métrica | 2026-08-13 | 2026-08-14 |
|---|---|---|
| F1 ORG | 52.6% | **65.9%** |
| F1 PERSON | 94.9% | 94.9% (sin cambio neto) |
| F1 entidades (overall) | 74.0% | 80.4% |
| Accuracy `overall_sentiment` | 59.5% | 59.5% (sin cambio) |
| Accuracy `sentiment_toward` | 59.9% | 59.5% |

F1 de ORG sube con claridad (+13.3 puntos, tp/fp/fn 65/51/66 → 83/38/48) —
es el objetivo directo de las Tareas 1-3, consistente con las causas de
falsos negativos de ORG medidas en el plan.

**Nota sobre F1 de PERSON — pasó por una regresión real antes de esta
medición final.** La primera corrida contra el código de las Tareas 1-4 dio
94.1% (119/11/4), una caída de 0.8 puntos. Se investigó y se aisló a un solo
caso real, no ruido de entorno: `odin-db-040` (gold `"Eduardo Sanz
Lovatón"`) — el cuerpo del artículo escribe el nombre una vez como
`"Eduardo -Yayo- Sanz Lovatón"` (apodo entre guiones, patrón común del
periodismo dominicano) y tres veces como `"Sanz Lovatón"`. La regla de la
Tarea 2 (preferir la variante con más palabras significativas) elegía la
variante con el apodo por tener más palabras "en bruto", pero el apodo
insertado rompía el emparejamiento por substring contiguo del evaluador
contra el gold — convirtiendo un acierto en un falso positivo + un falso
negativo. Se corrigió `_best_display_name` (guarda `_has_nickname_splice`:
una variante con un segmento entre guiones/paréntesis/comillas con texto
real a ambos lados no compite por conteo de palabras) y se validó de nuevo
contra los 42 artículos: **F1 de PERSON vuelve exactamente a 94.9%
(120/10/3)**, idéntico al valor de 2026-08-13, sin afectar el F1 de ORG.

**Nota sobre `overall_sentiment` (59.5% → 59.5%, sin cambio) y
`sentiment_toward` (59.9% → 59.5%, -0.4 puntos).** La matriz de confusión de
`overall_sentiment` es idéntica antes y después. La Tarea 4 (amortiguador de
negación) tiene un cortocircuito documentado en el plan (Tarea 4, "Estado
real" bajo el Step 7): con el `factor=0.5` literal del plan (el valor
finalmente shippeado, tras revertir un ajuste no validado contra solo 2
artículos), **ninguno de los 2 artículos que motivaron la tarea alcanza
NEU** — re-chequeado en esta misma medición: `odin-db-024` sigue
prediciendo NEG (0.4567) y `odin-db-025` sigue prediciendo NEG (0.6221),
ambos con gold NEU. La pequeña caída en `sentiment_toward` (0.4 puntos) no
se investigó a fondo — es un efecto de segundo orden, probablemente por qué
entidades terminan emparejadas con el gold cambia levemente entre las dos
corridas; no se considera significativo dado el tamaño de muestra (42
artículos). El clúster de error más grande de `overall_sentiment` (dilución
de sentimiento en artículos largos y narrativos, 14 de los 17 casos mal
clasificados en la medición original) queda fuera de alcance de este plan —
ver `docs/planning/conflicts.md`, Conflicto 4.

**"Gobierno" seguía siendo el falso negativo más grande de ORG, y la Tarea 1 de
2026-08-14 no lo había arreglado.** Al medir los 48 falsos negativos de ORG,
11 (23%) eran literalmente `"Gobierno"`. La Tarea 1 lo había quitado de
`_GENERIC_STATE_ORGS` justamente para esto, pero ese filtro **solo actúa sobre
spans que spaCy ya marcó ORG** — y `es_core_news_lg` etiqueta "Gobierno" como
**LOC 25 veces contra 2 como ORG** (medido sobre 20 artículos), porque lo trata
como metonimia del país. El span nunca llegaba al filtro.

El arreglo promueve a ORG las cabezas institucionales
(`_INSTITUTION_HEADS`: gobierno, presidencia, poder judicial, ministerio
público) sin importar qué etiqueta les puso spaCy, reutilizando el mismo punto
de promoción que ya existía para los acrónimos MISC del catálogo. Resultado:

| Métrica | Antes | Después |
|---|---|---|
| F1 ORG | 65.9% | **71.3%** |
| Recall ORG | 63.4% | **74.1%** |
| F1 entidades (overall) | 80.4% | **82.7%** |
| F1 PERSON | 94.9% | 94.9% (sin tocar) |

Se descartó de paso una hipótesis alternativa: que muchos falsos negativos
fueran en realidad entidades sí detectadas pero nombradas distinto (p.ej.
"UNICEF" vs. "Fondo de las Naciones Unidas para la Infancia"). Al medirlo,
**solo 3 de los 48** comparten palabra con un falso positivo del mismo
artículo — no es un problema de convención de nombres.

**Medición 2026-08-20 — la agregación de sentimiento, y por qué la hipótesis
de 2026-08-14 era incorrecta.** El plan del 2026-08-14 atribuyó el 59.5% de
`overall_sentiment` a "dilución de sentimiento en artículos largos" y lo dejó
fuera de alcance. **Esa hipótesis quedó refutada al medirla**: los artículos
mal clasificados son de hecho **más cortos** que los acertados (457 vs. 525
palabras de media). La longitud no explicaba nada.

La causa real es un **sesgo de clase**. `_aggregate` era una media plana de
probabilidades con argmax: pysentimiento está entrenado en tuits y deja ~50%
de masa NEU por frase, así que promediar decenas de frases hace converger
cualquier artículo a esa tasa base. Síntoma medido: el analizador emitía POS
**solo 3 veces en 42 artículos cuando el gold trae 12**, con **cero**
confusiones POS↔NEG — el modelo acertaba el signo, no se atrevía a salir de
NEU. 14 de los 17 errores eran POS/NEG colapsando a NEU.

Además, `_aggregate` servía a **dos problemas opuestos** con una sola función:
el artículo agrega decenas de frases (hay que des-diluir), la entidad agrega
**una sola** (mediana medida = 1 mención) y hay que ser conservador. Ese era el
defecto de raíz. Se separó en `_aggregate_document` y `_aggregate_entity`.

| Métrica | 2026-08-14 | 2026-08-20 |
|---|---|---|
| Accuracy `overall_sentiment` | 59.5% | **73.8%** |
| Recall de POS (artículos) | 3/12 | **9/12** |
| Accuracy `sentiment_toward` (end-to-end) | 47.4%\* | **58.6%** |
| Precisión de etiquetas polares | 32.9% | **50.0%** |
| F1 entidades (overall / ORG / PERSON) | 80.4 / 65.9 / 94.9 | **82.7 / 71.3** / 94.9 |

\* Recalculada a mano sobre la línea base de 2026-08-14 (119 aciertos / 251
entidades etiquetadas) porque aquel reporte no emitía la métrica end-to-end.

**La `sentiment_toward` condicional bajó de 70.5% a 68.7%, y eso NO es una
regresión** — es el mismo espejismo del denominador descrito más abajo, ahora
disparado a propósito: al recuperar 14 entidades ORG más, el denominador pasó
de 200 a 214. La end-to-end (denominador fijo) subió, y la precisión polar
también. Es exactamente el caso que motivó añadir la métrica end-to-end.

`_aggregate_document` descuenta la tasa base de cada clase (log-pooling con
corrección de prior). **No tiene ningún umbral que tunear**, y el prior **no
sale del golden set**: se mide con `scripts/estimate_sentiment_prior.py` sobre
un corpus scrapeado aparte (162 artículos / 3.109 frases, excluyendo las URLs
del golden set) y se guarda en `src/odin/analysis/sentiment_prior.json`. Es
decir, los 42 artículos de evaluación **nunca participan en calibrar nada**:
el 73.8% es una cifra limpia, no un ajuste al conjunto de prueba.

Robustez verificada de tres formas:

- Con el prior estimado **solo** sobre folds de entrenamiento del propio golden
  set (7-fold × 30 seeds): **72.2% held-out vs. 59.5%** de la línea base.
- Con ±10% de error en el prior el resultado se mueve entre 66.7% y 73.8% —
  siempre muy por encima de la línea base, así que no depende de acertar el
  valor exacto.
- Con un prior **uniforme** (1/3 cada clase) reproduce exactamente el 59.5%
  viejo: confirmación aritmética de que toda la ganancia viene de la
  corrección de tasa base y de nada más.

Nota operativa: el prior se puede regenerar cuando el corpus crezca
(`python scripts/estimate_sentiment_prior.py`); el script se niega a escribir
con menos de 100 artículos en vez de producir una estimación ruidosa en
silencio. Al pasar de 106 a 162 artículos, `overall_sentiment` subió de 71.4% a
73.8%, así que vale la pena rehacerlo cuando haya más corpus.

`_aggregate_entity` va en la dirección **contraria**: exige corroboración antes
de atribuir una etiqueta polar (≥2 frases de mención que coincidan, o que el
léxico relacional haya apuntado explícitamente a esa entidad). Aplicarle la
corrección de prior del documento lo **empeora** (59.5% → 54.5%), porque su
gold es 71.5% NEU.

**Advertencia honesta sobre `sentiment_toward`: 70.5% NO le gana al benchmark
trivial.** Responder siempre NEU acierta el **71.5%** de las entidades
etiquetadas. Se probaron 12 reglas de gating (margen, confianza mínima,
corroboración) y **ninguna supera ese piso**. El techo es estructural: la
entidad hereda el sentimiento de TODA la frase — en "X criticó la corrupción
del Gobierno" toda entidad presente recibe NEG, incluida la que solo está
mencionada de paso — y un modelo de frase no puede decidir de QUIÉN es el
sentimiento. Superarlo exige atribución por rol sintáctico (que la entidad sea
sujeto/objeto de la predicación polar) o un LLM; ninguna de las dos está
implementada.

Lo que sí mejora, y es la razón de shippear la regla, es la **precisión de lo
que afirma**: las etiquetas polares emitidas sobre entidades cuyo gold es NEU
—es decir, afirmar algo sobre alguien de quien el artículo no opina— bajan de
**48 a 16** (precisión polar 32.9% → 45.2%; polares emitidos 73 → 31).
`docs/planning/task.md` §8.2 liga
precisamente esos juicios a exposición legal bajo Ley 172-13, así que es
reducción de riesgo, no solo una métrica más bonita.

**El "59.9% → 59.5%" del 2026-08-14 nunca fue una regresión.** La accuracy de
`sentiment_toward` solo se puntúa sobre entidades **emparejadas**: en aquella
corrida 51 entidades etiquetadas (20.3%) quedaron fuera del denominador, y los
fixes de ORG añadieron 18 ORGs recién emparejados que diluyeron un numerador
PERSON fijo. Las dos cifras no se calculaban sobre la misma población. Desde
esta medición `scripts/evaluate.py` reporta **ambas** accuracies con sus
denominadores visibles (condicional y end-to-end) y guarda el detalle por
entidad en `per_article`, para que esto no vuelva a leerse mal.

**`dampen_negated` ya no aporta nada medible.** Re-medido en este contexto: con
y sin él, las tres métricas dan **idéntico**, y `odin-db-024`/`odin-db-025`
(los 2 artículos que motivaron la Tarea 4 del plan anterior) siguen prediciendo
NEG con gold NEU en ambos casos. Se deja intacto porque quitarlo sería un
cambio no medido fuera de estos 42 artículos, pero queda anotado como candidato
a eliminación cuando el golden set crezca.

**Línea base de Groq bloqueada (2026-08-13).** Se intentó correr
`scripts/evaluate.py --analyzer groq` contra el mismo golden set de 42
artículos y falló de forma determinística, dos veces, con
`groq.BadRequestError: 400 json_validate_failed` en la salida estructurada
de un artículo (`failed_generation` vino vacío, sin pista de qué falló).
La causa es un hueco en el manejo de errores de `groq_analyzer.py`: su
`_call_groq` solo reintenta el caso de truncado (`finish_reason=length`), no
otros `APIStatusError`, y `evaluate()` no captura fallos por artículo — un
solo artículo con salida inválida tumba la corrida completa de 42 sin
reporte parcial. Esto es deuda técnica en el evaluador/analizador, no un
problema de los datos del golden set (ver `docs/planning/conflicts.md`,
Conflicto 4, "Deuda menor asociada", para el detalle técnico y como
seguimiento pendiente). No hay fila de `groq` en la tabla porque no se
completó ninguna corrida.

Esta tabla se llena corriendo `scripts/evaluate.py --out reporte.json` y
copiando el resultado aquí con fecha, una vez que el golden set tenga tamaño
representativo. El README debe enlazar a esta tabla en vez de mantener sus
propios porcentajes.

## 5. Limitaciones conocidas de la metodología

- El emparejamiento de entidades por contención de substrings puede
  sobreestimar precisión en nombres cortos o muy comunes (p. ej. apellidos
  únicos que coinciden con múltiples personas reales) — mismo riesgo que
  tiene `canonicalize.py` en producción, heredado a propósito para que la
  métrica sea representativa del comportamiento real.
- `sentiment_toward` solo se evalúa sobre entidades ya emparejadas
  correctamente: si el sistema falla en detectar la entidad, ese caso no
  penaliza la métrica de sentimiento — la precisión "hacia una entidad" es
  condicional a haberla detectado, no una medida end-to-end independiente.
- El campo `framing` ya está etiquetado en 34 de 42 artículos del golden set
  y se mide su precisión (ver §4); los demás campos de encuadre
  (`headline_intent`, `lead_orientation`, `source_quality`, `has_hard_data`)
  son **juicios editoriales de un LLM** sin verdad de terreno objetiva
  evidente — el golden set actual no los etiqueta. Para estos últimos, medir
  su precisión requiere una metodología distinta (posiblemente acuerdo
  inter-anotador en vez de una única respuesta "correcta").
