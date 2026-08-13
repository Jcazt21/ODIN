"""POST /api/analyze y GET /api/jobs/{id} — flujo de análisis en dos pasos
(§3.1 de task.md): la descarga y el NLP corren en background; el cliente hace
polling del job hasta que `status` sea `done` o `failed`."""
from __future__ import annotations

import json

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Response

from odin.api.schemas import AnalyzeAccepted, AnalyzeRequest, AnalyzeResult, JobResponse
from odin.core import auth, url_guard
from odin.core.url_guard import UrlNotAllowed
from odin.services import analyze_service

router = APIRouter(tags=["analyze"])


@router.post(
    "/api/analyze",
    dependencies=[Depends(auth.require_auth)],
    response_model=AnalyzeResult | AnalyzeAccepted,
    status_code=200,
    responses={202: {"model": AnalyzeAccepted}},
)
def analyze(req: AnalyzeRequest, background_tasks: BackgroundTasks, response: Response):
    """Encola el análisis de la URL (§3.1 de task.md): la descarga y el NLP
    corren en segundo plano en vez de bloquear el request hasta 60s. Si la
    URL ya estaba guardada —o se analizó hace poco, o ya hay un job suyo
    corriendo— no se encola nada nuevo (ver `start_analyze_job`). Si es nueva,
    devuelve `202` + `job_id`; el cliente consulta el resultado con
    GET /api/jobs/{job_id}."""
    # Se valida antes de tocar la BD: una URL que no pasa el guard no debe
    # producir ninguna respuesta distinguible según lo que haya guardado.
    try:
        url = url_guard.validate_url(req.url)
    except UrlNotAllowed as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    started = analyze_service.start_analyze_job(url)
    if started.result is not None:
        return started.result
    assert started.job_id is not None  # invariante: nunca result y job_id a la vez None

    if started.enqueue:
        background_tasks.add_task(analyze_service.run_analyze_job, started.job_id)
    response.status_code = 202
    return AnalyzeAccepted(job_id=started.job_id)


@router.get(
    "/api/jobs/{job_id}",
    dependencies=[Depends(auth.require_auth)],
    response_model=JobResponse,
)
def get_job(job_id: str):
    """Estado/resultado de un job de POST /api/analyze.

    Devuelve el JSON armado a mano en vez de un `JobResponse`: el cliente
    poletea esto cada 1.5s, y el resultado ya está guardado como JSON en la
    fila. Construir el modelo solo para que FastAPI lo vuelva a serializar
    significa parsear y re-serializar el artículo completo (cuerpo incluido)
    en cada poll. `response_model` se mantiene arriba para que el OpenAPI —y
    los tipos que el frontend genera desde él— sigan describiendo la
    respuesta."""
    job = analyze_service.get_job_row(job_id)
    # Todo lo escalar se serializa normalmente; lo único que se inserta crudo
    # es `result_json`, que es JSON que produjo este mismo servicio con
    # `AnalyzeResult.model_dump_json()`.
    head = json.dumps(
        {"job_id": job.id, "status": job.status, "stage": job.stage, "error": job.error},
        ensure_ascii=False,
    )
    payload = f'{head[:-1]},"result":{job.result_json or "null"}}}'
    return Response(content=payload, media_type="application/json")
