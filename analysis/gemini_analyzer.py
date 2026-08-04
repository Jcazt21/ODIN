"""Analizador basado en LLM de Google (Gemini) — OPCIONAL, precisión de producción.

Implementa la MISMA interfaz `Analyzer` que `LocalAnalyzer`, así que se enchufa
sin tocar scrapers, pipeline ni base de datos:

    from analysis.gemini_analyzer import GeminiAnalyzer
    run(analyzer=GeminiAnalyzer(), ...)

Ventaja frente al analizador local: mucho mejor en la parte difícil —
"¿hablan bien o mal de esta figura/empresa?" (aspect-based sentiment) — porque
el modelo entiende ironía, contexto y a quién se refiere cada frase.

Coste: consume la API de Google Gemini (de pago) por artículo. No está activo
por defecto; el sistema usa `LocalAnalyzer` (gratis) salvo que se pida esto.

Requisitos:
    pip install google-genai
    export GEMINI_API_KEY=...        (o GOOGLE_API_KEY)
"""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

from analysis.base import AnalysisResult, EntityResult

_SENTIMENTS = ("POS", "NEG", "NEU")
_MAX_BODY_CHARS = 16_000  # acota tokens/coste por artículo

Sentiment = Literal["POS", "NEG", "NEU"]


class _Entity(BaseModel):
    name: str = Field(description="Nombre de la figura pública o empresa mencionada")
    type: Literal["PERSON", "ORG"] = Field(
        description="PERSON para personas, ORG para empresas/organizaciones"
    )
    sentiment_toward: Sentiment = Field(
        description="Opinión del artículo hacia esta entidad"
    )
    mentions_count: int = Field(description="Número aproximado de menciones en el artículo")
    context: str = Field(
        description="Cita textual breve (máx. 12 palabras) que justifica el sentimiento"
    )


class _Analysis(BaseModel):
    main_topic: str = Field(description="Tema principal en pocas palabras, p.ej. 'agua potable'")
    topic_keywords: list[str] = Field(description="3 a 8 palabras clave del artículo")
    overall_sentiment: Sentiment = Field(description="Sentimiento global del artículo")
    entities: list[_Entity] = Field(
        description="Figuras públicas y empresas mencionadas, con la opinión hacia cada una"
    )
    framing: Literal[
        "crisis_conflicto",
        "logro_institucional",
        "negligencia",
        "crecimiento",
        "denuncia",
        "neutro_informativo",
    ] = Field(
        description=(
            "Encuadre principal de la nota: crisis_conflicto (falla del servicio, "
            "sufrimiento ciudadano, disputa entre actores), logro_institucional "
            "(métricas de eficiencia, obra entregada, récord), negligencia (se "
            "culpa a la inacción de una autoridad), crecimiento (el problema es "
            "efecto del crecimiento económico), denuncia (reclamo/acusación de "
            "un sector), neutro_informativo (sin ángulo marcado)"
        )
    )
    headline_intent: Literal["informativo", "alarmista", "sensacionalista"] = Field(
        description="Intención del TITULAR: informar objetivamente, apelar a la alarma, o exagerar para atraer clics"
    )
    lead_orientation: Literal["social", "oficialista", "tecnico"] = Field(
        description=(
            "Con qué abre el primer párrafo: social (queja/vivencia ciudadana), "
            "oficialista (declaración de autoridad/institución), tecnico (dato o cifra)"
        )
    )
    dominant_actor: str = Field(
        description="Nombre de la entidad listada con más peso en la nota (quien abre o tiene la última palabra); '' si ninguna"
    )
    source_quality: Literal[
        "citas_directas", "testimonios_anonimos", "datos_duros", "mixtas", "sin_fuentes"
    ] = Field(
        description=(
            "Tipo de fuente predominante: citas_directas (declaraciones "
            "atribuidas con nombre), testimonios_anonimos ('usuarios aseguran'), "
            "datos_duros (cifras oficiales/estadísticas), mixtas, sin_fuentes"
        )
    )
    has_hard_data: bool = Field(
        description="true si la nota incluye cifras verificables (montos, porcentajes, MW, tarifas)"
    )
    blamed_actor: str = Field(
        description="Entidad señalada como causante del problema; '' si la nota no culpa a nadie"
    )
    credited_actor: str = Field(
        description="Entidad presentada como quien resuelve o mejora la situación; '' si no hay"
    )


# Versión del prompt/esquema de salida (§2.1 de task.md): subirla cuando
# cambie _SYSTEM o los campos/descripciones de _Analysis/_Entity, para poder
# distinguir en la BD qué filas se generaron con qué versión del prompt.
_PROMPT_VERSION = "1"

