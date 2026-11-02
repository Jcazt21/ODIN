from __future__ import annotations

from odin.core.auth import create_token
from odin.db.models import Article


def _h():
    t, _ = create_token("tester")
    return {"Authorization": f"Bearer {t}"}


def test_articles_author_param(api_client, sqlite_sessionmaker):
    s = sqlite_sessionmaker()
    s.add_all([
        Article(source="a", url="https://x/1", title="uno", body="b", authors="Ana Pérez, Luis Soto"),
        Article(source="a", url="https://x/2", title="dos", body="b", authors="Mariana Gómez"),
    ])
    s.commit()
    s.close()
    r = api_client.get("/api/articles?author=Luis Soto", headers=_h())
    assert r.status_code == 200
    assert r.json()["total"] == 1
    assert [i["title"] for i in r.json()["items"]] == ["uno"]
    assert api_client.get("/api/articles", headers=_h()).json()["total"] == 2
