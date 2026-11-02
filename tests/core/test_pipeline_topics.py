"""`_persist` clasifica el tema en el rastreo masivo: los artículos que entran
por crawl salen con sus filas `article_topics` `origin="AUTO"`, igual que los
que entran por /api/analyze. Clasificador regex puro, sin LLM (CLAUDE.md)."""
from __future__ import annotations

from odin.analysis.base import AnalysisResult
from odin.core import pipeline
from odin.db import topics as topic_store
from odin.db.models import ArticleTopic
from odin.scrapers.base import ScrapedArticle


class _A:
    name, model, version = "local", "test", "t"


def test_persist_creates_article_topics(sqlite_sessionmaker, monkeypatch):
    import odin.analysis.canonicalize as canonicalize
    import odin.analysis.topic_classifier as tc

    monkeypatch.setattr(canonicalize.alias_store, "resolve", lambda name: None)
    monkeypatch.setattr(canonicalize.alias_store, "all_canonicals", lambda: [])
    monkeypatch.setattr(topic_store, "get_session", sqlite_sessionmaker)
    monkeypatch.setattr(topic_store, "init_db", lambda: None)
    topic_store.invalidate_cache()
    tc.invalidate_matcher()

    topic_store.load_seed()
    agua = topic_store.resolve("Agua")
    session = sqlite_sessionmaker()

    scraped = ScrapedArticle(source="acento", url="https://acento.com.do/p1",
                             title="Protesta por escasez de agua", body="El acueducto falla.")
    result = AnalysisResult(main_topic="escasez de agua", topic_keywords=["agua"],
                            overall_sentiment="NEG", sentiment_score=0.6, entities=[])

    pipeline._persist(session, scraped, result, _A())

    rows = session.query(ArticleTopic).all()
    assert agua in {r.topic_id for r in rows}
    assert rows and all(r.origin == "AUTO" for r in rows)
