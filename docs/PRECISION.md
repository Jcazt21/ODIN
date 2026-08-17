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
