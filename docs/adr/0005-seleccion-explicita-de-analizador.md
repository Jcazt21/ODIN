# ADR-005: El motor de análisis se decide por configuración explícita, nunca por presencia de credencial

## Status
Accepted (resuelve el hallazgo de `task.md` §3.2)

## Date
2026-08-02

## Context
La versión original decidía el analizador así:

```python
if os.getenv("GEMINI_API_KEY"):
    _analyzer = GeminiAnalyzer()
else:
    _analyzer = LocalAnalyzer()
```

`docker-compose.yml` monta `.env` en `backend`, y `.env` tiene `GEMINI_API_KEY`
definida (para uso manual del usuario, ver `CLAUDE.md`). Resultado:
`docker compose up` arrancaba el backend en modo de pago sin que nadie lo
pidiera — la sola presencia de la llave (guardada ahí por otros motivos: CLI,
árbitro puntual) activaba una llamada facturada por request.

## Decision
Variable de entorno explícita `ODIN_ANALYZER` (`local|gemini|groq|hybrid`,
default `local`), consumida igual por la API (`services/analyzer_registry.py`)
y por el CLI (`main.py`). Un valor inválido lanza `ValueError` al arrancar en
vez de caer a un default silencioso. El árbitro de personas ambiguas
(`ODIN_GEMINI_ARBITER`, otra ruta facturable independiente) requiere su propio
opt-in explícito, apagado por defecto. `GeminiAnalyzer` se importa de forma
perezosa: en modo `local`, `google.genai` ni se importa.

## Alternatives Considered

### Seguir usando la presencia de `GEMINI_API_KEY` como interruptor
- Rejected: "tener la llave configurada" no es lo mismo que "quiero pagar por
  cada análisis" — la llave puede estar ahí solo para el CLI o el árbitro
  puntual. Un secreto nunca debe doblar como flag de comportamiento
  facturable.

### Detectar el motor por variable separada pero con fallback silencioso a `local` en error
- Pros: nunca rompe el arranque.
- Cons: un typo (`ODIN_ANALYZER=gemeni`) pasaría desapercibido y el operador
  creería que está usando Gemini cuando no es así — el error opuesto pero
  igual de peligroso (facturación fantasma o resultados con el motor
  equivocado sin aviso).
- Rejected: preferible fallar rápido y ruidoso al arrancar.

## Consequences
- La presencia de una API key en `.env` deja de tener efecto en qué motor
  corre; hay que declarar `ODIN_ANALYZER=gemini` a propósito.
- Verificado 2026-08-02 con 24 casos de configuración (ver `task.md` §3.2):
  el `.env` real del proyecto —que sí tiene `GEMINI_API_KEY`— arranca en
  `LocalAnalyzer`, `gemini_arbiter=False`, sin importar `google.genai`.
- Al iniciar se registra en el log qué motor se usa, con `WARNING` explícito
  si es uno facturado.
