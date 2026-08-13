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
`odin.api`, importable como `odin.api:app`) monta la app, el middleware de
observabilidad y los routers. Cada grupo de rutas vive en
`odin/api/routers/`, los schemas Pydantic en `odin/api/schemas.py`, y la
lógica de negocio (queries SQLAlchemy) en `odin/services/` — los handlers
HTTP ya no hablan SQLAlchemy directamente.

Uso:
  uvicorn odin.api:app --reload --port 8000
"""
from __future__ import annotations

import threading
import time
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware

import odin.db.aliases as alias_store
from odin.analysis.local_analyzer import LocalAnalyzer
from odin.api.routers import (
    aliases,
    analyze,
    articles,
    canonical_entities,
    entities,
    misc,
    scrape_jobs,
)
from odin.core import auth
from odin.core.config import settings
from odin.core.observability import (
    HTTP_REQUEST_DURATION_SECONDS,
    HTTP_REQUESTS_TOTAL,
    configure_logging,
    correlation_scope,
    get_logger,
    init_sentry,
)
from odin.db.session import init_db
from odin.services import analyze_service
from odin.services.analyzer_registry import analyzer

configure_logging()
init_sentry()
log = get_logger("odin.api")


def _warm_up_analyzer() -> None:
    """Carga los modelos locales antes del primer request.

    `LocalAnalyzer` los carga de forma perezosa, así que sin esto el primer
    análisis tras cada despliegue paga la carga de spaCy (~1.6s) y de
    pysentimiento (~4.3s) además del análisis en sí. Corre en un hilo aparte
    para no retrasar el arranque del servidor —si llega un request mientras
    tanto, simplemente espera lo mismo que esperaba antes— y solo con los
    motores que de verdad usan spaCy: con `ODIN_ANALYZER=groq`/`gemini` no hay
    nada local que cargar.
    """
    local = getattr(analyzer, "_local", analyzer)
    if not isinstance(local, LocalAnalyzer):
        return

    def _load() -> None:
        try:
            local.nlp("Calentando el modelo.")
            local.sent  # noqa: B018 (la propiedad es la que carga el modelo)
            log.info("analyzer_warmed_up", analyzer=analyzer.name)
        except Exception as exc:
            # Que falle el calentamiento no debe tumbar la API: el primer
            # análisis real volverá a intentarlo y reportará el error a quien
            # lo pidió.
            log.warning("analyzer_warmup_failed", error=str(exc))

    threading.Thread(target=_load, name="odin-warmup", daemon=True).start()


@asynccontextmanager
async def _lifespan(app: FastAPI):
    """Crea tablas, carga el catálogo semilla, repara los jobs que quedaron a
    medias y calienta los modelos."""
    try:
        init_db()
        n = alias_store.load_seed()
        if n:
            log.info("seed_catalog_loaded", aliases=n)
    except Exception as exc:
        log.warning("seed_catalog_load_failed", error=str(exc))
    try:
        # Arrancar es justo el momento en que hay jobs huérfanos: los que
        # estaban corriendo cuando este proceso (o el anterior) se cayó.
        analyze_service.reap_stale_jobs()
    except Exception as exc:
        log.warning("analyze_jobs_reap_failed", error=str(exc))
    _warm_up_analyzer()
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


# El HEALTHCHECK del contenedor (docker-compose.yml, servicio "backend") le
# pega a /api/health cada 10s. Sin esto, cada sonda emite un
# `http_request_finished` que inunda los logs y hace imposible seguir los
# eventos de verdad. Se siguen registrando las métricas Prometheus (el conteo
# de sondas es barato y útil); solo se omite la línea de log — salvo error,
# que sí interesa ver.
_HEALTH_PATH = "/api/health"


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
        # La sonda de salud es puro ruido en los logs (cada 10s): se omite su
        # línea mientras responda bien; un código >= 400 sí se registra.
        if path != _HEALTH_PATH or response.status_code >= 400:
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
