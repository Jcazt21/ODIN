"""Catálogo geográfico: carga de la semilla y resolución de nombres.

El árbol vive en `localities` (ver `db/models.Locality`); aquí está lo que lo
llena y lo que lo consulta por nombre. La semilla en JSON
(`db/seeds/localities_rd.json`) es el baseline versionado: garantiza que una
base nueva arranque con el mismo catálogo que las demás, y deja el histórico
de cambios en git. Pero la fuente de verdad en runtime es la TABLA, porque el
catálogo cambia por ley (Baitoa pasó a municipio en 2013; La Victoria y La
Caleta en 2024) y el cliente tiene que poder agregar el municipio nuevo el día
que sale la ley, sin esperar un deploy.
"""
from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

from odin.analysis.text_norm import norm_key
from odin.db.models import Locality, LocalityAlias

SEED_PATH = Path(__file__).parent / "seeds" / "localities_rd.json"


@lru_cache(maxsize=1)
def load_seed() -> dict:
    """Lee el JSON de la semilla (cacheado: el archivo no cambia en runtime)."""
    with SEED_PATH.open(encoding="utf-8") as fh:
        return json.load(fh)


def _flatten(seed: dict) -> list[dict]:
    """Aplana el JSON anidado a una lista de nodos en orden padre-antes-que-hijo.

    El orden importa: `seed_localities` necesita el id del padre ya asignado
    para poder calcular el `path` del hijo, así que no puede insertar un
    municipio antes que su provincia.

    Cada nodo sale como `{"key", "name", "level", "parent_key", "aliases"}`.
    `key` es una ruta de nombres normalizados ("pais/cibao/santiago") y sirve
    solo para enlazar padres con hijos durante la carga; no se persiste.
    """
    nodes: list[dict] = []

    pais = seed["pais"]
    pais_key = norm_key(pais["nombre"])
    nodes.append(
        {
            "key": pais_key,
            "name": pais["nombre"],
            "level": "PAIS",
            "parent_key": None,
            "aliases": pais.get("alias", []),
        }
    )

    for macro in seed["macrorregiones"]:
        macro_key = f"{pais_key}/{norm_key(macro['nombre'])}"
        nodes.append(
            {
                "key": macro_key,
                "name": macro["nombre"],
                "level": "MACRORREGION",
                "parent_key": pais_key,
                "aliases": macro.get("alias", []),
            }
        )
        for region in macro["regiones"]:
            region_key = f"{macro_key}/{norm_key(region['nombre'])}"
            nodes.append(
                {
                    "key": region_key,
                    "name": region["nombre"],
                    "level": "REGION",
                    "parent_key": macro_key,
                    "aliases": region.get("alias", []),
                }
            )
            for prov in region["provincias"]:
                prov_key = f"{region_key}/{norm_key(prov['nombre'])}"
                nodes.append(
                    {
                        "key": prov_key,
                        "name": prov["nombre"],
                        "level": "PROVINCIA",
                        "parent_key": region_key,
                        "aliases": prov.get("alias", []),
                    }
                )
                for muni in prov["municipios"]:
                    nodes.append(
                        {
                            "key": f"{prov_key}/{norm_key(muni['nombre'])}",
                            "name": muni["nombre"],
                            "level": "MUNICIPIO",
                            "parent_key": prov_key,
                            "aliases": muni.get("alias", []),
                        }
                    )
    return nodes


def _sync_aliases(session: Session, locality: Locality, aliases: list[str]) -> int:
    """Agrega los alias del JSON que le falten a este nodo. Devuelve cuántos.

    Solo agrega: no borra los que un admin haya creado desde la UI, y no toca
    el nombre del nodo (un municipio renombrado a mano no se revierte —ver el
    docstring de `seed_localities`).
    """
    existing = set(
        session.scalars(
            select(LocalityAlias.alias_key).where(
                LocalityAlias.locality_id == locality.id
            )
        ).all()
    )
    added = 0
    for alias in aliases:
        akey = norm_key(alias)
        if akey == locality.norm_key or akey in existing:
            continue  # un alias idéntico al nombre no aporta nada
        session.add(LocalityAlias(locality_id=locality.id, alias=alias, alias_key=akey))
        existing.add(akey)
        added += 1
    return added


