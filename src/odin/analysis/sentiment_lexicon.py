"""Vocabulario de refuerzo para el sentimiento (POS/NEG/NEU) en cobertura
política dominicana, compartido por los tres analizadores (`LocalAnalyzer`,
`GeminiAnalyzer`, `GroqAnalyzer`/`HybridAnalyzer`).

Motivo: `pysentimiento` (usado por `LocalAnalyzer`) está entrenado sobre
tweets en español general y no siempre pesa correctamente vocabulario
institucional/legal específico de la nota política dominicana ("prisión
preventiva", "desvío de fondos"); los LLM (Gemini/Groq) sí entienden ese
vocabulario, pero se benefician de un glosario explícito para ser
consistentes entre artículos, sobre todo en frases cortas o ambiguas.

Cada término debe tener carga de sentimiento fuerte e inequívoca por sí solo
(mismo criterio que `scripts/scrape_politics.py:_POLITICS_TERMS` para el
vocabulario de tema): si una palabra depende del contexto para saber si es
buena o mala noticia ("investigación", "cambio", "salida", "detenido",
"cárcel"), no entra aquí — metería ruido en vez de reforzar la señal. Por
eso la lista es deliberadamente corta: cada término nuevo debe pasar ese
filtro, no solo "sonar" a política o a crimen.

Dos problemas distintos, dos mecanismos:
  1. Sentimiento GLOBAL de la nota (`apply_boost` + `lexicon_label`):
     vocabulario con carga inequívoca por sí solo ("corrupción", "consenso").
  2. Sentimiento hacia una ENTIDAD puntual (`apply_entity_relation_boost` +
     `entity_relation_label`): frases relacionales cuya dirección hacia el
     sujeto no depende del complemento ("acusado de", "reconocido por") — un
     evento con carga política ("corrupción") no siempre implica que TODAS
     las entidades de la nota queden mal paradas; puede haber una entidad
     acusada y otra que investiga o corrige. Este segundo léxico solo debe
     aplicarse a las frases donde YA se sabe que se menciona a esa entidad
     puntual (ver `_entities()` en `analysis/local_analyzer.py`), nunca de
     forma global al documento.

Tres consumidores del mismo vocabulario:
  - `apply_boost`: para `LocalAnalyzer`, empuja la probabilidad de la frase
    hacia NEG/POS antes de agregar el sentimiento GLOBAL de la nota.
  - `apply_entity_relation_boost`: para `LocalAnalyzer`, igual pero solo
    sobre las frases ya asociadas a una entidad, usando el léxico
    relacional en vez del léxico general.
  - `PROMPT_GLOSSARY`: para Gemini/Groq, se inyecta como texto en `_SYSTEM`
    (ver `analysis/gemini_analyzer.py`) — el LLM ya entiende estos términos
    y ya distingue sentimiento global de sentimiento por entidad de forma
    nativa (lee el artículo completo), el glosario solo estandariza el
    criterio en casos límite.
"""
from __future__ import annotations

import re

from odin.analysis.text_norm import strip_accents

# ---- léxico general: carga inequívoca por sí sola, sin necesitar sujeto ----
_NEG_TERMS = [
    "corrupcion", "corrupto", "corrupta", "soborno", "sobornos", "coima",
    "coimas", "desfalco", "malversacion", "fraude", "fraude electoral",
    "compra de votos", "narcotrafico", "crimen organizado", "extorsion",
    "trata de personas", "trafico de influencias", "peculado",
    "lavado de activos", "prision preventiva", "arresto domiciliario",
    "condena", "condenado", "condenada", "impunidad", "escandalo",
    "encubrimiento", "nepotismo", "clientelismo", "desvio de fondos",
    "enriquecimiento ilicito", "evasion fiscal", "abuso de poder",
    "represion", "censura", "destitucion", "destituido", "destituida",
    "renuncia forzada", "crisis politica", "vacancia", "juicio politico",
    "malos manejos", "opacidad", "conflicto de intereses",
    "irregularidades administrativas",
]

_POS_TERMS = [
    "acuerdo bipartidista", "acuerdo historico", "consenso",
    "pacto nacional", "dialogo nacional", "transparencia",
    "rendicion de cuentas", "reforma exitosa", "gobernabilidad",
    "estabilidad politica", "institucionalidad",
    "cooperacion internacional", "crecimiento economico", "reconciliacion",
    "gobernanza", "buenas practicas", "gestion eficiente",
    "victoria electoral", "triunfo electoral", "aprobado por unanimidad",
    "aprobada por unanimidad",
]

# ---- léxico relacional: dirección hacia UNA entidad, no carga del evento --
# Frases donde la estructura gramatical ya define si el sujeto queda mal o
# bien parado, sin importar el complemento ("acusado de [cualquier cosa]"
# siempre es negativo para quien lo recibe). Deliberadamente sin variantes
# ambiguas ("investigado" solo, "señalado" solo) que dependen del resto de
# la oración para saber si hay sujeto/objeto de verdad.
_ENTITY_NEG_PATTERNS = [
    "acusado de", "acusada de", "acusados de", "acusadas de",
    "senalado por", "senalada por", "senalados por", "senaladas por",
    "vinculado a", "vinculada a", "vinculados a", "vinculadas a",
    "implicado en", "implicada en", "implicados en", "implicadas en",
    "condenado por", "condenada por", "condenados por", "condenadas por",
    "investigado por", "investigada por", "investigados por",
    "investigadas por",
    "sancionado por", "sancionada por", "sancionados por", "sancionadas por",
]

