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
from analysis.entity_verify import recount_mentions, verify_entities
from analysis.sentiment_lexicon import PROMPT_GLOSSARY

_SENTIMENTS = ("POS", "NEG", "NEU")
_MAX_BODY_CHARS = 16_000  # acota tokens/coste por artículo
_REQUEST_TIMEOUT_MS = 45_000  # ver el comentario en `GeminiAnalyzer.client`

Sentiment = Literal["POS", "NEG", "NEU"]


class _Entity(BaseModel):
    # Orden deliberado (§ "afinar el prompt" para /api/analyze): con
    # response_schema, el modelo genera los campos EN ESTE ORDEN (salida
    # estructurada = igual de autoregresiva que el texto libre). Cada campo de
    # evidencia/justificación va ANTES del campo de conclusión que sustenta
    # (context -> sentiment_toward, confidence_reason -> confidence), para que
    # el modelo escriba la cita/razón primero y la clasificación se apoye en
    # ella — al revés (como estaba antes) el modelo se compromete con la
    # etiqueta antes de haber "mirado" la evidencia que se supone la justifica.
    name: str = Field(description="Nombre de la figura pública o empresa")
    type: Literal["PERSON", "ORG"] = Field(description="PERSON o ORG (empresa/organización)")
    mentions_count: int = Field(description="Menciones aproximadas en el artículo")
    context: str = Field(description="Cita textual (máx. 12 palabras) que justifica el sentimiento")
    sentiment_toward: Sentiment = Field(
        description="Opinión del artículo hacia esta entidad, según la cita de 'context'"
    )
    sentiment_confidence: float = Field(
        description=(
            "0..1: qué tan marcada e inequívoca es esa opinión en el texto. "
            "1.0 = valoración explícita y rotunda; 0.5 = leve o indirecta; "
            "<0.4 = casi neutra, la etiqueta es dudosa"
        )
    )
    confidence_reason: str = Field(
        description="Motivo breve de 'confidence' (p.ej. 'apellido único, sin ambigüedad')"
    )
    confidence: float = Field(
        description=(
            "0..1: certeza de que 'name' es el nombre canónico y de que las "
            "variantes fusionadas (apellido, apodo, cargo) son la MISMA entidad, "
            "según SOLO este artículo. <0.7 si asumiste a quién se refería una "
            "mención parcial"
        )
    )


