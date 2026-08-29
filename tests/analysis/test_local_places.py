"""Extracción de lugares (entidades LOC de spaCy) en LocalAnalyzer.

Usa el modelo real por la misma razón que test_local_analyzer.py: las reglas
dependen de cómo spaCy segmenta y etiqueta, y mockearlo probaría el mock.

El caso de referencia es el artículo 68 del corpus ("Puente entre Hato Nuevo
y Quita Sueño"): tiene los cuatro modos de falla juntos —span pegado por la
conjunción, span que cruza un salto de línea, accidente geográfico, y
sectores que no están en el catálogo—. El fixture es el texto tal como quedó
guardado, con el titular repetido al inicio del cuerpo y todo: si se limpia
para que el test se vea bonito, deja de medir lo que el analizador recibe.
"""
from __future__ import annotations

from pathlib import Path

import pytest

pytest.importorskip("spacy")

from odin.analysis.local_analyzer import LocalAnalyzer, _norm_key

FIXTURE = Path(__file__).parent / "fixtures" / "articulo_68_puente.txt"


@pytest.fixture(scope="module")
def analyzer():
    try:
        a = LocalAnalyzer()
        a.nlp  # noqa: B018 (la propiedad es la que carga el modelo, acá y no en un test)
    except Exception:
        pytest.skip("modelo es_core_news_lg no instalado")
    return a


@pytest.fixture(scope="module")
def places_68(analyzer):
    lines = FIXTURE.read_text(encoding="utf-8").strip().split("\n")
    title, body = lines[0], "\n".join(lines[1:])
    doc = analyzer.nlp(f"{title}.\n\n{body}".strip())
    return analyzer._places(doc)


def _keys(places):
    return {_norm_key(p.name) for p in places}


def test_separa_lugares_pegados_por_la_conjuncion(places_68):
    """spaCy devuelve 'Hato Nuevo y Quita Sueño' como UN span."""
    keys = _keys(places_68)
    assert "hato nuevo" in keys
    assert "quita sueno" in keys
    assert not any(" y " in p.name for p in places_68)


def test_descarta_accidentes_geograficos(places_68):
    """'río Haina' es un río, no una localidad."""
    assert "rio haina" not in _keys(places_68)


def test_descarta_spans_que_cruzan_salto_de_linea(places_68):
    """'Haina\\nPuente' y 'Haina\\nResidentes' son basura de segmentación."""
    assert all("\n" not in p.name for p in places_68)
    assert "haina puente" not in _keys(places_68)


def test_encuentra_los_municipios_del_catalogo(places_68):
    keys = _keys(places_68)
    assert "santo domingo oeste" in keys
    assert "haina" in keys


def test_lugar_del_titular_se_marca_como_hecho(places_68):
    """Hato Nuevo y Quita Sueño están en el titular: ahí ocurre el hecho."""
    by_key = {_norm_key(p.name): p for p in places_68}
    assert by_key["quita sueno"].kind == "HECHO"
    assert by_key["quita sueno"].in_title is True
    assert by_key["quita sueno"].confidence >= 0.7


def test_lugar_de_enumeracion_final_es_solo_mencionado(places_68):
    """'Batey Bienvenido' aparece una vez, en la lista del cierre."""
    by_key = {_norm_key(p.name): p for p in places_68}
    assert by_key["batey bienvenido"].kind == "MENCIONADO"
    assert by_key["batey bienvenido"].confidence < 0.7


def test_orden_por_confianza_descendente(places_68):
    scores = [p.confidence for p in places_68]
    assert scores == sorted(scores, reverse=True)


