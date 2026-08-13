"""Groq primero, Gemini como red de seguridad.

Motivo: `GroqAnalyzer` es gratis pero su free tier tiene un TPM de 8.000 tokens
por request (prompt + cupo de salida), y el esquema de análisis de Odin es
grande. Un artículo largo o con muchas entidades puede pasarse por arriba
(413 `rate_limit_exceeded`) o quedarse sin cupo de salida a mitad del JSON
(`finish_reason=length`). Ninguna de las dos cosas es un fallo del análisis:
es el límite del plan. Cuando pasa, esto reintenta con `GeminiAnalyzer`, que
no tiene ese techo.

Coste: el fallback a Gemini PUEDE facturar (ver CLAUDE.md). Por eso Groq va
SIEMPRE primero y Gemini solo entra cuando Groq ya falló — el gasto es la
excepción, no el camino normal. Ambos comparten el mismo prompt y esquema
(`_SYSTEM`/`_Analysis` en `analysis/gemini_analyzer.py`), así que el resultado
es comparable venga de donde venga; lo único que cambia es quién lo produjo.

Cadena de Gemini (dos cuentas): para que el gasto sea aún más raro, el fallback
puede probar DOS cuentas de Google en orden — primero el free tier
(GEMINI_API_KEY_FREE, no factura) y solo si ese también se agota, la de pago
(GEMINI_API_KEY_PAID). El flujo completo queda: Groq (gratis) → Gemini free
(gratis) → Gemini pago. Si no se configura ninguna de esas dos, se usa la key
única del entorno como siempre (un solo Gemini). Ver `_gemini_chain`.

Linaje (§2.1 de task.md): `name`/`model`/`version` reflejan el motor que
realmente produjo el ÚLTIMO análisis de este hilo, no el analizador compuesto.
Es lo que permite responder después "¿por qué esta fila dice NEG?" y saber si
la produjo Groq o el fallback. `api.py` lee esas tres propiedades justo
después de `analyze()`, así que se guardan por hilo (`threading.local`): los
trabajos de `/api/analyze` corren en el threadpool de `BackgroundTasks` y dos
análisis simultáneos no deben pisarse el linaje entre sí.
"""
from __future__ import annotations

import logging
import threading

from odin.analysis.base import AnalysisResult

log = logging.getLogger("odin.fallback_analyzer")


def _fallback_reason(exc: Exception) -> str:
    """Clasifica por qué se recurrió al motor de pago, para la métrica
    `odin_analyzer_fallback_total`. Cada causa tiene un arreglo distinto: un
    `rate_limit` recurrente pide revisar el reparto del TPM en
    `odin/analysis/groq_analyzer.py`; un `truncated` que sobrevive al reintento
    pide más cupo de salida; un `timeout` no se arregla con tokens."""
    from odin.analysis.groq_analyzer import _TruncatedOutput

    if isinstance(exc, _TruncatedOutput):
        return "truncated"
    message = str(exc).lower()
    if "saturado" in message or "límite diario" in message or "rate" in message:
        return "rate_limit"
    if "timeout" in message or "timed out" in message:
        return "timeout"
    return "other"


class GroqWithGeminiFallback:
    # `name`/`version`/`model` son propiedades, no atributos de clase como en
    # los otros analizadores: aquí no se sabe el valor hasta que se corre, y
    # depende de cuál de los dos motores respondió.

    def __init__(self) -> None:
        from odin.analysis.groq_analyzer import GroqAnalyzer

        self._groq = GroqAnalyzer()
        self._gemini_tiers = None  # cadena perezosa de Gemini, ver _gemini_chain
        self._state = threading.local()

    # ---- motor efectivo del último analyze() de ESTE hilo ---------------------
    @property
    def _last(self):
        """El motor que produjo el último análisis en este hilo.

        Antes de la primera llamada (p.ej. si algo lee `.model` solo para
        registrar linaje) devuelve Groq, que es el que va a correr primero.
        """
        return getattr(self._state, "engine", None) or self._groq

    @property
    def name(self) -> str:
        return self._last.name

    @property
    def version(self) -> str:
        return self._last.version

    @property
    def model(self) -> str:
        return self._last.model

    # ---- API pública ----------------------------------------------------------
    def analyze(self, title: str, body: str) -> AnalysisResult:
        from odin.core.observability import ANALYZER_FALLBACK_TOTAL

        try:
            result = self._groq.analyze(title, body)
        except Exception as exc:
            # Cualquier fallo de Groq cae a Gemini, no solo el rate limit: un
            # 5xx, un timeout o un JSON inválido dejan al usuario sin análisis
            # igual que un 413, y ya tenemos un motor capaz de responder. El
            # coste de equivocarse hacia el fallback es una llamada facturada;
            # el de no hacerlo es un análisis perdido.
            reason = _fallback_reason(exc)
            log.warning(
                "groq_fallo_usando_gemini reason=%s error=%s: %s",
                reason,
                type(exc).__name__,
                exc,
            )
            ANALYZER_FALLBACK_TOTAL.labels(reason=reason).inc()
            result, engine = self._run_gemini_chain(title, body)
        else:
            engine = self._groq
        self._state.engine = engine
        return result

    def _gemini_chain(self):
        """Cadena de Gemini a probar EN ORDEN cuando Groq falla.

        Si hay dos cuentas configuradas, primero la gratuita
        (GEMINI_API_KEY_FREE, no factura pero con límite diario) y solo si esa
        también falla, la de pago (GEMINI_API_KEY_PAID) — así el gasto es el
        último recurso, no el primero. Si no hay ninguna de las dos, un único
        Gemini con la key del entorno (GEMINI_API_KEY/GOOGLE_API_KEY): el
        comportamiento histórico de este modo.

        Perezoso: no importa google-genai ni construye clientes si Groq nunca
        falla. `name` distinto por cuenta ("gemini-free"/"gemini-paid") para que
        el linaje guardado diga cuál respondió — y, con eso, cuál facturó.
        """
        if self._gemini_tiers is None:
            from odin.analysis.gemini_analyzer import GeminiAnalyzer
            from odin.core.config import settings

            tiers = []
            if settings.gemini_api_key_free:
                tiers.append(
                    GeminiAnalyzer(api_key=settings.gemini_api_key_free, name="gemini-free")
                )
            if settings.gemini_api_key_paid:
                tiers.append(
                    GeminiAnalyzer(api_key=settings.gemini_api_key_paid, name="gemini-paid")
                )
            if not tiers:
                tiers.append(GeminiAnalyzer())
            self._gemini_tiers = tiers
        return self._gemini_tiers

    def _run_gemini_chain(self, title: str, body: str):
        """Recorre la cadena hasta que una cuenta responde. La última que falla
        propaga: si ni la de pago pudo, el análisis se pierde igual que antes."""
        chain = self._gemini_chain()
        for i, engine in enumerate(chain):
            try:
                return engine.analyze(title, body), engine
            except Exception as exc:
                if i == len(chain) - 1:
                    raise  # era el último recurso configurado: propaga
                log.warning(
                    "gemini_cuenta_fallo_probando_siguiente engine=%s error=%s: %s",
                    getattr(engine, "name", "gemini"),
                    type(exc).__name__,
                    exc,
                )
        raise AssertionError("inalcanzable: la cadena de Gemini nunca está vacía")
