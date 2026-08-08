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

import logging
from concurrent.futures import ThreadPoolExecutor

from pydantic import BaseModel

from analysis.base import AnalysisResult
from analysis.gemini_analyzer import (
    _SYSTEM,
    ANALYSIS_JSON_SCHEMA,
    _Analysis,
    _result_from_llm,
)

# --- Reparto del TPM del free tier de Groq -----------------------------------
# El límite que muerde aquí no es el coste (es gratis) sino el TPM: 8.000 tokens
# POR REQUEST, y en Groq eso incluye `max_completion_tokens`, que se RESERVA
# contra el límite aunque el modelo no lo use (ver _call_groq).
#
#   prompt fijo (system + schema compacto) ~3.330
#   + cuerpo 7.000 chars                   ~2.000
#   + reserva de salida                     2.400
#   = ~7.730 de 8.000
#
# Antes la cuenta era ~3.600 + 1.430 (cuerpo de 5.000) + 3.700 = ~8.730: por
# encima del TPM, o sea que un artículo largo daba 429 de forma estructural y
# se iba al fallback FACTURADO de Gemini. Los dos números se movieron a la vez:
#
#   - La reserva de salida baja de 3.700 a 2.400 porque 3.700 nunca hizo falta:
#     el JSON de un artículo con 15 entidades (el tope que pide el prompt) ronda
#     los 1.300-1.500 tokens. Reservar el doble de lo que se usa se paga en
#     entrada recortada, no en calidad.
#   - El cuerpo sube de 5.000 a 7.000 chars con lo liberado: es entrada que el
#     modelo SÍ lee, y era la causa de que se perdieran las entidades del final
#     del artículo (listados de nombres después del desarrollo).
#
# Si aun así la salida se trunca, `_analyze_full` reintenta con el reparto
# invertido (_RETRY_*) — gratis, antes de recurrir a Gemini. El log de
# `groq_usage` dice el consumo real: ajustar con ese dato, no estimando tokens a
# ojo (chars/4 ya falló una vez; la cuenta de arriba usa chars/3.5).
_MAX_BODY_CHARS = 7_000
_MAX_OUTPUT_TOKENS = 2_400

# Segundo intento cuando el modelo corta el JSON por límite de tokens: menos
# artículo a cambio de más cupo de salida (~860 + 3.700 + 3.330 = ~7.900).
_RETRY_BODY_CHARS = 3_000
_RETRY_OUTPUT_TOKENS = 3_700

# Techo de tiempo por llamada. Sin esto, el default del SDK (60s de lectura y 2
# reintentos = hasta ~180s) más el fallback a Gemini se pasa del tiempo que el
# frontend espera por un job, y el usuario ve "está tardando demasiado" mientras
# el análisis —posiblemente ya pagado— termina bien y queda sin mostrarse. Ver
# JOB_POLL_TIMEOUT_MS en frontend/src/lib/odin-api.ts.
_REQUEST_TIMEOUT_SECONDS = 25.0
# 1 y no el default 2: el reintento del SDK sirve para un 429 puntual con
# Retry-After corto, pero encadenar dos solo alarga la espera antes del fallback.
_MAX_RETRIES = 1

log = logging.getLogger("odin.groq_analyzer")

# Versión del prompt/esquema de salida (§2.1 de task.md): GroqAnalyzer y
# HybridAnalyzer comparten el mismo prompt/schema (_SYSTEM/_Analysis) de
# GeminiAnalyzer sin modificarlo; se versiona aparte porque el transporte
# (formato de schema, modelo) puede cambiar el resultado aunque el prompt sea
# idéntico. Aun así, sube en paralelo a gemini_analyzer._PROMPT_VERSION cada
# vez que cambia el CONTENIDO de _SYSTEM (p.ej. el glosario de
# analysis/sentiment_lexicon.py), porque ese texto sí es compartido.
_GROQ_ANALYZER_PROMPT_VERSION = "6"


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
        _client = Groq(timeout=_REQUEST_TIMEOUT_SECONDS, max_retries=_MAX_RETRIES)
    return _client


