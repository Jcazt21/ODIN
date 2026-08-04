"""Pipeline principal: scrape -> analizar -> guardar.

Orquesta los scrapers y el analizador, y persiste todo en la base de datos.
Evita duplicados por URL (no re-analiza artículos ya guardados).
"""
from __future__ import annotations

import logging
from datetime import UTC, datetime

from sqlalchemy import select

import db.canonical_entities as canonical_entity_store
from analysis.base import ANALYSIS_SCHEMA_VERSION, Analyzer
from analysis.canonicalize import canonicalize_result, known_person_fullname_map
from db.models import Article, CanonicalEntity, Entity
from db.session import get_session, init_db
from scrapers import SCRAPERS
from scrapers.base import BaseScraper, ScrapedArticle

log = logging.getLogger("odin.pipeline")


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
) -> dict[str, int]:
    """Ejecuta el pipeline. Devuelve conteo de artículos nuevos por fuente."""
    init_db()

    if sources:
        selected = {s: SCRAPERS[s] for s in sources if s in SCRAPERS}
    else:
        selected = dict(SCRAPERS)

    stats: dict[str, int] = {}
    session = get_session()
    try:
        for key, scraper_cls in selected.items():
            scraper: BaseScraper = scraper_cls()
            log.info("Rastreando %s ...", scraper.name)
            # Una consulta por fuente (no por artículo) para el mapa de
            # nombres completos conocidos usado en la canonicalización.
            person_map = known_person_fullname_map()
            new_count = 0

            pending = [
                a for a in scraper.scrape(limit=limit) if not _already_stored(session, a.url)
            ]

            # Si el analizador soporta lote (LocalAnalyzer), una sola pasada de
            # spaCy sobre todos los artículos de la fuente es más eficiente que
            # analizar uno por uno. Si el lote falla, se cae a analizar artículo
            # por artículo para no perder toda la fuente por un solo texto malo.
            results: list | None = None
            analyze_batch = getattr(analyzer, "analyze_batch", None)
            if analyze_batch is not None and pending:
                try:
                    results = analyze_batch([(a.title, a.body or "") for a in pending])
                except Exception:
                    log.exception(
                        "  Falló el análisis en lote de %s, se analiza artículo por artículo",
                        scraper.name,
                    )
                    results = None
            if results is None:
                results = [None] * len(pending)

            for scraped, result in zip(pending, results, strict=True):
                try:
                    if result is None:
                        result = analyzer.analyze(scraped.title, scraped.body or "")
                    _persist(session, scraped, result, analyzer, person_map=person_map)
                    new_count += 1
                    log.info("  [%s] %s", scraper.source, scraped.title[:70])
                except Exception:  # no dejar que un artículo tumbe la corrida
                    session.rollback()
                    log.exception("  Error procesando %s", scraped.url)
            stats[key] = new_count
    finally:
        session.close()
    return stats
