"""Lógica de negocio de POST /api/analyze y GET /api/jobs/{id} (§9.2 de
task.md): descarga con protecciones de `url_guard`, extracción con
trafilatura, análisis (con arbitraje opcional de personas ambiguas) y
canonicalización. Separado de la ruta HTTP para poder reutilizarse sin FastAPI
de por medio (CLI, worker) y para no mezclar en un mismo archivo el
transporte y la lógica.
"""
from __future__ import annotations

import json
import threading
import time
import uuid
from datetime import UTC, datetime, timedelta
from typing import NamedTuple

import requests
import trafilatura
from fastapi import HTTPException
from sqlalchemy import delete, select

import url_guard
from analysis.base import ANALYSIS_SCHEMA_VERSION
from analysis.canonicalize import canonicalize_result
from analysis.local_analyzer import sentence_mentions_venue_word
from api import deps
from api.deps import log
from api.schemas import AnalyzePreviewEntity, AnalyzeResult, ArticleDetail
from config import settings
from db.models import AnalyzeJob, Article
from observability import (
    ANALYZE_JOB_DURATION_SECONDS,
    ANALYZE_JOBS_TOTAL,
)
from scrapers.base import _parse_date
from services.analyzer_registry import ANALYZER_READS_WHOLE_ARTICLE, analyzer
from url_guard import UrlNotAllowed

# Pasos del pipeline de run_analyze_job, en orden — el frontend los muestra
# como progreso durante el polling de GET /api/jobs/{id} (status="running").
ANALYZE_STAGES = ("fetching", "analyzing", "canonicalizing")

_thread_state = threading.local()


def _http_session() -> requests.Session:
    """Una `requests.Session` por hilo.

    Antes había UNA sola sesión a nivel de módulo (la de un `BaseScraper`)
    compartida por todos los jobs. Los jobs de /api/analyze corren en el
    threadpool de `BackgroundTasks`, así que dos análisis simultáneos usaban la
    misma sesión a la vez, y `requests.Session` no promete ser segura entre
    hilos. Una por hilo mantiene el reuso de conexiones (el threadpool
    recicla sus hilos) sin compartir estado mutable.
    """
    session = getattr(_thread_state, "http_session", None)
    if session is None:
        session = requests.Session()
        session.headers["User-Agent"] = settings.user_agent
        _thread_state.http_session = session
    return session


def fetch_and_extract(url: str):
    # La URL viene del usuario: se descarga con las protecciones de url_guard
    # (allowlist de dominios, bloqueo de IPs internas, tope de tamaño), no con
    # el fetch del scraper, que confía en las URLs de sus propios sitemaps.
    try:
        html = url_guard.fetch_html(url, session=_http_session())
    except UrlNotAllowed as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except requests.RequestException as exc:
        log.warning("fetch_failed", url=url, error=str(exc))
        raise HTTPException(status_code=422, detail="No se pudo descargar la URL.") from exc

    if not html:
        raise HTTPException(status_code=422, detail="No se pudo descargar la URL.")

    data = trafilatura.extract(
        html,
        output_format="json",
        with_metadata=True,
        include_comments=False,
        url=url,
    )
    if not data:
        raise HTTPException(status_code=422, detail="No se pudo extraer el artículo de esa URL.")

    meta = json.loads(data)
    body = (meta.get("text") or "").strip()
    title = (meta.get("title") or "").strip()
    if not body or not title:
        raise HTTPException(status_code=422, detail="La página no parece un artículo (falta título o cuerpo).")

    authors = meta.get("author") or None
    section = None
    cats = meta.get("categories")
    if cats:
        section = cats[0] if isinstance(cats, list) else str(cats)
    published_at = _parse_date(meta.get("date"))

    return {
        "title": title,
        "body": body,
        "authors": authors,
        "section": section,
        "published_at": published_at,
        "sitename": meta.get("sitename"),
    }


def analyze_safely(title: str, body: str):
    """Ejecuta el analizador activo traduciendo cualquier fallo a un mensaje
    presentable.

    `RuntimeError` es el error "esperado" —los analizadores lo usan para lo que
    el usuario sí puede entender: "el servicio de IA está saturado", "no se
    pudo parsear la respuesta"— y su texto va tal cual al UI. Lo que no lo es
    (un error del SDK de Groq/Gemini, un timeout de httpx, un fallo de
    validación) antes también terminaba en pantalla como `str(exc)`: jerga
    inútil para quien pegó un link, y detalle interno de más. Se registra
    completo en el log y al usuario le llega una frase que puede accionar.
    """
    try:
        return analyzer.analyze(title, body)
    except HTTPException:
        raise
    except RuntimeError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    except Exception as exc:
        log.exception("analyzer_failed", analyzer=analyzer.name)
        raise HTTPException(
            status_code=502,
            detail="El servicio de análisis no está disponible en este momento. Intenta de nuevo.",
        ) from exc