# NOTA: deliberadamente SIN docstring de clase. Pydantic copia el docstring al
# JSON schema como "description", y el schema viaja completo en CADA llamada —
# con el TPM de 8000 del free tier de Groq, cada token fijo aquí es un token
# menos para el artículo. Misma razón por la que las `description` de los
# campos de abajo son telegráficas: son instrucciones que se pagan por request,
# no documentación. Lo que el lector humano necesita saber va en comentarios
# como este, que no salen del archivo.
#
# El orden de los campos NO es cosmético: con salida estructurada el modelo los
# genera en este orden, así que cada campo se apoya solo en lo ya escrito.
# Bloques: 1) observación del texto, 2) entidades (cita antes que etiqueta,
# ver `_Entity`), 3) atribución —de quién es la polaridad: hechos reportados
# vs. discurso citado vs. voz del medio, tres capas distintas que no deben
# colapsarse—, 4) actores (necesitan `entities` ya escrito), 5) clasificación
# global al final: justificación en prosa y solo después la etiqueta.
class _Analysis(BaseModel):
    # --- 1. Observación del texto -------------------------------------------
    main_topic: str = Field(description="Tema principal en pocas palabras, p.ej. 'agua potable'")
    topic_keywords: list[str] = Field(description="3 a 8 palabras clave del artículo")
    source_quality: Literal[
        "citas_directas", "testimonios_anonimos", "datos_duros", "mixtas", "sin_fuentes"
    ] = Field(
        description=(
            "Fuente predominante. citas_directas=atribuidas con nombre; "
            "testimonios_anonimos='usuarios aseguran'; datos_duros=cifras oficiales"
        )
    )
    has_hard_data: bool = Field(
        description="true si hay cifras verificables (montos, porcentajes, MW, tarifas)"
    )
    lead_orientation: Literal["social", "oficialista", "tecnico"] = Field(
        description=(
            "Con qué abre el primer párrafo. social=queja/vivencia ciudadana; "
            "oficialista=declaración de autoridad; tecnico=dato o cifra"
        )
    )
    content_flags: list[
        Literal["alarmismo", "sensacionalismo", "dato_no_verificable", "posible_ironia"]
    ] = Field(
        description=(
            "0 o varias ([] si ninguna). alarmismo=exagera amenaza sin sustento; "
            "sensacionalismo=busca reacción emocional sobre información; "
            "dato_no_verificable=cifras sin fuente; posible_ironia=el sentido "
            "literal no es el pretendido"
        )
    )

    # --- 2. Entidades (cada una: cita -> etiqueta, ver `_Entity`) -----------
    entities: list[_Entity] = Field(
        description=(
            "Figuras públicas y empresas mencionadas, con la opinión hacia cada "
            "una. Máximo 15, las de más peso en la nota"
        )
    )

    # --- 3. Atribución: ¿de quién es la polaridad? --------------------------
    sentiment_basis: Literal["hechos_reportados", "discurso_citado", "mixto"] = Field(
        description=(
            "Dónde reside la carga. hechos_reportados=buenos/malos por sí mismos; "
            "discurso_citado=está en lo que dicen las fuentes; mixto=ambas pesan igual"
        )
    )
    facts_sentiment: Sentiment = Field(
        description=(
            "Polaridad de los HECHOS reportados como ocurridos, al margen de quién "
            "opine. NEU si la nota solo recoge declaraciones"
        )
    )
    quoted_sentiment: Sentiment = Field(
        description=(
            "Polaridad del DISCURSO CITADO. NEU si no hay citas o no tienen carga. "
            "Puede diferir de facts_sentiment"
        )
    )
    media_stance_evidence: str = Field(
        description=(
            "Señal textual breve que justifica media_stance: verbo de reporte "
            "('denunció' vs 'informó'), si todo va atribuido, si hay réplica, si "
            "el medio adjetiva por cuenta propia"
        )
    )
    media_stance: Literal[
        "neutra_transmisiva", "critica", "favorable", "editorializante"
    ] = Field(
        description=(
            "Postura de la VOZ DEL MEDIO, no de las fuentes que cita. "
            "neutra_transmisiva=atribuye sin adjetivar; critica/favorable=el medio "
            "cuestiona/respalda por cuenta propia. Recoger una denuncia feroz NO "
            "hace crítico al medio"
        )
    )

    # --- 4. Actores del encuadre (requieren `entities` ya escrito) ----------
    dominant_actor: str = Field(
        description="Entidad ya listada con más peso en la nota; '' si ninguna"
    )
    blamed_actor: str = Field(
        description="Entidad señalada como causante del problema; '' si no hay"
    )
    credited_actor: str = Field(
        description="Entidad presentada como quien resuelve o mejora; '' si no hay"
    )

    # --- 5. Clasificación global (última: justificación -> etiqueta) --------
    framing: Literal[
        "crisis_conflicto",
        "logro_institucional",
        "negligencia",
        "crecimiento",
        "denuncia",
        "neutro_informativo",
    ] = Field(
        description=(
            "Encuadre de la nota. crisis_conflicto=falla del servicio, sufrimiento "
            "ciudadano o disputa; logro_institucional=obra entregada, récord, "
            "eficiencia; negligencia=se culpa la inacción de una autoridad; "
            "crecimiento=el problema es efecto del auge económico; denuncia=reclamo "
            "de un sector; neutro_informativo=sin ángulo marcado"
        )
    )
    headline_intent: Literal["informativo", "alarmista", "sensacionalista"] = Field(
        description="Intención del TITULAR: informar, alarmar, o exagerar para atraer clics"
    )
    overall_sentiment_reason: str = Field(
        description=(
            "Una o dos oraciones que justifican la etiqueta global, apoyadas en lo "
            "ya analizado (hechos vs discurso, postura del medio, entidades)"
        )
    )
    overall_sentiment: Sentiment = Field(
        description="Sentimiento global, coherente con la justificación anterior"
    )


