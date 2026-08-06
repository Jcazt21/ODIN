"""Pipeline principal: scrape -> analizar -> guardar.

Orquesta los scrapers y el analizador, y persiste todo en la base de datos.
Evita duplicados por URL (no re-analiza artículos ya guardados).
"""
from __future__ import annotations

import json
import time
import traceback
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from datetime import UTC, datetime

from sqlalchemy import select

import db.canonical_entities as canonical_entity_store
from analysis.base import ANALYSIS_SCHEMA_VERSION, Analyzer
from analysis.canonicalize import canonicalize_result, known_person_fullname_map
from db.models import Article, CanonicalEntity, CrawlRun, Entity
from db.session import get_session, init_db
from observability import (
    CRAWL_RUN_IN_PROGRESS,
    PIPELINE_ARTICLES_TOTAL,
    PIPELINE_RUN_DURATION_SECONDS,
    PIPELINE_RUNS_TOTAL,
    correlation_scope,
    get_logger,
)
from scrapers import SCRAPERS
from scrapers.base import BaseScraper, ScrapedArticle

log = get_logger("odin.pipeline")


@dataclass
class _SourceResult:
    """Lo que devuelve `_process_source` al thread principal, que agrega
    esto en `stats`/`discovered_total`/etc. — la única escritura de ese
    estado compartido, ya no hay que protegerla con locks."""

    key: str
    discovered: int
    new_count: int
    failed: int
    cancelled: bool


def _already_stored(session, url: str) -> bool:
    return session.scalar(select(Article.id).where(Article.url == url)) is not None


def _persist(
    session,
    scraped: ScrapedArticle,
    result,
    analyzer: Analyzer,
    person_map: dict[str, str] | None = None,
) -> Article:
    # Unifica nombres antes de guardar ("Abinader" -> "Luis Abinader",
    # "MINERD" -> nombre completo) para no crear entidades duplicadas.
    canonicalize_result(result, person_map=person_map)

    article = Article(
        source=scraped.source,
        url=scraped.url,
        title=scraped.title,
        authors=scraped.authors,
        section=scraped.section,
        published_at=scraped.published_at,
        body=scraped.body,
        main_topic=result.main_topic,
        topic_keywords=", ".join(result.topic_keywords) or None,
        overall_sentiment=result.overall_sentiment,
        sentiment_score=result.sentiment_score,
        framing=result.framing,
        headline_intent=result.headline_intent,
        lead_orientation=result.lead_orientation,
        source_quality=result.source_quality,
        has_hard_data=result.has_hard_data,
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
    )
    canonical_by_name: dict[str, CanonicalEntity] = {}
    for e in result.entities:
        canonical = canonical_entity_store.get_or_create(session, e.name, e.type)
        canonical_by_name[e.name] = canonical
        article.entities.append(
            Entity(
                name=e.name,
                type=e.type,
                mentions_count=e.mentions_count,
                sentiment_toward=e.sentiment_toward,
                sentiment_score=e.sentiment_score,
                context=e.context,
                extraction_confidence=e.extraction_confidence,
                canonical_entity=canonical,
            )
        )
    article.dominant_actor_id = canonical_entity_store.resolve_actor_id(
        result.dominant_actor, canonical_by_name
    )
    article.blamed_actor_id = canonical_entity_store.resolve_actor_id(
        result.blamed_actor, canonical_by_name
    )
    article.credited_actor_id = canonical_entity_store.resolve_actor_id(
        result.credited_actor, canonical_by_name
    )
    session.add(article)
    session.commit()
    return article


