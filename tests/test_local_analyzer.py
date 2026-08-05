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
    LocalAnalyzer,
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


class TestEntitySentimentBoost:
    """`_entities()` recibe `probas_by_index` ya calculado (no llama a
    pysentimiento), así que se puede probar con probabilidades neutrales
    fabricadas a mano — solo se ejercita spaCy (NER + segmentación) y el
    léxico relacional de analysis/sentiment_lexicon.py."""

    # Probabilidades base "cerca del límite" (NEU apenas por delante de NEG):
    # así el boost de 0.12 (analysis/sentiment_lexicon.BOOST) alcanza para
    # voltear la etiqueta cuando SÍ hay patrón relacional, y no cuando no lo
    # hay — igual que se espera que se comporte con predicciones reales de
    # pysentimiento cerca del límite.
    _NEG_LEANING = {"NEG": 0.40, "NEU": 0.45, "POS": 0.15}
    _POS_LEANING = {"POS": 0.40, "NEU": 0.45, "NEG": 0.15}

    @staticmethod
    def _run(nlp, text: str, default: dict[str, float]):
        doc = nlp(text)
        sents = list(doc.sents)
        probas_by_index = [dict(default) for _ in sents]
        start_to_index = {s.start_char: i for i, s in enumerate(sents)}
        results = LocalAnalyzer()._entities(doc, probas_by_index, start_to_index)
        return {e.name: e for e in results}

    def test_accused_entity_leans_negative(self, nlp):
        entities = self._run(
            nlp,
            "El senador Ramón Pérez fue acusado de corrupción por el fiscal.",
            self._NEG_LEANING,
        )
        assert entities["Ramón Pérez"].sentiment_toward == "NEG"

    def test_recognized_entity_leans_positive(self, nlp):
        entities = self._run(
            nlp,
            "La alcaldesa Rosa Martínez fue reconocida por su gestión municipal.",
            self._POS_LEANING,
        )
        assert entities["Rosa Martínez"].sentiment_toward == "POS"

    def test_plain_mention_stays_neutral(self, nlp):
        entities = self._run(
            nlp,
            "El senador Ramón Pérez asistió a la sesión ordinaria del Congreso.",
            self._NEG_LEANING,
        )
        assert entities["Ramón Pérez"].sentiment_toward == "NEU"

    def test_relation_boost_is_scoped_to_the_mentioned_entity(self, nlp):
        # "acusado de" describe a Pérez en una frase; Martínez solo aparece en
        # otra frase sin patrón — no debe heredar el sentimiento negativo de Pérez.
        text = (
            "El senador Ramón Pérez fue acusado de corrupción. "
            "Rosa Martínez presidió la sesión del ayuntamiento."
        )
        entities = self._run(nlp, text, self._NEG_LEANING)
        assert entities["Ramón Pérez"].sentiment_toward == "NEG"
        assert entities["Rosa Martínez"].sentiment_toward == "NEU"
