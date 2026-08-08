"""Canonicalización de entidades: un solo nombre por figura/empresa.

Resuelve el problema de que la misma entidad entre a la BD con nombres
distintos según el artículo ("Abinader" vs "Luis Abinader", "PRM" vs
"Partido Revolucionario Moderno"). Se aplica en TODOS los puntos donde un
análisis se convierte en filas de la BD: la vista previa (`/api/analyze`),
el guardado manual (`POST /api/articles`) y el crawl (`pipeline.py`).

Pasos, todos locales y gratis (cero llamadas a LLM):

  1. Catálogo de aliases (`entity_aliases`): "MINERD" -> nombre completo.
  2. Fusión intra-lista: un nombre contenido por palabras en otro más largo
     del mismo tipo se funde con él ("Abinader" ⊂ "Luis Abinader").
  3. Apellido/nombre parcial -> nombre completo ya conocido en la BD, SOLO
     si la coincidencia es única: "Abinader" -> "Luis Abinader" se aplica
     porque solo hay un *Abinader* registrado; "Fernández" NO se toca si
     conviven Leonel, Omar y César Fernández.
  4. Deduplicado final por (nombre normalizado, tipo) sumando menciones.

Funciona con cualquier objeto que tenga los atributos `name`, `type`,
`mentions_count`, `sentiment_toward`, `sentiment_score` y `context`
(EntityResult del análisis o EntityPayload de la API).
"""
from __future__ import annotations

import logging
import threading
import time
from typing import Any

from sqlalchemy import select

import db.aliases as alias_store
from analysis.text_norm import norm_key as _norm_key
from analysis.text_norm import strip_accents as _strip_accents

log = logging.getLogger("odin.canonicalize")

# partículas que no cuentan como "palabra significativa" de un nombre
_NAME_PARTICLES = {"de", "del", "la", "las", "los", "y", "e"}

# títulos de cortesía/cargo que spaCy a veces incluye en el span de PERSON
# cuando van pegados al nombre sin coma ("Presidente Abinader" como una sola
# entidad): no son parte del nombre y duplican la entidad si se dejan (misma
# persona con y sin título cuenta como dos claves distintas).
_TITLE_WORDS = {
    "presidente", "vicepresidente", "ministro", "ministra", "director", "directora",
    "senador", "senadora", "diputado", "diputada", "gobernador", "gobernadora",
    "alcalde", "alcaldesa", "general", "coronel", "doctor", "doctora", "ingeniero",
    "ingeniera", "licenciado", "licenciada", "reverendo", "monsenor", "cardenal",
    "obispo", "padre", "pastor", "pastora",
}


def _strip_title_prefix(name: str) -> str:
    """Elimina un título de cortesía del inicio del nombre, si lo hay."""
    words = name.split()
    if len(words) > 1 and _strip_accents(words[0].lower()) in _TITLE_WORDS:
        return " ".join(words[1:])
    return name


# Caché del mapa apellido -> nombre completo. Mismo diseño que el catálogo de
# aliases (`db/aliases.py`): se construye a demanda y se invalida
# explícitamente desde los puntos que escriben entidades. El mapa se consulta
# en CADA análisis y se arma con un escaneo de todos los PERSON guardados; con
# el corpus pequeño no se nota, pero es una consulta que crece con el histórico
# para responder siempre casi lo mismo.
#
# Además del descarte explícito hay un TTL, y no es redundante: la
# invalidación solo alcanza al proceso que hizo la escritura. Un crawl del CLI
# (`main.py`) mete entidades en la misma BD desde OTRO proceso, y el servidor
# de la API no se entera de eso por más que se invalide bien en su propio
# código. El TTL es el techo de cuánto puede quedarse atrás en ese caso.
_PERSON_MAP_TTL_SECONDS = 600

_map_lock = threading.Lock()
_person_map_cache: dict[str, str] | None = None
_person_map_built_at = 0.0


def invalidate_person_map() -> None:
    """Descarta la caché de `known_person_fullname_map`. La llaman los puntos
    que agregan o renombran entidades PERSON: es lo que mantiene vivo el ciclo
    de retroalimentación descrito abajo (una corrección manual debe verse en el
    análisis siguiente, no cuando venza el TTL)."""
    global _person_map_cache
    with _map_lock:
        _person_map_cache = None


