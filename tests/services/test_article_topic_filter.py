from __future__ import annotations

from sqlalchemy import select

import odin.api  # noqa: F401  (orden de import: evita el ciclo api <-> services)
from odin.db.models import Article, ArticleTopic, Topic
from odin.services.article_service import _apply_article_filters


def _ids(session, **kw):
    base = dict(source=None, sentiment=None, framing=None, headline_intent=None,
                lead_orientation=None, source_quality=None, has_hard_data=None,
                date_from=None, date_to=None, q=None, entity=None)
    base.update(kw)
    return sorted(session.scalars(_apply_article_filters(select(Article.title), **base)).all())


def _seed(s):
    s.add_all([
        Topic(id=1, name="Raíz", norm_key="raiz", slug="raiz", path="/1/"),
        Topic(id=2, name="Hijo", norm_key="hijo", slug="hijo", path="/1/2/", parent_id=1),
        Topic(id=10, name="Otro", norm_key="otro", slug="otro", path="/10/"),
    ])
    arts = [Article(source="a", url=f"https://x/{i}", title=f"t{i}", body="b", main_topic="raiz") for i in range(3)]
    s.add_all(arts)
    s.flush()
    s.add_all([
        ArticleTopic(article_id=arts[0].id, topic_id=1, origin="AUTO"),
        ArticleTopic(article_id=arts[0].id, topic_id=2, origin="AUTO"),
        ArticleTopic(article_id=arts[1].id, topic_id=2, origin="AUTO"),
        ArticleTopic(article_id=arts[2].id, topic_id=10, origin="AUTO"),
    ])
    s.commit()


def test_parent_includes_children_once(db_session):
    _seed(db_session)
    assert _ids(db_session, topic_id=1) == ["t0", "t1"]


def test_child_only_and_no_prefix_confusion(db_session):
    _seed(db_session)
    assert _ids(db_session, topic_id=2) == ["t0", "t1"]
    assert _ids(db_session, topic_id=10) == ["t2"]


def test_independent_from_text_topic_filter(db_session):
    _seed(db_session)
    # topic_id no es el filtro de texto: se combinan con AND, cada uno por su lado
    assert _ids(db_session, topic="raiz", topic_id=10) == ["t2"]
    assert _ids(db_session, topic="zzz", topic_id=10) == []
