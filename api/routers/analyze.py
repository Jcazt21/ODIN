"""POST /api/analyze y GET /api/jobs/{id} — flujo de análisis en dos pasos
(§3.1 de task.md): la descarga y el NLP corren en background; el cliente hace
polling del job hasta que `status` sea `done` o `failed`."""
from __future__ import annotations

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Response

import auth
import url_guard
from api.schemas import AnalyzeAccepted, AnalyzeRequest, ArticleDetail, JobResponse
from services import analyze_service
from url_guard import UrlNotAllowed

router = APIRouter(tags=["analyze"])


@router.post(
    "/api/analyze",
    dependencies=[Depends(auth.require_auth)],
    response_model=ArticleDetail | AnalyzeAccepted,
    status_code=200,
    responses={202: {"model": AnalyzeAccepted}},
)
def analyze(req: AnalyzeRequest, background_tasks: BackgroundTasks, response: Response):
    """Encola el análisis de la URL (§3.1 de task.md): la descarga y el NLP
    corren en segundo plano en vez de bloquear el request hasta 60s. Si la
    URL ya estaba guardada, devuelve `200` con el registro directamente (no
    hay nada que encolar). Si es nueva, devuelve `202` + `job_id`; el cliente
    consulta el resultado con GET /api/jobs/{job_id}."""
    # Se valida antes de tocar la BD: una URL que no pasa el guard no debe
    # producir ninguna respuesta distinguible según lo que haya guardado.
    try:
        url = url_guard.validate_url(req.url)
    except UrlNotAllowed as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    existing, job_id = analyze_service.start_analyze_job(url)
    if existing is not None:
        return existing

    background_tasks.add_task(analyze_service.run_analyze_job, job_id, url)
    response.status_code = 202
    return AnalyzeAccepted(job_id=job_id)


@router.get(
    "/api/jobs/{job_id}",
    dependencies=[Depends(auth.require_auth)],
    response_model=JobResponse,
)
def get_job(job_id: str):
    """Estado/resultado de un job de POST /api/analyze."""
    return analyze_service.get_job(job_id)