def run(
    analyzer: Analyzer,
    sources: list[str] | None = None,
    limit: int | None = None,
    article_filter: Callable[[ScrapedArticle], bool] | None = None,
    on_progress: Callable[[str, str, str, str], None] | None = None,
    should_stop: Callable[[], bool] | None = None,
    correlation_id: str | None = None,
) -> dict[str, int]:
    """Ejecuta el pipeline. Devuelve conteo de artículos nuevos por fuente.

    Cada corrida queda registrada en `crawl_runs` (§7.1 de task.md): antes el
    resumen solo se imprimía por consola y se perdía. El `correlation_id` de
    la fila es el mismo que decora cada línea de log de la corrida, para
    poder cruzar logs y BD. Si se pasa `correlation_id`, se usa ese en vez de
    generar uno nuevo — para que un caller externo (p. ej. un job de la API)
    pueda ubicar después la fila `crawl_runs` que produjo esta corrida.

    `article_filter`, si se pasa, decide qué artículos ya descubiertos (y no
    guardados aún) se analizan y persisten — p. ej. para acotar una corrida a
    una temática o imponer un tope por fuente (ver `scripts/scrape_politics.py`).
    No afecta el descubrimiento ni el fetch: eso lo sigue gobernando `limit`.

    `on_progress(source, stage, status, detail)`, si se pasa, se llama en los
    puntos de transición de cada fuente — `stage` es `"discover"` o
    `"analyze"`, `status` es `"running"`/`"done"`/`"cancelled"`. Pensado para
    que un caller
    externo espeje el avance en algo consultable (p. ej. `scrape_jobs.py`
    para el polling de la UI); un error del callback nunca debe tumbar la
    corrida, así que se atrapa y se loguea.

    `should_stop()`, si se pasa, se consulta entre fuentes y entre artículos
    dentro de una fuente para cancelación cooperativa: si devuelve `True`, la
    corrida corta ahí (sin tocar las fuentes que faltan) y `crawl_runs.status`
    queda en `"cancelled"`. Un error del callback se trata como `False` (nunca
    cancela una corrida por accidente).
    """
    init_db()

    def _report(source: str, stage: str, status: str, detail: str) -> None:
        if on_progress is None:
            return
        try:
            on_progress(source, stage, status, detail)
        except Exception:
            log.warning("progress_callback_failed", source=source, stage=stage)

    def _stopped() -> bool:
        if should_stop is None:
            return False
        try:
            return should_stop()
        except Exception:
            log.warning("should_stop_callback_failed")
            return False

    if sources:
        selected = {s: SCRAPERS[s] for s in sources if s in SCRAPERS}
    else:
        selected = dict(SCRAPERS)

    with correlation_scope(correlation_id) as run_id:
        run_started = time.perf_counter()
        crawl_run_session = get_session()
        crawl_run = CrawlRun(
            correlation_id=run_id,
            sources=", ".join(selected.keys()),
            analyzer_name=analyzer.name,
        )
        crawl_run_session.add(crawl_run)
        crawl_run_session.commit()
        crawl_run_id = crawl_run.id
        crawl_run_session.close()
        CRAWL_RUN_IN_PROGRESS.set(1)

        # Una sola consulta para todo el run (antes: una por fuente, repetida
        # 9 veces) — el mapa resultante es de solo lectura, seguro de
        # compartir entre los threads de _process_source de abajo.
        person_map = known_person_fullname_map()

        stats: dict[str, int] = {}
        discovered_total = 0
        saved_total = 0
        failed_total = 0
        cancelled = False

        def _process_source(key: str, scraper_cls: type[BaseScraper]) -> _SourceResult:
            """Descubre, filtra, analiza y guarda UNA fuente, con su propia
            sesión de BD (SQLAlchemy `Session` no es thread-safe: cada
            llamada concurrente necesita la suya). Nunca deja escapar una
            excepción — una fuente rota se reporta como fallida y no tumba
            las demás, que es justo el punto de aislarlas en tareas separadas."""
            try:
                with correlation_scope(run_id):
                    session = get_session()
                    try:
                        scraper: BaseScraper = scraper_cls()
                        log.info("crawl_source_started", source=scraper.name)
                        _report(key, "discover", "running", "Descargando listado de artículos...")
                        source_started = time.perf_counter()
                        new_count = 0
                        source_failed = 0
                        source_cancelled = False

                        scraped_articles = list(
                            scraper.scrape(limit=limit, should_stop=_stopped)
                        )
                        PIPELINE_ARTICLES_TOTAL.labels(source=key, stage="discovered").inc(
                            len(scraped_articles)
                        )

                        if _stopped():
                            # Cortó durante la descarga de ESTA fuente (scrape()
                            # ya dejó de bajar URLs por su propio chequeo de
                            # should_stop): no tiene sentido analizar/guardar lo
                            # poco que se alcanzó a juntar, cancelar es "ahora".
                            _report(
                                key, "discover", "cancelled", f"{len(scraped_articles)} encontrados"
                            )
                            _report(key, "analyze", "cancelled", "0 nuevos, 0 fallidos")
                            return _SourceResult(key, len(scraped_articles), 0, 0, True)

                        pending = [
                            a
                            for a in scraped_articles
                            if not _already_stored(session, a.url)
                            and (article_filter is None or article_filter(a))
                        ]
                        log.info(
                            "crawl_source_scraped",
                            source=scraper.name,
                            scraped=len(scraped_articles),
                            pending_to_analyze=len(pending),
                            skipped=len(scraped_articles) - len(pending),
                        )
                        _report(
                            key,
                            "discover",
                            "done",
                            f"{len(scraped_articles)} encontrados, "
                            f"{len(pending)} pendientes de analizar",
                        )

                        # Si el analizador soporta lote (LocalAnalyzer), una sola
                        # pasada de spaCy sobre todos los artículos de la fuente
                        # es más eficiente que analizar uno por uno. Si el lote
                        # falla, se cae a analizar artículo por artículo para no
                        # perder toda la fuente por un solo texto malo.
                        _report(key, "analyze", "running", f"Analizando {len(pending)} artículos...")
                        results: list | None = None
                        analyze_batch = getattr(analyzer, "analyze_batch", None)
                        if analyze_batch is not None and pending:
                            try:
                                results = analyze_batch(
                                    [(a.title, a.body or "") for a in pending]
                                )
                            except Exception:
                                log.exception("batch_analysis_failed", source=scraper.name)
                                results = None
                        if results is None:
                            results = [None] * len(pending)

                        for scraped, result in zip(pending, results, strict=True):
                            if _stopped():
                                source_cancelled = True
                                break
                            try:
                                if result is None:
                                    result = analyzer.analyze(scraped.title, scraped.body or "")
                                PIPELINE_ARTICLES_TOTAL.labels(source=key, stage="analyzed").inc()
                                _persist(session, scraped, result, analyzer, person_map=person_map)
                                PIPELINE_ARTICLES_TOTAL.labels(source=key, stage="saved").inc()
                                new_count += 1
                                log.info(
                                    "article_saved", source=scraper.source, title=scraped.title[:70]
                                )
                            except Exception:  # no dejar que un artículo tumbe la fuente
                                session.rollback()
                                PIPELINE_ARTICLES_TOTAL.labels(source=key, stage="failed").inc()
                                source_failed += 1
                                log.exception("article_processing_failed", url=scraped.url)

                        PIPELINE_RUN_DURATION_SECONDS.labels(source=key).observe(
                            time.perf_counter() - source_started
                        )
                        log.info("crawl_source_finished", source=scraper.name, new_articles=new_count)
                        _report(
                            key,
                            "analyze",
                            "cancelled" if source_cancelled else "done",
                            f"{new_count} nuevos, {source_failed} fallidos",
                        )
                        return _SourceResult(
                            key, len(scraped_articles), new_count, source_failed, source_cancelled
                        )
                    finally:
                        session.close()
            except Exception:
                log.exception("source_processing_failed", source=key)
                _report(key, "discover", "failed", "Error inesperado procesando la fuente")
                return _SourceResult(key, 0, 0, 1, False)

        try:
            # Cada fuente es un dominio distinto: _DomainThrottle
            # (scrapers/base.py) ya limita la tasa POR DOMINIO, así que
            # correrlas concurrentemente no le pega más fuerte a ningún sitio
            # individual — solo deja de esperar a que termine una para recién
            # arrancar la siguiente (antes: secuencial, ~suma de los tiempos
            # de las 9; ahora: ~el máximo de las 9).
            with ThreadPoolExecutor(max_workers=max(1, len(selected))) as pool:
                futures = {
                    pool.submit(_process_source, key, scraper_cls): key
                    for key, scraper_cls in selected.items()
                }
                for future in as_completed(futures):
                    result = future.result()
                    stats[result.key] = result.new_count
                    discovered_total += result.discovered
                    saved_total += result.new_count
                    failed_total += result.failed
                    if result.cancelled:
                        cancelled = True
        except Exception:
            _finish_crawl_run(
                crawl_run_id,
                status="failed",
                discovered=discovered_total,
                saved=saved_total,
                failed=failed_total,
                stats_by_source=stats,
                error=traceback.format_exc(),
            )
            PIPELINE_RUNS_TOTAL.labels(source=",".join(selected.keys()), status="failed").inc()
            raise
        else:
            final_status = "cancelled" if cancelled else "success"
            _finish_crawl_run(
                crawl_run_id,
                status=final_status,
                discovered=discovered_total,
                saved=saved_total,
                failed=failed_total,
                stats_by_source=stats,
            )
            PIPELINE_RUNS_TOTAL.labels(source=",".join(selected.keys()), status=final_status).inc()
        finally:
            CRAWL_RUN_IN_PROGRESS.set(0)
            log.info(
                "crawl_run_finished",
                duration_seconds=round(time.perf_counter() - run_started, 2),
                articles_saved=saved_total,
                articles_failed=failed_total,
            )
        return stats


def _finish_crawl_run(
    crawl_run_id: int,
    *,
    status: str,
    discovered: int,
    saved: int,
    failed: int,
    stats_by_source: dict[str, int],
    error: str | None = None,
) -> None:
    session = get_session()
    try:
        crawl_run = session.get(CrawlRun, crawl_run_id)
        if crawl_run is None:  # no debería pasar; no tumbar la corrida por esto
            return
        crawl_run.finished_at = datetime.now(UTC)
        crawl_run.status = status
        crawl_run.articles_discovered = discovered
        crawl_run.articles_saved = saved
        crawl_run.articles_failed = failed
        crawl_run.stats_by_source = json.dumps(stats_by_source)
        crawl_run.error = error
        session.commit()
    finally:
        session.close()
