"""Clasificador de temas por reglas sobre el catálogo. Puro: no toca la BD
(recibe el catálogo ya cargado vía `db.topics.get_catalog()`), no llama a ningún
LLM. Le da al cliente control directo — lo que cuenta como cada tema son los
nombres y alias que él administra.

Diseño calcado de `analysis/politics_filter.py`: una sola regex de alternación
compilada sobre los términos del catálogo, coincidencia por palabra completa
sobre texto sin acentos y en minúsculas. "Señal fuerte primero": un término en
el título / `main_topic` / `topic_keywords` pesa más que en el cuerpo.
"""
from __future__ import annotations

import re
import threading
from dataclasses import dataclass

from odin.analysis.text_norm import strip_accents

TOPIC_MIN_SCORE = 0.5

_TITLE_SCORE = 0.9
_BODY_MULTI_SCORE = 0.6
_BODY_SINGLE_SCORE = 0.35


@dataclass(frozen=True)
class TopicMatch:
    topic_id: int
    score: float
    evidence: str


class _Matcher:
    def __init__(self, pattern: re.Pattern[str], term_to_topic: dict[str, int],
                 parent_of: dict[int, int | None]):
        self.pattern = pattern
        self.term_to_topic = term_to_topic
        self.parent_of = parent_of


_lock = threading.Lock()
_matcher: _Matcher | None = None


def invalidate_matcher() -> None:
    global _matcher
    with _lock:
        _matcher = None


def build_matcher(catalog) -> _Matcher:
    term_to_topic: dict[str, int] = {}
    parent_of: dict[int, int | None] = {}
    for t in catalog:
        parent_of[t.id] = t.parent_id
        for term in (t.norm_key, *t.aliases):
            term = strip_accents(term).lower().strip()
            if term:
                term_to_topic.setdefault(term, t.id)
    if not term_to_topic:
        return _Matcher(re.compile(r"(?!x)x"), {}, parent_of)  # nunca matchea
    alternation = "|".join(
        re.escape(term) for term in sorted(term_to_topic, key=len, reverse=True)
    )
    pattern = re.compile(rf"\b(?:{alternation})\b")
    return _Matcher(pattern, term_to_topic, parent_of)


def _get_matcher() -> _Matcher:
    global _matcher
    with _lock:
        if _matcher is None:
            from odin.db.topics import get_catalog
            _matcher = build_matcher(get_catalog())
        return _matcher


def _hits(text: str, m: _Matcher) -> dict[int, set[str]]:
    """topic_id -> conjunto de términos distintos encontrados en `text`."""
    found: dict[int, set[str]] = {}
    for term in m.pattern.findall(strip_accents(text or "").lower()):
        tid = m.term_to_topic.get(term)
        if tid is not None:
            found.setdefault(tid, set()).add(term)
    return found


def classify(title: str, body: str, keywords: str | None, main_topic: str | None,
             *, min_score: float = TOPIC_MIN_SCORE) -> list[TopicMatch]:
    m = _get_matcher()
    strong_text = " . ".join(x for x in (title, main_topic, keywords) if x)
    strong = _hits(strong_text, m)
    weak = _hits(body, m)

    scored: dict[int, tuple[float, str]] = {}
    for tid, terms in strong.items():
        scored[tid] = (_TITLE_SCORE, sorted(terms)[0])
    for tid, terms in weak.items():
        if tid in scored:
            continue
        score = _BODY_MULTI_SCORE if len(terms) >= 2 else _BODY_SINGLE_SCORE
        scored[tid] = (score, sorted(terms)[0])

    # Roll-up: si matchea un subtema, el padre hereda el mismo score.
    for tid, (score, ev) in list(scored.items()):
        parent = m.parent_of.get(tid)
        if parent is not None and parent not in scored:
            scored[parent] = (score, ev)

    out = [
        TopicMatch(topic_id=tid, score=score, evidence=ev)
        for tid, (score, ev) in scored.items()
        if score >= min_score
    ]
    out.sort(key=lambda x: x.score, reverse=True)
    return out
