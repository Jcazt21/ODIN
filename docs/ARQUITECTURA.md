# Arquitectura de Odin

> Estilo C4 (contexto → contenedores → componentes). Complementa
> [PROCESOS.md](PROCESOS.md) (el pipeline de 5 pasos) y
> [GUIA_DE_USO.md](GUIA_DE_USO.md) (uso desde la UI). Este documento describe
> **cómo está construido el sistema**, no cómo operarlo (eso es
> [RUNBOOK.md](RUNBOOK.md)) ni cómo se decidieron las piezas no obvias (eso son
> los [ADRs](adr/)).

## 1. Contexto

Odin analiza artículos de prensa dominicana: extrae texto, identifica
entidades (personas, organizaciones, lugares) y su sentimiento, y expone el
resultado en una API y una UI para revisar/corregir antes de guardar.

```
┌──────────────┐        ┌────────────────────────┐        ┌──────────────────┐
│   Usuario    │───────▶│   Frontend (React)     │───────▶│  API (FastAPI)    │
│ (analista de │        │  odin.local / :3000    │        │  api/, :8000       │
│  prensa)     │◀───────│                        │◀───────│                    │
└──────────────┘        └────────────────────────┘        └─────────┬─────────┘
                                                                      │
                          ┌───────────────────────────────────────────┼───────────────┐
                          ▼                                           ▼               ▼
                 ┌─────────────────┐                       ┌──────────────────┐ ┌────────────┐
                 │ Medios digitales │                       │  PostgreSQL /    │ │  Gemini /   │
                 │ (9 fuentes: RD)  │◀── scrapers/base.py ──│  SQLite (db/)    │ │  Groq API   │
                 └─────────────────┘   (solo si el usuario  └──────────────────┘ │ (opt-in,    │
                                        pega una URL o corre                     │  facturado) │
                                        un scrape job)                           └────────────┘
```

El sistema es **a demanda**, no un crawler continuo (decisión de producto,
`task.md` §0.1): no hay cron ni scheduler; cada análisis o corrida masiva la
dispara un usuario o un operador explícitamente.

## 2. Contenedores

| Contenedor | Tecnología | Responsabilidad | Puerto |
|---|---|---|---|
| `backend` | Python 3.13, FastAPI, SQLAlchemy | API HTTP, orquestación de análisis y scraping, migraciones | 8000 |
| `frontend` | React + Vite, servido por nginx | UI de análisis, reportes, gestión de aliases/entidades | 3000→8080 (nginx) |
| `db` | PostgreSQL 17 (o SQLite en dev/tests) | Persistencia de artículos, entidades, jobs | 5433→5432 |
| `scraper` | misma imagen que `backend`, perfil Docker `tools` | CLI de rastreo masivo (`main.py`), no arranca con `docker compose up` por defecto | — |

Los cuatro se definen en [`docker-compose.yml`](../docker-compose.yml).
`backend` y `frontend` tienen `HEALTHCHECK`; `db` y `backend` tienen límites de
CPU/memoria explícitos.

## 3. Componentes del backend

```
api/                    — capa HTTP (FastAPI)
├── __init__.py         — app, lifespan, middleware (CORS, correlation-id, métricas)
├── deps.py             — get_session, log (punto único que parchean los tests)
├── schemas.py          — modelos Pydantic + enums (Sentiment, Framing, HeadlineIntent, ...)
└── routers/
    ├── analyze.py       — POST /api/analyze, GET /api/jobs/{id}
    ├── articles.py      — GET/PUT/DELETE /api/articles, POST /api/articles
    ├── entities.py       — PUT/DELETE /api/entities/{id}
    ├── aliases.py         — CRUD /api/aliases
    ├── canonical_entities.py — GET/PUT /api/canonical-entities, POST .../merge
    ├── scrape_jobs.py     — POST/GET /api/scrape-jobs, /api/crawl-runs
    └── misc.py             — GET /api/health, GET /metrics

auth.py                 — router /api/auth (login JWT, usuario único)

services/                — lógica de negocio (los routers no hablan SQLAlchemy directo)
├── analyzer_registry.py  — instancia única del Analyzer activo del proceso
├── analyze_service.py     — fetch+extract+analyze+arbitraje, jobs de /api/analyze
├── article_service.py      — filtros, búsqueda, guardado/rectificación de artículos
├── entity_service.py        — rectificación/borrado de menciones puntuales
├── canonical_entity_service.py — fusión y edición de la dimensión de entidad
├── scrape_job_service.py     — arranque/cancelación de corridas masivas
└── alias_service.py           — CRUD de siglas con invalidación de caché

analysis/                — Analyzer como Protocol (base.py) + 4 implementaciones
├── base.py               — Protocol Analyzer, AnalysisResult, EntityResult, ANALYSIS_SCHEMA_VERSION
├── local_analyzer.py       — spaCy (NER) + pysentimiento (sentimiento), sin costo
├── gemini_analyzer.py       — LLM, agrega framing/headline_intent/lead_orientation (facturado)
├── groq_analyzer.py          — GroqAnalyzer + HybridAnalyzer (local + Groq solo para encuadre)
├── canonicalize.py             — unifica nombres (siglas, apellido único) antes de persistir
├── text_norm.py                 — norm_key, comparación insensible a acentos
├── entity_arbiter.py             — arbitraje Gemini opcional para PERSON ambiguas
├── politics_filter.py             — filtro temático para el scrape masivo
└── sentiment_lexicon.py            — glosario político que refuerza el sentimiento

scrapers/                — descubrimiento + extracción, un módulo por fuente
├── base.py               — BaseScraper: sitemap/RSS, throttle por dominio, robots.txt, trafilatura
└── do_scrapers.py, diario_libre.py, listin.py — 8 scrapers concretos

pipeline.py              — run(): orquesta scrapers en paralelo, persiste, agrega CrawlRun
scrape_jobs.py            — puente API↔pipeline.run() para corridas masivas en background
main.py                    — CLI (python main.py --source X --analyzer local|gemini|groq|hybrid)

db/
├── models.py             — 7 tablas (ver DATA_DICTIONARY.md)
├── session.py              — engine, init_db() (solo create_all; DDL real va por Alembic)
├── canonical_entities.py    — get_or_create/merge de la dimensión de entidad
└── aliases.py                 — resolución y caché de siglas

alembic/                 — migraciones versionadas (baseline 2026-08-03)
url_guard.py              — anti-SSRF: allowlist + bloqueo de IP privada + límites
observability.py            — structlog, correlation-id, métricas Prometheus, Sentry opt-in
```

