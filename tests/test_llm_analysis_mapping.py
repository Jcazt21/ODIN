"""Pruebas del contrato entre la respuesta de un LLM y `AnalysisResult`
(`analysis/gemini_analyzer.py`), compartido por Gemini y Groq.

Nada de red: se construye `_Analysis` a mano, que es exactamente lo que
devuelve la salida estructurada de cualquiera de los dos proveedores. Ver
CLAUDE.md — no se llama a la API real de Gemini en pruebas automatizadas.
"""
from __future__ import annotations

import json

from analysis.gemini_analyzer import (
    _SYSTEM,
    ANALYSIS_JSON_SCHEMA,
    _Analysis,
    _Entity,
    _result_from_llm,
)


def _entity(name: str, **overrides) -> _Entity:
    data = {
        "name": name,
        "type": "PERSON",
        "mentions_count": 1,
        "context": "cita de ejemplo",
        "sentiment_toward": "NEU",
        "sentiment_confidence": 0.5,
        "confidence_reason": "nombre completo",
        "confidence": 1.0,
    }
    return _Entity(**{**data, **overrides})


def _analysis(**overrides) -> _Analysis:
    data = {
        "main_topic": "dengue",
        "topic_keywords": ["dengue", "hospitales"],
        "source_quality": "citas_directas",
        "has_hard_data": True,
        "lead_orientation": "oficialista",
        "content_flags": [],
        "entities": [],
        "sentiment_basis": "mixto",
        "facts_sentiment": "NEU",
        "quoted_sentiment": "NEU",
        "media_stance_evidence": "informó",
        "media_stance": "neutra_transmisiva",
        "dominant_actor": "",
        "blamed_actor": "",
        "credited_actor": "",
        "framing": "neutro_informativo",
        "headline_intent": "informativo",
        "overall_sentiment_reason": "anuncio oficial",
        "overall_sentiment": "NEU",
    }
    return _Analysis(**{**data, **overrides})


TEXTO = (
    "Abinader anunció el plan. El Ministerio de Salud lo ejecutará. "
    "Luis Abinader insistió en que no habrá retrasos."
)


class TestEntitySentimentIntensity:
    def test_sentiment_confidence_becomes_sentiment_score(self):
        """Con los motores LLM esta columna quedaba SIEMPRE en NULL: la opinión
        hacia una entidad era un POS/NEG/NEU plano, sin intensidad."""
        data = _analysis(
            entities=[_entity("Luis Abinader", sentiment_toward="NEG", sentiment_confidence=0.9)]
        )
        entity = _result_from_llm(data, TEXTO).entities[0]
        assert entity.sentiment_toward == "NEG"
        assert entity.sentiment_score == 0.9

    def test_out_of_range_confidence_is_clamped(self):
        data = _analysis(entities=[_entity("Luis Abinader", sentiment_confidence=1.7)])
        assert _result_from_llm(data, TEXTO).entities[0].sentiment_score == 1.0


class TestEntitiesAreCheckedAgainstTheText:
    def test_hallucinated_entity_is_dropped(self):
        data = _analysis(entities=[_entity("Fuerza del Pueblo", type="ORG")])
        assert _result_from_llm(data, TEXTO).entities == []

    def test_mentions_count_is_recounted_from_the_article(self):
        # El schema pide un número "aproximado" y es el que ordena la lista.
        data = _analysis(entities=[_entity("Luis Abinader", mentions_count=1)])
        assert _result_from_llm(data, TEXTO).entities[0].mentions_count == 2

    def test_entities_come_back_ordered_by_mentions(self):
        data = _analysis(
            entities=[
                _entity("Ministerio de Salud", type="ORG"),
                _entity("Luis Abinader"),
            ]
        )
        names = [e.name for e in _result_from_llm(data, TEXTO).entities]
        assert names == ["Luis Abinader", "Ministerio de Salud"]


class TestCompactSchema:
    def test_schema_has_no_pydantic_titles(self):
        """Cada `title` viaja en TODAS las llamadas y no le dice nada al modelo
        que el nombre del campo no diga ya. Con el TPM del free tier de Groq,
        son tokens que se le quitan al artículo."""
        assert "title" not in json.dumps(ANALYSIS_JSON_SCHEMA)

    def test_schema_keeps_the_instructions(self):
        # Lo que sí debe seguir viajando: las descripciones y los enums.
        serialized = json.dumps(ANALYSIS_JSON_SCHEMA, ensure_ascii=False)
        assert "sentiment_confidence" in serialized
        assert "neutra_transmisiva" in serialized
        assert "description" in serialized

    def test_fixed_prompt_fits_the_free_tier_budget(self):
        """Guardarraíl del reparto documentado en analysis/groq_analyzer.py: si
        el prompt fijo vuelve a crecer, el 429 por TPM (y con él el fallback
        FACTURADO a Gemini) reaparece en artículos largos."""
        from analysis.groq_analyzer import (
            _MAX_BODY_CHARS,
            _MAX_OUTPUT_TOKENS,
            _RETRY_BODY_CHARS,
            _RETRY_OUTPUT_TOKENS,
        )

        chars = len(_SYSTEM) + len(json.dumps(ANALYSIS_JSON_SCHEMA, ensure_ascii=False))
        fixed_tokens = chars / 3.5
        for body_chars, output_tokens in (
            (_MAX_BODY_CHARS, _MAX_OUTPUT_TOKENS),
            (_RETRY_BODY_CHARS, _RETRY_OUTPUT_TOKENS),
        ):
            total = fixed_tokens + body_chars / 3.5 + output_tokens
            assert total < 8_000, f"{total:.0f} tokens supera el TPM del free tier"
