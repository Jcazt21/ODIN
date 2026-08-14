"""Pruebas de analysis/local_analyzer.py sobre las heurísticas de lugar vs.
persona: usan el modelo real de spaCy (es_core_news_lg, ya instalado
localmente) porque el comportamiento depende de su parser de dependencias y
POS-tagging — no tiene sentido mockearlo para estas pruebas puntuales.

No llama a pysentimiento ni a Gemini: solo se ejercitan las funciones a nivel
de token/entidad, sin pasar por LocalAnalyzer.analyze().
"""
from __future__ import annotations

from collections import Counter

import pytest

pytest.importorskip("spacy")

from odin.analysis.local_analyzer import (
    LocalAnalyzer,
    _best_display_name,
    _extraction_confidence,
    _is_named_after_place,
    _norm_key,
    _preceded_by_venue_noun,
    _Sentences,
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


class TestBestDisplayName:
    def test_prefers_full_name_over_more_frequent_acronym(self):
        display = Counter({"PLD": 5, "Partido de la Liberación Dominicana": 1})
        assert _best_display_name(display) == "Partido de la Liberación Dominicana"

    def test_falls_back_to_most_common_on_tied_word_count(self):
        display = Counter({"Luis Abinader": 1, "Rafael Abinader": 3})
        assert _best_display_name(display) == "Rafael Abinader"

    def test_single_candidate_is_returned_unchanged(self):
        display = Counter({"MINERD": 3})
        assert _best_display_name(display) == "MINERD"


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


class TestGenericStateOrgFilter:
    """`_GENERIC_STATE_ORGS` filtra "República"/"Estado"/etc. sueltos, pero
    NO "Gobierno" — 12 de 131 entidades ORG del golden set son literalmente
    "Gobierno" (tests/eval/golden_set.jsonl) y el filtro viejo las perdía
    todas (verificado en vivo, ver local_analyzer.py:54-69)."""

    @staticmethod
    def _org_names(nlp, text: str) -> set[str]:
        doc = nlp(text)
        sentences = _Sentences.from_doc(doc)
        probas_by_index = [None for _ in sentences.texts]
        entities = LocalAnalyzer()._entities(doc, probas_by_index, sentences)
        return {e.name for e in entities if e.type == "ORG"}

    def test_gobierno_is_extracted_as_an_org_entity(self, nlp):
        orgs = self._org_names(
            nlp, "La Fuerza del Pueblo presentó sus críticas y propuestas frente al Gobierno."
        )
        assert "Gobierno" in orgs

    def test_bare_estado_is_still_filtered(self, nlp):
        orgs = self._org_names(
            nlp, "La Fuerza del Pueblo presentó sus críticas y propuestas frente al Estado."
        )
        assert "Estado" not in orgs


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
    def _run(nlp, text: str, default: dict[str, float] | None):
        doc = nlp(text)
        sentences = _Sentences.from_doc(doc)
        probas_by_index = [dict(default) if default else None for _ in sentences.texts]
        results = LocalAnalyzer()._entities(doc, probas_by_index, sentences)
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

    def test_accuser_in_the_same_sentence_does_not_get_the_boost(self, nlp):
        # El patrón relacional se lo lleva la mención que lo precede (el
        # acusado), no el agente que va después: acusar a alguien no deja mal
        # parado a quien acusa. Con una sola etiqueta por frase, ambos caían
        # en NEG.
        text = (
            "Ramón Pérez fue acusado de corrupción por la Procuraduría "
            "General de la República."
        )
        entities = self._run(nlp, text, self._NEG_LEANING)
        assert entities["Ramón Pérez"].sentiment_toward == "NEG"
        procuraduria = next(e for name, e in entities.items() if "Procuraduría" in name)
        assert procuraduria.sentiment_toward == "NEU"

    def test_opposite_patterns_on_the_same_entity_cancel_out(self, nlp):
        # Señal contradictoria en la misma frase: no se fuerza ninguna
        # dirección (mismo criterio que `lexicon_label`).
        text = "Ramón Pérez, acusado de corrupción y reconocido por su gestión, habló ayer."
        entities = self._run(nlp, text, self._NEG_LEANING)
        assert entities["Ramón Pérez"].sentiment_toward == "NEU"

    def test_entity_without_scored_sentences_has_no_opinion(self, nlp):
        # Sin probabilidades para ninguna de sus frases (p.ej. menciones más
        # allá de _MAX_SENTENCES) el sentimiento es None, no un "NEU 0.0" que
        # no se distingue de un neutro real.
        entities = self._run(nlp, "El senador Ramón Pérez asistió a la sesión.", None)
        assert entities["Ramón Pérez"].sentiment_toward is None
        assert entities["Ramón Pérez"].sentiment_score is None


class TestAnalyzeTopics:
    """`HybridAnalyzer` solo usa tema y palabras clave de este analizador; el
    resto del pipeline local (NER + pysentimiento sobre cada frase) era trabajo
    que se hacía para tirarlo."""

    _TEXTO = (
        "El Ministerio de Salud amplía el plan de agua potable. "
        "El plan de agua potable llegará a 30 mil familias este año. "
        "Las obras de agua potable comenzaron en marzo."
    )

    def test_does_not_load_the_sentiment_model(self, nlp, monkeypatch):
        analyzer = LocalAnalyzer()
        monkeypatch.setattr(type(analyzer), "nlp", property(lambda self: nlp))

        analyzer.analyze_topics("Agua potable", self._TEXTO)

        # Tocar `analyzer.sent` lo cargaría; que siga en None prueba que este
        # camino no pasa por pysentimiento.
        assert analyzer._sent is None

    def test_returns_the_same_topic_as_the_full_analysis(self, nlp, monkeypatch):
        analyzer = LocalAnalyzer()
        monkeypatch.setattr(type(analyzer), "nlp", property(lambda self: nlp))

        main_topic, keywords = analyzer.analyze_topics("Agua potable", self._TEXTO)

        doc = nlp(f"Agua potable.\n\n{self._TEXTO}".strip())
        expected_keywords = analyzer._keywords(doc)
        assert keywords == expected_keywords
        assert main_topic == analyzer._main_topic(doc, expected_keywords)
