"""Analizador local (gratis) en español.

Combina:
  - spaCy (es_core_news_lg) -> segmentación de frases + NER (PERSON / ORG)
  - pysentimiento -> sentimiento en español (POS / NEG / NEU)

Rendimiento: el sentimiento de cada frase ÚNICA se calcula UNA sola vez y se
reutiliza tanto para el sentimiento global como para el de cada entidad (antes
se recalculaba por frase y por entidad, con ~38% de llamadas redundantes).

Campos:
  - main_topic / topic_keywords: sustantivos y nombres propios frecuentes;
    el tema principal prefiere una frase nominal ("agua potable") si existe.
  - overall_sentiment: sentimiento agregado sobre TODAS las frases del artículo,
    reforzado por frase con el glosario político de
    `analysis/sentiment_lexicon.py` antes de agregar (ver `_predict_batch`).
  - entities + sentiment_toward: por cada figura/empresa se agregan las frases
    donde se le menciona. Los nombres se normalizan y se fusionan alias
    ("Policía" -> "Policía Nacional"). Esas frases también se refuerzan con
    el léxico RELACIONAL de `analysis/sentiment_lexicon.py` ("acusado de",
    "reconocido por"): a diferencia del léxico general (que se aplica a toda
    frase por igual), este solo aplica sobre las frases ya asociadas a esa
    entidad puntual, y dentro de la frase solo a la mención que RECIBE la
    acción — la más cercana antes del patrón (ver `_relational_boosts`), para
    no dejar mal parado también a quien acusa.

NOTA: `sentiment_toward` es una aproximación por frase (aspect-based sentiment
sencillo). Para máxima precisión, sustituir por el analizador con LLM (misma
interfaz Analyzer); ver analysis/gemini_analyzer.py.
"""
from __future__ import annotations

from collections import Counter, defaultdict
from collections.abc import Sequence
from dataclasses import dataclass

from odin.analysis.base import AnalysisResult, EntityResult
from odin.analysis.sentiment_lexicon import apply_boost as _apply_sentiment_boost
from odin.analysis.sentiment_lexicon import apply_label_boost as _apply_label_boost
from odin.analysis.sentiment_lexicon import entity_relation_hits as _entity_relation_hits
from odin.analysis.text_norm import norm_key as _norm_key
from odin.analysis.text_norm import strip_accents as _strip_accents

# Versión de la heurística de LocalAnalyzer (§2.1 de task.md): subirla cuando
# cambie una regla que afecta el resultado (_VENUE_WORDS, _is_named_after_place,
# _merge_aliases, umbrales de _extraction_confidence, el glosario de
# analysis/sentiment_lexicon.py...), para poder distinguir en la BD qué filas
# se analizaron con qué versión del código.
_LOCAL_ANALYZER_VERSION = "6"