def arbitrate_ambiguous_persons(result) -> None:
    """Segundo filtro (pagado, opcional) solo para PERSON cuya oración de
    contexto menciona una palabra de lugar en algún punto — la heurística
    local ya descartó los casos claros; esto cubre lo que queda ambiguo.

    Está APAGADO por defecto: se activa con `ODIN_GEMINI_ARBITER=1`, nunca por
    tener GEMINI_API_KEY en el entorno (antes bastaba con eso y se facturaba sin
    pedirlo). Solo se llama desde /api/analyze, nunca desde el crawl
    (main.py/pipeline.py).

    Se salta con CUALQUIER motor LLM, no solo con Gemini: el prompt que
    comparten Gemini y Groq ya excluye los nombres que solo bautizan un lugar o
    reciben un homenaje, así que preguntarlo de nuevo es pagar dos veces por la
    misma decisión. Antes el guard miraba solo `ODIN_ANALYZER=gemini`, de modo
    que con `groq`/`hybrid`/`groq+gemini` el árbitro sí corría — y encima sobre
    un `context` que en esos motores es una cita de 12 palabras más la razón
    entre corchetes, no la oración completa: el chequeo de palabras de lugar
    sobre ese texto dispara casi al azar.

    Todos los casos ambiguos del artículo van en UNA sola llamada a Gemini."""
    if ANALYZER_READS_WHOLE_ARTICLE or not settings.gemini_arbiter:
        return

    ambiguous = [
        e
        for e in result.entities
        if e.type == "PERSON" and e.context and sentence_mentions_venue_word(e.context)
    ]
    if not ambiguous:
        return

    from analysis.entity_arbiter import are_person_mentions

    verdicts = are_person_mentions([(e.name, e.context) for e in ambiguous])
    dropped = {id(e) for e, keep in zip(ambiguous, verdicts, strict=True) if not keep}
    result.entities = [e for e in result.entities if id(e) not in dropped]


def run_analyze_job(job_id: str) -> None:
    """Cuerpo del trabajo encolado por POST /api/analyze: descarga, analiza y
    guarda el resultado en la fila `AnalyzeJob`. Corre en el threadpool de
    `BackgroundTasks`, fuera del ciclo request/response — cualquier excepción
    de aquí NUNCA debe propagarse (no hay a quién devolvérsela), se guarda
    como `error` en el job para que el polling la muestre.

    La URL se lee de la fila, no se recibe por parámetro: es la ya
    canonicalizada por `start_analyze_job`, y pasarla aparte abría la puerta a
    analizar una URL distinta de la que quedó registrada en el job."""
    session = deps.get_session()
    started = time.perf_counter()
    try:
        job = session.get(AnalyzeJob, job_id)
        if job is None:  # no debería pasar
            return
        url = job.url
        job.status = "running"
        job.stage = "fetching"
        job.started_at = datetime.now(UTC)
        session.commit()

        try:
            extracted = fetch_and_extract(url)

            job.stage = "analyzing"
            session.commit()
            result = analyze_safely(extracted["title"], extracted["body"])
            arbitrate_ambiguous_persons(result)

            job.stage = "canonicalizing"
            session.commit()
            canonicalize_result(result)

            detail = AnalyzeResult(
                already_saved=False,
                source=extracted.get("sitename") or "manual",
                url=url,
                title=extracted["title"],
                authors=extracted["authors"],
                section=extracted["section"],
                published_at=extracted["published_at"],
                body=extracted["body"],
                main_topic=result.main_topic,
                topic_keywords=", ".join(result.topic_keywords) or None,
                overall_sentiment=result.overall_sentiment,
                sentiment_score=result.sentiment_score,
                framing=result.framing,
                headline_intent=result.headline_intent,
                lead_orientation=result.lead_orientation,
                dominant_actor=result.dominant_actor,
                source_quality=result.source_quality,
                has_hard_data=result.has_hard_data,
                blamed_actor=result.blamed_actor,
                credited_actor=result.credited_actor,
                sentiment_basis=result.sentiment_basis,
                facts_sentiment=result.facts_sentiment,
                quoted_sentiment=result.quoted_sentiment,
                media_stance=result.media_stance,
                media_stance_evidence=result.media_stance_evidence,
                overall_sentiment_reason=result.overall_sentiment_reason,
                content_flags=", ".join(result.content_flags) or None,
                analyzer_name=analyzer.name,
                analyzer_model=analyzer.model,
                analyzer_version=analyzer.version,
                analysis_schema_version=ANALYSIS_SCHEMA_VERSION,
                analyzed_at=datetime.now(UTC),
                entities=[AnalyzePreviewEntity.model_validate(e) for e in result.entities],
            )
            job.status = "done"
            job.result_json = detail.model_dump_json()
        except HTTPException as exc:
            job.status = "failed"
            job.error = str(exc.detail)
        except Exception:
            # Detalle completo al log; al usuario, algo que pueda leer. Antes
            # el `str(exc)` de cualquier excepción interna se mostraba tal cual
            # en el UI.
            log.exception("analyze_job_failed", job_id=job_id, url=url)
            job.status = "failed"
            job.error = "El análisis falló por un error interno. Intenta de nuevo."
        job.stage = None  # solo tiene sentido mientras el job corre
        job.finished_at = datetime.now(UTC)
        session.commit()
        ANALYZE_JOBS_TOTAL.labels(status=job.status).inc()
        ANALYZE_JOB_DURATION_SECONDS.labels(status=job.status).observe(
            time.perf_counter() - started
        )
    finally:
        session.close()


