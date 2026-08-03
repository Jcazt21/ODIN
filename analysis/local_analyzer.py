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
  - overall_sentiment: sentimiento agregado sobre TODAS las frases del artículo.
  - entities + sentiment_toward: por cada figura/empresa se agregan las frases
    donde se le menciona. Los nombres se normalizan y se fusionan alias
    ("Policía" -> "Policía Nacional").

NOTA: `sentiment_toward` es una aproximación por frase (aspect-based sentiment
sencillo). Para máxima precisión, sustituir por el analizador con LLM (misma
interfaz Analyzer); ver analysis/gemini_analyzer.py.
"""
from __future__ import annotations

import unicodedata
from collections import Counter, defaultdict

from analysis.base import AnalysisResult, EntityResult

_MAX_SENT_CHARS = 500        # límite por frase para el modelo de sentimiento
_MAX_SENTENCES = 400         # tope de seguridad para artículos patológicos
_STOP_ENTITY_TOKENS = {"foto", "video", "listín", "listin", "diario", "libre"}
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


def _preceded_by_venue_noun(ent, window: int = 6) -> bool:
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
    """
    for tok in ent:
        if not tok.is_alpha:
            continue
        if tok.lemma_.lower() in _NAME_PARTICLES or tok.text.lower() in _NAME_PARTICLES:
            continue
        if tok.pos_ != "PROPN":
            return False
    return True


def _strip_accents(text: str) -> str:
    return "".join(
        c for c in unicodedata.normalize("NFD", text) if unicodedata.category(c) != "Mn"
    )


def _norm_key(name: str) -> str:
    """Clave de comparación: sin acentos, minúsculas, espacios colapsados."""
    return " ".join(_strip_accents(name).lower().split())


def _aggregate(probas_list: list[dict | None]) -> tuple[str, float]:
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
    label = max(totals, key=totals.get)
    return label, round(float(totals[label] / n), 4)


class LocalAnalyzer:
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
    def sent(self):
        if self._sent is None:
            from pysentimiento import create_analyzer

            self._sent = create_analyzer(task="sentiment", lang="es")
        return self._sent

    # ---- API pública ------------------------------------------------------------
    def analyze(self, title: str, body: str) -> AnalysisResult:
        text = f"{title}.\n\n{body}".strip()
        doc = self.nlp(text)

        sents = list(doc.sents)[:_MAX_SENTENCES]
        sent_texts = [s.text.strip()[:_MAX_SENT_CHARS] for s in sents]

        # --- sentimiento de cada frase, UNA sola vez y en batch ---
        probas_by_index = self._sentiment_per_sentence(sent_texts)
        start_to_index = {s.start_char: i for i, s in enumerate(sents)}

        # --- sentimiento global ---
        overall_label, overall_score = _aggregate(probas_by_index)

        # --- tema principal + palabras clave ---
        keywords = self._keywords(doc)
        main_topic = self._main_topic(doc, keywords)

        # --- entidades + opinión hacia cada una ---
        entities = self._entities(doc, probas_by_index, start_to_index)

        return AnalysisResult(
            main_topic=main_topic,
            topic_keywords=keywords,
            overall_sentiment=overall_label,
            sentiment_score=overall_score,
            entities=entities,
        )

    # ---- helpers ----------------------------------------------------------------
    def _sentiment_per_sentence(self, sent_texts: list[str]) -> list[dict | None]:
        """Probabilidades por frase, calculando cada frase ÚNICA una sola vez.

        Nota: se llama a predict() por frase individual a propósito. Pasar la
        lista completa a pysentimiento activa una ruta con DataLoader/pin_memory
        que es órdenes de magnitud más lenta en CPU/MPS. La ganancia real está en
        deduplicar y reutilizar (el mismo sentimiento sirve para el global y para
        cada entidad), no en el batch.
        """
        probas_map: dict[str, dict] = {}
        for t in sent_texts:
            if t and t not in probas_map:
                probas_map[t] = self.sent.predict(t).probas
        return [probas_map.get(t) for t in sent_texts]

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

    def _entities(self, doc, probas_by_index, start_to_index) -> list[EntityResult]:
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
                key, {"display": Counter(), "count": 0, "sent_idx": set()}
            )
            g["display"][name] += 1
            g["count"] += 1
            if ent.sent is not None:
                idx = start_to_index.get(ent.sent.start_char)
                if idx is not None:
                    g["sent_idx"].add(idx)

        # 2) fusionar alias: nombre corto contenido en uno más largo (mismo tipo)
        groups = self._merge_aliases(groups)

        # 3) construir resultados agregando el sentimiento ya calculado
        results: list[EntityResult] = []
        for (nkey, etype), g in groups.items():
            display = g["display"].most_common(1)[0][0]  # variante más usada
            probas = [probas_by_index[i] for i in sorted(g["sent_idx"])]
            label, score = _aggregate(probas)
            context = None
            if g["sent_idx"]:
                first = min(g["sent_idx"])
                context = list(doc.sents)[first].text.strip()[:_MAX_SENT_CHARS]
            results.append(
                EntityResult(
                    name=display,
                    type=etype,
                    mentions_count=g["count"],
                    sentiment_toward=label,
                    sentiment_score=score,
                    context=context,
                )
            )
        results.sort(key=lambda e: e.mentions_count, reverse=True)
        return results

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
                dst["sent_idx"] |= src["sent_idx"]
        return merged
