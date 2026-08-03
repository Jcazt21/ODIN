"""CLI de Odin.

Ejemplos:
  python main.py --init-db                 # solo crear tablas
  python main.py                           # rastrear ambos periódicos
  python main.py --source diario_libre     # solo uno
  python main.py --limit 10                # máx. 10 artículos por fuente
  python main.py --list-sources            # ver fuentes disponibles
"""
from __future__ import annotations

import argparse
import logging

from config import settings
from scrapers import SCRAPERS


def main() -> None:
    parser = argparse.ArgumentParser(description="Odin - scraper y análisis de periódicos RD")
    parser.add_argument(
        "--source",
        action="append",
        dest="sources",
        choices=sorted(SCRAPERS.keys()),
        help="Fuente a rastrear (se puede repetir). Por defecto: todas.",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=settings.max_articles_per_source or None,
        help="Máximo de artículos por fuente (0 = sin límite).",
    )
    parser.add_argument(
        "--analyzer",
        choices=["local", "gemini"],
        default="local",
        help="Motor de análisis: 'local' (gratis, por defecto) o 'gemini' "
        "(Google Gemini, requiere google-genai + GEMINI_API_KEY).",
    )
    parser.add_argument("--init-db", action="store_true", help="Solo crear las tablas y salir.")
    parser.add_argument("--list-sources", action="store_true", help="Listar fuentes y salir.")
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

    if args.list_sources:
        for key, cls in SCRAPERS.items():
            print(f"  {key:16s} -> {cls.name}")
        return

    if args.init_db:
        from db.session import init_db

        init_db()
        print("Tablas creadas.")
        return

    # Carga perezosa: importar el analizador aquí evita cargar modelos pesados
    # cuando solo se listan fuentes o se inicializa la BD.
    if args.analyzer == "gemini":
        from analysis.gemini_analyzer import GeminiAnalyzer

        analyzer = GeminiAnalyzer()
    else:
        from analysis import LocalAnalyzer

        analyzer = LocalAnalyzer()
    limit = args.limit if args.limit and args.limit > 0 else None

    from pipeline import run

    stats = run(analyzer=analyzer, sources=args.sources, limit=limit)

    print("\n=== Resumen ===")
    total = 0
    for source, count in stats.items():
        print(f"  {source:16s}: {count} artículos nuevos")
        total += count
    print(f"  {'TOTAL':16s}: {total}")


if __name__ == "__main__":
    main()
