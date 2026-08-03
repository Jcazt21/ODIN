"""Pipeline principal: scrape -> analizar -> guardar.

Orquesta los scrapers y el analizador, y persiste todo en la base de datos.
Evita duplicados por URL (no re-analiza artículos ya guardados).
"""
from __future__ import annotations

import logging

from sqlalchemy import select

from analysis.base import Analyzer
from analysis.canonicalize import canonicalize_result, known_person_fullname_map
from db.models import Article, Entity
from db.session import get_session, init_db
from scrapers import SCRAPERS
from scrapers.base import BaseScraper, ScrapedArticle

log = logging.getLogger("odin.pipeline")


def _already_stored(session, url: str) -> bool:
    return session.scalar(select(Article.id).where(Article.url == url)) is not None


def _persist(
    session,
    scraped: ScrapedArticle,
    analyzer: Analyzer,
    person_map: dict[str, str] | None = None,
) -> Article:
    result = analyzer.analyze(scraped.title, scraped.body or "")
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
        dominant_actor=result.dominant_actor,
        source_quality=result.source_quality,
        has_hard_data=result.has_hard_data,
        blamed_actor=result.blamed_actor,
        credited_actor=result.credited_actor,
    )
    for e in result.entities:
        article.entities.append(
            Entity(
                name=e.name,
                type=e.type,
                mentions_count=e.mentions_count,
                sentiment_toward=e.sentiment_toward,
                sentiment_score=e.sentiment_score,
                context=e.context,
            )
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
            for scraped in scraper.scrape(limit=limit):
                if _already_stored(session, scraped.url):
                    continue
                try:
                    _persist(session, scraped, analyzer, person_map=person_map)
                    new_count += 1
                    log.info("  [%s] %s", scraper.source, scraped.title[:70])
                except Exception:  # no dejar que un artículo tumbe la corrida
                    session.rollback()
                    log.exception("  Error procesando %s", scraped.url)
            stats[key] = new_count
    finally:
        session.close()
    return stats
