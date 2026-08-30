"""Catálogo de documentalistas y su KPI."""
from __future__ import annotations

from fastapi import APIRouter, Depends

from odin.api.schemas import (
    DocumentalistCreated,
    DocumentalistKpiRow,
    DocumentalistPayload,
    DocumentalistResponse,
    DocumentalistUpdatePayload,
)
from odin.core import auth
from odin.services import documentalist_kpi_service, user_service

router = APIRouter(tags=["documentalists"])


@router.get(
    "/api/documentalists",
    dependencies=[Depends(auth.require_auth)],
    response_model=list[DocumentalistResponse],
)
def list_documentalists(include_inactive: bool = True):
    """Documentalistas registrados. Cualquier usuario autenticado puede verlos: son
    los valores del filtro de reportes."""
    return user_service.list_documentalists(include_inactive)


@router.post(
    "/api/documentalists",
    status_code=201,
    dependencies=[Depends(auth.require_admin)],
    response_model=DocumentalistCreated,
)
def create_documentalist(payload: DocumentalistPayload):
    """Da de alta a alguien con un PIN de primer acceso, devuelto una sola vez."""
    return user_service.create_documentalist(payload)


@router.post(
    "/api/documentalists/{documentalist_id}/pin",
    dependencies=[Depends(auth.require_admin)],
    response_model=DocumentalistCreated,
)
def reset_pin(documentalist_id: int):
    """Genera un PIN nuevo de primer acceso. Devuelve el PIN una sola vez."""
    return user_service.reset_pin(documentalist_id)


# Nota para quien añada GET /api/documentalists/kpi: FastAPI resuelve las rutas en el
# orden en que se registran, así que un GET con un segmento fijo como "kpi"
# tiene que quedar declarado ANTES de cualquier GET "/api/documentalists/{documentalist_id}"
# que se agregue a futuro — si no, ese GET paramétrico capturaría "kpi" como si
# fuera un `documentalist_id` y la ruta de KPI nunca se alcanzaría. El PUT de abajo no
# corre este riesgo (distinto método HTTP), pero un futuro GET por id sí.


@router.get(
    "/api/documentalists/kpi",
    dependencies=[Depends(auth.require_admin)],
    response_model=list[DocumentalistKpiRow],
)
def documentalist_kpi(date_from: str | None = None, date_to: str | None = None):
    """Trabajo por documentalista en el rango indicado. Solo admin: son datos de
    evaluación, no de operación."""
    return documentalist_kpi_service.documentalist_kpi(date_from, date_to)


@router.put(
    "/api/documentalists/{documentalist_id}",
    dependencies=[Depends(auth.require_admin)],
    response_model=DocumentalistResponse,
)
def update_documentalist(documentalist_id: int, payload: DocumentalistUpdatePayload):
    """Renombra, cambia el rol, resetea la contraseña o da de baja."""
    return user_service.update_documentalist(documentalist_id, payload)
