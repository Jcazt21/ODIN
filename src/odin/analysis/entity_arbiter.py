"""Árbitro puntual con Gemini: ¿la oración habla DE la persona, o el nombre
solo bautiza un lugar/evento (un salón, una calle, una asamblea...) en su
honor? La heurística local de `analysis/local_analyzer.py` resuelve la
mayoría de estos casos gratis; este módulo solo se consulta para lo que
queda ambiguo, y SOLO desde el flujo manual (`api.py`) — nunca desde
`main.py`/`pipeline.py`. Ver CLAUDE.md: no se llama a la API real de Gemini
en pruebas automatizadas, solo en uso real disparado por el usuario.

Costo: TODOS los casos ambiguos de un artículo van en UNA sola llamada
(`are_person_mentions`), no una llamada por entidad — el system prompt es la
mayor parte de los tokens de entrada y así se paga una vez por artículo en
lugar de N veces.

Emparejamiento: cada veredicto viene con el `case_id` de su caso. Se hizo así
en lugar de una lista posicional de booleanos porque, con posiciones, que el
modelo omitiera un caso intermedio corría todos los veredictos siguientes y se
los aplicaba a la entidad equivocada, sin forma de detectarlo. Ver `_align`.

Activación: requiere `ODIN_GEMINI_ARBITER=1` (apagado por defecto). Tener la
llave configurada no basta — una credencial no debe activar gasto.

Requisitos: pip install google-genai; GEMINI_API_KEY (o GOOGLE_API_KEY).
"""
from __future__ import annotations

import logging

from pydantic import BaseModel, Field

log = logging.getLogger("odin.entity_arbiter")

_MODEL = "gemini-3.5-flash"


class _Verdict(BaseModel):
    """Un veredicto atado a su caso por número, no por posición.

    La versión anterior devolvía `list[bool]` y se emparejaba por índice: si el
    modelo omitía un caso intermedio, todos los veredictos siguientes se
    aplicaban a la entidad equivocada y no había forma de notarlo. Con `case_id`
    una respuesta incompleta o desordenada se detecta y solo afecta a los casos
    realmente ausentes.
    """

    case_id: int = Field(
        description="Número del CASO al que corresponde este veredicto (el que aparece como 'CASO N')"
    )
    is_person_mention: bool = Field(
        description=(
            "true si la oración habla DE la persona (alguien que hizo, dijo o "
            "vivió algo en la noticia); false si el nombre solo aparece porque "
            "es el nombre de un lugar, edificio, calle, sala o evento nombrado "
            "en su honor"
        )
    )


class _Verdicts(BaseModel):
    verdicts: list[_Verdict] = Field(
        description="Un veredicto por cada CASO recibido, cada uno con su case_id"
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
    "caso, cada uno con el case_id del CASO correspondiente. No omitas "
    "ningún caso ni inventes case_id que no te haya dado."
)


def _align(verdicts: list[_Verdict], total: int) -> list[bool]:
    """Empareja los veredictos con los casos por `case_id`, no por posición.

    Los casos van numerados 1..total. Lo que no venga con un case_id válido se
    resuelve fail-open (True): preferimos conservar una mención real antes que
    descartarla por un fallo del modelo. A diferencia del emparejamiento
    posicional anterior, un caso omitido solo se pierde a sí mismo — no corre a
    los demás — y queda registrado en el log en vez de pasar en silencio.
    """
    by_id: dict[int, bool] = {}
    for v in verdicts:
        if 1 <= v.case_id <= total:
            by_id[v.case_id] = v.is_person_mention
        else:
            log.warning("árbitro devolvió un case_id fuera de rango: %s", v.case_id)

    faltantes = [i for i in range(1, total + 1) if i not in by_id]
    if faltantes:
        log.warning(
            "árbitro no devolvió veredicto para los casos %s de %d; se conservan "
            "esas menciones",
            faltantes,
            total,
        )

    return [by_id.get(i, True) for i in range(1, total + 1)]


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
                # Cada veredicto es ahora un objeto {case_id, is_person_mention}
                # en vez de un booleano suelto: ~20 tokens en lugar de ~3. El
                # margen es holgado a propósito — quedarse corto trunca el JSON
                # y tira toda la llamada al fail-open, que es justo el desperdicio
                # que se quiere evitar.
                "max_output_tokens": 128 + 32 * len(items),
            },
        )
        # El SDK tipa `parsed` como una unión amplia; el `response_schema` de
        # arriba garantiza que aquí viene un _Verdicts. Si no lo fuera, el
        # except de abajo lo convierte en fail-open.
        return _align(list(response.parsed.verdicts), len(items))  # type: ignore[union-attr]
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
