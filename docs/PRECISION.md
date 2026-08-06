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

Tests unitarios del evaluador: `tests/test_evaluate.py`.

## 2. Estado actual de la muestra

**7 artículos** en `tests/eval/golden_set.jsonl` a la fecha de este
documento — uno por cada artículo que hoy vive en `odin.db`. El objetivo
fijado en `task.md` §2.4 es **150-300 artículos**, repartidos por fuente y
por sección. Con 7 casos:

- Cualquier métrica calculada tiene un intervalo de confianza demasiado
  ancho para ser accionable (un solo artículo mal clasificado mueve el F1 en
  ~14 puntos).
- No hay representación de las 8 fuentes ni de secciones variadas (política,
  economía, sucesos, etc.) — el rendimiento real puede variar mucho por
  sección (titulares de sucesos vs. columnas de opinión, por ejemplo).
- **No se debe publicar ningún número derivado de esta muestra como cifra de
  producto.** Sirve para verificar que el evaluador funciona end-to-end, no
  para reportar precisión.

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
| _pendiente_ | 7 | — | — | — | — | **No** — muestra insuficiente |

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
- Los campos de encuadre (`framing`, `headline_intent`, `lead_orientation`,
  `source_quality`, `has_hard_data`) son **juicios editoriales de un LLM**
  sin verdad de terreno objetiva evidente — el golden set actual no los
  etiqueta; si se quiere medir su precisión, requiere una metodología
  distinta (posiblemente acuerdo inter-anotador en vez de una única
  respuesta "correcta").
