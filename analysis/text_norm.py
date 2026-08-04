"""Normalización de nombres compartida entre `local_analyzer.py` y
`canonicalize.py`: ambos deben derivar la MISMA clave de comparación para
que las entidades extraídas y su canonicalización posterior coincidan.

También provee `accent_insensitive_regex`, usada por la búsqueda de la API
(`api.py`) para que "matias" encuentre "Matías" sin necesitar la extensión
`unaccent` de Postgres ni traer filas a Python para filtrarlas: se expande
cada vocal del término buscado a una clase de caracteres y se compara en SQL
con el operador `~*` (regex case-insensitive nativo, sin extensiones).
"""
from __future__ import annotations

import re
import unicodedata


def strip_accents(text: str) -> str:
    return "".join(
        c for c in unicodedata.normalize("NFD", text) if unicodedata.category(c) != "Mn"
    )


# Cada vocal (con o sin tilde/diéresis, en ambos casos) mapea a la misma clase
# de caracteres: así el patrón generado encuentra la mención sin importar con
# qué variante fue escrita originalmente.
_ACCENT_CLASSES = {
    "a": "aàáâãäå",
    "e": "eèéêë",
    "i": "iìíîï",
    "o": "oòóôõö",
    "u": "uùúûü",
    "n": "nñ",
    "c": "cç",
}


def accent_insensitive_regex(term: str) -> str:
    """Construye un patrón para `~*` (regex case-insensitive de Postgres) que
    encuentra `term` sin importar los acentos de NINGUNO de los dos lados
    (columna o término buscado) — cubre tanto buscar "matias" y encontrar
    "Matías", como buscar "Matías" y encontrar una fila guardada sin tilde.

    No usa `unaccent` de Postgres (no requiere `CREATE EXTENSION`) ni trae
    filas a Python para filtrarlas: el patrón se arma aquí y SQL hace el
    filtrado, así que sigue pudiendo indexarse más adelante si el volumen de
    datos lo justifica.
    """
    normalized = strip_accents(term).lower()
    parts = []
    for ch in normalized:
        cls = _ACCENT_CLASSES.get(ch)
        if cls:
            parts.append(f"[{cls}]")
        else:
            parts.append(re.escape(ch))
    return "".join(parts)


def norm_key(name: str) -> str:
    """Clave de comparación: sin acentos, minúsculas, espacios colapsados.

    Guiones -> espacio ("Jean-Claude" == "Jean Claude") y puntos fuera
    ("P.R.M." == "PRM"), para que variantes tipográficas de la misma sigla o
    nombre compuesto no generen entidades duplicadas.
    """
    name = name.replace("-", " ").replace(".", "")
    return " ".join(strip_accents(name).lower().split())
