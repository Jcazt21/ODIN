from __future__ import annotations

from odin.analysis import topic_classifier as tc
from odin.db import topics as topic_store


def _wire_store(monkeypatch, sqlite_sessionmaker):
    """Apunta el store de temas a la BD en memoria del test (igual que en
    `tests/db/test_topics_store.py`) y descarta las cachés de proceso: el
    matcher del clasificador se compila desde `topic_store.get_catalog()`, que
    fuera de la API usa la DATABASE_URL real."""
    monkeypatch.setattr(topic_store, "get_session", sqlite_sessionmaker)
    monkeypatch.setattr(topic_store, "init_db", lambda: None)
    topic_store.invalidate_cache()
    tc.invalidate_matcher()


def _ids(matches):
    return {m.topic_id for m in matches}


def test_title_hit_scores_high(monkeypatch, sqlite_sessionmaker):
    _wire_store(monkeypatch, sqlite_sessionmaker)
    topic_store.load_seed()
    agua = topic_store.resolve("Agua")
    m = tc.classify(title="Protestan por la escasez de agua en Villa Altagracia",
                    body="Vecinos reclaman.", keywords=None, main_topic=None)
    assert agua in _ids(m)
    assert max(x.score for x in m if x.topic_id == agua) >= 0.85


def test_single_body_mention_below_threshold(monkeypatch, sqlite_sessionmaker):
    _wire_store(monkeypatch, sqlite_sessionmaker)
    topic_store.load_seed()
    agua = topic_store.resolve("Agua")
    m = tc.classify(title="Inauguran parque infantil",
                    body="Al acto asistió el director del acueducto local.",
                    keywords=None, main_topic=None)
    assert agua not in _ids(m)


def test_two_distinct_body_terms_match(monkeypatch, sqlite_sessionmaker):
    _wire_store(monkeypatch, sqlite_sessionmaker)
    topic_store.load_seed()
    energia = topic_store.resolve("Energía eléctrica")
    m = tc.classify(
        title="Comunidad en reclamo",
        body="El apagón lleva ocho horas. EDESUR no responde por la avería.",
        keywords=None, main_topic=None,
    )
    assert energia in _ids(m)


def test_main_topic_is_a_signal(monkeypatch, sqlite_sessionmaker):
    _wire_store(monkeypatch, sqlite_sessionmaker)
    topic_store.load_seed()
    salud = topic_store.resolve("Salud")
    m = tc.classify(title="Nota", body="Cuerpo sin señales.",
                    keywords="hospital, dengue", main_topic="servicios de salud")
    assert salud in _ids(m)