def _strip_titles(node):
    """Quita recursivamente las claves `title` que Pydantic agrega al JSON
    schema ("Main Topic", "Topic Keywords"...).

    No aportan nada al modelo —el nombre del campo ya está ahí, y la
    instrucción real vive en `description`— pero el schema viaja completo en
    CADA request. Con el TPM de 8.000 del free tier de Groq son ~120 tokens
    fijos por llamada que salen del presupuesto del artículo.
    """
    if isinstance(node, dict):
        return {k: _strip_titles(v) for k, v in node.items() if k != "title"}
    if isinstance(node, list):
        return [_strip_titles(v) for v in node]
    return node


# Se calcula UNA vez al importar, no en cada llamada: es el mismo schema
# siempre y `model_json_schema()` no es gratis.
ANALYSIS_JSON_SCHEMA = _strip_titles(_Analysis.model_json_schema())


# Versión del prompt/esquema de salida (§2.1 de task.md): subirla cuando
# cambie _SYSTEM o los campos/descripciones de _Analysis/_Entity, para poder
# distinguir en la BD qué filas se generaron con qué versión del prompt.
_PROMPT_VERSION = "7"

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
    "- CUATRO CAPAS que evalúas por separado, sin mezclar: hechos reportados "
    "(facts_sentiment), discurso citado (quoted_sentiment), voz del medio "
    "(media_stance) y cada entidad (sentiment_toward). Una nota puede reportar "
    "hechos graves con voz neutra. 'Malas noticias' ≠ 'artículo negativo'.\n"
    "- Clasifica el sentimiento y el encuadre según cómo el TEXTO trata al "
    "actor en ESTA nota, nunca según tu conocimiento previo o reputación de "
    "esa persona/institución fuera del artículo.\n"
    "- No uses información externa al texto para evaluar el contenido "
    "(contexto histórico, lo que tú sepas de la persona, eventos no "
    "mencionados).\n"
    "- Evalúas el ENCUADRE (framing): cómo se presenta el hecho o el actor, "
    "no si el hecho es verdadero, falso, justo o injusto.\n"
    "- Si una mención de una entidad no trae valoración explícita ni "
    "implícita clara, es NEU — una mención no implica apoyo ni rechazo.\n"
    "- Presta atención a negaciones, desmentidos y condicionales ('no fue "
    "acusado', 'negó las acusaciones', 'descartó irregularidades', 'de "
    "confirmarse'): invierten o anulan la carga de la palabra que sigue. "
    "Clasifica según lo que el texto AFIRMA que ocurrió, no según la "
    "presencia aislada de una palabra con carga fuerte.\n\n"
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


def _clamp01(value: float) -> float:
    return round(min(max(value, 0.0), 1.0), 2)


def _entity_from_llm(e: _Entity) -> EntityResult:
    """Mapea la entidad devuelta por el LLM (Gemini o Groq, mismo schema
    `_Entity`) a `EntityResult`. `confidence`/`confidence_reason` van al
    mismo campo `extraction_confidence`/`context` que ya usa el frontend para
    el badge "revisar" (`extraction_confidence < 0.9`, ver
    frontend/src/lib/format.ts) — no hace falta un campo nuevo en el schema
    de BD, el LLM solo empieza a llenar uno que antes quedaba en el default
    1.0 (certeza asumida) para cualquier Analyzer que no lo calculara.

    Lo mismo con `sentiment_confidence` -> `sentiment_score`: la columna
    existía y con los analizadores LLM quedaba SIEMPRE en NULL, así que la
    opinión hacia una entidad era un POS/NEG/NEU plano, sin forma de ordenar
    por intensidad ni de distinguir un "NEG rotundo" de un "NEG apenas
    insinuado". No es la misma magnitud que la de `LocalAnalyzer` (allí es la
    probabilidad agregada de pysentimiento; aquí, cuán marcada ve el modelo la
    valoración), pero sí responde a la misma pregunta y el linaje guardado
    (`analyzer_name`) dice cuál de las dos es.
    """
    reason = (e.confidence_reason or "").strip()
    context = (e.context or "").strip()
    combined_context = f"{context} [{reason}]" if reason else context or None
    return EntityResult(
        name=e.name.strip(),
        type="ORG" if e.type == "ORG" else "PERSON",
        mentions_count=max(1, e.mentions_count),
        sentiment_toward=_norm_sentiment(e.sentiment_toward),
        sentiment_score=_clamp01(e.sentiment_confidence),
        context=combined_context,
        extraction_confidence=_clamp01(e.confidence),
    )


