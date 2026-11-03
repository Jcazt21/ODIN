# Odin

## Flujo de Git

No existe un branch `dev`. Cada feature grande va en su propio branch (se
trabaja por planes); los cambios chicos pueden ir directo en el branch actual.
Se pueden hacer commits, **sin líneas de atribución** (nada de
`Co-Authored-By` ni `Claude-Session`). Los PRs van hacia `main`.

## Gemini API

`GEMINI_API_KEY` (o `GOOGLE_API_KEY`) está configurada en `.env` para uso manual
del usuario. **No ejecutar pruebas automatizadas, scripts de verificación ni
llamadas de prueba contra la API de Gemini** (`analysis/gemini_analyzer.py`,
`--analyzer gemini`) por costo — cada llamada consume cuota de pago. Si hace
falta validar cambios en `GeminiAnalyzer`, usar `LocalAnalyzer` o revisar el
código estáticamente; solo llamar a la API real si el usuario lo pide
explícitamente.
