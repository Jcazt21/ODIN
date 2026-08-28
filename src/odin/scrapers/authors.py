"""Limpieza del campo de autores.

Módulo aparte para que `base.py` pueda usarlo sin importar el paquete que lo
importa a él: la versión con registro vive en `scrapers/__init__.py` y delega
acá pasando el nombre del medio ya resuelto.
"""
from __future__ import annotations

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
