# Auditoría de dependencias — 2026-10-19

Generado por `scripts/dependency_audit.py`. Fuentes: [OSV.dev](https://osv.dev) para Python (`requirements.lock`), `npm audit` (GitHub Advisory DB) para el frontend, y [NVD](https://nvd.nist.gov) para enriquecer severidad CVSS de los CVEs encontrados (con API key).

## Resumen

- **Python** (`requirements.lock`): 0 vulnerabilidad(es) encontradas.
- **Frontend** (`frontend/package-lock.json`): 7 vulnerabilidad(es) encontradas (critical=0, high=7, moderate=0, low=0).
- **Actualizaciones Python directas**: 0 patch/minor, 0 major disponibles.
- **Actualizaciones npm**: 0 patch/minor, 4 major disponibles.
- ✅ **`npm ci` limpio ya resuelve** (se añadió `overrides` en `package.json`; ver sección "Seguimiento" al final). El hallazgo original queda documentado abajo como histórico.

## Vulnerabilidades — Python (requirements.lock)

Sin vulnerabilidades conocidas en OSV.dev para los paquetes bloqueados.

## Vulnerabilidades — Frontend (npm audit)

| Paquete | Severidad | Vía | Fix disponible | Advisory |
|---|---|---|---|---|
| @shadcn/registry (transitiva) | HIGH | fast-glob | sí | — |
| @ts-morph/common (transitiva) | HIGH | fast-glob | sí | — |
| braces (transitiva) | HIGH | braces | sí | [braces vulnerable to stack-exhaustion denial of service through deeply nested pa](https://github.com/advisories/GHSA-vfj7-8cjw-p6xm) |
| fast-glob (transitiva) | HIGH | micromatch | sí | — |
| micromatch (transitiva) | HIGH | braces | sí | — |
| shadcn (directa) | HIGH | @shadcn/registry, fast-glob, ts-morph | sí | — |
| ts-morph (transitiva) | HIGH | @ts-morph/common | sí | — |

> **Ojo con "Fix disponible: sí"**: para estas 7 el único fix que ofrece npm es `npm audit fix --force`, que baja `shadcn` a `1.0.0` (breaking, rompería el proyecto). No hay fix no-destructivo hoy; ver "Próximo paso".

## Hallazgo (histórico, ya resuelto): `npm ci` falla en limpio

Con `frontend/node_modules` ausente, `npm ci` (y `npm install --dry-run`) fallan con `ERESOLVE` — no es una vulnerabilidad, pero rompe cualquier instalación limpia (CI, onboarding, Docker build sin caché):

```
While resolving: openapi-typescript@7.13.0
Found: typescript@6.0.3
node_modules/typescript
  dev typescript@"~6.0.2" from the root project

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
C:\Users\jazar\AppData\Local\npm-cache\_logs\2026-10-19T12_46_07_774Z-eresolve-report.txt
```

Causa: `openapi-typescript@7.13.0` exige `typescript@^5.x` como peer, pero `package.json` fija `typescript: ~6.0.2` y el lockfile ya resolvió `typescript@6.0.3` (probablemente generado con `--legacy-peer-deps` o `--force`). Las opciones eran bajar `typescript` a `^5.x`, esperar una versión de `openapi-typescript` compatible con TS 6, o forzar la resolución. **Se resolvió con `overrides` en `package.json`; ver la sección "Seguimiento".**

## Actualizaciones disponibles — Python (dependencias directas)

| Paquete | Actual (lock) | Última en PyPI | Tipo |
|---|---|---|---|

_20 paquete(s) directos ya están en la última versión._

## Actualizaciones disponibles — Frontend (npm)

| Paquete | Actual (lock) | Wanted (dentro del rango) | Última | Tipo |
|---|---|---|---|---|
| @types/node | 24.13.3 | 24.19.2 | 26.6.5 | major |
| framer-motion | 12.43.0 | 12.43.0 | 14.4.0 | major |
| typescript | 6.0.3 | 6.0.3 | 7.0.2 | major |
| vitest | 4.1.12 | 4.1.12 | 5.0.5 | major |

_0 paquete(s) directos ya están en la última versión._

## Aplicado en este pase

Se aplicaron todas las actualizaciones patch y minor disponibles tanto en Python como en Frontend, resolviendo todas las vulnerabilidades en Python y la gran mayoría en Frontend (incluyendo la CRITICAL de `proxy-addr`). Los cambios quedan listos en el **working tree sin commitear**, a tu criterio:

### Python (`requirements.lock`, vía `uv pip compile --upgrade-package`, sin tocar `requirements.txt`)

| Paquete | Antes | Después | Tipo / Vulnerabilidad |
|---|---|---|---|
| accelerate | 1.14.0 | 1.15.0 | minor / Fix CVE-2026-69112 (HIGH 7.1) |
| alembic | 1.19.1 | 1.20.0 | minor |
| fastapi | 0.141.1 | 0.148.0 | minor |
| google-genai | 2.18.1 | 2.31.0 | minor |
| groq | 1.6.0 | 1.7.0 | minor |
| lxml | 6.1.1 | 6.1.3 | patch |
| mako | 1.3.12 | 1.4.3 | minor / Fix CVE-2026-102991 (MEDIUM 6.5) |
| multidict | 6.7.1 | 6.9.1 | minor / Fix CVE-2026-104874 (MEDIUM 5.3) |
| psycopg2-binary | 2.9.12 | 2.9.13 | patch |
| pyjwt | 2.13.0 | 2.15.1 | minor / Fix 14 CVEs (inc. CRITICAL 9.1 GHSA-ffc3-869f-jxw9) |
| python-dotenv | 1.2.3 | 1.2.4 | patch |
| sentry-sdk | 2.68.0 | 2.72.0 | minor |
| spacy | 3.8.15 | 3.8.16 | patch |
| sqlalchemy | 2.0.52 | 2.1.5 | minor |
| trafilatura | 2.2.0 | 2.3.1 | minor |
| urllib3 | 2.7.0 | 2.8.0 | minor / Fix 3 CVEs (CVE-2026-97687 HIGH 8.1, etc.) |
| uvicorn | 0.52.3 | 0.54.0 | minor |

Cierre transitivo mínimo actualizado: `charset-normalizer` (3.4.9→3.5.2), `dateparser` (1.4.2→1.4.3), `htmldate` (1.10.0→1.11.0), `opentelemetry-api` (1.45.1, nueva). Además, `greenlet` (3.5.4) **salió del lock**: ya no la arrastra `sqlalchemy 2.1`.
Vulnerabilidades restantes en Python: **0** (antes: 40).
Tests Python: la primera corrida (599 passed) fue contra un entorno global que NO tenía instalado el lock nuevo completo; la validación real contra los pines del lock está en "Seguimiento".

---

### Frontend (`frontend/package.json` + `package-lock.json`)

Los bumps se aplicaron primero con `--legacy-peer-deps`; después el lockfile se regeneró con `npm install` normal (ver "Seguimiento").

| Paquete | Antes | Después | Tipo |
|---|---|---|---|
| @base-ui/react | 1.7.0 | 1.9.0 | minor |
| @tanstack/react-query | 5.101.4 | 5.104.4 | minor |
| lucide-react | 1.32.0 | 1.59.0 | minor |
| mx-icons | 1.1.1 | 1.1.2 | patch |
| react | 19.2.8 | 19.3.1 | minor |
| react-dom | 19.2.8 | 19.3.1 | minor |
| react-router-dom | 7.18.2 | 7.18.4 | patch |
| tailwind-merge | 3.6.0 | 3.7.0 | minor |
| @testing-library/dom | 10.4.1 | 10.4.2 | patch |
| @testing-library/jest-dom | 7.0.0 | 7.0.1 | patch |
| @testing-library/react | 16.3.2 | 16.3.3 | patch |
| @testing-library/user-event | 14.6.3 | 14.6.8 | patch |
| @types/react | 19.2.18 | 19.3.0 | minor |
| @types/react-dom | 19.2.4 | 19.3.0 | minor |
| @vitejs/plugin-react | 6.0.5 | 6.1.2 | minor |
| jsdom | 30.0.1 | 30.1.3 | minor |
| oxlint | 1.76.0 | 1.88.0 | minor |
| vite | 8.2.0 | 8.3.4 | minor |

Más `npm audit fix` (corrido con `--legacy-peer-deps`):
- **Eliminada vulnerabilidad CRITICAL**: `proxy-addr` (IP spoofing).
- **Eliminadas 12 vulnerabilidades HIGH y MODERATE**: `undici` (DoS), `fast-uri` (SSRF/host confusion), `brace-expansion`, `js-yaml`, `@modelcontextprotocol/sdk`, `hono`, `ip-address`, `postcss-selector-parser`, `qs`, `@vitest/mocker`.
- Vulnerabilidades restantes en Frontend: **7 high transitivas** en el CLI de `shadcn` ligadas a `braces`/`micromatch`/`fast-glob` (requerirían `npm audit fix --force` que provocaría un downgrade destructivo a `shadcn@1.0.0`).

Validaciones frontend:
- `npx tsc --noEmit` → **0 errores**
- `npm run lint` (`oxlint`) → **0 errores**
- `npm run test` (`vitest run`) → **27 test files passed, 121 passed, 0 failed**.

---

## Seguimiento (mismo día)

- **`npm ci` arreglado**: `frontend/package.json` ahora tiene `"overrides": {"openapi-typescript": {"typescript": "$typescript"}}`, así `openapi-typescript` usa el TS 6 del proyecto. El lockfile se regeneró con `npm install` (sin `--legacy-peer-deps`: el anterior quedaba incompleto, le faltaban los `@emnapi/*`). Verificado: `npm ci --dry-run` sobre una copia limpia → exit 0, sin `ERESOLVE`. Ya no hace falta `--legacy-peer-deps`.
- **Python validado contra el lock nuevo**: venv limpio con Python 3.13 y los pines del lock (`sqlalchemy 2.1.5`, `fastapi 0.148.0`, `alembic 1.20.0`, `pyjwt 2.15.1`, `urllib3 2.8.0`, `uvicorn 0.54.0`, etc.) → `pytest` **599 passed**. El pase anterior corrió contra un entorno global que solo tenía 4 de esos paquetes actualizados.
- Aviso nuevo (no falla): `starlette` depreca `httpx` en su `TestClient` y pide `httpx2`. Revisar cuando `fastapi` lo exija.
- **`mypy src`: 3 errores corregidos** (no los causaban los bumps; salían igual con `sqlalchemy 2.0.52`). `db/topics.py`: se protege `session.get(...)` que puede devolver `None`. `services/article_service.py`: se anota el tipo de `chosen`. `services/topic_service.py`: el label `count` pasa a `total`, porque mypy lee `Row.count` como `tuple.count` (en runtime SQLAlchemy 2.0 ya devolvía la columna, así que no era un bug en producción, solo ambiguo). Se añadió `test_frequency_returns_real_counts_per_topic_and_day` para `/api/topics/frequency`, que no tenía test. Verificado con `sqlalchemy 2.1.5`: `mypy src` limpio y `pytest` exit 0.

## Majors y limpieza (2026-10-19, tras el plan)

Aplicado en el working tree, sin commitear:

- `framer-motion` 12.43.0 → 14.4.0 (solo 2 archivos lo importan).
- `vitest` 4.1.12 → 5.0.5 (exige Node ^22.12 || ^24).
- `@types/node` 24.13.3 → 24.19.2 (se queda en 24.x a propósito: debe coincidir con Node 22/24, no con 26).
- `frontend/Dockerfile`: `node:20-alpine` → `node:22-alpine` y se quitó `--legacy-peer-deps` (ya lo cubre `overrides`).
- `requirements.lock`: cabecera corregida (`-o requirements.lock`, había quedado `scratch_pinned.lock`).

Validación: `tsc --noEmit` (app y node) sin errores; `oxlint` solo con warnings preexistentes; `vitest` 27 files / 121 tests passed; `npm run build` OK; `npm ci --dry-run` en copia limpia → exit 0. No se construyó la imagen Docker ni se revisaron visualmente las animaciones de framer-motion.

## Resolución de lo diferido (2026-10-19)

- **shadcn (7 high) → resuelto, `npm audit` = 0.** El paquete solo aportaba `shadcn/tailwind.css` al build. Se copió a `frontend/vendor/shadcn-tailwind.css` (shadcn 4.22.1, MIT; fuera de `src/` para que `css-tokens.test.ts` no lo escanee), `src/index.css` lo importa desde ahí y se desinstaló `shadcn`. Para añadir componentes: `npx shadcn@latest add <componente>`. Costo: esa hoja ya no se actualiza sola; revisar upstream de vez en cuando.
- **TypeScript 6.0.3 → 7.0.2 → aplicado.** `tsc -b`, lint, 121 tests y build pasan. TS 7 elimina la API JS del compilador y `openapi-typescript` 7.13 se rompe con él (`ts.factory` undefined), así que se sacó de devDependencies, se quitó el `overrides` y `generate:types` ahora corre `npx --yes --legacy-peer-deps -p typescript@6.0.3 -p openapi-typescript@7.13.0 openapi-typescript ...` (aislado con TS 6). Verificado generando contra el esquema actual. El Dockerfile ya no necesita flags.
- `npm ci --dry-run` en copia limpia: exit 0.

## Pendiente

- **`@types/node` 26**: no aplica mientras se use Node 22/24.
- `frontend/src/lib/api-types.ts` está desactualizado respecto al backend (faltan los endpoints `/api/topics/*`); regenerar con `npm run generate:types` cuando se quiera (necesita `PYTHONPATH=src`).
