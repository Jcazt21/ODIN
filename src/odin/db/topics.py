"""Store del catálogo de temas: caché en memoria + carga de la semilla.

Mismo diseño que `db/aliases.py`: la caché se llena en el primer `resolve()`/
`get_catalog()` y se descarta con `invalidate_cache()` desde los endpoints CRUD.
"""
from __future__ import annotations

import sys
import threading
from dataclasses import dataclass

from sqlalchemy import select

from odin.analysis.text_norm import norm_key
from odin.db.models import Topic, TopicAlias
from odin.db.session import get_session, init_db


@dataclass(frozen=True)
class CatalogTopic:
    id: int
    name: str
    norm_key: str
    parent_id: int | None
    path: str
    aliases: tuple[str, ...]  # ya normalizados con norm_key


_lock = threading.Lock()
_catalog: list[CatalogTopic] | None = None
_by_key: dict[str, int] | None = None  # norm_key (nombre o alias) -> topic_id


def _build() -> tuple[list[CatalogTopic], dict[str, int]]:
    session = get_session()
    try:
        topics = session.scalars(select(Topic).where(Topic.is_active.is_(True))).all()
        aliases = session.scalars(
            select(TopicAlias).where(TopicAlias.is_active.is_(True))
        ).all()
        by_topic_aliases: dict[int, list[str]] = {}
        key_map: dict[str, int] = {}
        for a in aliases:
            k = norm_key(a.alias)
            if not k:
                continue
            by_topic_aliases.setdefault(a.topic_id, []).append(k)
            key_map.setdefault(k, a.topic_id)
        catalog: list[CatalogTopic] = []
        for t in topics:
            k = norm_key(t.name)
            key_map.setdefault(k, t.id)
            catalog.append(CatalogTopic(
                id=t.id, name=t.name, norm_key=k, parent_id=t.parent_id,
                path=t.path, aliases=tuple(sorted(set(by_topic_aliases.get(t.id, [])))),
            ))
        return catalog, key_map
    finally:
        session.close()


def _load_cache() -> tuple[list[CatalogTopic], dict[str, int]]:
    global _catalog, _by_key
    with _lock:
        if _catalog is None or _by_key is None:
            _catalog, _by_key = _build()
        return _catalog, _by_key


def get_catalog() -> list[CatalogTopic]:
    return list(_load_cache()[0])


def resolve(text: str) -> int | None:
    key = norm_key(text)
    if not key:
        return None
    return _load_cache()[1].get(key)


def invalidate_cache() -> None:
    global _catalog, _by_key
    with _lock:
        _catalog = None
        _by_key = None
    # El clasificador compila su matcher a partir de este catálogo, así que un
    # tema/alias nuevo lo deja obsoleto. Solo se invalida si el módulo YA está
    # cargado: si nadie lo ha importado su matcher tampoco existe, y hacerlo
    # incondicional crearía un ciclo de import (topic_classifier importa este
    # módulo).
    classifier = sys.modules.get("odin.analysis.topic_classifier")
    if classifier is not None:
        classifier.invalidate_matcher()


def load_seed() -> int:
    from odin.db.seed_topics import SEED_TOPICS

    init_db()
    session = get_session()
    inserted = 0
    try:
        existing_slugs = set(session.scalars(select(Topic.slug)).all())
        slug_to_id: dict[str, int] = {
            s: i for i, s in session.execute(select(Topic.id, Topic.slug)).all()
        }
        # 1ª pasada: temas raíz y luego hijos (la semilla lista los padres antes).
        for name, slug, parent_slug, _aliases in SEED_TOPICS:
            if slug in existing_slugs:
                continue
            parent_id = slug_to_id.get(parent_slug) if parent_slug else None
            row = Topic(
                name=name.strip(), norm_key=norm_key(name), slug=slug,
                parent_id=parent_id, path="",
            )
            session.add(row)
            session.flush()
            parent_path = "/"
            if parent_id is not None:
                parent_path = session.get(Topic, parent_id).path
            row.path = f"{parent_path}{row.id}/"
            slug_to_id[slug] = row.id
            existing_slugs.add(slug)
            inserted += 1
        # 2ª pasada: alias (todos los temas ya tienen id).
        existing_alias_keys = {
            (tid, k) for tid, k in session.execute(
                select(TopicAlias.topic_id, TopicAlias.alias_key)
            ).all()
        }
        for name, slug, _parent, aliases in SEED_TOPICS:
            tid = slug_to_id.get(slug)
            if tid is None:
                continue
            for alias in aliases:
                k = norm_key(alias)
                if not k or (tid, k) in existing_alias_keys:
                    continue
                session.add(TopicAlias(topic_id=tid, alias=alias.strip(), alias_key=k))
                existing_alias_keys.add((tid, k))
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
    invalidate_cache()
    return inserted
