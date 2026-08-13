"""Lógica de negocio de POST /api/analyze y GET /api/jobs/{id} (§9.2 de
task.md): descarga con protecciones de `url_guard`, extracción con
trafilatura, análisis (con arbitraje opcional de personas ambiguas) y
canonicalización. Separado de la ruta HTTP para poder reutilizarse sin FastAPI
de por medio (CLI, worker) y para no mezclar en un mismo archivo el
transporte y la lógica.
"""
from __future__ import annotations

import json
import uuid
from datetime import UTC, datetime

import requests
import trafilatura
from fastapi import HTTPException
from sqlalchemy import select

from odin.core import url_guard
from odin.analysis.base import ANALYSIS_SCHEMA_VERSION
from odin.analysis.canonicalize import canonicalize_result
from odin.analysis.local_analyzer import sentence_mentions_venue_word
from api import deps
from api.deps import log
from api.schemas import AnalyzePreviewEntity, AnalyzeResult, ArticleDetail
from odin.core.config import settings
from odin.db.models import AnalyzeJob, Article
from odin.scrapers.base import BaseScraper, _parse_date
from services.analyzer_registry import IS_GEMINI_ANALYZER, analyzer
from odin.core.url_guard import UrlNotAllowed

_extractor = BaseScraper()

# Pasos del pipeline de run_analyze_job, en orden — el frontend los muestra
# como progreso durante el polling de GET /api/jobs/{id} (status="running").
ANALYZE_STAGES = ("fetching", "analyzing", "canonicalizing")


def fetch_and_extract(url: str):
    # La URL viene del usuario: se descarga con las protecciones de url_guard
    # (allowlist de dominios, bloqueo de IPs internas, tope de tamaño), no con
    # el fetch del scraper, que confía en las URLs de sus propios sitemaps.
    try:
        html = url_guard.fetch_html(url, session=_extractor.session)
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
    try:
        return analyzer.analyze(title, body)
    except RuntimeError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


def arbitrate_ambiguous_persons(result) -> None:
    """Segundo filtro (pagado, opcional) solo para PERSON cuya oración de
    contexto menciona una palabra de lugar en algún punto — la heurística
    local ya descartó los casos claros; esto cubre lo que queda ambiguo.

    Está APAGADO por defecto: se activa con `ODIN_GEMINI_ARBITER=1`, nunca por
    tener GEMINI_API_KEY en el entorno (antes bastaba con eso y se facturaba sin
    pedirlo). También se salta si el análisis principal ya lo hizo
    GeminiAnalyzer: su prompt ya excluye lugares/homenajes y repetirlo sería
    pagar dos veces. Solo se llama desde /api/analyze, nunca desde el crawl
    (main.py/pipeline.py).

    Todos los casos ambiguos del artículo van en UNA sola llamada a Gemini."""
    if IS_GEMINI_ANALYZER or not settings.gemini_arbiter:
        return

    ambiguous = [
        e
        for e in result.entities
        if e.type == "PERSON" and e.context and sentence_mentions_venue_word(e.context)
    ]
    if not ambiguous:
        return

    from odin.analysis.entity_arbiter import are_person_mentions

    verdicts = are_person_mentions([(e.name, e.context) for e in ambiguous])
    dropped = {id(e) for e, keep in zip(ambiguous, verdicts, strict=True) if not keep}
    result.entities = [e for e in result.entities if id(e) not in dropped]


def run_analyze_job(job_id: str, url: str) -> None:
    """Cuerpo del trabajo encolado por POST /api/analyze: descarga, analiza y
    guarda el resultado en la fila `AnalyzeJob`. Corre en el threadpool de
    `BackgroundTasks`, fuera del ciclo request/response — cualquier excepción
    de aquí NUNCA debe propagarse (no hay a quién devolvérsela), se guarda
    como `error` en el job para que el polling la muestre."""
    session = deps.get_session()
    try:
        job = session.get(AnalyzeJob, job_id)
        if job is None:  # no debería pasar
            return
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
        except Exception as exc:
            log.exception("analyze_job_failed", job_id=job_id, url=url)
            job.status = "failed"
            job.error = str(exc)
        job.finished_at = datetime.now(UTC)
        session.commit()
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


def start_analyze_job(url: str) -> tuple[AnalyzeResult | None, str | None]:
    """Si la URL ya estaba guardada, devuelve `(detalle, None)`. Si es nueva,
    crea la fila `AnalyzeJob` en estado `pending` y devuelve `(None, job_id)`
    — quien llama debe encolar `run_analyze_job(job_id, url)` en background."""
    from services.article_service import serialize_article

    session = deps.get_session()
    try:
        existing = session.scalar(select(Article).where(Article.url == url))
        if existing:
            return _to_analyze_result(serialize_article(existing), already_saved=True), None

        job = AnalyzeJob(id=str(uuid.uuid4()), url=url)
        session.add(job)
        session.commit()
        return None, job.id
    finally:
        session.close()


def get_job(job_id: str):
    from api.schemas import JobResponse

    session = deps.get_session()
    try:
        job = session.get(AnalyzeJob, job_id)
        if job is None:
            raise HTTPException(status_code=404, detail="Job no encontrado.")
        result = AnalyzeResult.model_validate_json(job.result_json) if job.result_json else None
        return JobResponse(job_id=job.id, status=job.status, stage=job.stage, error=job.error, result=result)
    finally:
        session.close()
