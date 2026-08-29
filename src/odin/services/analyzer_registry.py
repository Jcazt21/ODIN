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

# ¿El motor activo LEE el artículo completo con un LLM? Todos menos "local":
# `LocalAnalyzer` extrae entidades con spaCy (patrones de mayúsculas, POS y
# dependencias), sin entender el texto. La distinción decide si vale la pena
# el árbitro pagado de entidades ambiguas: el prompt de los motores LLM ya
# excluye los nombres que solo bautizan un lugar o reciben un homenaje (ver
# `_SYSTEM` en analysis/gemini_analyzer.py), así que preguntárselo otra vez a
# Gemini es pagar dos veces por la misma decisión.
ANALYZER_READS_WHOLE_ARTICLE = settings.analyzer != "local"

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

    if settings.gemini_api_key_free or settings.gemini_api_key_paid:
        chain = ["Groq (gratis)"]
        if settings.gemini_api_key_free:
            chain.append("Gemini free (gratis)")
        if settings.gemini_api_key_paid:
            chain.append("Gemini pago (FACTURADO)")
        log.warning(
            "ODIN_ANALYZER=groq+gemini — cadena: %s. Cada eslabón solo entra si "
            "el anterior falla; el linaje guardado dice cuál respondió.",
            " → ".join(chain),
        )
    else:
        log.warning(
            "ODIN_ANALYZER=groq+gemini — GroqAnalyzer (gratis) primero; si falla "
            "(rate limit, respuesta truncada, error de red) reintenta con Gemini, "
            "que es una llamada FACTURADA. El linaje guardado dice cuál respondió. "
            "Configura GEMINI_API_KEY_FREE para intercalar una cuenta gratuita "
            "antes de la de pago."
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

# Extractor de lugares, independiente del motor activo. Los topónimos salen
# del NER de spaCy: reconocer "San Juan" como lugar no exige entender el
# artículo, así que no tiene por qué depender de quién lo leyó. Los motores
# LLM devuelven `AnalysisResult.places` vacío, y sin esto la detección
# automática solo funcionaría con ODIN_ANALYZER=local.
_place_extractor: LocalAnalyzer | None = None


def place_extractor() -> LocalAnalyzer:
    """`LocalAnalyzer` compartido, solo para extraer lugares.

    Reusa el motor activo cuando YA es local —cargar spaCy dos veces en el
    mismo proceso serían ~500 MB de más— y si no, crea uno perezosamente: el
    modelo se carga recién en la primera llamada, no al importar el módulo.
    """
    global _place_extractor
    if isinstance(analyzer, LocalAnalyzer):
        return analyzer
    if _place_extractor is None:
        _place_extractor = LocalAnalyzer()
    return _place_extractor


if settings.gemini_arbiter:
    if ANALYZER_READS_WHOLE_ARTICLE:
        log.warning(
            "ODIN_GEMINI_ARBITER está activo pero se IGNORA con "
            "ODIN_ANALYZER=%s: ese motor ya descarta por prompt los nombres "
            "que solo bautizan un lugar. Solo aplica con ODIN_ANALYZER=local.",
            settings.analyzer,
        )
    else:
        log.warning(
            "ODIN_GEMINI_ARBITER activo — se hará una llamada FACTURADA extra a "
            "Gemini en los análisis con personas ambiguas."
        )
