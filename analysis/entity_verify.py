"""Contraste de las entidades que devuelve un LLM contra el texto real.

Un LLM extrae entidades leyendo el artículo, pero nada garantiza que lo que
devuelve esté en él: puede completar un nombre con lo que sabe del mundo, o
directamente inventar una organización plausible. El prompt lo pide ("solo
entidades que el texto realmente menciona"), y un pedido no es una garantía.
Esto lo verifica después, gratis y sin llamadas extra.

Dos cosas distintas, con dos criterios distintos:

  1. **Soporte léxico** (`verify_entities`): ¿queda algún rastro del nombre en
     el texto? Se distinguen tres casos, y solo el más extremo descarta:

       - el nombre completo aparece tal cual -> se acepta sin tocar nada;
       - aparece solo una parte ("Abinader" cuando el LLM devolvió "Luis
         Abinader") -> se acepta, porque expandir al nombre canónico es
         justamente lo que el prompt pide, pero baja `extraction_confidence`
         si el modelo venía muy confiado;
       - no aparece NINGUNA palabra significativa del nombre -> se descarta.
         Ahí ya no hay nada que revisar a mano: la mención no está en el texto.

  2. **Conteo de menciones** (`recount_mentions`): `mentions_count` sale del
     LLM como una estimación ("número aproximado", dice el schema) y es el
     campo que ORDENA la lista de entidades en toda la app y decide qué
     variante gana al fusionar (`analysis/canonicalize.py`). Contarlo con una
     expresión regular es exacto y gratis. Se cuenta sobre el artículo
     COMPLETO, no sobre el recorte que se le mandó al modelo: las menciones
     que quedaron fuera del tope de caracteres también son menciones.

Solo se cuenta cuando se puede hacer sin inventar:

  - PERSON con nombre y apellido -> se cuentan las apariciones de la última
    palabra significativa (el apellido), que es como la prensa abrevia y por
    tanto cubre "Luis Abinader" y "Abinader" con un solo patrón.
  - el resto (ORG, PERSON de una sola palabra) -> solo el nombre completo. No
    se cuentan palabras sueltas de una organización: "educación" aparece en
    cualquier nota sobre el "Ministerio de Educación" sin ser una mención.

Si el conteo da cero, se respeta el del modelo: significa que el nombre no
está literal en el texto (caso 2 de arriba), no que no se le mencione.
"""
from __future__ import annotations

import re

from analysis.text_norm import strip_accents

# Partículas que no cuentan como palabra significativa de un nombre. Misma
# lista que `analysis/canonicalize.py`; se repite aquí en vez de importarla
# para no crear una dependencia entre dos módulos que no se necesitan para
# nada más (y que se aplican en órdenes distintos del pipeline).
_NAME_PARTICLES = {"de", "del", "la", "las", "los", "y", "e"}

# Por debajo de este valor el frontend ya marca la entidad como "revisar"
# (ver frontend/src/lib/format.ts): es el techo que se le pone a una entidad
# cuyo nombre completo no está literal en el texto.
_PARTIAL_MATCH_CONFIDENCE = 0.6


def _fold(text: str) -> str:
    """Minúsculas, sin acentos y con los espacios colapsados, para que un
    nombre partido por un salto de línea siga encontrándose."""
    return " ".join(strip_accents(text).lower().split())


def _significant_words(folded_name: str) -> list[str]:
    return [w for w in folded_name.split() if w not in _NAME_PARTICLES]


def _count(folded_text: str, phrase: str) -> int:
    if not phrase:
        return 0
    return len(re.findall(rf"(?<!\w){re.escape(phrase)}(?!\w)", folded_text))


def verify_entities(entities: list, text: str) -> list:
    """Descarta las entidades sin ningún rastro en el texto y baja la
    confianza de las que solo aparecen parcialmente. Devuelve la lista
    filtrada; no modifica el orden."""
    folded_text = _fold(text)
    kept = []
    for ent in entities:
        folded_name = _fold(ent.name)
        words = _significant_words(folded_name)
        if not words:
            continue
        if _count(folded_text, folded_name):
            kept.append(ent)
            continue
        if any(_count(folded_text, word) for word in words):
            ent.extraction_confidence = min(
                getattr(ent, "extraction_confidence", 1.0), _PARTIAL_MATCH_CONFIDENCE
            )
            kept.append(ent)
    return kept


def recount_mentions(entities: list, text: str) -> None:
    """Reemplaza in-place el `mentions_count` estimado por el LLM con el
    conteo real, cuando se puede contar de forma inequívoca (ver el docstring
    del módulo)."""
    folded_text = _fold(text)
    for ent in entities:
        folded_name = _fold(ent.name)
        words = _significant_words(folded_name)
        if not words:
            continue
        if getattr(ent, "type", None) == "PERSON" and len(words) >= 2:
            counted = _count(folded_text, words[-1])  # el apellido
        else:
            # El nombre entero, con partículas y todo: "ministerio educacion"
            # no encuentra "Ministerio de Educación".
            counted = _count(folded_text, folded_name)
        if counted:
            ent.mentions_count = counted
