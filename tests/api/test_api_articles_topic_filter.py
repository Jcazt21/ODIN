from __future__ import annotations

from odin.core.auth import create_token
from odin.db.models import Article, ArticleTopic, Topic


def _h():
    t, _ = create_token("tester")
    return {"Authorization": f"Bearer {t}"}


def _seed(sm):
    s = sm()
    s.add_all([
        Topic(id=1, name="Raíz", norm_key="raiz", slug="raiz", path="/1/"),
        Topic(id=2, name="Hijo", norm_key="hijo", slug="hijo", path="/1/2/", parent_id=1),
    ])
    a = Article(source="a", url="https://x/1", title="uno", body="b")
    b = Article(source="b", url="https://x/2", title="dos", body="b")
    s.add_all([a, b])
    s.flush()
    s.add_all([ArticleTopic(article_id=a.id, topic_id=2, origin="AUTO"),
               ArticleTopic(article_id=b.id, topic_id=2, origin="AUTO")])
    s.commit()
    s.close()


def test_topic_id_filters_with_total(api_client, sqlite_sessionmaker):
    _seed(sqlite_sessionmaker)
    r = api_client.get("/api/articles?topic_id=1", headers=_h())
    assert r.status_code == 200 and r.json()["total"] == 2
    r = api_client.get("/api/articles?topic_id=1&source=a", headers=_h())
    assert [i["title"] for i in r.json()["items"]] == ["uno"]


def test_unknown_topic_id_is_empty(api_client, sqlite_sessionmaker):
    _seed(sqlite_sessionmaker)
    r = api_client.get("/api/articles?topic_id=999", headers=_h())
    assert r.status_code == 200 and r.json() == {"total": 0, "limit": 20, "offset": 0, "items": []}
