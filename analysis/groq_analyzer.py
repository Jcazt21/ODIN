"""Analizadores basados en LLM vía Groq — alternativa GRATUITA (free tier con
rate limits) a `GeminiAnalyzer`.

Dos clases, misma interfaz `Analyzer`:

  - `GroqAnalyzer`: todo el análisis (tema, entidades, sentimiento y encuadre)
    vía Groq, igual que `GeminiAnalyzer` pero con otro proveedor.
  - `HybridAnalyzer` (recomendado): `LocalAnalyzer` (spaCy + pysentimiento,
    gratis) SOLO para tema/keywords/sentimiento global, + Groq para entidades
    (personas/organizaciones) Y encuadre en una sola llamada.

    from analysis.groq_analyzer import GroqAnalyzer, HybridAnalyzer
    run(analyzer=HybridAnalyzer(), ...)

Por qué las entidades también pasan por el LLM (y no solo el encuadre): la
extracción de spaCy es estadística por patrones (mayúsculas, POS tags,
árbol de dependencias), no comprende el texto — produce errores sistemáticos
que ninguna heurística de post-procesado cierra del todo: nombres truncados
("Secretaría del" en vez de "Secretaría del Consejo" cuando la palabra
siguiente ya quedó etiquetada como el inicio de otra entidad), siglas o
apellidos fusionados con el homónimo equivocado de la base de datos en vez
del nombre completo que trae el propio artículo, o sustantivos genéricos
("República", cargos) etiquetados como organización real. Un LLM que ya lee
el artículo completo para el encuadre extrae las entidades correctamente en
la misma pasada, al mismo costo por llamada — no hace falta pagar/gastar
rate limit dos veces. `LocalAnalyzer` se queda con lo que sigue haciendo
bien sin depender de una API externa: tema, palabras clave y sentimiento
global agregado por frase.

Reutiliza el mismo schema Pydantic, prompt y post-procesamiento que
`GeminiAnalyzer` (ver ese módulo para el detalle de cada campo); solo cambia
el transporte: Groq expone una API compatible con OpenAI, con salida JSON
estructurada vía `response_format={"type": "json_schema", ...}`.

Requisitos:
    pip install groq
    export GROQ_API_KEY=...
"""
from __future__ import annotations

from pydantic import BaseModel

from analysis.base import AnalysisResult
from analysis.gemini_analyzer import _SYSTEM, _Analysis, _entity_from_llm, _norm_sentiment

_MAX_BODY_CHARS = 16_000  # acota tokens/coste por artículo, igual que Gemini

# Versión del prompt/esquema de salida (§2.1 de task.md): GroqAnalyzer y
# HybridAnalyzer comparten el mismo prompt/schema (_SYSTEM/_Analysis) de
# GeminiAnalyzer sin modificarlo; se versiona aparte porque el transporte
# (formato de schema, modelo) puede cambiar el resultado aunque el prompt sea
# idéntico.
_GROQ_ANALYZER_PROMPT_VERSION = "3"


_DEFAULT_MODEL = "openai/gpt-oss-120b"
# openai/gpt-oss-120b: modelo gratuito del free tier de Groq que además
# soporta salida estructurada (`response_format: json_schema`) — a la fecha
# (2026), "llama-3.3-70b-versatile" NO la soporta y Groq responde 400
# (invalid_request_error) al usarlo con este código; ver
# https://console.groq.com/docs/structured-outputs#supported-models antes de
# cambiar el modelo. Alternativa más rápida/ligera: "openai/gpt-oss-20b"
# (calidad de encuadre algo menor).

_client = None


def _groq_client():
    global _client
    if _client is None:
        from groq import Groq  # import perezoso: solo si se usa algún analizador de Groq

        # Toma la API key de GROQ_API_KEY del entorno.
        _client = Groq()
    return _client


def _call_groq(model: str, system: str, prompt: str, schema: type[BaseModel]):
    response = _groq_client().chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": prompt},
        ],
        temperature=0.0,
        # 4096 y no 2048: con "confidence"/"confidence_reason" por entidad
        # (ver _Entity en gemini_analyzer.py) un artículo con ~10-15
        # entidades ya no cabe en 2048 — el modelo corta a mitad del JSON
        # (finish_reason="length") y Pydantic falla con "Field required" en
        # los campos de encuadre, que van al final del schema y nunca
        # llegan a escribirse.
        max_completion_tokens=4096,
        response_format={
            "type": "json_schema",
            "json_schema": {"name": "analysis", "schema": schema.model_json_schema()},
        },
    )
    raw = response.choices[0].message.content
    finish_reason = response.choices[0].finish_reason
    if not raw:
        raise RuntimeError(f"Groq no devolvió contenido (finish_reason={finish_reason})")
    if finish_reason == "length":
        raise RuntimeError(
            "Groq cortó la respuesta por límite de tokens antes de completar "
            "el JSON (finish_reason=length) — sube max_completion_tokens en "
            "_call_groq si esto se repite con artículos largos/con muchas "
            "entidades."
        )
    return schema.model_validate_json(raw)


