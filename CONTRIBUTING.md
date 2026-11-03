# Contribuir a Odin

## Entorno local

```bash
python3.13 -m venv .venv && source .venv/bin/activate
make install              # pip install -e ".[dev]" + pre-commit install
make frontend-install     # npm ci (Node 22, ver frontend/.nvmrc)
```

Más detalle (base de datos, `.env`, Docker) en el [README](README.md#instalación).

## Antes de abrir un PR

```bash
make check    # ruff, mypy, pytest, oxlint, vitest y build del frontend
```

Es exactamente lo que corre el CI (`.github/workflows/ci.yml`). Si tocas
endpoints o schemas de la API, regenera los tipos del frontend con
`npm run generate:types` (en `frontend/`).

El CI no instala spaCy ni pysentimiento (varios GB), así que los tests de
`test_local_analyzer` y `test_local_places` se saltan allí. Córrelos en local
con el entorno completo si tocas `analysis/`.

## Flujo de ramas

Trunk-based: no hay rama `dev`.

1. Crea una rama desde `main` (`feat/…`, `fix/…`, `chore/…`, `docs/…`).
2. Commits con [Conventional Commits](https://www.conventionalcommits.org/) en español (`feat(frontend): …`).
3. Abre un PR hacia `main`. Debe pasar el CI (`backend` y `frontend`).
4. Merge con squash; la rama se borra al fusionar.

## Qué tests escribir

Pocos y que valgan la pena: lógica de dominio (canonicalización, sentimiento,
parsing de scrapers), contratos de la API y regresiones de bugs reales. Evita
tests que solo verifican estilos, markup trivial o mocks.

**Nunca** llames a la API de Gemini desde tests o scripts de verificación
(cuesta dinero); usa `LocalAnalyzer`.

## Configuración de GitHub (una vez, por el administrador)

- Settings → Branches → proteger `main`: PR obligatorio, status checks
  `backend` y `frontend` requeridos, sin force-push.
- Settings → General → activar "Automatically delete head branches".
- Settings → Code security → activar Dependabot alerts.
- Borrar ramas remotas ya fusionadas (`plan/crud-temas`, `upgrade/entities`).
