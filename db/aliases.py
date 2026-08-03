"""Resolutor y cargador de la tabla `entity_aliases`.

Expone dos funciones públicas:

  * ``load_seed()`` — inserta las siglas del catálogo semilla que aún no existen.
    Idempotente: rellamar no duplica entradas.

  * ``resolve(name)`` — dado el token tal como spaCy lo extrajo (p.ej. "MINERD"
    o "minerd"), devuelve el nombre canónico si existe un alias activo;
    de lo contrario devuelve ``None``.

Diseño de caché:
  Los alias se cargan en memoria la primera vez que se llama ``resolve()`` y
  se refrescan en cada llamada a ``load_seed()`` o cuando se modifica un
  registro desde la API CRUD.  El módulo expone ``invalidate_cache()`` para
  que los endpoints puedan forzar el refresco tras un PUT/POST/DELETE.
"""
from __future__ import annotations

import logging
import threading
import unicodedata
from typing import TYPE_CHECKING

from sqlalchemy import select

from db.models import EntityAlias
from db.session import get_session, init_db

if TYPE_CHECKING:
    pass

log = logging.getLogger("odin.aliases")

# ──────────────────────────────────────────────────────────────────────────────
# Caché en memoria (alias_key -> (canonical_name, type))
# ──────────────────────────────────────────────────────────────────────────────
_lock = threading.Lock()
_cache: dict[str, tuple[str, str]] | None = None  # None = no cargado aún


def normalize_key(text: str) -> str:
    """Clave de comparación para alias: minúsculas y sin acentos, para que
    "Policia" y "Policía" (o "MINERD"/"Minerd") generen la misma clave."""
    text = text.strip().lower()
    return "".join(
        c for c in unicodedata.normalize("NFD", text) if unicodedata.category(c) != "Mn"
    )


def _build_cache() -> dict[str, tuple[str, str]]:
    session = get_session()
    try:
        rows = session.scalars(
            select(EntityAlias).where(EntityAlias.is_active.is_(True))
        ).all()
        # Se renormaliza `alias_key` acá (no solo al insertar) para que las
        # filas ya existentes con acentos en la clave también matcheen.
        return {normalize_key(r.alias_key): (r.canonical_name, r.type) for r in rows}
    finally:
        session.close()


def _get_cache() -> dict[str, tuple[str, str]]:
    global _cache
    with _lock:
        if _cache is None:
            _cache = _build_cache()
        return _cache


def invalidate_cache() -> None:
    """Descarta la caché para que el próximo ``resolve()`` la recargue."""
    global _cache
    with _lock:
        _cache = None


# ──────────────────────────────────────────────────────────────────────────────
# API pública
# ──────────────────────────────────────────────────────────────────────────────

def resolve(name: str) -> tuple[str, str] | None:
    """Devuelve ``(canonical_name, type)`` si existe un alias activo para
    *name*, o ``None`` si no hay coincidencia.

    La búsqueda es case-insensitive y sin acentos: "MINERD", "Minerd" y
    "minerd" son iguales, igual que "Policía" y "Policia".
    """
    key = normalize_key(name)
    if not key:
        return None
    return _get_cache().get(key)


def all_canonicals() -> list[tuple[str, str]]:
    """Devuelve los ``(canonical_name, type)`` únicos de los alias activos.
    Si la BD no está disponible, devuelve vacío en lugar de romper."""
    try:
        return list(set(_get_cache().values()))
    except Exception:
        log.warning("no se pudo cargar el catálogo de aliases", exc_info=True)
        return []


def load_seed() -> int:
    """Inserta el catálogo semilla en la BD.  Solo añade siglas que no existan;
    no modifica las existentes.  Devuelve el número de filas insertadas."""
    from db.seed_aliases import SEED_ALIASES  # importación local para evitar ciclos

    init_db()
    session = get_session()
    inserted = 0
    try:
        existing_keys = {
            normalize_key(k) for k in session.scalars(select(EntityAlias.alias_key)).all()
        }
        for alias, canonical_name, entity_type in SEED_ALIASES:
            alias_key = normalize_key(alias)
            if alias_key in existing_keys:
                continue
            session.add(
                EntityAlias(
                    alias=alias.strip(),
                    alias_key=alias_key,
                    canonical_name=canonical_name.strip(),
                    type=entity_type,
                )
            )
            existing_keys.add(alias_key)
            inserted += 1
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()

    invalidate_cache()
    log.info("seed_aliases: %d siglas insertadas", inserted)
    return inserted