def _friendly_groq_error(exc) -> str:
    """Traduce un error HTTP de Groq (APIStatusError) a un mensaje en español
    apto para mostrar tal cual en el UI — sin el JSON crudo de la API, que
    trae jerga de facturación (TPM/TPD/tokens) que un usuario no técnico no
    puede interpretar."""
    body = exc.body if isinstance(exc.body, dict) else {}
    error = body.get("error")
    inner = error if isinstance(error, dict) else {}
    code = inner.get("code", "")
    message = inner.get("message", "") or str(exc)

    if exc.status_code == 429 and code == "rate_limit_exceeded":
        import re

        m = re.search(r"try again in ([0-9]+m)?([0-9.]+s)?", message)
        wait = "".join(g for g in (m.group(1), m.group(2)) if g) if m else None
        if "tokens per day" in message or "TPD" in message:
            return (
                "Se alcanzó el límite diario de análisis del servicio de IA. "
                "Vuelve a intentarlo más tarde (el límite se restablece en 24h)."
            )
        return (
            f"El servicio de IA está saturado por el momento — intenta de "
            f"nuevo en {wait or 'unos minutos'}."
        )
    if exc.status_code == 413:
        return "El artículo es demasiado largo para analizarlo en este momento. Intenta con otro."
    return "El servicio de IA no pudo procesar este artículo. Intenta de nuevo más tarde."


class _TruncatedOutput(RuntimeError):
    """El modelo cortó el JSON por límite de tokens (finish_reason=length).

    Excepción propia y no un RuntimeError genérico porque tiene arreglo local
    y gratis —reintentar con otro reparto del TPM (ver `_analyze_full`)— y no
    debe confundirse con los fallos que sí justifican caer al fallback pagado.
    """


def _call_groq(
    model: str,
    system: str,
    prompt: str,
    schema: type[BaseModel],
    *,
    json_schema: dict,
    max_output_tokens: int,
):
    from groq import APIStatusError

    from observability import GROQ_REQUESTS_TOTAL, GROQ_TOKENS_TOTAL

    try:
        response = _groq_client().chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": prompt},
            ],
            temperature=0.0,
            # OJO: en Groq este tope NO es solo un cap sobre lo generado — se
            # RESERVA contra el rate limit. El TPM del free tier (8.000) se
            # compara contra prompt + max_completion_tokens, así que subirlo
            # encarece cada request aunque el modelo no llegue a usarlo: con
            # 6144 aquí, un artículo corto ya devolvía 413 antes de generar un
            # solo token. El reparto entre entrada y salida está razonado en
            # los comentarios de _MAX_BODY_CHARS.
            max_completion_tokens=max_output_tokens,
            response_format={
                "type": "json_schema",
                "json_schema": {"name": "analysis", "schema": json_schema},
            },
        )
    except APIStatusError as exc:
        GROQ_REQUESTS_TOTAL.labels(model=model, status=f"http_{exc.status_code}").inc()
        raise RuntimeError(_friendly_groq_error(exc)) from exc
    except Exception:
        GROQ_REQUESTS_TOTAL.labels(model=model, status="error").inc()
        raise

    # Uso real, para poder ajustar _MAX_BODY_CHARS/max_output_tokens con datos
    # en vez de estimando tokens a ojo (chars/4 se queda corto y fue lo que
    # llevó al 413 de arriba). `completion` dice cuánto del cupo se usó de
    # verdad; `total` dice cuán cerca del TPM quedó el request.
    finish_reason = response.choices[0].finish_reason
    usage = getattr(response, "usage", None)
    if usage is not None:
        log.info(
            "groq_usage model=%s prompt=%s completion=%s total=%s finish=%s",
            model,
            getattr(usage, "prompt_tokens", "?"),
            getattr(usage, "completion_tokens", "?"),
            getattr(usage, "total_tokens", "?"),
            finish_reason,
        )
        GROQ_TOKENS_TOTAL.labels(model=model, kind="prompt").inc(
            getattr(usage, "prompt_tokens", 0) or 0
        )
        GROQ_TOKENS_TOTAL.labels(model=model, kind="output").inc(
            getattr(usage, "completion_tokens", 0) or 0
        )

    raw = response.choices[0].message.content
    if finish_reason == "length":
        GROQ_REQUESTS_TOTAL.labels(model=model, status="truncated").inc()
        raise _TruncatedOutput(
            "Groq cortó la respuesta por límite de tokens antes de completar el JSON"
        )
    if not raw:
        GROQ_REQUESTS_TOTAL.labels(model=model, status="empty").inc()
        raise RuntimeError(f"Groq no devolvió contenido (finish_reason={finish_reason})")
    GROQ_REQUESTS_TOTAL.labels(model=model, status="success").inc()
    return schema.model_validate_json(raw)


