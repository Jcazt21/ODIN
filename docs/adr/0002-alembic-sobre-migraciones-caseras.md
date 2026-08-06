# ADR-002: Alembic en lugar de `_add_missing_columns` casero

## Status
Accepted (reemplaza el mecanismo descrito en el "Diagnóstico original" de
`task.md` §3.4)

## Date
2026-08-03

## Context
El esquema original evolucionaba con una función (`_add_missing_columns` en
`db/session.py`) que inspeccionaba las tablas con SQLAlchemy `inspect()` y
ejecutaba `ALTER TABLE ADD COLUMN` por interpolación de strings, automáticamente
al arrancar la app. Solo sabía agregar columnas nullables: no renombraba, no
borraba, no cambiaba tipos, no hacía backfill, no era reversible y no dejaba
constancia de en qué versión de esquema estaba una base de datos dada.

El primer cambio de esquema no trivial (§4.1: pasar de string crudo a FK hacia
una dimensión `CanonicalEntity`) no podía implementarse con ese mecanismo.

## Decision
Adoptar Alembic. Se aplicó `alembic stamp head` sobre el esquema existente el
2026-08-03 (con la BD en 7 filas, el momento más barato posible para migrar),
y desde entonces todo cambio de esquema es una migración versionada en
`alembic/versions/`. `db/session.py::init_db()` se redujo a `create_all`
idempotente (solo crea tablas que no existen; nunca altera columnas de tablas
existentes).

## Alternatives Considered

### Mantener `_add_missing_columns` y extenderlo a más operaciones
- Pros: cero dependencia nueva.
- Cons: reimplementar rename/drop/type-change/backfill de forma segura es,
  en esencia, reimplementar Alembic peor.
- Rejected.

### Migraciones SQL a mano sin herramienta (carpeta `migrations/001.sql`, ...)
- Pros: sin dependencia de Python, portable a cualquier motor.
- Cons: sin autogenerate, sin downgrade automático, sin tracking de versión
  aplicada por entorno — hay que reconstruir a mano lo que Alembic ya resuelve.
- Rejected.

## Consequences
- Todo cambio de esquema pasa por `alembic revision --autogenerate` +
  revisión humana antes de `alembic upgrade head`. Ya no hay DDL automático
  al arrancar la app en producción.
- Cada entorno (dev/CI/prod) puede consultar su versión de esquema
  (`alembic current`) — elimina la ambigüedad "¿en qué estado está esta BD?"
  que señalaba `task.md` §3.4.
- Las 8 migraciones existentes en `alembic/versions/` (baseline +
  scrape_jobs + crawl_runs + ampliación de analyzer_version + linaje del
  análisis + canonical_entities + FKs de actores + analyze_jobs) son el
  registro histórico de la evolución del esquema — no se reescriben, solo se
  agregan nuevas.
