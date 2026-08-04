"""Interfaz del analizador.

El resto del sistema (scraper, base de datos, pipeline) depende SOLO de esta
interfaz. Hoy la implementa `LocalAnalyzer` (modelos locales gratis); mañana se
puede implementar con un LLM para el cliente sin tocar nada más.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol

# Versión del esquema de `AnalysisResult` (§2.1 de task.md): incrementar cuando
# se agregue, quite o cambie de significado un campo del análisis, para poder
# distinguir en la BD qué filas usan qué forma del esquema y decidir un
# backfill selectivo en vez de re-analizar todo el corpus a ciegas.
ANALYSIS_SCHEMA_VERSION = 1


@dataclass
class EntityResult:
    name: str
    type: str                       # "PERSON" | "ORG"
    mentions_count: int = 1
    sentiment_toward: str | None = None   # "POS" | "NEG" | "NEU"
    sentiment_score: float | None = None  # 0..1
    context: str | None = None
    # Cuán segura estuvo la extracción de que esta es una mención real (no
    # ruido de segmentación ni un nombre parcial ambiguo). 1.0 = certera;
    # más bajo sugiere revisión manual en el frontend. Solo LocalAnalyzer la
    # calcula hoy (ver analysis/local_analyzer.py); 1.0 por defecto para
    # cualquier otro Analyzer que no la produzca explícitamente.
    extraction_confidence: float = 1.0


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
    # Metadatos de linaje (§2.1): quién produjo el análisis, con qué modelo
    # exacto y qué versión de heurística/prompt — para poder responder "¿por
    # qué esta fila dice NEG?" y decidir backfills selectivos sin adivinar por
    # la presencia/ausencia de campos de encuadre.
    name: str      # "local" | "gemini"
    model: str     # p.ej. "es_core_news_lg-3.8.0" | "gemini-3.5-flash"
    version: str   # versión de la heurística/prompt de ESTE analizador

    def analyze(self, title: str, body: str) -> AnalysisResult: ...
