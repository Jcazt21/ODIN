"""Pruebas de analysis/canonicalize.py: fusión de entidades, desambiguación
por apellido único y reasignación de actores.

Ninguna prueba de este archivo debe golpear la `DATABASE_URL` real (por
defecto Postgres): el fixture `_no_real_alias_db`, autouse, sustituye el
catálogo de aliases por uno vacío salvo que un test lo sobreescriba
explícitamente.
"""
from __future__ import annotations

import pytest

import odin.analysis.canonicalize as canonicalize
import odin.db.session as db_session_module
from odin.analysis.base import EntityResult
from odin.analysis.canonicalize import (
    _apply_alias_catalog,
    _merge_duplicates,
    _norm_key,
    _resolve_partial_persons,
    _strip_title_prefix,
    canonicalize_entities,
    known_person_fullname_map,
    match_actor_name,
)
from odin.db.models import Entity


@pytest.fixture(autouse=True)
def _no_real_alias_db(monkeypatch):
    monkeypatch.setattr(canonicalize.alias_store, "resolve", lambda name: None)
    monkeypatch.setattr(canonicalize.alias_store, "all_canonicals", lambda: [])


# ── _norm_key ────────────────────────────────────────────────────────────────


class TestNormKey:
    def test_lowercases(self):
        assert _norm_key("ABINADER") == "abinader"

    def test_strips_accents(self):
        assert _norm_key("Policía Nacional") == "policia nacional"

    def test_collapses_whitespace(self):
        assert _norm_key("  Luis   Abinader  ") == "luis abinader"

    def test_normalizes_hyphens_to_spaces(self):
        assert _norm_key("Jean-Claude") == _norm_key("Jean Claude")

    def test_strips_periods(self):
        assert _norm_key("P.R.M.") == _norm_key("PRM")


# ── _strip_title_prefix ──────────────────────────────────────────────────────


class TestStripTitlePrefix:
    def test_strips_known_title(self):
        assert _strip_title_prefix("Presidente Abinader") == "Abinader"

    def test_strips_accented_title(self):
        assert _strip_title_prefix("Monseñor Ramírez") == "Ramírez"

    def test_leaves_name_without_title_unchanged(self):
        assert _strip_title_prefix("Luis Abinader") == "Luis Abinader"

    def test_does_not_strip_single_word_title(self):
        # sin resto de nombre detrás, se conserva tal cual (mejor eso que vaciarlo)
        assert _strip_title_prefix("Presidente") == "Presidente"


# ── _apply_alias_catalog ─────────────────────────────────────────────────────


class TestApplyAliasCatalog:
    def test_renames_and_retypes_when_alias_matches(self, monkeypatch):
        monkeypatch.setattr(
            canonicalize.alias_store,
            "resolve",
            lambda name: ("Ministerio de Educación", "ORG") if name.strip().lower() == "minerd" else None,
        )
        entities = [EntityResult(name="MINERD", type="ORG", mentions_count=1)]
        _apply_alias_catalog(entities)
        assert entities[0].name == "Ministerio de Educación"
        assert entities[0].type == "ORG"

    def test_alias_type_overrides_wrong_detected_type(self, monkeypatch):
        # spaCy a veces marca "Impuestos Internos" como PERSON; el catálogo
        # de aliases tiene la última palabra.
        monkeypatch.setattr(
            canonicalize.alias_store,
            "resolve",
            lambda name: ("Dirección General de Impuestos Internos", "ORG"),
        )
        entities = [EntityResult(name="Impuestos Internos", type="PERSON", mentions_count=1)]
        _apply_alias_catalog(entities)
        assert entities[0].type == "ORG"

    def test_leaves_entity_unchanged_without_alias_match(self):
        entities = [EntityResult(name="Foo Bar", type="PERSON", mentions_count=1)]
        _apply_alias_catalog(entities)
        assert entities[0].name == "Foo Bar"
        assert entities[0].type == "PERSON"


# ── _resolve_partial_persons ─────────────────────────────────────────────────


class TestResolvePartialPersons:
    def test_resolves_single_word_person_to_unique_full_name(self):
        entities = [EntityResult(name="Abinader", type="PERSON", mentions_count=1)]
        _resolve_partial_persons(entities, {"abinader": "Luis Abinader"})
        assert entities[0].name == "Luis Abinader"

    def test_leaves_multi_word_names_untouched(self):
        entities = [EntityResult(name="Luis Abinader", type="PERSON", mentions_count=1)]
        _resolve_partial_persons(entities, {"abinader": "Luis Abinader"})
        assert entities[0].name == "Luis Abinader"

    def test_ignores_non_person_entities(self):
        entities = [EntityResult(name="Abinader", type="ORG", mentions_count=1)]
        _resolve_partial_persons(entities, {"abinader": "Luis Abinader"})
        assert entities[0].name == "Abinader"

    def test_no_op_when_surname_not_in_map(self):
        entities = [EntityResult(name="Fernández", type="PERSON", mentions_count=1)]
        _resolve_partial_persons(entities, {})  # apellido ambiguo, no está en el mapa
        assert entities[0].name == "Fernández"