### Flujo principal: `POST /api/analyze`

1. `api/routers/analyze.py` valida y encola vía `analyze_service.start_analyze_job`
   (`AnalyzeJob` con `id` UUID, `status=pending`).
2. `BackgroundTasks` corre `run_analyze_job`: `url_guard.fetch_html` (anti-SSRF)
   → `trafilatura.extract` → `analyzer_registry` (motor activo del proceso) →,
   si aplica, `entity_arbiter` para personas ambiguas.
3. El cliente hace polling a `GET /api/jobs/{id}` hasta `status=done|failed`.
4. El usuario revisa el resultado en el frontend y confirma con
   `POST /api/articles`, que corre `canonicalize_entities` antes de persistir.

### Flujo masivo (parcialmente vigente): `POST /api/scrape-jobs`

Existe en el código y es funcional, pero no se ejecuta automáticamente
(sin cron, ver `task.md` §0.1). `scrape_job_service` arranca un
`ScrapeJob`, `scrape_jobs.py` corre `pipeline.run()` en un hilo de fondo con
`analyzer_name` restringido a `local|groq|hybrid` (nunca `gemini`, para no
facturar por volumen), y expone progreso vía `progress_json` y cancelación
cooperativa (`cancel_requested`).

## 4. Selección del analizador

`ODIN_ANALYZER` (env var, default `local`) decide el motor **una sola vez, al
arrancar el proceso**, en `services/analyzer_registry.py` — nunca por la mera
presencia de una API key (ver [ADR-005](adr/0005-seleccion-explicita-de-analizador.md)
y `task.md` §3.2). Un valor inválido falla el arranque en vez de degradar en
silencio. El árbitro de personas ambiguas (`ODIN_GEMINI_ARBITER`) es un
interruptor de costo aparte, apagado por defecto.

Cinco valores válidos: `local` (spaCy+pysentimiento, gratis, sin campos de
encuadre), `gemini` (LLM, facturado), `groq` (LLM, gratis con límites),
`hybrid` (local + Groq solo para entidades/encuadre) y `groq+gemini`
(`analysis/fallback_analyzer.py::GroqWithGeminiFallback` — Groq primero,
Gemini como red de seguridad cuando Groq falla por rate limit o truncado; el
linaje guardado dice cuál de los dos respondió). El rastreo masivo
(`POST /api/scrape-jobs`) restringe el motor a `local`/`groq`/`hybrid` a nivel
de schema — ni `gemini` ni `groq+gemini` son valores aceptados ahí.

## 5. Seguridad

Resumen; detalle en `task.md` §5 y [LEGAL.md](LEGAL.md).

- **Anti-SSRF** (`url_guard.py`): allowlist de dominios + bloqueo de IP no
  pública revalidado en cada redirección + límites de tamaño/puerto/esquema.
  Es la única salida de red de la API hacia URLs de usuario.
- **Auth**: JWT (`auth.py`), usuario único, en todos los endpoints de
  escritura y en `/api/analyze`. Las lecturas (`GET /api/articles`, etc.)
  quedan abiertas por decisión documentada en el README.
- **CORS**: orígenes explícitos vía `ODIN_CORS_ORIGINS`, sin `*`.

## 6. Observabilidad

`observability.py` centraliza logging estructurado (`structlog`, formato
`console` en dev / `json` en prod), un correlation-id por request/corrida
(propagado en el header `X-Correlation-ID` y en `CrawlRun.correlation_id`/
`ScrapeJob.correlation_id`), métricas Prometheus en `GET /metrics`
(`odin_http_*`, `odin_pipeline_*`, `odin_gemini_*`), y Sentry opt-in
(`ODIN_SENTRY_DSN`, solo si se configura).

## 7. Frontend

`frontend/src/pages/` (una página por área: analizar, reportes, entidades,
aliases, scrape, login) sobre `frontend/src/components/` y
`frontend/src/lib/` — `odin-api.ts` (fetch wrapper), `queries/` (TanStack
Query por recurso), `api-types.ts` **generado desde el OpenAPI real**
(`scripts/generate_openapi.py`) en vez de mantenido a mano, lo que elimina la
triplicación de esquemas que señalaba `task.md` §9.2.

## 8. Qué no cubre este documento

- La justificación de por qué se tomaron ciertas decisiones → [ADRs](adr/).
- El significado de cada columna → [DATA_DICTIONARY.md](DATA_DICTIONARY.md).
- Cómo operar el sistema en producción → [RUNBOOK.md](RUNBOOK.md).
- Metodología y resultados de precisión del análisis → [PRECISION.md](PRECISION.md).