def _result_from_llm(data: _Analysis, source_text: str) -> AnalysisResult:
    """Mapea la respuesta del LLM a `AnalysisResult`, contrastando antes las
    entidades con el texto del artículo.

    Compartido por `GeminiAnalyzer` y por Groq (`_analyze_full` en
    `analysis/groq_analyzer.py`): ambos usan el MISMO `_Analysis`, así que el
    mapeo vive en un solo sitio — cuando se agrega un campo al schema no puede
    quedarse a medias en un proveedor y no en el otro, que es exactamente cómo
    se pierde un campo nuevo en silencio. Por la misma razón la verificación
    (`analysis/entity_verify.py`) se hace aquí dentro y no en cada analizador:
    ningún proveedor puede saltársela por olvido.

    `source_text` es el artículo COMPLETO, no el recorte que se le mandó al
    modelo: sirve para contar menciones que quedaron fuera del tope.
    """
    entities = [_entity_from_llm(e) for e in data.entities]
    entities = verify_entities(entities, source_text)
    recount_mentions(entities, source_text)
    entities.sort(key=lambda e: e.mentions_count, reverse=True)
    return AnalysisResult(
        main_topic=data.main_topic.strip() or None,
        topic_keywords=[k.strip() for k in data.topic_keywords if k.strip()],
        overall_sentiment=_norm_sentiment(data.overall_sentiment),
        sentiment_score=None,  # el LLM no devuelve una probabilidad calibrada
        entities=entities,
        framing=data.framing,
        headline_intent=data.headline_intent,
        lead_orientation=data.lead_orientation,
        dominant_actor=data.dominant_actor.strip() or None,
        source_quality=data.source_quality,
        has_hard_data=data.has_hard_data,
        blamed_actor=data.blamed_actor.strip() or None,
        credited_actor=data.credited_actor.strip() or None,
        sentiment_basis=data.sentiment_basis,
        facts_sentiment=_norm_sentiment(data.facts_sentiment),
        quoted_sentiment=_norm_sentiment(data.quoted_sentiment),
        media_stance=data.media_stance,
        media_stance_evidence=data.media_stance_evidence.strip() or None,
        overall_sentiment_reason=data.overall_sentiment_reason.strip() or None,
        # dict.fromkeys y no set(): quita repetidos conservando el orden en que
        # el modelo los emitió, para que la lista guardada sea estable.
        content_flags=list(dict.fromkeys(data.content_flags)),
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
            # El timeout (en MILISEGUNDOS, así lo define HttpOptions) es
            # explícito porque este analizador suele ser el último eslabón:
            # cuando entra como fallback de Groq, el tiempo que tarde se suma
            # al que ya se gastó, y el frontend deja de esperar el job en algún
            # momento (JOB_POLL_TIMEOUT_MS en frontend/src/lib/odin-api.ts).
            # Sin tope, una llamada colgada convierte un análisis ya pagado en
            # un resultado que nadie llega a ver.
            self._client = genai.Client(http_options={"timeout": _REQUEST_TIMEOUT_MS})
        return self._client

    def analyze(self, title: str, body: str) -> AnalysisResult:
        from observability import GEMINI_REQUESTS_TOTAL, GEMINI_TOKENS_TOTAL

        full_body = body or ""
        body = full_body[:_MAX_BODY_CHARS]
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
                    # debería superar esto salvo que el modelo se desvíe.
                    #
                    # 6144 y no 4096 desde que el esquema sumó las capas de
                    # atribución y las justificaciones en prosa. A diferencia de
                    # Groq —donde este tope se RESERVA contra el TPM y subirlo
                    # provoca 413— en Gemini es un cap de verdad: se factura lo
                    # que se genera, así que el margen extra no cuesta nada
                    # mientras no se use, y evita perder el análisis entero por
                    # un truncado (data is None abajo, finish_reason="MAX_TOKENS").
                    "max_output_tokens": 6144,
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

        return _result_from_llm(data, f"{title}\n{full_body}")
