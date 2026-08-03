"""Consultas rápidas sobre lo guardado (para revisar resultados sin SQL a mano).

Ejemplos:
  python report.py                      # resumen general
  python report.py --entity "Abinader"  # opiniones hacia una figura/empresa
"""
from __future__ import annotations

import argparse

from sqlalchemy import func, select

from db.models import Article, Entity
from db.session import get_session


def summary(session) -> None:
    total = session.scalar(select(func.count(Article.id)))
    print(f"Artículos guardados: {total}\n")

    print("Por fuente:")
    for source, count in session.execute(
        select(Article.source, func.count(Article.id)).group_by(Article.source)
    ):
        print(f"  {source:16s}: {count}")

    print("\nSentimiento global:")
    for sent, count in session.execute(
        select(Article.overall_sentiment, func.count(Article.id)).group_by(
            Article.overall_sentiment
        )
    ):
        print(f"  {sent or '-':4s}: {count}")

    print("\nFiguras/empresas más mencionadas:")
    rows = session.execute(
        select(Entity.name, Entity.type, func.count(Entity.id).label("n"))
        .group_by(Entity.name, Entity.type)
        .order_by(func.count(Entity.id).desc())
        .limit(15)
    )
    for name, etype, n in rows:
        print(f"  {n:3d}  {name} ({etype})")


def entity_report(session, needle: str) -> None:
    rows = session.execute(
        select(Entity, Article.title, Article.source)
        .join(Article, Entity.article_id == Article.id)
        .where(Entity.name.ilike(f"%{needle}%"))
        .order_by(Entity.sentiment_toward)
    ).all()
    if not rows:
        print(f"Sin menciones de '{needle}'.")
        return
    print(f"Menciones de '{needle}':\n")
    for ent, title, source in rows:
        print(f"  [{ent.sentiment_toward} {ent.sentiment_score}] {ent.name} — {source}")
        print(f"      art: {title[:70]}")
        if ent.context:
            print(f"      ctx: {ent.context[:120]}")
        print()


def main() -> None:
    parser = argparse.ArgumentParser(description="Reportes de Odin")
    parser.add_argument("--entity", help="Filtrar opiniones hacia una figura/empresa")
    args = parser.parse_args()

    session = get_session()
    try:
        if args.entity:
            entity_report(session, args.entity)
        else:
            summary(session)
    finally:
        session.close()


if __name__ == "__main__":
    main()
