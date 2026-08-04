"""Resuelve la fila de `canonical_entities` para un (nombre, tipo) ya
canonicalizado por `analysis/canonicalize.py`.

Este módulo NO reintenta la canonicalización (siglas, apellido único...): eso
ya ocurrió antes de llegar aquí. Su único trabajo es la dimensión durable:
dado el nombre que `canonicalize_entities()` produjo, buscar o crear la fila
de `CanonicalEntity` correspondiente y devolverla, para que `Entity` (la
mención en un artículo concreto) quede vinculada a ella.

`merge()` es la otra mitad del ciclo: cuando un usuario nota que dos filas de
`canonical_entities` son en realidad la misma figura ("Abinader" vs "Luis
Abinader" creadas antes de que la heurística los uniera), fusionarlas
reasigna TODAS las menciones ya guardadas de una a la otra — la corrección se
aplica de inmediato a todo el histórico, no solo a análisis futuros.
"""
from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from db.models import CanonicalEntity, Entity


def get_or_create(session: Session, name: str, type_: str) -> CanonicalEntity:
    """Devuelve la `CanonicalEntity` para (name, type), creándola si no existe.

    `session.flush()` tras crear: dentro de una misma transacción (p.ej. el
    crawl, que persiste muchos artículos antes de un solo commit por fuente)
    una llamada posterior con el mismo nombre debe encontrar esta fila por
    SELECT en vez de violar la unique constraint intentando crearla de nuevo.
    """
    existing = session.scalar(
        select(CanonicalEntity).where(
            CanonicalEntity.name == name, CanonicalEntity.type == type_
        )
    )
    if existing:
        return existing
    row = CanonicalEntity(name=name, type=type_)
    session.add(row)
    session.flush()
    return row


def resolve_actor_id(
    name: str | None, canonical_by_name: dict[str, CanonicalEntity]
) -> int | None:
    """Resuelve un actor de encuadre (`dominant_actor`/`blamed_actor`/
    `credited_actor`, ya reapuntado por `match_actor_name` al nombre
    canonicalizado de una entidad del propio artículo) a su `CanonicalEntity.id`.

    `canonical_by_name` es el mapa {Entity.name -> CanonicalEntity} construido
    en el mismo `_persist`/`save_article` mientras se crean las menciones del
    artículo: el actor SIEMPRE debe ser una de esas entidades (así lo garantiza
    `match_actor_name`), así que no se vuelve a tocar la BD aquí. Si el nombre
    no aparece en el mapa (no debería pasar, pero no se descarta el dato del
    LLM por un desajuste), devuelve `None` en vez de crear una fila nueva.
    """
    if not name:
        return None
    match = canonical_by_name.get(name)
    return match.id if match else None


def merge(session: Session, target_id: int, source_id: int) -> CanonicalEntity:
    """Funde `source_id` dentro de `target_id`: reasigna todas las menciones
    (`Entity.canonical_entity_id`) de una a la otra y borra la fuente.

    Devuelve la fila destino. Lanza `ValueError` si falta alguna, si son la
    misma, o si son de tipos distintos (no tiene sentido fundir una PERSON
    con una ORG aunque compartan nombre)."""
    if target_id == source_id:
        raise ValueError("no se puede fusionar una entidad canónica consigo misma")

    target = session.get(CanonicalEntity, target_id)
    source = session.get(CanonicalEntity, source_id)
    if target is None or source is None:
        raise ValueError("entidad canónica no encontrada")
    if target.type != source.type:
        raise ValueError(
            f"no se puede fusionar tipos distintos ({source.type} -> {target.type})"
        )

    session.query(Entity).filter(Entity.canonical_entity_id == source_id).update(
        {Entity.canonical_entity_id: target_id}
    )
    session.delete(source)
    session.flush()
    return target
