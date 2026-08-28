"""Repara el medio y los autores de reportes ya guardados.

Por qué hace falta: hasta ahora el medio de una nota analizada por URL salía
del `sitename` de trafilatura y, si no lo detectaba, quedaba "manual" — un
valor que no es un medio y que ensucia la dimensión por la que se filtra (R14).
Y el campo de autores conservaba al propio medio ("Listin Diario; Ashley
Martínez"), lo que mezcla una redacción con personas al contar por autor (R15).

Ambas cosas ya están corregidas para lo que entre de ahora en más; esto es para
lo que quedó guardado antes.

Uso:
    python scripts/repair_source_and_authors.py            # solo muestra
    python scripts/repair_source_and_authors.py --apply    # escribe
"""
from __future__ import annotations

import argparse
import sys
from dataclasses import dataclass

from sqlalchemy import select

from odin.db.models import Article
from odin.db.session import _get_sessionmaker
from odin.scrapers import SCRAPERS, source_from_url, source_name, strip_outlet_from_authors


@dataclass
class _Cambio:
    """Lo que se le va a escribir a un reporte.

    `authors_cambia` es un campo aparte y no se deduce de `new_authors`: dejar
    el campo VACÍO es un resultado legítimo —cuando lo único que había era el
    nombre del medio— y usar `None` para decir "no hay nada que hacer" saltaba
    justo esas filas, que son las que más lo necesitaban.
    """

    article: Article
    new_source: str | None = None
    new_authors: str | None = None
    authors_cambia: bool = False


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--apply",
        action="store_true",
        help="escribe los cambios; sin esta bandera solo los muestra",
    )
    args = parser.parse_args()

    session = _get_sessionmaker()()
    try:
        articles = session.scalars(select(Article).order_by(Article.id)).all()
        changes: list[_Cambio] = []

        for article in articles:
            # El medio solo se toca si HOY no es uno del registro y la URL sí
            # lo identifica: un medio ya correcto no se pisa, y uno que no
            # rastreamos conserva lo que tenga en vez de perderlo.
            new_source = None
            if article.source not in SCRAPERS:
                derived = source_from_url(article.url or "")
                if derived and derived != article.source:
                    new_source = derived

            effective = new_source or article.source
            cleaned = strip_outlet_from_authors(article.authors, effective)
            authors_cambia = cleaned != article.authors

            if new_source or authors_cambia:
                changes.append(
                    _Cambio(
                        article=article,
                        new_source=new_source,
                        new_authors=cleaned,
                        authors_cambia=authors_cambia,
                    )
                )

        if not changes:
            print("Nada que reparar.")
            return 0

        print(f"{len(changes)} de {len(articles)} reportes cambiarían:\n")
        for cambio in changes:
            article = cambio.article
            print(f"  #{article.id} {(article.title or '')[:52]}")
            if cambio.new_source:
                print(
                    f"      medio : {article.source!r} -> {cambio.new_source!r} "
                    f"({source_name(cambio.new_source)})"
                )
            if cambio.authors_cambia:
                destino = repr(cambio.new_authors) if cambio.new_authors else "(vacío: era solo el medio)"
                print(f"      autor : {article.authors!r} -> {destino}")

        if not args.apply:
            print("\nNada escrito. Repetí con --apply para aplicarlo.")
            return 0

        for cambio in changes:
            if cambio.new_source:
                cambio.article.source = cambio.new_source
            if cambio.authors_cambia:
                cambio.article.authors = cambio.new_authors
        session.commit()
        print(f"\nAplicado sobre {len(changes)} reportes.")
        return 0
    finally:
        session.close()


if __name__ == "__main__":
    sys.exit(main())
