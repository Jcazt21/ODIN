"""Groq primero, Gemini como red de seguridad.

Motivo: `GroqAnalyzer` es gratis pero su free tier tiene un TPM de 8.000 tokens
por request (prompt + cupo de salida), y el esquema de análisis de Odin es
grande. Un artículo largo o con muchas entidades puede pasarse por arriba
(413 `rate_limit_exceeded`) o quedarse sin cupo de salida a mitad del JSON
(`finish_reason=length`). Ninguna de las dos cosas es un fallo del análisis:
es el límite del plan. Cuando pasa, esto reintenta con `GeminiAnalyzer`, que
no tiene ese techo.

Coste: el fallback es una llamada FACTURADA a Gemini (ver CLAUDE.md). Por eso
Groq va SIEMPRE primero y Gemini solo entra cuando Groq ya falló — el gasto es
la excepción, no el camino normal. Ambos comparten el mismo prompt y esquema
(`_SYSTEM`/`_Analysis` en `analysis/gemini_analyzer.py`), así que el resultado
es comparable venga de donde venga; lo único que cambia es quién lo produjo.

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


class GroqWithGeminiFallback:
    # `name`/`version`/`model` son propiedades, no atributos de clase como en
    # los otros analizadores: aquí no se sabe el valor hasta que se corre, y
    # depende de cuál de los dos motores respondió.

    def __init__(self) -> None:
        from odin.analysis.groq_analyzer import GroqAnalyzer

        self._groq = GroqAnalyzer()
        self._gemini = None  # perezoso: no exigir google-genai si nunca se usa
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
        try:
            result = self._groq.analyze(title, body)
        except Exception as exc:
            # Cualquier fallo de Groq cae a Gemini, no solo el rate limit: un
            # 5xx, un timeout o un JSON inválido dejan al usuario sin análisis
            # igual que un 413, y ya tenemos un motor capaz de responder. El
            # coste de equivocarse hacia el fallback es una llamada facturada;
            # el de no hacerlo es un análisis perdido.
            log.warning(
                "groq_fallo_usando_gemini error=%s: %s", type(exc).__name__, exc
            )
            engine = self._gemini_analyzer()
            result = engine.analyze(title, body)  # si Gemini también falla, propaga
        else:
            engine = self._groq
        self._state.engine = engine
        return result

    def _gemini_analyzer(self):
        if self._gemini is None:
            from odin.analysis.gemini_analyzer import GeminiAnalyzer

            self._gemini = GeminiAnalyzer()
        return self._gemini