_MAX_SENT_CHARS = 500        # límite por frase para el modelo de sentimiento
_MAX_SENTENCES = 400         # tope de seguridad para artículos patológicos
_STOP_ENTITY_TOKENS = {"foto", "video", "listín", "listin", "diario", "libre"}
# palabras de estado/país genéricas: spaCy a veces las etiqueta como ORG
# cuando aparecen solas y capitalizadas ("presidente... de la República"),
# pero no son el nombre propio de ninguna organización real. Solo se filtran
# cuando son la entidad COMPLETA (p.ej. "República Dominicana" sigue
# reconociéndose porque ahí "República" no es el span entero).
#
# "gobierno" NO está en esta lista a propósito (medido contra el golden set,
# tests/eval/golden_set.jsonl: 12 de 131 entidades ORG etiquetadas a mano
# son literalmente "Gobierno" — 9.2% del total — y el filtro viejo las
# perdía las 7 verificadas en vivo). A diferencia de "República"/"Estado"
# sueltos, "el Gobierno" SÍ es como la prensa dominicana nombra al actor
# político de turno ("el Gobierno sostiene que...", "acusó al Gobierno de
# ..."), no una referencia vaga al país.
_GENERIC_STATE_ORGS = {
    "republica", "estado", "nacion", "pais", "administracion",
}
# las 31 provincias de RD + el Distrito Nacional: spaCy las etiqueta como
# PERSON cuando aparecen solas y capitalizadas entre paréntesis tras un nombre
# propio ("Moisés Ayala Pérez, (Barahona)") — el patrón "Nombre, (Lugar)" no
# le da suficiente contexto para distinguir el gentilicio del topónimo. Se
# filtran solo cuando son la entidad COMPLETA (mismo criterio que
# _GENERIC_STATE_ORGS): "Santiago" a secas cae aquí, pero "Santiago Zorrilla
# Sena" no, porque el span entero no coincide con ningún nombre de la lista.
_DOMINICAN_PROVINCES = {
    "azua", "bahoruco", "barahona", "dajabon", "distrito nacional",
    "duarte", "el seibo", "elias pina", "espaillat", "hato mayor",
    "hermanas mirabal", "independencia", "la altagracia", "la romana",
    "la vega", "maria trinidad sanchez", "monsenor nouel", "monte cristi",
    "montecristi", "monte plata", "pedernales", "peravia", "puerto plata",
    "samana", "san cristobal", "san jose de ocoa", "san juan",
    "san pedro de macoris", "sanchez ramirez", "santiago",
    "santiago rodriguez", "santo domingo", "valverde",
}
# tipos de entidad de spaCy que nos interesan -> tipo canónico
_WANTED_ENT = {"PER": "PERSON", "PERSON": "PERSON", "ORG": "ORG"}
# partículas que no rompen un nombre propio ("Policía del Distrito Nacional")
_NAME_PARTICLES = {"de", "del", "la", "las", "los", "y", "e"}
# marcas/redes sociales que spaCy suele etiquetar como PERSON por error
_KNOWN_ORGS = {
    "instagram", "facebook", "twitter", "x", "tiktok", "youtube",
    "whatsapp", "telegram", "linkedin",
}
# sustantivos de lugar/institución: cuando un nombre de persona cuelga de uno
# de estos (de cerca, o como cabeza en el árbol de dependencias), casi siempre
# es un topónimo/edificio/vía que lleva ese nombre en su honor, no la persona
# actuando en la noticia ("Casa del Pueblo Johnny Ventura", "avenida Abraham
# Lincoln", "Sala de Conferencias Juan Bosch").
_VENUE_WORDS = {
    "calle", "avenida", "autopista", "carretera", "salon", "sala",
    "auditorio", "asamblea", "conferencia", "coliseo", "estadio",
    "polideportivo", "gimnasio", "palacio", "casa", "centro", "complejo",
    "plaza", "plazoleta", "parque", "malecon", "puente", "glorieta",
    "rotonda", "monumento", "iglesia", "parroquia", "catedral", "escuela",
    "liceo", "colegio", "universidad", "instituto", "biblioteca", "museo",
    "teatro", "hospital", "clinica", "hotel", "aeropuerto", "puerto",
    "mercado", "club", "estacion", "terminal", "edificio", "torre",
    "residencial", "urbanizacion", "sector", "barrio", "condominio",
    "circunscripcion", "demarcacion", "subalcaldia", "subsecretaria",
    "tribunal", "gabinete", "despacho", "consultorio", "villa",
    # no son lugares, pero funcionan igual sintácticamente ("el homenaje a
    # Juan Pablo Duarte", "en honor a..."): el nombre que sigue no actúa, solo
    # recibe el homenaje/da nombre a algo.
    "homenaje", "honor", "tributo", "reconocimiento", "memoria",
}
# relaciones de dependencia que conectan un nombre propio con la palabra que
# describe qué es (para subir por la cadena y encontrar la cabeza real).
_HEAD_CHAIN_DEPS = {"appos", "flat", "nmod", "conj"}


def sentence_mentions_venue_word(text: str) -> bool:
    """True si el texto contiene alguna palabra de `_VENUE_WORDS` (chequeo
    léxico simple, sin spaCy) — usado para decidir cuándo vale la pena
    preguntarle al árbitro de Gemini si una mención de PERSON es ambigua."""
    words = _strip_accents(text.lower()).split()
    return any(w.strip(".,;:()\"'") in _VENUE_WORDS for w in words)


def _preceded_by_venue_noun(ent, window: int = 10) -> bool:
    """Mira hacia atrás desde la entidad (la más cercana primero); se detiene
    al cruzar un verbo, que marca el límite de la cláusula/sintagma actual.

    Respaldo barato de `_is_named_after_place` por si el parser de
    dependencias se equivoca; no depende del árbol, solo del orden lineal.
    """
    sent = ent.sent
    start = max(ent.start - window, sent.start if sent is not None else 0)
    for tok in reversed(ent.doc[start : ent.start]):
        if tok.pos_ == "VERB":
            break
        if _strip_accents(tok.lemma_.lower()) in _VENUE_WORDS:
            return True
    return False


