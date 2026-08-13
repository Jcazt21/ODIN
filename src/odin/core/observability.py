"""Observabilidad centralizada (§7.1 de task.md): logs estructurados, métricas
Prometheus y seguimiento de errores con Sentry.

Un solo punto de configuración para que `main.py` (CLI) y `api.py` (servidor)
compartan el mismo formato de log y el mismo registro de métricas.

Uso:
    from odin.core.observability import configure_logging, get_logger, init_sentry

    configure_logging()
    log = get_logger("odin.pipeline")
    log.info("crawl_started", source="diario_libre", run_id=run_id)
"""
from __future__ import annotations

import logging
import time
import uuid
from contextlib import contextmanager
from contextvars import ContextVar
from typing import Any

import structlog
from prometheus_client import CollectorRegistry, Counter, Gauge, Histogram

from odin.core.config import settings

# --- Correlation ID ---------------------------------------------------------
# Un ID por request HTTP o por corrida de pipeline, propagado a cada línea de
# log emitida durante esa unidad de trabajo sin tener que pasarlo a mano por
# cada función. `ContextVar` es seguro entre threads/tareas async.
_correlation_id: ContextVar[str | None] = ContextVar("correlation_id", default=None)


def new_correlation_id() -> str:
    return uuid.uuid4().hex[:16]


def get_correlation_id() -> str | None:
    return _correlation_id.get()


@contextmanager
def correlation_scope(correlation_id: str | None = None):
    """Fija el correlation ID activo durante el bloque `with`."""
    cid = correlation_id or new_correlation_id()
    token = _correlation_id.set(cid)
    try:
        yield cid
    finally:
        _correlation_id.reset(token)


def _add_correlation_id(logger: Any, method_name: str, event_dict: dict) -> dict:
    cid = _correlation_id.get()
    if cid is not None:
        event_dict["correlation_id"] = cid
    return event_dict


_configured = False


def configure_logging() -> None:
    """Configura structlog + logging estándar. Idempotente: llamarla varias
    veces (CLI y API pueden compartir proceso en tests) no duplica handlers."""
    global _configured
    if _configured:
        return
    _configured = True

    shared_processors: list[Any] = [
        structlog.contextvars.merge_contextvars,
        _add_correlation_id,
        structlog.processors.add_log_level,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
    ]

    if settings.log_format == "json":
        renderer: Any = structlog.processors.JSONRenderer()
    else:
        renderer = structlog.dev.ConsoleRenderer()

    structlog.configure(
        processors=[*shared_processors, structlog.stdlib.ProcessorFormatter.wrap_for_formatter],
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        cache_logger_on_first_use=True,
    )

    formatter = structlog.stdlib.ProcessorFormatter(
        foreign_pre_chain=shared_processors,
        processors=[
            structlog.stdlib.ProcessorFormatter.remove_processors_meta,
            renderer,
        ],
    )
    handler = logging.StreamHandler()
    handler.setFormatter(formatter)
    root = logging.getLogger()
    root.handlers = [handler]
    root.setLevel(settings.log_level)


def get_logger(name: str) -> structlog.stdlib.BoundLogger:
    return structlog.get_logger(name)


# --- Sentry ------------------------------------------------------------------


def init_sentry() -> None:
    """Inicializa Sentry si ODIN_SENTRY_DSN está configurado. Sin DSN, no hace
    nada: el seguimiento de errores es opt-in, nunca una llamada de red por
    sorpresa en desarrollo."""
    if not settings.sentry_dsn:
        return
    import sentry_sdk

    sentry_sdk.init(
        dsn=settings.sentry_dsn,
        environment=settings.sentry_environment,
        traces_sample_rate=0.0,  # solo errores, sin performance tracing (evita costo/ruido)
    )


# --- Métricas Prometheus -----------------------------------------------------
# Registro propio (no el REGISTRY global por defecto) para que importar este
# módulo varias veces en tests no falle por métricas duplicadas.
registry = CollectorRegistry()

# Pipeline: las métricas que definen si el producto funciona (task.md §7.1).
PIPELINE_ARTICLES_TOTAL = Counter(
    "odin_pipeline_articles_total",
    "Artículos procesados por el pipeline, por fuente y etapa",
    ["source", "stage"],  # stage: discovered | downloaded | analyzed | saved | failed
    registry=registry,
)
PIPELINE_RUN_DURATION_SECONDS = Histogram(
    "odin_pipeline_run_duration_seconds",
    "Duración de una corrida completa del pipeline por fuente",
    ["source"],
    registry=registry,
)
PIPELINE_RUNS_TOTAL = Counter(
    "odin_pipeline_runs_total",
    "Corridas de pipeline finalizadas, por fuente y resultado",
    ["source", "status"],  # status: success | failed
    registry=registry,
)

# API: latencia y tasa de error por endpoint.
HTTP_REQUESTS_TOTAL = Counter(
    "odin_http_requests_total",
    "Peticiones HTTP recibidas, por método, ruta y código de estado",
    ["method", "path", "status_code"],
    registry=registry,
)
HTTP_REQUEST_DURATION_SECONDS = Histogram(
    "odin_http_request_duration_seconds",
    "Latencia de peticiones HTTP, por método y ruta",
    ["method", "path"],
    registry=registry,
)

# Gemini: contador de llamadas y gasto (§7.1 — "crítico dado el modelo de costo").
GEMINI_REQUESTS_TOTAL = Counter(
    "odin_gemini_requests_total",
    "Llamadas a la API de Gemini, por modelo y resultado",
    ["model", "status"],  # status: success | error
    registry=registry,
)
GEMINI_TOKENS_TOTAL = Counter(
    "odin_gemini_tokens_total",
    "Tokens consumidos en llamadas a Gemini, por modelo y tipo",
    ["model", "kind"],  # kind: prompt | output
    registry=registry,
)

CRAWL_RUN_IN_PROGRESS = Gauge(
    "odin_crawl_run_in_progress",
    "1 si hay una corrida de crawl en curso, 0 si no",
    registry=registry,
)


@contextmanager
def time_histogram(histogram: Histogram, **labels: str):
    start = time.perf_counter()
    try:
        yield
    finally:
        histogram.labels(**labels).observe(time.perf_counter() - start)
