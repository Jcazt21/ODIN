"""Pruebas de scripts/evaluate.py: emparejamiento de entidades, agregación de
métricas y parseo del golden set. Sin cargar spaCy/pysentimiento — se prueba
la lógica de evaluación con un analizador de mentira (stub)."""
from __future__ import annotations

from pathlib import Path

from odin.analysis.base import AnalysisResult, EntityResult
from scripts.evaluate import (
    SENTIMENT_VALUES,
    ConfusionMatrix,
    EntityMetrics,
    GoldArticle,
    GoldEntity,
    _match_entities,
    _names_match,
    _update_metrics,
    evaluate,
    load_golden_set,
)

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
GOLDEN_SET_PATH = REPO_ROOT / "tests" / "eval" / "golden_set.jsonl"


class _StubAnalyzer:
    """Devuelve resultados fijos por título, para probar `evaluate()` sin
    cargar ningún modelo real."""

    def __init__(self, by_title: dict[str, AnalysisResult]):
        self._by_title = by_title

    def analyze(self, title: str, body: str) -> AnalysisResult:
        return self._by_title[title]


# ── _names_match ──────────────────────────────────────────────────────────────


class TestNamesMatch:
    def test_exact_match_case_and_accent_insensitive(self):
        assert _names_match("Policía Nacional", "POLICIA NACIONAL")

    def test_matches_by_word_containment_either_direction(self):
        assert _names_match("Abinader", "Luis Abinader")
        assert _names_match("Luis Abinader", "Abinader")

    def test_does_not_match_unrelated_names(self):
        assert not _names_match("Luis Abinader", "Leonel Fernández")

    def test_empty_names_never_match(self):
        assert not _names_match("", "algo")
        assert not _names_match("algo", "")

    def test_hyphen_and_period_normalized_like_canonicalize(self):
        # Antes del fix: la copia local de _norm_key no quitaba "-"/"."
        # (a diferencia de analysis/text_norm.norm_key), así que este caso
        # fallaba pese a que canonicalize.py sí los trata como iguales.
        assert _names_match("P.R.M.", "PRM")
        assert _names_match("Jean-Claude", "Jean Claude")


# ── _match_entities / _update_metrics ────────────────────────────────────────