def _to_analyze_result(detail: ArticleDetail, *, already_saved: bool) -> AnalyzeResult:
    """Adapta el schema de artículo guardado (`ArticleDetail`, de
    `article_service.serialize_article`) al de vista previa de /api/analyze
    (`AnalyzeResult`): mismos campos, distinta clase porque son casos de uso
    distintos (ver comentario en api/schemas.py)."""
    return AnalyzeResult(
        already_saved=already_saved,
        entities=[AnalyzePreviewEntity(**e.model_dump()) for e in detail.entities],
        **detail.model_dump(exclude={"entities"}),
    )


class StartedAnalysis(NamedTuple):
    """Qué hacer tras `start_analyze_job`.

    Tres desenlaces, y el tercero es la razón de que esto no sea una tupla
    suelta: puede haber un `job_id` que NO hay que encolar, porque ya lo está
    corriendo otro request."""

    result: AnalyzeResult | None  # respuesta inmediata: no hay nada que encolar
    job_id: str | None
    enqueue: bool = False


def start_analyze_job(url: str) -> StartedAnalysis:
    """Decide si hay que analizar la URL o si ya existe una respuesta.

    En orden, del más barato al más caro:

      1. el artículo ya está guardado -> se devuelve tal cual;
      2. la misma URL se analizó hace poco y no se guardó -> se reusa ese
         resultado en vez de volver a llamar al LLM (ver
         `ODIN_ANALYZE_REUSE_MINUTES`);
      3. hay un job de esa URL corriendo ahora mismo -> se devuelve SU id para
         que este cliente haga polling del mismo trabajo, sin lanzar un
         segundo análisis en paralelo;
      4. nada de lo anterior -> se crea el job y quien llama lo encola.

    Los pasos 2 y 3 son los que evitan pagar (o gastar rate limit) dos veces
    por el mismo artículo: sin ellos, dos clics seguidos en "Analizar", o dos
    usuarios con el mismo link, disparaban dos análisis completos.
    """
    from services.article_service import serialize_article

    canonical = url_guard.canonical_url(url)
    session = deps.get_session()
    try:
        # Las dos formas de la URL: las notas guardadas antes de que existiera
        # la canonicalización están con la URL tal como llegó.
        existing = session.scalar(
            select(Article).where(Article.url.in_({url, canonical}))
        )
        if existing:
            return StartedAnalysis(
                _to_analyze_result(serialize_article(existing), already_saved=True), None
            )

        now = datetime.now(UTC)
        if settings.analyze_reuse_minutes > 0:
            reusable = session.scalar(
                select(AnalyzeJob)
                .where(
                    AnalyzeJob.url == canonical,
                    AnalyzeJob.status == "done",
                    AnalyzeJob.result_json.is_not(None),
                    AnalyzeJob.created_at
                    >= now - timedelta(minutes=settings.analyze_reuse_minutes),
                )
                .order_by(AnalyzeJob.created_at.desc())
            )
            if reusable is not None and reusable.result_json:
                log.info("analyze_result_reused", url=canonical, job_id=reusable.id)
                ANALYZE_JOBS_TOTAL.labels(status="reused").inc()
                return StartedAnalysis(
                    AnalyzeResult.model_validate_json(reusable.result_json), None
                )

        in_flight = session.scalar(
            select(AnalyzeJob)
            .where(
                AnalyzeJob.url == canonical,
                AnalyzeJob.status.in_(("pending", "running")),
                # Un job más viejo que esto está colgado (ver reap_stale_jobs):
                # engancharse a él dejaría al cliente esperando para siempre.
                AnalyzeJob.created_at
                >= now - timedelta(minutes=settings.analyze_job_stale_minutes),
            )
            .order_by(AnalyzeJob.created_at.desc())
        )
        if in_flight is not None:
            log.info("analyze_job_joined", url=canonical, job_id=in_flight.id)
            return StartedAnalysis(None, in_flight.id, enqueue=False)

        job = AnalyzeJob(id=str(uuid.uuid4()), url=canonical)
        session.add(job)
        session.commit()
        return StartedAnalysis(None, job.id, enqueue=True)
    finally:
        session.close()


