"""Unifica entidades duplicadas YA guardadas en la BD.

Aplica retroactivamente la misma canonicalización que ahora corre en cada
análisis (analysis/canonicalize.py): catálogo de aliases, apellido -> nombre
completo único ("Abinader" -> "Luis Abinader") y fusión de filas que quedan
con el mismo (artículo, nombre, tipo), sumando menciones.

100% local: no llama a ningún LLM.

Uso:
  python scripts/merge_duplicate_entities.py            # BD del .env
  DATABASE_URL=... python scripts/merge_duplicate_entities.py   # otra BD
  python scripts/merge_duplicate_entities.py --dry-run  # solo mostrar
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import select

import odin.db.aliases as alias_store
from analysis.canonicalize import _NAME_PARTICLES, _norm_key, known_person_fullname_map
from odin.db.models import Article, Entity
from odin.db.session import get_session, init_db


def _canonical_name(name: str, etype: str, person_map: dict[str, str]) -> tuple[str, str]:
    """Nombre y tipo canónicos para una fila existente (aliases + apellido)."""
    match = alias_store.resolve(name)
    if match:
        return match
    if etype == "PERSON":
        words = [w for w in _norm_key(name).split() if w not in _NAME_PARTICLES]
        if len(words) == 1:
            full = person_map.get(words[0])
            if full and _norm_key(full) != _norm_key(name):
                return full, etype
    return name, etype


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true", help="Mostrar cambios sin aplicarlos.")
    args = parser.parse_args()

    init_db()
    alias_store.load_seed()  # idempotente: asegura el catálogo al día
    person_map = known_person_fullname_map()
    session = get_session()
    renamed = merged = 0
    try:
        with session.no_autoflush:
            for article in session.scalars(select(Article)).all():
                # 1) agrupar filas por su (nombre, tipo) canónico
                groups: dict[tuple[str, str], list[Entity]] = {}
                targets: dict[tuple[str, str], tuple[str, str]] = {}
                for ent in list(article.entities):
                    new_name, new_type = _canonical_name(ent.name, ent.type, person_map)
                    key = (_norm_key(new_name), new_type)
                    groups.setdefault(key, []).append(ent)
                    targets[key] = (new_name, new_type)

                # 2) por grupo: conservar la fila que YA tiene el nombre canónico
                # (así nunca renombramos hacia un nombre ocupado, lo que
                # chocaría con la constraint única al hacer flush) y fundir
                # las demás en ella.
                for key, rows in groups.items():
                    new_name, new_type = targets[key]
                    keeper = next(
                        (r for r in rows if r.name == new_name and r.type == new_type),
                        max(rows, key=lambda r: r.mentions_count),
                    )
                    if keeper.name != new_name or keeper.type != new_type:
                        print(
                            f"  [art {article.id}] {keeper.name!r} ({keeper.type}) "
                            f"-> {new_name!r} ({new_type})"
                        )
                        keeper.name, keeper.type = new_name, new_type
                        renamed += 1
                    for ent in rows:
                        if ent is keeper:
                            continue
                        print(
                            f"  [art {article.id}] fusionando {ent.name!r} "
                            f"({ent.mentions_count} menciones) en {new_name!r}"
                        )
                        keeper.mentions_count += ent.mentions_count
                        if keeper.sentiment_toward is None:
                            keeper.sentiment_toward = ent.sentiment_toward
                            keeper.sentiment_score = ent.sentiment_score
                        if keeper.context is None:
                            keeper.context = ent.context
                        article.entities.remove(ent)  # delete-orphan la borra
                        merged += 1
        if args.dry_run:
            session.rollback()
            print(f"\n[dry-run] {renamed} renombres, {merged} fusiones (no aplicado)")
        else:
            session.commit()
            print(f"\nListo: {renamed} renombres, {merged} fusiones")
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


if __name__ == "__main__":
    main()