# ── _merge_duplicates ─────────────────────────────────────────────────────────


class TestMergeDuplicates:
    def test_merges_short_name_into_longer_containing_name(self):
        entities = [
            EntityResult(
                name="Abinader", type="PERSON", mentions_count=5,
                sentiment_toward="POS", sentiment_score=0.9, context="corto",
            ),
            EntityResult(
                name="Luis Abinader", type="PERSON", mentions_count=2,
                sentiment_toward="NEG", sentiment_score=0.5, context="largo",
            ),
        ]
        result = _merge_duplicates(entities)
        assert len(result) == 1
        merged = result[0]
        assert merged.name == "Luis Abinader"
        assert merged.mentions_count == 7
        # El nombre más largo se procesa primero (target) y conserva SU
        # propio sentimiento; no lo pisa el de la variante corta.
        assert merged.sentiment_toward == "NEG"
        assert merged.context == "largo"

    def test_fills_in_sentiment_only_when_target_has_none(self):
        entities = [
            EntityResult(
                name="Ministerio de Educación", type="ORG", mentions_count=2,
                sentiment_toward=None, sentiment_score=None, context=None,
            ),
            EntityResult(
                name="Educación", type="ORG", mentions_count=1,
                sentiment_toward="NEU", sentiment_score=0.6, context="frase",
            ),
        ]
        result = _merge_duplicates(entities)
        assert len(result) == 1
        merged = result[0]
        assert merged.name == "Ministerio de Educación"
        assert merged.mentions_count == 3
        assert merged.sentiment_toward == "NEU"
        assert merged.sentiment_score == 0.6
        assert merged.context == "frase"

    def test_does_not_merge_across_different_types(self):
        entities = [
            EntityResult(name="Salud", type="ORG", mentions_count=1),
            EntityResult(name="Salud", type="PERSON", mentions_count=1),
        ]
        result = _merge_duplicates(entities)
        assert len(result) == 2

    def test_does_not_merge_unrelated_names(self):
        entities = [
            EntityResult(name="Luis Abinader", type="PERSON", mentions_count=1),
            EntityResult(name="Leonel Fernández", type="PERSON", mentions_count=1),
        ]
        result = _merge_duplicates(entities)
        assert len(result) == 2

    def test_merges_non_contiguous_partial_name_into_full_legal_name(self):
        # "Luis Abinader" no es subcadena contigua de "Luis Rodolfo Abinader
        # Corona" (Rodolfo se interpone) — el apellido materno que la prensa
        # omite queda al final, así que el chequeo de subcadena contigua no
        # los conecta. La fusión por palabras compartidas sí debe hacerlo.
        entities = [
            EntityResult(name="Luis Abinader", type="PERSON", mentions_count=5),
            EntityResult(name="Luis Rodolfo Abinader Corona", type="PERSON", mentions_count=1),
        ]
        result = _merge_duplicates(entities)
        assert len(result) == 1
        assert result[0].name == "Luis Rodolfo Abinader Corona"
        assert result[0].mentions_count == 6

    def test_does_not_merge_when_only_given_name_is_shared(self):
        # comparten "Juan Pablo" pero no el apellido: son personas distintas,
        # no debe fundirlas aunque una sea nombre parcial de la otra en teoría.
        entities = [
            EntityResult(name="Juan Pablo Duarte", type="PERSON", mentions_count=1),
            EntityResult(name="Juan Pablo Pichardo", type="PERSON", mentions_count=1),
        ]
        result = _merge_duplicates(entities)
        assert len(result) == 2

    def test_does_not_merge_ambiguous_shared_name_across_multiple_candidates(self):
        # "Luis Abinader" es subconjunto de dos nombres largos distintos:
        # ambiguo, no se debe fundir con ninguno.
        entities = [
            EntityResult(name="Luis Abinader", type="PERSON", mentions_count=1),
            EntityResult(name="Luis Alberto Abinader", type="PERSON", mentions_count=1),
            EntityResult(name="Luis Fernando Abinader", type="PERSON", mentions_count=1),
        ]
        result = _merge_duplicates(entities)
        assert len(result) == 3

    def test_does_not_apply_partial_name_merge_to_org(self):
        entities = [
            EntityResult(name="Banco Popular", type="ORG", mentions_count=1),
            EntityResult(name="Banco Popular Dominicano Multiple", type="ORG", mentions_count=1),
        ]
        # "banco popular" SÍ es subcadena contigua de "banco popular
        # dominicano multiple", así que esto se funde por la regla existente
        # (no por la nueva de PERSON) — control de que ORG sigue funcionando.
        result = _merge_duplicates(entities)
        assert len(result) == 1


