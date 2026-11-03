# Política de seguridad

## Reportar una vulnerabilidad

No abras un issue público. Usa **Security → Report a vulnerability** en
[GitHub](https://github.com/Jcazt21/ODIN/security/advisories/new) o escribe
directamente al mantenedor del repositorio.

Incluye qué componente afecta, cómo reproducirlo y el impacto que ves. Se
responde en un plazo razonable y se coordina la corrección antes de divulgar.

## Alcance y datos sensibles

- Las llaves (`GEMINI_API_KEY`, `GROQ_API_KEY`, secreto JWT) viven en `.env`,
  que está en `.gitignore`. Si una llave se llega a commitear, rótala de inmediato.
- Las dependencias se auditan cada semana (`.github/workflows/audit.yml`) y
  Dependabot propone actualizaciones.