_SYSTEM = (
    "Eres un analista de prensa dominicana. Analizas artículos en español y "
    "extraes: tema principal, palabras clave, sentimiento global, y las figuras "
    "públicas y empresas mencionadas junto con la opinión que el artículo expresa "
    "hacia cada una.\n\n"
    "Reglas para entidades:\n"
    "- Devuelve cada persona/organización UNA sola vez, con su nombre más "
    "completo. Si el artículo alterna 'Abinader' y 'Luis Abinader', es UNA "
    "entidad 'Luis Abinader' y mentions_count suma todas las variantes "
    "(apellido solo, nombre de pila, cargo + apellido).\n"
    "- Si una figura pública ampliamente conocida aparece solo por apellido o "
    "cargo y su identidad es inequívoca en el contexto dominicano, usa su "
    "nombre completo estándar (p.ej. 'Abinader' -> 'Luis Abinader').\n"
    "- NO incluyas personas cuyo nombre aparece únicamente porque bautiza un "
    "lugar, calle, salón, edificio, monumento o evento en su honor ('avenida "
    "Abraham Lincoln', 'Salón Juan Bosch'), ni personas que solo reciben un "
    "homenaje sin actuar en la noticia.\n"
    "- Solo entidades que el texto realmente menciona; no inventes ninguna.\n\n"
    "Palabras clave: de 3 a 8, en minúsculas, específicas del artículo (temas y "
    "conceptos, no los nombres de las entidades ya listadas), sin sinónimos "
    "repetidos.\n\n"
    "Sentimiento (siempre POS, NEG o NEU): NEG si el artículo deja mal parada a "
    "la entidad (acusaciones, críticas, fracasos, escándalos); POS si la deja "
    "bien (logros, elogios, anuncios favorables, obras entregadas); NEU si solo "
    "se le menciona sin carga valorativa. Sé objetivo: 'sentiment_toward' "
    "refleja cómo queda la entidad según el artículo, no tu opinión personal.\n\n"
    "Encuadre y actores: clasifica además el marco de la nota (framing), la "
    "intención del titular, con qué abre el lead, el tipo de fuentes y los "
    "actores. 'dominant_actor', 'blamed_actor' y 'credited_actor' deben ser "
    "nombres EXACTOS de entidades que ya listaste en 'entities' (o '' si no "
    "aplica). Analiza el texto tal como está escrito: el encuadre es el del "
    "medio, no tu valoración de los hechos."
)


def _norm_sentiment(value: str) -> str:
    v = (value or "").strip().upper()[:3]
    return v if v in _SENTIMENTS else "NEU"


class GeminiAnalyzer:
    name = "gemini"
    version = _PROMPT_VERSION

    def __init__(self, model: str = "gemini-3.5-flash", thinking_budget: int = 0) -> None:
        # gemini-3.5-flash: buen equilibrio calidad/coste. Usa "gemini-3.5-pro"
        # para máxima precisión (más caro).
        #
        # thinking_budget=0 apaga el "thinking" (razonamiento interno) de los
        # modelos 2.5: por defecto Gemini gasta tokens de salida adicionales
        # (facturados, no visibles) "pensando" antes de responder. Para esta
        # tarea —extracción estructurada con schema fijo, no razonamiento
        # multi-paso— el thinking no mejora la calidad de forma perceptible y
        # puede duplicar o triplicar el coste por artículo. gemini-3.5-pro no
        # permite budget=0 (mínimo 128); si se usa ese modelo, súbelo a 128.
        self.model = model
        self.thinking_budget = thinking_budget
        self._client = None

    @property
    def client(self):
        if self._client is None:
            from google import genai  # import perezoso: solo si se usa este analizador

            # Toma la API key de GEMINI_API_KEY o GOOGLE_API_KEY del entorno.
            self._client = genai.Client()
        return self._client

    def analyze(self, title: str, body: str) -> AnalysisResult:
        body = (body or "")[:_MAX_BODY_CHARS]
        prompt = f"Analiza este artículo de periódico.\n\nTITULAR: {title}\n\nCUERPO:\n{body}"

        # Salida estructurada: Gemini valida la respuesta contra el esquema Pydantic.
        response = self.client.models.generate_content(
            model=self.model,
            contents=prompt,
            config={
                "system_instruction": _SYSTEM,
                "response_mime_type": "application/json",
                "response_schema": _Analysis,
                "temperature": 0.0,
                # Evita gastar tokens de salida en "thinking" para una tarea
                # de extracción con schema fijo (ver comentario en __init__).
                "thinking_config": {"thinking_budget": self.thinking_budget},
                # Tope de seguridad: el JSON esperado (tema + hasta ~15
                # entidades con contexto corto) no debería superar esto salvo
                # que el modelo se desvíe.
                "max_output_tokens": 2048,
            },
        )
        data: _Analysis = response.parsed
        if data is None:
            # Pasa si el modelo agota max_output_tokens o devuelve JSON
            # inválido; sin este guard el fallo sería un AttributeError críptico.
            raise RuntimeError(
                "Gemini no devolvió un análisis parseable "
                f"(finish_reason={getattr(response.candidates[0], 'finish_reason', '?') if response.candidates else '?'})"
            )

        entities = [
            EntityResult(
                name=e.name.strip(),
                type="ORG" if e.type == "ORG" else "PERSON",
                mentions_count=max(1, e.mentions_count),
                sentiment_toward=_norm_sentiment(e.sentiment_toward),
                sentiment_score=None,  # el LLM no devuelve una probabilidad calibrada
                context=(e.context or "").strip() or None,
            )
            for e in data.entities
        ]

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