class TestMatchEntitiesAndMetrics:
    def test_exact_match_counts_as_true_positive(self):
        predicted = [EntityResult(name="Luis Abinader", type="PERSON", sentiment_toward="POS")]
        gold = [GoldEntity(name="Luis Abinader", type="PERSON", sentiment_toward="POS")]
        pairs = _match_entities(predicted, gold)

        by_type: dict[str, EntityMetrics] = {}
        overall = EntityMetrics()
        _update_metrics(by_type, overall, pairs, count_false_positives=True)

        assert overall.tp == 1
        assert overall.fp == 0
        assert overall.fn == 0
        assert overall.sentiment_correct == 1
        assert overall.sentiment_total == 1

    def test_missing_gold_entity_is_false_negative(self):
        predicted: list[EntityResult] = []
        gold = [GoldEntity(name="Luis Abinader", type="PERSON", sentiment_toward=None)]
        pairs = _match_entities(predicted, gold)

        by_type: dict[str, EntityMetrics] = {}
        overall = EntityMetrics()
        _update_metrics(by_type, overall, pairs, count_false_positives=True)

        assert overall.fn == 1
        assert overall.tp == 0

    def test_extra_predicted_entity_is_false_positive_when_exhaustive(self):
        predicted = [EntityResult(name="Entidad Inventada", type="ORG")]
        gold: list[GoldEntity] = []
        pairs = _match_entities(predicted, gold)

        by_type: dict[str, EntityMetrics] = {}
        overall = EntityMetrics()
        _update_metrics(by_type, overall, pairs, count_false_positives=True)

        assert overall.fp == 1

    def test_extra_predicted_entity_ignored_when_not_exhaustive(self):
        predicted = [EntityResult(name="Entidad Inventada", type="ORG")]
        gold: list[GoldEntity] = []
        pairs = _match_entities(predicted, gold)

        by_type: dict[str, EntityMetrics] = {}
        overall = EntityMetrics()
        _update_metrics(by_type, overall, pairs, count_false_positives=False)

        assert overall.fp == 0

    def test_different_types_do_not_match_even_with_same_name(self):
        predicted = [EntityResult(name="Salud", type="ORG")]
        gold = [GoldEntity(name="Salud", type="PERSON", sentiment_toward=None)]
        pairs = _match_entities(predicted, gold)

        by_type: dict[str, EntityMetrics] = {}
        overall = EntityMetrics()
        _update_metrics(by_type, overall, pairs, count_false_positives=True)

        assert overall.tp == 0
        assert overall.fn == 1  # el gold PERSON no encontró contraparte
        assert overall.fp == 1  # el predicho ORG tampoco encontró contraparte

    def test_sentiment_accuracy_only_counts_matched_pairs_with_known_gold(self):
        predicted = [
            EntityResult(name="A", type="ORG", sentiment_toward="POS"),
            EntityResult(name="B", type="ORG", sentiment_toward="NEG"),
        ]
        gold = [
            GoldEntity(name="A", type="ORG", sentiment_toward="POS"),  # correcto
            GoldEntity(name="B", type="ORG", sentiment_toward=None),   # sin gold de sentimiento
        ]
        pairs = _match_entities(predicted, gold)
        by_type: dict[str, EntityMetrics] = {}
        overall = EntityMetrics()
        _update_metrics(by_type, overall, pairs, count_false_positives=True)

        assert overall.tp == 2
        assert overall.sentiment_total == 1  # solo "A" tenía gold de sentimiento
        assert overall.sentiment_correct == 1

    def test_end_to_end_sentiment_counts_unextracted_labeled_entities_as_failures(self):
        """`sentiment_accuracy` es condicional a haber detectado la entidad, así
        que su denominador se mueve cuando cambia la extracción — por eso el
        "59.9% -> 59.5%" entre las líneas base de 2026-08-13 y 2026-08-14 se
        leyó como regresión sin serlo. `sentiment_accuracy_e2e` cuenta la
        entidad etiquetada que nunca se extrajo como fallo, y su denominador
        no depende del recall."""
        predicted = [EntityResult(name="A", type="ORG", sentiment_toward="POS")]
        gold = [
            GoldEntity(name="A", type="ORG", sentiment_toward="POS"),  # extraída y correcta
            GoldEntity(name="B", type="ORG", sentiment_toward="NEG"),  # nunca extraída
        ]
        pairs = _match_entities(predicted, gold)
        by_type: dict[str, EntityMetrics] = {}
        overall = EntityMetrics()
        _update_metrics(by_type, overall, pairs, count_false_positives=True)

        assert overall.sentiment_total == 1
        assert overall.sentiment_correct == 1
        assert overall.sentiment_missed == 1
        assert overall.sentiment_accuracy == 1.0      # condicional: 1/1
        assert overall.sentiment_accuracy_e2e == 0.5  # end-to-end: 1/2

    def test_unextracted_entity_without_gold_sentiment_is_not_counted_as_missed(self):
        predicted: list[EntityResult] = []
        gold = [GoldEntity(name="A", type="ORG", sentiment_toward=None)]
        pairs = _match_entities(predicted, gold)
        overall = EntityMetrics()
        _update_metrics({}, overall, pairs, count_false_positives=True)

        assert overall.fn == 1
        assert overall.sentiment_missed == 0  # no había juicio que acertar
        assert overall.sentiment_accuracy_e2e is None

    def test_polar_precision_ignores_neutral_predictions(self):
        """Solo POS/NEG afirman algo sobre la entidad; NEU no puede ser un
        juicio falso. La precisión polar mide exactamente eso."""
        predicted = [
            EntityResult(name="A", type="ORG", sentiment_toward="NEG"),  # polar, acierta
            EntityResult(name="B", type="ORG", sentiment_toward="NEG"),  # polar, falla
            EntityResult(name="C", type="ORG", sentiment_toward="NEU"),  # no polar
        ]
        gold = [
            GoldEntity(name="A", type="ORG", sentiment_toward="NEG"),
            GoldEntity(name="B", type="ORG", sentiment_toward="NEU"),
            GoldEntity(name="C", type="ORG", sentiment_toward="NEU"),
        ]
        pairs = _match_entities(predicted, gold)
        overall = EntityMetrics()
        _update_metrics({}, overall, pairs, count_false_positives=True)

        assert overall.sentiment_polar_predicted == 2
        assert overall.sentiment_polar_correct == 1
        assert overall.sentiment_polar_precision == 0.5
        assert overall.sentiment_accuracy == round(2 / 3, 4)  # A y C aciertan


