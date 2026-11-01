from __future__ import annotations

import odin.api  # noqa: F401  (orden de import: evita el ciclo api <-> services)
from odin.db.models import Article, ArticleTopic, Topic
from odin.services.topic_service import topic_article_counts


def _seed(s):
    root = Topic(name="Raíz", norm_key="raiz", slug="raiz", path="/1/")
    child = Topic(name="Hijo", norm_key="hijo", slug="hijo", path="/1/2/", parent_id=1)
    other = Topic(name="Otro", norm_key="otro", slug="otro", path="/10/")
    root.id, child.id, other.id = 1, 2, 10
    arts = [Article(source="a", url=f"https://x/{i}", title="t", body="b") for i in range(3)]
    s.add_all([root, child, other, *arts])
    s.flush()
    # a0 en padre e hijo; a1 solo en hijo; a2 en "Otro"
    s.add_all([
        ArticleTopic(article_id=arts[0].id, topic_id=1, origin="AUTO"),
        ArticleTopic(article_id=arts[0].id, topic_id=2, origin="AUTO"),
        ArticleTopic(article_id=arts[1].id, topic_id=2, origin="AUTO"),
        ArticleTopic(article_id=arts[2].id, topic_id=10, origin="AUTO"),
    ])
    s.commit()


def test_rollup_counts_distinct_articles(db_session):
    _seed(db_session)
    counts = topic_article_counts(db_session)
    assert counts[1] == 2   # a0 (una sola vez) + a1 vía el hijo
    assert counts[2] == 2
    assert counts[10] == 1  # "/10/" no se mezcla con "/1/"
