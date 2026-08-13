"""Rastrea las 8 fuentes permitidas filtrando solo noticias de política de RD,
para construir la base del golden set (task.md §2.4 / §0.1).

Ningún scraper salvo Diario Libre expone una sección "política" confiable
(`main.py` no tiene `--category`, ver task.md), así que el filtro corre por
palabras clave sobre título + cuerpo del artículo ya extraído, reutilizando el
hook `article_filter` de `pipeline.run()`. Reparte el total entre fuentes con
un tope por fuente para que el corpus no quede dominado por una sola (el golden
set necesita variedad de fuente/sección, no solo volumen).

100% LocalAnalyzer por defecto (gratis) — ver CLAUDE.md: no se factura Gemini
para construir un corpus de cientos de artículos.

Uso:
  python scripts/scrape_politics.py                     # hasta 250, reparto automático
  python scripts/scrape_politics.py --target 300
  python scripts/scrape_politics.py --per-source-cap 40
  python scripts/scrape_politics.py --dry-run            # solo cuenta, no persiste
  python scripts/scrape_politics.py --analyzer groq      # motor alterno (free tier)
"""
from __future__ import annotations

import argparse
import math
import sys
from collections import defaultdict
from pathlib import Path
from typing import TYPE_CHECKING

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from odin.analysis.politics_filter import is_dominican_politics, make_filter  # noqa: E402
from odin.scrapers import SCRAPERS  # noqa: E402

if TYPE_CHECKING:
    from odin.analysis.base import Analyzer


def _dry_run(target: int, per_source_cap: int) -> None:
    """Solo cuenta cuántos artículos de política habría por fuente, sin
    analizar ni persistir nada (sigue haciendo fetch real, robots.txt +
    throttle de BaseScraper aplican igual)."""
    counts: dict[str, int] = defaultdict(int)
    total = 0
    for key, scraper_cls in SCRAPERS.items():
        scraper = scraper_cls()
        print(f"-- {scraper.name} ({key}) --")
        for article in scraper.scrape(limit=None):
            if total >= target or counts[key] >= per_source_cap:
                break
            if is_dominican_politics(article):
                counts[key] += 1
                total += 1
                print(f"  [{counts[key]:>3}] {article.title[:80]}")
        if total >= target:
            break
    print("\n=== Resumen (dry-run, nada se guardó) ===")
    for key in SCRAPERS:
        print(f"  {key:16s}: {counts.get(key, 0)}")
    print(f"  {'TOTAL':16s}: {total}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--target", type=int, default=250, help="Total de artículos de política a insertar.")
    parser.add_argument(
        "--per-source-cap",
        type=int,
        default=None,
        help="Máx. por fuente (default: ceil(target / nº de fuentes)).",
    )
    parser.add_argument(
        "--analyzer",
        choices=["local", "gemini", "groq", "hybrid"],
        default="local",
        help="Motor de análisis: 'local' (gratis, por defecto). 'gemini' hace "
        "una llamada FACTURADA por artículo (ver CLAUDE.md) — úsalo solo si lo "
        "pides explícitamente.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Solo cuenta cuántos artículos de política encontraría por fuente; no analiza ni guarda.",
    )
    args = parser.parse_args()

    per_source_cap = args.per_source_cap or math.ceil(args.target / len(SCRAPERS))

    if args.dry_run:
        _dry_run(args.target, per_source_cap)
        return

    if args.analyzer == "gemini":
        print(
            "AVISO: --analyzer gemini factura una llamada por artículo. "
            f"Vas a insertar hasta {args.target} artículos — confirma que "
            "quieres pagar por esto antes de seguir.",
            file=sys.stderr,
        )

    from odin.core.observability import configure_logging, init_sentry

    configure_logging()
    init_sentry()

    analyzer: Analyzer
    if args.analyzer == "gemini":
        from odin.analysis.gemini_analyzer import GeminiAnalyzer

        analyzer = GeminiAnalyzer()
    elif args.analyzer == "groq":
        from odin.analysis.groq_analyzer import GroqAnalyzer

        analyzer = GroqAnalyzer()
    elif args.analyzer == "hybrid":
        from odin.analysis.groq_analyzer import HybridAnalyzer

        analyzer = HybridAnalyzer()
    else:
        from odin.analysis import LocalAnalyzer

        analyzer = LocalAnalyzer()

    from odin.core.pipeline import run

    article_filter, _ = make_filter(args.target, per_source_cap)
    print(f"Objetivo: {args.target} artículos de política, tope {per_source_cap} por fuente.\n")
    stats = run(analyzer=analyzer, sources=list(SCRAPERS), limit=None, article_filter=article_filter)

    print("\n=== Resumen ===")
    total = 0
    for source, count in stats.items():
        print(f"  {source:16s}: {count} artículos nuevos")
        total += count
    print(f"  {'TOTAL':16s}: {total}")
    if total < args.target:
        print(
            f"\nNo se alcanzó el objetivo ({total}/{args.target}). Las fuentes con "
            "RSS chico (al_momento, el_dia, n_digital) se agotan rápido y los "
            "sitemaps solo cubren noticias recientes — vuelve a correr el script "
            "en unos días para sumar lo nuevo publicado, o baja --target."
        )


if __name__ == "__main__":
    main()