def _analyze_full(model: str, title: str, body: str) -> AnalysisResult:
    """Análisis completo (tema, entidades, sentimiento, encuadre) vía Groq —
    usado tal cual por `GroqAnalyzer` y por `HybridAnalyzer` para la parte
    que sí delega al LLM (entidades + encuadre).

    Si la salida se trunca, reintenta UNA vez con menos artículo y más cupo de
    salida. Es gratis y evita el único desenlace que sí cuesta dinero: caer al
    fallback de Gemini (`analysis/fallback_analyzer.py`) por un problema de
    reparto de tokens, no por un fallo del análisis.
    """
    full_body = body or ""
    attempts = (
        (_MAX_BODY_CHARS, _MAX_OUTPUT_TOKENS),
        (_RETRY_BODY_CHARS, _RETRY_OUTPUT_TOKENS),
    )
    for attempt, (body_chars, output_tokens) in enumerate(attempts, start=1):
        prompt = (
            "Analiza este artículo de periódico.\n\n"
            f"TITULAR: {title}\n\nCUERPO:\n{full_body[:body_chars]}"
        )
        try:
            data = _call_groq(
                model,
                _SYSTEM,
                prompt,
                _Analysis,
                json_schema=ANALYSIS_JSON_SCHEMA,
                max_output_tokens=output_tokens,
            )
        except _TruncatedOutput:
            if attempt == len(attempts):
                raise
            log.warning(
                "groq_salida_truncada: reintento con cuerpo=%d chars y salida=%d tokens",
                *attempts[attempt],
            )
            continue
        # El texto COMPLETO, no el recorte: `_result_from_llm` cuenta menciones
        # sobre él, así que las del final del artículo también suman.
        return _result_from_llm(data, f"{title}\n{full_body}")
    raise AssertionError("inalcanzable: el bucle sale por return o por raise")


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
        # Los dos motores arrancan a la vez: uno es CPU (spaCy) y el otro es
        # espera de red (Groq), así que en serie se sumaban dos tiempos que no
        # compiten por el mismo recurso. El hilo extra vive solo lo que dura
        # esta llamada.
        with ThreadPoolExecutor(max_workers=1, thread_name_prefix="odin-topics") as pool:
            topics = pool.submit(self._local.analyze_topics, title, body)
            try:
                groq_result = _analyze_full(self._groq_model, title, body)
            except BaseException:
                topics.cancel()
                raise
            main_topic, keywords = topics.result()

        # Solo tema/keywords vienen de LocalAnalyzer: es extracción pura de
        # sustantivos frecuentes, sin ambigüedad semántica que un LLM resuelva
        # mejor. Por eso se llama `analyze_topics` y no `analyze`: el análisis
        # local completo también corría pysentimiento sobre cada frase (~60%
        # de su tiempo) para tirar el resultado a la basura, porque
        # overall_sentiment/sentiment_score se dejan tal cual los devuelve Groq
        # — ya lee el artículo completo con contexto entre frases, mientras que
        # pysentimiento agrega probabilidades por frase de forma independiente.
        groq_result.main_topic = main_topic
        groq_result.topic_keywords = keywords
        return groq_result
