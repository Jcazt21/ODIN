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
    _aggregate_document,
    _aggregate_entity,
    _best_display_name,
    _extraction_confidence,
    _is_institution_head,
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

    def test_ignores_nickname_spliced_in_middle_of_name(self):
        # Regresión odin-db-040 (golden set): el artículo escribe el nombre
        # una vez como "Eduardo -Yayo- Sanz Lovatón" (apodo entre guiones,
        # patrón típico del periodismo dominicano) y tres veces como "Sanz
        # Lovatón". El gold es "Eduardo Sanz Lovatón": la variante con
        # apodo insertado tiene más palabras "significativas" en bruto (4
        # contra 2), pero ese conteo extra viene de "Yayo", no de una
        # extensión real del nombre, y romper el guion en medio hace que
        # scripts/evaluate.py:_names_match dejara de reconocerla como el
        # mismo nombre que el gold. "Sanz Lovatón" debe ganar.
        display = Counter({"Eduardo -Yayo- Sanz Lovatón": 1, "Sanz Lovatón": 3})
        assert _best_display_name(display) == "Sanz Lovatón"

    def test_does_not_confuse_two_hyphenated_surnames_with_a_spliced_nickname(self):
        # Falso positivo encontrado en revisión: sin anclar la alternativa de
        # guiones a límites de espacio/cadena, el guión de cierre de
        # "Jean-Claude" se emparejaba con el guión de apertura de
        # "Pérez-Gómez" (un apellido compuesto distinto, más adelante en el
        # mismo nombre), tragándose "Claude Pérez" como si fuera un apodo
        # insertado y dejando ganar por default al nombre truncado — la
        # misma clase de bug que esta regla existe para evitar, disparada de
        # otra forma. "Jean-Claude Pérez-Gómez" no tiene ningún apodo
        # insertado: debe ganarle a "Pérez-Gómez" por tener más palabras.
        display = Counter({"Jean-Claude Pérez-Gómez": 1, "Pérez-Gómez": 3})
        assert _best_display_name(display) == "Jean-Claude Pérez-Gómez"


# distribuciones de referencia para las dos agregaciones. No salen de ninguna
# frase real: son formas de distribución (tibia-neutra / claramente polar) que
# reproducen el patrón medido en el golden set.
_WEAK_NEU = {"POS": 0.30, "NEG": 0.20, "NEU": 0.50}
_STRONG_POS = {"POS": 0.80, "NEG": 0.05, "NEU": 0.15}
_STRONG_NEG = {"POS": 0.05, "NEG": 0.80, "NEU": 0.15}


class TestAggregateDocument:
    """`_aggregate_document` descuenta la tasa base por clase para que un
    artículo no colapse a NEU solo por acumular frases tibias — el mecanismo
    real detrás del 59.5% de accuracy medido (ver su docstring)."""

    def test_polar_signal_survives_a_majority_of_weak_neutral_sentences(self):
        probas = [_WEAK_NEU] * 8 + [_STRONG_POS] * 2
        # la media plana da NEU aquí (0.43 NEU vs. 0.40 POS): es exactamente el
        # caso que la agregación vieja perdía
        assert _aggregate_document(probas)[0] == "POS"

    def test_genuinely_neutral_article_stays_neutral(self):
        assert _aggregate_document([{"POS": 0.15, "NEG": 0.15, "NEU": 0.70}] * 6)[0] == "NEU"

    def test_score_is_the_raw_mean_of_the_winning_label(self):
        label, score = _aggregate_document([_WEAK_NEU] * 8 + [_STRONG_POS] * 2)
        assert label == "POS"
        assert score == 0.4  # (8*0.30 + 2*0.80) / 10, sin tocar por el prior

    def test_unscored_sentences_are_ignored(self):
        assert _aggregate_document([None, _STRONG_NEG, None])[0] == "NEG"

    def test_empty_input_is_neutral(self):
        assert _aggregate_document([]) == ("NEU", 0.0)


