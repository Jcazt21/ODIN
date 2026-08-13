"""Historial de corridas del pipeline (`/api/crawl-runs`) y corridas
encoladas del scraper de política (`/api/scrape-jobs`, tab "Scraper" del
frontend) — mismo patrón que POST /api/analyze + GET /api/jobs/{id}, escalado
a una corrida de varios minutos con 9 fuentes."""
from __future__ import annotations

from fastapi import APIRouter, BackgroundTasks, Depends, Query

from odin.core import auth
from api.schemas import (
    CrawlRunResponse,
    ScrapeJobAccepted,
    ScrapeJobResponse,
    ScrapeJobStartRequest,
)
from odin.core.scrape_jobs import run_scrape_job
from services import scrape_job_service

router = APIRouter(tags=["scrape-jobs"])


@router.get(
    "/api/crawl-runs",
    response_model=list[CrawlRunResponse],
    dependencies=[Depends(auth.require_auth)],
)
def list_crawl_runs(limit: int = Query(20, ge=1, le=200)):
    """Historial de corridas del pipeline, más reciente primero."""
    return scrape_job_service.list_crawl_runs(limit)


@router.post(
    "/api/scrape-jobs",
    dependencies=[Depends(auth.require_auth)],
    response_model=ScrapeJobAccepted,
    status_code=202,
)
def start_scrape_job(req: ScrapeJobStartRequest, background_tasks: BackgroundTasks):
    """Encola una corrida del scraper de política sobre las 9 fuentes
    permitidas. Rechaza con 409 si ya hay una en curso — un backend de un
    solo worker no tiene por qué correr dos scrapes de 9 fuentes a la vez."""
    accepted, job_args = scrape_job_service.start_scrape_job(req)
    background_tasks.add_task(run_scrape_job, *job_args)
    return accepted


@router.get(
    "/api/scrape-jobs/{job_id}",
    dependencies=[Depends(auth.require_auth)],
    response_model=ScrapeJobResponse,
)
def get_scrape_job(job_id: str):
    """Estado/avance de una corrida encolada por POST /api/scrape-jobs."""
    return scrape_job_service.get_scrape_job(job_id)


@router.get(
    "/api/scrape-jobs",
    dependencies=[Depends(auth.require_auth)],
    response_model=list[ScrapeJobResponse],
)
def list_scrape_jobs(limit: int = Query(5, ge=1, le=50)):
    """Corridas recientes, más reciente primero — el frontend la usa al
    montar la tab para detectar un job pending/running y retomar el polling
    en vez de mostrar el formulario (p. ej. tras recargar la página)."""
    return scrape_job_service.list_scrape_jobs(limit)


@router.post(
    "/api/scrape-jobs/{job_id}/cancel",
    dependencies=[Depends(auth.require_auth)],
    response_model=ScrapeJobResponse,
)
def cancel_scrape_job(job_id: str):
    """Pide cancelar una corrida en curso. Cooperativo, no instantáneo:
    pipeline.run() solo lo consulta entre fuentes y entre artículos, así que
    puede tardar hasta que termine de descargar la fuente actual."""
    return scrape_job_service.cancel_scrape_job(job_id)
