# Auditoría de dependencias — 2026-08-18

Generado por `scripts/dependency_audit.py`. Fuentes: [OSV.dev](https://osv.dev) para Python (`requirements.lock`), `npm audit` (GitHub Advisory DB) para el frontend, y [NVD](https://nvd.nist.gov) para enriquecer severidad CVSS de los CVEs encontrados (con API key).

## Resumen

- **Python** (`requirements.lock`): 0 vulnerabilidad(es) encontradas.
- **Frontend** (`frontend/package-lock.json`): 0 vulnerabilidad(es) encontradas (critical=0, high=0, moderate=0, low=0).
- **Actualizaciones Python directas**: 0 patch/minor, 0 major disponibles.
- **Actualizaciones npm**: 4 patch/minor, 3 major disponibles.
- ⚠️ **`npm ci` limpio falla** por un conflicto de peer dependencies (ver sección de hallazgos).

## Vulnerabilidades — Python (requirements.lock)

Sin vulnerabilidades conocidas en OSV.dev para los paquetes bloqueados.

## Vulnerabilidades — Frontend (npm audit)

Sin vulnerabilidades reportadas por `npm audit`.

## Hallazgo: `npm ci` falla en limpio

Con `frontend/node_modules` ausente, `npm ci` (y `npm install --dry-run`) fallan con `ERESOLVE` — no es una vulnerabilidad, pero rompe cualquier instalación limpia (CI, onboarding, Docker build sin caché):

```
While resolving: openapi-typescript@7.13.0
Found: typescript@6.0.3
node_modules/typescript
  dev typescript@"~6.0.2" from the root project
  peerOptional typescript@">=4.9.5" from cosmiconfig@9.0.2
  node_modules/cosmiconfig
    cosmiconfig@"^9.0.0" from shadcn@4.18.0
    node_modules/shadcn
      shadcn@"^4.18.0" from the root project

Could not resolve dependency:
peer typescript@"^5.x" from openapi-typescript@7.13.0
node_modules/openapi-typescript
  dev openapi-typescript@"^7.13.0" from the root project

Conflicting peer dependency: typescript@5.9.3
node_modules/typescript
  peer typescript@"^5.x" from openapi-typescript@7.13.0
  node_modules/openapi-typescript
    dev openapi-typescript@"^7.13.0" from the root project

Fix the upstream dependency conflict, or retry
this command with --force or --legacy-peer-deps
to accept an incorrect (and potentially broken) dependency resolution.


For a full report see:
C:\Users\jazar\AppData\Local\npm-cache\_logs\2026-08-18T13_53_06_557Z-eresolve-report.txt
```

Causa: `openapi-typescript@7.13.0` exige `typescript@^5.x` como peer, pero `package.json` fija `typescript: ~6.0.2` y el lockfile ya resolvió `typescript@6.0.3` (probablemente generado con `--legacy-peer-deps` o `--force`). No se tocó nada — requiere decisión: bajar `typescript` a `^5.x`, esperar una versión de `openapi-typescript` compatible con TS 6, o documentar que el equipo debe instalar con `--legacy-peer-deps`.

## Actualizaciones disponibles — Python (dependencias directas)

| Paquete | Actual (lock) | Última en PyPI | Tipo |
|---|---|---|---|

_19 paquete(s) directos ya están en la última versión._

## Actualizaciones disponibles — Frontend (npm)

| Paquete | Actual (lock) | Wanted (dentro del rango) | Última | Tipo |
|---|---|---|---|---|
| @testing-library/jest-dom | 7.0.0 | 7.0.1 | 7.0.1 | patch |
| @testing-library/user-event | 14.6.3 | 14.6.5 | 14.6.5 | patch |
| vite | 8.2.0 | 8.2.1 | 8.2.1 | patch |
| oxlint | 1.76.0 | 1.78.0 | 1.78.0 | minor |
| @types/node | 24.13.3 | 24.13.3 | 26.2.0 | major |
| framer-motion | 12.43.0 | 12.43.0 | 13.1.0 | major |
| typescript | 6.0.3 | 6.0.3 | 7.0.2 | major |

_0 paquete(s) directos ya están en la última versión._

## Aplicado en este pase

Con tu ok, se aplicaron (working tree sin commitear — quedan a tu criterio):

**Python** (`requirements.lock`, vía `uv pip compile --upgrade-package`, sin tocar `requirements.txt`):

| Paquete | Antes | Después | Tipo |
|---|---|---|---|
| python-dotenv | 1.2.2 | 1.2.3 | patch |
| sqlalchemy | 2.0.51 | 2.0.52 | patch |
| uvicorn | 0.52.1 | 0.52.3 | patch |
| spacy | 3.8.14 | 3.8.15 | patch |
| alembic | 1.18.5 | 1.19.1 | minor |
| google-genai | 2.16.0 | 2.18.1 | minor |
| sentry-sdk | 2.66.1 | 2.68.0 | minor |

Ningún otro paquete del lock se movió (diff mínimo, solo estos 7 + su cierre de hashes). Tests: `pytest -q` → **249 passed, 0 failed** (entorno recreado desde cero con `requirements-ci.txt` fijado a las versiones nuevas del lock; los tests de `LocalAnalyzer` que necesitan spaCy/pysentimiento se saltan solos si no están instalados, igual que en CI).

**Frontend** (`frontend/package.json` + `package-lock.json`, instalado con `--legacy-peer-deps` para no verse bloqueado por el conflicto de `typescript` de abajo — no se tocó `typescript` ni `openapi-typescript`):

| Paquete | Antes | Después | Tipo |
|---|---|---|---|
| @base-ui/react | 1.6.0 | 1.7.0 | minor |
| lucide-react | 1.28.0 | 1.32.0 | minor |
| shadcn | 4.16.1 | 4.18.0 | minor |

Más `npm audit fix --legacy-peer-deps`, que resolvió las 3 vulnerabilidades high transitivas (`js-yaml`/`@redocly/openapi-core`/`nanoid`) sin bajar versión de nada directo. Resultado: **0 vulnerabilidades** (antes: 3 high). Tests: `vitest run` → **17 passed (4 test files)**, y `tsc -b` compiló sin errores.

No se tocó el conflicto de peer deps (`typescript ~6.0.2` vs `openapi-typescript` que pide `^5.x`) ni ninguno de los majors — quedan documentados arriba para que decidas.

## Próximo paso

Quedan pendientes de decisión (no se tocaron):

- **Conflicto `npm ci`**: bajar `typescript` a `^5.x` (riesgo: perder features de TS6 que ya use el código), esperar una versión de `openapi-typescript` compatible con TS6, o documentar `--legacy-peer-deps` como forma oficial de instalar.
- **Majors**: `framer-motion` 12→13, `typescript` 6→7, `@types/node` 24→26 (frontend); ninguno en Python por ahora. Revisar changelog antes de subir cada uno — no van en batch.
