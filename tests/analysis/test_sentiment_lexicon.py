"""Pruebas de odin/analysis/sentiment_lexicon.py: el glosario de refuerzo de
sentimiento compartido por LocalAnalyzer y los analizadores basados en LLM.

Solo importa analysis.text_norm (sin spaCy/pysentimiento/torch): rápido y sin
dependencias pesadas.
"""
from __future__ import annotations

from odin.analysis.sentiment_lexicon import (
    PROMPT_GLOSSARY,
    apply_boost,
    apply_entity_relation_boost,
    apply_negation_dampening,
    dampen_negated,
    entity_relation_label,
    has_negation_cue,
    lexicon_label,
    lexicon_matches,
)


class TestLexiconLabel:
    def test_negative_term_returns_neg(self):
        assert lexicon_label("El funcionario fue acusado de corrupción.") == "NEG"

    def test_negative_term_ignores_accents_and_case(self):
        assert lexicon_label("CASO DE CORRUPCION en el ayuntamiento") == "NEG"

    def test_positive_term_returns_pos(self):
        assert lexicon_label("Las partes alcanzaron un consenso histórico.") == "POS"

    def test_multiword_term_matches_as_phrase(self):
        assert lexicon_label("Se decretó prisión preventiva contra el exfuncionario.") == "NEG"

    def test_no_match_returns_none(self):
        assert lexicon_label("El presidente visitó una escuela primaria hoy.") is None

    def test_contradictory_match_returns_none(self):
        # Frase con vocabulario de ambos lados: no forzar una etiqueta.
        text = "Tras el escándalo de corrupción, el gobierno prometió transparencia."
        assert lexicon_label(text) is None

    def test_partial_word_does_not_match(self):
        # "corruptible" no es "corrupto"/"corrupción": el boundary \b no debe matchear substrings.
        assert lexicon_label("Un sistema corruptible en teoría, según el informe.") is None

    def test_generic_crime_desk_words_are_not_in_lexicon(self):
        # "prisión"/"cárcel"/"detenido" solos son vocabulario de sucesos
        # genérico (ambiguo sin sujeto ni contexto), deliberadamente excluido
        # del léxico general para no generar falsos positivos en cualquier
        # nota de crimen común.
        assert lexicon_label("Fue trasladado a la cárcel local esta mañana.") is None
        assert lexicon_label("El detenido declaró ante el juez.") is None


class TestEntityRelationLabel:
    def test_accused_pattern_is_negative(self):
        assert entity_relation_label("El diputado fue acusado de malversación.") == "NEG"

    def test_recognized_pattern_is_positive(self):
        assert entity_relation_label("La alcaldesa fue reconocida por su gestión.") == "POS"

    def test_plain_mention_has_no_relation(self):
        assert entity_relation_label("El diputado asistió a la sesión del Congreso.") is None

    def test_does_not_overlap_with_general_lexicon_terms(self):
        # "corrupción" sola (sin patrón relacional) no debe activar este léxico.
        assert entity_relation_label("El caso de corrupción sigue en investigación.") is None


class TestApplyBoost:
    def test_boosts_neg_and_renormalizes(self):
        probas = {"NEG": 0.3, "NEU": 0.4, "POS": 0.3}
        boosted = apply_boost("Escándalo de soborno en el ministerio.", probas)
        assert boosted["NEG"] > probas["NEG"]
        assert abs(sum(boosted.values()) - 1.0) < 1e-9

    def test_no_match_is_noop(self):
        probas = {"NEG": 0.3, "NEU": 0.4, "POS": 0.3}
        assert apply_boost("El presidente visitó una escuela primaria hoy.", probas) == probas

    def test_boost_does_not_exceed_one(self):
        probas = {"NEG": 0.95, "NEU": 0.03, "POS": 0.02}
        boosted = apply_boost("Nuevo caso de desfalco en el ayuntamiento.", probas)
        assert boosted["NEG"] <= 1.0
        assert abs(sum(boosted.values()) - 1.0) < 1e-9


class TestApplyEntityRelationBoost:
    def test_boosts_neg_for_accused_pattern(self):
        probas = {"NEG": 0.3, "NEU": 0.4, "POS": 0.3}
        boosted = apply_entity_relation_boost(
            "El senador fue acusado de tráfico de influencias.", probas
        )
        assert boosted["NEG"] > probas["NEG"]
        assert abs(sum(boosted.values()) - 1.0) < 1e-9

    def test_boosts_pos_for_recognized_pattern(self):
        probas = {"NEG": 0.3, "NEU": 0.4, "POS": 0.3}
        boosted = apply_entity_relation_boost(
            "El ministro fue felicitado por el resultado.", probas
        )
        assert boosted["POS"] > probas["POS"]

    def test_no_relation_pattern_is_noop(self):
        probas = {"NEG": 0.3, "NEU": 0.4, "POS": 0.3}
        text = "El senador participó en la sesión ordinaria del Congreso."
        assert apply_entity_relation_boost(text, probas) == probas


class TestLexiconMatches:
    def test_reports_matched_terms_by_bucket(self):
        text = "El diputado, acusado de corrupción, fue reconocido por su labor previa."
        matches = lexicon_matches(text)
        assert "corrupcion" in matches["NEG"]
        assert "acusado de" in matches["ENTITY_NEG"]
        assert "reconocido por" in matches["ENTITY_POS"]

    def test_no_matches_returns_empty_lists(self):
        matches = lexicon_matches("El presidente visitó una escuela primaria hoy.")
        assert matches == {"NEG": [], "POS": [], "ENTITY_NEG": [], "ENTITY_POS": []}


class TestPromptGlossary:
    def test_is_nonempty_and_mentions_polarities(self):
        assert "NEGATIVOS" in PROMPT_GLOSSARY
        assert "POSITIVOS" in PROMPT_GLOSSARY
        assert "corrupcion" in PROMPT_GLOSSARY

    def test_warns_against_conflating_event_and_entity_sentiment(self):
        assert "CADA entidad" in PROMPT_GLOSSARY


class TestHasNegationCue:
    def test_detects_common_denial_phrases(self):
        assert has_negation_cue(
            "No hay apagones, no podemos hablar de apagones sino de sobrecarga"
        )
        assert has_negation_cue("El funcionario negó las acusaciones en su contra")
        assert has_negation_cue("Nosotros no damos apagones de noche")

    def test_plain_statement_has_no_negation_cue(self):
        assert not has_negation_cue("Hubo un apagón anoche en el sector Los Ríos")


class TestDampenNegated:
    def test_pulls_probabilities_toward_neutral(self):
        probas = {"NEG": 0.7, "NEU": 0.2, "POS": 0.1}
        dampened = dampen_negated(probas, negated=True)
        assert dampened["NEG"] < probas["NEG"]
        assert abs(sum(dampened.values()) - 1.0) < 1e-9

    def test_noop_when_not_negated(self):
        probas = {"NEG": 0.7, "NEU": 0.2, "POS": 0.1}
        assert dampen_negated(probas, negated=False) == probas


class TestApplyNegationDampening:
    def test_dampens_when_text_has_negation_cue(self):
        probas = {"NEG": 0.7, "NEU": 0.2, "POS": 0.1}
        result = apply_negation_dampening("No hay irregularidades en el proceso", probas)
        assert result["NEG"] < probas["NEG"]

    def test_noop_when_no_negation_cue(self):
        probas = {"NEG": 0.7, "NEU": 0.2, "POS": 0.1}
        assert apply_negation_dampening("Hubo un escándalo en el ministerio", probas) == probas
