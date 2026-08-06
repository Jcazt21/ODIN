"""Chequeos de operación: salud de la BD y métricas Prometheus."""
from __future__ import annotations

from fastapi import APIRouter, HTTPException
from fastapi.responses import Response
from prometheus_client import CONTENT_TYPE_LATEST, generate_latest
from sqlalchemy import text

from api import deps
from api.deps import log
from api.schemas import HealthResponse
from observability import registry as metrics_registry

router = APIRouter(tags=["misc"])


@router.get("/api/health", response_model=HealthResponse)
def health():
    """Chequeo real: si la BD no responde, `status` refleja el problema en
    vez de devolver "ok" incondicionalmente (antes lo hacía sin tocar la
    BD; un orquestador lo daría por sano mientras todo falla)."""
    session = deps.get_session()
    try:
        session.execute(text("SELECT 1"))
    except Exception as exc:
        log.warning("health_check_db_unreachable", error=str(exc))
        raise HTTPException(status_code=503, detail="La base de datos no responde.") from exc
    finally:
        session.close()
    return {"status": "ok"}


@router.get("/metrics")
def metrics():
    """Métricas en formato Prometheus (§7.1 de task.md): pipeline, latencia y
    tasa de error por endpoint, llamadas/gasto de Gemini."""
    return Response(generate_latest(metrics_registry), media_type=CONTENT_TYPE_LATEST)
