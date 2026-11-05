from __future__ import annotations

import pytest

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
    s.add_all([t, a])
    s.flush()
    s.add(ArticleTopic(article_id=a.id, topic_id=t.id, score=0.9, origin="AUTO"))
    s.commit()
    tid = t.id
    s.close()

    r = api_client.delete(f"/api/topics/{tid}", headers=_h())
    assert r.status_code == 204
    s = sqlite_sessionmaker()
    assert s.get(Topic, tid).is_active is False  # no se borró


def test_frequency_returns_real_counts_per_topic_and_day(api_client, sqlite_sessionmaker):
    from datetime import datetime

    from odin.db.models import Article, ArticleTopic, Topic
    s = sqlite_sessionmaker()
    t = Topic(name="Deportes", norm_key="deportes", slug="deportes-freq", path="/98/")
    a1 = Article(source="acento", url="https://x/f1", title="t", body="b",
                 published_at=datetime(2026, 10, 1, 12))
    a2 = Article(source="acento", url="https://x/f2", title="t", body="b",
                 published_at=datetime(2026, 10, 1, 15))
    s.add_all([t, a1, a2])
    s.flush()
    s.add_all([
        ArticleTopic(article_id=a1.id, topic_id=t.id, score=0.9, origin="AUTO"),
        ArticleTopic(article_id=a2.id, topic_id=t.id, score=0.9, origin="AUTO"),
    ])
    s.commit()
    tid = t.id
    s.close()

    r = api_client.get("/api/topics/frequency", headers=_h())
    assert r.status_code == 200, r.text
    rows = [x for x in r.json() if x["topic_id"] == tid]
    assert len(rows) == 1
    assert rows[0]["name"] == "Deportes"
    assert rows[0]["day"] == "2026-10-01"
    assert rows[0]["count"] == 2


# ── CRUD de temas (plan 2026-11-02) ──────────────────────────────────────────

def _post(api_client, **body):
    return api_client.post("/api/topics", headers=_h(), json=body)


def test_create_without_slug_derives_it(api_client):
    r = _post(api_client, name="Política y Gobierno")
    assert r.status_code == 201, r.text
    assert r.json()["slug"] == "politica-y-gobierno"


def test_derived_slug_collision_gets_suffix(api_client):
    root = _post(api_client, name="Padre").json()["id"]
    assert _post(api_client, name="Salud").json()["slug"] == "salud"
    assert _post(api_client, name="Salud", parent_id=root).json()["slug"] == "salud-2"
    other = _post(api_client, name="Otro").json()["id"]
    assert _post(api_client, name="Salud", parent_id=other).json()["slug"] == "salud-3"


def test_name_without_alphanumerics_is_422(api_client):
    r = _post(api_client, name="***")
    assert r.status_code == 422
    assert r.json()["detail"] == "El nombre debe contener letras o números."
    assert api_client.get("/api/topics?include_inactive=true").json() == []


def test_explicit_slug_respected_and_clash_409(api_client):
    # Caracterización: nace verde.
    assert _post(api_client, name="Uno", slug="mi-slug").json()["slug"] == "mi-slug"
    r = _post(api_client, name="Dos", slug="mi-slug")
    assert r.status_code == 409
    assert r.json()["detail"] == "El slug 'mi-slug' ya está en uso."


def _tree(api_client, inactive=False):
    q = "?include_inactive=true" if inactive else ""
    return api_client.get(f"/api/topics/tree{q}").json()


def _off(api_client, tid):
    return api_client.put(f"/api/topics/{tid}", headers=_h(), json={"is_active": False})


def test_tree_exposes_state_fields(api_client):
    tid = _post(api_client, name="Agua", description="Recursos", display_order=3).json()["id"]
    _off(api_client, tid)
    assert _tree(api_client) == []
    node = _tree(api_client, inactive=True)[0]
    assert node["is_active"] is False
    assert node["description"] == "Recursos"
    assert node["display_order"] == 3
    assert isinstance(node["aliases"], list)


def test_tree_child_count_includes_inactive_children(api_client):
    pid = _post(api_client, name="Padre").json()["id"]
    cid = _post(api_client, name="Hijo", parent_id=pid).json()["id"]
    _off(api_client, cid)
    root = _tree(api_client)[0]
    assert root["children"] == []
    assert root["child_count"] == 1
    leaf = _post(api_client, name="Hoja").json()["id"]
    assert next(n for n in _tree(api_client) if n["id"] == leaf)["child_count"] == 0