def known_person_fullname_map() -> dict[str, str]:
    """Mapa apellido -> nombre completo, construido con los PERSON ya guardados
    en la BD, los `canonical_entities` PERSON (incluye renombrados manuales) y
    los canónicos PERSON del catálogo de aliases.

    El resultado queda cacheado hasta que alguien llame a
    `invalidate_person_map()` (ver arriba).

    Solo se indexa la ÚLTIMA palabra significativa de cada nombre completo
    ("abinader" para "Luis Abinader"): es el patrón con que la prensa abrevia
    ("Abinader", "Fulcar"). Los nombres de pila famosos ("Danilo", "Leonel")
    se resuelven vía el catálogo curado de aliases, no aquí — indexar todas
    las palabras produciría falsos positivos. Los apellidos que apuntan a MÁS
    de un nombre completo distinto se descartan por ambiguos ("Fernández" con
    Leonel, Omar y César en la BD no se toca). Si la BD no está disponible,
    devuelve vacío en lugar de romper el análisis — y en ese caso NO se cachea,
    para no dejar clavado un mapa vacío por un fallo pasajero.

    Incluir `canonical_entities` (no solo `Entity.name`) es lo que cierra el
    ciclo de retroalimentación: si un usuario corrige el nombre de una figura
    en el panel de entidades canónicas, esa corrección entra aquí en el
    siguiente análisis — no hace falta esperar a que la prensa repita el
    nombre completo en un artículo nuevo para que vuelva a resolverse bien.
    """
    global _person_map_cache, _person_map_built_at

    with _map_lock:
        fresh = time.monotonic() - _person_map_built_at < _PERSON_MAP_TTL_SECONDS
        if _person_map_cache is not None and fresh:
            return _person_map_cache

    from db.models import CanonicalEntity, Entity
    from db.session import get_session

    candidates: dict[str, set[str]] = {}

    def _index(full_name: str) -> None:
        words = [w for w in _norm_key(full_name).split() if w not in _NAME_PARTICLES]
        if len(words) < 2:
            return  # un nombre de una sola palabra no desambigua nada
        candidates.setdefault(words[-1], set()).add(full_name)

    db_available = True
    try:
        session = get_session()
        try:
            names = session.scalars(
                select(Entity.name).where(Entity.type == "PERSON").distinct()
            ).all()
            canonical_names = session.scalars(
                select(CanonicalEntity.name).where(CanonicalEntity.type == "PERSON")
            ).all()
        finally:
            session.close()
    except Exception:
        log.warning("no se pudo leer entidades PERSON de la BD", exc_info=True)
        db_available = False
        names = []
        canonical_names = []

    for name in names:
        _index(name)
    for name in canonical_names:
        _index(name)
    for canonical, etype in alias_store.all_canonicals():
        if etype == "PERSON":
            _index(canonical)

    person_map = {w: next(iter(fulls)) for w, fulls in candidates.items() if len(fulls) == 1}
    if db_available:
        with _map_lock:
            _person_map_cache = person_map
            _person_map_built_at = time.monotonic()
    return person_map


def _apply_alias_catalog(entities: list) -> None:
    """Sustituye in-place el nombre por el canónico del catálogo de siglas.
    El tipo registrado en el alias tiene prioridad (corrige p.ej. "Impuestos
    Internos" marcado como PERSON)."""
    for ent in entities:
        match = alias_store.resolve(ent.name)
        if match:
            ent.name, ent.type = match


def _resolve_partial_persons(entities: list, person_map: dict[str, str]) -> None:
    """"Abinader" -> "Luis Abinader" cuando la BD solo conoce un Abinader."""
    for ent in entities:
        if ent.type != "PERSON":
            continue
        words = [w for w in _norm_key(ent.name).split() if w not in _NAME_PARTICLES]
        if len(words) != 1:  # solo nombres parciales de una palabra
            continue
        full = person_map.get(words[0])
        if full and _norm_key(full) != _norm_key(ent.name):
            log.info("canonicalizado %r -> %r", ent.name, full)
            ent.name = full


def _significant_words(nkey: str) -> set[str]:
    return {w for w in nkey.split() if w not in _NAME_PARTICLES}