# ── canonicalize_entities (integración de los pasos, sin BD) ────────────────


class TestCanonicalizeEntities:
    def test_full_pipeline_merges_partial_and_full_name(self):
        raw = [
            EntityResult(name="Abinader", type="PERSON", mentions_count=3, sentiment_toward="POS"),
            EntityResult(name="   Luis   Abinader  ", type="PERSON", mentions_count=1, sentiment_toward="NEG"),
        ]
        result = canonicalize_entities(raw, person_map={"abinader": "Luis Abinader"})
        assert len(result) == 1
        assert result[0].name == "Luis Abinader"
        assert result[0].mentions_count == 4

    def test_strips_title_prefix_before_merging(self):
        raw = [
            EntityResult(name="Presidente Abinader", type="PERSON", mentions_count=1),
            EntityResult(name="Luis Abinader", type="PERSON", mentions_count=3),
        ]
        result = canonicalize_entities(raw, person_map={})
        assert len(result) == 1
        assert result[0].name == "Luis Abinader"
        assert result[0].mentions_count == 4

    def test_drops_entities_with_blank_name(self):
        raw = [
            EntityResult(name="   ", type="PERSON", mentions_count=1),
            EntityResult(name="Real Nombre", type="PERSON", mentions_count=1),
        ]
        result = canonicalize_entities(raw, person_map={})
        assert [e.name for e in result] == ["Real Nombre"]

    def test_computes_person_map_when_not_provided(self, monkeypatch, sqlite_sessionmaker):
        session = sqlite_sessionmaker()
        session.add(Entity(article_id=1, name="Luis Abinader", type="PERSON", mentions_count=1))
        session.commit()
        session.close()
        monkeypatch.setattr(db_session_module, "get_session", sqlite_sessionmaker)

        raw = [EntityResult(name="Abinader", type="PERSON", mentions_count=1)]
        result = canonicalize_entities(raw)
        assert result[0].name == "Luis Abinader"


# ── known_person_fullname_map ────────────────────────────────────────────────


class TestKnownPersonFullnameMap:
    def test_resolves_unique_surname_and_skips_ambiguous(self, monkeypatch, sqlite_sessionmaker):
        session = sqlite_sessionmaker()
        session.add_all([
            Entity(article_id=1, name="Luis Abinader", type="PERSON", mentions_count=1),
            Entity(article_id=1, name="Leonel Fernández", type="PERSON", mentions_count=1),
            Entity(article_id=1, name="Omar Fernández", type="PERSON", mentions_count=1),
            Entity(article_id=1, name="Acme Corp", type="ORG", mentions_count=1),
        ])
        session.commit()
        session.close()
        monkeypatch.setattr(db_session_module, "get_session", sqlite_sessionmaker)

        result = known_person_fullname_map()

        assert result["abinader"] == "Luis Abinader"
        assert "fernandez" not in result  # dos personas distintas: ambiguo
        assert "acme" not in result  # ORG, no PERSON

    def test_returns_empty_when_db_unavailable(self, monkeypatch):
        def _broken_get_session():
            raise RuntimeError("sin conexión")

        monkeypatch.setattr(db_session_module, "get_session", _broken_get_session)
        assert known_person_fullname_map() == {}


# ── match_actor_name ──────────────────────────────────────────────────────────


class TestMatchActorName:
    def test_none_and_blank_return_none(self):
        assert match_actor_name(None, []) is None
        assert match_actor_name("   ", []) is None

    def test_matches_substring_of_known_entity(self):
        entities = [EntityResult(name="Luis Abinader", type="PERSON", mentions_count=1)]
        assert match_actor_name("Abinader", entities) == "Luis Abinader"

    def test_returns_name_unchanged_when_no_entity_matches(self):
        entities = [EntityResult(name="Luis Abinader", type="PERSON", mentions_count=1)]
        assert match_actor_name("Nombre Desconocido", entities) == "Nombre Desconocido"

    def test_resolves_alias_before_matching(self, monkeypatch):
        monkeypatch.setattr(
            canonicalize.alias_store,
            "resolve",
            lambda name: ("Partido Revolucionario Moderno", "ORG") if name.strip().lower() == "prm" else None,
        )
        entities = [EntityResult(name="Partido Revolucionario Moderno", type="ORG", mentions_count=1)]
        assert match_actor_name("PRM", entities) == "Partido Revolucionario Moderno"
