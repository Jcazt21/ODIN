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
        Topic(id=3, name="Vacío", norm_key="vacio", slug="vacio", path="/3/"),
    ])
    a = Article(source="a", url="https://x/1", title="t", body="b")
    s.add(a)
    s.flush()
    s.add(ArticleTopic(article_id=a.id, topic_id=2, origin="AUTO"))
    s.commit()
    s.close()


def test_tree_and_list_carry_article_count(api_client, sqlite_sessionmaker):
    _seed(sqlite_sessionmaker)
    tree = {n["id"]: n for n in api_client.get("/api/topics/tree").json()}
    assert tree[1]["article_count"] == 1
    assert tree[1]["children"][0]["article_count"] == 1
    assert tree[3]["article_count"] == 0
    flat = {t["id"]: t for t in api_client.get("/api/topics").json()}
    assert flat[1]["article_count"] == 1 and flat[3]["article_count"] == 0
