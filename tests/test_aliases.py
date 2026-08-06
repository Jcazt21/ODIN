"""Pruebas de db/aliases.py: resolve() debe matchear sin importar acentos ni
mayúsculas (bug: "Policia" no matcheaba un alias guardado como "Policía")."""
from __future__ import annotations

import db.aliases as alias_store
from db.models import EntityAlias


def _seed(session, **overrides):
    defaults = dict(
        alias="Policía Nacional",
        alias_key=alias_store.normalize_key("Policía Nacional"),
        canonical_name="Policía Nacional",
        type="ORG",
    )
    defaults.update(overrides)
    session.add(EntityAlias(**defaults))
    session.commit()


class TestNormalizeKey:
    def test_strips_accents(self):
        assert alias_store.normalize_key("Policía") == alias_store.normalize_key("Policia")

    def test_lowercases(self):
        assert alias_store.normalize_key("MINERD") == alias_store.normalize_key("minerd")

    def test_strips_periods_in_acronym(self):
        assert alias_store.normalize_key("P.R.M.") == alias_store.normalize_key("PRM")

    def test_normalizes_hyphens_to_spaces(self):
        assert alias_store.normalize_key("Jean-Claude") == alias_store.normalize_key("Jean Claude")


class TestResolve:
    def test_matches_unaccented_query_against_accented_alias(self, monkeypatch, sqlite_sessionmaker):
        session = sqlite_sessionmaker()
        _seed(session)
        session.close()

        monkeypatch.setattr(alias_store, "get_session", sqlite_sessionmaker)
        alias_store.invalidate_cache()

        assert alias_store.resolve("Policia Nacional") == ("Policía Nacional", "ORG")
        assert alias_store.resolve("policía nacional") == ("Policía Nacional", "ORG")
        assert alias_store.resolve("POLICIA NACIONAL") == ("Policía Nacional", "ORG")

    def test_matches_legacy_accented_alias_key_stored_in_db(self, monkeypatch, sqlite_sessionmaker):
        """Filas insertadas antes del fix pueden tener alias_key con acentos
        (p.ej. 'policía nacional'); resolve() debe seguir matcheándolas."""
        session = sqlite_sessionmaker()
        _seed(session, alias_key="policía nacional")
        session.close()

        monkeypatch.setattr(alias_store, "get_session", sqlite_sessionmaker)
        alias_store.invalidate_cache()

        assert alias_store.resolve("Policia Nacional") == ("Policía Nacional", "ORG")


class TestLoadSeed:
    def test_load_seed_and_resolve_new_entities(self, monkeypatch, sqlite_sessionmaker):
        monkeypatch.setattr(alias_store, "get_session", sqlite_sessionmaker)
        monkeypatch.setattr(alias_store, "init_db", lambda: None)
        alias_store.invalidate_cache()

        inserted = alias_store.load_seed()
        assert inserted > 50

        # Verificar algunas entidades clave recién agregadas
        assert alias_store.resolve("PEPCA") == ("Procuraduría Especializada de Persecución de la Corrupción Administrativa", "ORG")
        assert alias_store.resolve("INDOMET") == ("Instituto Dominicano de Meteorología", "ORG")
        assert alias_store.resolve("POLITUR") == ("Dirección Central de Policía de Turismo", "ORG")
        assert alias_store.resolve("SUPERATE") == ("Programa Supérate", "ORG")
        assert alias_store.resolve("ADN") == ("Ayuntamiento del Distrito Nacional", "ORG")
        assert alias_store.resolve("Faride") == ("Faride Raful", "PERSON")
        assert alias_store.resolve("Guido") == ("Guido Gómez Mazara", "PERSON")
        assert alias_store.resolve("Hipólito") == ("Hipólito Mejía", "PERSON")
