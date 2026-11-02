"""Limpieza del campo de autores.

Módulo aparte para que `base.py` pueda usarlo sin importar el paquete que lo
importa a él: la versión con registro vive en `scrapers/__init__.py` y delega
acá pasando el nombre del medio ya resuelto.
"""
from __future__ import annotations

import html
import re

from odin.analysis.text_norm import norm_key


def strip_outlet(authors: str | None, outlet_names: set[str]) -> str | None:
    """Quita del campo de autores las partes que sean el nombre del medio.

    Varios sitios se listan a sí mismos ahí ("Listin Diario; Ashley Martínez"),
    y guardarlo entero convierte al medio en periodista. R15 pide al periodista
    como dimensión propia: con el medio adentro, contar notas por autor mezcla
    una redacción entera con personas.

    La comparación usa `norm_key`, así que "Listin" y "Listín" coinciden, y
    exige que la parte COMPLETA sea el medio: "Juan Diario" no se toca por
    contener una palabra del nombre.

    Solo se parte por ";", que es lo que usan los medios que rastreamos.
    Partir también por coma rompería nombres escritos "Apellido, Nombre".
    """
    if not authors or not authors.strip():
        return None

    # Algunos sitios dejan entidades HTML en el meta de autor ("JES&Uacute;S").
    # Hay que decodificarlas ANTES de partir por ";": el punto y coma de la
    # entidad se leería como separador y el nombre quedaría hecho pedazos.
    authors = html.unescape(authors)

    # Se compara también sin espacios porque algunos sitios ponen su dominio
    # en el campo autor con formato de nombre: "Eldia Com Do" es el mismo medio
    # que "eldia.com.do" y que "El Día", y las tres formas conviven en los
    # datos ya guardados.
    keys = {norm_key(n) for n in outlet_names if n}
    keys |= {k.replace(" ", "") for k in keys}

    def _is_outlet(part: str) -> bool:
        key = norm_key(part)
        return key in keys or key.replace(" ", "") in keys

    kept = [part.strip() for part in authors.split(";") if part.strip() and not _is_outlet(part)]
    return "; ".join(kept) or None


_JSONLD = re.compile(r"(<script[^>]+application/ld\+json[^>]*>)(.*?)(</script>)", re.S | re.I)
_ENTIDAD = re.compile(r"&[A-Za-z][A-Za-z0-9]*;|&#\d+;|&#x[0-9a-fA-F]+;")


def _decode_accents(match: re.Match[str]) -> str:
    decoded = html.unescape(match.group(0))
    # Solo las que producen letras acentuadas: decodificar &quot; o &amp; rompería el JSON.
    return decoded if ord(decoded[0]) > 127 and len(decoded) == 1 else match.group(0)


def decode_jsonld_entities(page: str) -> str:
    """Decodifica las tildes en entidad dentro del JSON-LD de la página.

    Un navegador decodifica las entidades del HTML, pero el contenido de un
    <script> es texto crudo: Diario Libre escribe ahí "Jes&uacute;s V&aacute;squez"
    y trafilatura, que toma el autor de ese bloque, lo parte por el ";" de cada
    entidad antes de que `strip_outlet` lo vea ("Jes; Uacute; S V; ...").
    """
    return _JSONLD.sub(lambda m: m.group(1) + _ENTIDAD.sub(_decode_accents, m.group(2)) + m.group(3), page)
