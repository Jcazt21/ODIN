"""Estima la tasa base de sentimiento por frase de pysentimiento y la escribe
a `src/odin/analysis/sentiment_prior.json`.

`LocalAnalyzer._aggregate_document` descuenta esa tasa base para quitar el
sesgo de clase del modelo: pysentimiento está entrenado en tuits y deja ~50% de
masa NEU por frase, así que promediar decenas de frases arrastra cualquier
artículo hacia NEU sin importar lo que diga (ver el docstring de
`_aggregate_document` y docs/PRECISION.md §4).

POR QUÉ UN CORPUS APARTE: el prior NO debe salir del golden set. Si sale de
ahí, los 42 artículos dejan de ser un conjunto de prueba limpio y la métrica se
vuelve optimista sin que se note. Este script usa los artículos ya scrapeados
en la BD (`scripts/scrape_politics.py`) y descarta cualquiera cuya URL esté en
el golden set.

No llama a ningún LLM: solo usa pysentimiento, que corre local y gratis
(ver CLAUDE.md).

Uso:
  python scripts/estimate_sentiment_prior.py
  python scripts/estimate_sentiment_prior.py --min-articles 100
  python scripts/estimate_sentiment_prior.py --out otro/sitio.json
"""
from __future__ import annotations

import argparse
import json
import sys
from collections import defaultdict
from datetime import UTC, datetime
from pathlib import Path

from odin.analysis.local_analyzer import LocalAnalyzer, _Sentences
from odin.db.models import Article
from odin.db.session import get_session

DEFAULT_OUT = Path(__file__).resolve().parents[1] / "src/odin/analysis/sentiment_prior.json"
DEFAULT_GOLDEN_SET = Path(__file__).resolve().parents[1] / "tests/eval/golden_set.jsonl"
# por debajo de esto el prior es demasiado ruidoso para confiar en él: mejor
# fallar ruidosamente que escribir un archivo malo que nadie va a revisar
DEFAULT_MIN_ARTICLES = 100


def _golden_set_urls(path: Path) -> set[str]:
    if not path.exists():
        return set()
    urls: set[str] = set()
    with path.open(encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            url = json.loads(line).get("url")
            if url:
                urls.add(url.strip())
    return urls


def main() -> None:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    parser.add_argument("--golden-set", type=Path, default=DEFAULT_GOLDEN_SET)
    parser.add_argument("--min-articles", type=int, default=DEFAULT_MIN_ARTICLES)
    args = parser.parse_args()

    excluded = _golden_set_urls(args.golden_set)
    print(f"URLs del golden set a excluir: {len(excluded)}")

    with get_session() as session:
        rows = session.query(Article.url, Article.title, Article.body).all()

    corpus = [
        (title or "", body or "")
        for url, title, body in rows
        if (url or "").strip() not in excluded and (body or "").strip()
    ]
    skipped = len(rows) - len(corpus)
    print(f"Artículos en la BD: {len(rows)}  |  usables: {len(corpus)}  |  descartados: {skipped}")

    if len(corpus) < args.min_articles:
        print(
            f"\nERROR: hacen falta al menos {args.min_articles} artículos y hay {len(corpus)}.\n"
            "Corre primero:  python scripts/scrape_politics.py --target 250\n"
            "NO se escribió nada: un prior estimado sobre pocos artículos es peor\n"
            "que el fallback que ya trae local_analyzer.py.",
            file=sys.stderr,
        )
        raise SystemExit(1)

    analyzer = LocalAnalyzer()
    totals: dict[str, float] = defaultdict(float)
    n_sentences = 0
    for i, (title, body) in enumerate(corpus, start=1):
        # spaCy solo para segmentar frases: el NER es el componente más caro y
        # aquí no se usa ninguna entidad
        doc = analyzer.nlp(f"{title}.\n\n{body}".strip(), disable=["ner"])
        for probas in analyzer._sentiment_per_sentence(_Sentences.from_doc(doc).texts):
            if not probas:
                continue
            for label, prob in probas.items():
                totals[label] += prob
            n_sentences += 1
        if i % 25 == 0:
            print(f"  {i}/{len(corpus)} artículos, {n_sentences} frases")

    prior = {label: round(total / n_sentences, 6) for label, total in sorted(totals.items())}
    payload = {
        "prior": prior,
        "n_articles": len(corpus),
        "n_sentences": n_sentences,
        "estimated_at": datetime.now(UTC).date().isoformat(),
        "note": (
            "Tasa base de sentimiento por frase de pysentimiento sobre prensa "
            "dominicana, medida sobre artículos scrapeados SIN etiquetar y "
            "excluyendo las URLs del golden set. La consume "
            "LocalAnalyzer._aggregate_document. Regenerar con "
            "scripts/estimate_sentiment_prior.py."
        ),
    }
    args.out.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"\nPrior por frase ({n_sentences} frases de {len(corpus)} artículos):")
    for label, value in prior.items():
        print(f"  {label}: {value}")
    print(f"\nEscrito en {args.out}")


if __name__ == "__main__":
    main()
