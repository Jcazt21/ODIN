"""Pruebas de db/canonical_entities.py: get_or_create y merge sobre SQLite en
memoria (fixture `sqlite_sessionmaker`, nunca la DATABASE_URL real)."""
from __future__ import annotations

import pytest

from odin.db.canonical_entities import get_or_create, merge
from odin.db.models import Article, CanonicalEntity, Entity


class TestGetOrCreate:
    def test_creates_new_row(self, sqlite_sessionmaker):
        session = sqlite_sessionmaker()
        row = get_or_create(session, "Luis Abinader", "PERSON")
        session.commit()
        assert row.id is not None
        assert row.name == "Luis Abinader"
        assert row.type == "PERSON"

    def test_returns_existing_row_instead_of_duplicating(self, sqlite_sessionmaker):
        session = sqlite_sessionmaker()
        first = get_or_create(session, "Luis Abinader", "PERSON")
        session.commit()
        second = get_or_create(session, "Luis Abinader", "PERSON")
        session.commit()
        assert first.id == second.id
        assert session.query(CanonicalEntity).count() == 1

    def test_same_name_different_type_is_a_different_row(self, sqlite_sessionmaker):
        session = sqlite_sessionmaker()
        person = get_or_create(session, "Salud", "PERSON")
        org = get_or_create(session, "Salud", "ORG")
        session.commit()
        assert person.id != org.id

    def test_visible_within_same_uncommitted_transaction(self, sqlite_sessionmaker):
        # get_or_create hace flush(), no commit(): una segunda llamada dentro
        # de la misma transacción (como ocurre procesando varios artículos de
        # una fuente en pipeline.py antes del commit por artículo) debe
        # encontrar la fila recién creada, no violar la unique constraint.
        session = sqlite_sessionmaker()
        first = get_or_create(session, "Abinader", "PERSON")
        second = get_or_create(session, "Abinader", "PERSON")
        assert first.id == second.id


class TestMerge:
    def _two_rows(self, session):
        a = CanonicalEntity(name="Abinader", type="PERSON")
        b = CanonicalEntity(name="Luis Abinader", type="PERSON")
        session.add_all([a, b])
        session.commit()
        return a, b

    def test_reassigns_mentions_and_deletes_source(self, sqlite_sessionmaker):
        session = sqlite_sessionmaker()
        short, full = self._two_rows(session)
        article = Article(source="diario_libre", url="https://diariolibre.com/x", title="t", body="b")
        article.entities.append(
            Entity(name="Abinader", type="PERSON", mentions_count=2, canonical_entity_id=short.id)
        )
        session.add(article)
        session.commit()

        result = merge(session, target_id=full.id, source_id=short.id)
        session.commit()

        assert result.id == full.id
        assert session.get(CanonicalEntity, short.id) is None
        refreshed = session.query(Entity).filter_by(name="Abinader").one()
        assert refreshed.canonical_entity_id == full.id

    def test_rejects_merging_into_itself(self, sqlite_sessionmaker):
        session = sqlite_sessionmaker()
        _, full = self._two_rows(session)
        with pytest.raises(ValueError):
            merge(session, target_id=full.id, source_id=full.id)

    def test_rejects_mismatched_types(self, sqlite_sessionmaker):
        session = sqlite_sessionmaker()
        person = CanonicalEntity(name="Salud", type="PERSON")
        org = CanonicalEntity(name="Salud", type="ORG")
        session.add_all([person, org])
        session.commit()
        with pytest.raises(ValueError):
            merge(session, target_id=org.id, source_id=person.id)

    def test_rejects_missing_ids(self, sqlite_sessionmaker):
        session = sqlite_sessionmaker()
        _, full = self._two_rows(session)
        with pytest.raises(ValueError):
            merge(session, target_id=full.id, source_id=99999)