def get_job_row(job_id: str) -> AnalyzeJob:
    """La fila del job, o 404. Se devuelve la fila y no un schema para que el
    router pueda entregar `result_json` tal cual, sin parsearlo (ver
    `api/routers/analyze.py`)."""
    session = deps.get_session()
    try:
        job = session.get(AnalyzeJob, job_id)
        if job is None:
            raise HTTPException(status_code=404, detail="Job no encontrado.")
        session.expunge(job)
        return job
    finally:
        session.close()


def get_job(job_id: str):
    """Versión tipada de `get_job_row`, para quien necesite el objeto ya
    validado (tests, un cliente Python) en vez del JSON crudo."""
    from api.schemas import JobResponse

    job = get_job_row(job_id)
    result = AnalyzeResult.model_validate_json(job.result_json) if job.result_json else None
    return JobResponse(
        job_id=job.id, status=job.status, stage=job.stage, error=job.error, result=result
    )


def reap_stale_jobs() -> int:
    """Marca como fallidos los jobs que quedaron a medias y borra los viejos.

    `BackgroundTasks` vive en la memoria del proceso: si el servidor se
    reinicia con un análisis en curso, la fila se queda en `running` para
    siempre y el cliente hace polling hasta rendirse por su propio timeout.
    Esto se ejecuta al arrancar (ver el lifespan en `api/__init__.py`), que es
    justo cuando esos jobs quedaron huérfanos.

    Aprovecha el mismo barrido para podar los terminados: `result_json` guarda
    el cuerpo completo del artículo, así que la tabla crece sin techo si nadie
    la limpia. Devuelve cuántas filas tocó, entre reparadas y borradas.
    """
    now = datetime.now(UTC)
    session = deps.get_session()
    try:
        stale = session.scalars(
            select(AnalyzeJob).where(
                AnalyzeJob.status.in_(("pending", "running")),
                AnalyzeJob.created_at
                <= now - timedelta(minutes=settings.analyze_job_stale_minutes),
            )
        ).all()
        for job in stale:
            job.status = "failed"
            job.stage = None
            job.error = "El análisis se interrumpió. Vuelve a intentarlo."
            job.finished_at = now
            ANALYZE_JOBS_TOTAL.labels(status="reaped").inc()

        purged = 0
        if settings.analyze_job_ttl_hours > 0:
            purged = session.execute(
                delete(AnalyzeJob)
                .where(
                    AnalyzeJob.status.in_(("done", "failed")),
                    AnalyzeJob.created_at
                    <= now - timedelta(hours=settings.analyze_job_ttl_hours),
                )
                # Sin sincronizar la sesión: es un DELETE masivo y justo arriba
                # se marcaron filas como `failed`, así que la sincronización por
                # defecto ("evaluate") intentaría reevaluar el filtro de fechas
                # en Python contra esos objetos. La sesión se cierra enseguida.
                .execution_options(synchronize_session=False)
            ).rowcount  # type: ignore[attr-defined]  # DELETE siempre devuelve CursorResult
        session.commit()
        if stale or purged:
            log.info("analyze_jobs_reaped", interrupted=len(stale), purged=purged)
        return len(stale) + purged
    finally:
        session.close()
