"""Pruebas de analysis/entity_verify.py: el contraste de las entidades que
devuelve un LLM contra el texto real del artículo.

Sin red ni modelos: se construyen `EntityResult` a mano, que es exactamente lo
que `_result_from_llm` le pasa a estas funciones.
"""
from __future__ import annotations

from analysis.base import EntityResult
from analysis.entity_verify import recount_mentions, verify_entities

TEXTO = (
    "Abinader anunció el plan de emergencia. El Ministerio de Salud Pública lo "
    "ejecutará desde el lunes. Luis Abinader insistió en que no habrá retrasos y "
    "Abinader pidió calma a la población."
)


def _entity(name: str, etype: str = "PERSON", *, mentions: int = 1, confidence: float = 1.0):
    return EntityResult(
        name=name, type=etype, mentions_count=mentions, extraction_confidence=confidence
    )


class TestVerifyEntities:
    def test_keeps_entity_that_appears_literally(self):
        entities = [_entity("Ministerio de Salud Pública", "ORG")]
        assert verify_entities(entities, TEXTO) == entities

    def test_drops_entity_with_no_trace_in_the_text(self):
        # El caso que esto existe para atajar: el modelo devuelve una
        # organización plausible que el artículo nunca menciona.
        kept = verify_entities([_entity("Partido Revolucionario Moderno", "ORG")], TEXTO)
        assert kept == []

    def test_expanded_name_survives_but_loses_confidence(self):
        # "Luis Abinader" sí está literal; probamos el caso de una expansión
        # que NO está completa en el texto (el prompt pide el nombre canónico).
        entity = _entity("Raquel Peña", confidence=0.95)
        texto = "La vicepresidenta Peña encabezó el acto en Santiago."
        kept = verify_entities([entity], texto)
        assert kept == [entity]
        assert entity.extraction_confidence == 0.6

    def test_does_not_raise_confidence_of_an_already_doubtful_entity(self):
        entity = _entity("Raquel Peña", confidence=0.3)
        verify_entities([entity], "La vicepresidenta Peña encabezó el acto.")
        assert entity.extraction_confidence == 0.3

    def test_ignores_accents_and_case(self):
        kept = verify_entities([_entity("MINISTERIO DE SALUD PUBLICA", "ORG")], TEXTO)
        assert len(kept) == 1

    def test_matches_a_name_split_across_lines(self):
        texto = "El ministro Víctor\nAtallah encabezó la rueda de prensa."
        assert len(verify_entities([_entity("Víctor Atallah")], texto)) == 1


class TestRecountMentions:
    def test_person_is_counted_by_surname_covering_partial_mentions(self):
        # "Abinader" x2 + "Luis Abinader" x1 = 3 menciones de la misma persona;
        # el LLM había estimado 1.
        entity = _entity("Luis Abinader", mentions=1)
        recount_mentions([entity], TEXTO)
        assert entity.mentions_count == 3

    def test_org_is_counted_by_full_name_including_particles(self):
        entity = _entity("Ministerio de Salud Pública", "ORG", mentions=5)
        recount_mentions([entity], TEXTO)
        assert entity.mentions_count == 1

    def test_org_is_not_counted_by_its_individual_words(self):
        # "salud" aparece suelta varias veces sin ser una mención al ministerio.
        texto = "El ministerio habló de salud. La salud pública preocupa. Salud para todos."
        entity = _entity("Ministerio de Salud Pública", "ORG", mentions=1)
        recount_mentions([entity], texto)
        assert entity.mentions_count == 1

    def test_keeps_the_model_estimate_when_the_name_is_not_literal(self):
        # Sin ninguna aparición literal no hay nada que contar: se respeta lo
        # que dijo el modelo en vez de forzar un 0.
        entity = _entity("Luis Rodolfo Abinader Corona", mentions=4)
        recount_mentions([entity], "El presidente encabezó el acto.")
        assert entity.mentions_count == 4

    def test_does_not_count_a_surname_inside_a_longer_word(self):
        entity = _entity("Juan Paz", mentions=1)
        recount_mentions([entity], "Juan Paz habló de la pazguatería del debate.")
        assert entity.mentions_count == 1
