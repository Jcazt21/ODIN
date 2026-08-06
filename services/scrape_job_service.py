"""Lógica de negocio del historial de corridas del pipeline (`crawl_runs`) y
de las corridas del scraper de política encoladas desde la tab "Scraper" del
frontend (§9.2 de task.md).

Arranca una corrida del scraper de política dominicana (pipeline.run() +
analysis.politics_filter) en background y expone su avance para polling —
mismo patrón que POST /api/analyze + GET /api/jobs/{id}, escalado a una
corrida de varios minutos con 9 fuentes. El motor de análisis está
restringido a local|groq|hybrid a nivel de schema (Literal, ver
api/schemas.py::ScrapeJobStartRequest): "gemini" ni siquiera es un valor
aceptable acá, adrede — ver CLAUDE.md.
"""
from __future__ import annotations

import json
import math
import uuid
from collections.abc import Sequence

from fastapi import HTTPException
from pydantic import ValidationError
from sqlalchemy import select

from api import deps
from api.schemas import (
    CrawlRunResponse,
    ScrapeJobAccepted,
    ScrapeJobResponse,
    ScrapeJobStartRequest,
    ScrapeSourceProgress,
)
from db.models import CrawlRun, ScrapeJob
from observability import get_logger
from scrape_jobs import has_active_scrape_job

log = get_logger("odin.api")


def list_crawl_runs(limit: int) -> Sequence[CrawlRun]:
    """Historial de corridas del pipeline, más reciente primero.

    Devuelve las filas ORM tal cual: la conversión a `CrawlRunResponse` la
    hace `response_model=` en la ruta (`api/routers/scrape_jobs.py`), igual
    que el resto de los endpoints de solo lectura."""
    session = deps.get_session()
    try:
        runs = session.scalars(
            select(CrawlRun).order_by(CrawlRun.started_at.desc()).limit(limit)
        ).all()
        return runs
    finally:
        session.close()


def _serialize_scrape_job(job: ScrapeJob) -> ScrapeJobResponse:
    progress_raw = json.loads(job.progress_json) if job.progress_json else {}
    progress: dict[str, ScrapeSourceProgress] = {}
    for k, v in progress_raw.items():
        try:
            progress[k] = ScrapeSourceProgress(**v)
        except ValidationError:
            # Fila de un formato de progress_json anterior (p. ej. de antes de
            # que "source" fuera requerido) — no tumbar el listado entero por
            # una entrada vieja, solo omitirla.
            log.warning("scrape_job_progress_entry_unparseable", job_id=job.id, key=k)
    return ScrapeJobResponse(
        job_id=job.id,
        status=job.status,
        target=job.target,
        per_source_cap=job.per_source_cap,
        analyzer=job.analyzer_name,
        created_at=job.created_at,
        started_at=job.started_at,
        finished_at=job.finished_at,
        progress=progress,
        crawl_run=CrawlRunResponse.model_validate(job.crawl_run) if job.crawl_run else None,
        error=job.error,
    )


def start_scrape_job(req: ScrapeJobStartRequest) -> tuple[ScrapeJobAccepted, tuple]:
    """Encola una corrida del scraper de política sobre las 9 fuentes
    permitidas. Rechaza con 409 si ya hay una en curso — un backend de un
    solo worker no tiene por qué correr dos scrapes de 9 fuentes a la vez.

    Devuelve `(respuesta, args_para_background_task)`: quien llama debe
    encolar `run_scrape_job(*args_para_background_task)`."""
    from scrapers import SCRAPERS

    per_source_cap = req.per_source_cap or math.ceil(req.target / len(SCRAPERS))
    session = deps.get_session()
    try:
        if has_active_scrape_job(session):
            raise HTTPException(status_code=409, detail="Ya hay una corrida de scraping en curso.")
        job = ScrapeJob(
            id=str(uuid.uuid4()),
            target=req.target,
            per_source_cap=per_source_cap,
            analyzer_name=req.analyzer,
        )
        session.add(job)
        session.commit()
        job_id = job.id
    finally:
        session.close()

    return ScrapeJobAccepted(job_id=job_id), (job_id, req.target, per_source_cap, req.analyzer)


def get_scrape_job(job_id: str) -> ScrapeJobResponse:
    """Estado/avance de una corrida encolada por start_scrape_job."""
    session = deps.get_session()
    try:
        job = session.get(ScrapeJob, job_id)
        if job is None:
            raise HTTPException(status_code=404, detail="Job no encontrado.")
        return _serialize_scrape_job(job)
    finally:
        session.close()


def list_scrape_jobs(limit: int) -> list[ScrapeJobResponse]:
    """Corridas recientes, más reciente primero — el frontend la usa al
    montar la tab para detectar un job pending/running y retomar el polling
    en vez de mostrar el formulario (p. ej. tras recargar la página)."""
    session = deps.get_session()
    try:
        jobs = session.scalars(
            select(ScrapeJob).order_by(ScrapeJob.created_at.desc()).limit(limit)
        ).all()
        return [_serialize_scrape_job(j) for j in jobs]
    finally:
        session.close()


def cancel_scrape_job(job_id: str) -> ScrapeJobResponse:
    """Pide cancelar una corrida en curso. Cooperativo, no instantáneo:
    pipeline.run() solo lo consulta entre fuentes y entre artículos, así que
    puede tardar hasta que termine de descargar la fuente actual."""
    session = deps.get_session()
    try:
        job = session.get(ScrapeJob, job_id)
        if job is None:
            raise HTTPException(status_code=404, detail="Job no encontrado.")
        if job.status not in ("pending", "running"):
            raise HTTPException(
                status_code=409, detail=f"El job ya está en estado '{job.status}', no se puede cancelar."
            )
        job.cancel_requested = True
        session.commit()
        return _serialize_scrape_job(job)
    finally:
        session.close()
