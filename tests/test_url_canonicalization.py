"""Pruebas de `url_guard.canonical_url`: la forma con la que se compara una
URL contra lo ya analizado o guardado.

Importa que sea conservadora en las dos direcciones: si normaliza de menos, la
misma nota se analiza dos veces (dos llamadas al LLM y dos filas en
`articles`); si normaliza de más, dos notas distintas se confunden en una.
"""
from __future__ import annotations

import pytest

from url_guard import canonical_url

MISMA_NOTA = "https://listindiario.com/politica/20260807/nota-de-prueba"


@pytest.mark.parametrize(
    "variante",
    [
        MISMA_NOTA,
        MISMA_NOTA + "/",
        MISMA_NOTA + "#comentarios",
        MISMA_NOTA + "?utm_source=whatsapp&utm_medium=social",
        MISMA_NOTA + "?fbclid=IwAR123",
        MISMA_NOTA + "/?utm_campaign=x#top",
        "https://LISTINDIARIO.com/politica/20260807/nota-de-prueba",
        "HTTPS://listindiario.com/politica/20260807/nota-de-prueba",
    ],
)
def test_variants_of_the_same_link_collapse(variante):
    assert canonical_url(variante) == canonical_url(MISMA_NOTA)


class TestKeepsWhatChangesTheContent:
    def test_query_params_that_select_the_article_are_kept(self):
        # Hay medios que sirven la nota por id: quitar el query apuntaría a
        # otra página, no a la misma.
        assert "id=1234" in canonical_url("https://hoy.com.do/articulo?id=1234")

    def test_different_articles_stay_different(self):
        assert canonical_url("https://hoy.com.do/a?id=1") != canonical_url(
            "https://hoy.com.do/a?id=2"
        )

    def test_query_order_does_not_matter(self):
        assert canonical_url("https://hoy.com.do/a?b=2&a=1") == canonical_url(
            "https://hoy.com.do/a?a=1&b=2"
        )

    def test_path_case_is_preserved(self):
        # El dominio no distingue mayúsculas, la ruta sí.
        assert canonical_url("https://hoy.com.do/Nota") != canonical_url("https://hoy.com.do/nota")

    def test_root_path_survives(self):
        assert canonical_url("https://hoy.com.do/") == "https://hoy.com.do/"