class TestEntityMetricsProperties:
    def test_precision_recall_f1_none_when_no_data(self):
        m = EntityMetrics()
        assert m.precision is None
        assert m.recall is None
        assert m.f1 is None
        assert m.sentiment_accuracy is None

    def test_computes_precision_recall_f1(self):
        m = EntityMetrics(tp=8, fp=2, fn=2)
        assert m.precision == 0.8
        assert m.recall == 0.8
        assert m.f1 == 0.8


# ── ConfusionMatrix ───────────────────────────────────────────────────────────


class TestConfusionMatrix:
    def test_accuracy_and_recording(self):
        cm = ConfusionMatrix.empty(SENTIMENT_VALUES, fallback="NEU")
        cm.record("POS", "POS")
        cm.record("NEG", "NEU")
        cm.record("NEU", "NEU")
        assert cm.accuracy == round(2 / 3, 4)

    def test_unrecognized_prediction_falls_back_to_neu_bucket(self):
        cm = ConfusionMatrix.empty(SENTIMENT_VALUES, fallback="NEU")
        cm.record("POS", "algo-raro")
        assert cm.counts[("POS", "NEU")] == 1

    def test_empty_matrix_accuracy_is_none(self):
        assert ConfusionMatrix.empty(SENTIMENT_VALUES, fallback="NEU").accuracy is None

    def test_arbitrary_categories_and_custom_fallback(self):
        cm = ConfusionMatrix.empty(("critica", "favorable", "neutra"), fallback="neutra")
        cm.record("critica", "critica")
        cm.record("favorable", "algo-desconocido")
        assert cm.accuracy == 0.5
        assert cm.counts[("favorable", "neutra")] == 1

    def test_none_prediction_falls_back(self):
        cm = ConfusionMatrix.empty(("a", "b"), fallback="a")
        cm.record("b", None)
        assert cm.counts[("b", "a")] == 1


# ── load_golden_set ───────────────────────────────────────────────────────────


class TestLoadGoldenSet:
    def test_loads_from_tmp_jsonl(self, tmp_path):
        path = tmp_path / "mini.jsonl"
        path.write_text(
            '{"id": "x1", "title": "T", "body": "B", "overall_sentiment": "NEU", '
            '"entities": [{"name": "A", "type": "ORG", "sentiment_toward": "NEU"}]}\n'
            "\n"  # línea vacía: debe ignorarse
            '{"id": "x2", "title": "T2", "body": "B2", "overall_sentiment": "POS", '
            '"entities_exhaustive": false, "entities": []}\n',
            encoding="utf-8",
        )
        articles = load_golden_set(path)
        assert len(articles) == 2
        assert articles[0].entities_exhaustive is True  # default
        assert articles[1].entities_exhaustive is False
        assert articles[0].entities[0].name == "A"

    def test_real_golden_set_file_parses_and_matches_schema(self):
        articles = load_golden_set(GOLDEN_SET_PATH)
        assert len(articles) >= 1
        for article in articles:
            assert article.id
            assert article.title
            assert article.body
            assert article.overall_sentiment in ("POS", "NEG", "NEU")
            for ent in article.entities:
                assert ent.type in ("PERSON", "ORG")
                assert ent.sentiment_toward in ("POS", "NEG", "NEU", None)

    def test_new_optional_fields_default_to_none_when_absent(self):
        articles = load_golden_set(GOLDEN_SET_PATH)
        # las 7 filas originales no etiquetan los campos nuevos
        assert articles[0].framing is None
        assert articles[0].content_flags is None

    def test_loads_new_optional_fields_when_present(self, tmp_path):
        path = tmp_path / "mini.jsonl"
        path.write_text(
            '{"id": "x1", "title": "T", "body": "B", "overall_sentiment": "NEU", '
            '"entities": [], "framing": "denuncia", "sentiment_basis": "mixto", '
            '"facts_sentiment": "NEU", "quoted_sentiment": "NEG", '
            '"media_stance": "critica", "content_flags": ["alarmismo"]}\n',
            encoding="utf-8",
        )
        articles = load_golden_set(path)
        a = articles[0]
        assert a.framing == "denuncia"
        assert a.sentiment_basis == "mixto"
        assert a.facts_sentiment == "NEU"
        assert a.quoted_sentiment == "NEG"
        assert a.media_stance == "critica"
        assert a.content_flags == ["alarmismo"]


# ── evaluate() end-to-end con analizador de mentira ──────────────────────────


