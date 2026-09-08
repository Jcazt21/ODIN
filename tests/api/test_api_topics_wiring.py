"""Cableado del catálogo de temas en los tres puntos donde un análisis se
vuelve filas: vista previa de /api/analyze (Task 6), guardado manual (Task 7) y
filtro/faceta del listado (Task 9). El clasificador es regex puro y local — sin
Gemini/Groq (CLAUDE.md)."""
from __future__ import annotations

from types import SimpleNamespace

from odin.analysis.base import AnalysisResult
from odin.core.auth import create_token
from odin.db import topics as topic_store
from odin.services import analyze_service


def _h():
    t, _ = create_token("tester")
    return {"Authorization": f"Bearer {t}"}


def _wire_topics(monkeypatch, sqlite_sessionmaker):
    """El store de temas y el matcher del clasificador usan `odin.db.session`
    fuera de la API; apuntarlos a la BD en memoria del test."""
    import odin.analysis.topic_classifier as tc

    monkeypatch.setattr(topic_store, "get_session", sqlite_sessionmaker)
    monkeypatch.setattr(topic_store, "init_db", lambda: None)
    topic_store.invalidate_cache()
    tc.invalidate_matcher()


def _patch_analyze(monkeypatch, *, title, body, main_topic="", keywords=()):
    """Doble del pipeline de análisis, calcado de tests/api/test_api_analyze_jobs.py."""
    from odin.core import url_guard

    monkeypatch.setattr(url_guard, "validate_url", lambda url: url)
    monkeypatch.setattr(analyze_service, "fetch_and_extract", lambda url: {
        "title": title, "body": body, "authors": None, "section": None,
        "published_at": None, "sitename": "acento",
    })
    result = AnalysisResult(main_topic=main_topic, topic_keywords=list(keywords),
                            overall_sentiment="NEG", sentiment_score=0.6)
    monkeypatch.setattr(analyze_service, "analyze_safely", lambda t, b: result)
    monkeypatch.setattr(analyze_service, "place_extractor",
                        lambda: SimpleNamespace(extract_places=lambda t, b: []))
    monkeypatch.setattr(analyze_service, "arbitrate_ambiguous_persons", lambda r: None)
    monkeypatch.setattr(analyze_service, "canonicalize_result", lambda r: None)


def test_preview_returns_suggested_topics(api_client, monkeypatch, sqlite_sessionmaker):
    _wire_topics(monkeypatch, sqlite_sessionmaker)
    topic_store.load_seed()
    _patch_analyze(monkeypatch,
                   title="Protestan por la escasez de agua en Villa Altagracia",
                   body="Vecinos reclaman agua potable.",
                   main_topic="escasez de agua", keywords=("agua", "acueducto"))

    r = api_client.post("/api/analyze", headers=_h(),
                        json={"url": "https://acento.com.do/x"})
    assert r.status_code == 202, r.text
    job_id = r.json()["job_id"]

    jr = api_client.get(f"/api/jobs/{job_id}", headers=_h())
    assert jr.status_code == 200
    body = jr.json()
    assert body["status"] == "done", body
    suggested = body["result"]["suggested_topics"]
    names = {s["name"] for s in suggested}
    assert "Agua" in names
    agua = next(s for s in suggested if s["name"] == "Agua")
    assert agua["score"] >= 0.6 and agua["evidence"]


# ── Task 7: persistir article_topics al guardar (manual) ─────────────────────

def test_save_with_explicit_topic_ids_is_manual(api_client, monkeypatch, sqlite_sessionmaker):
    _wire_topics(monkeypatch, sqlite_sessionmaker)
    topic_store.load_seed()
    agua = topic_store.resolve("Agua")
    body = dict(source="acento", url="https://acento.com.do/s1", title="t", body="cuerpo",
                entities=[], topic_ids=[agua])
    r = api_client.post("/api/articles", headers=_h(), json=body)
    assert r.status_code == 201, r.text
    from odin.db.models import ArticleTopic
    s = sqlite_sessionmaker()
    rows = s.query(ArticleTopic).all()
    assert [(x.topic_id, x.origin) for x in rows] == [(agua, "MANUAL")]


def test_save_without_topic_ids_runs_classifier(api_client, monkeypatch, sqlite_sessionmaker):
    _wire_topics(monkeypatch, sqlite_sessionmaker)
    topic_store.load_seed()
    agua = topic_store.resolve("Agua")
    body = dict(source="acento", url="https://acento.com.do/s2",
                title="Reclaman por la escasez de agua", body="El acueducto no da servicio.",
                main_topic="escasez de agua", entities=[])
    r = api_client.post("/api/articles", headers=_h(), json=body)
    assert r.status_code == 201
    from odin.db.models import ArticleTopic
    s = sqlite_sessionmaker()
    rows = s.query(ArticleTopic).filter_by(origin="AUTO").all()
    assert agua in {x.topic_id for x in rows}
