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
from analysis.sentiment_lexicon import PROMPT_GLOSSARY

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
    confidence: float = Field(
        description=(
            "Qué tan seguro estás de que 'name' es el nombre canónico correcto "
            "y de que TODAS las variantes que fusionaste (apellido solo, "
            "apodo, cargo + apellido) se refieren realmente a esta misma "
            "entidad, basándote SOLO en el contexto de este artículo. 1.0 = "
            "certeza total (nombre completo inequívoco, sin variantes "
            "ambiguas). Baja (<0.7) cuando tuviste que asumir a quién se "
            "refería una mención parcial o genérica ('el mandatario', "
            "'Molina') sin que el texto lo confirmara sin dudas."
        )
    )
    confidence_reason: str = Field(
        description="Una frase breve explicando el motivo de la confianza asignada, especialmente si es baja (p.ej. 'apellido único en el texto, sin ambigüedad' o 'referencia genérica sin nombre propio cercano')"
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
_PROMPT_VERSION = "5"

_SYSTEM = (
    "Eres un analista senior de prensa dominicana, especializado en evaluación "
    "objetiva de noticias políticas e institucionales. Analizas artículos en "
    "español y extraes: tema principal, palabras clave, sentimiento global, "
    "las figuras públicas y empresas mencionadas junto con la opinión que el "
    "artículo expresa hacia cada una, y el encuadre editorial de la nota.\n\n"
    "PRINCIPIOS METODOLÓGICOS (aplican a TODO el análisis, no solo al "
    "encuadre):\n"
    "- No infieras intenciones que el texto no expresa explícita o "
    "implícitamente. Si el texto no lo dice ni lo sugiere con claridad, no lo "
    "asumas.\n"
    "- Separa hechos de opiniones: una declaración atribuida a alguien "
    "('el ministro afirmó que...') es su opinión, no un hecho verificado por "
    "el medio; no la trates como si el medio la respaldara.\n"
    "- Clasifica el sentimiento y el encuadre según cómo el TEXTO trata al "
    "actor en ESTA nota, nunca según tu conocimiento previo o reputación de "
    "esa persona/institución fuera del artículo.\n"
    "- No uses información externa al texto para evaluar el contenido "
    "(contexto histórico, lo que tú sepas de la persona, eventos no "
    "mencionados).\n"
    "- Evalúas el ENCUADRE (framing): cómo se presenta el hecho o el actor, "
    "no si el hecho es verdadero, falso, justo o injusto.\n"
    "- Si una mención de una entidad no trae valoración explícita ni "
    "implícita clara, es NEU — una mención no implica apoyo ni rechazo.\n\n"
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
    "Sentimiento hacia cada entidad (siempre POS, NEG o NEU): NEG si el "
    "tratamiento en la nota la deja mal parada — acusaciones, críticas, "
    "escándalos, corrupción, fracasos, errores; POS si el tratamiento la deja "
    "bien — felicitaciones, logros presentados, avances explicados, una "
    "medida defendida, resultados resaltados; NEU si el texto solo la "
    "menciona o narra hechos sobre ella sin valoración. Justifica cada "
    "clasificación con la frase concreta del texto que la sustenta (campo "
    "'context').\n\n"
    f"{PROMPT_GLOSSARY}\n\n"
    "Encuadre y actores: clasifica además el marco de la nota (framing), la "
    "intención del titular, con qué abre el lead, el tipo de fuentes y los "
    "actores. 'dominant_actor', 'blamed_actor' y 'credited_actor' deben ser "
    "nombres EXACTOS de entidades que ya listaste en 'entities' (o '' si no "
    "aplica). Marca un actor como 'blamed_actor' o 'credited_actor' SOLO si "
    "el texto explícitamente lo señala como causante o como quien resuelve — "
    "no lo infieras de su cargo ni de quién luce mejor o peor en general. Si "
    "el titular y el cuerpo tienen intención distinta (titular alarmista "
    "sobre un cuerpo informativo, por ejemplo), 'headline_intent' describe "
    "SOLO el titular; el resto de los campos de encuadre describen el "
    "cuerpo."
)


def _norm_sentiment(value: str) -> str:
    v = (value or "").strip().upper()[:3]
    return v if v in _SENTIMENTS else "NEU"


def _entity_from_llm(e: _Entity) -> EntityResult:
    """Mapea la entidad devuelta por el LLM (Gemini o Groq, mismo schema
    `_Entity`) a `EntityResult`. `confidence`/`confidence_reason` van al
    mismo campo `extraction_confidence`/`context` que ya usa el frontend para
    el badge "revisar" (`extraction_confidence < 0.9`, ver
    frontend/src/lib/format.ts) — no hace falta un campo nuevo en el schema
    de BD, el LLM solo empieza a llenar uno que antes quedaba en el default
    1.0 (certeza asumida) para cualquier Analyzer que no lo calculara."""
    reason = (e.confidence_reason or "").strip()
    context = (e.context or "").strip()
    combined_context = f"{context} [{reason}]" if reason else context or None
    return EntityResult(
        name=e.name.strip(),
        type="ORG" if e.type == "ORG" else "PERSON",
        mentions_count=max(1, e.mentions_count),
        sentiment_toward=_norm_sentiment(e.sentiment_toward),
        sentiment_score=None,  # el LLM no devuelve una probabilidad calibrada
        context=combined_context,
        extraction_confidence=round(min(max(e.confidence, 0.0), 1.0), 2),
    )


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
        from observability import GEMINI_REQUESTS_TOTAL, GEMINI_TOKENS_TOTAL

        body = (body or "")[:_MAX_BODY_CHARS]
        prompt = f"Analiza este artículo de periódico.\n\nTITULAR: {title}\n\nCUERPO:\n{body}"

        # Salida estructurada: Gemini valida la respuesta contra el esquema Pydantic.
        try:
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
                    # entidades, cada una con context+confidence_reason) no
                    # debería superar esto salvo que el modelo se desvíe. 4096 y
                    # no 2048: con confidence/confidence_reason por entidad (ver
                    # _Entity) un artículo con muchas entidades se acerca al
                    # límite anterior y el análisis termina truncado a mitad de
                    # JSON (data is None abajo, finish_reason="MAX_TOKENS").
                    "max_output_tokens": 4096,
                },
            )
        except Exception:
            GEMINI_REQUESTS_TOTAL.labels(model=self.model, status="error").inc()
            raise

        usage = getattr(response, "usage_metadata", None)
        if usage is not None:
            GEMINI_TOKENS_TOTAL.labels(model=self.model, kind="prompt").inc(
                usage.prompt_token_count or 0
            )
            GEMINI_TOKENS_TOTAL.labels(model=self.model, kind="output").inc(
                (usage.candidates_token_count or 0) + (usage.thoughts_token_count or 0)
            )

        data: _Analysis = response.parsed
        if data is None:
            # Pasa si el modelo agota max_output_tokens o devuelve JSON
            # inválido; sin este guard el fallo sería un AttributeError críptico.
            GEMINI_REQUESTS_TOTAL.labels(model=self.model, status="error").inc()
            raise RuntimeError(
                "Gemini no devolvió un análisis parseable "
                f"(finish_reason={getattr(response.candidates[0], 'finish_reason', '?') if response.candidates else '?'})"
            )
        GEMINI_REQUESTS_TOTAL.labels(model=self.model, status="success").inc()

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
