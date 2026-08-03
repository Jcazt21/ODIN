"""Evalúa un analizador contra el golden set (tests/eval/golden_set.jsonl).

Reemplaza la tabla de precisión de README.md, que hoy no tiene ningún
artefacto que la respalde (task.md §2.4): corre un analizador sobre artículos
reales etiquetados a mano y saca precision/recall/F1 por tipo de entidad,
matriz de confusión de sentimiento global y accuracy de `sentiment_toward`.

Uso:
  python scripts/evaluate.py                      # LocalAnalyzer (gratis), golden set por defecto
  python scripts/evaluate.py --golden-set otro.jsonl
  python scripts/evaluate.py --analyzer gemini     # llamadas FACTURADAS a Gemini, ver CLAUDE.md

Formato de tests/eval/golden_set.jsonl: ver tests/eval/README.md.
"""
from __future__ import annotations

import argparse
import json
import sys
import unicodedata
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from analysis.base import Analyzer, EntityResult

SENTIMENT_VALUES = ("POS", "NEG", "NEU")


# ── carga del golden set ─────────────────────────────────────────────────────


@dataclass
class GoldEntity:
    name: str
    type: str
    sentiment_toward: str | None


@dataclass
class GoldArticle:
    id: str
    title: str
    body: str
    overall_sentiment: str
    entities: list[GoldEntity]
    entities_exhaustive: bool


def load_golden_set(path: Path) -> list[GoldArticle]:
    articles: list[GoldArticle] = []
    with path.open(encoding="utf-8") as f:
        for lineno, line in enumerate(f, start=1):
            line = line.strip()
            if not line:
                continue
            try:
                row = json.loads(line)
            except json.JSONDecodeError as exc:
                raise ValueError(f"{path}:{lineno}: JSON inválido: {exc}") from exc
            articles.append(
                GoldArticle(
                    id=row["id"],
                    title=row["title"],
                    body=row["body"],
                    overall_sentiment=row["overall_sentiment"],
                    entities_exhaustive=row.get("entities_exhaustive", True),
                    entities=[
                        GoldEntity(
                            name=e["name"],
                            type=e["type"],
                            sentiment_toward=e.get("sentiment_toward"),
                        )
                        for e in row["entities"]
                    ],
                )
            )
    return articles


# ── normalización y emparejamiento de nombres (mismo criterio que
#    analysis/canonicalize.py: sin acentos, minúsculas, contención por
#    palabras completas — para no penalizar como "falso negativo" que el
#    analizador extraiga "Impuestos Internos" cuando el gold dice "Dirección
#    General de Impuestos Internos") ─────────────────────────────────────────


def _strip_accents(text: str) -> str:
    return "".join(
        c for c in unicodedata.normalize("NFD", text) if unicodedata.category(c) != "Mn"
    )


def _norm_key(name: str) -> str:
    return " ".join(_strip_accents(name).lower().split())


def _names_match(a: str, b: str) -> bool:
    na, nb = _norm_key(a), _norm_key(b)
    if not na or not nb:
        return False
    return na == nb or f" {na} " in f" {nb} " or f" {nb} " in f" {na} "


# ── métricas de entidades ────────────────────────────────────────────────────


@dataclass
class EntityMetrics:
    tp: int = 0
    fp: int = 0
    fn: int = 0
    sentiment_correct: int = 0
    sentiment_total: int = 0

    @property
    def precision(self) -> float | None:
        denom = self.tp + self.fp
        return round(self.tp / denom, 4) if denom else None

    @property
    def recall(self) -> float | None:
        denom = self.tp + self.fn
        return round(self.tp / denom, 4) if denom else None

    @property
    def f1(self) -> float | None:
        p, r = self.precision, self.recall
        if not p or not r or (p + r) == 0:
            return None
        return round(2 * p * r / (p + r), 4)

    @property
    def sentiment_accuracy(self) -> float | None:
        return round(self.sentiment_correct / self.sentiment_total, 4) if self.sentiment_total else None


