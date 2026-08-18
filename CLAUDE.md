# Odin

## Flujo de Git

Trabajar sobre el branch `dev`, no `main`. `dev` es donde vive todo el
trabajo hasta el merge — no crear branches ni worktrees locales para
aislar una tarea a menos que el usuario lo pida explícitamente, o que la
tarea implique un riesgo real para el codebase (cambios grandes o
reversibles con dificultad, refactors amplios, algo que el usuario
querría poder descartar entero sin tocar `dev`). **No hacer commits** — el
usuario los hace manualmente. Dejar los cambios listos en el working tree
(o, si corresponde aislar el trabajo por lo de arriba, en un
worktree/branch) sin commitear, y que el usuario decida cuándo y qué
commitear.

## Gemini API

`GEMINI_API_KEY` (o `GOOGLE_API_KEY`) está configurada en `.env` para uso manual
del usuario. **No ejecutar pruebas automatizadas, scripts de verificación ni
llamadas de prueba contra la API de Gemini** (`analysis/gemini_analyzer.py`,
`--analyzer gemini`) por costo — cada llamada consume cuota de pago. Si hace
falta validar cambios en `GeminiAnalyzer`, usar `LocalAnalyzer` o revisar el
código estáticamente; solo llamar a la API real si el usuario lo pide
explícitamente.
