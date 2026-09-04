# Estructura del proyecto

Mapa completo de directorios y archivos del backend. Para la vista de
arquitectura (contexto, contenedores, componentes) ver
[ARQUITECTURA.md](ARQUITECTURA.md); esto es solo "qué hay dónde".

## Por qué `src/odin/`

Todo el backend Python vive bajo un único paquete instalable, `odin`, dentro
de `src/`. Es el layout estándar (`src/<paquete>/`) en vez de tener el
paquete suelto en la raíz del repo: obliga a que el código se importe
siempre desde el paquete instalado (`pip install -e .`), nunca por accidente
vía el directorio de trabajo — el bug clásico del layout plano, donde un
import roto solo se nota si alguien corre las pruebas desde otra carpeta.

## Árbol completo

```
src/odin/
├── __init__.py
├── core/                     módulos base — CLI, configuración, entrada/salida del proceso
│   ├── config.py               configuración por variables de entorno (.env)
│   ├── auth.py                 login de usuario único + JWT
│   ├── url_guard.py            anti-SSRF: allowlist + bloqueo de IP privada
│   ├── observability.py        logging estructurado, correlation-id, métricas Prometheus, Sentry
│   ├── main.py                 punto de entrada del CLI (expuesto como el comando `odin`)
│   ├── pipeline.py             orquesta: descubrir -> descargar -> analizar -> guardar
│   ├── scrape_jobs.py           puente API↔pipeline.run() para corridas encoladas desde el frontend
│   └── report.py               consultas rápidas de resultados en consola
│
├── api/                       API HTTP (FastAPI) — el camino principal: analizar / guardar / listar
│   ├── __init__.py              app, middleware (CORS, correlation-id, métricas), monta los routers
│   ├── schemas.py                requests/respuestas Pydantic (fuente de los tipos TS del frontend)
│   ├── deps.py                   dependencias compartidas (sesión de BD)
│   └── routers/                  un módulo por grupo de rutas
│       ├── analyze.py              POST /api/analyze, GET /api/jobs/{id}
│       ├── articles.py             CRUD de artículos guardados
│       ├── entities.py             rectificación/borrado de menciones
│       ├── aliases.py              CRUD de siglas
│       ├── canonical_entities.py   entidades canónicas (dimensión persona/organización)
│       ├── scrape_jobs.py          estado del rastreo masivo
│       └── misc.py                 health / métricas Prometheus
│
├── services/                  lógica de negocio (SQLAlchemy) detrás de cada router
│   ├── analyzer_registry.py     instancia única del Analyzer activo del proceso
│   ├── analyze_service.py        POST /api/analyze + dedup/reuso de análisis recientes
│   ├── article_service.py        listado, detalle, rectificación, borrado de artículos
│   ├── entity_service.py         rectificación de menciones individuales
│   ├── canonical_entity_service.py  entidades canónicas: listado, fusión
│   ├── alias_service.py          CRUD de siglas
│   └── scrape_job_service.py     estado y arranque de corridas de rastreo
│
├── scrapers/                  descarga y extracción por medio
│   ├── base.py                  BaseScraper: reintentos, throttle por dominio, robots.txt
│   ├── do_scrapers.py            7 de las 9 fuentes dominicanas (descubrimiento por RSS/sitemap)
│   └── diario_libre.py, listin.py   las otras 2
│
├── analysis/                  motor de NLP/sentimiento — piezas intercambiables detrás de `Analyzer`
│   ├── base.py                   interfaz Analyzer + AnalysisResult
│   ├── local_analyzer.py         spaCy (NER) + pysentimiento — por defecto, gratis
│   ├── gemini_analyzer.py        Google Gemini (opcional, de pago)
│   ├── groq_analyzer.py          Groq: GroqAnalyzer + HybridAnalyzer (gratis, con límites)
│   ├── fallback_analyzer.py      GroqWithGeminiFallback: Groq primero, Gemini como red de seguridad
│   ├── entity_verify.py          contraste de entidades del LLM contra el texto real
│   ├── entity_arbiter.py         desambiguación puntual de personas (llamada extra a Gemini)
│   ├── canonicalize.py           unificación de nombres de entidades
│   ├── sentiment_lexicon.py      glosario de refuerzo de sentimiento
│   └── text_norm.py              normalización de texto (acentos, mayúsculas)
│
└── db/
    ├── models.py                 tablas — ver DATA_DICTIONARY.md
    ├── session.py                 conexión (SQLite / PostgreSQL / SQL Server)
    ├── canonical_entities.py, aliases.py   dimensión de entidad y resolución de siglas
    └── seed_aliases.py            catálogo semilla de siglas

tests/                        espejo de src/odin/ — un subdirectorio por paquete
├── conftest.py                 fixtures compartidas (SQLite en memoria, api_client, etc.)
├── core/                       pipeline, url_guard, canonicalización de URLs
├── analysis/                   canonicalize, local_analyzer, sentiment_lexicon, entity_verify,
│                                mapeo de respuestas LLM
├── api/                        endpoints /api/analyze, /api/jobs, filtros, rectificación
├── db/                         aliases, entidades canónicas
├── scrapers/                   parsers puros de scrapers/base.py
├── services/                   guardas del árbitro de entidades
├── scripts/                    scripts/evaluate.py (evaluación contra el golden set)
├── test_quick_wins.py           grab-bag de pruebas puntuales, no encaja en un solo paquete
└── eval/                       golden_set.jsonl + README.md, usados por scripts/evaluate.py

scripts/                      CLIs de mantenimiento — NO forman parte del paquete instalable
                               (hash de contraseña, fusión de entidades duplicadas, evaluación,
                               generación del schema OpenAPI, checkpoint de docs desactualizados)

alembic/                      migraciones versionadas del esquema (sin moverse en la migración)

docs/
├── ESTRUCTURA.md               este archivo
├── ARQUITECTURA.md             vista C4 (contexto, contenedores, componentes)
├── PROCESOS.md                 cada proceso del pipeline paso a paso, con diagramas
├── DATA_DICTIONARY.md          cada columna de cada tabla: significado, quién la produce
├── RUNBOOK.md                  operación: fuente caída, jobs, migraciones, backups
├── GUIA_DE_USO.md              guía paso a paso para el usuario final
├── docker.md                   cómo funciona la dockerización (servicios, cache, comandos)
├── scrapers_nuevas_fuentes.md  cómo agregar un scraper nuevo
├── EXPORT_DOCX.md              diseño del .docx de reportes: cuadro de ficha, estilos, plantilla
├── LEGAL.md, PRECISION.md      ToS por medio / metodología de evaluación
├── adr/                        decisiones arquitectónicas (por qué se eligió cada cosa)
├── planning/                   task.md, conflicts.md, deploy-test.md — documentos de trabajo
└── design_handoff_odin_redesign/   spec de diseño del frontend (referenciada por el código, no build)

frontend/                     SPA React + Vite + React Query, proyecto npm independiente
```

