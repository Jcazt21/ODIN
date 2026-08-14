# Odin

## Flujo de Git

Trabajar sobre el branch `dev`, no `main`. **No hacer commits** — el
usuario los hace manualmente. Dejar los cambios listos en el working tree
(o, si se pidió explícitamente aislar el trabajo, en un worktree/branch)
sin commitear, y que el usuario decida cuándo y qué commitear.

## Gemini API

`GEMINI_API_KEY` (o `GOOGLE_API_KEY`) está configurada en `.env` para uso manual
del usuario. **No ejecutar pruebas automatizadas, scripts de verificación ni
llamadas de prueba contra la API de Gemini** (`analysis/gemini_analyzer.py`,
`--analyzer gemini`) por costo — cada llamada consume cuota de pago. Si hace
falta validar cambios en `GeminiAnalyzer`, usar `LocalAnalyzer` o revisar el
código estáticamente; solo llamar a la API real si el usuario lo pide
explícitamente.