def test_put_renames_and_redescribes(api_client):
    tid = _post(api_client, name="Viejo").json()["id"]
    r = api_client.put(f"/api/topics/{tid}", headers=_h(),
                       json={"name": "Nuevo", "description": "d"})
    assert r.status_code == 200
    assert (r.json()["name"], r.json()["description"]) == ("Nuevo", "d")


def test_put_blank_name_is_422(api_client):
    tid = _post(api_client, name="A").json()["id"]
    r = api_client.put(f"/api/topics/{tid}", headers=_h(), json={"name": "  "})
    assert r.status_code == 422


def test_put_duplicate_sibling_name_is_409(api_client):
    _post(api_client, name="Uno")
    tid = _post(api_client, name="Dos").json()["id"]
    r = api_client.put(f"/api/topics/{tid}", headers=_h(), json={"name": "UNO"})
    assert r.status_code == 409


def test_put_unknown_id_is_404(api_client):
    r = api_client.put("/api/topics/99999", headers=_h(), json={"name": "x"})
    assert r.status_code == 404


def test_put_reactivates(api_client):
    tid = _post(api_client, name="A").json()["id"]
    _off(api_client, tid)
    r = api_client.put(f"/api/topics/{tid}", headers=_h(), json={"is_active": True})
    assert r.status_code == 200 and r.json()["is_active"] is True


def test_delete_topic_with_children_is_soft(api_client):
    pid = _post(api_client, name="Padre").json()["id"]
    cid = _post(api_client, name="Hijo", parent_id=pid).json()["id"]
    _off(api_client, cid)  # hijo inactivo también cuenta
    assert api_client.delete(f"/api/topics/{pid}", headers=_h()).status_code == 204
    node = next(n for n in _tree(api_client, inactive=True) if n["id"] == pid)
    assert node["is_active"] is False


def test_delete_empty_topic_removes_it(api_client):
    tid = _post(api_client, name="Vacío").json()["id"]
    assert api_client.delete(f"/api/topics/{tid}", headers=_h()).status_code == 204
    assert _tree(api_client, inactive=True) == []


def test_delete_unknown_is_404(api_client):
    assert api_client.delete("/api/topics/99999", headers=_h()).status_code == 404


def test_delete_empty_topic_removes_its_aliases(api_client, sqlite_sessionmaker):
    from odin.db.models import TopicAlias
    tid = _post(api_client, name="Vacío").json()["id"]
    r = api_client.post(f"/api/topics/{tid}/aliases", headers=_h(), json={"alias": "x"})
    assert r.status_code == 201
    s = sqlite_sessionmaker()
    assert s.query(TopicAlias).filter_by(topic_id=tid).count() == 1
    s.close()
    api_client.delete(f"/api/topics/{tid}", headers=_h())
    s = sqlite_sessionmaker()
    assert s.query(TopicAlias).filter_by(topic_id=tid).count() == 0
    s.close()


def test_create_unknown_parent_404(api_client):
    assert _post(api_client, name="X", parent_id=99999).status_code == 404


@pytest.mark.parametrize("method,url,body", [
    ("post", "/api/topics", {"name": "X"}),
    ("put", "/api/topics/1", {"name": "X"}),
    ("delete", "/api/topics/1", None),
])
def test_mutations_require_auth(api_client, method, url, body):
    kw = {"json": body} if body is not None else {}
    assert getattr(api_client, method)(url, **kw).status_code == 401


def test_mutations_invalidate_catalog_cache(api_client, monkeypatch):
    calls = []
    monkeypatch.setattr("odin.db.topics.invalidate_cache", lambda: calls.append(1))
    tid = _post(api_client, name="A").json()["id"]
    assert len(calls) == 1
    api_client.put(f"/api/topics/{tid}", headers=_h(), json={"name": "B"})
    assert len(calls) == 2
    api_client.delete(f"/api/topics/{tid}", headers=_h())
    assert len(calls) == 3
    _post(api_client, name="***")  # 422
    api_client.put("/api/topics/99999", headers=_h(), json={"name": "x"})  # 404
    api_client.delete("/api/topics/99999", headers=_h())  # 404
    assert len(calls) == 3


def test_blank_description_stored_as_null(api_client):
    r = _post(api_client, name="A", description="  ")
    assert r.json()["description"] is None
    tid = _post(api_client, name="B", description="algo").json()["id"]
    r = api_client.put(f"/api/topics/{tid}", headers=_h(), json={"description": ""})
    assert r.json()["description"] is None