## Puntos de entrada

| Comando | Qué hace |
|---|---|
| `odin` | CLI de rastreo masivo → `odin.core.main:main` (console script, ver `pyproject.toml`) |
| `uvicorn odin.api:app` | Levanta la API FastAPI |
| `python -m odin.core.report` | Consultas rápidas de resultados en consola |
| `pytest` | Corre la suite completa (`tests/`) |
| `docker compose up` | Levanta `db` + `backend` + `frontend` |
| `docker compose --profile tools run --rm scraper odin` | Corre el rastreo dentro de un contenedor |

## Dónde mirar para qué

| Necesito... | Ver |
|---|---|
| Entender el flujo completo del sistema (contexto/contenedores/componentes) | [ARQUITECTURA.md](ARQUITECTURA.md) |
| Cada paso del pipeline de análisis, con diagramas | [PROCESOS.md](PROCESOS.md) |
| Qué significa cada columna de cada tabla | [DATA_DICTIONARY.md](DATA_DICTIONARY.md) |
| Instalar y usar Odin paso a paso | [GUIA_DE_USO.md](GUIA_DE_USO.md) |
| Cómo están armadas las imágenes Docker | [docker.md](docker.md) |
| Agregar un periódico/medio nuevo | [scrapers_nuevas_fuentes.md](scrapers_nuevas_fuentes.md) |
| Operar en producción (fuente caída, jobs colgados, backups) | [RUNBOOK.md](RUNBOOK.md) |
| Por qué se eligió tal librería o enfoque | [adr/](adr/) |

## Nota histórica

El proyecto vivió antes como un layout plano: los módulos y paquetes
(`analysis/`, `api/`, `db/`, `services/`, `scrapers/`, más los módulos
sueltos como `main.py`/`config.py`) estaban directamente en la raíz del
repo, mezclados con `tests/`, `scripts/`, `docs/` y los archivos de
configuración. Se migró a `src/odin/` para separar claramente el paquete
instalable del resto del repositorio — mismo código, misma lógica, solo
reubicado y con sus imports actualizados.
