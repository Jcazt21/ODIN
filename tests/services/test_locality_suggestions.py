"""Candidatos crudos del analizador -> nodos reales del catálogo.

Es la frontera entre el extractor (que no sabe de base de datos) y el
catálogo administrable. Lo que NO resuelve se descarta en silencio: los
sectores y distritos municipales no están en el catálogo, y proponer un
lugar inexistente sería peor que no proponer nada.
"""
from __future__ import annotations

import pytest

from odin.analysis.base import PlaceResult
from odin.db.localities import seed_localities
from odin.services.locality_service import suggest_from_places


@pytest.fixture
def session_con_catalogo(db_session):
    """Sesión SQLite (fixture `db_session` de tests/conftest.py) con el
    catálogo real ya sembrado: estos tests miden la resolución contra los
    nombres y alias de verdad, no contra un catálogo de juguete."""
    seed_localities(db_session)
    return db_session


def test_resuelve_por_alias(session_con_catalogo):
    places = [PlaceResult(name="Haina", mentions_count=2, kind="HECHO", confidence=0.9)]
    out = suggest_from_places(session_con_catalogo, places)
    assert len(out) == 1
    assert out[0].name == "Bajos de Haina"
    assert out[0].level == "MUNICIPIO"
    assert out[0].kind == "HECHO"
    assert out[0].origin == "AUTO"
    assert out[0].confidence == 0.9
    assert out[0].matched_text == "Haina"


def test_descarta_lo_que_no_esta_en_el_catalogo(session_con_catalogo):
    """Quita Sueño es un distrito municipal: el catálogo tiene piso en municipio."""
    places = [PlaceResult(name="Quita Sueño"), PlaceResult(name="Batey Bienvenido")]
    assert suggest_from_places(session_con_catalogo, places) == []


def test_deduplica_cuando_dos_candidatos_caen_en_el_mismo_nodo(session_con_catalogo):
    """"Haina" y "Bajos de Haina" son el mismo municipio: una sola sugerencia."""
    places = [
        PlaceResult(name="Haina", kind="HECHO", confidence=0.9),
        PlaceResult(name="Bajos de Haina", kind="MENCIONADO", confidence=0.4),
    ]
    out = suggest_from_places(session_con_catalogo, places)
    assert len(out) == 1
    assert out[0].confidence == 0.9  # gana el candidato más confiable


def test_trae_el_camino_completo(session_con_catalogo):
    out = suggest_from_places(
        session_con_catalogo, [PlaceResult(name="Santo Domingo Oeste")]
    )
    names = [c.name for c in out[0].breadcrumb]
    assert names[0] == "República Dominicana"
    assert names[-1] == "Santo Domingo Oeste"


def test_respeta_el_limite(session_con_catalogo):
    places = [PlaceResult(name=n, confidence=c) for n, c in [
        ("Santiago", 0.9), ("Azua", 0.8), ("Barahona", 0.7),
        ("Samaná", 0.6), ("Mao", 0.5), ("Higüey", 0.4),
    ]]
    out = suggest_from_places(session_con_catalogo, places, limit=5)
    assert len(out) == 5
    assert out[0].name == "Santiago"  # el de mayor confianza sobrevive


def test_no_usa_coincidencia_difusa(session_con_catalogo):
    """"Hato Nuevo" está a UNA edición de "Hato Mayor", provincia real a 100 km.

    Un match difuso mandaría la noticia a la otra punta del país con confianza
    alta, que es peor que no sugerir nada.
    """
    out = suggest_from_places(session_con_catalogo, [PlaceResult(name="Hato Nuevo")])
    assert out == []