def _is_named_after_place(ent, max_hops: int = 4) -> bool:
    """Sube por la cadena de dependencias desde la entidad buscando una
    cabeza tipo "lugar" (salón, avenida, casa...). A diferencia de la ventana
    de tokens, esto no depende de la distancia ni se confunde si hay un verbo
    de otra cláusula de por medio (p.ej. "el salón X ... se realizó...").
    """
    tok = ent.root
    for _ in range(max_hops):
        head = tok.head
        if head is tok:
            break
        if head.pos_ in {"NOUN", "PROPN"} and _strip_accents(head.lemma_.lower()) in _VENUE_WORDS:
            return True
        if tok.dep_ not in _HEAD_CHAIN_DEPS:
            break
        tok = head
    return False


def _is_proper_span(ent) -> bool:
    """Un nombre real casi siempre tiene todos sus tokens como PROPN (spaCy).

    Filtra spans que mezclan un título con un subtítulo pegado sin puntuación
    (p.ej. "Leonel Cuestionamientos", donde "Cuestionamientos" es NOUN, no
    PROPN) — un error típico de segmentación, no un nombre real.

    También filtra spans TRUNCADOS que terminan en una partícula ("Secretaría
    del", "Consejo Nacional de la") — spaCy a veces corta el span de NER antes
    de completarlo (frecuente cuando la siguiente palabra del nombre real ya
    quedó etiquetada como el inicio de OTRA entidad, p.ej. "Secretaría del
    [Consejo]" donde "Consejo" se extrae aparte). Un nombre propio real nunca
    termina en una preposición/artículo suelto.
    """
    alpha_tokens = [tok for tok in ent if tok.is_alpha]
    if alpha_tokens and alpha_tokens[-1].text.lower() in _NAME_PARTICLES:
        return False
    for tok in ent:
        if not tok.is_alpha:
            continue
        if tok.lemma_.lower() in _NAME_PARTICLES or tok.text.lower() in _NAME_PARTICLES:
            continue
        if tok.pos_ != "PROPN":
            return False
    return True


def _extraction_confidence(display_name: str, etype: str, count: int) -> float:
    """Qué tan segura estuvo la extracción de que esta es una mención real,
    no ruido. Señales baratas, disponibles ya en este punto del pipeline:

    - una sola mención en todo el artículo pesa menos que varias
      (más chance de ser un acierto aislado del NER, no un patrón repetido).
    - un nombre PERSON de una sola palabra significativa ("Fernández") es
      intrínsecamente más ambiguo que uno completo, incluso después de
      intentar resolverlo (`_resolve_partial_persons` en canonicalize.py
      puede no encontrar un único candidato).

    No incluye la señal del árbitro de Gemini: ese paso corre después, en
    api.py, fuera de LocalAnalyzer.
    """
    score = 1.0
    if count == 1:
        score -= 0.15
    if etype == "PERSON":
        words = [w for w in _norm_key(display_name).split() if w not in _NAME_PARTICLES]
        if len(words) <= 1:
            score -= 0.1
    return round(max(score, 0.1), 2)


def _best_display_name(display: Counter[str]) -> str:
    """Elige la variante más COMPLETA como nombre a mostrar, no la más
    repetida: dentro de un mismo artículo una sigla puede aparecer más veces
    que el nombre completo (p.ej. "PLD" 5 veces vs. "Partido de la
    Liberación Dominicana" 1 vez), pero el nombre completo es la forma
    canónica que espera quien lee el resultado — y la que puede coincidir
    con el nombre etiquetado a mano en el golden set (medido:
    tests/eval/golden_set.jsonl, odin-db-008/013/037/038 fallaban así antes
    de esta regla). Empate en palabras significativas -> gana la más usada.
    """
    return max(
        display,
        key=lambda name: (
            len([w for w in _norm_key(name).split() if w not in _NAME_PARTICLES]),
            display[name],
        ),
    )


