"""Pruebas de pipeline.py: que _persist() vincule cada entidad guardada a su
fila de canonical_entities, igual que save_article en api.py. Usa un Analyzer
falso (sin spaCy/pysentimiento/Gemini) y SQLite en memoria."""
from __future__ import annotations

from analysis.base import ANALYSIS_SCHEMA_VERSION, AnalysisResult, EntityResult
from db.models import CanonicalEntity, Entity
from pipeline import _persist
from scrapers.base import ScrapedArticle


class _FakeAnalyzer:
    name = "fake"
    model = "fake-model"
    version = "0"

    def analyze(self, title: str, body: str) -> AnalysisResult:
        return AnalysisResult(
            main_topic="tema",
            entities=[EntityResult(name="Luis Abinader", type="PERSON", mentions_count=2)],
        )


def _scraped(url: str) -> ScrapedArticle:
    return ScrapedArticle(source="diario_libre", url=url, title="Título", body="cuerpo")


class TestPersistLinksCanonicalEntity:
    def test_new_entity_gets_a_canonical_row(self, sqlite_sessionmaker, monkeypatch):
        import analysis.canonicalize as canonicalize

        monkeypatch.setattr(canonicalize.alias_store, "resolve", lambda name: None)
        monkeypatch.setattr(canonicalize.alias_store, "all_canonicals", lambda: [])

        session = sqlite_sessionmaker()
        result = _FakeAnalyzer().analyze("Título", "cuerpo")
        article = _persist(session, _scraped("https://diariolibre.com/pipeline-1"), result)

        entity = article.entities[0]
        assert entity.canonical_entity_id is not None
        canonical = session.get(CanonicalEntity, entity.canonical_entity_id)
        assert canonical.name == "Luis Abinader"

    def test_two_articles_in_same_run_share_canonical_row(self, sqlite_sessionmaker, monkeypatch):
        import analysis.canonicalize as canonicalize

        monkeypatch.setattr(canonicalize.alias_store, "resolve", lambda name: None)
        monkeypatch.setattr(canonicalize.alias_store, "all_canonicals", lambda: [])

        session = sqlite_sessionmaker()
        analyzer = _FakeAnalyzer()
        _persist(session, _scraped("https://diariolibre.com/pipeline-2a"), analyzer.analyze("Título", "cuerpo"))
        _persist(session, _scraped("https://diariolibre.com/pipeline-2b"), analyzer.analyze("Título", "cuerpo"))

        assert session.query(CanonicalEntity).filter_by(name="Luis Abinader").count() == 1
        mentions = session.query(Entity).filter_by(name="Luis Abinader").all()
        assert len(mentions) == 2
        assert mentions[0].canonical_entity_id == mentions[1].canonical_entity_id


class TestPersistRecordsLineage:
    def test_stamps_analyzer_lineage(self, sqlite_sessionmaker, monkeypatch):
        import analysis.canonicalize as canonicalize

        monkeypatch.setattr(canonicalize.alias_store, "resolve", lambda name: None)
        monkeypatch.setattr(canonicalize.alias_store, "all_canonicals", lambda: [])

        session = sqlite_sessionmaker()
        article = _persist(session, _scraped("https://diariolibre.com/pipeline-lineage"), _FakeAnalyzer())

        assert article.analyzer_name == "fake"
        assert article.analyzer_model == "fake-model"
        assert article.analyzer_version == "0"
        assert article.analysis_schema_version == ANALYSIS_SCHEMA_VERSION
        assert article.analyzed_at is not None
