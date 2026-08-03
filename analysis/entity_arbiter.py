"""Árbitro puntual con Gemini: ¿la oración habla DE la persona, o el nombre
solo bautiza un lugar/evento (un salón, una calle, una asamblea...) en su
honor? La heurística local de `analysis/local_analyzer.py` resuelve la
mayoría de estos casos gratis; este módulo solo se consulta para lo que
queda ambiguo, y SOLO desde el flujo manual (`api.py`) — nunca desde
`main.py`/`pipeline.py`. Ver CLAUDE.md: no se llama a la API real de Gemini
en pruebas automatizadas, solo en uso real disparado por el usuario.

Costo: TODOS los casos ambiguos de un artículo van en UNA sola llamada
(`are_person_mentions`), no una llamada por entidad — el system prompt se
paga una vez por artículo en lugar de N veces.

Requisitos: pip install google-genai; GEMINI_API_KEY (o GOOGLE_API_KEY).
"""
from __future__ import annotations

import logging

from pydantic import BaseModel, Field

log = logging.getLogger("odin.entity_arbiter")

_MODEL = "gemini-3.5-flash"


class _Verdicts(BaseModel):
    is_person_mention: list[bool] = Field(
        description=(
            "Un veredicto por CASO, en el mismo orden: true si la oración "
            "habla DE la persona (alguien que hizo, dijo o vivió algo en la "
            "noticia); false si el nombre solo aparece porque es el nombre "
            "de un lugar, edificio, calle, sala o evento nombrado en su honor"
        )
    )


_SYSTEM = (
    "Eres un revisor de noticias dominicanas. Te doy una lista de CASOS; en "
    "cada uno, el nombre de una persona que un sistema automático detectó en "
    "una oración, y la oración completa. Tu única tarea, para CADA caso: "
    "decidir si esa oración habla DE esa persona (alguien que hizo, dijo o "
    "vivió algo), o si el nombre solo aparece porque es el nombre de un "
    "lugar, calle, salón, edificio, asamblea o evento nombrado en su honor. "
    "Una persona real puede dar nombre a un lugar sin estar presente ni ser "
    "el sujeto de la noticia.\n\n"
    "Ejemplos:\n"
    '- NOMBRE: "Juan Pérez" / ORACIÓN: "El senador Juan Pérez presentó el '
    'proyecto de ley." -> true (Juan Pérez es quien actúa).\n'
    '- NOMBRE: "Juan Pérez" / ORACIÓN: "El acto se realizó en el Salón Juan '
    'Pérez del ayuntamiento." -> false (es el nombre del salón, no aparece '
    "actuando).\n"
    '- NOMBRE: "Abraham Lincoln" / ORACIÓN: "La avenida Abraham Lincoln fue '
    'remodelada por el ayuntamiento." -> false (nombre de una avenida).\n'
    '- NOMBRE: "Juan Pablo Duarte" / ORACIÓN: "Danilo Medina participó en el '
    'homenaje a Juan Pablo Duarte por su aniversario." -> false para "Juan '
    'Pablo Duarte" (se le rinde homenaje, no actúa; nótese que "Danilo '
    'Medina" en la misma oración sí sería true, porque él sí participa).\n\n'
    "Ante una duda razonable, responde true — preferimos no perder una "
    "mención real a descartar de más. Devuelve exactamente un veredicto por "
    "caso, en el mismo orden."
)


def are_person_mentions(items: list[tuple[str, str]]) -> list[bool]:
    """Para cada (nombre, oración), True si la oración habla de la persona
    (no de un lugar/evento que lleva su nombre). UNA sola llamada a Gemini
    para toda la lista. Ante cualquier error de red, cuota o parseo devuelve
    todo True (fail-open: nunca perdemos una mención real por un problema
    ajeno)."""
    if not items:
        return []
    try:
        from google import genai

        contents = "\n\n".join(
            f'CASO {i + 1}\nNOMBRE: "{name}"\nORACIÓN: "{sentence}"'
            for i, (name, sentence) in enumerate(items)
        )
        client = genai.Client()
        response = client.models.generate_content(
            model=_MODEL,
            contents=contents,
            config={
                "system_instruction": _SYSTEM,
                "response_mime_type": "application/json",
                "response_schema": _Verdicts,
                "temperature": 0.0,
                "thinking_config": {"thinking_budget": 0},
                # el JSON es una lista de booleanos: unas decenas de tokens
                "max_output_tokens": 64 + 8 * len(items),
            },
        )
        verdicts = list(response.parsed.is_person_mention)
        if len(verdicts) < len(items):
            # respuesta incompleta: fail-open para los casos sin veredicto
            verdicts += [True] * (len(items) - len(verdicts))
        return verdicts[: len(items)]
    except Exception:
        log.warning(
            "árbitro de Gemini falló para %d casos; se conservan las menciones",
            len(items),
            exc_info=True,
        )
        return [True] * len(items)


def is_person_mention(name: str, sentence: str) -> bool:
    """Caso individual; conveniencia sobre `are_person_mentions`."""
    return are_person_mentions([(name, sentence)])[0]
