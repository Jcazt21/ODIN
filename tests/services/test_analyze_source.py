"""El medio de una nota analizada por URL sale del dominio.

Antes salía del `sitename` que detectara trafilatura y, si no detectaba nada,
quedaba "manual". Eso metía valores que no son medios en `articles.source`, que
es la dimensión por la que el cliente filtra (R14): una nota de Listín Diario
aparecía bajo "Manual" en el desplegable de medios.
"""
from __future__ import annotations

import pytest

from odin.services.analyze_service import resolve_source


class TestResolveSource:
    def test_a_known_domain_wins_over_whatever_was_extracted(self):
        """El dominio es un dato duro; el `sitename` es una heurística."""
        assert resolve_source("https://listindiario.com/x", "Listin Diario Digital") == "listin_diario"

    def test_uses_the_domain_when_nothing_was_extracted(self):
        assert resolve_source("https://www.diariolibre.com/x", None) == "diario_libre"

    @pytest.mark.parametrize("extracted", ["El País", "  El País  "])
    def test_falls_back_to_the_extracted_name_for_an_unknown_outlet(self, extracted):
        """Un medio que no rastreamos conserva lo que se pudo extraer: es más
        informativo que "manual", aunque no sea una clave del registro."""
        assert resolve_source("https://elpais.com/x", extracted) == "El País"

    def test_last_resort_is_manual(self):
        assert resolve_source("https://elpais.com/x", None) == "manual"

    def test_a_blank_extraction_is_not_a_name(self):
        assert resolve_source("https://elpais.com/x", "   ") == "manual"
