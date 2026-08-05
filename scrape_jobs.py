"""Job de background para `POST /api/scrape-jobs`: corre el scraper de
política dominicana (`pipeline.run()` + `analysis.politics_filter`) desde la
API en vez de la terminal, y deja su avance en la fila `ScrapeJob` para que
el frontend haga polling — mismo patrón que `_run_analyze_job` en `api.py`
para `POST /api/analyze`, escalado a una corrida de varios minutos con 9
fuentes en vez de una sola descarga.
"""
from __future__ import annotations

import json
import threading
from datetime import UTC, datetime

from sqlalchemy import select

from analysis.base import Analyzer
from analysis.politics_filter import make_filter
from db.models import CrawlRun, ScrapeJob
from db.session import get_session
from observability import get_logger, new_correlation_id
from scrapers import SCRAPERS

log = get_logger("odin.scrape_jobs")


def _build_analyzer(name: str) -> Analyzer:
    """local | groq | hybrid -> instancia. Nunca acepta "gemini": ese valor
    ni siquiera es válido en el schema del request (Literal en api.py), así
    que este endpoint no puede disparar llamadas facturadas a Gemini — es
    política de costo (CLAUDE.md), no una preferencia de UI a mayores."""
    if name == "groq":
        from analysis.groq_analyzer import GroqAnalyzer

        return GroqAnalyzer()
    if name == "hybrid":
        from analysis.groq_analyzer import HybridAnalyzer

        return HybridAnalyzer()
    from analysis import LocalAnalyzer

    return LocalAnalyzer()


def has_active_scrape_job(session) -> bool:
    """True si ya hay un ScrapeJob pending/running (bloquea encolar otro:
    una corrida de 9 fuentes es pesada, no tiene sentido correr dos a la vez
    en un backend de un solo worker)."""
    return (
        session.scalar(select(ScrapeJob.id).where(ScrapeJob.status.in_(["pending", "running"])))
        is not None
    )


def run_scrape_job(job_id: str, target: int, per_source_cap: int, analyzer_name: str) -> None:
    """Cuerpo del trabajo encolado por POST /api/scrape-jobs. Corre en el
    threadpool de BackgroundTasks, fuera del ciclo request/response —
    cualquier excepción de aquí NUNCA debe propagarse (no hay a quién
    devolvérsela), se guarda como `error` en el job."""
    session = get_session()
    try:
        job = session.get(ScrapeJob, job_id)
        if job is None:  # no debería pasar
            return
        job.status = "running"
        job.started_at = datetime.now(UTC)
        correlation_id = new_correlation_id()
        job.correlation_id = correlation_id
        session.commit()

        # pipeline.run() ahora procesa las 9 fuentes en threads concurrentes
        # (una por dominio) — on_progress/should_stop se van a llamar desde
        # varios de esos threads a la vez, todos sobre el mismo `job`/`session`
        # compartido. `Session` de SQLAlchemy no es thread-safe, así que las
        # dos closures de abajo (la única escritura/lectura compartida de
        # verdad) se serializan con un lock — el trabajo real de cada fuente
        # (su propia sesión, en pipeline.py) sigue corriendo en paralelo.
        lock = threading.Lock()

        def _persist_progress(source_key: str, stage: str, status: str, detail: str) -> None:
            # Clave compuesta "fuente:etapa", no solo "fuente": cada fuente pasa
            # por dos etapas (discover -> analyze) y el frontend necesita poder
            # mostrar ambas subtareas a la vez (p. ej. "descubrimiento: listo" +
            # "análisis: corriendo"). Con una clave por fuente, la segunda
            # actualización pisaría el estado final de la primera etapa.
            with lock:
                progress = json.loads(job.progress_json) if job.progress_json else {}
                progress[f"{source_key}:{stage}"] = {
                    "source": source_key,
                    "stage": stage,
                    "status": status,
                    "detail": detail,
                    "updated_at": datetime.now(UTC).isoformat(),
                }
                job.progress_json = json.dumps(progress)
                session.commit()

        def _should_stop() -> bool:
            with lock:
                session.refresh(job)
                return job.cancel_requested

        analyzer = _build_analyzer(analyzer_name)
        article_filter, _counts = make_filter(target, per_source_cap)

        try:
            from pipeline import run as pipeline_run

            pipeline_run(
                analyzer=analyzer,
                sources=list(SCRAPERS),
                limit=None,
                article_filter=article_filter,
                on_progress=_persist_progress,
                should_stop=_should_stop,
                correlation_id=correlation_id,
            )
            session.refresh(job)  # recoge cancel_requested si se pidió mientras corría
            job.status = "cancelled" if job.cancel_requested else "done"
        except Exception as exc:
            log.exception("scrape_job_failed", job_id=job_id)
            job.status = "failed"
            job.error = str(exc)

        job.crawl_run_id = session.scalar(
            select(CrawlRun.id).where(CrawlRun.correlation_id == correlation_id)
        )
        job.finished_at = datetime.now(UTC)
        session.commit()
    finally:
        session.close()