class TestEvaluateEndToEnd:
    def test_perfect_predictions_yield_full_scores(self):
        articles = [
            GoldArticle(
                id="a1",
                title="T1",
                body="B1",
                overall_sentiment="POS",
                entities_exhaustive=True,
                entities=[GoldEntity(name="Acme", type="ORG", sentiment_toward="POS")],
            ),
        ]
        stub = _StubAnalyzer({
            "T1": AnalysisResult(
                overall_sentiment="POS",
                entities=[EntityResult(name="Acme", type="ORG", sentiment_toward="POS")],
            ),
        })
        report = evaluate(articles, stub)
        overall = report["entities"]["overall"]
        assert overall.precision == 1.0
        assert overall.recall == 1.0
        assert report["overall_sentiment"].accuracy == 1.0

    def test_wrong_predictions_are_reflected_in_metrics(self):
        articles = [
            GoldArticle(
                id="a1",
                title="T1",
                body="B1",
                overall_sentiment="NEG",
                entities_exhaustive=True,
                entities=[GoldEntity(name="Acme", type="ORG", sentiment_toward="NEG")],
            ),
        ]
        stub = _StubAnalyzer({
            "T1": AnalysisResult(overall_sentiment="NEU", entities=[]),
        })
        report = evaluate(articles, stub)
        overall = report["entities"]["overall"]
        assert overall.fn == 1
        assert overall.tp == 0
        assert report["overall_sentiment"].accuracy == 0.0


# ── métricas de campos categóricos v2 (framing, media_stance, ...) ──────────


class TestCategoryMetrics:
    def test_category_field_scored_only_when_gold_present(self):
        articles = [
            GoldArticle(
                id="a1", title="T1", body="B1", overall_sentiment="NEU",
                entities_exhaustive=True, entities=[],
                framing="denuncia",
            ),
            GoldArticle(
                id="a2", title="T2", body="B2", overall_sentiment="NEU",
                entities_exhaustive=True, entities=[],
                framing=None,  # sin etiquetar: no debe contar
            ),
        ]
        stub = _StubAnalyzer({
            "T1": AnalysisResult(overall_sentiment="NEU", framing="denuncia"),
            "T2": AnalysisResult(overall_sentiment="NEU", framing="crecimiento"),
        })
        report = evaluate(articles, stub)
        framing_matrix = report["category_matrices"]["framing"]
        assert sum(framing_matrix.counts.values()) == 1
        assert framing_matrix.accuracy == 1.0

    def test_missing_or_unrecognized_prediction_falls_back(self):
        articles = [
            GoldArticle(
                id="a1", title="T1", body="B1", overall_sentiment="NEU",
                entities_exhaustive=True, entities=[],
                media_stance="critica",
            ),
        ]
        stub = _StubAnalyzer({
            "T1": AnalysisResult(overall_sentiment="NEU", media_stance=None),
        })
        report = evaluate(articles, stub)
        matrix = report["category_matrices"]["media_stance"]
        assert matrix.counts[("critica", "neutra_transmisiva")] == 1


# ── content_flags (multi-etiqueta) ───────────────────────────────────────────


class TestFlagMetrics:
    def test_flags_precision_recall(self):
        articles = [
            GoldArticle(
                id="a1", title="T1", body="B1", overall_sentiment="NEU",
                entities_exhaustive=True, entities=[],
                content_flags=["alarmismo", "sensacionalismo"],
            ),
        ]
        stub = _StubAnalyzer({
            "T1": AnalysisResult(
                overall_sentiment="NEU",
                content_flags=["alarmismo", "posible_ironia"],
            ),
        })
        report = evaluate(articles, stub)
        flags = report["content_flags"]
        assert flags.tp == 1  # alarmismo
        assert flags.fp == 1  # posible_ironia
        assert flags.fn == 1  # sensacionalismo

    def test_flags_skipped_when_article_not_labeled(self):
        articles = [
            GoldArticle(
                id="a1", title="T1", body="B1", overall_sentiment="NEU",
                entities_exhaustive=True, entities=[],
                content_flags=None,
            ),
        ]
        stub = _StubAnalyzer({
            "T1": AnalysisResult(overall_sentiment="NEU", content_flags=["alarmismo"]),
        })
        report = evaluate(articles, stub)
        flags = report["content_flags"]
        assert flags.tp == 0 and flags.fp == 0 and flags.fn == 0
