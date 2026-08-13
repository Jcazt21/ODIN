"""El árbitro de entidades ambiguas es una llamada FACTURADA extra a Gemini
(`odin/analysis/entity_arbiter.py`). Estas pruebas fijan CUÁNDO se hace y cuándo no.

Nunca se llega a la API: el doble de `are_person_mentions` falla el test si
alguien lo invoca cuando no corresponde. Ver CLAUDE.md.
"""
from __future__ import annotations

import dataclasses

import pytest

from odin.analysis.base import AnalysisResult, EntityResult
from odin.services import analyze_service


@pytest.fixture
def arbiter_calls(monkeypatch):
    """Cuenta las llamadas al árbitro sin tocar la red."""
    calls: list[list[tuple[str, str]]] = []

    def _fake_arbiter(items):
        calls.append(items)
        return [False] * len(items)  # descarta todo, para notar si corrió

    monkeypatch.setattr(
        "odin.analysis.entity_arbiter.are_person_mentions", _fake_arbiter, raising=True
    )
    return calls


def _result_with_venue_person() -> AnalysisResult:
    """Un caso ambiguo de verdad: PERSON cuyo contexto menciona un lugar."""
    return AnalysisResult(
        entities=[
            EntityResult(
                name="Juan Pablo Duarte",
                type="PERSON",
                context="El acto se realizó en el Salón Juan Pablo Duarte.",
            )
        ]
    )


def _enable_arbiter(monkeypatch, *, reads_whole_article: bool):
    monkeypatch.setattr(
        analyze_service,
        "settings",
        dataclasses.replace(analyze_service.settings, gemini_arbiter=True),
    )
    monkeypatch.setattr(
        analyze_service, "ANALYZER_READS_WHOLE_ARTICLE", reads_whole_article
    )


class TestArbiterIsSkipped:
    def test_when_disabled(self, monkeypatch, arbiter_calls):
        monkeypatch.setattr(
            analyze_service,
            "settings",
            dataclasses.replace(analyze_service.settings, gemini_arbiter=False),
        )
        monkeypatch.setattr(analyze_service, "ANALYZER_READS_WHOLE_ARTICLE", False)

        result = _result_with_venue_person()
        analyze_service.arbitrate_ambiguous_persons(result)

        assert arbiter_calls == []
        assert len(result.entities) == 1

    def test_with_any_llm_analyzer_even_if_enabled(self, monkeypatch, arbiter_calls):
        """El guard miraba solo `ODIN_ANALYZER=gemini`, así que con groq/hybrid/
        groq+gemini se pagaba un segundo chequeo de algo que el prompt de esos
        motores ya resuelve."""
        _enable_arbiter(monkeypatch, reads_whole_article=True)

        result = _result_with_venue_person()
        analyze_service.arbitrate_ambiguous_persons(result)

        assert arbiter_calls == []
        assert len(result.entities) == 1

    def test_when_no_entity_is_ambiguous(self, monkeypatch, arbiter_calls):
        _enable_arbiter(monkeypatch, reads_whole_article=False)

        result = AnalysisResult(
            entities=[
                EntityResult(name="Luis Abinader", type="PERSON", context="Abinader anunció el plan.")
            ]
        )
        analyze_service.arbitrate_ambiguous_persons(result)

        assert arbiter_calls == []
        assert len(result.entities) == 1


class TestArbiterRuns:
    def test_with_the_local_analyzer_and_an_ambiguous_person(self, monkeypatch, arbiter_calls):
        _enable_arbiter(monkeypatch, reads_whole_article=False)

        result = _result_with_venue_person()
        analyze_service.arbitrate_ambiguous_persons(result)

        assert len(arbiter_calls) == 1  # UNA sola llamada para todo el artículo
        assert result.entities == []  # el doble respondió "no es una mención real"