def _analyze_full(model: str, title: str, body: str) -> AnalysisResult:
    """Análisis completo (tema, entidades, sentimiento, encuadre) vía Groq —
    usado tal cual por `GroqAnalyzer` y por `HybridAnalyzer` para la parte
    que sí delega al LLM (entidades + encuadre)."""
    body = (body or "")[:_MAX_BODY_CHARS]
    prompt = f"Analiza este artículo de periódico.\n\nTITULAR: {title}\n\nCUERPO:\n{body}"
    data = _call_groq(model, _SYSTEM, prompt, _Analysis)

    entities = [_entity_from_llm(e) for e in data.entities]

    return AnalysisResult(
        main_topic=data.main_topic.strip() or None,
        topic_keywords=[k.strip() for k in data.topic_keywords if k.strip()],
        overall_sentiment=_norm_sentiment(data.overall_sentiment),
        sentiment_score=None,
        entities=entities,
        framing=data.framing,
        headline_intent=data.headline_intent,
        lead_orientation=data.lead_orientation,
        dominant_actor=data.dominant_actor.strip() or None,
        source_quality=data.source_quality,
        has_hard_data=data.has_hard_data,
        blamed_actor=data.blamed_actor.strip() or None,
        credited_actor=data.credited_actor.strip() or None,
    )


class GroqAnalyzer:
    name = "groq"
    version = _GROQ_ANALYZER_PROMPT_VERSION

    def __init__(self, model: str = _DEFAULT_MODEL) -> None:
        self.model = model

    def analyze(self, title: str, body: str) -> AnalysisResult:
        return _analyze_full(self.model, title, body)


class HybridAnalyzer:
    """LocalAnalyzer (gratis) SOLO para tema/keywords/sentimiento global +
    Groq para entidades (personas/organizaciones) Y encuadre en una sola
    llamada.

    LocalAnalyzer sigue siendo mejor y gratis para lo que es extracción pura
    de patrones sin ambigüedad semántica: tema principal, palabras clave,
    sentimiento agregado por frase. Pero la extracción de ENTIDADES (NER) sí
    exige leer y entender el texto para no romperse con nombres compuestos,
    sustantivos genéricos o homónimos — ver el docstring del módulo para
    ejemplos reales de los tres tipos de error que esto corrige. Por eso
    entidades pasa a Groq junto con el encuadre, en la misma llamada (mismo
    costo, el LLM ya está leyendo el artículo completo de todos modos).
    """

    name = "hybrid"

    # Versión de CÓMO HybridAnalyzer combina los dos analizadores (qué campos
    # toma de cada uno) — independiente de _local.version y
    # _GROQ_ANALYZER_PROMPT_VERSION, que versionan cada analizador por
    # separado. Subir cuando cambie qué campos vienen de dónde (p.ej. este
    # cambio: overall_sentiment pasó de LocalAnalyzer a Groq).
    _COMBINE_VERSION = "2"

    def __init__(self, groq_model: str = _DEFAULT_MODEL) -> None:
        self._groq_model = groq_model

        from analysis.local_analyzer import LocalAnalyzer

        self._local = LocalAnalyzer()
        self.version = (
            f"local{self._local.version}+groq{_GROQ_ANALYZER_PROMPT_VERSION}"
            f"+combine{self._COMBINE_VERSION}"
        )

    @property
    def model(self) -> str:
        # Igual que LocalAnalyzer.model: refleja el modelo de spaCy real
        # una vez cargado (carga perezosa), combinado con el modelo de Groq.
        return f"{self._local.model}+{self._groq_model}"

    def analyze(self, title: str, body: str) -> AnalysisResult:
        local_result = self._local.analyze(title, body)
        groq_result = _analyze_full(self._groq_model, title, body)

        # Solo tema/keywords vienen de LocalAnalyzer: es extracción pura de
        # sustantivos frecuentes, sin ambigüedad semántica que un LLM resuelva
        # mejor. overall_sentiment/sentiment_score se dejan tal cual los
        # devuelve Groq (ya lee el artículo completo con contexto entre
        # frases) — pysentimiento en LocalAnalyzer agrega probabilidades por
        # frase de forma independiente, sin ver el artículo completo, así que
        # es la señal menos confiable de las dos para este campo.
        groq_result.main_topic = local_result.main_topic
        groq_result.topic_keywords = local_result.topic_keywords
        return groq_result
