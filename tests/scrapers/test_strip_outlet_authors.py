"""El medio no es un autor.

Trafilatura devuelve el campo `author` tal como lo publica el sitio, y varios
medios se listan a sí mismos ahí: "Listin Diario; Ashley Martínez". Guardarlo
entero convierte al medio en periodista, y R15 pide al periodista como
dimensión propia — con el medio adentro, esa dimensión queda contaminada.
"""
from __future__ import annotations

import pytest

from odin.scrapers import strip_outlet_from_authors


class TestRemovesTheOutlet:
    def test_drops_the_outlet_and_keeps_the_journalist(self):
        assert (
            strip_outlet_from_authors("Listin Diario; Ashley Martínez", "listin_diario")
            == "Ashley Martínez"
        )

    def test_ignores_accents_when_matching(self):
        """El sitio escribe "Listin" sin tilde; el registro, "Listín"."""
        assert (
            strip_outlet_from_authors("Listín Diario; Ashley Martínez", "listin_diario")
            == "Ashley Martínez"
        )

    def test_ignores_capitalisation_and_spacing(self):
        assert (
            strip_outlet_from_authors("  LISTIN   DIARIO ; Ashley Martínez", "listin_diario")
            == "Ashley Martínez"
        )

    def test_also_recognises_the_slug_itself(self):
        assert strip_outlet_from_authors("listin_diario; Ashley Martínez", "listin_diario") == "Ashley Martínez"

    def test_keeps_several_journalists(self):
        assert (
            strip_outlet_from_authors("Diario Libre; Ana Ruiz; Luis Paz", "diario_libre")
            == "Ana Ruiz; Luis Paz"
        )

    def test_removes_the_outlet_wherever_it_sits(self):
        assert (
            strip_outlet_from_authors("Ashley Martínez; Listin Diario", "listin_diario")
            == "Ashley Martínez"
        )


class TestLeavesEverythingElseAlone:
    def test_keeps_an_author_that_merely_contains_the_word(self):
        """"Diario" suelto no es el medio: solo se quita la coincidencia exacta."""
        assert strip_outlet_from_authors("Juan Diario", "listin_diario") == "Juan Diario"

    def test_returns_none_when_only_the_outlet_was_listed(self):
        assert strip_outlet_from_authors("Listin Diario", "listin_diario") is None

    @pytest.mark.parametrize("authors", [None, "", "   "])
    def test_handles_an_empty_field(self, authors):
        assert strip_outlet_from_authors(authors, "listin_diario") is None

    def test_leaves_authors_untouched_for_an_unknown_outlet(self):
        assert strip_outlet_from_authors("El País; Ana Ruiz", "manual") == "El País; Ana Ruiz"


class TestOutletDisguisedAsDomain:
    """Algunos sitios ponen su dominio en el campo autor, con formato de nombre.

    Salió de una reparación real: "Eldia Com Do; El Día" perdía "El Día" y
    conservaba "Eldia Com Do", que es el mismo medio escrito de otra forma.
    """

    def test_recognises_the_domain_written_as_words(self):
        assert strip_outlet_from_authors("Eldia Com Do; El Día", "el_dia") is None

    def test_recognises_the_bare_domain(self):
        assert strip_outlet_from_authors("eldia.com.do; Ana Ruiz", "el_dia") == "Ana Ruiz"

    def test_still_keeps_a_real_person(self):
        assert (
            strip_outlet_from_authors("Eldia Com Do; Ana Ruiz", "el_dia") == "Ana Ruiz"
        )
