from __future__ import annotations

from odin.db import topics as topic_store
from odin.db.models import Article, ArticleTopic, Topic


def _wire_store(monkeypatch, sqlite_sessionmaker):
    """Apunta el store a la BD en memoria del test, igual que en
    `tests/db/test_aliases.py`: `load_seed()`/`_build()` usan `get_session()` e
    `init_db()` de `odin.db.session`, que fuera de la API van a la DATABASE_URL
    real. Se parchean en el módulo del store y se descarta la caché de proceso."""
    monkeypatch.setattr(topic_store, "get_session", sqlite_sessionmaker)
    monkeypatch.setattr(topic_store, "init_db", lambda: None)
    topic_store.invalidate_cache()


def test_topic_hierarchy_and_unique_sibling(sqlite_sessionmaker):
    s = sqlite_sessionmaker()
    agua = Topic(name="Agua", norm_key="agua", slug="agua", path="")
    s.add(agua)
    s.flush()
    agua.path = f"/{agua.id}/"
    infra = Topic(name="Infraestructura", norm_key="infraestructura", slug="infra",
                  parent_id=agua.id, path=f"/{agua.id}/")
    s.add(infra)
    s.flush()
    infra.path = f"/{agua.id}/{infra.id}/"
    s.commit()
    assert [c.name for c in agua.children] == ["Infraestructura"]


def test_article_topics_cascade_delete(sqlite_sessionmaker):
    s = sqlite_sessionmaker()
    t = Topic(name="Energía", norm_key="energia", slug="energia", path="/1/")
    a = Article(source="diario_libre", url="https://x/1", title="t", body="b")
    s.add_all([t, a])
    s.flush()
    s.add(ArticleTopic(article_id=a.id, topic_id=t.id, score=0.9, origin="AUTO",
                       evidence="agua potable"))
    s.commit()
    s.delete(a)
    s.commit()
    assert s.query(ArticleTopic).count() == 0


def test_load_seed_idempotent_and_resolve(monkeypatch, sqlite_sessionmaker):
    _wire_store(monkeypatch, sqlite_sessionmaker)
    n1 = topic_store.load_seed()
    n2 = topic_store.load_seed()
    assert n1 > 0 and n2 == 0
    # por nombre y por alias, sin acentos ni mayúsculas
    agua_id = topic_store.resolve("Agua")
    assert agua_id is not None
    assert topic_store.resolve("ACUEDUCTO") == agua_id
    assert topic_store.resolve("no-existe-este-tema") is None


def test_get_catalog_shape(monkeypatch, sqlite_sessionmaker):
    _wire_store(monkeypatch, sqlite_sessionmaker)
    topic_store.load_seed()
    cat = topic_store.get_catalog()
    agua = next(t for t in cat if t.norm_key == "agua")
    assert "acueducto" in agua.aliases
    assert agua.path.endswith(f"/{agua.id}/")
