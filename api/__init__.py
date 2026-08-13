"""API REST de Odin (FastAPI).

Flujo en dos pasos:
  1. POST /api/analyze   — si la URL ya estaba guardada, devuelve `200` con
     ese registro directamente (already_saved=true). Si es nueva, encola el
     trabajo (descarga con trafilatura + NLP, §3.1 de task.md) y devuelve
     `202` + `job_id`; GET /api/jobs/{job_id} da el estado/resultado. NO
     guarda: es una vista previa para revisar/corregir en el frontend antes
     de persistir.
  2. POST /api/articles  — recibe el resultado (posiblemente editado por el
     usuario) y lo guarda.

CRUD de siglas: GET/POST /api/aliases, PUT/DELETE /api/aliases/{id}.

Rectificación/borrado (§8.2 de task.md — datos personales y perfilado):
  PUT/DELETE /api/articles/{id}, PUT/DELETE /api/entities/{id}.

Organización del código (tarea 24 de task.md, §9.2): este módulo (paquete
`api/`, importable como `api:app` — `uvicorn api:app` sigue funcionando igual
que cuando era un solo archivo) monta la app, el middleware de observabilidad
y los routers. Cada grupo de rutas vive en `api/routers/`, los schemas
Pydantic en `api/schemas.py`, y la lógica de negocio (queries SQLAlchemy) en
`services/` — los handlers HTTP ya no hablan SQLAlchemy directamente.

Uso:
  uvicorn api:app --reload --port 8000
"""
from __future__ import annotations

import time
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware

from odin.core import auth
import db.aliases as alias_store
from api.routers import (
    aliases,
    analyze,
    articles,
    canonical_entities,
    entities,
    misc,
    scrape_jobs,
)
from odin.core.config import settings
from db.session import init_db
from odin.core.observability import (
    HTTP_REQUEST_DURATION_SECONDS,
    HTTP_REQUESTS_TOTAL,
    configure_logging,
    correlation_scope,
    get_logger,
    init_sentry,
)

configure_logging()
init_sentry()
log = get_logger("odin.api")


@asynccontextmanager
async def _lifespan(app: FastAPI):
    """Crea tablas y carga el catálogo semilla al arrancar."""
    try:
        init_db()
        n = alias_store.load_seed()
        if n:
            log.info("seed_catalog_loaded", aliases=n)
    except Exception as exc:
        log.warning("seed_catalog_load_failed", error=str(exc))
    yield


app = FastAPI(title="Odin API", lifespan=_lifespan)

app.include_router(auth.router)
app.include_router(analyze.router)
app.include_router(articles.router)
app.include_router(entities.router)
app.include_router(aliases.router)
app.include_router(canonical_entities.router)
app.include_router(scrape_jobs.router)
app.include_router(misc.router)


# Rutas parametrizadas (`/api/articles/{article_id}`) colapsan a su plantilla
# para que las métricas no exploten en cardinalidad por cada ID distinto.
def _route_template(request: Request) -> str:
    route = request.scope.get("route")
    return route.path if route is not None else request.url.path


@app.middleware("http")
async def _observability_middleware(request: Request, call_next):
    """Correlation ID + logs estructurados + métricas de latencia/error por
    endpoint (§7.1 de task.md)."""
    with correlation_scope(request.headers.get("x-correlation-id")) as correlation_id:
        started = time.perf_counter()
        try:
            response = await call_next(request)
        except Exception:
            duration = time.perf_counter() - started
            path = _route_template(request)
            HTTP_REQUEST_DURATION_SECONDS.labels(method=request.method, path=path).observe(
                duration
            )
            HTTP_REQUESTS_TOTAL.labels(
                method=request.method, path=path, status_code="500"
            ).inc()
            log.exception(
                "http_request_failed",
                method=request.method,
                path=path,
                duration_seconds=round(duration, 4),
            )
            raise
        duration = time.perf_counter() - started
        path = _route_template(request)
        HTTP_REQUEST_DURATION_SECONDS.labels(method=request.method, path=path).observe(duration)
        HTTP_REQUESTS_TOTAL.labels(
            method=request.method, path=path, status_code=str(response.status_code)
        ).inc()
        log.info(
            "http_request_finished",
            method=request.method,
            path=path,
            status_code=response.status_code,
            duration_seconds=round(duration, 4),
        )
        response.headers["X-Correlation-ID"] = correlation_id
        return response


# Orígenes explícitos (ODIN_CORS_ORIGINS). Nada de "*": la API acepta escrituras
# autenticadas y no tiene por qué ser invocable desde cualquier página.
app.add_middleware(
    CORSMiddleware,
    allow_origins=list(settings.cors_origins),
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type"],
)