def _merge_duplicates(entities: list) -> list:
    """Funde entidades con el mismo (nombre normalizado, tipo) y las que están
    contenidas por palabras en un nombre más largo del mismo tipo. Conserva el
    sentimiento de la variante con más menciones y suma los conteos.

    Para PERSON también funde por nombre parcial no contiguo ("Luis Abinader"
    dentro de "Luis Rodolfo Abinader Corona"): el apellido materno que la
    prensa omite queda al final del nombre legal, así que exigir subcadena
    contigua (el chequeo de arriba) nunca conecta ambas formas. Se exige que
    TODAS las palabras significativas del nombre corto aparezcan en el largo
    (no solo una) y que el nombre largo sea la única coincidencia, para no
    fundir por un solo nombre de pila compartido ("Juan Pablo Duarte" con
    "Juan Pablo Pichardo")."""
    ordered = sorted(entities, key=lambda e: (len(_norm_key(e.name)), e.mentions_count), reverse=True)
    # Any y no un tipo concreto: esto trabaja por duck typing sobre EntityResult
    # (análisis) y EntityPayload (API), que comparten campos pero no jerarquía.
    merged: dict[tuple[str, str], Any] = {}
    for ent in ordered:
        nkey = _norm_key(ent.name)
        if not nkey:
            continue
        target_key = None
        if (nkey, ent.type) in merged:
            target_key = (nkey, ent.type)
        else:
            for mkey, mtype in merged:
                if mtype == ent.type and f" {nkey} " in f" {mkey} ":
                    target_key = (mkey, mtype)
                    break
        if target_key is None and ent.type == "PERSON":
            words = _significant_words(nkey)
            if len(words) >= 2:
                candidates = [
                    (mkey, mtype)
                    for mkey, mtype in merged
                    if mtype == ent.type
                    and words < _significant_words(mkey)  # subconjunto propio: mkey debe ser más largo
                ]
                if len(candidates) == 1:
                    target_key = candidates[0]
        if target_key is None:
            merged[(nkey, ent.type)] = ent
        else:
            dst = merged[target_key]
            dst.mentions_count += ent.mentions_count
            if dst.sentiment_toward is None:
                dst.sentiment_toward = ent.sentiment_toward
                dst.sentiment_score = ent.sentiment_score
            if dst.context is None:
                dst.context = ent.context
            # La fusión en sí es evidencia de que la identidad es correcta
            # (dos variantes del mismo string apuntan a la misma persona):
            # se queda con la confianza más alta entre las variantes, no la
            # del nombre más largo por defecto.
            dst_conf = getattr(dst, "extraction_confidence", 1.0)
            src_conf = getattr(ent, "extraction_confidence", 1.0)
            if src_conf > dst_conf:
                dst.extraction_confidence = src_conf
    result = list(merged.values())
    result.sort(key=lambda e: e.mentions_count, reverse=True)
    return result


def canonicalize_entities(entities: list, person_map: dict[str, str] | None = None) -> list:
    """Aplica los pasos y devuelve la lista canonicalizada (puede ser más
    corta que la de entrada si hubo fusiones). `person_map` se puede pasar
    precomputado para procesar varios artículos con una sola consulta.

    Orden importante: se funde PRIMERO dentro del propio artículo (mismo
    texto, sin depender de la BD) y solo DESPUÉS se resuelve contra el
    historial de la BD (`_resolve_partial_persons`). Si "Rodríguez" y "Jean
    Alain Rodríguez" aparecen como dos menciones separadas en el mismo
    artículo (spaCy extrajo una parcial y otra completa), deben fundirse
    entre sí antes de que "Rodríguez" tenga oportunidad de resolverse contra
    un homónimo histórico distinto ya guardado en la BD (p.ej. "Jean Luis
    Rodríguez") — hacerlo al revés fusiona con la persona equivocada porque
    nunca se le da la chance a la evidencia del propio artículo de ganar."""
    entities = [e for e in entities if (e.name or "").strip()]
    for ent in entities:
        ent.name = " ".join(ent.name.split())
        if ent.type == "PERSON":
            ent.name = _strip_title_prefix(ent.name)
    _apply_alias_catalog(entities)
    entities = _merge_duplicates(entities)
    if person_map is None:
        person_map = known_person_fullname_map()
    _resolve_partial_persons(entities, person_map)
    return _merge_duplicates(entities)


def match_actor_name(name: str | None, entities: list) -> str | None:
    """Reapunta un nombre de actor (dominant/blamed/credited) a la entidad
    canonicalizada que le corresponde: si "Abinader" se convirtió en
    "Luis Abinader", el actor debe seguirlo. Devuelve el nombre tal cual si
    no hay entidad que coincida (no inventamos ni descartamos)."""
    if not name or not (name := " ".join(name.split())):
        return None
    match = alias_store.resolve(name)
    if match:
        name = match[0]
    nkey = _norm_key(name)
    for ent in entities:
        ekey = _norm_key(ent.name)
        if nkey == ekey or f" {nkey} " in f" {ekey} ":
            return ent.name
    return name


def canonicalize_result(result, person_map: dict[str, str] | None = None) -> None:
    """Canonicaliza in-place un AnalysisResult completo: entidades + los
    campos de actor del análisis de encuadre."""
    result.entities = canonicalize_entities(result.entities, person_map=person_map)
    for attr in ("dominant_actor", "blamed_actor", "credited_actor"):
        if hasattr(result, attr):
            setattr(result, attr, match_actor_name(getattr(result, attr), result.entities))