@dataclass
class _Sentences:
    """Las frases del documento ya recortadas, más lo necesario para ubicar
    una entidad DENTRO de ellas.

    Existe para que el sentimiento por frase y la búsqueda de patrones
    relacionales trabajen sobre exactamente el mismo texto: antes las
    probabilidades se calculaban sobre la frase recortada a `_MAX_SENT_CHARS`
    y el léxico relacional se buscaba sobre la frase completa, así que un
    patrón que cayera después del corte ajustaba un sentimiento calculado
    sobre un texto donde ese patrón no estaba.
    """

    texts: list[str]                 # frase recortada, sin espacios al borde
    doc_starts: list[int]            # offset en el doc del primer carácter de texts[i]
    index_by_start: dict[int, int]   # start_char de la frase de spaCy -> índice

    @classmethod
    def from_doc(cls, doc) -> _Sentences:
        texts: list[str] = []
        doc_starts: list[int] = []
        index_by_start: dict[int, int] = {}
        for i, sent in enumerate(list(doc.sents)[:_MAX_SENTENCES]):
            raw = sent.text
            lead = len(raw) - len(raw.lstrip())
            texts.append(raw.strip()[:_MAX_SENT_CHARS])
            doc_starts.append(sent.start_char + lead)
            index_by_start[sent.start_char] = i
        return cls(texts, doc_starts, index_by_start)

    def index_of(self, sent) -> int | None:
        """Índice de la frase, o None si quedó fuera del tope de frases."""
        return self.index_by_start.get(sent.start_char)

    def offset_of(self, index: int, ent) -> int:
        """Posición de la entidad dentro de `texts[index]`."""
        return ent.start_char - self.doc_starts[index]


def _aggregate(probas_list: Sequence[dict | None]) -> tuple[str, float]:
    """Agrega sentimiento sumando probabilidades de varias frases."""
    totals: dict[str, float] = defaultdict(float)
    n = 0
    for probas in probas_list:
        if not probas:
            continue
        for label, prob in probas.items():
            totals[label] += prob
        n += 1
    if n == 0:
        return "NEU", 0.0
    label = max(totals, key=lambda k: totals[k])
    return label, round(float(totals[label] / n), 4)