class TestAggregateEntity:
    """`_aggregate_entity` exige corroboración antes de atribuir una etiqueta
    polar a una entidad: el fallo medido es sobre-emisión (48 de 73 etiquetas
    polares caían sobre entidades cuyo gold era NEU), no error de signo."""

    def test_a_single_polar_sentence_is_not_enough(self):
        assert _aggregate_entity([_STRONG_NEG])[0] == "NEU"

    def test_two_agreeing_polar_sentences_assign_the_label(self):
        assert _aggregate_entity([_STRONG_NEG, _STRONG_NEG])[0] == "NEG"

    def test_polar_sentences_that_disagree_fall_back_to_neutral(self):
        # la media da POS (0.45 vs. 0.375 NEG), pero solo UNA frase la respalda
        mid_neg = {"POS": 0.10, "NEG": 0.70, "NEU": 0.20}
        assert _aggregate_entity([_STRONG_POS, mid_neg])[0] == "NEU"

    def test_neutral_needs_no_corroboration(self):
        assert _aggregate_entity([{"POS": 0.20, "NEG": 0.20, "NEU": 0.60}])[0] == "NEU"

    def test_does_not_apply_the_document_prior_correction(self):
        # una sola frase tibia hacia NEU: `_aggregate_document` la sacaría de
        # NEU por el descuento de prior, `_aggregate_entity` NO debe hacerlo
        assert _aggregate_document([_WEAK_NEU])[0] == "POS"
        assert _aggregate_entity([_WEAK_NEU])[0] == "NEU"


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


class TestInstitutionHeadPromotion:
    """spaCy etiqueta "Gobierno" como LOC en la mayoría de los casos (medido:
    25 LOC vs. 2 ORG), y por eso quitarlo de `_GENERIC_STATE_ORGS` en
    2026-08-14 no bastó — ese filtro solo actúa sobre spans ya marcados ORG.
    Era el falso negativo individual más grande de ORG (11 de 48)."""

    @staticmethod
    def _org_names(nlp, text: str) -> set[str]:
        doc = nlp(text)
        sentences = _Sentences.from_doc(doc)
        probas_by_index = [None for _ in sentences.texts]
        entities = LocalAnalyzer()._entities(doc, probas_by_index, sentences)
        return {e.name for e in entities if e.type == "ORG"}

    def test_bare_gobierno_is_promoted_to_org(self, nlp):
        orgs = self._org_names(
            nlp, "El Gobierno anunció un nuevo programa de subsidios para el sector agrícola."
        )
        assert "Gobierno" in orgs

    def test_gobierno_with_complement_is_promoted(self, nlp):
        orgs = self._org_names(
            nlp, "El Gobierno de Venezuela respondió a las declaraciones del canciller."
        )
        assert any(o.startswith("Gobierno") for o in orgs)

    def test_head_matching_is_anchored_to_whole_words(self):
        # "gobernabilidad" empieza con "gob" pero NO es la cabeza "gobierno":
        # el prefijo debe exigir límite de palabra, no coincidencia parcial
        assert _is_institution_head("gobierno")
        assert _is_institution_head("gobierno de venezuela")
        assert not _is_institution_head("gobernabilidad democratica")
        assert not _is_institution_head("gobiernos locales")


class TestSeedAliasResolution:
    """Siglas del catálogo curado (db/seed_aliases.py) se resuelven al
    nombre canónico SIN necesitar que el artículo escriba el nombre
    completo — medido en el golden set: odin-db-008/012 solo dicen "PLD"
    en todo el cuerpo (ver tests/eval/golden_set.jsonl)."""

    @staticmethod
    def _org_names(nlp, text: str) -> set[str]:
        doc = nlp(text)
        sentences = _Sentences.from_doc(doc)
        probas_by_index = [None for _ in sentences.texts]
        entities = LocalAnalyzer()._entities(doc, probas_by_index, sentences)
        return {e.name for e in entities if e.type == "ORG"}

    def test_acronym_only_mention_resolves_to_canonical_name(self, nlp):
        orgs = self._org_names(nlp, "El vicepresidente del PLD, Iván Lorenzo, habló ayer.")
        assert "Partido de la Liberación Dominicana" in orgs
        assert "PLD" not in orgs

    def test_silabic_acronym_not_derivable_from_initials_resolves(self, nlp):
        orgs = self._org_names(
            nlp, "El ITLA anunció nuevas becas técnicas para el próximo semestre."
        )
        assert "Instituto Tecnológico de Las Américas" in orgs
        assert "ITLA" not in orgs


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
