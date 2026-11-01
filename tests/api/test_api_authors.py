from __future__ import annotations

from odin.core.auth import create_token
from odin.db.models import Article


def _h():
    t, _ = create_token("tester")
    return {"Authorization": f"Bearer {t}"}


def _seed(sm):
    s = sm()
    s.add_all([
        Article(source="a", url="https://x/1", title="t", body="b", authors="Ana Pérez"),
        Article(source="a", url="https://x/2", title="t", body="b", authors="Ana Pérez, Luis Soto"),
    ])
    s.commit()
    s.close()


def test_list_authors_ok(api_client, sqlite_sessionmaker):
    _seed(sqlite_sessionmaker)
    r = api_client.get("/api/authors", headers=_h())
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["total"] == 2
    assert body["items"][0] == {
        "name": "Ana Pérez", "article_count": 2, "sources": ["a"],
        "last_published_at": None,
    }


def test_invalid_sort_is_422(api_client):
    assert api_client.get("/api/authors?sort=zzz", headers=_h()).status_code == 422


def test_requires_auth(api_client):
    assert api_client.get("/api/authors").status_code in (401, 403)