class LocalAnalyzer:
    name = "local"
    version = _LOCAL_ANALYZER_VERSION

    def __init__(self, spacy_model: str = "es_core_news_lg") -> None:
        self._spacy_model = spacy_model
        self._nlp = None
        self._sent = None

    # ---- carga perezosa de modelos ---------------------------------------------
    @property
    def nlp(self):
        if self._nlp is None:
            import spacy

            try:
                self._nlp = spacy.load(self._spacy_model)
            except OSError as exc:
                raise RuntimeError(
                    f"Falta el modelo de spaCy '{self._spacy_model}'. "
                    f"Instálalo con:  python -m spacy download {self._spacy_model}"
                ) from exc
            self._nlp.max_length = 2_000_000
        return self._nlp

    @property
    def model(self) -> str:
        # Nombre y versión reales SI el modelo ya está cargado (nlp.meta); si
        # no, el nombre del paquete configurado sin versión. Deliberadamente
        # NO fuerza la carga perezosa de spaCy solo para leer esta propiedad
        # (analyze() la lee para cada guardado): eso rompería cualquier
        # análisis ya hecho por otro medio (Gemini, un Analyzer de prueba) que
        # solo necesita registrar linaje, no re-cargar spaCy de paso.
        if self._nlp is not None:
            meta = self._nlp.meta
            return f"{meta.get('lang', '?')}_{meta.get('name', self._spacy_model)}-{meta.get('version', '?')}"
        return self._spacy_model

    @property
    def sent(self):
        if self._sent is None:
            from pysentimiento import create_analyzer

            self._sent = create_analyzer(task="sentiment", lang="es")
        return self._sent

    # ---- API pública ------------------------------------------------------------
    def analyze(self, title: str, body: str) -> AnalysisResult:
        text = f"{title}.\n\n{body}".strip()
        return self._analyze_doc(self.nlp(text))

    def analyze_batch(self, items: list[tuple[str, str]]) -> list[AnalysisResult]:
        """Analiza varios artículos en una sola pasada de spaCy (`nlp.pipe`).

        Evita el overhead por-llamada de invocar `nlp()` una vez por artículo;
        vale la pena cuando se procesa un lote (p.ej. todo un rastreo de una
        fuente) en vez de un artículo suelto."""
        texts = [f"{title}.\n\n{body}".strip() for title, body in items]
        return [self._analyze_doc(doc) for doc in self.nlp.pipe(texts)]

    def analyze_topics(self, title: str, body: str) -> tuple[str | None, list[str]]:
        """Solo `(main_topic, topic_keywords)`, sin entidades ni sentimiento.

        Para quien combina este analizador con otro motor y descarta el resto
        (`HybridAnalyzer`, que toma las entidades y el encuadre de Groq):
        corre spaCy con el NER apagado —el componente más caro de los que aquí
        no se usan— y NO toca pysentimiento, que era ~60% del tiempo de
        `analyze()` y terminaba en la basura.
        """
        text = f"{title}.\n\n{body}".strip()
        doc = self.nlp(text, disable=["ner"])
        keywords = self._keywords(doc)
        return self._main_topic(doc, keywords), keywords

    def _analyze_doc(self, doc) -> AnalysisResult:
        sentences = _Sentences.from_doc(doc)

        # --- sentimiento de cada frase, UNA sola vez y en batch ---
        probas_by_index = self._sentiment_per_sentence(sentences.texts)

        # --- sentimiento global ---
        overall_label, overall_score = _aggregate(probas_by_index)

        # --- tema principal + palabras clave ---
        keywords = self._keywords(doc)
        main_topic = self._main_topic(doc, keywords)

        # --- entidades + opinión hacia cada una ---
        entities = self._entities(doc, probas_by_index, sentences)

        return AnalysisResult(
            main_topic=main_topic,
            topic_keywords=keywords,
            overall_sentiment=overall_label,
            sentiment_score=overall_score,
            entities=entities,
        )

    # ---- helpers ----------------------------------------------------------------
    _SENT_BATCH_SIZE = 32  # mismo batch_size con el que pysentimiento carga el modelo

    def _sentiment_per_sentence(self, sent_texts: list[str]) -> list[dict | None]:
        """Probabilidades por frase, calculando cada frase ÚNICA una sola vez."""
        unique_texts = list(dict.fromkeys(t for t in sent_texts if t))
        probas_map = self._predict_batch(unique_texts)
        return [probas_map.get(t) for t in sent_texts]

    def _predict_batch(self, texts: list[str]) -> dict[str, dict]:
        """Igual que `self.sent.predict(texts)`, pero sin pasar por
        `Trainer.predict()` de pysentimiento (que arma un `datasets.Dataset` +
        DataLoader por llamada: ~500x más lento en CPU/MPS para lotes chicos,
        medido). Tampoco es una frase a la vez: eso también deja rendimiento en
        la mesa (sin aprovechar el paralelismo del batch). Aquí se tokeniza y
        corre el modelo directamente, en lotes de `_SENT_BATCH_SIZE`.

        Replica el mismo preprocesamiento y truncado que usa la librería —
        `preprocess_tweet` por frase + `truncation=True,
        max_length=tokenizer.model_max_length` + softmax sobre los logits,
        igual que `AnalyzerForSequenceClassification` — así que el softmax
        crudo es idéntico bit a bit al de la librería; el único paso propio
        de Odin es el ajuste de `analysis/sentiment_lexicon.apply_boost`
        aplicado después, sobre vocabulario político dominicano.
        """
        if not texts:
            return {}

        import torch
        from pysentimiento.preprocessing import preprocess_tweet

        analyzer = self.sent
        device = next(analyzer.model.parameters()).device
        preprocessed = [preprocess_tweet(t, **analyzer.preprocessing_args) for t in texts]

        results: dict[str, dict] = {}
        for start in range(0, len(texts), self._SENT_BATCH_SIZE):
            batch_orig = texts[start : start + self._SENT_BATCH_SIZE]
            batch_pre = preprocessed[start : start + self._SENT_BATCH_SIZE]
            enc = analyzer.tokenizer(
                batch_pre,
                padding=True,
                truncation=True,
                max_length=analyzer.tokenizer.model_max_length,
                return_tensors="pt",
            ).to(device)
            with torch.no_grad():
                logits = analyzer.model(**enc).logits
            probs = torch.softmax(logits, dim=1)
            for orig, row in zip(batch_orig, probs, strict=True):
                probas = {analyzer.id2label[i]: row[i].item() for i in analyzer.id2label}
                results[orig] = _apply_sentiment_boost(orig, probas)
        return results

    def _keywords(self, doc, top_k: int = 8) -> list[str]:
        counts: Counter[str] = Counter()
        for tok in doc:
            if tok.pos_ in {"NOUN", "PROPN"} and not tok.is_stop and len(tok.lemma_) > 3:
                lemma = tok.lemma_.lower()
                if lemma not in _STOP_ENTITY_TOKENS:
                    counts[lemma] += 1
        return [w for w, _ in counts.most_common(top_k)]

    def _main_topic(self, doc, keywords: list[str]) -> str | None:
        """Tema principal: prefiere una frase nominal frecuente que incluya la
        palabra clave top (p.ej. 'agua potable'); si no, la palabra clave top."""
        if not keywords:
            return None
        top = keywords[0]
        chunk_counts: Counter[str] = Counter()
        for chunk in doc.noun_chunks:
            words = [t for t in chunk if not t.is_stop and t.is_alpha]
            if 2 <= len(words) <= 3:
                phrase = " ".join(t.lemma_.lower() for t in words)
                if top in phrase:
                    chunk_counts[phrase] += 1
        if chunk_counts:
            return chunk_counts.most_common(1)[0][0]
        return top

    def _entities(self, doc, probas_by_index, sentences: _Sentences) -> list[EntityResult]:
        # 1) recolectar menciones agrupadas por (clave normalizada, tipo)
        groups: dict[tuple[str, str], dict] = {}
        for ent in doc.ents:
            etype = _WANTED_ENT.get(ent.label_)
            if not etype:
                continue
            # Un salto de línea dentro del span es la señal más confiable de
            # que trafilatura pegó un título con el subtítulo siguiente sin
            # puntuación ("Leonel\nCuestionamientos a operativos" -> spaCy
            # llega a etiquetar "Cuestionamientos" como PROPN por el contexto,
            # así que el filtro por POS solo no basta).
            if "\n" in ent.text:
                continue
            name = " ".join(ent.text.split())
            nkey = _norm_key(name)
            if len(name) < 3 or nkey in _STOP_ENTITY_TOKENS:
                continue
            # "República"/"Estado" solas (no como parte de un nombre propio
            # compuesto tipo "República Dominicana") no son una organización
            # real, son una forma genérica de referirse al país. ("Gobierno"
            # ya no se filtra aquí — ver el comentario junto a
            # _GENERIC_STATE_ORGS más arriba.)
            if etype == "ORG" and nkey in _GENERIC_STATE_ORGS:
                continue
            # "Santiago", "Elías Piña", "María Trinidad Sánchez"... spaCy las
            # marca PERSON cuando el span completo es el nombre de una
            # provincia dominicana (ver _DOMINICAN_PROVINCES).
            if etype == "PERSON" and nkey in _DOMINICAN_PROVINCES:
                continue
            # Cifras, montos y porcentajes ("RD$654", "39%") no son nombres:
            # spaCy a veces los etiqueta como PERSON/ORG porque son tokens no
            # alfabéticos que _is_proper_span deja pasar sin evaluar.
            if any(ch.isdigit() for ch in name):
                continue
            if nkey in _KNOWN_ORGS:
                etype = "ORG"  # spaCy suele marcar estas marcas como PERSON
            elif not _is_proper_span(ent):
                continue
            elif etype == "PERSON" and (
                _is_named_after_place(ent) or _preceded_by_venue_noun(ent)
            ):
                continue
            key = (nkey, etype)
            g = groups.setdefault(
                key,
                {"display": Counter(), "count": 0, "mentions": defaultdict(list)},
            )
            g["display"][name] += 1
            g["count"] += 1
            if ent.sent is not None:
                idx = sentences.index_of(ent.sent)
                if idx is not None:
                    # La posición, no solo el índice de la frase: es lo que
                    # permite saber si esta mención va antes o después de un
                    # patrón relacional (ver _relational_boosts).
                    g["mentions"][idx].append(sentences.offset_of(idx, ent))

        # 2) fusionar alias: nombre corto contenido en uno más largo (mismo tipo)
        groups = self._merge_aliases(groups)

        # 3) repartir el léxico relacional entre las entidades de cada frase
        boosts = self._relational_boosts(sentences, groups)

        # 4) construir resultados agregando el sentimiento ya calculado
        results: list[EntityResult] = []
        for key, g in groups.items():
            _nkey, etype = key
            display = _best_display_name(g["display"])
            sent_indices = sorted(g["mentions"])
            probas = [
                _apply_label_boost(probas_by_index[i], boosts.get((key, i)))
                for i in sent_indices
                if probas_by_index[i] is not None
            ]
            # Sin ninguna frase puntuada (p.ej. la entidad solo aparece más
            # allá de _MAX_SENTENCES) no hay opinión que reportar: None, no
            # un "NEU 0.0" indistinguible de un neutro de verdad.
            label, score = _aggregate(probas) if probas else (None, None)
            context = sentences.texts[sent_indices[0]] if sent_indices else None
            results.append(
                EntityResult(
                    name=display,
                    type=etype,
                    mentions_count=g["count"],
                    sentiment_toward=label,
                    sentiment_score=score,
                    context=context,
                    extraction_confidence=_extraction_confidence(display, etype, g["count"]),
                )
            )
        results.sort(key=lambda e: e.mentions_count, reverse=True)
        return results

    @staticmethod
    def _relational_boosts(
        sentences: _Sentences, groups: dict[tuple[str, str], dict]
    ) -> dict[tuple[tuple[str, str], int], str | None]:
        """Decide, frase por frase, QUÉ entidad recibe cada patrón del léxico
        relacional. Devuelve `(clave de entidad, índice de frase) -> etiqueta`.

        Antes el ajuste se aplicaba a la frase entera, así que en "Ramón Pérez
        fue acusado de corrupción por la Procuraduría" tanto el acusado como
        quien acusa se iban a NEG — justo la confusión que el léxico relacional
        existe para evitar.

        Regla: cada patrón se lo lleva la mención más cercana que lo PRECEDE.
        Todos los patrones del léxico son participios con preposición ("acusado
        de", "señalado por", "reconocido por"), donde el que recibe la acción va
        antes y el agente —si aparece— va después. Una entidad sin ninguna
        mención delante del patrón no recibe nada, y si dos patrones opuestos
        apuntan a la misma entidad en la misma frase se anulan (mismo criterio
        que `lexicon_label` ante señales contradictorias: no forzar nada).
        """
        mentions_by_sentence: dict[int, list[tuple[int, tuple[str, str]]]] = defaultdict(list)
        for key, g in groups.items():
            for idx, offsets in g["mentions"].items():
                mentions_by_sentence[idx].extend((offset, key) for offset in offsets)

        boosts: dict[tuple[tuple[str, str], int], str | None] = {}
        for idx, mentions in mentions_by_sentence.items():
            hits = _entity_relation_hits(sentences.texts[idx])
            if not hits:
                continue
            mentions.sort()
            for position, label in hits:
                preceding = [key for offset, key in mentions if offset < position]
                if not preceding:
                    continue
                target = (preceding[-1], idx)
                boosts[target] = label if boosts.get(target, label) == label else None
        return boosts

    @staticmethod
    def _initials(nkey: str) -> str:
        """Iniciales de las palabras significativas de un nombre normalizado."""
        words = [w for w in nkey.split() if w not in _NAME_PARTICLES]
        return "".join(w[0] for w in words if w)

    @classmethod
    def _merge_aliases(cls, groups: dict[tuple[str, str], dict]) -> dict[tuple[str, str], dict]:
        """Fusiona 'Policía' dentro de 'Policía Nacional' (subcadena por palabras)
        y 'FDD' dentro de 'Fundación Dominicana de Desarrollo' (siglas)."""
        keys = sorted(groups.keys(), key=lambda k: len(k[0]), reverse=True)  # largos 1º
        merged: dict[tuple[str, str], dict] = {}
        for key in keys:
            nkey, etype = key
            is_acronym_candidate = (
                " " not in nkey and 2 <= len(nkey) <= 6 and nkey.isalpha()
            )
            target = None
            for mkey in merged:
                if mkey[1] != etype:
                    continue
                # coincidencia por límites de palabra
                if f" {nkey} " in f" {mkey[0]} ":
                    target = mkey
                    break
                # coincidencia por siglas ("fdd" -> "fundación dominicana de desarrollo")
                if is_acronym_candidate and nkey == cls._initials(mkey[0]):
                    target = mkey
                    break
            if target is None:
                merged[key] = groups[key]
            else:
                dst = merged[target]
                src = groups[key]
                dst["display"].update(src["display"])
                dst["count"] += src["count"]
                for idx, offsets in src["mentions"].items():
                    dst["mentions"][idx].extend(offsets)
        return merged
