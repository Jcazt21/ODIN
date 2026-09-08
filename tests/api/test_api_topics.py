from __future__ import annotations

from odin.core.auth import create_token


def _h():
    t, _ = create_token("tester")
    return {"Authorization": f"Bearer {t}"}


def test_crud_topic_and_alias(api_client):
    r = api_client.post("/api/topics", headers=_h(),
                        json={"name": "Vivienda", "slug": "vivienda"})
    assert r.status_code == 201, r.text
    tid = r.json()["id"]

    r = api_client.post(f"/api/topics/{tid}/aliases", headers=_h(),
                        json={"alias": "déficit habitacional"})
    assert r.status_code == 201

    r = api_client.get("/api/topics")
    assert any(t["slug"] == "vivienda" for t in r.json())

    r = api_client.put(f"/api/topics/{tid}", headers=_h(), json={"is_active": False})
    assert r.status_code == 200 and r.json()["is_active"] is False


def test_duplicate_sibling_slug_conflicts(api_client):
    api_client.post("/api/topics", headers=_h(), json={"name": "Agua", "slug": "agua-x"})
    r = api_client.post("/api/topics", headers=_h(), json={"name": "AGUA", "slug": "agua-y"})
    assert r.status_code == 409


def test_delete_topic_with_articles_is_soft(api_client, sqlite_sessionmaker):
    from odin.db.models import Article, ArticleTopic, Topic
    s = sqlite_sessionmaker()
    t = Topic(name="Deportes", norm_key="deportes", slug="deportes", path="/99/")
    a = Article(source="acento", url="https://x/dep", title="t", body="b")
    s.add_all([t, a]); s.flush()
    s.add(ArticleTopic(article_id=a.id, topic_id=t.id, score=0.9, origin="AUTO"))
    s.commit(); tid = t.id; s.close()

    r = api_client.delete(f"/api/topics/{tid}", headers=_h())
    assert r.status_code == 204
    s = sqlite_sessionmaker()
    assert s.get(Topic, tid).is_active is False  # no se borró
