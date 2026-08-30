"""Medio deducido del dominio de la URL.

Al analizar por URL el medio salía de lo que detectara trafilatura, y si no
detectaba nada caía a "manual". Eso llenaba `articles.source` —la dimensión que
el cliente pide para filtrar (R14)— de valores que no son medios. El dominio,
en cambio, es un dato duro que ya está en la URL.
"""
from __future__ import annotations

import pytest

from odin.scrapers import SCRAPERS, source_from_url


class TestKnownOutlets:
    @pytest.mark.parametrize(
        ("url", "expected"),
        [
            ("https://listindiario.com/las-sociales/20260828/nota.html", "listin_diario"),
            ("https://www.listindiario.com/nota", "listin_diario"),
            ("https://www.diariolibre.com/actualidad/nota", "diario_libre"),
            ("https://elnacional.com.do/nota/", "el_nacional"),
            ("https://hoy.com.do/nota/", "hoy"),
            ("https://www.elcaribe.com.do/nota", "el_caribe"),
            ("https://almomento.net/nota/", "al_momento"),
            ("https://eldia.com.do/nota/", "el_dia"),
            ("https://n.com.do/nota/", "n_digital"),
            ("https://acento.com.do/nota/", "acento"),
        ],
    )
    def test_maps_the_domain_to_the_registered_slug(self, url, expected):
        assert source_from_url(url) == expected

    def test_every_registered_scraper_is_reachable_by_domain(self):
        """Si se agrega un scraper sin feeds ni sitemaps, esto lo delata."""
        covered = {source_from_url(f"https://{d}/x") for d in _domains()}
        assert covered >= set(SCRAPERS)


def _domains() -> set[str]:
    from urllib.parse import urlparse

    out = set()
    for scraper in SCRAPERS.values():
        derived = [urlparse(u).netloc for u in list(scraper.feeds) + list(scraper.sitemaps)]
        for host in list(scraper.domains) + derived:
            out.add(host.lower().removeprefix("www."))
    return out - {""}


class TestUnknownOrUnusable:
    @pytest.mark.parametrize(
        "url",
        [
            "https://www.nytimes.com/nota",
            "no-es-una-url",
            "",
            "ftp://listindiario.com/x",
        ],
    )
    def test_returns_none_when_it_cannot_tell(self, url):
        """Devuelve None y deja decidir a quien llama: inventar un medio sería
        peor que admitir que no se sabe."""
        assert source_from_url(url) is None
