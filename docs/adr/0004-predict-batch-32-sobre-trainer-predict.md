# ADR-004: `_predict_batch` en lotes de 32 en lugar de `Trainer.predict()` de pysentimiento

## Status
Accepted

## Date
2026-08-03 (auditoría de rendimiento de pysentimiento citada en `task.md` §2.9)

## Context
`LocalAnalyzer` (`analysis/local_analyzer.py`) calcula sentimiento por frase
para cada artículo. La forma directa de usar `pysentimiento` es llamar a
`self.sent.predict(lista_de_frases)`, que internamente arma un
`datasets.Dataset` y un `DataLoader` de HuggingFace `Trainer` por cada
llamada — pensado para evaluar corpora completos offline, no para inferencia
repetida artículo por artículo dentro de un proceso de larga vida.

## Decision
Reemplazar `self.sent.predict()` por tokenización manual + forward pass en
lotes de tamaño fijo `_SENT_BATCH_SIZE = 32` (`_predict_batch`,
`analysis/local_analyzer.py`), el mismo tamaño de lote con el que
`pysentimiento` carga el modelo por defecto.

## Alternatives Considered

### Seguir usando `Trainer.predict()` por artículo
- Pros: cero código propio, mantenimiento nulo.
- Cons: medido ~500x más lento que pasar la lista completa a `predict()` en
  CPU/MPS para lotes chicos (el tamaño típico de frases por artículo), por el
  overhead de construir `Dataset`+`DataLoader` en cada llamada.
- Rejected: inaceptable para un endpoint que hoy corre síncronamente dentro
  del ciclo request/response (`task.md` §3.1).

### `Trainer.predict()` una sola vez sobre todas las frases del artículo
- Pros: más simple que tokenización manual, evita N llamadas.
- Cons: sigue pagando el overhead de `Dataset`/`DataLoader` una vez por
  artículo; medido ~7-8x más lento por frase que `_predict_batch`.
- Rejected como insuficiente, aunque mejor que la opción anterior.

## Consequences
- ~7-8x más rápido por frase que la mejor alternativa con `Trainer.predict()`,
  ~500x más rápido que el loop ingenuo original — verificado bit-a-bit
  idéntico (mismo `preprocess_tweet` + softmax sobre los mismos logits).
- El caché de deduplicación de frases sigue acotado a un solo artículo
  (`dict.fromkeys` local a `analyze()`); extenderlo entre artículos de la
  misma fuente queda como optimización pendiente y de bajo riesgo
  (`task.md` §2.9), no aplicada a propósito hasta tener telemetría real de
  cuánto texto se repite entre artículos.