class TestExtractPlaces:
    """`extract_places` es el camino que usan los motores LLM.

    Los lugares salen del NER de spaCy, no de entender el texto: da igual
    quién haya leído el artículo. Sin esto la detección solo funcionaba con
    ODIN_ANALYZER=local, que no es como corre el sistema en la práctica.
    """

    def test_devuelve_lo_mismo_que_el_analisis_completo(self, analyzer):
        lines = FIXTURE.read_text(encoding="utf-8").strip().split("\n")
        title, body = lines[0], "\n".join(lines[1:])

        doc = analyzer.nlp(f"{title}.\n\n{body}".strip())
        esperado = [(p.name, p.kind, p.confidence) for p in analyzer._places(doc)]
        obtenido = [
            (p.name, p.kind, p.confidence) for p in analyzer.extract_places(title, body)
        ]

        assert obtenido == esperado

    def test_no_toca_pysentimiento(self, analyzer):
        """Correr el modelo de sentimiento para tirarlo sería ~60% del tiempo.

        Se verifica sobre una instancia nueva: si `extract_places` lo cargara,
        `_sent` dejaría de ser None.
        """
        fresco = LocalAnalyzer()
        fresco.extract_places("Acueducto en San Juan", "La obra se inauguró hoy.")

        assert fresco._sent is None

    def test_encuentra_el_lugar_del_titular(self, analyzer):
        """El caso que reportó el usuario: 'San Juan' en titular y cuerpo."""
        places = analyzer.extract_places(
            "Fundación Popular inaugura acueducto en San Juan",
            "La obra beneficia a familias de San Juan. El acueducto ya opera.",
        )
        por_nombre = {p.name: p for p in places}

        assert "San Juan" in por_nombre
        assert por_nombre["San Juan"].kind == "HECHO"


class TestPrefijoAdministrativo:
    """La prensa alterna "San Juan" y "provincia San Juan" en la misma nota.

    Sin quitar el prefijo son dos candidatos distintos: el conteo del lugar
    queda partido y una de las dos formas ni siquiera resuelve contra el
    catálogo, porque el nodo se llama "San Juan" a secas.
    """

    def test_colapsa_el_prefijo_sobre_el_mismo_lugar(self, analyzer):
        places = analyzer.extract_places(
            "Acueducto en San Juan",
            "La obra está en la provincia San Juan. San Juan la esperaba hace años.",
        )
        nombres = [p.name for p in places]

        assert "San Juan" in nombres
        assert not any(n.lower().startswith("provincia ") for n in nombres)

    def test_no_recorta_cuando_el_prefijo_es_parte_del_nombre(self, analyzer):
        """"Villa González" o "Villa Altagracia" son municipios de verdad."""
        from odin.analysis.local_analyzer import _strip_admin_prefix

        assert _strip_admin_prefix("Villa González") == "Villa González"
        assert _strip_admin_prefix("provincia San Juan") == "San Juan"
        assert _strip_admin_prefix("municipio de Bajos de Haina") == "Bajos de Haina"
        assert _strip_admin_prefix("provincia") == "provincia"


FIXTURE_71 = Path(__file__).parent / "fixtures" / "articulo_71_pedro_brand.txt"


class TestLugaresEtiquetadosComoPersona:
    """spaCy marca "Pedro Brand" como PER: "Pedro" es nombre de pila.

    Es el espejo del problema que ya resuelve `_DOMINICAN_PROVINCES` —ahí
    spaCy etiqueta provincias como PERSON y hay que descartarlas de las
    entidades—. Acá hay que RECUPERARLAS como lugar, y la señal que lo permite
    sin abrir la puerta a cualquier nombre propio es la palabra que las
    antecede: a una persona nadie la presenta como "el municipio de".
    """

    @pytest.fixture(scope="class")
    def places_71(self, analyzer):
        lines = FIXTURE_71.read_text(encoding="utf-8").strip().split("\n")
        title, body = lines[0], "\n".join(lines[1:])
        return analyzer.extract_places(title, body)

    def test_recupera_el_municipio_pese_a_la_etiqueta_person(self, places_71):
        """Aparece como "el municipio de Pedro Brand" en el cuerpo."""
        assert "Pedro Brand" in {p.name for p in places_71}

    def test_cuenta_todas_las_menciones_no_solo_la_que_trae_la_señal(self, places_71):
        """La señal aparece una vez, pero el lugar se nombra tres.

        Si solo contara la mención con "municipio de", el titular no pesaría y
        el lugar caería a MENCIONADO — que es justo lo contrario de lo que
        dice el artículo.
        """
        pedro = next(p for p in places_71 if p.name == "Pedro Brand")

        assert pedro.mentions_count >= 3
        assert pedro.in_title is True
        assert pedro.kind == "HECHO"

    def test_no_confunde_a_una_persona_con_un_lugar(self, places_71):
        """"al alcalde Ramón Pascual Gómez": el cargo no es una unidad admin."""
        assert "Ramón Pascual Gómez" not in {p.name for p in places_71}

    def test_no_toma_la_via_que_lleva_el_nombre_de_una_provincia(self, places_71):
        """"a la autopista Duarte" — Duarte es provincia, pero acá es una vía."""
        assert "Duarte" not in {p.name for p in places_71}
