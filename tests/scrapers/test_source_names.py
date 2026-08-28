"""Nombre legible del medio a partir del slug que se guarda en `articles.source`."""
from odin.scrapers import source_name


class TestSourceName:
    def test_resolves_registered_source_to_its_display_name(self):
        assert source_name("listin_diario") == "Listín Diario"

    def test_keeps_accents_and_casing_of_the_scraper_name(self):
        assert source_name("el_dia") == "El Día"

    def test_unregistered_slug_falls_back_to_a_readable_form(self):
        # Un reporte cargado a mano, o un scraper retirado del registro: vale
        # más "Diario X" que el slug crudo en pantalla.
        assert source_name("diario_x") == "Diario X"

    def test_empty_source_returns_empty(self):
        assert source_name("") == ""
