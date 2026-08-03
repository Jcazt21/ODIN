"""Pruebas de analysis/local_analyzer.py sobre las heurísticas de lugar vs.
persona: usan el modelo real de spaCy (es_core_news_lg, ya instalado
localmente) porque el comportamiento depende de su parser de dependencias y
POS-tagging — no tiene sentido mockearlo para estas pruebas puntuales.

No llama a pysentimiento ni a Gemini: solo se ejercitan las funciones a nivel
de token/entidad, sin pasar por LocalAnalyzer.analyze().
"""
from __future__ import annotations

import pytest

pytest.importorskip("spacy")

from analysis.local_analyzer import (
    _extraction_confidence,
    _is_named_after_place,
    _norm_key,
    _preceded_by_venue_noun,
)


@pytest.fixture(scope="module")
def nlp():
    import spacy

    try:
        return spacy.load("es_core_news_lg")
    except OSError:
        pytest.skip("modelo es_core_news_lg no instalado")


def _person_ents(doc):
    return [ent for ent in doc.ents if ent.label_ == "PER"]


class TestNormKey:
    def test_normalizes_hyphens_to_spaces(self):
        assert _norm_key("Jean-Claude") == _norm_key("Jean Claude")

    def test_strips_periods(self):
        assert _norm_key("P.R.M.") == _norm_key("PRM")


class TestExtractionConfidence:
    def test_full_name_multiple_mentions_is_full_confidence(self):
        assert _extraction_confidence("Luis Abinader", "PERSON", count=5) == 1.0

    def test_single_mention_lowers_confidence(self):
        assert _extraction_confidence("Luis Abinader", "PERSON", count=1) < 1.0

    def test_partial_person_name_lowers_confidence(self):
        assert _extraction_confidence("Abinader", "PERSON", count=5) < 1.0

    def test_partial_name_and_single_mention_stack(self):
        both = _extraction_confidence("Abinader", "PERSON", count=1)
        only_partial = _extraction_confidence("Abinader", "PERSON", count=5)
        only_single = _extraction_confidence("Luis Abinader", "PERSON", count=1)
        assert both < only_partial
        assert both < only_single

    def test_org_names_are_not_penalized_for_being_one_word(self):
        # "unidad" no cuenta como nombre parcial ambiguo para ORG, solo PERSON
        assert _extraction_confidence("MINERD", "ORG", count=5) == 1.0

    def test_never_goes_below_floor(self):
        assert _extraction_confidence("X", "PERSON", count=1) >= 0.1


class TestVenueHeuristics:
    def test_homenaje_a_pattern_is_caught_by_linear_window(self, nlp):
        # No hace falta un heurístico nuevo para "homenaje a"/"en honor a":
        # esas palabras ya están en _VENUE_WORDS y quedan a 1-2 tokens de la
        # entidad, dentro de la ventana lineal existente.
        doc = nlp(
            "Danilo Medina participó en el homenaje a Juan Pablo Duarte "
            "por su aniversario."
        )
        ents = {ent.text: ent for ent in _person_ents(doc)}
        assert not _preceded_by_venue_noun(ents["Danilo Medina"])
        assert _preceded_by_venue_noun(ents["Juan Pablo Duarte"])

    def test_en_honor_a_pattern_is_caught_by_linear_window(self, nlp):
        doc = nlp(
            "El acto se realizó en honor a Juan Pablo Duarte, prócer de la "
            "independencia."
        )
        ents = _person_ents(doc)
        assert any(
            _preceded_by_venue_noun(ent) for ent in ents if ent.text == "Juan Pablo Duarte"
        )

    def test_new_venue_words_catch_dominican_press_patterns(self, nlp):
        cases = [
            "El acto se celebró en el despacho de Ramón Pérez.",
            "La denuncia fue presentada ante el tribunal de Marcos Villamán.",
        ]
        for text in cases:
            doc = nlp(text)
            ents = _person_ents(doc)
            assert ents, f"spaCy no detectó PERSON en: {text}"
            assert any(
                _preceded_by_venue_noun(ent) or _is_named_after_place(ent)
                for ent in ents
            ), f"no se detectó patrón de lugar/venue en: {text}"
