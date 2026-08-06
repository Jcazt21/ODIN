# ADR-003: `thinking_budget=0` en `GeminiAnalyzer`

## Status
Accepted

## Date
2026-08-05 (decisión tomada al implementar `GeminiAnalyzer`; formalizada
retroactivamente)

## Context
`GeminiAnalyzer` (`analysis/gemini_analyzer.py`) pide a un modelo Gemini que
extraiga entidades, sentimiento y campos de encuadre (framing, headline_intent,
lead_orientation, source_quality, has_hard_data, actores) en un esquema JSON
fijo. Los modelos Gemini 2.5+ soportan un modo "thinking" que consume tokens
adicionales (facturados) para razonar antes de responder.

## Decision
Configurar `thinking_budget=0` (desactivar el modo thinking) para las llamadas
de `GeminiAnalyzer`, y usar `gemini-3.5-flash` en vez de `gemini-3.5-pro`
(cuyo `thinking_budget` mínimo es 128, no permite desactivarlo).

## Alternatives Considered

### Dejar el thinking budget por defecto del modelo
- Pros: potencialmente mejor calidad de razonamiento en casos ambiguos.
- Cons: para extracción estructurada contra un esquema fijo (no es una tarea
  de razonamiento abierto), el thinking no mejora medible mente la salida pero
  puede duplicar o triplicar el costo por llamada.
- Rejected: el control de costo del LLM es un requisito de producto explícito
  (`CLAUDE.md`, `task.md` §1 — "alguien pensó en la factura"), y aquí no compra
  calidad a cambio.

### Usar `gemini-3.5-pro` para mejor calidad
- Pros: modelo más capaz.
- Cons: no permite `thinking_budget=0` (mínimo 128) y es más caro por token.
- Rejected para el flujo por defecto; queda como opción manual si el usuario
  la pide explícitamente para un caso puntual.

## Consequences
- Costo por análisis predecible y menor que el default del modelo.
- Si en el futuro se observa que casos ambiguos concretos (p. ej. sarcasmo,
  ironía editorial) requieren razonamiento adicional, esta decisión debe
  revisarse con evidencia del golden set (ver [PRECISION.md](../PRECISION.md))
  antes de subir el budget — no a ciegas.