def seed_localities(session: Session, *, seed: dict | None = None) -> int:
    """Carga el catálogo si falta, y devuelve cuántos nodos insertó.

    Idempotente: los nodos que ya existen (mismo padre y mismo `norm_key`) se
    saltan sin tocarse. Eso permite llamarla en cada arranque sin duplicar, y
    —más importante— que un municipio renombrado a mano desde la UI no se
    revierta solo la próxima vez que corra la semilla.

    Los ALIAS sí se sincronizan aunque el nodo ya exista: son aditivos y no
    pisan nada editado a mano. Si no, un alias nuevo en el JSON solo llegaría
    a las bases creadas desde cero, y en las que ya están en producción
    —justo donde hace falta— no aparecería nunca.
    """
    seed = seed or load_seed()
    inserted = 0
    ids: dict[str, int] = {}
    paths: dict[str, str] = {}

    for node in _flatten(seed):
        parent_key = node["parent_key"]
        parent_id = ids.get(parent_key) if parent_key else None
        nkey = norm_key(node["name"])

        existing = session.scalar(
            select(Locality).where(
                Locality.parent_id == parent_id, Locality.norm_key == nkey
            )
        )
        if existing:
            ids[node["key"]] = existing.id
            paths[node["key"]] = existing.path
            _sync_aliases(session, existing, node["aliases"])
            continue

        row = Locality(
            name=node["name"],
            norm_key=nkey,
            level=node["level"],
            parent_id=parent_id,
            path="",
            is_active=True,
        )
        session.add(row)
        # flush (no commit): necesitamos el id autogenerado AHORA para armar el
        # path de este nodo y el de sus hijos, pero sin cerrar la transacción
        # —si algo falla más adelante, la carga entera se revierte.
        session.flush()

        parent_path = paths.get(parent_key, "/") if parent_key else "/"
        row.path = f"{parent_path}{row.id}/"

        ids[node["key"]] = row.id
        paths[node["key"]] = row.path
        inserted += 1

        _sync_aliases(session, row, node["aliases"])

    session.commit()
    return inserted


def resolve(session: Session, name: str, *, level: str | None = None) -> Locality | None:
    """Busca un lugar por nombre exacto o por alias, sin importar acentos.

    Primero el nombre, después los alias: si "Santiago" es a la vez el nombre
    de una provincia y un alias de otra cosa, gana el nombre propio.
    """
    nkey = norm_key(name)

    stmt = select(Locality).where(Locality.norm_key == nkey, Locality.is_active.is_(True))
    if level:
        stmt = stmt.where(Locality.level == level)
    # order_by(id): con varios homónimos activos (el municipio cabecera suele
    # repetir el nombre de su provincia), devolver siempre el mismo evita que
    # el resultado dependa del orden físico de las filas.
    found = session.scalars(stmt.order_by(Locality.id)).first()
    if found:
        return found

    stmt = (
        select(Locality)
        .join(LocalityAlias, LocalityAlias.locality_id == Locality.id)
        .where(LocalityAlias.alias_key == nkey, Locality.is_active.is_(True))
    )
    if level:
        stmt = stmt.where(Locality.level == level)
    return session.scalars(stmt.order_by(Locality.id)).first()


def subtree_prefix(locality: Locality) -> str:
    """Prefijo LIKE que matchea el nodo y todo lo que cuelga de él.

    `path` ya termina en "/", así que agregar "%" cubre a los descendientes; y
    como el propio nodo se compara aparte (`path == prefix`), filtrar por una
    provincia incluye tanto las noticias marcadas en la provincia misma como
    las marcadas en sus municipios.
    """
    return f"{locality.path}%"