def _match_entities(
    predicted: list[EntityResult], gold: list[GoldEntity]
) -> list[tuple[EntityResult | None, GoldEntity | None]]:
    """Empareja predicción <-> gold por (tipo, nombre normalizado con
    contención). Greedy: cada entidad se usa como máximo una vez. Devuelve
    pares (pred, gold); uno de los dos es None cuando no hay contraparte."""
    remaining_pred = list(predicted)
    pairs: list[tuple[EntityResult | None, GoldEntity | None]] = []
    for g in gold:
        match = next(
            (p for p in remaining_pred if p.type == g.type and _names_match(p.name, g.name)),
            None,
        )
        if match is not None:
            remaining_pred.remove(match)
            pairs.append((match, g))
        else:
            pairs.append((None, g))
    for p in remaining_pred:
        pairs.append((p, None))
    return pairs


def _update_metrics(
    by_type: dict[str, EntityMetrics],
    overall: EntityMetrics,
    pairs: list[tuple[EntityResult | None, GoldEntity | None]],
    *,
    count_false_positives: bool,
) -> None:
    for pred, gold in pairs:
        etype = (gold or pred).type  # type: ignore[union-attr]
        m_type = by_type.setdefault(etype, EntityMetrics())
        if pred is not None and gold is not None:
            m_type.tp += 1
            overall.tp += 1
            if gold.sentiment_toward is not None:
                m_type.sentiment_total += 1
                overall.sentiment_total += 1
                if pred.sentiment_toward == gold.sentiment_toward:
                    m_type.sentiment_correct += 1
                    overall.sentiment_correct += 1
        elif pred is None and gold is not None:
            m_type.fn += 1
            overall.fn += 1
        elif pred is not None and gold is None and count_false_positives:
            m_type.fp += 1
            overall.fp += 1


# ── sentimiento global ───────────────────────────────────────────────────────


@dataclass
class ConfusionMatrix:
    counts: dict[tuple[str, str], int]  # (gold, predicho) -> n

    @classmethod
    def empty(cls) -> ConfusionMatrix:
        return cls(counts=dict.fromkeys(
            ((g, p) for g in SENTIMENT_VALUES for p in SENTIMENT_VALUES), 0
        ))

    def record(self, gold: str, predicted: str) -> None:
        key = (gold, predicted if predicted in SENTIMENT_VALUES else "NEU")
        self.counts[key] = self.counts.get(key, 0) + 1

    @property
    def accuracy(self) -> float | None:
        total = sum(self.counts.values())
        if not total:
            return None
        correct = sum(n for (g, p), n in self.counts.items() if g == p)
        return round(correct / total, 4)

    def render(self) -> str:
        header = "gold\\pred".ljust(10) + "".join(v.ljust(8) for v in SENTIMENT_VALUES)
        lines: list[str] = [header]
        for g in SENTIMENT_VALUES:
            row = g.ljust(10) + "".join(str(self.counts[(g, p)]).ljust(8) for p in SENTIMENT_VALUES)
            lines.append(row)
        return "\n".join(lines)


# ── orquestación ─────────────────────────────────────────────────────────────


def _build_analyzer(name: str) -> Analyzer:
    if name == "gemini":
        from analysis.gemini_analyzer import GeminiAnalyzer

        return GeminiAnalyzer()
    from analysis import LocalAnalyzer

    return LocalAnalyzer()


def evaluate(articles: list[GoldArticle], analyzer: Analyzer) -> dict[str, Any]:
    by_type: dict[str, EntityMetrics] = {}
    overall = EntityMetrics()
    sentiment_cm = ConfusionMatrix.empty()

    per_article: list[dict[str, Any]] = []
    for article in articles:
        result = analyzer.analyze(article.title, article.body)
        sentiment_cm.record(article.overall_sentiment, result.overall_sentiment or "NEU")

        pairs = _match_entities(result.entities, article.entities)
        _update_metrics(
            by_type, overall, pairs, count_false_positives=article.entities_exhaustive
        )
        per_article.append(
            {
                "id": article.id,
                "overall_sentiment": {"gold": article.overall_sentiment, "predicted": result.overall_sentiment},
                "entities_exhaustive": article.entities_exhaustive,
                "entity_pairs": len(pairs),
            }
        )

    return {
        "n_articles": len(articles),
        "entities": {
            "overall": overall,
            "by_type": by_type,
        },
        "overall_sentiment": sentiment_cm,
        "per_article": per_article,
    }


