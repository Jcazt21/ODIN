"""Interfaz del analizador.

El resto del sistema (scraper, base de datos, pipeline) depende SOLO de esta
interfaz. Hoy la implementa `LocalAnalyzer` (modelos locales gratis); mañana se
puede implementar con un LLM para el cliente sin tocar nada más.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol


@dataclass
class EntityResult:
    name: str
    type: str                       # "PERSON" | "ORG"
    mentions_count: int = 1
    sentiment_toward: str | None = None   # "POS" | "NEG" | "NEU"
    sentiment_score: float | None = None  # 0..1
    context: str | None = None


@dataclass
class AnalysisResult:
    main_topic: str | None = None
    topic_keywords: list[str] = field(default_factory=list)
    overall_sentiment: str | None = None  # "POS" | "NEG" | "NEU"
    sentiment_score: float | None = None
    entities: list[EntityResult] = field(default_factory=list)

    # --- Análisis de encuadre (solo lo produce GeminiAnalyzer; LocalAnalyzer
    # los deja en None: exigen comprensión del texto, no extracción) ---
    framing: str | None = None            # crisis_conflicto | logro_institucional | negligencia | crecimiento | denuncia | neutro_informativo
    headline_intent: str | None = None    # informativo | alarmista | sensacionalista
    lead_orientation: str | None = None   # social | oficialista | tecnico
    dominant_actor: str | None = None     # entidad con más peso en la nota
    source_quality: str | None = None     # citas_directas | testimonios_anonimos | datos_duros | mixtas | sin_fuentes
    has_hard_data: bool | None = None     # ¿hay cifras/datos cuantitativos?
    blamed_actor: str | None = None       # a quién se señala como causante
    credited_actor: str | None = None     # a quién se presenta como solución


class Analyzer(Protocol):
    def analyze(self, title: str, body: str) -> AnalysisResult: ...
