"""Scraper de Diario Libre.

Diario Libre publica feeds RSS por sección, así que reutilizamos el flujo
estándar de BaseScraper (descubrir por RSS + extraer con trafilatura).
"""
from __future__ import annotations

from odin.scrapers.base import BaseScraper

_BASE = "https://www.diariolibre.com/rss"


class DiarioLibreScraper(BaseScraper):
    source = "diario_libre"
    name = "Diario Libre"
    feeds = [
        f"{_BASE}/portada.xml",
        f"{_BASE}/actualidad.xml",
        f"{_BASE}/politica.xml",
        f"{_BASE}/economia.xml",
        f"{_BASE}/mundo.xml",
        f"{_BASE}/deportes.xml",
        f"{_BASE}/opinion.xml",
        f"{_BASE}/planeta.xml",
        f"{_BASE}/revista.xml",
    ]
