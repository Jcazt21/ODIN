"""Instancia única del `Analyzer` activo para todo el proceso (§9.2 de
task.md): antes vivía como estado a nivel de módulo en `api.py`; ahora la
comparten `services/analyze_service.py` y `services/article_service.py` sin
duplicar la lógica de selección.

El motor lo decide `ODIN_ANALYZER`, NUNCA la presencia de `GEMINI_API_KEY`:
tener la llave en el `.env` no es lo mismo que querer pagar por cada
análisis. Mismo criterio que el CLI (`main.py --analyzer`). Ver CLAUDE.md.
"""
from __future__ import annotations

from odin.analysis import LocalAnalyzer
from odin.analysis.base import Analyzer
from odin.core.config import settings
from odin.core.observability import get_logger

log = get_logger("odin.api")

IS_GEMINI_ANALYZER = settings.analyzer == "gemini"

# Carga perezosa: los modelos se inicializan aquí. El tipo declarado es el
# puerto (`Analyzer`), no la implementación: es lo que permite intercambiarlas.
analyzer: Analyzer
if IS_GEMINI_ANALYZER:
    # Import perezoso: sin esto, correr en modo local exigiría google-genai.
    from odin.analysis.gemini_analyzer import GeminiAnalyzer

    log.warning(
        "ODIN_ANALYZER=gemini — cada análisis es una llamada FACTURADA a la API "
        "de Gemini. Usa ODIN_ANALYZER=local para el motor gratuito."
    )
    analyzer = GeminiAnalyzer()
elif settings.analyzer == "groq+gemini":
    from odin.analysis.fallback_analyzer import GroqWithGeminiFallback

    log.warning(
        "ODIN_ANALYZER=groq+gemini — GroqAnalyzer (gratis) primero; si falla "
        "(rate limit, respuesta truncada, error de red) reintenta con Gemini, "
        "que es una llamada FACTURADA. El linaje guardado dice cuál respondió."
    )
    analyzer = GroqWithGeminiFallback()
elif settings.analyzer == "groq":
    # Import perezoso: sin esto, correr en modo local exigiría el paquete groq.
    from odin.analysis.groq_analyzer import GroqAnalyzer

    log.info("ODIN_ANALYZER=groq — GroqAnalyzer (free tier, rate-limited)")
    analyzer = GroqAnalyzer()
elif settings.analyzer == "hybrid":
    from odin.analysis.groq_analyzer import HybridAnalyzer

    log.info(
        "ODIN_ANALYZER=hybrid — LocalAnalyzer (spaCy + pysentimiento) + Groq "
        "solo para el encuadre (free tier, rate-limited)"
    )
    analyzer = HybridAnalyzer()
else:
    log.info("ODIN_ANALYZER=local — LocalAnalyzer (spaCy + pysentimiento), sin costo")
    analyzer = LocalAnalyzer()

if settings.gemini_arbiter and not IS_GEMINI_ANALYZER:
    log.warning(
        "ODIN_GEMINI_ARBITER activo — se hará una llamada FACTURADA extra a "
        "Gemini en los análisis con personas ambiguas."
    )