_ENTITY_POS_PATTERNS = [
    "reconocido por", "reconocida por", "reconocidos por", "reconocidas por",
    "respaldado por", "respaldada por", "respaldados por", "respaldadas por",
    "premiado por", "premiada por", "premiados por", "premiadas por",
    "felicitado por", "felicitada por", "felicitados por", "felicitadas por",
    "elogiado por", "elogiada por", "elogiados por", "elogiadas por",
]

# Empuje moderado sobre la probabilidad: alcanza para inclinar una frase que
# el modelo ya veía cerca del límite entre etiquetas, pero no para voltear
# una que el modelo clasificó con alta confianza en la dirección contraria
# (0.12 sobre un rango [0,1], con renormalización posterior). Deliberadamente
# NO escala con la cantidad de términos que matchean: a nivel de una sola
# frase rara vez hay más de un match, y sumar una capa de "fuerza" ahí sería
# calibración sin datos que la respalden (mismo criterio de
# scrape_politics.py: "un match simple alcanza sin sumar una capa extra").
BOOST = 0.12


def _compile(terms: list[str]) -> re.Pattern[str]:
    escaped = sorted({re.escape(t) for t in terms}, key=len, reverse=True)
    return re.compile(r"\b(?:" + "|".join(escaped) + r")\b")


_NEG_RE = _compile(_NEG_TERMS)
_POS_RE = _compile(_POS_TERMS)
_ENTITY_NEG_RE = _compile(_ENTITY_NEG_PATTERNS)
_ENTITY_POS_RE = _compile(_ENTITY_POS_PATTERNS)


def _label_from(text: str, neg_re: re.Pattern[str], pos_re: re.Pattern[str]) -> str | None:
    normalized = strip_accents(text).lower()
    has_neg = neg_re.search(normalized) is not None
    has_pos = pos_re.search(normalized) is not None
    if has_neg and not has_pos:
        return "NEG"
    if has_pos and not has_neg:
        return "POS"
    return None  # sin match, o señal contradictoria: mejor no forzar nada


def _boosted(probas: dict[str, float], label: str | None) -> dict[str, float]:
    if label is None or label not in probas:
        return probas
    boosted = dict(probas)
    boosted[label] = min(boosted[label] + BOOST, 1.0)
    total = sum(boosted.values())
    return {k: v / total for k, v in boosted.items()}


def lexicon_label(text: str) -> str | None:
    """"NEG"/"POS" si el texto trae vocabulario GLOBAL de un solo lado del
    glosario; None si no hay match o si matchea de ambos lados (señal
    contradictoria: mejor dejar que decida el modelo, no forzar un empate)."""
    return _label_from(text, _NEG_RE, _POS_RE)


def apply_boost(text: str, probas: dict[str, float]) -> dict[str, float]:
    """Ajusta las probabilidades por frase de `LocalAnalyzer` sumando `BOOST`
    a la etiqueta que sugiere el léxico GLOBAL y renormalizando. No-op si el
    glosario no aplica a este texto."""
    return _boosted(probas, lexicon_label(text))


def entity_relation_label(text: str) -> str | None:
    """Igual que `lexicon_label`, pero con el léxico RELACIONAL ("acusado
    de", "reconocido por"). Solo tiene sentido aplicarlo a una frase que ya
    se sabe que menciona a la entidad en cuestión — ver el docstring del
    módulo."""
    return _label_from(text, _ENTITY_NEG_RE, _ENTITY_POS_RE)


def apply_entity_relation_boost(text: str, probas: dict[str, float]) -> dict[str, float]:
    """Como `apply_boost`, pero con el léxico relacional dirigido a entidad.
    Debe llamarse solo sobre frases ya asociadas a esa entidad puntual (ver
    `LocalAnalyzer._entities`), nunca sobre el documento completo: la
    dirección de "acusado de" depende de a quién menciona la frase, no es
    una carga global de la nota."""
    return _boosted(probas, entity_relation_label(text))


def lexicon_matches(text: str) -> dict[str, list[str]]:
    """Términos del léxico (general + relacional) que matchearon en `text`,
    para depurar desacuerdos entre analizadores — qué disparó el ajuste, no
    solo la etiqueta final."""
    normalized = strip_accents(text).lower()
    return {
        "NEG": sorted(set(_NEG_RE.findall(normalized))),
        "POS": sorted(set(_POS_RE.findall(normalized))),
        "ENTITY_NEG": sorted(set(_ENTITY_NEG_RE.findall(normalized))),
        "ENTITY_POS": sorted(set(_ENTITY_POS_RE.findall(normalized))),
    }


PROMPT_GLOSSARY = (
    "Glosario de referencia (vocabulario con carga de sentimiento fuerte e "
    "inequívoca en cobertura política/institucional dominicana — apóyate en "
    "él para ser consistente en casos límite, pero el contexto de la frase "
    "siempre pesa más que la sola presencia de una palabra):\n"
    "- NEGATIVOS: " + ", ".join(_NEG_TERMS) + "\n"
    "- POSITIVOS: " + ", ".join(_POS_TERMS) + "\n\n"
    "IMPORTANTE: que la nota mencione un hecho negativo (corrupción, "
    "escándalo, investigación) no implica que TODAS las entidades "
    "mencionadas queden mal paradas — puede haber una entidad acusada y "
    "otra que investiga, corrige o denuncia el hecho. Evalúa el "
    "sentimiento de CADA entidad según cómo la trata el texto a ELLA "
    "específicamente, no según la carga general de la noticia."
)