def _fmt(value: float | None) -> str:
    return f"{value:.1%}" if value is not None else "n/d"


def render_report(report: dict[str, Any], *, analyzer_name: str, golden_set: Path) -> str:
    lines = [
        f"Golden set: {golden_set} ({report['n_articles']} artículos)",
        f"Analizador: {analyzer_name}",
        "",
        "── Entidades (precision/recall/F1) ──────────────────────────",
    ]
    overall: EntityMetrics = report["entities"]["overall"]
    lines.append(
        f"  {'TOTAL':10s} P={_fmt(overall.precision):>7s}  R={_fmt(overall.recall):>7s}  "
        f"F1={_fmt(overall.f1):>7s}  (tp={overall.tp} fp={overall.fp} fn={overall.fn})"
    )
    for etype, m in sorted(report["entities"]["by_type"].items()):
        lines.append(
            f"  {etype:10s} P={_fmt(m.precision):>7s}  R={_fmt(m.recall):>7s}  "
            f"F1={_fmt(m.f1):>7s}  (tp={m.tp} fp={m.fp} fn={m.fn})"
        )
    lines.append(
        f"\n  sentiment_toward accuracy (sobre entidades emparejadas con gold "
        f"conocido): {_fmt(overall.sentiment_accuracy)} "
        f"({overall.sentiment_correct}/{overall.sentiment_total})"
    )
    lines.append("")
    lines.append("── Sentimiento global (matriz de confusión, filas=gold) ──────")
    lines.append(report["overall_sentiment"].render())
    lines.append(f"\n  accuracy: {_fmt(report['overall_sentiment'].accuracy)}")
    n_non_exhaustive = sum(1 for a in report["per_article"] if not a["entities_exhaustive"])
    if n_non_exhaustive:
        lines.append(
            f"\nNota: {n_non_exhaustive} artículo(s) con entities_exhaustive=false — "
            "sus falsos positivos NO se cuentan en precision (ver tests/eval/README.md)."
        )
    return "\n".join(lines)


def _report_to_json(report: dict[str, Any]) -> dict[str, Any]:
    def _metrics(m: EntityMetrics) -> dict[str, Any]:
        return {
            "tp": m.tp, "fp": m.fp, "fn": m.fn,
            "precision": m.precision, "recall": m.recall, "f1": m.f1,
            "sentiment_accuracy": m.sentiment_accuracy,
        }

    return {
        "n_articles": report["n_articles"],
        "entities": {
            "overall": _metrics(report["entities"]["overall"]),
            "by_type": {k: _metrics(v) for k, v in report["entities"]["by_type"].items()},
        },
        "overall_sentiment": {
            "accuracy": report["overall_sentiment"].accuracy,
            "confusion_matrix": {f"{g}->{p}": n for (g, p), n in report["overall_sentiment"].counts.items()},
        },
        "per_article": report["per_article"],
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument(
        "--golden-set",
        type=Path,
        default=Path(__file__).resolve().parent.parent / "tests" / "eval" / "golden_set.jsonl",
    )
    parser.add_argument(
        "--analyzer",
        choices=["local", "gemini"],
        default="local",
        help="'local' (gratis, por defecto) o 'gemini' (llamadas FACTURADAS, una por artículo).",
    )
    parser.add_argument("--out", type=Path, default=None, help="Escribir el reporte también como JSON.")
    args = parser.parse_args()

    if args.analyzer == "gemini":
        print(
            "AVISO: vas a correr el golden set con GeminiAnalyzer — una llamada "
            "FACTURADA por artículo. Ctrl+C en los próximos 5s para cancelar.",
            file=sys.stderr,
        )
        import time

        time.sleep(5)

    articles = load_golden_set(args.golden_set)
    if not articles:
        print(f"{args.golden_set}: golden set vacío.", file=sys.stderr)
        raise SystemExit(1)

    analyzer = _build_analyzer(args.analyzer)
    report = evaluate(articles, analyzer)
    print(render_report(report, analyzer_name=args.analyzer, golden_set=args.golden_set))

    if args.out:
        args.out.write_text(
            json.dumps(_report_to_json(report), ensure_ascii=False, indent=2), encoding="utf-8"
        )
        print(f"\nReporte JSON escrito en {args.out}")


if __name__ == "__main__":
    main()
